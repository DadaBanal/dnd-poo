"""Email intake: what arrived, what it became, and never the same ticket twice.

Reads a **drop of RFC 822 files** -- a directory a mail system delivers into --
and not an API. There is no API client in this repository and nowhere to put a
key: the TeamsWork keys were exposed in a screenshot, neither is ever written
down, and both should be rotated. A drop needs no credential at all.

Three rules, each answering something measured rather than imagined:

  * **Never the same ticket twice.** §13 records the double-creation as measured
    and prescribes aliasing `support@` onto `helpdesk@` to stop it. Aliasing
    fixes one cause; it does not make intake idempotent. So every message is
    written to `intake_message` exactly once by its Message-ID, and a message
    already spoken for is skipped on a re-run rather than creating a second
    ticket. Running intake twice over the same drop is a no-op.

  * **A reply continues a ticket, it does not open one.** Threading is by
    In-Reply-To and References first, because that is what mail clients
    actually set. Only when a message carries no usable thread header does the
    weaker requester+subject+window heuristic apply, and that one is INFERRED
    and says so.

  * **Nothing is dropped.** A message that cannot be placed is imported as
    UNCLASSIFIED and counted. The standing rule in this programme is that flags
    are counted, never filtered out, and a message silently discarded at intake
    is a request a hospital thinks it made.

PHI is scanned here too (§6.1): the finding names the shape and the field and
never repeats the value, and the message still imports.

Standard library only.
"""
from __future__ import annotations

import email
import email.policy
import email.utils
import hashlib
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from . import db, phi

# How close in time two messages from the same requester with the same subject
# have to be before the second is read as a resend rather than a new request.
# INFERRED, not measured: it is a heuristic of last resort, used only when a
# message carries no thread header at all.
DUPLICATE_WINDOW = timedelta(hours=24)


def _decode(value) -> str:
    """Header text as a plain string. Never raises on a malformed header -- a
    message with a broken Subject is still a message somebody sent."""
    if value is None:
        return ""
    try:
        return str(value).strip()
    except Exception:                                      # noqa: BLE001
        return ""


def normalise_subject(subject: str) -> str:
    """Strip the reply and forward prefixes so a thread keeps one identity.

    'RE: FW: Re: printer' and 'printer' are the same subject, and a duplicate
    guard that cannot see that is a duplicate guard that never fires.
    """
    text = _decode(subject)
    changed = True
    while changed:
        changed = False
        low = text.lower().lstrip()
        for prefix in ("re:", "fw:", "fwd:"):
            if low.startswith(prefix):
                text = text.lstrip()[len(prefix):].lstrip()
                changed = True
                break
    return " ".join(text.split())


def sender_of(message) -> str:
    """The bare address, lower-cased. 'Ward 3 <a@b>' and 'a@b' are one person."""
    _, address = email.utils.parseaddr(_decode(message.get("From")))
    return address.lower()


def received_at(message, *, fallback: datetime) -> datetime:
    raw = _decode(message.get("Date"))
    if raw:
        try:
            parsed = email.utils.parsedate_to_datetime(raw)
            if parsed is not None:
                return parsed.replace(tzinfo=None)
        except (TypeError, ValueError):
            pass
    return fallback


def message_id_of(message, *, raw_bytes: bytes) -> str:
    """The Message-ID, or a stable synthetic one.

    A message with no Message-ID still has to be identifiable, or it is
    reprocessed on every run and makes a ticket each time. Hashing the bytes
    gives the same id for the same message and a different one for a different
    message, which is exactly what the column is for.
    """
    mid = _decode(message.get("Message-ID"))
    if mid:
        return mid
    return "sha256:" + hashlib.sha256(raw_bytes).hexdigest()


def thread_parents(message) -> list[str]:
    """Message-IDs this message claims to continue, most specific first."""
    parents = []
    for header in ("In-Reply-To", "References"):
        value = _decode(message.get(header))
        for token in value.split():
            token = token.strip()
            if token.startswith("<") and token.endswith(">"):
                parents.append(token)
    # In-Reply-To first, then the References chain from newest backwards.
    return list(dict.fromkeys(parents))


def body_of(message) -> str:
    """The plain-text body, best effort. HTML-only mail yields its text part if
    there is one and an empty string otherwise; the raw HTML is not ticket text."""
    if message.is_multipart():
        for part in message.walk():
            if part.get_content_type() == "text/plain":
                try:
                    return part.get_content().strip()
                except Exception:                          # noqa: BLE001
                    continue
        return ""
    if message.get_content_type() == "text/plain":
        try:
            return message.get_content().strip()
        except Exception:                                  # noqa: BLE001
            return ""
    return ""


def _seen(conn: sqlite3.Connection, message_id: str):
    return conn.execute("SELECT * FROM intake_message WHERE message_id = ?",
                        (message_id,)).fetchone()


def _ticket_for_parent(conn: sqlite3.Connection, parents: list[str]):
    for parent in parents:
        row = conn.execute(
            "SELECT work_item_id FROM intake_message"
            " WHERE message_id = ? AND work_item_id IS NOT NULL", (parent,)).fetchone()
        if row:
            return parent, row["work_item_id"]
    return None, None


def _recent_same_subject(conn: sqlite3.Connection, sender: str, subject: str,
                         at: datetime):
    """The weaker guard, used only when there is no thread header. INFERRED."""
    cutoff = (at - DUPLICATE_WINDOW).isoformat(sep=" ", timespec="minutes")
    return conn.execute(
        "SELECT message_id, work_item_id FROM intake_message"
        "  WHERE from_address = ? AND subject = ? AND received_at >= ?"
        "    AND work_item_id IS NOT NULL"
        "  ORDER BY received_at DESC LIMIT 1",
        (sender, subject, cutoff)).fetchone()


def import_drop(conn: sqlite3.Connection, drop_dir, *, run_id: str,
                board_id: str | None = None, channel: str = "helpdesk",
                at: datetime | None = None) -> dict:
    """Import every message in a directory. Returns counts; raises on nothing.

    Losslessness is the invariant, as it is for the register and the desk
    export: every file produces exactly one `intake_message` row, and anything
    unplaceable is recorded and counted rather than skipped.
    """
    at = at or datetime.now()
    drop = Path(drop_dir)
    files = sorted(p for p in drop.iterdir() if p.is_file())

    if board_id is None:
        row = conn.execute(
            "SELECT board_id FROM board WHERE is_unrouted = 1").fetchone()
        board_id = row["board_id"] if row else None

    counts = {"files": len(files), "new": 0, "appended": 0, "duplicate": 0,
              "unclassified": 0, "already_seen": 0, "phi_flagged": 0}

    for path in files:
        raw = path.read_bytes()
        message = email.message_from_bytes(raw, policy=email.policy.default)
        mid = message_id_of(message, raw_bytes=raw)

        if _seen(conn, mid):
            # Idempotent: this message is already spoken for. Re-running intake
            # over the same drop must not make a second ticket.
            counts["already_seen"] += 1
            continue

        sender = sender_of(message)
        subject = normalise_subject(message.get("Subject"))
        when = received_at(message, fallback=at)
        stamp = when.isoformat(sep=" ", timespec="minutes")
        body = body_of(message)

        for code, severity, detail in phi.scan_fields(
                {"subject": subject, "body": body}):
            conn.execute(
                "INSERT INTO data_quality (run_id, subject_kind, subject_id, code,"
                " detail, severity) VALUES (?,?,?,?,?,?)",
                (run_id, "intake_message", mid, code, detail, severity))
            counts["phi_flagged"] += 1

        parents = thread_parents(message)
        parent_id, parent_ticket = _ticket_for_parent(conn, parents)

        if parent_ticket:
            _append_note(conn, parent_ticket, body or subject, sender, stamp)
            _record(conn, mid, stamp, sender, subject, channel, "APPENDED",
                    parent_ticket, parent_id, run_id)
            counts["appended"] += 1
            continue

        if not parents:
            recent = _recent_same_subject(conn, sender, subject, when)
            if recent:
                _append_note(conn, recent["work_item_id"], body or subject,
                             sender, stamp)
                _record(conn, mid, stamp, sender, subject, channel, "DUPLICATE",
                        None, recent["message_id"], run_id)
                counts["duplicate"] += 1
                continue

        if not board_id or not sender or not subject:
            # Nothing to hang a ticket on. Recorded and counted, never dropped.
            _record(conn, mid, stamp, sender, subject, channel, "UNCLASSIFIED",
                    None, None, run_id)
            conn.execute(
                "INSERT INTO data_quality (run_id, subject_kind, subject_id, code,"
                " detail, severity) VALUES (?,?,?,?,?,?)",
                (run_id, "intake_message", mid, "INTAKE_UNCLASSIFIED",
                 "no board to route to, or no sender or subject to open a ticket"
                 " with; imported and flagged rather than dropped", "ERROR"))
            counts["unclassified"] += 1
            continue

        ticket_id = _open_ticket(conn, board_id=board_id, summary=subject,
                                 requester=sender, body=body, at=when)
        _record(conn, mid, stamp, sender, subject, channel, "NEW_TICKET",
                ticket_id, None, run_id)
        counts["new"] += 1

    conn.commit()
    return counts


def _open_ticket(conn: sqlite3.Connection, *, board_id: str, summary: str,
                 requester: str, body: str, at: datetime) -> str:
    """One ticket, numbered from the one sequence (D4), admitted to its board.

    An email says nothing about who is affected or whether a patient is
    waiting, so it opens at I3/U3 (P4) and triage raises it — the same rule the
    record set for intake, now through the one door every ticket uses.
    """
    from . import tickets
    return tickets.open_ticket(conn, board_id=board_id, summary=summary,
                               impact="I3", urgency="U3", requested_by=requester,
                               description=body or None, at=at, source="EMAIL")


def _append_note(conn: sqlite3.Connection, work_item_id: str, body: str,
                 actor: str, stamp: str) -> None:
    conn.execute(
        "INSERT INTO ticket_event (work_item_id, occurred_at, kind, actor, detail,"
        " note_flag) VALUES (?,?,'INTAKE_REPLY',?,?,'DISCUSSION')",
        (work_item_id, stamp, actor, body))
    conn.execute("UPDATE ticket SET updated_at = ? WHERE work_item_id = ?",
                 (stamp, work_item_id))


def _record(conn: sqlite3.Connection, message_id: str, stamp: str, sender: str,
            subject: str, channel: str, disposition: str,
            work_item_id: str | None, duplicate_of: str | None,
            run_id: str) -> None:
    conn.execute(
        "INSERT INTO intake_message (message_id, received_at, from_address,"
        " subject, channel, disposition, work_item_id, duplicate_of, run_id)"
        " VALUES (?,?,?,?,?,?,?,?,?)",
        (message_id, stamp, sender or None, subject or None, channel,
         disposition, work_item_id, duplicate_of, run_id))

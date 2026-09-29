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
import re
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
            if part.get_content_type() == "text/plain" and not _is_file(part):
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


# ---------------------------------------------------------- attachments
#
# A file on a message goes onto the ticket the message became, through the
# same door as a file uploaded at the desk: sniffed, compressed, and PENDING
# review for patient information. A file the desk will not keep is recorded
# on the ticket and in data_quality, never silently dropped. The one thing
# not kept is a small inline image named by Content-ID -- a signature logo --
# and those are counted.

INLINE_LOGO_BYTES = 20 * 1024


def _is_file(part) -> bool:
    return part.get_content_disposition() == "attachment" or bool(part.get_filename())


def files_of(message):
    """(filename, bytes, is_inline_logo) for every file a message carries."""
    import mimetypes
    for part in message.walk():
        if part.is_multipart():
            continue
        kind = part.get_content_type()
        if kind == "message/rfc822":
            inner = part.get_payload()
            inner = inner[0] if isinstance(inner, list) else inner
            data = inner.as_bytes() if hasattr(inner, "as_bytes") else b""
            yield (part.get_filename() or "forwarded.eml"), data, False
            continue
        if kind in ("text/plain", "text/html") and not _is_file(part):
            continue                                   # the body, not a file
        data = part.get_payload(decode=True) or b""
        logo = (part.get_content_disposition() != "attachment" and bool(part.get("Content-ID"))
                and part.get_content_maintype() == "image" and len(data) < INLINE_LOGO_BYTES)
        name = part.get_filename() or ("attachment" + (mimetypes.guess_extension(kind) or ""))
        yield name, data, logo


def _keep_files(conn: sqlite3.Connection, message, work_item_id: str, *, sender: str,
                at: datetime, run_id: str, counts: dict) -> None:
    from . import attachments
    from .board import _event
    logos = 0
    for name, data, logo in files_of(message):
        if logo:
            logos += 1
            continue
        try:
            attachments.add(conn, work_item_id, data, name, actor=sender or "intake", at=at,
                            source="EMAIL")
            counts["files_kept"] += 1
        except attachments.Refused as exc:
            counts["files_refused"] += 1
            safe = attachments.safe_name(name)
            conn.execute(
                "INSERT INTO data_quality (run_id, subject_kind, subject_id, code,"
                " detail, severity) VALUES (?,?,?,?,?,?)",
                (run_id, "ticket", work_item_id, "ATTACHMENT_REFUSED", f"{safe}: {exc}", "WARN"))
            _event(conn, work_item_id, at.isoformat(sep=" ", timespec="minutes"), "ATTACHMENT",
                   "intake", f"file {safe} from email not kept: {exc}")
    if logos:
        counts["inline_skipped"] += logos
        conn.execute(
            "INSERT INTO data_quality (run_id, subject_kind, subject_id, code,"
            " detail, severity) VALUES (?,?,?,?,?,?)",
            (run_id, "ticket", work_item_id, "INLINE_IMAGE_SKIPPED",
             f"{logos} small inline image(s), signature logos, not kept", "INFO"))


# ---------------------------------------------------------- loop guards
#
# The reference PSA ignores mail from mailer-daemon, postmaster and MicrosoftExchange
# (VERIFIED, docs.connectwise.com/ConnectWise_Documentation/090/020/170/040,
# archived 2024-07-15). Here also RFC 3834 auto-replies (out-of-office), and the
# desk's own addresses. An auto-GENERATED message (a backup or monitoring alert)
# is not dropped: the reference PSA ships parsing presets for exactly those.
LOOP_SENDERS = ("mailer-daemon", "postmaster", "microsoftexchange")


def loop_guard(message, sender: str, own_addresses=()) -> str | None:
    """Why this message must not open or touch a ticket, or None."""
    local = (sender or "").split("@")[0]
    if any(local.startswith(x) for x in LOOP_SENDERS):
        return f"a delivery-system sender ({local})"
    if sender and sender in {a.lower() for a in own_addresses}:
        return "sent by the desk itself"
    auto = str(message.get("Auto-Submitted", "")).strip().lower()
    if auto.startswith("auto-replied"):
        return "an automatic reply (Auto-Submitted: auto-replied)"
    if str(message.get("X-Autoreply", "")).strip().lower() in ("yes", "true") or \
            str(message.get("Precedence", "")).strip().lower() == "auto_reply":
        return "an automatic reply"
    return None


# A ticket number anywhere in the subject: the second way a reply finds its
# ticket, for a client that dropped the thread headers. Dada PSA needs the
# token in one exact shape; any position works here.
_TOKEN = re.compile(r"\b([A-Z]{2,10}-\d{4,})\b")


def recipients_of(message) -> list[str]:
    """Every address the message was delivered to, lower case, in header
    order: To and Cc as the sender wrote them, then what the mail system
    stamped (Delivered-To, X-Original-To, Envelope-To, Resent-To). The
    stamped ones matter when Exchange aliased biomed@ onto the helpdesk
    mailbox: To still says biomed@, and that is the board's address."""
    out: list[str] = []
    for header in ("To", "Cc", "Delivered-To", "X-Original-To", "Envelope-To", "Resent-To", "X-Delivered-To"):
        for raw in message.get_all(header, []):
            for _, addr in email.utils.getaddresses([_decode(raw)]):
                a = (addr or "").strip().lower()
                if a and a not in out:
                    out.append(a)
    return out


def board_addresses(conn: sqlite3.Connection) -> dict[str, str]:
    """address (lower case) -> board_id, for every live board that claims one."""
    return {r["intake_address"].strip().lower(): r["board_id"] for r in conn.execute(
        "SELECT board_id, intake_address FROM board WHERE intake_address IS NOT NULL AND COALESCE(inactive, 0) = 0")
        if r["intake_address"] and r["intake_address"].strip()}


def route(conn: sqlite3.Connection, message, *, fallback: str | None) -> tuple[str | None, str | None]:
    """(board_id, the address that decided it). A board that claims one of
    the message's recipient addresses wins; else the board the run was
    given; else the unrouted board. A message to two boards' addresses goes
    to the first named in the headers, and the ticket says which."""
    claims = board_addresses(conn)
    for addr in recipients_of(message):
        if addr in claims:
            return claims[addr], addr
    return fallback, None


def subject_token(work_item_id: str) -> str:
    """What outbound mail puts in its subject so a reply can find its ticket."""
    return f"[{work_item_id}]"


def ticket_from_subject(conn: sqlite3.Connection, raw_subject) -> str | None:
    for token in _TOKEN.findall(_decode(raw_subject).upper()):
        if conn.execute("SELECT 1 FROM ticket WHERE work_item_id = ?", (token,)).fetchone():
            return token
    return None


def _closed_policy(conn: sqlite3.Connection, work_item_id: str, at: datetime):
    """For a reply to this ticket: ('OPEN', None) if it is open, ('REOPEN',
    status) or ('NEW_TICKET', None) per its board's policy if it is closed."""
    t = conn.execute(
        "SELECT t.closed_at, t.board_id, s.is_closed, b.closed_reply_policy,"
        "       b.reopen_within_days, b.reopen_status_id FROM ticket t"
        "  JOIN board b ON b.board_id = t.board_id"
        "  LEFT JOIN board_status s ON s.board_status_id = t.board_status_id"
        " WHERE t.work_item_id = ?", (work_item_id,)).fetchone()
    if not (t["closed_at"] or t["is_closed"]):
        return "OPEN", None
    if t["closed_reply_policy"] == "NEW_TICKET":
        return "NEW_TICKET", None
    if t["reopen_within_days"] and t["closed_at"]:
        closed = datetime.fromisoformat(t["closed_at"])
        if at - closed > timedelta(days=t["reopen_within_days"]):
            return "NEW_TICKET", None
    from .board import default_status
    return "REOPEN", t["reopen_status_id"] or default_status(conn, t["board_id"])


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
                at: datetime | None = None, own_addresses=()) -> dict:
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
    run_board = board_id
    # A board's own address is the desk's own address too: mail from it is
    # the desk talking, and never opens a ticket (the loop guard).
    own_addresses = list(own_addresses) + list(board_addresses(conn))

    counts = {"files": len(files), "new": 0, "appended": 0, "duplicate": 0,
              "unclassified": 0, "already_seen": 0, "phi_flagged": 0,
              "loop_guarded": 0, "reopened": 0, "reply_to_closed": 0,
              "files_kept": 0, "files_refused": 0, "inline_skipped": 0}

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
        board_id, to_address = route(conn, message, fallback=run_board)
        if to_address:
            counts["routed_by_address"] = counts.get("routed_by_address", 0) + 1

        for code, severity, detail in phi.scan_fields(
                {"subject": subject, "body": body}):
            conn.execute(
                "INSERT INTO data_quality (run_id, subject_kind, subject_id, code,"
                " detail, severity) VALUES (?,?,?,?,?,?)",
                (run_id, "intake_message", mid, code, detail, severity))
            counts["phi_flagged"] += 1

        guarded = loop_guard(message, sender, own_addresses)
        if guarded:
            # Recorded and counted like everything else; it just opens nothing.
            _record(conn, mid, stamp, sender, subject, channel, "UNCLASSIFIED",
                    None, None, run_id)
            conn.execute(
                "INSERT INTO data_quality (run_id, subject_kind, subject_id, code,"
                " detail, severity) VALUES (?,?,?,?,?,?)",
                (run_id, "intake_message", mid, "MAIL_LOOP_GUARD",
                 f"not turned into a ticket: {guarded}", "INFO"))
            counts["unclassified"] += 1
            counts["loop_guarded"] += 1
            continue

        parents = thread_parents(message)
        parent_id, parent_ticket = _ticket_for_parent(conn, parents)
        if not parent_ticket:
            parent_ticket = ticket_from_subject(conn, message.get("Subject"))

        if parent_ticket:
            action, reopen_to = _closed_policy(conn, parent_ticket, when)
            if action == "NEW_TICKET":
                # The board says a reply this late is new work. Open it, and
                # point back at the ticket it answered.
                ticket_id = _open_ticket(conn, board_id=board_id or _board_of(conn, parent_ticket),
                                         summary=subject or f"Reply to {parent_ticket}",
                                         requester=sender, body=body, at=when)
                from . import itil
                itil.link(conn, ticket_id, parent_ticket, "RELATED", actor="intake", at=when)
                _keep_files(conn, message, ticket_id, sender=sender, at=when, run_id=run_id,
                            counts=counts)
                _record(conn, mid, stamp, sender, subject, channel, "NEW_TICKET",
                        ticket_id, parent_id, run_id, to_address)
                counts["new"] += 1
                counts["reply_to_closed"] += 1
                continue
            _append_note(conn, parent_ticket, body or subject, sender, stamp)
            _keep_files(conn, message, parent_ticket, sender=sender, at=when, run_id=run_id,
                        counts=counts)
            if action == "REOPEN" and reopen_to:
                from .board import change_status
                change_status(conn, parent_ticket, reopen_to, at=when, actor="intake")
                conn.execute("UPDATE ticket SET closed_at = NULL WHERE work_item_id = ?",
                             (parent_ticket,))
                counts["reopened"] += 1
            _record(conn, mid, stamp, sender, subject, channel, "APPENDED",
                    parent_ticket, parent_id, run_id)
            counts["appended"] += 1
            continue

        if not parents:
            recent = _recent_same_subject(conn, sender, subject, when)
            if recent:
                _append_note(conn, recent["work_item_id"], body or subject,
                             sender, stamp)
                _keep_files(conn, message, recent["work_item_id"], sender=sender, at=when,
                            run_id=run_id, counts=counts)
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
        _keep_files(conn, message, ticket_id, sender=sender, at=when, run_id=run_id,
                    counts=counts)
        _record(conn, mid, stamp, sender, subject, channel, "NEW_TICKET",
                ticket_id, None, run_id, to_address)
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


def _board_of(conn: sqlite3.Connection, work_item_id: str) -> str:
    return conn.execute("SELECT board_id FROM ticket WHERE work_item_id = ?",
                        (work_item_id,)).fetchone()[0]


def _append_note(conn: sqlite3.Connection, work_item_id: str, body: str,
                 actor: str, stamp: str) -> None:
    conn.execute(
        "INSERT INTO ticket_event (work_item_id, occurred_at, kind, actor, detail,"
        " note_flag) VALUES (?,?,'INTAKE_REPLY',?,?,'DISCUSSION')",
        (work_item_id, stamp, actor, body))
    conn.execute("UPDATE ticket SET updated_at = ?, customer_updated = 1"
                 " WHERE work_item_id = ?", (stamp, work_item_id))


def _record(conn: sqlite3.Connection, message_id: str, stamp: str, sender: str,
            subject: str, channel: str, disposition: str,
            work_item_id: str | None, duplicate_of: str | None,
            run_id: str, to_address: str | None = None) -> None:
    conn.execute(
        "INSERT INTO intake_message (message_id, received_at, from_address,"
        " subject, channel, disposition, work_item_id, duplicate_of, run_id, to_address)"
        " VALUES (?,?,?,?,?,?,?,?,?,?)",
        (message_id, stamp, sender or None, subject or None, channel,
         disposition, work_item_id, duplicate_of, run_id, to_address))

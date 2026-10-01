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

from . import cc
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
    """address (lower case) -> board_id, for every live board that claims one.
    A board may claim several (058): helpdesk@, its help@ alias and support@
    can all land on one board."""
    return {r["address"]: r["board_id"] for r in conn.execute(
        "SELECT a.address, a.board_id FROM board_intake_address a JOIN board b ON b.board_id = a.board_id"
        " WHERE COALESCE(b.inactive, 0) = 0")}


def addresses_of(conn: sqlite3.Connection, board_id: str) -> list[str]:
    return [r["address"] for r in conn.execute(
        "SELECT address FROM board_intake_address WHERE board_id = ? ORDER BY address", (board_id,))]


_ADDRESS = re.compile(r"^[a-z0-9._%+'-]+@[a-z0-9-]+(\.[a-z0-9-]+)+$")


def set_addresses(conn: sqlite3.Connection, board_id: str, text: str, *, at: datetime, actor: str) -> list[str]:
    """The addresses a board claims, as written (commas, semicolons, spaces
    or new lines between them). Every one is checked before any is written:
    each must look like an address and none may be another board's."""
    from . import db
    wanted: list[str] = []
    for a in re.split(r"[\s,;]+", (text or "").lower()):
        if a and a not in wanted:
            wanted.append(a)
    for a in wanted:
        if not _ADDRESS.match(a) or len(a) > 200:
            raise ValueError(f"{a} does not look like an email address")
        other = conn.execute("SELECT b.display_name FROM board_intake_address a JOIN board b ON b.board_id = a.board_id"
                             " WHERE a.address = ? AND a.board_id <> ?", (a, board_id)).fetchone()
        if other:
            raise ValueError(f"{other['display_name']} already claims {a}")
    before = addresses_of(conn, board_id)
    if before == sorted(wanted):
        return before
    conn.execute("DELETE FROM board_intake_address WHERE board_id = ?", (board_id,))
    conn.execute("UPDATE board SET intake_address = NULL WHERE board_id = ?", (board_id,))   # the 053 column, unread
    for a in wanted:
        conn.execute("INSERT INTO board_intake_address (address, board_id) VALUES (?, ?)", (a, board_id))
    db.audit(conn, at=at.isoformat(sep=" ", timespec="minutes"), actor=actor, action="BOARD_INTAKE_ADDRESS",
             subject_kind="board", subject_id=board_id,
             detail="intake " + (", ".join(sorted(wanted)) if wanted else "none") + f" (was {', '.join(before) or 'none'})")
    return sorted(wanted)


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


EXCLUSION_KINDS = {"ADDRESS": "an address", "DOMAIN": "a domain", "SUBJECT": "a phrase in the subject"}


def exclusions(conn: sqlite3.Connection) -> list[dict]:
    return [dict(r) for r in conn.execute("SELECT * FROM mail_exclusion ORDER BY kind, pattern")]


def add_exclusion(conn: sqlite3.Connection, kind: str, pattern: str, *, note=None, at: datetime, actor: str) -> int:
    """A rule made once: mail from this address or domain, or with this
    phrase in its subject, is recorded and opens nothing."""
    kind = (kind or "").upper()
    if kind not in EXCLUSION_KINDS:
        raise ValueError("An exclusion is an ADDRESS, a DOMAIN or a SUBJECT phrase.")
    pat = " ".join(str(pattern or "").split()).lower()[:200]
    if not pat or (kind == "ADDRESS" and "@" not in pat) or (kind == "DOMAIN" and ("@" in pat or "." not in pat)):
        raise ValueError({"ADDRESS": "An address looks like someone@somewhere.", "DOMAIN": "A domain looks like somewhere.com.",
                          "SUBJECT": "A subject phrase is a few words."}[kind])
    if kind == "DOMAIN":
        from .contacts import PUBLIC_DOMAINS
        if pat in PUBLIC_DOMAINS or any(pat.endswith("." + d) for d in PUBLIC_DOMAINS):
            # Dada, 1 Oct 2026: yahoo, gmail "and all other generic emails" are
            # requesters. A rule on a public mail domain would turn every one
            # of them away; one sender is excluded by their address instead.
            raise ValueError(f"{pat} is a public mail domain: every requester on it would be turned away."
                             " Exclude the one address instead.")
    if conn.execute("SELECT 1 FROM mail_exclusion WHERE kind = ? AND pattern = ?", (kind, pat)).fetchone():
        raise ValueError("That exclusion already exists.")
    cur = conn.execute("INSERT INTO mail_exclusion (kind, pattern, note, created_at, created_by) VALUES (?,?,?,?,?)",
                       (kind, pat, (note or "").strip()[:400] or None, at.isoformat(sep=" ", timespec="minutes"), actor))
    from . import db
    db.audit(conn, at=at.isoformat(sep=" ", timespec="minutes"), actor=actor, action="MAIL_EXCLUSION_ADD",
             subject_kind="mail_exclusion", subject_id=str(cur.lastrowid), detail=f"{kind} {pat}")
    return cur.lastrowid


def remove_exclusion(conn: sqlite3.Connection, exclusion_id: int, *, at: datetime, actor: str) -> bool:
    row = conn.execute("SELECT kind, pattern FROM mail_exclusion WHERE exclusion_id = ?", (exclusion_id,)).fetchone()
    if row is None:
        return False
    conn.execute("DELETE FROM mail_exclusion WHERE exclusion_id = ?", (exclusion_id,))
    from . import db
    db.audit(conn, at=at.isoformat(sep=" ", timespec="minutes"), actor=actor, action="MAIL_EXCLUSION_REMOVE",
             subject_kind="mail_exclusion", subject_id=str(exclusion_id), detail=f"{row['kind']} {row['pattern']}")
    return True


def excluded_by(sender: str, subject: str, rules) -> str | None:
    """Why this message opens nothing under Setup > Email connector's
    exclusions, or None."""
    s = (sender or "").lower()
    subj = (subject or "").lower()
    for r in rules:
        k, pat = r["kind"], r["pattern"]
        if k == "ADDRESS" and s == pat:
            return f"excluded address {pat}"
        if k == "DOMAIN" and (s.endswith("@" + pat) or s.endswith("." + pat)):
            return f"excluded domain {pat}"
        if k == "SUBJECT" and pat in subj:
            return f"excluded subject phrase '{pat}'"
    return None


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
    # A .part file is one the pickup is still writing, or one a crash left
    # half-written: never a message to import.
    files = sorted(p for p in drop.iterdir() if p.is_file() and not p.name.endswith(".part"))

    if board_id is None:
        row = conn.execute(
            "SELECT board_id FROM board WHERE is_unrouted = 1").fetchone()
        board_id = row["board_id"] if row else None
    run_board = board_id
    rules = exclusions(conn)
    # A board's own address is the desk's own address too: mail from it is
    # the desk talking, and never opens a ticket (the loop guard).
    own_addresses = list(own_addresses) + list(board_addresses(conn))

    counts = {"files": len(files), "new": 0, "appended": 0, "duplicate": 0,
              "unclassified": 0, "already_seen": 0, "phi_flagged": 0,
              "loop_guarded": 0, "reopened": 0, "reply_to_closed": 0,
              "files_kept": 0, "files_refused": 0, "inline_skipped": 0}

    for path in files:
        # One message at a time, committed as it lands: a message the importer
        # cannot place is recorded with its error and the rest of the drop
        # still lands. Before this, one unexpected error lost the whole pass,
        # the pickup kept retrying the same files every minute, and every
        # later message waited behind it (Dada, 1 Oct 2026: "make sure it
        # ingests all").
        try:
            _import_one(conn, path, run_id=run_id, channel=channel, at=at, rules=rules,
                        own_addresses=own_addresses, run_board=run_board, counts=counts)
            conn.commit()
        except Exception as exc:                                 # noqa: BLE001
            conn.rollback()
            _record_failure(conn, path, exc, run_id=run_id, channel=channel, at=at, counts=counts)
            conn.commit()
    return counts


def _import_one(conn: sqlite3.Connection, path: Path, *, run_id: str, channel: str, at: datetime,
                rules, own_addresses, run_board: str | None, counts: dict) -> None:
    """One file of the drop: exactly one outcome, counted."""
    raw = path.read_bytes()
    message = email.message_from_bytes(raw, policy=email.policy.default)
    mid = message_id_of(message, raw_bytes=raw)

    if _seen(conn, mid):
        # Idempotent: this message is already spoken for. Re-running intake
        # over the same drop must not make a second ticket.
        counts["already_seen"] += 1
        return

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

    guarded = loop_guard(message, sender, own_addresses) or excluded_by(sender, subject, rules)
    if guarded:
        # Recorded and counted like everything else; it just opens nothing.
        _record(conn, mid, stamp, sender, subject, channel, "UNCLASSIFIED",
                None, None, run_id)
        conn.execute(
            "INSERT INTO data_quality (run_id, subject_kind, subject_id, code,"
            " detail, severity) VALUES (?,?,?,?,?,?)",
            (run_id, "intake_message", mid, "MAIL_EXCLUDED" if guarded.startswith("excluded") else "MAIL_LOOP_GUARD",
             f"not turned into a ticket: {guarded}", "INFO"))
        counts["unclassified"] += 1
        if guarded.startswith("excluded"):
            counts["excluded"] = counts.get("excluded", 0) + 1
        else:
            counts["loop_guarded"] += 1
        return

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
            cc.add_from_message(conn, ticket_id, message, sender=sender, own_addresses=own_addresses, at=when)
            _record(conn, mid, stamp, sender, subject, channel, "NEW_TICKET",
                    ticket_id, parent_id, run_id, to_address)
            counts["new"] += 1
            counts["reply_to_closed"] += 1
            return
        _append_note(conn, parent_ticket, body or subject, sender, stamp)
        _keep_files(conn, message, parent_ticket, sender=sender, at=when, run_id=run_id,
                    counts=counts)
        cc.add_from_message(conn, parent_ticket, message, sender=sender, own_addresses=own_addresses, at=when)
        if action == "REOPEN" and reopen_to:
            from .board import change_status
            change_status(conn, parent_ticket, reopen_to, at=when, actor="intake")
            conn.execute("UPDATE ticket SET closed_at = NULL WHERE work_item_id = ?",
                         (parent_ticket,))
            counts["reopened"] += 1
        _record(conn, mid, stamp, sender, subject, channel, "APPENDED",
                parent_ticket, parent_id, run_id)
        counts["appended"] += 1
        return

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
            return

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
        return

    ticket_id = _open_ticket(conn, board_id=board_id, summary=subject,
                             requester=sender, body=body, at=when)
    _keep_files(conn, message, ticket_id, sender=sender, at=when, run_id=run_id,
                counts=counts)
    cc.add_from_message(conn, ticket_id, message, sender=sender, own_addresses=own_addresses, at=when)
    _record(conn, mid, stamp, sender, subject, channel, "NEW_TICKET",
            ticket_id, None, run_id, to_address)
    from . import outbox
    outbox.settle_reply_from(conn, ticket_id)     # the acknowledgement answers from the address written to
    counts["new"] += 1


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


def _record_failure(conn: sqlite3.Connection, path: Path, exc: BaseException, *, run_id: str,
                    channel: str, at: datetime, counts: dict) -> None:
    """A message the importer could not place: an intake_message row
    (UNCLASSIFIED) and a data_quality ERROR naming the error and the file, so
    it is counted, visible on Setup > Email connector, and never silently
    dropped. The file keeps its name (a hash, never the subject); the pickup
    keeps it in its failed folder."""
    raw = path.read_bytes()
    try:
        message = email.message_from_bytes(raw, policy=email.policy.default)
        mid = message_id_of(message, raw_bytes=raw)
        sender, subject = sender_of(message), normalise_subject(message.get("Subject"))
    except Exception:                                            # noqa: BLE001
        mid, sender, subject = "sha256:" + hashlib.sha256(raw).hexdigest(), None, None
    stamp = at.isoformat(sep=" ", timespec="minutes")
    if not _seen(conn, mid):
        _record(conn, mid, stamp, sender, subject, channel, "UNCLASSIFIED", None, None, run_id)
    conn.execute(
        "INSERT INTO data_quality (run_id, subject_kind, subject_id, code, detail, severity) VALUES (?,?,?,?,?,?)",
        (run_id, "intake_message", mid, "INTAKE_ERROR",
         f"{type(exc).__name__}: {str(exc)[:160]}; file {path.name}; recorded, opened nothing", "ERROR"))
    counts["unclassified"] += 1
    counts["errors"] = counts.get("errors", 0) + 1


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


def why(conn: sqlite3.Connection, *, subject: str | None = None, sender: str | None = None,
        since: str | None = None) -> dict:
    """What intake did with the messages matching a subject fragment or a
    sender (Dada, 1 Oct 2026: two mails "arent being ingested"). Returns the
    rows intake saw, each with its disposition, ticket and findings, and the
    exclusion rule that would catch the sender, so "never arrived" and
    "arrived and was set aside" are told apart on the host."""
    if not (subject or sender):
        raise ValueError("give a subject fragment or a sender")
    where, args = [], []
    if subject:
        where.append("LOWER(COALESCE(i.subject, '')) LIKE ?"); args.append(f"%{subject.lower()}%")
    if sender:
        where.append("LOWER(COALESCE(i.from_address, '')) LIKE ?"); args.append(f"%{sender.lower()}%")
    if since:
        where.append("i.received_at >= ?"); args.append(since)
    rows = []
    for i in conn.execute(
            "SELECT i.message_id, i.received_at, i.from_address, i.to_address, i.subject, i.disposition,"
            "       i.work_item_id, i.run_id, t.board_id FROM intake_message i"
            "  LEFT JOIN ticket t ON t.work_item_id = i.work_item_id"
            f" WHERE {' AND '.join(where)} ORDER BY i.received_at DESC LIMIT 50", args):
        findings = [f"{r['code']} ({r['severity']}): {r['detail']}" for r in conn.execute(
            "SELECT code, severity, detail FROM data_quality WHERE (subject_kind = 'intake_message' AND subject_id = ?)"
            "    OR (subject_kind = 'ticket' AND subject_id = ?) ORDER BY finding_id",
            (i["message_id"], i["work_item_id"] or ""))]
        rows.append({**dict(i), "findings": findings})
    rules = exclusions(conn)
    probe = sender if (not sender or "@" in sender) else f"someone@{sender}"     # a bare domain is asked as a domain
    caught = excluded_by(probe or "", subject or "", rules) if sender else None
    return {"rows": rows, "exclusion": caught, "exclusions": len(rules), "claims": board_addresses(conn)}


def retry(conn: sqlite3.Connection, message_id: str, *, at: datetime, actor: str) -> str:
    """Forget a message intake set aside (UNCLASSIFIED: excluded, guarded, or
    an INTAKE_ERROR) so that a fresh pickup sync imports it again, after the
    cause (an exclusion rule, say) has been put right. A message that opened
    or joined a ticket is never forgotten: that would make a second ticket.
    Returns what was done."""
    from . import db
    row = conn.execute("SELECT disposition, subject, work_item_id FROM intake_message WHERE message_id = ?",
                       (message_id,)).fetchone()
    if row is None:
        raise LookupError(f"intake never saw {message_id}")
    if row["disposition"] != "UNCLASSIFIED":
        raise ValueError(f"{message_id} is {row['disposition']}"
                         + (f" on {row['work_item_id']}" if row["work_item_id"] else "") + ": nothing to retry")
    conn.execute("DELETE FROM data_quality WHERE subject_kind = 'intake_message' AND subject_id = ?", (message_id,))
    conn.execute("DELETE FROM intake_message WHERE message_id = ?", (message_id,))
    db.audit(conn, at=at.isoformat(sep=" ", timespec="minutes"), actor=actor, action="MAIL_RETRY",
             subject_kind="intake_message", subject_id=message_id,
             detail="set-aside message forgotten so the next pickup sync imports it again")
    return f"{message_id} forgotten; the next pickup sync from before it arrived imports it again"

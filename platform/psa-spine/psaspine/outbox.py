"""The notification outbox: what workflow rules asked to tell whom, and whether
it went.

The desk holds no mail credential. `scripts/Send-PmcNotifications.ps1` on
DND-SQL01 asks `psaspine outbox-pending` for what is due, sends each through
Microsoft Graph from the helpdesk mailbox (a certificate, and Exchange RBAC for
Applications scoping Mail.Send to that one mailbox), and reports back with
`psaspine outbox-mark`. The same shape as mail pickup, in the other direction.

A recipient is sent to only when it resolves to an address: an address as
written, or a contact whose AD account name or sign-in matches. Anything else is
NO_SENDER, never a guess, and the desk shows it. Only addresses in the allowed
domains are ever released, so a rule can never mail outside the hospital.

**The requester is told, and told nothing else.** When their ticket is opened,
and when a fulfiller writes a note they can read (Discussion, or a Resolution),
the requester gets one email: the ticket number, that it was opened or
updated, and a link to the portal. Never the summary, never the note: a note is
written for the portal, where sign-in and the §6.1 controls apply, and mail
leaves the building. A second update before the first has gone adds nothing,
Internal notes never send, and a board can switch it off
(`board.notify_requester`; unset means OFF, as Dada PSA leaves contact
emails off until a board turns them on). The portal's address is deployment
config (`PSA_PORTAL_URL` or `--portal-url`), never the repository.
"""
from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime

from . import richtext
from .contacts import email_of

STATUSES = ("SENT", "FAILED")
REQUESTER = "REQUESTER"
# Where a new ticket did come from a person who expects to hear back. API
# tickets come from monitoring; imported ones are history.
NOTIFY_ON_OPEN = ("PORTAL", "EMAIL", "PHONE", "WALK_UP", "DESK")
# The desk's own words per kind, when a board has not written its own (057:
# Setup > board > Emails). {board} is the name of the board that owns the
# request: a request may be for any department, so the email never says "IT".
# {ticket} is the reference, {actor} who did it, {when} the visit's time.
# There is no {summary} and no {note}: a subject and a body leave the building.
TEMPLATE_KINDS = {
    "OPENED": "Ticket opened, to the requester",
    "UPDATED": "Ticket updated, to the requester",
    "CLOSED": "Ticket closed, to the requester",
    "ASSIGNED": "Assigned, to the owner",
    "SCHEDULED": "A visit booked, to the member",
    "APPROVAL": "Approval asked, to the approver",
}
# 058 added six more for the mail cut-over: {requester} and {owner} are names
# (staff, never a patient), {status} the status's name, {status_text} what the
# portal says about it (board_status.customer_description), {link} the
# ticket on the portal, {date} the day it happened. Still no {summary}, no
# {note} and no requester's subject: those are Dada's call under 6.1.
PLACEHOLDERS = ("ticket", "board", "actor", "when", "requester", "status", "status_text", "owner", "link", "date",
                "hospital", "note")
# {note}: the technician's reply to the requester, in the Updated email only
# (Dada, 1 Oct 2026: "make sure the replies from the tech gets advised to the
# user on the email or on the portal"). It goes into the email only when the
# PHI scan finds nothing in it; otherwise the email says to read it on the
# portal. Elsewhere it is empty.
PLACEHOLDER_HELP = ", ".join("{" + p + "}" for p in PLACEHOLDERS)
# {hospital}: the name every requester email signs off with. Deployment
# config (PSA_HOSPITAL_NAME), else PMC's own name.
HOSPITAL = "Premiere Medical Center - Nueva Ecija"
# How every desk email to a requester ends: the board that has it, then the
# hospital. The sender adds the reference, the portal link and how to reply.
_SIGN = "\n\n{board}\n{hospital}"
_WARD = ("\n\nIf this is stopping care on the ward right now, call the helpdesk and quote {ticket}; "
         "an email can wait, a patient cannot.")
DEFAULTS = {
    "OPENED": ("We have your request",
               "Hello {requester},\n\n{board} has your request, as of {date}, and it is with {owner}. You do not "
               "need to do anything; we will email you as it moves." + _WARD + _SIGN),
    "UPDATED": ("{owner} has replied to your request",
                "Hello {requester},\n\n{owner} from {board} has replied to your request, as of {date}:\n\n{note}\n\n"
                "To answer, reply to this email and keep the reference in the subject." + _SIGN),
    "CLOSED": ("Your request is closed",
               "Hello {requester},\n\n{board} has closed your request, as of {date}. If it is not fixed, reply to "
               "this email and it reopens. On the portal you can tell us how we did, one to five." + _SIGN),
    "ASSIGNED": ("Assigned to you on {board}", "{ticket} on {board} was assigned to you by {actor}."),
    "SCHEDULED": ("Scheduled for you on {board}", "{ticket} on {board}: a visit booked for you by {actor}, {when}."),
    "APPROVAL": ("A request needs your approval",
                 "A request on the desk waits for your approval before the work is done. Sign in to the portal and "
                 "open Approvals to read it and decide, with a reason."),
}
REQUESTER_WORDS = {k: DEFAULTS[k] for k in ("OPENED", "UPDATED", "CLOSED")}   # kept for readers of 03x


class _Fill(dict):
    def __missing__(self, key):
        return "{" + key + "}"


def _placeholders(text: str) -> set[str]:
    import string
    names = set()
    for _, field, spec, conversion in string.Formatter().parse(text):
        if field is not None:
            # A conversion or a format spec ({owner!r}, {requester:>9999}) is
            # never a plain placeholder: refused, as an unknown name is.
            names.add(field if not spec and not conversion else field + "!")
    return names


def _checked(subject, body) -> tuple[str, str]:
    """A subject and body a board may save: both present, and no placeholder
    outside PLACEHOLDERS."""
    subj = " ".join(str(subject or "").split())[:120]
    text = str(body or "").replace("\r\n", "\n").strip()[:2000]
    if not subj or not text:
        raise ValueError("an email needs a subject and a body")
    try:
        unknown = (_placeholders(subj) | _placeholders(text)) - set(PLACEHOLDERS)
    except ValueError:
        raise ValueError(f"a placeholder is one of {PLACEHOLDER_HELP}; a brace on its own is written {{{{ }}}}")
    if unknown:
        raise ValueError(f"a placeholder is one of {PLACEHOLDER_HELP}; not " + ", ".join(sorted("{" + u + "}" for u in unknown)))
    return subj, text


def _name(conn: sqlite3.Connection, who: str | None) -> str:
    """A person's name for an email: the AD contact's or the member record's,
    else the part of the address before the @. Never a guess."""
    who = (who or "").strip()
    if not who:
        return ""
    if "@" in who:
        row = conn.execute("SELECT display_name FROM contact WHERE LOWER(email) = LOWER(?) AND display_name IS NOT NULL"
                           " ORDER BY inactive", (who,)).fetchone()
        if row is None:
            row = conn.execute("SELECT display_name FROM member WHERE LOWER(email) = LOWER(?) AND display_name IS NOT NULL",
                               (who,)).fetchone()
        return row["display_name"] if row else who.split("@", 1)[0]
    from .members import name_of
    return name_of(conn, who)


def _first(name: str) -> str:
    """A person's first name for an email (Dada, 1 Oct 2026: "use the first
    name", not the user name). "Susan Dolfo" -> Susan; "Dela Cruz, Thobie" ->
    Thobie; an identifier like thobie.delacruz -> Thobie; an address's local
    part the same way."""
    n = (name or "").strip()
    if not n:
        return ""
    if "@" in n:
        n = n.split("@", 1)[0]
    # A shared mailbox or a place ("Ward 3 Station", "ER Nurses Desk") is
    # addressed by its whole name: it has no first name.
    _PLACE = {"ward", "station", "nurse", "nurses", "desk", "department", "dept", "office", "unit", "clinic",
              "team", "er", "icu", "opd", "lab", "laboratory", "pharmacy", "radiology", "billing", "admin", "hr"}
    if any(ch.isdigit() for ch in n) or any(w.lower().strip(".,") in _PLACE for w in n.split()):
        return n
    if "," in n:                                    # "Last, First"
        n = n.split(",", 1)[1].strip()
    for sep in (".", "_", "-"):
        if sep in n and " " not in n:
            n = n.split(sep, 1)[0]
    first = n.split()[0] if n.split() else n
    return first if first[:1].isupper() else first.capitalize()


def _hospital() -> str:
    import os
    return " ".join((os.environ.get("PSA_HOSPITAL_NAME") or HOSPITAL).split())[:120]


def _values(conn: sqlite3.Connection, work_item_id: str, *, at: datetime, actor: str = "desk", when: str = "") -> dict:
    """Every placeholder's value for one ticket now. {link} stays a
    placeholder: the portal's address is the sender's config, filled in by
    pending()."""
    row = conn.execute(
        "SELECT t.requested_by, t.owner, b.display_name AS board, s.name AS status, s.customer_description"
        "  FROM ticket t JOIN board b ON b.board_id = t.board_id"
        "  LEFT JOIN board_status s ON s.board_status_id = t.board_status_id WHERE t.work_item_id = ?",
        (work_item_id,)).fetchone()
    if row is None:
        return {"ticket": work_item_id, "actor": actor, "when": when, "date": f"{at.day} {at:%B %Y}", "link": "{link}",
                "hospital": _hospital(), "note": ""}
    status = (row["status"] or "").lstrip(">")
    return {"ticket": work_item_id, "board": row["board"], "actor": actor, "when": when,
            "requester": _first(_name(conn, row["requested_by"])) or "there",
            "status": status, "status_text": row["customer_description"] or status,
            "owner": _first(_name(conn, row["owner"])) if row["owner"] else f"the {row['board']} team",
            "link": "{link}", "date": f"{at.day} {at:%B %Y}", "hospital": _hospital(), "note": ""}


def reply_from(conn: sqlite3.Connection, work_item_id: str) -> str | None:
    """The address a requester wrote to when their email opened this ticket,
    while a board still claims it: the desk answers from where it was asked.
    None for a ticket raised any other way, which the sender sends from its
    own mailbox."""
    row = conn.execute(
        "SELECT i.to_address FROM intake_message i JOIN board_intake_address a ON a.address = i.to_address"
        " WHERE i.work_item_id = ? AND i.disposition = 'NEW_TICKET' ORDER BY i.received_at", (work_item_id,)).fetchone()
    return row["to_address"] if row else None


def settle_reply_from(conn: sqlite3.Connection, work_item_id: str) -> None:
    """The 'we have your request' email is queued when the ticket opens, before
    intake has written which address the mail came to; once it has, the
    waiting email takes that address, so the first reply comes from where the
    requester wrote (058: an emailed ticket's acknowledgement was going out
    from the sender's own mailbox instead)."""
    sender = reply_from(conn, work_item_id)
    if sender:
        conn.execute("UPDATE notification SET from_address = ? WHERE work_item_id = ? AND from_address IS NULL"
                     " AND status = 'PENDING'", (sender, work_item_id))


def template(conn: sqlite3.Connection, board_id: str, kind: str) -> dict:
    """The words a board uses for one kind: its own row, else the desk's."""
    if kind not in TEMPLATE_KINDS:
        raise ValueError("no such email kind")
    row = conn.execute("SELECT subject, body, updated_at, updated_by FROM mail_template WHERE board_id = ? AND kind = ?",
                       (board_id, kind)).fetchone()
    if row is None:
        subject, body = DEFAULTS[kind]
        return {"kind": kind, "subject": subject, "body": body, "custom": False, "updated_at": None, "updated_by": None}
    return {"kind": kind, "subject": row["subject"], "body": row["body"], "custom": True,
            "updated_at": row["updated_at"], "updated_by": row["updated_by"]}


def set_template(conn: sqlite3.Connection, board_id: str, kind: str, *, subject: str, body: str,
                 at: datetime, actor: str) -> None:
    """A board writes its own words for one kind. Only the placeholders in
    PLACEHOLDERS are allowed: nothing here can pull a summary or a note into
    an email."""
    from . import db
    if kind not in TEMPLATE_KINDS:
        raise ValueError("no such email kind")
    subj, text = _checked(subject, body)
    stamp = at.isoformat(sep=" ", timespec="minutes")
    conn.execute("DELETE FROM mail_template WHERE board_id = ? AND kind = ?", (board_id, kind))
    conn.execute("INSERT INTO mail_template (board_id, kind, subject, body, updated_at, updated_by) VALUES (?,?,?,?,?,?)",
                 (board_id, kind, subj, text, stamp, actor))
    db.audit(conn, at=stamp, actor=actor, action="MAIL_TEMPLATE", subject_kind="board", subject_id=board_id,
             detail=f"{kind} email: own words")


def reset_template(conn: sqlite3.Connection, board_id: str, kind: str, *, at: datetime, actor: str) -> bool:
    from . import db
    if kind not in TEMPLATE_KINDS:
        raise ValueError("no such email kind")
    cur = conn.execute("DELETE FROM mail_template WHERE board_id = ? AND kind = ?", (board_id, kind))
    if cur.rowcount:
        db.audit(conn, at=at.isoformat(sep=" ", timespec="minutes"), actor=actor, action="MAIL_TEMPLATE",
                 subject_kind="board", subject_id=board_id, detail=f"{kind} email: the desk's words")
    return bool(cur.rowcount)


def words(conn: sqlite3.Connection, board_id: str, kind: str, **values) -> tuple[str, str]:
    """(subject without the reference token, body) with the placeholders filled."""
    tpl = template(conn, board_id, kind)
    fill = _Fill(values)
    return tpl["subject"].format_map(fill), tpl["body"].format_map(fill)


PORTAL_WORDS = "Sign in to the portal to read it."


def note_for_email(note: str | None) -> str:
    """The technician's words for the Updated email: as written when the PHI
    scan finds nothing, else a line to read them on the portal."""
    from . import phi
    text = str(note or "").strip()
    if not text or phi.scan(text, field="note"):
        return PORTAL_WORDS
    return text[:2000]


THREAD_LIMIT = 8      # the last exchanges; the portal has the whole thread
THREAD_TITLE = "Earlier in this request, newest first"


def conversation(conn: sqlite3.Connection, work_item_id: str, *, limit: int = THREAD_LIMIT) -> list[dict]:
    """The exchange the requester may read, newest first, as the portal shows
    it (Dada, 1 Oct 2026: "the discussion doesn't get carried over on the
    replies; the reply should be read on the email as well"): their own words
    (the first email, every reply by email or on the portal) and the desk's
    Discussion and Resolution notes. Never an Internal note, never a system
    event. Each entry is `who`, `when`, `raw` (as written) and `text` (as it
    may go into an email: the PHI gate applies to every entry on its own)."""
    rows = conn.execute(
        "SELECT e.occurred_at, e.kind, e.actor, e.detail, e.note_flag, e.is_resolution, e.body_format,"
        "       b.display_name AS board"
        "  FROM ticket_event e JOIN ticket t ON t.work_item_id = e.work_item_id"
        "  JOIN board b ON b.board_id = t.board_id"
        "  WHERE e.work_item_id = ?"
        "    AND (e.kind IN ('INTAKE','INTAKE_REPLY','PORTAL_REPLY') OR e.note_flag IN ('DISCUSSION','RESOLUTION'))"
        "    AND (e.note_flag IS NULL OR e.note_flag <> 'INTERNAL')"
        "    AND e.detail IS NOT NULL AND TRIM(e.detail) <> ''"
        "  ORDER BY e.ticket_event_id DESC LIMIT ?", (work_item_id, limit)).fetchall()
    out = []
    for e in rows:
        if e["kind"] in ("INTAKE", "INTAKE_REPLY", "PORTAL_REPLY"):
            who = "You"
        else:
            first = _first(_name(conn, e["actor"])) if e["actor"] and e["actor"] != "desk" else ""
            who = f"{first} from {e['board']}" if first else e["board"]
            if e["note_flag"] == "RESOLUTION" or e["is_resolution"]:
                who += " (resolution)"
        raw = str(e["detail"]).strip()
        # A rich note goes out as itself (6 Oct 2026). Until today every entry
        # was read as plain text, so a note written in the editor or an email's
        # own HTML arrived in the requester's mailbox as its markup -- "<p>",
        # "<br></p>", a whole <a href=...> spelled out (Dada's screenshot of
        # PMC-000165). The PHI gate reads the words, as it does everywhere; the
        # HTML part carries the reply alone, because the thread around it
        # already lists the earlier messages its fold would repeat.
        html = None
        if richtext.is_rich(e["body_format"]):
            from .web.templates import is_email_note
            prof = "email" if is_email_note(e["body_format"], e["kind"]) else "note"
            cleaned = richtext.clean(raw, limit=richtext.READ_MAX, profile=prof)
            if prof == "email" and "<details>" not in cleaned:
                cleaned = richtext.fold(cleaned, profile="email", limit=richtext.READ_MAX) or cleaned
            reply = richtext.unfolded(cleaned)
            words = richtext.text(reply)
            text = note_for_email(words)[:1200]
            if text != PORTAL_WORDS:
                html = richtext.email_inline(reply)
        else:
            text = note_for_email(raw)[:1200]
        out.append({"who": who, "when": (e["occurred_at"] or "")[:16], "raw": raw,
                    "text": text, "html": html})
    return out


def conversation_text(items: list[dict]) -> str:
    """The thread as plain text, under its title; empty when there is nothing."""
    if not items:
        return ""
    lines = [THREAD_TITLE, "-" * len(THREAD_TITLE)]
    for i in items:
        lines.append(f"{i['who']}, {i['when']}")
        lines.extend("    " + ln for ln in i["text"].splitlines() or [""])
        lines.append("")
    return "\n".join(lines).rstrip()


NOTE_SLOT = "NOTEWRITTENHERE"      # where the note's own formatting goes, in the HTML part


def queue_requester(conn: sqlite3.Connection, work_item_id: str, reason: str, *,
                    at: datetime, note: str | None = None, note_html: str | None = None) -> bool:
    """Queue the one email a requester gets. Returns whether one was queued.
    An UPDATED email carries the technician's reply (note) when it is clean."""
    from .board import _event
    from .intake import subject_token
    row = conn.execute(
        "SELECT t.requested_by, t.intake_source, t.board_id, b.notify_requester, b.display_name FROM ticket t"
        " JOIN board b ON b.board_id = t.board_id WHERE t.work_item_id = ?",
        (work_item_id,)).fetchone()
    if row is None or not row["notify_requester"] or not row["requested_by"]:
        return False                          # off until the board turns it on
    if reason == "OPENED" and row["intake_source"] not in NOTIFY_ON_OPEN:
        return False
    if not address_for(conn, row["requested_by"]):
        return False                          # only an address we can resolve now
    values = _values(conn, work_item_id, at=at)
    plain = note_for_email(note) if reason == "UPDATED" else ""
    values["note"] = plain
    headline, said = words(conn, row["board_id"], reason, **values)
    # 064: the same email with the note's own formatting in it. Built here,
    # once, so the sender has nothing to decide; the text above is always sent
    # as well, and a note the PHI gate held back carries no formatting either.
    said_html = None
    if reason == "UPDATED" and note_html and plain != PORTAL_WORDS:
        from .web.templates import rich as _rich
        marked = dict(values, note=NOTE_SLOT)
        _, shell = words(conn, row["board_id"], reason, **marked)
        # The note's own HTML, with the spacing the desk shows written inline:
        # Outlook gives a bare <p> most of a line of margin, which double-spaced
        # every note written one line per paragraph in the editor.
        said_html = _rich(shell, email=True).replace(NOTE_SLOT, richtext.email_inline(note_html))
    sender = reply_from(conn, work_item_id)
    stamp = at.isoformat(sep=" ", timespec="minutes")
    pending = conn.execute("SELECT notification_id FROM notification WHERE work_item_id = ? AND"
                           " recipient = ? AND recipient_role = ? AND status = 'PENDING'",
                           (work_item_id, row["requested_by"], REQUESTER)).fetchone()
    if pending:
        if reason not in ("CLOSED", "UPDATED"):
            return False                      # one unsent email already says so
        # A close outranks an unsent "we have it": the one email says the newer thing.
        conn.execute("UPDATE notification SET subject = ?, body = ?, body_html = ?, created_at = ?"
                     " WHERE notification_id = ?",
                     (f"{subject_token(work_item_id)} {headline}", said, said_html, stamp,
                      pending["notification_id"]))
        _event(conn, work_item_id, stamp, "NOTIFY", "desk",
               f"email to the requester queued: {headline.lower()}")
        return True
    conn.execute(
        "INSERT INTO notification (work_item_id, recipient, recipient_role, subject, body, body_html,"
        " created_at, status, from_address) VALUES (?,?,?,?,?,?,?,'PENDING',?)",
        (work_item_id, row["requested_by"], REQUESTER,
         f"{subject_token(work_item_id)} {headline}", said, said_html, stamp, sender))
    _event(conn, work_item_id, stamp, "NOTIFY", "desk",
           f"email to the requester queued: {headline.lower()}")
    return True


FRESH_LINK_SUBJECT = "A fresh link to your request"


def queue_fresh_link(conn: sqlite3.Connection, work_item_id: str, *, asked_by: str, at: datetime) -> str:
    """076: one email to the address a request came from, carrying its portal
    link, because somebody signed in to the portal found that an older link
    did not open it (every email sent before 075 went without the key).

    It goes only to the requester the ticket already has, never to the person
    asking, so asking proves nothing and gives nothing away; at most one an
    hour per request; not while an email about it is already waiting to go
    (that one carries the link). Returns what happened, for the audit trail:
    the person asking is told the same thing whatever it is."""
    from datetime import timedelta
    from .board import _event
    from .intake import subject_token
    row = conn.execute("SELECT t.requested_by, b.notify_requester FROM ticket t JOIN board b ON b.board_id = t.board_id"
                       " WHERE t.work_item_id = ?", (work_item_id,)).fetchone()
    if row is None:
        return "not sent: no such request"
    if not row["notify_requester"]:
        return "not sent: its board does not email requesters"
    if not row["requested_by"] or not address_for(conn, row["requested_by"]):
        return "not sent: no address the desk can email"
    since = (at - timedelta(hours=1)).isoformat(sep=" ", timespec="seconds")
    if conn.execute("SELECT 1 FROM audit_event WHERE action = 'PORTAL_LINK_REQUEST' AND subject_id = ?"
                    " AND occurred_at >= ? AND detail LIKE 'queued%'", (work_item_id, since)).fetchone():
        return "not sent: one was queued within the hour"
    if conn.execute("SELECT 1 FROM notification WHERE work_item_id = ? AND recipient = ? AND recipient_role IN (?, ?)"
                    " AND status = 'PENDING'", (work_item_id, row["requested_by"], REQUESTER, STATUS)).fetchone():
        return "not sent: an email about it is waiting to go, and carries the link"
    stamp = at.isoformat(sep=" ", timespec="minutes")
    body = ("Here is a fresh link to your request. It opens the request on the PMC Requests portal once you are "
            "signed in, whichever account you sign in with.\n\n"
            f"It was asked for on the portal by {asked_by or 'somebody signed in'}. If that was not you, there is "
            "nothing you need to do.")
    conn.execute(
        "INSERT INTO notification (work_item_id, recipient, recipient_role, subject, body,"
        " created_at, status, from_address) VALUES (?,?,?,?,?,?,'PENDING',?)",
        (work_item_id, row["requested_by"], REQUESTER, f"{subject_token(work_item_id)} {FRESH_LINK_SUBJECT}",
         body, stamp, reply_from(conn, work_item_id)))
    _event(conn, work_item_id, stamp, "NOTIFY", "desk",
           f"email to the requester queued: a fresh link to the request, asked for on the portal by {asked_by}")
    return "queued to the requester"


# 058: the requester hears as their ticket moves: at each status change,
# worded per status, and when someone picks the ticket up. Both share one
# unsent slot per ticket, so the requester reads where it is now.
STATUS = "REQUESTER_STATUS"
PICKED_UP = "PICKED_UP"
# The desk's words, by what kind of status it is. A board writes its own per
# status on its Emails tab; these are what it starts from.
STATUS_SHAPES = {
    "WAITING": "waits on the requester",
    "RESOLVED": "says it is fixed",
    "CLOSED": "closes the ticket",
    "OTHER": "moves the work on",
}
STATUS_DEFAULTS = {
    "WAITING": ("We need something from you",
                "Hello {requester},\n\nTo go on with your request, {owner} needs something from you: {status_text}."
                "\n\nReply to this email with it and keep the reference in the subject, so your reply joins your "
                "request. The ward, the room or the machine is all we need; never a patient's details." + _SIGN),
    "RESOLVED": ("We think your request is fixed",
                 "Hello {requester},\n\n{owner} thinks your request is fixed, as of {date}: {status_text}.\n\n"
                 "Please check it on the ward. If it is not fixed, reply to this email and it comes straight back "
                 "to us." + _SIGN),
    "CLOSED": DEFAULTS["CLOSED"],
    "OTHER": ("Your request: {status}",
              "Hello {requester},\n\nYour request has moved on, as of {date}: {status_text}.\n\n"
              "It is with {owner}. You do not need to do anything; we will email you when it moves again." + _WARD + _SIGN),
}
PICKUP_DEFAULT = ("{owner} has picked up your request",
                  "Hello {requester},\n\n{owner} from {board} has picked up your request, as of {date}, and is "
                  "working on it now.\n\nIf {owner} needs anything they will contact you. To add "
                  "something, reply to this email and keep the reference in the subject." + _WARD + _SIGN)
_WAITS_ON_REQUESTER = re.compile(r"requester|customer|from you|your reply", re.I)


def status_shape(status_row) -> str:
    """Which of the desk's words a status starts from. INFERRED from the
    status's settings and words; a board that disagrees writes its own."""
    if status_row["is_closed"]:
        return "CLOSED"
    if status_row["escalation_status"] == "RESOLVED":
        return "RESOLVED"
    if status_row["escalation_status"] == "NO_ESCALATION" and _WAITS_ON_REQUESTER.search(
            f"{status_row['name']} {status_row['customer_description'] or ''}"):
        return "WAITING"
    return "OTHER"


def _mail(conn, board_id: str, key: str, name: str, shape: str, default: tuple[str, str]) -> dict:
    row = conn.execute("SELECT * FROM status_mail WHERE board_id = ? AND mail_key = ?", (board_id, key)).fetchone()
    custom = bool(row and row["subject"] and row["body"])
    return {"board_status_id": key, "mail_key": key, "board_id": board_id, "name": name, "shape": shape,
            "enabled": bool(row and row["enabled"]),
            "subject": row["subject"] if custom else default[0], "body": row["body"] if custom else default[1],
            "default": default, "custom": custom,
            "updated_at": row["updated_at"] if row else None, "updated_by": row["updated_by"] if row else None}


def status_mail(conn: sqlite3.Connection, board_status_id: str) -> dict:
    """One status's email: whether it is on, and its words (the board's own,
    else the desk's for that kind of status)."""
    st = conn.execute("SELECT * FROM board_status WHERE board_status_id = ?", (board_status_id,)).fetchone()
    if st is None:
        raise ValueError("no such status")
    shape = status_shape(st)
    return _mail(conn, st["board_id"], board_status_id, st["name"].lstrip(">"), shape, STATUS_DEFAULTS[shape])


def pickup_mail(conn: sqlite3.Connection, board_id: str) -> dict:
    """The email a requester gets when someone picks their ticket up."""
    return _mail(conn, board_id, PICKED_UP, "Picked up", "PICKUP", PICKUP_DEFAULT)


def status_mails(conn: sqlite3.Connection, board_id: str) -> list[dict]:
    return [status_mail(conn, r["board_status_id"]) for r in conn.execute(
        "SELECT board_status_id FROM board_status WHERE board_id = ? AND inactive = 0 ORDER BY sort_order, name",
        (board_id,))]


def _set_mail(conn, cur: dict, *, enabled: bool, at: datetime, actor: str,
              subject: str | None, body: str | None, desk_words: bool) -> None:
    from . import db
    if desk_words:
        subj = text = None
    elif subject is None and body is None:
        subj, text = (cur["subject"], cur["body"]) if cur["custom"] else (None, None)
    else:
        subj, text = _checked(subject, body)
        if (subj, text) == tuple(cur["default"]):
            subj = text = None                  # the desk's words, kept as the desk's
    stamp = at.isoformat(sep=" ", timespec="minutes")
    conn.execute("DELETE FROM status_mail WHERE board_id = ? AND mail_key = ?", (cur["board_id"], cur["mail_key"]))
    conn.execute("INSERT INTO status_mail (board_id, mail_key, enabled, subject, body, updated_at, updated_by)"
                 " VALUES (?,?,?,?,?,?,?)", (cur["board_id"], cur["mail_key"], 1 if enabled else 0, subj, text, stamp, actor))
    db.audit(conn, at=stamp, actor=actor, action="STATUS_MAIL", subject_kind="board", subject_id=cur["board_id"],
             detail=f"{cur['name']}: " + ("on" if enabled else "off") + ("; own words" if subj else "; the desk's words"))


def set_status_mail(conn: sqlite3.Connection, board_status_id: str, *, enabled: bool, at: datetime, actor: str,
                    subject: str | None = None, body: str | None = None, desk_words: bool = False) -> dict:
    """Turn one status's email on or off, and keep the board's own words for
    it, or go back to the desk's (desk_words). Words are checked as a
    template's are."""
    _set_mail(conn, status_mail(conn, board_status_id), enabled=enabled, at=at, actor=actor,
              subject=subject, body=body, desk_words=desk_words)
    return status_mail(conn, board_status_id)


def set_pickup_mail(conn: sqlite3.Connection, board_id: str, *, enabled: bool, at: datetime, actor: str,
                    subject: str | None = None, body: str | None = None, desk_words: bool = False) -> dict:
    _set_mail(conn, pickup_mail(conn, board_id), enabled=enabled, at=at, actor=actor,
              subject=subject, body=body, desk_words=desk_words)
    return pickup_mail(conn, board_id)


def set_all_status_mails(conn: sqlite3.Connection, board_id: str, *, enabled: bool, at: datetime, actor: str) -> int:
    """Every live status on the board, and the picked-up email, on (or off)
    at once, keeping each one's words. Returns how many changed."""
    n = 0
    for m in status_mails(conn, board_id):
        if m["enabled"] != enabled:
            set_status_mail(conn, m["board_status_id"], enabled=enabled, at=at, actor=actor)
            n += 1
    if pickup_mail(conn, board_id)["enabled"] != enabled:
        set_pickup_mail(conn, board_id, enabled=enabled, at=at, actor=actor)
        n += 1
    return n


def _queue_moving(conn, work_item_id: str, mail_for, *, at: datetime, actor: str, said_what: str) -> bool:
    """Queue a requester's moving-on email (a status's, or picked up) when
    the board has it on. The same gates as every requester email: the board's
    requester switch, a person who expects to hear back, an address we can
    resolve. One unsent one per ticket: a newer one replaces it."""
    from .board import _event
    from .intake import subject_token
    row = conn.execute(
        "SELECT t.requested_by, t.intake_source, t.board_id, b.notify_requester FROM ticket t"
        " JOIN board b ON b.board_id = t.board_id WHERE t.work_item_id = ?", (work_item_id,)).fetchone()
    if row is None or not row["notify_requester"] or not row["requested_by"]:
        return False
    if row["intake_source"] not in NOTIFY_ON_OPEN or not address_for(conn, row["requested_by"]):
        return False
    try:
        mail = mail_for(row["board_id"])
    except ValueError:
        return False
    if not mail["enabled"] or mail["board_id"] != row["board_id"]:
        return False
    fill = _Fill(_values(conn, work_item_id, at=at, actor=actor))
    headline, said = mail["subject"].format_map(fill), mail["body"].format_map(fill)
    stamp = at.isoformat(sep=" ", timespec="minutes")
    subject = f"{subject_token(work_item_id)} {headline}"
    pending_row = conn.execute("SELECT notification_id FROM notification WHERE work_item_id = ? AND recipient_role = ?"
                               " AND status = 'PENDING'", (work_item_id, STATUS)).fetchone()
    if pending_row:
        conn.execute("UPDATE notification SET subject = ?, body = ?, created_at = ? WHERE notification_id = ?",
                     (subject, said, stamp, pending_row["notification_id"]))
    else:
        conn.execute(
            "INSERT INTO notification (work_item_id, recipient, recipient_role, subject, body, created_at, status,"
            " from_address) VALUES (?,?,?,?,?,?,'PENDING',?)",
            (work_item_id, row["requested_by"], STATUS, subject, said, stamp, reply_from(conn, work_item_id)))
    _event(conn, work_item_id, stamp, "NOTIFY", "desk", f"email to the requester queued: {said_what}")
    return True


def queue_status(conn: sqlite3.Connection, work_item_id: str, board_status_id: str, *,
                 at: datetime, actor: str) -> bool:
    """The requester's email for the status their ticket has just entered."""
    def mail_for(board_id):
        m = status_mail(conn, board_status_id)
        return m if m["board_id"] == board_id else {**m, "enabled": False}
    name = conn.execute("SELECT name FROM board_status WHERE board_status_id = ?", (board_status_id,)).fetchone()
    return _queue_moving(conn, work_item_id, mail_for, at=at, actor=actor,
                         said_what="now " + ((name["name"] if name else board_status_id).lstrip(">")))


def queue_pickup(conn: sqlite3.Connection, work_item_id: str, *, at: datetime, actor: str) -> bool:
    """The requester's email when someone picks their ticket up: the owner
    changed to a person after the ticket was opened."""
    return _queue_moving(conn, work_item_id, lambda b: pickup_mail(conn, b), at=at, actor=actor,
                         said_what="picked up")


def describe_board(conn: sqlite3.Connection, board_id: str) -> str:
    """Every email a board sends a requester, as it stands: the switch, the
    addresses, and each email's state, subject and words, the board's own or
    the desk's. For a person to read before mail moves; no ticket in it."""
    from .intake import addresses_of
    b = conn.execute("SELECT display_name, notify_requester FROM board WHERE board_id = ?", (board_id,)).fetchone()
    out = [f"{b['display_name']} ({board_id})",
           f"  email the requester: {'ON' if b['notify_requester'] else 'OFF (nothing below is sent)'}",
           f"  intake addresses: {', '.join(addresses_of(conn, board_id)) or 'none'}",
           f"  signed off as: {_hospital()}"]

    def one(title, state, subject, body, whose):
        out.append(f"\n  [{state}] {title} ({whose})")
        out.append(f"    Subject: [PMC-000000] {subject}")
        out.extend("    | " + line for line in body.split("\n"))

    for kind in ("OPENED", "UPDATED", "CLOSED"):
        t = template(conn, board_id, kind)
        one(TEMPLATE_KINDS[kind], "on" if b["notify_requester"] else "off", t["subject"], t["body"],
            "the board's words" if t["custom"] else "the desk's words")
    for m in [pickup_mail(conn, board_id)] + status_mails(conn, board_id):
        one("Picked up" if m["shape"] == "PICKUP" else f"Status: {m['name']}", "on" if m["enabled"] else "off",
            m["subject"], m["body"], "the board's words" if m["custom"] else "the desk's words")
    out.append("\n  The sender adds to each: the reference, the portal link, and how to reply.")
    return "\n".join(out)


OWNER = "OWNER"


def queue_owner(conn: sqlite3.Connection, work_item_id: str, *, at: datetime, actor: str) -> bool:
    """Dada PSA's "send to resource": the owner is emailed when a ticket is
    assigned to them, when the board says so (board.notify_owner). One unsent
    email per ticket and owner; the person who assigned it to themselves gets
    none. No summary in the subject: a subject leaves the desk (§6.1)."""
    from .board import _event
    from .intake import subject_token
    row = conn.execute(
        "SELECT t.owner, t.board_id, b.notify_owner, b.display_name FROM ticket t"
        " JOIN board b ON b.board_id = t.board_id WHERE t.work_item_id = ?", (work_item_id,)).fetchone()
    if row is None or not row["notify_owner"] or not row["owner"]:
        return False
    if (row["owner"] or "").lower() == (actor or "").lower():
        return False
    if not address_for(conn, row["owner"]):
        return False
    if conn.execute("SELECT 1 FROM notification WHERE work_item_id = ? AND recipient = ? AND recipient_role = ?"
                    " AND status = 'PENDING'", (work_item_id, row["owner"], OWNER)).fetchone():
        return False
    stamp = at.isoformat(sep=" ", timespec="minutes")
    headline, said = words(conn, row["board_id"], "ASSIGNED", **_values(conn, work_item_id, at=at, actor=actor))
    conn.execute(
        "INSERT INTO notification (work_item_id, recipient, recipient_role, subject, body, created_at, status)"
        " VALUES (?,?,?,?,?,?,'PENDING')",
        (work_item_id, row["owner"], OWNER, f"{subject_token(work_item_id)} {headline}", said, stamp))
    _event(conn, work_item_id, stamp, "NOTIFY", "desk", f"email to the owner queued: assigned to {row['owner']}")
    return True


RESOURCE = "RESOURCE"


def queue_resource(conn: sqlite3.Connection, work_item_id: str, member: str, *, at: datetime,
                   actor: str, note: bool = False) -> bool:
    """067: a member put on a ticket as a resource gets the same email the
    owner gets when it is assigned to them, on the same board switch
    (notify_owner). Nobody is emailed for adding themselves."""
    from .board import _event
    from .intake import subject_token
    row = conn.execute("SELECT t.board_id, b.notify_owner FROM ticket t JOIN board b ON b.board_id = t.board_id"
                       " WHERE t.work_item_id = ?", (work_item_id,)).fetchone()
    if row is None or not row["notify_owner"] or (member or "").lower() == (actor or "").lower():
        return False
    if not address_for(conn, member):
        return False
    role = "RESOURCE_NOTE" if note else RESOURCE
    if conn.execute("SELECT 1 FROM notification WHERE work_item_id = ? AND recipient = ? AND recipient_role = ?"
                    " AND status = 'PENDING'", (work_item_id, member, role)).fetchone():
        return False
    stamp = at.isoformat(sep=" ", timespec="minutes")
    if note:
        # The time entry window's "Email: Resources" tick (6 Oct 2026). That a
        # note was added, and by whom; the note itself stays on the desk.
        from . import members as _members
        headline = "A note was added"
        said = f"{_members.name_of(conn, actor)} added a note and time to {work_item_id}."
    else:
        headline, said = words(conn, row["board_id"], "ASSIGNED", **_values(conn, work_item_id, at=at, actor=actor))
    conn.execute(
        "INSERT INTO notification (work_item_id, recipient, recipient_role, subject, body, created_at, status)"
        " VALUES (?,?,?,?,?,?,'PENDING')",
        (work_item_id, member, role, f"{subject_token(work_item_id)} {headline}", said, stamp))
    _event(conn, work_item_id, stamp, "NOTIFY", "desk", f"email to a resource queued: {member}")
    return True


APPROVER = "APPROVER"


def queue_approver(conn: sqlite3.Connection, work_item_id: str, approver: str, *, at: datetime) -> bool:
    """049: one email to the person asked to approve a request, with the
    portal's Approvals page as the place to decide. No summary, no note:
    the words stay behind the sign-in."""
    from .board import _event
    from .intake import subject_token
    if not address_for(conn, approver):
        return False
    if conn.execute("SELECT 1 FROM notification WHERE work_item_id = ? AND recipient = ? AND recipient_role = ?"
                    " AND status = 'PENDING'", (work_item_id, approver, APPROVER)).fetchone():
        return False
    stamp = at.isoformat(sep=" ", timespec="minutes")
    b = conn.execute("SELECT t.board_id, b.display_name FROM ticket t JOIN board b ON b.board_id = t.board_id"
                     " WHERE t.work_item_id = ?", (work_item_id,)).fetchone()
    headline, said = words(conn, b["board_id"] if b else "", "APPROVAL", **_values(conn, work_item_id, at=at))
    conn.execute(
        "INSERT INTO notification (work_item_id, recipient, recipient_role, subject, body, created_at, status)"
        " VALUES (?,?,?,?,?,?,'PENDING')",
        (work_item_id, approver, APPROVER, f"{subject_token(work_item_id)} {headline}", said, stamp))
    _event(conn, work_item_id, stamp, "NOTIFY", "desk", f"email to the approver queued: {approver}")
    return True


SCHEDULED = "SCHEDULED"


def queue_scheduled(conn: sqlite3.Connection, schedule_id: int, *, at: datetime, actor: str) -> bool:
    """The reference PSA emails the member a schedule entry is for. Here under
    the same board switch as the owner's mail (board.notify_owner): one unsent
    email per visit and member, none to the person who booked themselves, and
    no summary in the subject (§6.1)."""
    from .board import _event
    from .intake import subject_token
    row = conn.execute(
        "SELECT s.member, s.starts_at, s.ends_at, s.work_item_id, t.board_id, b.notify_owner, b.display_name"
        "  FROM ticket_schedule s JOIN ticket t ON t.work_item_id = s.work_item_id"
        "  JOIN board b ON b.board_id = t.board_id WHERE s.schedule_id = ?", (schedule_id,)).fetchone()
    if row is None or not row["notify_owner"]:
        return False
    if (row["member"] or "").lower() == (actor or "").lower() or not address_for(conn, row["member"]):
        return False
    wid = row["work_item_id"]
    when = f"{row['starts_at']} to {row['ends_at'][11:]}"
    if conn.execute("SELECT 1 FROM notification WHERE work_item_id = ? AND recipient = ? AND recipient_role = ?"
                    " AND status = 'PENDING' AND body LIKE ?", (wid, row["member"], SCHEDULED, f"%{when}%")).fetchone():
        return False
    stamp = at.isoformat(sep=" ", timespec="minutes")
    headline, said = words(conn, row["board_id"], "SCHEDULED", **_values(conn, wid, at=at, actor=actor, when=when))
    conn.execute(
        "INSERT INTO notification (work_item_id, recipient, recipient_role, subject, body, created_at, status)"
        " VALUES (?,?,?,?,?,?,'PENDING')",
        (wid, row["member"], SCHEDULED, f"{subject_token(wid)} {headline}", said, stamp))
    _event(conn, wid, stamp, "NOTIFY", "desk", f"email to {row['member']} queued: a visit {when}")
    return True


def address_for(conn: sqlite3.Connection, recipient: str) -> str | None:
    if "@" in (recipient or ""):
        return email_of(recipient)
    row = conn.execute(
        "SELECT email FROM contact WHERE inactive = 0 AND email IS NOT NULL AND"
        " (lower(sam_account) = lower(?) OR lower(upn) = lower(?))",
        (recipient, recipient)).fetchall()
    return row[0]["email"] if len(row) == 1 else None


STAFF_ROLES = (OWNER, RESOURCE, SCHEDULED, "PAGE")
AWAY_WORDS = "asks for the PMC sign-in code, once a day"


def desk_addresses(desk_url: str | None = None, desk_away_url: str | None = None) -> tuple[str, str]:
    """The desk's two addresses for a link a member is sent: at PMC (the LAN
    name, PSA_PUBLIC_URL) and away from PMC (the published one behind the
    sign-in gate, PSA_DESK_AWAY_URL). Dada, 9 Oct 2026: both, since an email
    cannot know where it will be opened. Either may be empty; each must be
    https://. Links only: neither changes which origins the desk accepts.

    An address given on the command line that is not https:// is refused. One
    read from the environment that is not is quietly left out instead, so a
    setting meant for something else can never stop the email. Quietly: the
    senders read stderr into the JSON they parse (2>&1, SQL01 part 28), so a
    warning line would fail every pass."""
    return (_address(desk_url, "PSA_PUBLIC_URL", "desk"),
            _address(desk_away_url, "PSA_DESK_AWAY_URL", "desk away"))


def _address(given: str | None, env: str, what: str) -> str:
    """One https:// address: refused when given and wrong, quietly dropped
    when inherited from the environment and wrong (see desk_addresses)."""
    import os
    url = (given or "").strip().rstrip("/")
    if url and not url.lower().startswith("https://"):
        raise ValueError(f"the {what} address must be https://")
    if not url:
        url = (os.environ.get(env) or "").strip().rstrip("/")
        if url and not url.lower().startswith("https://"):
            url = ""
    return url


def desk_links(work_item_id: str, desk_url: str, desk_away_url: str) -> str:
    """The lines under a member's email: one per address that is set."""
    import urllib.parse
    path = "/ticket/" + urllib.parse.quote(work_item_id, safe="")
    lines = []
    if desk_url:
        lines.append(f"At PMC: {desk_url}{path}")
    if desk_away_url:
        lines.append(f"Away from PMC: {desk_away_url}{path} ({AWAY_WORDS})")
    return "\n".join(lines)


def pending(conn: sqlite3.Connection, *, allowed_domains: tuple[str, ...],
            limit: int = 50, dry_run: bool = False,
            portal_url: str | None = None, desk_url: str | None = None,
            desk_away_url: str | None = None, portal_away_url: str | None = None) -> list[dict]:
    """What is due now, as the sender needs it. Resolves addresses; anything that
    cannot be sent is marked here, so it never sits PENDING for ever."""
    import os
    portal_url = (portal_url or os.environ.get("PSA_PORTAL_URL") or "").rstrip("/")
    if portal_url and not portal_url.lower().startswith("https://"):
        raise ValueError("the portal address must be https://")
    desk_url, desk_away_url = desk_addresses(desk_url, desk_away_url)
    # Dada, 9 Oct 2026: the requester's and approver's links too, at PMC and
    # away (PSA_PORTAL_AWAY_URL, the published portal). Only beside a portal
    # address: an away link alone would be the only way in, and the portal
    # off the LAN is a separate decision.
    portal_away_url = _address(portal_away_url, "PSA_PORTAL_AWAY_URL", "portal away") if portal_url else ""
    allowed = tuple(d.lower().lstrip("@") for d in allowed_domains)
    # "*" releases every domain: a requester on yahoo or gmail hears back too
    # (Dada, 1 Oct 2026: "all other generic emails"). The words are the same
    # for everyone: a reference and a link, never the summary or a note.
    everyone = "*" in allowed
    # 076: the link a requester email carries is kept on it, so the desk can
    # say which link a person was sent without opening their mailbox. Only
    # once the step is in; before it, the email goes exactly as it did.
    from . import db as _db
    keep_link = portal_url and not dry_run and _db.column_exists(conn, "notification", "portal_link")
    out = []
    for n in conn.execute("SELECT * FROM notification WHERE status = 'PENDING' AND COALESCE(channel, 'EMAIL') = 'EMAIL'"
                          " ORDER BY notification_id LIMIT ?", (limit,)).fetchall():
        to = address_for(conn, n["recipient"])
        if not to or (not everyone and to.rsplit("@", 1)[1] not in allowed):
            if dry_run:
                continue
            conn.execute("UPDATE notification SET status = 'NO_SENDER' WHERE notification_id = ?",
                         (n["notification_id"],))
            continue
        # 075: the link carries the ticket's own key, so the holder of this
        # email opens this request on the portal whichever address they sign
        # in with (a shared mailbox, a Windows name the desk cannot tie to it).
        from . import tickets as _tickets
        key = f"/my/{n['work_item_id']}?k={_tickets.portal_key(conn, n['work_item_id']) or ''}" if portal_url else ""
        link = f"{portal_url}{key}" if portal_url else "the PMC Requests portal, under Your requests"
        away_link = f"{portal_away_url}{key}" if portal_away_url else ""
        subject = (n["subject"] or "").replace("{link}", link)
        thread = []
        if n["recipient_role"] in (REQUESTER, STATUS):
            where = link
            if keep_link:
                conn.execute("UPDATE notification SET portal_link = ? WHERE notification_id = ?",
                             (link, n["notification_id"]))
            # The exchange so far rides under every requester email, so the
            # reply reads in the mail as it does on the portal; what the body
            # itself already says is not said twice.
            said_already = n["body"] or ""
            thread = [x for x in conversation(conn, n["work_item_id"]) if x["raw"] not in said_already]
            body = (f"{(n['body'] or '').replace('{link}', link)}"
                    + (f"\n\n{conversation_text(thread)}" if thread else "")
                    + f"\n\nYour reference: {n['work_item_id']}\n"
                    f"See it here: {where}\n"
                    + (f"Away from PMC: {away_link}\n" if away_link else "")
                    + "\nTo add something, reply to this email "
                    "and keep the reference in the subject. The ward, the room or the "
                    "machine is all we need; a patient's details never are.")
        elif n["recipient_role"] == APPROVER:
            where = (f"{portal_url}/my/approvals" if portal_url else "the PMC Requests portal, under Approvals")
            body = f"{n['body'] or ''}\n\nThe reference: {n['work_item_id']}\nDecide it here: {where}"
            if portal_away_url:
                body += f"\nAway from PMC: {portal_away_url}/my/approvals"
        elif n["recipient_role"] == "PAGE":
            body = (n["body"] or "") + f"\n\nOpen the ticket on the desk and press Acknowledge: {n['work_item_id']}"
        else:
            body = (n["body"] or "") + f"\n\nOpen the ticket on the desk: {n['work_item_id']}"
        if n["recipient_role"] in STAFF_ROLES:
            # 9 Oct 2026: a member's email names the ticket on the desk at PMC
            # and away from it; the requester's and approver's stay on the portal
            links = desk_links(n["work_item_id"], desk_url, desk_away_url)
            if links:
                body += "\n" + links
        copied = []
        if n["recipient_role"] in (REQUESTER, STATUS):      # 061: the ticket's Cc hears what the requester hears
            from . import cc as _cc
            copied = [a for a in _cc.of(conn, n["work_item_id"]) if a != to and (everyone or a.rsplit("@", 1)[1] in allowed)]
        item = {"id": n["notification_id"], "to": to, "subject": subject,
                "body": body.replace("{link}", link), "ticket": n["work_item_id"],
                "from": n["from_address"] if n["recipient_role"] in (REQUESTER, STATUS) else None,
                "cc": copied}
        if n["recipient_role"] in (REQUESTER, STATUS):
            b = conn.execute("SELECT b.display_name FROM ticket t JOIN board b ON b.board_id = t.board_id WHERE t.work_item_id = ?",
                             (n["work_item_id"],)).fetchone()
            try:
                written = n["body_html"]
            except (KeyError, IndexError):
                written = None                       # a store that has not taken 064 yet
            item["html"] = html_email((n["body"] or "").replace("{link}", link), ticket=n["work_item_id"],
                                      link=link if portal_url else None, away_link=away_link or None,
                                      board=b["display_name"] if b else "", hospital=_hospital(),
                                      thread=thread,
                                      written=(written or "").replace("{link}", link) or None)
        out.append(item)
    if not dry_run:
        conn.commit()
    return out


def html_email(text: str, *, ticket: str, link: str | None, board: str, hospital: str,
               thread: list[dict] | None = None, written: str | None = None,
               away_link: str | None = None) -> str:
    """The same words as the plain text, laid out (Dada, 1 Oct 2026: "a better
    formatted email this looks kinda bland"): a header with the hospital and
    the board, the reference, the paragraphs, a button to the request, and
    the sign-off. Inline styles only, no image and no external request, so
    it reads the same in Outlook, a phone and a text-only client. Nothing
    is added that the text does not say."""
    import html as _h
    paras = [pp.strip() for pp in (text or "").split("\n\n") if pp.strip()]
    sign = ""
    if paras and paras[-1].startswith(("Your reference", "To add something")):
        pass
    # The one renderer the desk and the portal use, so a note that was written
    # with a heading or a list reads the same wherever it is read (Dada, 2 Oct
    # 2026). `email=True` carries the styles, because an email has no
    # stylesheet. The words are still the plain text that was stored.
    from .web.templates import rich as _rich
    # `written` is the same words with the note's own formatting already in
    # them (064); it is used in place of rendering the plain text again.
    body_html = written if written else "".join(_rich(pp, email=True) for pp in paras)
    if link and link.startswith("http"):
        body_html = body_html.replace(_h.escape(link), f'<a href="{_h.escape(link)}" style="color:#3d63dd">{_h.escape(link)}</a>')
    if thread:
        # The exchange so far: each entry quoted with who and when, newest
        # first, the same words as the plain text (the PHI gate already ran).
        entries = "".join(
            f'<div style="border-left:3px solid #d5dae6;padding:6px 12px;margin:0 0 10px">'
            f'<div style="font-size:12px;font-weight:600;color:#3b4454">{_h.escape(i["who"])}'
            f'<span style="font-weight:400;color:#6b7785"> &middot; {_h.escape(i["when"])}</span></div>'
            f'<div style="font-size:14px;line-height:1.5;color:#1f2430">'
            f'{i.get("html") or _rich(i["text"], email=True)}</div></div>'
            for i in thread)
        body_html += (f'<div style="margin:18px 0 4px;font-size:12px;letter-spacing:.3px;text-transform:uppercase;color:#6b7785">'
                      f'{_h.escape(THREAD_TITLE)}</div>{entries}')
    button = (f'<p style="margin:18px 0 6px"><a href="{_h.escape(link)}" style="display:inline-block;background:#3d63dd;color:#ffffff;'
              f'text-decoration:none;font-weight:600;font-size:14px;padding:10px 18px;border-radius:8px">See your request</a></p>'
              if link and link.startswith("http") else "")
    if button and away_link and away_link.startswith("http"):
        # 9 Oct 2026: the same request from outside PMC, plainer, beside it
        button = button.replace("</p>", f' <a href="{_h.escape(away_link)}" style="display:inline-block;color:#3d63dd;'
                                f'text-decoration:none;font-weight:600;font-size:14px;padding:9px 16px;border-radius:8px;'
                                f'border:1px solid #3d63dd;margin-left:6px">Away from PMC</a></p>', 1)
    return (
        '<!doctype html><html><body style="margin:0;padding:0;background:#f4f5f8;font-family:Segoe UI,Arial,sans-serif">'
        '<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f4f5f8;padding:24px 12px">'
        '<tr><td align="center">'
        '<table role="presentation" width="600" cellspacing="0" cellpadding="0" style="max-width:600px;width:100%;background:#ffffff;'
        'border:1px solid #e3e6ee;border-radius:12px;overflow:hidden">'
        f'<tr><td style="background:#1f2a5a;padding:18px 24px;color:#ffffff">'
        f'<div style="font-size:12px;letter-spacing:.4px;text-transform:uppercase;opacity:.8">{_h.escape(hospital)}</div>'
        f'<div style="font-size:18px;font-weight:650;margin-top:2px">{_h.escape(board)}</div></td></tr>'
        f'<tr><td style="padding:22px 24px 6px">'
        f'<div style="display:inline-block;font-size:12px;font-weight:600;color:#3d63dd;background:#e9eefc;border-radius:999px;'
        f'padding:3px 10px;margin-bottom:14px">Reference {_h.escape(ticket)}</div>'
        f'{body_html}{button}</td></tr>'
        '<tr><td style="padding:12px 24px 20px;font-size:12px;line-height:1.5;color:#6b7785;border-top:1px solid #eef0f5">'
        'Reply to this email to add something, and keep the reference in the subject. The ward, the room or the machine is all '
        'we need; a patient\'s details never are.</td></tr>'
        '</table></td></tr></table></body></html>')


def mark(conn: sqlite3.Connection, notification_id: int, status: str, *, at: datetime) -> bool:
    if status not in STATUSES:
        raise ValueError(f"status must be one of {STATUSES}")
    cur = conn.execute("UPDATE notification SET status = ?, sent_at = ? WHERE notification_id = ?"
                       " AND status = 'PENDING'",
                       (status, at.isoformat(sep=" ", timespec="seconds") if status == "SENT"
                        else None, notification_id))
    conn.commit()
    return bool(cur.rowcount)


def as_json(items: list[dict]) -> str:
    return json.dumps(items, ensure_ascii=True)

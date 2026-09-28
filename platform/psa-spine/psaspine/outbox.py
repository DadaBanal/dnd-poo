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
import sqlite3
from datetime import datetime

from .contacts import email_of

STATUSES = ("SENT", "FAILED")
REQUESTER = "REQUESTER"
# Where a new ticket did come from a person who expects to hear back. API
# tickets come from monitoring; imported ones are history.
NOTIFY_ON_OPEN = ("PORTAL", "EMAIL", "PHONE", "WALK_UP", "DESK")
REQUESTER_WORDS = {
    "OPENED": ("We have your request",
               "We have your request and it is in the queue. You do not need to do "
               "anything; we will update you here as it moves."),
    # {board} is the name of the board that owns the request: a request may be
    # for any department, so the email never says "IT".
    "UPDATED": ("Your request has been updated",
                "{board} has added an update to your request. Sign in to the portal to read it."),
    "CLOSED": ("Your request is closed",
               "{board} has closed your request. If it is not fixed, reply to this email and it "
               "reopens. On the portal you can tell us how we did, one to five."),
}


def queue_requester(conn: sqlite3.Connection, work_item_id: str, reason: str, *,
                    at: datetime) -> bool:
    """Queue the one email a requester gets. Returns whether one was queued."""
    from .board import _event
    from .intake import subject_token
    row = conn.execute(
        "SELECT t.requested_by, t.intake_source, b.notify_requester, b.display_name FROM ticket t"
        " JOIN board b ON b.board_id = t.board_id WHERE t.work_item_id = ?",
        (work_item_id,)).fetchone()
    if row is None or not row["notify_requester"] or not row["requested_by"]:
        return False                          # off until the board turns it on
    if reason == "OPENED" and row["intake_source"] not in NOTIFY_ON_OPEN:
        return False
    if not address_for(conn, row["requested_by"]):
        return False                          # only an address we can resolve now
    headline, said = REQUESTER_WORDS[reason]
    said = said.format(board=row["display_name"])
    stamp = at.isoformat(sep=" ", timespec="minutes")
    pending = conn.execute("SELECT notification_id FROM notification WHERE work_item_id = ? AND"
                           " recipient = ? AND recipient_role = ? AND status = 'PENDING'",
                           (work_item_id, row["requested_by"], REQUESTER)).fetchone()
    if pending:
        if reason != "CLOSED":
            return False                      # one unsent email already says so
        # A close outranks an unsent "we have it": the one email says the newer thing.
        conn.execute("UPDATE notification SET subject = ?, body = ?, created_at = ? WHERE notification_id = ?",
                     (f"{subject_token(work_item_id)} {headline}", said, stamp, pending["notification_id"]))
        _event(conn, work_item_id, stamp, "NOTIFY", "desk",
               f"email to the requester queued: {headline.lower()}")
        return True
    conn.execute(
        "INSERT INTO notification (work_item_id, recipient, recipient_role, subject, body,"
        " created_at, status) VALUES (?,?,?,?,?,?,'PENDING')",
        (work_item_id, row["requested_by"], REQUESTER,
         f"{subject_token(work_item_id)} {headline}", said, stamp))
    _event(conn, work_item_id, stamp, "NOTIFY", "desk",
           f"email to the requester queued: {headline.lower()}")
    return True


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
    conn.execute(
        "INSERT INTO notification (work_item_id, recipient, recipient_role, subject, body, created_at, status)"
        " VALUES (?,?,?,?,?,?,'PENDING')",
        (work_item_id, row["owner"], OWNER, f"{subject_token(work_item_id)} Assigned to you on {row['display_name']}",
         f"{work_item_id} on {row['display_name']} was assigned to you by {actor}.", stamp))
    _event(conn, work_item_id, stamp, "NOTIFY", "desk", f"email to the owner queued: assigned to {row['owner']}")
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
        "SELECT s.member, s.starts_at, s.ends_at, s.work_item_id, b.notify_owner, b.display_name"
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
    conn.execute(
        "INSERT INTO notification (work_item_id, recipient, recipient_role, subject, body, created_at, status)"
        " VALUES (?,?,?,?,?,?,'PENDING')",
        (wid, row["member"], SCHEDULED, f"{subject_token(wid)} Scheduled for you on {row['display_name']}",
         f"{wid} on {row['display_name']}: a visit booked for you by {actor}, {when}.", stamp))
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


def pending(conn: sqlite3.Connection, *, allowed_domains: tuple[str, ...],
            limit: int = 50, dry_run: bool = False,
            portal_url: str | None = None) -> list[dict]:
    """What is due now, as the sender needs it. Resolves addresses; anything that
    cannot be sent is marked here, so it never sits PENDING for ever."""
    import os
    portal_url = (portal_url or os.environ.get("PSA_PORTAL_URL") or "").rstrip("/")
    if portal_url and not portal_url.lower().startswith("https://"):
        raise ValueError("the portal address must be https://")
    allowed = tuple(d.lower().lstrip("@") for d in allowed_domains)
    out = []
    for n in conn.execute("SELECT * FROM notification WHERE status = 'PENDING'"
                          " ORDER BY notification_id LIMIT ?", (limit,)).fetchall():
        to = address_for(conn, n["recipient"])
        if not to or to.rsplit("@", 1)[1] not in allowed:
            if dry_run:
                continue
            conn.execute("UPDATE notification SET status = 'NO_SENDER' WHERE notification_id = ?",
                         (n["notification_id"],))
            continue
        if n["recipient_role"] == REQUESTER:
            where = (f"{portal_url}/my/{n['work_item_id']}" if portal_url
                     else "the PMC Requests portal, under Your requests")
            body = (f"{n['body'] or ''}\n\nYour reference: {n['work_item_id']}\n"
                    f"See it here: {where}\n\nTo add something, reply to this email "
                    "and keep the reference in the subject. The ward, the room or the "
                    "machine is all we need; a patient's details never are.")
        else:
            body = (n["body"] or "") + f"\n\nOpen the ticket on the desk: {n['work_item_id']}"
        out.append({"id": n["notification_id"], "to": to, "subject": n["subject"],
                    "body": body, "ticket": n["work_item_id"]})
    if not dry_run:
        conn.commit()
    return out


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

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
(`board.notify_requester` = 0; unset means on). The portal's address is
deployment config (`PSA_PORTAL_URL` or `--portal-url`), never the repository.
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
    "UPDATED": ("Your request has been updated",
                "IT has added an update to your request. Sign in to the portal to read it."),
}


def queue_requester(conn: sqlite3.Connection, work_item_id: str, reason: str, *,
                    at: datetime) -> bool:
    """Queue the one email a requester gets. Returns whether one was queued."""
    from .board import _event
    from .intake import subject_token
    row = conn.execute(
        "SELECT t.requested_by, t.intake_source, b.notify_requester FROM ticket t"
        " JOIN board b ON b.board_id = t.board_id WHERE t.work_item_id = ?",
        (work_item_id,)).fetchone()
    if row is None or row["notify_requester"] == 0 or not row["requested_by"]:
        return False
    if reason == "OPENED" and row["intake_source"] not in NOTIFY_ON_OPEN:
        return False
    if not address_for(conn, row["requested_by"]):
        return False                          # only an address we can resolve now
    if conn.execute("SELECT 1 FROM notification WHERE work_item_id = ? AND recipient = ?"
                    " AND recipient_role = ? AND status = 'PENDING'",
                    (work_item_id, row["requested_by"], REQUESTER)).fetchone():
        return False                          # one unsent email already says so
    headline, said = REQUESTER_WORDS[reason]
    stamp = at.isoformat(sep=" ", timespec="minutes")
    conn.execute(
        "INSERT INTO notification (work_item_id, recipient, recipient_role, subject, body,"
        " created_at, status) VALUES (?,?,?,?,?,?,'PENDING')",
        (work_item_id, row["requested_by"], REQUESTER,
         f"{subject_token(work_item_id)} {headline}", said, stamp))
    _event(conn, work_item_id, stamp, "NOTIFY", "desk",
           f"email to the requester queued: {headline.lower()}")
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
                     else "the IT portal, under Your requests")
            body = (f"{n['body'] or ''}\n\nYour reference: {n['work_item_id']}\n"
                    f"See it here: {where}\n\nTo add something, reply to this email "
                    "and keep the reference in the subject. Please do not send patient "
                    "details by email.")
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

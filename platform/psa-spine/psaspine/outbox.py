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
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime

from .contacts import email_of

STATUSES = ("SENT", "FAILED")


def address_for(conn: sqlite3.Connection, recipient: str) -> str | None:
    if "@" in (recipient or ""):
        return email_of(recipient)
    row = conn.execute(
        "SELECT email FROM contact WHERE inactive = 0 AND email IS NOT NULL AND"
        " (lower(sam_account) = lower(?) OR lower(upn) = lower(?))",
        (recipient, recipient)).fetchall()
    return row[0]["email"] if len(row) == 1 else None


def pending(conn: sqlite3.Connection, *, allowed_domains: tuple[str, ...],
            limit: int = 50, dry_run: bool = False) -> list[dict]:
    """What is due now, as the sender needs it. Resolves addresses; anything that
    cannot be sent is marked here, so it never sits PENDING for ever."""
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
        out.append({"id": n["notification_id"], "to": to, "subject": n["subject"],
                    "body": (n["body"] or "") + f"\n\nOpen the ticket on the desk: {n['work_item_id']}",
                    "ticket": n["work_item_id"]})
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

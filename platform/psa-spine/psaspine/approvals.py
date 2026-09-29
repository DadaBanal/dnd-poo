"""Request approvals (049): a manager says yes before the desk does the work.

A new user account, an access change, a licence: the desk should not do it on
the requester's word alone. A department names its approver (Setup ›
Departments); a catalogue pair can require approval; a technician can ask for
one by hand. A request parks the ticket in the board's "Awaiting approval"
status (a waiting status, so the resolve clock pauses), emails the approver,
and shows on the approver's portal under Approvals. The decision, with a
reason, goes on the ticket as a note the requester can read, and the ticket
comes back to the status it was in. Decisions are appended, never edited, and
every step is audited.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime

from . import db
from .contacts import email_of

STATUSES = {"PENDING": "Waiting", "APPROVED": "Approved", "DECLINED": "Declined", "WITHDRAWN": "Withdrawn"}
AWAITING = "Awaiting approval"
CLOSED_STATES = ("RESOLVED", "CLOSED", "CANCELLED")


class Refused(ValueError):
    """A sentence for the person; nothing was written."""


def _stamp(at: datetime) -> str:
    return at.isoformat(sep=" ", timespec="minutes")


def _email(value) -> str:
    e = (value or "").strip().lower()
    if not e or "@" not in e or " " in e or len(e) > 200:
        raise Refused("An approver is an email address, e.g. head.nursing@pmcne.ph.")
    return e


def get(conn: sqlite3.Connection, approval_id: int):
    return conn.execute("SELECT * FROM approval WHERE approval_id = ?", (approval_id,)).fetchone()


def pending(conn: sqlite3.Connection, work_item_id: str):
    return conn.execute("SELECT * FROM approval WHERE work_item_id = ? AND status = 'PENDING'"
                        " ORDER BY approval_id DESC LIMIT 1", (work_item_id,)).fetchone()


def for_ticket(conn: sqlite3.Connection, work_item_id: str):
    return conn.execute("SELECT * FROM approval WHERE work_item_id = ? ORDER BY approval_id", (work_item_id,)).fetchall()


def approver_for(conn: sqlite3.Connection, work_item_id: str) -> str | None:
    """The requester's department's approver, when the desk knows the
    requester as a contact and the department names one."""
    t = conn.execute("SELECT requested_by FROM ticket WHERE work_item_id = ?", (work_item_id,)).fetchone()
    if t is None or not t["requested_by"]:
        return None
    who = (email_of(t["requested_by"]) or t["requested_by"]).lower()
    c = conn.execute("SELECT department FROM contact WHERE inactive = 0 AND (LOWER(email) = ? OR LOWER(upn) = ?"
                     " OR LOWER(sam_account) = ?)", (who, who, who)).fetchone()
    if c is None or not c["department"]:
        return None
    d = conn.execute("SELECT approver FROM department WHERE name = ?", (c["department"],)).fetchone()
    return d["approver"] if d and d["approver"] else None


def _awaiting_status(conn, board_id: str) -> str | None:
    row = conn.execute("SELECT board_status_id FROM board_status WHERE board_id = ? AND LOWER(name) = LOWER(?)"
                       " AND COALESCE(inactive, 0) = 0", (board_id, AWAITING)).fetchone()
    return row[0] if row else None


def request(conn: sqlite3.Connection, work_item_id: str, *, approver, reason: str | None = None,
            at: datetime, actor: str) -> int:
    """Ask a person to approve the ticket. The ticket parks in Awaiting
    approval where the board has that status, the approver is emailed, and
    the ticket says so."""
    from . import board as engine
    from . import outbox
    from .board import _event
    tk = conn.execute("SELECT board_id, board_status_id, state FROM ticket WHERE work_item_id = ?",
                      (work_item_id,)).fetchone()
    if tk is None:
        raise Refused("No such ticket.")
    if tk["state"] in CLOSED_STATES:
        raise Refused("A closed ticket needs no approval.")
    if pending(conn, work_item_id) is not None:
        raise Refused("An approval is already waiting on this ticket.")
    email = _email(approver)
    reason = " ".join((reason or "").split())[:500] or None
    stamp = _stamp(at)
    park = _awaiting_status(conn, tk["board_id"])
    return_to = None
    if park and park != tk["board_status_id"]:
        return_to = tk["board_status_id"]
        engine.change_status(conn, work_item_id, park, at=at, actor=actor)
    cur = conn.execute(
        "INSERT INTO approval (work_item_id, approver, requested_at, requested_by, reason, status, return_status_id)"
        " VALUES (?,?,?,?,?,'PENDING',?)", (work_item_id, email, stamp, actor, reason, return_to))
    aid = cur.lastrowid
    _event(conn, work_item_id, stamp, "UPDATED", actor,
           f"approval requested from {email}" + (f": {reason}" if reason else ""))
    outbox.queue_approver(conn, work_item_id, email, at=at)
    db.audit(conn, at=stamp, actor=actor, action="APPROVAL", subject_kind="approval", subject_id=str(aid),
             detail=f"requested from {email} on {work_item_id}")
    engine.touch(conn, work_item_id, at)
    return aid


def _return(conn, row, *, at: datetime, actor: str) -> None:
    """Back to the status the ticket was in, if it is still parked."""
    from . import board as engine
    tk = conn.execute("SELECT board_id, board_status_id FROM ticket WHERE work_item_id = ?",
                      (row["work_item_id"],)).fetchone()
    park = _awaiting_status(conn, tk["board_id"]) if tk else None
    if not (row["return_status_id"] and park and tk["board_status_id"] == park):
        return
    ok = conn.execute("SELECT 1 FROM board_status WHERE board_status_id = ? AND board_id = ? AND COALESCE(inactive, 0) = 0",
                      (row["return_status_id"], tk["board_id"])).fetchone()
    if ok:
        engine.change_status(conn, row["work_item_id"], row["return_status_id"], at=at, actor=actor)


def decide(conn: sqlite3.Connection, approval_id: int, decision: str, *, identities, at: datetime,
           note: str | None = None):
    """The approver's yes or no, with a reason. Only the person it was sent to
    decides it; a decline says why. The decision goes on the ticket as a
    Discussion note, so the requester reads it and the desk sees it."""
    from .board import add_note
    row = get(conn, approval_id)
    if row is None:
        raise Refused("No such approval.")
    if decision not in ("APPROVE", "DECLINE"):
        raise Refused("A decision is Approve or Decline.")
    if row["status"] != "PENDING":
        raise Refused(f"This approval was already {STATUSES[row['status']].lower()}.")
    ids = {(i or "").lower() for i in identities}
    if row["approver"].lower() not in ids:
        raise Refused("This approval is for someone else to decide.")
    note = " ".join((note or "").split())[:500]
    if decision == "DECLINE" and not note:
        raise Refused("A decline says why, so the desk and the requester know.")
    status = "APPROVED" if decision == "APPROVE" else "DECLINED"
    stamp = _stamp(at)
    conn.execute("UPDATE approval SET status = ?, decided_at = ?, decided_by = ?, note = ? WHERE approval_id = ?",
                 (status, stamp, row["approver"], note or None, approval_id))
    _return(conn, row, at=at, actor=row["approver"])
    word = "Approved" if status == "APPROVED" else "Declined"
    add_note(conn, row["work_item_id"], body=f"{word} by {row['approver']}" + (f": {note}" if note else "."),
             flag="DISCUSSION", actor=row["approver"], at=at)
    db.audit(conn, at=stamp, actor=row["approver"], action="APPROVAL", subject_kind="approval",
             subject_id=str(approval_id), detail=f"{status.lower()} on {row['work_item_id']}" + (f": {note}" if note else ""))
    return get(conn, approval_id)


def withdraw(conn: sqlite3.Connection, approval_id: int, *, at: datetime, actor: str):
    """The desk takes the question back; the ticket returns to where it was."""
    from .board import _event
    row = get(conn, approval_id)
    if row is None:
        raise Refused("No such approval.")
    if row["status"] != "PENDING":
        raise Refused(f"This approval was already {STATUSES[row['status']].lower()}.")
    stamp = _stamp(at)
    conn.execute("UPDATE approval SET status = 'WITHDRAWN', decided_at = ?, decided_by = ? WHERE approval_id = ?",
                 (stamp, actor, approval_id))
    _return(conn, row, at=at, actor=actor)
    _event(conn, row["work_item_id"], stamp, "UPDATED", actor, f"approval request to {row['approver']} withdrawn")
    db.audit(conn, at=stamp, actor=actor, action="APPROVAL", subject_kind="approval", subject_id=str(approval_id),
             detail=f"withdrawn on {row['work_item_id']}")
    return get(conn, approval_id)


def waiting_for(conn: sqlite3.Connection, identities):
    """What a person has been asked to decide, oldest first."""
    ids = sorted({(i or "").lower() for i in identities if i})
    if not ids:
        return []
    return conn.execute(
        "SELECT a.*, w.name AS summary, t.requested_by AS raised_by, b.display_name AS board_name FROM approval a"
        " JOIN ticket t ON t.work_item_id = a.work_item_id JOIN work_item w ON w.work_item_id = a.work_item_id"
        " JOIN board b ON b.board_id = t.board_id"
        f" WHERE a.status = 'PENDING' AND LOWER(a.approver) IN ({','.join('?' * len(ids))})"
        " ORDER BY a.requested_at, a.approval_id", ids).fetchall()


def decided_by(conn: sqlite3.Connection, identities, *, limit: int = 20):
    ids = sorted({(i or "").lower() for i in identities if i})
    if not ids:
        return []
    return conn.execute(
        "SELECT a.*, w.name AS summary FROM approval a JOIN work_item w ON w.work_item_id = a.work_item_id"
        f" WHERE a.status IN ('APPROVED', 'DECLINED') AND LOWER(a.approver) IN ({','.join('?' * len(ids))})"
        " ORDER BY a.decided_at DESC, a.approval_id DESC LIMIT ?", ids + [limit]).fetchall()


def needs_approval(conn: sqlite3.Connection, work_item_id: str) -> bool:
    row = conn.execute("SELECT i.needs_approval FROM ticket t JOIN catalogue_item i ON i.catalogue_item_id = t.catalogue_item_id"
                       " WHERE t.work_item_id = ?", (work_item_id,)).fetchone()
    return bool(row and row[0])


def maybe_request(conn: sqlite3.Connection, work_item_id: str, *, at: datetime, actor: str) -> str:
    """When the ticket's item requires approval and none is waiting or given:
    ask the requester's department's approver. Returns REQUESTED, ALREADY,
    NOT_NEEDED or NO_APPROVER (then the ticket says who to set up)."""
    from .board import _event
    if not needs_approval(conn, work_item_id):
        return "NOT_NEEDED"
    if conn.execute("SELECT 1 FROM approval WHERE work_item_id = ? AND status IN ('PENDING', 'APPROVED')",
                    (work_item_id,)).fetchone():
        return "ALREADY"
    approver = approver_for(conn, work_item_id)
    if not approver:
        _event(conn, work_item_id, _stamp(at), "UPDATED", actor,
               "this item needs an approval, but the requester's department names no approver"
               " (Setup › Departments); ask for one by hand on the Approval card")
        return "NO_APPROVER"
    request(conn, work_item_id, approver=approver, reason="the request's item needs approval", at=at, actor=actor)
    return "REQUESTED"

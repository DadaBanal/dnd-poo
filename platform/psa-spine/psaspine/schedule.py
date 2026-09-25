"""Scheduled visits (032): who goes where, when, on which ticket.

ConnectWise's schedule entry, kept to what a hospital desk needs: a member, a
start and an end, a note, on a ticket. The ticket records the visit as an
event; Dispatch shows a day by member so two people are not sent to the same
ward at the same hour. Times are the desk's own local timestamps, entered from
the browser's date-time control.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime


class Refused(ValueError):
    """The entry breaks a rule; the sentence says which."""


def _stamp(at: datetime) -> str:
    return at.isoformat(sep=" ", timespec="minutes")


def parse_local(text: str) -> datetime:
    """'YYYY-MM-DDTHH:MM' from a datetime-local input, or the desk's own form."""
    text = (text or "").strip().replace("T", " ")
    try:
        return datetime.strptime(text[:16], "%Y-%m-%d %H:%M")
    except ValueError:
        raise Refused("a time reads YYYY-MM-DD HH:MM")


def entries_for(conn: sqlite3.Connection, work_item_id: str):
    return conn.execute("SELECT * FROM ticket_schedule WHERE work_item_id = ? ORDER BY starts_at",
                        (work_item_id,)).fetchall()


def day(conn: sqlite3.Connection, boards, on: str):
    """Every entry starting on a day, on the boards given, with its ticket."""
    if not boards:
        return []
    marks = ",".join("?" * len(boards))
    return conn.execute(
        "SELECT s.*, w.name AS summary, t.board_id, t.priority, t.state"
        "  FROM ticket_schedule s JOIN ticket t USING (work_item_id) JOIN work_item w USING (work_item_id)"
        f" WHERE substr(s.starts_at, 1, 10) = ? AND t.board_id IN ({marks})"
        " ORDER BY s.member, s.starts_at", (on, *boards)).fetchall()


def add(conn: sqlite3.Connection, work_item_id: str, *, member: str, starts_at: datetime,
        ends_at: datetime, note: str | None, actor: str, at: datetime) -> int:
    from .board import _event, touch
    member = (member or "").strip()
    if not member:
        raise Refused("a visit needs a person")
    if ends_at <= starts_at:
        raise Refused("a visit ends after it starts")
    if (ends_at - starts_at).total_seconds() > 16 * 3600:
        raise Refused("a visit is at most 16 hours; book two")
    if conn.execute("SELECT 1 FROM ticket WHERE work_item_id = ?", (work_item_id,)).fetchone() is None:
        raise LookupError(f"no ticket {work_item_id!r}")
    clash = conn.execute(
        "SELECT s.work_item_id FROM ticket_schedule s WHERE LOWER(s.member) = LOWER(?)"
        " AND s.starts_at < ? AND s.ends_at > ? LIMIT 1",
        (member, _stamp(ends_at), _stamp(starts_at))).fetchone()
    if clash:
        raise Refused(f"{member} is already booked then, on {clash['work_item_id']}")
    cur = conn.execute(
        "INSERT INTO ticket_schedule (work_item_id, member, starts_at, ends_at, note, created_at,"
        " created_by) VALUES (?,?,?,?,?,?,?)",
        (work_item_id, member, _stamp(starts_at), _stamp(ends_at), (note or "").strip()[:400] or None,
         _stamp(at), actor))
    _event(conn, work_item_id, _stamp(at), "SCHEDULE", actor,
           f"visit scheduled: {member}, {_stamp(starts_at)} to {ends_at.strftime('%H:%M')}"
           + (f" — {(note or '').strip()[:120]}" if (note or "").strip() else ""))
    touch(conn, work_item_id, at)
    return cur.lastrowid


def remove(conn: sqlite3.Connection, schedule_id: int, *, actor: str, at: datetime) -> str | None:
    from .board import _event, touch
    row = conn.execute("SELECT * FROM ticket_schedule WHERE schedule_id = ?", (schedule_id,)).fetchone()
    if row is None:
        return None
    conn.execute("DELETE FROM ticket_schedule WHERE schedule_id = ?", (schedule_id,))
    _event(conn, row["work_item_id"], _stamp(at), "SCHEDULE", actor,
           f"visit cancelled: {row['member']}, {row['starts_at']}")
    touch(conn, row["work_item_id"], at)
    return row["work_item_id"]

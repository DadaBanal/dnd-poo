"""Timesheets and time approval (046): a week of one person's time entries,
submitted by them and decided by somebody else.

The uplift claim (§5.2) rests on time entries, and a finance function reading
them will ask who approved them. So every entry belongs to one timesheet: the
week (Monday to Sunday) of the day it was worked, by the person who performed
it. A sheet is OPEN while the week is being written, SUBMITTED when that person
says it is complete, APPROVED or REJECTED by a time administrator who is not
that person, and reopened only with a note. A submitted or approved week takes
no new entries. Every decision is appended, never edited, and audited.

Utilisation is hours recorded against hours a week a person is expected to
record (Setup, per member; 40 unless set). It is the team's own figure; the
client's capacity denominator for the uplift stays in capacity_declaration.
"""
from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta

from . import db

STATUSES = {"OPEN": "Open", "SUBMITTED": "Submitted", "APPROVED": "Approved", "REJECTED": "Rejected"}
LOCKED = ("SUBMITTED", "APPROVED")
DEFAULT_HOURS_PER_WEEK = 40.0
HOURS = "COALESCE(te.actual_hours, te.band_hours)"


class Refused(ValueError):
    """A sentence for the person; nothing was written."""


def _stamp(at: datetime) -> str:
    return at.isoformat(sep=" ", timespec="minutes")


def week_of(day) -> date:
    """The Monday of the week a day falls in."""
    if isinstance(day, datetime):
        day = day.date()
    elif isinstance(day, str):
        try:
            day = date.fromisoformat(day.strip()[:10])
        except ValueError:
            raise Refused("A week is picked by a date in it, e.g. 2026-09-28.") from None
    return day - timedelta(days=day.weekday())


def week_end(week_start: date) -> date:
    return week_start + timedelta(days=6)


def get(conn: sqlite3.Connection, member: str, week_start: date):
    return conn.execute("SELECT * FROM timesheet WHERE LOWER(member) = LOWER(?) AND week_start = ?",
                        (member, week_start.isoformat())).fetchone()


def by_id(conn: sqlite3.Connection, timesheet_id: int):
    return conn.execute("SELECT * FROM timesheet WHERE timesheet_id = ?", (timesheet_id,)).fetchone()


def ensure(conn: sqlite3.Connection, member: str, week_start: date, *, at: datetime):
    """The sheet for a member's week, made OPEN on first sight."""
    row = get(conn, member, week_start)
    if row is None:
        conn.execute("INSERT OR IGNORE INTO timesheet (member, week_start, status, created_at) VALUES (?,?,'OPEN',?)",
                     (member, week_start.isoformat(), _stamp(at)))
        row = get(conn, member, week_start)
    return row


def entries(conn: sqlite3.Connection, member: str, week_start: date):
    """The member's entries in the week, with the ticket each is on."""
    a, b = week_start.isoformat(), week_end(week_start).isoformat()
    return conn.execute(
        f"SELECT te.*, {HOURS} AS hours, w.name AS summary, t.board_id AS board_id, b.display_name AS board_name"
        " FROM time_entry te JOIN work_item w ON w.work_item_id = te.work_item_id"
        " LEFT JOIN ticket t ON t.work_item_id = te.work_item_id"
        " LEFT JOIN board b ON b.board_id = t.board_id"
        " WHERE LOWER(te.performed_by) = LOWER(?) AND te.worked_on >= ? AND te.worked_on <= ?"
        " ORDER BY te.worked_on, te.time_entry_id", (member, a, b)).fetchall()


def totals(rows) -> dict:
    days: dict[str, float] = {}
    by_charge: dict[str, float] = {}
    total = 0.0
    for r in rows:
        h = float(r["hours"] or 0)
        days[r["worked_on"]] = days.get(r["worked_on"], 0.0) + h
        by_charge[r["charge_method"]] = by_charge.get(r["charge_method"], 0.0) + h
        total += h
    return {"days": {k: round(v, 2) for k, v in days.items()},
            "by_charge": {k: round(v, 2) for k, v in by_charge.items()}, "total": round(total, 2)}


# ------------------------------------------------------------ the lock

def lock_reason(conn: sqlite3.Connection, member: str, worked_on) -> str | None:
    """Why no time may be added for this person on this day, in a sentence,
    or None. A submitted or approved week is closed to new entries."""
    try:
        ws = week_of(worked_on)
    except Refused:
        return None
    row = get(conn, member, ws)
    if row is not None and row["status"] in LOCKED:
        return (f"{member}'s timesheet for the week of {ws.isoformat()} is "
                f"{STATUSES[row['status']].lower()}; a time administrator reopens it before more time goes on it")
    return None


def sheet_id_for(conn: sqlite3.Connection, member: str, worked_on, *, at: datetime) -> int:
    """The sheet an entry on this day belongs to, made OPEN if missing. The
    caller checked lock_reason first."""
    return ensure(conn, member, week_of(worked_on), at=at)["timesheet_id"]


# ------------------------------------------------------------ the lifecycle

def _event(conn, timesheet_id: int, action: str, *, at: datetime, actor: str, note: str | None = None) -> None:
    conn.execute("INSERT INTO timesheet_event (timesheet_id, occurred_at, actor, action, note) VALUES (?,?,?,?,?)",
                 (timesheet_id, _stamp(at), actor, action, (note or "")[:500] or None))
    db.audit(conn, at=_stamp(at), actor=actor, action="TIMESHEET", subject_kind="timesheet",
             subject_id=str(timesheet_id), detail=action + (f": {note[:200]}" if note else ""))


def submit(conn: sqlite3.Connection, member: str, week_start: date, *, at: datetime, actor: str):
    """The member (or a time administrator for them) says the week is complete.
    Every entry of the week joins the sheet, including any written before 046."""
    if week_start > week_of(at):
        raise Refused("A week is submitted once it has started, not before.")
    row = ensure(conn, member, week_start, at=at)
    if row["status"] in LOCKED:
        raise Refused(f"This week is already {STATUSES[row['status']].lower()}.")
    stamp = _stamp(at)
    conn.execute("UPDATE timesheet SET status = 'SUBMITTED', submitted_at = ?, submitted_by = ?, decided_at = NULL,"
                 " decided_by = NULL, note = NULL WHERE timesheet_id = ?", (stamp, actor, row["timesheet_id"]))
    a, b = week_start.isoformat(), week_end(week_start).isoformat()
    conn.execute("UPDATE time_entry SET timesheet_id = ? WHERE LOWER(performed_by) = LOWER(?)"
                 " AND worked_on >= ? AND worked_on <= ?", (row["timesheet_id"], member, a, b))
    _event(conn, row["timesheet_id"], "SUBMIT", at=at, actor=actor)
    return by_id(conn, row["timesheet_id"])


def decide(conn: sqlite3.Connection, timesheet_id: int, decision: str, *, at: datetime, actor: str,
           note: str | None = None):
    """Approve or reject a submitted sheet. Never the member's own; a
    rejection says why."""
    row = by_id(conn, timesheet_id)
    if row is None:
        raise Refused("No such timesheet.")
    if decision not in ("APPROVE", "REJECT"):
        raise Refused("A decision is Approve or Reject.")
    if row["status"] != "SUBMITTED":
        raise Refused(f"Only a submitted timesheet is decided; this one is {STATUSES[row['status']].lower()}.")
    if (row["member"] or "").lower() == (actor or "").lower():
        raise Refused("Nobody approves their own timesheet. Another time administrator decides it.")
    note = " ".join((note or "").split())
    if decision == "REJECT" and not note:
        raise Refused("A rejection says why, so the member knows what to fix.")
    status = "APPROVED" if decision == "APPROVE" else "REJECTED"
    conn.execute("UPDATE timesheet SET status = ?, decided_at = ?, decided_by = ?, note = ? WHERE timesheet_id = ?",
                 (status, _stamp(at), actor, note or None, timesheet_id))
    _event(conn, timesheet_id, decision, at=at, actor=actor, note=note)
    return by_id(conn, timesheet_id)


def reopen(conn: sqlite3.Connection, timesheet_id: int, *, at: datetime, actor: str, note: str | None = None):
    """A submitted or approved week back to OPEN, with the reason on the record."""
    row = by_id(conn, timesheet_id)
    if row is None:
        raise Refused("No such timesheet.")
    if row["status"] not in LOCKED:
        raise Refused("Only a submitted or approved timesheet is reopened.")
    note = " ".join((note or "").split())
    if not note:
        raise Refused("Reopening says why; the decision it undoes stays on the record.")
    conn.execute("UPDATE timesheet SET status = 'OPEN', note = ? WHERE timesheet_id = ?", (note, timesheet_id))
    _event(conn, timesheet_id, "REOPEN", at=at, actor=actor, note=note)
    return by_id(conn, timesheet_id)


def history(conn: sqlite3.Connection, timesheet_id: int):
    return conn.execute("SELECT * FROM timesheet_event WHERE timesheet_id = ? ORDER BY event_id",
                        (timesheet_id,)).fetchall()


def waiting(conn: sqlite3.Connection):
    """Submitted sheets, oldest first, each with its hours."""
    return conn.execute(
        f"SELECT s.*, (SELECT COALESCE(SUM({HOURS}), 0) FROM time_entry te WHERE te.timesheet_id = s.timesheet_id) AS hours"
        " FROM timesheet s WHERE s.status = 'SUBMITTED' ORDER BY s.submitted_at, s.timesheet_id").fetchall()


def members(conn: sqlite3.Connection) -> list[str]:
    """Everyone who works a board, plus anyone with time recorded."""
    seen: dict[str, str] = {}
    for r in conn.execute("SELECT DISTINCT member FROM board_member"):
        seen.setdefault((r[0] or "").lower(), r[0])
    for r in conn.execute("SELECT DISTINCT performed_by FROM time_entry"):
        seen.setdefault((r[0] or "").lower(), r[0])
    return sorted((m for m in seen.values() if m), key=str.lower)


# ------------------------------------------------------------ capacity and utilisation

def capacity(conn: sqlite3.Connection, member: str) -> float:
    row = conn.execute("SELECT hours_per_week FROM member_capacity WHERE LOWER(member) = LOWER(?)",
                       (member,)).fetchone()
    return float(row[0]) if row else DEFAULT_HOURS_PER_WEEK


def set_capacity(conn: sqlite3.Connection, member: str, hours, *, at: datetime, actor: str) -> float:
    member = (member or "").strip()
    try:
        h = float(hours)
    except (TypeError, ValueError):
        raise Refused("Hours a week is a number, e.g. 40.") from None
    if not member or not (0 < h <= 168):
        raise Refused("Hours a week is between 1 and 168, for a named person.")
    conn.execute("INSERT OR REPLACE INTO member_capacity (member, hours_per_week, set_at, set_by) VALUES (?,?,?,?)",
                 (member, h, _stamp(at), actor))
    db.audit(conn, at=_stamp(at), actor=actor, action="TIMESHEET", subject_kind="member_capacity",
             subject_id=member, detail=f"hours a week set to {h:g}")
    return h


def utilisation(conn: sqlite3.Connection, *, since: date, until: date) -> list[dict]:
    """Hours per member between two dates (inclusive), how many sit on an
    approved sheet, and the share of that member's capacity for the span."""
    weeks = ((until - since).days + 1) / 7
    rows = conn.execute(
        f"SELECT te.performed_by AS member, SUM({HOURS}) AS hours,"
        f" SUM(CASE WHEN s.status = 'APPROVED' THEN {HOURS} ELSE 0 END) AS approved"
        " FROM time_entry te LEFT JOIN timesheet s ON s.timesheet_id = te.timesheet_id"
        " WHERE te.worked_on >= ? AND te.worked_on <= ? GROUP BY te.performed_by ORDER BY te.performed_by",
        (since.isoformat(), until.isoformat())).fetchall()
    out = []
    for r in rows:
        cap = capacity(conn, r["member"]) * weeks
        hours = float(r["hours"] or 0)
        out.append({"member": r["member"], "hours": round(hours, 2), "approved": round(float(r["approved"] or 0), 2),
                    "capacity": round(cap, 1), "percent": int(round(100 * hours / cap)) if cap else None})
    return out


def approval_summary(conn: sqlite3.Connection) -> tuple[float, float]:
    """(banded hours that count to capacity, of them the hours on an approved
    sheet), for the uplift evidence."""
    row = conn.execute(
        "SELECT COALESCE(SUM(te.band_hours), 0),"
        " COALESCE(SUM(CASE WHEN s.status = 'APPROVED' THEN te.band_hours ELSE 0 END), 0)"
        " FROM time_entry te LEFT JOIN timesheet s ON s.timesheet_id = te.timesheet_id"
        " WHERE te.counts_to_capacity = 1").fetchone()
    return float(row[0] or 0), float(row[1] or 0)

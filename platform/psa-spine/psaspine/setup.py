"""Setting a board up, the way a ConnectWise service board is set up.

A PSA does not arrive with boards in it (Dada's direction, 9 Sep 2026 — see
`db.seed_catalogue`), so nothing here runs on `init`. A board administrator
applies it to a board they have created, from the board's setup screen or with
`psaspine setup-board`, and then edits every value it wrote. That is how
ConnectWise does it too: the Service Board setup table is where the statuses,
the SLA and the calendar are chosen, per board, by a person.

What it writes is a STARTER, not a decision:

- **Statuses** in ConnectWise's shape — each declares the SLA milestone it
  represents (`escalationStatus`), whether it closes the ticket, whether time
  may be entered in it, and what the requester is shown instead of the internal
  name. The names follow the common ConnectWise convention (New, In Progress,
  Waiting…, Resolved, >Closed) **[INFERRED — ConnectWise's own documentation is
  behind its University login and was not read]**.
- **Two calendars**: all hours, and a Monday-to-Saturday business day.
- **Three clocks per priority** — respond, resolution plan, resolve — the three
  timestamps ConnectWise stores on a ticket. Every target is written with
  `enforced = 0`: measured, reported, never promised. The minutes are
  placeholders for the Service Manager to replace **[INFERRED]**; they are the
  same shape as `seed/sample/sla_targets.csv` and nobody at PMC has signed them.

Re-applying is safe: it adds what is missing and never overwrites what an
administrator has already changed.
"""
from __future__ import annotations

import re
import sqlite3
from datetime import datetime

from . import db

DAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")

CALENDARS = (
    ("ALL_HOURS", "All hours (24x7)", [("00:00", "24:00")] * 7),
    ("BUSINESS", "Business day (Mon-Sat 08:00-17:00)",
     [("08:00", "17:00")] * 6 + [(None, None)]),
)

# name, escalation, default, closed, time entry allowed, on board, portal wording
STARTER_STATUSES = (
    ("New", "NOT_RESPONDED", 1, 0, 1, 1, "Received — waiting for someone to pick it up"),
    ("Assigned", "NOT_RESPONDED", 0, 0, 1, 1, "Assigned to a technician"),
    ("In Progress", "RESPONDED", 0, 0, 1, 1, "Someone is working on it"),
    ("Scheduled", "RESOLUTION_PLAN", 0, 0, 1, 1, "A fix is planned — we will tell you when"),
    ("Waiting on Requester", "NO_ESCALATION", 0, 0, 1, 1, "We need something from you"),
    ("Waiting on Vendor", "NO_ESCALATION", 0, 0, 1, 1, "Waiting on a supplier"),
    ("Resolved", "RESOLVED", 0, 0, 1, 1, "We think this is fixed — reply if it is not"),
    (">Closed", "RESOLVED", 0, 1, 0, 0, "Closed"),
)

# priority -> (respond, resolution plan, resolve), in minutes. Placeholders.
STARTER_TARGETS = {
    "P1": (15, 60, 240),
    "P2": (60, 240, 480),
    "P3": (240, 480, 1440),
    "P4": (480, 1440, 4320),
}
CLOCKS = ("RESPOND", "RESOLUTION_PLAN", "RESOLVE")


def status_id(board_id: str, name: str) -> str:
    return f"{board_id}.{re.sub(r'[^A-Z0-9]+', '_', name.upper()).strip('_') or 'STATUS'}"


def ensure_calendars(conn: sqlite3.Connection) -> None:
    for cal_id, name, week in CALENDARS:
        cols = ", ".join(f"{d}_start, {d}_end" for d in DAYS)
        values = [v for pair in week for v in pair]
        conn.execute(
            f"INSERT OR IGNORE INTO calendar (calendar_id, name, {cols})"
            f" VALUES (?,?,{','.join('?' * 14)})", [cal_id, name, *values])


def apply_starter(conn: sqlite3.Connection, board_id: str, *, actor: str,
                  at: datetime) -> dict:
    """Give a board the statuses, calendar and SLA targets it needs to run.

    Adds only what is missing. A status an administrator renamed, a target they
    changed, a calendar they chose: all left exactly as they are.
    """
    if conn.execute("SELECT 1 FROM board WHERE board_id = ?", (board_id,)).fetchone() is None:
        raise LookupError(f"no board {board_id!r}")
    ensure_calendars(conn)

    has_default = conn.execute(
        "SELECT 1 FROM board_status WHERE board_id = ? AND is_default = 1 AND inactive = 0",
        (board_id,)).fetchone() is not None
    added_statuses = 0
    for order, (name, esc, default, closed, effort, shown, portal) in enumerate(
            STARTER_STATUSES, start=1):
        cur = conn.execute(
            "INSERT OR IGNORE INTO board_status (board_status_id, board_id, name,"
            " customer_description, escalation_status, is_default, is_closed,"
            " time_entry_allowed, display_on_board, sort_order)"
            " VALUES (?,?,?,?,?,?,?,?,?,?)",
            (status_id(board_id, name), board_id, name, portal, esc,
             0 if has_default else default, closed, effort, shown, order * 10))
        added_statuses += cur.rowcount

    added_targets = 0
    for priority, minutes in STARTER_TARGETS.items():
        for clock, target in zip(CLOCKS, minutes):
            cur = conn.execute(
                "INSERT OR IGNORE INTO sla_target (board_id, priority, clock,"
                " target_minutes, calendar, enforced, note)"
                " VALUES (?,?,?,?, 'CLINICAL_24x7', 0,"
                " 'starter placeholder: set by the Service Manager')",
                (board_id, priority, clock, target))
            added_targets += cur.rowcount

    cur = conn.execute("UPDATE board SET calendar_id = 'ALL_HOURS'"
                       " WHERE board_id = ? AND calendar_id IS NULL", (board_id,))
    calendar_set = bool(cur.rowcount)

    db.audit(conn, at=at.isoformat(sep=" ", timespec="minutes"), actor=actor,
             action="BOARD_SETUP", subject_kind="board", subject_id=board_id,
             detail=f"starter applied: {added_statuses} statuses, {added_targets} "
                    f"SLA targets{', calendar ALL_HOURS' if calendar_set else ''}")
    return {"board_id": board_id, "statuses": added_statuses,
            "targets": added_targets, "calendar_set": calendar_set}


def readiness(conn: sqlite3.Connection, board_id: str) -> list[str]:
    """What this board still lacks before a ticket on it can run, in words.

    Empty means ready: a default status to land in, a closed status to finish
    in, and a calendar for the clocks. Targets are not required — a board with
    no targets runs, it simply measures nothing, and the board view says so.
    """
    missing = []
    q = lambda sql: conn.execute(sql, (board_id,)).fetchone() is not None  # noqa: E731
    if not q("SELECT 1 FROM board_status WHERE board_id = ? AND is_default = 1 AND inactive = 0"):
        missing.append("a default status for new tickets")
    if not q("SELECT 1 FROM board_status WHERE board_id = ? AND is_closed = 1 AND inactive = 0"):
        missing.append("a closed status")
    if not q("SELECT 1 FROM board WHERE board_id = ? AND calendar_id IS NOT NULL"):
        missing.append("a calendar for the SLA clocks")
    return missing

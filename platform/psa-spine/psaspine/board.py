"""One status change, and everything that follows from it.

Until now the board, the clocks and the rules were three libraries that happened
to share a database. This is the seam: moving a ticket to a status stops the
clocks that status satisfies, pauses or resumes the ones it does not, keeps the
universal lifecycle in step, and writes what happened down.

It is one function on purpose. The moment a status change is done in two places
they disagree, and the place they disagree is a clock that says a P1 was answered
when nobody answered it.

What this module does NOT do is act on rules. `rules.evaluate` decides; the
caller sends the page. That boundary is why all of this is testable without a
mail server, and it is kept here too.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime

from . import clocks

# The universal lifecycle a board status maps onto. `state` is what the variation
# gate in 005 tests, so it cannot depend on a vocabulary each board edits.
LIFECYCLE = {
    "NOT_RESPONDED": "NEW",
    "RESPONDED": "IN_PROGRESS",
    "RESOLUTION_PLAN": "IN_PROGRESS",
    "RESOLVED": "RESOLVED",
    "NO_ESCALATION": "WAITING_CLIENT",
}


class NotOnThisBoard(Exception):
    """A status from another board. Refused rather than accepted, because a
    ticket wearing another board's status is a ticket no report can group."""


def status(conn: sqlite3.Connection, board_status_id: str) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM board_status WHERE board_status_id = ?",
                       (board_status_id,)).fetchone()
    if row is None:
        raise LookupError(f"no board status {board_status_id!r}")
    return row


def open_clocks(conn: sqlite3.Connection, work_item_id: str, *, at: datetime,
                calendar_id: str) -> list[int]:
    """Start the clocks this ticket's board and priority call for.

    Targets come from `sla_target`, which still ships `enforced = 0` on every
    row. Starting a clock measures; it does not promise.
    """
    ticket = conn.execute("SELECT board_id, priority FROM ticket WHERE work_item_id = ?",
                          (work_item_id,)).fetchone()
    if ticket is None:
        raise LookupError(f"no ticket {work_item_id!r}")

    started: list[int] = []
    for target in conn.execute(
            "SELECT clock, target_minutes FROM sla_target"
            " WHERE board_id = ? AND priority = ?", (ticket["board_id"], ticket["priority"])):
        cur = conn.execute(
            "INSERT OR IGNORE INTO ticket_clock (work_item_id, clock, calendar_id,"
            " target_minutes, started_at) VALUES (?,?,?,?,?)",
            (work_item_id, target["clock"], calendar_id, target["target_minutes"],
             at.isoformat(sep=" ", timespec="minutes")))
        if cur.rowcount:
            started.append(cur.lastrowid)
    return started


def running_clocks(conn: sqlite3.Connection, work_item_id: str) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM ticket_clock WHERE work_item_id = ? AND stopped_at IS NULL",
        (work_item_id,)).fetchall()


def change_status(conn: sqlite3.Connection, work_item_id: str, to_status_id: str, *,
                  at: datetime, actor: str) -> dict:
    """Move a ticket to a status, and settle everything that follows.

    Returns what changed, so a caller can report it and a test can assert it
    rather than inspecting five tables.
    """
    ticket = conn.execute("SELECT * FROM ticket WHERE work_item_id = ?",
                          (work_item_id,)).fetchone()
    if ticket is None:
        raise LookupError(f"no ticket {work_item_id!r}")

    new = status(conn, to_status_id)
    if new["board_id"] != ticket["board_id"]:
        raise NotOnThisBoard(
            f"status {to_status_id!r} belongs to board {new['board_id']!r} but the "
            f"ticket is on {ticket['board_id']!r}. Move the ticket first; a handover "
            f"is one ticket changing board, not a status borrowed from another one.")
    if new["inactive"]:
        raise NotOnThisBoard(
            f"status {to_status_id!r} is retired. Retired statuses stay for the "
            f"tickets that sat in them; nothing new enters one.")

    stamp = at.isoformat(sep=" ", timespec="minutes")
    escalation = new["escalation_status"]
    stopped, paused, resumed = [], [], []

    for clock in running_clocks(conn, work_item_id):
        open_pause = conn.execute(
            "SELECT pause_id FROM ticket_clock_pause WHERE clock_id = ?"
            "   AND resumed_at IS NULL", (clock["clock_id"],)).fetchone()

        if clocks.stops_clock(escalation, clock["clock"]):
            # Close any pause first, or the paused interval runs past the stop.
            if open_pause:
                conn.execute("UPDATE ticket_clock_pause SET resumed_at = ? WHERE pause_id = ?",
                             (stamp, open_pause["pause_id"]))
                resumed.append(clock["clock"])
            conn.execute(
                "UPDATE ticket_clock SET stopped_at = ?, stopped_by_status = ?"
                " WHERE clock_id = ?", (stamp, to_status_id, clock["clock_id"]))
            stopped.append(clock["clock"])
        elif clocks.is_pause(escalation):
            if not open_pause:
                conn.execute(
                    "INSERT INTO ticket_clock_pause (clock_id, paused_at, board_status_id)"
                    " VALUES (?,?,?)", (clock["clock_id"], stamp, to_status_id))
                paused.append(clock["clock"])
        elif open_pause:
            conn.execute("UPDATE ticket_clock_pause SET resumed_at = ? WHERE pause_id = ?",
                         (stamp, open_pause["pause_id"]))
            resumed.append(clock["clock"])

    # The universal lifecycle follows the board's status, never the other way.
    # A closed status closes the ticket whatever milestone it declares.
    state = "CLOSED" if new["is_closed"] else LIFECYCLE.get(escalation, ticket["state"])
    conn.execute(
        "UPDATE ticket SET board_status_id = ?, state = ?,"
        " closed_at = CASE WHEN ? = 1 THEN ? ELSE closed_at END"
        " WHERE work_item_id = ?",
        (to_status_id, state, 1 if new["is_closed"] else 0, stamp, work_item_id))

    conn.execute(
        "INSERT INTO ticket_event (work_item_id, occurred_at, kind, actor, detail)"
        " VALUES (?,?,'STATUS_CHANGE',?,?)",
        (work_item_id, stamp, actor,
         f"{ticket['board_status_id'] or ticket['state']} -> {to_status_id} "
         f"({escalation}); stopped={stopped or '-'} paused={paused or '-'} "
         f"resumed={resumed or '-'}"))

    return {"work_item_id": work_item_id, "board_status_id": to_status_id,
            "state": state, "escalation_status": escalation,
            "stopped": stopped, "paused": paused, "resumed": resumed,
            "time_entry_allowed": bool(new["time_entry_allowed"])}


def may_book_effort(conn: sqlite3.Connection, work_item_id: str) -> tuple[bool, str]:
    """Whether effort may be booked against this ticket right now, and why not.

    Two independent gates, and both have to pass. The variation gate in 005 is
    enforced by a trigger and will refuse the insert regardless; this reports the
    same answer before the attempt, so a user interface can say why rather than
    showing a database error to a nurse.
    """
    row = conn.execute(
        "SELECT t.board_status_id, t.path, w.variation_id, s.name, s.time_entry_allowed"
        "  FROM ticket t JOIN work_item w ON w.work_item_id = t.work_item_id"
        "  LEFT JOIN board_status s ON s.board_status_id = t.board_status_id"
        " WHERE t.work_item_id = ?", (work_item_id,)).fetchone()
    if row is None:
        raise LookupError(f"no ticket {work_item_id!r}")

    if row["path"] == "VARIATION" and row["variation_id"] is None:
        return False, ("a variation-path ticket must be attached to a variation before "
                       "it can consume effort")
    if row["board_status_id"] and not row["time_entry_allowed"]:
        return False, f"the status {row['name']!r} does not allow effort to be booked"
    return True, "allowed"

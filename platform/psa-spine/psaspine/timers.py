"""The stopwatch a technician runs on a ticket, and nothing to do with the SLA.

Dada, 3 Oct 2026: *"there is usually a clock on the ConnectWise ticketing for
time entries, that's apart from the SLA"*. This is that clock.

It measures one person's worked time on one ticket so the time entry's start
and end are **measured rather than remembered**. A technician starts it when
they pick the job up, pauses it when the ward pulls them away, stops it when
they are done, and the Time form opens with the times already in it.

What it is not, and the reason 065 says so twice: it is not `ticket_clock`.
The SLA clocks measure what the hospital is owed — response and resolution,
on the board's calendar, paused by the statuses that pause them — and nobody
starts or stops those by hand. This one counts wall-clock seconds for one
person, honours no calendar, and no SLA number is derived from it.

Elapsed is computed, never stored: `(stopped_at or now) - started_at -
paused_seconds`, and while paused the sum freezes at `paused_at`. Storing a
running total would be a second truth to keep in step with the first.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime

STAMP = "%Y-%m-%d %H:%M:%S"


class NotYours(Exception):
    """A timer belongs to the person who started it, and to nobody else."""


class AlreadyRunning(Exception):
    """One running timer per person per ticket (065). Two double-count."""


def _stamp(at: datetime) -> str:
    return at.strftime(STAMP)


def _parse(value: str) -> datetime:
    return datetime.strptime(value[:19], STAMP) if len(value) >= 19 else \
        datetime.strptime(value, "%Y-%m-%d %H:%M")


def elapsed_seconds(row, *, now: datetime) -> int:
    """How long this timer has actually run, in seconds, never negative.

    A clock read while it is paused reads the same a minute later, which is
    what being paused means.
    """
    started = _parse(row["started_at"])
    if row["stopped_at"]:
        end = _parse(row["stopped_at"])
    elif row["paused_at"]:
        end = _parse(row["paused_at"])
    else:
        end = now
    whole = int((end - started).total_seconds()) - int(row["paused_seconds"] or 0)
    return max(0, whole)


def hours(seconds: int) -> float:
    """Seconds as hours to the quarter, which is the unit time is kept in.

    Rounded up: a job that took sixteen minutes cost the quarter hour it ran
    into, and rounding it down would bill the hospital for work nobody did.
    """
    import math
    return round(math.ceil(seconds / 900) * 0.25, 2) if seconds else 0.0


def running(conn: sqlite3.Connection, member: str) -> list[sqlite3.Row]:
    """Every timer this person has going, across every ticket."""
    return conn.execute(
        "SELECT t.*, w.name AS summary FROM time_timer t"
        "  JOIN work_item w ON w.work_item_id = t.work_item_id"
        " WHERE t.member = ? AND t.stopped_at IS NULL"
        " ORDER BY t.started_at", (member,)).fetchall()


def for_ticket(conn: sqlite3.Connection, work_item_id: str, member: str) -> sqlite3.Row | None:
    """This person's timer on this ticket: the running one, or a stopped one
    not yet turned into an entry, which is still theirs to save or discard."""
    return conn.execute(
        "SELECT * FROM time_timer WHERE work_item_id = ? AND member = ?"
        "   AND time_entry_id IS NULL ORDER BY started_at DESC LIMIT 1",
        (work_item_id, member)).fetchone()


def start(conn: sqlite3.Connection, work_item_id: str, *, member: str, at: datetime) -> int:
    """Start counting. Refuses a second one on the same ticket for the same
    person, because two would count the same hour twice."""
    open_one = conn.execute(
        "SELECT timer_id FROM time_timer WHERE work_item_id = ? AND member = ?"
        "   AND stopped_at IS NULL", (work_item_id, member)).fetchone()
    if open_one:
        raise AlreadyRunning(
            "a timer is already running for you on this ticket; stop it before starting another")
    cur = conn.execute(
        "INSERT INTO time_timer (work_item_id, member, started_at, paused_seconds)"
        " VALUES (?,?,?,0)", (work_item_id, member, _stamp(at)))
    return cur.lastrowid


def _mine(conn: sqlite3.Connection, timer_id: int, member: str) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM time_timer WHERE timer_id = ?", (timer_id,)).fetchone()
    if row is None:
        raise LookupError(f"no timer {timer_id}")
    if row["member"].lower() != member.lower():
        raise NotYours("a timer belongs to the person who started it")
    return row


def pause(conn: sqlite3.Connection, timer_id: int, *, member: str, at: datetime) -> None:
    """Stop counting without ending the job. Pausing a paused timer does
    nothing, which is what a second click on the same button should do."""
    row = _mine(conn, timer_id, member)
    if row["stopped_at"] or row["paused_at"]:
        return
    conn.execute("UPDATE time_timer SET paused_at = ? WHERE timer_id = ?",
                 (_stamp(max(at, _parse(row["started_at"]))), timer_id))


def resume(conn: sqlite3.Connection, timer_id: int, *, member: str, at: datetime) -> None:
    """Count again, with the pause added to what is not counted."""
    row = _mine(conn, timer_id, member)
    if row["stopped_at"] or not row["paused_at"]:
        return
    paused_for = max(0, int((at - _parse(row["paused_at"])).total_seconds()))
    conn.execute(
        "UPDATE time_timer SET paused_at = NULL, paused_seconds = paused_seconds + ?"
        " WHERE timer_id = ?", (paused_for, timer_id))


def stop(conn: sqlite3.Connection, timer_id: int, *, member: str, at: datetime) -> dict:
    """End it, and hand back what the time entry form needs.

    A timer stopped while paused keeps the pause: the seconds between the
    pause and the stop were not worked, so they are added to paused_seconds
    rather than counted.
    """
    row = _mine(conn, timer_id, member)
    if not row["stopped_at"]:
        extra = 0
        if row["paused_at"]:
            extra = max(0, int((at - _parse(row["paused_at"])).total_seconds()))
        # Never before it started: the same rule 007 states for the SLA clocks,
        # for the same reason (3 Oct 2026).
        when = max(at, _parse(row["started_at"]))
        conn.execute(
            "UPDATE time_timer SET stopped_at = ?, paused_at = NULL,"
            " paused_seconds = paused_seconds + ? WHERE timer_id = ?",
            (_stamp(when), extra, timer_id))
        row = conn.execute("SELECT * FROM time_timer WHERE timer_id = ?", (timer_id,)).fetchone()
    secs = elapsed_seconds(row, now=at)
    return {"timer_id": timer_id, "seconds": secs, "hours": hours(secs),
            "time_start": row["started_at"][11:16], "time_end": row["stopped_at"][11:16],
            "worked_on": row["started_at"][:10], "note": row["note"] or ""}


def note(conn: sqlite3.Connection, timer_id: int, *, member: str, text: str) -> None:
    """What is being done, typed while it is being done."""
    _mine(conn, timer_id, member)
    conn.execute("UPDATE time_timer SET note = ? WHERE timer_id = ?",
                 ((text or "").strip() or None, timer_id))


def discard(conn: sqlite3.Connection, timer_id: int, *, member: str) -> None:
    """Throw it away. Only a timer that never became an entry can go, and
    only its owner may; a spent one is part of a time entry's evidence."""
    row = _mine(conn, timer_id, member)
    if row["time_entry_id"] is not None:
        raise ValueError("this timer is already part of a saved time entry")
    conn.execute("DELETE FROM time_timer WHERE timer_id = ?", (timer_id,))


def spend(conn: sqlite3.Connection, timer_id: int, time_entry_id: int) -> None:
    """Mark the timer as the one that produced this entry, so it leaves the
    pod and cannot be saved twice."""
    conn.execute("UPDATE time_timer SET time_entry_id = ?, stopped_at = COALESCE(stopped_at,"
                 " started_at) WHERE timer_id = ?", (time_entry_id, timer_id))


def clock(seconds: int) -> str:
    """h:mm:ss, the way a stopwatch reads."""
    h, rest = divmod(max(0, int(seconds)), 3600)
    m, s = divmod(rest, 60)
    return f"{h}:{m:02d}:{s:02d}"

"""Elapsed working time against a calendar, and whether a clock has breached.

This is the arithmetic under every SLA number the spine will ever report, so it
is written to be argued with: one function computes working minutes between two
instants against one calendar, and everything else is built on it.

Three rules it holds to, each of which is a decision somebody could take
differently and should be able to see:

  * **Breach is derived, never stored.** `breached()` takes an `as_of` and
    recomputes. Correct a target or fix a calendar and yesterday's answer changes
    with it, which is the honest behaviour: the old answer was wrong.

  * **A pause is an interval, not a counter.** Pauses are subtracted by
    intersecting them with working time, so pausing a ticket at 02:00 on a
    Manila business calendar subtracts nothing, because nothing was counting.

  * **The calendar is data.** A closed day is a NULL start. `'24:00'` is a legal
    end meaning midnight, so a 24x7 calendar is seven ordinary rows rather than
    a branch in this file.

Standard library only, like the rest of the engine.
"""
from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta

DAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")

# The escalation_status values that stop each clock. A status declares which
# milestone it represents; this says which clock that milestone satisfies.
STOPS = {
    "RESPOND": {"RESPONDED", "RESOLUTION_PLAN", "RESOLVED"},
    "RESOLUTION_PLAN": {"RESOLUTION_PLAN", "RESOLVED"},
    "RESOLVE": {"RESOLVED"},
    "ACKNOWLEDGE": {"RESPONDED", "RESOLUTION_PLAN", "RESOLVED"},
    "DECISION": {"RESOLVED"},
}

PAUSES = "NO_ESCALATION"

# Clocks a waiting status never pauses. Parking a ticket "waiting on the
# requester" before anybody has answered them is not a response, and pausing the
# respond clock there would let a missed response vanish from the numbers. The
# record's own §5.5 pauses the RESOLVE clock in a waiting status; ITFlow documents
# the same rule ("On Hold pauses the resolution clock, not the response clock").
NEVER_PAUSED = {"RESPOND", "ACKNOWLEDGE"}


def parse_clock_time(text: str | None) -> int | None:
    """'08:00' -> 480. '24:00' -> 1440, meaning midnight at the end of the day.

    Minutes from midnight rather than a `time`, because `time` cannot hold 24:00
    and a calendar that runs to the end of the day is the common case in a
    hospital, not the exotic one.
    """
    if text is None or not text.strip():
        return None
    hours, _, minutes = text.strip().partition(":")
    total = int(hours) * 60 + int(minutes or 0)
    if not 0 <= total <= 1440:
        raise ValueError(f"clock time {text!r} is outside 00:00..24:00")
    return total


def parse_instant(text: str) -> datetime:
    """Accept the shapes the record actually contains."""
    value = text.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        if len(value) == 8 and value.isdigit():          # '20260904'
            parsed = datetime(int(value[:4]), int(value[4:6]), int(value[6:]))
        else:
            raise
    return parsed.replace(tzinfo=None)


class Calendar:
    """A working week and the days it does not work.

    Built from rows rather than constants, so a ward roster, Manila business
    hours and a supplier's support window are the same kind of thing.
    """

    def __init__(self, windows: dict[int, tuple[int, int]], holidays: set[date],
                 name: str = "") -> None:
        self.windows = windows          # weekday 0..6 -> (start_min, end_min)
        self.holidays = holidays
        self.name = name
        # Minutes a whole working day of each weekday is worth, and a whole week:
        # the fast path below counts full days arithmetically instead of walking
        # them one by one, which a clock that has run for a year would otherwise do.
        self.day_minutes = {d: end - start for d, (start, end) in windows.items()}
        self.week_minutes = sum(self.day_minutes.values())
        self.round_the_clock = all(windows.get(d) == (0, 1440) for d in range(7))

    @classmethod
    def load(cls, conn: sqlite3.Connection, calendar_id: str) -> "Calendar":
        row = conn.execute("SELECT * FROM calendar WHERE calendar_id = ?",
                           (calendar_id,)).fetchone()
        if row is None:
            raise LookupError(f"no calendar {calendar_id!r}")
        windows: dict[int, tuple[int, int]] = {}
        for index, day in enumerate(DAYS):
            start = parse_clock_time(row[f"{day}_start"])
            end = parse_clock_time(row[f"{day}_end"])
            if start is not None and end is not None and end > start:
                windows[index] = (start, end)
        holidays: set[date] = set()
        if row["holiday_list_id"]:
            for h in conn.execute(
                    "SELECT observed_on FROM holiday WHERE holiday_list_id = ?",
                    (row["holiday_list_id"],)):
                try:
                    holidays.add(parse_instant(h["observed_on"]).date())
                except ValueError:
                    continue            # unparseable dates are counted elsewhere
        return cls(windows, holidays, row["name"])

    def is_working_day(self, day: date) -> bool:
        return day.weekday() in self.windows and day not in self.holidays

    def _day_overlap(self, day: date, start: datetime, end: datetime) -> int:
        if not self.is_working_day(day):
            return 0
        open_min, close_min = self.windows[day.weekday()]
        midnight = datetime(day.year, day.month, day.day)
        overlap_start = max(midnight + timedelta(minutes=open_min), start)
        overlap_end = min(midnight + timedelta(minutes=close_min), end)
        if overlap_end <= overlap_start:
            return 0
        return int((overlap_end - overlap_start).total_seconds() // 60)

    def working_minutes(self, start: datetime, end: datetime) -> int:
        """Working minutes between two instants. Never negative.

        The first and last days are measured against their windows; the whole
        days between are counted by weekday arithmetic, less any holiday that
        falls in the span. Same answer as walking every day, in constant time
        for a clock that has run for months."""
        if end <= start:
            return 0
        if self.round_the_clock and not self.holidays:
            return int((end - start).total_seconds() // 60)
        first, last = start.date(), end.date()
        if first == last:
            return self._day_overlap(first, start, end)
        total = self._day_overlap(first, start, end) + self._day_overlap(last, start, end)
        inner_first = first + timedelta(days=1)
        inner_days = (last - inner_first).days
        if inner_days <= 0:
            return total
        weeks, rest = divmod(inner_days, 7)
        total += weeks * self.week_minutes
        day = inner_first
        for _ in range(rest):
            total += self.day_minutes.get(day.weekday(), 0)
            day += timedelta(days=1)
        for holiday in self.holidays:
            if inner_first <= holiday < last:
                total -= self.day_minutes.get(holiday.weekday(), 0)
        return total


# ------------------------------------------------------------------- clocks

def pauses(conn: sqlite3.Connection, clock_id: int) -> list[tuple[datetime, datetime | None]]:
    return [
        (parse_instant(r["paused_at"]),
         parse_instant(r["resumed_at"]) if r["resumed_at"] else None)
        for r in conn.execute(
            "SELECT paused_at, resumed_at FROM ticket_clock_pause"
            " WHERE clock_id = ? ORDER BY paused_at", (clock_id,))
    ]


def elapsed_minutes(conn: sqlite3.Connection, clock_id: int, *,
                    as_of: datetime | None = None) -> int:
    """Working minutes this clock has actually counted.

    Pauses are intersected with working time rather than subtracted wholesale,
    so a ticket parked at 02:00 on a business calendar loses nothing — there was
    nothing running to lose.
    """
    row = conn.execute("SELECT * FROM ticket_clock WHERE clock_id = ?",
                       (clock_id,)).fetchone()
    if row is None:
        raise LookupError(f"no clock {clock_id}")
    calendar = Calendar.load(conn, row["calendar_id"])

    start = parse_instant(row["started_at"])
    end = parse_instant(row["stopped_at"]) if row["stopped_at"] else (as_of or datetime.now())
    if end < start:
        return 0

    total = calendar.working_minutes(start, end)
    for paused_at, resumed_at in pauses(conn, clock_id):
        pause_start = max(paused_at, start)
        pause_end = min(resumed_at or end, end)
        if pause_end > pause_start:
            total -= calendar.working_minutes(pause_start, pause_end)
    return max(total, 0)


def _state(row, pause_rows, calendar: Calendar, as_of: datetime) -> dict:
    """One clock's state from rows already in hand. state_of and states_many
    both end here, so a board of a thousand tickets and one ticket's screen
    cannot disagree."""
    start = parse_instant(row["started_at"])
    end = parse_instant(row["stopped_at"]) if row["stopped_at"] else as_of
    used = 0
    open_pauses = 0
    if end >= start:
        used = calendar.working_minutes(start, end)
        for p in pause_rows:
            paused_at = parse_instant(p["paused_at"])
            resumed_at = parse_instant(p["resumed_at"]) if p["resumed_at"] else None
            if resumed_at is None:
                open_pauses += 1
            pause_start = max(paused_at, start)
            pause_end = min(resumed_at or end, end)
            if pause_end > pause_start:
                used -= calendar.working_minutes(pause_start, pause_end)
        used = max(used, 0)
    else:
        open_pauses = sum(1 for p in pause_rows if not p["resumed_at"])
    return {
        "clock": row["clock"],
        "work_item_id": row["work_item_id"],
        "calendar_id": row["calendar_id"],
        "target_minutes": row["target_minutes"],
        "elapsed_minutes": used,
        "remaining_minutes": row["target_minutes"] - used,
        "breached": used > row["target_minutes"],
        "running": row["stopped_at"] is None and not open_pauses,
        "paused": bool(open_pauses),
        "stopped_at": row["stopped_at"],
    }


def states_many(conn: sqlite3.Connection, work_item_ids, *,
                as_of: datetime | None = None) -> dict[str, list[dict]]:
    """Every clock of every ticket named, in three queries however many tickets:
    the clocks, their pauses, and each calendar once. What a board does per row
    is what made a 3,000-ticket board take seconds."""
    ids = list(dict.fromkeys(work_item_ids))
    out: dict[str, list[dict]] = {wid: [] for wid in ids}
    if not ids:
        return out
    as_of = as_of or datetime.now()
    calendars: dict[str, Calendar] = {}
    clock_rows: list = []
    for i in range(0, len(ids), 500):                      # under SQLite's parameter limit
        chunk = ids[i:i + 500]
        clock_rows += conn.execute(
            "SELECT * FROM ticket_clock WHERE work_item_id IN (%s) ORDER BY clock_id"
            % ",".join("?" * len(chunk)), chunk).fetchall()
    pauses_by_clock: dict[int, list] = {}
    clock_ids = [r["clock_id"] for r in clock_rows]
    for i in range(0, len(clock_ids), 500):
        chunk = clock_ids[i:i + 500]
        for p in conn.execute(
                "SELECT clock_id, paused_at, resumed_at FROM ticket_clock_pause"
                " WHERE clock_id IN (%s) ORDER BY paused_at" % ",".join("?" * len(chunk)), chunk):
            pauses_by_clock.setdefault(p["clock_id"], []).append(p)
    for row in clock_rows:
        cal = calendars.get(row["calendar_id"])
        if cal is None:
            cal = calendars[row["calendar_id"]] = Calendar.load(conn, row["calendar_id"])
        out[row["work_item_id"]].append(
            _state(row, pauses_by_clock.get(row["clock_id"], []), cal, as_of))
    return out


def breached(conn: sqlite3.Connection, clock_id: int, *,
             as_of: datetime | None = None) -> bool:
    """Derived, every time. Never a column."""
    row = conn.execute("SELECT target_minutes FROM ticket_clock WHERE clock_id = ?",
                       (clock_id,)).fetchone()
    if row is None:
        raise LookupError(f"no clock {clock_id}")
    return elapsed_minutes(conn, clock_id, as_of=as_of) > row["target_minutes"]


def stops_clock(escalation_status: str, clock: str) -> bool:
    """Does a ticket entering this status satisfy this clock?"""
    return escalation_status in STOPS.get(clock, set())


def is_pause(escalation_status: str, clock: str | None = None) -> bool:
    """Does entering this status pause this clock? Without `clock`, whether the
    status is a waiting status at all."""
    if escalation_status != PAUSES:
        return False
    return clock not in NEVER_PAUSED


def state_of(conn: sqlite3.Connection, clock_id: int, *,
             as_of: datetime | None = None) -> dict:
    """Everything a report needs about one clock, computed rather than read."""
    row = conn.execute("SELECT * FROM ticket_clock WHERE clock_id = ?",
                       (clock_id,)).fetchone()
    if row is None:
        raise LookupError(f"no clock {clock_id}")
    pause_rows = conn.execute(
        "SELECT clock_id, paused_at, resumed_at FROM ticket_clock_pause"
        " WHERE clock_id = ? ORDER BY paused_at", (clock_id,)).fetchall()
    return _state(row, pause_rows, Calendar.load(conn, row["calendar_id"]),
                  as_of or datetime.now())

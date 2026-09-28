"""Setup › Calendars: the working weeks the SLA clocks run on, and the holidays.

The reference PSA's Calendar setup table is a name, a start and an end for each
of the seven days, and a holiday list; its Holiday List setup table is a named
list of dates, each a name, an all-day flag and, when the flag is off, the hours
it closes (the record's extracted model, VERIFIED 9 Sep 2026 from its published
OpenAPI schema: Calendar.mondayStartTime … sundayEndTime, holidayList;
Holiday.date, name, allDayFlag, timeStart, timeEnd). Dada PSA keeps the same
shape on its own tables (schema/006, 037) and edits it here.

- A blank start or end closes the calendar that day; `24:00` is midnight at the
  end of the day, so 24x7 is seven ordinary rows.
- A calendar is retired, never deleted: the boards on it keep it, new boards
  are not offered it.
- A holiday date may be removed, because it is reference data typed by a
  person and may be typed wrong. Every clock recomputes from the rows as they
  stand, so the removal is audited.

Every write is one CALENDAR_CONFIG audit row saying what changed.
"""
from __future__ import annotations

import csv
import re
import sqlite3
from datetime import date, datetime
from pathlib import Path

from . import db
from .clocks import DAYS, parse_clock_time

MAX_NAME = 60
_TIME = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$|^24:00$")


class Refused(ValueError):
    """A sentence for the person; nothing was written."""


def slug(name: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "_", name.upper()).strip("_")


def _name(value: str | None, what: str) -> str:
    name = " ".join((value or "").split())
    if not name:
        raise Refused(f"A {what} needs a name.")
    if len(name) > MAX_NAME:
        raise Refused(f"A {what} name is at most {MAX_NAME} characters.")
    return name


def _audit(conn, *, at: datetime, actor: str, kind: str, subject: str, detail: str) -> None:
    db.audit(conn, at=at.isoformat(sep=" ", timespec="minutes"), actor=actor,
             action="CALENDAR_CONFIG", subject_kind=kind, subject_id=subject, detail=detail)


def _fresh_id(conn, table: str, key: str, base: str) -> str:
    cand, n = base or "X", 2
    while conn.execute(f"SELECT 1 FROM {table} WHERE {key} = ?", (cand,)).fetchone():
        cand, n = f"{base}_{n}", n + 1
    return cand


def clean_time(value: str | None, what: str) -> str | None:
    """'8:00' -> '08:00'; blank -> None; anything else is refused."""
    text = (value or "").strip()
    if not text:
        return None
    if re.fullmatch(r"\d{1,2}:\d{2}", text):
        text = text.zfill(5)
    if not _TIME.match(text):
        raise Refused(f"{what}: write a time as HH:MM, 00:00 to 24:00.")
    return text


def clean_week(form: dict) -> dict[str, tuple[str | None, str | None]]:
    """The seven day windows from a form: `<day>_start` and `<day>_end`. A day
    with one side blank is refused; both blank is closed; end after start."""
    week = {}
    for day in DAYS:
        start = clean_time(form.get(f"{day}_start"), day.title())
        end = clean_time(form.get(f"{day}_end"), day.title())
        if (start is None) != (end is None):
            raise Refused(f"{day.title()}: give both a start and an end, or leave both blank for closed.")
        if start is not None and parse_clock_time(end) <= parse_clock_time(start):
            raise Refused(f"{day.title()}: the end must be after the start.")
        week[day] = (start, end)
    return week


# ---------------------------------------------------------------- reading

def calendars(conn: sqlite3.Connection) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT c.*, COALESCE(c.inactive, 0) AS retired, l.name AS holiday_list_name,"
        "       (SELECT COUNT(*) FROM board b WHERE b.calendar_id = c.calendar_id) AS boards"
        "  FROM calendar c LEFT JOIN holiday_list l ON l.holiday_list_id = c.holiday_list_id"
        " ORDER BY COALESCE(c.inactive, 0), c.name")]


def live_calendars(conn: sqlite3.Connection, keep: str | None = None) -> list[dict]:
    """For a picker: every calendar in use, plus `keep` (the one already chosen)
    even if it has been retired, so a save does not silently drop it."""
    return [c for c in calendars(conn) if not c["retired"] or c["calendar_id"] == keep]


def holiday_lists(conn: sqlite3.Connection) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT l.holiday_list_id, l.name,"
        "       (SELECT COUNT(*) FROM holiday h WHERE h.holiday_list_id = l.holiday_list_id) AS days,"
        "       (SELECT COUNT(*) FROM calendar c WHERE c.holiday_list_id = l.holiday_list_id) AS calendars"
        "  FROM holiday_list l ORDER BY l.name")]


def holidays(conn: sqlite3.Connection, holiday_list_id: str) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT observed_on, name, COALESCE(all_day, 1) AS all_day, time_start, time_end"
        "  FROM holiday WHERE holiday_list_id = ? ORDER BY observed_on", (holiday_list_id,))]


# -------------------------------------------------------------- calendars

def _week_words(week: dict) -> str:
    return " ".join(f"{d[:3].title()} {s}-{e}" if s else f"{d[:3].title()} closed"
                    for d, (s, e) in week.items())


def add_calendar(conn, name: str, week: dict, *, holiday_list_id: str | None = None,
                 at: datetime, actor: str) -> str:
    name = _name(name, "calendar")
    if conn.execute("SELECT 1 FROM calendar WHERE LOWER(name) = LOWER(?)", (name,)).fetchone():
        raise Refused(f"There is already a calendar called {name}.")
    if not any(s for s, _ in week.values()):
        raise Refused("A calendar needs at least one open day.")
    if holiday_list_id and conn.execute("SELECT 1 FROM holiday_list WHERE holiday_list_id = ?",
                                        (holiday_list_id,)).fetchone() is None:
        raise Refused("No such holiday list.")
    cid = _fresh_id(conn, "calendar", "calendar_id", slug(name))
    cols = ", ".join(f"{d}_start, {d}_end" for d in DAYS)
    values = [v for d in DAYS for v in week[d]]
    conn.execute(f"INSERT INTO calendar (calendar_id, name, holiday_list_id, inactive, {cols})"
                 f" VALUES (?,?,?,0,{','.join('?' * 14)})", [cid, name, holiday_list_id or None, *values])
    _audit(conn, at=at, actor=actor, kind="calendar", subject=cid,
           detail=f"calendar added: {name}; {_week_words(week)}; holidays {holiday_list_id or '-'}")
    return cid


def save_calendar(conn, calendar_id: str, *, name: str | None = None, week: dict | None = None,
                  holiday_list_id: str | None = None, set_list: bool = False,
                  inactive: bool | None = None, at: datetime, actor: str) -> str:
    row = conn.execute("SELECT * FROM calendar WHERE calendar_id = ?", (calendar_id,)).fetchone()
    if row is None:
        raise Refused("No such calendar.")
    changed = []
    if name is not None:
        name = _name(name, "calendar")
        if name != row["name"]:
            if conn.execute("SELECT 1 FROM calendar WHERE LOWER(name) = LOWER(?) AND calendar_id <> ?",
                            (name, calendar_id)).fetchone():
                raise Refused(f"There is already a calendar called {name}.")
            conn.execute("UPDATE calendar SET name = ? WHERE calendar_id = ?", (name, calendar_id))
            changed.append(f"renamed {row['name']!r} -> {name!r}")
    if week is not None:
        if not any(s for s, _ in week.values()):
            raise Refused("A calendar needs at least one open day.")
        old = {d: (row[f"{d}_start"], row[f"{d}_end"]) for d in DAYS}
        diff = {d: week[d] for d in DAYS if week[d] != old[d]}
        if diff:
            sets = ", ".join(f"{d}_start = ?, {d}_end = ?" for d in diff)
            conn.execute(f"UPDATE calendar SET {sets} WHERE calendar_id = ?",
                         [v for d in diff for v in diff[d]] + [calendar_id])
            changed.append("hours: " + "; ".join(
                f"{d[:3].title()} {old[d][0] or 'closed'}{('-' + old[d][1]) if old[d][0] else ''}"
                f" -> {week[d][0] or 'closed'}{('-' + week[d][1]) if week[d][0] else ''}" for d in diff))
    if set_list and (holiday_list_id or None) != row["holiday_list_id"]:
        if holiday_list_id and conn.execute("SELECT 1 FROM holiday_list WHERE holiday_list_id = ?",
                                            (holiday_list_id,)).fetchone() is None:
            raise Refused("No such holiday list.")
        conn.execute("UPDATE calendar SET holiday_list_id = ? WHERE calendar_id = ?",
                     (holiday_list_id or None, calendar_id))
        changed.append(f"holidays {row['holiday_list_id'] or '-'} -> {holiday_list_id or '-'}")
    if inactive is not None and int(inactive) != (row["inactive"] or 0):
        conn.execute("UPDATE calendar SET inactive = ? WHERE calendar_id = ?", (int(inactive), calendar_id))
        changed.append("retired" if inactive else "restored")
    if changed:
        _audit(conn, at=at, actor=actor, kind="calendar", subject=calendar_id, detail="; ".join(changed))
    return "; ".join(changed) or "nothing changed"


# ----------------------------------------------------------- holiday lists

def add_holiday_list(conn, name: str, *, at: datetime, actor: str) -> str:
    name = _name(name, "holiday list")
    if conn.execute("SELECT 1 FROM holiday_list WHERE LOWER(name) = LOWER(?)", (name,)).fetchone():
        raise Refused(f"There is already a holiday list called {name}.")
    lid = _fresh_id(conn, "holiday_list", "holiday_list_id", slug(name))
    conn.execute("INSERT INTO holiday_list (holiday_list_id, name) VALUES (?,?)", (lid, name))
    _audit(conn, at=at, actor=actor, kind="holiday_list", subject=lid, detail=f"holiday list added: {name}")
    return lid


def rename_holiday_list(conn, holiday_list_id: str, name: str, *, at: datetime, actor: str) -> str:
    row = conn.execute("SELECT name FROM holiday_list WHERE holiday_list_id = ?", (holiday_list_id,)).fetchone()
    if row is None:
        raise Refused("No such holiday list.")
    name = _name(name, "holiday list")
    if name == row["name"]:
        return "nothing changed"
    if conn.execute("SELECT 1 FROM holiday_list WHERE LOWER(name) = LOWER(?) AND holiday_list_id <> ?",
                    (name, holiday_list_id)).fetchone():
        raise Refused(f"There is already a holiday list called {name}.")
    conn.execute("UPDATE holiday_list SET name = ? WHERE holiday_list_id = ?", (name, holiday_list_id))
    _audit(conn, at=at, actor=actor, kind="holiday_list", subject=holiday_list_id,
           detail=f"renamed {row['name']!r} -> {name!r}")
    return f"renamed {row['name']!r} -> {name!r}"


def _date(value: str | None) -> str:
    text = (value or "").strip()
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError:
        raise Refused("A holiday needs a date, as YYYY-MM-DD.") from None


def add_holiday(conn, holiday_list_id: str, observed_on: str, name: str, *, all_day: bool = True,
                time_start: str | None = None, time_end: str | None = None,
                at: datetime, actor: str) -> str:
    """One holiday on a list: a whole day, or the hours it closes (the
    reference PSA's allDayFlag off with timeStart and timeEnd)."""
    if conn.execute("SELECT 1 FROM holiday_list WHERE holiday_list_id = ?", (holiday_list_id,)).fetchone() is None:
        raise Refused("No such holiday list.")
    day = _date(observed_on)
    name = _name(name, "holiday")[:50]
    start = end = None
    if not all_day:
        start, end = clean_time(time_start, "Closed from"), clean_time(time_end, "Closed until")
        if start is None or end is None:
            raise Refused("A part-day holiday needs the hours it closes, from and until.")
        if parse_clock_time(end) <= parse_clock_time(start):
            raise Refused("A part-day holiday must end after it starts.")
    if conn.execute("SELECT 1 FROM holiday WHERE holiday_list_id = ? AND observed_on = ?",
                    (holiday_list_id, day)).fetchone():
        raise Refused(f"{day} is already on this list.")
    conn.execute("INSERT INTO holiday (holiday_list_id, observed_on, name, all_day, time_start, time_end)"
                 " VALUES (?,?,?,?,?,?)", (holiday_list_id, day, name, 1 if all_day else 0, start, end))
    _audit(conn, at=at, actor=actor, kind="holiday_list", subject=holiday_list_id,
           detail=f"holiday added: {day} {name}" + ("" if all_day else f" (closed {start}-{end})"))
    return day


def remove_holiday(conn, holiday_list_id: str, observed_on: str, *, at: datetime, actor: str) -> str:
    day = _date(observed_on)
    row = conn.execute("SELECT name FROM holiday WHERE holiday_list_id = ? AND observed_on = ?",
                       (holiday_list_id, day)).fetchone()
    if row is None:
        raise Refused("No such holiday on this list.")
    conn.execute("DELETE FROM holiday WHERE holiday_list_id = ? AND observed_on = ?", (holiday_list_id, day))
    _audit(conn, at=at, actor=actor, kind="holiday_list", subject=holiday_list_id,
           detail=f"holiday removed: {day} {row['name']}; the clocks on this list recompute")
    return day


def import_csv(conn, holiday_list_id: str, path: str | Path, *, at: datetime, actor: str = "cli") -> dict:
    """Holidays from a CSV with columns Date, Name and optionally AllDay
    (yes/no), Start, End. A date already on the list is left as it is; nothing
    is removed. PMC's HR list is the source; nothing is compiled in."""
    path = Path(path)
    if not path.exists():
        raise LookupError(f"{path} does not exist")
    counts = {"rows": 0, "new": 0, "seen": 0}
    with path.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        cols = {c.strip().lower(): c for c in (reader.fieldnames or [])}
        if "date" not in cols or "name" not in cols:
            raise ValueError("the CSV needs columns Date and Name")
        for row in reader:
            counts["rows"] += 1
            day = _date(row[cols["date"]])
            if conn.execute("SELECT 1 FROM holiday WHERE holiday_list_id = ? AND observed_on = ?",
                            (holiday_list_id, day)).fetchone():
                counts["seen"] += 1
                continue
            all_day = (row.get(cols.get("allday", ""), "yes") or "yes").strip().lower() not in ("no", "0", "false")
            add_holiday(conn, holiday_list_id, day, row[cols["name"]], all_day=all_day,
                        time_start=row.get(cols.get("start", "")), time_end=row.get(cols.get("end", "")),
                        at=at, actor=actor)
            counts["new"] += 1
    return counts

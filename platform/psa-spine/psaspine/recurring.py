"""Recurring tickets (047): a board's template raised on a cadence.

Preventive maintenance is a ticket that must exist on a day nobody remembered:
the monthly analyser check, the quarterly printer care, the yearly UPS test. A
recurrence names a template, a cadence and the next due day. The minute runner
(`psaspine run-rules`) raises the ticket through the one door every ticket
uses, with the template's tasks, an owner or the board's queue, the machine it
concerns, and a line on the ticket saying which recurrence raised it. A runner
that was down raises the ticket once and moves the due day past today, never
once per missed period. Every change to a recurrence is audited.
"""
from __future__ import annotations

import calendar
import sqlite3
from datetime import date, datetime, timedelta

from . import db

CADENCES = {"DAILY": "day", "WEEKLY": "week", "MONTHLY": "month", "QUARTERLY": "quarter", "YEARLY": "year"}
MONTHS = {"MONTHLY": 1, "QUARTERLY": 3, "YEARLY": 12}
IMPACTS = ("I1", "I2", "I3")
URGENCIES = ("U1", "U2", "U3")
MAX_EVERY = 52


class Refused(ValueError):
    """A sentence for the person; nothing was written."""


def _stamp(at: datetime) -> str:
    return at.isoformat(sep=" ", timespec="minutes")


def _day(value) -> date:
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat((value or "").strip()[:10])
    except ValueError:
        raise Refused("The first due day is a date, e.g. 2026-10-01.") from None


def advance(day: date, cadence: str, n: int = 1, *, anchor_day: int | None = None) -> date:
    """The due day after `day`. A monthly series set on the 31st lands on the
    30th or 28th when the month is short and returns to the 31st after: the
    anchor is the day the series was set on, not the day it last landed."""
    if cadence == "DAILY":
        return day + timedelta(days=n)
    if cadence == "WEEKLY":
        return day + timedelta(weeks=n)
    months = MONTHS[cadence] * n
    y, m = day.year + (day.month - 1 + months) // 12, (day.month - 1 + months) % 12 + 1
    return date(y, m, min(anchor_day or day.day, calendar.monthrange(y, m)[1]))


def cadence_words(cadence: str, every_n: int) -> str:
    unit = CADENCES.get(cadence, cadence.lower())
    return f"Every {unit}" if every_n == 1 else f"Every {every_n} {unit}s"


def get(conn: sqlite3.Connection, recurrence_id: int):
    return conn.execute("SELECT * FROM recurrence WHERE recurrence_id = ?", (recurrence_id,)).fetchone()


def all_(conn: sqlite3.Connection, *, boards=None):
    """Every recurrence, or those on the boards given, with the template's and
    the board's names."""
    where, args = "", []
    if boards is not None:
        boards = sorted(boards)
        if not boards:
            return []
        where = f" WHERE r.board_id IN ({','.join('?' * len(boards))})"
        args = boards
    return conn.execute(
        "SELECT r.*, t.name AS template_name, b.display_name AS board_name FROM recurrence r"
        " JOIN ticket_template t ON t.template_id = r.template_id JOIN board b ON b.board_id = r.board_id"
        + where + " ORDER BY r.active DESC, r.next_due_on, r.name", args).fetchall()


def create(conn: sqlite3.Connection, *, name: str, template_id: str, cadence: str, first_due_on,
           every_n=1, owner: str | None = None, entity_id: str | None = None, contact_id: str | None = None,
           configuration_id: str | None = None, impact: str = "I3", urgency: str = "U3",
           at: datetime, actor: str) -> int:
    name = " ".join((name or "").split())[:120]
    if not name:
        raise Refused("A recurrence needs a name, e.g. Monthly analyser check.")
    tpl = conn.execute("SELECT * FROM ticket_template WHERE template_id = ? AND inactive = 0",
                       (template_id or "",)).fetchone()
    if tpl is None:
        raise Refused("Pick a template that is in use; the recurrence raises its ticket from it.")
    if cadence not in CADENCES:
        raise Refused("The cadence is daily, weekly, monthly, quarterly or yearly.")
    try:
        n = int(every_n or 1)
    except (TypeError, ValueError):
        raise Refused("Every N is a whole number.") from None
    if not 1 <= n <= MAX_EVERY:
        raise Refused(f"Every N is between 1 and {MAX_EVERY}.")
    first = _day(first_due_on)
    owner = (owner or "").strip() or None
    if owner and conn.execute("SELECT 1 FROM board_member WHERE board_id = ? AND LOWER(member) = LOWER(?)",
                              (tpl["board_id"], owner)).fetchone() is None:
        raise Refused(f"{owner} is not a member of the template's board; leave the owner blank for the board's queue.")
    entity_id = (entity_id or "").strip() or None
    if entity_id is None or conn.execute("SELECT 1 FROM entity WHERE entity_id = ?", (entity_id,)).fetchone() is None:
        raise Refused("Say which company the ticket is for.")
    contact_id = (contact_id or "").strip() or None
    if contact_id and conn.execute("SELECT 1 FROM contact WHERE contact_id = ?", (contact_id,)).fetchone() is None:
        raise Refused("No such contact.")
    configuration_id = (configuration_id or "").strip() or None
    if configuration_id and conn.execute("SELECT 1 FROM configuration WHERE configuration_id = ?",
                                         (configuration_id,)).fetchone() is None:
        raise Refused("No such configuration.")
    if impact not in IMPACTS or urgency not in URGENCIES:
        raise Refused("Impact is I1 to I3 and urgency U1 to U3.")
    stamp = _stamp(at)
    cur = conn.execute(
        "INSERT INTO recurrence (name, board_id, template_id, cadence, every_n, anchor_day, next_due_on, owner,"
        " entity_id, contact_id, configuration_id, impact, urgency, active, created_at, created_by)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,1,?,?)",
        (name, tpl["board_id"], template_id, cadence, n, first.day, first.isoformat(), owner, entity_id,
         contact_id, configuration_id, impact, urgency, stamp, actor))
    rid = cur.lastrowid
    db.audit(conn, at=stamp, actor=actor, action="RECURRENCE", subject_kind="recurrence", subject_id=str(rid),
             detail=f"created: {name}, {cadence_words(cadence, n).lower()} from {first.isoformat()}, template {template_id}")
    return rid


def set_active(conn: sqlite3.Connection, recurrence_id: int, active: bool, *, at: datetime, actor: str):
    row = get(conn, recurrence_id)
    if row is None:
        raise Refused("No such recurrence.")
    conn.execute("UPDATE recurrence SET active = ? WHERE recurrence_id = ?", (1 if active else 0, recurrence_id))
    db.audit(conn, at=_stamp(at), actor=actor, action="RECURRENCE", subject_kind="recurrence",
             subject_id=str(recurrence_id), detail="resumed" if active else "paused")
    return get(conn, recurrence_id)


def due(conn: sqlite3.Connection, today: date):
    return conn.execute("SELECT * FROM recurrence WHERE active = 1 AND next_due_on <= ? ORDER BY next_due_on, recurrence_id",
                        (today.isoformat(),)).fetchall()


def _raise(conn: sqlite3.Connection, rec, *, at: datetime, actor: str) -> str:
    """One ticket from the recurrence, through tasks.open_from_template."""
    from . import configurations, tasks
    from .board import _event
    requested_by = None
    if rec["contact_id"]:
        c = conn.execute("SELECT email FROM contact WHERE contact_id = ?", (rec["contact_id"],)).fetchone()
        requested_by = c["email"] if c and c["email"] else None
    wid = tasks.open_from_template(conn, rec["template_id"], impact=rec["impact"], urgency=rec["urgency"],
                                   requested_by=requested_by, at=at, actor=actor, entity_id=rec["entity_id"],
                                   owner=rec["owner"], source="DESK")
    conn.execute("UPDATE ticket SET recurrence_id = ? WHERE work_item_id = ?", (rec["recurrence_id"], wid))
    if rec["configuration_id"]:
        configurations.attach(conn, wid, rec["configuration_id"], at=at, actor=actor)
    _event(conn, wid, _stamp(at), "UPDATED", actor,
           f"raised by the recurrence {rec['name']} (#{rec['recurrence_id']}), due {rec['next_due_on']}")
    conn.execute("UPDATE recurrence SET last_raised_at = ?, last_work_item_id = ? WHERE recurrence_id = ?",
                 (_stamp(at), wid, rec["recurrence_id"]))
    return wid


def raise_due(conn: sqlite3.Connection, *, at: datetime, actor: str = "recurring") -> list[dict]:
    """Every active recurrence whose due day has come: one ticket each, and the
    due day moved past today. All or nothing per recurrence; a failure is
    audited and the others still run."""
    today = at.date()
    out = []
    for rec in due(conn, today):
        conn.execute("SAVEPOINT recurrence")
        try:
            wid = _raise(conn, rec, at=at, actor=actor)
            nxt = _day(rec["next_due_on"])
            while nxt <= today:
                nxt = advance(nxt, rec["cadence"], rec["every_n"], anchor_day=rec["anchor_day"])
            conn.execute("UPDATE recurrence SET next_due_on = ? WHERE recurrence_id = ?",
                         (nxt.isoformat(), rec["recurrence_id"]))
            conn.execute("RELEASE recurrence")
            out.append({"recurrence_id": rec["recurrence_id"], "work_item_id": wid, "next_due_on": nxt.isoformat()})
        except Exception as exc:                                    # noqa: BLE001
            conn.execute("ROLLBACK TO recurrence")
            conn.execute("RELEASE recurrence")
            db.audit(conn, at=_stamp(at), actor=actor, action="RECURRENCE", subject_kind="recurrence",
                     subject_id=str(rec["recurrence_id"]), detail=f"failed: {type(exc).__name__}: {exc}"[:500])
            out.append({"recurrence_id": rec["recurrence_id"], "error": str(exc)})
    conn.commit()
    return out


def run_now(conn: sqlite3.Connection, recurrence_id: int, *, at: datetime, actor: str) -> str:
    """One extra ticket, now, without moving the due day."""
    rec = get(conn, recurrence_id)
    if rec is None:
        raise Refused("No such recurrence.")
    wid = _raise(conn, rec, at=at, actor=actor)
    db.audit(conn, at=_stamp(at), actor=actor, action="RECURRENCE", subject_kind="recurrence",
             subject_id=str(recurrence_id), detail=f"run now: {wid}")
    return wid

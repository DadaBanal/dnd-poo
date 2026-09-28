"""Scheduling (032, 038): who goes where, when, on which ticket, and who is away.

The reference PSA's schedule, kept to what a hospital desk needs (its
ScheduleEntry, the record's extracted model, VERIFIED 9 Sep 2026 from its
published OpenAPI schema):

- **A visit** is a member, a start and an end on a ticket, with a **status**
  (the Schedule Status setup table: Firm, Tentative), a **where** (the Service
  Location setup table: On-site, Remote, In-house), a **lead** flag for the one
  who owns the visit when several go (its ownerFlag), **done** (doneFlag and
  closeDate) and **acknowledged** (acknowledgedFlag and acknowledgedDate, set by
  the member themselves).
- **A block** is what is on a person's schedule that is not a ticket: a
  meeting, an activity, or time off.
- **Conflicts** are refused unless the booking says to allow them (its
  allowScheduleConflictsFlag), and time off is never overridden: a person on
  leave is not dispatched. An allowed double booking is recorded as such.

Every visit change is a ticket event; every block and every setup change is an
audit row. Times are the desk's own local timestamps, from the browser's
date-time control. Not copied: reminders and recurring spans (see schema/038).
"""
from __future__ import annotations

import re
import sqlite3
from datetime import date, datetime, timedelta

from . import db

# INFERRED: the names the reference PSA ships in its Schedule Status and Service
# Location setup tables; both are rows here, renamed and added to in Setup.
STARTER_STATUSES = (("FIRM", "Firm", 1, 10), ("TENTATIVE", "Tentative", 0, 20))
STARTER_LOCATIONS = (("ON_SITE", "On-site"), ("REMOTE", "Remote"), ("IN_HOUSE", "In-house"))
BLOCK_KINDS = {"MEETING": "Meeting", "ACTIVITY": "Activity", "TIME_OFF": "Time off"}
MAX_VISIT_HOURS = 16
MAX_BLOCK_DAYS = 31


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


def slug(name: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "_", name.upper()).strip("_")


# ------------------------------------------------------------- vocabulary

def ensure_vocabulary(conn: sqlite3.Connection) -> None:
    """The starter statuses and locations, only into an empty table: once a
    person has edited either, it is theirs."""
    if conn.execute("SELECT COUNT(*) FROM schedule_status").fetchone()[0] == 0:
        for sid, name, default, order in STARTER_STATUSES:
            conn.execute("INSERT INTO schedule_status (status_id, name, is_default, inactive, sort_order)"
                         " VALUES (?,?,?,0,?)", (sid, name, default, order))
    if conn.execute("SELECT COUNT(*) FROM service_location").fetchone()[0] == 0:
        for lid, name in STARTER_LOCATIONS:
            conn.execute("INSERT INTO service_location (location_id, name, inactive) VALUES (?,?,0)", (lid, name))


def statuses(conn, *, all_rows: bool = False) -> list[dict]:
    ensure_vocabulary(conn)
    return [dict(r) for r in conn.execute(
        "SELECT * FROM schedule_status" + ("" if all_rows else " WHERE inactive = 0")
        + " ORDER BY inactive, sort_order, name")]


def locations(conn, *, all_rows: bool = False) -> list[dict]:
    ensure_vocabulary(conn)
    return [dict(r) for r in conn.execute(
        "SELECT * FROM service_location" + ("" if all_rows else " WHERE inactive = 0")
        + " ORDER BY inactive, name")]


def default_status(conn) -> str | None:
    rows = statuses(conn)
    for r in rows:
        if r["is_default"]:
            return r["status_id"]
    return rows[0]["status_id"] if rows else None


def _audit(conn, *, at: datetime, actor: str, action: str, kind: str, subject: str, detail: str) -> None:
    db.audit(conn, at=_stamp(at), actor=actor, action=action, subject_kind=kind, subject_id=subject,
             detail=detail)


def _vocab_name(value: str, what: str) -> str:
    name = " ".join((value or "").split())
    if not name:
        raise Refused(f"a {what} needs a name")
    return name[:50]


def add_status(conn, name: str, *, at: datetime, actor: str) -> str:
    ensure_vocabulary(conn)
    name = _vocab_name(name, "status")
    if conn.execute("SELECT 1 FROM schedule_status WHERE LOWER(name) = LOWER(?)", (name,)).fetchone():
        raise Refused(f"there is already a status called {name}")
    sid = slug(name) or "STATUS"
    n = 2
    while conn.execute("SELECT 1 FROM schedule_status WHERE status_id = ?", (sid,)).fetchone():
        sid, n = f"{slug(name)}_{n}", n + 1
    order = (conn.execute("SELECT MAX(sort_order) FROM schedule_status").fetchone()[0] or 0) + 10
    conn.execute("INSERT INTO schedule_status (status_id, name, is_default, inactive, sort_order)"
                 " VALUES (?,?,0,0,?)", (sid, name, order))
    _audit(conn, at=at, actor=actor, action="SCHEDULE_CONFIG", kind="schedule_status", subject=sid,
           detail=f"status added: {name}")
    return sid


def add_location(conn, name: str, *, at: datetime, actor: str) -> str:
    ensure_vocabulary(conn)
    name = _vocab_name(name, "location")
    if conn.execute("SELECT 1 FROM service_location WHERE LOWER(name) = LOWER(?)", (name,)).fetchone():
        raise Refused(f"there is already a location called {name}")
    lid = slug(name) or "LOCATION"
    n = 2
    while conn.execute("SELECT 1 FROM service_location WHERE location_id = ?", (lid,)).fetchone():
        lid, n = f"{slug(name)}_{n}", n + 1
    conn.execute("INSERT INTO service_location (location_id, name, inactive) VALUES (?,?,0)", (lid, name))
    _audit(conn, at=at, actor=actor, action="SCHEDULE_CONFIG", kind="service_location", subject=lid,
           detail=f"location added: {name}")
    return lid


def save_vocab(conn, kind: str, key: str, *, name: str | None = None, inactive: bool | None = None,
               make_default: bool = False, at: datetime, actor: str) -> str:
    """Rename, retire or restore a status or a location; make a status the default."""
    table, col = {"status": ("schedule_status", "status_id"), "location": ("service_location", "location_id")}[kind]
    row = conn.execute(f"SELECT * FROM {table} WHERE {col} = ?", (key,)).fetchone()
    if row is None:
        raise Refused(f"no such {kind}")
    changed = []
    if name is not None:
        name = _vocab_name(name, kind)
        if name != row["name"]:
            if conn.execute(f"SELECT 1 FROM {table} WHERE LOWER(name) = LOWER(?) AND {col} <> ?",
                            (name, key)).fetchone():
                raise Refused(f"there is already a {kind} called {name}")
            conn.execute(f"UPDATE {table} SET name = ? WHERE {col} = ?", (name, key))
            changed.append(f"renamed {row['name']!r} -> {name!r}")
    if inactive is not None and int(inactive) != row["inactive"]:
        if inactive and kind == "status" and row["is_default"]:
            raise Refused("the default status cannot be retired; make another the default first")
        conn.execute(f"UPDATE {table} SET inactive = ? WHERE {col} = ?", (int(inactive), key))
        changed.append("retired" if inactive else "restored")
    if make_default and kind == "status" and not row["is_default"]:
        if row["inactive"]:
            raise Refused("a retired status cannot be the default")
        conn.execute("UPDATE schedule_status SET is_default = 0")
        conn.execute("UPDATE schedule_status SET is_default = 1 WHERE status_id = ?", (key,))
        changed.append("made the default")
    if changed:
        _audit(conn, at=at, actor=actor, action="SCHEDULE_CONFIG", kind=table, subject=key,
               detail="; ".join(changed))
    return "; ".join(changed) or "nothing changed"


# --------------------------------------------------------------- reading

def entries_for(conn: sqlite3.Connection, work_item_id: str):
    return conn.execute(
        "SELECT s.*, st.name AS status_name, l.name AS location_name FROM ticket_schedule s"
        "  LEFT JOIN schedule_status st ON st.status_id = s.status_id"
        "  LEFT JOIN service_location l ON l.location_id = s.location_id"
        " WHERE s.work_item_id = ? ORDER BY s.starts_at", (work_item_id,)).fetchall()


def _visits(conn, boards, first: str, last: str):
    if not boards:
        return []
    marks = ",".join("?" * len(boards))
    return conn.execute(
        "SELECT s.*, w.name AS summary, t.board_id, t.priority, t.state, st.name AS status_name,"
        "       l.name AS location_name"
        "  FROM ticket_schedule s JOIN ticket t ON t.work_item_id = s.work_item_id"
        "  JOIN work_item w ON w.work_item_id = t.work_item_id"
        "  LEFT JOIN schedule_status st ON st.status_id = s.status_id"
        "  LEFT JOIN service_location l ON l.location_id = s.location_id"
        f" WHERE s.starts_at < ? AND s.ends_at > ? AND t.board_id IN ({marks})"
        " ORDER BY s.member, s.starts_at", (last, first, *boards)).fetchall()


def day(conn: sqlite3.Connection, boards, on: str):
    """Every visit starting on a day, on the boards given, with its ticket."""
    return [r for r in _visits(conn, boards, f"{on} 00:00", f"{on} 24:00") if r["starts_at"][:10] == on]


def members_of(conn, boards) -> list[str]:
    """The people who work the boards given: the rows of the schedule."""
    if not boards:
        return []
    marks = ",".join("?" * len(boards))
    return [r[0] for r in conn.execute(
        f"SELECT DISTINCT member FROM board_member WHERE board_id IN ({marks}) AND access IN ('WORK','ADMIN')"
        " ORDER BY member", tuple(boards))]


def blocks(conn, members, first: str, last: str):
    if not members:
        return []
    marks = ",".join("?" * len(members))
    return conn.execute(
        f"SELECT * FROM schedule_block WHERE starts_at < ? AND ends_at > ? AND LOWER(member) IN ({marks})"
        " ORDER BY member, starts_at", (last, first, *[m.lower() for m in members])).fetchall()


def week(conn, boards, start: date, *, days: int = 7) -> dict:
    """The schedule for `days` from `start`: visits on the boards given, and the
    blocks of everyone who works them or has a visit on them."""
    first, last = f"{start.isoformat()} 00:00", f"{(start + timedelta(days=days)).isoformat()} 00:00"
    visits = _visits(conn, boards, first, last)
    people = sorted(set(members_of(conn, boards)) | {v["member"] for v in visits}, key=str.lower)
    return {"visits": visits, "blocks": blocks(conn, people, first, last), "members": people}


# ------------------------------------------------------------- conflicts

def clash(conn, member: str, starts_at: datetime, ends_at: datetime, *,
          skip_visit: int | None = None, skip_block: int | None = None) -> tuple[str, str] | None:
    """What already holds this person at that time: (kind, words), or None.
    kind is TIME_OFF, which nothing overrides, or BUSY."""
    s, e = _stamp(starts_at), _stamp(ends_at)
    for b in conn.execute("SELECT block_id, kind, name FROM schedule_block WHERE LOWER(member) = LOWER(?)"
                          " AND starts_at < ? AND ends_at > ? ORDER BY kind DESC", (member, e, s)):
        if b["block_id"] == skip_block:
            continue
        words = f"{member} is {'away' if b['kind'] == 'TIME_OFF' else 'in ' + BLOCK_KINDS[b['kind']].lower()}: {b['name']}"
        return ("TIME_OFF" if b["kind"] == "TIME_OFF" else "BUSY", words)
    for v in conn.execute("SELECT schedule_id, work_item_id FROM ticket_schedule WHERE LOWER(member) = LOWER(?)"
                          " AND starts_at < ? AND ends_at > ?", (member, e, s)):
        if v["schedule_id"] == skip_visit:
            continue
        return ("BUSY", f"{member} is already booked then, on {v['work_item_id']}")
    return None


def _check(conn, member, starts_at, ends_at, *, allow: bool, skip_visit=None, skip_block=None,
           time_off_blocks: bool = True) -> bool:
    """Raise if the time is taken and not allowed; return whether a clash was allowed."""
    found = clash(conn, member, starts_at, ends_at, skip_visit=skip_visit, skip_block=skip_block)
    if found is None:
        return False
    kind, words = found
    if kind == "TIME_OFF" and time_off_blocks:
        raise Refused(words + "; time off is never double-booked")
    if not allow:
        raise Refused(words + ". Tick \"allow a double booking\" to book it anyway")
    return True


# ---------------------------------------------------------------- visits

def _vocab_ok(conn, status_id, location_id):
    if status_id and not conn.execute("SELECT 1 FROM schedule_status WHERE status_id = ? AND inactive = 0",
                                      (status_id,)).fetchone():
        raise Refused("no such schedule status in use")
    if location_id and not conn.execute("SELECT 1 FROM service_location WHERE location_id = ? AND inactive = 0",
                                        (location_id,)).fetchone():
        raise Refused("no such location in use")


def _span_ok(starts_at, ends_at):
    if ends_at <= starts_at:
        raise Refused("a visit ends after it starts")
    if (ends_at - starts_at).total_seconds() > MAX_VISIT_HOURS * 3600:
        raise Refused(f"a visit is at most {MAX_VISIT_HOURS} hours; book two")


def _words(r) -> str:
    return f"{r['member']}, {r['starts_at']} to {r['ends_at'][11:]}"


def add(conn: sqlite3.Connection, work_item_id: str, *, member: str, starts_at: datetime,
        ends_at: datetime, note: str | None, actor: str, at: datetime, status_id: str | None = None,
        location_id: str | None = None, is_lead: bool | None = None, allow_conflict: bool = False) -> int:
    from .board import _event, touch
    ensure_vocabulary(conn)
    member = (member or "").strip()
    if not member:
        raise Refused("a visit needs a person")
    _span_ok(starts_at, ends_at)
    if conn.execute("SELECT 1 FROM ticket WHERE work_item_id = ?", (work_item_id,)).fetchone() is None:
        raise LookupError(f"no ticket {work_item_id!r}")
    status_id = status_id or default_status(conn)
    _vocab_ok(conn, status_id, location_id)
    allowed = _check(conn, member, starts_at, ends_at, allow=allow_conflict)
    first = conn.execute("SELECT COUNT(*) FROM ticket_schedule WHERE work_item_id = ?",
                         (work_item_id,)).fetchone()[0] == 0
    lead = first if is_lead is None else bool(is_lead)
    if lead:
        conn.execute("UPDATE ticket_schedule SET is_lead = 0 WHERE work_item_id = ?", (work_item_id,))
    cur = conn.execute(
        "INSERT INTO ticket_schedule (work_item_id, member, starts_at, ends_at, note, created_at,"
        " created_by, status_id, location_id, is_lead, conflict_allowed) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (work_item_id, member, _stamp(starts_at), _stamp(ends_at), (note or "").strip()[:400] or None,
         _stamp(at), actor, status_id, location_id or None, int(lead), int(allowed)))
    sname = conn.execute("SELECT name FROM schedule_status WHERE status_id = ?", (status_id,)).fetchone()
    _event(conn, work_item_id, _stamp(at), "SCHEDULE", actor,
           f"visit scheduled: {member}, {_stamp(starts_at)} to {ends_at.strftime('%H:%M')}"
           + (f" ({sname[0].lower()})" if sname else "")
           + (", lead" if lead else "") + (", double booking allowed" if allowed else "")
           + (f" — {(note or '').strip()[:120]}" if (note or "").strip() else ""))
    touch(conn, work_item_id, at)
    from . import outbox
    outbox.queue_scheduled(conn, cur.lastrowid, at=at, actor=actor)
    return cur.lastrowid


def _visit(conn, schedule_id: int):
    row = conn.execute("SELECT * FROM ticket_schedule WHERE schedule_id = ?", (schedule_id,)).fetchone()
    if row is None:
        raise Refused("no such visit")
    return row


def update(conn, schedule_id: int, *, actor: str, at: datetime, member: str | None = None,
           starts_at: datetime | None = None, ends_at: datetime | None = None, status_id: str | None = None,
           location_id: str | None = None, note: str | None = None, allow_conflict: bool = False) -> str:
    """Move, resize or re-assign a visit, or change its status or where."""
    from .board import _event, touch
    r = _visit(conn, schedule_id)
    if r["done_at"]:
        raise Refused("a done visit is history; reopen it first")
    new_member = (member or "").strip() or r["member"]
    s = starts_at or parse_local(r["starts_at"])
    e = ends_at or parse_local(r["ends_at"])
    _span_ok(s, e)
    _vocab_ok(conn, status_id, location_id)
    changed = []
    moved = (new_member.lower() != r["member"].lower() or _stamp(s) != r["starts_at"] or _stamp(e) != r["ends_at"])
    allowed = bool(r["conflict_allowed"])
    if moved:
        allowed = _check(conn, new_member, s, e, allow=allow_conflict, skip_visit=schedule_id)
        changed.append(f"moved {_words(r)} -> {new_member}, {_stamp(s)} to {e.strftime('%H:%M')}")
    if status_id and status_id != r["status_id"]:
        changed.append(f"status {r['status_id'] or '-'} -> {status_id}")
    if location_id is not None and (location_id or None) != r["location_id"]:
        changed.append(f"where {r['location_id'] or '-'} -> {location_id or '-'}")
    if note is not None and ((note or "").strip()[:400] or None) != r["note"]:
        changed.append("note changed")
    if not changed:
        return "nothing changed"
    conn.execute(
        "UPDATE ticket_schedule SET member = ?, starts_at = ?, ends_at = ?, status_id = ?, location_id = ?,"
        " note = ?, conflict_allowed = ?, acknowledged_at = ? WHERE schedule_id = ?",
        (new_member, _stamp(s), _stamp(e), status_id or r["status_id"],
         (location_id or None) if location_id is not None else r["location_id"],
         ((note or "").strip()[:400] or None) if note is not None else r["note"], int(allowed),
         None if moved else r["acknowledged_at"], schedule_id))
    _event(conn, r["work_item_id"], _stamp(at), "SCHEDULE", actor, "visit changed: " + "; ".join(changed))
    touch(conn, r["work_item_id"], at)
    if moved and new_member.lower() != r["member"].lower():
        from . import outbox
        outbox.queue_scheduled(conn, schedule_id, at=at, actor=actor)
    return "; ".join(changed)


def set_done(conn, schedule_id: int, done: bool, *, actor: str, at: datetime) -> None:
    from .board import _event, touch
    r = _visit(conn, schedule_id)
    if bool(r["done_at"]) == done:
        return
    conn.execute("UPDATE ticket_schedule SET done_at = ? WHERE schedule_id = ?",
                 (_stamp(at) if done else None, schedule_id))
    _event(conn, r["work_item_id"], _stamp(at), "SCHEDULE", actor,
           f"visit {'done' if done else 'reopened'}: {_words(r)}")
    touch(conn, r["work_item_id"], at)


def acknowledge(conn, schedule_id: int, *, member: str, at: datetime) -> None:
    """The scheduled person says they have seen it. Only they can."""
    from .board import _event
    r = _visit(conn, schedule_id)
    if r["member"].lower() != (member or "").lower():
        raise Refused(f"only {r['member']} can acknowledge their own visit")
    if r["acknowledged_at"]:
        return
    conn.execute("UPDATE ticket_schedule SET acknowledged_at = ? WHERE schedule_id = ?", (_stamp(at), schedule_id))
    _event(conn, r["work_item_id"], _stamp(at), "SCHEDULE", member, f"visit acknowledged: {_words(r)}")


def make_lead(conn, schedule_id: int, *, actor: str, at: datetime) -> None:
    from .board import _event
    r = _visit(conn, schedule_id)
    if r["is_lead"]:
        return
    conn.execute("UPDATE ticket_schedule SET is_lead = 0 WHERE work_item_id = ?", (r["work_item_id"],))
    conn.execute("UPDATE ticket_schedule SET is_lead = 1 WHERE schedule_id = ?", (schedule_id,))
    _event(conn, r["work_item_id"], _stamp(at), "SCHEDULE", actor, f"visit lead: {r['member']}")


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


# ---------------------------------------------------------------- blocks

def add_block(conn, *, member: str, kind: str, name: str, starts_at: datetime, ends_at: datetime,
              actor: str, at: datetime, allow_conflict: bool = False) -> int:
    """Time off, a meeting or an activity on a person's schedule. Time off over
    a booked visit is refused unless allowed, so a visit is never silently
    orphaned; the visit then shows as a clash on the schedule."""
    member = (member or "").strip()
    if not member:
        raise Refused("a block needs a person")
    if kind not in BLOCK_KINDS:
        raise Refused("a block is a meeting, an activity or time off")
    name = " ".join((name or "").split())[:120] or BLOCK_KINDS[kind]
    if ends_at <= starts_at:
        raise Refused("a block ends after it starts")
    if (ends_at - starts_at).days > MAX_BLOCK_DAYS:
        raise Refused(f"a block is at most {MAX_BLOCK_DAYS} days; add another")
    allowed = _check(conn, member, starts_at, ends_at, allow=allow_conflict, time_off_blocks=kind != "TIME_OFF")
    cur = conn.execute(
        "INSERT INTO schedule_block (member, kind, name, starts_at, ends_at, created_at, created_by)"
        " VALUES (?,?,?,?,?,?,?)", (member, kind, name, _stamp(starts_at), _stamp(ends_at), _stamp(at), actor))
    _audit(conn, at=at, actor=actor, action="SCHEDULE_BLOCK", kind="schedule_block", subject=str(cur.lastrowid),
           detail=f"{BLOCK_KINDS[kind].lower()} added: {member}, {_stamp(starts_at)} to {_stamp(ends_at)}, {name}"
           + (", over a booking (allowed)" if allowed else ""))
    return cur.lastrowid


def remove_block(conn, block_id: int, *, actor: str, at: datetime) -> bool:
    row = conn.execute("SELECT * FROM schedule_block WHERE block_id = ?", (block_id,)).fetchone()
    if row is None:
        return False
    conn.execute("DELETE FROM schedule_block WHERE block_id = ?", (block_id,))
    _audit(conn, at=at, actor=actor, action="SCHEDULE_BLOCK", kind="schedule_block", subject=str(block_id),
           detail=f"{BLOCK_KINDS[row['kind']].lower()} removed: {row['member']}, {row['starts_at']} to "
                  f"{row['ends_at']}, {row['name']}")
    return True

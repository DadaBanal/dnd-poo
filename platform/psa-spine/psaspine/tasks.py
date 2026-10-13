"""Ticket tasks and ticket templates (026).

A task is a line of a ticket's checklist; ticking it off records who and when,
and unticking it says so too. A template is a board's recipe for repeatable
work. `open_from_template` starts a ticket from one through tickets.open_ticket,
the one door every ticket uses; `apply_template` adds a template's tasks to a
ticket already open, and applying the same template twice adds nothing twice.
"""
from __future__ import annotations

import re
import sqlite3
from datetime import datetime

from . import db


def _stamp(at: datetime) -> str:
    return at.isoformat(sep=" ", timespec="minutes")


def tasks_of(conn: sqlite3.Connection, work_item_id: str) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM ticket_task WHERE work_item_id = ?"
                        " ORDER BY sort_order, task_id", (work_item_id,)).fetchall()


def _grid(conn) -> bool:
    """Whether the store has taken 080 (the reference PSA's grid columns)."""
    return db.column_exists(conn, "ticket_task", "notes")


def add_task(conn: sqlite3.Connection, work_item_id: str, text: str, *, actor: str,
             at: datetime, template_id: str | None = None, notes: str | None = None) -> int:
    from .board import _event, touch
    text = (text or "").strip()
    if not text:
        raise ValueError("a task needs some words")
    order = conn.execute("SELECT COALESCE(MAX(sort_order), 0) + 10 FROM ticket_task"
                         " WHERE work_item_id = ?", (work_item_id,)).fetchone()[0]
    cur = conn.execute(
        "INSERT INTO ticket_task (work_item_id, text, sort_order, template_id, created_at,"
        " created_by) VALUES (?,?,?,?,?,?)",
        (work_item_id, text[:400], order, template_id, _stamp(at), actor))
    if _grid(conn):
        conn.execute("UPDATE ticket_task SET notes = ? WHERE task_id = ?", ((notes or "").strip()[:2000] or None, cur.lastrowid))
        _renumber(conn, work_item_id)
    if template_id is None:
        _event(conn, work_item_id, _stamp(at), "TASK", actor, f"task added: {text[:200]}")
        touch(conn, work_item_id, at)
    return cur.lastrowid


# 080 (Dada, 13 Oct 2026): the reference PSA's Tasks grid. Priority is the
# task's place in the list, 1 first, kept in step with the order; notes and
# resolution are the two words columns; a task scheduled to a member is a
# visit on the ticket, and the task remembers which.

def task_of(conn: sqlite3.Connection, task_id: int):
    return conn.execute("SELECT * FROM ticket_task WHERE task_id = ?", (task_id,)).fetchone()


def _renumber(conn, work_item_id: str) -> None:
    for n, r in enumerate(tasks_of(conn, work_item_id), 1):
        conn.execute("UPDATE ticket_task SET sort_order = ?, priority = ? WHERE task_id = ?", (n * 10, n, r["task_id"]))


def update_task(conn: sqlite3.Connection, task_id: int, *, actor: str, at: datetime, text: str | None = None,
                notes: str | None = None, resolution: str | None = None) -> list[str]:
    """Change a task's words, notes or resolution; None leaves a field alone.
    One history line names what changed, never the whole text twice."""
    from .board import _event, touch
    row = task_of(conn, task_id)
    if row is None:
        raise LookupError("no such task")
    changes = {}
    if text is not None:
        new = " ".join(text.split())[:400]
        if not new:
            raise ValueError("a task needs some words")
        if new != row["text"]:
            changes["text"] = new
    if _grid(conn):
        for key, value in (("notes", notes), ("resolution", resolution)):
            if value is not None and (value.strip()[:2000] or None) != row[key]:
                changes[key] = value.strip()[:2000] or None
    if changes:
        conn.execute("UPDATE ticket_task SET " + ", ".join(f"{k} = ?" for k in changes) + " WHERE task_id = ?",
                     [*changes.values(), task_id])
        _event(conn, row["work_item_id"], _stamp(at), "TASK", actor,
               f"task {row['priority'] or ''} {', '.join(changes)} changed: {(changes.get('text') or row['text'])[:120]}".replace("task  ", "task "))
        touch(conn, row["work_item_id"], at)
    return list(changes)


def reorder(conn: sqlite3.Connection, work_item_id: str, ordered_ids, *, actor: str, at: datetime) -> bool:
    """The grid's order after a drag: every task of the ticket, once each;
    anything else is refused and nothing moves."""
    from .board import _event, touch
    have = [r["task_id"] for r in tasks_of(conn, work_item_id)]
    want = []
    for x in ordered_ids:
        try:
            want.append(int(x))
        except (TypeError, ValueError):
            raise ValueError("the order must name tasks")
    if sorted(want) != sorted(have) or len(want) != len(set(want)):
        raise ValueError("the order must name every task of this ticket once")
    if want == have:
        return False
    for n, tid in enumerate(want, 1):
        conn.execute("UPDATE ticket_task SET sort_order = ?, priority = ? WHERE task_id = ?", (n * 10, n, tid))
    _event(conn, work_item_id, _stamp(at), "TASK", actor, "tasks reordered")
    touch(conn, work_item_id, at)
    return True


def move_task(conn: sqlite3.Connection, task_id: int, direction: str, *, actor: str, at: datetime) -> bool:
    """Up or down one place (the no-script way to reorder)."""
    row = task_of(conn, task_id)
    if row is None:
        raise LookupError("no such task")
    ids = [r["task_id"] for r in tasks_of(conn, row["work_item_id"])]
    i = ids.index(task_id)
    j = i - 1 if direction == "up" else i + 1
    if j < 0 or j >= len(ids):
        return False
    ids[i], ids[j] = ids[j], ids[i]
    return reorder(conn, row["work_item_id"], ids, actor=actor, at=at)


def remove_task(conn: sqlite3.Connection, task_id: int, *, actor: str, at: datetime) -> None:
    """Take a task off the list. Its visit, if it has one, stays on the ticket."""
    from .board import _event, touch
    row = task_of(conn, task_id)
    if row is None:
        raise LookupError("no such task")
    conn.execute("DELETE FROM ticket_task WHERE task_id = ?", (task_id,))
    if _grid(conn):
        _renumber(conn, row["work_item_id"])
    _event(conn, row["work_item_id"], _stamp(at), "TASK", actor, f"task removed: {row['text'][:200]}")
    touch(conn, row["work_item_id"], at)


def schedule_task(conn: sqlite3.Connection, task_id: int, *, member: str, starts_at: datetime, ends_at: datetime,
                  actor: str, at: datetime) -> int:
    """Book a visit on the ticket for this task, as the reference PSA's
    Schedule column does, and remember it on the task. A task already
    scheduled is refused: unschedule it on the Schedule tab first."""
    from . import schedule
    row = task_of(conn, task_id)
    if row is None:
        raise LookupError("no such task")
    if not _grid(conn):
        raise ValueError("this store has not taken 080 yet")
    if row["schedule_id"] and conn.execute("SELECT 1 FROM ticket_schedule WHERE schedule_id = ?",
                                           (row["schedule_id"],)).fetchone():
        raise ValueError("this task is already scheduled; change the visit on the Schedule tab")
    sid = schedule.add(conn, row["work_item_id"], member=member, starts_at=starts_at, ends_at=ends_at,
                       note=f"Task {row['priority'] or ''}: {row['text']}".replace("Task :", "Task:")[:400],
                       actor=actor, at=at)
    conn.execute("UPDATE ticket_task SET schedule_id = ? WHERE task_id = ?", (sid, task_id))
    return sid


def visits_of(conn: sqlite3.Connection, work_item_id: str) -> dict:
    """schedule_id -> the visit, for the grid's Schedule column."""
    if not _grid(conn):
        return {}
    return {r["schedule_id"]: r for r in conn.execute(
        "SELECT s.schedule_id, s.member, s.starts_at, s.ends_at, s.done_at FROM ticket_schedule s"
        " JOIN ticket_task k ON k.schedule_id = s.schedule_id WHERE k.work_item_id = ?", (work_item_id,))}


def set_done(conn: sqlite3.Connection, task_id: int, done: bool, *, actor: str,
             at: datetime) -> str:
    """Tick or untick a task. Returns the ticket it belongs to."""
    from .board import _event, touch
    t = conn.execute("SELECT * FROM ticket_task WHERE task_id = ?", (task_id,)).fetchone()
    if t is None:
        raise LookupError(f"no task {task_id}")
    if bool(t["done_at"]) == done:
        return t["work_item_id"]
    conn.execute("UPDATE ticket_task SET done_at = ?, done_by = ? WHERE task_id = ?",
                 (_stamp(at) if done else None, actor if done else None, task_id))
    _event(conn, t["work_item_id"], _stamp(at), "TASK", actor,
           f"task {'done' if done else 'reopened'}: {t['text'][:200]}")
    touch(conn, t["work_item_id"], at)
    return t["work_item_id"]


def progress(conn: sqlite3.Connection, work_item_id: str) -> tuple[int, int]:
    row = conn.execute("SELECT COUNT(*), COUNT(done_at) FROM ticket_task WHERE work_item_id = ?",
                       (work_item_id,)).fetchone()
    return row[1], row[0]


# ------------------------------------------------------------------ templates

def template_id_for(name: str) -> str:
    return "TPL_" + (re.sub(r"[^A-Z0-9]+", "_", name.upper()).strip("_")[:40] or "TEMPLATE")


def save_template(conn: sqlite3.Connection, *, board_id: str, name: str, actor: str,
                  at: datetime, summary: str | None = None, record_type: str | None = None,
                  catalogue_item_id: str | None = None, description: str | None = None,
                  task_lines: list[str] | None = None) -> str:
    """Create a template. The Type must be one the board takes."""
    from . import itil
    name = (name or "").strip()
    if not name:
        raise ValueError("a template needs a name")
    if record_type and not itil.accepts(conn, board_id, record_type):
        raise itil.NotAccepted(f"this board does not take a {itil.LABEL[record_type].lower()}")
    base = tid = template_id_for(name)
    n = 1
    while conn.execute("SELECT 1 FROM ticket_template WHERE template_id = ?", (tid,)).fetchone():
        n += 1
        tid = f"{base}_{n}"
    conn.execute(
        "INSERT INTO ticket_template (template_id, board_id, name, summary, record_type,"
        " catalogue_item_id, description, created_at, created_by) VALUES (?,?,?,?,?,?,?,?,?)",
        (tid, board_id, name, (summary or "").strip() or None, record_type or None,
         catalogue_item_id or None, (description or "").strip() or None, _stamp(at), actor))
    lines = [x.strip() for x in (task_lines or []) if x.strip()]
    for i, line in enumerate(lines, start=1):
        conn.execute("INSERT INTO ticket_template_task (template_id, sort_order, text)"
                     " VALUES (?,?,?)", (tid, i * 10, line[:400]))
    db.audit(conn, at=_stamp(at), actor=actor, action="TEMPLATE_CREATE",
             subject_kind="ticket_template", subject_id=tid,
             detail=f"{name} on {board_id}: {len(lines)} task(s)")
    return tid


def apply_template(conn: sqlite3.Connection, work_item_id: str, template_id: str, *,
                   actor: str, at: datetime) -> int:
    """Add the template's tasks to the ticket. Applying it again adds none."""
    from .board import _event, touch
    tpl = conn.execute("SELECT * FROM ticket_template WHERE template_id = ?",
                       (template_id,)).fetchone()
    if tpl is None:
        raise LookupError(f"no template {template_id!r}")
    if conn.execute("SELECT 1 FROM ticket_task WHERE work_item_id = ? AND template_id = ?",
                    (work_item_id, template_id)).fetchone():
        return 0
    lines = conn.execute("SELECT text FROM ticket_template_task WHERE template_id = ?"
                         " ORDER BY sort_order", (template_id,)).fetchall()
    for line in lines:
        add_task(conn, work_item_id, line["text"], actor=actor, at=at, template_id=template_id)
    _event(conn, work_item_id, _stamp(at), "TEMPLATE", actor,
           f"template {tpl['name']} applied: {len(lines)} task(s)")
    touch(conn, work_item_id, at)
    return len(lines)


def open_from_template(conn: sqlite3.Connection, template_id: str, *, impact: str, urgency: str,
                       requested_by: str | None, at: datetime, actor: str,
                       summary: str | None = None, entity_id: str | None = None,
                       owner: str | None = None, source: str = "DESK") -> str:
    """A new ticket from a template, through the one door every ticket uses."""
    from . import tickets
    tpl = conn.execute("SELECT * FROM ticket_template WHERE template_id = ? AND inactive = 0",
                       (template_id,)).fetchone()
    if tpl is None:
        raise LookupError(f"no active template {template_id!r}")
    wid = tickets.open_ticket(
        conn, board_id=tpl["board_id"], summary=(summary or "").strip() or tpl["summary"] or tpl["name"],
        impact=impact, urgency=urgency, requested_by=requested_by, at=at, actor=actor,
        description=tpl["description"], entity_id=entity_id, owner=owner, source=source,
        record_type=tpl["record_type"], catalogue_item_id=tpl["catalogue_item_id"])
    apply_template(conn, wid, template_id, actor=actor, at=at)
    return wid

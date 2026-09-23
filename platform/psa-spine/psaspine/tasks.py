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


def add_task(conn: sqlite3.Connection, work_item_id: str, text: str, *, actor: str,
             at: datetime, template_id: str | None = None) -> int:
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
    if template_id is None:
        _event(conn, work_item_id, _stamp(at), "TASK", actor, f"task added: {text[:200]}")
        touch(conn, work_item_id, at)
    return cur.lastrowid


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

"""On-call paging (050): a page repeats until somebody answers.

A page is one episode on one ticket: the person paged (the one on call, the
duty manager, or a named member), how often it repeats and how many times.
Each attempt is an email to the person and a card in every Teams channel
that carries pages. It ends when the person acknowledges it on the ticket
(or writes a note there), when someone stops it, when the ticket closes, or
when the attempts run out: then it is EXHAUSTED and, if it was the on-call,
the duty manager is paged in turn. The runner (`run-rules`, every minute)
moves the clock; nothing here sends anything itself.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta

from . import db

DEFAULT_EVERY_MINUTES = 5
DEFAULT_MAX_ATTEMPTS = 3
ROLES = ("ON_CALL", "DUTY_MANAGER", "NAMED")
CLOSED_STATES = ("RESOLVED", "CLOSED", "CANCELLED")


class Refused(ValueError):
    """A sentence for the person; nothing was written."""


def _stamp(at: datetime) -> str:
    return at.isoformat(sep=" ", timespec="minutes")


def get(conn: sqlite3.Connection, page_id: int):
    return conn.execute("SELECT * FROM page WHERE page_id = ?", (page_id,)).fetchone()


def open_for(conn: sqlite3.Connection, work_item_id: str) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM page WHERE work_item_id = ? AND status = 'OPEN' ORDER BY page_id",
                        (work_item_id,)).fetchall()


def history(conn: sqlite3.Connection, work_item_id: str) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM page WHERE work_item_id = ? ORDER BY page_id", (work_item_id,)).fetchall()


def _ticket(conn, work_item_id):
    return conn.execute("SELECT t.work_item_id, t.board_id, t.state, t.priority, t.closed_at, b.display_name AS board_name"
                        "  FROM ticket t JOIN board b ON b.board_id = t.board_id WHERE t.work_item_id = ?",
                        (work_item_id,)).fetchone()


def _send(conn, page, tk, *, at: datetime) -> None:
    """One attempt: the email, and a card to every channel that carries pages."""
    from . import channels
    from .board import _event
    from .intake import subject_token
    n = page["attempts"] + 1
    stamp = _stamp(at)
    subject = f"{subject_token(page['work_item_id'])} Page {n} of {page['max_attempts']}: {tk['priority']} on {tk['board_name']}"
    body = (f"You are paged for {page['work_item_id']} ({tk['priority']}, {tk['board_name']}). "
            + (f"{page['note']} " if page["note"] else "")
            + f"Open the ticket and acknowledge the page; it repeats every {page['every_minutes']} minutes until you do.")
    conn.execute(
        "INSERT INTO notification (work_item_id, recipient, recipient_role, subject, body, created_at, status,"
        " channel, page_id) VALUES (?,?,?,?,?,?,'PENDING','EMAIL',?)",
        (page["work_item_id"], page["member"], "PAGE", subject, body, stamp, page["page_id"]))
    for tgt in channels.targets(conn, active_only=True):
        if tgt["pages"]:
            channels.queue_teams(conn, page["work_item_id"], tgt["target_id"], subject=subject,
                                 body=f"Paging {page['member']} ({page['role'].replace('_', ' ').lower()}), attempt {n} of {page['max_attempts']}.",
                                 at=at, page_id=page["page_id"], actor="paging")
    conn.execute("UPDATE page SET attempts = ?, last_sent_at = ? WHERE page_id = ?", (n, stamp, page["page_id"]))
    _event(conn, page["work_item_id"], stamp, "NOTIFY", "paging",
           f"page {n} of {page['max_attempts']} to {page['member']} ({page['role'].replace('_', ' ').lower()})")


def start(conn: sqlite3.Connection, work_item_id: str, *, member: str, role: str = "NAMED",
          every_minutes: int = DEFAULT_EVERY_MINUTES, max_attempts: int = DEFAULT_MAX_ATTEMPTS,
          at: datetime, actor: str, note: str | None = None) -> int:
    """Page a person about a ticket, first attempt now. A page already open for
    the same person on the same ticket is returned, not doubled: a rule that
    fires every minute must not page every minute."""
    tk = _ticket(conn, work_item_id)
    if tk is None:
        raise Refused("No such ticket.")
    if tk["state"] in CLOSED_STATES or tk["closed_at"]:
        raise Refused("A closed ticket pages nobody.")
    member = (member or "").strip()
    if not member:
        raise Refused("A page needs a person.")
    if role not in ROLES:
        raise Refused("A page is to the on-call, the duty manager or a named person.")
    if not (1 <= int(every_minutes) <= 120) or not (1 <= int(max_attempts) <= 20):
        raise Refused("A page repeats every 1 to 120 minutes, 1 to 20 times.")
    for p in open_for(conn, work_item_id):
        if p["member"].lower() == member.lower():
            return p["page_id"]
    stamp = _stamp(at)
    cur = conn.execute(
        "INSERT INTO page (work_item_id, member, role, started_at, started_by, every_minutes, max_attempts,"
        " attempts, status, note) VALUES (?,?,?,?,?,?,?,0,'OPEN',?)",
        (work_item_id, member, role, stamp, actor, int(every_minutes), int(max_attempts),
         " ".join((note or "").split())[:300] or None))
    pid = cur.lastrowid
    db.audit(conn, at=stamp, actor=actor, action="PAGE", subject_kind="page", subject_id=str(pid),
             detail=f"started to {member} ({role.lower()}) on {work_item_id}: every {every_minutes} min, {max_attempts} times")
    _send(conn, get(conn, pid), tk, at=at)
    return pid


def page_oncall(conn: sqlite3.Connection, work_item_id: str, *, at: datetime, actor: str,
                every_minutes: int = DEFAULT_EVERY_MINUTES, max_attempts: int = DEFAULT_MAX_ATTEMPTS,
                note: str | None = None) -> int:
    """Page whoever the rota says is on call for the ticket's board now, or the
    duty manager when nobody is; refuse in words when the rota is empty."""
    from .board import current_oncall
    tk = _ticket(conn, work_item_id)
    if tk is None:
        raise Refused("No such ticket.")
    for role in ("ON_CALL", "DUTY_MANAGER"):
        who = current_oncall(conn, tk["board_id"], role, at=at)
        if who:
            return start(conn, work_item_id, member=who, role=role, every_minutes=every_minutes,
                         max_attempts=max_attempts, at=at, actor=actor, note=note)
    raise LookupError(f"nobody is on call for {tk['board_name']} right now (On-call rota)")


def _end(conn, page, status: str, *, at: datetime, actor: str, why: str) -> None:
    from .board import _event
    stamp = _stamp(at)
    conn.execute("UPDATE page SET status = ?, ended_at = ?, ended_by = ? WHERE page_id = ? AND status = 'OPEN'",
                 (status, stamp, actor, page["page_id"]))
    _event(conn, page["work_item_id"], stamp, "UPDATED", actor, f"page to {page['member']} {why}")
    db.audit(conn, at=stamp, actor=actor, action="PAGE", subject_kind="page", subject_id=str(page["page_id"]),
             detail=f"{status.lower()} on {page['work_item_id']}: {why}")


def acknowledge(conn: sqlite3.Connection, page_id: int, *, at: datetime, actor: str):
    page = get(conn, page_id)
    if page is None:
        raise Refused("No such page.")
    if page["status"] != "OPEN":
        raise Refused(f"This page already ended ({page['status'].lower()}).")
    _end(conn, page, "ACKNOWLEDGED", at=at, actor=actor, why=f"acknowledged by {actor}")
    return get(conn, page_id)


def stop(conn: sqlite3.Connection, page_id: int, *, at: datetime, actor: str, reason: str | None = None):
    page = get(conn, page_id)
    if page is None:
        raise Refused("No such page.")
    if page["status"] != "OPEN":
        raise Refused(f"This page already ended ({page['status'].lower()}).")
    why = "stopped by " + actor + (f": {' '.join(reason.split())[:200]}" if reason and reason.strip() else "")
    _end(conn, page, "STOPPED", at=at, actor=actor, why=why)
    return get(conn, page_id)


def note_by(conn: sqlite3.Connection, work_item_id: str, actor: str, *, at: datetime) -> int:
    """A note on the ticket by the person paged is an answer: their open
    pages end as acknowledged. Returns how many did."""
    n = 0
    for p in open_for(conn, work_item_id):
        if p["member"].lower() == (actor or "").lower():
            _end(conn, p, "ACKNOWLEDGED", at=at, actor=actor, why=f"acknowledged by {actor}, who wrote on the ticket")
            n += 1
    return n


def tick(conn: sqlite3.Connection, *, at: datetime) -> dict:
    """Move every open page along: repeat what is due, end what the ticket's
    close ends, hand an unanswered on-call page to the duty manager."""
    from .board import current_oncall
    counts = {"open": 0, "sent": 0, "ended": 0, "escalated": 0}
    for page in conn.execute("SELECT * FROM page WHERE status = 'OPEN' ORDER BY page_id").fetchall():
        counts["open"] += 1
        tk = _ticket(conn, page["work_item_id"])
        if tk is None or tk["state"] in CLOSED_STATES or tk["closed_at"]:
            _end(conn, page, "STOPPED", at=at, actor="paging", why="ended: the ticket closed")
            counts["ended"] += 1
            continue
        last = datetime.fromisoformat(page["last_sent_at"]) if page["last_sent_at"] else None
        due = last is None or last + timedelta(minutes=page["every_minutes"]) <= at
        if not due:
            continue
        if page["attempts"] < page["max_attempts"]:
            _send(conn, page, tk, at=at)
            counts["sent"] += 1
            continue
        _end(conn, page, "EXHAUSTED", at=at, actor="paging",
             why=f"unanswered after {page['attempts']} attempts")
        counts["ended"] += 1
        if page["role"] == "ON_CALL":
            dm = current_oncall(conn, tk["board_id"], "DUTY_MANAGER", at=at)
            if dm and dm.lower() != page["member"].lower():
                start(conn, page["work_item_id"], member=dm, role="DUTY_MANAGER", every_minutes=page["every_minutes"],
                      max_attempts=page["max_attempts"], at=at, actor="paging",
                      note=f"The on-call ({page['member']}) did not answer {page['attempts']} pages.")
                counts["escalated"] += 1
            else:
                from .board import _event
                _event(conn, page["work_item_id"], _stamp(at), "UPDATED", "paging",
                       "nobody to escalate to: no duty manager on the rota now")
    return counts

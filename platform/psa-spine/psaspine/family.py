"""Child tickets (030): one parent, many children, one level, close together.

Dada PSA's parent/child, as a fulfiller uses it: a ward reports the same
outage five times; the first ticket becomes the parent and the rest are attached
as children, so one person works one ticket and every requester still has their
own. When the parent closes, each child closes on its own board's closed status
with an event saying so; a child that cannot close (a change awaiting approval,
a board with no closed status) is left open and says why, and the parent still
closes. Detaching a child gives it its own life back.

Rules, each refused with a sentence: a ticket is not its own parent; a child has
no children and a parent has no parent (one level, so no loops); only open
tickets are attached; a child already attached elsewhere is moved, never
duplicated.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime

CLOSED_STATES = ("RESOLVED", "CLOSED", "CANCELLED")


class Refused(ValueError):
    """The attachment breaks a rule; the sentence says which."""


def _stamp(at: datetime) -> str:
    return at.isoformat(sep=" ", timespec="minutes")


def _ticket(conn: sqlite3.Connection, work_item_id: str):
    row = conn.execute(
        "SELECT t.work_item_id, t.parent_id, t.state, t.closed_at, t.board_id, w.name AS summary"
        "  FROM ticket t JOIN work_item w ON w.work_item_id = t.work_item_id WHERE t.work_item_id = ?",
        (work_item_id,)).fetchone()
    if row is None:
        raise LookupError(f"no ticket {work_item_id!r}")
    return row


def children_of(conn: sqlite3.Connection, parent_id: str) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT t.work_item_id, t.board_id, t.state, t.priority, t.owner, t.requested_by,"
        "       t.closed_at, w.name AS summary, s.name AS status_name"
        "  FROM ticket t JOIN work_item w ON w.work_item_id = t.work_item_id"
        "  LEFT JOIN board_status s ON s.board_status_id = t.board_status_id"
        " WHERE t.parent_id = ? ORDER BY t.opened_at, t.work_item_id", (parent_id,)).fetchall()


def parent_of(conn: sqlite3.Connection, child_id: str):
    row = conn.execute("SELECT parent_id FROM ticket WHERE work_item_id = ?", (child_id,)).fetchone()
    if row is None or not row["parent_id"]:
        return None
    return _ticket(conn, row["parent_id"])


def attach(conn: sqlite3.Connection, parent_id: str, child_id: str, *, actor: str,
           at: datetime) -> bool:
    """Make child_id a child of parent_id. Returns False if it already was."""
    from .board import _event, touch
    if parent_id == child_id:
        raise Refused("a ticket is not its own parent")
    parent, child = _ticket(conn, parent_id), _ticket(conn, child_id)
    if child["parent_id"] == parent_id:
        return False
    if parent["parent_id"]:
        raise Refused(f"{parent_id} is itself a child of {parent['parent_id']}; children have "
                      "no children (one level)")
    if conn.execute("SELECT 1 FROM ticket WHERE parent_id = ? LIMIT 1", (child_id,)).fetchone():
        raise Refused(f"{child_id} has children of its own; a parent cannot become a child")
    for row in (parent, child):
        if row["state"] in CLOSED_STATES or row["closed_at"]:
            raise Refused(f"{row['work_item_id']} is closed; only open tickets are attached")
    stamp = _stamp(at)
    if child["parent_id"]:
        _event(conn, child["parent_id"], stamp, "CHILD", actor,
               f"{child_id} moved to be a child of {parent_id}")
    conn.execute("UPDATE ticket SET parent_id = ? WHERE work_item_id = ?", (parent_id, child_id))
    _event(conn, child_id, stamp, "CHILD", actor,
           f"made a child of {parent_id}: closes when it closes")
    _event(conn, parent_id, stamp, "CHILD", actor, f"{child_id} attached as a child")
    touch(conn, child_id, at)
    touch(conn, parent_id, at)
    return True


def detach(conn: sqlite3.Connection, child_id: str, *, actor: str, at: datetime) -> bool:
    """Give a child its own life back. Returns False if it had no parent."""
    from .board import _event, touch
    child = _ticket(conn, child_id)
    if not child["parent_id"]:
        return False
    stamp = _stamp(at)
    conn.execute("UPDATE ticket SET parent_id = NULL WHERE work_item_id = ?", (child_id,))
    _event(conn, child_id, stamp, "CHILD", actor, f"detached from parent {child['parent_id']}")
    _event(conn, child["parent_id"], stamp, "CHILD", actor, f"{child_id} detached")
    touch(conn, child_id, at)
    touch(conn, child["parent_id"], at)
    return True


def close_with_parent(conn: sqlite3.Connection, parent_id: str, *, at: datetime,
                      actor: str) -> dict:
    """The parent has just reached a closed status: close each open child on its
    own board's closed status. A child that cannot close stays open and its
    ticket says why; the parent's close stands either way."""
    from . import board
    from .board import _event
    closed, left = [], []
    stamp = _stamp(at)
    for child in children_of(conn, parent_id):
        if child["state"] in CLOSED_STATES or child["closed_at"]:
            continue
        target = conn.execute(
            "SELECT board_status_id FROM board_status WHERE board_id = ? AND is_closed = 1"
            " AND inactive = 0 ORDER BY sort_order LIMIT 1", (child["board_id"],)).fetchone()
        if target is None:
            left.append(child["work_item_id"])
            _event(conn, child["work_item_id"], stamp, "CHILD", actor,
                   f"parent {parent_id} closed, but this board has no closed status; left open")
            continue
        try:
            _event(conn, child["work_item_id"], stamp, "CHILD", actor,
                   f"closed with parent {parent_id}")
            board.change_status(conn, child["work_item_id"], target["board_status_id"],
                                at=at, actor=actor)
            closed.append(child["work_item_id"])
        except (ValueError, LookupError) as exc:                  # a change awaiting approval, etc.
            left.append(child["work_item_id"])
            _event(conn, child["work_item_id"], stamp, "CHILD", actor,
                   f"parent {parent_id} closed, but this ticket could not: {exc}")
    if closed or left:
        _event(conn, parent_id, stamp, "CHILD", actor,
               f"closed with {len(closed)} child(ren)"
               + (f"; {len(left)} left open: {', '.join(left)}" if left else ""))
    return {"closed": closed, "left_open": left}


# ------------------------------------------------------------------- merge

def merge(conn: sqlite3.Connection, dup_id: str, into_id: str, *, actor: str,
          at: datetime) -> dict:
    """Dada PSA's Merge: the duplicate's notes are copied onto the ticket
    that stays, its files and links move, its children move, and it closes on
    its own board with merged_into set so its number still answers.

    A Discussion note is copied as Discussion only when both tickets have the
    same requester; otherwise it is copied as Internal, because one requester's
    words are not another requester's to read on their portal (§6.1).
    """
    from . import board
    from .board import _event, touch
    if dup_id == into_id:
        raise Refused("a ticket is not merged into itself")
    dup, into = _ticket(conn, dup_id), _ticket(conn, into_id)
    for row in (dup, into):
        if row["state"] in CLOSED_STATES or row["closed_at"]:
            raise Refused(f"{row['work_item_id']} is closed; only open tickets merge")
    if conn.execute("SELECT merged_into FROM ticket WHERE work_item_id = ?", (into_id,)).fetchone()[0]:
        raise Refused(f"{into_id} was itself merged away")
    if into["parent_id"] and conn.execute("SELECT 1 FROM ticket WHERE parent_id = ?", (dup_id,)).fetchone():
        raise Refused(f"{dup_id} has children and {into_id} is a child; children have no children")
    target = conn.execute(
        "SELECT board_status_id FROM board_status WHERE board_id = ? AND is_closed = 1"
        " AND inactive = 0 ORDER BY sort_order LIMIT 1", (dup["board_id"],)).fetchone()
    if target is None:
        raise Refused(f"{dup_id}'s board has no closed status to merge into")
    stamp = _stamp(at)
    same_requester = (conn.execute("SELECT LOWER(COALESCE(requested_by, '')) FROM ticket WHERE work_item_id = ?",
                                   (dup_id,)).fetchone()[0]
                      == conn.execute("SELECT LOWER(COALESCE(requested_by, '')) FROM ticket WHERE work_item_id = ?",
                                      (into_id,)).fetchone()[0])
    notes = conn.execute(
        "SELECT occurred_at, actor, detail, note_flag, is_resolution FROM ticket_event"
        " WHERE work_item_id = ? AND note_flag IS NOT NULL ORDER BY ticket_event_id", (dup_id,)).fetchall()
    for n in notes:
        flag = n["note_flag"] if (n["note_flag"] == "INTERNAL" or same_requester) else "INTERNAL"
        conn.execute("INSERT INTO ticket_event (work_item_id, occurred_at, kind, actor, detail, note_flag)"
                     " VALUES (?,?,'MERGED_NOTE',?,?,?)",
                     (into_id, n["occurred_at"], n["actor"], f"(from {dup_id}) {n['detail']}", flag))
    files = conn.execute("UPDATE attachment SET work_item_id = ? WHERE work_item_id = ?", (into_id, dup_id)).rowcount
    for l in conn.execute("SELECT * FROM ticket_link WHERE work_item_id = ? OR linked_id = ?", (dup_id, dup_id)).fetchall():
        a = into_id if l["work_item_id"] == dup_id else l["work_item_id"]
        b = into_id if l["linked_id"] == dup_id else l["linked_id"]
        if a != b:
            conn.execute("INSERT OR IGNORE INTO ticket_link (work_item_id, linked_id, relation, linked_at,"
                         " linked_by) VALUES (?,?,?,?,?)", (a, b, l["relation"], l["linked_at"], l["linked_by"]))
    conn.execute("DELETE FROM ticket_link WHERE work_item_id = ? OR linked_id = ?", (dup_id, dup_id))
    kids = conn.execute("UPDATE ticket SET parent_id = ? WHERE parent_id = ?", (into_id, dup_id)).rowcount
    if dup["parent_id"]:
        conn.execute("UPDATE ticket SET parent_id = NULL WHERE work_item_id = ?", (dup_id,))
    conn.execute("UPDATE ticket SET merged_into = ? WHERE work_item_id = ?", (into_id, dup_id))
    _event(conn, dup_id, stamp, "MERGED", actor, f"merged into {into_id}: {len(notes)} note(s) copied,"
           f" {files} file(s) moved" + (f", {kids} child(ren) moved" if kids else ""))
    _event(conn, into_id, stamp, "MERGED", actor, f"{dup_id} merged in: {len(notes)} note(s) copied,"
           f" {files} file(s) moved" + ("" if same_requester else "; its Discussion notes arrived as Internal"))
    board.change_status(conn, dup_id, target["board_status_id"], at=at, actor=actor)
    touch(conn, into_id, at)
    return {"notes": len(notes), "files": files, "children": kids, "same_requester": same_requester}

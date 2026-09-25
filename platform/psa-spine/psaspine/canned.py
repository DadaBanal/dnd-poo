"""Standard notes (031): a board's canned replies, and a person's saved views.

A standard note is written once by a board administrator and dropped into the
note box by a technician; it carries a flag (Discussion or Internal) so the
"we have received your request" text cannot land as an internal note by
accident. A saved view is one person's own filter on the board, named.
"""
from __future__ import annotations

import sqlite3
import urllib.parse
from datetime import datetime

from . import db

FLAGS = ("DISCUSSION", "INTERNAL")
# The board's own query keys; anything else in a saved view is dropped.
VIEW_KEYS = ("board", "view", "owner", "pri", "src", "type", "q", "tile", "sort", "dir")


def _stamp(at: datetime) -> str:
    return at.isoformat(sep=" ", timespec="minutes")


# ------------------------------------------------------------- standard notes

def notes_for(conn: sqlite3.Connection, board_id: str, *, include_inactive: bool = False):
    return conn.execute(
        "SELECT * FROM standard_note WHERE board_id = ?" + ("" if include_inactive else " AND inactive = 0")
        + " ORDER BY name", (board_id,)).fetchall()


def add_note(conn: sqlite3.Connection, *, board_id: str, name: str, body: str, flag: str,
             actor: str, at: datetime) -> int:
    name, body = (name or "").strip(), (body or "").strip()
    if not name or not body:
        raise ValueError("a standard note needs a name and some words")
    if flag not in FLAGS:
        raise ValueError("a standard note is Discussion or Internal")
    cur = conn.execute(
        "INSERT INTO standard_note (board_id, name, body, flag, created_at, created_by)"
        " VALUES (?,?,?,?,?,?)", (board_id, name[:120], body[:4000], flag, _stamp(at), actor))
    db.audit(conn, at=_stamp(at), actor=actor, action="STANDARD_NOTE", subject_kind="board",
             subject_id=board_id, detail=f"standard note added: {name[:80]}")
    return cur.lastrowid


def set_note_inactive(conn: sqlite3.Connection, note_id: int, inactive: bool, *, actor: str,
                      at: datetime) -> bool:
    cur = conn.execute("UPDATE standard_note SET inactive = ? WHERE note_id = ?",
                       (1 if inactive else 0, note_id))
    if cur.rowcount:
        row = conn.execute("SELECT board_id, name FROM standard_note WHERE note_id = ?",
                           (note_id,)).fetchone()
        db.audit(conn, at=_stamp(at), actor=actor, action="STANDARD_NOTE", subject_kind="board",
                 subject_id=row["board_id"],
                 detail=f"standard note {'retired' if inactive else 'restored'}: {row['name']}")
    return bool(cur.rowcount)


# ---------------------------------------------------------------- saved views

def clean_query(query: str) -> str:
    """Only the board's own keys, in a fixed order, so two saves of the same
    filter compare equal and nothing foreign rides along."""
    pairs = dict(urllib.parse.parse_qsl(query.lstrip("?")))
    kept = [(k, pairs[k]) for k in VIEW_KEYS if pairs.get(k)]
    return urllib.parse.urlencode(kept)


def views_for(conn: sqlite3.Connection, member: str):
    return conn.execute("SELECT * FROM user_view WHERE member = ? ORDER BY sort_order, name",
                        (member,)).fetchall()


def save_view(conn: sqlite3.Connection, *, member: str, name: str, query: str, at: datetime) -> int:
    name = (name or "").strip()[:60]
    if not name:
        raise ValueError("a view needs a name")
    query = clean_query(query)
    existing = conn.execute("SELECT view_id FROM user_view WHERE member = ? AND name = ?",
                            (member, name)).fetchone()
    if existing:
        conn.execute("UPDATE user_view SET query = ? WHERE view_id = ?", (query, existing["view_id"]))
        return existing["view_id"]
    order = conn.execute("SELECT COALESCE(MAX(sort_order), 0) + 10 FROM user_view WHERE member = ?",
                         (member,)).fetchone()[0]
    cur = conn.execute("INSERT INTO user_view (member, name, query, sort_order, created_at)"
                       " VALUES (?,?,?,?,?)", (member, name, query, order, _stamp(at)))
    return cur.lastrowid


def delete_view(conn: sqlite3.Connection, *, member: str, view_id: int) -> bool:
    cur = conn.execute("DELETE FROM user_view WHERE member = ? AND view_id = ?", (member, view_id))
    return bool(cur.rowcount)

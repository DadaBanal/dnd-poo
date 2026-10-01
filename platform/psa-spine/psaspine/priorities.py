"""The Priority setup table (060): what P1 to P4 are called and coloured.

The codes are fixed: every SLA target, catalogue floor and clinical floor
names them, and the matrix computes them. The words and colours are the
hospital's, editable at Setup > Priorities, in the reference PSA's shape
(name, colour, sort order, default). The default is what a ticket gets when
nothing decides its priority, which on this desk never happens (the matrix
always does); it is kept so the table reads as ConnectWise's does.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime

CODES = ("P1", "P2", "P3", "P4")
COLORS = ("Red", "Orange", "Yellow", "Green", "Blue", "Cyan", "Lime", "Purple", "Pink", "Gray", "Black", "White")
# What a named colour paints: readable on white text.
PAINT = {"Red": "#c62828", "Orange": "#b26a00", "Yellow": "#8a7a00", "Green": "#1a7f37", "Blue": "#3d63dd",
         "Cyan": "#0e7490", "Lime": "#4d7c0f", "Purple": "#6d28d9", "Pink": "#be185d", "Gray": "#6b7785",
         "Black": "#15181e", "White": "#9aa3b2"}
DEFAULTS = (
    ("P1", "Priority 1 - Emergency Response", "Red", 1, 0),
    ("P2", "Priority 2 - Quick Response", "Orange", 2, 0),
    ("P3", "Priority 3 - Normal Response", "Yellow", 3, 0),
    ("P4", "Priority 4 - Low Response", "Green", 4, 1),
)


def seed(conn: sqlite3.Connection) -> None:
    """The four rows, once. A row already there is never touched."""
    for code, name, color, order, default in DEFAULTS:
        conn.execute("INSERT OR IGNORE INTO priority (priority_id, name, color, sort_order, is_default)"
                     " VALUES (?,?,?,?,?)", (code, name, color, order, default))


def rows(conn: sqlite3.Connection) -> list[dict]:
    """The table's rows. A desk whose store has not had 060 applied yet reads
    the defaults, so every page still opens; Setup > Priorities says so."""
    from . import db
    if not db.table_exists(conn, "priority"):
        return [dict(priority_id=c, name=n, color=k, sort_order=o, is_default=d) for c, n, k, o, d in DEFAULTS]
    out = [dict(r) for r in conn.execute("SELECT * FROM priority ORDER BY sort_order, priority_id")]
    if not out:
        seed(conn)
        out = [dict(r) for r in conn.execute("SELECT * FROM priority ORDER BY sort_order, priority_id")]
    return out


def table(conn: sqlite3.Connection) -> dict[str, dict]:
    return {r["priority_id"]: r for r in rows(conn)}


def name_of(conn: sqlite3.Connection, code: str) -> str:
    r = table(conn).get(code)
    return r["name"] if r else (code or "")


def save(conn: sqlite3.Connection, code: str, *, name: str | None = None, color: str | None = None,
         sort_order: int | None = None, is_default: bool | None = None, at: datetime, actor: str) -> str:
    from . import db
    if code not in CODES:
        raise ValueError("a priority is P1, P2, P3 or P4")
    if not db.table_exists(conn, "priority"):
        raise ValueError("schema step 060 has not been applied on this store yet; the defaults are in use")
    cur = table(conn)[code]
    changed = []
    if name is not None:
        n = " ".join(str(name).split())[:50]
        if not n:
            raise ValueError("a priority needs a name")
        if n != cur["name"]:
            conn.execute("UPDATE priority SET name = ? WHERE priority_id = ?", (n, code))
            changed.append(f"name {cur['name']} -> {n}")
    if color is not None and color != cur["color"]:
        if color not in COLORS:
            raise ValueError("a colour is one of " + ", ".join(COLORS))
        conn.execute("UPDATE priority SET color = ? WHERE priority_id = ?", (color, code))
        changed.append(f"colour {cur['color']} -> {color}")
    if sort_order is not None and sort_order != cur["sort_order"]:
        conn.execute("UPDATE priority SET sort_order = ? WHERE priority_id = ?", (int(sort_order), code))
        changed.append(f"order {cur['sort_order']} -> {int(sort_order)}")
    if is_default:
        conn.execute("UPDATE priority SET is_default = CASE WHEN priority_id = ? THEN 1 ELSE 0 END", (code,))
        if not cur["is_default"]:
            changed.append("now the default")
    if not changed:
        return "nothing changed"
    db.audit(conn, at=at.isoformat(sep=" ", timespec="minutes"), actor=actor, action="PRIORITY_SETUP",
             subject_kind="priority", subject_id=code, detail="; ".join(changed))
    return "; ".join(changed)

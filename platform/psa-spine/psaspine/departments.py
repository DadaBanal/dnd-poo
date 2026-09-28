"""Departments, and which boards each may send requests to (034).

The desk holds no department list of its own and its SQL login must not read
payroll, so the list arrives as a CSV of one column, `Department` (SQL01
produces it from payroll, read-only, no people), or a name is added by hand in
Setup. A re-run adds new names and never deletes one: a name that has gone is
retired and keeps its ticks.

`boards_for` is the one question everything else asks: which live service
boards may this department's staff raise a request onto? Empty means the
Employee Portal door refuses them and the portal's form lands on Unrouted.
"""
from __future__ import annotations

import csv
import sqlite3
from datetime import datetime
from pathlib import Path

from . import db


def _stamp(at: datetime) -> str:
    return at.isoformat(sep=" ", timespec="minutes")


def import_csv(conn: sqlite3.Connection, path: str | Path, *, at: datetime,
               actor: str = "cli") -> dict:
    """Upsert the department names in a one-column CSV. Names not in the file
    that came from payroll before are retired, never deleted; a manual name is
    left alone."""
    text = Path(path).read_bytes().decode("utf-8-sig")
    reader = csv.DictReader(text.splitlines())
    if "Department" not in (reader.fieldnames or []):
        raise ValueError("not a department export: no column 'Department'")
    names = []
    for row in reader:
        name = (row.get("Department") or "").strip()
        if name and name not in names:
            names.append(name)
    stamp = _stamp(at)
    counts = {"rows": len(names), "new": 0, "seen": 0, "retired": 0, "restored": 0}
    for name in names:
        row = conn.execute("SELECT retired FROM department WHERE name = ?", (name,)).fetchone()
        if row is None:
            conn.execute("INSERT INTO department (name, source, retired, created_at, last_seen_at)"
                         " VALUES (?, 'PAYROLL', 0, ?, ?)", (name, stamp, stamp))
            counts["new"] += 1
        else:
            if row["retired"]:
                counts["restored"] += 1
            else:
                counts["seen"] += 1
            conn.execute("UPDATE department SET retired = 0, last_seen_at = ? WHERE name = ?", (stamp, name))
    gone = [r["name"] for r in conn.execute(
        "SELECT name FROM department WHERE source = 'PAYROLL' AND retired = 0").fetchall()
        if r["name"] not in names]
    for name in gone:
        conn.execute("UPDATE department SET retired = 1 WHERE name = ?", (name,))
        counts["retired"] += 1
    db.audit(conn, at=stamp, actor=actor, action="DEPARTMENT_IMPORT", subject_kind="department",
             subject_id=None, detail=(f"{counts['rows']} names: {counts['new']} new, {counts['seen']} seen, "
                                      f"{counts['restored']} restored, {counts['retired']} retired"))
    return counts


def add(conn: sqlite3.Connection, name: str, *, at: datetime, actor: str) -> str:
    """A department payroll does not have yet, by hand. Exact name."""
    name = (name or "").strip()
    if not name:
        raise ValueError("a department needs a name")
    if len(name) > 100:
        raise ValueError("a department name is at most 100 characters")
    if conn.execute("SELECT 1 FROM department WHERE name = ?", (name,)).fetchone():
        raise ValueError(f"there is already a department {name!r}")
    conn.execute("INSERT INTO department (name, source, retired, created_at) VALUES (?, 'MANUAL', 0, ?)",
                 (name, _stamp(at)))
    db.audit(conn, at=_stamp(at), actor=actor, action="DEPARTMENT_ADD", subject_kind="department",
             subject_id=name, detail="added by hand")
    return name


def all_departments(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM department ORDER BY retired, name").fetchall()


def live_boards(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """The columns of the grid: live service boards, not Unrouted."""
    return conn.execute(
        "SELECT board_id, display_name FROM board WHERE is_live = 1 AND is_unrouted = 0"
        " AND COALESCE(inactive, 0) = 0 ORDER BY display_name").fetchall()


def ticks(conn: sqlite3.Connection) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for r in conn.execute("SELECT department, board_id FROM department_board"):
        out.setdefault(r["department"], set()).add(r["board_id"])
    return out


def any_configured(conn: sqlite3.Connection) -> bool:
    """Whether the checklist decides yet. Until one tick exists, the door may
    still honour PSA_EMPLOYEE_PORTAL_DEPARTMENTS as a migration."""
    return conn.execute("SELECT 1 FROM department_board LIMIT 1").fetchone() is not None


def boards_for(conn: sqlite3.Connection, department: str | None) -> list[sqlite3.Row]:
    """The live boards this department may raise onto, by name. Exact match."""
    if not department:
        return []
    return conn.execute(
        "SELECT b.board_id, b.display_name FROM department_board d JOIN board b ON b.board_id = d.board_id"
        " WHERE d.department = ? AND b.is_live = 1 AND b.is_unrouted = 0 AND COALESCE(b.inactive, 0) = 0"
        " ORDER BY b.display_name", (department,)).fetchall()


def save_grid(conn: sqlite3.Connection, wanted: dict[str, set[str]], *, at: datetime,
              actor: str) -> list[str]:
    """One Save for the whole grid. Only live boards and known departments are
    written; the audit is one line per department that changed, as
    'Ward A: + IT Help, − Maintenance'. Returns those lines."""
    boards = {b["board_id"]: b["display_name"] for b in live_boards(conn)}
    known = {r["name"] for r in all_departments(conn)}
    have = ticks(conn)
    stamp = _stamp(at)
    lines = []
    for dept in sorted(known):
        want = {b for b in wanted.get(dept, set()) if b in boards}
        got = have.get(dept, set()) & set(boards)
        plus, minus = sorted(want - got), sorted(got - want)
        if not plus and not minus:
            continue
        for b in plus:
            conn.execute("INSERT INTO department_board (department, board_id, ticked_at, ticked_by)"
                         " VALUES (?,?,?,?)", (dept, b, stamp, actor))
        for b in minus:
            conn.execute("DELETE FROM department_board WHERE department = ? AND board_id = ?", (dept, b))
        words = ", ".join([f"+ {boards[b]}" for b in plus] + [f"− {boards[b]}" for b in minus])
        lines.append(f"{dept}: {words}")
    if lines:
        db.audit(conn, at=stamp, actor=actor, action="DEPARTMENT_BOARDS", subject_kind="department",
                 subject_id=None, detail="; ".join(lines))
    return lines

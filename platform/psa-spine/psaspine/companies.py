"""Company status and type (057): words on a company, kept in Setup.

The reference PSA has CompanyStatus (a customer, a former customer, a
prospect) and CompanyType (a hospital department, a supplier, a partner).
A hospital has one company and a handful of suppliers, so these are two
short lists a system administrator keeps, and a chip on the company's page.
Nothing reads them to decide anything: a company's coverage is still the
executed instrument (entity.is_covered), and its tickets are still its own.
"""
from __future__ import annotations

import re
import sqlite3
from datetime import datetime

from . import db


class Refused(ValueError):
    """A sentence for the person; nothing was written."""


def _slug(name: str, prefix: str) -> str:
    base = re.sub(r"[^A-Z0-9]+", "_", (name or "").upper()).strip("_")[:40]
    return f"{prefix}_{base}" if base else prefix


def _name(value, what) -> str:
    n = " ".join(str(value or "").split())[:80]
    if not n:
        raise Refused(f"A {what} needs a name.")
    return n


_TABLES = {"status": ("company_status", "status_id", "CS"), "type": ("company_type", "type_id", "CT")}


def rows(conn: sqlite3.Connection, what: str, *, all_rows: bool = False) -> list[dict]:
    table, key, _ = _TABLES[what]
    return [dict(r) for r in conn.execute(
        f"SELECT t.*, (SELECT COUNT(*) FROM entity e WHERE e.{key} = t.{key}) AS used FROM {table} t"
        + ("" if all_rows else " WHERE t.inactive = 0") + " ORDER BY t.sort_order, t.name")]


def add(conn: sqlite3.Connection, what: str, name: str, *, at: datetime, actor: str) -> str:
    table, key, prefix = _TABLES[what]
    n = _name(name, what)
    if conn.execute(f"SELECT 1 FROM {table} WHERE LOWER(name) = LOWER(?)", (n,)).fetchone():
        raise Refused(f"A {what} with that name exists.")
    ident = _slug(n, prefix)
    if conn.execute(f"SELECT 1 FROM {table} WHERE {key} = ?", (ident,)).fetchone():
        raise Refused("That name is too close to one that exists.")
    order = conn.execute(f"SELECT COALESCE(MAX(sort_order), 0) + 10 FROM {table}").fetchone()[0]
    conn.execute(f"INSERT INTO {table} ({key}, name, inactive, sort_order) VALUES (?,?,0,?)", (ident, n, order))
    db.audit(conn, at=at.isoformat(sep=" ", timespec="minutes"), actor=actor, action="COMPANY_SETUP",
             subject_kind=table, subject_id=ident, detail=f"added {n}")
    return ident


def save(conn: sqlite3.Connection, what: str, ident: str, *, at: datetime, actor: str, name=None, inactive=None) -> str:
    table, key, _ = _TABLES[what]
    row = conn.execute(f"SELECT * FROM {table} WHERE {key} = ?", (ident,)).fetchone()
    if row is None:
        raise Refused(f"No such {what}.")
    changes = []
    if name is not None and _name(name, what) != row["name"]:
        changes.append(("name", _name(name, what)))
    if inactive is not None and int(bool(inactive)) != row["inactive"]:
        changes.append(("inactive", int(bool(inactive))))
    for col, val in changes:
        conn.execute(f"UPDATE {table} SET {col} = ? WHERE {key} = ?", (val, ident))
    if changes:
        db.audit(conn, at=at.isoformat(sep=" ", timespec="minutes"), actor=actor, action="COMPANY_SETUP",
                 subject_kind=table, subject_id=ident, detail="; ".join(f"{c} -> {v}" for c, v in changes))
    return "saved" if changes else "nothing changed"


def set_company(conn: sqlite3.Connection, entity_id: str, *, at: datetime, actor: str, status_id=None, type_id=None) -> list[str]:
    """Give a company its status and type (either may be blank)."""
    row = conn.execute("SELECT entity_id, name, status_id, type_id FROM entity WHERE entity_id = ?", (entity_id,)).fetchone()
    if row is None:
        raise Refused("No such company.")
    wanted = {}
    for what, value in (("status", status_id), ("type", type_id)):        # check everything before writing anything
        table, key, _ = _TABLES[what]
        v = (value or "").strip() or None
        if v and conn.execute(f"SELECT 1 FROM {table} WHERE {key} = ? AND inactive = 0", (v,)).fetchone() is None:
            raise Refused(f"No such {what}.")
        wanted[what] = (key, v)
    changed = []
    for what, (key, v) in wanted.items():
        if v != row[key]:
            conn.execute(f"UPDATE entity SET {key} = ? WHERE entity_id = ?", (v, entity_id))
            changed.append(f"{what} {row[key] or '-'} -> {v or '-'}")
    if changed:
        db.audit(conn, at=at.isoformat(sep=" ", timespec="minutes"), actor=actor, action="COMPANY_SETUP",
                 subject_kind="entity", subject_id=entity_id, detail="; ".join(changed))
    return changed


def words(conn: sqlite3.Connection, entity_row) -> tuple[str | None, str | None]:
    """(status name, type name) for a company row, either None."""
    s = tp = None
    if entity_row["status_id"]:
        r = conn.execute("SELECT name FROM company_status WHERE status_id = ?", (entity_row["status_id"],)).fetchone()
        s = r["name"] if r else None
    if entity_row["type_id"]:
        r = conn.execute("SELECT name FROM company_type WHERE type_id = ?", (entity_row["type_id"],)).fetchone()
        tp = r["name"] if r else None
    return s, tp

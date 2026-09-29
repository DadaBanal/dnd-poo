"""Setup › Catalogue: the Areas, Subtypes and Items a ticket is classified by.

The reference PSA's Service Board setup table has a Types tab, a Subtypes tab
and an Items tab, each a list a person adds to, renames and inactivates, and
Subtype › Item pairs are associated so a ticket offers only pairs somebody has
approved. Dada PSA keeps the same three actions on its own tree (schema/004):

- **Type** stays the board's ITIL kind (Incident, Request, Problem, Event,
  Change, Project; the board's Types tab). The six are a closed set because
  the change gate and the SLA-by-type targets key on them.
- **Area** (`service_family`) groups subtypes for the picker: Networking,
  Servers and storage, Clinical applications.
- **Subtype** (`service_component`): the thing — Printer, Hyper-V host.
- **Item** (`service_action`): the verb — Install, Outage, Failure — with the
  kind a fresh ticket takes from it (REQUEST or FAULT) and the impact it implies.
- **An association** is a `catalogue_item`: Subtype × Item, with the board it
  lands on, its contract basis and any priority floor. Only associated pairs
  are offered on a ticket.

Every write here is audited as CATALOGUE_CONFIG with what changed, and nothing
is ever deleted: retiring hides from the pickers and leaves history whole.
"""
from __future__ import annotations

import re
import sqlite3
from datetime import datetime

from . import db

KINDS = ("REQUEST", "FAULT")
IMPACTS = ("I1", "I2", "I3")
BASES = ("BASELINE", "VARIATION", "UNKNOWN")
PRIORITIES = ("P1", "P2", "P3", "P4")
MAX_NAME = 80


class Refused(ValueError):
    """A sentence for the person; nothing was written."""


def slug(name: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "_", name.upper()).strip("_")


def _name(value: str | None) -> str:
    name = " ".join((value or "").split())
    if not name:
        raise Refused("A name is required.")
    if len(name) > MAX_NAME:
        raise Refused(f"A name is at most {MAX_NAME} characters.")
    return name


def _audit(conn, *, at: datetime, actor: str, kind: str, subject: str, detail: str) -> None:
    db.audit(conn, at=at.isoformat(sep=" ", timespec="minutes"), actor=actor,
             action="CATALOGUE_CONFIG", subject_kind=kind, subject_id=subject, detail=detail)


def _taken(conn, table: str, name: str, *, exclude: str | None = None, key: str) -> bool:
    row = conn.execute(f"SELECT {key} FROM {table} WHERE LOWER(display_name) = LOWER(?)",
                       (name,)).fetchone()
    return row is not None and row[0] != exclude


def _fresh_id(conn, table: str, key: str, base: str) -> str:
    cand, n = base or "X", 2
    while conn.execute(f"SELECT 1 FROM {table} WHERE {key} = ?", (cand,)).fetchone():
        cand, n = f"{base}_{n}", n + 1
    return cand


# ------------------------------------------------------------------ reading

def areas(conn: sqlite3.Connection) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT f.family_id, f.display_name, f.note, COALESCE(f.inactive, 0) AS inactive,"
        "       (SELECT COUNT(*) FROM service_component c WHERE c.family_id = f.family_id) AS subtypes"
        "  FROM service_family f ORDER BY COALESCE(f.inactive, 0), f.display_name")]


def subtypes(conn: sqlite3.Connection) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT c.component_id, c.family_id, c.display_name, c.note, c.is_draft AS inactive,"
        "       f.display_name AS area,"
        "       (SELECT COUNT(*) FROM catalogue_item i WHERE i.component_id = c.component_id) AS pairs"
        "  FROM service_component c JOIN service_family f ON f.family_id = c.family_id"
        " ORDER BY c.is_draft, f.display_name, c.display_name")]


def items(conn: sqlite3.Connection) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT a.action_id, a.display_name, a.kind, a.implies_impact, a.note,"
        "       COALESCE(a.inactive, 0) AS inactive,"
        "       (SELECT COUNT(*) FROM catalogue_item i WHERE i.action_id = a.action_id) AS pairs"
        "  FROM service_action a ORDER BY COALESCE(a.inactive, 0), a.kind, a.display_name")]


# -------------------------------------------------------------------- areas

def add_area(conn, name: str, *, note: str | None = None, at: datetime, actor: str) -> str:
    name = _name(name)
    if _taken(conn, "service_family", name, key="family_id"):
        raise Refused(f"There is already an area called {name}.")
    fid = _fresh_id(conn, "service_family", "family_id", slug(name))
    conn.execute("INSERT INTO service_family (family_id, display_name, note, inactive) VALUES (?,?,?,0)",
                 (fid, name, (note or "").strip() or None))
    _audit(conn, at=at, actor=actor, kind="service_family", subject=fid, detail=f"area added: {name}")
    return fid


def save_area(conn, family_id: str, *, name: str | None = None, inactive: bool | None = None,
              at: datetime, actor: str) -> str:
    row = conn.execute("SELECT display_name, COALESCE(inactive, 0) AS inactive FROM service_family"
                       " WHERE family_id = ?", (family_id,)).fetchone()
    if row is None:
        raise Refused("No such area.")
    changed = []
    if name is not None:
        name = _name(name)
        if name != row["display_name"]:
            if _taken(conn, "service_family", name, exclude=family_id, key="family_id"):
                raise Refused(f"There is already an area called {name}.")
            conn.execute("UPDATE service_family SET display_name = ? WHERE family_id = ?", (name, family_id))
            changed.append(f"renamed {row['display_name']} -> {name}")
    if inactive is not None and int(inactive) != row["inactive"]:
        conn.execute("UPDATE service_family SET inactive = ? WHERE family_id = ?", (int(inactive), family_id))
        changed.append("retired" if inactive else "restored")
    if changed:
        _audit(conn, at=at, actor=actor, kind="service_family", subject=family_id, detail="; ".join(changed))
    return "; ".join(changed) or "nothing changed"


# ----------------------------------------------------------------- subtypes

def add_subtype(conn, family_id: str, name: str, *, note: str | None = None, at: datetime,
                actor: str) -> str:
    name = _name(name)
    fam = conn.execute("SELECT display_name FROM service_family WHERE family_id = ?", (family_id,)).fetchone()
    if fam is None:
        raise Refused("Choose the area the subtype belongs to.")
    if conn.execute("SELECT 1 FROM service_component WHERE family_id = ? AND LOWER(display_name) = LOWER(?)",
                    (family_id, name)).fetchone():
        raise Refused(f"{fam['display_name']} already has a subtype called {name}.")
    cid = _fresh_id(conn, "service_component", "component_id", slug(name))
    conn.execute("INSERT INTO service_component (component_id, family_id, display_name, is_draft, note)"
                 " VALUES (?,?,?,0,?)", (cid, family_id, name, (note or "").strip() or None))
    _audit(conn, at=at, actor=actor, kind="service_component", subject=cid,
           detail=f"subtype added: {fam['display_name']} › {name}")
    return cid


def save_subtype(conn, component_id: str, *, name: str | None = None, family_id: str | None = None,
                 inactive: bool | None = None, at: datetime, actor: str) -> str:
    row = conn.execute("SELECT display_name, family_id, is_draft FROM service_component WHERE component_id = ?",
                       (component_id,)).fetchone()
    if row is None:
        raise Refused("No such subtype.")
    changed = []
    target_family = row["family_id"]
    if family_id and family_id != row["family_id"]:
        fam = conn.execute("SELECT display_name FROM service_family WHERE family_id = ?", (family_id,)).fetchone()
        if fam is None:
            raise Refused("No such area.")
        conn.execute("UPDATE service_component SET family_id = ? WHERE component_id = ?", (family_id, component_id))
        changed.append(f"moved to {fam['display_name']}")
        target_family = family_id
    if name is not None:
        name = _name(name)
        if name != row["display_name"]:
            if conn.execute("SELECT 1 FROM service_component WHERE family_id = ? AND LOWER(display_name) = LOWER(?)"
                            " AND component_id <> ?", (target_family, name, component_id)).fetchone():
                raise Refused(f"That area already has a subtype called {name}.")
            conn.execute("UPDATE service_component SET display_name = ? WHERE component_id = ?", (name, component_id))
            changed.append(f"renamed {row['display_name']} -> {name}")
    if inactive is not None and int(inactive) != row["is_draft"]:
        conn.execute("UPDATE service_component SET is_draft = ? WHERE component_id = ?", (int(inactive), component_id))
        changed.append("retired" if inactive else "restored")
    if changed:
        _audit(conn, at=at, actor=actor, kind="service_component", subject=component_id, detail="; ".join(changed))
    return "; ".join(changed) or "nothing changed"


# -------------------------------------------------------------------- items

def add_item(conn, name: str, *, kind: str, implies_impact: str | None = None, note: str | None = None,
             at: datetime, actor: str) -> str:
    name = _name(name)
    if kind not in KINDS:
        raise Refused("An item is a request or a fault.")
    if implies_impact and implies_impact not in IMPACTS:
        raise Refused("The implied impact is I1, I2, I3 or none.")
    if _taken(conn, "service_action", name, key="action_id"):
        raise Refused(f"There is already an item called {name}.")
    aid = _fresh_id(conn, "service_action", "action_id", slug(name))
    conn.execute("INSERT INTO service_action (action_id, display_name, kind, implies_impact, note, inactive)"
                 " VALUES (?,?,?,?,?,0)", (aid, name, kind, implies_impact or None, (note or "").strip() or None))
    _audit(conn, at=at, actor=actor, kind="service_action", subject=aid,
           detail=f"item added: {name} ({kind}{', ' + implies_impact if implies_impact else ''})")
    return aid


def save_item(conn, action_id: str, *, name: str | None = None, kind: str | None = None,
              implies_impact: str | None = None, inactive: bool | None = None,
              at: datetime, actor: str) -> str:
    row = conn.execute("SELECT display_name, kind, implies_impact, COALESCE(inactive, 0) AS inactive"
                       " FROM service_action WHERE action_id = ?", (action_id,)).fetchone()
    if row is None:
        raise Refused("No such item.")
    changed = []
    if name is not None:
        name = _name(name)
        if name != row["display_name"]:
            if _taken(conn, "service_action", name, exclude=action_id, key="action_id"):
                raise Refused(f"There is already an item called {name}.")
            conn.execute("UPDATE service_action SET display_name = ? WHERE action_id = ?", (name, action_id))
            changed.append(f"renamed {row['display_name']} -> {name}")
    if kind is not None and kind != row["kind"]:
        if kind not in KINDS:
            raise Refused("An item is a request or a fault.")
        conn.execute("UPDATE service_action SET kind = ? WHERE action_id = ?", (kind, action_id))
        changed.append(f"kind {row['kind']} -> {kind}")
    if implies_impact is not None and (implies_impact or None) != row["implies_impact"]:
        if implies_impact and implies_impact not in IMPACTS:
            raise Refused("The implied impact is I1, I2, I3 or none.")
        conn.execute("UPDATE service_action SET implies_impact = ? WHERE action_id = ?",
                     (implies_impact or None, action_id))
        changed.append(f"impact {row['implies_impact'] or '-'} -> {implies_impact or '-'}")
    if inactive is not None and int(inactive) != row["inactive"]:
        conn.execute("UPDATE service_action SET inactive = ? WHERE action_id = ?", (int(inactive), action_id))
        changed.append("retired" if inactive else "restored")
    if changed:
        _audit(conn, at=at, actor=actor, kind="service_action", subject=action_id, detail="; ".join(changed))
    return "; ".join(changed) or "nothing changed"


# ------------------------------------------------------------- associations

def associate(conn, component_id: str, action_id: str, default_board_id: str, *,
              basis: str = "UNKNOWN", scope_item_id: str | None = None, min_priority: str | None = None,
              clinical_impact: bool = False, restricted: bool = False, note: str | None = None,
              needs_approval: bool = False, at: datetime, actor: str) -> str:
    """A new Subtype › Item pair, offered on tickets from now on."""
    c = conn.execute("SELECT c.display_name, f.display_name AS area FROM service_component c"
                     " JOIN service_family f ON f.family_id = c.family_id WHERE c.component_id = ?",
                     (component_id,)).fetchone()
    a = conn.execute("SELECT display_name FROM service_action WHERE action_id = ?", (action_id,)).fetchone()
    b = conn.execute("SELECT display_name FROM board WHERE board_id = ? AND COALESCE(inactive, 0) = 0",
                     (default_board_id,)).fetchone()
    if c is None or a is None:
        raise Refused("Choose a subtype and an item.")
    if b is None:
        raise Refused("Choose the board the pair lands on.")
    if basis not in BASES:
        raise Refused("The contract basis is baseline, variation or unknown.")
    if basis == "BASELINE" and not scope_item_id:
        raise Refused("A baseline pair must name the baseline scope item it sits in.")
    if min_priority and min_priority not in PRIORITIES:
        raise Refused("The priority floor is P1 to P4 or none.")
    if conn.execute("SELECT 1 FROM catalogue_item WHERE component_id = ? AND action_id = ?",
                    (component_id, action_id)).fetchone():
        raise Refused(f"{c['display_name']} › {a['display_name']} is already a pair.")
    cid = _fresh_id(conn, "catalogue_item", "catalogue_item_id", f"CI_{component_id}_{action_id}")
    conn.execute(
        "INSERT INTO catalogue_item (catalogue_item_id, component_id, action_id, default_board_id,"
        " default_scope_item_id, default_contract_basis, clinical_impact, min_priority, restricted, is_draft, note,"
        " needs_approval) VALUES (?,?,?,?,?,?,?,?,?,0,?,?)",
        (cid, component_id, action_id, default_board_id, scope_item_id or None, basis,
         int(bool(clinical_impact)), min_priority or None, int(bool(restricted)), (note or "").strip() or None,
         int(bool(needs_approval))))
    _audit(conn, at=at, actor=actor, kind="catalogue_item", subject=cid,
           detail=f"pair added: {c['area']} › {c['display_name']} › {a['display_name']} -> {b['display_name']}, {basis}")
    return cid


def set_needs_approval(conn, catalogue_item_id: str, flag: bool, *, at: datetime, actor: str) -> bool:
    """049: whether a ticket classified with this pair asks the requester's
    department's approver before the work is done. Returns whether it changed."""
    row = conn.execute("SELECT needs_approval FROM catalogue_item WHERE catalogue_item_id = ?",
                       (catalogue_item_id,)).fetchone()
    if row is None:
        raise Refused("No such pair.")
    if bool(row[0]) == bool(flag):
        return False
    conn.execute("UPDATE catalogue_item SET needs_approval = ? WHERE catalogue_item_id = ?",
                 (1 if flag else 0, catalogue_item_id))
    _audit(conn, at=at, actor=actor, kind="catalogue_item", subject=catalogue_item_id,
           detail="needs approval" if flag else "no approval needed")
    return True

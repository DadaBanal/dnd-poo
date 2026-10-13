"""Security roles (040): what a member may do in the modules that are not boards.

The reference PSA's Security Roles setup table, kept to the modules Dada PSA
has outside the boards. A role grants each module a level:

    NONE   the module is not shown
    READ   look (its "inquire")
    WRITE  add and edit (its "add" and "edit")
    ADMIN  everything, including delete and the module's own setup

A member has one role; with none, the default role. A system administrator
holds every module at ADMIN. A role never widens a board: tickets are still
governed by board membership, and a restricted board stays members-only.
"""
from __future__ import annotations

import re
import sqlite3
from datetime import datetime

from . import db

MODULES = {"KNOWLEDGE": "Knowledge base", "PROJECTS": "Projects", "REPORTS": "Reports",
           "SCHEDULE": "Schedule", "FINANCE": "Finance (BizBox)", "TIME": "Timesheets",
           "PROC_PO": "Procurement: purchase orders", "PROC_RR": "Procurement: receiving",
           "PROC_ITEM": "Procurement: items", "PROC_DRUG": "Procurement: drugs and medicines"}
# Procurement, 13 Oct 2026. Dada: "rbac for the procurement module needs to be
# made as it will bypass the bizbox permissions". One BizBox login will push
# every approved change, so the desk keeps what BizBox's per-user rights did,
# per area, as BizBox grants Purchasing, Warehouse and Inventory apart. The
# levels read differently in these three: READ is see, WRITE is propose (edits
# and adds), ADMIN is approve, and never one's own. There is no fallback to
# Finance: a role sees an area only once Setup says so (a live desk's roles
# start at NONE; the starter roles below are only written into an empty table).
# 13 Oct 2026, later: a fourth area, drugs and medicines, apart from the rest
# of Items so pharmacy can be given See or Propose on its own (Dada).
PROCUREMENT_AREAS = ("PROC_PO", "PROC_RR", "PROC_ITEM", "PROC_DRUG")
PROCUREMENT_AREA_OF = {"purchase_order": "PROC_PO", "invoice": "PROC_RR", "product": "PROC_ITEM", "medicine": "PROC_DRUG",
                       # the MMS document kinds (14 Oct 2026): purchasing, receiving, and the rest with the stores
                       "purchase_req": "PROC_PO", "expense_req": "PROC_ITEM", "stock_req": "PROC_ITEM",
                       "expense_issuance": "PROC_ITEM", "stock_issuance": "PROC_ITEM", "material_production": "PROC_ITEM",
                       "physical_count": "PROC_ITEM", "qty_adjustment": "PROC_ITEM"}
AREA_WORDS = {"NONE": "None", "READ": "See", "WRITE": "Propose", "ADMIN": "Approve"}
# A module that is the highest of several: PROCUREMENT (the menu, the Changes
# and Vendors tabs) is whichever area the role holds highest.
UMBRELLA = {"PROCUREMENT": PROCUREMENT_AREAS}
MODULE_WORDS = MODULES | {"PROCUREMENT": "Procurement"}        # for a refusal's sentence
FALLBACK: dict[str, str] = {}
# A module added after a role was written has no row for that role; the role
# keeps working at this level until Setup says otherwise. Timesheets: everyone
# keeps their own (WRITE); deciding them is ADMIN, given in Setup.
DEFAULT_LEVEL = {"TIME": "WRITE"}
LEVELS = ("NONE", "READ", "WRITE", "ADMIN")
RANK = {level: i for i, level in enumerate(LEVELS)}

# The starter roles, only into an empty table: once a person edits them they are theirs.
STARTER = (
    ("TECHNICIAN", "Technician", 1, {"KNOWLEDGE": "WRITE", "PROJECTS": "WRITE", "REPORTS": "READ",
                                    "SCHEDULE": "WRITE", "FINANCE": "READ", "TIME": "WRITE",
                                    "PROC_PO": "READ", "PROC_RR": "READ", "PROC_ITEM": "READ", "PROC_DRUG": "READ"}),
    ("SERVICE_MANAGER", "Service manager", 0, {"KNOWLEDGE": "ADMIN", "PROJECTS": "ADMIN", "REPORTS": "ADMIN",
                                               "SCHEDULE": "ADMIN", "FINANCE": "WRITE", "TIME": "ADMIN",
                                               "PROC_PO": "ADMIN", "PROC_RR": "ADMIN", "PROC_ITEM": "ADMIN", "PROC_DRUG": "ADMIN"}),
    ("READ_ONLY", "Read only", 0, {"KNOWLEDGE": "READ", "PROJECTS": "READ", "REPORTS": "READ",
                                   "SCHEDULE": "READ", "FINANCE": "NONE", "TIME": "READ",
                                   "PROC_PO": "NONE", "PROC_RR": "NONE", "PROC_ITEM": "NONE", "PROC_DRUG": "NONE"}),
)


class Refused(ValueError):
    """A sentence for the person; nothing was written."""


def _carry_over(conn: sqlite3.Connection) -> None:
    """040 -> 046: grants written into role_permission before Timesheets are
    read once into role_grant, whose module column carries no list. Nothing is
    deleted; role_permission stays, superseded (the port never drops a table)."""
    if conn.execute("SELECT COUNT(*) FROM role_grant").fetchone()[0]:
        return
    for r in conn.execute("SELECT role_id, module, level FROM role_permission").fetchall():
        conn.execute("INSERT OR IGNORE INTO role_grant (role_id, module, level) VALUES (?,?,?)",
                     (r[0], r[1], r[2]))


def ensure_roles(conn: sqlite3.Connection) -> None:
    """The starter roles, written on first use. OR IGNORE: two first requests
    on the threaded server can both see an empty table, and the second must
    not fail on the key the first just wrote."""
    _carry_over(conn)
    if conn.execute("SELECT COUNT(*) FROM security_role").fetchone()[0]:
        return
    for rid, name, default, grants in STARTER:
        conn.execute("INSERT OR IGNORE INTO security_role (role_id, name, is_default, inactive) VALUES (?,?,?,0)",
                     (rid, name, default))
        for module in MODULES:
            conn.execute("INSERT OR IGNORE INTO role_grant (role_id, module, level) VALUES (?,?,?)",
                         (rid, module, grants.get(module, "NONE")))


def role_of(conn, member: str) -> str | None:
    ensure_roles(conn)
    row = conn.execute("SELECT r.role_id FROM member_role m JOIN security_role r ON r.role_id = m.role_id"
                       " WHERE LOWER(m.member) = LOWER(?) AND r.inactive = 0", (member,)).fetchone()
    if row:
        return row[0]
    row = conn.execute("SELECT role_id FROM security_role WHERE is_default = 1 AND inactive = 0").fetchone()
    return row[0] if row else None


def level(conn, user, module: str) -> str:
    """The user's level in a module. A requester (on no board) has none: the
    portal is theirs, and a published requester article reaches them there."""
    if getattr(user, "is_sysadmin", False):
        return "ADMIN"
    if getattr(user, "requester", False):
        return "NONE"
    if module in UMBRELLA:
        return max((level(conn, user, m) for m in UMBRELLA[module]), key=RANK.__getitem__)
    rid = role_of(conn, user.id)
    if rid is None:
        return "NONE"
    row = conn.execute("SELECT level FROM role_grant WHERE role_id = ? AND module = ?",
                       (rid, module)).fetchone()
    if row:
        return row[0]
    if module in FALLBACK:
        return level(conn, user, FALLBACK[module])
    return DEFAULT_LEVEL.get(module, "NONE")


def levels(conn, user) -> dict[str, str]:
    """Every module's level for the user in one role lookup, for the request
    shell: five calls of level() resolved the same role five times."""
    if getattr(user, "is_sysadmin", False):
        return {m: "ADMIN" for m in (*MODULES, *UMBRELLA)}
    if getattr(user, "requester", False):
        return {m: "NONE" for m in (*MODULES, *UMBRELLA)}
    rid = role_of(conn, user.id)
    if rid is None:
        return {m: "NONE" for m in (*MODULES, *UMBRELLA)}
    got = {r[0]: r[1] for r in conn.execute("SELECT module, level FROM role_grant WHERE role_id = ?", (rid,))}
    out = {m: got.get(m, DEFAULT_LEVEL.get(m, "NONE")) for m in MODULES}
    for m, parent in FALLBACK.items():
        if m not in got:
            out[m] = out[parent]
    for m, parts in UMBRELLA.items():
        out[m] = max((out[p] for p in parts), key=RANK.__getitem__)
    return out


def allows(conn, user, module: str, need: str = "READ") -> bool:
    return RANK[level(conn, user, module)] >= RANK[need]


# ---------------------------------------------------------------- setup

def _audit(conn, *, at: datetime, actor: str, subject: str, detail: str) -> None:
    db.audit(conn, at=at.isoformat(sep=" ", timespec="minutes"), actor=actor, action="SECURITY_ROLE",
             subject_kind="security_role", subject_id=subject, detail=detail)


def roles(conn) -> list[dict]:
    ensure_roles(conn)
    out = []
    for r in conn.execute("SELECT * FROM security_role ORDER BY inactive, name"):
        grants = {row["module"]: row["level"] for row in conn.execute(
            "SELECT module, level FROM role_grant WHERE role_id = ?", (r["role_id"],))}
        members = [m[0] for m in conn.execute("SELECT member FROM member_role WHERE role_id = ? ORDER BY member",
                                              (r["role_id"],))]
        out.append(dict(r) | {"grants": {m: grants.get(m, "NONE") for m in MODULES}, "members": members})
    return out


def add_role(conn, name: str, *, copy_from: str | None = None, at: datetime, actor: str) -> str:
    ensure_roles(conn)
    name = " ".join((name or "").split())[:60]
    if not name:
        raise Refused("A role needs a name.")
    if conn.execute("SELECT 1 FROM security_role WHERE LOWER(name) = LOWER(?)", (name,)).fetchone():
        raise Refused(f"There is already a role called {name}.")
    rid = re.sub(r"[^A-Z0-9]+", "_", name.upper()).strip("_") or "ROLE"
    n = 2
    while conn.execute("SELECT 1 FROM security_role WHERE role_id = ?", (rid,)).fetchone():
        rid, n = f"{rid}_{n}", n + 1
    conn.execute("INSERT INTO security_role (role_id, name, is_default, inactive) VALUES (?,?,0,0)", (rid, name))
    base = {r["module"]: r["level"] for r in conn.execute(
        "SELECT module, level FROM role_grant WHERE role_id = ?", (copy_from or "",))}
    for module in MODULES:
        conn.execute("INSERT INTO role_grant (role_id, module, level) VALUES (?,?,?)",
                     (rid, module, base.get(module, "NONE")))
    _audit(conn, at=at, actor=actor, subject=rid, detail=f"role added: {name}" + (f", copied from {copy_from}" if base else ""))
    return rid


def save_grants(conn, role_id: str, grants: dict[str, str], *, at: datetime, actor: str) -> str:
    before = {r["module"]: r["level"] for r in conn.execute(
        "SELECT module, level FROM role_grant WHERE role_id = ?", (role_id,))}
    if not conn.execute("SELECT 1 FROM security_role WHERE role_id = ?", (role_id,)).fetchone():
        raise Refused("No such role.")
    changed = []
    for module in MODULES:
        new = grants.get(module)
        if new is None or new == before.get(module, "NONE"):
            continue
        if new not in LEVELS:
            raise Refused(f"{new} is not a level.")
        conn.execute("DELETE FROM role_grant WHERE role_id = ? AND module = ?", (role_id, module))
        conn.execute("INSERT INTO role_grant (role_id, module, level) VALUES (?,?,?)", (role_id, module, new))
        changed.append(f"{MODULES[module]} {before.get(module, 'NONE')} -> {new}")
    if changed:
        _audit(conn, at=at, actor=actor, subject=role_id, detail="; ".join(changed))
    return "; ".join(changed) or "nothing changed"


def set_default(conn, role_id: str, *, at: datetime, actor: str) -> None:
    row = conn.execute("SELECT inactive FROM security_role WHERE role_id = ?", (role_id,)).fetchone()
    if row is None or row[0]:
        raise Refused("Only a role in use can be the default.")
    conn.execute("UPDATE security_role SET is_default = 0")
    conn.execute("UPDATE security_role SET is_default = 1 WHERE role_id = ?", (role_id,))
    _audit(conn, at=at, actor=actor, subject=role_id, detail="made the default role")


def set_inactive(conn, role_id: str, inactive: bool, *, at: datetime, actor: str) -> None:
    row = conn.execute("SELECT is_default FROM security_role WHERE role_id = ?", (role_id,)).fetchone()
    if row is None:
        raise Refused("No such role.")
    if inactive and row[0]:
        raise Refused("The default role cannot be retired; make another the default first.")
    conn.execute("UPDATE security_role SET inactive = ? WHERE role_id = ?", (int(inactive), role_id))
    _audit(conn, at=at, actor=actor, subject=role_id, detail="retired" if inactive else "restored")


def assign(conn, member: str, role_id: str | None, *, at: datetime, actor: str) -> str:
    """Give a member a role, or (role_id None) put them back on the default."""
    member = (member or "").strip()
    if not member:
        raise Refused("Name the member.")
    before = conn.execute("SELECT role_id FROM member_role WHERE LOWER(member) = LOWER(?)", (member,)).fetchone()
    conn.execute("DELETE FROM member_role WHERE LOWER(member) = LOWER(?)", (member,))
    if role_id:
        if not conn.execute("SELECT 1 FROM security_role WHERE role_id = ? AND inactive = 0", (role_id,)).fetchone():
            raise Refused("No such role in use.")
        conn.execute("INSERT INTO member_role (member, role_id, assigned_at, assigned_by) VALUES (?,?,?,?)",
                     (member, role_id, at.isoformat(sep=" ", timespec="minutes"), actor))
    detail = f"{member}: {before[0] if before else 'default'} -> {role_id or 'default'}"
    _audit(conn, at=at, actor=actor, subject=role_id or "DEFAULT", detail=detail)
    return detail

"""Board kinds and board Types (ITIL), change approval and ticket links.

A board is one of three kinds: SERVICE, CHANGE or PROJECT (board.kind). A
board's Types are ConnectWise's Types tab, and on a service board they are the
ITIL four: Incident, Request, Problem, Event. A ticket reads Type > Subtype >
Item. The Type is stored as ticket.record_type; "record type" in this module
means the board Type.

One vocabulary, six words: INCIDENT, SERVICE_REQUEST, PROBLEM, EVENT, CHANGE,
PROJECT. The first four are ConnectWise's own ITIL example Types for a service
board, and Dada's workbook column A (see schema/022). CHANGE and PROJECT are the
work whose workflow differs enough to run on a board of its own.

Everything that decides a ticket's record type, whether a board takes it, which
SLA targets it runs on, and what its commercial path is lives here, so that the
four intake doors, the desk, a board move and a field edit cannot disagree.

Change enablement follows ITIL 4 (and ConnectWise's Service Transition page,
which uses the same three words): a STANDARD change is pre-authorised; a NORMAL
change may not enter an "authorised" status (board_status.requires_approval)
until a change authority has approved it; an EMERGENCY change goes ahead and may
not be closed until an authorisation has been recorded afterwards. The owner of
a change never authorises it.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime

RECORD_TYPES = ("INCIDENT", "SERVICE_REQUEST", "PROBLEM", "EVENT", "CHANGE", "PROJECT")
LABEL = {"INCIDENT": "Incident", "SERVICE_REQUEST": "Request", "PROBLEM": "Problem",
         "EVENT": "Event", "CHANGE": "Change", "PROJECT": "Project"}
# ConnectWise's Type category: Reactive or Proactive. The commercial path in 005
# predates this and uses INCIDENT / SERVICE_REQUEST for the same split.
PROACTIVE = frozenset({"SERVICE_REQUEST", "CHANGE", "PROJECT"})

# The board profiles: which record types a new board takes, the first its default.
PROFILES = {
    "SERVICE": ("INCIDENT", "SERVICE_REQUEST", "PROBLEM", "EVENT"),
    "CHANGE": ("CHANGE",),
    "PROJECT": ("PROJECT",),
}
PROFILE_LABEL = {
    "SERVICE": "Service board: incidents, service requests, problems, events",
    "CHANGE": "Change board: changes, with approval",
    "PROJECT": "Project board: projects",
}

CHANGE_TYPES = ("STANDARD", "NORMAL", "EMERGENCY")
RISKS = ("LOW", "MEDIUM", "HIGH")
AUTHORITIES = ("CHANGE_AUTHORITY", "CAB", "ECAB", "CLIENT")
RELATIONS = {
    # relation: (the linked ticket must be, how the pair reads)
    "CAUSED_BY": ("PROBLEM", "caused by problem"),
    "FIXED_BY": ("CHANGE", "fixed by change"),
    "RELATED": (None, "related to"),
}


class NotAccepted(ValueError):
    """The board does not take this record type."""


class ChangeNotAuthorised(ValueError):
    """A change tried to go where only an authorised change may go."""


# ----------------------------------------------------------- record types

def boards_types(conn: sqlite3.Connection, board_id: str) -> list[sqlite3.Row]:
    return conn.execute("SELECT record_type, is_default FROM board_record_type"
                        " WHERE board_id = ? ORDER BY is_default DESC, record_type",
                        (board_id,)).fetchall()


def accepts(conn: sqlite3.Connection, board_id: str, record_type: str | None) -> bool:
    """A board with no rows takes every type; a ticket with no type fits anywhere."""
    if record_type is None:
        return True
    rows = boards_types(conn, board_id)
    return not rows or any(r["record_type"] == record_type for r in rows)


def board_default(conn: sqlite3.Connection, board_id: str) -> str | None:
    rows = boards_types(conn, board_id)
    for r in rows:
        if r["is_default"]:
            return r["record_type"]
    return rows[0]["record_type"] if len(rows) == 1 else None


def fit(conn: sqlite3.Connection, board_id: str, wanted: str | None) -> str | None:
    """`wanted` if the board takes it, else None (so the board default applies)."""
    return wanted if wanted and accepts(conn, board_id, wanted) else None


def of_item(conn: sqlite3.Connection, item) -> str | None:
    """A catalogue item's record type: its own, else from its action's kind."""
    if item is None:
        return None
    if item["record_type"]:
        return item["record_type"]
    kind = conn.execute("SELECT kind FROM service_action WHERE action_id = ?",
                        (item["action_id"],)).fetchone()
    if kind is None:
        return None
    return {"FAULT": "INCIDENT", "REQUEST": "SERVICE_REQUEST"}.get(kind["kind"])


def resolve(conn: sqlite3.Connection, board_id: str, *, explicit: str | None = None,
            item=None) -> str | None:
    """The record type a new ticket gets: said, else the item's, else the board's
    default, else not set. Refuses a type the board does not take."""
    if explicit is not None and explicit not in RECORD_TYPES:
        raise NotAccepted(f"unknown record type {explicit!r}")
    chosen = explicit or of_item(conn, item) or board_default(conn, board_id)
    if not accepts(conn, board_id, chosen):
        names = ", ".join(LABEL[r["record_type"]] for r in boards_types(conn, board_id))
        raise NotAccepted(f"this board does not take {LABEL.get(chosen, chosen)}; "
                          f"it takes {names}")
    return chosen


def derive_path(record_type: str | None, contract_basis: str | None) -> str:
    """The commercial path (005): VARIATION if the basis is, else the record
    type's Reactive/Proactive side. Never passed in by a caller, because a path
    that disagrees with its basis is how the variation gate was bypassed."""
    if contract_basis == "VARIATION":
        return "VARIATION"
    return "SERVICE_REQUEST" if record_type in PROACTIVE else "INCIDENT"


def set_board_types(conn: sqlite3.Connection, board_id: str, types, *,
                    default: str | None = None) -> None:
    """Replace which record types a board takes. The first is the default unless
    one is named. An empty list means the board takes every type."""
    types = [t for t in types if t]
    unknown = [t for t in types if t not in RECORD_TYPES]
    if unknown:
        raise NotAccepted("unknown record type(s) " + ", ".join(unknown))
    if default and default not in types:
        raise NotAccepted("the default must be one of the types the board takes")
    conn.execute("DELETE FROM board_record_type WHERE board_id = ?", (board_id,))
    for n, rt in enumerate(dict.fromkeys(types)):
        is_default = (rt == default) if default else n == 0
        conn.execute("INSERT INTO board_record_type (board_id, record_type, is_default)"
                     " VALUES (?,?,?)", (board_id, rt, 1 if is_default else 0))


def profile_of(conn: sqlite3.Connection, board_id: str) -> str | None:
    """The board's kind: SERVICE, CHANGE or PROJECT. NULL reads as SERVICE."""
    row = conn.execute("SELECT kind FROM board WHERE board_id = ?", (board_id,)).fetchone()
    if row is None:
        return None
    return row["kind"] or "SERVICE"


# ------------------------------------------------------------- SLA targets

def targets(conn: sqlite3.Connection, board_id: str, record_type: str | None,
            priority: str) -> list[sqlite3.Row]:
    """The clocks a ticket runs on: its record type's targets on this board if
    any exist for its priority, else the board's general ones."""
    if record_type:
        typed = conn.execute(
            "SELECT clock, target_minutes FROM sla_target_type WHERE board_id = ?"
            " AND record_type = ? AND priority = ?", (board_id, record_type, priority)).fetchall()
        if typed:
            return typed
    return conn.execute("SELECT clock, target_minutes FROM sla_target"
                        " WHERE board_id = ? AND priority = ?", (board_id, priority)).fetchall()


# ------------------------------------------------------------ change enablement

def latest_decision(conn: sqlite3.Connection, work_item_id: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM change_approval WHERE work_item_id = ?"
                        " ORDER BY approval_id DESC LIMIT 1", (work_item_id,)).fetchone()


def check_status_move(conn: sqlite3.Connection, ticket, new_status) -> None:
    """Refuse a change's move that its authorisation does not allow."""
    if ticket["record_type"] != "CHANGE":
        return
    kind = ticket["change_type"] or "NORMAL"
    decision = latest_decision(conn, ticket["work_item_id"])
    if kind == "NORMAL" and new_status["requires_approval"]:
        if decision is None or decision["decision"] != "APPROVED":
            raise ChangeNotAuthorised(
                f"a normal change enters {new_status['name']!r} only once it is approved"
                + ("; the last decision was DECLINED" if decision else "; no decision yet"))
    if kind == "EMERGENCY" and new_status["is_closed"] and decision is None:
        raise ChangeNotAuthorised("an emergency change is closed only once its "
                                  "authorisation has been recorded, afterwards")


def may_authorise(conn: sqlite3.Connection, board_id: str, member: str) -> bool:
    """A board administrator, or the board's Service Manager."""
    return conn.execute(
        "SELECT 1 FROM board_member WHERE board_id = ? AND member = ? AND access = 'ADMIN'"
        " UNION SELECT 1 FROM board_role WHERE board_id = ? AND member = ?"
        " AND role = 'SERVICE_MANAGER'", (board_id, member, board_id, member)).fetchone() is not None


def decide(conn: sqlite3.Connection, work_item_id: str, *, decision: str, authority: str,
           actor: str, at: datetime, comment: str | None = None) -> int:
    """Record a change authority's decision on a change. Append-only."""
    from .board import _event, touch
    t = conn.execute("SELECT * FROM ticket WHERE work_item_id = ?", (work_item_id,)).fetchone()
    if t is None:
        raise LookupError(f"no ticket {work_item_id!r}")
    if t["record_type"] != "CHANGE":
        raise ChangeNotAuthorised("only a change is authorised")
    if decision not in ("APPROVED", "DECLINED"):
        raise ValueError(f"unknown decision {decision!r}")
    if authority not in AUTHORITIES:
        raise ValueError(f"unknown change authority {authority!r}")
    if t["owner"] and t["owner"].lower() == actor.lower():
        raise PermissionError("the owner of a change does not authorise it")
    if not may_authorise(conn, t["board_id"], actor):
        raise PermissionError("authorising a change takes the board's administrator "
                              "or its Service Manager")
    stamp = at.isoformat(sep=" ", timespec="minutes")
    cur = conn.execute(
        "INSERT INTO change_approval (work_item_id, decided_by, authority, decision,"
        " decided_at, comment) VALUES (?,?,?,?,?,?)",
        (work_item_id, actor, authority, decision, stamp, (comment or "").strip() or None))
    _event(conn, work_item_id, stamp, "CHANGE_DECISION", actor,
           f"{decision.lower()} by {authority.replace('_', ' ').lower()}"
           + (f": {comment.strip()}" if comment and comment.strip() else ""))
    touch(conn, work_item_id, at)
    return cur.lastrowid


# ------------------------------------------------------------------ links

def link(conn: sqlite3.Connection, work_item_id: str, linked_id: str, relation: str, *,
         actor: str, at: datetime) -> bool:
    """Link two tickets: an incident CAUSED_BY a problem, anything FIXED_BY a
    change, or RELATED. Both tickets keep their own clocks and status."""
    from .board import _event, touch
    if relation not in RELATIONS:
        raise ValueError(f"unknown relation {relation!r}")
    if work_item_id == linked_id:
        raise ValueError("a ticket is not linked to itself")
    rows = {r["work_item_id"]: r for r in conn.execute(
        "SELECT work_item_id, record_type FROM ticket WHERE work_item_id IN (?, ?)",
        (work_item_id, linked_id))}
    for wid in (work_item_id, linked_id):
        if wid not in rows:
            raise LookupError(f"no ticket {wid!r}")
    must_be, reads = RELATIONS[relation]
    if must_be and rows[linked_id]["record_type"] != must_be:
        raise ValueError(f"{linked_id} is not a {LABEL[must_be].lower()}, so this ticket "
                         f"cannot be {reads} it")
    stamp = at.isoformat(sep=" ", timespec="minutes")
    cur = conn.execute("INSERT OR IGNORE INTO ticket_link (work_item_id, linked_id, relation,"
                       " linked_at, linked_by) VALUES (?,?,?,?,?)",
                       (work_item_id, linked_id, relation, stamp, actor))
    if cur.rowcount:
        _event(conn, work_item_id, stamp, "LINKED", actor, f"{reads} {linked_id}")
        back = {"CAUSED_BY": "causes", "FIXED_BY": "fixes", "RELATED": "related to"}[relation]
        _event(conn, linked_id, stamp, "LINKED", actor, f"{back} {work_item_id}")
        touch(conn, work_item_id, at)
    return bool(cur.rowcount)


def unlink(conn: sqlite3.Connection, work_item_id: str, linked_id: str, *, actor: str,
           at: datetime) -> bool:
    from .board import _event, touch
    stamp = at.isoformat(sep=" ", timespec="minutes")
    cur = conn.execute("DELETE FROM ticket_link WHERE work_item_id = ? AND linked_id = ?",
                       (work_item_id, linked_id))
    if cur.rowcount:
        _event(conn, work_item_id, stamp, "UNLINKED", actor, f"link to {linked_id} removed")
        _event(conn, linked_id, stamp, "UNLINKED", actor, f"link from {work_item_id} removed")
        touch(conn, work_item_id, at)
    return bool(cur.rowcount)


def links_of(conn: sqlite3.Connection, work_item_id: str) -> list[dict]:
    """Both directions, each phrased from this ticket's side."""
    out = []
    for r in conn.execute(
            "SELECT l.linked_id AS other, l.relation, t.board_id, t.record_type, w.name"
            "  FROM ticket_link l JOIN ticket t ON t.work_item_id = l.linked_id"
            "  JOIN work_item w ON w.work_item_id = l.linked_id WHERE l.work_item_id = ?",
            (work_item_id,)):
        out.append(dict(r) | {"reads": RELATIONS[r["relation"]][1], "outgoing": True})
    back = {"CAUSED_BY": "causes", "FIXED_BY": "fixes", "RELATED": "related to"}
    for r in conn.execute(
            "SELECT l.work_item_id AS other, l.relation, t.board_id, t.record_type, w.name"
            "  FROM ticket_link l JOIN ticket t ON t.work_item_id = l.work_item_id"
            "  JOIN work_item w ON w.work_item_id = l.work_item_id WHERE l.linked_id = ?",
            (work_item_id,)):
        out.append(dict(r) | {"reads": back[r["relation"]], "outgoing": False})
    return out

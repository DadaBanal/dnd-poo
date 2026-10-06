"""Several members on one ticket (067, Dada 6 Oct 2026: "assigning tickets to
multiple members").

The reference PSA's Resources: the owner is the one point of contact, and any
number of other members can be on the ticket as well. A resource here is either
a member assigned in this table or a member with a visit booked on the ticket
(038); `everyone` gives both, and the ticket page shows them together. Taking
somebody off removes only their assignment here, never a visit they have.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime


def assigned(conn: sqlite3.Connection, work_item_id: str) -> list[str]:
    """The members assigned here, in the order they were added."""
    return [r[0] for r in conn.execute(
        "SELECT member FROM ticket_resource WHERE work_item_id = ? ORDER BY added_at, member", (work_item_id,))]


def everyone(conn: sqlite3.Connection, work_item_id: str) -> list[str]:
    """Assigned members, then anybody with a visit who is not already listed."""
    from . import schedule
    out = assigned(conn, work_item_id)
    seen = {m.lower() for m in out}
    for r in schedule.entries_for(conn, work_item_id):
        if r["member"].lower() not in seen:
            seen.add(r["member"].lower())
            out.append(r["member"])
    return out


def set_(conn: sqlite3.Connection, work_item_id: str, members, *, at: datetime, actor: str,
         allowed=None) -> str:
    """Make the assigned members exactly `members`. Returns a line for the
    Saved message, or "" when nothing changed. `allowed` (lower-case ids) is who
    may be added: the board's working members; an existing assignment of
    somebody who has since left the board is kept, not silently dropped."""
    from .board import _event
    from . import outbox
    want, seen = [], set()
    for m in members or []:
        m = (m or "").strip()
        if m and m.lower() not in seen:
            seen.add(m.lower())
            want.append(m)
    have = {m.lower(): m for m in assigned(conn, work_item_id)}
    added = [m for m in want if m.lower() not in have]
    if allowed is not None:
        refused = [m for m in added if m.lower() not in allowed]
        if refused:
            raise ValueError(f"{', '.join(refused)} cannot be put on this ticket: not a working member of its board")
    removed = [m for k, m in have.items() if k not in seen]
    if not added and not removed:
        return ""
    stamp = at.isoformat(sep=" ", timespec="minutes")
    for m in added:
        conn.execute("INSERT INTO ticket_resource (work_item_id, member, added_at, added_by) VALUES (?,?,?,?)",
                     (work_item_id, m, stamp, actor))
    for m in removed:
        conn.execute("DELETE FROM ticket_resource WHERE work_item_id = ? AND LOWER(member) = ?",
                     (work_item_id, m.lower()))
    bits = ([f"added {', '.join(added)}"] if added else []) + ([f"took off {', '.join(removed)}"] if removed else [])
    _event(conn, work_item_id, stamp, "RESOURCE", actor, "resources: " + "; ".join(bits))
    for m in added:
        outbox.queue_resource(conn, work_item_id, m, at=at, actor=actor)
    return "resources " + "; ".join(bits)


def tickets_of(conn: sqlite3.Connection, member: str) -> set[str]:
    return {r[0] for r in conn.execute("SELECT work_item_id FROM ticket_resource WHERE LOWER(member) = ?",
                                       ((member or "").lower(),))}

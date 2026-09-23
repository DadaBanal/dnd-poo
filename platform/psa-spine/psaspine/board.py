"""One status change, and everything that follows from it.

Until now the board, the clocks and the rules were three libraries that happened
to share a database. This is the seam: moving a ticket to a status stops the
clocks that status satisfies, pauses or resumes the ones it does not, keeps the
universal lifecycle in step, and writes what happened down.

It is one function on purpose. The moment a status change is done in two places
they disagree, and the place they disagree is a clock that says a P1 was answered
when nobody answered it.

What this module does NOT do is act on rules. `rules.evaluate` decides; the
caller sends the page. That boundary is why all of this is testable without a
mail server, and it is kept here too.
"""
from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime

from . import clocks

# The universal lifecycle a board status maps onto. `state` is what the variation
# gate in 005 tests, so it cannot depend on a vocabulary each board edits.
LIFECYCLE = {
    "NOT_RESPONDED": "NEW",
    "RESPONDED": "IN_PROGRESS",
    "RESOLUTION_PLAN": "IN_PROGRESS",
    "RESOLVED": "RESOLVED",
    "NO_ESCALATION": "WAITING_CLIENT",
}


class NotOnThisBoard(Exception):
    """A status from another board. Refused rather than accepted, because a
    ticket wearing another board's status is a ticket no report can group."""


class EffortRefused(Exception):
    """The closed loop was asked to do something a gate forbids — band effort on
    a status that disallows it, or close a variation-path ticket with no
    variation. Raised before anything is written, so nothing partial is left."""


def status(conn: sqlite3.Connection, board_status_id: str) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM board_status WHERE board_status_id = ?",
                       (board_status_id,)).fetchone()
    if row is None:
        raise LookupError(f"no board status {board_status_id!r}")
    return row


def open_clocks(conn: sqlite3.Connection, work_item_id: str, *, at: datetime,
                calendar_id: str) -> list[int]:
    """Start the clocks this ticket's board and priority call for.

    Targets come from `sla_target`, which still ships `enforced = 0` on every
    row. Starting a clock measures; it does not promise.
    """
    ticket = conn.execute("SELECT board_id, priority FROM ticket WHERE work_item_id = ?",
                          (work_item_id,)).fetchone()
    if ticket is None:
        raise LookupError(f"no ticket {work_item_id!r}")

    started: list[int] = []
    for target in conn.execute(
            "SELECT clock, target_minutes FROM sla_target"
            " WHERE board_id = ? AND priority = ?", (ticket["board_id"], ticket["priority"])):
        cur = conn.execute(
            "INSERT OR IGNORE INTO ticket_clock (work_item_id, clock, calendar_id,"
            " target_minutes, started_at) VALUES (?,?,?,?,?)",
            (work_item_id, target["clock"], calendar_id, target["target_minutes"],
             at.isoformat(sep=" ", timespec="minutes")))
        if cur.rowcount:
            started.append(cur.lastrowid)
    return started


def running_clocks(conn: sqlite3.Connection, work_item_id: str) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM ticket_clock WHERE work_item_id = ? AND stopped_at IS NULL",
        (work_item_id,)).fetchall()


def change_status(conn: sqlite3.Connection, work_item_id: str, to_status_id: str, *,
                  at: datetime, actor: str) -> dict:
    """Move a ticket to a status, and settle everything that follows.

    Returns what changed, so a caller can report it and a test can assert it
    rather than inspecting five tables.
    """
    ticket = conn.execute("SELECT * FROM ticket WHERE work_item_id = ?",
                          (work_item_id,)).fetchone()
    if ticket is None:
        raise LookupError(f"no ticket {work_item_id!r}")

    new = status(conn, to_status_id)
    if new["board_id"] != ticket["board_id"]:
        raise NotOnThisBoard(
            f"status {to_status_id!r} belongs to board {new['board_id']!r} but the "
            f"ticket is on {ticket['board_id']!r}. Move the ticket first; a handover "
            f"is one ticket changing board, not a status borrowed from another one.")
    if new["inactive"]:
        raise NotOnThisBoard(
            f"status {to_status_id!r} is retired. Retired statuses stay for the "
            f"tickets that sat in them; nothing new enters one.")

    stamp = at.isoformat(sep=" ", timespec="minutes")
    escalation = new["escalation_status"]
    stopped, paused, resumed = [], [], []

    for clock in running_clocks(conn, work_item_id):
        open_pause = conn.execute(
            "SELECT pause_id FROM ticket_clock_pause WHERE clock_id = ?"
            "   AND resumed_at IS NULL", (clock["clock_id"],)).fetchone()

        if clocks.stops_clock(escalation, clock["clock"]):
            # Close any pause first, or the paused interval runs past the stop.
            if open_pause:
                conn.execute("UPDATE ticket_clock_pause SET resumed_at = ? WHERE pause_id = ?",
                             (stamp, open_pause["pause_id"]))
                resumed.append(clock["clock"])
            conn.execute(
                "UPDATE ticket_clock SET stopped_at = ?, stopped_by_status = ?"
                " WHERE clock_id = ?", (stamp, to_status_id, clock["clock_id"]))
            stopped.append(clock["clock"])
        elif clocks.is_pause(escalation, clock["clock"]):
            if not open_pause:
                conn.execute(
                    "INSERT INTO ticket_clock_pause (clock_id, paused_at, board_status_id)"
                    " VALUES (?,?,?)", (clock["clock_id"], stamp, to_status_id))
                paused.append(clock["clock"])
        elif open_pause:
            conn.execute("UPDATE ticket_clock_pause SET resumed_at = ? WHERE pause_id = ?",
                         (stamp, open_pause["pause_id"]))
            resumed.append(clock["clock"])

    # The universal lifecycle follows the board's status, never the other way.
    # A closed status closes the ticket whatever milestone it declares.
    state = "CLOSED" if new["is_closed"] else LIFECYCLE.get(escalation, ticket["state"])
    conn.execute(
        "UPDATE ticket SET board_status_id = ?, state = ?,"
        " closed_at = CASE WHEN ? = 1 THEN ? ELSE closed_at END"
        " WHERE work_item_id = ?",
        (to_status_id, state, 1 if new["is_closed"] else 0, stamp, work_item_id))

    conn.execute(
        "INSERT INTO ticket_event (work_item_id, occurred_at, kind, actor, detail)"
        " VALUES (?,?,'STATUS_CHANGE',?,?)",
        (work_item_id, stamp, actor,
         f"{ticket['board_status_id'] or ticket['state']} -> {to_status_id} "
         f"({escalation}); stopped={stopped or '-'} paused={paused or '-'} "
         f"resumed={resumed or '-'}"))

    touch(conn, work_item_id, at)
    return {"work_item_id": work_item_id, "board_status_id": to_status_id,
            "state": state, "escalation_status": escalation,
            "stopped": stopped, "paused": paused, "resumed": resumed,
            "time_entry_allowed": bool(new["time_entry_allowed"])}


def may_book_effort(conn: sqlite3.Connection, work_item_id: str) -> tuple[bool, str]:
    """Whether effort may be booked against this ticket right now, and why not.

    Two independent gates, and both have to pass. The variation gate in 005 is
    enforced by a trigger and will refuse the insert regardless; this reports the
    same answer before the attempt, so a user interface can say why rather than
    showing a database error to a nurse.
    """
    row = conn.execute(
        "SELECT t.board_status_id, t.path, w.variation_id, s.name, s.time_entry_allowed"
        "  FROM ticket t JOIN work_item w ON w.work_item_id = t.work_item_id"
        "  LEFT JOIN board_status s ON s.board_status_id = t.board_status_id"
        " WHERE t.work_item_id = ?", (work_item_id,)).fetchone()
    if row is None:
        raise LookupError(f"no ticket {work_item_id!r}")

    if row["path"] == "VARIATION" and row["variation_id"] is None:
        return False, ("a variation-path ticket must be attached to a variation before "
                       "it can consume effort")
    if row["board_status_id"] and not row["time_entry_allowed"]:
        return False, f"the status {row['name']!r} does not allow effort to be booked"
    return True, "allowed"


def current_oncall(conn: sqlite3.Connection, board_id: str, role: str, *,
                   at: datetime | None = None) -> str | None:
    """Who is on call for this board and role at `at` (default: now).

    The rota answers the question board_role cannot: not "who is the named
    on-call member" but "who is actually on shift right now". Slots are compared
    as parsed instants rather than by text order, because the record carries dates
    in more than one shape and a lexical comparison of mixed shapes is a bug
    waiting for a night shift. Overlapping slots resolve to the one that started
    most recently — a hand-off writes a new slot, and the new slot wins.
    """
    at = at or datetime.now()
    best: tuple[datetime, str] | None = None
    for row in conn.execute(
            "SELECT member, starts_at, ends_at FROM oncall_slot"
            " WHERE board_id = ? AND role = ?", (board_id, role)):
        start = clocks.parse_instant(row["starts_at"])
        end = clocks.parse_instant(row["ends_at"])
        if start <= at < end and (best is None or start > best[0]):
            best = (start, row["member"])
    return best[1] if best else None


def close_loop(conn: sqlite3.Connection, work_item_id: str, to_status_id: str, *,
               body: str, sent_by: str, at: datetime, actor: str | None = None,
               band_hours: float | None = None, performed_by: str | None = None,
               entered_by: str | None = None, entity_id: str | None = None,
               charge_method: str = "INCLUDED_IN_MONTHLY_FEE",
               authority_source: str | None = None,
               counts_to_capacity: bool = True) -> dict:
    """Answer the requester and band the effort in one action, then close.

    This is §5.2 made mechanical: the reply and the banding are a single write,
    so the numerator of an uplift claim is captured by construction rather than by
    a fulfiller remembering to log time after the fact. The effort still goes
    through the variation gate in 005 — the loop makes the honest path the easy
    one, it does not open a way round the gate.

    Refuses BEFORE writing anything if the ticket is variation-path with no
    variation attached (the close would be refused anyway, and a half-written loop
    reply is worse than a clear refusal), or if banding is asked for with no entity
    to book it against.
    """
    ticket = conn.execute(
        "SELECT t.path, t.owner, w.variation_id, w.entity_id"
        "  FROM ticket t JOIN work_item w ON w.work_item_id = t.work_item_id"
        " WHERE t.work_item_id = ?", (work_item_id,)).fetchone()
    if ticket is None:
        raise LookupError(f"no ticket {work_item_id!r}")

    if ticket["path"] == "VARIATION" and ticket["variation_id"] is None:
        raise EffortRefused(
            "a variation-path ticket cannot be closed with no variation attached")

    book_entity = entity_id or ticket["entity_id"]
    if band_hours is not None and not book_entity:
        raise EffortRefused(
            "effort was banded but the work item names no entity to book it against")

    stamp = at.isoformat(sep=" ", timespec="minutes")
    loop_reply_id = f"LR-{uuid.uuid4().hex[:16]}"
    effort_minutes = int(round(band_hours * 60)) if band_hours is not None else None

    conn.execute(
        "INSERT INTO loop_reply (loop_reply_id, work_item_id, body, sent_at,"
        " sent_by, effort_minutes, banded_at) VALUES (?,?,?,?,?,?,?)",
        (loop_reply_id, work_item_id, body, stamp, sent_by, effort_minutes,
         stamp if band_hours is not None else None))

    if band_hours is not None:
        conn.execute(
            "INSERT INTO time_entry (work_item_id, entity_id, worked_on, band_hours,"
            " performed_by, entered_by, counts_to_capacity, charge_method,"
            " authority_source, loop_reply_id) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (work_item_id, book_entity, at.date().isoformat(), band_hours,
             performed_by or sent_by, entered_by or sent_by,
             1 if counts_to_capacity else 0, charge_method, authority_source,
             loop_reply_id))

    # The reply is what the requester reads on the portal, so it is a
    # Resolution note on the ticket as well as a loop_reply row.
    conn.execute(
        "INSERT INTO ticket_event (work_item_id, occurred_at, kind, actor, detail,"
        " note_flag) VALUES (?,?,'LOOP_REPLY',?,?,'RESOLUTION')",
        (work_item_id, stamp, sent_by, body))
    result = change_status(conn, work_item_id, to_status_id, at=at,
                           actor=actor or sent_by)
    return {"loop_reply_id": loop_reply_id, "effort_minutes": effort_minutes,
            "band_hours": band_hours, "status": result}


# The catch-all a ticket's company falls to when intake cannot tell who it is
# for — ConnectWise's email connector does the same with a "catch-all" company.
# It is a seeded entity that is flagged, never a guess that it is PMC.
UNKNOWN_ENTITY = "UNCLASSIFIED"


def default_status(conn: sqlite3.Connection, board_id: str,
                   escalation: str | None = None) -> str | None:
    """The status a ticket lands in on this board.

    With `escalation`, the first active status that declares the same SLA
    milestone — so a ticket moved between boards keeps its place in the
    lifecycle rather than falling back to New.
    """
    if escalation:
        row = conn.execute(
            "SELECT board_status_id FROM board_status WHERE board_id = ?"
            " AND escalation_status = ? AND is_closed = 0 AND inactive = 0"
            " ORDER BY is_default DESC, sort_order LIMIT 1",
            (board_id, escalation)).fetchone()
        if row:
            return row["board_status_id"]
    row = conn.execute(
        "SELECT board_status_id FROM board_status WHERE board_id = ?"
        " AND is_default = 1 AND inactive = 0 LIMIT 1", (board_id,)).fetchone()
    return row["board_status_id"] if row else None


def touch(conn: sqlite3.Connection, work_item_id: str, at: datetime) -> None:
    conn.execute("UPDATE ticket SET updated_at = ? WHERE work_item_id = ?",
                 (at.isoformat(sep=" ", timespec="minutes"), work_item_id))


def admit(conn: sqlite3.Connection, work_item_id: str, *, at: datetime) -> dict:
    """Everything a new ticket needs the moment it exists, in one place.

    Every way in — the portal, email, the machine API, a fulfiller's New Ticket
    — calls this, so a ticket is never on a board without a status, a company
    or its clocks. That was the gap: the engine could run clocks, but nothing
    that opened a ticket ever started one.

    - the board's default status, if the ticket has none;
    - a company: the catch-all if intake could not tell;
    - the SLA clocks the board's targets call for, on the board's calendar,
      started at the moment the ticket was opened. A board that is not set up
      starts none, and the board view says so.
    """
    ticket = conn.execute(
        "SELECT t.board_id, t.board_status_id, t.opened_at, b.calendar_id"
        "  FROM ticket t JOIN board b ON b.board_id = t.board_id"
        " WHERE t.work_item_id = ?", (work_item_id,)).fetchone()
    if ticket is None:
        raise LookupError(f"no ticket {work_item_id!r}")

    landed = ticket["board_status_id"]
    if landed is None:
        landed = default_status(conn, ticket["board_id"])
        if landed:
            conn.execute("UPDATE ticket SET board_status_id = ? WHERE work_item_id = ?",
                         (landed, work_item_id))

    conn.execute("UPDATE work_item SET entity_id = ? WHERE work_item_id = ?"
                 " AND entity_id IS NULL", (UNKNOWN_ENTITY, work_item_id))

    started: list[int] = []
    if ticket["calendar_id"]:
        opened = clocks.parse_instant(ticket["opened_at"])
        started = open_clocks(conn, work_item_id, at=opened,
                              calendar_id=ticket["calendar_id"])
    touch(conn, work_item_id, at)
    return {"work_item_id": work_item_id, "board_status_id": landed,
            "clocks_started": len(started)}


def move(conn: sqlite3.Connection, work_item_id: str, to_board_id: str, *,
         at: datetime, actor: str, owner: str | None = None,
         reason: str = "moved") -> dict:
    """Move a ticket to another board. One ticket, one id, its clocks intact.

    ConnectWise documents that Auto Assign does not follow a ticket moved from
    another board (§5.2 of the build scope); cross-board handover on one id is
    the thing this desk must do better, so the move keeps the ticket's clocks
    running and lands it on the new board's status for the same SLA milestone.
    """
    ticket = conn.execute(
        "SELECT t.board_id, t.owner, s.escalation_status FROM ticket t"
        "  LEFT JOIN board_status s ON s.board_status_id = t.board_status_id"
        " WHERE t.work_item_id = ?", (work_item_id,)).fetchone()
    if ticket is None:
        raise LookupError(f"no ticket {work_item_id!r}")
    if ticket["board_id"] == to_board_id:
        raise NotOnThisBoard(f"{work_item_id} is already on {to_board_id}")
    if conn.execute("SELECT 1 FROM board WHERE board_id = ?",
                    (to_board_id,)).fetchone() is None:
        raise LookupError(f"no board {to_board_id!r}")

    stamp = at.isoformat(sep=" ", timespec="minutes")
    landed = default_status(conn, to_board_id, ticket["escalation_status"])
    conn.execute(
        "INSERT INTO ticket_handover (work_item_id, from_board_id, to_board_id,"
        " handover_at, from_owner, to_owner, reason) VALUES (?,?,?,?,?,?,?)",
        (work_item_id, ticket["board_id"], to_board_id, stamp, ticket["owner"],
         owner or ticket["owner"], reason))
    conn.execute(
        "UPDATE ticket SET board_id = ?, board_status_id = ?,"
        " owner = COALESCE(?, owner) WHERE work_item_id = ?",
        (to_board_id, landed, owner, work_item_id))
    conn.execute(
        "INSERT INTO ticket_event (work_item_id, occurred_at, kind, actor, detail)"
        " VALUES (?,?,'ROUTED',?,?)",
        (work_item_id, stamp, actor,
         f"moved {ticket['board_id']} -> {to_board_id}"
         + (f", owner {owner}" if owner else "") + f" ({reason})"))
    # A board that had no calendar may have started no clocks; start them now.
    cal = conn.execute("SELECT calendar_id FROM board WHERE board_id = ?",
                       (to_board_id,)).fetchone()["calendar_id"]
    if cal and not conn.execute("SELECT 1 FROM ticket_clock WHERE work_item_id = ?",
                                (work_item_id,)).fetchone():
        open_clocks(conn, work_item_id, at=at, calendar_id=cal)
    touch(conn, work_item_id, at)
    return {"work_item_id": work_item_id, "board_id": to_board_id,
            "board_status_id": landed}


NOTE_FLAGS = ("DISCUSSION", "INTERNAL", "RESOLUTION")
CHARGE_METHODS = ("INCLUDED_IN_MONTHLY_FEE", "CAPACITY_UPLIFT", "SEPARATE_CHARGE",
                  "PASS_THROUGH", "NON_CHARGEABLE")
# The bands effort is recorded in (003_delivery: time_entry.band_hours).
BANDS = (0.5, 2, 4, 8, 20)


def _event(conn, work_item_id, stamp, kind, actor, detail, flag=None):
    conn.execute(
        "INSERT INTO ticket_event (work_item_id, occurred_at, kind, actor, detail,"
        " note_flag) VALUES (?,?,?,?,?,?)",
        (work_item_id, stamp, kind, actor, detail, flag))


def add_note(conn: sqlite3.Connection, work_item_id: str, *, body: str, flag: str,
             actor: str, at: datetime, band_hours: float | None = None,
             charge_method: str | None = None, to_status_id: str | None = None) -> dict:
    """One note, the way ConnectWise takes one: flagged, optionally with time
    against it, optionally moving the status in the same action.

    Discussion and Resolution notes are the requester's to read on the portal;
    Internal ones never leave the desk. Time goes through both effort gates
    before anything is written, so a refused booking leaves no half-note.
    """
    if flag not in NOTE_FLAGS:
        raise ValueError(f"a note is Discussion, Internal or Resolution, not {flag!r}")
    body = (body or "").strip()
    if not body:
        raise ValueError("a note needs some words")
    ticket = conn.execute(
        "SELECT w.entity_id FROM ticket t JOIN work_item w USING (work_item_id)"
        " WHERE t.work_item_id = ?", (work_item_id,)).fetchone()
    if ticket is None:
        raise LookupError(f"no ticket {work_item_id!r}")

    if band_hours is not None:
        if band_hours not in BANDS:
            raise EffortRefused(f"effort is banded: one of {', '.join(f'{b:g}' for b in BANDS)} hours")
        if charge_method not in CHARGE_METHODS:
            raise EffortRefused("say how the time is charged; it is never assumed")
        ok, why = may_book_effort(conn, work_item_id)
        if not ok:
            raise EffortRefused(why)
        if not ticket["entity_id"]:
            raise EffortRefused("set the ticket's company before booking time against it")

    stamp = at.isoformat(sep=" ", timespec="minutes")
    _event(conn, work_item_id, stamp, "NOTE", actor, body, flag)
    if band_hours is not None:
        conn.execute(
            "INSERT INTO time_entry (work_item_id, entity_id, worked_on, band_hours,"
            " performed_by, entered_by, charge_method, authority_source, note)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            (work_item_id, ticket["entity_id"], at.date().isoformat(), band_hours,
             actor, actor, charge_method, "ticket note", body[:500]))
    status = None
    if to_status_id:
        status = change_status(conn, work_item_id, to_status_id, at=at, actor=actor)
    touch(conn, work_item_id, at)
    return {"flag": flag, "band_hours": band_hours, "status": status}


def update_fields(conn: sqlite3.Connection, work_item_id: str, *, at: datetime,
                  actor: str, owner: str | None = None, entity_id: str | None = None,
                  requested_by: str | None = None, impact: str | None = None,
                  urgency: str | None = None,
                  catalogue_item_id: str | None = None) -> list[str]:
    """Change the ticket's editable fields and write down every change.

    Priority is never set here. Changing impact or urgency re-runs the matrix,
    as ConnectWise's SLA matrix does, and the running clocks take the new
    priority's targets. A priority someone OVERRODE (with a named role and a
    reason, 005) is not undone by a field edit: the override stands and only
    the axes are recorded.
    """
    from .tickets import compute_priority

    row = conn.execute(
        "SELECT t.*, w.entity_id FROM ticket t JOIN work_item w USING (work_item_id)"
        " WHERE t.work_item_id = ?", (work_item_id,)).fetchone()
    if row is None:
        raise LookupError(f"no ticket {work_item_id!r}")
    stamp = at.isoformat(sep=" ", timespec="minutes")
    changed: list[str] = []

    def norm(v):
        v = (v or "").strip()
        return v or None

    if owner is not None and norm(owner) != row["owner"]:
        conn.execute("UPDATE ticket SET owner = ? WHERE work_item_id = ?",
                     (norm(owner), work_item_id))
        changed.append(f"owner {row['owner'] or '-'} -> {norm(owner) or '-'}")
    if requested_by is not None and norm(requested_by) != row["requested_by"]:
        conn.execute("UPDATE ticket SET requested_by = ? WHERE work_item_id = ?",
                     (norm(requested_by), work_item_id))
        changed.append(f"contact {row['requested_by'] or '-'} -> {norm(requested_by) or '-'}")
    if entity_id and entity_id != row["entity_id"]:
        if conn.execute("SELECT 1 FROM entity WHERE entity_id = ?", (entity_id,)).fetchone() is None:
            raise LookupError(f"no company {entity_id!r}")
        conn.execute("UPDATE work_item SET entity_id = ? WHERE work_item_id = ?",
                     (entity_id, work_item_id))
        changed.append(f"company {row['entity_id'] or '-'} -> {entity_id}")

    item_changed = False
    if catalogue_item_id is not None and (catalogue_item_id or None) != row["catalogue_item_id"]:
        if catalogue_item_id and conn.execute(
                "SELECT 1 FROM catalogue_item WHERE catalogue_item_id = ?",
                (catalogue_item_id,)).fetchone() is None:
            raise LookupError(f"no catalogue item {catalogue_item_id!r}")
        conn.execute("UPDATE ticket SET catalogue_item_id = ? WHERE work_item_id = ?",
                     (catalogue_item_id or None, work_item_id))
        changed.append(f"type/subtype/item {row['catalogue_item_id'] or '-'} -> "
                       f"{catalogue_item_id or '-'}")
        item_changed = True

    new_i = impact or row["impact"]
    new_u = urgency or row["urgency"]
    axes_changed = (new_i, new_u) != (row["impact"], row["urgency"])
    if axes_changed:
        conn.execute("UPDATE ticket SET impact = ?, urgency = ? WHERE work_item_id = ?",
                     (new_i, new_u, work_item_id))
        changed.append(f"impact/urgency {row['impact']}/{row['urgency']} -> {new_i}/{new_u}")
    if (axes_changed or item_changed) and row["priority_source"] != "OVERRIDE":
        item = conn.execute(
            "SELECT i.min_priority, i.clinical_impact FROM ticket t JOIN catalogue_item i"
            " ON i.catalogue_item_id = t.catalogue_item_id WHERE t.work_item_id = ?",
            (work_item_id,)).fetchone()
        priority, source = compute_priority(
            new_i, new_u, min_priority=item["min_priority"] if item else None,
            clinical_impact=item["clinical_impact"] if item else 0)
        if priority != row["priority"]:
            conn.execute("UPDATE ticket SET priority = ?, priority_source = ?"
                         " WHERE work_item_id = ?", (priority, source, work_item_id))
            changed.append(f"priority {row['priority']} -> {priority} ({source})")
            for target in conn.execute(
                    "SELECT clock, target_minutes FROM sla_target"
                    " WHERE board_id = ? AND priority = ?", (row["board_id"], priority)):
                conn.execute(
                    "UPDATE ticket_clock SET target_minutes = ? WHERE work_item_id = ?"
                    " AND clock = ? AND stopped_at IS NULL",
                    (target["target_minutes"], work_item_id, target["clock"]))

    if changed:
        _event(conn, work_item_id, stamp, "UPDATED", actor, "; ".join(changed))
        touch(conn, work_item_id, at)
    return changed

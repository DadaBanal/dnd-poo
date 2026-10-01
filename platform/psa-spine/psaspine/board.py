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

from . import clocks, contacts, itil

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
    ticket = conn.execute("SELECT board_id, priority, record_type FROM ticket"
                          " WHERE work_item_id = ?", (work_item_id,)).fetchone()
    if ticket is None:
        raise LookupError(f"no ticket {work_item_id!r}")

    started: list[int] = []
    for target in itil.targets(conn, ticket["board_id"], ticket["record_type"],
                               ticket["priority"]):
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
    itil.check_status_move(conn, ticket, new)      # a change goes only where it is authorised

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
    from . import outbox, workflow
    workflow.fire(conn, work_item_id, "ON_STATUS_CHANGE", at=at)
    merged = conn.execute("SELECT merged_into FROM ticket WHERE work_item_id = ?",
                          (work_item_id,)).fetchone()[0]
    # 058: the status's own email, when the board has turned it on. A merge
    # says nothing; a status the ticket was already in is no change.
    told = (not merged and to_status_id != ticket["board_status_id"]
            and outbox.queue_status(conn, work_item_id, to_status_id, at=at, actor=actor))
    if new["is_closed"]:
        # Children close with their parent (030). A child has no children, so
        # this goes one level and stops.
        from . import family
        family.close_with_parent(conn, work_item_id, at=at, actor=actor)
        if not merged and not told:
            outbox.queue_requester(conn, work_item_id, "CLOSED", at=at)   # a merge says nothing
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
            " authority_source, loop_reply_id, actual_hours, hours_deduct, billable_option,"
            " entry_status) VALUES (?,?,?,?,?,?,?,?,?,?,?,0,'NO_DEFAULT','OPEN')",
            (work_item_id, book_entity, at.date().isoformat(), band_hours,
             performed_by or sent_by, entered_by or sent_by,
             1 if counts_to_capacity else 0, charge_method, authority_source,
             loop_reply_id, band_hours))

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
# for — the reference PSA's email connector does the same with a "catch-all" company.
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
    - the contact, when the requester's address is exactly one active contact,
      and that contact's company if intake named none;
    - a company: the catch-all if intake could not tell;
    - the SLA clocks the board's targets call for, on the board's calendar,
      started at the moment the ticket was opened. A board that is not set up
      starts none, and the board view says so.
    """
    ticket = conn.execute(
        "SELECT t.board_id, t.board_status_id, t.opened_at, t.contact_id,"
        "       t.requested_by, t.owner, t.catalogue_item_id, b.calendar_id, b.auto_assign"
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

    contact_id = ticket["contact_id"]
    if contact_id is None:
        person = contacts.resolve(conn, ticket["requested_by"])
        if person is not None:
            contact_id = person["contact_id"]
            conn.execute("UPDATE ticket SET contact_id = ? WHERE work_item_id = ?",
                         (contact_id, work_item_id))
            conn.execute("UPDATE work_item SET entity_id = ? WHERE work_item_id = ?"
                         " AND entity_id IS NULL", (person["entity_id"], work_item_id))
        else:
            # No one person: the sender's domain may still name one company.
            company = contacts.company_for_domain(conn, ticket["requested_by"])
            if company:
                conn.execute("UPDATE work_item SET entity_id = ? WHERE work_item_id = ?"
                             " AND entity_id IS NULL", (company, work_item_id))

    conn.execute("UPDATE work_item SET entity_id = ? WHERE work_item_id = ?"
                 " AND entity_id IS NULL", (UNKNOWN_ENTITY, work_item_id))

    started: list[int] = []
    if ticket["calendar_id"]:
        opened = clocks.parse_instant(ticket["opened_at"])
        started = open_clocks(conn, work_item_id, at=opened,
                              calendar_id=ticket["calendar_id"])

    # 057: auto-assign. A ticket that arrives with an owner keeps it.
    assigned = None
    if not ticket["owner"]:
        assigned = auto_assignee(conn, ticket["board_id"], ticket["catalogue_item_id"])
        if assigned:
            from . import outbox
            stamp = at.isoformat(sep=" ", timespec="minutes")
            conn.execute("UPDATE ticket SET owner = ? WHERE work_item_id = ?", (assigned, work_item_id))
            _event(conn, work_item_id, stamp, "ASSIGN", "auto-assign", f"owner - -> {assigned} (the board's auto-assign)")
            outbox.queue_owner(conn, work_item_id, at=at, actor="auto-assign")
    touch(conn, work_item_id, at)
    return {"work_item_id": work_item_id, "board_status_id": landed,
            "contact_id": contact_id, "clocks_started": len(started), "owner": assigned}


AUTO_ASSIGN_MODES = {"OFF": "Nobody: the queue is worked by hand",
                     "LEAST_LOADED": "The working member with the fewest open tickets on the board",
                     "TEAM_LEADER": "The default team's leader"}


def _working_members(conn: sqlite3.Connection, board_id: str) -> list[str]:
    """Who may take work on the board: WORK or ADMIN, and not a deactivated member."""
    return [r["member"] for r in conn.execute(
        "SELECT bm.member FROM board_member bm LEFT JOIN member m ON LOWER(m.member) = LOWER(bm.member)"
        " WHERE bm.board_id = ? AND bm.access IN ('WORK', 'ADMIN') AND m.inactive_from IS NULL ORDER BY bm.member",
        (board_id,))]


def auto_assignee(conn: sqlite3.Connection, board_id: str, catalogue_item_id: str | None) -> str | None:
    """057: who a new unowned ticket goes to. A rule for its Subtype > Item pair
    names the member, if they still work the board; else the board's mode. A
    board with no mode (or OFF) assigns nobody, as it always did."""
    working = _working_members(conn, board_id)
    lower = {w.lower(): w for w in working}
    if catalogue_item_id:
        rule = conn.execute("SELECT member FROM board_auto_assign WHERE board_id = ? AND catalogue_item_id = ?",
                            (board_id, catalogue_item_id)).fetchone()
        if rule and rule["member"].lower() in lower:
            return lower[rule["member"].lower()]
    mode = conn.execute("SELECT auto_assign FROM board WHERE board_id = ?", (board_id,)).fetchone()
    mode = mode["auto_assign"] if mode else None
    if mode == "LEAST_LOADED" and working:
        load = {r["owner"].lower(): r["n"] for r in conn.execute(
            "SELECT LOWER(owner) AS owner, COUNT(*) AS n FROM ticket WHERE board_id = ? AND owner IS NOT NULL"
            " AND state NOT IN ('RESOLVED', 'CLOSED', 'CANCELLED') GROUP BY LOWER(owner)", (board_id,))}
        return min(working, key=lambda m: (load.get(m.lower(), 0), m.lower()))
    if mode == "TEAM_LEADER":
        team = conn.execute("SELECT team_leader FROM board_team WHERE board_id = ? AND is_default = 1", (board_id,)).fetchone()
        if team and team["team_leader"] and team["team_leader"].lower() in lower:
            return lower[team["team_leader"].lower()]
    return None


def set_auto_assign(conn: sqlite3.Connection, board_id: str, mode: str, *, at: datetime, actor: str) -> None:
    from . import db
    if mode not in AUTO_ASSIGN_MODES:
        raise ValueError("no such auto-assign mode")
    conn.execute("UPDATE board SET auto_assign = ? WHERE board_id = ?", (mode, board_id))
    db.audit(conn, at=at.isoformat(sep=" ", timespec="minutes"), actor=actor, action="BOARD_CONFIG",
             subject_kind="board", subject_id=board_id, detail=f"auto-assign: {mode}")


def auto_assign_rules(conn: sqlite3.Connection, board_id: str) -> list[dict]:
    from . import setup
    labels = {c["catalogue_item_id"]: c["label"] for c in setup.catalogue_choices(conn)}
    return [{"catalogue_item_id": r["catalogue_item_id"], "member": r["member"],
             "label": labels.get(r["catalogue_item_id"], r["catalogue_item_id"])}
            for r in conn.execute("SELECT catalogue_item_id, member FROM board_auto_assign WHERE board_id = ?"
                                  " ORDER BY catalogue_item_id", (board_id,))]


def set_auto_assign_rule(conn: sqlite3.Connection, board_id: str, catalogue_item_id: str, member: str | None, *,
                         at: datetime, actor: str) -> None:
    """Name who takes a Subtype > Item pair on the board; None removes the rule."""
    from . import db
    if not conn.execute("SELECT 1 FROM catalogue_item WHERE catalogue_item_id = ?", (catalogue_item_id or "",)).fetchone():
        raise ValueError("no such Subtype > Item pair")
    conn.execute("DELETE FROM board_auto_assign WHERE board_id = ? AND catalogue_item_id = ?", (board_id, catalogue_item_id))
    m = (member or "").strip()
    if m:
        lower = {w.lower(): w for w in _working_members(conn, board_id)}
        if m.lower() not in lower:
            raise ValueError(f"{m} does not work this board")
        conn.execute("INSERT INTO board_auto_assign (board_id, catalogue_item_id, member) VALUES (?,?,?)",
                     (board_id, catalogue_item_id, lower[m.lower()]))
    db.audit(conn, at=at.isoformat(sep=" ", timespec="minutes"), actor=actor, action="BOARD_CONFIG",
             subject_kind="board", subject_id=board_id,
             detail=f"auto-assign rule {catalogue_item_id}: " + (lower[m.lower()] if m else "removed"))


def move(conn: sqlite3.Connection, work_item_id: str, to_board_id: str, *,
         at: datetime, actor: str, owner: str | None = None,
         reason: str = "moved", record_type: str | None = None) -> dict:
    """Move a ticket to another board. One ticket, one id, its clocks intact.

    The reference PSA documents that Auto Assign does not follow a ticket moved from
    another board (§5.2 of the build scope); cross-board handover on one id is
    the thing this desk must do better, so the move keeps the ticket's clocks
    running and lands it on the new board's status for the same SLA milestone.
    """
    ticket = conn.execute(
        "SELECT t.board_id, t.owner, t.record_type, s.escalation_status FROM ticket t"
        "  LEFT JOIN board_status s ON s.board_status_id = t.board_status_id"
        " WHERE t.work_item_id = ?", (work_item_id,)).fetchone()
    if ticket is None:
        raise LookupError(f"no ticket {work_item_id!r}")
    if ticket["board_id"] == to_board_id:
        raise NotOnThisBoard(f"{work_item_id} is already on {to_board_id}")
    if conn.execute("SELECT 1 FROM board WHERE board_id = ?",
                    (to_board_id,)).fetchone() is None:
        raise LookupError(f"no board {to_board_id!r}")
    if record_type and record_type != ticket["record_type"]:
        # Moving to a board of another kind usually means another Type too
        # (an incident found to need a change): both in one step, checked
        # against the destination.
        if not itil.accepts(conn, to_board_id, record_type):
            raise NotOnThisBoard(f"{to_board_id} does not take a "
                                 f"{itil.LABEL.get(record_type, record_type).lower()}")
        basis = conn.execute("SELECT contract_basis FROM work_item WHERE work_item_id = ?",
                             (work_item_id,)).fetchone()[0]
        conn.execute("UPDATE ticket SET record_type = ?, path = ?,"
                     " change_type = CASE WHEN ? = 'CHANGE' THEN COALESCE(change_type, 'NORMAL')"
                     " ELSE change_type END WHERE work_item_id = ?",
                     (record_type, itil.derive_path(record_type, basis), record_type,
                      work_item_id))
        reason += f"; Type {itil.LABEL.get(ticket['record_type'], '-')} -> {itil.LABEL[record_type]}"
    elif not itil.accepts(conn, to_board_id, ticket["record_type"]):
        raise NotOnThisBoard(
            f"{to_board_id} does not take a {itil.LABEL[ticket['record_type']].lower()}. "
            "Change the ticket's record type first, or move it to a board that takes it.")

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
    from . import outbox, workflow
    if owner and owner != ticket["owner"]:
        outbox.queue_owner(conn, work_item_id, at=at, actor=actor)
        outbox.queue_pickup(conn, work_item_id, at=at, actor=actor)
    workflow.fire(conn, work_item_id, "ON_HANDOVER", at=at)
    return {"work_item_id": work_item_id, "board_id": to_board_id,
            "board_status_id": landed}


NOTE_FLAGS = ("DISCUSSION", "INTERNAL", "RESOLUTION")
CHARGE_METHODS = ("INCLUDED_IN_MONTHLY_FEE", "CAPACITY_UPLIFT", "SEPARATE_CHARGE",
                  "PASS_THROUGH", "NON_CHARGEABLE")
# The bands effort is recorded in (003_delivery: time_entry.band_hours). Since
# 033 a band is DERIVED from the actual hours Dada PSA-style time entry
# records: the smallest band the hours fit in. §5.2's arithmetic stays in bands.
BANDS = (0.5, 2, 4, 8, 20)
# The reference PSA's TimeEntry.billableOption (the record's model, VERIFIED
# 9 Sep 2026 from its OpenAPI schema). NO_DEFAULT: the agreement decides.
BILL_OPTIONS = ("BILLABLE", "DO_NOT_BILL", "NO_CHARGE", "NO_DEFAULT")
# Time is kept to the quarter hour. INFERRED: the reference PSA rounds time entries
# by a per-company setting; a quarter hour is the usual choice and is what the
# desk applies. Half up, so 0.13 h is a quarter, never nothing.
ROUND_HOURS = 0.25
MAX_HOURS = BANDS[-1]

# The starter work roles and work types, as data: Setup › Time edits them.
# The reference PSA ships its own list; these are the ones a hospital IT desk uses.
STARTER_WORK_ROLES = (("TECHNICIAN", "Technician"), ("ENGINEER", "Engineer"),
                      ("SERVICE_MANAGER", "Service manager"), ("ON_CALL", "On-call"))
STARTER_WORK_TYPES = (("REGULAR", "Regular", "BILLABLE"), ("REMOTE", "Remote", "BILLABLE"),
                      ("ON_SITE", "On-site", "BILLABLE"), ("AFTER_HOURS", "After hours", "BILLABLE"),
                      ("INTERNAL", "Internal", "DO_NOT_BILL"))


def ensure_time_vocabulary(conn: sqlite3.Connection) -> None:
    """Seed the starter work roles and types once; never overwrite an edit."""
    for n, (rid, name) in enumerate(STARTER_WORK_ROLES):
        conn.execute("INSERT OR IGNORE INTO work_role (work_role_id, name, sort_order)"
                     " VALUES (?,?,?)", (rid, name, n))
    for n, (tid, name, bill) in enumerate(STARTER_WORK_TYPES):
        conn.execute("INSERT OR IGNORE INTO work_type (work_type_id, name, bill_time, sort_order)"
                     " VALUES (?,?,?,?)", (tid, name, bill, n))


def work_roles(conn: sqlite3.Connection, *, all_rows: bool = False) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM work_role" + ("" if all_rows else " WHERE inactive = 0")
                        + " ORDER BY sort_order, name").fetchall()


def work_types(conn: sqlite3.Connection, *, all_rows: bool = False) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM work_type" + ("" if all_rows else " WHERE inactive = 0")
                        + " ORDER BY sort_order, name").fetchall()


def time_defaults(conn: sqlite3.Connection, *, work_item_id: str | None = None,
                  board_id: str | None = None) -> dict:
    """The work role and type a time entry starts with: the board's own
    (Board.workRole / workType in Dada PSA, Setup › the board), else the
    first active of each in Setup › Time. Either may be None when nothing is
    set up at all."""
    ensure_time_vocabulary(conn)
    if work_item_id and not board_id:
        row = conn.execute("SELECT board_id FROM ticket WHERE work_item_id = ?", (work_item_id,)).fetchone()
        board_id = row["board_id"] if row else None
    board = conn.execute("SELECT default_work_role_id, default_work_type_id FROM board WHERE board_id = ?",
                         (board_id or "",)).fetchone()
    out = {}
    for key, table in (("work_role_id", "work_role"), ("work_type_id", "work_type")):
        chosen = board[f"default_{key}"] if board else None
        if chosen and conn.execute(f"SELECT 1 FROM {table} WHERE {key} = ? AND inactive = 0",
                                   (chosen,)).fetchone():
            out[key] = chosen
            continue
        first = conn.execute(f"SELECT {key} FROM {table} WHERE inactive = 0 ORDER BY sort_order, name LIMIT 1").fetchone()
        out[key] = first[0] if first else None
    return out


def band_for(hours: float) -> float:
    """The smallest band the hours fit in; over the largest band is refused,
    because a day's work is one entry and a week's work is several."""
    for b in BANDS:
        if hours <= b + 1e-9:
            return b
    raise EffortRefused(f"{hours:g} h is more than one entry holds ({MAX_HOURS:g} h); "
                        "enter one per day worked")


def _round_hours(hours: float) -> float:
    steps = int(hours / ROUND_HOURS + 0.5 + 1e-9)
    return steps * ROUND_HOURS


def _parse_when(value, label: str) -> datetime:
    if isinstance(value, datetime):
        return value
    text = (value or "").strip().replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    raise EffortRefused(f"{label} is not a date and time (YYYY-MM-DD HH:MM)")


def resolve_hours(*, actual_hours=None, time_start=None, time_end=None,
                  hours_deduct=None) -> dict:
    """Dada PSA's rule: start and end, OR actual hours, never both. Hours
    are end minus start minus the deduction, rounded to the quarter hour, and
    must come out above zero. Returns what to store."""
    deduct = float(hours_deduct or 0)
    if deduct < 0:
        raise EffortRefused("a deduction cannot be negative")
    has_span = bool(time_start) or bool(time_end)
    has_actual = actual_hours not in (None, "", 0, 0.0) if not isinstance(actual_hours, str) \
        else bool(actual_hours.strip())
    if has_span and has_actual:
        raise EffortRefused("enter a start and end time, or the actual hours, not both")
    if has_span:
        if not (time_start and time_end):
            raise EffortRefused("a start time needs an end time, and the other way round")
        start, end = _parse_when(time_start, "start"), _parse_when(time_end, "end")
        if end <= start:
            raise EffortRefused("the end time is not after the start time")
        raw = (end - start).total_seconds() / 3600 - deduct
        start_text, end_text = start.isoformat(sep=" ", timespec="minutes"), \
            end.isoformat(sep=" ", timespec="minutes")
        worked_on = start.date().isoformat()
    elif has_actual:
        try:
            raw = float(actual_hours) - deduct
        except (TypeError, ValueError):
            raise EffortRefused("actual hours is a number, e.g. 1.5") from None
        start_text = end_text = worked_on = None
    else:
        raise EffortRefused("enter a start and end time, or the actual hours")
    hours = _round_hours(raw)
    if hours <= 0:
        raise EffortRefused("the time comes to nothing once the deduction is taken off")
    return {"actual_hours": hours, "hours_deduct": deduct, "time_start": start_text,
            "time_end": end_text, "worked_on": worked_on, "band_hours": band_for(hours)}


def prepare_time(conn: sqlite3.Connection, work_item_id: str, *, charge_method,
                 work_role_id=None, work_type_id=None, billable_option=None,
                 **hours_kw) -> dict:
    """Everything a time entry needs, checked before a byte is written: the
    hours (Dada PSA's rule), the charge method (never assumed), a real work
    role and type, a bill option, and the two effort gates. Returns the values
    to store; raises EffortRefused in a sentence."""
    values = resolve_hours(**hours_kw)
    if charge_method not in CHARGE_METHODS:
        raise EffortRefused("say how the time is charged; it is never assumed")
    ensure_time_vocabulary(conn)
    # The reference PSA fills the work role and type from the member's own defaults;
    # the desk's default is the first of each in Setup › Time. A named one must
    # exist and be in use.
    defaults = time_defaults(conn, work_item_id=work_item_id)
    if work_role_id:
        role = conn.execute("SELECT work_role_id FROM work_role WHERE work_role_id = ? AND inactive = 0",
                            (work_role_id,)).fetchone()
        if role is None:
            raise EffortRefused("choose a work role that is in use")
    else:
        role = {"work_role_id": defaults["work_role_id"]} if defaults["work_role_id"] else None
        if role is None:
            raise EffortRefused("no work role is set up (Setup › Time)")
    if work_type_id:
        wtype = conn.execute("SELECT work_type_id FROM work_type WHERE work_type_id = ? AND inactive = 0",
                             (work_type_id,)).fetchone()
        if wtype is None:
            raise EffortRefused("choose a work type that is in use")
    else:
        wtype = {"work_type_id": defaults["work_type_id"]} if defaults["work_type_id"] else None
        if wtype is None:
            raise EffortRefused("no work type is set up (Setup › Time)")
    bill = billable_option or "NO_DEFAULT"
    if bill not in BILL_OPTIONS:
        raise EffortRefused("the bill option is Billable, Do not bill, No charge or No default")
    ok, why = may_book_effort(conn, work_item_id)
    if not ok:
        raise EffortRefused(why)
    ticket = conn.execute(
        "SELECT w.entity_id FROM ticket t JOIN work_item w ON w.work_item_id = t.work_item_id"
        " WHERE t.work_item_id = ?", (work_item_id,)).fetchone()
    if ticket is None:
        raise LookupError(f"no ticket {work_item_id!r}")
    if not ticket["entity_id"]:
        raise EffortRefused("set the ticket's company before booking time against it")
    values.update(charge_method=charge_method, work_role_id=role["work_role_id"],
                  work_type_id=wtype["work_type_id"], billable_option=bill,
                  entity_id=ticket["entity_id"])
    return values


def add_time(conn: sqlite3.Connection, work_item_id: str, *, at: datetime, actor: str,
             charge_method, performed_by: str | None = None, worked_on: str | None = None,
             ticket_event_id: int | None = None, note: str | None = None,
             authority_source: str = "ticket time entry", counts_to_capacity: bool = True,
             values: dict | None = None, **kw) -> int:
    """One time entry, as Dada PSA records one: who, when (a start and end,
    or actual hours, less a deduction), the work role and type, the bill
    option, and the spine's own charge method. band_hours is derived. Returns
    the entry's id. `values` is prepare_time's answer when the caller checked
    first; otherwise the checks run here."""
    from . import timesheets
    v = values or prepare_time(conn, work_item_id, charge_method=charge_method, **kw)
    who = (performed_by or actor).strip()
    day = worked_on or v["worked_on"] or at.date().isoformat()
    # 046: a submitted or approved week is closed; an open week's entry joins its sheet.
    locked = timesheets.lock_reason(conn, who, day)
    if locked:
        raise EffortRefused(locked)
    sheet_id = timesheets.sheet_id_for(conn, who, day, at=at)
    cur = conn.execute(
        "INSERT INTO time_entry (work_item_id, entity_id, worked_on, band_hours, performed_by,"
        " entered_by, counts_to_capacity, charge_method, authority_source, note, time_start,"
        " time_end, hours_deduct, actual_hours, work_role_id, work_type_id, billable_option,"
        " ticket_event_id, entry_status, timesheet_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'OPEN',?)",
        (work_item_id, v["entity_id"], day,
         v["band_hours"], who, actor, 1 if counts_to_capacity else 0, v["charge_method"],
         authority_source, (note or "")[:500] or None, v["time_start"], v["time_end"],
         v["hours_deduct"], v["actual_hours"], v["work_role_id"], v["work_type_id"],
         v["billable_option"], ticket_event_id, sheet_id))
    stamp = at.isoformat(sep=" ", timespec="minutes")
    span = (f"{v['time_start'][11:]}–{v['time_end'][11:]}" if v["time_start"] else "actual")
    _event(conn, work_item_id, stamp, "TIME", actor,
           f"{v['actual_hours']:g} h ({span}"
           + (f", less {v['hours_deduct']:g} h" if v["hours_deduct"] else "")
           + f") by {who}, {v['work_role_id'].lower().replace('_', ' ')} · "
           f"{v['work_type_id'].lower().replace('_', ' ')} · {v['billable_option'].lower().replace('_', ' ')}"
           f" · band {v['band_hours']:g} h")
    touch(conn, work_item_id, at)
    return cur.lastrowid


def _event(conn, work_item_id, stamp, kind, actor, detail, flag=None):
    """One row of the ticket's history. Returns its id."""
    return conn.execute(
        "INSERT INTO ticket_event (work_item_id, occurred_at, kind, actor, detail,"
        " note_flag) VALUES (?,?,?,?,?,?)",
        (work_item_id, stamp, kind, actor, detail, flag)).lastrowid


def add_note(conn: sqlite3.Connection, work_item_id: str, *, body: str, flag: str,
             actor: str, at: datetime, band_hours: float | None = None,
             charge_method: str | None = None, to_status_id: str | None = None,
             resolution: bool = False, time: dict | None = None,
             notify_requester: bool = True) -> dict:
    """One note, the way Dada PSA takes one: flagged, optionally with time
    against it, optionally moving the status in the same action.
    `notify_requester` is Dada PSA's "Contact" tick on the note: a
    Discussion note emails the requester unless the technician unticks it.

    Discussion and Resolution notes are the requester's to read on the portal;
    Internal ones never leave the desk. Time is Dada PSA's time entry
    (`time`: actual_hours or time_start/time_end, hours_deduct, work_role_id,
    work_type_id, billable_option, performed_by); `band_hours` is the older
    spelling and means actual hours. Every check runs before anything is
    written, so a refused booking leaves no half-note.
    """
    if flag not in NOTE_FLAGS:
        raise ValueError(f"a note is Discussion, Internal or Resolution, not {flag!r}")
    body = (body or "").strip()
    if not body:
        raise ValueError("a note needs some words")
    ticket = conn.execute(
        "SELECT w.entity_id FROM ticket t JOIN work_item w ON w.work_item_id = t.work_item_id"
        " WHERE t.work_item_id = ?", (work_item_id,)).fetchone()
    if ticket is None:
        raise LookupError(f"no ticket {work_item_id!r}")

    time = dict(time or {})
    if band_hours is not None and not time:
        time["actual_hours"] = band_hours
    prepared = None
    if time:
        performed_by = time.pop("performed_by", None) or actor
        prepared = prepare_time(conn, work_item_id, charge_method=charge_method, **time)
        prepared["performed_by"] = performed_by

    stamp = at.isoformat(sep=" ", timespec="minutes")
    event_id = _event(conn, work_item_id, stamp, "NOTE", actor, body, flag)
    from . import paging
    paging.note_by(conn, work_item_id, actor, at=at)              # 050: a note answers an open page
    if resolution and flag != "RESOLUTION":
        # Dada PSA's second flag on one note (025): who reads it is still
        # the note's own flag; an Internal resolution stays internal.
        conn.execute("UPDATE ticket_event SET is_resolution = 1 WHERE ticket_event_id = ?",
                     (event_id,))
    # A fulfiller has written: the requester's reply has been seen.
    conn.execute("UPDATE ticket SET customer_updated = 0 WHERE work_item_id = ?",
                 (work_item_id,))
    booked = None
    if prepared is not None:
        add_time(conn, work_item_id, at=at, actor=actor, charge_method=prepared["charge_method"],
                 performed_by=prepared.pop("performed_by"), ticket_event_id=event_id, note=body,
                 authority_source="ticket note", values=prepared)
        booked = prepared["band_hours"]
    status = None
    if to_status_id:
        status = change_status(conn, work_item_id, to_status_id, at=at, actor=actor)
    touch(conn, work_item_id, at)
    from . import workflow
    workflow.fire(conn, work_item_id, "ON_NOTE_ADDED", at=at)
    if flag != "INTERNAL" and notify_requester:
        # The requester can read this note on the portal: tell them it is there.
        from . import outbox
        outbox.queue_requester(conn, work_item_id, "UPDATED", at=at)
    return {"flag": flag, "band_hours": booked, "actual_hours": prepared["actual_hours"] if prepared else None,
            "status": status}


def update_fields(conn: sqlite3.Connection, work_item_id: str, *, at: datetime,
                  actor: str, owner: str | None = None, entity_id: str | None = None,
                  requested_by: str | None = None, impact: str | None = None,
                  urgency: str | None = None,
                  catalogue_item_id: str | None = None,
                  record_type: str | None = None, change_type: str | None = None,
                  change_risk: str | None = None, planned_start: str | None = None,
                  planned_end: str | None = None,
                  backout_plan: str | None = None,
                  priority: str | None = None, priority_reason: str | None = None) -> list[str]:
    """Change the ticket's editable fields and write down every change.

    The record type is checked against the board. If the item changes and the
    same save does not change the record type, the type follows the new item.
    The commercial path is re-derived from the type and the basis. A new item
    can raise the basis to VARIATION, never lower it: taking a ticket off the
    variation path is a commercial decision, not a field edit.

    Priority is never set here. Changing impact or urgency re-runs the matrix,
    as Dada PSA's SLA matrix does, and the running clocks take the new
    priority's targets. A priority someone OVERRODE (with a named role and a
    reason, 005) is not undone by a field edit: the override stands and only
    the axes are recorded.
    """
    from .tickets import compute_priority

    row = conn.execute(
        "SELECT t.*, w.entity_id, w.contract_basis FROM ticket t"
        " JOIN work_item w ON w.work_item_id = t.work_item_id WHERE t.work_item_id = ?",
        (work_item_id,)).fetchone()
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
        # The resolved person follows the text: a contact that no longer matches
        # what the ticket says is cleared, never left pointing at someone else.
        person = contacts.resolve(conn, norm(requested_by))
        conn.execute("UPDATE ticket SET requested_by = ?, contact_id = ? WHERE work_item_id = ?",
                     (norm(requested_by), person["contact_id"] if person else None,
                      work_item_id))
        changed.append(f"contact {row['requested_by'] or '-'} -> {norm(requested_by) or '-'}")
        # A ticket filed under the catch-all takes the contact's company, unless
        # the same save names a different company of its own.
        if (person is not None and row["entity_id"] in (None, UNKNOWN_ENTITY)
                and entity_id in (None, "", row["entity_id"])):
            entity_id = person["entity_id"]
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

    # ------------------------------------------ record type and the path
    new_rt = row["record_type"]
    asked_rt = (record_type or None) if record_type is not None else row["record_type"]
    if asked_rt != row["record_type"]:
        new_rt = asked_rt
    elif item_changed and catalogue_item_id:
        from_item = itil.of_item(conn, conn.execute(
            "SELECT * FROM catalogue_item WHERE catalogue_item_id = ?",
            (catalogue_item_id,)).fetchone())
        if from_item and itil.accepts(conn, row["board_id"], from_item):
            new_rt = from_item
    rt_changed = new_rt != row["record_type"]
    if rt_changed:
        if new_rt is not None and new_rt not in itil.RECORD_TYPES:
            raise itil.NotAccepted(f"unknown record type {new_rt!r}")
        if not itil.accepts(conn, row["board_id"], new_rt):
            raise itil.NotAccepted(f"this board does not take a "
                                   f"{itil.LABEL[new_rt].lower()}")
        conn.execute("UPDATE ticket SET record_type = ? WHERE work_item_id = ?",
                     (new_rt, work_item_id))
        changed.append(f"record type {itil.LABEL.get(row['record_type'], '-')} -> "
                       f"{itil.LABEL.get(new_rt, '-')}")

    basis = row["contract_basis"]
    if item_changed and catalogue_item_id:
        item_basis = conn.execute("SELECT default_contract_basis FROM catalogue_item"
                                  " WHERE catalogue_item_id = ?",
                                  (catalogue_item_id,)).fetchone()[0]
        if basis != "VARIATION" and item_basis != basis and (
                item_basis == "VARIATION" or basis == "UNKNOWN"):
            conn.execute("UPDATE work_item SET contract_basis = ?, contract_basis_raw = ?"
                         " WHERE work_item_id = ?",
                         (item_basis, f"from catalogue item {catalogue_item_id}", work_item_id))
            changed.append(f"contract basis {basis} -> {item_basis}")
            basis = item_basis
    path = itil.derive_path(new_rt, basis)
    if path != row["path"]:
        conn.execute("UPDATE ticket SET path = ? WHERE work_item_id = ?", (path, work_item_id))
        changed.append(f"commercial path {row['path']} -> {path}")

    # ------------------------------------------------------ change fields
    change = {"change_type": change_type, "change_risk": change_risk,
              "planned_start": planned_start, "planned_end": planned_end,
              "backout_plan": backout_plan}
    given = {k: norm(v) for k, v in change.items() if v is not None}
    if new_rt == "CHANGE":
        if rt_changed and not row["change_type"] and not given.get("change_type"):
            given["change_type"] = "NORMAL"          # the safe default: it needs approval
        if given.get("change_type") and given["change_type"] not in itil.CHANGE_TYPES:
            raise ValueError(f"unknown change type {given['change_type']!r}")
        if given.get("change_risk") and given["change_risk"] not in itil.RISKS:
            raise ValueError(f"unknown risk {given['change_risk']!r}")
        window = {}
        for k in ("planned_start", "planned_end"):
            v = given.get(k, row[k]) if k in given else row[k]
            if v:
                try:
                    window[k] = clocks.parse_instant(v)
                except ValueError:
                    raise ValueError(f"{k.replace('_', ' ')} is not a date and time: {v!r}")
        if len(window) == 2 and window["planned_end"] < window["planned_start"]:
            raise ValueError("the implementation window ends before it starts")
        for k, v in given.items():
            if v != row[k]:
                conn.execute(f"UPDATE ticket SET {k} = ? WHERE work_item_id = ?",
                             (v, work_item_id))
                shown = "(set)" if k == "backout_plan" and v else (v or "-")
                changed.append(f"{k.replace('_', ' ')} {'-' if k == 'backout_plan' else (row[k] or '-')}"
                               f" -> {shown}")
    elif any(given.values()):
        raise ValueError("change fields belong to a change; set the record type to Change first")

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
        computed, source = compute_priority(
            new_i, new_u, min_priority=item["min_priority"] if item else None,
            clinical_impact=item["clinical_impact"] if item else 0)
        if computed != row["priority"]:
            conn.execute("UPDATE ticket SET priority = ?, priority_source = ?"
                         " WHERE work_item_id = ?", (computed, source, work_item_id))
            changed.append(f"priority {row['priority']} -> {computed} ({source})")
    # A person sets the priority (P1-P4, with a reason), or gives it back to the
    # matrix ("MATRIX"). An override stays until it is given back: the matrix no
    # longer moves it (above).
    if priority:
        cur = conn.execute("SELECT priority, priority_source FROM ticket WHERE work_item_id = ?",
                           (work_item_id,)).fetchone()
        if priority == "MATRIX":
            if cur["priority_source"] == "OVERRIDE":
                item = conn.execute(
                    "SELECT i.min_priority, i.clinical_impact FROM ticket t JOIN catalogue_item i"
                    " ON i.catalogue_item_id = t.catalogue_item_id WHERE t.work_item_id = ?",
                    (work_item_id,)).fetchone()
                p, source = compute_priority(new_i, new_u, min_priority=item["min_priority"] if item else None,
                                             clinical_impact=item["clinical_impact"] if item else 0)
                conn.execute("UPDATE ticket SET priority = ?, priority_source = ? WHERE work_item_id = ?",
                             (p, source, work_item_id))
                changed.append(f"priority {cur['priority']} -> {p} (back to the matrix, {source})")
        elif priority in ("P1", "P2", "P3", "P4"):
            if priority != cur["priority"] or cur["priority_source"] != "OVERRIDE":
                why = " ".join(str(priority_reason or "").split())[:200]
                if not why:
                    raise ValueError("changing the priority by hand needs a reason")
                conn.execute("UPDATE ticket SET priority = ?, priority_source = 'OVERRIDE' WHERE work_item_id = ?",
                             (priority, work_item_id))
                changed.append(f"priority {cur['priority']} -> {priority} (set by {actor}: {why})")
        else:
            raise ValueError("a priority is P1, P2, P3 or P4")
    now_priority = conn.execute("SELECT priority FROM ticket WHERE work_item_id = ?",
                                (work_item_id,)).fetchone()["priority"]
    if now_priority != row["priority"] or rt_changed:
        # The running clocks take the targets for the ticket's priority and type now.
        for target in itil.targets(conn, row["board_id"], new_rt, now_priority):
            conn.execute(
                "UPDATE ticket_clock SET target_minutes = ? WHERE work_item_id = ?"
                " AND clock = ? AND stopped_at IS NULL",
                (target["target_minutes"], work_item_id, target["clock"]))

    if changed:
        _event(conn, work_item_id, stamp, "UPDATED", actor, "; ".join(changed))
        touch(conn, work_item_id, at)
        if any(c.startswith("owner ") for c in changed):
            from . import outbox, workflow
            outbox.queue_owner(conn, work_item_id, at=at, actor=actor)
            if norm(owner):
                outbox.queue_pickup(conn, work_item_id, at=at, actor=actor)   # 058: the requester hears who has it
            workflow.fire(conn, work_item_id, "ON_OWNER_CHANGE", at=at)
    return changed

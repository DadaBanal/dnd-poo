"""Dada's rule for a ticket waiting on someone outside the desk (job 03).

His words, 15 Oct 2026, are in docs/handoffs/HANDOFF-sql01-cloud-WS36-20261015-
waiting-rule.md. As built:

  * In *Awaiting approval* or *Waiting on requester* both clocks stop
    (clocks.NEVER_PAUSED is empty; board.change_status pauses them).
  * After **3 days** in the status with no answer, a reminder goes out: to the
    requester; on *Awaiting approval* to the approver as well (Dada: "it should
    go to both").
  * **3 days after the reminder**, still no answer, the ticket closes to the
    board's >Closed status, never Resolved, with the reason on the ticket and
    the reopen sentence in the email.
  * A reply by email or on the portal reopens it (intake.reopen_on_reply).

Days are calendar days, the reading stated in the handoff. The count starts
when the ticket entered the status, or at the requester's latest reply if that
is later: a reply that leaves the status unchanged is still an answer, and a
ticket is never closed "for no response" over the top of one.

Which statuses: a waiting status (NO_ESCALATION) whose name says approval, or
whose words say it waits on the requester (outbox.status_shape's WAITING).
INFERRED from the status's words, as status_shape is; the other waiting
statuses (parts, vendor, BizBox, on hold) wait on someone the desk chases, so
nothing is sent and nothing closes there, while their clocks still stop.

Run by `psaspine run-rules` (the PSA-Rules task), after the timed rules.
"""
from __future__ import annotations

import re
import sqlite3
from datetime import datetime, timedelta

from .clocks import PAUSES, parse_instant

REMIND_AFTER = timedelta(days=3)
CLOSE_AFTER = timedelta(days=3)          # counted from the reminder
APPROVAL, RESPONSE = "APPROVAL", "RESPONSE"
ACTOR = "desk:waiting-rule"
REMINDED = "WAITING_REMINDER"            # ticket_event.kind: the reminder went (or was due)
CLOSED = "WAITING_CLOSED"                # ticket_event.kind: closed for no response
REPLIES = ("INTAKE_REPLY", "PORTAL_REPLY")
_APPROVAL = re.compile(r"approv", re.I)


def waits_on(status_row) -> str | None:
    """APPROVAL, RESPONSE, or None when this status is not one the rule
    chases."""
    if status_row is None or status_row["escalation_status"] != PAUSES:
        return None
    if status_row["is_closed"] or status_row["inactive"]:
        return None
    if _APPROVAL.search(status_row["name"] or ""):
        return APPROVAL
    from .outbox import status_shape
    return RESPONSE if status_shape(status_row) == "WAITING" else None


def _stamp(at: datetime) -> str:
    return at.isoformat(sep=" ", timespec="minutes")


def _latest(conn, work_item_id: str, kinds: tuple[str, ...]) -> datetime | None:
    row = conn.execute(
        "SELECT occurred_at FROM ticket_event WHERE work_item_id = ? AND kind IN (%s)"
        " ORDER BY ticket_event_id DESC" % ",".join("?" * len(kinds)), (work_item_id, *kinds)).fetchone()
    if row is None:
        return None
    try:
        return parse_instant(row["occurred_at"])
    except ValueError:
        return None


def status_since(conn: sqlite3.Connection, work_item_id: str) -> datetime | None:
    """When the ticket entered the status it is in now: its latest status
    change or board move, else when it was opened."""
    moved = _latest(conn, work_item_id, ("STATUS_CHANGE", "ROUTED"))
    if moved is not None:
        return moved
    row = conn.execute("SELECT opened_at FROM ticket WHERE work_item_id = ?", (work_item_id,)).fetchone()
    try:
        return parse_instant(row["opened_at"]) if row and row["opened_at"] else None
    except ValueError:
        return None


def waiting_since(conn: sqlite3.Connection, work_item_id: str) -> datetime | None:
    """Where the rule's three days count from: entering the status, or the
    requester's latest reply if later."""
    since = status_since(conn, work_item_id)
    replied = _latest(conn, work_item_id, REPLIES)
    if since is None or (replied is not None and replied > since):
        return replied
    return since


def closed_status(conn: sqlite3.Connection, board_id: str) -> str | None:
    """The board's >Closed: a closed status that is not a Resolved one."""
    rows = conn.execute(
        "SELECT board_status_id, name, escalation_status FROM board_status WHERE board_id = ? AND is_closed = 1"
        " AND COALESCE(inactive, 0) = 0 ORDER BY sort_order, name", (board_id,)).fetchall()
    for r in rows:
        if (r["name"] or "").lstrip(">").strip().lower() == "closed":
            return r["board_status_id"]
    for r in rows:
        if "resolv" not in (r["name"] or "").lower():
            return r["board_status_id"]
    return None


def _approver(conn, work_item_id: str) -> str | None:
    from . import approvals
    row = approvals.pending(conn, work_item_id)
    return row["approver"] if row else approvals.approver_for(conn, work_item_id)


def remind(conn: sqlite3.Connection, work_item_id: str, waits: str, *, at: datetime, days: int) -> list[str]:
    """The day-3 reminder. Recorded on the ticket whether or not an email
    could be queued (the board's requester switch, an address), so the close
    is counted from it either way and the ticket says who was told."""
    from . import outbox
    from .board import _event
    told = []
    if outbox.queue_requester(conn, work_item_id, outbox.WAITING_REMINDER, at=at, variant=waits):
        told.append("the requester")
    if waits == APPROVAL:
        approver = _approver(conn, work_item_id)
        if approver and outbox.queue_approver(conn, work_item_id, approver, at=at, reminder=True):
            told.append(f"the approver ({approver})")
    _event(conn, work_item_id, _stamp(at), REMINDED, ACTOR,
           f"no {'approval' if waits == APPROVAL else 'response'} after {days} days: reminder "
           + (("sent to " + " and ".join(told)) if told else "due, but no email could be queued")
           + f"; the ticket closes if nothing comes in {CLOSE_AFTER.days} more days")
    return told


def close(conn: sqlite3.Connection, work_item_id: str, waits: str, *, at: datetime, days: int) -> str | None:
    """Close for no response: to >Closed, never Resolved, the reason on the
    ticket, and the requester's email saying why and how to reopen it."""
    from . import approvals, outbox
    from .board import _event, change_status
    tk = conn.execute("SELECT board_id FROM ticket WHERE work_item_id = ?", (work_item_id,)).fetchone()
    target = closed_status(conn, tk["board_id"]) if tk else None
    stamp = _stamp(at)
    what = "approval" if waits == APPROVAL else "response"
    if target is None:
        _event(conn, work_item_id, stamp, CLOSED, ACTOR,
               f"no {what} after {days} days, but the board has no >Closed status: left open")
        return None
    pending = approvals.pending(conn, work_item_id)
    if pending is not None:
        # The question is closed with the ticket, so it leaves the approver's
        # list; no status is returned to, the ticket is closing.
        from . import db
        conn.execute("UPDATE approval SET status = 'WITHDRAWN', decided_at = ?, decided_by = ? WHERE approval_id = ?",
                     (stamp, ACTOR, pending["approval_id"]))
        db.audit(conn, at=stamp, actor=ACTOR, action="APPROVAL", subject_kind="approval",
                 subject_id=str(pending["approval_id"]), detail=f"withdrawn on {work_item_id}: closed for no {what}")
    change_status(conn, work_item_id, target, at=at, actor=ACTOR, quiet=True)
    _event(conn, work_item_id, stamp, CLOSED, ACTOR,
           f"closed: no {what} after {days} days (reminder sent {REMIND_AFTER.days} days in); "
           "a reply by email or on the portal reopens it")
    outbox.queue_requester(conn, work_item_id, outbox.CLOSED_NO_RESPONSE, at=at, variant=waits)
    return target


def settle_pauses(conn: sqlite3.Connection, *, at: datetime) -> int:
    """A clock still running on a ticket that sits in a waiting status gets
    the pause it would have had, from when the ticket entered that status.
    For the tickets parked before this rule (PMC-001527, respond running in
    Awaiting approval): no status move is needed to stop the false breach.
    Idempotent: a clock with an open pause is left alone."""
    from .board import _event
    rows = conn.execute(
        "SELECT c.clock_id, c.clock, c.started_at, t.work_item_id, t.board_status_id FROM ticket_clock c"
        "  JOIN ticket t ON t.work_item_id = c.work_item_id"
        "  JOIN board_status s ON s.board_status_id = t.board_status_id"
        " WHERE c.stopped_at IS NULL AND s.escalation_status = ? AND t.closed_at IS NULL"
        "   AND NOT EXISTS (SELECT 1 FROM ticket_clock_pause p WHERE p.clock_id = c.clock_id"
        "                   AND p.resumed_at IS NULL)", (PAUSES,)).fetchall()
    done: dict[str, list[str]] = {}
    for r in rows:
        since = status_since(conn, r["work_item_id"]) or at
        mark = max(_stamp(since), r["started_at"])
        conn.execute("INSERT INTO ticket_clock_pause (clock_id, paused_at, board_status_id) VALUES (?,?,?)",
                     (r["clock_id"], mark, r["board_status_id"]))
        done.setdefault(r["work_item_id"], []).append(r["clock"])
    for wid, names in done.items():
        _event(conn, wid, _stamp(at), "WAITING_PAUSE", ACTOR,
               f"clocks paused from when the ticket entered its waiting status: {', '.join(sorted(names))}")
    return sum(len(v) for v in done.values())


def sweep(conn: sqlite3.Connection, *, at: datetime) -> dict:
    """Every open ticket in a status the rule chases: remind at day 3, close
    3 days after the reminder. Each ticket on its own savepoint, so one bad
    row is counted and the rest still run."""
    counts = {"paused": settle_pauses(conn, at=at), "waiting": 0, "reminded": 0, "closed": 0, "errors": 0}
    rows = conn.execute(
        "SELECT t.work_item_id, s.name, s.customer_description, s.escalation_status, s.is_closed, s.inactive"
        "  FROM ticket t JOIN board_status s ON s.board_status_id = t.board_status_id"
        " WHERE t.closed_at IS NULL AND t.state NOT IN ('CLOSED','CANCELLED') AND s.escalation_status = ?"
        "   AND t.merged_into IS NULL ORDER BY t.work_item_id", (PAUSES,)).fetchall()
    for r in rows:
        waits = waits_on(r)
        if waits is None:
            continue
        wid = r["work_item_id"]
        counts["waiting"] += 1
        conn.execute("SAVEPOINT waiting_rule")
        try:
            since = waiting_since(conn, wid)
            if since is not None:
                reminded = _latest(conn, wid, (REMINDED,))
                if reminded is not None and reminded < since:
                    reminded = None                       # a reminder from an earlier wait
                if reminded is None and at - since >= REMIND_AFTER:
                    remind(conn, wid, waits, at=at, days=(at - since).days)
                    counts["reminded"] += 1
                elif reminded is not None and at - reminded >= CLOSE_AFTER:
                    if close(conn, wid, waits, at=at, days=(at - since).days):
                        counts["closed"] += 1
            conn.execute("RELEASE waiting_rule")
        except Exception as exc:                          # noqa: BLE001 - counted, and the rest still run
            conn.execute("ROLLBACK TO waiting_rule")
            conn.execute("RELEASE waiting_rule")
            from . import db
            db.audit(conn, at=_stamp(at), actor=ACTOR, action="WAITING_RULE", subject_kind="ticket",
                     subject_id=wid, detail=f"{type(exc).__name__}: {exc}"[:500])
            counts["errors"] += 1
    conn.commit()
    return counts

"""Running the rules: 008 decides, this acts.

`rules.evaluate` decides whether an event fires and records the decision. This
module is the caller its docstring asks for. It is ConnectWise's workflow rules
(VERIFIED 23 Sep 2026, docs.connectwise.com/ConnectWise_Documentation/090/020/
070/130, archived 2025-08-30), with three things done better:

  * **At the moment, not on a sweep.** ConnectWise evaluates rules at most every
    ten minutes. Here every engine seam fires its event as it happens: a ticket
    created, a status changed, a note added, an owner changed, a board move.
    Only time-based events (ON_SCHEDULE, ON_SLA_THRESHOLD) wait for `sweep`,
    which the server runs every minute.
  * **Age is SLA time.** `sla_percent_used` is the largest share of a running
    clock's target used so far, from clocks.state_of, so it follows the board's
    calendar and time in a waiting status does not count. ConnectWise ages
    tickets the same way.
  * **Every action says which rule did it.** Each action writes a ticket event
    naming the workflow and event, and every NOTIFY or ESCALATE goes to the
    `notification` outbox with the ticket token in its subject.

Test before activate, deactivate on edit (024): `test_event` records how many
open tickets match now; `activate` refuses a rule with an untested event, and
the Setup screen deactivates a rule whenever it is changed.

A rule's own actions never fire further rules. A status set by a rule does not
trigger ON_STATUS_CHANGE again: that is how two rules page each other for ever.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime

from . import clocks, rules

# The vocabulary a TICKET condition may read. Rows in workflow_trigger, written
# by ensure_vocabulary; ticket_row must carry every field listed here.
TICKET_FIELDS = (
    ("TICKET.PRIORITY", "priority", "Priority", "CODE"),
    ("TICKET.RECORD_TYPE", "record_type", "Type", "CODE"),
    ("TICKET.STATUS", "status_name", "Status", "TEXT"),
    ("TICKET.ESCALATION", "escalation_status", "Status milestone", "CODE"),
    ("TICKET.OWNER", "owner", "Owner", "TEXT"),
    ("TICKET.BOARD", "board_id", "Board", "CODE"),
    ("TICKET.COMPANY", "entity_id", "Company", "CODE"),
    ("TICKET.SOURCE", "intake_source", "Source", "CODE"),
    ("TICKET.CUSTOMER_UPDATED", "customer_updated", "Customer updated", "BOOLEAN"),
    ("TICKET.AGE_MINUTES", "age_minutes", "Minutes since opened", "NUMBER"),
    ("TICKET.IDLE_MINUTES", "idle_minutes", "Minutes since last update", "NUMBER"),
    ("TICKET.SLA_PERCENT", "sla_percent_used", "SLA used (%)", "NUMBER"),
    ("TICKET.CHANGE_TYPE", "change_type", "Change type", "CODE"),
)
SEAMS = ("ON_CREATE", "ON_STATUS_CHANGE", "ON_OWNER_CHANGE", "ON_NOTE_ADDED", "ON_HANDOVER")
TIMED = ("ON_SCHEDULE", "ON_SLA_THRESHOLD")

_running = False          # a rule's own actions never fire further rules


def ensure_vocabulary(conn: sqlite3.Connection) -> None:
    for trigger_id, field, name, kind in TICKET_FIELDS:
        conn.execute("INSERT OR IGNORE INTO workflow_trigger (trigger_id, table_type, field,"
                     " display_name, value_type) VALUES (?, 'TICKET', ?, ?, ?)",
                     (trigger_id, field, name, kind))


def _minutes(since: str | None, now: datetime) -> int | None:
    if not since:
        return None
    try:
        return max(0, int((now - clocks.parse_instant(since)).total_seconds() // 60))
    except (TypeError, ValueError):
        return None


def ticket_row(conn: sqlite3.Connection, work_item_id: str, *, now: datetime) -> dict | None:
    """Everything a TICKET condition may test, computed now."""
    t = conn.execute(
        "SELECT t.*, w.entity_id, w.name AS summary, s.name AS status_name,"
        "       s.escalation_status"
        "  FROM ticket t JOIN work_item w ON w.work_item_id = t.work_item_id"
        "  LEFT JOIN board_status s ON s.board_status_id = t.board_status_id"
        " WHERE t.work_item_id = ?", (work_item_id,)).fetchone()
    if t is None:
        return None
    row = {k: t[k] for k in t.keys()}
    row["customer_updated"] = int(t["customer_updated"] or 0)
    row["age_minutes"] = _minutes(t["opened_at"], now)
    row["idle_minutes"] = _minutes(t["updated_at"] or t["opened_at"], now)
    used = 0.0
    for c in conn.execute("SELECT clock_id FROM ticket_clock WHERE work_item_id = ?"
                          " AND stopped_at IS NULL", (work_item_id,)):
        st = clocks.state_of(conn, c["clock_id"], as_of=now)
        if st["target_minutes"]:
            used = max(used, 100.0 * st["elapsed_minutes"] / st["target_minutes"])
    row["sla_percent_used"] = round(used, 1)
    return row


def _events(conn: sqlite3.Connection, board_id: str, fires_on: tuple) -> list[sqlite3.Row]:
    marks = ",".join("?" * len(fires_on))
    return conn.execute(
        "SELECT e.*, w.name AS workflow_name, w.board_id AS workflow_board FROM workflow_event e"
        "  JOIN workflow w ON w.workflow_id = e.workflow_id"
        f" WHERE w.is_active = 1 AND w.table_type = 'TICKET' AND e.fires_on IN ({marks})"
        "   AND (w.board_id IS NULL OR w.board_id = ?)"
        " ORDER BY w.sort_order, w.workflow_id, e.event_id", (*fires_on, board_id)).fetchall()


def fire(conn: sqlite3.Connection, work_item_id: str, fires_on: str, *,
         at: datetime) -> list[dict]:
    """Run every active event for this seam on this ticket. Never raises into the
    caller: a broken rule is recorded as ERROR, and the ticket change stands."""
    global _running
    if _running or not conn.execute("SELECT 1 FROM workflow WHERE is_active = 1"
                                    " AND table_type = 'TICKET' LIMIT 1").fetchone():
        return []
    row = ticket_row(conn, work_item_id, now=at)
    if row is None:
        return []
    out = []
    _running = True
    try:
        for event in _events(conn, row["board_id"], (fires_on,)):
            out.append(_run(conn, event, row, at=at))
    finally:
        _running = False
    return out


def sweep(conn: sqlite3.Connection, *, at: datetime) -> dict:
    """Time-based events over every open ticket. Run every minute by the server."""
    global _running
    counts = {"tickets": 0, "acted": 0, "errors": 0}
    ids = [r[0] for r in conn.execute(
        "SELECT work_item_id FROM ticket WHERE state NOT IN ('CLOSED','CANCELLED')"
        " AND closed_at IS NULL")]
    _running = True
    try:
        for wid in ids:
            row = ticket_row(conn, wid, now=at)
            events = _events(conn, row["board_id"], TIMED)
            if not events:
                continue
            counts["tickets"] += 1
            for event in events:
                r = _run(conn, event, row, at=at)
                counts["acted"] += bool(r.get("fired"))
                counts["errors"] += bool(r.get("error"))
    finally:
        _running = False
    conn.commit()
    return counts


def _run(conn, event, row, *, at: datetime) -> dict:
    """One event on one ticket, all or nothing: an action that fails halfway is
    rolled back to before the event, and the failure is what gets recorded."""
    conn.execute("SAVEPOINT workflow_event")
    try:
        result = rules.evaluate(conn, event["event_id"], row, as_of=at,
                                work_item_id=row["work_item_id"])
        for action in result["actions"]:
            _act(conn, event, action, row, at=at)
        conn.execute("RELEASE workflow_event")
        return result
    except Exception as exc:                                  # noqa: BLE001
        conn.execute("ROLLBACK TO workflow_event")
        conn.execute("RELEASE workflow_event")
        rules.record(conn, event["event_id"], row["work_item_id"], at=at,
                     outcome="ERROR", detail=f"{type(exc).__name__}: {exc}"[:500])
        return {"fired": False, "error": str(exc), "actions": []}


# ------------------------------------------------------------------ actions

def _who(conn, action, row, at) -> tuple[str | None, str | None]:
    """The person a NOTIFY or ESCALATE reaches: a named member, or a board role."""
    if action["target_member"]:
        return action["target_member"], None
    role = action["notify_role"]
    if role == "OWNER":
        return row["owner"], role
    if role == "REQUESTER":
        return row["requested_by"], role
    if role in ("ON_CALL", "DUTY_MANAGER"):
        from .board import current_oncall
        who = current_oncall(conn, row["board_id"], role, at=at)
        if who:
            return who, role
    if role == "TEAM_LEADER":
        t = conn.execute("SELECT team_leader FROM board_team WHERE board_id = ?"
                         " AND is_default = 1", (row["board_id"],)).fetchone()
        return (t["team_leader"] if t else None), role
    r = conn.execute("SELECT member FROM board_role WHERE board_id = ? AND role = ?",
                     (row["board_id"], role)).fetchone()
    return (r["member"] if r else None), role


def _act(conn, event, action, row, *, at: datetime) -> None:
    from . import board
    from .intake import subject_token
    wid = row["work_item_id"]
    by = f"workflow:{event['workflow_id']}/{event['event_id']}"
    stamp = at.isoformat(sep=" ", timespec="minutes")
    kind = action["action"]
    said = f"{event['workflow_name']}: {action['detail'] or kind.lower().replace('_', ' ')}"

    if kind == "SET_STATUS" and action["target_status_id"]:
        board.change_status(conn, wid, action["target_status_id"], at=at, actor=by)
    elif kind == "SET_BOARD" and action["target_board_id"]:
        board.move(conn, wid, action["target_board_id"], at=at, actor=by, reason=said)
    elif kind in ("ASSIGN_OWNER", "ASSIGN_TEAM"):
        owner = action["target_member"]
        if kind == "ASSIGN_TEAM" and action["target_team_id"]:
            t = conn.execute("SELECT team_leader FROM board_team WHERE team_id = ?",
                             (action["target_team_id"],)).fetchone()
            owner = t["team_leader"] if t else None
        if owner:
            board.update_fields(conn, wid, at=at, actor=by, owner=owner)
    elif kind == "ADD_NOTE":
        board._event(conn, wid, stamp, "NOTE", by, action["detail"] or said, "INTERNAL")
    elif kind in ("NOTIFY", "ESCALATE"):
        who, role = _who(conn, action, row, at)
        if not who:
            # Nobody to reach is a failure, said out loud (the 008 CHECK's point).
            raise LookupError(f"{kind.lower()} to {role or 'nobody'}: no one holds that role "
                              f"on {row['board_id']} right now")
        conn.execute(
            "INSERT INTO notification (work_item_id, event_id, recipient, recipient_role,"
            " subject, body, created_at, status) VALUES (?,?,?,?,?,?,?,'PENDING')",
            (wid, event["event_id"], who, role,
             f"{subject_token(wid)} {kind.title()}: {row.get('summary') or row['priority']}",
             said, stamp))
        board._event(conn, wid, stamp, kind, by, f"{kind.lower()} {who}"
                     + (f" ({role.replace('_', ' ').lower()})" if role else "") + f": {said}")
        return
    elif kind == "FLAG":
        conn.execute("INSERT INTO data_quality (run_id, subject_kind, subject_id, code, detail,"
                     " severity) VALUES (?,?,?,?,?,?)",
                     (by, "ticket", wid, "WORKFLOW_FLAG", said, "WARN"))
    else:
        raise LookupError(f"action {kind} is not carried out by this runner yet")
    board._event(conn, wid, stamp, "WORKFLOW", by, said)


# -------------------------------------------------------- test and activate

def test_event(conn: sqlite3.Connection, event_id: str, *, at: datetime,
               limit: int = 1000) -> dict:
    """How many open tickets this event's conditions match now (ConnectWise
    shows the count and at most 1,000 records). Records the test; acts on
    nothing."""
    ev = conn.execute("SELECT e.*, w.board_id FROM workflow_event e JOIN workflow w"
                      " ON w.workflow_id = e.workflow_id WHERE e.event_id = ?",
                      (event_id,)).fetchone()
    if ev is None:
        raise LookupError(f"no workflow event {event_id!r}")
    sql = "SELECT work_item_id FROM ticket WHERE closed_at IS NULL"
    params: list = []
    if ev["board_id"]:
        sql += " AND board_id = ?"
        params.append(ev["board_id"])
    hits = []
    for (wid,) in conn.execute(sql, params).fetchall():
        if rules.matches(conn, event_id, ticket_row(conn, wid, now=at)):
            hits.append(wid)
    conn.execute("UPDATE workflow_event SET tested_at = ?, tested_matches = ? WHERE event_id = ?",
                 (at.isoformat(sep=" ", timespec="minutes"), len(hits), event_id))
    return {"matches": len(hits), "sample": hits[:limit]}


def activate(conn: sqlite3.Connection, workflow_id: str, *, actor: str, at: datetime) -> None:
    untested = [r["event_id"] for r in conn.execute(
        "SELECT event_id FROM workflow_event WHERE workflow_id = ? AND tested_at IS NULL",
        (workflow_id,))]
    if untested:
        raise ValueError("test every event before switching the rule on: "
                         + ", ".join(untested))
    if not conn.execute("SELECT 1 FROM workflow_event WHERE workflow_id = ?",
                        (workflow_id,)).fetchone():
        raise ValueError("a rule with no events does nothing")
    from . import db
    conn.execute("UPDATE workflow SET is_active = 1 WHERE workflow_id = ?", (workflow_id,))
    db.audit(conn, at=at.isoformat(sep=" ", timespec="minutes"), actor=actor,
             action="WORKFLOW_ACTIVATE", subject_kind="workflow", subject_id=workflow_id)


def edited(conn: sqlite3.Connection, workflow_id: str) -> None:
    """A changed rule is off and untested until someone tests it again."""
    conn.execute("UPDATE workflow SET is_active = 0 WHERE workflow_id = ?", (workflow_id,))
    conn.execute("UPDATE workflow_event SET tested_at = NULL, tested_matches = NULL"
                 " WHERE workflow_id = ?", (workflow_id,))

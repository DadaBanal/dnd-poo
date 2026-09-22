"""Run the board engine end to end and narrate it.

This exists because of the record's own base rate. The Power BI collector was
fully designed on 3 September and never run. The gateway has been two clicks
away since 3 September. `Build-EvidencePack.py` does not exist. BUILT-NOT-RUN is
a live status in the register.

So the board engine is not finished when its tests pass. It is finished when it
runs, on every commit, and prints something a person at PMC can read and argue
with. That is what this does, and CI calls it.

Nothing here is seeded into a real database. It builds its own board, its own
statuses and its own ticket, walks them through a shift, and prints the
arithmetic — including the arithmetic it would have got wrong without the pause,
because that difference is the entire case for modelling pauses at all.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime

from . import board, clocks, rules

CALENDARS = (
    ("CLINICAL", "Clinical 24x7", [("00:00", "24:00")] * 7),
    ("MANILA", "Manila business hours",
     [("08:00", "17:00")] * 5 + [(None, None)] * 2),
)

STATUSES = (
    ("IT_HELP.NEW", "New", "NOT_RESPONDED", 1, 0, 1),
    ("IT_HELP.WORKING", "In progress", "RESPONDED", 0, 0, 1),
    ("IT_HELP.PARTS", "Waiting for parts", "NO_ESCALATION", 0, 0, 0),
    ("IT_HELP.DONE", "Closed", "RESOLVED", 0, 1, 0),
)

DAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")


def _fmt(minutes: int) -> str:
    return f"{minutes // 60}h {minutes % 60:02d}m"


def setup(conn: sqlite3.Connection) -> None:
    for cal_id, name, week in CALENDARS:
        cols = ", ".join(f"{d}_start, {d}_end" for d in DAYS)
        values = [v for pair in week for v in pair]
        conn.execute(
            f"INSERT OR REPLACE INTO calendar (calendar_id, name, {cols})"
            f" VALUES (?,?,{','.join('?' * 14)})", [cal_id, name, *values])

    for sid, name, esc, default, closed, effort in STATUSES:
        conn.execute(
            "INSERT OR REPLACE INTO board_status (board_status_id, board_id, name,"
            " escalation_status, is_default, is_closed, time_entry_allowed)"
            " VALUES (?,'IT_HELP',?,?,?,?,?)", (sid, name, esc, default, closed, effort))

    for clock, minutes in (("RESPOND", 60), ("RESOLVE", 240)):
        conn.execute(
            "INSERT OR REPLACE INTO sla_target (board_id, priority, clock,"
            " target_minutes, calendar, enforced)"
            " VALUES ('IT_HELP','P1',?,?, 'CLINICAL_24x7', 0)", (clock, minutes))

    conn.execute(
        "INSERT OR REPLACE INTO work_item (work_item_id, source, name, entity_id,"
        " contract_basis) VALUES ('ITO-9001','desk','Ward 3 switch stack down',"
        "'PMC','BASELINE')")
    conn.execute(
        "INSERT OR REPLACE INTO ticket (work_item_id, board_id, path, impact, urgency,"
        " priority, priority_source, requested_by, requested_at, opened_at, state)"
        " VALUES ('ITO-9001','IT_HELP','INCIDENT','I1','U1','P1','MATRIX',"
        "'Ward 3 nurse station','2026-11-16 22:10','2026-11-16 22:10','NEW')")
    conn.commit()


def run(conn: sqlite3.Connection) -> list[str]:
    """Walk one ticket through a night shift. Returns the narrative."""
    setup(conn)
    out: list[str] = []
    w = out.append

    w("PMC PSA — board engine walkthrough")
    w("=" * 68)
    w("")
    w("A P1 raised on the ward at 22:10, worked overnight, parked for parts,")
    w("and closed the next morning. Every number below is computed, not stored.")
    w("")

    board.open_clocks(conn, "ITO-9001", at=datetime(2026, 11, 16, 22, 10),
                      calendar_id="CLINICAL")
    w("22:10  Ward 3 switch stack down. Impact I1, urgency U1, so priority P1.")
    for row in conn.execute(
            "SELECT clock, target_minutes FROM ticket_clock WHERE work_item_id='ITO-9001'"
            " ORDER BY clock"):
        w(f"       clock started: {row['clock']:<8} target {_fmt(row['target_minutes'])}")
    w("")

    shift = (
        (datetime(2026, 11, 16, 22, 35), "IT_HELP.WORKING", "On-call picks it up."),
        (datetime(2026, 11, 16, 23, 40), "IT_HELP.PARTS",
         "No spare SFP on site. Parked until the supplier opens."),
        (datetime(2026, 11, 17, 8, 5), "IT_HELP.WORKING", "Part collected, back on it."),
        (datetime(2026, 11, 17, 9, 20), "IT_HELP.DONE", "Stack up, ward confirms."),
    )
    for at, status_id, note in shift:
        result = board.change_status(conn, "ITO-9001", status_id, at=at, actor="Cadano")
        moves = []
        for label, key in (("stopped", "stopped"), ("paused", "paused"), ("resumed", "resumed")):
            if result[key]:
                moves.append(f"{label} {'+'.join(result[key])}")
        w(f"{at.strftime('%H:%M')}  {result['board_status_id'].split('.')[1]:<8} "
          f"{note}")
        if moves:
            w(f"       clocks: {', '.join(moves)}")
        if not result["time_entry_allowed"]:
            allowed, why = board.may_book_effort(conn, "ITO-9001")
            w(f"       effort: refused — {why}")
    w("")

    w("What the clocks say")
    w("-" * 68)
    closed_at = datetime(2026, 11, 17, 9, 20)
    for row in conn.execute(
            "SELECT clock_id, clock FROM ticket_clock WHERE work_item_id='ITO-9001'"
            " ORDER BY clock"):
        state = clocks.state_of(conn, row["clock_id"], as_of=closed_at)
        verdict = "BREACHED" if state["breached"] else "within target"
        w(f"  {state['clock']:<8} used {_fmt(state['elapsed_minutes']):>8}"
          f"  of {_fmt(state['target_minutes']):>8}   {verdict}")

    resolve = conn.execute(
        "SELECT clock_id FROM ticket_clock WHERE work_item_id='ITO-9001'"
        " AND clock='RESOLVE'").fetchone()
    calendar = clocks.Calendar.load(conn, "CLINICAL")
    naive = calendar.working_minutes(datetime(2026, 11, 16, 22, 10), closed_at)
    real = clocks.elapsed_minutes(conn, resolve["clock_id"], as_of=closed_at)
    w("")
    w(f"  Wall clock from raise to close is {_fmt(naive)}, which on a 240 minute")
    w(f"  target is a breach. The {_fmt(naive - real)} parked waiting for a supplier")
    w(f"  is not Dada IT's time, so the resolve clock counted {_fmt(real)} and did not")
    w("  breach. That difference is the whole reason a pause is modelled at all.")
    w("")
    w("  Every SLA target still ships enforced = 0. These measure. They do not promise.")
    w("")

    w("The Unrouted queue, ageing")
    w("-" * 68)
    conn.execute(
        "INSERT OR REPLACE INTO workflow (workflow_id, board_id, name, table_type,"
        " is_active) VALUES ('WF_AGE','UNROUTED','Unowned and ageing','TICKET',1)")
    conn.execute(
        "INSERT OR REPLACE INTO workflow_event (event_id, workflow_id, name, fires_on,"
        " execution_time, frequency, frequency_unit, max_executions)"
        " VALUES ('EV_AGE','WF_AGE','Nobody has picked it up','ON_SCHEDULE',"
        "'MULTIPLE_TIMES',30,'MINUTES',4)")
    conn.execute(
        "INSERT OR REPLACE INTO workflow_trigger (trigger_id, table_type, field,"
        " display_name, value_type) VALUES ('TICKET.OWNER','TICKET','owner','Owner','TEXT')")
    conn.execute(
        "INSERT INTO workflow_condition (event_id, trigger_id, operator, sort_order)"
        " VALUES ('EV_AGE','TICKET.OWNER','IS_NULL',1)")
    conn.execute(
        "INSERT INTO workflow_action (event_id, action, notify_role, detail)"
        " VALUES ('EV_AGE','ESCALATE','ON_CALL','Unrouted and unowned')")

    at = datetime(2026, 11, 17, 2, 0)
    unowned = {"work_item_id": "ITO-9002", "owner": None}
    for _ in range(6):
        result = rules.evaluate(conn, "EV_AGE", unowned, as_of=at)
        mark = "PAGE ON-CALL" if result["fired"] else "silent"
        w(f"  {at.strftime('%H:%M')}  {mark:<13} {result['reason']}")
        at = at.replace(minute=(at.minute + 30) % 60,
                        hour=at.hour + (1 if at.minute >= 30 else 0))
    w("")
    w("  Four pages, then it stops. Today triage is one person, and when she is")
    w("  unavailable the path is a personal chat to a CIO in another country.")
    w("")
    conn.commit()
    return out

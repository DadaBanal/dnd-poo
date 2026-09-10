"""Evaluate workflow rules. No expression language, and nothing reaches eval.

The engine can only do three things, and the limits are the design:

  * **Read a field a `workflow_trigger` row names.** If the vocabulary does not
    list it, a condition cannot test it. Adding a testable field is a row.
  * **Compare with one of eleven operators**, each a small function in
    `OPERATORS` below. There is no parser, no `eval`, no `exec`, and no string
    ever becomes code. A rules engine that evaluates arbitrary text is an
    injection surface wearing a configuration screen, and this one will be
    edited by hospital administrators.
  * **Decide whether a rule may fire again**, from `workflow_run` and the event's
    execution policy.

Deciding *whether* to act is here. Actually acting is the caller's job, because
the caller is the thing that knows how to send a page at two in the morning, and
that boundary is what makes all of this testable without a mail server.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta

from .clocks import parse_instant

UNITS = {"MINUTES": "minutes", "HOURS": "hours", "DAYS": "days"}


def _split(value: str | None) -> list[str]:
    return [v.strip() for v in (value or "").split(",") if v.strip()]


def _number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _compare(left, right, op) -> bool:
    """Numbers compare as numbers when both look like numbers, else as text."""
    a, b = _number(left), _number(right)
    if a is not None and b is not None:
        return op(a, b)
    return op(str(left), str(right))


OPERATORS = {
    "EQ": lambda left, value: str(left) == str(value),
    "NE": lambda left, value: str(left) != str(value),
    "IN": lambda left, value: str(left) in _split(value),
    "NOT_IN": lambda left, value: str(left) not in _split(value),
    "LT": lambda left, value: _compare(left, value, lambda a, b: a < b),
    "LTE": lambda left, value: _compare(left, value, lambda a, b: a <= b),
    "GT": lambda left, value: _compare(left, value, lambda a, b: a > b),
    "GTE": lambda left, value: _compare(left, value, lambda a, b: a >= b),
    "IS_NULL": lambda left, value: left is None,
    "IS_NOT_NULL": lambda left, value: left is not None,
    "CONTAINS": lambda left, value: str(value).lower() in str(left or "").lower(),
}


class UnknownField(Exception):
    """A condition naming a field the vocabulary does not list. Never ignored:
    a rule silently evaluating to False is a control that stopped working and
    told nobody."""


def conditions(conn: sqlite3.Connection, event_id: str) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT c.*, t.field, t.table_type, t.value_type FROM workflow_condition c"
        "  JOIN workflow_trigger t ON t.trigger_id = c.trigger_id"
        " WHERE c.event_id = ? ORDER BY c.sort_order, c.condition_id", (event_id,)
    ).fetchall()


def matches(conn: sqlite3.Connection, event_id: str, row: dict) -> bool:
    """Does this record satisfy the event's conditions?

    Conditions are read in order and combined left to right using each row's own
    conjunction, which is how the administrator sees them listed. No precedence
    rules, deliberately: a rule that needs brackets is a rule nobody can read on
    a screen, and it should be two rules.
    """
    tests = conditions(conn, event_id)
    if not tests:
        return True                     # an event with no conditions fires on its trigger

    result: bool | None = None
    for test in tests:
        field = test["field"]
        if field not in row:
            raise UnknownField(
                f"condition {test['condition_id']} reads {test['table_type']}.{field}, "
                f"which the record passed in does not carry. The vocabulary and the "
                f"caller disagree; fix one rather than letting the rule quietly fail.")
        operator = OPERATORS.get(test["operator"])
        if operator is None:
            raise UnknownField(f"operator {test['operator']!r} has no implementation")
        outcome = operator(row[field], test["value"])
        if result is None:
            result = outcome
        elif test["conjunction"] == "OR":
            result = result or outcome
        else:
            result = result and outcome
    return bool(result)


# ------------------------------------------------------- the execution policy

def firings(conn: sqlite3.Connection, event_id: str, work_item_id: str | None) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM workflow_run WHERE event_id = ?"
        "   AND (work_item_id = ? OR (? IS NULL AND work_item_id IS NULL))"
        "   AND outcome = 'ACTED' ORDER BY occurred_at",
        (event_id, work_item_id, work_item_id)).fetchall()


def may_fire(conn: sqlite3.Connection, event_id: str, work_item_id: str | None, *,
             as_of: datetime) -> tuple[bool, str]:
    """May this event act again on this record right now, and why or why not.

    Returns the reason as well as the answer, because "the rule did not fire" is
    the question somebody asks after an incident and a bare False does not
    answer it.
    """
    event = conn.execute("SELECT * FROM workflow_event WHERE event_id = ?",
                         (event_id,)).fetchone()
    if event is None:
        raise LookupError(f"no workflow event {event_id!r}")

    workflow = conn.execute("SELECT is_active FROM workflow WHERE workflow_id = ?",
                            (event["workflow_id"],)).fetchone()
    if not workflow or not workflow["is_active"]:
        return False, "the workflow is not active"

    already = firings(conn, event_id, work_item_id)
    policy = event["execution_time"]

    if policy == "ONCE":
        if already:
            return False, f"already acted once, at {already[0]['occurred_at']}"
        return True, "first firing"

    if policy == "MULTIPLE_TIMES" and len(already) >= (event["max_executions"] or 0):
        return False, (f"reached its cap of {event['max_executions']} firings, "
                       f"last at {already[-1]['occurred_at']}")

    if already:
        gap = timedelta(**{UNITS[event["frequency_unit"]]: event["frequency"]})
        due = parse_instant(already[-1]["occurred_at"]) + gap
        if as_of < due:
            return False, (f"next firing is due {due.isoformat(sep=' ')}, "
                           f"{event['frequency']} {event['frequency_unit'].lower()} "
                           f"after the last one")
    return True, (f"firing {len(already) + 1}"
                  + (f" of {event['max_executions']}" if event["max_executions"] else ""))


def record(conn: sqlite3.Connection, event_id: str, work_item_id: str | None, *,
           at: datetime, outcome: str, detail: str | None = None) -> int:
    """Append to the record. Every evaluation, not only the ones that acted."""
    number = len(firings(conn, event_id, work_item_id)) + 1
    cur = conn.execute(
        "INSERT INTO workflow_run (event_id, work_item_id, occurred_at,"
        " execution_number, outcome, detail) VALUES (?,?,?,?,?,?)",
        (event_id, work_item_id, at.isoformat(sep=" ", timespec="minutes"),
         number, outcome, detail))
    return cur.lastrowid


def actions(conn: sqlite3.Connection, event_id: str) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM workflow_action WHERE event_id = ?"
        " ORDER BY sort_order, action_id", (event_id,)).fetchall()


def evaluate(conn: sqlite3.Connection, event_id: str, row: dict, *,
             as_of: datetime, work_item_id: str | None = None) -> dict:
    """Decide, record the decision, and hand back what to do. Acting is yours.

    The split is deliberate: this function is pure enough to test without a mail
    server, a pager or a clock, and everything it decided is on the record
    whether it acted or not.
    """
    work_item_id = work_item_id or row.get("work_item_id")

    allowed, why = may_fire(conn, event_id, work_item_id, as_of=as_of)
    if not allowed:
        record(conn, event_id, work_item_id, at=as_of, outcome="SUPPRESSED", detail=why)
        return {"fired": False, "reason": why, "actions": []}

    if not matches(conn, event_id, row):
        record(conn, event_id, work_item_id, at=as_of, outcome="NOT_MATCHED",
               detail="conditions not met")
        return {"fired": False, "reason": "conditions not met", "actions": []}

    to_do = actions(conn, event_id)
    record(conn, event_id, work_item_id, at=as_of, outcome="ACTED",
           detail=f"{why}; {len(to_do)} action(s)")
    return {"fired": True, "reason": why, "actions": to_do}

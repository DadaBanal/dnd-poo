"""Desk metrics for the Reports screen: what a Service Manager asks each month.

Everything is computed from the tickets and their clocks at the moment asked,
never from a stored figure: opened and closed by month, the backlog, the share
of clocks met (the same working-minute arithmetic the ticket screen shows),
median working time to respond and to resolve, and the mix by board, Type and
source. A month is the calendar month of the ticket's opened_at (volume) or
closed_at (outcomes), in the desk's own local timestamps.

Scoped to the boards the reader is on: a count is not a read of a ticket, so
nothing here names one, and nothing here is audited as a restricted read.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime

from . import clocks, db

CLOSED = "('RESOLVED','CLOSED','CANCELLED')"


def month_keys(now: datetime, months: int) -> list[str]:
    """The last `months` calendar months ending with now's, oldest first."""
    y, m = now.year, now.month
    out = []
    for _ in range(months):
        out.append(f"{y:04d}-{m:02d}")
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return list(reversed(out))


def _median(values: list[int]) -> int | None:
    if not values:
        return None
    s = sorted(values)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) // 2


def desk(conn: sqlite3.Connection, boards, *, now: datetime, months: int = 6,
         board: str | None = None) -> dict:
    boards = sorted(b for b in boards if not board or b == board)
    keys = month_keys(now, months)
    empty = {"months": keys, "opened": {k: 0 for k in keys}, "closed": {k: 0 for k in keys},
             "respond_met": {k: None for k in keys}, "resolve_met": {k: None for k in keys},
             "backlog": 0, "opened_total": 0, "closed_total": 0,
             "median_respond": None, "median_resolve": None,
             "respond_met_total": None, "resolve_met_total": None,
             "by_board": [], "by_type": [], "by_source": [], "by_came_from": [], "by_priority": [],
             "satisfaction": None, "satisfaction_n": 0, "chat_rating": None, "chat_rating_n": 0,
             "chat_by_operator": []}
    if not boards:
        return empty
    marks = ",".join("?" * len(boards))
    since = keys[0] + "-01"
    out = dict(empty)

    for k, n in conn.execute(
            f"SELECT substr(opened_at, 1, 7) AS m, COUNT(*) FROM ticket WHERE board_id IN ({marks})"
            " AND opened_at >= ? GROUP BY substr(opened_at, 1, 7)", (*boards, since)):
        if k in out["opened"]:
            out["opened"][k] = n
    for k, n in conn.execute(
            f"SELECT substr(closed_at, 1, 7) AS m, COUNT(*) FROM ticket WHERE board_id IN ({marks})"
            " AND closed_at >= ? GROUP BY substr(closed_at, 1, 7)", (*boards, since)):
        if k in out["closed"]:
            out["closed"][k] = n
    out["opened_total"] = sum(out["opened"].values())
    out["closed_total"] = sum(out["closed"].values())
    out["backlog"] = conn.execute(
        f"SELECT COUNT(*) FROM ticket WHERE board_id IN ({marks}) AND state NOT IN {CLOSED}",
        boards).fetchone()[0]

    # Outcomes: every ticket closed in the window, its clocks computed once.
    closed_rows = conn.execute(
        f"SELECT work_item_id, substr(closed_at, 1, 7) AS m FROM ticket WHERE board_id IN ({marks})"
        " AND closed_at >= ?", (*boards, since)).fetchall()
    states = clocks.states_many(conn, [r["work_item_id"] for r in closed_rows], as_of=now)
    met = {"RESPOND": {k: [0, 0] for k in keys}, "RESOLVE": {k: [0, 0] for k in keys}}
    elapsed = {"RESPOND": [], "RESOLVE": []}
    for r in closed_rows:
        for st in states.get(r["work_item_id"], []):
            c = st["clock"]
            if c not in met or not st["stopped_at"] or r["m"] not in keys:
                continue
            met[c][r["m"]][1] += 1
            met[c][r["m"]][0] += 0 if st["breached"] else 1
            elapsed[c].append(st["elapsed_minutes"])
    for c, key in (("RESPOND", "respond_met"), ("RESOLVE", "resolve_met")):
        for k in keys:
            hit, n = met[c][k]
            out[key][k] = round(100 * hit / n) if n else None
        hit = sum(v[0] for v in met[c].values())
        n = sum(v[1] for v in met[c].values())
        out[key + "_total"] = round(100 * hit / n) if n else None
    out["median_respond"] = _median(elapsed["RESPOND"])
    out["median_resolve"] = _median(elapsed["RESOLVE"])

    def mix(expr: str, joins: str = "") -> list[tuple[str, int]]:
        return [(r[0] or "—", r[1]) for r in conn.execute(
            f"SELECT {expr} AS k, COUNT(*) AS n FROM ticket t {joins}"
            f" WHERE t.board_id IN ({marks}) AND t.opened_at >= ? GROUP BY {expr} ORDER BY COUNT(*) DESC, {expr}",
            (*boards, since))]
    out["by_board"] = mix("b.display_name", "JOIN board b ON b.board_id = t.board_id")
    out["by_type"] = mix("t.record_type")
    out["by_source"] = mix("t.intake_source")
    # 9 Oct 2026: where tickets came from, Chat apart (origin.py). Counted here
    # rather than grouped in SQL: SQL Server refuses a subquery in GROUP BY.
    from . import origin
    rows = conn.execute(f"SELECT t.work_item_id, t.intake_source FROM ticket t WHERE t.board_id IN ({marks})"
                        " AND t.opened_at >= ?", (*boards, since)).fetchall()
    came: dict[str, int] = {}
    for o in origin.of(conn, [(r[0], r[1]) for r in rows]).values():
        came[o["key"]] = came.get(o["key"], 0) + 1
    out["by_came_from"] = sorted(came.items(), key=lambda x: (-x[1], list(origin.BUCKETS).index(x[0])))
    out["by_priority"] = sorted(mix("t.priority"), key=lambda x: x[0])

    if db.table_exists(conn, "survey_response"):
        row = conn.execute(
            f"SELECT AVG(CAST(s.score AS REAL)), COUNT(*) FROM survey_response s"
            f" JOIN ticket t ON t.work_item_id = s.work_item_id"
            f" WHERE t.board_id IN ({marks}) AND s.answered_at >= ?", (*boards, since)).fetchone()
        if row and row[1]:
            out["satisfaction"], out["satisfaction_n"] = round(row[0], 2), row[1]
    if db.table_exists(conn, "chat_survey"):                 # 072: chats rated at their end
        row = conn.execute(
            f"SELECT AVG(CAST(s.score AS REAL)), COUNT(*) FROM chat_survey s"
            f" JOIN chat_session c ON c.chat_id = s.chat_id"
            f" WHERE c.board_id IN ({marks}) AND s.answered_at >= ?", (*boards, since)).fetchone()
        if row and row[1]:
            out["chat_rating"], out["chat_rating_n"] = round(row[0], 2), row[1]
        # 074: and each operator's own (Dada, 7 Oct 2026: "how i did")
        from . import chat as _chat
        out["chat_by_operator"] = _chat.ratings_by_operator(conn, boards, since=since)
    return out


def csv_rows(m: dict) -> list[list]:
    rows = [["month", "opened", "closed", "respond_met_pct", "resolve_met_pct"]]
    for k in m["months"]:
        rows.append([k, m["opened"][k], m["closed"][k],
                     "" if m["respond_met"][k] is None else m["respond_met"][k],
                     "" if m["resolve_met"][k] is None else m["resolve_met"][k]])
    return rows

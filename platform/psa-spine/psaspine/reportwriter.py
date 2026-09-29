"""The report writer (042): saved reports over datasets the desk defines.

The reference PSA's report writer lets a person pick fields and groupings. Here
a person picks from each dataset's own list; the dataset's code writes every
query, so no SQL is ever typed or stored, and every dataset is limited to the
boards the viewer may see (a restricted board's rows reach only its members).
A report is a dataset, columns, an optional grouping (a count and, where the
dataset has hours, their sum) and filters: board, a date range on the
dataset's own date, and a state where it has one.
"""
from __future__ import annotations

import csv
import io
import sqlite3
import urllib.parse
from datetime import date, datetime

MAX_ROWS = 5000

# dataset: (from + joins, board expression or None, date column, {key: (sql, label)}, hours sql or None, state sql or None)
DATASETS = {
    "TICKETS": {
        "label": "Tickets",
        "from": " FROM ticket t JOIN work_item w ON w.work_item_id = t.work_item_id"
                " JOIN board b ON b.board_id = t.board_id",
        "board": "t.board_id", "date": "t.opened_at", "hours": None, "state": "t.state",
        "columns": {"id": ("t.work_item_id", "Ticket"), "summary": ("w.name", "Summary"),
                    "board": ("b.display_name", "Board"), "state": ("t.state", "State"),
                    "priority": ("t.priority", "Priority"), "type": ("t.record_type", "Type"),
                    "owner": ("t.owner", "Owner"), "source": ("t.intake_source", "Source"),
                    "opened": ("t.opened_at", "Opened"), "closed": ("t.closed_at", "Closed"),
                    "month": ("SUBSTR(t.opened_at, 1, 7)", "Month opened")},
    },
    "TIME": {
        "label": "Time entries",
        "from": " FROM time_entry te JOIN ticket t ON t.work_item_id = te.work_item_id"
                " JOIN board b ON b.board_id = t.board_id",
        "board": "t.board_id", "date": "te.worked_on", "hours": "COALESCE(te.actual_hours, te.band_hours)",
        "state": None,
        "columns": {"ticket": ("te.work_item_id", "Ticket"), "member": ("te.performed_by", "Member"),
                    "worked_on": ("te.worked_on", "Worked on"), "board": ("b.display_name", "Board"),
                    "hours": ("COALESCE(te.actual_hours, te.band_hours)", "Hours"),
                    "work_role": ("te.work_role_id", "Work role"), "work_type": ("te.work_type_id", "Work type"),
                    "charge": ("te.charge_method", "Charge method"),
                    "month": ("SUBSTR(te.worked_on, 1, 7)", "Month")},
    },
    "VISITS": {
        "label": "Scheduled visits",
        "from": " FROM ticket_schedule s JOIN ticket t ON t.work_item_id = s.work_item_id"
                " JOIN board b ON b.board_id = t.board_id",
        "board": "t.board_id", "date": "s.starts_at", "hours": None, "state": None,
        "columns": {"ticket": ("s.work_item_id", "Ticket"), "member": ("s.member", "Member"),
                    "starts": ("s.starts_at", "Starts"), "ends": ("s.ends_at", "Ends"),
                    "board": ("b.display_name", "Board"), "status": ("s.status_id", "Status"),
                    "where": ("s.location_id", "Where"),
                    "done": ("CASE WHEN s.done_at IS NULL THEN 'no' ELSE 'yes' END", "Done"),
                    "day": ("SUBSTR(s.starts_at, 1, 10)", "Day")},
    },
    "PROJECTS": {
        "label": "Projects",
        "from": " FROM project p LEFT JOIN board b ON b.board_id = p.board_id",
        "board": "p.board_id", "date": "p.starts_on", "hours": None, "state": "p.status",
        "columns": {"id": ("p.project_id", "Project"), "name": ("p.name", "Name"), "manager": ("p.manager", "Manager"),
                    "status": ("p.status", "Status"), "board": ("b.display_name", "Board"),
                    "starts": ("p.starts_on", "Starts"), "ends": ("p.ends_on", "Ends"),
                    "budget": ("p.budget_hours", "Budget hours")},
    },
    "KNOWLEDGE": {
        "label": "Knowledge articles",
        "from": " FROM kb_article a LEFT JOIN board b ON b.board_id = a.board_id",
        "board": "a.board_id", "date": "a.updated_at", "hours": None, "state": "a.status",
        "columns": {"id": ("a.article_id", "Article"), "title": ("a.title", "Title"),
                    "audience": ("a.audience", "Audience"), "status": ("a.status", "Status"),
                    "board": ("b.display_name", "Board"), "uses": ("a.uses", "Uses"),
                    "updated": ("a.updated_at", "Updated")},
    },
}


class Refused(ValueError):
    """A sentence for the person; nothing was written."""


def clean(dataset: str, columns, group_by: str | None) -> tuple[list[str], str | None]:
    ds = DATASETS.get(dataset)
    if ds is None:
        raise Refused("No such dataset.")
    cols = [c for c in columns if c in ds["columns"]]
    if group_by and group_by not in ds["columns"]:
        raise Refused("That grouping is not on this dataset.")
    if not cols and not group_by:
        raise Refused("Pick at least one column, or a grouping.")
    return cols, group_by or None


def _d(value: str | None) -> str | None:
    try:
        return date.fromisoformat((value or "").strip()).isoformat()
    except ValueError:
        return None


def run(conn: sqlite3.Connection, dataset: str, columns, group_by: str | None, filters: dict, *,
        boards) -> dict:
    """Rows for a report, limited to `boards` (the viewer's). Returns headers,
    rows and whether the row limit was reached."""
    ds = DATASETS[dataset]
    cols, group_by = clean(dataset, columns, group_by)
    where, args = [], []
    boards = sorted(boards)
    if dataset in ("PROJECTS", "KNOWLEDGE"):
        # a project or article on no board is everyone's; on a board, its members'
        where.append(f"({ds['board']} IS NULL" + (f" OR {ds['board']} IN ({','.join('?' * len(boards))})" if boards else "") + ")")
    else:
        if not boards:
            return {"headers": [], "rows": [], "capped": False, "boards": {}}
        where.append(f"{ds['board']} IN ({','.join('?' * len(boards))})")
    args += boards
    if filters.get("board"):
        where.append(f"{ds['board']} = ?")
        args.append(filters["board"])
    if _d(filters.get("from")):
        where.append(f"{ds['date']} >= ?")
        args.append(_d(filters["from"]))
    if _d(filters.get("to")):
        where.append(f"{ds['date']} < ?")
        args.append(_d(filters["to"]) + " 99")        # the whole of the last day
    if filters.get("state") and ds["state"]:
        where.append(f"{ds['state']} = ?")
        args.append(filters["state"])
    tail = " WHERE " + " AND ".join(where)
    # which restricted boards' tickets the rows come from, so the view can audit
    # the read (§6.1 requirement 4); a project or article list names no ticket
    per_board = {}
    if dataset not in ("PROJECTS", "KNOWLEDGE"):
        per_board = {r[0]: r[1] for r in conn.execute(
            f"SELECT {ds['board']}, COUNT(*){ds['from']}{tail} GROUP BY {ds['board']}", args)}
    if group_by:
        expr, label = ds["columns"][group_by]
        measures = ["COUNT(*)"] + ([f"SUM({ds['hours']})"] if ds["hours"] else [])
        sql = f"SELECT {expr} AS g, {', '.join(measures)}{ds['from']}{tail} GROUP BY {expr} ORDER BY {expr}"
        headers = [label, "Count"] + (["Hours"] if ds["hours"] else [])
        rows = [[r[0], r[1]] + ([round(float(r[2] or 0), 2)] if ds["hours"] else []) for r in conn.execute(sql, args)]
        return {"headers": headers, "rows": rows[:MAX_ROWS], "capped": len(rows) > MAX_ROWS, "boards": per_board}
    sel = ", ".join(ds["columns"][c][0] for c in cols)
    sql = f"SELECT {sel}{ds['from']}{tail} ORDER BY {ds['date']} DESC"
    rows = [list(r) for r in conn.execute(sql, args).fetchmany(MAX_ROWS + 1)]
    return {"headers": [ds["columns"][c][1] for c in cols], "rows": rows[:MAX_ROWS], "capped": len(rows) > MAX_ROWS,
            "boards": per_board}


def as_csv(result: dict) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(result["headers"])
    for r in result["rows"]:
        # a leading = + - @ would be a formula in a spreadsheet: quote it
        w.writerow(["'" + v if isinstance(v, str) and v[:1] in "=+-@" else v for v in r])
    return buf.getvalue()


# ------------------------------------------------------------- saved reports

def save(conn, *, name: str, dataset: str, columns, group_by: str | None, filters: dict, owner: str,
         shared: bool, at: datetime, report_id: int | None = None) -> int:
    name = " ".join((name or "").split())[:120]
    if not name:
        raise Refused("A report needs a name.")
    cols, group_by = clean(dataset, columns, group_by)
    keep = {k: v for k, v in filters.items() if k in ("board", "from", "to", "state") and v}
    q = urllib.parse.urlencode(keep)
    if report_id is None:
        cur = conn.execute("INSERT INTO report_def (name, dataset, columns, group_by, filters, owner, shared, pinned,"
                           " created_at) VALUES (?,?,?,?,?,?,?,0,?)",
                           (name, dataset, ",".join(cols), group_by, q, owner, int(shared),
                            at.isoformat(sep=" ", timespec="minutes")))
        return cur.lastrowid
    conn.execute("UPDATE report_def SET name = ?, dataset = ?, columns = ?, group_by = ?, filters = ?, shared = ?"
                 " WHERE report_id = ?", (name, dataset, ",".join(cols), group_by, q, int(shared), report_id))
    return report_id


def visible(conn, member: str):
    return conn.execute("SELECT * FROM report_def WHERE LOWER(owner) = LOWER(?) OR shared = 1 ORDER BY name",
                        (member,)).fetchall()


def get(conn, report_id: int):
    return conn.execute("SELECT * FROM report_def WHERE report_id = ?", (report_id,)).fetchone()


def parts(row) -> tuple[list[str], str | None, dict]:
    return ([c for c in (row["columns"] or "").split(",") if c], row["group_by"],
            dict(urllib.parse.parse_qsl(row["filters"] or "")))

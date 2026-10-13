"""The desk's catalogue of MMS reports and the log of every run (082).

The reports live on the report server (ssrs.py); this module keeps what the
desk needs beside them: which area each belongs to (so a role's See on that
area shows it), a title a person reads, whether it is shown, and who ran
what with which values. Nothing here writes to the report server.
"""
from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime

from . import db, ssrs

AREAS = ("purchase_order", "invoice", "product")
AREA_WORDS = {"purchase_order": "Purchase orders", "invoice": "Receiving", "product": "Items and stock"}
# The area a report belongs to, from its name: purchasing words first, then
# receiving, then everything else is stock. A service manager can move one.
_PO = re.compile(r"purc|purchase|\bpo\b|_po_|vendor|supplier", re.I)
_RR = re.compile(r"receiv|recv|deliver|\bdel\b|_del|\brr\b|_rr_|apinv", re.I)


def area_of(name: str) -> str:
    if _PO.search(name):
        return "purchase_order"
    if _RR.search(name):
        return "invoice"
    return "product"


def _stamp(at: datetime) -> str:
    return at.isoformat(sep=" ", timespec="minutes")


def ready(conn) -> bool:
    return db.table_exists(conn, "mms_report")


# ---------------------------------------------------------------- catalogue

def sync(conn, reports: list, *, at: datetime, actor: str, apply: bool = True) -> dict:
    """Upsert the catalogue from the server's listing (ssrs.Report rows). A
    report the server no longer lists is marked absent, never deleted. A
    title or area a person set on Setup is kept."""
    counts = {"rows": len(reports), "new": 0, "changed": 0, "unchanged": 0, "absent": 0, "returned": 0}
    seen = set()
    for r in reports:
        path, name = (r.path or "").strip(), (r.name or "").strip()
        if not path or not name or path in seen:
            continue
        seen.add(path)
        title = ssrs.humanise(name)
        old = conn.execute("SELECT * FROM mms_report WHERE path = ?", (path,)).fetchone()
        if old is None:
            counts["new"] += 1
            conn.execute("INSERT INTO mms_report (path, name, title, description, area, shown, present, synced_at)"
                         " VALUES (?,?,?,?,?,1,1,?)", (path, name, title, r.description or None, area_of(name), _stamp(at)))
            continue
        sets, args = [], []
        if old["name"] != name:
            sets.append("name = ?"); args.append(name)
        if (old["description"] or None) != (r.description or None):
            sets.append("description = ?"); args.append(r.description or None)
        if not old["title_set_by"] and old["title"] != title:
            sets.append("title = ?"); args.append(title)
        if not old["present"]:
            counts["returned"] += 1
        if sets or not old["present"]:
            counts["changed" if sets else "unchanged"] += 1
            conn.execute(f"UPDATE mms_report SET {', '.join(sets + ['present = 1', 'synced_at = ?'])} WHERE report_id = ?",
                         args + [_stamp(at), old["report_id"]])
        else:
            counts["unchanged"] += 1
    for row in conn.execute("SELECT report_id, path FROM mms_report WHERE present = 1").fetchall():
        if row["path"] not in seen:
            counts["absent"] += 1
            conn.execute("UPDATE mms_report SET present = 0 WHERE report_id = ?", (row["report_id"],))
    words = (f"{counts['rows']} reports listed: {counts['new']} new, {counts['changed']} changed, "
             f"{counts['unchanged']} unchanged, {counts['absent']} no longer listed")
    if apply:
        db.audit(conn, at=_stamp(at), actor=actor, action="MMS_REPORTS_SYNC", subject_kind="mms_report", subject_id="*",
                 detail=words)
        conn.commit()
    else:
        conn.rollback()
    return counts | {"words": words}


def listed(conn, *, areas=None, q: str = "", shown_only: bool = True) -> list:
    sql, args = ["SELECT * FROM mms_report WHERE present = 1"], []
    if shown_only:
        sql.append(" AND shown = 1")
    if areas is not None:
        if not areas:
            return []
        sql.append(f" AND area IN ({','.join('?' * len(areas))})"); args += list(areas)
    if q.strip():
        like = f"%{q.strip().lower()}%"
        sql.append(" AND (LOWER(title) LIKE ? OR LOWER(name) LIKE ? OR LOWER(COALESCE(description, '')) LIKE ?)")
        args += [like, like, like]
    sql.append(" ORDER BY area, COALESCE(sort_no, 9999), title")
    return conn.execute("".join(sql), args).fetchall()


def get(conn, report_id):
    try:
        rid = int(report_id)
    except (TypeError, ValueError):
        return None
    return conn.execute("SELECT * FROM mms_report WHERE report_id = ?", (rid,)).fetchone()


def set_report(conn, report_id: int, *, at: datetime, actor: str, title: str | None = None, area: str | None = None,
               shown: bool | None = None, sort_no=None) -> str:
    r = get(conn, report_id)
    if r is None:
        raise ssrs.Refused("No such report in the catalogue.")
    changed = []
    if title is not None:
        title = " ".join(title.split())[:200]
        if title and title != r["title"]:
            conn.execute("UPDATE mms_report SET title = ?, title_set_by = ? WHERE report_id = ?", (title, actor, report_id))
            changed.append(f"title {r['title']!r} -> {title!r}")
    if area is not None:
        if area not in AREAS:
            raise ssrs.Refused("An area is purchase orders, receiving or items.")
        if area != r["area"]:
            conn.execute("UPDATE mms_report SET area = ?, area_set_by = ? WHERE report_id = ?", (area, actor, report_id))
            changed.append(f"area {r['area']} -> {area}")
    if shown is not None and int(shown) != r["shown"]:
        conn.execute("UPDATE mms_report SET shown = ? WHERE report_id = ?", (int(shown), report_id))
        changed.append("shown" if shown else "hidden")
    if sort_no is not None:
        n = int(sort_no) if str(sort_no).strip().isdigit() else None
        if n != r["sort_no"]:
            conn.execute("UPDATE mms_report SET sort_no = ? WHERE report_id = ?", (n, report_id))
            changed.append(f"order {n}")
    if changed:
        db.audit(conn, at=_stamp(at), actor=actor, action="MMS_REPORT", subject_kind="mms_report", subject_id=str(report_id),
                 detail="; ".join(changed))
    return "; ".join(changed) or "nothing changed"


def remember_params(conn, report_id: int, params: list) -> None:
    conn.execute("UPDATE mms_report SET params_json = ? WHERE report_id = ?",
                 (json.dumps([p.as_dict() for p in params]), report_id))


def params_summary(row) -> list[str]:
    try:
        return [p["prompt"] for p in json.loads(row["params_json"] or "[]") if p.get("prompt_user", True)]
    except (ValueError, TypeError):
        return []


# ------------------------------------------------------------------ values

def values_from(params: list, get, get_list, *, require: bool, prefix: str = "p.") -> tuple[dict, list[str]]:
    """The values a form or a query string sent, typed per parameter, and
    the sentences for what is missing (only when `require`: a refresh of
    the dropdowns asks for nothing). A nullable parameter left empty is sent
    as null; a multi-value one as its list; a date as YYYY-MM-DD."""
    values, missing = {}, []
    for p in params:
        if not p.prompt_user:
            continue
        key = prefix + p.name
        if get(key + ".null") == "1" and p.nullable:
            values[p.name] = None
            continue
        if p.multi:
            got = [v for v in get_list(key) if v != ""]
            if not got:
                if require and p.required:
                    if p.defaults:
                        values[p.name] = list(p.defaults)          # as the server would: its default
                    else:
                        missing.append(p.prompt)
                continue
            values[p.name] = got
            continue
        v = (get(key) or "").strip()
        if v == "":
            if require and p.required:
                if p.defaults:
                    values[p.name] = p.defaults[0]
                else:
                    missing.append(p.prompt)
            elif p.nullable and require:
                values[p.name] = None
            continue
        if p.type == "DateTime" and not re.fullmatch(r"\d{4}-\d{2}-\d{2}([ T]\d{2}:\d{2}(:\d{2})?)?", v):
            missing.append(f"{p.prompt} (a date)")
            continue
        if p.type in ("Integer", "Float") and not re.fullmatch(r"-?\d+(\.\d+)?", v):
            missing.append(f"{p.prompt} (a number)")
            continue
        if p.type == "Boolean" and v.lower() not in ("true", "false"):
            missing.append(f"{p.prompt} (yes or no)")
            continue
        values[p.name] = v
    return values, missing


def defaults_of(params: list) -> dict:
    out = {}
    for p in params:
        if p.defaults:
            out[p.name] = list(p.defaults) if p.multi else p.defaults[0]
    return out


# --------------------------------------------------------------------- runs

def log_run(conn, report_id: int, *, member: str, at: datetime, fmt: str, values: dict, ok: bool, message: str = "",
            size: int | None = None, millis: int | None = None) -> int:
    cur = conn.execute(
        "INSERT INTO mms_report_run (report_id, member, ran_at, format, params_json, outcome, message, bytes, millis)"
        " VALUES (?,?,?,?,?,?,?,?,?)",
        (report_id, member, _stamp(at), fmt, json.dumps(values, default=str), "OK" if ok else "ERROR",
         (message or "")[:1000] or None, size, millis))
    return cur.lastrowid


def last_values(conn, report_id: int, member: str) -> dict:
    """What this person ran it with last time: the form opens there."""
    row = conn.execute("SELECT params_json FROM mms_report_run WHERE report_id = ? AND LOWER(member) = LOWER(?)"
                       " AND outcome = 'OK' ORDER BY run_id DESC LIMIT 1", (report_id, member)).fetchone()
    if not row or not row["params_json"]:
        return {}
    try:
        return json.loads(row["params_json"])
    except ValueError:
        return {}


def recent_runs(conn, report_id: int, *, limit: int = 8) -> list:
    return conn.execute("SELECT * FROM mms_report_run WHERE report_id = ? ORDER BY run_id DESC LIMIT ?",
                        (report_id, limit)).fetchall()


def run_count(conn, *, member: str | None = None) -> int:
    if member:
        return conn.execute("SELECT COUNT(*) FROM mms_report_run WHERE LOWER(member) = LOWER(?)", (member,)).fetchone()[0]
    return conn.execute("SELECT COUNT(*) FROM mms_report_run").fetchone()[0]

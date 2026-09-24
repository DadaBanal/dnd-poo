"""BizBox, read-only: one agreed view, through a login allowed SELECT on it and
nothing else. Nothing is ever written to BizBox.

The view's contract (README, "The BizBox connector"): one row per imaging order,
with change_seq, the larger rowversion of the order and its patient, so a
corrected name or birth date counts as a change too. rowversion is a
database-wide counter: no clock, so no clock skew.

The change cursor, from the research proof. rowversion is taken when a row is
written, not when its transaction commits, so a reader asking only
"change_seq > cursor" can see a later write commit first, move past it, and
never see the earlier one (MEASURED there, T17 and T18). Two guards: only rows
below MIN_ACTIVE_ROWVERSION() are read, so nothing still in flight is skipped;
and READCOMMITTEDLOCK + READPAST passes over a row another transaction is
writing instead of waiting on it, so the connector never queues behind, or
holds up, BizBox. LOCK_TIMEOUT bounds any other wait.
"""
from __future__ import annotations

import re

import mssql_python

COLUMNS = ("order_no", "hospital_no", "last_name", "first_name", "middle_name", "birth_date",
           "sex", "encounter_no", "section", "procedure_code", "procedure_desc",
           "referring_doctor", "priority", "scheduled_at", "status", "change_seq")
_COLS = ", ".join(COLUMNS)


def _view(name: str) -> str:
    # A site value, but still SQL: accept only schema.name made of plain characters.
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*", name):
        raise SystemExit(f"orders: PMC_BIZBOX_VIEW is not a schema.view name: {name!r}")
    return name


def connect(cfg):
    conn = mssql_python.connect(
        f"SERVER={cfg.bizbox_server};DATABASE={cfg.bizbox_database};"
        f"UID={cfg.bizbox_user};PWD={cfg.bizbox_password};Encrypt=yes;"
        f"TrustServerCertificate={'yes' if cfg.bizbox_trust_server_cert else 'no'};"
        "ApplicationIntent=ReadOnly")
    conn.autocommit = True
    conn.cursor().execute("SET LOCK_TIMEOUT 5000")
    return conn


def fetch_changes(conn, view: str, since_seq: int, limit: int = 500) -> list[dict]:
    cur = conn.cursor()
    cur.execute(
        f"SELECT TOP ({int(limit)}) {_COLS} FROM {_view(view)} WITH (READCOMMITTEDLOCK, READPAST) "
        "WHERE change_seq > ? AND change_seq < CAST(MIN_ACTIVE_ROWVERSION() AS bigint) "
        "ORDER BY change_seq", (since_seq,))
    return [dict(zip(COLUMNS, row)) for row in cur.fetchall()]

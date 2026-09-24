"""The connector's own record, in PMC's platform database (schema ris,
db/migrations): which worklist entries each order has, where it has got to,
and an append-only log of what the connector did."""
from __future__ import annotations

import json

import psycopg
from psycopg.rows import dict_row


class State:
    def __init__(self, dsn: str):
        self.conn = psycopg.connect(dsn, autocommit=True, row_factory=dict_row)

    def q(self, sql: str, params=()) -> list[dict]:
        cur = self.conn.execute(sql, params)
        return cur.fetchall() if cur.description else []

    def one(self, sql: str, params=()) -> dict | None:
        rows = self.q(sql, params)
        return rows[0] if rows else None

    def cursor(self, name: str) -> int:
        row = self.one("SELECT value FROM ris.sync_cursor WHERE name = %s", (name,))
        return int(row["value"]) if row else 0

    def set_cursor(self, name: str, value: int) -> None:
        self.q("INSERT INTO ris.sync_cursor (name, value) VALUES (%s, %s) "
               "ON CONFLICT (name) DO UPDATE SET value = EXCLUDED.value", (name, value))

    def event(self, action: str, order_no: str, detail: dict) -> None:
        self.q("INSERT INTO ris.event (actor, action, order_no, detail) VALUES ('orders', %s, %s, %s)",
               (action, order_no, json.dumps(detail, default=str)))

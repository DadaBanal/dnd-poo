"""Open, create and seed the spine database.

SQLite by design for Phase 1: no server, no provisioning, no procurement, and
one file that can be escrowed to the client's own storage nightly. The Azure SQL
lift is a later gate; the schema is kept to constructs SQL Server also accepts
but that path is NOT VERIFIED.
"""
from __future__ import annotations

import csv
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_DIR = ROOT / "schema"
SEED_DIR = ROOT / "seed"


def connect(path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def create(conn: sqlite3.Connection) -> None:
    """Apply every migration in name order."""
    for sql_file in sorted(SCHEMA_DIR.glob("*.sql")):
        conn.executescript(sql_file.read_text(encoding="utf-8"))
    conn.commit()


def _seed_rows(name: str) -> list[dict]:
    with (SEED_DIR / name).open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def seed(conn: sqlite3.Connection) -> None:
    """Load the reference data that is the same for every deployment.

    Commercial amounts are deliberately NOT seeded here — see README. The fee
    schedule loads at runtime from a data file held outside version control.
    """
    for row in _seed_rows("entities.csv"):
        conn.execute(
            "INSERT OR REPLACE INTO entity (entity_id, name, is_covered, note) VALUES (?,?,?,?)",
            (row["entity_id"], row["name"], int(row["is_covered"]), row["note"]),
        )
    for row in _seed_rows("scope_items.csv"):
        conn.execute(
            "INSERT OR REPLACE INTO scope_item (scope_item_id, heading, is_baseline) VALUES (?,?,?)",
            (row["scope_item_id"], row["heading"], int(row["is_baseline"])),
        )
    for row in _seed_rows("instruments.csv"):
        conn.execute(
            "INSERT OR REPLACE INTO instrument "
            "(instrument_id, kind, title, effective_from, execution_status, note) VALUES (?,?,?,?,?,?)",
            (
                row["instrument_id"],
                row["kind"],
                row["title"],
                row["effective_from"] or None,
                row["execution_status"],
                row["note"],
            ),
        )
    conn.commit()


def init(path: str | Path) -> sqlite3.Connection:
    conn = connect(path)
    create(conn)
    seed(conn)
    return conn


def annex_b_categories() -> list[dict]:
    return _seed_rows("annex_b_categories.csv")


def audit(conn: sqlite3.Connection, *, at: str, actor: str, action: str,
          subject_kind: str, subject_id: str | None = None,
          detail: str | None = None, override_reason: str | None = None) -> None:
    conn.execute(
        "INSERT INTO audit_event (occurred_at, actor, action, subject_kind, subject_id, detail, override_reason)"
        " VALUES (?,?,?,?,?,?,?)",
        (at, actor, action, subject_kind, subject_id, detail, override_reason),
    )

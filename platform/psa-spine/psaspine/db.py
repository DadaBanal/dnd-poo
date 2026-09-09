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
    seed_catalogue(conn)
    conn.commit()


def seed_catalogue(conn: sqlite3.Connection) -> None:
    """Load the service catalogue.

    The five phase 2 boards seed LIVE, with an owner and a deputy, because they
    are Dada IT's and the PMO's own work and nobody else has to agree to them.
    The names are defaults taken from the fulfiller groups the record already
    states; they are in a CSV precisely so correcting one costs five seconds.

    The ten departmental boards seed not-live and unowned -- but the reason is
    sequencing, not a signature. Phase 3a and 3b have not opened, so there is no
    department to name an owner in yet. The CHECK still holds when they do.

    Clinical floors are the one thing seeded unsigned on purpose: that list is
    signed by the Chief of Hospital, the Chief Nurse and the Quality officer,
    and it changes no behaviour today because the catalogue items that matter
    carry their own P1 floor regardless.
    """
    def blank(v):
        return v if (v or "").strip() else None

    for row in _seed_rows("boards.csv"):
        conn.execute(
            "INSERT OR REPLACE INTO board (board_id, display_name, phase, fulfiller_group,"
            " owner, deputy, restricted, is_live, is_unrouted, note)"
            " VALUES (?,?,?,?,?,?,?,?,?,?)",
            (row["board_id"], row["display_name"], row["phase"], row["fulfiller_group"],
             blank(row["owner"]), blank(row["deputy"]), int(row["restricted"]),
             int(row["is_live"]), int(row["is_unrouted"]), blank(row["note"])),
        )
    for row in _seed_rows("service_actions.csv"):
        conn.execute(
            "INSERT OR REPLACE INTO service_action"
            " (action_id, display_name, raw_name, kind, implies_impact, note) VALUES (?,?,?,?,?,?)",
            (row["action_id"], row["display_name"], blank(row["raw_name"]), row["kind"],
             blank(row["implies_impact"]), blank(row["note"])),
        )
    for row in _seed_rows("service_families.csv"):
        conn.execute(
            "INSERT OR REPLACE INTO service_family (family_id, display_name, raw_name, note)"
            " VALUES (?,?,?,?)",
            (row["family_id"], row["display_name"], blank(row["raw_name"]), blank(row["note"])),
        )
    for row in _seed_rows("service_components.csv"):
        conn.execute(
            "INSERT OR REPLACE INTO service_component"
            " (component_id, family_id, display_name, raw_name, is_draft, note) VALUES (?,?,?,?,?,?)",
            (row["component_id"], row["family_id"], row["display_name"], blank(row["raw_name"]),
             int(row["is_draft"]), blank(row["note"])),
        )
    for row in _seed_rows("catalogue_items.csv"):
        conn.execute(
            "INSERT OR REPLACE INTO catalogue_item (catalogue_item_id, component_id, action_id,"
            " default_board_id, default_scope_item_id, default_contract_basis, clinical_impact,"
            " min_priority, restricted, is_draft, note) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (row["catalogue_item_id"], row["component_id"], row["action_id"], row["default_board_id"],
             blank(row["default_scope_item_id"]), row["default_contract_basis"],
             int(row["clinical_impact"]), blank(row["min_priority"]),
             int(row["restricted"]), int(row["is_draft"]), blank(row["note"])),
        )
    for row in _seed_rows("clinical_floors.csv"):
        conn.execute(
            "INSERT OR REPLACE INTO clinical_floor"
            " (floor_id, description, priority, status, signed_off_by, signed_off_on) VALUES (?,?,?,?,?,?)",
            (row["floor_id"], row["description"], row["priority"], row["status"],
             blank(row["signed_off_by"]), blank(row["signed_off_on"])),
        )
    for row in _seed_rows("sla_targets.csv"):
        conn.execute(
            "INSERT OR REPLACE INTO sla_target (board_id, priority, clock, target_minutes,"
            " calendar, attainment_percent, enforced, note) VALUES (?,?,?,?,?,?,?,?)",
            (row["board_id"], row["priority"], row["clock"], int(row["target_minutes"]),
             row["calendar"], float(row["attainment_percent"]) if row["attainment_percent"] else None,
             int(row["enforced"]), blank(row["note"])),
        )


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

"""Open, create and seed the spine database.

Two stores, one code. SQLite is the pilot's: no server, no provisioning, one
file escrowed nightly through SQLite's backup API (not a copy, because the
database runs in WAL mode; see create()). SQL Server is D7's (25 Sep 2026): the
desk on the instance PMC already runs, in a database of its own, opened with an
ODBC connection string in place of a path. Which one is in use is decided by
the shape of the target string and by nothing else; every module above this
one speaks sqlite3's dialect and surface, and psaspine/mssql.py makes SQL Server
answer to both.
"""
from __future__ import annotations

import csv
import sqlite3
from pathlib import Path

from . import mssql

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_DIR = ROOT / "schema"
SEED_DIR = ROOT / "seed"


# How long a writer waits for another writer before giving up, in seconds. The
# default is to fail at once with "database is locked", which on a desk with
# more than one person working is an error nobody caused and everybody sees.
BUSY_TIMEOUT_SECONDS = 5.0


def backend_of(target) -> str:
    """'mssql' for an ODBC connection string, 'sqlite' for a path."""
    return "mssql" if mssql.is_connection_string(target) else "sqlite"


def connect(path: str | Path):
    """One connection to whichever store the target names.

    SQLite: foreign keys are off by default and the setting is per connection,
    so it is set on every one; so is the busy timeout.

    `synchronous` is deliberately left at SQLite's default (FULL). NORMAL is
    faster and can lose the last committed transaction on a power cut -- a
    trade to make only once the host is known to be on a UPS, and not one to
    make quietly on a clinical desk. (sqlite.org/pragma.html#pragma_synchronous)
    """
    if backend_of(path) == "mssql":
        return mssql.connect(str(path))
    conn = sqlite3.connect(str(path), timeout=BUSY_TIMEOUT_SECONDS)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def backend(conn) -> str:
    return getattr(conn, "backend", "sqlite")


def close(conn) -> None:
    """Close, letting SQLite refresh its query-planner statistics first.

    sqlite.org recommends `PRAGMA optimize` when a short-lived connection
    closes, which is exactly how the web tier uses them (one per request). It
    is cheap when there is nothing to do.
    """
    if backend(conn) == "sqlite":
        try:
            conn.execute("PRAGMA optimize")
        except sqlite3.Error:
            pass
    conn.close()


def table_exists(conn, name: str) -> bool:
    if backend(conn) == "mssql":
        return mssql.table_exists(conn, name)
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
                        (name,)).fetchone() is not None


# The tables whose row counts must match between the live database and an escrow
# copy for the copy to be called good. The commercial record and the desk.
ESCROW_CHECK_TABLES = ("work_item", "ticket", "ticket_event", "time_entry",
                       "variation", "audit_event")


def backup(src_path: str | Path, dest_path: str | Path) -> dict:
    """Escrow copy of a live database, taken the only safe way under WAL.

    A copy of the .db file alone can miss commits that still live in the -wal
    file; SQLite's online backup API copies a consistent snapshot even while
    the desk is writing. Three refusals and one proof:

      * refuses to overwrite an existing file -- a backup that replaces another
        backup halves the number of backups;
      * refuses to back a database up onto itself;
      * refuses a source that does not exist, rather than creating an empty one;
      * proves the copy: PRAGMA integrity_check must say 'ok', and the row
        counts of the commercial and desk tables must equal the source's.

    The copy is left in DELETE journal mode, so the escrow is ONE self-contained
    file that can be moved to client-controlled storage as it is.
    """
    import hashlib

    if backend_of(src_path) == "mssql":
        raise ValueError("a SQL Server desk is backed up by SQL Server: BACKUP DATABASE on the "
                         "instance, on the schedule the handoff sets; this command is for the "
                         "SQLite file")
    src = Path(src_path)
    dest = Path(dest_path)
    if not src.is_file():
        raise FileNotFoundError(f"no database at {src}; nothing was written")
    if dest.exists():
        raise FileExistsError(
            f"{dest} already exists; a backup that overwrites another halves the "
            "number of backups")
    if dest.resolve() == src.resolve():
        raise ValueError("refusing to back a database up onto itself")

    live = connect(src)
    copy = sqlite3.connect(str(dest))
    try:
        live.backup(copy)
        copy.execute("PRAGMA journal_mode = DELETE")
        integrity = copy.execute("PRAGMA integrity_check").fetchone()[0]
        counts = {}
        for table in ESCROW_CHECK_TABLES:
            a = live.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            b = copy.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            counts[table] = (a, b)
    finally:
        copy.close()
        close(live)

    mismatched = {t: c for t, c in counts.items() if c[0] != c[1]}
    ok = integrity == "ok" and not mismatched
    digest = hashlib.sha256(dest.read_bytes()).hexdigest()
    return {"ok": ok, "integrity": integrity, "mismatched": mismatched,
            "counts": {t: c[1] for t, c in counts.items()},
            "bytes": dest.stat().st_size, "sha256": digest, "path": str(dest)}


def create(conn, *, any_database: bool = False) -> None:
    """Apply every migration in name order, in write-ahead-log mode.

    WAL lets readers carry on while one writer commits, which is what a desk
    with several people on it needs. It persists in the file, so it is set once,
    here. It has one consequence worth stating: recent commits can live in the
    `-wal` file beside the database until a checkpoint, so **the nightly escrow
    must use SQLite's backup API (`Connection.backup`) or checkpoint first -- a
    plain copy of the .db file alone can drop the latest commits.**

    schema/*.sql is the one schema, and the SQL Server port is generated from it;
    schema/local/ (the credential tables) is in both since D7 put the desk on
    SQL Server. On SQL Server this applies the generated port, every object of
    which is guarded, so on a database that already has the schema it changes
    nothing.
    """
    if backend(conn) == "mssql":
        mssql.apply_port(conn, any_database=any_database)
        return
    conn.execute("PRAGMA journal_mode = WAL")
    for sql_file in sorted(SCHEMA_DIR.glob("*.sql")):
        conn.executescript(sql_file.read_text(encoding="utf-8"))
    for sql_file in sorted((SCHEMA_DIR / "local").glob("*.sql")):
        conn.executescript(sql_file.read_text(encoding="utf-8"))
    conn.commit()


def _seed_rows(name: str) -> list[dict]:
    with (SEED_DIR / name).open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def _sample_rows(name: str) -> list[dict]:
    """Rows from seed/sample/ — never loaded unless somebody asks for them."""
    with (SEED_DIR / "sample" / name).open(encoding="utf-8-sig", newline="") as fh:
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
    # D4: one ticket sequence for the whole hospital. The prefix is a row rather
    # than a constant because §12 says configuration PMC cannot change without a
    # deployment is in the wrong place. Exactly one row, and the CHECK enforces
    # it, so there is never a question of which prefix is in force.
    conn.execute(
        "INSERT OR IGNORE INTO ticket_numbering (id, prefix, padding)"
        " VALUES (1, 'PMC', 6)")
    seed_catalogue(conn)
    conn.commit()


def seed_catalogue(conn: sqlite3.Connection) -> None:
    """Create the first board, and nothing else.

    Dada's direction, 9 Sep 2026: a PSA does not arrive with boards in it. You
    get the setup tables and you create the boards you are ready to run. So this
    seeds ONE board -- the one Dada IT already answers -- and the catalogue,
    the verbs, the floors and the SLA targets start empty.

    What was here before was sixteen boards and fifty-one catalogue items
    reverse-engineered from a workbook exported out of the desk in use today.
    That workbook is a sample of how somebody once configured a different
    system, not a model of how PMC works, and seeding it would have made
    somebody else's guesses look like PMC's decisions the first time anyone
    opened the database.

    It is kept, under seed/sample/, and loaded only by seed_sample() when a
    test or a demo asks for it. Nothing loads it by default.
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
    conn.commit()


def seed_sample(conn: sqlite3.Connection) -> None:
    """Load seed/sample/ -- the workbook-derived catalogue, boards and targets.

    NOT loaded by init(). This is a sample of how a different system was once
    configured, useful for exercising the importer and the reports against
    something shaped like real data. It is not PMC's configuration and must not
    be presented as one.
    """
    def blank(v):
        return v if (v or "").strip() else None

    for row in _sample_rows("boards.csv"):
        conn.execute(
            "INSERT OR REPLACE INTO board (board_id, display_name, phase, fulfiller_group,"
            " owner, deputy, restricted, is_live, is_unrouted, note)"
            " VALUES (?,?,?,?,?,?,?,?,?,?)",
            (row["board_id"], row["display_name"], row["phase"], row["fulfiller_group"],
             blank(row["owner"]), blank(row["deputy"]), int(row["restricted"]),
             int(row["is_live"]), int(row["is_unrouted"]), blank(row["note"])),
        )
    for row in _sample_rows("service_actions.csv"):
        conn.execute(
            "INSERT OR REPLACE INTO service_action"
            " (action_id, display_name, raw_name, kind, implies_impact, note) VALUES (?,?,?,?,?,?)",
            (row["action_id"], row["display_name"], blank(row["raw_name"]), row["kind"],
             blank(row["implies_impact"]), blank(row["note"])),
        )
    for row in _sample_rows("service_families.csv"):
        conn.execute(
            "INSERT OR REPLACE INTO service_family (family_id, display_name, raw_name, note)"
            " VALUES (?,?,?,?)",
            (row["family_id"], row["display_name"], blank(row["raw_name"]), blank(row["note"])),
        )
    for row in _sample_rows("service_components.csv"):
        conn.execute(
            "INSERT OR REPLACE INTO service_component"
            " (component_id, family_id, display_name, raw_name, is_draft, note) VALUES (?,?,?,?,?,?)",
            (row["component_id"], row["family_id"], row["display_name"], blank(row["raw_name"]),
             int(row["is_draft"]), blank(row["note"])),
        )
    for row in _sample_rows("catalogue_items.csv"):
        conn.execute(
            "INSERT OR REPLACE INTO catalogue_item (catalogue_item_id, component_id, action_id,"
            " default_board_id, default_scope_item_id, default_contract_basis, clinical_impact,"
            " min_priority, restricted, is_draft, note) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (row["catalogue_item_id"], row["component_id"], row["action_id"], row["default_board_id"],
             blank(row["default_scope_item_id"]), row["default_contract_basis"],
             int(row["clinical_impact"]), blank(row["min_priority"]),
             int(row["restricted"]), int(row["is_draft"]), blank(row["note"])),
        )
    for row in _sample_rows("clinical_floors.csv"):
        conn.execute(
            "INSERT OR REPLACE INTO clinical_floor"
            " (floor_id, description, priority, status, signed_off_by, signed_off_on) VALUES (?,?,?,?,?,?)",
            (row["floor_id"], row["description"], row["priority"], row["status"],
             blank(row["signed_off_by"]), blank(row["signed_off_on"])),
        )
    for row in _sample_rows("sla_targets.csv"):
        conn.execute(
            "INSERT OR REPLACE INTO sla_target (board_id, priority, clock, target_minutes,"
            " calendar, attainment_percent, enforced, note) VALUES (?,?,?,?,?,?,?,?)",
            (row["board_id"], row["priority"], row["clock"], int(row["target_minutes"]),
             row["calendar"], float(row["attainment_percent"]) if row["attainment_percent"] else None,
             int(row["enforced"]), blank(row["note"])),
        )
    for row in _sample_rows("sla_targets_by_type.csv"):
        conn.execute(
            "INSERT OR REPLACE INTO sla_target_type (board_id, record_type, priority, clock,"
            " target_minutes, calendar, attainment_percent, enforced, note)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            (row["board_id"], row["record_type"], row["priority"], row["clock"],
             int(row["target_minutes"]), row["calendar"],
             float(row["attainment_percent"]) if row["attainment_percent"] else None,
             int(row["enforced"]), blank(row["note"])),
        )


def init(path: str | Path, *, reset: bool = False):
    """Create the schema where it is missing and seed the reference rows.

    `reset` empties a SQL Server database first so a test starts from nothing;
    it is refused for SQLite, whose tests get a fresh file, and refused by the
    CLI, which never passes it."""
    conn = connect(path)
    if reset:
        if backend(conn) != "mssql":
            raise ValueError("reset is for a SQL Server test database only")
        create(conn, any_database=True)
        mssql.wipe(conn)
    else:
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

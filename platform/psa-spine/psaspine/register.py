"""Import the workstream register CSV into the spine, losslessly.

The register is the de-facto projects table today: one CSV, hand-edited, with
free-text cells thousands of characters long. Importing it is where a naive
transform quietly loses rows, and the standing rule in this programme is that
flags are COUNTED, never filtered out. So:

  * every input row produces exactly one work item — no row is ever dropped;
  * anything that cannot be classified is recorded as a data-quality finding
    and still imported;
  * compound scope values ('2->8', '3+5', '1/2') become two links each, never
    silently reduced to their first element;
  * the original cell text is kept alongside every normalised value.

The register itself is NOT in this repository: it carries internal network
addresses and at least one filename on the record's inventory denylist. It is
read at runtime from a path given on the command line.
"""
from __future__ import annotations

import csv
import hashlib
import re
import sqlite3
from pathlib import Path

from . import db

# The register's own vocabulary, mapped to the spine's.
ENTITY_MAP = {
    "PMC": "PMC",
    "JRBY": "JRBY-CI",
    "JRBY-CI": "JRBY-CI",
    "DADA IT": "DADA-IT",
    "UNCLASSIFIED": "UNCLASSIFIED",
}

STATUS_CANON = {"DONE", "IN-PROGRESS", "BLOCKED", "BUILT-NOT-RUN"}

# A compound scope cell joins two items. The separator carries meaning, so it is
# preserved as the relation rather than thrown away.
COMPOUND = {"->": "SUCCEEDS", "+": "SECONDARY", "/": "ALTERNATIVE"}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalise_basis(raw: str) -> str:
    """'variation', 'variation (Amendment 1)' -> VARIATION; 'baseline' -> BASELINE.

    The parenthesised form is the row an exact-match filter drops. That single
    row is a whole covered entity, so this function exists to make the mistake
    impossible rather than to be remembered.
    """
    text = (raw or "").strip().lower()
    if text.startswith("variation"):
        return "VARIATION"
    if text.startswith("baseline"):
        return "BASELINE"
    return "UNKNOWN"


def normalise_status(raw: str) -> str:
    """'DONE (filed; execution unverified)' -> DONE, keeping the qualifier as raw."""
    head = re.split(r"\s*\(", (raw or "").strip(), maxsplit=1)[0].strip().upper()
    return head if head in STATUS_CANON else (head or "UNKNOWN")


def parse_scope(raw: str) -> tuple[list[tuple[str, str]], str | None]:
    """Return ([(scope_item_id, relation), ...], unresolved_reason)."""
    text = (raw or "").strip()
    if not text or text == "?":
        return [], "scope item not stated"
    for sep, relation in COMPOUND.items():
        if sep in text:
            parts = [p.strip() for p in text.split(sep) if p.strip()]
            if len(parts) >= 2:
                links = [(parts[0], "PRIMARY")] + [(p, relation) for p in parts[1:]]
                return links, None
    return [(text, "PRIMARY")], None


def derive_lane(status: str, risk: str | None, next_action_by: str | None) -> str:
    """Which lane the item sits in — the programme is run by who must act next.

    INFERRED from the register's own four-lane description, not stated in it.
    """
    actor = (next_action_by or "").strip().lower()
    if status == "BLOCKED":
        return "C-chase"                       # waiting on the client
    if status == "BUILT-NOT-RUN":
        return "B-finish-what-is-built"
    if risk == "H" and actor == "dada":
        return "A-stop-the-bleeding"
    if status == "DONE":
        return "D-done"
    return "D-run"


def split_evidence(raw: str) -> list[tuple[str, str]]:
    """Split the evidence cell and classify each reference.

    Nothing here resolves to a real document yet: the column mixes repo-relative
    paths, absolute Windows paths and parenthetical placeholders. They are
    imported verbatim and marked, so the count of unresolved references is a
    number on a report rather than a silent gap.
    """
    out: list[tuple[str, str]] = []
    for part in (raw or "").split(";"):
        ref = part.strip()
        if not ref:
            continue
        low = ref.lower()
        if low.startswith("("):
            kind = "UNRESOLVED"
        elif low.startswith("docs/"):
            kind = "DOC"
        elif low.startswith("deliverables/"):
            kind = "DELIVERABLE"
        elif low.startswith("scripts/"):
            kind = "SCRIPT"
        else:
            kind = "PATH"
        out.append((ref, kind))
    return out


def import_register(conn: sqlite3.Connection, csv_path: str | Path, *,
                    run_id: str, at: str) -> dict:
    """Import every row. Returns a summary; raises nothing on bad data."""
    path = Path(csv_path)
    with path.open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))

    known_scope = {r["scope_item_id"] for r in conn.execute("SELECT scope_item_id FROM scope_item")}
    findings: list[tuple] = []

    def flag(kind: str, sid: str | None, code: str, detail: str, severity: str) -> None:
        findings.append((run_id, kind, sid, code, detail, severity))

    for row in rows:
        wid = (row.get("id") or "").strip()
        if not wid:
            flag("work_item", None, "NO_ID", f"row without an id: {row!r:.200}", "ERROR")
            continue

        entity_raw = (row.get("entity") or "").strip()
        entity_id = ENTITY_MAP.get(entity_raw.upper())
        if entity_id is None:
            # 'PMC+JRBY' and friends: attribute to the first named entity, keep
            # the original, and flag it — it moves the review-pack entity counts.
            first = re.split(r"[+/]", entity_raw)[0].strip().upper()
            entity_id = ENTITY_MAP.get(first)
            if entity_id:
                flag("work_item", wid, "MULTI_ENTITY",
                     f"entity {entity_raw!r} attributed to {entity_id}", "WARN")
            else:
                entity_id = "UNCLASSIFIED"
                flag("work_item", wid, "UNKNOWN_ENTITY",
                     f"entity {entity_raw!r} not recognised", "ERROR")

        basis_raw = (row.get("contract_basis") or "").strip()
        basis = normalise_basis(basis_raw)
        if basis == "UNKNOWN":
            flag("work_item", wid, "UNKNOWN_BASIS",
                 f"contract_basis {basis_raw!r} is neither baseline nor variation", "ERROR")
        elif basis_raw.lower() not in ("baseline", "variation"):
            flag("work_item", wid, "QUALIFIED_BASIS",
                 f"contract_basis {basis_raw!r} normalised to {basis}", "INFO")

        status_raw = (row.get("status") or "").strip()
        status = normalise_status(status_raw)
        risk = (row.get("risk") or "").strip().upper() or None
        if risk not in ("L", "M", "H", None):
            flag("work_item", wid, "UNKNOWN_RISK", f"risk {risk!r}", "WARN")
            risk = None

        conn.execute(
            "INSERT OR REPLACE INTO work_item (work_item_id, source, name, entity_id, entity_raw,"
            " contract_basis, contract_basis_raw, status, status_raw, blocked_on, next_action,"
            " next_action_by, risk, container, last_activity, lane)"
            " VALUES (?,'register',?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (wid, (row.get("name") or "").strip(), entity_id, entity_raw, basis, basis_raw,
             status, status_raw, (row.get("blocked_on") or "").strip() or None,
             (row.get("next_action") or "").strip() or None,
             (row.get("next_action_by") or "").strip() or None,
             risk, (row.get("container") or "").strip() or None,
             (row.get("last_activity") or "").strip() or None,
             derive_lane(status, risk, row.get("next_action_by"))),
        )

        links, unresolved = parse_scope(row.get("scope_item") or "")
        if unresolved:
            flag("scope_item", wid, "SCOPE_NOT_STATED", unresolved, "ERROR")
        for scope_id, relation in links:
            if scope_id not in known_scope:
                flag("scope_item", wid, "UNKNOWN_SCOPE_ITEM",
                     f"scope value {scope_id!r} is not one of the nine items or VAR", "ERROR")
                continue
            conn.execute(
                "INSERT OR REPLACE INTO work_item_scope_item"
                " (work_item_id, scope_item_id, relation, raw) VALUES (?,?,?,?)",
                (wid, scope_id, relation, (row.get("scope_item") or "").strip()),
            )

        for ordinal, (ref, kind) in enumerate(split_evidence(row.get("evidence") or ""), start=1):
            conn.execute(
                "INSERT OR REPLACE INTO work_item_evidence (work_item_id, ordinal, raw, kind)"
                " VALUES (?,?,?,?)",
                (wid, ordinal, ref, kind),
            )
            if kind in ("PATH", "UNRESOLVED"):
                flag("evidence", wid, "UNRESOLVABLE_EVIDENCE",
                     f"reference {ref!r} does not resolve to a filed document", "WARN")

        note = (row.get("next_action") or "").strip()
        if note:
            conn.execute(
                "INSERT INTO work_item_note (work_item_id, noted_on, author, body) VALUES (?,?,?,?)",
                (wid, at, "register-import", note),
            )

    conn.executemany(
        "INSERT INTO data_quality (run_id, subject_kind, subject_id, code, detail, severity)"
        " VALUES (?,?,?,?,?,?)", findings)

    rows_out = conn.execute("SELECT COUNT(*) c FROM work_item WHERE source='register'").fetchone()["c"]
    conn.execute(
        "INSERT OR REPLACE INTO import_run (run_id, started_at, source, source_sha256, rows_in, rows_out, note)"
        " VALUES (?,?,?,?,?,?,?)",
        (run_id, at, path.name, _sha256(path), len(rows), rows_out, None),
    )
    db.audit(conn, at=at, actor="register-import", action="IMPORT",
             subject_kind="import_run", subject_id=run_id,
             detail=f"{len(rows)} rows in, {rows_out} work items out, {len(findings)} findings")
    conn.commit()
    return {"rows_in": len(rows), "rows_out": rows_out, "findings": len(findings)}

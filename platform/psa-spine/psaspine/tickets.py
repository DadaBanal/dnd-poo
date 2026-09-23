"""Import a desk export into work items and tickets, losslessly.

Modelled on register.py, and holding the same line: every input row produces
exactly one work item and exactly one ticket, anything unclassifiable is imported
AND flagged, and the CLI exits non-zero if rows in do not equal rows out. Flags
are counted, never filtered out.

**An export file, never the API.** The TeamsWork API keys were exposed in a
screenshot. The standing instruction is that neither is written down and both
should be rotated, so this module reads a file a person exported. There is no
key here, no key in the config, and nowhere to put one.

Three things this importer does that a desk cannot:

  * **It defaults the commercial columns from the catalogue.** The scope item and
    the contract basis come from `catalogue_item`, which is what lets a nurse file
    a ticket without ever seeing a commercial field.

  * **It computes the priority and never reads one.** If the export carries a
    priority it is recorded as a disagreement, not used. The requester answers two
    plain questions — who is affected, and is a patient waiting — and the rest is
    arithmetic.

  * **It refuses to classify what it cannot classify.** A row that matches no
    curated triple keeps the board the export named, takes contract basis UNKNOWN
    and no scope item, and carries an ERROR flag. With no board named it lands on
    the Unrouted queue, which is what that queue is for. Twenty-one catalogue items already seed UNKNOWN because no
    baseline heading covers PACS, imaging or medical gas; forcing a row into the
    nearest heading is the quiet reclassification the spine exists to prevent.

One thing it deliberately does NOT do: import effort. `time_entry` requires a
performer, an enterer, a charge method and an authority source, and a desk export
carries none of them reliably. Effort is banded by a person, monthly, including
for open items. An importer that invented those four fields would be inventing
the numerator of an uplift claim.
"""
from __future__ import annotations

import csv
import hashlib
import re
import sqlite3
from pathlib import Path

from . import db, itil, phi
from .register import ENTITY_MAP

# ---------------------------------------------------------------- the export
#
# Desk exports do not agree on column names, so each field lists the headers
# seen or expected. A header that matches nothing is reported once per run
# rather than quietly read as blank on every row.

FIELDS: dict[str, tuple[str, ...]] = {
    "external_ref": ("ticket", "ticket id", "ticket number", "number", "id", "ref"),
    "summary": ("summary", "subject", "title", "short description"),
    "board": ("board", "queue", "service board"),
    "type": ("type",),
    "subtype": ("subtype", "sub type"),
    "item": ("item",),
    "catalogue_item_id": ("catalogue item id", "catalogue item"),
    "company": ("company", "entity", "client", "account"),
    "status": ("status", "state"),
    "impact": ("impact",),
    "urgency": ("urgency",),
    "priority": ("priority", "severity"),
    "requested_by": ("contact", "requester", "requested by", "reported by"),
    "owner": ("owner", "resource", "assigned to", "member", "assignee"),
    "opened_at": ("date entered", "date created", "created", "opened", "entered"),
    "closed_at": ("date closed", "closed", "date resolved", "resolved"),
    "description": ("description", "initial description", "detail", "notes"),
}

# The desk's status vocabulary, mapped to the ticket state machine. A pause
# state that stops the resolve clock is the reason WAITING_* exist at all.
STATE_MAP = {
    "new": "NEW", "open": "NEW", "unassigned": "NEW",
    "triaged": "TRIAGED", "assigned": "TRIAGED", "scheduled": "TRIAGED",
    "in progress": "IN_PROGRESS", "working": "IN_PROGRESS", "active": "IN_PROGRESS",
    "waiting for client": "WAITING_CLIENT", "waiting client": "WAITING_CLIENT",
    "waiting on client": "WAITING_CLIENT", "with client": "WAITING_CLIENT",
    "waiting for vendor": "WAITING_VENDOR", "waiting vendor": "WAITING_VENDOR",
    "waiting on vendor": "WAITING_VENDOR", "with vendor": "WAITING_VENDOR",
    "resolved": "RESOLVED", "completed": "RESOLVED", "complete": "RESOLVED",
    "closed": "CLOSED", "closed complete": "CLOSED",
    "cancelled": "CANCELLED", "canceled": "CANCELLED", "duplicate": "CANCELLED",
}

# ------------------------------------------------------------------ priority
#
# INFERRED from the impact and urgency definitions in the WS36 paper, not
# measured from any system: I1 hospital-wide or a clinical service, I2 a
# department or multiple users, I3 one user; U1 patient care stopped or a safety
# or regulatory exposure now, U2 degraded with a workaround, U3 no care impact.
#
# It is written here as a table rather than as a rule so it can be argued with
# in one place. The row that will be argued with is I3/U1 — one user, patient
# waiting — which lands at P3 on the matrix and is lifted to P2 by the clinical
# floor below whenever the catalogue item says the work touches care.

MATRIX = {
    ("I1", "U1"): "P1", ("I1", "U2"): "P2", ("I1", "U3"): "P3",
    ("I2", "U1"): "P2", ("I2", "U2"): "P3", ("I2", "U3"): "P4",
    ("I3", "U1"): "P3", ("I3", "U2"): "P4", ("I3", "U3"): "P4",
}
SEVERITY = {"P1": 1, "P2": 2, "P3": 3, "P4": 4}

# The programme is run by who has to act next, so a ticket lands in the same
# four lanes a workstream does. A ticket waiting on the client is a chase, and
# a chase is where a dependency notice comes from.
LANE = {
    "NEW": "D-run", "TRIAGED": "D-run", "IN_PROGRESS": "D-run",
    "WAITING_CLIENT": "C-chase", "WAITING_VENDOR": "D-run",
    "RESOLVED": "D-done", "CLOSED": "D-done", "CANCELLED": "D-done",
}


def compute_priority(impact: str, urgency: str, *, min_priority: str | None = None,
                     clinical_impact: int = 0) -> tuple[str, str]:
    """The whole priority rule, in one place. Returns (priority, source).

        priority = LEAST( matrix(impact, urgency),
                          catalogue_item.min_priority,
                          P2 when catalogue_item.clinical_impact = 1 )

    LEAST is by severity, so P1 wins. A floor that does not actually raise the
    priority does not get the credit for it: the source stays MATRIX, because
    the source is what a fulfiller will be shown when they ask why.

    No clinical_floor row is consulted. All four seed PROPOSED, none is signed
    by the Chief of Hospital, the Chief Nurse and the Quality officer, and an
    unsigned floor does not bind. When one is signed it will bind through the
    catalogue, not through this function guessing which tickets it covers.
    """
    candidates = [(MATRIX[(impact, urgency)], "MATRIX")]
    if min_priority:
        candidates.append((min_priority, "CATALOGUE_FLOOR"))
    if clinical_impact:
        candidates.append(("P2", "CLINICAL_IMPACT"))
    return min(candidates, key=lambda c: SEVERITY[c[0]])


# ------------------------------------------------------------- normalising

def _key(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def map_headers(fieldnames: list[str]) -> tuple[dict[str, str], list[str]]:
    """Return ({field: actual header}, [fields with no column])."""
    seen = {_key(name): name for name in (fieldnames or [])}
    found, missing = {}, []
    for field, aliases in FIELDS.items():
        for alias in aliases:
            if alias in seen:
                found[field] = seen[alias]
                break
        else:
            missing.append(field)
    return found, missing


def normalise_state(raw: str) -> tuple[str, bool]:
    """Return (state, recognised). An unrecognised status is never dropped."""
    text = _key(raw)
    if text in STATE_MAP:
        return STATE_MAP[text], True
    return "NEW", False


def normalise_axis(raw: str) -> str | None:
    """'I1', 'i-1', '1 - Hospital wide' -> 'I1'. Anything else -> None."""
    text = _key(raw)
    m = re.match(r"^[iu]?\s*([123])\b", text)
    return m.group(1) if m else None


# ------------------------------------------------------------- the catalogue

def catalogue_lookup(conn: sqlite3.Connection) -> dict:
    """Every way a catalogue item can be named, mapped to its row.

    The source workbook contains ten misspellings, which is why every component
    and every verb carries a raw_name beside its display name. Both are indexed
    here: an export written against the old spelling still lands on the right
    item instead of on the Unrouted board.
    """
    components: dict[str, str] = {}
    for row in conn.execute("SELECT component_id, display_name, raw_name FROM service_component"):
        for name in (row["component_id"], row["display_name"], row["raw_name"]):
            if name:
                components.setdefault(_key(name), row["component_id"])
    actions: dict[str, str] = {}
    for row in conn.execute("SELECT action_id, display_name, raw_name FROM service_action"):
        for name in (row["action_id"], row["display_name"], row["raw_name"]):
            if name:
                actions.setdefault(_key(name), row["action_id"])
    items = {
        (row["component_id"], row["action_id"]): row
        for row in conn.execute("SELECT * FROM catalogue_item")
    }
    by_id = {row["catalogue_item_id"]: row for row in conn.execute("SELECT * FROM catalogue_item")}
    return {"components": components, "actions": actions, "items": items, "by_id": by_id}


def resolve_catalogue_item(lookup: dict, *, catalogue_item_id: str, subtype: str,
                           item: str, type_: str) -> sqlite3.Row | None:
    """Place a row on the catalogue, or return None and let the caller flag it.

    Sheet3's structure wins: the Type axis is the board, so subtype names the
    component and item names the verb. Type is tried last, and only as a
    component, for exports that never had a subtype column at all.
    """
    if catalogue_item_id and catalogue_item_id in lookup["by_id"]:
        return lookup["by_id"][catalogue_item_id]
    component = lookup["components"].get(_key(subtype)) or lookup["components"].get(_key(type_))
    action = lookup["actions"].get(_key(item))
    if component and action:
        return lookup["items"].get((component, action))
    return None


# ---------------------------------------------------------------- the import

def import_tickets(conn: sqlite3.Connection, export_path: str | Path, *,
                   run_id: str, at: str) -> dict:
    """Import every row of a desk export. Returns a summary; raises on nothing."""
    path = Path(export_path)
    with path.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        headers, missing = map_headers(reader.fieldnames)
        rows = list(reader)

    lookup = catalogue_lookup(conn)
    # An export names a board the way a person reads it -- "IT Service Request",
    # not IT_REQUEST -- so both are indexed. A board it still cannot place is a
    # warning and the catalogue's default board, never a new board invented here.
    boards: dict[str, str] = {}
    for r in conn.execute("SELECT board_id, display_name FROM board"):
        boards[_key(r["board_id"])] = r["board_id"]
        boards[_key(r["display_name"])] = r["board_id"]
    unrouted = conn.execute(
        "SELECT board_id FROM board WHERE is_unrouted = 1").fetchone()
    unrouted_id = unrouted["board_id"] if unrouted else "UNROUTED"

    findings: list[tuple] = []

    def flag(kind: str, sid: str | None, code: str, detail: str, severity: str) -> None:
        findings.append((run_id, kind, sid, code, detail, severity))

    for field in missing:
        flag("export", None, "COLUMN_ABSENT",
             f"the export has no column for {field!r}; every row is read as blank there",
             "WARN" if field in ("impact", "urgency", "priority", "catalogue_item_id",
                                 "description", "closed_at") else "ERROR")

    # No floor is signed, so no floor binds. Say so once a run rather than
    # letting silence be read as "the floors are working".
    proposed = conn.execute(
        "SELECT COUNT(*) c FROM clinical_floor WHERE status = 'PROPOSED'").fetchone()["c"]
    if proposed:
        flag("clinical_floor", None, "FLOOR_NOT_SIGNED",
             f"{proposed} clinical floors are PROPOSED and none is signed by the Chief of "
             f"Hospital, the Chief Nurse and the Quality officer, so none was applied to "
             f"any priority in this run", "WARN")

    def cell(row: dict, field: str) -> str:
        header = headers.get(field)
        return (row.get(header) or "").strip() if header else ""

    used_ids: set[str] = set()
    imported = 0

    for lineno, row in enumerate(rows, start=2):      # line 1 is the header
        source_ref = f"{run_id}:{lineno}"
        external = cell(row, "external_ref")

        # A row with no reference is still a row. It gets an id derived from
        # where it sat in the file, so the count survives and the gap is loud.
        wid = external or f"DESK-{run_id}-{lineno}"
        if not external:
            flag("work_item", wid, "NO_TICKET_REFERENCE",
                 f"export row {lineno} carries no ticket reference; imported under {wid!r}",
                 "ERROR")
        if wid in used_ids:
            original, n = wid, 2
            while f"{original}#{n}" in used_ids:
                n += 1
            wid = f"{original}#{n}"
            flag("work_item", wid, "DUPLICATE_REFERENCE",
                 f"ticket reference {original!r} appears more than once in this export; "
                 f"the later row is imported as {wid!r} rather than overwriting the first",
                 "ERROR")
        used_ids.add(wid)

        # ------------------------------------------------------------- entity
        entity_raw = cell(row, "company")
        entity_id = ENTITY_MAP.get(entity_raw.upper())
        if entity_id is None:
            first = re.split(r"[+/]", entity_raw)[0].strip().upper()
            entity_id = ENTITY_MAP.get(first)
            if entity_id:
                flag("work_item", wid, "MULTI_ENTITY",
                     f"company {entity_raw!r} attributed to {entity_id}", "WARN")
            else:
                entity_id = "UNCLASSIFIED"
                flag("work_item", wid, "UNKNOWN_ENTITY",
                     f"company {entity_raw!r} is not a covered entity", "ERROR")

        # ---------------------------------------------------------- catalogue
        catalogue = resolve_catalogue_item(
            lookup,
            catalogue_item_id=cell(row, "catalogue_item_id"),
            subtype=cell(row, "subtype"),
            item=cell(row, "item"),
            type_=cell(row, "type"),
        )
        if catalogue is None:
            flag("catalogue_item", wid, "UNKNOWN_CATALOGUE_ITEM",
                 f"type/subtype/item {cell(row, 'type')!r}/{cell(row, 'subtype')!r}/"
                 f"{cell(row, 'item')!r} matches no curated triple. The ticket is "
                 f"imported with contract basis UNKNOWN and no scope item, and lands "
                 f"on {unrouted_id} unless the export named a board", "ERROR")

        basis = catalogue["default_contract_basis"] if catalogue else "UNKNOWN"
        scope_item_id = catalogue["default_scope_item_id"] if catalogue else None
        if basis == "UNKNOWN":
            flag("work_item", wid, "UNKNOWN_BASIS",
                 "contract basis is UNKNOWN: nobody has ruled whether this work sits "
                 "inside a baseline heading, so it is neither claimable nor absorbed",
                 "ERROR")

        # ------------------------------------------------------------- board
        board_raw = cell(row, "board")
        board_id = boards.get(_key(board_raw))
        if board_id is None:
            if board_raw:
                flag("ticket", wid, "UNKNOWN_BOARD",
                     f"board {board_raw!r} is not a seeded board; filed on the "
                     f"catalogue's default board instead", "WARN")
            board_id = catalogue["default_board_id"] if catalogue else unrouted_id

        # ---------------------------------------------- impact, urgency, path
        impact_digit = normalise_axis(cell(row, "impact"))
        if impact_digit:
            impact = f"I{impact_digit}"
        elif catalogue:
            implied = conn.execute(
                "SELECT implies_impact FROM service_action WHERE action_id = ?",
                (catalogue["action_id"],)).fetchone()
            impact = (implied and implied["implies_impact"]) or "I3"
            flag("ticket", wid, "IMPACT_NOT_STATED",
                 f"impact not stated; taken as {impact} from the action verb", "INFO")
        else:
            impact = "I3"
            flag("ticket", wid, "IMPACT_NOT_STATED",
                 "impact not stated and no catalogue item to imply one; taken as I3, "
                 "the lowest, so the import never inflates a priority", "WARN")

        urgency_digit = normalise_axis(cell(row, "urgency"))
        if urgency_digit:
            urgency = f"U{urgency_digit}"
        else:
            urgency = "U3"
            flag("ticket", wid, "URGENCY_NOT_STATED",
                 "urgency not stated; taken as U3, the lowest. Nobody asked the "
                 "requester whether a patient was waiting", "WARN")

        priority, priority_source = compute_priority(
            impact, urgency,
            min_priority=catalogue["min_priority"] if catalogue else None,
            clinical_impact=catalogue["clinical_impact"] if catalogue else 0)

        stated = cell(row, "priority")
        desk_says = re.search(r"[1-4]", stated)
        if desk_says and f"P{desk_says.group(0)}" != priority:
            flag("ticket", wid, "PRIORITY_DISAGREES",
                 f"the desk records priority {stated!r}; this spine computes {priority} "
                 f"from impact {impact} and urgency {urgency} ({priority_source}). "
                 f"The computed value is used; the desk's is evidence, not input", "INFO")

        # The ITIL class from the item (the desk export has no column for it);
        # the commercial path from that and the basis, as open_ticket does.
        record_type = itil.of_item(conn, catalogue)
        if catalogue is not None and record_type is None:
            record_type = "SERVICE_REQUEST"          # an action of no known kind
        path_kind = itil.derive_path(record_type, basis if catalogue is not None else None)

        # --------------------------------------------------------- the state
        status_raw = cell(row, "status")
        state, recognised = normalise_state(status_raw)
        if not recognised:
            flag("ticket", wid, "UNKNOWN_STATUS",
                 f"desk status {status_raw!r} is not a state this spine knows; imported "
                 f"as NEW and kept verbatim on the ticket's event log", "WARN")

        opened_at = cell(row, "opened_at") or at
        if not cell(row, "opened_at"):
            flag("ticket", wid, "OPENED_NOT_STATED",
                 f"no opened date in the export; taken as the import date {at}", "WARN")
        closed_at = cell(row, "closed_at") or None

        # A ticket that arrives already closed on the variation path never
        # passes through the close trigger, because it is an INSERT and the
        # trigger guards an UPDATE. That is deliberate -- history has to be
        # importable as it was -- so the gap is carried as a finding instead,
        # and it is exactly the list somebody owes a decision on.
        if path_kind == "VARIATION" and state in ("RESOLVED", "CLOSED"):
            flag("ticket", wid, "CLOSED_WITH_NO_VARIATION",
                 "arrived from the desk already closed on the variation path with no "
                 "variation attached. Imported as it was; the effort on it cannot reach "
                 "an uplift claim until a variation is raised for it", "ERROR")

        # §6.1: PHI arrives in ticket text and nothing today stops it — a
        # measured message on 9 Sep carried a named patient and a PhilHealth case
        # number on the same queue as printer faults. Detected here and flagged,
        # never dropped and never rewritten: the row imports as it was sent, and
        # the finding names the shape without repeating the identifier.
        for code, severity, detail in phi.scan_fields({
                "summary": cell(row, "summary"),
                "description": cell(row, "description")}):
            flag("ticket", wid, code, detail, severity)

        # ------------------------------------------------------------- write
        conn.execute(
            "INSERT OR REPLACE INTO work_item (work_item_id, source, name, entity_id,"
            " entity_raw, contract_basis, contract_basis_raw, status, status_raw, lane)"
            " VALUES (?,'desk',?,?,?,?,?,?,?,?)",
            (wid, cell(row, "summary") or f"(no summary, export row {lineno})",
             entity_id, entity_raw or None, basis,
             (f"defaulted from catalogue item {catalogue['catalogue_item_id']}"
              if catalogue else None),
             state, status_raw or None, LANE[state]),
        )
        conn.execute(
            "INSERT OR REPLACE INTO ticket (work_item_id, external_ref, board_id,"
            " catalogue_item_id, path, impact, urgency, priority, priority_source,"
            " requested_by, requested_at, owner, opened_at, closed_at, state, source_ref,"
            " intake_source, record_type) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'IMPORT',?)",
            (wid, external or None, board_id,
             catalogue["catalogue_item_id"] if catalogue else None,
             path_kind, impact, urgency, priority, priority_source,
             cell(row, "requested_by") or None, opened_at,
             cell(row, "owner") or None, opened_at, closed_at, state, source_ref,
             record_type),
        )

        if scope_item_id:
            conn.execute(
                "INSERT OR REPLACE INTO work_item_scope_item"
                " (work_item_id, scope_item_id, relation, raw) VALUES (?,?,'PRIMARY',?)",
                (wid, scope_item_id,
                 f"defaulted from catalogue item {catalogue['catalogue_item_id']}"))

        # Everything the desk said, kept verbatim, append-only. The spine
        # normalises for reporting and never for the record.
        conn.execute(
            "INSERT INTO ticket_event (work_item_id, occurred_at, kind, actor, detail)"
            " VALUES (?,?,'IMPORTED','desk-import',?)",
            (wid, at,
             f"row {lineno} of {path.name}: ref={external!r} board={cell(row, 'board')!r} "
             f"type={cell(row, 'type')!r} subtype={cell(row, 'subtype')!r} "
             f"item={cell(row, 'item')!r} status={status_raw!r} "
             f"priority={stated!r} impact={cell(row, 'impact')!r} "
             f"urgency={cell(row, 'urgency')!r}"))

        description = cell(row, "description")
        if description:
            conn.execute(
                "INSERT INTO work_item_note (work_item_id, noted_on, author, body)"
                " VALUES (?,?,'desk-import',?)", (wid, at, description))

        imported += 1

    conn.executemany(
        "INSERT INTO data_quality (run_id, subject_kind, subject_id, code, detail, severity)"
        " VALUES (?,?,?,?,?,?)", findings)

    rows_out = conn.execute(
        "SELECT COUNT(*) c FROM ticket WHERE source_ref LIKE ?", (f"{run_id}:%",)
    ).fetchone()["c"]

    conn.execute(
        "INSERT OR REPLACE INTO import_run (run_id, started_at, source, source_sha256,"
        " rows_in, rows_out, note) VALUES (?,?,?,?,?,?,?)",
        (run_id, at, path.name, hashlib.sha256(path.read_bytes()).hexdigest(),
         len(rows), rows_out, "desk export"))
    db.audit(conn, at=at, actor="desk-import", action="IMPORT",
             subject_kind="import_run", subject_id=run_id,
             detail=f"{len(rows)} rows in, {rows_out} tickets out, {len(findings)} findings")
    conn.commit()
    return {"rows_in": len(rows), "rows_out": rows_out,
            "findings": len(findings), "written": imported}


def open_ticket(conn: sqlite3.Connection, *, board_id: str, summary: str,
                impact: str, urgency: str, requested_by: str | None, at,
                actor: str | None = None, description: str | None = None,
                entity_id: str | None = None, owner: str | None = None,
                record_type: str | None = None, change_type: str | None = None,
                event_kind: str = "INTAKE",
                min_priority: str | None = None, source: str = "DESK",
                catalogue_item_id: str | None = None) -> str:
    """Open one ticket, the same way whichever door it came in by.

    The portal, email intake, the machine API and a fulfiller's New Ticket all
    come through here, so every ticket gets a number from the one sequence (D4),
    a priority the matrix computed rather than one somebody chose, the requester's
    words as the first Discussion note, and — through `board.admit` — the board's
    default status, a company and its SLA clocks. Four copies of this were how
    tickets came to exist with no clock at all.

    The ITIL record type is the one said, else the catalogue item's, else the
    board's default (itil.resolve), and a board that does not take it refuses.
    The commercial path is derived from it and the basis, never passed in: a
    caller-supplied path is how a variation item came to be opened as an
    INCIDENT and have effort booked against it unrefused.

    Does not commit: the caller owns the transaction, so a PHI flag or a dedup
    row written alongside lands or rolls back with the ticket.
    """
    from . import board, itil, numbering

    item = None
    if catalogue_item_id:
        item = conn.execute("SELECT * FROM catalogue_item WHERE catalogue_item_id = ?",
                            (catalogue_item_id,)).fetchone()
        if item is None:
            raise LookupError(f"no catalogue item {catalogue_item_id!r}")
    # The item's floors take part in the one priority rule (catalogue floor,
    # clinical impact); nobody chooses a priority.
    priority, priority_source = compute_priority(
        impact, urgency,
        min_priority=min_priority or (item["min_priority"] if item else None),
        clinical_impact=item["clinical_impact"] if item else 0)
    basis = item["default_contract_basis"] if item else "UNKNOWN"
    record_type = itil.resolve(conn, board_id, explicit=record_type, item=item)
    path = itil.derive_path(record_type, basis)
    if record_type == "CHANGE":
        if change_type is not None and change_type not in itil.CHANGE_TYPES:
            raise ValueError(f"unknown change type {change_type!r}")
        change_type = change_type or "NORMAL"      # the safe default: it needs approval
    else:
        change_type = None
    ticket_id = numbering.issue(conn, at=at)
    stamp = at.isoformat(sep=" ", timespec="minutes")
    conn.execute(
        "INSERT INTO work_item (work_item_id, source, name, entity_id, contract_basis,"
        " contract_basis_raw) VALUES (?,'desk',?,?,?,?)",
        (ticket_id, summary, entity_id, basis,
         f"defaulted from catalogue item {item['catalogue_item_id']}" if item else None))
    if item and item["default_scope_item_id"]:
        conn.execute("INSERT OR IGNORE INTO work_item_scope_item (work_item_id, scope_item_id,"
                     " relation, raw) VALUES (?,?,'PRIMARY',?)",
                     (ticket_id, item["default_scope_item_id"],
                      f"defaulted from catalogue item {item['catalogue_item_id']}"))
    conn.execute(
        "INSERT INTO ticket (work_item_id, board_id, catalogue_item_id, path, impact, urgency,"
        " priority, priority_source, requested_by, requested_at, owner, opened_at, state,"
        " intake_source, record_type, change_type)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,'NEW',?,?,?)",
        (ticket_id, board_id, catalogue_item_id, path, impact, urgency, priority,
         priority_source, requested_by, stamp, owner, stamp, source, record_type, change_type))
    numbering.bind(conn, ticket_id)
    if description:
        conn.execute(
            "INSERT INTO ticket_event (work_item_id, occurred_at, kind, actor, detail,"
            " note_flag) VALUES (?,?,?,?,?,'DISCUSSION')",
            (ticket_id, stamp, event_kind, actor or requested_by, description))
    board.admit(conn, ticket_id, at=at)
    from . import workflow
    workflow.fire(conn, ticket_id, "ON_CREATE", at=at)
    from . import outbox
    outbox.queue_requester(conn, ticket_id, "OPENED", at=at)
    return ticket_id

"""Configurations: the machines a ticket is about, and the links out to reach them.

Dada PSA keeps Configurations under each company; a ticket lists the ones it
concerns, and from a configuration a technician launches the remote-support
session in one click. Here:

  * **Computers come from AD.** `scripts/Export-PmcAdComputers.ps1` reads AD's
    computer objects and changes nothing; `import_ad_computers` upserts them by
    objectGUID, the same rules as contacts: disabled is INACTIVE, never deleted;
    absence from a scoped export is not a retirement; every row is counted.
    The desk owns a configuration's type and contact once it exists: a re-import
    refreshes what AD knows (name, OS, description, last logon) and nothing else.
  * **Links out are data, not code.** An administrator writes a URL template in
    Setup, e.g. ScreenConnect's
    `https://<instance>.screenconnect.com/Host#Access/All%20Machines//{remote_session_id}/Join`
    (the shape VERIFIED from NinjaOne's and Syncro's integration docs). Values
    are URL-encoded into the template; a template may name only the fields
    listed below, must be HTTPS, and a link whose field is empty is drawn
    disabled with the reason. No instance address ships in this repository.
  * **No IP address is collected.** A machine is reached by its session, not by
    its address.

Standard library only.
"""
from __future__ import annotations

import csv
import re
import sqlite3
import urllib.parse
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path

from . import db

COLUMNS = ("ObjectGUID", "Name", "DNSHostName", "OperatingSystem",
           "OperatingSystemVersion", "Description", "Enabled", "LastLogonDate")
REQUIRED = ("ObjectGUID", "Name", "Enabled")
TYPES = ("WORKSTATION", "LAPTOP", "SERVER", "PRINTER", "NETWORK", "MOBILE", "OTHER")
STATUSES = ("ACTIVE", "INACTIVE", "RETIRED")
_GUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")

# The fields a link template may name, per kind of record. Anything else in
# braces is refused when the template is saved.
LINK_FIELDS = {
    "CONFIGURATION": ("name", "dns_name", "remote_session_id", "serial_number",
                      "ad_object_guid", "configuration_id"),
    "CONTACT": ("email", "upn", "sam_account", "display_name", "contact_id"),
}
_PLACEHOLDER = re.compile(r"\{([a-z_]+)\}")


def _guid(value: str | None) -> str | None:
    v = (value or "").strip().strip("{}").lower()
    return v if _GUID.match(v) else None


def _enabled(value: str) -> bool | None:
    v = (value or "").strip().lower()
    return True if v in ("true", "1", "yes") else False if v in ("false", "0", "no") else None


def import_ad_computers(conn: sqlite3.Connection, path: str | Path, *, entity_id: str,
                        at: datetime, actor: str = "cli") -> dict:
    """Upsert AD computer objects as configurations under one company."""
    if conn.execute("SELECT 1 FROM entity WHERE entity_id = ?", (entity_id,)).fetchone() is None:
        raise LookupError(f"no company {entity_id!r}")
    text = Path(path).read_bytes().decode("utf-8-sig")
    reader = csv.DictReader(text.splitlines())
    missing = [c for c in REQUIRED if c not in (reader.fieldnames or [])]
    if missing:
        raise ValueError("not an AD computers export: no column " + ", ".join(missing))
    stamp = at.isoformat(sep=" ", timespec="seconds")
    counts = {"rows": 0, "new": 0, "updated": 0, "unchanged": 0, "skipped": 0,
              "deactivated": 0}
    reasons: list[str] = []

    for line_no, row in enumerate(reader, start=2):
        counts["rows"] += 1
        guid = _guid(row.get("ObjectGUID"))
        enabled = _enabled(row.get("Enabled", ""))
        name = (row.get("Name") or "").strip()
        if guid is None or enabled is None or not name:
            counts["skipped"] += 1
            why = ("no usable ObjectGUID" if guid is None else
                   "Enabled is neither true nor false" if enabled is None else "no name")
            reasons.append(f"line {line_no}: {why}")
            continue
        os_name = (row.get("OperatingSystem") or "").strip() or None
        fresh = {
            "name": name,
            "dns_name": (row.get("DNSHostName") or "").strip().lower() or None,
            "os_name": os_name,
            "os_version": (row.get("OperatingSystemVersion") or "").strip() or None,
            "description": (row.get("Description") or "").strip() or None,
            "last_seen_at": (row.get("LastLogonDate") or "").strip() or None,
        }
        existing = conn.execute("SELECT * FROM configuration WHERE ad_object_guid = ?",
                                (guid,)).fetchone()
        if existing is None:
            kind = "SERVER" if os_name and "server" in os_name.lower() else "WORKSTATION"
            conn.execute(
                "INSERT INTO configuration (configuration_id, entity_id, name, config_type,"
                " status, dns_name, os_name, os_version, description, ad_object_guid, source,"
                " created_at, last_synced_at, last_seen_at)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,'AD',?,?,?)",
                ("CF-" + uuid.uuid4().hex[:12].upper(), entity_id, name, kind,
                 "ACTIVE" if enabled else "INACTIVE", fresh["dns_name"], fresh["os_name"],
                 fresh["os_version"], fresh["description"], guid, stamp, stamp,
                 fresh["last_seen_at"]))
            counts["new"] += 1
            continue

        changed = [k for k, v in fresh.items() if existing[k] != v]
        status = existing["status"]
        if status != "RETIRED":            # a retirement is the desk's decision, not AD's
            want = "ACTIVE" if enabled else "INACTIVE"
            if want != status:
                if want == "INACTIVE":
                    counts["deactivated"] += 1
                status = want
        if changed or status != existing["status"]:
            sets = "".join(f"{k} = ?, " for k in changed)
            conn.execute(f"UPDATE configuration SET {sets}status = ?, last_synced_at = ?"
                         " WHERE configuration_id = ?",
                         [fresh[k] for k in changed] + [status, stamp,
                                                         existing["configuration_id"]])
            counts["updated"] += 1
        else:
            conn.execute("UPDATE configuration SET last_synced_at = ? WHERE configuration_id = ?",
                         (stamp, existing["configuration_id"]))
            counts["unchanged"] += 1

    db.audit(conn, at=at.isoformat(sep=" ", timespec="minutes"), actor=actor,
             action="CONFIGURATION_IMPORT", subject_kind="entity", subject_id=entity_id,
             detail=(f"{counts['rows']} rows: {counts['new']} new, {counts['updated']} "
                     f"updated, {counts['unchanged']} unchanged, {counts['skipped']} skipped"))
    counts["reasons"] = reasons
    return counts


# ------------------------------------------------ types, statuses, questions (056)

TYPE_WORDS = {"WORKSTATION": "Workstation", "LAPTOP": "Laptop", "SERVER": "Server", "PRINTER": "Printer",
              "NETWORK": "Network", "MOBILE": "Mobile", "OTHER": "Other"}
STATUS_WORDS = {"ACTIVE": "Active", "INACTIVE": "Inactive", "RETIRED": "Retired"}
FIELD_TYPES = {"TEXT": "Text", "NUMBER": "Number", "DATE": "Date", "CHECKBOX": "Yes / no"}


def ensure_vocabulary(conn: sqlite3.Connection) -> None:
    """The seven types and three statuses of 021 as rows, once, each
    mapping to itself. OR IGNORE: two first requests may both find the
    table empty."""
    for i, (code, word) in enumerate(TYPE_WORDS.items()):
        conn.execute("INSERT OR IGNORE INTO configuration_type (type_id, name, maps_to, inactive, sort_order) VALUES (?,?,?,0,?)",
                     (code, word, code, i * 10))
    for i, (code, word) in enumerate(STATUS_WORDS.items()):
        conn.execute("INSERT OR IGNORE INTO configuration_status (status_id, name, maps_to, inactive, sort_order) VALUES (?,?,?,0,?)",
                     (code, word, code, i * 10))


def types(conn: sqlite3.Connection, *, all_rows: bool = False) -> list[dict]:
    ensure_vocabulary(conn)
    return [dict(r) for r in conn.execute(
        "SELECT t.*, (SELECT COUNT(*) FROM configuration_question q WHERE q.type_id = t.type_id AND q.inactive = 0) AS questions,"
        "       (SELECT COUNT(*) FROM configuration c WHERE COALESCE(c.type_id, c.config_type) = t.type_id) AS used"
        "  FROM configuration_type t" + ("" if all_rows else " WHERE t.inactive = 0") + " ORDER BY t.sort_order, t.name")]


def statuses(conn: sqlite3.Connection, *, all_rows: bool = False) -> list[dict]:
    ensure_vocabulary(conn)
    return [dict(r) for r in conn.execute(
        "SELECT s.*, (SELECT COUNT(*) FROM configuration c WHERE COALESCE(c.status_id, c.status) = s.status_id) AS used"
        "  FROM configuration_status s" + ("" if all_rows else " WHERE s.inactive = 0") + " ORDER BY s.sort_order, s.name")]


def type_names(conn: sqlite3.Connection) -> dict:
    return {r["type_id"]: r["name"] for r in types(conn, all_rows=True)}


def status_names(conn: sqlite3.Connection) -> dict:
    return {r["status_id"]: r["name"] for r in statuses(conn, all_rows=True)}


def type_word(conn: sqlite3.Connection, row) -> str:
    """The name of a configuration's type: the setup table's, else 021's word."""
    key = (row["type_id"] if "type_id" in row.keys() else None) or row["config_type"]
    return type_names(conn).get(key) or TYPE_WORDS.get(row["config_type"], row["config_type"].title())


def status_word(conn: sqlite3.Connection, row) -> str:
    key = (row["status_id"] if "status_id" in row.keys() else None) or row["status"]
    return status_names(conn).get(key) or STATUS_WORDS.get(row["status"], row["status"].title())


def _slug(name: str, prefix: str) -> str:
    base = re.sub(r"[^A-Z0-9]+", "_", (name or "").upper()).strip("_")[:40]
    return f"{prefix}_{base}" if base else prefix


def _vocab_name(name, what) -> str:
    n = " ".join(str(name or "").split())[:80]
    if not n:
        raise ValueError(f"A {what} needs a name.")
    return n


def add_type(conn: sqlite3.Connection, name: str, maps_to: str, *, at: datetime, actor: str) -> str:
    ensure_vocabulary(conn)
    n = _vocab_name(name, "type")
    if maps_to not in TYPE_WORDS:
        raise ValueError("A type counts as one of the seven kinds the reports know: workstation, laptop, server, printer, network, mobile or other.")
    if conn.execute("SELECT 1 FROM configuration_type WHERE LOWER(name) = LOWER(?)", (n,)).fetchone():
        raise ValueError("A type with that name exists.")
    tid = _slug(n, "CT")
    if conn.execute("SELECT 1 FROM configuration_type WHERE type_id = ?", (tid,)).fetchone():
        tid = tid + "_" + uuid.uuid4().hex[:4].upper()
    order = conn.execute("SELECT COALESCE(MAX(sort_order), 0) + 10 FROM configuration_type").fetchone()[0]
    conn.execute("INSERT INTO configuration_type (type_id, name, maps_to, inactive, sort_order) VALUES (?,?,?,0,?)", (tid, n, maps_to, order))
    db.audit(conn, at=at.isoformat(sep=" ", timespec="minutes"), actor=actor, action="CONFIGURATION_TYPE",
             subject_kind="configuration_type", subject_id=tid, detail=f"added {n}, counts as {maps_to}")
    return tid


def save_type(conn: sqlite3.Connection, type_id: str, *, at: datetime, actor: str, name=None, maps_to=None, inactive=None) -> str:
    row = conn.execute("SELECT * FROM configuration_type WHERE type_id = ?", (type_id,)).fetchone()
    if row is None:
        raise LookupError("No such type.")
    changes = []
    if name is not None and _vocab_name(name, "type") != row["name"]:
        changes.append(("name", _vocab_name(name, "type")))
    if maps_to is not None and maps_to != row["maps_to"]:
        if maps_to not in TYPE_WORDS:
            raise ValueError("No such kind.")
        if type_id in TYPE_WORDS:
            raise ValueError("One of the seven kinds counts as itself.")
        changes.append(("maps_to", maps_to))
    if inactive is not None and int(bool(inactive)) != row["inactive"]:
        if inactive and type_id in TYPE_WORDS:
            raise ValueError("One of the seven kinds is not retired: it is what the others count as.")
        changes.append(("inactive", int(bool(inactive))))
    for col, val in changes:
        conn.execute(f"UPDATE configuration_type SET {col} = ? WHERE type_id = ?", (val, type_id))
        if col == "maps_to":
            conn.execute("UPDATE configuration SET config_type = ? WHERE type_id = ?", (val, type_id))
    if changes:
        db.audit(conn, at=at.isoformat(sep=" ", timespec="minutes"), actor=actor, action="CONFIGURATION_TYPE",
                 subject_kind="configuration_type", subject_id=type_id, detail="; ".join(f"{c} -> {v}" for c, v in changes))
    return "saved" if changes else "nothing changed"


def add_status(conn: sqlite3.Connection, name: str, maps_to: str, *, at: datetime, actor: str) -> str:
    ensure_vocabulary(conn)
    n = _vocab_name(name, "status")
    if maps_to not in STATUS_WORDS:
        raise ValueError("A status counts as active, inactive or retired.")
    if conn.execute("SELECT 1 FROM configuration_status WHERE LOWER(name) = LOWER(?)", (n,)).fetchone():
        raise ValueError("A status with that name exists.")
    sid = _slug(n, "CS")
    if conn.execute("SELECT 1 FROM configuration_status WHERE status_id = ?", (sid,)).fetchone():
        sid = sid + "_" + uuid.uuid4().hex[:4].upper()
    order = conn.execute("SELECT COALESCE(MAX(sort_order), 0) + 10 FROM configuration_status").fetchone()[0]
    conn.execute("INSERT INTO configuration_status (status_id, name, maps_to, inactive, sort_order) VALUES (?,?,?,0,?)", (sid, n, maps_to, order))
    db.audit(conn, at=at.isoformat(sep=" ", timespec="minutes"), actor=actor, action="CONFIGURATION_STATUS",
             subject_kind="configuration_status", subject_id=sid, detail=f"added {n}, counts as {maps_to}")
    return sid


def save_status(conn: sqlite3.Connection, status_id: str, *, at: datetime, actor: str, name=None, inactive=None) -> str:
    row = conn.execute("SELECT * FROM configuration_status WHERE status_id = ?", (status_id,)).fetchone()
    if row is None:
        raise LookupError("No such status.")
    changes = []
    if name is not None and _vocab_name(name, "status") != row["name"]:
        changes.append(("name", _vocab_name(name, "status")))
    if inactive is not None and int(bool(inactive)) != row["inactive"]:
        if inactive and status_id in STATUS_WORDS:
            raise ValueError("One of the three statuses is not retired.")
        changes.append(("inactive", int(bool(inactive))))
    for col, val in changes:
        conn.execute(f"UPDATE configuration_status SET {col} = ? WHERE status_id = ?", (val, status_id))
    if changes:
        db.audit(conn, at=at.isoformat(sep=" ", timespec="minutes"), actor=actor, action="CONFIGURATION_STATUS",
                 subject_kind="configuration_status", subject_id=status_id, detail="; ".join(f"{c} -> {v}" for c, v in changes))
    return "saved" if changes else "nothing changed"


def resolve_type(conn: sqlite3.Connection, value: str) -> tuple[str, str]:
    """(type_id, the 021 code it counts as) for a type id or a code."""
    ensure_vocabulary(conn)
    row = conn.execute("SELECT type_id, maps_to FROM configuration_type WHERE type_id = ? AND inactive = 0", ((value or "").strip(),)).fetchone()
    if row is None:
        raise ValueError(f"unknown type {value!r}")
    return row["type_id"], row["maps_to"]


def resolve_status(conn: sqlite3.Connection, value: str) -> tuple[str, str]:
    ensure_vocabulary(conn)
    row = conn.execute("SELECT status_id, maps_to FROM configuration_status WHERE status_id = ? AND inactive = 0", ((value or "").strip(),)).fetchone()
    if row is None:
        raise ValueError(f"unknown status {value!r}")
    return row["status_id"], row["maps_to"]


def questions(conn: sqlite3.Connection, type_id: str, *, all_rows: bool = False) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT * FROM configuration_question WHERE type_id = ?" + ("" if all_rows else " AND inactive = 0")
        + " ORDER BY sort_order, question_id", (type_id,))]


def add_question(conn: sqlite3.Connection, type_id: str, *, label: str, field_type: str, required=False, at: datetime, actor: str) -> int:
    if conn.execute("SELECT 1 FROM configuration_type WHERE type_id = ?", (type_id,)).fetchone() is None:
        raise LookupError("No such type.")
    lab = " ".join(str(label or "").split())[:120]
    if not lab:
        raise ValueError("A question needs a label.")
    if field_type not in FIELD_TYPES:
        raise ValueError("A question is text, a number, a date, or yes / no.")
    if conn.execute("SELECT 1 FROM configuration_question WHERE type_id = ? AND LOWER(label) = LOWER(?) AND inactive = 0", (type_id, lab)).fetchone():
        raise ValueError("That question is already asked of this type.")
    order = conn.execute("SELECT COALESCE(MAX(sort_order), 0) + 10 FROM configuration_question WHERE type_id = ?", (type_id,)).fetchone()[0]
    cur = conn.execute("INSERT INTO configuration_question (type_id, label, field_type, required, sort_order, inactive) VALUES (?,?,?,?,?,0)",
                       (type_id, lab, field_type, int(bool(required)), order))
    db.audit(conn, at=at.isoformat(sep=" ", timespec="minutes"), actor=actor, action="CONFIGURATION_TYPE",
             subject_kind="configuration_type", subject_id=type_id, detail=f"question added: {lab} ({field_type}{', required' if required else ''})")
    return cur.lastrowid


def save_question(conn: sqlite3.Connection, question_id: int, *, at: datetime, actor: str, label=None, required=None, inactive=None) -> str:
    row = conn.execute("SELECT * FROM configuration_question WHERE question_id = ?", (question_id,)).fetchone()
    if row is None:
        raise LookupError("No such question.")
    changes = []
    if label is not None:
        lab = " ".join(str(label).split())[:120]
        if not lab:
            raise ValueError("A question needs a label.")
        if lab != row["label"]:
            changes.append(("label", lab))
    if required is not None and int(bool(required)) != row["required"]:
        changes.append(("required", int(bool(required))))
    if inactive is not None and int(bool(inactive)) != row["inactive"]:
        changes.append(("inactive", int(bool(inactive))))
    for col, val in changes:
        conn.execute(f"UPDATE configuration_question SET {col} = ? WHERE question_id = ?", (val, question_id))
    if changes:
        db.audit(conn, at=at.isoformat(sep=" ", timespec="minutes"), actor=actor, action="CONFIGURATION_TYPE",
                 subject_kind="configuration_type", subject_id=row["type_id"],
                 detail=f"question {row['label']}: " + "; ".join(f"{c} -> {v}" for c, v in changes))
    return "saved" if changes else "nothing changed"


def answers(conn: sqlite3.Connection, configuration_id: str) -> list[dict]:
    """The questions the configuration's type asks, each with its answer."""
    row = conn.execute("SELECT type_id, config_type FROM configuration WHERE configuration_id = ?", (configuration_id,)).fetchone()
    if row is None:
        raise LookupError(f"no configuration {configuration_id!r}")
    tid = row["type_id"] or row["config_type"]
    given = {r["question_id"]: r["value"] for r in conn.execute(
        "SELECT question_id, value FROM configuration_answer WHERE configuration_id = ?", (configuration_id,))}
    return [{**q, "value": given.get(q["question_id"])} for q in questions(conn, tid)]


def _clean_answer(q: dict, raw) -> str | None:
    v = " ".join(str(raw if raw is not None else "").split())
    if q["field_type"] == "CHECKBOX":
        return "1" if v.lower() in ("1", "on", "yes", "true") else ("0" if v.lower() in ("0", "no", "false", "") else None)
    if not v:
        return None
    if q["field_type"] == "NUMBER":
        try:
            return f"{float(v.replace(',', '')):g}"
        except ValueError:
            raise ValueError(f"{q['label']} is a number.") from None
    if q["field_type"] == "DATE":
        try:
            return date.fromisoformat(v).isoformat()
        except ValueError:
            raise ValueError(f"{q['label']} is a date, e.g. 2026-12-31.") from None
    return v[:400]


def save_answers(conn: sqlite3.Connection, configuration_id: str, values: dict, *, at: datetime, actor: str) -> list[str]:
    """Write the answers a form posted, one per question of the type: a
    question missing from `values` is an empty answer (a browser posts no
    key for a blank box or an unticked box), and a required question with
    no answer is refused. Returns what changed."""
    changed = []
    cleaned = []
    for q in answers(conn, configuration_id):                  # every answer checked before any is written
        new = _clean_answer(q, values.get(str(q["question_id"])))
        if q["required"] and (new is None or (q["field_type"] == "CHECKBOX" and new == "0")):
            raise ValueError(f"{q['label']} is needed for a {type_word(conn, conn.execute('SELECT type_id, config_type FROM configuration WHERE configuration_id = ?', (configuration_id,)).fetchone()).lower()}.")
        cleaned.append((q, new))
    for q, new in cleaned:
        if new != q["value"]:
            conn.execute("DELETE FROM configuration_answer WHERE configuration_id = ? AND question_id = ?", (configuration_id, q["question_id"]))
            if new is not None:
                conn.execute("INSERT INTO configuration_answer (configuration_id, question_id, value) VALUES (?,?,?)",
                             (configuration_id, q["question_id"], new))
            changed.append(f"{q['label']}: {q['value'] if q['value'] is not None else '-'} -> {new if new is not None else '-'}")
    if changed:
        db.audit(conn, at=at.isoformat(sep=" ", timespec="minutes"), actor=actor, action="CONFIGURATION_UPDATE",
                 subject_kind="configuration", subject_id=configuration_id, detail="; ".join(changed)[:900])
    return changed


def create(conn: sqlite3.Connection, *, name: str, entity_id: str, config_type: str,
           at: datetime, actor: str, contact_id: str | None = None, serial_number: str | None = None,
           manufacturer: str | None = None, model: str | None = None, description: str | None = None,
           site_id: str | None = None, remote_session_id: str | None = None) -> str:
    """A configuration typed in by hand (source MANUAL): a printer, a network
    device, a machine AD does not know. AD's own machines arrive by import and
    are never typed. The name must be new on the company."""
    name = (name or "").strip()
    if not name:
        raise ValueError("a configuration needs a name")
    if len(name) > 100:
        raise ValueError("a name is at most 100 characters")
    type_id, config_type = resolve_type(conn, config_type)
    if conn.execute("SELECT 1 FROM entity WHERE entity_id = ?", (entity_id,)).fetchone() is None:
        raise LookupError(f"no company {entity_id!r}")
    if conn.execute("SELECT 1 FROM configuration WHERE entity_id = ? AND LOWER(name) = LOWER(?)",
                    (entity_id, name)).fetchone():
        raise ValueError(f"there is already a configuration named {name!r} at this company")
    if contact_id and conn.execute("SELECT 1 FROM contact WHERE contact_id = ? AND entity_id = ?",
                                   (contact_id, entity_id)).fetchone() is None:
        raise LookupError("that contact is not at this company")
    if site_id and conn.execute("SELECT 1 FROM site WHERE site_id = ? AND entity_id = ?",
                                (site_id, entity_id)).fetchone() is None:
        raise LookupError("that site is not this company's")
    session = None
    if remote_session_id and remote_session_id.strip():
        session = _guid(remote_session_id)
        if session is None:
            raise ValueError("a ScreenConnect session id is a GUID")
    cid = "CF-" + uuid.uuid4().hex[:12].upper()
    stamp = at.isoformat(sep=" ", timespec="seconds")
    conn.execute(
        "INSERT INTO configuration (configuration_id, entity_id, name, config_type, status, contact_id,"
        " site_id, manufacturer, model, serial_number, description, remote_session_id, source, created_at, type_id, status_id)"
        " VALUES (?,?,?,?,'ACTIVE',?,?,?,?,?,?,?,'MANUAL',?,?,'ACTIVE')",
        (cid, entity_id, name, config_type, contact_id or None, site_id or None,
         (manufacturer or "").strip() or None, (model or "").strip() or None,
         (serial_number or "").strip() or None, (description or "").strip() or None, session, stamp, type_id))
    db.audit(conn, at=at.isoformat(sep=" ", timespec="minutes"), actor=actor,
             action="CONFIGURATION_CREATE", subject_kind="configuration", subject_id=cid,
             detail=f"{name} ({config_type.lower()}) at {entity_id}, by hand")
    return cid


# What the desk may change. AD owns name, dns_name, os_name, os_version and
# description on an imported machine (a re-import refreshes them); on a
# machine typed in by hand the desk owns the name and the description too.
DESK_FIELDS = ("config_type", "status", "contact_id", "site_id", "remote_session_id",
               "serial_number", "manufacturer", "model")
MANUAL_FIELDS = ("name", "description")


def update(conn: sqlite3.Connection, configuration_id: str, *, at: datetime, actor: str,
           config_type: str | None = None, status: str | None = None,
           contact_id: str | None = None, remote_session_id: str | None = None,
           serial_number: str | None = None, manufacturer: str | None = None,
           model: str | None = None, site_id: str | None = None, name: str | None = None,
           description: str | None = None, purchased_on: str | None = None,
           warranty_ends_on: str | None = None, installed_on: str | None = None,
           vendor: str | None = None, purchase_ref: str | None = None, location: str | None = None,
           agreement_id: str | None = None) -> list[str]:
    """Change what the desk owns about a configuration, and audit it.

    `contact_id=""` clears the contact; `None` leaves any field as it is. A
    remote session id must be a GUID: that is what ScreenConnect uses, and it is
    what keeps a pasted URL or note from becoming part of a launch link. The
    name and description are the desk's only on a machine typed in by hand.
    """
    row = conn.execute("SELECT * FROM configuration WHERE configuration_id = ?",
                       (configuration_id,)).fetchone()
    if row is None:
        raise LookupError(f"no configuration {configuration_id!r}")
    changes: dict[str, object] = {}
    for key, value in (("manufacturer", manufacturer), ("model", model)):
        if value is not None and (value.strip()[:100] or None) != row[key]:
            changes[key] = value.strip()[:100] or None
    if site_id is not None and (site_id or None) != row["site_id"]:
        if site_id and conn.execute("SELECT 1 FROM site WHERE site_id = ? AND entity_id = ?",
                                    (site_id, row["entity_id"])).fetchone() is None:
            raise LookupError("that site is not this configuration's company's")
        changes["site_id"] = site_id or None
    if name is not None or description is not None:
        if row["source"] != "MANUAL":
            if (name is not None and name.strip() != row["name"]) or \
                    (description is not None and (description.strip() or None) != row["description"]):
                raise ValueError("the name and description of an imported machine are Active Directory's; "
                                 "change them there and re-import")
        else:
            if name is not None:
                new_name = name.strip()
                if not new_name:
                    raise ValueError("a configuration needs a name")
                if new_name != row["name"]:
                    changes["name"] = new_name[:100]
            if description is not None and (description.strip() or None) != row["description"]:
                changes["description"] = description.strip() or None
    if config_type is not None and config_type != (row["type_id"] or row["config_type"]):
        type_id, code = resolve_type(conn, config_type)
        changes["type_id"] = type_id
        changes["config_type"] = code
    if status is not None and status != (row["status_id"] or row["status"]):
        status_id, code = resolve_status(conn, status)
        changes["status_id"] = status_id
        changes["status"] = code
    if contact_id is not None and (contact_id or None) != row["contact_id"]:
        if contact_id and conn.execute(
                "SELECT 1 FROM contact WHERE contact_id = ? AND entity_id = ?",
                (contact_id, row["entity_id"])).fetchone() is None:
            raise LookupError("that contact is not at this configuration's company")
        changes["contact_id"] = contact_id or None
    if remote_session_id is not None:
        value = remote_session_id.strip()
        if value and _guid(value) is None:
            raise ValueError("a ScreenConnect session id is a GUID, "
                             "e.g. 0f9c3a0e-1111-4c2a-9a55-2b8f3c1d0001")
        value = _guid(value) if value else None
        if value != row["remote_session_id"]:
            changes["remote_session_id"] = value
    if serial_number is not None and (serial_number.strip() or None) != row["serial_number"]:
        changes["serial_number"] = serial_number.strip() or None
    # 048: the life of the machine, the desk's own knowledge
    for key, value in (("purchased_on", purchased_on), ("warranty_ends_on", warranty_ends_on),
                       ("installed_on", installed_on)):
        if value is None:
            continue
        v = value.strip() or None
        if v:
            try:
                v = date.fromisoformat(v[:10]).isoformat()
            except ValueError:
                raise ValueError(f"{key.replace('_', ' ')} is a date, e.g. 2026-03-31") from None
        if v != row[key]:
            changes[key] = v
    for key, value, width in (("vendor", vendor, 100), ("purchase_ref", purchase_ref, 60), ("location", location, 120)):
        if value is not None and (value.strip()[:width] or None) != row[key]:
            changes[key] = value.strip()[:width] or None
    if agreement_id is not None and (agreement_id or None) != row["agreement_id"]:
        if agreement_id and conn.execute("SELECT 1 FROM agreement WHERE agreement_id = ?",
                                         (agreement_id,)).fetchone() is None:
            raise LookupError("no such agreement")
        changes["agreement_id"] = agreement_id or None
    if changes:
        conn.execute("UPDATE configuration SET " + ", ".join(f"{k} = ?" for k in changes)
                     + " WHERE configuration_id = ?", list(changes.values()) + [configuration_id])
        db.audit(conn, at=at.isoformat(sep=" ", timespec="minutes"), actor=actor,
                 action="CONFIGURATION_UPDATE", subject_kind="configuration",
                 subject_id=configuration_id,
                 detail="; ".join(f"{k} {row[k] or '-'} -> {v or '-'}" for k, v in changes.items()))
    return list(changes)


def attach(conn: sqlite3.Connection, work_item_id: str, configuration_id: str, *,
           at: datetime, actor: str) -> bool:
    """List a configuration on a ticket. Returns False if it already was."""
    from .board import _event, touch
    row = conn.execute("SELECT name FROM configuration WHERE configuration_id = ?",
                       (configuration_id,)).fetchone()
    if row is None:
        raise LookupError(f"no configuration {configuration_id!r}")
    stamp = at.isoformat(sep=" ", timespec="minutes")
    cur = conn.execute(
        "INSERT OR IGNORE INTO ticket_configuration (work_item_id, configuration_id,"
        " linked_at, linked_by) VALUES (?,?,?,?)", (work_item_id, configuration_id, stamp, actor))
    if cur.rowcount:
        _event(conn, work_item_id, stamp, "UPDATED", actor,
               f"configuration {row['name']} ({configuration_id}) attached")
        touch(conn, work_item_id, at)
    return bool(cur.rowcount)


def detach(conn: sqlite3.Connection, work_item_id: str, configuration_id: str, *,
           at: datetime, actor: str) -> bool:
    from .board import _event, touch
    stamp = at.isoformat(sep=" ", timespec="minutes")
    row = conn.execute("SELECT name FROM configuration WHERE configuration_id = ?",
                       (configuration_id,)).fetchone()
    cur = conn.execute("DELETE FROM ticket_configuration WHERE work_item_id = ?"
                       " AND configuration_id = ?", (work_item_id, configuration_id))
    if cur.rowcount:
        _event(conn, work_item_id, stamp, "UPDATED", actor,
               f"configuration {row['name'] if row else '?'} ({configuration_id}) removed")
        touch(conn, work_item_id, at)
    return bool(cur.rowcount)


# ------------------------------------------------------------- links out

def check_template(applies_to: str, template: str) -> None:
    """Refuse a template that could send a technician anywhere unexpected."""
    if applies_to not in LINK_FIELDS:
        raise ValueError(f"unknown record kind {applies_to!r}")
    parts = urllib.parse.urlsplit(template)
    if parts.scheme != "https" or not parts.hostname or "{" in (parts.netloc or ""):
        raise ValueError("a link must be https:// with a fixed host; only the path may "
                         "carry {fields}")
    unknown = sorted(set(_PLACEHOLDER.findall(template)) - set(LINK_FIELDS[applies_to]))
    if unknown:
        raise ValueError("unknown field(s) " + ", ".join(unknown) + "; allowed: "
                         + ", ".join(LINK_FIELDS[applies_to]))
    if not _PLACEHOLDER.search(template):
        raise ValueError("the template names no {field}, so every record would open the "
                         "same page")


def add_link(conn: sqlite3.Connection, *, label: str, applies_to: str, url_template: str,
             at: datetime, actor: str) -> str:
    label = label.strip()
    if not label:
        raise ValueError("a link needs a label")
    check_template(applies_to, url_template.strip())
    link_id = "LK-" + uuid.uuid4().hex[:8].upper()
    conn.execute("INSERT INTO integration_link (link_id, label, applies_to, url_template,"
                 " created_at, created_by) VALUES (?,?,?,?,?,?)",
                 (link_id, label, applies_to, url_template.strip(),
                  at.isoformat(sep=" ", timespec="minutes"), actor))
    db.audit(conn, at=at.isoformat(sep=" ", timespec="minutes"), actor=actor,
             action="INTEGRATION_LINK_ADD", subject_kind="integration_link",
             subject_id=link_id, detail=f"{applies_to}: {label}")
    return link_id


def links_for(conn: sqlite3.Connection, applies_to: str, record) -> list[dict]:
    """Each active link for this record: its label, and a URL or why there is none."""
    out = []
    for link in conn.execute("SELECT * FROM integration_link WHERE applies_to = ?"
                             " AND inactive = 0 ORDER BY label", (applies_to,)):
        missing = [f for f in _PLACEHOLDER.findall(link["url_template"])
                   if not (record[f] if f in record.keys() else None)]
        if missing:
            out.append({"label": link["label"], "url": None,
                        "why": "no " + ", ".join(m.replace("_", " ") for m in missing)
                               + " recorded"})
            continue
        url = _PLACEHOLDER.sub(
            lambda m: urllib.parse.quote(str(record[m.group(1)]), safe=""),
            link["url_template"])
        out.append({"label": link["label"], "url": url, "why": ""})
    return out


# ------------------------------------------------------------ 048: warranty and maintenance

WARRANTY_SOON_DAYS = 90


def warranty_state(warranty_ends_on: str | None, today: date) -> tuple[str | None, int | None]:
    """EXPIRED, EXPIRING (within 90 days) or COVERED, with the days left
    (negative once expired); (None, None) with no date."""
    if not warranty_ends_on:
        return None, None
    try:
        ends = date.fromisoformat(str(warranty_ends_on)[:10])
    except ValueError:
        return None, None
    days = (ends - today).days
    if days < 0:
        return "EXPIRED", days
    if days <= WARRANTY_SOON_DAYS:
        return "EXPIRING", days
    return "COVERED", days


def warranty_counts(conn: sqlite3.Connection, today: date) -> dict:
    """Active machines whose warranty has ended, and whose ends within 90 days."""
    t, soon = today.isoformat(), (today + timedelta(days=WARRANTY_SOON_DAYS)).isoformat()
    expired = conn.execute("SELECT COUNT(*) FROM configuration WHERE status = 'ACTIVE' AND warranty_ends_on IS NOT NULL"
                           " AND warranty_ends_on < ?", (t,)).fetchone()[0]
    expiring = conn.execute("SELECT COUNT(*) FROM configuration WHERE status = 'ACTIVE' AND warranty_ends_on >= ?"
                            " AND warranty_ends_on <= ?", (t, soon)).fetchone()[0]
    return {"expired": expired, "expiring": expiring}


def maintenance(conn: sqlite3.Connection, configuration_ids, *, boards, since: str | None = None,
                until: str | None = None, limit: int = 5000):
    """The maintenance record: every ticket attached to the machines, on the
    boards given (the reader's), with the hours booked and the visits made.
    What a DOH inspection asks for, per asset."""
    ids = list(configuration_ids)
    boards = sorted(boards)
    if not ids or not boards:
        return []
    where = [f"tc.configuration_id IN ({','.join('?' * len(ids))})", f"t.board_id IN ({','.join('?' * len(boards))})"]
    args: list = ids + boards
    if since:
        where.append("t.opened_at >= ?")
        args.append(since)
    if until:
        where.append("t.opened_at < ?")
        args.append(until + " 99")
    args.append(limit)
    return conn.execute(
        "SELECT c.configuration_id, c.name AS configuration, c.config_type, c.serial_number, t.work_item_id, t.board_id,"
        " w.name AS summary, b.display_name AS board, t.record_type, t.state, t.opened_at, t.closed_at, t.owner,"
        " COALESCE(th.h, 0) AS hours, COALESCE(vs.n, 0) AS visits"
        " FROM ticket_configuration tc JOIN configuration c ON c.configuration_id = tc.configuration_id"
        " JOIN ticket t ON t.work_item_id = tc.work_item_id JOIN work_item w ON w.work_item_id = t.work_item_id"
        " JOIN board b ON b.board_id = t.board_id"
        " LEFT JOIN (SELECT work_item_id, SUM(COALESCE(actual_hours, band_hours)) AS h FROM time_entry GROUP BY work_item_id) th"
        "   ON th.work_item_id = t.work_item_id"
        " LEFT JOIN (SELECT work_item_id, COUNT(*) AS n FROM ticket_schedule GROUP BY work_item_id) vs"
        "   ON vs.work_item_id = t.work_item_id"
        " WHERE " + " AND ".join(where) + " ORDER BY c.name, t.opened_at LIMIT ?", args).fetchall()

"""Configurations: the machines a ticket is about, and the links out to reach them.

ConnectWise keeps Configurations under each company; a ticket lists the ones it
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
from datetime import datetime
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


def update(conn: sqlite3.Connection, configuration_id: str, *, at: datetime, actor: str,
           config_type: str | None = None, status: str | None = None,
           contact_id: str | None = None, remote_session_id: str | None = None,
           serial_number: str | None = None) -> list[str]:
    """Change what the desk owns about a configuration, and audit it.

    `contact_id=""` clears the contact; `None` leaves any field as it is. A
    remote session id must be a GUID: that is what ScreenConnect uses, and it is
    what keeps a pasted URL or note from becoming part of a launch link.
    """
    row = conn.execute("SELECT * FROM configuration WHERE configuration_id = ?",
                       (configuration_id,)).fetchone()
    if row is None:
        raise LookupError(f"no configuration {configuration_id!r}")
    changes: dict[str, object] = {}
    if config_type is not None and config_type != row["config_type"]:
        if config_type not in TYPES:
            raise ValueError(f"unknown type {config_type!r}")
        changes["config_type"] = config_type
    if status is not None and status != row["status"]:
        if status not in STATUSES:
            raise ValueError(f"unknown status {status!r}")
        changes["status"] = status
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
    if conn.execute("SELECT 1 FROM configuration WHERE configuration_id = ?",
                    (configuration_id,)).fetchone() is None:
        raise LookupError(f"no configuration {configuration_id!r}")
    stamp = at.isoformat(sep=" ", timespec="minutes")
    cur = conn.execute(
        "INSERT OR IGNORE INTO ticket_configuration (work_item_id, configuration_id,"
        " linked_at, linked_by) VALUES (?,?,?,?)", (work_item_id, configuration_id, stamp, actor))
    if cur.rowcount:
        _event(conn, work_item_id, stamp, "UPDATED", actor,
               f"configuration {configuration_id} attached")
        touch(conn, work_item_id, at)
    return bool(cur.rowcount)


def detach(conn: sqlite3.Connection, work_item_id: str, configuration_id: str, *,
           at: datetime, actor: str) -> bool:
    from .board import _event, touch
    stamp = at.isoformat(sep=" ", timespec="minutes")
    cur = conn.execute("DELETE FROM ticket_configuration WHERE work_item_id = ?"
                       " AND configuration_id = ?", (work_item_id, configuration_id))
    if cur.rowcount:
        _event(conn, work_item_id, stamp, "UPDATED", actor,
               f"configuration {configuration_id} removed")
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

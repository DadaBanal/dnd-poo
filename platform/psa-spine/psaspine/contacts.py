"""Contacts: who asks, under which company, read from what AD already knows.

ConnectWise keeps a contact under each company, and every ticket names one. Here
the people asking are almost all PMC staff, and PMC's Active Directory already
holds them, so contacts are **imported from an export of AD**, not typed in.

The export is a CSV written by `scripts/Export-PmcAdContacts.ps1`, which reads AD
and changes nothing. There is no directory connection in this repository and no
credential to hold: a file dropped on the server is the whole interface, the same
shape as email intake.

Three rules:

  * **The AD objectGUID is the identity.** A renamed person, a new mailbox or a
    moved OU is the same contact. A GUID seen twice is updated, never duplicated.
  * **Disabled, never deleted.** A person disabled in AD is marked inactive.
    Their old tickets still name them, and a ticket's history is evidence.
  * **Every row is accounted for.** new + updated + unchanged + skipped equals the
    rows in, and a skipped row says why. The same losslessness rule as every
    other importer here.

These are staff. Nothing here is a patient identifier, and the export carries no
password, hash or group membership.

Standard library only.
"""
from __future__ import annotations

import csv
import re
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path

from . import db

# The export's header, as Export-PmcAdContacts.ps1 writes it. Get-ADUser property
# names, so the file can also be produced by hand with Select-Object.
COLUMNS = {
    "ObjectGUID": "ad_object_guid",
    "DisplayName": "display_name",
    "Mail": "email",
    "UserPrincipalName": "upn",
    "SamAccountName": "sam_account",
    "Department": "department",
    "Title": "title",
    "Office": "office",
    "TelephoneNumber": "phone",
}
REQUIRED = ("ObjectGUID", "DisplayName", "Enabled")
_GUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
_EMAIL = re.compile(r"[\w.+'-]+@[\w-]+(?:\.[\w-]+)+")
FIELDS = ("display_name", "email", "upn", "sam_account", "department", "title",
          "office", "phone")


def _enabled(value: str) -> bool | None:
    v = (value or "").strip().lower()
    if v in ("true", "1", "yes"):
        return True
    if v in ("false", "0", "no"):
        return False
    return None


def import_csv(conn: sqlite3.Connection, path: str | Path, *, entity_id: str,
               at: datetime, actor: str = "cli", source: str = "AD") -> dict:
    """Upsert contacts under one company from an AD export. Returns the counts.

    Never deactivates a contact that is merely absent from the file: an export
    scoped to one OU is not a statement that everybody else has left.
    """
    if conn.execute("SELECT 1 FROM entity WHERE entity_id = ?", (entity_id,)).fetchone() is None:
        raise LookupError(f"no company {entity_id!r}")
    stamp = at.isoformat(sep=" ", timespec="seconds")
    counts = {"rows": 0, "new": 0, "updated": 0, "unchanged": 0, "skipped": 0,
              "deactivated": 0, "reactivated": 0}
    reasons: list[str] = []

    raw = Path(path).read_bytes()
    text = raw.decode("utf-8-sig")      # PowerShell 5.1's Export-Csv writes a BOM
    reader = csv.DictReader(text.splitlines())
    missing = [c for c in REQUIRED if c not in (reader.fieldnames or [])]
    if missing:
        raise ValueError("not an AD contacts export: no column " + ", ".join(missing))

    for line_no, row in enumerate(reader, start=2):
        counts["rows"] += 1
        guid = (row.get("ObjectGUID") or "").strip().strip("{}").lower()
        enabled = _enabled(row.get("Enabled", ""))
        name = (row.get("DisplayName") or "").strip()
        if not _GUID.match(guid):
            counts["skipped"] += 1
            reasons.append(f"line {line_no}: no usable ObjectGUID")
            continue
        if enabled is None:
            counts["skipped"] += 1
            reasons.append(f"line {line_no}: Enabled is neither true nor false")
            continue
        if not name:
            name = (row.get("UserPrincipalName") or row.get("SamAccountName") or "").strip()
        if not name:
            counts["skipped"] += 1
            reasons.append(f"line {line_no}: no name of any kind")
            continue

        values = {col: ((row.get(src) or "").strip() or None)
                  for src, col in COLUMNS.items() if col != "ad_object_guid"}
        values["display_name"] = name
        if values["email"]:
            values["email"] = values["email"].lower()
        inactive = 0 if enabled else 1

        existing = conn.execute("SELECT * FROM contact WHERE ad_object_guid = ?",
                                (guid,)).fetchone()
        if existing is None:
            conn.execute(
                "INSERT INTO contact (contact_id, entity_id, display_name, email, phone,"
                " department, title, office, upn, sam_account, ad_object_guid, source,"
                " inactive, created_at, last_synced_at)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                ("CT-" + uuid.uuid4().hex[:12].upper(), entity_id, name, values["email"],
                 values["phone"], values["department"], values["title"], values["office"],
                 values["upn"], values["sam_account"], guid, source, inactive, stamp, stamp))
            counts["new"] += 1
            continue

        changed = [f for f in FIELDS if existing[f] != values[f]]
        if existing["inactive"] != inactive:
            counts["deactivated" if inactive else "reactivated"] += 1
        if changed or existing["inactive"] != inactive:
            sets = ", ".join(f"{f} = ?" for f in changed)
            conn.execute(
                "UPDATE contact SET " + (sets + ", " if sets else "")
                + "inactive = ?, last_synced_at = ? WHERE contact_id = ?",
                [values[f] for f in changed] + [inactive, stamp, existing["contact_id"]])
            counts["updated"] += 1
        else:
            conn.execute("UPDATE contact SET last_synced_at = ? WHERE contact_id = ?",
                         (stamp, existing["contact_id"]))
            counts["unchanged"] += 1

    db.audit(conn, at=at.isoformat(sep=" ", timespec="minutes"), actor=actor,
             action="CONTACT_IMPORT", subject_kind="entity", subject_id=entity_id,
             detail=(f"{counts['rows']} rows: {counts['new']} new, {counts['updated']} "
                     f"updated, {counts['unchanged']} unchanged, {counts['skipped']} skipped"))
    counts["reasons"] = reasons
    return counts


def email_of(requested_by: str | None) -> str | None:
    """The address in 'Name <a@b>' or a bare address; None if there is none."""
    if not requested_by:
        return None
    m = _EMAIL.search(requested_by)
    return m.group(0).lower() if m else None


def resolve(conn: sqlite3.Connection, requested_by: str | None) -> sqlite3.Row | None:
    """The one active contact this requester is, or None.

    Matched on email, then on UPN, never on a display name: two people can share
    a name, and a ticket put under the wrong person is worse than one put under
    nobody. More than one match is no match.
    """
    address = email_of(requested_by)
    if address is None:
        return None
    for column in ("email", "upn"):
        rows = conn.execute(
            f"SELECT * FROM contact WHERE lower({column}) = ? AND inactive = 0",
            (address,)).fetchall()
        if len(rows) == 1:
            return rows[0]
        if len(rows) > 1:
            return None
    return None


# Mail providers anyone can sign up to: a domain here says nothing about which
# company a sender belongs to.
PUBLIC_DOMAINS = frozenset({
    "gmail.com", "googlemail.com", "yahoo.com", "ymail.com", "outlook.com",
    "hotmail.com", "live.com", "msn.com", "icloud.com", "me.com", "aol.com",
    "proton.me", "protonmail.com", "gmx.com", "zoho.com", "mail.com"})


def company_for_domain(conn: sqlite3.Connection, requested_by: str | None) -> str | None:
    """The one company whose active contacts use this address's domain, or None.

    ConnectWise's third match, after exact address and unique name: an email
    domain that belongs to exactly one company (VERIFIED, docs.connectwise.com/
    ConnectWise_Documentation/090/020/170/040, archived 2024-07-15). A name is
    never matched here (see resolve). Public mail domains never match, and a
    domain seen at two companies matches neither.
    """
    address = email_of(requested_by)
    if address is None:
        return None
    domain = address.rsplit("@", 1)[1]
    if domain in PUBLIC_DOMAINS:
        return None
    rows = conn.execute(
        "SELECT DISTINCT entity_id FROM contact WHERE inactive = 0 AND ("
        " lower(email) LIKE ? OR lower(upn) LIKE ?)",
        (f"%@{domain}", f"%@{domain}")).fetchall()
    return rows[0]["entity_id"] if len(rows) == 1 else None


def search(conn: sqlite3.Connection, q: str = "", *, entity_id: str | None = None,
           include_inactive: bool = False, limit: int = 200) -> list[sqlite3.Row]:
    sql = ["SELECT c.*, e.name AS entity_name,"
           " (SELECT COUNT(*) FROM ticket t WHERE t.contact_id = c.contact_id"
           "   AND t.closed_at IS NULL) AS open_tickets"
           " FROM contact c JOIN entity e ON e.entity_id = c.entity_id WHERE 1 = 1"]
    params: list = []
    if entity_id:
        sql.append(" AND c.entity_id = ?")
        params.append(entity_id)
    if not include_inactive:
        sql.append(" AND c.inactive = 0")
    if q:
        like = f"%{q.lower()}%"
        sql.append(" AND (lower(c.display_name) LIKE ? OR lower(coalesce(c.email,'')) LIKE ?"
                   " OR lower(coalesce(c.department,'')) LIKE ?)")
        params += [like, like, like]
    sql.append(" ORDER BY c.display_name LIMIT ?")
    params.append(limit)
    return conn.execute("".join(sql), params).fetchall()

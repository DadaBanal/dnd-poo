"""BizBox: agreements, products, purchase orders and invoices, mirrored read-only (043).

Finance, agreements and procurement are BizBox's (Dada's direction, 29 Sep
2026); Dada PSA makes way for them. `psaspine sync-bizbox` copies what a map
file names into the ext_* tables, and the desk links tickets and projects to
those rows. Nothing here writes to BizBox, and the desk issues no invoice.

**BizBox is the hospital information system and holds patient records** (the
record, §8.1, MEASURED: on DND-SQL01, with `sa` enabled and an audit open). So
what crosses is fenced four ways, before any query is sent:

1. Only the objects and columns a map file names. The map is data, reviewed
   in the repo; nothing is discovered at run time.
2. Every name must be a plain identifier (schema.view, column): no brackets,
   quotes, spaces or semicolons, so a map cannot smuggle SQL.
3. A name that looks like a patient table or field is refused (patient,
   admission, diagnosis, PhilHealth, case number, birth date and the like).
   A finance view that needs one of those words renamed is a better outcome
   than a patient field reaching the desk.
4. The ODBC login must not be `sa` and the connection asks for read-only
   intent; the host's own read-only login and views are SQL01's to create.

Two sources feed the same mapping: a folder of CSV exports (one file per kind,
headed with BizBox's column names), which works with no access at all, and a
read-only ODBC connection whose string comes from PSA_BIZBOX_ODBC and never
from the repo. Preview is the default; --apply writes.
"""
from __future__ import annotations

import csv
import json
import os
import re
import sqlite3
from datetime import date, datetime
from pathlib import Path

from . import db

SOURCE = "BIZBOX"

# kind -> (table, {field: kind of value}); ext_ref is every kind's key
KINDS = {
    "agreement": ("ext_agreement", {"ext_ref": "text", "name": "text", "party": "text", "starts_on": "date",
                                    "ends_on": "date", "status": "text", "amount": "money", "currency": "text"}),
    "product": ("ext_product", {"ext_ref": "text", "name": "text", "category": "text", "unit": "text",
                                "unit_cost": "money"}),
    "purchase_order": ("ext_purchase_order", {"ext_ref": "text", "vendor": "text", "ordered_on": "date",
                                              "status": "text", "total": "money", "currency": "text"}),
    "invoice": ("ext_invoice", {"ext_ref": "text", "party": "text", "invoiced_on": "date", "due_on": "date",
                                "status": "text", "total": "money", "currency": "text", "agreement_ref": "text",
                                "supplier_ref": "text"}),
    "po_line": ("ext_po_line", {"ext_ref": "text", "po_ref": "text", "line_no": "int", "product_ref": "text",
                                "description": "text", "quantity": "money", "received_qty": "money",
                                "unit_cost": "money"}),
}
LABEL = {"agreement": "Agreements", "product": "Products", "purchase_order": "Purchase orders", "invoice": "Invoices"}
LINK_KIND = {"agreement": "AGREEMENT", "product": "PRODUCT", "purchase_order": "PURCHASE_ORDER", "invoice": "INVOICE"}
REQUIRED = {"ext_ref", "name"}          # name only where the kind has one

_IDENT = re.compile(r"\A[A-Za-z_][A-Za-z0-9_]{0,127}(\.[A-Za-z_][A-Za-z0-9_]{0,127})?\Z")
_COL = re.compile(r"\A[A-Za-z_][A-Za-z0-9_]{0,127}\Z")
# Names that look like a patient's record. Deliberately broad: a false refusal
# costs a rename on SQL01's side; a false pass costs a patient field on the desk.
PATIENT_WORDS = re.compile(
    r"(?i)(patient|pxn|px_|^px|^pt_|pt_?name|admission|admit|diagnos|philhealth|phic|mrn|case_?no|caseno|case_?num|"
    r"chart|birth|dob|ward_?bed|bed_?n|guarantor|physician|doctor|prescri|medic|lab_?result|laborator|radiolog|"
    r"firstname|lastname|middlename|first_name|last_name|middle_name|fullname|full_name|surname|given_?name|"
    r"^f_?name$|^l_?name$|hosp|encounter|visit|discharge|icd|allerg|gender|^sex$|^age$|insur|hmo|member_?no|"
    r"religion|civil_?status|national|payor|payer|bill_?to|address|contact_?no|mobile)")
MAX_ROWS = 50_000
MAX_TEXT = 400
# Per-field widths that match the SQL Server port (tools/tsql-decisions.json:
# status, currency and unit are CODE, NVARCHAR(32)). SQLite has no widths, so
# without this a 37-character BizBox status would pass every test and fail the
# host's insert with "string or binary data would be truncated".
WIDTH = {"status": 32, "currency": 32, "unit": 32}
PAGE = 100
# The longest key the mirror accepts. SQL Server caps an index key at 900 bytes
# and warned on the first apply (29 Sep 2026) that ext_link's and ext_po_line's
# keys could exceed it at REF's full width; BizBox's own keys are cast to 20 or
# 64 characters in SQL01's views (MEASURED), so a longer one is not a BizBox
# key. It is skipped and counted, never inserted to fail on the server.
MAX_KEY = 64


class Refused(ValueError):
    """A sentence for the person; nothing was read or written."""


# ------------------------------------------------------------------ the map

def load_map(path: str | Path) -> dict:
    """A map file: {"objects": {kind: {"view": "schema.view", "columns": {field: bizbox_column}}}}.
    Checked in full before anything is read."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise Refused(f"cannot read the map: {exc}") from None
    return check_map(data)


def check_map(data: dict) -> dict:
    objects = (data or {}).get("objects")
    if not isinstance(objects, dict) or not objects:
        raise Refused("the map names no objects")
    for kind, spec in objects.items():
        if kind not in KINDS:
            raise Refused(f"the map names {kind!r}; the kinds are {', '.join(KINDS)}")
        view = (spec or {}).get("view", "")
        if not _IDENT.match(view or ""):
            raise Refused(f"{kind}: {view!r} is not a plain schema.view name")
        if PATIENT_WORDS.search(view):
            raise Refused(f"{kind}: {view!r} looks like a patient table; it is never read")
        cols = (spec or {}).get("columns")
        if not isinstance(cols, dict) or "ext_ref" not in cols:
            raise Refused(f"{kind}: the map must name the column for ext_ref")
        fields = KINDS[kind][1]
        for field, col in cols.items():
            if field not in fields:
                raise Refused(f"{kind}: {field!r} is not a field of {kind}")
            if not isinstance(col, str) or not _COL.match(col):
                raise Refused(f"{kind}.{field}: {col!r} is not a plain column name")
            if PATIENT_WORDS.search(col):
                raise Refused(f"{kind}.{field}: {col!r} looks like a patient field; it is never read")
        if "name" in fields and "name" not in cols:
            raise Refused(f"{kind}: the map must name the column for name")
        if kind == "po_line" and "po_ref" not in cols:
            raise Refused("po_line: the map must name the column for po_ref")
    return data


# ------------------------------------------------------------------ readers

def read_csv_dir(folder: str | Path, mapping: dict) -> dict[str, list[dict]]:
    """One CSV per kind (<kind>.csv), headed with BizBox's column names. Only
    the mapped columns are read; any other column in the file is ignored."""
    folder = Path(folder)
    out = {}
    for kind, spec in mapping["objects"].items():
        path = folder / f"{kind}.csv"
        if not path.exists():
            raise Refused(f"{path.name} is missing from {folder}")
        with path.open(encoding="utf-8-sig", newline="") as fh:
            reader = csv.DictReader(fh)
            missing = [c for c in spec["columns"].values() if c not in (reader.fieldnames or [])]
            if missing:
                raise Refused(f"{path.name} lacks column(s) {', '.join(missing)}")
            rows = []
            for i, r in enumerate(reader):
                if i >= MAX_ROWS:
                    raise Refused(f"{path.name} has more than {MAX_ROWS} rows; split the export")
                rows.append({field: r.get(col) for field, col in spec["columns"].items()})
        out[kind] = rows
    return out


def odbc_string(raw: str | None = None) -> str:
    cs = (raw if raw is not None else os.environ.get("PSA_BIZBOX_ODBC", "")).strip()
    if not cs:
        raise Refused("PSA_BIZBOX_ODBC is not set; the connection string lives on the host, never in the repo")
    # ODBC lets a value be brace-quoted (UID={sa}); the fence reads it the way the driver does
    if re.search(r"(?i)(^|;)\s*(uid|user id|user)\s*=\s*\{?\s*sa\s*\}?\s*(;|$)", cs):
        raise Refused("refused: the BizBox login must not be sa; use the read-only login made for the desk")
    # read-only intent, whatever the string said (a ReadWrite intent is not kept)
    cs = re.sub(r"(?i)(?:^|;)\s*applicationintent\s*=[^;]*", "", cs).strip(";")
    return cs + ";ApplicationIntent=ReadOnly"


def read_odbc(mapping: dict, *, connection_string: str | None = None) -> dict[str, list[dict]]:
    """SELECT only the mapped columns from only the mapped views. Every name
    was checked by check_map; they are bracketed again here all the same."""
    cs = odbc_string(connection_string)                      # the refusals first, before any import
    import pyodbc                                            # the host has it; the tests use CSV
    out = {}
    con = pyodbc.connect(cs, autocommit=True, readonly=True, timeout=15)
    try:
        for kind, spec in mapping["objects"].items():
            view = ".".join(f"[{p}]" for p in spec["view"].split("."))
            fields = list(spec["columns"].items())
            sel = ", ".join(f"[{col}]" for _, col in fields)
            cur = con.cursor()
            cur.execute(f"SELECT TOP ({MAX_ROWS + 1}) {sel} FROM {view}")
            rows = cur.fetchall()
            if len(rows) > MAX_ROWS:
                raise Refused(f"{spec['view']} returned more than {MAX_ROWS} rows; narrow the view")
            out[kind] = [{field: row[i] for i, (field, _) in enumerate(fields)} for row in rows]
    finally:
        con.close()
    return out


# ------------------------------------------------------------------- values

def _value(v, how: str, field: str = "", cap: int = MAX_TEXT):
    """A BizBox cell as the mirror keeps it. A refusal names the field, never
    the cell: the log is counts and names only."""
    if v is None:
        return None
    if how == "money":
        if isinstance(v, (int, float)):
            return round(float(v), 4)
        text = str(v).strip().replace(",", "")
        if not text:
            return None
        try:
            return round(float(text), 4)
        except ValueError:
            raise Refused(f"{field or 'a money field'} holds something that is not an amount") from None
    if how == "int":
        if isinstance(v, int):
            return v
        text = str(v).strip()
        if not text:
            return None
        try:
            return int(float(text))
        except ValueError:
            raise Refused(f"{field or 'a whole-number field'} holds something that is not a whole number") from None
    if how == "date":
        if isinstance(v, datetime):
            return v.date().isoformat()
        if isinstance(v, date):
            return v.isoformat()
        text = str(v).strip()
        if not text:
            return None
        if re.fullmatch(r"\d{8}", text):
            return f"{text[:4]}-{text[4:6]}-{text[6:]}"
        try:
            return date.fromisoformat(text[:10]).isoformat()
        except ValueError:
            raise Refused(f"{field or 'a date field'} holds something that is not a date") from None
    text = " ".join(str(v).split())
    return text[:cap] or None


# --------------------------------------------------------------------- sync

def sync(conn: sqlite3.Connection, rows_by_kind: dict[str, list[dict]], *, at: datetime, actor: str,
         apply: bool = False) -> dict:
    """Upsert the mirror from rows. Preview (the default) writes nothing and
    says what would change. A row gone from BizBox is marked absent, never
    deleted, so a link to it survives; one that returns is marked present."""
    stamp = at.isoformat(sep=" ", timespec="minutes")
    counts = {}
    if not conn.execute("SELECT 1 FROM ext_source WHERE source_id = ?", (SOURCE,)).fetchone():
        conn.execute("INSERT INTO ext_source (source_id, name) VALUES (?, 'BizBox HIS')", (SOURCE,))
    for kind, rows in rows_by_kind.items():
        table, fields = KINDS[kind]
        c = {"rows": len(rows), "new": 0, "changed": 0, "unchanged": 0, "absent": 0, "skipped": 0, "returned": 0}
        seen = set()
        for raw in rows:
            rec = {f: _value(raw.get(f), how, f"{kind}.{f}", WIDTH.get(f, MAX_TEXT)) for f, how in fields.items() if f in raw}
            ref = rec.get("ext_ref")
            if not ref or ("name" in fields and not rec.get("name")) or ref in seen \
                    or (kind == "po_line" and not rec.get("po_ref")) \
                    or len(ref) > MAX_KEY or len(rec.get("po_ref") or "") > MAX_KEY:
                c["skipped"] += 1
                continue
            seen.add(ref)
            old = conn.execute(f"SELECT * FROM {table} WHERE source_id = ? AND ext_ref = ?", (SOURCE, ref)).fetchone()
            if old is None:
                c["new"] += 1
                cols = ["source_id", *rec, "present", "synced_at"]
                conn.execute(f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
                             [SOURCE, *rec.values(), 1, stamp])
                continue
            diff = {f: v for f, v in rec.items() if f != "ext_ref" and v != old[f]}
            if not old["present"]:
                c["returned"] += 1
            if diff or not old["present"]:
                if diff:
                    c["changed"] += 1
                sets = ", ".join(f"{f} = ?" for f in diff)
                conn.execute(f"UPDATE {table} SET {sets + ', ' if sets else ''}present = 1, synced_at = ?"
                             " WHERE source_id = ? AND ext_ref = ?", [*diff.values(), stamp, SOURCE, ref])
            else:
                c["unchanged"] += 1
        for (ref,) in conn.execute(f"SELECT ext_ref FROM {table} WHERE source_id = ? AND present = 1", (SOURCE,)).fetchall():
            if ref not in seen:
                c["absent"] += 1
                conn.execute(f"UPDATE {table} SET present = 0 WHERE source_id = ? AND ext_ref = ?", (SOURCE, ref))
        counts[kind] = c
    words = "; ".join(f"{k}: {v['rows']} rows, {v['new']} new, {v['changed']} changed, {v['unchanged']} unchanged,"
                      f" {v['absent']} absent, {v['skipped']} skipped" for k, v in counts.items())
    if apply:
        conn.execute("UPDATE ext_source SET last_sync_at = ?, last_sync_by = ?, last_result = ? WHERE source_id = ?",
                     (stamp, actor, words, SOURCE))
        db.audit(conn, at=stamp, actor=actor, action="BIZBOX_SYNC", subject_kind="ext_source", subject_id=SOURCE,
                 detail=words)
        conn.commit()
    else:
        conn.rollback()
    return counts


# ------------------------------------------------------------ reading, links

def _like(needle: str) -> str:
    # SQLite's two wildcards and '[', which SQL Server's LIKE reads as a class
    return "%" + (needle.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_").replace("[", "\\[")) + "%"


def _filter(kind: str, q: str, include_absent: bool) -> tuple[str, list]:
    table, fields = KINDS[kind]
    sql, args = [f" FROM {table} WHERE source_id = ?"], [SOURCE]
    if not include_absent:
        sql.append(" AND present = 1")
    text_fields = [f for f, how in fields.items() if how == "text"]
    for word in (q or "").split()[:4]:
        sql.append(" AND (" + " OR ".join(f"LOWER(COALESCE({f}, '')) LIKE ? ESCAPE '\\'" for f in text_fields) + ")")
        args += [_like(word.lower())] * len(text_fields)
    return "".join(sql), args


def records(conn, kind: str, *, q: str = "", include_absent: bool = False, limit: int = PAGE, offset: int = 0):
    """One page of a kind, newest reference first; the limit is in the SQL,
    so a 50,000-row mirror is never fetched to show 100."""
    where, args = _filter(kind, q, include_absent)
    return conn.execute(f"SELECT *{where} ORDER BY ext_ref DESC LIMIT ? OFFSET ?", [*args, limit, offset]).fetchall()


def count(conn, kind: str, *, q: str = "", include_absent: bool = False) -> int:
    where, args = _filter(kind, q, include_absent)
    return conn.execute(f"SELECT COUNT(*){where}", args).fetchone()[0]


def summary(conn, kind: str, *, q: str = "", include_absent: bool = False) -> list:
    """(status, count, total) per status word, over the whole filtered set."""
    where, args = _filter(kind, q, include_absent)
    money = "total" if "total" in KINDS[kind][1] else "amount" if "amount" in KINDS[kind][1] else "0"
    return conn.execute(f"SELECT COALESCE(status, '(none)') AS status, COUNT(*) AS n, SUM({money}) AS total{where}"
                        " GROUP BY COALESCE(status, '(none)') ORDER BY 1", args).fetchall()


def links_for(conn, kind: str, refs) -> dict[str, list]:
    """The links of many records in one query (the list page's Linked column)."""
    refs = [r for r in refs if r]
    out: dict[str, list] = {r: [] for r in refs}
    for i in range(0, len(refs), 200):
        chunk = refs[i:i + 200]
        for l in conn.execute("SELECT subject_kind, subject_id, ext_ref FROM ext_link WHERE source_id = ? AND kind = ?"
                              f" AND ext_ref IN ({','.join('?' * len(chunk))}) ORDER BY linked_at",
                              [SOURCE, LINK_KIND[kind], *chunk]):
            out[l["ext_ref"]].append(l)
    return out


def get(conn, kind: str, ext_ref: str):
    table, _ = KINDS[kind]
    return conn.execute(f"SELECT * FROM {table} WHERE source_id = ? AND ext_ref = ?", (SOURCE, ext_ref)).fetchone()


def status(conn):
    return conn.execute("SELECT * FROM ext_source WHERE source_id = ?", (SOURCE,)).fetchone()


def present_kinds(conn) -> list[str]:
    """The kinds BizBox has given the desk anything for, in the order of KINDS.
    BizBox holds no supplier agreements (SQL01, 29 Sep 2026, MEASURED), so a
    Finance page that showed an Agreements tab would show an empty one for
    ever; the pages show the kinds that have rows, and all of them while the
    mirror is still empty."""
    out = []
    for kind, (table, _) in KINDS.items():
        if kind in LINK_KIND and conn.execute(f"SELECT 1 FROM {table} WHERE source_id = ? LIMIT 1", (SOURCE,)).fetchone():
            out.append(kind)
    return out or list(LINK_KIND)


def link(conn, subject_kind: str, subject_id: str, kind: str, ext_ref: str, *, at: datetime, actor: str) -> bool:
    if kind not in LINK_KIND:
        raise Refused("No such kind.")
    ext_ref = (ext_ref or "").strip()
    if get(conn, kind, ext_ref) is None:
        raise Refused(f"No {LABEL[kind].lower()[:-1]} {ext_ref!r} in the BizBox mirror; sync first.")
    if conn.execute("SELECT 1 FROM ext_link WHERE subject_kind = ? AND subject_id = ? AND source_id = ? AND kind = ?"
                    " AND ext_ref = ?", (subject_kind, subject_id, SOURCE, LINK_KIND[kind], ext_ref)).fetchone():
        return False
    stamp = at.isoformat(sep=" ", timespec="minutes")
    conn.execute("INSERT INTO ext_link (subject_kind, subject_id, source_id, kind, ext_ref, linked_at, linked_by)"
                 " VALUES (?,?,?,?,?,?,?)", (subject_kind, subject_id, SOURCE, LINK_KIND[kind], ext_ref, stamp, actor))
    if subject_kind == "TICKET":
        from .board import _event
        _event(conn, subject_id, stamp, "FINANCE", actor, f"linked to BizBox {LINK_KIND[kind].lower()} {ext_ref}")
    else:
        db.audit(conn, at=stamp, actor=actor, action="PROJECT", subject_kind="project", subject_id=subject_id,
                 detail=f"linked to BizBox {LINK_KIND[kind].lower()} {ext_ref}")
    return True


def unlink(conn, subject_kind: str, subject_id: str, kind: str, ext_ref: str, *, at: datetime, actor: str) -> bool:
    cur = conn.execute("DELETE FROM ext_link WHERE subject_kind = ? AND subject_id = ? AND source_id = ? AND kind = ?"
                       " AND ext_ref = ?", (subject_kind, subject_id, SOURCE, LINK_KIND.get(kind, ""), ext_ref))
    if cur.rowcount and subject_kind == "TICKET":
        from .board import _event
        _event(conn, subject_id, at.isoformat(sep=" ", timespec="minutes"), "FINANCE", actor,
               f"unlinked BizBox {LINK_KIND[kind].lower()} {ext_ref}")
    return bool(cur.rowcount)


def links(conn, subject_kind: str, subject_id: str) -> list[dict]:
    back = {v: k for k, v in LINK_KIND.items()}
    out = []
    for r in conn.execute("SELECT kind, ext_ref FROM ext_link WHERE subject_kind = ? AND subject_id = ?"
                          " ORDER BY kind, ext_ref", (subject_kind, subject_id)):
        kind = back[r["kind"]]
        rec = get(conn, kind, r["ext_ref"])
        out.append({"kind": kind, "ext_ref": r["ext_ref"], "record": rec})
    return out


def linked_to(conn, kind: str, ext_ref: str):
    return conn.execute("SELECT subject_kind, subject_id, linked_at, linked_by FROM ext_link WHERE source_id = ?"
                        " AND kind = ? AND ext_ref = ? ORDER BY linked_at", (SOURCE, LINK_KIND[kind], ext_ref)).fetchall()


# ------------------------------------------------- edits back to BizBox, later
#
# What a person may propose to change on a mirrored record: the fields the
# reference PSA lets a service manager edit on the matching screen. A proposal
# is recorded PENDING and BizBox is not touched. When a write path is approved,
# a Writer applies PENDING rows and says APPLIED or REJECTED; `NoWriter` is the
# one in force today, so nothing can reach BizBox by accident.

EDITABLE = {
    "agreement": {"status": "text", "ends_on": "date"},
    "purchase_order": {"status": "text"},
    "invoice": {"status": "text", "due_on": "date"},
    "product": {"name": "text", "unit_cost": "money"},
}
FIELD_WORDS = {"status": "Status", "ends_on": "End date", "due_on": "Due date", "name": "Name", "unit_cost": "Unit cost"}


class Writer:
    """How an approved change reaches BizBox. Subclass and implement apply();
    return BizBox's own answer. Registered by configuration on the host, never
    by default."""
    name = "none"

    def apply(self, change) -> str:              # pragma: no cover - the interface
        raise NotImplementedError


class NoWriter(Writer):
    """Today's writer: BizBox takes no edits from the desk."""
    name = "none"

    def apply(self, change) -> str:
        raise Refused("BizBox takes no edits from Dada PSA yet; the change stays pending")


def propose(conn, kind: str, ext_ref: str, field: str, new_value: str, *, reason: str, at: datetime,
            actor: str) -> int:
    rec = get(conn, kind, ext_ref)
    if rec is None:
        raise Refused("No such record in the BizBox mirror.")
    how = EDITABLE.get(kind, {}).get(field)
    if how is None:
        raise Refused(f"{field} is not a field that can be changed on this record.")
    reason = " ".join((reason or "").split())
    if not reason:
        raise Refused("Say why, so the person who applies it in BizBox knows.")
    value = _value(new_value, how)
    old = rec[field]
    if value == old:
        raise Refused("That is the value BizBox already has.")
    if conn.execute("SELECT 1 FROM ext_change WHERE source_id = ? AND kind = ? AND ext_ref = ? AND field = ?"
                    " AND status = 'PENDING'", (SOURCE, LINK_KIND[kind], ext_ref, field)).fetchone():
        raise Refused(f"A change to {FIELD_WORDS[field].lower()} is already pending; cancel it first.")
    stamp = at.isoformat(sep=" ", timespec="minutes")
    cur = conn.execute(
        "INSERT INTO ext_change (source_id, kind, ext_ref, field, old_value, new_value, reason, status, requested_at,"
        " requested_by) VALUES (?,?,?,?,?,?,?, 'PENDING', ?,?)",
        (SOURCE, LINK_KIND[kind], ext_ref, field, None if old is None else str(old),
         None if value is None else str(value), reason[:2000], stamp, actor))
    db.audit(conn, at=stamp, actor=actor, action="BIZBOX_CHANGE", subject_kind="ext_change", subject_id=str(cur.lastrowid),
             detail=f"proposed: {LINK_KIND[kind].lower()} {ext_ref} {field} {old!r} -> {value!r}")
    return cur.lastrowid


def changes(conn, kind: str | None = None, ext_ref: str | None = None, *, status: str | None = None):
    sql, args = ["SELECT * FROM ext_change WHERE source_id = ?"], [SOURCE]
    if kind:
        sql.append(" AND kind = ?")
        args.append(LINK_KIND[kind])
    if ext_ref:
        sql.append(" AND ext_ref = ?")
        args.append(ext_ref)
    if status:
        sql.append(" AND status = ?")
        args.append(status)
    sql.append(" ORDER BY change_id DESC")
    return conn.execute("".join(sql), args).fetchall()


def decide(conn, change_id: int, status: str, *, answer: str = "", at: datetime, actor: str) -> None:
    """Close a proposal: CANCELLED by a person; APPLIED or REJECTED by a writer
    (or by hand, after it was done in BizBox directly)."""
    if status not in ("APPLIED", "REJECTED", "CANCELLED"):
        raise Refused("A change ends APPLIED, REJECTED or CANCELLED.")
    row = conn.execute("SELECT status FROM ext_change WHERE change_id = ?", (change_id,)).fetchone()
    if row is None:
        raise Refused("No such change.")
    if row["status"] != "PENDING":
        raise Refused(f"That change is already {row['status'].lower()}.")
    stamp = at.isoformat(sep=" ", timespec="minutes")
    conn.execute("UPDATE ext_change SET status = ?, decided_at = ?, decided_by = ?, answer = ? WHERE change_id = ?",
                 (status, stamp, actor, (answer or "").strip()[:2000] or None, change_id))
    db.audit(conn, at=stamp, actor=actor, action="BIZBOX_CHANGE", subject_kind="ext_change", subject_id=str(change_id),
             detail=f"{status.lower()}" + (f": {answer}" if answer else ""))


def push(conn, writer: Writer | None = None, *, at: datetime, actor: str = "writer") -> dict:
    """Offer every PENDING change to the writer. With NoWriter (today) nothing
    moves and every change stays pending."""
    writer = writer or NoWriter()
    counts = {"applied": 0, "rejected": 0, "pending": 0}
    for ch in changes(conn, status="PENDING"):
        try:
            answer = writer.apply(ch)
        except Refused:
            counts["pending"] += 1
            continue
        except Exception as exc:                    # noqa: BLE001 - BizBox's answer, recorded
            decide(conn, ch["change_id"], "REJECTED", answer=str(exc)[:500], at=at, actor=actor)
            counts["rejected"] += 1
            continue
        decide(conn, ch["change_id"], "APPLIED", answer=answer, at=at, actor=actor)
        counts["applied"] += 1
    return counts


def po_lines(conn, po_ref: str):
    return conn.execute("SELECT * FROM ext_po_line WHERE source_id = ? AND po_ref = ? AND present = 1"
                        " ORDER BY line_no, ext_ref", (SOURCE, po_ref)).fetchall()

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
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path

from . import db

SOURCE = "BIZBOX"

# kind -> (table, {field: kind of value}); ext_ref is every kind's key
KINDS = {
    "agreement": ("ext_agreement", {"ext_ref": "text", "name": "text", "party": "text", "starts_on": "date",
                                    "ends_on": "date", "status": "text", "amount": "money", "currency": "text"}),
    "product": ("ext_product", {"ext_ref": "text", "name": "text", "category": "text", "unit": "text",
                                "unit_cost": "money", "tstamp": "text"}),
    "purchase_order": ("ext_purchase_order", {"ext_ref": "text", "vendor": "text", "ordered_on": "date",
                                              "status": "text", "total": "money", "currency": "text", "tstamp": "text"}),
    "invoice": ("ext_invoice", {"ext_ref": "text", "party": "text", "invoiced_on": "date", "due_on": "date",
                                "status": "text", "total": "money", "currency": "text", "agreement_ref": "text",
                                "supplier_ref": "text", "tstamp": "text"}),
    "po_line": ("ext_po_line", {"ext_ref": "text", "po_ref": "text", "line_no": "int", "product_ref": "text",
                                "description": "text", "quantity": "money", "received_qty": "money",
                                "unit_cost": "money", "tstamp": "text"}),
    # 081: BizBox's own code lists, one row per entry; see choices() below.
    "lookup": ("ext_lookup", {"ext_ref": "text", "list": "text", "code": "text", "label": "text", "sort_no": "int"}),
    # 083: the 73 warehouses in their groups, and the items that are medicines
    "warehouse": ("ext_warehouse", {"ext_ref": "text", "name": "text", "group_name": "text", "active": "int"}),
    "medicine": ("ext_medicine", {"ext_ref": "text", "generic": "text", "dosage": "text", "controlled": "int",
                                  "doh_ref": "text", "mims_ref": "text", "admin_group": "text", "remarks": "text"}),
    # 084: stock on hand (one row per warehouse and item that holds any; the
    # key is made here as <warehouse>:<item> when the view has none), the item
    # ledger inside the window SQL01's view keeps, and a receiving report's lines.
    "stock": ("ext_stock", {"ext_ref": "text", "warehouse_ref": "text", "item_ref": "text", "quantity": "money",
                            "unit_cost": "money", "as_of": "date", "tstamp": "text"}),
    "movement": ("ext_movement", {"ext_ref": "text", "item_ref": "text", "warehouse_ref": "text", "moved_on": "date",
                                  "kind": "text", "doc_ref": "text", "qty_in": "money", "qty_out": "money",
                                  "balance": "money", "unit_cost": "money", "remarks": "text", "tstamp": "text"}),
    "rr_line": ("ext_rr_line", {"ext_ref": "text", "rr_ref": "text", "line_no": "int", "product_ref": "text",
                                "description": "text", "quantity": "money", "unit_cost": "money", "po_ref": "text", "tstamp": "text"}),
}
# Kinds whose view is a window in time (Dada, 13 Oct 2026: "views based on
# time or days or months"): a row the view no longer returns is deleted on
# the next read, not kept absent. Nothing was lost in BizBox; the window moved.
WINDOWED = {"movement"}
LABEL = {"agreement": "Agreements", "product": "Products", "purchase_order": "Purchase orders", "invoice": "Invoices"}
LINK_KIND = {"agreement": "AGREEMENT", "product": "PRODUCT", "purchase_order": "PURCHASE_ORDER", "invoice": "INVOICE"}
# The MMS document kinds a change may carry (14 Oct 2026, the Bizbox Chat
# session's measurement, Part 90: the ten in scope by volume). Two of the ten
# are kinds the desk had: Purchase Order is purchase_order, and Delivery/
# Receiving is invoice (SQL01, Part 95, MEASURED: psa.vw_invoice reads the
# receiving header). Where the word is the function the MMS term stays (ruling 2).
MMS_KINDS = {"expense_req": "EXPENSE_REQ", "stock_req": "STOCK_REQ", "expense_issuance": "EXPENSE_ISSUANCE",
             "stock_issuance": "STOCK_ISSUANCE", "purchase_req": "PURCHASE_REQ", "material_production": "MATERIAL_PRODUCTION",
             "physical_count": "PHYSICAL_COUNT", "qty_adjustment": "QTY_ADJUSTMENT"}
MMS_WORDS = {"expense_req": "Expense Requisition", "stock_req": "Stock Requisition", "expense_issuance": "Expense Issuance",
             "stock_issuance": "Stock Issuance", "purchase_req": "Purchase Requisition", "material_production": "Material Production",
             "physical_count": "Physical Count", "qty_adjustment": "Quantity Adjustment"}
LINK_KIND.update(MMS_KINDS)
BACK_KIND = {v: k for k, v in LINK_KIND.items()}
# One record, in words, for every kind a change can name.
KIND_WORDS = {"agreement": "agreement", "product": "item", "purchase_order": "purchase order", "invoice": "receiving report"} | {
    k: w.lower() for k, w in MMS_WORDS.items()}
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
WIDTH = {"status": 32, "currency": 32, "unit": 32, "list": 32, "kind": 32}
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
        if kind == "lookup":
            # a list entry's key is <list>:<code>, made up by sync when the view has none
            if not isinstance(cols, dict) or "list" not in cols or "code" not in cols:
                raise Refused("lookup: the map must name the columns for list and code")
        elif kind == "stock":
            # a stock row's key is <warehouse>:<item>, made up by sync when the view has none
            if not isinstance(cols, dict) or not {"warehouse_ref", "item_ref", "quantity"} <= set(cols):
                raise Refused("stock: the map must name the columns for warehouse_ref, item_ref and quantity")
        elif not isinstance(cols, dict) or "ext_ref" not in cols:
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
        if kind == "rr_line" and "rr_ref" not in cols:
            raise Refused("rr_line: the map must name the column for rr_ref")
        if kind == "movement" and not {"item_ref", "moved_on"} <= set(cols):
            raise Refused("movement: the map must name the columns for item_ref and moved_on")
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
            if kind == "lookup" and not rec.get("ext_ref") and rec.get("list") and rec.get("code"):
                rec = {"ext_ref": f"{rec['list']}:{rec['code']}"} | rec
            if kind == "stock" and not rec.get("ext_ref") and rec.get("warehouse_ref") and rec.get("item_ref"):
                rec = {"ext_ref": f"{rec['warehouse_ref']}:{rec['item_ref']}"} | rec
            ref = rec.get("ext_ref")
            if not ref or ("name" in fields and not rec.get("name")) or ref in seen \
                    or (kind == "po_line" and not rec.get("po_ref")) \
                    or (kind == "rr_line" and not rec.get("rr_ref")) \
                    or (kind == "lookup" and not (rec.get("list") and rec.get("code"))) \
                    or (kind == "stock" and not (rec.get("warehouse_ref") and rec.get("item_ref") and rec.get("quantity") is not None)) \
                    or (kind == "movement" and not (rec.get("item_ref") and rec.get("moved_on"))) \
                    or len(ref) > MAX_KEY or len(rec.get("po_ref") or "") > MAX_KEY or len(rec.get("rr_ref") or "") > MAX_KEY:
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
        if kind in WINDOWED:
            conn.execute(f"DELETE FROM {table} WHERE source_id = ? AND present = 0", (SOURCE,))
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


READ_WORDS = {"purchase_order": "purchase orders", "po_line": "order lines", "product": "items",
              "invoice": "receiving reports", "agreement": "agreements", "lookup": "list entries",
              "warehouse": "warehouses", "medicine": "medicines", "stock": "stock lines", "movement": "movements",
              "rr_line": "receiving lines"}


def read_words(result: str | None) -> str:
    """The read's own summary ("purchase_order: 5 rows, 5 new, ...") in words:
    what BizBox holds, and what changed since the read before. No kind or
    table name reaches a screen (Dada, 13 Oct 2026)."""
    parts = []
    for m in re.finditer(r"(\w+): (\d+) rows, (\d+) new, (\d+) changed, (\d+) unchanged, (\d+) absent", result or ""):
        kind, rows, new, changed, _, gone = m.group(1), *map(int, m.groups()[1:])
        if not rows and not gone:
            continue
        bits = ", ".join(b for b in (f"{new} new" if new else "", f"{changed} changed" if changed else "",
                                     f"{gone} gone" if gone else "") if b)
        parts.append(f"{rows} {READ_WORDS.get(kind, kind.replace('_', ' '))}" + (f" ({bits})" if bits else ""))
    return (" · " + " · ".join(parts)) if parts else ""


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
    "purchase_order": {"status": "text", "vendor": "text", "ordered_on": "date"},
    "invoice": {"status": "text", "due_on": "date", "supplier_ref": "text"},
    "product": {"name": "text", "category": "text", "unit": "text", "unit_cost": "money"},
}
# A document's lines (14 Oct 2026, Dada: "why is there no edit also for the
# PO"): the fields a person may change on a line that BizBox has, and what a
# line added from the desk carries. A line change travels as one ext_change
# whose field is "line:<line id>:<field>" with the line's own row version as
# @expected_tstamp; a new line as "line:new:<n>" whose new_value is the line as
# JSON. The procedure's EDIT contract widens by exactly those two field shapes.
EDITABLE_LINES = {"purchase_order": {"quantity": "money", "unit_cost": "money", "description": "text"}}
NEW_LINE_FIELDS = {"purchase_order": {"product_ref": "text", "description": "text", "quantity": "money", "unit_cost": "money"}}
LINE_TABLE = {"purchase_order": ("ext_po_line", "po_ref")}
FIELD_WORDS = {"status": "Status", "ends_on": "End date", "due_on": "Due date", "name": "Name", "unit_cost": "Unit cost",
               "vendor": "Vendor", "ordered_on": "Order date", "supplier_ref": "Supplier's invoice no.",
               "category": "Category", "unit": "Unit", "currency": "Currency", "total": "Total", "amount": "Amount",
               "party": "Vendor", "invoiced_on": "Invoice date", "starts_on": "Start date", "description": "Description",
               "quantity": "Quantity", "NEW": "New record", "department": "Issuing Department", "warehouse_ref": "Warehouse (from)",
               "center": "Center", "doc_date": "Date", "product_ref": "Item ID"}
# What a person may ADD (13 Oct 2026, Dada: "edits and adds on the bizbox
# system"): the fields a new record carries, which of them BizBox needs
# before it will take the record, and, for a purchase order, its lines.
ADDABLE = {
    "purchase_order": {"fields": {"vendor": "text", "ordered_on": "date", "currency": "text", "status": "text"},
                       "required": ("vendor",),
                       "lines": {"product_ref": "text", "description": "text", "quantity": "money", "unit_cost": "money"}},
    "product": {"fields": {"ext_ref": "text", "name": "text", "category": "text", "unit": "text", "unit_cost": "money"},
                "required": ("name",), "lines": None},
}
# The MMS documents the desk raises and tracks itself (Dada, 14 Oct 2026:
# "everything not on the desk yet, add on the desk"): a header of the fields
# BizBox's forms carry in common and the lines, each an item BizBox has. They
# go to BizBox as an ADD through psa.sp_apply_change under their own kind; the
# desk has no mirror of BizBox's existing ones until SQL01 maps a view per kind.
MMS_DOC_FIELDS = {"department": "text", "warehouse_ref": "text", "center": "text", "doc_date": "date"}
MMS_DOC_LINES = {"product_ref": "text", "description": "text", "quantity": "money", "unit_cost": "money"}
MMS_DOC_REQUIRED = {"stock_req": ("department", "warehouse_ref"), "expense_req": ("department", "warehouse_ref"),
                    "purchase_req": ("department",), "stock_issuance": ("warehouse_ref", "department"),
                    "expense_issuance": ("warehouse_ref", "department"), "physical_count": ("warehouse_ref",)}
for _k, _req in MMS_DOC_REQUIRED.items():
    ADDABLE[_k] = {"fields": dict(MMS_DOC_FIELDS), "required": _req, "lines": dict(MMS_DOC_LINES)}
DESK_KINDS = tuple(MMS_DOC_REQUIRED)


# ---------------------------------------------------------- choices (081)
# Fields whose value must be one BizBox accepts (Dada, 13 Oct 2026: "status or
# fields that needs a drop down to match bizbox choices must be done; all
# fields must not error when importing into bizbox"). Each names a list:
# BizBox's own code list once the host's lookup view is mapped and read
# (ext_lookup), else the values the mirror has seen on real records. A vendor
# is always one BizBox has named on an order or a receipt.
CHOICE_LIST = {("purchase_order", "status"): "po_status", ("purchase_order", "currency"): "currency",
               ("purchase_order", "vendor"): "vendor", ("invoice", "status"): "rr_status",
               ("product", "unit"): "unit", ("product", "category"): "category"}
# the desk's documents: a warehouse BizBox has, a department the desk knows, a
# centre from BizBox's list once SQL01 maps it (free text until then)
for _k in MMS_DOC_REQUIRED:
    CHOICE_LIST[(_k, "warehouse_ref")] = "warehouse"
    CHOICE_LIST[(_k, "department")] = "department"
    CHOICE_LIST[(_k, "center")] = "center"
SEEN_IN = {"po_status": ("ext_purchase_order", "status"), "rr_status": ("ext_invoice", "status"),
           "currency": ("ext_purchase_order", "currency"), "unit": ("ext_product", "unit"),
           "category": ("ext_product", "category")}
LIST_WORDS = {"po_status": "a status BizBox uses on purchase orders", "rr_status": "a status BizBox uses on receiving reports",
              "currency": "a currency BizBox uses", "unit": "a unit BizBox uses", "category": "a category BizBox uses",
              "vendor": "a vendor BizBox has", "warehouse": "a warehouse BizBox has", "department": "a department the desk knows",
              "center": "a centre BizBox uses"}


def choices(conn, kind: str, field: str) -> list[tuple[str, str]]:
    """(code, label) pairs the field may take; [] when the field is free text."""
    lst = CHOICE_LIST.get((kind, field))
    if lst is None:
        return []
    if lst == "vendor":
        return [(v["name"], v["name"]) for v in vendors(conn)]
    if lst == "warehouse":
        return [(w["ext_ref"], w["name"]) for w in warehouses(conn, include_inactive=False)]
    if lst == "department":
        if not db.table_exists(conn, "department"):
            return []
        return [(d["name"], d["name"]) for d in conn.execute("SELECT name FROM department WHERE retired = 0 ORDER BY name")]
    if db.table_exists(conn, "ext_lookup"):
        rows = conn.execute("SELECT code, label FROM ext_lookup WHERE source_id = ? AND list = ? AND present = 1"
                            " ORDER BY sort_no, label, code", (SOURCE, lst)).fetchall()
        if rows:
            return [(r[0], r[1] or r[0]) for r in rows]
    if lst not in SEEN_IN:
        return []                                       # no list yet: free text until BizBox's is mapped
    table, col = SEEN_IN[lst]
    return [(r[0], r[0]) for r in conn.execute(
        f"SELECT DISTINCT {col} FROM {table} WHERE source_id = ? AND present = 1 AND {col} IS NOT NULL ORDER BY {col}",
        (SOURCE,))]


def choices_from(conn, kind: str, field: str) -> str:
    """Where a field's list comes from, in words for the screen."""
    lst = CHOICE_LIST.get((kind, field))
    if lst is None:
        return ""
    if lst == "vendor":
        return "the vendors BizBox has named"
    if lst == "warehouse":
        return "the warehouses BizBox has"
    if lst == "department":
        return "the desk's departments"
    if db.table_exists(conn, "ext_lookup") and conn.execute(
            "SELECT 1 FROM ext_lookup WHERE source_id = ? AND list = ? AND present = 1 LIMIT 1", (SOURCE, lst)).fetchone():
        return "BizBox's own list"
    return "what BizBox has used so far"


def labels_for(conn, kind: str) -> dict:
    """{field: {code: label}} for the kind's fields that have a list, so a
    screen shows the word BizBox's own list gives a code (Dada, 13 Oct 2026:
    a category read 1001 until SQL01's lookup view was read)."""
    out = {}
    for (k, field), lst in CHOICE_LIST.items():
        if k != kind or lst == "vendor":
            continue
        pairs = choices(conn, kind, field)
        if any(c != l for c, l in pairs):
            out[field] = dict(pairs)
    return out


def word(labels: dict, field: str, value) -> str:
    """The label for a stored value, or the value itself."""
    if value is None:
        return ""
    return labels.get(field, {}).get(str(value), str(value))


def check_choice(conn, kind: str, field: str, value) -> None:
    """Refuse what BizBox would refuse: a value off the field's list. With no
    list at all (an empty mirror) only a vendor is refused: a purchase order
    for a vendor BizBox has never named cannot be created there."""
    lst = CHOICE_LIST.get((kind, field))
    if lst is None or value in (None, ""):
        return
    opts = choices(conn, kind, field)
    if not opts:
        if lst == "vendor":
            raise Refused("No vendor has been read from BizBox yet, so none can be named here.")
        return
    if str(value) not in {c for c, _ in opts}:
        raise Refused(f"That is not {LIST_WORDS[lst]}; pick one from the list.")


BATCH_WORDS = {"PENDING": "Waiting for approval", "APPROVED": "Approved, waiting to be sent", "SENDING": "Being sent to BizBox",
               "APPLIED": "Applied in BizBox", "REJECTED": "Refused by BizBox", "CANCELLED": "Cancelled"}
CHANGE_WORDS = {"PENDING": "Waiting for BizBox", "SENDING": "Being sent to BizBox", "APPLIED": "Applied in BizBox",
                "REJECTED": "Refused by BizBox", "CANCELLED": "Cancelled"}
MAX_BATCH = 500


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
        raise Refused("BizBox takes no edits from Dada PSA yet; the change stays approved and waits")


class ProcedureWriter(Writer):
    """The write path Dada chose (13 Oct 2026): one stored procedure SQL01
    creates inside BizBox, called under a login of its own that may do nothing
    but EXECUTE it. The procedure checks the change and writes BizBox's MMS
    tables itself, so BizBox's own flags and rules are kept; the desk never
    writes a table. Its contract, which the handoff spells out for SQL01:

        EXEC psa.sp_apply_change @change_id, @kind, @change_kind, @ext_ref,
             @field, @new_value, @payload, @requested_by, @approved_by

    returning one row (ok BIT, message NVARCHAR(400), ext_ref NVARCHAR(64)).
    ok = 1 applies the change; message is what BizBox says; ext_ref is the
    number BizBox gave a new record. ok = 0 refuses it with the message.
    The connection string is PSA_BIZBOX_WRITE_ODBC on the host, never the
    read-only one and never sa."""
    name = "procedure"

    def __init__(self, connection_string: str | None = None, procedure: str = "psa.sp_apply_change"):
        self.cs = write_odbc_string(connection_string)
        if not _IDENT.match(procedure):
            raise Refused("the procedure name must be a plain schema.name")
        self.procedure = ".".join(f"[{p}]" for p in procedure.split("."))

    @staticmethod
    def params(change) -> tuple:
        """The ten parameters, in the procedure's order; the tenth is the row
        version the desk read (BINARY(8), bytes) or NULL for a new record. A
        row version the desk cannot read is the desk's own fault, so it is a
        ValueError, which push() records as REJECTED with the reason, never a
        decline retried every run."""
        try:
            version = tstamp_bytes(change["expected_tstamp"] if "expected_tstamp" in change.keys() else None)
        except Refused as exc:
            raise ValueError(f"not sent: the row version the desk holds for this change is unreadable ({exc}); re-propose it from the record's page") from None
        return (int(change["change_id"]), change["kind"], change["change_kind"] or "EDIT", change["ext_ref"],
                change["field"], change["new_value"], change["payload"], change["requested_by"],
                change["approved_by"], version)

    def apply(self, change) -> str:
        import json as _json
        import pyodbc                                            # the host has it; the tests use a fake writer
        con = pyodbc.connect(self.cs, autocommit=False, timeout=15)
        try:
            cur = con.cursor()
            cur.execute(f"{{CALL {self.procedure} (?,?,?,?,?,?,?,?,?,?)}}", self.params(change))
            row = cur.fetchone()
            if row is None:
                con.rollback()
                raise RuntimeError("the procedure answered nothing")
            ok, message, new_ref = (list(row) + [None, None, None])[:3]
            if not ok:
                con.rollback()
                raise RuntimeError(str(message or "refused by the procedure")[:400])
            con.commit()
            return _json.dumps({"message": str(message or "")[:400], "ext_ref": str(new_ref or "")[:MAX_KEY]})
        finally:
            con.close()


def tstamp_bytes(text) -> bytes | None:
    """BizBox's tstamp as the read view gives it ('0x00000000000F4240', or the
    16 hex digits bare) back to BINARY(8); None when the desk holds none."""
    if text in (None, ""):
        return None
    h = str(text).strip()
    h = h[2:] if h[:2].lower() == "0x" else h
    if not re.fullmatch(r"[0-9A-Fa-f]{1,16}", h):
        raise Refused(f"a row version must be up to 16 hex digits; {h[:20]!r} is not")
    return bytes.fromhex(h.rjust(16, "0"))


def write_odbc_string(raw: str | None = None) -> str:
    """The write string: one condition (SQL01, 14 Oct 2026: identity is the
    grant). Unset is the off-switch (NoWriter). A string that names a login
    is refused: the write path is Windows-authenticated, as psa_desk, with
    no password anywhere; the checks for sa and for a reused read login are
    gone, subsumed and void. A guard that cannot fail is deleted, not kept."""
    cs = (raw if raw is not None else os.environ.get("PSA_BIZBOX_WRITE_ODBC", "")).strip()
    if not cs:
        raise Refused("PSA_BIZBOX_WRITE_ODBC is not set; nothing is pushed to BizBox")
    if re.search(r"(?i)(^|;)\s*(uid|user id|user)\s*=", cs):
        raise Refused("refused: the write string names a login. The write path is Windows-authenticated by decision of 14 Oct 2026 "
                      "(psa_desk, no password); if the desk has moved host, use a domain account, or change this guard deliberately.")
    return re.sub(r"(?i)(?:^|;)\s*applicationintent\s*=[^;]*", "", cs).strip(";")


def writer_in_force() -> Writer:
    """ProcedureWriter when the host names a write login, else NoWriter."""
    if os.environ.get("PSA_BIZBOX_WRITE_ODBC", "").strip():
        return ProcedureWriter()
    return NoWriter()


# ------------------------------------------------------------------ batches

def _stamp(at: datetime) -> str:
    return at.isoformat(sep=" ", timespec="minutes")


def _reason(reason: str) -> str:
    reason = " ".join((reason or "").split())
    if not reason:
        raise Refused("Say why, so the person who approves it and BizBox's owner know.")
    return reason[:2000]


def _new_batch(conn, kind: str, change_kind: str, reason: str, *, at: datetime, actor: str, payload=None) -> int:
    import json as _json
    cur = conn.execute(
        "INSERT INTO ext_batch (source_id, kind, change_kind, reason, status, payload, requested_at, requested_by)"
        " VALUES (?,?,?,?,'PENDING',?,?,?)",
        (SOURCE, LINK_KIND[kind], change_kind, reason, _json.dumps(payload) if payload is not None else None,
         _stamp(at), actor))
    return cur.lastrowid


_SAME = object()      # the cell already reads so: not a change


def line_of(conn, kind: str, doc_ref: str, line_ref: str):
    """One line of a document, by the line's own BizBox id."""
    table, col = LINE_TABLE[kind]
    return conn.execute(f"SELECT * FROM {table} WHERE source_id = ? AND {col} = ? AND ext_ref = ? AND present = 1",
                        (SOURCE, doc_ref, str(line_ref))).fetchone()


def field_word(field: str) -> str:
    """A change's field in a person's words, a line's included."""
    if field.startswith("line:"):
        parts = field.split(":", 2)
        if parts[1] == "new":
            return "New line"
        sub = parts[2] if len(parts) > 2 else ""
        return f"{FIELD_WORDS.get(sub, sub)} on line {parts[1]}"
    return FIELD_WORDS.get(field, field)


def line_words(value) -> str:
    """A new line, as stored (JSON), in words: item, description, qty at cost."""
    import json as _json
    try:
        d = _json.loads(value) if isinstance(value, str) else dict(value or {})
    except ValueError:
        return str(value)
    bits = [d.get("product_ref") or "", d.get("description") or ""]
    qty = d.get("quantity")
    cost = d.get("unit_cost")
    tail = (f"{float(qty):g}" if qty not in (None, "") else "") + (f" @ {float(cost):,.2f}" if cost not in (None, "") else "")
    return " · ".join(b for b in (" ".join(x for x in bits if x).strip(), tail) if b) or "—"


def value_word(labels: dict, field: str, value) -> str:
    """A change's value in words: a list's word for a code, a new line spelled out."""
    if field.startswith("line:new"):
        return line_words(value) if value not in (None, "") else "—"
    sub = field.split(":", 2)[2] if field.startswith("line:") else field
    if value not in (None, "") and sub in ("quantity", "received_qty"):
        try:
            return f"{float(value):g}"
        except ValueError:
            pass
    if value not in (None, "") and sub == "unit_cost":
        try:
            return f"{float(value):,.2f}"
        except ValueError:
            pass
    return word(labels, sub, value) or "—"


def _line_edit_check(conn, kind: str, rec, field: str, new_value):
    import json as _json
    parts = field.split(":", 2)
    if parts[1] == "new":
        spec = NEW_LINE_FIELDS.get(kind)
        if spec is None:
            raise Refused("A line cannot be added to this record from the desk.")
        row = new_value if isinstance(new_value, dict) else (_json.loads(new_value) if isinstance(new_value, str) and new_value.startswith("{") else {})
        kept = {}
        for f, how in spec.items():
            v = _value(row.get(f), how, f"{kind} line.{f}", WIDTH.get(f, MAX_TEXT))
            if v is not None:
                kept[f] = v
        if not kept.get("product_ref") and not kept.get("description"):
            return _SAME                                   # a blank row on the form
        if not kept.get("quantity") or float(kept["quantity"]) <= 0:
            raise Refused("A new line needs a quantity above zero.")
        if kept.get("product_ref") and get(conn, "product", kept["product_ref"]) is None:
            raise Refused(f"{kept['product_ref']} is not an item BizBox has.")
        return _json.dumps(kept)
    sub = parts[2] if len(parts) > 2 else ""
    how = EDITABLE_LINES.get(kind, {}).get(sub)
    if how is None:
        raise Refused(f"{sub or field} is not a field that can be changed on a line of this record.")
    line = line_of(conn, kind, rec["ext_ref"], parts[1])
    if line is None:
        raise Refused(f"Line {parts[1]} is not on {rec['ext_ref']} in the BizBox mirror.")
    value = _value(new_value, how, f"{kind} line.{sub}", WIDTH.get(sub, MAX_TEXT))
    current = line[sub]
    if value == current or (how == "money" and value is not None and current is not None and float(value) == float(current)):
        return _SAME
    if sub == "quantity" and (value is None or float(value) <= 0):
        raise Refused(f"Line {parts[1]}: a quantity above zero is needed.")
    if conn.execute("SELECT 1 FROM ext_change WHERE source_id = ? AND kind = ? AND ext_ref = ? AND field = ?"
                    " AND status = 'PENDING'", (SOURCE, LINK_KIND[kind], rec["ext_ref"], field)).fetchone():
        raise Refused(f"A change to {field_word(field).lower()} on {rec['ext_ref']} is already pending; cancel it first.")
    return value


def current_value(conn, kind: str, rec, field: str):
    """What BizBox has now for a change's field: the record's, or the line's."""
    if field.startswith("line:"):
        parts = field.split(":", 2)
        if parts[1] == "new":
            return None
        line = line_of(conn, kind, rec["ext_ref"], parts[1])
        return None if line is None or len(parts) < 3 else line[parts[2]]
    return rec[field]


def _edit_check(conn, kind: str, rec, field: str, new_value):
    """Every refusal an edit can meet, before any row is written: the field,
    the value's shape, BizBox's choices, a change already waiting. Returns the
    value to store, or _SAME. Checked first so a refused batch never opens:
    SQL Server keeps a burnt identity number on rollback where SQLite does
    not, and CI run 92 (13 Oct 2026) read "Batch #2" where the desk said #1."""
    if field.startswith("line:"):
        return _line_edit_check(conn, kind, rec, field, new_value)
    how = EDITABLE.get(kind, {}).get(field)
    if how is None:
        raise Refused(f"{field} is not a field that can be changed on this record.")
    value = _value(new_value, how, f"{kind}.{field}", WIDTH.get(field, MAX_TEXT))
    if value == rec[field]:
        return _SAME
    check_choice(conn, kind, field, value)
    if conn.execute("SELECT 1 FROM ext_change WHERE source_id = ? AND kind = ? AND ext_ref = ? AND field = ?"
                    " AND status = 'PENDING'", (SOURCE, LINK_KIND[kind], rec["ext_ref"], field)).fetchone():
        raise Refused(f"A change to {FIELD_WORDS[field].lower()} on {rec['ext_ref']} is already pending; cancel it first.")
    return value


def new_uid() -> str:
    """A change's own id, minted by the desk: it survives a restore of PMC_PSA,
    where change_id would be minted again (SQL01's question, 14 Oct 2026)."""
    return uuid.uuid4().hex


def _tstamp_of(rec) -> str | None:
    """The record's BizBox row version as the desk read it, if the view gives one."""
    try:
        v = rec["tstamp"]
    except (IndexError, KeyError):
        return None
    return str(v).strip() or None if v is not None else None


def _edit_insert(conn, kind: str, rec, field: str, value, *, reason: str, batch_id: int, at: datetime, actor: str) -> int:
    if field.startswith("line:") and field.split(":", 2)[1] != "new":
        line = line_of(conn, kind, rec["ext_ref"], field.split(":", 2)[1])
        old, version = current_value(conn, kind, rec, field), _tstamp_of(line) if line is not None else None
    elif field.startswith("line:"):
        old, version = None, None                           # a new line: nothing to hold a version of
    else:
        old, version = rec[field], _tstamp_of(rec)
    cur = conn.execute(
        "INSERT INTO ext_change (source_id, kind, ext_ref, field, old_value, new_value, reason, status, requested_at,"
        " requested_by, batch_id, expected_tstamp, change_uid) VALUES (?,?,?,?,?,?,?, 'PENDING', ?,?,?,?,?)",
        (SOURCE, LINK_KIND[kind], rec["ext_ref"], field, None if old is None else str(old),
         None if value is None else str(value), reason, _stamp(at), actor, batch_id, version, new_uid()))
    return cur.lastrowid


def propose(conn, kind: str, ext_ref: str, field: str, new_value: str, *, reason: str, at: datetime,
            actor: str) -> int:
    """One field on one record: a batch of one. Returns the change id."""
    rec = get(conn, kind, ext_ref)
    if rec is None:
        raise Refused("No such record in the BizBox mirror.")
    reason = _reason(reason)
    value = _edit_check(conn, kind, rec, field, new_value)
    if value is _SAME:
        raise Refused("That is the value BizBox already has.")
    bid = _new_batch(conn, kind, "EDIT", reason, at=at, actor=actor)
    cid = _edit_insert(conn, kind, rec, field, value, reason=reason, batch_id=bid, at=at, actor=actor)
    db.audit(conn, at=_stamp(at), actor=actor, action="BIZBOX_CHANGE", subject_kind="ext_change", subject_id=str(cid),
             detail=f"proposed (batch {bid}): {LINK_KIND[kind].lower()} {ext_ref} {field} {rec[field]!r} -> {value!r}")
    return cid


# propose_many and preview_many have no screen since 14 Oct 2026 (SQL01: no
# bulk-change bar over a list). They stay as the library's one-field-on-many
# batch, for an action inside a document (several lines at once) when one is
# asked for; the CLI and the tests keep them honest until then.
def propose_many(conn, kind: str, refs, field: str, new_value: str, *, reason: str, at: datetime, actor: str) -> dict:
    """The same new value for one field on many records (ticked rows): one
    batch. A record that already has the value is left out and counted."""
    refs = [r for r in dict.fromkeys(str(x).strip() for x in refs) if r]
    if not refs:
        raise Refused("Tick at least one record.")
    if len(refs) > MAX_BATCH:
        raise Refused(f"At most {MAX_BATCH} records in one batch.")
    reason = _reason(reason)
    if EDITABLE.get(kind, {}).get(field) is None:
        raise Refused(f"{field} is not a field that can be changed on these records.")
    todo, same = [], 0
    for ref in refs:
        rec = get(conn, kind, ref)
        if rec is None:
            raise Refused(f"{ref} is not in the BizBox mirror.")
        value = _edit_check(conn, kind, rec, field, new_value)
        if value is _SAME:
            same += 1
        else:
            todo.append((rec, value))
    if not todo:
        raise Refused("Every ticked record already has that value in BizBox.")
    bid = _new_batch(conn, kind, "EDIT", reason, at=at, actor=actor)
    for rec, value in todo:
        _edit_insert(conn, kind, rec, field, value, reason=reason, batch_id=bid, at=at, actor=actor)
    queued = len(todo)
    db.audit(conn, at=_stamp(at), actor=actor, action="BIZBOX_BATCH", subject_kind="ext_batch", subject_id=str(bid),
             detail=f"proposed: {LINK_KIND[kind].lower()} {field} on {queued} record(s) ({same} already so)")
    return {"batch_id": bid, "queued": queued, "same": same}


def preview_edits(conn, kind: str, edits, *, reason: str) -> dict:
    """What propose_edits would queue, for the review window (Dada, 13 Oct
    2026: "a window saying what will be changed before pushing to bizbox").
    Every check runs; nothing is written. Returns the rows that differ
    (ref, field, the words, from, to) and how many were already so."""
    reason = _reason(reason)
    labels = labels_for(conn, kind)
    rows, same = [], 0
    for ref, field, value in edits:
        rec = get(conn, kind, str(ref).strip())
        if rec is None:
            raise Refused(f"{ref} is not in the BizBox mirror.")
        kept = _edit_check(conn, kind, rec, field, value)
        if kept is _SAME:
            same += 1
            continue
        old = current_value(conn, kind, rec, field)
        rows.append({"ref": rec["ext_ref"], "field": field, "word": field_word(field),
                     "old": old, "new": kept,
                     "old_word": value_word(labels, field, old), "new_word": value_word(labels, field, kept)})
    return {"rows": rows, "same": same, "reason": reason}


def preview_many(conn, kind: str, refs, field: str, new_value: str, *, reason: str) -> dict:
    """What propose_many would queue: the same checks, nothing written."""
    refs = [r for r in dict.fromkeys(str(x).strip() for x in refs) if r]
    if not refs:
        raise Refused("Tick at least one record.")
    if len(refs) > MAX_BATCH:
        raise Refused(f"At most {MAX_BATCH} records in one batch.")
    if EDITABLE.get(kind, {}).get(field) is None:
        raise Refused(f"{field} is not a field that can be changed on these records.")
    return preview_edits(conn, kind, [(r, field, new_value) for r in refs], reason=reason)


def propose_edits(conn, kind: str, edits, *, reason: str, at: datetime, actor: str) -> dict:
    """Cells edited in place on the grid, saved in one go: (ext_ref, field,
    new_value) triples, one batch. A cell left as BizBox has it is not a
    change."""
    reason = _reason(reason)
    if len(edits) > MAX_BATCH:
        raise Refused(f"At most {MAX_BATCH} cells in one batch.")
    todo = []
    for ref, field, value in edits:
        rec = get(conn, kind, str(ref).strip())
        if rec is None:
            raise Refused(f"{ref} is not in the BizBox mirror.")
        kept = _edit_check(conn, kind, rec, field, value)
        if kept is not _SAME:
            todo.append((rec, field, kept))
    if not todo:
        raise Refused("Nothing was changed: every cell still reads what BizBox has.")
    bid = _new_batch(conn, kind, "EDIT", reason, at=at, actor=actor)
    for rec, field, value in todo:
        _edit_insert(conn, kind, rec, field, value, reason=reason, batch_id=bid, at=at, actor=actor)
    queued = len(todo)
    db.audit(conn, at=_stamp(at), actor=actor, action="BIZBOX_BATCH", subject_kind="ext_batch", subject_id=str(bid),
             detail=f"proposed: {LINK_KIND[kind].lower()} {queued} cell(s) edited")
    return {"batch_id": bid, "queued": queued}


def check_add(conn, kind: str, record: dict, lines=None, *, reason: str) -> dict:
    """What propose_add would queue, for the review window (Dada, 13 Oct
    2026): every check runs, nothing is written. Returns the record as it
    would be kept, its lines, and the reason."""
    spec = ADDABLE.get(kind)
    if spec is None:
        raise Refused(f"A new {kind.replace('_', ' ')} cannot be added from the desk.")
    reason = _reason(reason)
    rec = {}
    for f, how in spec["fields"].items():
        v = _value(record.get(f), how, f"{kind}.{f}", WIDTH.get(f, MAX_TEXT))
        if v is not None:
            rec[f] = v
    for f in spec["required"]:
        if rec.get(f) in (None, ""):
            raise Refused(f"{FIELD_WORDS.get(f, f.replace('_', ' ').capitalize())} is needed.")
    for f, v in rec.items():
        check_choice(conn, kind, f, v)
    if "ext_ref" in rec:
        if len(rec["ext_ref"]) > MAX_KEY or not re.fullmatch(r"[A-Za-z0-9._/-]+", rec["ext_ref"]):
            raise Refused("An item code is letters, digits, dots, dashes or slashes, up to 64 of them.")
        if get(conn, kind, rec["ext_ref"]) is not None:
            raise Refused(f"BizBox already has {rec['ext_ref']}.")
    kept_lines = []
    if spec["lines"]:
        for n, line in enumerate(lines or [], 1):
            row = {}
            for f, how in spec["lines"].items():
                v = _value(line.get(f), how, f"{kind} line {n}.{f}", WIDTH.get(f, MAX_TEXT))
                if v is not None:
                    row[f] = v
            if not any(row.get(f) for f in ("product_ref", "description")):
                continue                                   # a blank row on the form
            if not row.get("quantity") or float(row["quantity"]) <= 0:
                raise Refused(f"Line {n}: a quantity above zero is needed.")
            if row.get("product_ref") and get(conn, "product", row["product_ref"]) is None:
                raise Refused(f"Line {n}: {row['product_ref']} is not an item BizBox has.")
            kept_lines.append(row)
        if not kept_lines:
            raise Refused(f"A {KIND_WORDS.get(kind, kind.replace('_', ' '))} needs at least one line.")
    return {"record": rec, "lines": kept_lines, "reason": reason}


def propose_add(conn, kind: str, record: dict, lines=None, *, reason: str, at: datetime, actor: str) -> int:
    """A new record for BizBox: a purchase order with its lines, or an item.
    The record is checked field by field as the mirror checks a cell
    (check_add), kept as JSON on the batch, and shown in the grid as
    NEW-<batch> until BizBox answers with its own number. Returns the batch id."""
    checked = check_add(conn, kind, record, lines, reason=reason)
    rec, kept_lines, reason = checked["record"], checked["lines"], checked["reason"]
    payload = {"record": rec, "lines": kept_lines}
    bid = _new_batch(conn, kind, "ADD", reason, at=at, actor=actor, payload=payload)
    summary = add_summary(rec)
    conn.execute(
        "INSERT INTO ext_change (source_id, kind, ext_ref, field, old_value, new_value, reason, status, requested_at,"
        " requested_by, batch_id, change_uid) VALUES (?,?,?,?,?,?,?, 'PENDING', ?,?,?,?)",
        (SOURCE, LINK_KIND[kind], rec.get("ext_ref") or f"NEW-{bid}", "NEW", None,
         (f"{summary} ({len(kept_lines)} line(s))" if kept_lines else summary)[:MAX_TEXT], reason, _stamp(at), actor, bid, new_uid()))
    db.audit(conn, at=_stamp(at), actor=actor, action="BIZBOX_BATCH", subject_kind="ext_batch", subject_id=str(bid),
             detail=f"proposed: new {LINK_KIND[kind].lower()}" + (f" with {len(kept_lines)} line(s)" if kept_lines else ""))
    return bid


def batch(conn, batch_id: int):
    return conn.execute("SELECT * FROM ext_batch WHERE batch_id = ? AND source_id = ?", (batch_id, SOURCE)).fetchone()


def desk_document(conn, kind: str, ref: str):
    """A document the desk raised (ext_ref NEW-<batch>): its batch, the header
    as kept, its lines, and BizBox's number once applied. None when there is
    no such batch of that kind."""
    import json as _json
    if not str(ref).startswith("NEW-") or not str(ref)[4:].isdigit():
        return None
    b = batch(conn, int(str(ref)[4:]))
    if b is None or b["change_kind"] != "ADD" or b["kind"] != LINK_KIND.get(kind):
        return None
    p = payload_of(b)
    return {"batch": b, "record": p.get("record", {}), "lines": p.get("lines", []), "number": desk_numbers(conn, kind, b["batch_id"]).get(b["batch_id"])}


def _number_in(answer) -> str | None:
    """BizBox's number from an applied NEW change's answer (the procedure's
    JSON); None for anything that is not an object with ext_ref."""
    import json as _json
    if not answer:
        return None
    try:
        parsed = _json.loads(answer)
    except ValueError:
        return None
    return (str(parsed.get("ext_ref")).strip() or None) if isinstance(parsed, dict) and parsed.get("ext_ref") else None


def desk_numbers(conn, kind: str, batch_id: int | None = None) -> dict:
    """{batch_id: BizBox's number} for the desk documents of a kind that
    BizBox has applied, in one query; one batch when asked for."""
    sql = ("SELECT batch_id, answer FROM ext_change WHERE source_id = ? AND kind = ? AND field = 'NEW' AND status = 'APPLIED'"
           " AND answer IS NOT NULL")
    args = [SOURCE, LINK_KIND.get(kind, "")]
    if batch_id is not None:
        sql += " AND batch_id = ?"
        args.append(batch_id)
    out = {}
    for r in conn.execute(sql, args):
        n = _number_in(r["answer"])
        if n:
            out[r["batch_id"]] = n
    return out


def add_summary(rec: dict) -> str:
    """A new record in a few words: its name, its vendor, or the department
    and warehouse of a desk document."""
    rec = rec or {}
    return (rec.get("name") or rec.get("vendor")
            or " · ".join(str(x) for x in (rec.get("department"), rec.get("warehouse_ref")) if x) or "new record")


def replace_add(conn, kind: str, batch_id: int, record: dict, lines=None, *, reason: str, at: datetime, actor: str) -> None:
    """A desk document edited while it still waits for approval: the header
    and lines checked as on the first save, the batch's payload replaced, the
    reason kept with it, audited. Refused once a second person has approved."""
    b = batch(conn, batch_id)
    if b is None or b["change_kind"] != "ADD" or b["kind"] != LINK_KIND.get(kind):
        raise Refused("No such document on the desk.")
    if b["status"] != "PENDING":
        raise Refused(f"This document is {BATCH_WORDS[b['status']].lower()}; it can no longer be edited here.")
    checked = check_add(conn, kind, record, lines, reason=reason)
    import json as _json
    rec, kept_lines, reason = checked["record"], checked["lines"], checked["reason"]
    conn.execute("UPDATE ext_batch SET payload = ?, reason = ? WHERE batch_id = ?",
                 (_json.dumps({"record": rec, "lines": kept_lines}), reason, batch_id))
    summary = add_summary(rec)
    conn.execute("UPDATE ext_change SET new_value = ?, reason = ? WHERE batch_id = ? AND field = 'NEW'",
                 ((f"{summary} ({len(kept_lines)} line(s))" if kept_lines else summary)[:MAX_TEXT], reason, batch_id))
    db.audit(conn, at=_stamp(at), actor=actor, action="BIZBOX_BATCH", subject_kind="ext_batch", subject_id=str(batch_id),
             detail=f"edited while waiting: new {LINK_KIND[kind].lower()}, {len(kept_lines)} line(s)")


def on_hand(conn, warehouse_ref: str, item_ref: str):
    """What the warehouse holds of the item at the last read, from the ledger
    mirror (never actualqty: Bizbox Chat's stock-truth addendum); None when
    the mirror has no row, which reads as nothing there."""
    if not warehouse_ref or not item_ref or not db.table_exists(conn, "ext_stock"):
        return None
    r = conn.execute("SELECT quantity FROM ext_stock WHERE source_id = ? AND warehouse_ref = ? AND item_ref = ? AND present = 1",
                     (SOURCE, warehouse_ref, item_ref)).fetchone()
    return None if r is None else float(r[0] or 0)


def desk_currency(conn) -> str | None:
    """The currency word for a document the desk raises: the one BizBox puts on
    its purchase orders, when the mirror has seen exactly one; else none."""
    seen = [c for c, _ in choices(conn, "purchase_order", "currency")]
    return seen[0] if len(seen) == 1 else None


def batches(conn, *, status: str | None = None, kind: str | None = None, limit: int = 200):
    sql, args = ["SELECT b.*, (SELECT COUNT(*) FROM ext_change c WHERE c.batch_id = b.batch_id) AS n"
                 " FROM ext_batch b WHERE b.source_id = ?"], [SOURCE]
    if status:
        sql.append(" AND b.status = ?")
        args.append(status)
    if kind:
        sql.append(" AND b.kind = ?")
        args.append(LINK_KIND[kind])
    sql.append(" ORDER BY b.batch_id DESC LIMIT ?")
    args.append(limit)
    return conn.execute("".join(sql), args).fetchall()


def batch_changes(conn, batch_id: int):
    return conn.execute("SELECT * FROM ext_change WHERE batch_id = ? ORDER BY change_id", (batch_id,)).fetchall()


def payload_of(row) -> dict:
    import json as _json
    try:
        return _json.loads(row["payload"]) if row and row["payload"] else {}
    except ValueError:
        return {}


def approve(conn, batch_id: int, *, at: datetime, actor: str) -> None:
    """A second person says yes (Dada, 13 Oct 2026: a person with WRITE
    approves; their own queued changes need someone else)."""
    b = batch(conn, batch_id)
    if b is None:
        raise Refused("No such batch.")
    if b["status"] != "PENDING":
        raise Refused(f"That batch is already {BATCH_WORDS[b['status']].lower()}.")
    if (b["requested_by"] or "").lower() == (actor or "").lower():
        raise Refused("A change is approved by someone other than the person who asked for it.")
    conn.execute("UPDATE ext_batch SET status = 'APPROVED', approved_at = ?, approved_by = ? WHERE batch_id = ?",
                 (_stamp(at), actor, batch_id))
    db.audit(conn, at=_stamp(at), actor=actor, action="BIZBOX_BATCH", subject_kind="ext_batch", subject_id=str(batch_id),
             detail="approved")


def cancel_batch(conn, batch_id: int, *, at: datetime, actor: str, answer: str = "") -> int:
    """Cancel a batch that has not reached BizBox, and every change in it."""
    b = batch(conn, batch_id)
    if b is None:
        raise Refused("No such batch.")
    if b["status"] == "SENDING":
        raise Refused("That batch is being sent to BizBox now; it ends applied or refused, not cancelled.")
    if b["status"] not in ("PENDING", "APPROVED"):
        raise Refused(f"That batch is already {BATCH_WORDS[b['status']].lower()}.")
    n = 0
    for ch in batch_changes(conn, batch_id):
        if ch["status"] == "PENDING":
            decide(conn, ch["change_id"], "CANCELLED", answer=answer, at=at, actor=actor, settle=False)
            n += 1
    _settle(conn, batch_id, at=at, actor=actor)
    return n


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


def _settle(conn, batch_id, *, at: datetime, actor: str) -> None:
    """A batch ends when its last change has: APPLIED if every change was,
    REJECTED if any was, CANCELLED if all were."""
    if batch_id is None:
        return
    rows = batch_changes(conn, batch_id)
    if not rows or any(r["status"] in ("PENDING", "SENDING") for r in rows):
        return
    states = {r["status"] for r in rows}
    end = "REJECTED" if "REJECTED" in states else "APPLIED" if "APPLIED" in states else "CANCELLED"
    answers = "; ".join(r["answer"] for r in rows if r["answer"])
    conn.execute("UPDATE ext_batch SET status = ?, decided_at = ?, decided_by = ?, answer = ? WHERE batch_id = ?"
                 " AND status IN ('PENDING', 'APPROVED', 'SENDING')", (end, _stamp(at), actor, answers[:2000] or None, batch_id))


def decide(conn, change_id: int, status: str, *, answer: str = "", at: datetime, actor: str,
           settle: bool = True) -> None:
    """Close a proposal: CANCELLED by a person; APPLIED or REJECTED by a writer
    (or by hand, after it was done in BizBox directly)."""
    if status not in ("APPLIED", "REJECTED", "CANCELLED"):
        raise Refused("A change ends APPLIED, REJECTED or CANCELLED.")
    row = conn.execute("SELECT status, batch_id FROM ext_change WHERE change_id = ?", (change_id,)).fetchone()
    if row is None:
        raise Refused("No such change.")
    if row["status"] == "SENDING" and status == "CANCELLED":
        raise Refused("That change is being sent to BizBox now; it ends applied or refused, not cancelled.")
    if row["status"] not in ("PENDING", "SENDING"):
        raise Refused(f"That change is already {row['status'].lower()}.")
    stamp = _stamp(at)
    conn.execute("UPDATE ext_change SET status = ?, decided_at = ?, decided_by = ?, answer = ? WHERE change_id = ?",
                 (status, stamp, actor, (answer or "").strip()[:2000] or None, change_id))
    db.audit(conn, at=stamp, actor=actor, action="BIZBOX_CHANGE", subject_kind="ext_change", subject_id=str(change_id),
             detail=f"{status.lower()}" + (f": {answer}" if answer else ""))
    if settle:
        _settle(conn, row["batch_id"], at=at, actor=actor)


def pushable(conn):
    """The changes the writer may be offered: PENDING rows whose batch is
    APPROVED. A change with no batch (written before 080) is offered as it
    always was."""
    return conn.execute(
        "SELECT c.*, b.change_kind, b.payload, b.approved_by, b.approved_at FROM ext_change c"
        " LEFT JOIN ext_batch b ON b.batch_id = c.batch_id"
        " WHERE c.source_id = ? AND c.status = 'PENDING' AND (c.batch_id IS NULL OR b.status IN ('APPROVED', 'SENDING'))"
        " ORDER BY c.change_id", (SOURCE,)).fetchall()


def claim(conn, change_id: int, *, at: datetime, actor: str) -> bool:
    """The sender's one UPDATE (SQL01, 14 Oct 2026): PENDING -> SENDING on this
    row alone, so two overlapping runs cannot both send it. False when
    somebody else has it. The batch follows its first claimed change.

    The claim COMMITS: that is the mechanism, the other run must see it. So
    this is the sender's to call, on a connection with nothing else pending
    (bizbox-push), never from a request that has work of its own open."""
    cur = conn.execute("UPDATE ext_change SET status = 'SENDING', decided_by = ?, decided_at = ? WHERE change_id = ? AND status = 'PENDING'",
                       (actor, _stamp(at), change_id))
    if cur.rowcount != 1:
        return False
    conn.execute("UPDATE ext_batch SET status = 'SENDING' WHERE batch_id = (SELECT batch_id FROM ext_change WHERE change_id = ?)"
                 " AND status = 'APPROVED'", (change_id,))
    conn.commit()
    return True


def unclaim(conn, change_id: int) -> None:
    """The inverse of claim, for a change that was never sent (the writer
    declined before calling BizBox): back to PENDING, the batch back to
    APPROVED once none of its changes is being sent. Committed, as the claim was."""
    conn.execute("UPDATE ext_change SET status = 'PENDING', decided_by = NULL, decided_at = NULL WHERE change_id = ? AND status = 'SENDING'",
                 (change_id,))
    conn.execute("UPDATE ext_batch SET status = 'APPROVED' WHERE batch_id = (SELECT batch_id FROM ext_change WHERE change_id = ?)"
                 " AND status = 'SENDING' AND NOT EXISTS (SELECT 1 FROM ext_change WHERE batch_id = ext_batch.batch_id AND status = 'SENDING')",
                 (change_id,))
    conn.commit()


def push(conn, writer: Writer | None = None, *, at: datetime, actor: str = "writer") -> dict:
    """Offer every approved change to the writer, one at a time: claim it
    (PENDING -> SENDING, committed), apply it, then APPLIED or REJECTED with
    BizBox's words, committed. With NoWriter nothing is claimed and nothing
    moves. A change the writer refuses with Refused goes back to PENDING: it
    was never sent. A row another run holds is skipped."""
    writer = writer or NoWriter()
    counts = {"applied": 0, "rejected": 0, "pending": 0, "skipped": 0}
    for ch in pushable(conn):
        if isinstance(writer, NoWriter):
            counts["pending"] += 1
            continue
        if not claim(conn, ch["change_id"], at=at, actor=actor):
            counts["skipped"] += 1
            continue
        item = dict(ch)
        item["change_kind"] = item.get("change_kind") or "EDIT"
        try:
            answer = writer.apply(item)
        except Refused:
            unclaim(conn, ch["change_id"])
            counts["pending"] += 1
            continue
        except Exception as exc:                    # noqa: BLE001 - BizBox's answer, recorded
            decide(conn, ch["change_id"], "REJECTED", answer=str(exc)[:500], at=at, actor=actor)
            conn.commit()
            counts["rejected"] += 1
            continue
        decide(conn, ch["change_id"], "APPLIED", answer=answer, at=at, actor=actor)
        conn.commit()
        counts["applied"] += 1
    return counts


def stuck_sending(conn, *, now: datetime, older_than_minutes: int = 15) -> list:
    """Changes claimed by a run that never finished (a crash between the claim
    and the answer). Nobody retries them by accident: a person reads BizBox,
    then decides each one APPLIED or REJECTED by hand (bizbox-changes)."""
    cutoff = _stamp(now - timedelta(minutes=older_than_minutes))
    return conn.execute("SELECT * FROM ext_change WHERE source_id = ? AND status = 'SENDING' AND COALESCE(decided_at, '') <= ?"
                        " ORDER BY change_id", (SOURCE, cutoff)).fetchall()


def vendors(conn, *, q: str = "") -> list:
    """The vendors BizBox names on purchase orders and receipts: the name, how
    many of each, and the sums. The mirror has no vendor kind of its own
    (SQL01, 29 Sep 2026: the name comes from BizBox's own function), so
    this reads the names the records carry."""
    like = _like(q.lower()) if q else None
    rows = conn.execute(
        "SELECT vendor AS name, SUM(po) AS pos, SUM(po_total) AS po_total, SUM(rr) AS receipts, SUM(rr_total) AS rr_total"
        " FROM (SELECT vendor, 1 AS po, COALESCE(total, 0) AS po_total, 0 AS rr, 0 AS rr_total FROM ext_purchase_order"
        "        WHERE source_id = ? AND present = 1 AND vendor IS NOT NULL"
        "       UNION ALL"
        "       SELECT party, 0, 0, 1, COALESCE(total, 0) FROM ext_invoice"
        "        WHERE source_id = ? AND present = 1 AND party IS NOT NULL) v"
        + (" WHERE LOWER(vendor) LIKE ? ESCAPE '\\'" if like else "")
        + " GROUP BY vendor ORDER BY vendor",
        [SOURCE, SOURCE] + ([like] if like else [])).fetchall()
    return rows


# ------------------------------------------------- warehouses, medicines (083)

def warehouses(conn, *, q: str = "", include_inactive: bool = True) -> list:
    """Every warehouse the mirror holds, by group then name, active first."""
    if not db.table_exists(conn, "ext_warehouse"):
        return []
    where, args = _filter("warehouse", q, False)
    if not include_inactive:
        where += " AND COALESCE(active, 1) = 1"
    return conn.execute(f"SELECT *{where} ORDER BY COALESCE(group_name, ''), COALESCE(active, 1) DESC, name", args).fetchall()


def medicines(conn, *, q: str = "", controlled: bool | None = None, limit: int = PAGE, offset: int = 0) -> tuple[list, int]:
    """The medicines with their item's name and category; a page and the
    count. `controlled` filters the flag."""
    if not db.table_exists(conn, "ext_medicine"):
        return [], 0
    sql, args = [" FROM ext_medicine m LEFT JOIN ext_product p ON p.source_id = m.source_id AND p.ext_ref = m.ext_ref"
                 " WHERE m.source_id = ? AND m.present = 1"], [SOURCE]
    if controlled is not None:
        sql.append(" AND COALESCE(m.controlled, 0) = ?"); args.append(1 if controlled else 0)
    for word in (q or "").split()[:4]:
        cols = ("m.ext_ref", "p.name", "m.generic", "m.dosage", "m.doh_ref", "m.mims_ref", "m.admin_group")
        sql.append(" AND (" + " OR ".join(f"LOWER(COALESCE({c}, '')) LIKE ? ESCAPE '\\'" for c in cols) + ")")
        args += [_like(word.lower())] * len(cols)
    where = "".join(sql)
    total = conn.execute(f"SELECT COUNT(*){where}", args).fetchone()[0]
    rows = conn.execute(f"SELECT m.*, p.name AS item_name, p.category AS category, p.unit AS unit, p.present AS item_present{where}"
                        " ORDER BY COALESCE(p.name, m.ext_ref), m.ext_ref LIMIT ? OFFSET ?", [*args, limit, offset]).fetchall()
    return rows, total


def medicine_of(conn, item_ref: str):
    if not db.table_exists(conn, "ext_medicine"):
        return None
    return conn.execute("SELECT * FROM ext_medicine WHERE source_id = ? AND ext_ref = ? AND present = 1", (SOURCE, item_ref)).fetchone()


def po_lines(conn, po_ref: str):
    return conn.execute("SELECT * FROM ext_po_line WHERE source_id = ? AND po_ref = ? AND present = 1"
                        " ORDER BY line_no, ext_ref", (SOURCE, po_ref)).fetchall()


# ------------------------------------------------- stock and movements (084)

# BizBox's movement kinds in a person's words. The two-letter codes are the
# ledger's doctype, named from BizBox's own stock-card procedure (SQL01, 14 Oct
# 2026); the longer keys are what a view may already spell out. A code that is
# BizBox's asset family (PP, AT, DP, GL, RT, RS) has no word: the code is shown.
MOVE_WORDS = {"CH": "Charged", "CA": "Charged", "CN": "Returned by patient", "DC": "Charge deleted", "DR": "Received",
              "PI": "Received (petty cash)", "PR": "Returned to supplier", "SS": "Transferred", "EI": "Issued",
              "MP": "Produced", "QA": "Adjusted", "PC": "Counted",
              "RECEIPT": "Received", "RECEIVE": "Received", "RR": "Received", "ISSUE": "Issued", "ISSUANCE": "Issued",
              "TRANSFER_IN": "Transferred in", "TRANSFER_OUT": "Transferred out", "TRANSFER": "Transferred",
              "ADJUST": "Adjusted", "ADJUSTMENT": "Adjusted", "ADJ_IN": "Adjusted up", "ADJ_OUT": "Adjusted down",
              "COUNT": "Counted", "RETURN": "Returned", "CONSUME": "Used", "SALE": "Sold", "PURCHASE": "Received"}
CODE_ONLY = {"PP", "AT", "DP", "GL", "RT", "RS"}
# The stock card's own three buckets (SQL01's doctypes document, 14 Oct 2026:
# "Receipts = PR, DR, PI · Issuances = CA, CH, CN, DC · Transfers = QA, SS, MP,
# PC, EI"), the product's grouping and not the desk's. A view that spells a
# kind out lands where its plain meaning puts it; a kind in no bucket (the
# asset family, a word nobody has placed) is "Other" and still listed.
BUCKETS = {"Receipts": ("PR", "DR", "PI", "RECEIPT", "RECEIVE", "RR", "PURCHASE"),
           "Issuances": ("CA", "CH", "CN", "DC", "CONSUME", "SALE"),
           "Transfers": ("QA", "SS", "MP", "PC", "EI", "ISSUE", "ISSUANCE", "TRANSFER_IN", "TRANSFER_OUT", "TRANSFER",
                         "ADJUST", "ADJUSTMENT", "ADJ_IN", "ADJ_OUT", "COUNT")}
OTHER_BUCKET = "Other"
_BUCKET_OF = {code: name for name, codes in BUCKETS.items() for code in codes}


def bucket_of(kind) -> str:
    """The bucket a movement kind sits in, by BizBox's own grouping; Other when none."""
    key = (kind or "").strip().upper().replace(" ", "_").replace("-", "_")
    return _BUCKET_OF.get(key, OTHER_BUCKET)


def _bucket_clause(bucket: str, alias: str = "m") -> tuple[str, list]:
    """The SQL that keeps a bucket's kinds (or, for Other, drops every bucketed kind)."""
    col = f"UPPER(COALESCE({alias}.kind, ''))" if alias else "UPPER(COALESCE(kind, ''))"
    if bucket == OTHER_BUCKET:
        every = sorted(_BUCKET_OF)
        return f" AND {col} NOT IN ({','.join('?' * len(every))})", every
    codes = BUCKETS.get(bucket)
    if not codes:
        return "", []
    return f" AND {col} IN ({','.join('?' * len(codes))})", list(codes)


def move_word(kind) -> str:
    """The word for a movement kind; the code itself for the asset family and
    for a code nobody has named yet (never a BizBox description: the fence)."""
    k = (kind or "").strip()
    key = k.upper().replace(" ", "_").replace("-", "_")
    if key in CODE_ONLY:
        return k
    if key in MOVE_WORDS:
        return MOVE_WORDS[key]
    return k if len(k) <= 3 and k.isalpha() else (k.replace("_", " ").capitalize() or "Moved")


_STOCK_FROM = (" FROM ext_stock s LEFT JOIN ext_product p ON p.source_id = s.source_id AND p.ext_ref = s.item_ref"
               " LEFT JOIN ext_warehouse w ON w.source_id = s.source_id AND w.ext_ref = s.warehouse_ref"
               " WHERE s.source_id = ? AND s.present = 1")
_STOCK_COLS = ("s.ext_ref, s.warehouse_ref, s.item_ref, s.quantity, s.as_of, COALESCE(s.unit_cost, p.unit_cost) AS unit_cost,"
               " s.quantity * COALESCE(s.unit_cost, p.unit_cost, 0) AS value, p.name AS item_name, p.unit, p.category,"
               " p.present AS item_present, w.name AS warehouse_name, w.group_name")


def stock(conn, *, warehouse: str = "", item: str = "", q: str = "", limit: int = PAGE, offset: int = 0) -> tuple[list, int]:
    """Stock on hand: every line, or one warehouse's, or one item's, with the
    item's and the warehouse's names and a value at the item's unit cost
    when the view gives none. (rows, total)."""
    sql, args = [_STOCK_FROM], [SOURCE]
    if warehouse:
        sql.append(" AND s.warehouse_ref = ?")
        args.append(warehouse)
    if item:
        sql.append(" AND s.item_ref = ?")
        args.append(item)
    for word in (q or "").split()[:4]:
        sql.append(" AND (LOWER(COALESCE(p.name, '')) LIKE ? ESCAPE '\\' OR LOWER(s.item_ref) LIKE ? ESCAPE '\\')")
        args += [_like(word.lower())] * 2
    where = "".join(sql)
    total = conn.execute("SELECT COUNT(*)" + where, args).fetchone()[0]
    rows = conn.execute(f"SELECT {_STOCK_COLS}" + where + " ORDER BY w.group_name, w.name, p.name, s.item_ref LIMIT ? OFFSET ?",
                        [*args, limit, offset]).fetchall()
    return rows, total


def stock_of_item(conn, item_ref: str) -> list:
    return conn.execute(f"SELECT {_STOCK_COLS}" + _STOCK_FROM + " AND s.item_ref = ? ORDER BY w.group_name, w.name",
                        (SOURCE, item_ref)).fetchall()


def stock_summary(conn) -> dict:
    """Lines, items, warehouses holding stock, the value at unit cost, and
    the newest as-of the view gave."""
    r = conn.execute(
        "SELECT COUNT(*) AS lines, COUNT(DISTINCT s.item_ref) AS items, COUNT(DISTINCT s.warehouse_ref) AS warehouses,"
        " COALESCE(SUM(s.quantity * COALESCE(s.unit_cost, p.unit_cost, 0)), 0) AS value, MAX(s.as_of) AS as_of,"
        " MAX(s.synced_at) AS synced_at"
        " FROM ext_stock s LEFT JOIN ext_product p ON p.source_id = s.source_id AND p.ext_ref = s.item_ref"
        " WHERE s.source_id = ? AND s.present = 1", (SOURCE,)).fetchone()
    return {"lines": r["lines"], "items": r["items"], "warehouses": r["warehouses"], "value": float(r["value"] or 0),
            "as_of": r["as_of"], "synced_at": r["synced_at"]}


def stock_by_warehouse(conn) -> list:
    """One row per warehouse holding stock: lines, items and value, largest first."""
    return conn.execute(
        "SELECT s.warehouse_ref, w.name AS warehouse_name, w.group_name, COUNT(*) AS n, COUNT(DISTINCT s.item_ref) AS items,"
        " COALESCE(SUM(s.quantity * COALESCE(s.unit_cost, p.unit_cost, 0)), 0) AS value"
        + _STOCK_FROM + " GROUP BY s.warehouse_ref, w.name, w.group_name ORDER BY value DESC, n DESC", (SOURCE,)).fetchall()


def movements(conn, *, item: str = "", warehouse: str = "", days: int = 30, kind: str = "", bucket: str = "",
              now: datetime | None = None, limit: int = PAGE, offset: int = 0) -> tuple[list, int]:
    """The item ledger inside a window of days, newest first, for one item,
    one warehouse, or every one; one kind, or one of the stock card's buckets;
    with the names. (rows, total)."""
    since = ((now or datetime.now()).date() - timedelta(days=max(1, int(days)))).isoformat()
    sql = [" FROM ext_movement m LEFT JOIN ext_product p ON p.source_id = m.source_id AND p.ext_ref = m.item_ref"
           " LEFT JOIN ext_warehouse w ON w.source_id = m.source_id AND w.ext_ref = m.warehouse_ref"
           " WHERE m.source_id = ? AND m.present = 1 AND m.moved_on >= ?"]
    args: list = [SOURCE, since]
    if item:
        sql.append(" AND m.item_ref = ?")
        args.append(item)
    if warehouse:
        sql.append(" AND m.warehouse_ref = ?")
        args.append(warehouse)
    if kind:
        sql.append(" AND UPPER(COALESCE(m.kind, '')) = ?")
        args.append(kind.upper())
    if bucket:
        clause, more = _bucket_clause(bucket)
        sql.append(clause)
        args.extend(more)
    where = "".join(sql)
    total = conn.execute("SELECT COUNT(*)" + where, args).fetchone()[0]
    rows = conn.execute(
        "SELECT m.*, p.name AS item_name, p.unit, w.name AS warehouse_name, w.group_name" + where
        + " ORDER BY m.moved_on DESC, m.ext_ref DESC LIMIT ? OFFSET ?", [*args, limit, offset]).fetchall()
    return rows, total


def movement_kinds(conn, *, days: int = 30, now: datetime | None = None, bucket: str = "") -> list:
    """(kind, word, count) inside the window, most common first; one bucket's when asked."""
    since = ((now or datetime.now()).date() - timedelta(days=max(1, int(days)))).isoformat()
    clause, more = _bucket_clause(bucket, alias="") if bucket else ("", [])
    out = conn.execute("SELECT UPPER(COALESCE(kind, '')) AS k, COUNT(*) AS n FROM ext_movement WHERE source_id = ? AND present = 1"
                       f" AND moved_on >= ?{clause} GROUP BY UPPER(COALESCE(kind, '')) ORDER BY n DESC, k", (SOURCE, since, *more)).fetchall()
    return [(r["k"], move_word(r["k"]), r["n"]) for r in out]


def movement_buckets(conn, *, days: int = 30, now: datetime | None = None) -> list:
    """(bucket, count) inside the window in the stock card's order, Other last
    and only when something sits in it."""
    counts = {b: 0 for b in BUCKETS}
    counts[OTHER_BUCKET] = 0
    for k, _, n in movement_kinds(conn, days=days, now=now):
        counts[bucket_of(k)] += n
    return [(b, n) for b, n in counts.items() if b != OTHER_BUCKET or n]


def movement_window(conn) -> tuple[str | None, str | None]:
    """The oldest and newest movement the desk holds: what the view's window covers."""
    r = conn.execute("SELECT MIN(moved_on) AS a, MAX(moved_on) AS b FROM ext_movement WHERE source_id = ? AND present = 1",
                     (SOURCE,)).fetchone()
    return (r["a"], r["b"]) if r else (None, None)


def rr_lines(conn, rr_ref: str) -> list:
    if not db.table_exists(conn, "ext_rr_line"):
        return []
    return conn.execute("SELECT * FROM ext_rr_line WHERE source_id = ? AND rr_ref = ? AND present = 1 ORDER BY line_no, ext_ref",
                        (SOURCE, rr_ref)).fetchall()


def received_against(conn, po_ref: str) -> list:
    """The receiving lines that name a purchase order, each with its receiving
    report's date, vendor and status beside it (the order's other half)."""
    if not db.table_exists(conn, "ext_rr_line"):
        return []
    return conn.execute(
        "SELECT l.*, i.invoiced_on, i.party, i.status AS rr_status FROM ext_rr_line l"
        " LEFT JOIN ext_invoice i ON i.source_id = l.source_id AND i.ext_ref = l.rr_ref"
        " WHERE l.source_id = ? AND l.present = 1 AND l.po_ref = ? ORDER BY i.invoiced_on, l.rr_ref, l.line_no, l.ext_ref",
        (SOURCE, po_ref)).fetchall()


# ----------------------------------------------- after a restore (SQL01 §5)

def reconcile(conn) -> list[dict]:
    """Read-only: for every change the desk recorded as APPLIED, does the
    mirror still show it? An edit: the field reads the value the desk sent.
    A new record: the number BizBox gave it is present. Run after a restore
    into BizBox's database (LiveDB_PMC was restored into twice, July 2026),
    once the hourly read has run; what is missing is re-queued deliberately
    (requeue), never by a guard on every write."""
    import json as _json
    out = []
    for ch in conn.execute("SELECT c.*, b.change_kind, b.payload FROM ext_change c LEFT JOIN ext_batch b ON b.batch_id = c.batch_id"
                           " WHERE c.source_id = ? AND c.status = 'APPLIED' ORDER BY c.change_id", (SOURCE,)):
        kind = BACK_KIND.get(ch["kind"])
        row = {"change_id": ch["change_id"], "kind": kind or ch["kind"], "ext_ref": ch["ext_ref"], "field": ch["field"],
               "sent": ch["new_value"], "decided_at": ch["decided_at"], "mirror": None, "verdict": ""}
        if kind not in KINDS:
            row["verdict"] = "not mirrored: cannot be checked from the desk"
            out.append(row)
            continue
        if (ch["change_kind"] or "EDIT") == "ADD":
            ref = ch["ext_ref"]
            try:
                parsed = _json.loads(ch["answer"] or "{}")
            except ValueError:
                parsed = None
            if isinstance(parsed, dict) and parsed.get("ext_ref"):
                ref = str(parsed["ext_ref"])
            rec = get(conn, kind, ref) if ref and not ref.startswith("NEW-") else None
            row["ext_ref"] = ref
            row["mirror"] = "present" if rec is not None and rec["present"] else ("absent" if rec is not None else "none")
            row["verdict"] = "holds" if rec is not None and rec["present"] else "missing: BizBox no longer has the record the desk created"
        else:
            rec = get(conn, kind, ch["ext_ref"])
            if rec is None or ch["field"] not in rec.keys():
                row["verdict"] = "missing: the record is not in the mirror"
            else:
                now = rec[ch["field"]]
                row["mirror"] = None if now is None else str(now)
                same = (str(now) if now is not None else "") == (ch["new_value"] or "")
                try:
                    same = same or float(now) == float(ch["new_value"])
                except (TypeError, ValueError):
                    pass
                row["verdict"] = "holds" if same else "differs: BizBox reads another value now (a later edit, or a restore)"
        out.append(row)
    return out


def requeue(conn, change_ids, *, reason: str, at: datetime, actor: str) -> list[int]:
    """Deliberately, after reconcile: an APPLIED change BizBox no longer shows
    becomes a new batch, PENDING, for a second person to approve again. The
    old row is left as it was. Returns the new batch ids."""
    reason = _reason(reason)
    out = []
    for cid in change_ids:
        if not str(cid).strip().isdigit():
            raise Refused(f"{cid!r} is not a change id")
        ch = conn.execute("SELECT c.*, b.change_kind, b.payload FROM ext_change c LEFT JOIN ext_batch b ON b.batch_id = c.batch_id"
                          " WHERE c.change_id = ? AND c.source_id = ?", (int(str(cid).strip()), SOURCE)).fetchone()
        if ch is None or ch["status"] != "APPLIED":
            raise Refused(f"change {cid} is not an applied change")
        kind = BACK_KIND.get(ch["kind"])
        if kind not in KINDS:
            raise Refused(f"change {cid} is a {KIND_WORDS.get(kind, ch['kind'].lower())}, which the desk does not mirror; propose it again from its page")
        change_kind = ch["change_kind"] or "EDIT"
        payload = ch["payload"]
        bid = _new_batch(conn, kind, change_kind, reason, at=at, actor=actor,
                         payload=json.loads(payload) if payload else None)
        rec = get(conn, kind, ch["ext_ref"]) if change_kind == "EDIT" else None
        conn.execute(
            "INSERT INTO ext_change (source_id, kind, ext_ref, field, old_value, new_value, reason, status, requested_at,"
            " requested_by, batch_id, expected_tstamp, change_uid) VALUES (?,?,?,?,?,?,?, 'PENDING', ?,?,?,?,?)",
            (SOURCE, ch["kind"], ch["ext_ref"] if change_kind == "EDIT" else f"NEW-{bid}", ch["field"],
             None if rec is None or ch["field"] not in rec.keys() or rec[ch["field"]] is None else str(rec[ch["field"]]),
             ch["new_value"], reason, _stamp(at), actor, bid, _tstamp_of(rec) if rec is not None else None, new_uid()))
        db.audit(conn, at=_stamp(at), actor=actor, action="BIZBOX_BATCH", subject_kind="ext_batch", subject_id=str(bid),
                 detail=f"re-queued change {cid} after reconcile: {reason}")
        out.append(bid)
    return out

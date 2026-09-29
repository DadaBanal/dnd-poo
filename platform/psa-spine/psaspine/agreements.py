"""Agreements, made and kept on the desk (045).

BizBox holds no supplier agreements (SQL01, 29 Sep 2026, MEASURED), so Dada
asked for them here: "the agreements need to exist they can add it on the psa
... and add the needed invoices and whatever is exisitng on bizbox". An
agreement is the desk's own record, in the reference PSA's shape: a name, the
other party, a term, a status and an amount. From it, staff name the mirrored
BizBox invoices, purchase orders and products it covers. The coverings live
in the desk's own table, so `sync-bizbox` never touches them, and nothing
here writes to BizBox or to the mirror.

Who may create, edit or cover is a Security roles matter (Finance: Read to
see, Write to change) and which roles get Write is Dada's decision, made in
Setup › Security roles, not here.
"""
from __future__ import annotations

import sqlite3
from datetime import date, datetime

from . import bizbox, db

STATUSES = {"DRAFT": "Draft", "ACTIVE": "Active", "INACTIVE": "Inactive", "CANCELLED": "Cancelled"}
# the mirror kinds an agreement covers, by the mirror's own kind word
COVERS = {"invoice": "INVOICE", "purchase_order": "PURCHASE_ORDER", "product": "PRODUCT"}
WORDS = {"INVOICE": "Invoices", "PURCHASE_ORDER": "Purchase orders", "PRODUCT": "Products"}
FIELDS = ("name", "party", "starts_on", "ends_on", "status", "amount", "currency", "notes")
FIELD_WORDS = {"name": "Name", "party": "Party", "starts_on": "Starts", "ends_on": "Ends", "status": "Status",
               "amount": "Amount", "currency": "Currency", "notes": "Notes"}


class Refused(ValueError):
    """A sentence for the person; nothing was written."""


def _stamp(at: datetime) -> str:
    return at.isoformat(sep=" ", timespec="minutes")


def _day(value, what: str) -> str | None:
    text = (value or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError:
        raise Refused(f"{what}: write a date as YYYY-MM-DD.") from None


def _amount(value) -> float | None:
    if value in (None, ""):
        return None
    try:
        v = round(float(str(value).replace(",", "")), 4)
    except (TypeError, ValueError):
        raise Refused("The amount is a number.") from None
    if v < 0:
        raise Refused("The amount is not negative.")
    return v


def _text(value, width: int) -> str | None:
    text = " ".join(str(value or "").split())[:width]
    return text or None


def _clean(fields: dict) -> dict:
    out = {}
    if "name" in fields:
        out["name"] = _text(fields["name"], 200)
        if not out["name"]:
            raise Refused("An agreement needs a name.")
    if "party" in fields:
        out["party"] = _text(fields["party"], 200)
    if "starts_on" in fields:
        out["starts_on"] = _day(fields["starts_on"], "Starts")
    if "ends_on" in fields:
        out["ends_on"] = _day(fields["ends_on"], "Ends")
    if "status" in fields:
        if fields["status"] not in STATUSES:
            raise Refused("No such status.")
        out["status"] = fields["status"]
    if "amount" in fields:
        out["amount"] = _amount(fields["amount"])
    if "currency" in fields:
        out["currency"] = (_text(fields["currency"], 8) or "").upper() or None
    if "notes" in fields:
        out["notes"] = " ".join(str(fields["notes"] or "").split("\r")).strip()[:4000] or None
    return out


def _audit(conn, at: datetime, actor: str, subject: str, detail: str) -> None:
    db.audit(conn, at=_stamp(at), actor=actor, action="AGREEMENT", subject_kind="agreement", subject_id=subject,
             detail=detail)


def _next_id(conn) -> str:
    n = 0
    for (aid,) in conn.execute("SELECT agreement_id FROM agreement"):
        try:
            n = max(n, int(aid.split("-", 1)[1]))
        except (IndexError, ValueError):
            continue
    return f"AGR-{n + 1:04d}"


# ------------------------------------------------------------ the record

def create(conn: sqlite3.Connection, *, name: str, party=None, starts_on=None, ends_on=None, amount=None,
           currency=None, notes=None, status: str = "DRAFT", at: datetime, actor: str) -> str:
    f = _clean({"name": name, "party": party, "starts_on": starts_on, "ends_on": ends_on, "amount": amount,
                "currency": currency, "notes": notes, "status": status})
    if f["starts_on"] and f["ends_on"] and f["ends_on"] < f["starts_on"]:
        raise Refused("An agreement ends after it starts.")
    aid = _next_id(conn)
    stamp = _stamp(at)
    conn.execute("INSERT INTO agreement (agreement_id, name, party, starts_on, ends_on, status, amount, currency, notes,"
                 " created_at, created_by, updated_at, updated_by) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                 (aid, f["name"], f["party"], f["starts_on"], f["ends_on"], f["status"], f["amount"], f["currency"],
                  f["notes"], stamp, actor, stamp, actor))
    _audit(conn, at, actor, aid, f"agreement created: {f['name']}")
    return aid


def get(conn, agreement_id: str):
    return conn.execute("SELECT * FROM agreement WHERE agreement_id = ?", (agreement_id,)).fetchone()


def all_(conn, *, status: str | None = None, q: str = ""):
    """Every agreement, with how many records it covers; a status and a search
    narrow it. Cancelled ones sort last."""
    sql = ["SELECT a.*, (SELECT COUNT(*) FROM agreement_item i WHERE i.agreement_id = a.agreement_id) AS items"
           " FROM agreement a WHERE 1 = 1"]
    args: list = []
    if status:
        sql.append(" AND a.status = ?")
        args.append(status)
    for word in (q or "").split()[:4]:
        like = bizbox._like(word.lower())
        sql.append(" AND (LOWER(a.agreement_id) LIKE ? ESCAPE '\\' OR LOWER(a.name) LIKE ? ESCAPE '\\'"
                   " OR LOWER(COALESCE(a.party, '')) LIKE ? ESCAPE '\\')")
        args += [like, like, like]
    sql.append(" ORDER BY CASE a.status WHEN 'CANCELLED' THEN 1 ELSE 0 END, a.name")
    return conn.execute("".join(sql), args).fetchall()


def update(conn, agreement_id: str, *, at: datetime, actor: str, **fields) -> str:
    row = get(conn, agreement_id)
    if row is None:
        raise Refused("No such agreement.")
    f = _clean({k: v for k, v in fields.items() if k in FIELDS})
    merged = {k: (f[k] if k in f else row[k]) for k in FIELDS}
    if merged["starts_on"] and merged["ends_on"] and merged["ends_on"] < merged["starts_on"]:
        raise Refused("An agreement ends after it starts.")
    changes = {k: v for k, v in f.items() if v != row[k]}
    if not changes:
        return "nothing changed"
    sets = ", ".join(f"{k} = ?" for k in changes)
    conn.execute(f"UPDATE agreement SET {sets}, updated_at = ?, updated_by = ? WHERE agreement_id = ?",
                 [*changes.values(), _stamp(at), actor, agreement_id])
    words = "; ".join(f"{FIELD_WORDS[k]} {row[k] if row[k] is not None else '-'} -> {v if v is not None else '-'}"
                      for k, v in changes.items() if k != "notes") + ("; notes" if "notes" in changes else "")
    words = words.strip("; ")
    _audit(conn, at, actor, agreement_id, words)
    return words


def set_status(conn, agreement_id: str, status: str, *, at: datetime, actor: str) -> str:
    return update(conn, agreement_id, at=at, actor=actor, status=status)


# ------------------------------------------------------------ what it covers

def add_item(conn, agreement_id: str, kind: str, ext_ref: str, *, note=None, at: datetime, actor: str) -> bool:
    """Name a mirrored BizBox record as covered. The record must be in the
    mirror (present or, if it has gone from BizBox, kept); the mirror itself
    is not touched. Returns False when it was already covered."""
    row = get(conn, agreement_id)
    if row is None:
        raise Refused("No such agreement.")
    if row["status"] == "CANCELLED":
        raise Refused("A cancelled agreement covers nothing new; reopen it first.")
    if kind not in COVERS:
        raise Refused("An agreement covers invoices, purchase orders and products.")
    ext_ref = (ext_ref or "").strip()
    if not ext_ref or bizbox.get(conn, kind, ext_ref) is None:
        raise Refused(f"No {bizbox.LABEL[kind].lower()[:-1]} {ext_ref!r} in the BizBox mirror; check the number, or sync first.")
    if conn.execute("SELECT 1 FROM agreement_item WHERE agreement_id = ? AND source_id = ? AND kind = ? AND ext_ref = ?",
                    (agreement_id, bizbox.SOURCE, COVERS[kind], ext_ref)).fetchone():
        return False
    conn.execute("INSERT INTO agreement_item (agreement_id, source_id, kind, ext_ref, added_at, added_by, note)"
                 " VALUES (?,?,?,?,?,?,?)", (agreement_id, bizbox.SOURCE, COVERS[kind], ext_ref, _stamp(at), actor,
                                             _text(note, 400)))
    _audit(conn, at, actor, agreement_id, f"covers {COVERS[kind].lower()} {ext_ref}")
    return True


def remove_item(conn, agreement_id: str, kind: str, ext_ref: str, *, at: datetime, actor: str) -> bool:
    if kind not in COVERS or get(conn, agreement_id) is None:
        raise Refused("No such agreement or kind.")
    cur = conn.execute("DELETE FROM agreement_item WHERE agreement_id = ? AND source_id = ? AND kind = ? AND ext_ref = ?",
                       (agreement_id, bizbox.SOURCE, COVERS[kind], (ext_ref or "").strip()))
    if not cur.rowcount:
        return False
    _audit(conn, at, actor, agreement_id, f"no longer covers {COVERS[kind].lower()} {ext_ref}")
    return True


def items(conn, agreement_id: str) -> list[dict]:
    """What an agreement covers, each with its mirrored record (or None if the
    mirror has lost it entirely, which the sync never does) and whether BizBox
    still has it. Three queries whatever the count."""
    rows = [dict(r) for r in conn.execute(
        "SELECT * FROM agreement_item WHERE agreement_id = ? ORDER BY kind, ext_ref", (agreement_id,))]
    back = {v: k for k, v in COVERS.items()}
    for word, kind in back.items():
        refs = [r["ext_ref"] for r in rows if r["kind"] == word]
        found: dict = {}
        table = bizbox.KINDS[kind][0]
        for i in range(0, len(refs), 200):
            chunk = refs[i:i + 200]
            for rec in conn.execute(f"SELECT * FROM {table} WHERE source_id = ? AND ext_ref IN ({','.join('?' * len(chunk))})",
                                    [bizbox.SOURCE, *chunk]):
                found[rec["ext_ref"]] = rec
        for r in rows:
            if r["kind"] == word:
                r["mirror_kind"] = kind
                r["record"] = found.get(r["ext_ref"])
                r["present"] = bool(r["record"] and r["record"]["present"])
    return rows


def totals(conn, agreement_id: str) -> dict:
    """Per covered kind: how many, and the sum of the mirrored totals where the
    kind has one (invoices and purchase orders; products have a unit cost, not
    a total). Absent records still count: they were covered."""
    out = {}
    for word, kind in {v: k for k, v in COVERS.items()}.items():
        table = bizbox.KINDS[kind][0]
        money = "r.total" if "total" in bizbox.KINDS[kind][1] else "NULL"
        row = conn.execute(
            f"SELECT COUNT(*) AS n, SUM({money}) AS total FROM agreement_item i"
            f"  LEFT JOIN {table} r ON r.source_id = i.source_id AND r.ext_ref = i.ext_ref"
            " WHERE i.agreement_id = ? AND i.kind = ?", (agreement_id, word)).fetchone()
        out[word] = {"n": row["n"], "total": (None if money == "NULL" else float(row["total"] or 0))}
    return out


def covering(conn, kind: str, ext_ref: str):
    """The agreements that cover a mirrored record."""
    if kind not in COVERS:
        return []
    return conn.execute("SELECT a.* FROM agreement_item i JOIN agreement a ON a.agreement_id = i.agreement_id"
                        " WHERE i.source_id = ? AND i.kind = ? AND i.ext_ref = ? ORDER BY a.name",
                        (bizbox.SOURCE, COVERS[kind], ext_ref)).fetchall()


def covering_for(conn, kind: str, refs) -> dict[str, list]:
    """The same for many records in one query (a list page)."""
    refs = [r for r in refs if r]
    out: dict[str, list] = {r: [] for r in refs}
    if kind not in COVERS:
        return out
    for i in range(0, len(refs), 200):
        chunk = refs[i:i + 200]
        for r in conn.execute("SELECT i.ext_ref, a.agreement_id, a.name, a.status FROM agreement_item i"
                              " JOIN agreement a ON a.agreement_id = i.agreement_id WHERE i.source_id = ? AND i.kind = ?"
                              f" AND i.ext_ref IN ({','.join('?' * len(chunk))}) ORDER BY a.name",
                              [bizbox.SOURCE, COVERS[kind], *chunk]):
            out[r["ext_ref"]].append(r)
    return out

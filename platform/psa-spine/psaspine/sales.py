"""Opportunities and quotes (052): what the desk proposes, and how it went.

An opportunity moves LEAD → QUALIFIED → PROPOSAL → WON or LOST; a quote under
it is DRAFT until sent, then ACCEPTED, DECLINED or EXPIRED. Totals are
computed from the lines, never typed. A won opportunity becomes an agreement
(045) in one step, so the work that follows is covered. Nothing here writes
an invoice: BizBox does that. Every change is audited (SALES).
"""
from __future__ import annotations

import sqlite3
from datetime import date, datetime

from . import db

STAGES = {"LEAD": "Lead", "QUALIFIED": "Qualified", "PROPOSAL": "Proposal sent", "WON": "Won", "LOST": "Lost"}
OPEN_STAGES = ("LEAD", "QUALIFIED", "PROPOSAL")
DEFAULT_PROBABILITY = {"LEAD": 10, "QUALIFIED": 40, "PROPOSAL": 70, "WON": 100, "LOST": 0}
QUOTE_STATUSES = {"DRAFT": "Draft", "SENT": "Sent", "ACCEPTED": "Accepted", "DECLINED": "Declined", "EXPIRED": "Expired"}
MAX_LINES = 200


class Refused(ValueError):
    """A sentence for the person; nothing was written."""


def _stamp(at: datetime) -> str:
    return at.isoformat(sep=" ", timespec="minutes")


def _text(value, width: int) -> str | None:
    return " ".join(str(value or "").split())[:width] or None


def _day(value, what: str) -> str | None:
    v = (value or "").strip()
    if not v:
        return None
    try:
        return date.fromisoformat(v).isoformat()
    except ValueError:
        raise Refused(f"{what} is a date, e.g. 2026-12-31.")


def _number(value, what: str, *, allow_none=True, minimum=None):
    v = str(value if value is not None else "").strip().replace(",", "")
    if not v:
        if allow_none:
            return None
        raise Refused(f"{what} is needed.")
    try:
        n = float(v)
    except ValueError:
        raise Refused(f"{what} is a number.")
    if minimum is not None and n < minimum:
        raise Refused(f"{what} is at least {minimum:g}.")
    return round(n, 4)


def _next_id(conn, table: str, column: str, prefix: str) -> str:
    n = 0
    for (v,) in conn.execute(f"SELECT {column} FROM {table}"):
        try:
            n = max(n, int(v.split("-", 1)[1]))
        except (IndexError, ValueError):
            continue
    return f"{prefix}-{n + 1:04d}"


def _audit(conn, at: datetime, actor: str, subject: str, detail: str) -> None:
    db.audit(conn, at=_stamp(at), actor=actor, action="SALES", subject_kind="opportunity", subject_id=subject, detail=detail)


# ------------------------------------------------------------ opportunities

def get(conn: sqlite3.Connection, opportunity_id: str):
    return conn.execute(
        "SELECT o.*, e.name AS entity_name, c.display_name AS contact_name, a.name AS agreement_name"
        "  FROM opportunity o LEFT JOIN entity e ON e.entity_id = o.entity_id"
        "  LEFT JOIN contact c ON c.contact_id = o.contact_id LEFT JOIN agreement a ON a.agreement_id = o.agreement_id"
        " WHERE o.opportunity_id = ?", (opportunity_id,)).fetchone()


def _clean(conn, fields: dict) -> dict:
    out = {}
    if "name" in fields:
        out["name"] = _text(fields["name"], 200)
        if not out["name"]:
            raise Refused("An opportunity needs a name.")
    if "entity_id" in fields:
        eid = (fields["entity_id"] or "").strip() or None
        if eid and conn.execute("SELECT 1 FROM entity WHERE entity_id = ?", (eid,)).fetchone() is None:
            raise Refused("No such company.")
        out["entity_id"] = eid
    if "contact_id" in fields:
        cid = (fields["contact_id"] or "").strip() or None
        if cid and conn.execute("SELECT 1 FROM contact WHERE contact_id = ?", (cid,)).fetchone() is None:
            raise Refused("No such contact.")
        out["contact_id"] = cid
    if "probability" in fields:
        p = _number(fields["probability"], "Probability")
        if p is not None and not (0 <= p <= 100):
            raise Refused("Probability is 0 to 100.")
        out["probability"] = int(p) if p is not None else None
    if "expected_on" in fields:
        out["expected_on"] = _day(fields["expected_on"], "Expected close")
    if "amount" in fields:
        out["amount"] = _number(fields["amount"], "Amount", minimum=0)
    if "currency" in fields:
        out["currency"] = (_text(fields["currency"], 8) or "").upper() or None
    if "owner" in fields:
        out["owner"] = _text(fields["owner"], 200)
    if "notes" in fields:
        out["notes"] = " ".join(str(fields["notes"] or "").split("\r")).strip()[:4000] or None
    return out


def create(conn: sqlite3.Connection, *, name: str, at: datetime, actor: str, stage: str = "LEAD", **fields) -> str:
    if stage not in OPEN_STAGES:
        raise Refused("A new opportunity is a lead, qualified, or a proposal.")
    f = _clean(conn, {"name": name, **fields})
    if f.get("probability") is None:
        f["probability"] = DEFAULT_PROBABILITY[stage]
    oid = _next_id(conn, "opportunity", "opportunity_id", "OPP")
    stamp = _stamp(at)
    conn.execute(
        "INSERT INTO opportunity (opportunity_id, name, entity_id, contact_id, stage, probability, expected_on, amount,"
        " currency, owner, notes, created_at, created_by, updated_at, updated_by) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (oid, f["name"], f.get("entity_id"), f.get("contact_id"), stage, f["probability"], f.get("expected_on"),
         f.get("amount"), f.get("currency"), f.get("owner"), f.get("notes"), stamp, actor, stamp, actor))
    _audit(conn, at, actor, oid, f"created ({STAGES[stage]}): {f['name']}")
    return oid


def update(conn: sqlite3.Connection, opportunity_id: str, *, at: datetime, actor: str, **fields) -> list[str]:
    row = get(conn, opportunity_id)
    if row is None:
        raise Refused("No such opportunity.")
    if row["stage"] not in OPEN_STAGES:
        raise Refused("A won or lost opportunity is not edited; open a new one.")
    f = _clean(conn, fields)
    changed = []
    for k, v in f.items():
        if v != row[k]:
            conn.execute(f"UPDATE opportunity SET {k} = ? WHERE opportunity_id = ?", (v, opportunity_id))
            changed.append(f"{k} {row[k] if row[k] is not None else '-'} -> {v if v is not None else '-'}")
    if changed:
        conn.execute("UPDATE opportunity SET updated_at = ?, updated_by = ? WHERE opportunity_id = ?",
                     (_stamp(at), actor, opportunity_id))
        _audit(conn, at, actor, opportunity_id, "; ".join(changed)[:900])
    return changed


def move(conn: sqlite3.Connection, opportunity_id: str, stage: str, *, at: datetime, actor: str,
         reason: str | None = None) -> str | None:
    """Move the stage. WON makes an agreement from the accepted quote (or the
    amount) and returns its id; LOST needs a reason."""
    from . import agreements
    row = get(conn, opportunity_id)
    if row is None:
        raise Refused("No such opportunity.")
    if stage not in STAGES:
        raise Refused("No such stage.")
    if row["stage"] not in OPEN_STAGES:
        raise Refused("A won or lost opportunity stays where it ended.")
    if stage == row["stage"]:
        return None
    stamp = _stamp(at)
    agreement_id = None
    if stage == "LOST":
        reason = _text(reason, 300)
        if not reason:
            raise Refused("A lost opportunity says why, so the next one goes better.")
        conn.execute("UPDATE opportunity SET stage = 'LOST', probability = 0, lost_reason = ?, closed_at = ?,"
                     " updated_at = ?, updated_by = ? WHERE opportunity_id = ?", (reason, stamp, stamp, actor, opportunity_id))
        _audit(conn, at, actor, opportunity_id, f"lost: {reason}")
        return None
    if stage == "WON":
        accepted = conn.execute("SELECT * FROM quote WHERE opportunity_id = ? AND status = 'ACCEPTED' ORDER BY decided_at DESC",
                                (opportunity_id,)).fetchone()
        amount = accepted["total"] if accepted else row["amount"]
        agreement_id = agreements.create(conn, name=row["name"], party=row["entity_name"], amount=amount,
                                         currency=row["currency"], status="DRAFT", at=at, actor=actor,
                                         notes=f"From opportunity {opportunity_id}" + (f", quote {accepted['quote_id']}" if accepted else ""))
        conn.execute("UPDATE opportunity SET stage = 'WON', probability = 100, agreement_id = ?, closed_at = ?, amount = ?,"
                     " updated_at = ?, updated_by = ? WHERE opportunity_id = ?",
                     (agreement_id, stamp, amount, stamp, actor, opportunity_id))
        _audit(conn, at, actor, opportunity_id, f"won; agreement {agreement_id} drafted"
               + (f" from quote {accepted['quote_id']}" if accepted else ""))
        return agreement_id
    conn.execute("UPDATE opportunity SET stage = ?, probability = ?, updated_at = ?, updated_by = ? WHERE opportunity_id = ?",
                 (stage, DEFAULT_PROBABILITY[stage], stamp, actor, opportunity_id))
    _audit(conn, at, actor, opportunity_id, f"stage {STAGES[row['stage']]} -> {STAGES[stage]}")
    return None


def all_(conn: sqlite3.Connection, *, stage: str | None = None, q: str = "", owner: str | None = None):
    where, params = ["1 = 1"], []
    if stage == "OPEN":
        where.append(f"o.stage IN ({','.join('?' * len(OPEN_STAGES))})")
        params += list(OPEN_STAGES)
    elif stage:
        where.append("o.stage = ?")
        params.append(stage)
    if q:
        where.append("(o.name LIKE ? OR o.opportunity_id LIKE ? OR e.name LIKE ?)")
        params += [f"%{q}%"] * 3
    if owner:
        where.append("LOWER(o.owner) = LOWER(?)")
        params.append(owner)
    return conn.execute(
        "SELECT o.*, e.name AS entity_name, (SELECT COUNT(*) FROM quote qq WHERE qq.opportunity_id = o.opportunity_id) AS quotes"
        "  FROM opportunity o LEFT JOIN entity e ON e.entity_id = o.entity_id"
        " WHERE " + " AND ".join(where) + " ORDER BY CASE o.stage WHEN 'LOST' THEN 2 WHEN 'WON' THEN 1 ELSE 0 END,"
        " o.expected_on, o.opportunity_id", params).fetchall()


def pipeline(conn: sqlite3.Connection) -> list[dict]:
    """Count, amount and weighted amount (amount × probability) by stage."""
    out = []
    rows = {r["stage"]: r for r in conn.execute(
        "SELECT stage, COUNT(*) AS n, COALESCE(SUM(amount), 0) AS amount,"
        " COALESCE(SUM(amount * probability / 100.0), 0) AS weighted FROM opportunity GROUP BY stage")}
    for stage, word in STAGES.items():
        r = rows.get(stage)
        out.append({"stage": stage, "word": word, "count": r["n"] if r else 0, "amount": float(r["amount"]) if r else 0.0,
                    "weighted": float(r["weighted"]) if r else 0.0})
    return out


# ------------------------------------------------------------------ quotes

def quote(conn: sqlite3.Connection, quote_id: str):
    return conn.execute("SELECT * FROM quote WHERE quote_id = ?", (quote_id,)).fetchone()


def quotes_of(conn: sqlite3.Connection, opportunity_id: str):
    return conn.execute("SELECT * FROM quote WHERE opportunity_id = ? ORDER BY quote_id", (opportunity_id,)).fetchall()


def lines(conn: sqlite3.Connection, quote_id: str):
    return conn.execute("SELECT * FROM quote_line WHERE quote_id = ? ORDER BY sort_order, line_id", (quote_id,)).fetchall()


def _recalc(conn, quote_id: str, *, at: datetime, actor: str) -> None:
    q = quote(conn, quote_id)
    subtotal = round(sum(r["line_total"] for r in lines(conn, quote_id)), 4)
    total = round(subtotal * (1 + (q["tax_percent"] or 0) / 100.0), 2)
    conn.execute("UPDATE quote SET subtotal = ?, total = ?, updated_at = ?, updated_by = ? WHERE quote_id = ?",
                 (subtotal, total, _stamp(at), actor, quote_id))


def create_quote(conn: sqlite3.Connection, opportunity_id: str, *, name: str, at: datetime, actor: str,
                 valid_until=None, tax_percent=0, note=None) -> str:
    opp = get(conn, opportunity_id)
    if opp is None:
        raise Refused("No such opportunity.")
    if opp["stage"] not in OPEN_STAGES:
        raise Refused("A won or lost opportunity takes no new quote.")
    name = _text(name, 200)
    if not name:
        raise Refused("A quote needs a name.")
    tax = _number(tax_percent, "Tax %", allow_none=False, minimum=0)
    if tax > 100:
        raise Refused("Tax % is at most 100.")
    qid = _next_id(conn, "quote", "quote_id", "Q")
    stamp = _stamp(at)
    conn.execute("INSERT INTO quote (quote_id, opportunity_id, name, status, valid_until, tax_percent, subtotal, total, note,"
                 " created_at, created_by, updated_at, updated_by) VALUES (?,?,?,'DRAFT',?,?,0,0,?,?,?,?,?)",
                 (qid, opportunity_id, name, _day(valid_until, "Valid until"), tax, _text(note, 2000), stamp, actor, stamp, actor))
    _audit(conn, at, actor, opportunity_id, f"quote {qid} drafted: {name}")
    return qid


def _editable(conn, quote_id: str):
    q = quote(conn, quote_id)
    if q is None:
        raise Refused("No such quote.")
    if q["status"] != "DRAFT":
        raise Refused(f"A {QUOTE_STATUSES[q['status']].lower()} quote is not edited; draft a new one.")
    return q


def add_line(conn: sqlite3.Connection, quote_id: str, *, description: str, quantity, unit_price, at: datetime, actor: str) -> int:
    q = _editable(conn, quote_id)
    desc = _text(description, 300)
    if not desc:
        raise Refused("A line needs a description.")
    qty = _number(quantity, "Quantity", allow_none=False)
    if qty <= 0:
        raise Refused("Quantity is more than 0.")
    price = _number(unit_price, "Unit price", allow_none=False, minimum=0)
    if conn.execute("SELECT COUNT(*) FROM quote_line WHERE quote_id = ?", (quote_id,)).fetchone()[0] >= MAX_LINES:
        raise Refused(f"A quote has at most {MAX_LINES} lines.")
    order = conn.execute("SELECT COALESCE(MAX(sort_order), 0) + 1 FROM quote_line WHERE quote_id = ?", (quote_id,)).fetchone()[0]
    cur = conn.execute("INSERT INTO quote_line (quote_id, sort_order, description, quantity, unit_price, line_total)"
                       " VALUES (?,?,?,?,?,?)", (quote_id, order, desc, qty, price, round(qty * price, 4)))
    _recalc(conn, quote_id, at=at, actor=actor)
    _audit(conn, at, actor, q["opportunity_id"], f"quote {quote_id}: line added, {desc} x{qty:g} @ {price:.2f}")
    return cur.lastrowid


def remove_line(conn: sqlite3.Connection, quote_id: str, line_id: int, *, at: datetime, actor: str) -> bool:
    q = _editable(conn, quote_id)
    cur = conn.execute("DELETE FROM quote_line WHERE quote_id = ? AND line_id = ?", (quote_id, line_id))
    if cur.rowcount:
        _recalc(conn, quote_id, at=at, actor=actor)
        _audit(conn, at, actor, q["opportunity_id"], f"quote {quote_id}: line {line_id} removed")
    return bool(cur.rowcount)


def set_quote_status(conn: sqlite3.Connection, quote_id: str, status: str, *, at: datetime, actor: str) -> str:
    """DRAFT → SENT (needs a line) → ACCEPTED / DECLINED / EXPIRED. Accepting
    moves the opportunity to Proposal sent if it was earlier, and sets its
    amount to the quote's total."""
    q = quote(conn, quote_id)
    if q is None:
        raise Refused("No such quote.")
    if status not in QUOTE_STATUSES:
        raise Refused("No such quote status.")
    allowed = {"DRAFT": ("SENT",), "SENT": ("ACCEPTED", "DECLINED", "EXPIRED", "DRAFT")}
    if status not in allowed.get(q["status"], ()):
        raise Refused(f"A {QUOTE_STATUSES[q['status']].lower()} quote cannot become {QUOTE_STATUSES[status].lower()}.")
    if status == "SENT" and not lines(conn, quote_id):
        raise Refused("A quote with no lines is not sent.")
    stamp = _stamp(at)
    conn.execute("UPDATE quote SET status = ?, sent_at = CASE WHEN ? = 'SENT' THEN ? ELSE sent_at END,"
                 " decided_at = CASE WHEN ? IN ('ACCEPTED', 'DECLINED', 'EXPIRED') THEN ? ELSE NULL END,"
                 " updated_at = ?, updated_by = ? WHERE quote_id = ?",
                 (status, status, stamp, status, stamp, stamp, actor, quote_id))
    opp = get(conn, q["opportunity_id"])
    if status == "SENT" and opp["stage"] in ("LEAD", "QUALIFIED"):
        move(conn, opp["opportunity_id"], "PROPOSAL", at=at, actor=actor)
    if status == "ACCEPTED":
        conn.execute("UPDATE opportunity SET amount = ?, currency = COALESCE(currency, 'PHP'), updated_at = ?, updated_by = ?"
                     " WHERE opportunity_id = ?", (q["total"], stamp, actor, opp["opportunity_id"]))
    _audit(conn, at, actor, q["opportunity_id"], f"quote {quote_id} {status.lower()}")
    return status

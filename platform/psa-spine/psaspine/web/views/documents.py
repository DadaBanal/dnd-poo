"""The document screen (SQL01, 14 Oct 2026, the Procurement review; Dada, the
same day: the whole template, an edit on the PO, and every MMS document on the
desk).

A BizBox document opens as a document, to the shape of the Bizbox Chat
session's 1:1 draft of 13 Oct: the title with its breadcrumb and a search box,
an action bar (Add, Edit Mode), the header's fields as pickers in one row, the
lines grid, and a footer with the totals, the approval sentence, Print slip and
Save. Below it the approval line in full. The BizBox module list is the top
menu (Dada: "the side bar should be placed on the top"), not a side rail.

Two families share the screen:

* A document BizBox has and the desk mirrors (a purchase order). Edit Mode
  turns the header's pickers and the lines' quantity, unit price and
  description into controls and offers rows for new items; Save opens the
  window that says what will change; one batch; a second person approves; the
  push sends each change through psa.sp_apply_change (a line's as
  "line:<id>:<field>" with the line's row version, a new line as
  "line:new:<n>").
* A document the desk raises itself (a stock, expense or purchase requisition,
  an issuance, a physical count): the header and lines are kept on the desk as
  the batch's payload (ext_ref NEW-<batch>), with stock on hand at the source
  on every row and the shortfall shown, approved here, sent as one ADD, and
  numbered by BizBox when applied. It can be edited while it still waits.

Design: the desk's own tokens and type scale (templates.STYLE), gap-based
layout, one column on a phone, tabular numerals. Nothing loaded from outside.
"""
from __future__ import annotations

import json
import re
import urllib.parse

from ... import bizbox, mms_reports
from .. import templates as t
from . import common, finance

AREA = "procurement"
NEW_ROWS = 3                       # lines a person may add to a BizBox document in one go
FORM_ROWS = 8                      # lines on a desk document's form (the New form's eight, 13 Oct 2026)

# The document kinds this screen serves. Mirrored kinds carry the header fields
# in the order the slip shows them and how their lines are read; desk kinds
# ("desk": True) are raised here and kept as a batch's payload. The report
# server's slip is named as SQL01 measured it in the catalogue (§4 of the
# Bizbox Chat brief: the eight most-run reports are these document prints).
DOCS = {
    "purchase_order": {
        "word": "Purchase order", "many": "purchase orders", "title": "Purchase Order Details", "many_title": "Purchase Orders",
        "icon": "cart", "menu": "popo",
        "fields": (("vendor", "Vendor"), ("ordered_on", "Order date"), ("status", "Status"), ("currency", "Currency")),
        "lines": "po", "slip": r"POSLIP", "slip_word": "Print Purchase Order Slip",
    },
    # Delivery/Receiving is the desk's invoice kind (SQL01, Part 95, MEASURED:
    # psa.vw_invoice reads the receiving header). Its lines come from the
    # receiving-lines mirror, each naming the order it was received against.
    "invoice": {
        "word": "Receiving report", "many": "receiving reports", "title": "Receiving Report Details", "many_title": "Receiving",
        "icon": "inbox", "menu": "porr",
        "fields": (("party", "Vendor"), ("invoiced_on", "Receiving date"), ("supplier_ref", "Supplier's invoice no."),
                   ("due_on", "Due date"), ("status", "Status"), ("currency", "Currency")),
        "lines": "rr", "slip": r"DelReceive", "slip_word": "Print Receiving Report",
    },
    "stock_req": {
        "word": "Stock requisition", "many": "stock requisitions", "title": "Stock Requisition Details", "many_title": "Stock Requisitions",
        "icon": "note", "menu": "postockreq", "desk": True,
        "fields": (("department", "Issuing Department"), ("warehouse_ref", "Warehouse (from)"), ("center", "Center"), ("doc_date", "Requisition Date")),
        "lines": "mms", "slip": r"StockReq", "slip_word": "Print Stock Requisition Slip",
    },
    "expense_req": {
        "word": "Expense requisition", "many": "expense requisitions", "title": "Expense Requisition Details", "many_title": "Expense Requisitions",
        "icon": "note", "menu": "poexpreq", "desk": True,
        "fields": (("department", "Issuing Department"), ("warehouse_ref", "Warehouse (from)"), ("center", "Center"), ("doc_date", "Requisition Date")),
        "lines": "mms", "slip": r"ExpRequisition", "slip_word": "Print Expense Requisition Slip",
    },
    "purchase_req": {
        "word": "Purchase requisition", "many": "purchase requisitions", "title": "Purchase Requisition Details", "many_title": "Purchase Requisitions",
        "icon": "note", "menu": "popurchreq", "desk": True,
        "fields": (("department", "Requesting Department"), ("warehouse_ref", "Warehouse (for)"), ("center", "Center"), ("doc_date", "Requisition Date")),
        "lines": "mms", "slip": r"PurcReq", "slip_word": "Print Purchase Requisition Slip",
    },
    "stock_issuance": {
        "word": "Stock issuance", "many": "stock issuances", "title": "Stock Issuance Details", "many_title": "Stock Issuances",
        "icon": "arrow", "menu": "poissue", "desk": True,
        "fields": (("warehouse_ref", "Warehouse (from)"), ("department", "Issued To"), ("center", "Center"), ("doc_date", "Issuance Date")),
        "lines": "mms", "slip": r"StockIssuance", "slip_word": "Print Stock Issuance Slip",
    },
    "expense_issuance": {
        "word": "Expense issuance", "many": "expense issuances", "title": "Expense Issuance Details", "many_title": "Expense Issuances",
        "icon": "arrow", "menu": "poexpissue", "desk": True,
        "fields": (("warehouse_ref", "Warehouse (from)"), ("department", "Issued To"), ("center", "Center"), ("doc_date", "Issuance Date")),
        "lines": "mms", "slip": r"ExpIssuance", "slip_word": "Print Expense Issuance Slip",
    },
    "physical_count": {
        "word": "Physical count", "many": "physical counts", "title": "Physical Count Details", "many_title": "Physical Counts",
        "icon": "checks", "menu": "pocount", "desk": True,
        "fields": (("warehouse_ref", "Warehouse"), ("department", "Counted By"), ("center", "Center"), ("doc_date", "Count Date")),
        "lines": "mms", "slip": r"PhysicalCount", "slip_word": "Print Physical Count Sheet", "variance": True,
    },
}
DESK_KINDS = tuple(k for k, v in DOCS.items() if v.get("desk"))
# A line's columns per kind of lines: (field, heading, numeric, editable in Edit Mode)
LINE_COLUMNS = {
    "po": (("line_no", "#", False, False), ("product_ref", "Item ID", False, False), ("description", "Item Description", False, True),
           ("quantity", "Quantity", True, True), ("received_qty", "Served Quantity", True, False), ("unit_cost", "Unit Price", True, True)),
    "mms": (("line_no", "#", False, False), ("product_ref", "Item ID", False, False), ("description", "Item Description", False, False),
            ("generic", "Generic Name", False, False), ("unit", "Unit", False, False), ("quantity", "Quantity", True, False),
            ("unit_cost", "Unit Price", True, False)),
    # a receiving report's lines: what was received, at what price, against which order (not edited from the desk:
    # a received quantity is a stock movement, corrected in BizBox by its own adjustment, never by an edit here)
    "rr": (("line_no", "#", False, False), ("product_ref", "Item ID", False, False), ("description", "Item Description", False, False),
           ("quantity", "Quantity Received", True, False), ("unit_cost", "Unit Price", True, False), ("po_ref", "Purchase Order", False, False)),
}


def _module(kind: str) -> str:
    return finance.module_for(kind, AREA)


def _extended(line) -> float:
    return float(line["quantity"] or 0) * float(line["unit_cost"] or 0)


def _lines(conn, kind: str, ext_ref: str) -> list:
    how = DOCS[kind]["lines"]
    if how == "po":
        return bizbox.po_lines(conn, ext_ref)
    if how == "rr":
        return bizbox.rr_lines(conn, ext_ref)
    return []


def desk_lines(conn, kind: str, record: dict, lines: list) -> list:
    """A desk document's lines as the screen shows them: the item's name,
    generic and unit from the mirror, stock on hand at the source warehouse
    from the ledger mirror, and whether the line is short (the BETTER items of
    the draft: on hand on every row, the shortfall shown)."""
    out = []
    src = (record or {}).get("warehouse_ref") or ""
    for i, l in enumerate(lines or [], 1):
        ref = (l.get("product_ref") or "").strip()
        p = bizbox.get(conn, "product", ref) if ref else None
        m = bizbox.medicine_of(conn, ref) if ref else None
        qty = float(l.get("quantity") or 0)
        have = bizbox.on_hand(conn, src, ref) if ref else None
        out.append({"ext_ref": f"n{i}", "line_no": i, "product_ref": ref, "description": l.get("description") or (p["name"] if p else ""),
                    "generic": (m["generic"] if m else None), "unit": (p["unit"] if p else None), "quantity": qty,
                    "unit_cost": l.get("unit_cost") if l.get("unit_cost") not in (None, "") else (p["unit_cost"] if p else None),
                    "on_hand": have, "short": have is not None and qty > have, "variance": (qty - have) if have is not None else None})
    return out


def desk_record(conn, kind: str, doc: dict, ref: str) -> dict:
    """A desk document's header as the screen reads it, with what a mirrored
    record would carry beside it."""
    b, rec = doc["batch"], dict(doc["record"])
    rec.setdefault("ext_ref", ref)
    rec["number"] = doc["number"]
    rec["status"] = b["status"]
    rec["present"] = 1
    rec["synced_at"] = b["requested_at"]
    rec["currency"] = bizbox.desk_currency(conn)
    rec["total"] = None
    for f, _ in DOCS[kind]["fields"]:
        rec.setdefault(f, None)
    return rec


def totals(rec, lines) -> dict:
    """What the lines add up to, beside what BizBox's header says. Computed the
    same way everywhere (SQL01, 14 Oct 2026: compute it the same way or stored
    totals silently drift from their lines)."""
    lines_total = sum(_extended(l) for l in lines)
    header_total = float(rec["total"]) if "total" in rec.keys() and rec["total"] is not None else None
    return {"lines": len(lines),
            "ordered": sum(float(l["quantity"] or 0) for l in lines),
            "received": sum(float(l["received_qty"] or 0) for l in lines) if lines and "received_qty" in lines[0].keys() else None,
            "lines_total": lines_total, "header_total": header_total,
            "differs": header_total is not None and lines and abs(header_total - lines_total) >= 0.005}


def slip_report(conn, kind: str):
    """The report server's slip for this kind of document, if the catalogue
    (082) has it: the row, or None. Most ADHOC prints want a document number,
    so the slip belongs on the document (SQL01, Part 81)."""
    if not mms_reports.ready(conn):
        return None
    pattern = re.compile(DOCS[kind]["slip"], re.I)
    for r in conn.execute("SELECT * FROM mms_report WHERE present = 1 AND shown = 1 ORDER BY sort_no, report_id"):
        if pattern.search(r["name"] or ""):
            return r
    return None


def batches_of(conn, kind: str, ext_ref: str) -> list:
    """The change batches that touch this document, newest first, each with
    its changes."""
    rows = conn.execute(
        "SELECT DISTINCT b.* FROM ext_batch b JOIN ext_change c ON c.batch_id = b.batch_id"
        " WHERE b.source_id = ? AND c.kind = ? AND c.ext_ref = ? ORDER BY b.batch_id DESC",
        (bizbox.SOURCE, bizbox.LINK_KIND[kind], ext_ref)).fetchall()
    return [(b, [c for c in bizbox.batch_changes(conn, b["batch_id"]) if c["ext_ref"] == ext_ref]) for b in rows]


def _path(b) -> str:
    """The approval line: where a batch stands, as steps. Proposed, approved by
    a second person, sent, in BizBox; or refused or cancelled, said as such."""
    st = b["status"]
    who = lambda a, when: f"{t.esc(a or '')}" + (f" · {t.esc(when)}" if when else "")
    steps = [("done", "Proposed", who(b["requested_by"], b["requested_at"]))]
    if st == "PENDING":
        steps += [("now", "Approval", "waiting for a second person"), ("", "Sent to BizBox", ""), ("", "In BizBox", "")]
    elif st == "APPROVED":
        steps += [("done", "Approved", who(b["approved_by"], b["approved_at"])), ("now", "Sent to BizBox", "waiting for the push"), ("", "In BizBox", "")]
    elif st == "SENDING":
        steps += [("done", "Approved", who(b["approved_by"], b["approved_at"])), ("now", "Sent to BizBox", "being sent now"), ("", "In BizBox", "")]
    elif st == "APPLIED":
        steps += [("done", "Approved", who(b["approved_by"], b["approved_at"])), ("done", "Sent to BizBox", ""), ("done", "In BizBox", who(None, b["decided_at"]))]
    elif st == "REJECTED":
        steps += [("done", "Approved", who(b["approved_by"], b["approved_at"])), ("done", "Sent to BizBox", ""), ("bad", "Refused by BizBox", t.esc(b["answer"] or ""))]
    else:   # CANCELLED
        steps += [("bad", "Cancelled", who(b["decided_by"], b["decided_at"]))]
    return "<ol class=path>" + "".join(f"<li class='{cls}'><b>{t.esc(word)}</b><span>{detail}</span></li>" for cls, word, detail in steps) + "</ol>"


def approval_sentence(conn, kind: str, ext_ref: str, batches: list | None = None) -> str:
    """The footer's one line: the newest open batch and where it stands, or
    that nothing waits."""
    batches = batches_of(conn, kind, ext_ref) if batches is None else batches
    for b, _ in batches:
        if b["status"] in ("PENDING", "APPROVED", "SENDING"):
            return f"Approval: batch #{b['batch_id']} · {bizbox.BATCH_WORDS[b['status']].lower()}"
    for b, _ in batches:
        if ext_ref.startswith("NEW-"):
            return f"Approval: {bizbox.BATCH_WORDS[b['status']].lower()}"
    return "Approval: nothing waiting · a change saved here goes to a second person first"


def approval_card(ctx, kind: str, ext_ref: str, batches: list | None = None) -> str:
    """The approval line for this document: each batch of proposed changes as
    a path with its changes under it, and the approve or cancel actions for a
    person who may (the area's Approve level, never one's own)."""
    from . import procurement as procurement_view
    labels = bizbox.labels_for(ctx.conn, kind)
    blocks = []
    batches = batches_of(ctx.conn, kind, ext_ref) if batches is None else batches
    for b, changes in batches:
        trs = "".join(
            f"<tr><td>{t.esc(bizbox.field_word(c['field']))}</td>"
            f"<td>{t.esc(bizbox.value_word(labels, c['field'], c['old_value']))} <span class=arrow aria-hidden=true>→</span> "
            f"<b>{t.esc(bizbox.value_word(labels, c['field'], c['new_value']))}</b></td>"
            f"<td>{t.esc(c['reason'])}</td><td>{t.chip(bizbox.CHANGE_WORDS.get(c['status'], c['status']))}"
            + (f"<div class=muted>{t.esc(c['answer'])}</div>" if c["answer"] else "") + "</td></tr>" for c in changes)
        acts = procurement_view._batch_actions(ctx, b)
        blocks.append(
            f"<div class=batch><div class='row' style='justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap'>"
            f"<div><a href='/procurement/batch/{b['batch_id']}'>Batch #{b['batch_id']}</a> · {t.chip(bizbox.BATCH_WORDS[b['status']])}"
            f" · <span class=muted>{t.esc(b['reason'])}</span></div><div class=noprint>{acts}</div></div>"
            + _path(b)
            + f"<div class=tablewrap><table class=compact><thead><tr><th>Field</th><th>From → to</th><th>Why</th><th>State</th></tr></thead>"
            f"<tbody>{trs}</tbody></table></div></div>")
    if not blocks:
        body = ("<p class=muted>No change to this document is waiting. A change saved in Edit Mode goes here for a second person to "
                "approve; BizBox itself changes only after that, when the approved change is pushed.</p>")
    else:
        body = "".join(blocks)
    return f"<div class='card doc-approval'><h3>{t.icon('checks')}Approval</h3>{body}</div>"


def fact_text(rec, field: str, labels: dict) -> str:
    """A BizBox field as a person reads it: money with the record's currency,
    a stored code as its list's word, else the value; a dash for nothing. The
    one rule for the document, its slip and the review."""
    v = rec[field]
    if field in ("total", "amount", "unit_cost"):
        return finance._money(v, rec["currency"] if "currency" in rec.keys() else None) or "—"
    if field in labels:
        return bizbox.word(labels, field, v) or "—"
    return str(v) if v not in (None, "") else "—"


def pickers(ctx, kind: str, rec, editable: dict, posted: dict, labels: dict) -> str:
    """The header's fields in one row, as the draft has them: a control for
    each field a person may change (prefilled with BizBox's value) in Edit
    Mode, the value itself otherwise."""
    out = []
    for f, lab in DOCS[kind]["fields"]:
        if f in editable:
            ctl = finance._edit_control(ctx, kind, f, editable[f], rec[f], posted.get(f"e:{f}"))
        else:
            ctl = f"<div class=ro>{t.esc(fact_text(rec, f, labels))}</div>"
        out.append(f"<div><label>{t.esc(lab)}</label>{ctl}</div>")
    return f"<div class=pickers>{''.join(out)}</div>"


def _onhand_cell(l, kind: str) -> str:
    have = l["on_hand"] if "on_hand" in l.keys() else None
    if have is None:
        return "<td class='num onhand'><span class=muted>—</span></td>"
    cell = f"<td class='num onhand'>{have:g}"
    if DOCS[kind].get("variance") and l.get("variance") is not None:
        v = l["variance"]
        cell += f" <span class='muted code'>{'+' if v > 0 else ''}{v:g}</span>"
    elif l.get("short"):
        cell += " <span class='chip sla-bad'>SHORT</span>"
    return cell + "</td>"


def lines_table(ctx, kind: str, rec, lines: list, *, link_items: bool, css: str, editing: bool = False, posted: dict | None = None,
                source: bool = False) -> str:
    """The lines as a grid: the kind's columns, each line's total, a lines-total
    row. In Edit Mode of a BizBox document the editable cells are controls
    (named l:<line>:<field>) and three rows take a new item each, picked from
    what exists. A desk document shows stock on hand at the source on every
    row, the shortfall marked (or, on a count, the variance)."""
    posted = posted or {}
    cols = LINE_COLUMNS[DOCS[kind]["lines"]]
    cur = rec["currency"] if "currency" in rec.keys() else None
    line_edit = bizbox.EDITABLE_LINES.get(kind, {}) if editing else {}

    def cell(l, f, num, can):
        v = l[f] if f in l.keys() else None
        if can and f in line_edit:
            name = f"l:{l['ext_ref']}:{f}"
            how = line_edit[f]
            shown = posted.get(name, "" if v is None else (f"{float(v):g}" if how == "money" else str(v)))
            was = "" if v is None else (f"{float(v):g}" if how == "money" else str(v))
            if how == "money":
                return (f"<td class='num ecell'><input type=number step=any min=0 name='{name}' value='{t.esc(shown)}' data-was='{t.esc(was)}'"
                        f" aria-label='{t.esc(bizbox.FIELD_WORDS.get(f, f))} on line {t.esc(l['ext_ref'])}'></td>")
            return (f"<td class=ecell><input name='{name}' maxlength=400 value='{t.esc(shown)}' data-was='{t.esc(was)}'"
                    f" aria-label='{t.esc(bizbox.FIELD_WORDS.get(f, f))} on line {t.esc(l['ext_ref'])}'></td>")
        if f == "product_ref" and link_items:
            return f"<td>{finance._ref_link('product', v, AREA)}</td>"
        if f == "po_ref":                                   # the order a receiving line came from opens as its document
            return f"<td>{finance._ref_link('purchase_order', v, AREA) if link_items else t.esc(v or '')}</td>"
        if f == "unit_cost":
            return f"<td class=num>{t.esc(finance._money(v))}</td>"
        if num:
            return f"<td class=num>{float(v or 0):g}</td>"
        return f"<td>{t.esc(v if v is not None else '')}</td>"
    trs = "".join("<tr>" + "".join(cell(l, f, num, can) for f, _, num, can in cols) + f"<td class=num>{t.esc(finance._money(_extended(l)))}</td>"
                  + (_onhand_cell(l, kind) if source else "") + "</tr>" for l in lines)
    if editing and kind in bizbox.NEW_LINE_FIELDS:
        items = "".join(f"<option value='{t.esc(p['ext_ref'])}'>{t.esc(p['name'])}</option>" for p in bizbox.records(ctx.conn, "product", limit=2000))
        g = lambda k: t.esc(posted.get(k, "") or "")
        trs += "".join(
            f"<tr class=addrow><td class=muted>+</td>"
            f"<td><input name='n{i}_product_ref' list=docitems maxlength=64 placeholder='type to search existing items' value='{g(f'n{i}_product_ref')}' aria-label='New line {i}: item'></td>"
            f"<td><input name='n{i}_description' maxlength=400 placeholder='description' value='{g(f'n{i}_description')}' aria-label='New line {i}: description'></td>"
            f"<td class=num><input type=number step=any min=0 name='n{i}_quantity' placeholder='qty' value='{g(f'n{i}_quantity')}' aria-label='New line {i}: quantity'></td>"
            f"<td class=num></td>"
            f"<td class=num><input type=number step=any min=0 name='n{i}_unit_cost' placeholder='unit price' value='{g(f'n{i}_unit_cost')}' aria-label='New line {i}: unit price'></td>"
            f"<td class=num></td></tr>" for i in range(1, NEW_ROWS + 1))
        trs += (f"<tr class=addnote><td colspan={len(cols) + 1}><i>Add item: type to search existing items; a new item is never created from here.</i>"
                f"<datalist id=docitems>{items}</datalist></td></tr>")
    head = ("".join(f"<th{' class=num' if num else ''}>{t.esc(h)}</th>" for _, h, num, _ in cols) + "<th class=num>Total Amount</th>"
            + (("<th class=num>On hand at source <span class=better>BETTER</span></th>" if not DOCS[kind].get("variance")
                else "<th class=num>On hand · variance <span class=better>BETTER</span></th>") if source else ""))
    tot = totals(rec, lines)
    span = len(cols) + 1 + (1 if source else 0)
    foot = (f"<tr class=total><td colspan={len(cols)} class=num><b>Lines total</b></td><td class=num><b>{t.esc(finance._money(tot['lines_total'], cur))}</b></td>"
            + ("<td></td>" if source else "") + "</tr>" if lines else "")
    empty = "" if editing else f"<tr><td colspan={span} class=muted>No lines read from BizBox for this document.</td></tr>"
    return f"<table class='{css}'><thead><tr>{head}</tr></thead><tbody>{trs or empty}{foot}</tbody></table>"


def shortfall_note(kind: str, lines: list) -> str:
    """The draft's note under the grid: each short line named, the document
    still allowed (the source serves what it has and the row says so)."""
    if DOCS[kind].get("variance"):
        return ""
    short = [l for l in lines if l.get("short")]
    if not short:
        return ""
    parts = [f"row {l['line_no']}: only <b>{l['on_hand']:g}</b> on hand at the source against <b>{l['quantity']:g}</b> requested" for l in short]
    return (f"<p class='banner warn' style='margin:10px 0 0'>Short on {len(short)} line{'s' if len(short) != 1 else ''}: {'; '.join(parts)}. "
            "The document can still be sent; the source serves what it has and the row shows the shortfall instead of silently serving less.</p>")


def footer(ctx, kind: str, rec, lines: list, ext_ref: str, *, editing: bool, posted: dict, number: str | None = None, batches: list | None = None) -> str:
    """The draft's footer: the totals in BizBox's words, the approval sentence,
    the slip, and Save in Edit Mode."""
    tot = totals(rec, lines)
    cur = rec["currency"] if "currency" in rec.keys() else None
    cells = [("Total Record(s)", f"{tot['lines']}"), ("Total Item", f"{tot['ordered']:g}"), ("Total Amount", t.esc(finance._money(tot["lines_total"], cur)))]
    if tot["header_total"] is not None:
        cells.append(("Total in BizBox", t.esc(finance._money(tot["header_total"], cur))))
    nums = "".join(f"<div class=tot><span class=l>{lab}:</span> <b>{val}</b></div>" for lab, val in cells)
    own = f"/procurement/{kind}/slip?" + urllib.parse.urlencode({"ref": ext_ref, "now": "1"})
    acts = f"<a class='btn ghost' href='{t.esc(own)}' target=_blank rel=noopener>{t.icon('reports')} {t.esc(DOCS[kind]['slip_word'])}</a>"
    r = slip_report(ctx.conn, kind)
    doc_no = number if DOCS[kind].get("desk") else ext_ref
    if r is not None and doc_no:
        href = f"/procurement/report/{r['report_id']}?" + urllib.parse.urlencode({"doc": doc_no})
        acts += f" <a class='btn ghost' href='{t.esc(href)}'>{t.icon('arrow')} BizBox's slip ({t.esc(r['name'])})</a>"
    if editing:
        acts += (f" <span class=why><label class=sr-only for=docwhy>Why</label><input id=docwhy name=reason maxlength=400 required"
                 f" value='{t.esc(posted.get('reason', ''))}' placeholder='Why? The approver sees this'></span>"
                 f" <button type=submit>{t.icon('check')} Save</button>")
    note = (f"<p class='why' style='margin:8px 0 0'>BizBox's total and the lines differ by "
            f"<b>{t.esc(finance._money(abs(tot['header_total'] - tot['lines_total']), cur))}</b>: the header carries what BizBox computed "
            "(tax, discount, or lines the desk has not read); the lines are what the desk read.</p>" if tot["differs"] else "")
    return (f"<div class=mmsfoot><div class=nums>{nums}</div><div class=appr>{t.esc(approval_sentence(ctx.conn, kind, ext_ref, batches))}</div>"
            f"<div class='acts noprint'>{acts}</div></div>" + note)


def _editing(ctx, can_edit: bool, posted: dict, err: str) -> bool:
    """Edit Mode is on when asked for (?edit=1), when a form came back (a
    review or a refusal carries what was typed), or when a refusal is shown."""
    if not can_edit:
        return False
    q = ctx.request.query
    return (q.get("edit") == "1" or posted.get("edit") == "1" or bool(err or q.get("err"))
            or any(k.startswith(("e:", "l:")) or re.match(r"n\d+_", k) for k in posted))


def _links_card(ctx, kind: str, ext_ref: str) -> str:
    linked = bizbox.linked_to(ctx.conn, kind, ext_ref)
    visible = finance._visible_subjects(ctx, linked, common.board_ids_for(ctx))
    links = "".join(
        (f"<li>Ticket <a href='/ticket/{t.esc(l['subject_id'])}'>{t.esc(l['subject_id'])}</a> · {t.esc(l['linked_at'])} · {t.esc(l['linked_by'])}</li>"
         if l["subject_kind"] == "TICKET" else
         f"<li>Project <a href='/project/{t.esc(l['subject_id'])}'>{t.esc(l['subject_id'])}</a> · {t.esc(l['linked_at'])}</li>")
        for l in linked if (l["subject_kind"], l["subject_id"]) in visible)
    return f"<div class=card><h3>{t.icon('note')}Work linked to it</h3>" + (f"<ul class=plain>{links}</ul>" if links else "<div class=muted>No ticket or project yet.</div>") + "</div>"


def _received_card(ctx, kind: str, ext_ref: str) -> str:
    """On a purchase order: every receiving line that names it, with the
    receiving report it is on (the order's other half; the report opens as
    its own document)."""
    if kind != "purchase_order":
        return ""
    rows = bizbox.received_against(ctx.conn, ext_ref)
    labels = bizbox.labels_for(ctx.conn, "invoice")
    cur = None
    rec = bizbox.get(ctx.conn, kind, ext_ref)
    if rec is not None and "currency" in rec.keys():
        cur = rec["currency"]
    trs = "".join(
        f"<tr><td>{finance._ref_link('invoice', r['rr_ref'], AREA)}</td><td>{t.esc(r['invoiced_on'] or '')}</td><td>{t.esc(r['party'] or '')}</td>"
        f"<td>{t.esc(bizbox.word(labels, 'status', r['rr_status']) if r['rr_status'] else '')}</td>"
        f"<td>{finance._ref_link('product', r['product_ref'], AREA)} {t.esc(r['description'] or '')}</td>"
        f"<td class=num>{float(r['quantity'] or 0):g}</td><td class=num>{t.esc(finance._money(r['unit_cost']))}</td></tr>" for r in rows)
    total = sum(float(r["quantity"] or 0) for r in rows)
    return (f"<div class=card><h3>{t.icon('inbox')}Received against this order</h3>"
            + ((f"<div class=tablewrap><table class=compact><thead><tr><th>Receiving report</th><th>Date</th><th>Vendor</th><th>Status</th><th>Item</th>"
                f"<th class=num>Quantity Received</th><th class=num>Unit Price{(' (' + t.esc(cur) + ')') if cur else ''}</th></tr></thead><tbody>{trs}"
                f"<tr class=total><td colspan=5 class=num><b>Received in all</b></td><td class=num><b>{total:g}</b></td><td></td></tr></tbody></table></div>")
               if rows else "<div class=muted>Nothing received against this order yet, as of the last read.</div>") + "</div>")


def _dochead(kind: str, title: str, crumbs: str, *, search: bool = True) -> str:
    spec = DOCS[kind]
    s = (f"<form method=get action='/procurement' class='docsearch noprint' role=search><input type=hidden name=tab value={kind}>"
         f"<input name=q placeholder='Find a {t.esc(spec['word'].lower())}…' aria-label='Find a {t.esc(spec['word'].lower())}'></form>") if search else ""
    return f"<div class=dochead><div><h1>{t.esc(title)}</h1><p class=crumbs>{crumbs}</p></div>{s}</div>"


def page(ctx, kind: str, ext_ref: str, *, dialog: str = "", err: str = "", posted: dict | None = None):
    """The document: title and breadcrumb, the action bar, the header pickers,
    the lines, the footer; the approval line and the work linked below. A desk
    document (NEW-<batch>) reads from its batch; its Edit Mode is the form it
    was raised with, while it still waits."""
    from .. import HttpError, Response
    from . import procurement as procurement_view
    common.require_module(ctx, _module(kind))
    spec = DOCS[kind]
    posted = posted or {}
    q = ctx.request.query
    if spec.get("desk"):
        doc = bizbox.desk_document(ctx.conn, kind, ext_ref)
        if doc is None:
            raise HttpError("404 Not Found", "No such document on the desk.")
        b = doc["batch"]
        mine = (b["requested_by"] or "").lower() == (ctx.user.id or "").lower()
        can_edit = b["status"] == "PENDING" and (mine or common.allows(ctx, _module(kind), "ADMIN")) and common.allows(ctx, _module(kind), "WRITE")
        if can_edit and (q.get("edit") == "1" or err or q.get("err")):
            form = {f: (doc["record"].get(f) or "") for f in bizbox.ADDABLE[kind]["fields"]}
            for i, l in enumerate(doc["lines"], 1):
                for k in bizbox.ADDABLE[kind]["lines"]:
                    form[f"line{i}_{k}"] = "" if l.get(k) in (None, "") else (f"{float(l[k]):g}" if k in ("quantity", "unit_cost") else str(l[k]))
            form["reason"] = b["reason"]
            return new_page(ctx, kind, posted=form | posted, err=err, dialog=dialog, batch=b["batch_id"])
        rec = desk_record(ctx.conn, kind, doc, ext_ref)
        lines = desk_lines(ctx.conn, kind, doc["record"], doc["lines"])
        labels = bizbox.labels_for(ctx.conn, kind)
        number = doc["number"]
        batches = batches_of(ctx.conn, kind, ext_ref)
        status_word = bizbox.BATCH_WORDS[b["status"]]
        bar = ("<div class='mmsbar noprint'>"
               + (f"<a class=btn href='/procurement/{kind}/new'>{t.icon('plus')} Add</a> " if common.allows(ctx, _module(kind), "WRITE") else "")
               + (f"<a class='btn ghost' href='{t.esc(finance._url(kind, ext_ref, AREA) + '&edit=1')}'>{t.icon('edit')} Edit Mode</a>" if can_edit else "")
               + f"<div class=state>raised on the desk {t.esc(b['requested_at'])} by {t.esc(b['requested_by'])}"
               + (f" · in BizBox as <b>{t.esc(number)}</b>" if number else "") + "</div></div>")
        sheet = (pickers(ctx, kind, rec, {}, posted, labels)
                 + "<div class=tablewrap>" + lines_table(ctx, kind, rec, lines, link_items=True, css="compact doclines", source=True) + "</div>"
                 + shortfall_note(kind, lines)
                 + footer(ctx, kind, rec, lines, ext_ref, editing=False, posted=posted, number=number, batches=batches))
        crumbs = (f"<a href='/procurement?tab={kind}'>{t.esc(spec['many_title'])}</a> › {t.esc(number or ext_ref)} › {t.esc(status_word.lower())}")
        body = (procurement_view._banners(q) + (f"<div class='banner err' id=flash-err role=alert>{t.esc(err)}</div>" if err else "") + dialog
                + "<div class=doc>" + _dochead(kind, spec["title"], crumbs) + f"<div class='card docsheet'>{bar}{sheet}</div>"
                + approval_card(ctx, kind, ext_ref, batches) + _links_card(ctx, kind, ext_ref) + "</div>")
        return Response(body=t.page(f"{spec['word']} {number or ext_ref}", body, user=ctx.user, active=spec["menu"]))
    rec = bizbox.get(ctx.conn, kind, ext_ref)
    if rec is None:
        raise HttpError("404 Not Found", "No such document in the BizBox mirror.")
    labels = bizbox.labels_for(ctx.conn, kind)
    can_edit = common.allows(ctx, _module(kind), "WRITE") and bool(rec["present"]) and (kind in bizbox.EDITABLE or kind in bizbox.EDITABLE_LINES)
    editing = _editing(ctx, can_edit, posted, err)
    editable = bizbox.EDITABLE.get(kind, {}) if editing else {}
    lines = _lines(ctx.conn, kind, ext_ref)
    batches = batches_of(ctx.conn, kind, ext_ref)
    status_word = bizbox.word(labels, "status", rec["status"]) if "status" in rec.keys() and rec["status"] else ""
    pending = sum(1 for _, cs in batches for c in cs if c["status"] in ("PENDING", "SENDING"))
    can_add = common.allows(ctx, _module(kind), "WRITE") and kind in bizbox.ADDABLE
    # the action bar: Add, Edit Mode (BizBox's own buttons); the read state on the right
    bar = ("<div class='mmsbar noprint'>"
           + (f"<a class=btn href='/procurement/{kind}/new'>{t.icon('plus')} Add</a> " if can_add else "")
           + ((f"<a class='btn ghost' href='{t.esc(finance._url(kind, ext_ref, AREA))}'>{t.icon('check')} Done editing</a>" if editing
               else f"<a class='btn ghost' href='{t.esc(finance._url(kind, ext_ref, AREA) + '&edit=1')}'>{t.icon('edit')} Edit Mode</a>") if can_edit else "")
           + "<div class=state>"
           + ("" if rec["present"] else "<b>no longer in BizBox</b>; kept because work links to it · ")
           + f"read from BizBox {t.esc(rec['synced_at'])}"
           + (f" · <span class='chip sla-warn'>{pending} change{'s' if pending != 1 else ''} waiting</span>" if pending else "")
           + "</div></div>")
    sheet = (pickers(ctx, kind, rec, editable, posted, labels)
             + "<div class=tablewrap>" + lines_table(ctx, kind, rec, lines, link_items=not editing, css="compact doclines", editing=editing, posted=posted) + "</div>"
             + footer(ctx, kind, rec, lines, ext_ref, editing=editing, posted=posted, batches=batches))
    if editing:
        sheet = (f"<form method=post action='/procurement/{kind}/review' class=fields data-record{' aria-describedby=flash-err' if (err or q.get('err')) else ''}>"
                 f"<input type=hidden name=ref value='{t.esc(ext_ref)}'><input type=hidden name=edit value=1>{sheet}</form>")
    crumbs = (f"<a href='/procurement?tab={kind}'>{t.esc(spec['many_title'])}</a> › {t.esc(ext_ref)}"
              + (f" › {t.esc(status_word)}" if status_word else "") + (" › editing" if editing else ""))
    body = (procurement_view._banners(q) + (f"<div class='banner err' id=flash-err role=alert>{t.esc(err)}</div>" if err else "") + dialog
            + "<div class=doc>" + _dochead(kind, spec["title"], crumbs) + f"<div class='card docsheet'>{bar}{sheet}</div>"
            + approval_card(ctx, kind, ext_ref, batches) + _received_card(ctx, kind, ext_ref) + _links_card(ctx, kind, ext_ref) + "</div>")
    return Response(body=t.page(f"{spec['word']} {ext_ref}", body, user=ctx.user, active=spec["menu"]))


# ---------------------------------------------------------------- the lists

def desk_list(ctx, kind: str) -> str:
    """The desk's own documents of a kind, newest first: the number (BizBox's
    once applied), the header's words, lines, total, where it stands, who
    raised it. A row opens the document."""
    q = ctx.request.query
    state, search = q.get("state", "open"), q.get("q", "").strip().lower()
    labels = bizbox.labels_for(ctx.conn, kind)
    rows = []
    numbers = bizbox.desk_numbers(ctx.conn, kind)
    costs = {}

    def unit_cost(ref):
        if ref not in costs:
            p = bizbox.get(ctx.conn, "product", ref) if ref else None
            costs[ref] = p["unit_cost"] if p else None
        return costs[ref]
    for b in bizbox.batches(ctx.conn, kind=kind, limit=300):
        if b["change_kind"] != "ADD":
            continue
        if state == "open" and b["status"] not in ("PENDING", "APPROVED", "SENDING"):
            continue
        if state not in ("open", "all") and b["status"] != state:
            continue
        p = bizbox.payload_of(b)
        rec, lines = p.get("record", {}), p.get("lines", [])
        number = numbers.get(b["batch_id"]) or f"NEW-{b['batch_id']}"
        words = " ".join(str(x) for x in (number, rec.get("department"), rec.get("warehouse_ref"), bizbox.word(labels, "warehouse_ref", rec.get("warehouse_ref")))).lower()
        if search and search not in words:
            continue
        # the same unit price rule as the document: the item's when the line has none
        total = sum(float(l.get("quantity") or 0) * float(l.get("unit_cost") if l.get("unit_cost") not in (None, "") else (unit_cost(l.get("product_ref")) or 0))
                    for l in lines)
        rows.append((b, number, rec, lines, total))
    cur = bizbox.desk_currency(ctx.conn)

    def tr(b, number, rec, lines, total):
        url = t.esc(finance._url(kind, f"NEW-{b['batch_id']}", AREA))
        wh = bizbox.word(labels, "warehouse_ref", rec.get("warehouse_ref")) or "—"
        return (f"<tr data-href='{url}'><td><a href='{url}'>{t.esc(number)}</a></td>"
                f"<td>{t.esc(rec.get('department') or '—')}</td><td>{t.esc(wh)}</td>"
                f"<td>{t.esc(rec.get('doc_date') or b['requested_at'][:10])}</td><td class=num>{len(lines)}</td><td class=num>{t.esc(finance._money(total, cur))}</td>"
                f"<td>{t.chip(bizbox.BATCH_WORDS[b['status']])}</td><td>{t.esc(b['requested_by'])}</td></tr>")
    trs = "".join(tr(*r) for r in rows)
    opts = "".join(f"<option value='{v}'{' selected' if v == state else ''}>{w}</option>" for v, w in
                   (("open", "Open"), ("all", "All"), ("PENDING", "Waiting for approval"), ("APPROVED", "Approved, to send"),
                    ("APPLIED", "In BizBox"), ("REJECTED", "Refused"), ("CANCELLED", "Cancelled")))
    filters = (f"<form method=get action='/procurement' class='row schedbar'><input type=hidden name=tab value={kind}>"
               f"<div style='flex:1 1 220px'><input name=q value='{t.esc(q.get('q', ''))}' placeholder='Search by number, department or warehouse' aria-label='Search'></div>"
               f"<div style='flex:0 0 200px'><select name=state aria-label='State'>{opts}</select></div>"
               "<div style='flex:0 0 auto'><button class=ghost type=submit>Filter</button></div></form>")
    head = ("<th>Number</th><th>Department</th><th>Warehouse</th><th>Date</th><th class=num>Lines</th><th class=num>Total Amount</th>"
            "<th>State</th><th>Raised by</th>")
    return ("<div class=card>" + filters + f"<div class=tablewrap><table class='compact pgrid doclist'><thead><tr>{head}</tr></thead><tbody>"
            + (trs or "<tr><td colspan=8 class=muted>None yet. Add raises one here; BizBox's own, once SQL01 maps a view for them, will list beside it.</td></tr>")
            + f"</tbody></table></div><div class=muted style='margin-top:8px'>{len(rows)} record(s).</div></div>")


def list_page(ctx, kind: str):
    """The list, in the draft's frame: the title with its crumb, the search,
    Add, then the read-only rows that open the document."""
    from .. import Response
    from . import procurement as procurement_view
    spec = DOCS[kind]
    q = ctx.request.query
    can_add = common.allows(ctx, _module(kind), "WRITE") and kind in bizbox.ADDABLE
    body = (procurement_view._head(ctx, kind, q, title=False)
            + f"<div class=dochead><div><h1>{t.esc(spec['many_title'])}</h1><p class=crumbs>Materials › {t.esc(spec['many_title'])}</p></div>"
            + (f"<div class=docbar><a class=btn href='/procurement/{kind}/new'>{t.icon('plus')} Add</a></div>" if can_add else "") + "</div>"
            + (desk_list(ctx, kind) if spec.get("desk") else procurement_view._list(ctx, kind, with_new=False)))
    return Response(body=t.page(spec["many_title"], body, user=ctx.user, active=spec["menu"]))


# ------------------------------------------------- a desk document's form

ONHAND_SCRIPT = ("<script>(function(){var f=document.querySelector('form[data-docform]');if(!f)return;"
                 "var wh=f.querySelector('[name=warehouse_ref]');"
                 "function row(inp){return inp.closest('tr')}"
                 "function look(inp){var tr=row(inp);var cell=tr&&tr.querySelector('.onhand');if(!cell)return;var item=inp.value.trim();var w=wh?wh.value:'';"
                 "if(!item||!w){cell.textContent='—';return}"
                 "fetch('/procurement/stock.json?'+new URLSearchParams({warehouse:w,item:item}),{credentials:'same-origin'}).then(function(r){return r.json()}).then(function(d){"
                 "var q=parseFloat((tr.querySelector('[name$=_quantity]')||{}).value||'0')||0;"
                 "if(d.on_hand===null||d.on_hand===undefined){cell.textContent='—';return}"
                 "cell.textContent=String(d.on_hand);if(q>d.on_hand){var s=document.createElement('span');s.className='chip sla-bad';s.textContent='SHORT';cell.appendChild(document.createTextNode(' '));cell.appendChild(s)}"
                 "}).catch(function(){cell.textContent='—'})}"
                 "f.querySelectorAll('[name$=_product_ref]').forEach(function(inp){inp.addEventListener('change',function(){look(inp)});"
                 "var qn=row(inp)&&row(inp).querySelector('[name$=_quantity]');if(qn)qn.addEventListener('change',function(){look(inp)});if(inp.value)look(inp)});"
                 "if(wh)wh.addEventListener('change',function(){f.querySelectorAll('[name$=_product_ref]').forEach(function(inp){if(inp.value)look(inp)})})})()</script>")


def new_page(ctx, kind: str, *, posted: dict | None = None, dialog: str = "", err: str = "", batch: int | None = None):
    """A desk document's form, in the draft's frame: the pickers in a row, a
    grid of rows that take an item each (stock on hand at the source filled
    in as you pick, the shortfall marked), the footer with Save. The same form
    edits the document while it still waits for approval."""
    from .. import Response
    from . import procurement as procurement_view
    spec = DOCS[kind]
    q = ctx.request.query
    v = posted or {}
    g = lambda k: v.get(k, "") or ""
    pick = procurement_view._pick
    fields = []
    for f, lab in spec["fields"]:
        required = f in bizbox.ADDABLE[kind]["required"]
        if f == "doc_date":
            ctl = f"<input type=date name=doc_date value='{t.esc(g('doc_date') or ctx.now.strftime('%Y-%m-%d'))}'>"
        else:
            ctl = pick(ctx, kind, f, f, g(f), empty=("Choose" if required else "(none)"), required=required,
                       fallback=f"<input name={f}{' required' if required else ''} maxlength=400 value='{t.esc(g(f))}' placeholder='{t.esc(bizbox.LIST_WORDS.get(bizbox.CHOICE_LIST.get((kind, f), ''), ''))}'>")
        fields.append(f"<div><label>{t.esc(lab)}{' *' if required else ''}</label>{ctl}</div>")
    items = "".join(f"<option value='{t.esc(p['ext_ref'])}'>{t.esc(p['name'])}</option>" for p in bizbox.records(ctx.conn, "product", limit=2000))
    rows = "".join(
        f"<tr><td class=muted>{i}</td>"
        f"<td><input name='line{i}_product_ref' list=docitems maxlength=64 placeholder='type to search existing items' value='{t.esc(g(f'line{i}_product_ref'))}' aria-label='Line {i}: item'></td>"
        f"<td><input name='line{i}_description' maxlength=400 placeholder='description' value='{t.esc(g(f'line{i}_description'))}' aria-label='Line {i}: description'></td>"
        f"<td class=num><input type=number step=any min=0 name='line{i}_quantity' placeholder='qty' value='{t.esc(g(f'line{i}_quantity'))}' aria-label='Line {i}: quantity'></td>"
        f"<td class=num><input type=number step=any min=0 name='line{i}_unit_cost' placeholder='unit price' value='{t.esc(g(f'line{i}_unit_cost'))}' aria-label='Line {i}: unit price'></td>"
        f"<td class='num onhand'><span class=muted>—</span></td></tr>" for i in range(1, FORM_ROWS + 1))
    grid = (f"<div class=tablewrap><table class='compact doclines'><thead><tr><th>#</th><th>Item ID</th><th>Item Description</th><th class=num>Quantity</th>"
            f"<th class=num>Unit Price</th><th class=num>{'On hand · variance' if spec.get('variance') else 'On hand at source'} <span class=better>BETTER</span></th></tr></thead>"
            f"<tbody>{rows}<tr class=addnote><td colspan=6><i>Add item: type to search existing items; a new item is never created from here. "
            f"Stock on hand at the warehouse chosen above shows as you pick.</i><datalist id=docitems>{items}</datalist></td></tr></tbody></table></div>")
    word = spec["word"].lower()
    crumbs = (f"<a href='/procurement?tab={kind}'>{t.esc(spec['many_title'])}</a> › " + (f"NEW-{batch} › editing" if batch else "new"))
    foot = (f"<div class=mmsfoot><div class=appr>Approval: a second person with Approve on this area, then the push to BizBox</div>"
            f"<div class='acts noprint'><span class=why><label class=sr-only for=docwhy>Why</label><input id=docwhy name=reason required maxlength=400"
            f" value='{t.esc(g('reason'))}' placeholder='Why? The approver sees this'></span> <button type=submit>{t.icon('check')} Save</button></div></div>")
    body = (procurement_view._banners(q) + (f"<div class='banner err' id=flash-err role=alert>{t.esc(err)}</div>" if err else "") + dialog
            + "<div class=doc>" + _dochead(kind, spec["title"], crumbs, search=False)
            + f"<div class='card docsheet'><form method=post action='/procurement/{kind}/add/review' class=fields data-docform{' aria-describedby=flash-err' if (err or q.get('err')) else ''}>"
            + (f"<input type=hidden name=batch value={batch}>" if batch else "")
            + f"<div class='mmsbar noprint'><div class=state>A new {t.esc(word)} on the desk: saved here, approved by a second person, then created in BizBox, which numbers it.</div></div>"
            + f"<div class=pickers>{''.join(fields)}</div>" + grid + foot + "</form></div></div>" + ONHAND_SCRIPT)
    return Response(body=t.page(f"New {word}" if not batch else f"{spec['word']} NEW-{batch}", body, user=ctx.user, active=spec["menu"]))


def add_window_body(ctx, kind: str, checked: dict) -> str:
    """The review window's body for a desk document: the header as it will be
    kept and the lines with stock on hand at the source and the shortfall."""
    rec, lines = checked["record"], checked["lines"]
    labels = bizbox.labels_for(ctx.conn, kind)
    facts = "".join(f"<tr><td>{t.esc(lab)}</td><td><b>{t.esc(bizbox.word(labels, f, rec.get(f)) or '—')}</b></td></tr>" for f, lab in DOCS[kind]["fields"])
    shown = desk_lines(ctx.conn, kind, rec, lines)
    fake = {"currency": bizbox.desk_currency(ctx.conn), "total": None}
    return (f"<div class=tablewrap><table class=compact><thead><tr><th>Field</th><th>Will be</th></tr></thead><tbody>{facts}</tbody></table></div>"
            f"<p style='margin:10px 0 4px'><b>{len(shown)} line{'s' if len(shown) != 1 else ''}</b></p>"
            "<div class=tablewrap>" + lines_table(ctx, kind, fake, shown, link_items=False, css="compact doclines", source=True) + "</div>"
            + shortfall_note(kind, shown))


def stock_json(ctx):
    """Stock on hand at a warehouse for an item, for the form as a person picks
    (standard item 5 of the Bizbox Chat brief: live stock while you type)."""
    from .. import HttpError, Response
    from ... import security
    if not any(common.allows(ctx, area) for area in security.PROCUREMENT_AREAS):     # any Procurement area may see stock on hand
        raise HttpError("403 Forbidden", "Your security role does not let you see procurement. Ask your service manager.")
    q = ctx.request.query
    have = bizbox.on_hand(ctx.conn, q.get("warehouse", ""), q.get("item", ""))
    return Response(body=json.dumps({"on_hand": have}), content_type="application/json; charset=utf-8", headers=[("Cache-Control", "no-store")])


# ----------------------------------------------------------- edit mode: review, send

def _posted_edits(f, kind: str) -> list:
    """What Edit Mode posted, as (ref, field, value) triples for the model:
    the header's e:<field>, each line's l:<line>:<field> as line:<line>:<field>,
    and each new row n<i>_* as line:new:<i> with the row as a dict; a hidden
    copy from the review window carries e:line:... already shaped."""
    ref = f.get("ref", "")
    out = []
    for key in f.keys():
        if key.startswith("e:line:"):
            field = key[2:]
            v = f.get(key, "")
            if field.startswith("line:new:"):
                try:
                    v = json.loads(v) if v.startswith("{") else {}
                except ValueError:
                    v = {}
            out.append((ref, field, v))
        elif key.startswith("e:") and key[2:] in bizbox.EDITABLE.get(kind, {}):
            out.append((ref, key[2:], f.get(key, "")))
        elif key.startswith("l:"):
            parts = key.split(":", 2)
            if len(parts) == 3 and parts[2] in bizbox.EDITABLE_LINES.get(kind, {}):
                out.append((ref, f"line:{parts[1]}:{parts[2]}", f.get(key, "")))
    for i in range(1, NEW_ROWS + 1):
        row = {k: f.get(f"n{i}_{k}", "") for k in bizbox.NEW_LINE_FIELDS.get(kind, {})}
        if any(v.strip() for v in row.values() if isinstance(v, str)):
            out.append((ref, f"line:new:{i}", row))
    return out


def review(ctx, kind: str):
    """POST from Edit Mode's Save: the window that says what will change on the
    header and on the lines. Nothing is queued yet."""
    from .. import HttpError, redirect
    if kind not in DOCS or DOCS[kind].get("desk"):
        return redirect("/procurement")
    common.require_module(ctx, _module(kind), "WRITE")
    f = ctx.request.form()
    ext_ref = f.get("ref", "")
    if not ext_ref:
        raise HttpError("404 Not Found", "No such document.")
    posted = dict(f)
    try:
        preview = bizbox.preview_edits(ctx.conn, kind, _posted_edits(f, kind), reason=f.get("reason", ""))
    except bizbox.Refused as exc:
        return page(ctx, kind, ext_ref, err=f"Not sent: {exc}", posted=posted)
    if not preview["rows"]:
        return page(ctx, kind, ext_ref, err="Nothing is changed: every field and line still reads what BizBox has.", posted=posted)
    hidden = [("ref", ext_ref), ("edit", "1"), ("reason", preview["reason"])] + [
        (f"e:{r['field']}", "" if r["new"] is None else str(r["new"])) for r in preview["rows"]]
    n = len(preview["rows"])
    dialog = finance.review_dialog(f"What will change on {ext_ref}: {n} thing{'s' if n != 1 else ''}", preview | {"same": 0},
                                   action=f"/procurement/{kind}/send", hidden=hidden)
    return page(ctx, kind, ext_ref, dialog=dialog, posted=posted)


def send(ctx, kind: str):
    """POST from the review window: queue the batch for a second person."""
    from .. import redirect
    if kind not in DOCS or DOCS[kind].get("desk"):
        return redirect("/procurement")
    common.require_module(ctx, _module(kind), "WRITE")
    f = ctx.request.form()
    ext_ref = f.get("ref", "")
    if not ext_ref:
        return redirect("/procurement")
    back = finance._url(kind, ext_ref, AREA)
    try:
        out = bizbox.propose_edits(ctx.conn, kind, _posted_edits(f, kind), reason=f.get("reason", ""), at=ctx.now, actor=ctx.user.id)
        ctx.conn.commit()
    except bizbox.Refused as exc:
        ctx.conn.rollback()
        return redirect(back + "&" + urllib.parse.urlencode({"err": f"Not sent: {exc}", "edit": "1"}))
    return redirect(back + "&" + urllib.parse.urlencode(
        {"msg": f"Batch #{out['batch_id']} sent for approval: {out['queued']} change(s). BizBox has not changed yet."}))


# ----------------------------------------------------------------------- slip

def slip(ctx, kind: str):
    """The desk's own slip for the document: what a department accepts in
    place of the printed form (Bizbox Chat, §4: the printed document is the
    product). Opens the print window when asked to (?now=1); the Print button
    stays for a second copy."""
    from .. import HttpError, Response
    if kind not in DOCS:
        raise HttpError("404 Not Found", "No slip for that kind of record.")
    common.require_module(ctx, _module(kind))
    ext_ref = ctx.request.query.get("ref", "")
    spec = DOCS[kind]
    labels = bizbox.labels_for(ctx.conn, kind)
    number = None
    if spec.get("desk"):
        doc = bizbox.desk_document(ctx.conn, kind, ext_ref) if ext_ref else None
        if doc is None:
            raise HttpError("404 Not Found", "No such document on the desk.")
        rec = desk_record(ctx.conn, kind, doc, ext_ref)
        lines = desk_lines(ctx.conn, kind, doc["record"], doc["lines"])
        number = doc["number"]
        read_line = f"Raised on the desk {t.esc(doc['batch']['requested_at'])}"
    else:
        rec = bizbox.get(ctx.conn, kind, ext_ref) if ext_ref else None
        if rec is None:
            raise HttpError("404 Not Found", "No such document in the BizBox mirror.")
        lines = _lines(ctx.conn, kind, ext_ref)
        read_line = f"Read from BizBox {t.esc(rec['synced_at'])}"
    cur = rec["currency"] if "currency" in rec.keys() else None
    facts = "".join(f"<div><dt>{t.esc(lab)}</dt><dd>{t.esc(fact_text(rec, f, labels))}</dd></div>" for f, lab in spec["fields"])
    tot = totals(rec, lines)
    approvals = batches_of(ctx.conn, kind, ext_ref)
    approval = "".join(
        f"<li>Batch #{b['batch_id']} · {t.esc(bizbox.BATCH_WORDS[b['status']])} · proposed by {t.esc(b['requested_by'])} {t.esc(b['requested_at'])}"
        + (f" · approved by {t.esc(b['approved_by'])} {t.esc(b['approved_at'])}" if b["approved_by"] else "") + "</li>" for b, _ in approvals)
    body = (f"<div class='row noprint' style='justify-content:space-between;align-items:center;margin-bottom:12px'>"
            f"<a class=backbtn data-back href='{t.esc(finance._url(kind, ext_ref, AREA))}'>{t.icon('left')}<span class=lbl>Back to the document</span></a>"
            f"<button type=button data-print>{t.icon('reports')} Print</button></div>"
            f"<article class=slip aria-label='{t.esc(spec['word'])} {t.esc(number or ext_ref)} slip'>"
            f"<header><div><div class=kicker>PMC · Materials Management</div><div class=kicker>{t.esc(spec['word'])}</div><h1>{t.esc(number or ext_ref)}</h1></div>"
            f"<div class=stamp><div>{read_line.split(' ', 1)[0]} {read_line.split(' ', 1)[1].rsplit(' ', 1)[0]}</div><b>{t.esc(read_line.rsplit(' ', 1)[1])}</b></div></header>"
            f"<dl class=facts>{facts}</dl>"
            + lines_table(ctx, kind, rec, lines, link_items=False, css="doclines", source=bool(spec.get("desk")))
            + (f"<p class=tot>Total in BizBox: <b>{t.esc(finance._money(tot['header_total'], cur))}</b></p>" if tot["header_total"] is not None else "")
            + (f"<section><h2>Approval on the desk</h2><ul>{approval}</ul></section>" if approval else "")
            + "<div class=sigs><div class=sig>Prepared by</div><div class=sig>Checked by</div><div class=sig>Approved by</div><div class=sig>Received by</div></div>"
            f"<footer>Printed from the PSA desk by {t.esc(ctx.user.name or ctx.user.id)} on {t.esc(ctx.now.strftime('%Y-%m-%d %H:%M'))}. "
            "BizBox is the system of record; this slip shows the document as the desk last read it.</footer></article>"
            + ("<script>window.addEventListener('load',function(){window.print()})</script>" if ctx.request.query.get("now") == "1" else ""))
    return Response(body=t.page(f"{spec['word']} {number or ext_ref} · slip", body, user=ctx.user, active=spec["menu"]))

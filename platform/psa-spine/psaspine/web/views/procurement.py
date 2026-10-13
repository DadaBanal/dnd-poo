"""Procurement: BizBox's MMS module as the reference PSA's Procurement module.

Dada, 13 Oct 2026: "make sure that the mms module is mirrored in a separate
procurement module on connectwise where it will be easier for them to do edits
and adds on the bizbox system and easier for them to do multiple edits as well".
Confirmed before building: a Procurement menu of its own with Purchase orders,
Receiving, Products and Vendors; grids where rows are ticked and changed in one
go, cells are edited in place and saved together, and a new purchase order or
item is added; a Changes tab; and the write path -- approve on the desk, push by
a procedure inside BizBox (bizbox.ProcedureWriter).

The records are the same mirror Finance shows (043); a record's own page is
Finance's, served here under this menu. What changes here never touches the
mirror: every edit or add is a batch (080) that waits for a second person's
approval and then for the push.

Rights (Dada, 13 Oct 2026: "rbac for the procurement module needs to be made
as it will bypass the bizbox permissions"): three areas in Security roles,
purchase orders, receiving and items, each at See, Propose or Approve
(security.PROCUREMENT_AREAS). Every page and action here asks the area the
record belongs to; the menu, Vendors and Changes ask the highest of the three.
Fields with BizBox's choices (status, currency, vendor, unit, category) are
dropdowns and a value off the list is refused (bizbox.check_choice), so what
is approved is something BizBox will take.
"""
from __future__ import annotations

import re
import urllib.parse

from ... import bizbox, db, security
from .. import templates as t
from . import common, finance

AREA = "procurement"
TABS = (("home", "Overview"), ("purchase_order", "Purchase orders"), ("invoice", "Receiving"), ("product", "Products"),
        ("stock", "Stock on hand"), ("movement", "Movements"), ("medicine", "Drugs"), ("vendor", "Vendors"),
        ("warehouse", "Warehouses"), ("changes", "Changes"), ("reports", "Reports"))
# The windows a person picks movements from: days, then months (Dada, 13 Oct
# 2026: "views based on time or days or months").
WINDOWS = ((7, "Last 7 days"), (30, "Last 30 days"), (90, "Last 90 days"), (183, "Last 6 months"), (365, "Last 12 months"))
KINDS = ("purchase_order", "invoice", "product")
NEW_WORDS = {"purchase_order": "New purchase order", "product": "New item"}
# the record in words, one and many, for the review window's title
ONE_WORD = {"purchase_order": "purchase order", "invoice": "receiving report", "product": "item"}
MANY_WORD = {"purchase_order": "purchase orders", "invoice": "receiving reports", "product": "items"}
# the column a vendor filter reads, per kind
VENDOR_COL = {"purchase_order": "vendor", "invoice": "party"}
# the column the first filter reads, per kind: an item has no status, so its
# filter is the category (the reference PSA's Products list filters by one)
FILTER_COL = {"purchase_order": "status", "invoice": "status", "product": "category"}
FILTER_WORD = {"status": "status", "category": "category"}


BACK_KIND = {v: k for k, v in bizbox.LINK_KIND.items()}


def _gate(ctx, kind: str | None = None, need: str = "READ"):
    """The area's module for a kind; the highest of the three for the menu."""
    common.require_module(ctx, security.PROCUREMENT_AREA_OF[kind] if kind else "PROCUREMENT", need)


def _may(ctx, kind: str, need: str = "READ") -> bool:
    return common.allows(ctx, security.PROCUREMENT_AREA_OF[kind], need)


def _can_write(ctx, kind: str) -> bool:
    return _may(ctx, kind, "WRITE")


def _seen(ctx) -> list:
    return [k for k in KINDS if _may(ctx, k)]


def _banners(q) -> str:
    """The page's answer to the last thing sent: the refusal is an alert with
    an id, so the form that drew it points at it (aria-describedby, Part 80)."""
    return ((f"<div class='banner ok' id=flash-ok role=status aria-live=polite>{t.esc(q.get('msg', ''))}</div>" if q.get("msg") else "")
            + (f"<div class='banner err' id=flash-err role=alert>{t.esc(q.get('err', ''))}</div>" if q.get("err") else ""))


def _described(q) -> str:
    return " aria-describedby=flash-err" if q.get("err") else ""


def _tabs(ctx, on: str) -> str:
    seen = _seen(ctx)
    counts = {k: ctx.conn.execute(f"SELECT COUNT(*) FROM {bizbox.KINDS[k][0]} WHERE source_id = ? AND present = 1",
                                  (bizbox.SOURCE,)).fetchone()[0] for k in seen}
    if "purchase_order" in seen or "invoice" in seen:
        counts["vendor"] = len(bizbox.vendors(ctx.conn))
    marks = ",".join("?" * len(seen))
    counts["changes"] = ctx.conn.execute(
        "SELECT COUNT(*) FROM ext_batch WHERE source_id = ? AND status IN ('PENDING', 'APPROVED')"
        f" AND kind IN ({marks})", [bizbox.SOURCE, *(bizbox.LINK_KIND[k] for k in seen)]).fetchone()[0] if seen else 0
    if seen and mms_reports.ready(ctx.conn):
        counts["reports"] = ctx.conn.execute(
            f"SELECT COUNT(*) FROM mms_report WHERE present = 1 AND shown = 1 AND area IN ({marks})", seen).fetchone()[0]
    if _may(ctx, "medicine") and db.table_exists(ctx.conn, "ext_medicine"):
        counts["medicine"] = ctx.conn.execute("SELECT COUNT(*) FROM ext_medicine WHERE source_id = ? AND present = 1", (bizbox.SOURCE,)).fetchone()[0]
    if "product" in seen and db.table_exists(ctx.conn, "ext_warehouse"):
        counts["warehouse"] = ctx.conn.execute("SELECT COUNT(*) FROM ext_warehouse WHERE source_id = ? AND present = 1", (bizbox.SOURCE,)).fetchone()[0]
    if "product" in seen and db.table_exists(ctx.conn, "ext_stock"):
        counts["stock"] = ctx.conn.execute("SELECT COUNT(*) FROM ext_stock WHERE source_id = ? AND present = 1", (bizbox.SOURCE,)).fetchone()[0]
    if "product" in seen and db.table_exists(ctx.conn, "ext_movement"):
        counts["movement"] = bizbox.movements(ctx.conn, days=30, now=ctx.now, limit=1)[1]
    if seen:
        counts["home"] = None
    return ("<div class=stabs>" + "".join(
        f"<a class='{'on' if k == on else ''}' href='/procurement?tab={k}'>{v}{'' if counts[k] is None else f' · {counts[k]}'}</a>"
        for k, v in TABS if k in counts) + "</div>")


def _head(ctx, on: str, q) -> str:
    st = bizbox.status(ctx.conn)
    sync = (f"Read from BizBox {t.esc(st['last_sync_at'])}{t.esc(bizbox.read_words(st['last_result']))}" if st and st["last_sync_at"]
            else "Not read from BizBox yet: the hourly read has not run.")
    return (_banners(q) + "<h1>Procurement</h1><p class=sub>Everything here is read from BizBox: purchase orders, "
            "receiving, items, stock on hand and its movements, and vendors. To change something, tick rows and set one thing on all of them, or edit "
            "the cells in a row, say why, and review it: a window shows what will change before it is sent for approval. "
            "A second person approves it on the Changes tab. Nothing in BizBox changes until it is approved and sent.</p>"
            f"<div class='banner ok'>{sync}</div>" + _tabs(ctx, on))


def index(ctx):
    from .. import Response
    _gate(ctx)
    q = ctx.request.query
    tab = q.get("tab", "")
    if tab == "home":
        return _home(ctx)
    if tab == "stock":
        _gate(ctx, "product")
        return _stock(ctx)
    if tab == "movement":
        _gate(ctx, "product")
        return _movements(ctx)
    if tab == "vendor":
        return _vendors(ctx)
    if tab == "changes":
        return _changes(ctx)
    if tab == "reports":
        return _reports(ctx)
    if tab == "medicine":
        _gate(ctx, "medicine")
        return _drugs(ctx)
    if tab == "warehouse":
        _gate(ctx, "product")
        return _warehouses(ctx)
    if tab not in KINDS:
        # no tab asked for: the overview for a role that sees an area; a
        # role with drugs alone lands on Drugs, which is all it would find
        if _seen(ctx):
            return _home(ctx)
        return _drugs(ctx) if _may(ctx, "medicine") else _changes(ctx)
    _gate(ctx, tab)
    return Response(body=t.page("Procurement", _head(ctx, tab, q) + _grid(ctx, tab), user=ctx.user, active=AREA))


# -------------------------------------------------------------------- grids

def _statuses(conn, kind) -> list[str]:
    """The values the kind's first filter offers: statuses, or an item's categories."""
    table, col = bizbox.KINDS[kind][0], FILTER_COL[kind]
    return [r[0] for r in conn.execute(f"SELECT DISTINCT {col} FROM {table} WHERE source_id = ? AND present = 1"
                                       f" AND {col} IS NOT NULL ORDER BY {col}", (bizbox.SOURCE,))]


def _rows(ctx, kind, *, search, status, vendor, absent, page_no):
    where, params = bizbox._filter(kind, search, absent)             # " FROM <table> WHERE ..." and its params
    if status:
        where += f" AND {FILTER_COL[kind]} = ?"
        params.append(status)
    if vendor and kind in VENDOR_COL:
        where += f" AND {VENDOR_COL[kind]} = ?"
        params.append(vendor)
    total = ctx.conn.execute(f"SELECT COUNT(*){where}", params).fetchone()[0]
    rows = ctx.conn.execute(f"SELECT *{where} ORDER BY ext_ref DESC LIMIT ? OFFSET ?",
                            params + [bizbox.PAGE, (page_no - 1) * bizbox.PAGE]).fetchall()
    return rows, total


def _grid(ctx, kind, *, posted: dict | None = None) -> str:
    """`posted`: what a review window was asked about, so "Go back and
    change it" finds the grid as the person left it (edited cells, ticks,
    the field and the reasons), not BizBox's values again."""
    posted = posted or {}
    cells = posted.get("cells", {})
    ticked = posted.get("refs", set())
    q = ctx.request.query
    search, status, vendor = q.get("q", ""), q.get("status", ""), q.get("vendor", "")
    absent = q.get("absent") == "1"
    page_no = int(q["page"]) if q.get("page", "").isdigit() and int(q["page"]) > 0 else 1
    rows, total = _rows(ctx, kind, search=search, status=status, vendor=vendor, absent=absent, page_no=page_no)
    # Finance's columns, in Procurement's words: the receiving report's
    # counterparty is the vendor here, never "party" (Dada, 13 Oct 2026).
    columns = [(f, "Vendor" if f == "party" else lab) for f, lab in finance._columns(ctx, kind)]
    can = _can_write(ctx, kind)
    editable = bizbox.EDITABLE.get(kind, {}) if can else {}
    choice = {f: bizbox.choices(ctx.conn, kind, f) for f in editable}     # [] for a free-text field
    labels = bizbox.labels_for(ctx.conn, kind)                                # the word for a stored code
    lines = {}
    if kind == "purchase_order" and rows:
        refs = [r["ext_ref"] for r in rows]
        for r in ctx.conn.execute("SELECT po_ref, COUNT(*) AS n FROM ext_po_line WHERE source_id = ? AND present = 1"
                                  f" AND po_ref IN ({','.join('?' * len(refs))}) GROUP BY po_ref", [bizbox.SOURCE, *refs]):
            lines[r["po_ref"]] = r["n"]
    pending = {}
    for c in bizbox.changes(ctx.conn, kind, status="PENDING"):
        pending.setdefault(c["ext_ref"], set()).add(c["field"])
    head = ("<th><input type=checkbox data-tickall aria-label='Tick every row shown'></th>"
            + "".join(f"<th{' class=num' if f in ('amount', 'total', 'unit_cost') else ''}>{t.esc(lab)}</th>" for f, lab in columns)
            + ("<th class=num>Lines</th>" if kind == "purchase_order" else "") + "<th>Waiting</th>")

    def cell(r, f):
        if f == "ext_ref":
            return (f"<td>{finance._ref_link(kind, r['ext_ref'], AREA)}"
                    + ("" if r["present"] else " <span class=pill>gone from BizBox</span>") + "</td>")
        if f in editable and r["present"]:
            v = r[f]
            if f == "unit_cost" and v is not None:
                v = f"{float(v):g}"
            cur = "" if v is None else str(v)
            shown = cells.get(f"e:{r['ext_ref']}:{f}", cur)          # BizBox's value, or what the person had typed
            label = f"{bizbox.FIELD_WORDS.get(f, f)} of {r['ext_ref']}"
            if choice[f]:
                # a dropdown of what BizBox accepts; the row's own value stays
                # choosable even when BizBox no longer lists it
                options = "".join(f"<option value='{t.esc(c)}'{' selected' if c == shown else ''}>{t.esc(l)}</option>" for c, l in choice[f])
                if cur and cur not in {c for c, _ in choice[f]}:
                    options = f"<option value='{t.esc(cur)}'{' selected' if cur == shown else ''}>{t.esc(cur)} (as in BizBox)</option>" + options
                return (f"<td class=ecell><select form=grid name='e:{t.esc(r['ext_ref'])}:{f}' data-was='{t.esc(cur)}'"
                        f" aria-label='{t.esc(label)}'>{options}</select></td>")
            typ = "date" if editable[f] == "date" else "text"
            return (f"<td class='ecell{' num' if f == 'unit_cost' else ''}'><input form=grid type={typ} name='e:{t.esc(r['ext_ref'])}:{f}'"
                    f" value='{t.esc(shown)}' data-was='{t.esc(cur)}' aria-label='{t.esc(label)}'></td>")
        return finance._cell(r, f, AREA, labels)
    trs = []
    for r in rows:
        waiting = ", ".join(sorted(bizbox.FIELD_WORDS.get(f, f) for f in pending.get(r["ext_ref"], ())))
        wait_cell = f"<span class='chip sla-warn'>{t.esc(waiting)}</span>" if waiting else ""
        trs.append(f"<tr><td><input type=checkbox form=bulk name=refs value='{t.esc(r['ext_ref'])}'{' checked' if r['ext_ref'] in ticked else ''}"
                   f" aria-label='Tick {t.esc(r['ext_ref'])}'></td>"
                   + "".join(cell(r, f) for f, _ in columns)
                   + (f"<td class=num>{lines.get(r['ext_ref'], 0)}</td>" if kind == "purchase_order" else "")
                   + f"<td>{wait_cell}</td></tr>")
    ncol = len(columns) + 2 + (1 if kind == "purchase_order" else 0)
    keep = {"tab": kind, "q": search, "status": status, "vendor": vendor} | ({"absent": "1"} if absent else {})
    keep = {k: v for k, v in keep.items() if v}
    first, last = (page_no - 1) * bizbox.PAGE + 1, min(page_no * bizbox.PAGE, total)
    pager = (f"<div class='row schedbar' style='justify-content:space-between'><div class=muted>Showing {first}–{last} of {total}</div><div>"
             + (f"<a class='ghost small' href='/procurement?{urllib.parse.urlencode(keep | {'page': page_no - 1})}'>‹ Previous</a> " if page_no > 1 else "")
             + (f"<a class='ghost small' href='/procurement?{urllib.parse.urlencode(keep | {'page': page_no + 1})}'>Next ›</a>" if last < total else "")
             + "</div></div>") if total > bizbox.PAGE else f"<div class=muted style='margin-top:8px'>{total} record(s).</div>"
    sopts = "".join(f"<option value='{t.esc(s)}'{' selected' if s == status else ''}>{t.esc(bizbox.word(labels, FILTER_COL[kind], s))}</option>"
                    for s in _statuses(ctx.conn, kind))
    vopts = "".join(f"<option value='{t.esc(v['name'])}'{' selected' if v['name'] == vendor else ''}>{t.esc(v['name'])}</option>"
                    for v in bizbox.vendors(ctx.conn)) if kind in VENDOR_COL else ""
    filters = (f"<form method=get action='/procurement' class='row schedbar'><input type=hidden name=tab value={kind}>"
               f"<div style='flex:1 1 220px'><input name=q value='{t.esc(search)}' placeholder='Search {dict(TABS)[kind].lower()}'></div>"
               f"<div style='flex:0 0 160px'><select name=status aria-label='{FILTER_WORD[FILTER_COL[kind]].capitalize()}'><option value=''>Any {FILTER_WORD[FILTER_COL[kind]]}</option>{sopts}</select></div>"
               + (f"<div style='flex:0 0 200px'><select name=vendor aria-label=Vendor><option value=''>Any vendor</option>{vopts}</select></div>" if vopts else "")
               + f"<div style='flex:0 0 auto'><label><input type=checkbox name=absent value=1{' checked' if absent else ''}> Gone from BizBox too</label></div>"
               "<div style='flex:0 0 auto'><button class=ghost type=submit>Filter</button></div>"
               + (f"<div style='flex:0 0 auto'><a class=btn href='/procurement/{kind}/new'>{t.icon('plus')} {NEW_WORDS[kind]}</a></div>"
                  if can and kind in bizbox.ADDABLE else "") + "</form>")
    tools = ""
    if can and editable:
        fopts = "".join(f"<option value={f}{' selected' if f == posted.get('field') else ''}>{t.esc(bizbox.FIELD_WORDS[f])}</option>" for f in editable)
        why_bulk = t.esc(posted.get("reason", "")) if posted.get("form") == "bulk" else ""
        why_grid = t.esc(posted.get("reason", "")) if posted.get("form") == "grid" else ""
        tools = (f"<form id=bulk method=post action='/procurement/{kind}/bulk/review' class='row schedbar bulkbar' style='margin-top:10px' data-valuepick{_described(q)}>"
                 "<div style='flex:0 0 auto' aria-live=polite><b><span data-ticked>0</span> ticked</b> · change</div>"
                 f"<div style='flex:0 0 170px'><select name=field aria-label='Field to change'>{fopts}</select></div>"
                 f"<div style='flex:1 1 160px'>{finance.value_inputs(ctx, kind, list(editable))}</div>"
                 f"<div style='flex:1 1 200px'><input name=reason required maxlength=400 value='{why_bulk}' placeholder='Why? The approver sees this'></div>"
                 f"<div style='flex:0 0 auto'><button type=submit>{t.icon('checks')} Review and send</button></div></form>"
                 f"<form id=grid method=post action='/procurement/{kind}/edits/review' class='row schedbar' style='margin-top:6px'{_described(q)}>"
                 "<div style='flex:0 0 auto' aria-live=polite><b><span data-edited>0</span> cell(s) edited</b></div>"
                 f"<div style='flex:1 1 260px'><input name=reason maxlength=400 value='{why_grid}' placeholder='Why? Needed before sending edited cells'></div>"
                 f"<div style='flex:0 0 auto'><button class=ghost type=submit>{t.icon('checks')} Review edited cells and send</button></div></form>")
    script = ("<script>(function(){var tick=document.querySelector('[data-tickall]');var n=document.querySelector('[data-ticked]');"
              "var boxes=function(){return Array.prototype.slice.call(document.querySelectorAll(\"input[form=bulk][name=refs]\"))};"
              "function count(){if(n)n.textContent=boxes().filter(function(b){return b.checked}).length}"
              "if(tick)tick.addEventListener('change',function(){boxes().forEach(function(b){b.checked=tick.checked});count()});"
              "boxes().forEach(function(b){b.addEventListener('change',count)});"
              "var e=document.querySelector('[data-edited]');function edited(){var c=0;document.querySelectorAll('td.ecell input,td.ecell select').forEach(function(i){"
              "if(i.value!==i.getAttribute('data-was')){c++;i.classList.add('edited')}else{i.classList.remove('edited')}});if(e)e.textContent=c}"
              "document.querySelectorAll('td.ecell input,td.ecell select').forEach(function(i){i.addEventListener('input',edited);i.addEventListener('change',edited)});edited();count()})()</script>"
              + finance.VALUE_PICK_SCRIPT)
    return ("<div class=card>" + filters + tools + f"<div class=tablewrap><table class='compact pgrid'><thead><tr>{head}</tr></thead><tbody>"
            + ("".join(trs) or f"<tr><td colspan={ncol} class=muted>Nothing here yet.</td></tr>") + "</tbody></table></div>" + pager
            + "</div>" + script)


# ------------------------------------------------------------------ vendors

def _vendors(ctx):
    from .. import Response
    q = ctx.request.query
    search = q.get("q", "")
    rows = bizbox.vendors(ctx.conn, q=search)
    trs = "".join(
        f"<tr><td><b>{t.esc(v['name'])}</b></td>"
        f"<td class=num><a href='/procurement?{urllib.parse.urlencode({'tab': 'purchase_order', 'vendor': v['name']})}'>{v['pos']}</a></td>"
        f"<td class=num>{t.esc(finance._money(v['po_total'], 'PHP'))}</td>"
        f"<td class=num><a href='/procurement?{urllib.parse.urlencode({'tab': 'invoice', 'vendor': v['name']})}'>{v['receipts']}</a></td>"
        f"<td class=num>{t.esc(finance._money(v['rr_total'], 'PHP'))}</td></tr>" for v in rows)
    body = (_head(ctx, "vendor", q) + "<div class=card><form method=get action='/procurement' class='row schedbar'>"
            "<input type=hidden name=tab value=vendor>"
            f"<div style='flex:1 1 260px'><input name=q value='{t.esc(search)}' placeholder='Search vendors'></div>"
            "<div style='flex:0 0 auto'><button class=ghost type=submit>Search</button></div></form>"
            "<p class=why>The vendors BizBox names on purchase orders and receipts. A vendor's own record stays in BizBox "
            "(its people table), so there is nothing to edit here; the name on each order is edited on the order.</p>"
            "<div class=tablewrap><table class=compact><thead><tr><th>Vendor</th><th class=num>Purchase orders</th><th class=num>Ordered</th>"
            "<th class=num>Receipts</th><th class=num>Received</th></tr></thead><tbody>"
            + (trs or "<tr><td colspan=5 class=muted>No vendor named yet.</td></tr>") + "</tbody></table></div></div>")
    return Response(body=t.page("Procurement · Vendors", body, user=ctx.user, active=AREA))


# ------------------------------------------------------------------ changes

def _batch_what(b) -> str:
    kind = {v: k for k, v in bizbox.LINK_KIND.items()}[b["kind"]]
    word = {"purchase_order": "purchase order", "invoice": "receipt", "product": "item", "agreement": "agreement"}[kind]
    if b["change_kind"] == "ADD":
        p = bizbox.payload_of(b)
        rec = p.get("record", {})
        return f"New {word}: {t.esc(rec.get('name') or rec.get('vendor') or '')}" + (f", {len(p.get('lines') or [])} line(s)" if p.get("lines") else "")
    n = b["n"] if "n" in b.keys() else 0
    return f"{n} {word}{'s' if n != 1 else ''} changed"


def _batch_actions(ctx, b) -> str:
    """Approve: the area's Approve level, never one's own. Cancel: the person
    who asked, or an approver of the area."""
    if b["status"] not in ("PENDING", "APPROVED"):
        return ""
    kind = BACK_KIND[b["kind"]]
    mine = (b["requested_by"] or "").lower() == (ctx.user.id or "").lower()
    approver = _may(ctx, kind, "ADMIN")
    out = ""
    if b["status"] == "PENDING" and approver and not mine:
        out += (f"<form method=post action='/procurement/batch/{b['batch_id']}/approve' class=inline>"
                f"<button class=small type=submit>{t.icon('check')} Approve</button></form> ")
    elif b["status"] == "PENDING" and mine:
        out += "<span class=muted>yours: someone else approves</span> "
    if mine or approver:
        out += (f"<form method=post action='/procurement/batch/{b['batch_id']}/cancel' class=inline>"
                "<button class='ghost small' type=submit>Cancel</button></form>")
    return out


def _changes(ctx):
    from .. import Response
    q = ctx.request.query
    status = q.get("status", "OPEN")
    if status not in ("OPEN", "PENDING", "APPROVED", "APPLIED", "REJECTED", "CANCELLED", "ALL"):
        status = "OPEN"
    rows = bizbox.batches(ctx.conn, status=None if status in ("OPEN", "ALL") else status)
    seen = {bizbox.LINK_KIND[k] for k in _seen(ctx)}
    rows = [b for b in rows if b["kind"] in seen and (status != "OPEN" or b["status"] in ("PENDING", "APPROVED"))]
    opts = "".join(f"<option value={k}{' selected' if k == status else ''}>{v}</option>" for k, v in (
        ("OPEN", "Waiting to be approved or sent"), ("PENDING", "Waiting for approval"), ("APPROVED", "Approved, waiting to be sent"),
        ("APPLIED", "Applied in BizBox"), ("REJECTED", "Refused by BizBox"), ("CANCELLED", "Cancelled"), ("ALL", "All")))
    trs = "".join(
        f"<tr><td><a href='/procurement/batch/{b['batch_id']}'>#{b['batch_id']}</a></td><td>{_batch_what(b)}</td>"
        f"<td>{t.esc(b['reason'])}</td><td>{t.esc(b['requested_by'])}<div class=muted>{t.esc(b['requested_at'])}</div></td>"
        f"<td>{t.esc(b['approved_by'] or '—')}</td><td>{t.chip(bizbox.BATCH_WORDS[b['status']])}"
        + (f"<div class=muted>{t.esc(b['answer'])}</div>" if b["answer"] else "") + f"</td><td>{_batch_actions(ctx, b)}</td></tr>"
        for b in rows)
    try:
        writer = bizbox.writer_in_force().name
    except bizbox.Refused:
        writer = "none"
    how = ("Approved changes are sent to BizBox by the scheduled run on the host."
           if writer != "none" else
           "<b>Changes are not sent to BizBox automatically yet:</b> that link is still being set up. An approved change "
           "waits here until it is, or until someone makes the change in BizBox by hand and marks it applied here.")
    body = (_head(ctx, "changes", q) + "<div class=card><form method=get action='/procurement' class='row schedbar'>"
            f"<input type=hidden name=tab value=changes><div style='flex:0 0 300px'><select name=status>{opts}</select></div>"
            "<div style='flex:0 0 auto'><button class=ghost type=submit>Show</button></div></form>"
            f"<p class=why>Each batch is one request: one reason, one approval. Someone with Procurement write access approves it, never the person who asked. {how}</p>"
            "<div class=tablewrap><table class=compact><thead><tr><th>Batch</th><th>What</th><th>Why</th><th>Asked by</th>"
            "<th>Approved by</th><th>State</th><th></th></tr></thead><tbody>"
            + (trs or "<tr><td colspan=7 class=muted>Nothing waiting.</td></tr>") + "</tbody></table></div></div>")
    return Response(body=t.page("Procurement · Changes", body, user=ctx.user, active=AREA))


def batch_page(ctx, batch_id):
    from .. import HttpError, Response
    _gate(ctx)
    b = bizbox.batch(ctx.conn, int(batch_id) if str(batch_id).isdigit() else -1)
    if b is None:
        raise HttpError("404 Not Found", "No such batch.")
    _gate(ctx, BACK_KIND[b["kind"]])
    rows = bizbox.batch_changes(ctx.conn, b["batch_id"])
    b = dict(b) | {"n": len(rows)}
    kind = {v: k for k, v in bizbox.LINK_KIND.items()}[b["kind"]]
    extra = ""
    if b["change_kind"] == "ADD":
        p = bizbox.payload_of(b)
        rec, lines = p.get("record", {}), p.get("lines") or []
        labels = bizbox.labels_for(ctx.conn, kind)
        facts = "".join(f"<dt>{t.esc(bizbox.FIELD_WORDS.get(f, f.replace('_', ' ').capitalize()))}</dt><dd>{t.esc(bizbox.word(labels, f, v))}</dd>" for f, v in rec.items())
        extra = f"<div class=card><h3>{t.icon('plus')}The new record</h3><dl class=kv>{facts}</dl>"
        if lines:
            extra += ("<div class=tablewrap><table class=compact><thead><tr><th>#</th><th>Item</th><th>Description</th><th class=num>Qty</th>"
                      "<th class=num>Unit cost</th></tr></thead><tbody>"
                      + "".join(f"<tr><td>{i}</td><td>{finance._ref_link('product', l.get('product_ref'), AREA)}</td><td>{t.esc(l.get('description') or '')}</td>"
                                f"<td class=num>{t.esc(str(l.get('quantity') or ''))}</td><td class=num>{t.esc(finance._money(l.get('unit_cost')))}</td></tr>"
                                for i, l in enumerate(lines, 1)) + "</tbody></table></div>")
        extra += "</div>"
    q = ctx.request.query
    body = (_banners(q) + f"<h1>Change batch #{b['batch_id']}</h1><p class=sub>{_batch_what(b)} · {t.chip(bizbox.BATCH_WORDS[b['status']])}"
            f" · asked by {t.esc(b['requested_by'])} {t.esc(b['requested_at'])}"
            + (f" · approved by {t.esc(b['approved_by'])} {t.esc(b['approved_at'])}" if b["approved_by"] else "")
            + f" · <a href='/procurement?tab=changes'>Changes</a></p>"
            f"<div class=card><p><b>Why:</b> {t.esc(b['reason'])}</p>"
            + (f"<p><b>BizBox's answer:</b> {t.esc(b['answer'])}</p>" if b["answer"] else "")
            + f"<p>{_batch_actions(ctx, b)}</p></div>" + extra
            + ("<div class=card><h3>" + t.icon("rows") + "The changes</h3>" + finance._changes_table(ctx, rows, pending_word=bizbox.BATCH_WORDS[b['status']] if b['status'] in ('PENDING', 'APPROVED') else 'Waiting for BizBox') + "</div>"
               if b["change_kind"] == "EDIT" else ""))
    return Response(body=t.page(f"Batch #{b['batch_id']}", body, user=ctx.user, active=AREA))


def _batch_or_404(ctx, batch_id):
    from .. import HttpError
    b = bizbox.batch(ctx.conn, int(batch_id) if str(batch_id).isdigit() else -1)
    if b is None:
        raise HttpError("404 Not Found", "No such batch.")
    return b


def approve(ctx, batch_id):
    from .. import redirect
    _gate(ctx)
    _gate(ctx, BACK_KIND[_batch_or_404(ctx, batch_id)["kind"]], "ADMIN")
    try:
        bizbox.approve(ctx.conn, int(batch_id) if str(batch_id).isdigit() else -1, at=ctx.now, actor=ctx.user.id)
        ctx.conn.commit()
    except bizbox.Refused as exc:
        ctx.conn.rollback()
        return redirect("/procurement?" + urllib.parse.urlencode({"tab": "changes", "err": str(exc)}))
    return redirect("/procurement?" + urllib.parse.urlencode({"tab": "changes", "msg": f"Batch #{batch_id} approved. It will be sent to BizBox on the next run."}))


def cancel(ctx, batch_id):
    from .. import redirect
    _gate(ctx)
    b = _batch_or_404(ctx, batch_id)
    if (b["requested_by"] or "").lower() != (ctx.user.id or "").lower():
        _gate(ctx, BACK_KIND[b["kind"]], "ADMIN")
    try:
        n = bizbox.cancel_batch(ctx.conn, int(batch_id) if str(batch_id).isdigit() else -1, at=ctx.now, actor=ctx.user.id)
        ctx.conn.commit()
    except bizbox.Refused as exc:
        ctx.conn.rollback()
        return redirect("/procurement?" + urllib.parse.urlencode({"tab": "changes", "err": str(exc)}))
    return redirect("/procurement?" + urllib.parse.urlencode({"tab": "changes", "msg": f"Batch #{batch_id} cancelled ({n} change(s))."}))


# ------------------------------------------------------------ bulk and edits

def _back(kind, **extra) -> str:
    return "/procurement?" + urllib.parse.urlencode({"tab": kind} | extra)


def bulk(ctx, kind):
    from .. import redirect
    _gate(ctx)
    if kind not in KINDS:
        return redirect("/procurement")
    _gate(ctx, kind, "WRITE")
    f = ctx.request.form()
    try:
        out = bizbox.propose_many(ctx.conn, kind, ctx.request.form_list("refs"), f.get("field", ""),
                                  finance.picked_value(f, f.get("field", "")),
                                  reason=f.get("reason", ""), at=ctx.now, actor=ctx.user.id)
        ctx.conn.commit()
    except bizbox.Refused as exc:
        ctx.conn.rollback()
        return redirect(_back(kind, err=f"Not queued: {exc}"))
    return redirect(_back(kind, msg=f"Batch #{out['batch_id']} queued: {out['queued']} record(s)"
                                    + (f", {out['same']} already so" if out["same"] else "") + ". A second person approves it on the Changes tab."))


def edits(ctx, kind):
    from .. import redirect
    _gate(ctx)
    if kind not in KINDS:
        return redirect("/procurement")
    _gate(ctx, kind, "WRITE")
    f = ctx.request.form()
    try:
        out = bizbox.propose_edits(ctx.conn, kind, _cells(f), reason=f.get("reason", ""), at=ctx.now, actor=ctx.user.id)
        ctx.conn.commit()
    except bizbox.Refused as exc:
        ctx.conn.rollback()
        return redirect(_back(kind, err=f"Not queued: {exc}"))
    return redirect(_back(kind, msg=f"Batch #{out['batch_id']} queued: {out['queued']} cell(s). A second person approves it on the Changes tab."))


def _grid_page(ctx, kind, *, dialog: str = "", err: str = "", posted: dict | None = None):
    """The tab as a POST answers it: the grid as the person left it, with the
    review window on top or a refusal above."""
    from .. import Response
    banner = f"<div class='banner err' id=flash-err role=alert>{t.esc(err)}</div>" if err else ""
    return Response(body=t.page("Procurement", banner + dialog + _head(ctx, kind, ctx.request.query) + _grid(ctx, kind, posted=posted),
                                user=ctx.user, active=AREA))


def _posted(f, form: str, refs=()) -> dict:
    return {"form": form, "cells": {k: f.get(k, "") for k in f.keys() if k.startswith("e:")},
            "refs": {str(r).strip() for r in refs}, "field": f.get("field", ""), "reason": f.get("reason", "")}


def _cells(f) -> list:
    triples = []
    for key in f.keys():
        if not key.startswith("e:"):
            continue
        parts = key.split(":", 2)
        if len(parts) == 3:
            triples.append((parts[1], parts[2], f.get(key, "")))
    return triples


def review_bulk(ctx, kind):
    """POST from the tick-and-change bar: the window that says what will
    change on the ticked rows. Nothing is queued yet (Dada, 13 Oct 2026)."""
    from .. import redirect
    _gate(ctx)
    if kind not in KINDS:
        return redirect("/procurement")
    _gate(ctx, kind, "WRITE")
    f = ctx.request.form()
    refs = ctx.request.form_list("refs")
    field = f.get("field", "")
    value = finance.picked_value(f, field)
    posted = _posted(f, "bulk", refs)
    try:
        preview = bizbox.preview_many(ctx.conn, kind, refs, field, value, reason=f.get("reason", ""))
    except bizbox.Refused as exc:
        return _grid_page(ctx, kind, err=f"Not sent: {exc}", posted=posted)
    if not preview["rows"]:
        return _grid_page(ctx, kind, err="Nothing is changed: every ticked record already has that value in BizBox.", posted=posted)
    hidden = ([("refs", r) for r in dict.fromkeys(str(x).strip() for x in refs) if r]
              + [("field", field), ("new_value", value), ("reason", preview["reason"])])
    n = len(preview["rows"])
    dialog = finance.review_dialog(f"What will change on {n} {ONE_WORD[kind] if n == 1 else MANY_WORD[kind]}", preview,
                                   action=f"/procurement/{kind}/bulk", hidden=hidden, show_ref=True)
    return _grid_page(ctx, kind, dialog=dialog, posted=posted)


def review_edits(ctx, kind):
    """POST from the grid's edited cells: the window that lists each cell
    that differs from BizBox, from -> to. Nothing is queued yet."""
    from .. import redirect
    _gate(ctx)
    if kind not in KINDS:
        return redirect("/procurement")
    _gate(ctx, kind, "WRITE")
    f = ctx.request.form()
    posted = _posted(f, "grid")
    try:
        preview = bizbox.preview_edits(ctx.conn, kind, _cells(f), reason=f.get("reason", ""))
    except bizbox.Refused as exc:
        return _grid_page(ctx, kind, err=f"Not sent: {exc}", posted=posted)
    if not preview["rows"]:
        return _grid_page(ctx, kind, err="Nothing is changed: every cell still reads what BizBox has.", posted=posted)
    hidden = [(f"e:{r['ref']}:{r['field']}", "" if r["new"] is None else str(r["new"])) for r in preview["rows"]] + [("reason", preview["reason"])]
    n, recs = len(preview["rows"]), len({r["ref"] for r in preview["rows"]})
    dialog = finance.review_dialog(f"What will change: {n} cell{'s' if n != 1 else ''} on {recs} {ONE_WORD[kind] if recs == 1 else MANY_WORD[kind]}",
                                   preview | {"same": 0}, action=f"/procurement/{kind}/edits", hidden=hidden, show_ref=True)   # every cell was posted
    return _grid_page(ctx, kind, dialog=dialog, posted=posted)


# ---------------------------------------------------------------------- adds

def _pick(ctx, kind, field, name, chosen="", *, empty=None, required=False, fallback=""):
    """A dropdown of BizBox's choices for the field, or the plain input when
    there is no list yet."""
    opts = bizbox.choices(ctx.conn, kind, field)
    if not opts:
        return fallback
    o = (f"<option value=''>{t.esc(empty)}</option>" if empty is not None else "") + "".join(
        f"<option value='{t.esc(c)}'{' selected' if c == chosen else ''}>{t.esc(l)}</option>" for c, l in opts)
    return f"<select name={name}{' required' if required else ''}>{o}</select>"


def new_form(ctx, kind):
    """GET: the New form; a refusal that came back as a redirect carries the
    typed values in the query."""
    from .. import HttpError
    _gate(ctx)
    if kind not in bizbox.ADDABLE:
        raise HttpError("404 Not Found", "Nothing of that kind is added from the desk.")
    _gate(ctx, kind, "WRITE")
    q = ctx.request.query
    return _new_page(ctx, kind, posted={k: q.get(k, "") for k in q.keys()})


def _new_page(ctx, kind, *, posted: dict | None = None, dialog: str = "", err: str = ""):
    """The New form, prefilled from `posted` (the query on a GET, the form on
    a review), with the review window on top or a refusal above."""
    from .. import Response
    q = ctx.request.query
    v = posted or {}
    g = lambda k: v.get(k, "") or ""
    if kind == "purchase_order":
        items = "".join(f"<option value='{t.esc(p['ext_ref'])}'>{t.esc(p['name'])}</option>"
                        for p in bizbox.records(ctx.conn, "product", limit=2000))
        line = lambda i: (f"<tr><td>{i}</td><td><input name='line{i}_product_ref' list=items maxlength=64 placeholder='item code'"
                          f" value='{t.esc(g(f'line{i}_product_ref'))}'></td>"
                          f"<td><input name='line{i}_description' maxlength=400 value='{t.esc(g(f'line{i}_description'))}'></td>"
                          f"<td><input name='line{i}_quantity' type=number step=any min=0 style='width:90px' value='{t.esc(g(f'line{i}_quantity'))}'></td>"
                          f"<td><input name='line{i}_unit_cost' type=number step=any min=0 style='width:110px' value='{t.esc(g(f'line{i}_unit_cost'))}'></td></tr>")
        currencies = bizbox.choices(ctx.conn, kind, "currency")
        php = "PHP" if any(c == "PHP" for c, _ in currencies) else (currencies[0][0] if currencies else "")
        fields = ("<div><label>Vendor</label>"
                  + _pick(ctx, kind, "vendor", "vendor", g("vendor"), empty="Choose a vendor BizBox has", required=True,
                          fallback=f"<input name=vendor required maxlength=400 value='{t.esc(g('vendor'))}' placeholder='no vendor read from BizBox yet'>")
                  + "</div>"
                  f"<div><label>Order date</label><input type=date name=ordered_on value='{t.esc(g('ordered_on'))}'></div>"
                  "<div><label>Currency</label>"
                  + _pick(ctx, kind, "currency", "currency", g("currency") or php, fallback=f"<input name=currency maxlength=8 value='{t.esc(g('currency') or 'PHP')}'>")
                  + "</div><div><label>Status</label>"
                  + _pick(ctx, kind, "status", "status", g("status"), empty="Leave to BizBox",
                          fallback=f"<input name=status maxlength=32 value='{t.esc(g('status'))}' placeholder='leave empty: BizBox decides'>")
                  + "</div>"
                  "<div style='grid-column:1/-1'><label>Lines</label><div class=tablewrap><table class=compact><thead><tr><th>#</th><th>Item</th>"
                  "<th>Description</th><th>Qty</th><th>Unit cost</th></tr></thead><tbody>" + "".join(line(i) for i in range(1, 9))
                  + f"</tbody></table></div><datalist id=items>{items}</datalist></div>")
    else:
        fields = (f"<div><label>Item code</label><input name=ext_ref maxlength=64 value='{t.esc(g('ext_ref'))}' placeholder='leave empty: BizBox numbers it'></div>"
                  f"<div><label>Name</label><input name=name required maxlength=400 value='{t.esc(g('name'))}'></div>"
                  "<div><label>Category</label>"
                  + _pick(ctx, kind, "category", "category", g("category"), empty="(none)",
                          fallback=f"<input name=category maxlength=400 value='{t.esc(g('category'))}'>")
                  + "</div><div><label>Unit</label>"
                  + _pick(ctx, kind, "unit", "unit", g("unit"), empty="(none)",
                          fallback=f"<input name=unit maxlength=32 value='{t.esc(g('unit'))}' placeholder='pc, box, ream'>")
                  + "</div>"
                  f"<div><label>Unit cost</label><input name=unit_cost type=number step=any min=0 value='{t.esc(g('unit_cost'))}'></div>")
    banner = f"<div class='banner err' id=flash-err role=alert>{t.esc(err)}</div>" if err else ""
    body = (banner + _banners(q) + dialog
            + f"<h1>{NEW_WORDS[kind]}</h1><p class=sub>This goes to the Changes tab for a second person to approve. Once it is approved and sent, BizBox "
            f"creates it and gives it its number. <a href='/procurement?tab={kind}'>Back</a></p>"
            f"<div class=card><form method=post action='/procurement/{kind}/add/review' class=fields{' aria-describedby=flash-err' if err else _described(q)}><div class=grid2>{fields}"
            f"<div style='grid-column:1/-1'><label>Why</label><input name=reason required maxlength=400 value='{t.esc(g('reason'))}' placeholder='What the approver needs to know'></div>"
            f"</div><div style='margin-top:12px'><button type=submit>{t.icon('checks')} Review and send</button> "
            "<span class=muted>The window shows what will be created before it is sent.</span></div></form></div>")
    return Response(body=t.page(NEW_WORDS[kind], body, user=ctx.user, active=AREA))


def _add_parts(f, kind) -> tuple:
    record = {k: f.get(k, "") for k in bizbox.ADDABLE[kind]["fields"]}
    lines = []
    if bizbox.ADDABLE[kind]["lines"]:
        for i in range(1, 9):
            lines.append({k: f.get(f"line{i}_{k}", "") for k in bizbox.ADDABLE[kind]["lines"]})
    return record, lines


def _add_body(ctx, kind, checked: dict) -> str:
    """The review window's table for a new record: each field as it will be
    created, in BizBox's words, then the lines and their total."""
    rec, lines = checked["record"], checked["lines"]
    labels = bizbox.labels_for(ctx.conn, kind)
    left = {"status": "Left to BizBox", "ext_ref": "BizBox numbers it", "category": "(none)", "unit": "(none)"}

    def shown(field):
        v = rec.get(field)
        if v in (None, ""):
            return f"<span class=muted>{t.esc(left.get(field, '—'))}</span>"
        if field == "unit_cost":
            return t.esc(finance._money(v))
        return f"<b>{t.esc(bizbox.word(labels, field, v) or str(v))}</b>"
    words = {"ext_ref": "Item code"} | bizbox.FIELD_WORDS
    rows = "".join(f"<tr><td>{t.esc(words.get(f, f.replace('_', ' ').capitalize()))}</td><td>{shown(f)}</td></tr>"
                   for f in bizbox.ADDABLE[kind]["fields"])
    out = f"<div class=tablewrap><table class=compact><thead><tr><th>Field</th><th>Will be</th></tr></thead><tbody>{rows}</tbody></table></div>"
    if bizbox.ADDABLE[kind]["lines"]:
        cur = rec.get("currency")
        total = sum(float(l.get("quantity") or 0) * float(l.get("unit_cost") or 0) for l in lines)
        trs = "".join(f"<tr><td>{n}</td><td>{t.esc(l.get('product_ref') or '')}</td><td>{t.esc(l.get('description') or '')}</td>"
                      f"<td class=num>{float(l.get('quantity') or 0):g}</td><td class=num>{t.esc(finance._money(l.get('unit_cost')))}</td>"
                      f"<td class=num>{t.esc(finance._money(float(l.get('quantity') or 0) * float(l.get('unit_cost') or 0)))}</td></tr>"
                      for n, l in enumerate(lines, 1))
        out += (f"<p style='margin:10px 0 4px'><b>{len(lines)} line{'s' if len(lines) != 1 else ''}</b></p>"
                "<div class=tablewrap><table class=compact><thead><tr><th>#</th><th>Item</th><th>Description</th><th class=num>Qty</th>"
                f"<th class=num>Unit cost</th><th class=num>Extended</th></tr></thead><tbody>{trs}"
                f"<tr><td colspan=5 class=num><b>Lines total</b></td><td class=num><b>{t.esc(finance._money(total, cur))}</b></td></tr></tbody></table></div>")
    return out


def review_add(ctx, kind):
    """POST from a New form: the window that says what will be created.
    Nothing is queued yet (Dada, 13 Oct 2026)."""
    from .. import redirect
    _gate(ctx)
    if kind not in bizbox.ADDABLE:
        return redirect("/procurement")
    _gate(ctx, kind, "WRITE")
    f = ctx.request.form()
    posted = {k: f.get(k, "") for k in f.keys()}
    record, lines = _add_parts(f, kind)
    try:
        checked = bizbox.check_add(ctx.conn, kind, record, lines, reason=f.get("reason", ""))
    except bizbox.Refused as exc:
        return _new_page(ctx, kind, posted=posted, err=f"Not sent: {exc}")
    hidden = [(k, v) for k, v in record.items() if v] + [("reason", checked["reason"])]
    for i, line in enumerate(lines, 1):
        hidden += [(f"line{i}_{k}", v) for k, v in line.items() if v]
    n = len(checked["lines"])
    title = (f"What will be created: a purchase order with {n} line{'s' if n != 1 else ''}" if kind == "purchase_order"
             else f"What will be created: the item {checked['record'].get('name', '')}")
    dialog = finance.review_dialog(title, {"rows": [], "same": 0, "reason": checked["reason"]}, action=f"/procurement/{kind}/add",
                                   hidden=hidden, body=_add_body(ctx, kind, checked),
                                   note="Sending it queues the new record for a second person to approve. BizBox creates it, and "
                                        "gives it its number, only after that, when the approved change is pushed.")
    return _new_page(ctx, kind, posted=posted, dialog=dialog)


def add(ctx, kind):
    from .. import redirect
    _gate(ctx)
    if kind not in bizbox.ADDABLE:
        return redirect("/procurement")
    _gate(ctx, kind, "WRITE")
    f = ctx.request.form()
    record, lines = _add_parts(f, kind)
    try:
        bid = bizbox.propose_add(ctx.conn, kind, record, lines, reason=f.get("reason", ""), at=ctx.now, actor=ctx.user.id)
        ctx.conn.commit()
    except bizbox.Refused as exc:
        ctx.conn.rollback()
        return redirect(f"/procurement/{kind}/new?" + urllib.parse.urlencode({"err": f"Not queued: {exc}", **{k: v for k, v in record.items() if v}}))
    return redirect("/procurement?" + urllib.parse.urlencode({"tab": "changes", "msg": f"Batch #{bid} queued: {NEW_WORDS[kind].lower()}. A second person approves it here."}))


def detail(ctx, kind):
    return finance.detail(ctx, kind, area=AREA)


# ------------------------------------------------------------------ reports
#
# MMS reports (082, Dada 13 Oct 2026: "printing out reports for MMS"). The
# reports exist on the report server; the desk lists them by area, asks the
# server for each one's parameters, and shows the PDF on the page or hands
# over the Excel. Staff never leave the desk and never touch SSRS.

from ... import mms_reports, ssrs                     # noqa: E402 - below the module's own helpers on purpose

SSRS_FACTORY = None          # the tests put a client with a fake transport here


def _ssrs():
    return (SSRS_FACTORY or ssrs.Ssrs)()


def _reports(ctx):
    from .. import Response
    q = ctx.request.query
    search = q.get("q", "")
    area = q.get("area", "") if q.get("area", "") in mms_reports.AREAS else ""
    seen = _seen(ctx)
    if not mms_reports.ready(ctx.conn):
        body = _head(ctx, "reports", q) + ("<div class=card><p class=muted>The desk cannot list reports until schema 082 "
                                           "is applied on the host. Nothing else is affected.</p></div>")
        return Response(body=t.page("Procurement · Reports", body, user=ctx.user, active=AREA))
    rows = mms_reports.listed(ctx.conn, areas=[area] if area else seen, q=search)
    chips = "".join(
        f"<a class='{'on' if a == area else ''}' href='/procurement?{urllib.parse.urlencode({'tab': 'reports', 'q': search} | ({'area': a} if a else {}))}'>"
        f"{t.esc(w)}</a>" for a, w in [("", "Every area")] + [(a, mms_reports.AREA_WORDS[a]) for a in seen])
    groups = []
    for a in (seen if not area else [area]):
        here = [r for r in rows if r["area"] == a]
        if not here:
            continue
        items = "".join(
            f"<li><a class=rpt href='/procurement/report/{r['report_id']}'><b>{t.esc(r['title'])}</b>"
            + (f"<span class=muted> · {t.esc(r['description'])}</span>" if r["description"] else "")
            + (f"<div class=muted>Asks: {t.esc(', '.join(mms_reports.params_summary(r)))}</div>" if mms_reports.params_summary(r) else "")
            + "</a></li>" for r in here)
        groups.append(f"<div class=card><h3>{t.icon('reports')}{t.esc(mms_reports.AREA_WORDS[a])} · {len(here)}</h3><ul class='plain rptlist'>{items}</ul></div>")
    total = ctx.conn.execute("SELECT COUNT(*) FROM mms_report WHERE present = 1").fetchone()[0]
    empty = ("<div class=card><p class=muted>The desk has not read the report server's list yet. SQL01 runs the first read; "
             "after that it is read on a schedule.</p></div>" if not total else
             "<div class=card><p class=muted>No report matches.</p></div>")
    body = (_head(ctx, "reports", q) + "<div class=card><form method=get action='/procurement' class='row schedbar'>"
            "<input type=hidden name=tab value=reports>" + (f"<input type=hidden name=area value='{area}'>" if area else "")
            + f"<div style='flex:1 1 260px'><input name=q value='{t.esc(search)}' placeholder='Search reports'></div>"
            "<div style='flex:0 0 auto'><button class=ghost type=submit>Search</button></div></form>"
            f"<div class=stabs style='margin:10px 0 0'>{chips}</div>"
            "<p class=why>Each report is the report server's own, run with the values you choose here and shown as a PDF "
            "on this page, or handed over as an Excel file. Every run is logged.</p></div>"
            + ("".join(groups) or empty))
    return Response(body=t.page("Procurement · Reports", body, user=ctx.user, active=AREA))


def _report_or_404(ctx, report_id):
    from .. import HttpError
    r = mms_reports.get(ctx.conn, report_id) if mms_reports.ready(ctx.conn) else None
    if r is None or not r["present"]:
        raise HttpError("404 Not Found", "No such report.")
    _gate(ctx, r["area"])
    return r


def _param_control(p: ssrs.Param, chosen) -> str:
    """One parameter as the form shows it: the server's own list as a
    dropdown (several at once when the report takes several), a date box,
    a number, yes/no, or text; and a box to leave a nullable one empty."""
    key = t.esc("p." + p.name)
    label = t.esc(p.prompt) + ("" if p.required else " <span class=muted>(optional)</span>")
    if chosen is None:
        cur: list = []
    else:
        cur = [str(x) for x in (chosen if isinstance(chosen, list) else [chosen])]
    if p.valid_values or p.query_based or p.multi:
        # a list, even an empty one: a child dropdown waits for its parent's value before the server lists it
        opts = "".join(f"<option value='{t.esc(v)}'{' selected' if v in cur else ''}>{t.esc(l)}</option>" for l, v in p.valid_values)
        if p.multi:
            n = min(max(len(p.valid_values), 3), 8)
            ctl = (f"<select name='{key}' multiple size={n} data-param='{key}'{' data-cascade' if p.dependencies else ''}>{opts}</select>"
                   f"<div class=muted>Hold Ctrl to pick several.</div>")
        else:
            ctl = (f"<select name='{key}' data-param='{key}'{' data-cascade' if p.dependencies else ''}>"
                   + ("<option value=''>Choose…</option>" if not cur and not p.required else ("<option value=''>(none)</option>" if not p.required else ""))
                   + opts + "</select>")
    elif p.type == "DateTime":
        ctl = f"<input type=date name='{key}' value='{t.esc(cur[0][:10] if cur else '')}'{' required' if p.required else ''}>"
    elif p.type in ("Integer", "Float"):
        ctl = f"<input type=number step={'1' if p.type == 'Integer' else 'any'} name='{key}' value='{t.esc(cur[0] if cur else '')}'{' required' if p.required else ''}>"
    elif p.type == "Boolean":
        ctl = (f"<select name='{key}'><option value='true'{' selected' if cur and cur[0].lower() == 'true' else ''}>Yes</option>"
               f"<option value='false'{' selected' if cur and cur[0].lower() == 'false' else ''}>No</option></select>")
    else:
        ctl = f"<input name='{key}' value='{t.esc(cur[0] if cur else '')}' maxlength=400{' required' if p.required else ''}>"
    if p.state == "HasOutstandingDependencies":
        ctl += "<div class=muted>Choose the fields above first, then <i>Refresh choices</i>.</div>"
    elif p.state == "DynamicValuesUnavailable":
        ctl += "<div class=muted>The report server could not list the choices for this one.</div>"
    null = (f"<label class=muted style='font-weight:400'><input type=checkbox name='{key}.null' value=1{' checked' if chosen is None and p.nullable and chosen is not False else ''}> leave empty</label>"
            if p.nullable else "")
    return f"<div><label>{label}</label>{ctl}{null}</div>"


def report_page(ctx, report_id):
    from .. import Response
    r = _report_or_404(ctx, report_id)
    q = ctx.request.query
    rid = r["report_id"]
    err, params = "", []
    try:
        client = _ssrs()
        base = client.parameters(r["path"])
        chosen, _ = mms_reports.values_from(base, q.get, ctx.request.query_list, require=False)
        if not chosen and not q.get("refresh"):
            chosen = mms_reports.last_values(ctx.conn, rid, ctx.user.id) or mms_reports.defaults_of(base)
        params = client.parameters(r["path"], chosen) if chosen else base
        mms_reports.remember_params(ctx.conn, rid, params)
        ctx.conn.commit()
    except (ssrs.Refused, ssrs.ServerError) as exc:
        err = str(exc)
        chosen = {}
    want_run = q.get("run") == "1" and not err
    values, missing = (mms_reports.values_from(params, q.get, ctx.request.query_list, require=True) if want_run else ({}, []))
    asked = [p for p in params if p.prompt_user]
    controls = "".join(_param_control(p, chosen.get(p.name, None if p.name in chosen else "")) for p in asked)
    form = (f"<form method=get action='/procurement/report/{rid}' class=fields data-report{' aria-describedby=flash-err' if (err or q.get('err')) else ''}>"
            + (f"<div class=grid2>{controls}</div>" if asked else "<p class=muted>This report asks for nothing; run it as it is.</p>")
            + "<div class='row' style='margin-top:12px;gap:8px;flex-wrap:wrap'>"
            f"<div style='flex:0 0 auto'><button type=submit name=run value=1>{t.icon('reports')} Run and show the PDF</button></div>"
            + ("<div style='flex:0 0 auto'><button class=ghost type=submit name=refresh value=1>Refresh choices</button></div>"
               if any(p.dependencies for p in asked) else "")
            + "</div></form>")
    viewer = ""
    if want_run and missing:
        err = "Fill in: " + ", ".join(missing) + "."
    elif want_run:
        keep = [(k, v) for k, v in urllib.parse.parse_qsl(ctx.request.query_string) if k.startswith("p.")]
        pdf = f"/procurement/report/{rid}/render?" + urllib.parse.urlencode(keep + [("format", "PDF")])
        xls = f"/procurement/report/{rid}/render?" + urllib.parse.urlencode(keep + [("format", "EXCELOPENXML")])
        viewer = (f"<div class=card><div class='row' style='justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px'>"
                  f"<h3 style='margin:0'>{t.icon('reports')}{t.esc(r['title'])}</h3><div class=row style='gap:8px'>"
                  f"<a class='btn ghost' href='{pdf}' target=_blank rel=noopener>{t.icon('arrow')} Open in a new tab</a>"
                  f"<a class='btn' href='{xls}'>{t.icon('arrow')} Download Excel</a></div></div>"
                  f"<iframe class=rptframe src='{pdf}' title='{t.esc(r['title'])} as PDF'></iframe>"
                  "<p class=muted>If the PDF does not show here, your browser blocks embedded PDFs: use <i>Open in a new tab</i>.</p></div>")
    runs = mms_reports.recent_runs(ctx.conn, rid)
    runs_html = ("<div class=card><h3>" + t.icon("clock") + "Recent runs</h3><ul class=plain>" + "".join(
        f"<li>{t.esc(x['ran_at'])} · {t.esc(x['member'])} · {'Excel' if x['format'] == 'EXCELOPENXML' else 'PDF'} · "
        + (f"<span class=muted>{x['millis']} ms</span>" if x["outcome"] == "OK" else f"<span class='chip sla-bad'>failed</span> <span class=muted>{t.esc(x['message'] or '')}</span>")
        + "</li>" for x in runs) + "</ul></div>") if runs else ""
    body = (_banners(q) + (f"<div class='banner err' id=flash-err role=alert>{t.esc(err)}</div>" if err and not q.get("err")
                           else (f"<div class='banner err' role=alert>{t.esc(err)}</div>" if err else ""))
            + f"<a class=backbtn data-back href='/procurement?tab=reports' title='Back to reports'>{t.icon('left')}<span class=lbl>Back to reports</span></a>"
            f"<h1>{t.esc(r['title'])}</h1><p class=sub>{t.esc(mms_reports.AREA_WORDS[r['area']])}"
            + (f" · {t.esc(r['description'])}" if r["description"] else "")
            + " · from the report server, run with the values below</p>"
            + viewer + f"<div class=card><h3>{t.icon('edit')}" + ("Run it again with other values" if viewer else "Values") + f"</h3>{form}</div>"
            + runs_html
            + "<script>(function(){var f=document.querySelector('form[data-report]');if(!f)return;f.querySelectorAll('[data-cascade]').forEach(function(){});"
              "f.querySelectorAll('select[data-param]').forEach(function(s){s.addEventListener('change',function(){"
              "if(f.querySelector('[data-cascade]')){var b=document.createElement('input');b.type='hidden';b.name='refresh';b.value='1';f.appendChild(b);f.submit()}})})})()</script>")
    return Response(body=t.page(r["title"], body, user=ctx.user, active=AREA))


def report_render(ctx, report_id):
    from .. import Response, redirect
    r = _report_or_404(ctx, report_id)
    q = ctx.request.query
    fmt = q.get("format", "PDF")
    if fmt not in ssrs.FORMATS:
        fmt = "PDF"
    rid = r["report_id"]
    try:
        client = _ssrs()
        params = client.parameters(r["path"], mms_reports.values_from(client.parameters(r["path"]), q.get, ctx.request.query_list, require=False)[0])
        values, missing = mms_reports.values_from(params, q.get, ctx.request.query_list, require=True)
        if missing:
            raise ssrs.Refused("Fill in: " + ", ".join(missing) + ".")
        data, ctype, ext = client.render(r["path"], values, fmt)
    except (ssrs.Refused, ssrs.ServerError) as exc:
        mms_reports.log_run(ctx.conn, rid, member=ctx.user.id, at=ctx.now, fmt=fmt, values=q, ok=False, message=str(exc))
        ctx.conn.commit()
        keep = [(k, v) for k, v in urllib.parse.parse_qsl(ctx.request.query_string) if k.startswith("p.")]
        return redirect(f"/procurement/report/{rid}?" + urllib.parse.urlencode(keep + [("err", f"Not run: {exc}")]))
    mms_reports.log_run(ctx.conn, rid, member=ctx.user.id, at=ctx.now, fmt=fmt, values=values, ok=True,
                        size=len(data), millis=getattr(client, "last_millis", None))
    ctx.conn.commit()
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", r["title"]).strip("-") or "report"
    name = f"{stem}-{ctx.now.strftime('%Y%m%d-%H%M')}.{ext}"
    disposition = ("inline" if fmt == "PDF" else "attachment") + f"; filename=\"{name}\""
    return Response(body=data, content_type=ctype, headers=[("Content-Disposition", disposition), ("Cache-Control", "no-store")])


# ------------------------------------------------- drugs and warehouses (083)

def _drugs(ctx):
    """The items BizBox marks as medicines, with the controlled-drug flag:
    the one list a hospital asks for first (SQL01, 13 Oct 2026). Read-only;
    a medicine's own fields are BizBox's."""
    from .. import Response
    q = ctx.request.query
    search = q.get("q", "")
    flag = q.get("controlled", "")
    controlled = True if flag == "1" else False if flag == "0" else None
    page_no = int(q["page"]) if q.get("page", "").isdigit() and int(q["page"]) > 0 else 1
    if not db.table_exists(ctx.conn, "ext_medicine"):
        body = _head(ctx, "medicine", q) + "<div class=card><p class=muted>The desk cannot list medicines until schema 083 is applied on the host.</p></div>"
        return Response(body=t.page("Procurement · Drugs", body, user=ctx.user, active=AREA))
    rows, total = bizbox.medicines(ctx.conn, q=search, controlled=controlled, limit=bizbox.PAGE, offset=(page_no - 1) * bizbox.PAGE)
    labels = bizbox.labels_for(ctx.conn, "product")
    n_ctrl = ctx.conn.execute("SELECT COUNT(*) FROM ext_medicine WHERE source_id = ? AND present = 1 AND COALESCE(controlled, 0) = 1", (bizbox.SOURCE,)).fetchone()[0]
    keep = {k: v for k, v in {"tab": "medicine", "q": search, "controlled": flag}.items() if v}
    chips = "".join(f"<a class='{'on' if flag == f else ''}' href='/procurement?{urllib.parse.urlencode({k: v for k, v in (keep | {'controlled': f}).items() if v})}'>{w}</a>"
                    for f, w in (("", "All medicines"), ("1", f"Controlled · {n_ctrl}"), ("0", "Not controlled")))
    CONTROLLED = "<span class='chip sla-bad'>Controlled</span>"
    trs = "".join(
        f"<tr><td>{finance._ref_link('product', r['ext_ref'], AREA)}" + ("" if r["item_present"] in (1, None) else " <span class=pill>gone from BizBox</span>") + "</td>"
        f"<td>{t.esc(r['item_name'] or '')}</td><td>{t.esc(r['generic'] or '')}</td><td>{t.esc(r['dosage'] or '')}</td>"
        f"<td>{CONTROLLED if r['controlled'] else ''}</td>"
        f"<td>{t.esc(bizbox.word(labels, 'category', r['category']))}</td><td>{t.esc(r['admin_group'] or '')}</td>"
        f"<td class=muted>{t.esc(r['doh_ref'] or '')}" + (f"<div>{t.esc(r['mims_ref'])}</div>" if r["mims_ref"] else "") + "</td></tr>" for r in rows)
    first, last = (page_no - 1) * bizbox.PAGE + 1, min(page_no * bizbox.PAGE, total)
    pager = (f"<div class='row schedbar' style='justify-content:space-between'><div class=muted>Showing {first}–{last} of {total}</div><div>"
             + (f"<a class='ghost small' href='/procurement?{urllib.parse.urlencode(keep | {'page': page_no - 1})}'>‹ Previous</a> " if page_no > 1 else "")
             + (f"<a class='ghost small' href='/procurement?{urllib.parse.urlencode(keep | {'page': page_no + 1})}'>Next ›</a>" if last < total else "")
             + "</div></div>") if total > bizbox.PAGE else f"<div class=muted style='margin-top:8px'>{total} medicine(s).</div>"
    body = (_head(ctx, "medicine", q) + "<div class=card><form method=get action='/procurement' class='row schedbar'>"
            "<input type=hidden name=tab value=medicine>" + (f"<input type=hidden name=controlled value='{t.esc(flag)}'>" if flag else "")
            + f"<div style='flex:1 1 260px'><input name=q value='{t.esc(search)}' placeholder='Search by item, name, generic, dosage, DOH or MIMS'></div>"
            "<div style='flex:0 0 auto'><button class=ghost type=submit>Search</button></div></form>"
            f"<div class=stabs style='margin:10px 0 0'>{chips}</div>"
            "<p class=why>Every item BizBox marks as a medicine, with its generic name, dosage and whether it is a controlled drug. "
            "Read from BizBox; the medicine's own facts are changed there.</p>"
            "<div class=tablewrap><table class='compact pgrid'><thead><tr><th>Item</th><th>Name</th><th>Generic</th><th>Dosage</th><th></th>"
            "<th>Category</th><th>Administration</th><th>DOH · MIMS</th></tr></thead><tbody>"
            + (trs or "<tr><td colspan=8 class=muted>No medicine matches, or BizBox has not been read for medicines yet.</td></tr>")
            + "</tbody></table></div>" + pager + "</div>")
    return Response(body=t.page("Procurement · Drugs", body, user=ctx.user, active=AREA))


def _warehouses(ctx):
    """The 73 warehouses in their 6 groups (SQL01, 13 Oct 2026), read hourly.
    Read-only: a warehouse is BizBox's."""
    from .. import Response
    q = ctx.request.query
    search = q.get("q", "")
    if not db.table_exists(ctx.conn, "ext_warehouse"):
        body = _head(ctx, "warehouse", q) + "<div class=card><p class=muted>The desk cannot list warehouses until schema 083 is applied on the host.</p></div>"
        return Response(body=t.page("Procurement · Warehouses", body, user=ctx.user, active=AREA))
    rows = bizbox.warehouses(ctx.conn, q=search)
    held = {s["warehouse_ref"]: s for s in bizbox.stock_by_warehouse(ctx.conn)} if db.table_exists(ctx.conn, "ext_stock") else {}
    groups: dict = {}
    for r in rows:
        groups.setdefault(r["group_name"] or "No group", []).append(r)

    def holding(w):
        s = held.get(w["ext_ref"])
        if not s:
            return ""
        return (f" <a class='ghost small' href='/procurement?tab=stock&warehouse={urllib.parse.quote(w['ext_ref'])}'>"
                f"{s['items']} item{'s' if s['items'] != 1 else ''} in stock · {t.esc(finance._money(s['value']))}</a>")
    cards = "".join(
        f"<div class=card><h3>{t.icon('layers')}{t.esc(g)} · {len(ws)}</h3><ul class='plain rptlist'>"
        + "".join(f"<li><b>{t.esc(w['name'])}</b> <span class=muted>· {t.esc(w['ext_ref'])}</span>"
                  + ("" if w["active"] in (1, None) else " <span class=pill>inactive</span>") + holding(w) + "</li>" for w in ws)
        + "</ul></div>" for g, ws in groups.items())
    body = (_head(ctx, "warehouse", q) + "<div class=card><form method=get action='/procurement' class='row schedbar'>"
            "<input type=hidden name=tab value=warehouse>"
            f"<div style='flex:1 1 260px'><input name=q value='{t.esc(search)}' placeholder='Search warehouses'></div>"
            "<div style='flex:0 0 auto'><button class=ghost type=submit>Search</button></div></form>"
            "<p class=why>BizBox's warehouses, by group. A warehouse that holds stock says how much; click it for the lines. "
            "Perpetual inventory on the Reports tab has the same with BizBox's own valuation.</p></div>"
            + (cards or "<div class=card><p class=muted>No warehouse matches, or BizBox has not been read for warehouses yet.</p></div>"))
    return Response(body=t.page("Procurement · Warehouses", body, user=ctx.user, active=AREA))


# ------------------------------------------------ stock and movements (084)

def _qty(v) -> str:
    return f"{float(v):g}" if v not in (None, "", 0) else ""


def _bal(v) -> str:
    return f"{float(v):g}" if v is not None else ""


def _delta(r) -> str:
    if r["qty_in"]:
        return "+" + _qty(r["qty_in"])
    return ("−" + _qty(r["qty_out"])) if r["qty_out"] else ""


def _pager(keep: dict, page_no: int, total: int, word: str) -> str:
    first, last = (page_no - 1) * bizbox.PAGE + 1, min(page_no * bizbox.PAGE, total)
    if total <= bizbox.PAGE:
        return f"<div class=muted style='margin-top:8px'>{total} {word}.</div>"
    return (f"<div class='row schedbar' style='justify-content:space-between'><div class=muted>Showing {first}–{last} of {total}</div><div>"
            + (f"<a class='ghost small' href='/procurement?{urllib.parse.urlencode(keep | {'page': page_no - 1})}'>‹ Previous</a> " if page_no > 1 else "")
            + (f"<a class='ghost small' href='/procurement?{urllib.parse.urlencode(keep | {'page': page_no + 1})}'>Next ›</a>" if last < total else "")
            + "</div></div>")


def _warehouse_pick(ctx, chosen: str, *, name: str = "warehouse") -> str:
    if not db.table_exists(ctx.conn, "ext_warehouse"):
        return f"<input name={name} value='{t.esc(chosen)}' placeholder='Warehouse code' aria-label=Warehouse>"
    opts = "".join(f"<option value='{t.esc(w['ext_ref'])}'{' selected' if w['ext_ref'] == chosen else ''}>{t.esc(w['name'])}"
                   + (f" ({t.esc(w['group_name'])})" if w["group_name"] else "") + "</option>" for w in bizbox.warehouses(ctx.conn, include_inactive=False))
    return f"<select name={name} aria-label=Warehouse><option value=''>Any warehouse</option>{opts}</select>"


def _not_mapped(ctx, on: str, what: str) -> str:
    return (_head(ctx, on, ctx.request.query)
            + f"<div class=card><p class=muted>{what} is not read from BizBox yet: SQL01 builds the view and names it in the desk's map, "
              "and the hourly read fills this tab. The Reports tab has it meanwhile.</p></div>")


def _stock(ctx):
    """Stock on hand, by warehouse and item: the 4,358 lines BizBox holds a
    quantity for (SQL01, 13 Oct 2026), read hourly. Read-only."""
    from .. import Response
    q = ctx.request.query
    warehouse, search = q.get("warehouse", ""), q.get("q", "")
    page_no = int(q["page"]) if q.get("page", "").isdigit() and int(q["page"]) > 0 else 1
    if not db.table_exists(ctx.conn, "ext_stock"):
        return Response(body=t.page("Procurement · Stock on hand", _not_mapped(ctx, "stock", "Stock on hand"), user=ctx.user, active=AREA))
    summary = bizbox.stock_summary(ctx.conn)
    rows, total = bizbox.stock(ctx.conn, warehouse=warehouse, q=search, limit=bizbox.PAGE, offset=(page_no - 1) * bizbox.PAGE)
    labels = bizbox.labels_for(ctx.conn, "product")
    keep = {k: v for k, v in {"tab": "stock", "warehouse": warehouse, "q": search}.items() if v}
    trs = "".join(
        f"<tr><td>{t.esc(r['warehouse_name'] or r['warehouse_ref'])}" + (f" <span class=muted>· {t.esc(r['group_name'])}</span>" if r["group_name"] else "") + "</td>"
        f"<td>{finance._ref_link('product', r['item_ref'], AREA)}" + ("" if r["item_present"] in (1, None) else " <span class=pill>gone from BizBox</span>") + "</td>"
        f"<td>{t.esc(r['item_name'] or '')}</td><td>{t.esc(bizbox.word(labels, 'category', r['category']))}</td>"
        f"<td class=num>{float(r['quantity'] or 0):g} {t.esc(r['unit'] or '')}</td>"
        f"<td class=num>{t.esc(finance._money(r['unit_cost']))}</td><td class=num>{t.esc(finance._money(r['value']))}</td>"
        f"<td class=muted>{t.esc(r['as_of'] or '')}</td></tr>" for r in rows)
    tiles = ("<div class='tiles six'>"
             f"<div class=tile><div class=n>{summary['lines']:,}</div><div class=l>stock lines</div></div>"
             f"<div class=tile><div class=n>{summary['items']:,}</div><div class=l>items in stock</div></div>"
             f"<div class=tile><div class=n>{summary['warehouses']:,}</div><div class=l>warehouses holding stock</div></div>"
             f"<div class=tile><div class=n>{t.esc(finance._money(summary['value']))}</div><div class=l>value at unit cost</div></div>"
             f"<div class=tile><div class=n>{t.esc((summary['as_of'] or '—')[:10])}</div><div class=l>BizBox's as-of</div></div>"
             f"<div class=tile><div class=n>{t.esc((summary['synced_at'] or '—')[:16])}</div><div class=l>read by the desk</div></div></div>")
    body = (_head(ctx, "stock", q) + tiles + "<div class=card><form method=get action='/procurement' class='row schedbar'>"
            "<input type=hidden name=tab value=stock>"
            f"<div style='flex:0 0 260px'>{_warehouse_pick(ctx, warehouse)}</div>"
            f"<div style='flex:1 1 240px'><input name=q value='{t.esc(search)}' placeholder='Search by item code or name'></div>"
            "<div style='flex:0 0 auto'><button class=ghost type=submit>Show</button></div></form>"
            "<p class=why>What each warehouse holds, as BizBox's stock ledger has it at the last hourly read. The value is quantity at the "
            "item's unit cost; BizBox's own valuation is in Perpetual inventory on the Reports tab. A warehouse or item that is not here "
            "holds nothing.</p>"
            "<div class=tablewrap><table class='compact pgrid'><thead><tr><th>Warehouse</th><th>Item</th><th>Name</th><th>Category</th>"
            "<th class=num>On hand</th><th class=num>Unit cost</th><th class=num>Value</th><th>As of</th></tr></thead><tbody>"
            + (trs or "<tr><td colspan=8 class=muted>Nothing in stock matches, or BizBox has not been read for stock yet.</td></tr>")
            + "</tbody></table></div>" + _pager(keep, page_no, total, "line(s)") + "</div>")
    return Response(body=t.page("Procurement · Stock on hand", body, user=ctx.user, active=AREA))


def _window(q) -> int:
    days = q.get("days", "")
    return int(days) if days.isdigit() and int(days) in dict(WINDOWS) else 30


def _movements(ctx):
    """The item ledger inside a window of days or months: received, issued,
    transferred, adjusted, counted. Read hourly from a view SQL01 keeps to
    a window; read-only."""
    from .. import Response
    q = ctx.request.query
    item, warehouse, kind = q.get("item", ""), q.get("warehouse", ""), q.get("kind", "")
    days = _window(q)
    page_no = int(q["page"]) if q.get("page", "").isdigit() and int(q["page"]) > 0 else 1
    if not db.table_exists(ctx.conn, "ext_movement"):
        return Response(body=t.page("Procurement · Movements", _not_mapped(ctx, "movement", "The item ledger"), user=ctx.user, active=AREA))
    rows, total = bizbox.movements(ctx.conn, item=item, warehouse=warehouse, days=days, kind=kind, now=ctx.now,
                                   limit=bizbox.PAGE, offset=(page_no - 1) * bizbox.PAGE)
    kinds = bizbox.movement_kinds(ctx.conn, days=days, now=ctx.now)
    oldest, newest = bizbox.movement_window(ctx.conn)
    keep = {k: v for k, v in {"tab": "movement", "item": item, "warehouse": warehouse, "kind": kind, "days": str(days)}.items() if v}
    chips = "".join(f"<a class='{'on' if kind.upper() == k else ''}' href='/procurement?{urllib.parse.urlencode({kk: vv for kk, vv in (keep | {'kind': k}).items() if vv})}'>{t.esc(w)} · {n}</a>"
                    for k, w, n in kinds)
    allchip = f"<a class='{'on' if not kind else ''}' href='/procurement?{urllib.parse.urlencode({kk: vv for kk, vv in keep.items() if kk != 'kind'})}'>All · {sum(n for _, _, n in kinds)}</a>"
    trs = "".join(
        f"<tr><td>{t.esc(r['moved_on'] or '')}</td><td>{finance._ref_link('product', r['item_ref'], AREA)}</td><td>{t.esc(r['item_name'] or '')}</td>"
        f"<td>{t.esc(r['warehouse_name'] or r['warehouse_ref'] or '')}</td><td>{t.esc(bizbox.move_word(r['kind']))}</td>"
        f"<td>{t.esc(r['doc_ref'] or '')}</td>"
        f"<td class=num>{_qty(r['qty_in'])}</td><td class=num>{_qty(r['qty_out'])}</td>"
        f"<td class=num>{_bal(r['balance'])}</td>"
        f"<td class=muted>{t.esc(r['remarks'] or '')}</td></tr>" for r in rows)
    wopts = "".join(f"<option value={d}{' selected' if d == days else ''}>{w}</option>" for d, w in WINDOWS)
    body = (_head(ctx, "movement", q) + "<div class=card><form method=get action='/procurement' class='row schedbar'>"
            "<input type=hidden name=tab value=movement>"
            f"<div style='flex:0 0 170px'><select name=days aria-label=Window>{wopts}</select></div>"
            f"<div style='flex:0 0 240px'>{_warehouse_pick(ctx, warehouse)}</div>"
            f"<div style='flex:1 1 200px'><input name=item value='{t.esc(item)}' placeholder='Item code' aria-label='Item code'></div>"
            + (f"<input type=hidden name=kind value='{t.esc(kind)}'>" if kind else "")
            + "<div style='flex:0 0 auto'><button class=ghost type=submit>Show</button></div></form>"
            f"<div class=stabs style='margin:10px 0 0'>{allchip}{chips}</div>"
            "<p class=why>Every movement of stock BizBox recorded inside the window: what came in, what went out, and the balance after, "
            "with the document that moved it. The desk holds "
            + (f"{t.esc(oldest)} to {t.esc(newest)}" if oldest else "nothing yet") + "; older movements are in the MMS reports.</p>"
            "<div class=tablewrap><table class='compact pgrid'><thead><tr><th>Date</th><th>Item</th><th>Name</th><th>Warehouse</th>"
            "<th>Movement</th><th>Document</th><th class=num>In</th><th class=num>Out</th><th class=num>Balance</th><th>Remarks</th></tr></thead><tbody>"
            + (trs or "<tr><td colspan=10 class=muted>No movement matches inside that window.</td></tr>")
            + "</tbody></table></div>" + _pager(keep, page_no, total, "movement(s)") + "</div>")
    return Response(body=t.page("Procurement · Movements", body, user=ctx.user, active=AREA))


def stock_card(ctx, kind: str, ext_ref: str) -> str:
    """On an item's page: what each warehouse holds of it, and a way to raise
    a ticket about it on the desk (the PSA side of the MMS)."""
    if kind != "product" or not _may(ctx, "product") or not db.table_exists(ctx.conn, "ext_stock"):
        return ""
    rows = bizbox.stock_of_item(ctx.conn, ext_ref)
    rec = bizbox.get(ctx.conn, "product", ext_ref)
    name = (rec["name"] if rec else "") or ext_ref
    ask = urllib.parse.urlencode({"summary": f"{name} ({ext_ref}): ", "bizbox_kind": "product", "bizbox_ref": ext_ref})
    total = sum(float(r["quantity"] or 0) for r in rows)
    value = sum(float(r["value"] or 0) for r in rows)
    trs = "".join(f"<tr><td>{t.esc(r['warehouse_name'] or r['warehouse_ref'])}" + (f" <span class=muted>· {t.esc(r['group_name'])}</span>" if r["group_name"] else "") + "</td>"
                  f"<td class=num>{float(r['quantity'] or 0):g} {t.esc(r['unit'] or '')}</td><td class=num>{t.esc(finance._money(r['value']))}</td>"
                  f"<td class=muted>{t.esc(r['as_of'] or '')}</td></tr>" for r in rows)
    return ("<div class=card><h3>" + t.icon("layers") + "Stock on hand</h3>"
            + (f"<div class=tablewrap><table class=compact><thead><tr><th>Warehouse</th><th class=num>On hand</th><th class=num>Value</th><th>As of</th></tr></thead>"
               f"<tbody>{trs}<tr><td><b>All warehouses</b></td><td class=num><b>{total:g}</b></td><td class=num><b>{t.esc(finance._money(value))}</b></td><td></td></tr></tbody></table></div>"
               if rows else "<div class=muted>No warehouse holds this item, as of the last read.</div>")
            + f"<div style='margin-top:10px'><a class='btn ghost' href='/ticket/new?{ask}'>{t.icon('plus')} Raise a ticket about this item</a> "
              f"<a class='ghost small' href='/procurement?tab=movement&item={urllib.parse.quote(ext_ref)}&days=90'>Movements, last 90 days</a></div></div>")


def movements_card(ctx, kind: str, ext_ref: str) -> str:
    """On an item's page: its last movements."""
    if kind != "product" or not _may(ctx, "product") or not db.table_exists(ctx.conn, "ext_movement"):
        return ""
    rows, total = bizbox.movements(ctx.conn, item=ext_ref, days=30, now=ctx.now, limit=10)
    trs = "".join(f"<tr><td>{t.esc(r['moved_on'] or '')}</td><td>{t.esc(r['warehouse_name'] or r['warehouse_ref'] or '')}</td>"
                  f"<td>{t.esc(bizbox.move_word(r['kind']))}</td><td>{t.esc(r['doc_ref'] or '')}</td>"
                  f"<td class=num>{_qty(r['qty_in'])}</td><td class=num>{_qty(r['qty_out'])}</td>"
                  f"<td class=num>{_bal(r['balance'])}</td></tr>" for r in rows)
    return ("<div class=card><h3>" + t.icon("rows") + f"Movements, last 30 days · {total}</h3>"
            + (f"<div class=tablewrap><table class=compact><thead><tr><th>Date</th><th>Warehouse</th><th>Movement</th><th>Document</th>"
               f"<th class=num>In</th><th class=num>Out</th><th class=num>Balance</th></tr></thead><tbody>{trs}</tbody></table></div>"
               if rows else "<div class=muted>No movement in the last 30 days.</div>") + "</div>")


# ----------------------------------------------------------------- the home

def _home(ctx):
    """Procurement opens here: what BizBox's MMS holds, what moved this week,
    what waits for a person, and where to go. Every tile and card is the
    area the role may see; nothing is read live."""
    from .. import Response
    from ... import mms_reports
    q = ctx.request.query
    seen = _seen(ctx)
    conn = ctx.conn
    tiles = []

    def tile(n, label, href):
        tiles.append(f"<a class=tile href='{href}'><div class=n>{n}</div><div class=l>{label}</div></a>")
    pending_batches = conn.execute("SELECT COUNT(*) FROM ext_batch WHERE source_id = ? AND status = 'PENDING'", (bizbox.SOURCE,)).fetchone()[0]
    approved = conn.execute("SELECT COUNT(*) FROM ext_batch WHERE source_id = ? AND status = 'APPROVED'", (bizbox.SOURCE,)).fetchone()[0]
    month = ctx.now.strftime("%Y-%m")
    if "purchase_order" in seen:
        n = conn.execute("SELECT COUNT(*) FROM ext_purchase_order WHERE source_id = ? AND present = 1", (bizbox.SOURCE,)).fetchone()[0]
        this = conn.execute("SELECT COUNT(*) FROM ext_purchase_order WHERE source_id = ? AND present = 1 AND ordered_on LIKE ?", (bizbox.SOURCE, month + "%")).fetchone()[0]
        tile(f"{n:,}", f"purchase orders · {this} this month", "/procurement?tab=purchase_order")
    if "invoice" in seen:
        n = conn.execute("SELECT COUNT(*) FROM ext_invoice WHERE source_id = ? AND present = 1", (bizbox.SOURCE,)).fetchone()[0]
        this = conn.execute("SELECT COUNT(*) FROM ext_invoice WHERE source_id = ? AND present = 1 AND invoiced_on LIKE ?", (bizbox.SOURCE, month + "%")).fetchone()[0]
        tile(f"{n:,}", f"receiving reports · {this} this month", "/procurement?tab=invoice")
    stock_ok = "product" in seen and db.table_exists(conn, "ext_stock")
    moves_ok = "product" in seen and db.table_exists(conn, "ext_movement")
    if "product" in seen:
        n = conn.execute("SELECT COUNT(*) FROM ext_product WHERE source_id = ? AND present = 1", (bizbox.SOURCE,)).fetchone()[0]
        tile(f"{n:,}", "items", "/procurement?tab=product")
    if stock_ok:
        s = bizbox.stock_summary(conn)
        tile(t.esc(finance._money(s["value"])), f"stock on hand at unit cost · {s['lines']:,} lines", "/procurement?tab=stock")
    if moves_ok:
        week = bizbox.movements(conn, days=7, now=ctx.now, limit=1)[1]
        tile(f"{week:,}", "movements in the last 7 days", "/procurement?tab=movement&days=7")
    if seen:
        tile(f"{pending_batches:,}", "changes waiting for approval" + (f" · {approved} approved, to send" if approved else ""), "/procurement?tab=changes")
    cards = []
    if stock_ok:
        by = bizbox.stock_by_warehouse(conn)[:8]
        top = max((float(r["value"] or 0) for r in by), default=0) or 1
        cards.append("<div class=card><h3>" + t.icon("layers") + "Stock by warehouse</h3>"
                     + ("<div class=tablewrap><table class=compact><tbody>" + "".join(
                         f"<tr><td><a href='/procurement?tab=stock&warehouse={urllib.parse.quote(r['warehouse_ref'])}'>{t.esc(r['warehouse_name'] or r['warehouse_ref'])}</a>"
                         + (f" <span class=muted>· {t.esc(r['group_name'])}</span>" if r["group_name"] else "") + "</td>"
                         f"<td style='width:34%'><div class=bar><i style='width:{int(100 * float(r['value'] or 0) / top)}%'></i></div></td>"
                         f"<td class=num>{r['items']} item{'s' if r['items'] != 1 else ''}</td><td class=num>{t.esc(finance._money(r['value']))}</td></tr>" for r in by)
                         + "</tbody></table></div>" if by else "<div class=muted>No warehouse holds stock, as of the last read.</div>")
                     + "<p class=why><a href='/procurement?tab=warehouse'>All warehouses</a> · <a href='/procurement?tab=stock'>Every stock line</a></p></div>")
    if moves_ok:
        kinds = bizbox.movement_kinds(conn, days=7, now=ctx.now)
        recent, _ = bizbox.movements(conn, days=7, now=ctx.now, limit=8)
        cards.append("<div class=card><h3>" + t.icon("rows") + "Moved in the last 7 days</h3>"
                     + ("<div class=stabs style='margin:0 0 8px'>" + "".join(
                         f"<a href='/procurement?tab=movement&days=7&kind={urllib.parse.quote(k)}'>{t.esc(w)} · {n}</a>" for k, w, n in kinds) + "</div>" if kinds else "")
                     + ("<div class=tablewrap><table class=compact><tbody>" + "".join(
                         f"<tr><td>{t.esc(r['moved_on'] or '')}</td><td>{finance._ref_link('product', r['item_ref'], AREA)} {t.esc(r['item_name'] or '')}</td>"
                         f"<td>{t.esc(r['warehouse_name'] or r['warehouse_ref'] or '')}</td><td>{t.esc(bizbox.move_word(r['kind']))}</td>"
                         f"<td class=num>{_delta(r)}</td></tr>" for r in recent)
                         + "</tbody></table></div>" if recent else "<div class=muted>Nothing moved in the last 7 days, as of the last read.</div>")
                     + "<p class=why><a href='/procurement?tab=movement'>Every movement</a></p></div>")
    if seen:
        waiting = [b for b in bizbox.batches(conn, status="PENDING", limit=6) if b["kind"] in {bizbox.LINK_KIND[k] for k in seen}]
        cards.append("<div class=card><h3>" + t.icon("checks") + f"Waiting for approval · {pending_batches}</h3>"
                     + ("<ul class='plain rptlist'>" + "".join(
                         f"<li><a href='/procurement/batch/{b['batch_id']}'>#{b['batch_id']}</a> {t.esc(_batch_what(b))} · <span class=muted>{t.esc(b['requested_by'])}, {t.esc(b['requested_at'])}</span></li>"
                         for b in waiting) + "</ul>" if waiting else "<div class=muted>Nothing waits. BizBox has not changed from here.</div>")
                     + "<p class=why><a href='/procurement?tab=changes'>All changes</a></p></div>")
    if "purchase_order" in seen:
        labels = bizbox.labels_for(conn, "purchase_order")
        latest = conn.execute("SELECT * FROM ext_purchase_order WHERE source_id = ? AND present = 1 ORDER BY ordered_on DESC, ext_ref DESC LIMIT 6", (bizbox.SOURCE,)).fetchall()
        cards.append("<div class=card><h3>" + t.icon("cart") + "Latest purchase orders</h3>"
                     + ("<div class=tablewrap><table class=compact><tbody>" + "".join(
                         f"<tr><td>{finance._ref_link('purchase_order', r['ext_ref'], AREA)}</td><td>{t.esc(r['vendor'] or '')}</td><td>{t.esc(r['ordered_on'] or '')}</td>"
                         f"<td>{t.esc(bizbox.word(labels, 'status', r['status']))}</td><td class=num>{t.esc(finance._money(r['total'], r['currency']))}</td></tr>" for r in latest)
                         + "</tbody></table></div>" if latest else "<div class=muted>No purchase order read yet.</div>")
                     + ("<p class=why><a href='/procurement?tab=purchase_order'>All purchase orders</a>"
                        + (f" · <a href='/procurement/purchase_order/new'>{NEW_WORDS['purchase_order']}</a>" if _can_write(ctx, "purchase_order") else "") + "</p></div>"))
    if "invoice" in seen:
        labels = bizbox.labels_for(conn, "invoice")
        latest = conn.execute("SELECT * FROM ext_invoice WHERE source_id = ? AND present = 1 ORDER BY invoiced_on DESC, ext_ref DESC LIMIT 6", (bizbox.SOURCE,)).fetchall()
        cards.append("<div class=card><h3>" + t.icon("tag") + "Latest receiving</h3>"
                     + ("<div class=tablewrap><table class=compact><tbody>" + "".join(
                         f"<tr><td>{finance._ref_link('invoice', r['ext_ref'], AREA)}</td><td>{t.esc(r['party'] or '')}</td><td>{t.esc(r['invoiced_on'] or '')}</td>"
                         f"<td>{t.esc(bizbox.word(labels, 'status', r['status']))}</td><td class=num>{t.esc(finance._money(r['total'], r['currency']))}</td></tr>" for r in latest)
                         + "</tbody></table></div>" if latest else "<div class=muted>No receiving report read yet.</div>")
                     + "<p class=why><a href='/procurement?tab=invoice'>All receiving reports</a></p></div>")
    if seen and mms_reports.ready(conn):
        marks = ",".join("?" * len(seen))
        used = conn.execute(
            "SELECT r.report_id, r.title, r.name, COUNT(u.run_id) AS n FROM mms_report r LEFT JOIN mms_report_run u ON u.report_id = r.report_id"
            f" WHERE r.present = 1 AND r.shown = 1 AND r.area IN ({marks}) GROUP BY r.report_id, r.title, r.name ORDER BY n DESC, r.title LIMIT 6", seen).fetchall()
        cards.append("<div class=card><h3>" + t.icon("reports") + "Reports</h3>"
                     + ("<ul class='plain rptlist'>" + "".join(
                         f"<li><a href='/procurement/report/{r['report_id']}'>{t.esc(r['title'] or r['name'])}</a>"
                         + (f" <span class=muted>· run {r['n']} time{'s' if r['n'] != 1 else ''} from the desk</span>" if r["n"] else "") + "</li>" for r in used) + "</ul>"
                        if used else "<div class=muted>No report catalogued yet.</div>")
                     + "<p class=why><a href='/procurement?tab=reports'>All reports</a></p></div>")
    body = (_head(ctx, "home", q) + "<div class='tiles six'>" + "".join(tiles) + "</div>"
            + "<div class=home2>" + "".join(cards) + "</div>")
    return Response(body=t.page("Procurement", body, user=ctx.user, active=AREA))

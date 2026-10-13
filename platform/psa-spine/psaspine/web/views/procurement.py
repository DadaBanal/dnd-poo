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
approval and then for the push. Rights: the PROCUREMENT level in Security
roles, which falls back to the Finance level.
"""
from __future__ import annotations

import re
import urllib.parse

from ... import bizbox
from .. import templates as t
from . import common, finance

AREA = "procurement"
TABS = (("purchase_order", "Purchase orders"), ("invoice", "Receiving"), ("product", "Products"),
        ("vendor", "Vendors"), ("changes", "Changes"))
KINDS = ("purchase_order", "invoice", "product")
NEW_WORDS = {"purchase_order": "New purchase order", "product": "New item"}
# the column a vendor filter reads, per kind
VENDOR_COL = {"purchase_order": "vendor", "invoice": "party"}
# the column the first filter reads, per kind: an item has no status, so its
# filter is the category (the reference PSA's Products list filters by one)
FILTER_COL = {"purchase_order": "status", "invoice": "status", "product": "category"}
FILTER_WORD = {"status": "status", "category": "category"}


def _gate(ctx, need: str = "READ"):
    common.require_module(ctx, "PROCUREMENT", need)


def _can_write(ctx) -> bool:
    return common.allows(ctx, "PROCUREMENT", "WRITE")


def _banners(q) -> str:
    return ((f"<div class='banner ok'>{t.esc(q.get('msg', ''))}</div>" if q.get("msg") else "")
            + (f"<div class='banner err'>{t.esc(q.get('err', ''))}</div>" if q.get("err") else ""))


def _tabs(ctx, on: str) -> str:
    counts = {k: ctx.conn.execute(f"SELECT COUNT(*) FROM {bizbox.KINDS[k][0]} WHERE source_id = ? AND present = 1",
                                  (bizbox.SOURCE,)).fetchone()[0] for k in KINDS}
    counts["vendor"] = len(bizbox.vendors(ctx.conn))
    counts["changes"] = ctx.conn.execute("SELECT COUNT(*) FROM ext_batch WHERE source_id = ? AND status IN ('PENDING', 'APPROVED')",
                                         (bizbox.SOURCE,)).fetchone()[0]
    return ("<div class=stabs>" + "".join(
        f"<a class='{'on' if k == on else ''}' href='/procurement?tab={k}'>{v} · {counts[k]}</a>" for k, v in TABS) + "</div>")


READ_WORDS = {"purchase_order": "purchase orders", "po_line": "order lines", "product": "items",
              "invoice": "receiving reports", "agreement": "agreements"}


def _read_words(result: str) -> str:
    """The read's own summary ("purchase_order: 5 rows, 5 new, ...") in words:
    what BizBox holds, and what changed since the read before. No kind or
    table name reaches the screen (Dada, 13 Oct 2026)."""
    parts = []
    for m in re.finditer(r"(\w+): (\d+) rows, (\d+) new, (\d+) changed, (\d+) unchanged, (\d+) absent", result or ""):
        kind, rows, new, changed, _, gone = m.group(1), *map(int, m.groups()[1:])
        if not rows and not gone:
            continue
        bits = ", ".join(b for b in (f"{new} new" if new else "", f"{changed} changed" if changed else "",
                                     f"{gone} gone" if gone else "") if b)
        parts.append(f"{rows} {READ_WORDS.get(kind, kind.replace('_', ' '))}" + (f" ({bits})" if bits else ""))
    return (" · " + " · ".join(parts)) if parts else ""


def _head(ctx, on: str, q) -> str:
    st = bizbox.status(ctx.conn)
    sync = (f"Read from BizBox {t.esc(st['last_sync_at'])}{t.esc(_read_words(st['last_result']))}" if st and st["last_sync_at"]
            else "Not read from BizBox yet: the hourly read has not run.")
    return (_banners(q) + "<h1>Procurement</h1><p class=sub>Everything here is read from BizBox: purchase orders, "
            "receiving, items and vendors. To change something, tick rows and set one thing on all of them, or edit "
            "the cells in a row, say why, and send it for approval. A second person approves it on the Changes tab. "
            "Nothing in BizBox changes until it is approved and sent.</p>"
            f"<div class='banner ok'>{sync}</div>" + _tabs(ctx, on))


def index(ctx):
    from .. import Response
    _gate(ctx)
    q = ctx.request.query
    tab = q.get("tab", "purchase_order")
    if tab == "vendor":
        return _vendors(ctx)
    if tab == "changes":
        return _changes(ctx)
    if tab not in KINDS:
        tab = "purchase_order"
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


def _grid(ctx, kind) -> str:
    q = ctx.request.query
    search, status, vendor = q.get("q", ""), q.get("status", ""), q.get("vendor", "")
    absent = q.get("absent") == "1"
    page_no = int(q["page"]) if q.get("page", "").isdigit() and int(q["page"]) > 0 else 1
    rows, total = _rows(ctx, kind, search=search, status=status, vendor=vendor, absent=absent, page_no=page_no)
    # Finance's columns, in Procurement's words: the receiving report's
    # counterparty is the vendor here, never "party" (Dada, 13 Oct 2026).
    columns = [(f, "Vendor" if f == "party" else lab) for f, lab in finance._columns(ctx, kind)]
    can = _can_write(ctx)
    editable = bizbox.EDITABLE.get(kind, {}) if can else {}
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
            typ = "date" if editable[f] == "date" else "text"
            return (f"<td class='ecell{' num' if f == 'unit_cost' else ''}'><input form=grid type={typ} name='e:{t.esc(r['ext_ref'])}:{f}'"
                    f" value='{t.esc('' if v is None else str(v))}' data-was='{t.esc('' if v is None else str(v))}' aria-label='{t.esc(bizbox.FIELD_WORDS.get(f, f))} of {t.esc(r['ext_ref'])}'></td>")
        return finance._cell(r, f, AREA)
    trs = []
    for r in rows:
        waiting = ", ".join(sorted(bizbox.FIELD_WORDS.get(f, f) for f in pending.get(r["ext_ref"], ())))
        wait_cell = f"<span class='chip sla-warn'>{t.esc(waiting)}</span>" if waiting else ""
        trs.append(f"<tr><td><input type=checkbox form=bulk name=refs value='{t.esc(r['ext_ref'])}' aria-label='Tick {t.esc(r['ext_ref'])}'></td>"
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
    sopts = "".join(f"<option value='{t.esc(s)}'{' selected' if s == status else ''}>{t.esc(s)}</option>" for s in _statuses(ctx.conn, kind))
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
        fopts = "".join(f"<option value={f}>{t.esc(bizbox.FIELD_WORDS[f])}</option>" for f in editable)
        tools = (f"<form id=bulk method=post action='/procurement/{kind}/bulk' class='row schedbar bulkbar' style='margin-top:10px'>"
                 "<div style='flex:0 0 auto'><b><span data-ticked>0</span> ticked</b> · change</div>"
                 f"<div style='flex:0 0 170px'><select name=field aria-label='Field to change'>{fopts}</select></div>"
                 "<div style='flex:1 1 160px'><input name=new_value required maxlength=200 placeholder='to this new value'></div>"
                 "<div style='flex:1 1 200px'><input name=reason required maxlength=400 placeholder='Why? The approver sees this'></div>"
                 f"<div style='flex:0 0 auto'><button type=submit>{t.icon('check')} Send for approval</button></div></form>"
                 f"<form id=grid method=post action='/procurement/{kind}/edits' class='row schedbar' style='margin-top:6px'>"
                 "<div style='flex:0 0 auto'><b><span data-edited>0</span> cell(s) edited</b></div>"
                 "<div style='flex:1 1 260px'><input name=reason maxlength=400 placeholder='Why? Needed before sending edited cells'></div>"
                 f"<div style='flex:0 0 auto'><button class=ghost type=submit>{t.icon('check')} Send edited cells for approval</button></div></form>")
    script = ("<script>(function(){var tick=document.querySelector('[data-tickall]');var n=document.querySelector('[data-ticked]');"
              "var boxes=function(){return Array.prototype.slice.call(document.querySelectorAll(\"input[form=bulk][name=refs]\"))};"
              "function count(){if(n)n.textContent=boxes().filter(function(b){return b.checked}).length}"
              "if(tick)tick.addEventListener('change',function(){boxes().forEach(function(b){b.checked=tick.checked});count()});"
              "boxes().forEach(function(b){b.addEventListener('change',count)});"
              "var e=document.querySelector('[data-edited]');function edited(){var c=0;document.querySelectorAll('td.ecell input').forEach(function(i){"
              "if(i.value!==i.getAttribute('data-was')){c++;i.classList.add('edited')}else{i.classList.remove('edited')}});if(e)e.textContent=c}"
              "document.querySelectorAll('td.ecell input').forEach(function(i){i.addEventListener('input',edited)});edited();count()})()</script>")
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
    if not _can_write(ctx) or b["status"] not in ("PENDING", "APPROVED"):
        return ""
    out = ""
    if b["status"] == "PENDING" and (b["requested_by"] or "").lower() != (ctx.user.id or "").lower():
        out += (f"<form method=post action='/procurement/batch/{b['batch_id']}/approve' class=inline>"
                f"<button class=small type=submit>{t.icon('check')} Approve</button></form> ")
    elif b["status"] == "PENDING":
        out += "<span class=muted>yours: someone else approves</span> "
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
    if status == "OPEN":
        rows = [b for b in rows if b["status"] in ("PENDING", "APPROVED")]
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
    rows = bizbox.batch_changes(ctx.conn, b["batch_id"])
    b = dict(b) | {"n": len(rows)}
    kind = {v: k for k, v in bizbox.LINK_KIND.items()}[b["kind"]]
    extra = ""
    if b["change_kind"] == "ADD":
        p = bizbox.payload_of(b)
        rec, lines = p.get("record", {}), p.get("lines") or []
        facts = "".join(f"<dt>{t.esc(bizbox.FIELD_WORDS.get(f, f.replace('_', ' ').capitalize()))}</dt><dd>{t.esc(str(v))}</dd>" for f, v in rec.items())
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


def approve(ctx, batch_id):
    from .. import redirect
    _gate(ctx, "WRITE")
    try:
        bizbox.approve(ctx.conn, int(batch_id) if str(batch_id).isdigit() else -1, at=ctx.now, actor=ctx.user.id)
        ctx.conn.commit()
    except bizbox.Refused as exc:
        ctx.conn.rollback()
        return redirect("/procurement?" + urllib.parse.urlencode({"tab": "changes", "err": str(exc)}))
    return redirect("/procurement?" + urllib.parse.urlencode({"tab": "changes", "msg": f"Batch #{batch_id} approved. It will be sent to BizBox on the next run."}))


def cancel(ctx, batch_id):
    from .. import redirect
    _gate(ctx, "WRITE")
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
    _gate(ctx, "WRITE")
    if kind not in KINDS:
        return redirect("/procurement")
    f = ctx.request.form()
    try:
        out = bizbox.propose_many(ctx.conn, kind, ctx.request.form_list("refs"), f.get("field", ""), f.get("new_value", ""),
                                  reason=f.get("reason", ""), at=ctx.now, actor=ctx.user.id)
        ctx.conn.commit()
    except bizbox.Refused as exc:
        ctx.conn.rollback()
        return redirect(_back(kind, err=f"Not queued: {exc}"))
    return redirect(_back(kind, msg=f"Batch #{out['batch_id']} queued: {out['queued']} record(s)"
                                    + (f", {out['same']} already so" if out["same"] else "") + ". A second person approves it on the Changes tab."))


def edits(ctx, kind):
    from .. import redirect
    _gate(ctx, "WRITE")
    if kind not in KINDS:
        return redirect("/procurement")
    f = ctx.request.form()
    triples = []
    for key in f.keys():
        if not key.startswith("e:"):
            continue
        parts = key.split(":", 2)
        if len(parts) != 3:
            continue
        _, ref, field = parts
        triples.append((ref, field, f.get(key, "")))
    try:
        out = bizbox.propose_edits(ctx.conn, kind, triples, reason=f.get("reason", ""), at=ctx.now, actor=ctx.user.id)
        ctx.conn.commit()
    except bizbox.Refused as exc:
        ctx.conn.rollback()
        return redirect(_back(kind, err=f"Not queued: {exc}"))
    return redirect(_back(kind, msg=f"Batch #{out['batch_id']} queued: {out['queued']} cell(s). A second person approves it on the Changes tab."))


# ---------------------------------------------------------------------- adds

def new_form(ctx, kind):
    from .. import HttpError, Response
    _gate(ctx, "WRITE")
    if kind not in bizbox.ADDABLE:
        raise HttpError("404 Not Found", "Nothing of that kind is added from the desk.")
    q = ctx.request.query
    v = ctx.request.query
    if kind == "purchase_order":
        vendors = "".join(f"<option value='{t.esc(x['name'])}'>" for x in bizbox.vendors(ctx.conn))
        items = "".join(f"<option value='{t.esc(p['ext_ref'])}'>{t.esc(p['name'])}</option>"
                        for p in bizbox.records(ctx.conn, "product", limit=2000))
        line = lambda i: (f"<tr><td>{i}</td><td><input name='line{i}_product_ref' list=items maxlength=64 placeholder='item code'></td>"
                          f"<td><input name='line{i}_description' maxlength=400></td>"
                          f"<td><input name='line{i}_quantity' type=number step=any min=0 style='width:90px'></td>"
                          f"<td><input name='line{i}_unit_cost' type=number step=any min=0 style='width:110px'></td></tr>")
        fields = (f"<div><label>Vendor</label><input name=vendor list=vendors required maxlength=400 value='{t.esc(v.get('vendor', ''))}'>"
                  f"<datalist id=vendors>{vendors}</datalist></div>"
                  f"<div><label>Order date</label><input type=date name=ordered_on value='{t.esc(v.get('ordered_on', ''))}'></div>"
                  "<div><label>Currency</label><input name=currency maxlength=8 value='PHP'></div>"
                  "<div><label>Status</label><input name=status maxlength=32 placeholder='leave empty: BizBox decides'></div>"
                  "<div style='grid-column:1/-1'><label>Lines</label><div class=tablewrap><table class=compact><thead><tr><th>#</th><th>Item</th>"
                  "<th>Description</th><th>Qty</th><th>Unit cost</th></tr></thead><tbody>" + "".join(line(i) for i in range(1, 9))
                  + f"</tbody></table></div><datalist id=items>{items}</datalist></div>")
    else:
        fields = ("<div><label>Item code</label><input name=ext_ref maxlength=64 placeholder='leave empty: BizBox numbers it'></div>"
                  "<div><label>Name</label><input name=name required maxlength=400></div>"
                  "<div><label>Category</label><input name=category maxlength=400></div>"
                  "<div><label>Unit</label><input name=unit maxlength=32 placeholder='pc, box, ream'></div>"
                  "<div><label>Unit cost</label><input name=unit_cost type=number step=any min=0></div>")
    body = (_banners(q) + f"<h1>{NEW_WORDS[kind]}</h1><p class=sub>This goes to the Changes tab for a second person to approve. Once it is approved and sent, BizBox "
            f"creates it and gives it its number. <a href='/procurement?tab={kind}'>Back</a></p>"
            f"<div class=card><form method=post action='/procurement/{kind}/add' class=fields><div class=grid2>{fields}"
            "<div style='grid-column:1/-1'><label>Why</label><input name=reason required maxlength=400 placeholder='What the approver needs to know'></div>"
            f"</div><div style='margin-top:12px'><button type=submit>{t.icon('check')} Send for approval</button></div></form></div>")
    return Response(body=t.page(NEW_WORDS[kind], body, user=ctx.user, active=AREA))


def add(ctx, kind):
    from .. import redirect
    _gate(ctx, "WRITE")
    if kind not in bizbox.ADDABLE:
        return redirect("/procurement")
    f = ctx.request.form()
    record = {k: f.get(k, "") for k in bizbox.ADDABLE[kind]["fields"]}
    lines = []
    if bizbox.ADDABLE[kind]["lines"]:
        for i in range(1, 9):
            lines.append({k: f.get(f"line{i}_{k}", "") for k in bizbox.ADDABLE[kind]["lines"]})
    try:
        bid = bizbox.propose_add(ctx.conn, kind, record, lines, reason=f.get("reason", ""), at=ctx.now, actor=ctx.user.id)
        ctx.conn.commit()
    except bizbox.Refused as exc:
        ctx.conn.rollback()
        return redirect(f"/procurement/{kind}/new?" + urllib.parse.urlencode({"err": f"Not queued: {exc}", **{k: v for k, v in record.items() if v}}))
    return redirect("/procurement?" + urllib.parse.urlencode({"tab": "changes", "msg": f"Batch #{bid} queued: {NEW_WORDS[kind].lower()}. A second person approves it here."}))


def detail(ctx, kind):
    return finance.detail(ctx, kind, area=AREA)

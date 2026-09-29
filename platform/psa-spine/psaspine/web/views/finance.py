"""Finance: agreements, procurement, products and invoices from BizBox (043).

A read-only view of the BizBox mirror, gated by the security role's FINANCE
level: READ to look and to link a record to a ticket you work (a link is the
desk's own data); WRITE to propose a change to a BizBox record, which waits in
the change log and never reaches BizBox until a write path is switched on.
The mirror itself is written only by `sync-bizbox`.
"""
from __future__ import annotations

import urllib.parse

from ... import bizbox
from .. import templates as t
from . import common

COLUMNS = {
    "agreement": (("ext_ref", "Agreement"), ("name", "Name"), ("party", "Party"), ("starts_on", "Starts"),
                  ("ends_on", "Ends"), ("status", "Status"), ("amount", "Amount")),
    "purchase_order": (("ext_ref", "PO"), ("vendor", "Vendor"), ("ordered_on", "Ordered"), ("status", "Status"),
                       ("total", "Total")),
    "product": (("ext_ref", "Item"), ("name", "Name"), ("category", "Category"), ("unit", "Unit"),
                ("unit_cost", "Unit cost")),
    "invoice": (("ext_ref", "Invoice"), ("party", "Party"), ("invoiced_on", "Invoiced"), ("due_on", "Due"),
                ("status", "Status"), ("total", "Total"), ("agreement_ref", "Agreement")),
}
TABS = (("agreement", "Agreements"), ("purchase_order", "Procurement"), ("product", "Products"),
        ("invoice", "Invoices"))
ONE = {"agreement": "Agreement", "purchase_order": "Purchase order", "product": "Product", "invoice": "Invoice"}


def _money(v, cur=None) -> str:
    if v is None:
        return ""
    return f"{cur + ' ' if cur else ''}{float(v):,.2f}"


def _ref_link(kind: str, ref) -> str:
    return f"<a href='/finance/{kind}/{urllib.parse.quote(ref, safe='')}'>{t.esc(ref)}</a>" if ref else ""


def _cell(rec, field) -> str:
    v = rec[field]
    if field == "agreement_ref":
        return f"<td>{_ref_link('agreement', v)}</td>"
    if field in ("amount", "total", "unit_cost"):
        cur = rec["currency"] if "currency" in rec.keys() else None
        return f"<td class=num>{t.esc(_money(v, cur))}</td>"
    return f"<td>{t.esc(v or '')}</td>"


def _changes_table(ctx, rows, *, with_record: bool = True) -> str:
    can = common.allows(ctx, "FINANCE", "WRITE")
    back = {v: k for k, v in bizbox.LINK_KIND.items()}
    words = {"PENDING": "Waiting for BizBox", "APPLIED": "Applied in BizBox", "REJECTED": "Refused by BizBox",
             "CANCELLED": "Cancelled"}
    trs = []
    for c in rows:
        kind = back[c["kind"]]
        rec = (f"<td>{ONE[kind]} {_ref_link(kind, c['ext_ref'])}</td>" if with_record else "")
        cancel = (f"<form method=post action='/finance/change/{c['change_id']}/cancel' class=inline>"
                  "<button class='ghost small' type=submit>Cancel</button></form>" if can and c["status"] == "PENDING" else "")
        trs.append(f"<tr><td>#{c['change_id']}</td>{rec}<td>{t.esc(bizbox.FIELD_WORDS.get(c['field'], c['field']))}</td>"
                   f"<td>{t.esc(c['old_value'] or '—')} → <b>{t.esc(c['new_value'] or '—')}</b></td>"
                   f"<td>{t.esc(c['reason'])}</td><td>{t.esc(c['requested_by'])}<div class=muted>{t.esc(c['requested_at'])}</div></td>"
                   f"<td>{t.chip(words[c['status']])}" + (f"<div class=muted>{t.esc(c['answer'])}</div>" if c["answer"] else "")
                   + f"</td><td>{cancel}</td></tr>")
    head = "<th>Change</th>" + ("<th>Record</th>" if with_record else "") + "<th>Field</th><th>From → to</th><th>Why</th><th>Asked by</th><th>State</th><th></th>"
    return (f"<div class=tablewrap><table><thead><tr>{head}</tr></thead><tbody>"
            + ("".join(trs) or f"<tr><td colspan=8 class=muted>No changes proposed.</td></tr>") + "</tbody></table></div>")


def index(ctx):
    from .. import Response
    common.require_module(ctx, "FINANCE")
    q = ctx.request.query
    if q.get("tab") == "changes":
        return changes_page(ctx)
    kind = q.get("tab", "agreement")
    if kind not in bizbox.KINDS:
        kind = "agreement"
    search = q.get("q", "")
    absent = q.get("absent") == "1"
    rows = bizbox.records(ctx.conn, kind, q=search, include_absent=absent)
    tabs = _tabs(ctx, kind)
    head = "".join(f"<th{' class=num' if f in ('amount', 'total', 'unit_cost') else ''}>{t.esc(lab)}</th>"
                   for f, lab in COLUMNS[kind]) + "<th>Linked</th>"
    seen = common.board_ids_for(ctx)

    def linked_cell(ref):
        # the tickets this record serves, among those the viewer may see; projects by id
        out = []
        for l in bizbox.linked_to(ctx.conn, kind, ref):
            if l["subject_kind"] == "TICKET":
                b = ctx.conn.execute("SELECT board_id FROM ticket WHERE work_item_id = ?", (l["subject_id"],)).fetchone()
                if b is not None and b[0] in seen:
                    out.append(f"<a href='/ticket/{t.esc(l['subject_id'])}'>{t.esc(l['subject_id'])}</a>")
            else:
                out.append(f"<a href='/project/{t.esc(l['subject_id'])}'>{t.esc(l['subject_id'])}</a>")
        return ", ".join(out)
    summary = ""
    if kind == "purchase_order":
        by = {}
        total = {}
        for r in rows:
            st = r["status"] or "(none)"
            by[st] = by.get(st, 0) + 1
            total[st] = total.get(st, 0) + float(r["total"] or 0)
        summary = ("<div class='tiles' style='grid-template-columns:repeat(auto-fit,minmax(150px,1fr));margin-bottom:12px'>"
                   + "".join(f"<div class=tile><div class=l>{t.esc(st)}</div><div class=n>{n}</div>"
                             f"<div class=muted>{t.esc(_money(total[st], 'PHP'))}</div></div>" for st, n in sorted(by.items()))
                   + "</div>")
    trs = []
    for r in rows:
        n = linked_cell(r["ext_ref"])
        cells = "".join(
            (f"<td><a href='/finance/{kind}/{urllib.parse.quote(r['ext_ref'], safe='')}'>{t.esc(r['ext_ref'])}</a>"
             + ("" if r["present"] else " <span class=pill>gone from BizBox</span>") + "</td>")
            if f == "ext_ref" else _cell(r, f) for f, _ in COLUMNS[kind])
        trs.append(f"<tr>{cells}<td>{n}</td></tr>")
    st = bizbox.status(ctx.conn)
    sync = (f"Last synced {t.esc(st['last_sync_at'])} by {t.esc(st['last_sync_by'])}: {t.esc(st['last_result'] or '')}"
            if st and st["last_sync_at"] else "Not synced yet. SQL01 runs <code>psaspine sync-bizbox</code> once the "
            "read-only BizBox views exist.")
    body = ("<h1>Finance</h1><p class=sub>Agreements, purchase orders, products and invoices, as BizBox holds them. "
            "Read-only here: BizBox is where they are changed, and Dada PSA issues no invoice. Link a record to the "
            "ticket or project it concerns, so the work and what paid for it sit side by side.</p>"
            f"<div class='banner ok'>{sync}</div>" + tabs
            + "<div class=card><form method=get action='/finance' class='row schedbar'>"
              f"<input type=hidden name=tab value={kind}>"
              f"<div style='flex:1 1 260px'><input name=q value='{t.esc(search)}' placeholder='Search {dict(TABS)[kind].lower()}'></div>"
              f"<div style='flex:0 0 auto'><label><input type=checkbox name=absent value=1{' checked' if absent else ''}> "
              "Include records gone from BizBox</label></div>"
              "<div style='flex:0 0 auto'><button class=ghost type=submit>Search</button></div></form>"
              + summary + f"<div class=tablewrap><table><thead><tr>{head}</tr></thead><tbody>"
            + ("".join(trs) or f"<tr><td colspan={len(COLUMNS[kind]) + 1} class=muted>Nothing mirrored yet.</td></tr>")
            + "</tbody></table></div></div>")
    return Response(body=t.page("Finance", body, user=ctx.user, active="finance"))


def _tabs(ctx, on: str) -> str:
    counts = {k: len(bizbox.records(ctx.conn, k)) for k, _ in TABS}
    pending = len(bizbox.changes(ctx.conn, status="PENDING"))
    return ("<div class=stabs>" + "".join(
        f"<a class='{'on' if k == on else ''}' href='/finance?tab={k}'>{v} · {counts[k]}</a>" for k, v in TABS)
        + f"<a class='{'on' if on == 'changes' else ''}' href='/finance?tab=changes'>Changes to BizBox · {pending}</a></div>")


def changes_page(ctx):
    from .. import Response
    common.require_module(ctx, "FINANCE")
    q = ctx.request.query
    status = q.get("status", "PENDING") if q.get("status", "PENDING") in ("PENDING", "APPLIED", "REJECTED", "CANCELLED", "ALL") else "PENDING"
    rows = bizbox.changes(ctx.conn, status=None if status == "ALL" else status)
    opts = "".join(f"<option value={k}{' selected' if k == status else ''}>{v}</option>" for k, v in (
        ("PENDING", "Waiting for BizBox"), ("APPLIED", "Applied"), ("REJECTED", "Refused"), ("CANCELLED", "Cancelled"), ("ALL", "All")))
    body = ((f"<div class='banner ok'>{t.esc(q.get('msg', ''))}</div>" if q.get("msg") else "")
            + (f"<div class='banner err'>{t.esc(q.get('err', ''))}</div>" if q.get("err") else "")
            + "<h1>Finance</h1><p class=sub>Changes proposed to BizBox records. <b>BizBox has not changed:</b> Dada PSA "
              "keeps each proposal until a write path to BizBox is switched on, or until someone makes the change in "
              "BizBox and marks it here. The next sync then shows BizBox's own value.</p>" + _tabs(ctx, "changes")
            + "<div class=card><form method=get action='/finance' class='row schedbar'><input type=hidden name=tab value=changes>"
              f"<div style='flex:0 0 220px'><select name=status>{opts}</select></div>"
              "<div style='flex:0 0 auto'><button class=ghost type=submit>Show</button></div></form>"
            + _changes_table(ctx, rows) + "</div>")
    return Response(body=t.page("Finance", body, user=ctx.user, active="finance"))


def detail(ctx, kind, ext_ref):
    from .. import HttpError, Response
    common.require_module(ctx, "FINANCE")
    ext_ref = urllib.parse.unquote(ext_ref)
    if kind not in bizbox.KINDS:
        raise HttpError("404 Not Found", "No such record.")
    rec = bizbox.get(ctx.conn, kind, ext_ref)
    if rec is None:
        raise HttpError("404 Not Found", "No such record in the BizBox mirror.")
    def fact(f):
        if f == "agreement_ref":
            return _ref_link("agreement", rec[f]) or "—"
        if f in ("amount", "total", "unit_cost"):
            return t.esc(_money(rec[f], rec["currency"] if "currency" in rec.keys() else None))
        return t.esc(rec[f] or "—")
    facts = "".join(f"<dt>{t.esc(lab)}</dt><dd>{fact(f)}</dd>" for f, lab in COLUMNS[kind])
    seen = common.board_ids_for(ctx)
    links = []
    for l in bizbox.linked_to(ctx.conn, kind, ext_ref):
        if l["subject_kind"] == "TICKET":
            b = ctx.conn.execute("SELECT board_id FROM ticket WHERE work_item_id = ?", (l["subject_id"],)).fetchone()
            if b is None or b[0] not in seen:
                continue
            links.append(f"<li>Ticket <a href='/ticket/{t.esc(l['subject_id'])}'>{t.esc(l['subject_id'])}</a> · "
                         f"{t.esc(l['linked_at'])} · {t.esc(l['linked_by'])}</li>")
        else:
            links.append(f"<li>Project <a href='/project/{t.esc(l['subject_id'])}'>{t.esc(l['subject_id'])}</a> · "
                         f"{t.esc(l['linked_at'])}</li>")
    extra = ""
    if kind == "agreement":
        inv = ctx.conn.execute("SELECT ext_ref, invoiced_on, status, total, currency FROM ext_invoice WHERE source_id = ?"
                               " AND agreement_ref = ? AND present = 1 ORDER BY invoiced_on DESC", (bizbox.SOURCE, ext_ref)).fetchall()
        extra = ("<div class=card><h3>" + t.icon("tag") + "Invoices under this agreement</h3>"
                 + ("<div class=tablewrap><table class=compact><tbody>" + "".join(
                     f"<tr><td><a href='/finance/invoice/{urllib.parse.quote(i['ext_ref'], safe='')}'>{t.esc(i['ext_ref'])}</a></td>"
                     f"<td>{t.esc(i['invoiced_on'] or '')}</td><td>{t.esc(i['status'] or '')}</td>"
                     f"<td class=num>{t.esc(_money(i['total'], i['currency']))}</td></tr>" for i in inv) + "</tbody></table></div>"
                    if inv else "<div class=muted>None mirrored.</div>") + "</div>")
    if kind == "purchase_order":
        lines = bizbox.po_lines(ctx.conn, ext_ref)
        total = sum(float(l["quantity"] or 0) * float(l["unit_cost"] or 0) for l in lines)
        extra = ("<div class=card><h3>" + t.icon("rows") + "Lines</h3><div class=tablewrap><table><thead><tr><th>#</th><th>Item</th>"
                 "<th>Description</th><th class=num>Ordered</th><th class=num>Received</th><th class=num>Unit cost</th>"
                 "<th class=num>Extended</th></tr></thead><tbody>"
                 + ("".join(f"<tr><td>{t.esc(l['line_no'] if l['line_no'] is not None else '')}</td>"
                            f"<td>{_ref_link('product', l['product_ref'])}</td><td>{t.esc(l['description'] or '')}</td>"
                            f"<td class=num>{float(l['quantity'] or 0):g}</td><td class=num>{float(l['received_qty'] or 0):g}</td>"
                            f"<td class=num>{t.esc(_money(l['unit_cost']))}</td>"
                            f"<td class=num>{t.esc(_money(float(l['quantity'] or 0) * float(l['unit_cost'] or 0)))}</td></tr>" for l in lines)
                    or "<tr><td colspan=7 class=muted>No lines mirrored.</td></tr>")
                 + (f"<tr><td colspan=6 class=num><b>Lines total</b></td><td class=num><b>{t.esc(_money(total, rec['currency']))}</b></td></tr>" if lines else "")
                 + "</tbody></table></div></div>")
    can_edit = common.allows(ctx, "FINANCE", "WRITE") and kind in bizbox.EDITABLE
    proposals = bizbox.changes(ctx.conn, kind, ext_ref)
    form = ""
    if can_edit:
        fields = "".join(f"<option value={f}>{bizbox.FIELD_WORDS[f]}</option>" for f in bizbox.EDITABLE[kind])
        form = (f"<form method=post action='/finance/{kind}/{urllib.parse.quote(ext_ref, safe='')}/propose' class=grid2 style='margin-top:10px'>"
                f"<div><label>Field</label><select name=field>{fields}</select></div>"
                "<div><label>New value</label><input name=new_value required maxlength=200 placeholder='e.g. Approved, or 2026-12-31'></div>"
                "<div style='grid-column:1/-1'><label>Why</label><input name=reason required maxlength=400 "
                "placeholder='What the person applying it in BizBox needs to know'></div>"
                "<div><button class=ghost type=submit>Propose the change</button></div></form>")
    changes_card = ("<div class=card><h3>" + t.icon("note") + "Changes to BizBox</h3><p class=why>BizBox is where this record "
                    "changes. A change proposed here waits, recorded, until a write path to BizBox is switched on or "
                    "someone applies it in BizBox; BizBox itself has not changed.</p>"
                    + (_changes_table(ctx, proposals, with_record=False) if proposals else "") + form + "</div>"
                    if (can_edit or proposals) else "")
    extra += changes_card
    q = ctx.request.query
    body = ((f"<div class='banner ok'>{t.esc(q.get('msg', ''))}</div>" if q.get("msg") else "")
            + (f"<div class='banner err'>{t.esc(q.get('err', ''))}</div>" if q.get("err") else "")
            + f"<h1>{t.esc(ONE[kind])} {t.esc(ext_ref)}</h1><p class=sub>From BizBox, read-only"
            + ("" if rec["present"] else " · <b>no longer in BizBox</b>; kept because work links to it")
            + f" · synced {t.esc(rec['synced_at'])} · <a href='/finance?tab={kind}'>{dict(TABS)[kind]}</a>"
            + (f" · <span class='chip sla-warn'>{sum(1 for c in proposals if c['status'] == 'PENDING')} change(s) waiting for BizBox</span>"
               if any(c["status"] == "PENDING" for c in proposals) else "") + "</p>"
            + f"<div class=grid2><div class=card><dl class=kv>{facts}</dl></div>"
            + "<div class=card><h3>" + t.icon("note") + "Work linked to it</h3>"
            + (f"<ul class=plain>{''.join(links)}</ul>" if links else "<div class=muted>No ticket or project yet.</div>")
            + "</div></div>" + extra)
    return Response(body=t.page(ext_ref, body, user=ctx.user, active="finance"))


def ticket_card(ctx, tk, *, can_work: bool) -> str:
    """The Finance pod on a ticket: the BizBox records it concerns."""
    if not common.allows(ctx, "FINANCE"):
        return ""
    wid = t.esc(tk["work_item_id"])
    rows = bizbox.links(ctx.conn, "TICKET", tk["work_item_id"])
    can_link = can_work
    items = "".join(
        f"<li>{t.esc(ONE[r['kind']])} <a href='/finance/{r['kind']}/{urllib.parse.quote(r['ext_ref'], safe='')}'>"
        f"{t.esc(r['ext_ref'])}</a>"
        + (f" <span class=muted>{t.esc((r['record']['name'] if 'name' in r['record'].keys() else r['record'][list(r['record'].keys())[2]]) or '')}</span>" if r["record"] else "")
        + (f" <form method=post action='/ticket/{wid}/finance/unlink' style='display:inline'><input type=hidden name=kind value={r['kind']}>"
           f"<input type=hidden name=ext_ref value='{t.esc(r['ext_ref'])}'><button class='ghost small' type=submit title='Unlink'>×</button></form>"
           if can_link else "") + "</li>" for r in rows)
    add = ""
    if can_link:
        add = (f"<form method=post action='/ticket/{wid}/finance/link' class=row style='margin-top:6px'>"
               "<div style='flex:0 0 150px'><select name=kind aria-label='Kind'>"
               + "".join(f"<option value={k}>{ONE[k]}</option>" for k, _ in TABS) + "</select></div>"
               "<div><input name=ext_ref placeholder='PO or agreement number' aria-label='BizBox reference'></div>"
               "<div style='flex:0 0 auto'><button class=ghost type=submit>Link</button></div></form>")
    return (f"<div class=card data-pod=finance><h3>{t.icon('tag')}Finance</h3>"
            + (f"<ul class=plain>{items}</ul>" if items else "<div class=muted>No BizBox record linked.</div>")
            + add + "</div>")


def ticket_link(ctx, work_item_id):
    from .ticket import _back, _load
    common.require_module(ctx, "FINANCE")
    tk = _load(ctx, work_item_id)
    common.require_board(ctx, tk["board_id"], need="WORK")
    f = ctx.request.form()
    try:
        bizbox.link(ctx.conn, "TICKET", work_item_id, f.get("kind", ""), f.get("ext_ref", ""), at=ctx.now, actor=ctx.user.id)
        ctx.conn.commit()
    except bizbox.Refused as exc:
        return _back(work_item_id, err=str(exc))
    return _back(work_item_id, msg="Linked to BizBox")


def ticket_unlink(ctx, work_item_id):
    from .ticket import _back, _load
    common.require_module(ctx, "FINANCE")
    tk = _load(ctx, work_item_id)
    common.require_board(ctx, tk["board_id"], need="WORK")
    f = ctx.request.form()
    bizbox.unlink(ctx.conn, "TICKET", work_item_id, f.get("kind", ""), f.get("ext_ref", ""), at=ctx.now, actor=ctx.user.id)
    ctx.conn.commit()
    return _back(work_item_id, msg="Unlinked")


def propose(ctx, kind, ext_ref):
    from .. import redirect
    common.require_module(ctx, "FINANCE", "WRITE")
    ext_ref = urllib.parse.unquote(ext_ref)
    back = f"/finance/{kind}/{urllib.parse.quote(ext_ref, safe='')}"
    if kind not in bizbox.KINDS:
        return redirect("/finance")
    f = ctx.request.form()
    try:
        cid = bizbox.propose(ctx.conn, kind, ext_ref, f.get("field", ""), f.get("new_value", ""), reason=f.get("reason", ""),
                             at=ctx.now, actor=ctx.user.id)
        ctx.conn.commit()
    except bizbox.Refused as exc:
        ctx.conn.rollback()
        return redirect(back + "?" + urllib.parse.urlencode({"err": f"Not proposed: {exc}"}))
    return redirect(back + "?" + urllib.parse.urlencode({"msg": f"Change #{cid} recorded. BizBox has not changed; it waits "
                                                                "for the BizBox write path or for someone to apply it there."}))


def cancel_change(ctx, change_id):
    from .. import redirect
    common.require_module(ctx, "FINANCE", "WRITE")
    try:
        bizbox.decide(ctx.conn, int(change_id) if str(change_id).isdigit() else -1, "CANCELLED", at=ctx.now, actor=ctx.user.id)
        ctx.conn.commit()
    except bizbox.Refused as exc:
        return redirect("/finance?" + urllib.parse.urlencode({"tab": "changes", "err": str(exc)}))
    return redirect("/finance?" + urllib.parse.urlencode({"tab": "changes", "msg": f"Change #{change_id} cancelled"}))

"""Finance: procurement, products and invoices from BizBox (043); agreements
made on the desk (045, views/agreements.py).

A read-only view of the BizBox mirror, gated by the security role's FINANCE
level: READ to look and to link a record to a ticket you work (a link is the
desk's own data); WRITE to propose a change to a BizBox record, which waits in
the change log and never reaches BizBox until a write path is switched on.
The mirror itself is written only by `sync-bizbox`.
"""
from __future__ import annotations

import urllib.parse

from ... import agreements, bizbox
from .. import templates as t
from . import common

COLUMNS = {
    "agreement": (("ext_ref", "Agreement"), ("name", "Name"), ("party", "Party"), ("starts_on", "Starts"),
                  ("ends_on", "Ends"), ("status", "Status"), ("amount", "Amount")),
    "purchase_order": (("ext_ref", "PO"), ("vendor", "Vendor"), ("ordered_on", "Ordered"), ("status", "Status"),
                       ("total", "Total")),
    "product": (("ext_ref", "Item"), ("name", "Name"), ("category", "Category"), ("unit", "Unit"),
                ("unit_cost", "Unit cost")),
    "invoice": (("ext_ref", "Invoice"), ("supplier_ref", "Supplier's invoice no."), ("party", "Party"),
                ("invoiced_on", "Invoiced"), ("due_on", "Due"), ("status", "Status"), ("total", "Total"),
                ("agreement_ref", "Agreement")),
}
TABS = (("agreement", "Agreements"), ("purchase_order", "Procurement"), ("product", "Products"),
        ("invoice", "Invoices"))
ONE = {"agreement": "Agreement", "purchase_order": "Purchase order", "product": "Product", "invoice": "Invoice"}
# The kinds with a status summary above the list: a tile per status BizBox
# uses, with the count and the sum. The statuses are BizBox's own words; the
# desk adds none (it cannot: "paid" is not knowable from BizBox's receiving
# tables, SQL01 29 Sep 2026, MEASURED, so an invoice is Draft, Posted or Cancelled).
TILED = ("purchase_order", "invoice")


def _mirror_kinds(ctx) -> list[str]:
    """The mirror kinds BizBox has rows for, in the tabs' order."""
    on = set(bizbox.present_kinds(ctx.conn))
    return [k for k, _ in TABS if k in on and k != "agreement"]


def _kinds(ctx) -> list[str]:
    """The tabs: Agreements first (the desk's own, since 045), then the mirror
    kinds BizBox has rows for."""
    return ["agreement", *_mirror_kinds(ctx)]


def _tabs_for(ctx):
    on = _kinds(ctx)
    return [(k, v) for k, v in TABS if k in on]


def _mirror_tabs(ctx):
    """The kinds a ticket or project links to: mirrored records only."""
    on = _mirror_kinds(ctx)
    return [(k, v) for k, v in TABS if k in on]


def _columns(ctx, kind):
    """The list's columns: an invoice's Agreement column only when some invoice
    has one (BizBox has no supplier agreements to point at), and the
    supplier's invoice number only when the map fills it."""
    cols = COLUMNS[kind]
    if kind == "invoice":
        drop = set()
        for f in ("agreement_ref", "supplier_ref"):
            if not ctx.conn.execute(f"SELECT 1 FROM ext_invoice WHERE source_id = ? AND {f} IS NOT NULL LIMIT 1",
                                    (bizbox.SOURCE,)).fetchone():
                drop.add(f)
        cols = tuple(c for c in cols if c[0] not in drop)
    return cols


def _money(v, cur=None) -> str:
    if v is None:
        return ""
    return f"{cur + ' ' if cur else ''}{float(v):,.2f}"


AREAS = ("finance", "procurement")      # the two menus the same BizBox record page serves (13 Oct 2026)


def _url(kind: str, ref, area: str = "finance") -> str:
    """A record's page. The reference travels in the query string, never the
    path: a WSGI server percent-decodes the path before the router splits it,
    so a BizBox key holding '/' or '%' would never open from its own link."""
    return f"/{area if area in AREAS else 'finance'}/{kind}?" + urllib.parse.urlencode({"ref": ref})


def _ref_link(kind: str, ref, area: str = "finance") -> str:
    return f"<a href='{t.esc(_url(kind, ref, area))}'>{t.esc(ref)}</a>" if ref else ""


def _cell(rec, field, area: str = "finance") -> str:
    v = rec[field]
    if field == "agreement_ref":
        return f"<td>{_ref_link('agreement', v, area)}</td>"
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
    kinds = _kinds(ctx)
    kind = q.get("tab", kinds[0])
    if kind not in kinds:
        kind = kinds[0]
    if kind == "agreement":
        from . import agreements as agreements_view
        return agreements_view.tab(ctx)
    search = q.get("q", "")
    absent = q.get("absent") == "1"
    page_no = int(q["page"]) if q.get("page", "").isdigit() and int(q["page"]) > 0 else 1
    total_n = bizbox.count(ctx.conn, kind, q=search, include_absent=absent)
    rows = bizbox.records(ctx.conn, kind, q=search, include_absent=absent, limit=bizbox.PAGE, offset=(page_no - 1) * bizbox.PAGE)
    tabs = _tabs(ctx, kind)
    columns = _columns(ctx, kind)
    head = "".join(f"<th{' class=num' if f in ('amount', 'total', 'unit_cost') else ''}>{t.esc(lab)}</th>"
                   for f, lab in columns) + "<th>Linked</th>"
    seen = common.board_ids_for(ctx)
    # the tickets and projects each record on this page serves, among those the
    # viewer may see: one query for the links, one for the tickets' boards, one
    # for the projects' boards, whatever the page holds
    links = bizbox.links_for(ctx.conn, kind, [r["ext_ref"] for r in rows])
    visible = _visible_subjects(ctx, [l for ls in links.values() for l in ls], seen)
    covered = agreements.covering_for(ctx.conn, kind, [r["ext_ref"] for r in rows])

    def linked_cell(ref):
        return ", ".join([f"<a href='/{'ticket' if l['subject_kind'] == 'TICKET' else 'project'}/{t.esc(l['subject_id'])}'>"
                          f"{t.esc(l['subject_id'])}</a>" for l in links.get(ref, [])
                          if (l["subject_kind"], l["subject_id"]) in visible]
                         + [f"<a href='/agreement/{t.esc(a['agreement_id'])}' title='{t.esc(a['name'])}'>{t.esc(a['agreement_id'])}</a>"
                            for a in covered.get(ref, [])])
    summary = ""
    if kind in TILED:
        summary = ("<div class='tiles' style='grid-template-columns:repeat(auto-fit,minmax(150px,1fr));margin-bottom:12px'>"
                   + "".join(f"<div class=tile><div class=l>{t.esc(s['status'])}</div><div class=n>{s['n']}</div>"
                             f"<div class=muted>{t.esc(_money(s['total'] or 0, 'PHP'))}</div></div>"
                             for s in bizbox.summary(ctx.conn, kind, q=search, include_absent=absent))
                   + "</div>")
    trs = []
    for r in rows:
        n = linked_cell(r["ext_ref"])
        cells = "".join(
            (f"<td>{_ref_link(kind, r['ext_ref'])}"
             + ("" if r["present"] else " <span class=pill>gone from BizBox</span>") + "</td>")
            if f == "ext_ref" else _cell(r, f) for f, _ in columns)
        trs.append(f"<tr>{cells}<td>{n}</td></tr>")
    first, last = (page_no - 1) * bizbox.PAGE + 1, min(page_no * bizbox.PAGE, total_n)
    keep = {"tab": kind, "q": search} | ({"absent": "1"} if absent else {})
    pager = (f"<div class='row schedbar' style='justify-content:space-between'><div class=muted>Showing {first}–{last} of {total_n}</div><div>"
             + (f"<a class='ghost small' href='/finance?{urllib.parse.urlencode(keep | {'page': page_no - 1})}'>‹ Previous</a> " if page_no > 1 else "")
             + (f"<a class='ghost small' href='/finance?{urllib.parse.urlencode(keep | {'page': page_no + 1})}'>Next ›</a>" if last < total_n else "")
             + "</div></div>") if total_n > bizbox.PAGE else ""
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
            + ("".join(trs) or f"<tr><td colspan={len(columns) + 1} class=muted>Nothing mirrored yet.</td></tr>")
            + "</tbody></table></div>" + pager + "</div>")
    return Response(body=t.page("Finance", body, user=ctx.user, active="finance"))


def _visible_subjects(ctx, links, seen) -> set:
    """(kind, id) of the linked tickets and projects the viewer may see: a
    ticket by its board, a project by its board or none (views/projects' rule)."""
    out = set()
    tickets = sorted({l["subject_id"] for l in links if l["subject_kind"] == "TICKET"})
    projects_ = sorted({l["subject_id"] for l in links if l["subject_kind"] == "PROJECT"})
    for i in range(0, len(tickets), 200):
        chunk = tickets[i:i + 200]
        for r in ctx.conn.execute(f"SELECT work_item_id, board_id FROM ticket WHERE work_item_id IN ({','.join('?' * len(chunk))})", chunk):
            if r["board_id"] in seen:
                out.add(("TICKET", r["work_item_id"]))
    for i in range(0, len(projects_), 200):
        chunk = projects_[i:i + 200]
        for r in ctx.conn.execute(f"SELECT project_id, board_id FROM project WHERE project_id IN ({','.join('?' * len(chunk))})", chunk):
            if r["board_id"] is None or r["board_id"] in seen:
                out.add(("PROJECT", r["project_id"]))
    return out


def _tabs(ctx, on: str) -> str:
    tabs = _tabs_for(ctx)
    counts = {k: ctx.conn.execute(f"SELECT COUNT(*) FROM {bizbox.KINDS[k][0]} WHERE source_id = ? AND present = 1",
                                  (bizbox.SOURCE,)).fetchone()[0] for k, _ in tabs if k != "agreement"}
    # the desk's own agreements (045); a mirrored agreement, if a source is ever named, counts too
    counts["agreement"] = (ctx.conn.execute("SELECT COUNT(*) FROM agreement WHERE status <> 'CANCELLED'").fetchone()[0]
                           + bizbox.count(ctx.conn, "agreement"))
    pending = ctx.conn.execute("SELECT COUNT(*) FROM ext_change WHERE source_id = ? AND status = 'PENDING'",
                               (bizbox.SOURCE,)).fetchone()[0]
    return ("<div class=stabs>" + "".join(
        f"<a class='{'on' if k == on else ''}' href='/finance?tab={k}'>{v} · {counts[k]}</a>" for k, v in tabs)
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


def detail(ctx, kind, *, area: str = "finance"):
    from .. import HttpError, Response
    common.require_module(ctx, "PROCUREMENT" if area == "procurement" else "FINANCE")
    ext_ref = ctx.request.query.get("ref", "")
    if kind not in bizbox.LINK_KIND or not ext_ref:
        raise HttpError("404 Not Found", "No such record.")
    rec = bizbox.get(ctx.conn, kind, ext_ref)
    if rec is None:
        raise HttpError("404 Not Found", "No such record in the BizBox mirror.")
    def fact(f):
        if f == "agreement_ref":
            return _ref_link("agreement", rec[f], area) or "—"
        if f in ("amount", "total", "unit_cost"):
            return t.esc(_money(rec[f], rec["currency"] if "currency" in rec.keys() else None))
        return t.esc(rec[f] or "—")
    facts = "".join(f"<dt>{t.esc(lab)}</dt><dd>{fact(f)}</dd>" for f, lab in _columns(ctx, kind))
    seen = common.board_ids_for(ctx)
    linked = bizbox.linked_to(ctx.conn, kind, ext_ref)
    visible = _visible_subjects(ctx, linked, seen)
    links = []
    for l in linked:
        if (l["subject_kind"], l["subject_id"]) not in visible:
            continue
        if l["subject_kind"] == "TICKET":
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
                     f"<tr><td>{_ref_link('invoice', i['ext_ref'], area)}</td>"
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
                            f"<td>{_ref_link('product', l['product_ref'], area)}</td><td>{t.esc(l['description'] or '')}</td>"
                            f"<td class=num>{float(l['quantity'] or 0):g}</td><td class=num>{float(l['received_qty'] or 0):g}</td>"
                            f"<td class=num>{t.esc(_money(l['unit_cost']))}</td>"
                            f"<td class=num>{t.esc(_money(float(l['quantity'] or 0) * float(l['unit_cost'] or 0)))}</td></tr>" for l in lines)
                    or "<tr><td colspan=7 class=muted>No lines mirrored.</td></tr>")
                 + (f"<tr><td colspan=6 class=num><b>Lines total</b></td><td class=num><b>{t.esc(_money(total, rec['currency']))}</b></td></tr>" if lines else "")
                 + "</tbody></table></div></div>")
    module = "PROCUREMENT" if area == "procurement" else "FINANCE"
    can_edit = common.allows(ctx, module, "WRITE") and kind in bizbox.EDITABLE
    proposals = bizbox.changes(ctx.conn, kind, ext_ref)
    form = ""
    if can_edit:
        fields = "".join(f"<option value={f}>{bizbox.FIELD_WORDS[f]}</option>" for f in bizbox.EDITABLE[kind])
        form = (f"<form method=post action='/finance/{kind}/propose' class=grid2 style='margin-top:10px'>"
                f"<input type=hidden name=ref value='{t.esc(ext_ref)}'><input type=hidden name=area value='{area}'>"
                f"<div><label>Field</label><select name=field>{fields}</select></div>"
                "<div><label>New value</label><input name=new_value required maxlength=200 placeholder='e.g. Approved, or 2026-12-31'></div>"
                "<div style='grid-column:1/-1'><label>Why</label><input name=reason required maxlength=400 "
                "placeholder='What the person applying it in BizBox needs to know'></div>"
                "<div><button class=ghost type=submit>Propose the change</button></div></form>")
    changes_card = ("<div class=card><h3>" + t.icon("note") + "Changes to BizBox</h3><p class=why>BizBox is where this record "
                    "changes. A change proposed here is approved by a second person, then pushed to BizBox by its own "
                    "procedure once SQL01 has switched that on; until then it waits here, and BizBox itself has not changed.</p>"
                    + (_changes_table(ctx, proposals, with_record=False) if proposals else "") + form + "</div>"
                    if (can_edit or proposals) else "")
    from . import agreements as agreements_view
    extra = agreements_view.covering_card(ctx, kind, ext_ref) + extra + changes_card
    q = ctx.request.query
    body = ((f"<div class='banner ok'>{t.esc(q.get('msg', ''))}</div>" if q.get("msg") else "")
            + (f"<div class='banner err'>{t.esc(q.get('err', ''))}</div>" if q.get("err") else "")
            + f"<h1>{t.esc(ONE[kind])} {t.esc(ext_ref)}</h1><p class=sub>From BizBox, read-only"
            + ("" if rec["present"] else " · <b>no longer in BizBox</b>; kept because work links to it")
            + f" · synced {t.esc(rec['synced_at'])} · <a href='/{area}?tab={kind}'>"
            + t.esc(("Receiving" if kind == "invoice" else dict(TABS)[kind]) if area == "procurement" else dict(TABS)[kind]) + "</a>"
            + (f" · <span class='chip sla-warn'>{sum(1 for c in proposals if c['status'] == 'PENDING')} change(s) waiting for BizBox</span>"
               if any(c["status"] == "PENDING" for c in proposals) else "") + "</p>"
            + f"<div class=grid2><div class=card><dl class=kv>{facts}</dl></div>"
            + "<div class=card><h3>" + t.icon("note") + "Work linked to it</h3>"
            + (f"<ul class=plain>{''.join(links)}</ul>" if links else "<div class=muted>No ticket or project yet.</div>")
            + "</div></div>" + extra)
    return Response(body=t.page(ext_ref, body, user=ctx.user, active=area))


def ticket_card(ctx, tk, *, can_work: bool) -> str:
    """The Finance pod on a ticket: the BizBox records it concerns."""
    if not common.allows(ctx, "FINANCE"):
        return ""
    wid = t.esc(tk["work_item_id"])
    rows = bizbox.links(ctx.conn, "TICKET", tk["work_item_id"])
    can_link = can_work
    items = "".join(
        f"<li>{t.esc(ONE[r['kind']])} {_ref_link(r['kind'], r['ext_ref'])}"
        + (f" <span class=muted>{t.esc((r['record']['name'] if 'name' in r['record'].keys() else r['record'][list(r['record'].keys())[2]]) or '')}</span>" if r["record"] else "")
        + (f" <form method=post action='/ticket/{wid}/finance/unlink' style='display:inline'><input type=hidden name=kind value={r['kind']}>"
           f"<input type=hidden name=ext_ref value='{t.esc(r['ext_ref'])}'><button class='ghost small' type=submit title='Unlink'>×</button></form>"
           if can_link else "") + "</li>" for r in rows)
    add = ""
    if can_link:
        add = (f"<form method=post action='/ticket/{wid}/finance/link' class=row style='margin-top:6px'>"
               "<div style='flex:0 0 150px'><select name=kind aria-label='Kind'>"
               + "".join(f"<option value={k}>{ONE[k]}</option>" for k, _ in _mirror_tabs(ctx)) + "</select></div>"
               "<div><input name=ext_ref placeholder='PO, item or receiving number' aria-label='BizBox reference'></div>"
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


def propose(ctx, kind):
    from .. import redirect
    f = ctx.request.form()
    area = f.get("area", "finance") if f.get("area", "finance") in AREAS else "finance"
    common.require_module(ctx, "PROCUREMENT" if area == "procurement" else "FINANCE", "WRITE")
    ext_ref = f.get("ref", "")
    if kind not in bizbox.LINK_KIND or not ext_ref:
        return redirect(f"/{area}")
    back = _url(kind, ext_ref, area)
    try:
        cid = bizbox.propose(ctx.conn, kind, ext_ref, f.get("field", ""), f.get("new_value", ""), reason=f.get("reason", ""),
                             at=ctx.now, actor=ctx.user.id)
        ctx.conn.commit()
    except bizbox.Refused as exc:
        ctx.conn.rollback()
        return redirect(back + "&" + urllib.parse.urlencode({"err": f"Not proposed: {exc}"}))
    return redirect(back + "&" + urllib.parse.urlencode({"msg": f"Change #{cid} recorded. BizBox has not changed; it waits "
                                                                "for a second person's approval, then the push to BizBox."}))


def cancel_change(ctx, change_id):
    from .. import redirect
    common.require_module(ctx, "FINANCE", "WRITE")
    try:
        bizbox.decide(ctx.conn, int(change_id) if str(change_id).isdigit() else -1, "CANCELLED", at=ctx.now, actor=ctx.user.id)
        ctx.conn.commit()
    except bizbox.Refused as exc:
        return redirect("/finance?" + urllib.parse.urlencode({"tab": "changes", "err": str(exc)}))
    return redirect("/finance?" + urllib.parse.urlencode({"tab": "changes", "msg": f"Change #{change_id} cancelled"}))

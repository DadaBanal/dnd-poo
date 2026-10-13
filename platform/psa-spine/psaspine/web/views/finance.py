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

from ... import agreements, bizbox, security
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


def _cell(rec, field, area: str = "finance", labels: dict | None = None) -> str:
    v = rec[field]
    if field == "agreement_ref":
        return f"<td>{_ref_link('agreement', v, area)}</td>"
    if field in ("amount", "total", "unit_cost"):
        cur = rec["currency"] if "currency" in rec.keys() else None
        return f"<td class=num>{t.esc(_money(v, cur))}</td>"
    if labels and field in labels:
        return f"<td>{t.esc(bizbox.word(labels, field, v))}</td>"
    return f"<td>{t.esc(v or '')}</td>"


def medicine_card(ctx, kind: str, ext_ref: str) -> str:
    """An item that BizBox marks as a medicine shows its medicine facts, to a
    role with See on drugs and medicines (083)."""
    if kind != "product" or not common.allows(ctx, "PROC_DRUG"):
        return ""
    m = bizbox.medicine_of(ctx.conn, ext_ref)
    if m is None:
        return ""
    facts = "".join(f"<dt>{lab}</dt><dd>{t.esc(str(m[f]) if m[f] not in (None, '') else '—')}</dd>" for lab, f in (
        ("Generic name", "generic"), ("Dosage", "dosage"), ("Administration", "admin_group"), ("DOH reference", "doh_ref"),
        ("MIMS", "mims_ref"), ("Remarks", "remarks")))
    flag = "<span class='chip sla-bad'>Controlled drug</span>" if m["controlled"] else "<span class=chip>Not a controlled drug</span>"
    return f"<div class=card><h3>{t.icon('tag')}Medicine</h3><p>{flag}</p><dl class=kv>{facts}</dl></div>"


def module_for(kind: str, area: str) -> str:
    """The security module a record page answers to: Finance's, or, under the
    Procurement menu, the area the kind belongs to (13 Oct 2026)."""
    return security.PROCUREMENT_AREA_OF.get(kind, "PROC_PO") if area == "procurement" else "FINANCE"


def value_inputs(ctx, kind: str, fields: list, *, name: str = "new_value") -> str:
    """The "new value" control for a form whose field is chosen beside it: one
    dropdown per field that has BizBox's choices (named nv:<field>), and one
    text input for the rest. A script shows the one for the chosen field; the
    server reads nv:<field> first, so without the script the right one still
    wins (picked_value)."""
    out, first = [], fields[0] if fields else ""
    for f in fields:
        opts = bizbox.choices(ctx.conn, kind, f)
        if not opts:
            continue
        out.append(f"<select name='nv:{f}' data-for='{f}' aria-label='New {t.esc(bizbox.FIELD_WORDS.get(f, f).lower())}'"
                   f"{'' if f == first else ' hidden disabled'}>"
                   + "".join(f"<option value='{t.esc(c)}'>{t.esc(l)}</option>" for c, l in opts) + "</select>")
    has_first = any(f"data-for='{first}'" in x for x in out)
    out.append(f"<input name={name} maxlength=200 placeholder='the new value' data-for=''{' hidden disabled' if has_first else ' required'}>")
    return "".join(out)


def picked_value(form, field: str, *, name: str = "new_value") -> str:
    """The value a value_inputs form sent for the chosen field."""
    v = form.get(f"nv:{field}")
    return v if v is not None else form.get(name, "")


VALUE_PICK_SCRIPT = ("<script>(function(){document.querySelectorAll('form[data-valuepick]').forEach(function(fm){"
                     "var fs=fm.querySelector('select[name=field]');if(!fs)return;function pick(){var any=false;"
                     "fm.querySelectorAll('[data-for]').forEach(function(el){var on=el.getAttribute('data-for')===fs.value;"
                     "if(on)any=true;if(el.getAttribute('data-for')!==''){el.hidden=!on;el.disabled=!on}});"
                     "var tx=fm.querySelector(\"[data-for='']\");if(tx){tx.hidden=any;tx.disabled=any;tx.required=!any}}"
                     "fs.addEventListener('change',pick);pick()})})()</script>")


def _changes_table(ctx, rows, *, with_record: bool = True, pending_word: str = "Waiting for BizBox") -> str:
    """`pending_word`: what a PENDING change is waiting for. Inside a batch
    (080) that is its batch's word (approval first), not BizBox's."""
    can = common.allows(ctx, "FINANCE", "WRITE")
    back = {v: k for k, v in bizbox.LINK_KIND.items()}
    words = {"PENDING": pending_word, "APPLIED": "Applied in BizBox", "REJECTED": "Refused by BizBox",
             "CANCELLED": "Cancelled"}
    trs, labels = [], {}
    for c in rows:
        kind = back[c["kind"]]
        if kind not in labels:
            labels[kind] = bizbox.labels_for(ctx.conn, kind)
        rec = (f"<td>{ONE[kind]} {_ref_link(kind, c['ext_ref'])}</td>" if with_record else "")
        cancel = (f"<form method=post action='/finance/change/{c['change_id']}/cancel' class=inline>"
                  "<button class='ghost small' type=submit>Cancel</button></form>" if can and c["status"] == "PENDING" else "")
        trs.append(f"<tr><td>#{c['change_id']}</td>{rec}<td>{t.esc(bizbox.FIELD_WORDS.get(c['field'], c['field']))}</td>"
                   f"<td>{t.esc(bizbox.word(labels[kind], c['field'], c['old_value']) or '—')} → "
                   f"<b>{t.esc(bizbox.word(labels[kind], c['field'], c['new_value']) or '—')}</b></td>"
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
                   + "".join(f"<div class=tile><div class=l>{t.esc(bizbox.word(bizbox.labels_for(ctx.conn, kind), 'status', s['status']))}</div><div class=n>{s['n']}</div>"
                             f"<div class=muted>{t.esc(_money(s['total'] or 0, 'PHP'))}</div></div>"
                             for s in bizbox.summary(ctx.conn, kind, q=search, include_absent=absent))
                   + "</div>")
    trs = []
    labels = bizbox.labels_for(ctx.conn, kind)
    for r in rows:
        n = linked_cell(r["ext_ref"])
        cells = "".join(
            (f"<td>{_ref_link(kind, r['ext_ref'])}"
             + ("" if r["present"] else " <span class=pill>gone from BizBox</span>") + "</td>")
            if f == "ext_ref" else _cell(r, f, labels=labels) for f, _ in columns)
        trs.append(f"<tr>{cells}<td>{n}</td></tr>")
    first, last = (page_no - 1) * bizbox.PAGE + 1, min(page_no * bizbox.PAGE, total_n)
    keep = {"tab": kind, "q": search} | ({"absent": "1"} if absent else {})
    pager = (f"<div class='row schedbar' style='justify-content:space-between'><div class=muted>Showing {first}–{last} of {total_n}</div><div>"
             + (f"<a class='ghost small' href='/finance?{urllib.parse.urlencode(keep | {'page': page_no - 1})}'>‹ Previous</a> " if page_no > 1 else "")
             + (f"<a class='ghost small' href='/finance?{urllib.parse.urlencode(keep | {'page': page_no + 1})}'>Next ›</a>" if last < total_n else "")
             + "</div></div>") if total_n > bizbox.PAGE else ""
    st = bizbox.status(ctx.conn)
    sync = (f"Read from BizBox {t.esc(st['last_sync_at'])} by {t.esc(st['last_sync_by'])}{t.esc(bizbox.read_words(st['last_result']))}"
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
    from .. import HttpError
    common.require_module(ctx, module_for(kind, area))
    ext_ref = ctx.request.query.get("ref", "")
    if kind not in bizbox.LINK_KIND or not ext_ref:
        raise HttpError("404 Not Found", "No such record.")
    return _detail(ctx, kind, area, ext_ref)


def _edit_control(ctx, kind: str, field: str, how: str, current, shown=None) -> str:
    """The record's own field as a control, prefilled: BizBox's list as a
    dropdown, a date box, a number, or text (Dada, 13 Oct 2026: "the edit
    should be on the item itself"). `current` is BizBox's value (kept on the
    control as data-was); `shown` is what the person had typed when the page
    comes back from the review window, else the same."""
    cur = "" if current is None else (f"{float(current):g}" if how == "money" else str(current))
    val = cur if shown is None else str(shown)
    name = f"e:{field}"
    opts = bizbox.choices(ctx.conn, kind, field)
    if opts:
        options = "".join(f"<option value='{t.esc(c)}'{' selected' if c == val else ''}>{t.esc(l)}</option>" for c, l in opts)
        if cur and cur not in {c for c, _ in opts}:
            options = f"<option value='{t.esc(cur)}'{' selected' if cur == val else ''}>{t.esc(cur)} (as in BizBox)</option>" + options
        return f"<select name='{name}' data-was='{t.esc(cur)}' aria-label='{t.esc(bizbox.FIELD_WORDS.get(field, field))}'>{options}</select>"
    if how == "date":
        return f"<input type=date name='{name}' value='{t.esc(val)}' data-was='{t.esc(cur)}'>"
    if how == "money":
        return f"<input type=number step=any min=0 name='{name}' value='{t.esc(val)}' data-was='{t.esc(cur)}'>"
    return f"<input name='{name}' value='{t.esc(val)}' data-was='{t.esc(cur)}' maxlength=400>"


def review_dialog(title: str, preview: dict, *, action: str, hidden: list, show_ref: bool = False) -> str:
    """The window that says what will change before anything is sent for
    approval (Dada, 13 Oct 2026): one line per change, from -> to in BizBox's
    words, the reason, and two ways out. "Send" posts the hidden copy of the
    change to `action`; "Go back" closes the window natively (method=dialog),
    leaving the form underneath as the person filled it. Modal when scripts
    run; still usable when they do not."""
    rows = "".join("<tr>" + (f"<td>{t.esc(r['ref'])}</td>" if show_ref else "")
                   + f"<td>{t.esc(r['word'])}</td><td>{t.esc(r['old_word'])}</td><td aria-hidden=true>→</td><td><b>{t.esc(r['new_word'])}</b></td></tr>"
                   for r in preview["rows"])
    head = ("<th>Record</th>" if show_ref else "") + "<th>Field</th><th>Now in BizBox</th><th><span class=sr-only>becomes</span></th><th>After</th>"
    n = preview["same"]
    same = (f"<p class=muted>{n} {'is' if n == 1 else 'are'} already so in BizBox and {'stays' if n == 1 else 'stay'} as "
            f"{'it is' if n == 1 else 'they are'}.</p>" if n else "")
    fields = "".join(f"<input type=hidden name='{t.esc(k)}' value='{t.esc(v)}'>" for k, v in hidden)
    return (f"<dialog open class=review aria-labelledby=review-title><h2 id=review-title>{t.icon('checks')}{t.esc(title)}</h2>"
            f"<div class=tablewrap><table class=compact><thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table></div>" + same
            + f"<p><b>Why:</b> {t.esc(preview['reason'])}</p>"
            "<p class=why>Sending it queues the change for a second person to approve. BizBox itself changes only after that, "
            "when the approved change is pushed.</p>"
            f"<div class=acts><form method=post action='{action}'>{fields}<button type=submit>{t.icon('check')} Send for approval</button></form>"
            "<form method=dialog><button class=ghost type=submit>Go back and change it</button></form></div></dialog>"
            "<script>(function(){var d=document.querySelector('dialog.review');if(d&&d.showModal){d.removeAttribute('open');d.showModal()}})()</script>")


def _review_dialog(kind: str, area: str, ext_ref: str, preview: dict, *, action: str, hidden: list) -> str:
    return review_dialog(f"What will change on {ext_ref}", preview, action=action, hidden=hidden)


def _detail(ctx, kind, area, ext_ref, *, dialog: str = "", err: str = "", posted: dict | None = None):
    from .. import HttpError, Response
    rec = bizbox.get(ctx.conn, kind, ext_ref)
    if rec is None:
        raise HttpError("404 Not Found", "No such record in the BizBox mirror.")
    labels = bizbox.labels_for(ctx.conn, kind)

    def fact(f):
        if f == "agreement_ref":
            return _ref_link("agreement", rec[f], area) or "—"
        if f in ("amount", "total", "unit_cost"):
            return t.esc(_money(rec[f], rec["currency"] if "currency" in rec.keys() else None))
        if f in labels:
            return t.esc(bizbox.word(labels, f, rec[f]) or "—")
        return t.esc(rec[f] or "—")
    can_edit = common.allows(ctx, module_for(kind, area), "WRITE") and kind in bizbox.EDITABLE and bool(rec["present"])
    editable = bizbox.EDITABLE.get(kind, {}) if can_edit else {}
    posted = posted or {}
    facts = "".join(
        f"<dt>{t.esc(lab)}</dt><dd>"
        + (_edit_control(ctx, kind, f, editable[f], rec[f], posted.get(f"e:{f}")) if f in editable else fact(f))
        + "</dd>" for f, lab in _columns(ctx, kind))
    if can_edit:
        q0 = ctx.request.query
        facts = (f"<form method=post action='/finance/{kind}/review' class=fields data-record{' aria-describedby=flash-err' if (err or q0.get('err')) else ''}>"
                 f"<input type=hidden name=ref value='{t.esc(ext_ref)}'><input type=hidden name=area value='{area}'>"
                 f"<dl class=kv>{facts}</dl>"
                 f"<div style='margin-top:10px'><label>Why</label><input name=reason maxlength=400 value='{t.esc(posted.get('reason', ''))}' "
                 "placeholder='What the approver and BizBox need to know' required></div>"
                 f"<div style='margin-top:10px'><button type=submit>{t.icon('checks')} Review changes</button> "
                 "<span class=muted>Change the fields above; the window shows what will change before it is sent.</span></div></form>")
    else:
        facts = f"<dl class=kv>{facts}</dl>"
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
    proposals = bizbox.changes(ctx.conn, kind, ext_ref)
    changes_card = ("<div class=card><h3>" + t.icon("note") + "Changes waiting for BizBox</h3><p class=why>A change sent from "
                    "this page is approved by a second person, then pushed to BizBox once that link is switched on; until "
                    "then it waits here, and BizBox itself has not changed.</p>"
                    + _changes_table(ctx, proposals, with_record=False) + "</div>" if proposals else "")
    from . import agreements as agreements_view
    extra = agreements_view.covering_card(ctx, kind, ext_ref) + medicine_card(ctx, kind, ext_ref) + extra + changes_card
    q = ctx.request.query
    body = ((f"<div class='banner ok' id=flash-ok role=status aria-live=polite>{t.esc(q.get('msg', ''))}</div>" if q.get("msg") else "")
            + (f"<div class='banner err' id=flash-err role=alert>{t.esc(err or q.get('err', ''))}</div>" if (err or q.get("err")) else "")
            + dialog
            + f"<h1>{t.esc(ONE[kind])} {t.esc(ext_ref)}</h1><p class=sub>From BizBox" + (", changed from here" if can_edit else ", read-only")
            + ("" if rec["present"] else " · <b>no longer in BizBox</b>; kept because work links to it")
            + f" · synced {t.esc(rec['synced_at'])} · <a href='/{area}?tab={kind}'>"
            + t.esc(("Receiving" if kind == "invoice" else dict(TABS)[kind]) if area == "procurement" else dict(TABS)[kind]) + "</a>"
            + (f" · <span class='chip sla-warn'>{sum(1 for c in proposals if c['status'] == 'PENDING')} change(s) waiting for BizBox</span>"
               if any(c["status"] == "PENDING" for c in proposals) else "") + "</p>"
            + f"<div class=grid2><div class=card>{facts}</div>"
            + "<div class=card><h3>" + t.icon("note") + "Work linked to it</h3>"
            + (f"<ul class=plain>{''.join(links)}</ul>" if links else "<div class=muted>No ticket or project yet.</div>")
            + "</div></div>" + extra)
    return Response(body=t.page(ext_ref, body, user=ctx.user, active=area))


def _posted_edits(f, kind: str) -> list:
    return [(f.get("ref", ""), key[2:], f.get(key, "")) for key in f.keys() if key.startswith("e:") and key[2:] in bizbox.EDITABLE.get(kind, {})]


def review(ctx, kind):
    """POST: the record's form, checked, shown back with the window that
    says what will change. Nothing is queued yet."""
    from .. import HttpError, redirect
    f = ctx.request.form()
    area = f.get("area", "finance") if f.get("area", "finance") in AREAS else "finance"
    common.require_module(ctx, module_for(kind, area), "WRITE")
    ext_ref = f.get("ref", "")
    if kind not in bizbox.LINK_KIND or not ext_ref:
        raise HttpError("404 Not Found", "No such record.")
    edits = _posted_edits(f, kind)
    try:
        preview = bizbox.preview_edits(ctx.conn, kind, edits, reason=f.get("reason", ""))
    except bizbox.Refused as exc:
        return _detail(ctx, kind, area, ext_ref, err=f"Not sent: {exc}", posted=dict(f))
    if not preview["rows"]:
        return _detail(ctx, kind, area, ext_ref, err="Nothing is changed: every field still reads what BizBox has.", posted=dict(f))
    hidden = [("ref", ext_ref), ("area", area), ("reason", preview["reason"])] + [(f"e:{r['field']}", "" if r["new"] is None else str(r["new"])) for r in preview["rows"]]
    dialog = _review_dialog(kind, area, ext_ref, preview | {"same": 0}, action=f"/finance/{kind}/send", hidden=hidden)   # every field was posted: "left as they are" is noise here
    return _detail(ctx, kind, area, ext_ref, dialog=dialog, posted=dict(f))


def send(ctx, kind):
    """POST from the review window: queue the batch for approval."""
    from .. import redirect
    f = ctx.request.form()
    area = f.get("area", "finance") if f.get("area", "finance") in AREAS else "finance"
    common.require_module(ctx, module_for(kind, area), "WRITE")
    ext_ref = f.get("ref", "")
    if kind not in bizbox.LINK_KIND or not ext_ref:
        return redirect(f"/{area}")
    back = _url(kind, ext_ref, area)
    try:
        out = bizbox.propose_edits(ctx.conn, kind, _posted_edits(f, kind), reason=f.get("reason", ""), at=ctx.now, actor=ctx.user.id)
        ctx.conn.commit()
    except bizbox.Refused as exc:
        ctx.conn.rollback()
        return redirect(back + ("&" if "?" in back else "?") + urllib.parse.urlencode({"err": f"Not sent: {exc}"}))
    return redirect(back + ("&" if "?" in back else "?") + urllib.parse.urlencode(
        {"msg": f"Batch #{out['batch_id']} sent for approval: {out['queued']} change(s). BizBox has not changed yet."}))


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
    common.require_module(ctx, module_for(kind, area), "WRITE")
    ext_ref = f.get("ref", "")
    if kind not in bizbox.LINK_KIND or not ext_ref:
        return redirect(f"/{area}")
    back = _url(kind, ext_ref, area)
    try:
        cid = bizbox.propose(ctx.conn, kind, ext_ref, f.get("field", ""), picked_value(f, f.get("field", "")), reason=f.get("reason", ""),
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

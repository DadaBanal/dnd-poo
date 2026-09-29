"""Agreements: made on the desk, covering what BizBox holds (045).

Finance › Agreements is the desk's own list (BizBox holds none). An
agreement's page edits it and names the mirrored invoices, purchase orders and
products it covers, with their totals. Gated by the security role's FINANCE
level: READ to look, WRITE to create, edit or cover. Which roles have WRITE is
set in Setup › Security roles; that is Dada's decision, not this file's.
Nothing here writes to the mirror or to BizBox.
"""
from __future__ import annotations

import urllib.parse

from ... import agreements, bizbox
from .. import templates as t
from . import common
from . import finance as finance_view

CHIP = {"DRAFT": "", "ACTIVE": "sla-ok", "INACTIVE": "", "CANCELLED": "sla-bad"}
FIND_LIMIT = 10


def _back(path: str, **q):
    from .. import redirect
    q = {k: v for k, v in q.items() if v}
    return redirect(path + ("?" + urllib.parse.urlencode(q) if q else ""))


def _load(ctx, agreement_id):
    from .. import HttpError
    row = agreements.get(ctx.conn, agreement_id)
    if row is None:
        raise HttpError("404 Not Found", "No such agreement.")
    return row


def _chip(status: str) -> str:
    return f"<span class='chip {CHIP.get(status, '')}'>{t.esc(agreements.STATUSES.get(status, status))}</span>"


def _term(row) -> str:
    return t.esc(f"{row['starts_on'] or '…'} → {row['ends_on'] or '…'}" if (row["starts_on"] or row["ends_on"]) else "")


def _mirror_kinds(ctx) -> list[str]:
    """The mirror kinds an agreement can cover and that BizBox has rows for."""
    on = set(bizbox.present_kinds(ctx.conn))
    return [k for k in agreements.COVERS if k in on]


# ------------------------------------------------------------ the tab

def tab(ctx):
    """Finance › Agreements: the desk's agreements (and, below, any a BizBox
    source has ever provided, read-only, if one is ever named)."""
    from .. import Response
    common.require_module(ctx, "FINANCE")
    q = ctx.request.query
    status = q.get("status", "") if q.get("status", "") in agreements.STATUSES else ""
    search = q.get("q", "")
    rows = agreements.all_(ctx.conn, status=status or None, q=search)
    can = common.allows(ctx, "FINANCE", "WRITE")
    trs = "".join(
        f"<tr><td><a href='/agreement/{t.esc(r['agreement_id'])}'>{t.esc(r['agreement_id'])}</a></td><td><b>{t.esc(r['name'])}</b></td>"
        f"<td>{t.esc(r['party'] or '')}</td><td>{_term(r)}</td><td>{_chip(r['status'])}</td>"
        f"<td class=num>{t.esc(finance_view._money(r['amount'], r['currency']))}</td><td class=center>{r['items']}</td></tr>"
        for r in rows)
    opts = "<option value=''>Every status</option>" + "".join(
        f"<option value='{k}'{' selected' if k == status else ''}>{v}</option>" for k, v in agreements.STATUSES.items())
    new = ""
    if can:
        new = ("<div class=card><h3>" + t.icon("plus") + "New agreement</h3><p class=why>An agreement is the desk's own "
               "record: BizBox holds no supplier agreements. Once it exists, open it and add the BizBox invoices, purchase "
               "orders and products it covers.</p><form method=post action='/agreements/new' class=grid2>"
               "<div><label>Name</label><input name=name required maxlength=200 placeholder='Printer care, ward 3, 2026'></div>"
               "<div><label>Party</label><input name=party maxlength=200 placeholder='The supplier, as BizBox names it'></div>"
               "<div><label>Starts</label><input type=date name=starts_on></div><div><label>Ends</label><input type=date name=ends_on></div>"
               "<div><label>Amount</label><input name=amount inputmode=decimal placeholder='120000'></div>"
               "<div><label>Currency</label><input name=currency maxlength=8 value=PHP></div>"
               "<div style='grid-column:1/-1'><label>Notes</label><textarea name=notes></textarea></div>"
               "<div><button type=submit>Create</button></div></form></div>")
    mirrored = ""
    if bizbox.count(ctx.conn, "agreement"):
        mirrored = ("<div class=card><h3>" + t.icon("tag") + "From BizBox</h3><p class=why>A source named agreements; these "
                    "are mirrored read-only, as the other kinds are.</p><ul class=plain>"
                    + "".join(f"<li>{finance_view._ref_link('agreement', r['ext_ref'])} {t.esc(r['name'])}</li>"
                              for r in bizbox.records(ctx.conn, "agreement")) + "</ul></div>")
    body = ((f"<div class='banner ok'>{t.esc(q.get('msg', ''))}</div>" if q.get("msg") else "")
            + (f"<div class='banner err'>{t.esc(q.get('err', ''))}</div>" if q.get("err") else "")
            + "<h1>Finance</h1><p class=sub>Agreements are made and kept here, since BizBox holds none. From an agreement, "
              "add the BizBox invoices, purchase orders and products it covers; those stay BizBox's, mirrored read-only.</p>"
            + finance_view._tabs(ctx, "agreement")
            + "<div class=card><form method=get action='/finance' class='row schedbar'><input type=hidden name=tab value=agreement>"
              f"<div style='flex:1 1 260px'><input name=q value='{t.esc(search)}' placeholder='Search agreements'></div>"
              f"<div style='flex:0 0 180px'><select name=status>{opts}</select></div>"
              "<div style='flex:0 0 auto'><button class=ghost type=submit>Search</button></div></form>"
              "<div class=tablewrap><table><thead><tr><th>Agreement</th><th>Name</th><th>Party</th><th>Term</th><th>Status</th>"
              "<th class=num>Amount</th><th>Covers</th></tr></thead><tbody>"
            + (trs or "<tr><td colspan=7 class=muted>No agreement yet.</td></tr>") + "</tbody></table></div></div>"
            + new + mirrored)
    return Response(body=t.page("Finance", body, user=ctx.user, active="finance"))


def create(ctx):
    common.require_module(ctx, "FINANCE", "WRITE")
    f = ctx.request.form()
    try:
        aid = agreements.create(ctx.conn, name=f.get("name", ""), party=f.get("party"), starts_on=f.get("starts_on"),
                                ends_on=f.get("ends_on"), amount=f.get("amount"), currency=f.get("currency"),
                                notes=f.get("notes"), at=ctx.now, actor=ctx.user.id)
        ctx.conn.commit()
    except agreements.Refused as exc:
        ctx.conn.rollback()
        return _back("/finance", tab="agreement", err=str(exc))
    return _back(f"/agreement/{aid}", msg=f"{aid} created. Now add what it covers.")


# ------------------------------------------------------------ one agreement

def detail(ctx, agreement_id):
    from .. import Response
    common.require_module(ctx, "FINANCE")
    a = _load(ctx, agreement_id)
    q = ctx.request.query
    can = common.allows(ctx, "FINANCE", "WRITE")
    aid = t.esc(a["agreement_id"])
    items = agreements.items(ctx.conn, a["agreement_id"])
    totals = agreements.totals(ctx.conn, a["agreement_id"])
    tiles = ("<div class='tiles' style='grid-template-columns:repeat(auto-fit,minmax(150px,1fr));margin-bottom:12px'>"
             + "".join(f"<div class=tile><div class=l>{t.esc(agreements.WORDS[w])}</div><div class=n>{v['n']}</div>"
                       + (f"<div class=muted>{t.esc(finance_view._money(v['total'], a['currency'] or 'PHP'))}</div>" if v["total"] is not None else "")
                       + "</div>" for w, v in totals.items())
             + (f"<div class=tile><div class=l>Agreed amount</div><div class=n>{t.esc(finance_view._money(a['amount'], a['currency']))}</div></div>"
                if a["amount"] is not None else "") + "</div>")

    def describe(it) -> str:
        r = it["record"]
        if r is None:
            return "<span class=muted>not in the mirror</span>"
        k = it["mirror_kind"]
        if k == "invoice":
            return f"{t.esc(r['party'] or '')} · {t.esc(r['invoiced_on'] or '')} · {t.esc(r['status'] or '')}"
        if k == "purchase_order":
            return f"{t.esc(r['vendor'] or '')} · {t.esc(r['ordered_on'] or '')} · {t.esc(r['status'] or '')}"
        return f"{t.esc(r['name'] or '')} · {t.esc(r['category'] or '')}"

    def money(it) -> str:
        r = it["record"]
        if r is None:
            return ""
        if it["mirror_kind"] == "product":
            return t.esc(finance_view._money(r["unit_cost"])) + (" / " + t.esc(r["unit"]) if r["unit"] else "")
        return t.esc(finance_view._money(r["total"], r["currency"]))
    trs = "".join(
        f"<tr><td>{t.esc(finance_view.ONE[it['mirror_kind']])}</td><td>{finance_view._ref_link(it['mirror_kind'], it['ext_ref'])}"
        + ("" if it["present"] else " <span class=pill>gone from BizBox</span>") + f"</td><td>{describe(it)}</td>"
        f"<td class=num>{money(it)}</td><td>{t.esc(it['note'] or '')}</td><td class=muted>{t.esc(it['added_at'])} · {t.esc(it['added_by'])}</td>"
        + (f"<td><form method=post action='/agreement/{aid}/item/remove' class=inline><input type=hidden name=kind value={it['mirror_kind']}>"
           f"<input type=hidden name=ext_ref value='{t.esc(it['ext_ref'])}'><button class='ghost small' type=submit title='Remove'>×</button></form></td>"
           if can else "<td></td>") + "</tr>" for it in items)
    covered = ("<div class=card><h3>" + t.icon("tag") + "What it covers</h3>" + tiles
               + "<div class=tablewrap><table><thead><tr><th>Kind</th><th>BizBox record</th><th></th><th class=num>Amount</th>"
                 "<th>Note</th><th>Added</th><th></th></tr></thead><tbody>"
               + (trs or "<tr><td colspan=7 class=muted>Nothing yet. Add the invoices, purchase orders and products this agreement covers.</td></tr>")
               + "</tbody></table></div>")
    if can and a["status"] != "CANCELLED":
        kinds = _mirror_kinds(ctx)
        if kinds:
            find_kind = q.get("find", "") if q.get("find", "") in kinds else kinds[0]
            found = ""
            if q.get("fq"):
                hits = bizbox.records(ctx.conn, find_kind, q=q["fq"], limit=FIND_LIMIT)
                have = {(it["mirror_kind"], it["ext_ref"]) for it in items}
                found = ("<div class=tablewrap style='margin-top:8px'><table class=compact><tbody>" + "".join(
                    f"<tr><td>{finance_view._ref_link(find_kind, h['ext_ref'])}</td>"
                    f"<td>{t.esc(h['name'] if 'name' in h.keys() else (h['vendor'] if 'vendor' in h.keys() else h['party']) or '')}</td>"
                    + (f"<td class=num>{t.esc(finance_view._money(h['total'], h['currency']))}</td>" if "total" in h.keys() else "<td></td>")
                    + ("<td class=muted>covered</td>" if (find_kind, h["ext_ref"]) in have else
                       f"<td><form method=post action='/agreement/{aid}/item' class=inline><input type=hidden name=kind value={find_kind}>"
                       f"<input type=hidden name=ext_ref value='{t.esc(h['ext_ref'])}'><button class='ghost small' type=submit>Add</button></form></td>")
                    + "</tr>" for h in hits) + "</tbody></table></div>"
                    if hits else "<div class=muted style='margin-top:8px'>Nothing in the mirror matches.</div>")
            kind_opts = "".join(f"<option value={k}{' selected' if k == find_kind else ''}>{finance_view.ONE[k]}</option>" for k in kinds)
            covered += ("<div class=grid2 style='margin-top:12px'>"
                        f"<form method=post action='/agreement/{aid}/item' class=row><div style='flex:0 0 150px'><label>Kind</label>"
                        f"<select name=kind aria-label='Kind'>{kind_opts}</select></div>"
                        "<div><label>BizBox number</label><input name=ext_ref required placeholder='Receiving, PO or item number'></div>"
                        "<div><label>Note</label><input name=note maxlength=400 placeholder='optional'></div>"
                        "<div style='flex:0 0 auto;align-self:end'><button class=ghost type=submit>Add</button></div></form>"
                        f"<form method=get action='/agreement/{aid}' class=row><div style='flex:0 0 150px'><label>Find in BizBox</label>"
                        f"<select name=find aria-label='Kind'>{kind_opts}</select></div>"
                        f"<div><label>Search</label><input name=fq value='{t.esc(q.get('fq', ''))}' placeholder='vendor, item or number'></div>"
                        "<div style='flex:0 0 auto;align-self:end'><button class=ghost type=submit>Find</button></div></form></div>" + found)
        else:
            covered += "<p class=muted style='margin-top:10px'>The BizBox mirror is empty; there is nothing to cover until the first sync.</p>"
    covered += "</div>"
    facts = ("<div class=card><dl class=kv>"
             f"<dt>Name</dt><dd>{t.esc(a['name'])}</dd><dt>Party</dt><dd>{t.esc(a['party'] or '—')}</dd>"
             f"<dt>Term</dt><dd>{_term(a) or '—'}</dd><dt>Status</dt><dd>{_chip(a['status'])}</dd>"
             f"<dt>Amount</dt><dd>{t.esc(finance_view._money(a['amount'], a['currency']) or '—')}</dd>"
             f"<dt>Notes</dt><dd>{t.esc(a['notes'] or '—')}</dd>"
             f"<dt>Created</dt><dd>{t.esc(a['created_at'])} · {t.esc(a['created_by'])}</dd>"
             f"<dt>Updated</dt><dd>{t.esc(a['updated_at'])} · {t.esc(a['updated_by'])}</dd></dl></div>")
    forms = ""
    if can:
        nxt = {"DRAFT": [("ACTIVE", "Make active"), ("CANCELLED", "Cancel")],
               "ACTIVE": [("INACTIVE", "Make inactive"), ("CANCELLED", "Cancel")],
               "INACTIVE": [("ACTIVE", "Make active"), ("CANCELLED", "Cancel")],
               "CANCELLED": [("DRAFT", "Reopen as draft")]}[a["status"]]
        acts = "".join(f"<form method=post action='/agreement/{aid}/status' class=inline><input type=hidden name=status value={s}>"
                       f"<button class='ghost{' danger' if s == 'CANCELLED' else ''}' type=submit>{w}</button></form>" for s, w in nxt)
        forms = ("<div class=card><h3>" + t.icon("setup") + "Edit</h3>"
                 f"<div class='row schedbar'>{acts}</div>"
                 f"<form method=post action='/agreement/{aid}/update' class=grid2>"
                 f"<div><label>Name</label><input name=name required maxlength=200 value='{t.esc(a['name'])}'></div>"
                 f"<div><label>Party</label><input name=party maxlength=200 value='{t.esc(a['party'] or '')}'></div>"
                 f"<div><label>Starts</label><input type=date name=starts_on value='{t.esc(a['starts_on'] or '')}'></div>"
                 f"<div><label>Ends</label><input type=date name=ends_on value='{t.esc(a['ends_on'] or '')}'></div>"
                 f"<div><label>Amount</label><input name=amount inputmode=decimal value='{t.esc(a['amount'] if a['amount'] is not None else '')}'></div>"
                 f"<div><label>Currency</label><input name=currency maxlength=8 value='{t.esc(a['currency'] or '')}'></div>"
                 f"<div style='grid-column:1/-1'><label>Notes</label><textarea name=notes>{t.esc(a['notes'] or '')}</textarea></div>"
                 "<div><button class=ghost type=submit>Save</button></div></form></div>")
    body = ((f"<div class='banner ok'>{t.esc(q.get('msg', ''))}</div>" if q.get("msg") else "")
            + (f"<div class='banner err'>{t.esc(q.get('err', ''))}</div>" if q.get("err") else "")
            + f"<h1>{t.esc(a['name'])}</h1><p class=sub>{aid} · {_chip(a['status'])} · agreement kept on the desk · "
              "<a href='/finance?tab=agreement'>Agreements</a></p>"
            + f"<div class=grid2>{facts}{forms or ''}</div>" + covered)
    return Response(body=t.page(a["name"], body, user=ctx.user, active="finance"))


def _try(ctx, agreement_id, fn, ok, *, back: str | None = None):
    common.require_module(ctx, "FINANCE", "WRITE")
    _load(ctx, agreement_id)
    where = back if back and back.startswith(("/finance", "/agreement/")) and "\n" not in back else f"/agreement/{agreement_id}"
    try:
        r = fn()
        ctx.conn.commit()
    except (agreements.Refused, bizbox.Refused) as exc:
        ctx.conn.rollback()
        return _back(where, err=str(exc))
    return _back(where, msg=ok(r))


def update(ctx, agreement_id):
    f = ctx.request.form()
    fields = {k: f.get(k, "") for k in ("name", "party", "starts_on", "ends_on", "amount", "currency", "notes")}
    return _try(ctx, agreement_id, lambda: agreements.update(ctx.conn, agreement_id, at=ctx.now, actor=ctx.user.id, **fields),
                lambda w: "Saved" if w == "nothing changed" else f"Saved: {w}")


def set_status(ctx, agreement_id):
    f = ctx.request.form()
    return _try(ctx, agreement_id, lambda: agreements.set_status(ctx.conn, agreement_id, f.get("status", ""), at=ctx.now, actor=ctx.user.id),
                lambda w: f"Now {agreements.STATUSES.get(f.get('status', ''), '').lower()}")


def item_add(ctx, agreement_id):
    f = ctx.request.form()
    return _try(ctx, agreement_id, lambda: agreements.add_item(ctx.conn, agreement_id, f.get("kind", ""), f.get("ext_ref", ""),
                                                               note=f.get("note"), at=ctx.now, actor=ctx.user.id),
                lambda added: f"{f.get('ext_ref', '').strip()} is now covered" if added else f"{f.get('ext_ref', '').strip()} was already covered",
                back=f.get("back"))


def item_remove(ctx, agreement_id):
    f = ctx.request.form()
    return _try(ctx, agreement_id, lambda: agreements.remove_item(ctx.conn, agreement_id, f.get("kind", ""), f.get("ext_ref", ""),
                                                                  at=ctx.now, actor=ctx.user.id),
                lambda removed: "Removed" if removed else "It was not covered", back=f.get("back"))


def covering_card(ctx, kind: str, ext_ref: str) -> str:
    """On a mirrored record's page: the agreements that cover it, and a way to
    add it to one (Finance WRITE)."""
    if kind not in agreements.COVERS:
        return ""
    rows = agreements.covering(ctx.conn, kind, ext_ref)
    items = "".join(f"<li><a href='/agreement/{t.esc(r['agreement_id'])}'>{t.esc(r['agreement_id'])}</a> {t.esc(r['name'])} {_chip(r['status'])}</li>"
                    for r in rows)
    add = ""
    if common.allows(ctx, "FINANCE", "WRITE"):
        have = {r["agreement_id"] for r in rows}
        opts = "".join(f"<option value='{t.esc(a['agreement_id'])}'>{t.esc(a['agreement_id'])} {t.esc(a['name'])}</option>"
                       for a in agreements.all_(ctx.conn) if a["status"] != "CANCELLED" and a["agreement_id"] not in have)
        if opts:
            add = (f"<form method=post class=row style='margin-top:6px' data-agreement-add onsubmit=\"this.action='/agreement/'+this.agreement_id.value+'/item'\">"
                   f"<input type=hidden name=kind value={kind}><input type=hidden name=ext_ref value='{t.esc(ext_ref)}'>"
                   f"<input type=hidden name=back value='{t.esc(finance_view._url(kind, ext_ref))}'>"
                   f"<div><select name=agreement_id aria-label='Agreement'>{opts}</select></div>"
                   "<div style='flex:0 0 auto'><button class=ghost type=submit>Add to agreement</button></div></form>")
    return ("<div class=card><h3>" + t.icon("tag") + "Agreements</h3>"
            + (f"<ul class=plain>{items}</ul>" if items else "<div class=muted>Not covered by an agreement.</div>") + add + "</div>")

"""Sales: opportunities and quotes (052).

The desk's pipeline: what Dada IT has proposed to a department or a company,
at which stage, and the quotes under each. A won opportunity drafts an
agreement (045) so the work it brings is covered from day one. Gated by the
security role's FINANCE level, as agreements are: READ to look, WRITE to
create, edit, quote and move. Nothing here touches BizBox.
"""
from __future__ import annotations

import urllib.parse

from ... import sales
from .. import templates as t
from . import common
from . import finance as finance_view

STAGE_CHIP = {"LEAD": "", "QUALIFIED": "sla-warn", "PROPOSAL": "sla-warn", "WON": "sla-ok", "LOST": "sla-bad"}
QUOTE_CHIP = {"DRAFT": "", "SENT": "sla-warn", "ACCEPTED": "sla-ok", "DECLINED": "sla-bad", "EXPIRED": "sla-bad"}
CURRENCY = "PHP"


def _back(path: str, **q):
    from .. import redirect
    q = {k: v for k, v in q.items() if v}
    return redirect(path + ("?" + urllib.parse.urlencode(q) if q else ""))


def _opp(ctx, opportunity_id):
    from .. import HttpError
    row = sales.get(ctx.conn, opportunity_id)
    if row is None:
        raise HttpError("404 Not Found", "No such opportunity.")
    return row


def _quote(ctx, quote_id):
    from .. import HttpError
    row = sales.quote(ctx.conn, quote_id)
    if row is None:
        raise HttpError("404 Not Found", "No such quote.")
    return row


def _stage_chip(stage: str) -> str:
    return f"<span class='chip {STAGE_CHIP.get(stage, '')}'>{t.esc(sales.STAGES.get(stage, stage))}</span>"


def _quote_chip(status: str) -> str:
    return f"<span class='chip {QUOTE_CHIP.get(status, '')}'>{t.esc(sales.QUOTE_STATUSES.get(status, status))}</span>"


def _plain(v) -> str:
    """A number for an input box: 1080000, or 1.5, never 1.08e+06."""
    if v is None:
        return ""
    v = float(v)
    return f"{v:.0f}" if v == int(v) else f"{v:.4f}".rstrip("0")


def _money(v, cur=None) -> str:
    return t.esc(finance_view._money(v, cur or CURRENCY))


def _banners(q) -> str:
    return ((f"<div class='banner ok'>{t.esc(q.get('msg', ''))}</div>" if q.get("msg") else "")
            + (f"<div class='banner err'>{t.esc(q.get('err', ''))}</div>" if q.get("err") else ""))


def _entity_options(ctx, selected=None) -> str:
    rows = ctx.conn.execute("SELECT entity_id, name FROM entity ORDER BY name").fetchall()
    return "<option value=''>—</option>" + "".join(
        f"<option value='{t.esc(r['entity_id'])}'{' selected' if r['entity_id'] == selected else ''}>{t.esc(r['name'])}</option>"
        for r in rows)


def _contact_options(ctx, entity_id, selected=None) -> str:
    if not entity_id:
        return "<option value=''>— pick a company first —</option>"
    rows = ctx.conn.execute("SELECT contact_id, display_name FROM contact WHERE entity_id = ? ORDER BY display_name",
                            (entity_id,)).fetchall()
    return "<option value=''>—</option>" + "".join(
        f"<option value='{t.esc(r['contact_id'])}'{' selected' if r['contact_id'] == selected else ''}>{t.esc(r['display_name'])}</option>"
        for r in rows)


# ------------------------------------------------------------ the pipeline

def index(ctx):
    from .. import Response
    common.require_module(ctx, "FINANCE")
    q = ctx.request.query
    stage = q.get("stage", "")
    if stage not in sales.STAGES and stage != "OPEN":
        stage = "OPEN" if not q.get("stage") else ""
    search = q.get("q", "")
    can = common.allows(ctx, "FINANCE", "WRITE")
    tiles = "".join(
        f"<a class=tile href='/sales?{urllib.parse.urlencode({'stage': p['stage']})}'><div class=l>{t.esc(p['word'])}</div>"
        f"<div class=n>{p['count']}</div><div class=muted>{_money(p['amount'])}"
        + (f" · weighted {_money(p['weighted'])}" if p["stage"] in sales.OPEN_STAGES else "") + "</div></a>"
        for p in sales.pipeline(ctx.conn))
    rows = sales.all_(ctx.conn, stage=stage or None, q=search)
    trs = "".join(
        f"<tr><td><a href='/sales/{t.esc(r['opportunity_id'])}'>{t.esc(r['opportunity_id'])}</a></td><td><b>{t.esc(r['name'])}</b></td>"
        f"<td>{t.esc(r['entity_name'] or '')}</td><td>{_stage_chip(r['stage'])}</td><td class=center>{r['probability']}%</td>"
        f"<td>{t.esc(r['expected_on'] or '')}</td><td class=num>{_money(r['amount'], r['currency'])}</td>"
        f"<td>{t.esc(r['owner'] or '')}</td><td class=center>{r['quotes']}</td></tr>"
        for r in rows)
    opts = (f"<option value='OPEN'{' selected' if stage == 'OPEN' else ''}>Open</option>"
            f"<option value='ALL'{' selected' if stage == '' else ''}>Every stage</option>"
            + "".join(f"<option value='{k}'{' selected' if k == stage else ''}>{v}</option>" for k, v in sales.STAGES.items()))
    new = ""
    if can:
        new = ("<div class=card><h3>" + t.icon("plus") + "New opportunity</h3><p class=why>What Dada IT proposes to a "
               "department or a company. Quotes hang under it; winning it drafts the agreement.</p>"
               "<form method=post action='/sales/new' class=grid2>"
               "<div><label>Name</label><input name=name required maxlength=200 placeholder='Ward 3 endpoint refresh'></div>"
               f"<div><label>Company</label><select name=entity_id>{_entity_options(ctx)}</select></div>"
               "<div><label>Amount</label><input name=amount inputmode=decimal placeholder='250000'></div>"
               f"<div><label>Currency</label><input name=currency maxlength=8 value={CURRENCY}></div>"
               "<div><label>Expected close</label><input type=date name=expected_on></div>"
               f"<div><label>Owner</label><input name=owner maxlength=200 value='{t.esc(ctx.user.id)}'></div>"
               "<div style='grid-column:1/-1'><label>Notes</label><textarea name=notes></textarea></div>"
               "<div><button type=submit>Create</button></div></form></div>")
    body = (_banners(q)
            + "<h1>Sales</h1><p class=sub>The pipeline: what has been proposed, how likely it is, and what it is worth. "
              "A won opportunity becomes a draft agreement under Finance.</p>"
            + f"<div class=tiles>{tiles}</div>"
            + "<div class=card><form method=get action='/sales' class='row schedbar'>"
              f"<div style='flex:1 1 260px'><input name=q value='{t.esc(search)}' placeholder='Search opportunities'></div>"
              f"<div style='flex:0 0 180px'><select name=stage>{opts}</select></div>"
              "<div style='flex:0 0 auto'><button class=ghost type=submit>Search</button></div></form>"
              "<div class=tablewrap><table><thead><tr><th>Opportunity</th><th>Name</th><th>Company</th><th>Stage</th>"
              "<th>Probability</th><th>Expected</th><th class=num>Amount</th><th>Owner</th><th>Quotes</th></tr></thead><tbody>"
            + (trs or "<tr><td colspan=9 class=muted>No opportunity here.</td></tr>") + "</tbody></table></div></div>"
            + new)
    return Response(body=t.page("Sales", body, user=ctx.user, active="sales"))


def create(ctx):
    common.require_module(ctx, "FINANCE", "WRITE")
    f = ctx.request.form()
    try:
        oid = sales.create(ctx.conn, name=f.get("name", ""), entity_id=f.get("entity_id"), amount=f.get("amount"),
                           currency=f.get("currency"), expected_on=f.get("expected_on"), owner=f.get("owner"),
                           notes=f.get("notes"), at=ctx.now, actor=ctx.user.id)
        ctx.conn.commit()
    except sales.Refused as exc:
        ctx.conn.rollback()
        return _back("/sales", err=str(exc))
    return _back(f"/sales/{oid}", msg=f"{oid} created.")


# ------------------------------------------------------------ one opportunity

def detail(ctx, opportunity_id):
    from .. import Response
    common.require_module(ctx, "FINANCE")
    o = _opp(ctx, opportunity_id)
    q = ctx.request.query
    can = common.allows(ctx, "FINANCE", "WRITE")
    oid = t.esc(o["opportunity_id"])
    open_ = o["stage"] in sales.OPEN_STAGES
    facts = ("<div class=card><dl class=kv>"
             f"<dt>Name</dt><dd>{t.esc(o['name'])}</dd><dt>Company</dt><dd>{t.esc(o['entity_name'] or '—')}</dd>"
             f"<dt>Contact</dt><dd>{t.esc(o['contact_name'] or '—')}</dd><dt>Stage</dt><dd>{_stage_chip(o['stage'])}</dd>"
             f"<dt>Probability</dt><dd>{o['probability']}%</dd><dt>Expected close</dt><dd>{t.esc(o['expected_on'] or '—')}</dd>"
             f"<dt>Amount</dt><dd>{_money(o['amount'], o['currency']) or '—'}</dd><dt>Owner</dt><dd>{t.esc(o['owner'] or '—')}</dd>"
             + (f"<dt>Agreement</dt><dd><a href='/agreement/{t.esc(o['agreement_id'])}'>{t.esc(o['agreement_id'])}</a> {t.esc(o['agreement_name'] or '')}</dd>"
                if o["agreement_id"] else "")
             + (f"<dt>Lost because</dt><dd>{t.esc(o['lost_reason'])}</dd>" if o["lost_reason"] else "")
             + (f"<dt>Closed</dt><dd>{t.esc(o['closed_at'])}</dd>" if o["closed_at"] else "")
             + f"<dt>Notes</dt><dd>{t.esc(o['notes'] or '—')}</dd>"
             f"<dt>Updated</dt><dd class=muted>{t.esc(o['updated_at'])} · {t.esc(o['updated_by'])}</dd></dl></div>")
    edit = ""
    moves = ""
    if can and open_:
        amount_val = _plain(o["amount"])
        edit = ("<div class=card><h3>" + t.icon("note") + "Edit</h3>"
                f"<form method=post action='/sales/{oid}/update' class=grid2>"
                f"<div><label>Name</label><input name=name required maxlength=200 value='{t.esc(o['name'])}'></div>"
                f"<div><label>Company</label><select name=entity_id>{_entity_options(ctx, o['entity_id'])}</select></div>"
                f"<div><label>Contact</label><select name=contact_id>{_contact_options(ctx, o['entity_id'], o['contact_id'])}</select></div>"
                f"<div><label>Probability %</label><input name=probability inputmode=numeric value='{o['probability']}'></div>"
                f"<div><label>Amount</label><input name=amount inputmode=decimal value='{amount_val}'></div>"
                f"<div><label>Currency</label><input name=currency maxlength=8 value='{t.esc(o['currency'] or CURRENCY)}'></div>"
                f"<div><label>Expected close</label><input type=date name=expected_on value='{t.esc(o['expected_on'] or '')}'></div>"
                f"<div><label>Owner</label><input name=owner maxlength=200 value='{t.esc(o['owner'] or '')}'></div>"
                f"<div style='grid-column:1/-1'><label>Notes</label><textarea name=notes>{t.esc(o['notes'] or '')}</textarea></div>"
                "<div><button type=submit>Save</button></div></form></div>")
        stage_btns = "".join(
            f"<form method=post action='/sales/{oid}/stage' class=inline><input type=hidden name=stage value={s}>"
            f"<button class=ghost type=submit>{t.esc(w)}</button></form> "
            for s, w in sales.STAGES.items() if s in sales.OPEN_STAGES and s != o["stage"])
        moves = ("<div class=card><h3>" + t.icon("flag") + "Stage</h3><p class=why>Winning drafts an agreement from the "
                 "accepted quote, or from the amount when no quote was accepted. Losing asks why.</p>"
                 f"<div class=row>{stage_btns}"
                 f"<form method=post action='/sales/{oid}/stage' class=inline><input type=hidden name=stage value=WON>"
                 "<button type=submit>Won</button></form></div>"
                 f"<form method=post action='/sales/{oid}/stage' class=row style='margin-top:10px'><input type=hidden name=stage value=LOST>"
                 "<div style='flex:1 1 260px'><input name=reason maxlength=300 placeholder='Why it was lost'></div>"
                 "<div style='flex:0 0 auto'><button class=ghost type=submit>Lost</button></div></form></div>")
    quotes = sales.quotes_of(ctx.conn, o["opportunity_id"])
    trs = "".join(
        f"<tr><td><a href='/quote/{t.esc(r['quote_id'])}'>{t.esc(r['quote_id'])}</a></td><td><b>{t.esc(r['name'])}</b></td>"
        f"<td>{_quote_chip(r['status'])}</td><td>{t.esc(r['valid_until'] or '')}</td>"
        f"<td class=num>{_money(r['total'], o['currency'])}</td><td class=muted>{t.esc(r['updated_at'])}</td></tr>" for r in quotes)
    new_quote = ""
    if can and open_:
        new_quote = (f"<form method=post action='/sales/{oid}/quote' class=row style='margin-top:12px'>"
                     "<div style='flex:1 1 220px'><label>New quote</label><input name=name required maxlength=200 placeholder='Option A: refresh 24 endpoints'></div>"
                     "<div style='flex:0 0 160px'><label>Valid until</label><input type=date name=valid_until></div>"
                     "<div style='flex:0 0 100px'><label>Tax %</label><input name=tax_percent inputmode=decimal value=12></div>"
                     "<div style='flex:0 0 auto;align-self:end'><button class=ghost type=submit>Draft</button></div></form>")
    quotes_card = ("<div class=card><h3>" + t.icon("rows") + "Quotes</h3>"
                   "<div class=tablewrap><table><thead><tr><th>Quote</th><th>Name</th><th>Status</th><th>Valid until</th>"
                   "<th class=num>Total</th><th>Updated</th></tr></thead><tbody>"
                   + (trs or "<tr><td colspan=6 class=muted>No quote yet.</td></tr>") + "</tbody></table></div>" + new_quote + "</div>")
    body = (_banners(q) + f"<p class=crumbs><a href='/sales'>Sales</a> › {oid}</p><h1>{t.esc(o['name'])} {_stage_chip(o['stage'])}</h1>"
            + "<div class=grid2>" + facts + (edit or "") + "</div>" + moves + quotes_card)
    return Response(body=t.page(o["opportunity_id"], body, user=ctx.user, active="sales"))


def update(ctx, opportunity_id):
    common.require_module(ctx, "FINANCE", "WRITE")
    _opp(ctx, opportunity_id)
    f = ctx.request.form()
    try:
        changed = sales.update(ctx.conn, opportunity_id, at=ctx.now, actor=ctx.user.id, name=f.get("name", ""),
                               entity_id=f.get("entity_id"), contact_id=f.get("contact_id"), probability=f.get("probability"),
                               amount=f.get("amount"), currency=f.get("currency"), expected_on=f.get("expected_on"),
                               owner=f.get("owner"), notes=f.get("notes"))
        ctx.conn.commit()
    except sales.Refused as exc:
        ctx.conn.rollback()
        return _back(f"/sales/{opportunity_id}", err=str(exc))
    return _back(f"/sales/{opportunity_id}", msg="Saved." if changed else "Nothing changed.")


def stage(ctx, opportunity_id):
    common.require_module(ctx, "FINANCE", "WRITE")
    _opp(ctx, opportunity_id)
    f = ctx.request.form()
    try:
        aid = sales.move(ctx.conn, opportunity_id, f.get("stage", ""), at=ctx.now, actor=ctx.user.id, reason=f.get("reason"))
        ctx.conn.commit()
    except sales.Refused as exc:
        ctx.conn.rollback()
        return _back(f"/sales/{opportunity_id}", err=str(exc))
    if aid:
        return _back(f"/agreement/{aid}", msg=f"{opportunity_id} won. {aid} is drafted; set its term and what it covers.")
    return _back(f"/sales/{opportunity_id}", msg=f"Now {sales.STAGES.get(f.get('stage', ''), '').lower()}.")


def new_quote(ctx, opportunity_id):
    common.require_module(ctx, "FINANCE", "WRITE")
    _opp(ctx, opportunity_id)
    f = ctx.request.form()
    try:
        qid = sales.create_quote(ctx.conn, opportunity_id, name=f.get("name", ""), valid_until=f.get("valid_until"),
                                 tax_percent=f.get("tax_percent") or 0, note=f.get("note"), at=ctx.now, actor=ctx.user.id)
        ctx.conn.commit()
    except sales.Refused as exc:
        ctx.conn.rollback()
        return _back(f"/sales/{opportunity_id}", err=str(exc))
    return _back(f"/quote/{qid}", msg=f"{qid} drafted. Add its lines, then send it.")


# ------------------------------------------------------------ one quote

def quote_detail(ctx, quote_id):
    from .. import Response
    common.require_module(ctx, "FINANCE")
    qt = _quote(ctx, quote_id)
    o = _opp(ctx, qt["opportunity_id"])
    q = ctx.request.query
    can = common.allows(ctx, "FINANCE", "WRITE")
    qid = t.esc(qt["quote_id"])
    cur = o["currency"] or CURRENCY
    draft = qt["status"] == "DRAFT"
    rows = sales.lines(ctx.conn, qt["quote_id"])
    trs = "".join(
        f"<tr><td class=center>{i}</td><td>{t.esc(r['description'])}</td><td class=num>{_plain(r['quantity'])}</td>"
        f"<td class=num>{_money(r['unit_price'], cur)}</td><td class=num>{_money(r['line_total'], cur)}</td>"
        + (f"<td><form method=post action='/quote/{qid}/line/remove' class=inline><input type=hidden name=line_id value={r['line_id']}>"
           f"<button class='ghost small' type=submit title='Remove'>×</button></form></td>" if can and draft else "<td></td>") + "</tr>"
        for i, r in enumerate(rows, 1))
    totals = (f"<tr><td colspan=4 class=num><b>Subtotal</b></td><td class=num>{_money(qt['subtotal'], cur)}</td><td></td></tr>"
              f"<tr><td colspan=4 class=num>Tax {qt['tax_percent']:g}%</td><td class=num>{_money((qt['total'] or 0) - (qt['subtotal'] or 0), cur)}</td><td></td></tr>"
              f"<tr><td colspan=4 class=num><b>Total</b></td><td class=num><b>{_money(qt['total'], cur)}</b></td><td></td></tr>")
    add = ""
    if can and draft:
        add = (f"<form method=post action='/quote/{qid}/line' class=row style='margin-top:12px'>"
               "<div style='flex:1 1 260px'><label>Line</label><input name=description required maxlength=300 placeholder='Endpoint, 14in, 16 GB'></div>"
               "<div style='flex:0 0 100px'><label>Quantity</label><input name=quantity inputmode=decimal value=1></div>"
               "<div style='flex:0 0 140px'><label>Unit price</label><input name=unit_price inputmode=decimal required placeholder='45000'></div>"
               "<div style='flex:0 0 auto;align-self:end'><button class=ghost type=submit>Add line</button></div></form>")
    actions = ""
    if can:
        nxt = {"DRAFT": [("SENT", "Mark sent")], "SENT": [("ACCEPTED", "Accepted"), ("DECLINED", "Declined"), ("EXPIRED", "Expired"), ("DRAFT", "Back to draft")]}
        btns = "".join(
            f"<form method=post action='/quote/{qid}/status' class=inline><input type=hidden name=status value={s}>"
            f"<button class='{'ghost' if s != 'ACCEPTED' else ''}' type=submit>{w}</button></form> " for s, w in nxt.get(qt["status"], []))
        if btns:
            actions = ("<div class=card><h3>" + t.icon("check") + "Status</h3><p class=why>Sending moves the opportunity to "
                       "Proposal sent. Accepting sets the opportunity's amount to this total; winning it then drafts the agreement.</p>"
                       f"<div class=row>{btns}</div></div>")
    facts = ("<div class=card><dl class=kv>"
             f"<dt>Quote</dt><dd>{qid} · {t.esc(qt['name'])}</dd><dt>Status</dt><dd>{_quote_chip(qt['status'])}</dd>"
             f"<dt>Opportunity</dt><dd><a href='/sales/{t.esc(o['opportunity_id'])}'>{t.esc(o['opportunity_id'])}</a> {t.esc(o['name'])}</dd>"
             f"<dt>Company</dt><dd>{t.esc(o['entity_name'] or '—')}</dd><dt>Valid until</dt><dd>{t.esc(qt['valid_until'] or '—')}</dd>"
             + (f"<dt>Sent</dt><dd>{t.esc(qt['sent_at'])}</dd>" if qt["sent_at"] else "")
             + (f"<dt>Decided</dt><dd>{t.esc(qt['decided_at'])}</dd>" if qt["decided_at"] else "")
             + f"<dt>Note</dt><dd>{t.esc(qt['note'] or '—')}</dd></dl></div>")
    lines_card = ("<div class=card><h3>" + t.icon("rows") + "Lines</h3>"
                  "<div class=tablewrap><table><thead><tr><th>#</th><th>Description</th><th class=num>Qty</th><th class=num>Unit</th>"
                  "<th class=num>Total</th><th></th></tr></thead><tbody>"
                  + (trs or "<tr><td colspan=6 class=muted>No line yet. A quote with no lines is not sent.</td></tr>")
                  + totals + "</tbody></table></div>" + add + "</div>")
    body = (_banners(q) + f"<p class=crumbs><a href='/sales'>Sales</a> › <a href='/sales/{t.esc(o['opportunity_id'])}'>"
            f"{t.esc(o['opportunity_id'])}</a> › {qid}</p><h1>{t.esc(qt['name'])} {_quote_chip(qt['status'])}</h1>"
            + facts + lines_card + actions)
    return Response(body=t.page(qt["quote_id"], body, user=ctx.user, active="sales"))


def line_add(ctx, quote_id):
    common.require_module(ctx, "FINANCE", "WRITE")
    _quote(ctx, quote_id)
    f = ctx.request.form()
    try:
        sales.add_line(ctx.conn, quote_id, description=f.get("description", ""), quantity=f.get("quantity"),
                       unit_price=f.get("unit_price"), at=ctx.now, actor=ctx.user.id)
        ctx.conn.commit()
    except sales.Refused as exc:
        ctx.conn.rollback()
        return _back(f"/quote/{quote_id}", err=str(exc))
    return _back(f"/quote/{quote_id}")


def line_remove(ctx, quote_id):
    common.require_module(ctx, "FINANCE", "WRITE")
    _quote(ctx, quote_id)
    f = ctx.request.form()
    try:
        line_id = int(f.get("line_id", ""))
    except ValueError:
        return _back(f"/quote/{quote_id}", err="No such line.")
    try:
        sales.remove_line(ctx.conn, quote_id, line_id, at=ctx.now, actor=ctx.user.id)
        ctx.conn.commit()
    except sales.Refused as exc:
        ctx.conn.rollback()
        return _back(f"/quote/{quote_id}", err=str(exc))
    return _back(f"/quote/{quote_id}")


def quote_status(ctx, quote_id):
    common.require_module(ctx, "FINANCE", "WRITE")
    _quote(ctx, quote_id)
    f = ctx.request.form()
    try:
        status = sales.set_quote_status(ctx.conn, quote_id, f.get("status", ""), at=ctx.now, actor=ctx.user.id)
        ctx.conn.commit()
    except sales.Refused as exc:
        ctx.conn.rollback()
        return _back(f"/quote/{quote_id}", err=str(exc))
    return _back(f"/quote/{quote_id}", msg=f"{quote_id} is {sales.QUOTE_STATUSES[status].lower()}.")

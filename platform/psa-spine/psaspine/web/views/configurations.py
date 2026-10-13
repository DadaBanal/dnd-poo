"""Configurations, the ticket's Configurations card, and Setup › Integrations.

Dada PSA's Configurations: the machines under a company, each opening its
remote-support session in one click, and listed on the tickets that concern
them. The link targets are data an administrator writes in Setup; see
psaspine/configurations.py for the rules a template must meet.

Fulfillers only, as companies and contacts. Changing a configuration takes WORK
on any board; attaching one to a ticket takes WORK on that ticket's board; the
link templates take a system administrator, because they decide where every
technician's click goes.
"""
from __future__ import annotations

import csv
import io
import urllib.parse
from datetime import timedelta

from ... import configurations as cmdb
from .. import templates as t
from . import common
from .companies import _fulfiller, _hidden_note, _tickets


def _may_work(ctx) -> bool:
    return ctx.conn.execute(
        "SELECT 1 FROM board_member WHERE member = ? AND access IN ('WORK','ADMIN')",
        (ctx.user.id,)).fetchone() is not None


def links_html(ctx, applies_to: str, record) -> str:
    out = []
    for link in cmdb.links_for(ctx.conn, applies_to, record):
        if link["url"]:
            out.append(f"<a class='btn ghost' target=_blank rel='noopener noreferrer' "
                       f"href='{t.esc(link['url'])}'>{t.esc(link['label'])} ↗</a>")
        else:
            out.append(f"<span class='btn ghost' aria-disabled=true title='{t.esc(link['why'])}' "
                       f"style='opacity:.5;cursor:not-allowed'>{t.esc(link['label'])}</span>")
    return "<span class=linkrow>" + " ".join(out) + "</span>" if out else ""


def table(ctx, rows, *, with_company: bool = True) -> str:
    if not rows:
        return ("<div class=muted>No configurations. Import them from AD: "
                "psaspine import-computers.</div>")
    body = "".join(
        f"<tr><td><a href='/configuration/{t.esc(r['configuration_id'])}'>{t.esc(r['name'])}</a>"
        + (f" <span class=chip>{t.esc(r['status'].lower())}</span>" if r["status"] != "ACTIVE" else "")
        + "</td>"
        + (f"<td>{t.esc(r['entity_id'])}</td>" if with_company else "")
        + f"<td>{t.esc(r['config_type'].title())}</td><td>{t.esc(r['os_name'] or '—')}</td>"
        f"<td>{t.esc(r['contact_name'] or '—')}</td><td>{t.esc(r['last_seen_at'] or '—')}</td>"
        f"<td>{links_html(ctx, 'CONFIGURATION', r)}</td></tr>" for r in rows)
    return ("<div class=tablewrap><table><thead><tr><th>Name</th>"
            + ("<th>Company</th>" if with_company else "")
            + "<th>Type</th><th>OS</th><th>Contact</th><th>Last seen</th><th></th></tr></thead>"
            f"<tbody>{body}</tbody></table></div>")


def search(ctx, q: str = "", *, entity_id: str | None = None, contact_id: str | None = None,
           include_inactive: bool = False, limit: int = 300):
    sql = ["SELECT c.*, ct.display_name AS contact_name FROM configuration c"
           " LEFT JOIN contact ct ON ct.contact_id = c.contact_id WHERE 1 = 1"]
    params: list = []
    if entity_id:
        sql.append(" AND c.entity_id = ?")
        params.append(entity_id)
    if contact_id:
        sql.append(" AND c.contact_id = ?")
        params.append(contact_id)
    if not include_inactive:
        sql.append(" AND c.status = 'ACTIVE'")
    if q:
        like = f"%{q.lower()}%"
        sql.append(" AND (lower(c.name) LIKE ? OR lower(coalesce(c.dns_name,'')) LIKE ?"
                   " OR lower(coalesce(c.serial_number,'')) LIKE ?"
                   " OR lower(coalesce(c.description,'')) LIKE ?)")
        params += [like] * 4
    sql.append(" ORDER BY c.name LIMIT ?")
    params.append(limit)
    return ctx.conn.execute("".join(sql), params).fetchall()


TYPE_WORDS = {"WORKSTATION": "Workstations", "LAPTOP": "Laptops", "SERVER": "Servers", "PRINTER": "Printers",
              "NETWORK": "Network", "MOBILE": "Mobile", "OTHER": "Other"}
SORTS = {"name": "c.name", "type": "c.config_type, c.name", "os": "c.os_name, c.name",
         "contact": "ct.display_name, c.name", "seen": "c.last_seen_at DESC, c.name",
         "tickets": "open_tickets DESC, c.name", "company": "c.entity_id, c.name",
         "warranty": "c.warranty_ends_on, c.name", "status": "c.status, c.name", "site": "s.name, c.name",
         "serial": "c.serial_number, c.name", "model": "c.model, c.name", "tag": "c.tag_number, c.name",
         "manufacturer": "c.manufacturer, c.name", "vendor": "c.vendor, c.name"}
WARRANTY_FILTERS = ("expiring", "expired")
# 13 Oct 2026 (Dada: "revamp ... configurations to look like the connectwise
# build"): the reference PSA's list columns, chosen per person. Name is always
# first; the rest are ticked under Columns. The default set is its default.
LIST_COLUMNS = (("name", "Name"), ("type", "Type"), ("status", "Status"), ("company", "Company"), ("site", "Site"),
                ("contact", "Contact"), ("serial", "Serial #"), ("model", "Model"), ("tag", "Tag #"),
                ("manufacturer", "Manufacturer"), ("vendor", "Vendor"), ("os", "OS"), ("seen", "Last login"),
                ("warranty", "Warranty"), ("tickets", "Open"))
DEFAULT_COLUMNS = ("name", "type", "status", "company", "site", "contact", "serial", "model", "tag", "vendor", "seen", "warranty", "tickets")
CW_SORTS = {"tag", "manufacturer", "vendor", "serial", "model", "site", "status"}


def _warranty_cell(ctx, row) -> str:
    """The warranty as a chip: ended (red), ends within 90 days (amber), or the date."""
    state, days = cmdb.warranty_state(row["warranty_ends_on"], ctx.now.date())
    if state == "EXPIRED":
        return f"<span class='chip sla-bad'>ended {t.esc(row['warranty_ends_on'])}</span>"
    if state == "EXPIRING":
        return f"<span class='chip sla-warn'>{days} d left · {t.esc(row['warranty_ends_on'])}</span>"
    return t.esc(row["warranty_ends_on"] or "—")


def _list_filters(ctx):
    """The list's filters, shared by the page and its maintenance export."""
    q = ctx.request.query
    text = q.get("q", "").strip()
    kind = q.get("type", "") if q.get("type", "") in cmdb.type_names(ctx.conn) else ""
    status = q.get("status", "ACTIVE")
    if status not in cmdb.STATUSES + ("ALL",):
        status = "ACTIVE"
    entity = q.get("company", "")
    sort = q.get("sort", "name") if q.get("sort", "name") in SORTS else "name"
    if sort == "tag" and not cmdb.cw_shape(ctx.conn):
        sort = "name"
    warranty = q.get("warranty", "") if q.get("warranty", "") in WARRANTY_FILTERS else ""
    where, params = ["1 = 1"], []
    if text:
        if cmdb.cw_shape(ctx.conn):
            where.append("(c.name LIKE ? OR c.serial_number LIKE ? OR c.description LIKE ? OR c.dns_name LIKE ? OR c.tag_number LIKE ?)")
            params += [f"%{text}%"] * 5
        else:
            where.append("(c.name LIKE ? OR c.serial_number LIKE ? OR c.description LIKE ? OR c.dns_name LIKE ?)")
            params += [f"%{text}%"] * 4
    if kind:
        where.append("COALESCE(c.type_id, c.config_type) = ?"); params.append(kind)
    if status != "ALL":
        where.append("c.status = ?"); params.append(status)
    if entity:
        where.append("c.entity_id = ?"); params.append(entity)
    today = ctx.now.date().isoformat()
    if warranty == "expired":
        where.append("c.warranty_ends_on IS NOT NULL AND c.warranty_ends_on < ?"); params.append(today)
    elif warranty == "expiring":
        where.append("c.warranty_ends_on >= ? AND c.warranty_ends_on <= ?")
        params += [today, (ctx.now.date() + timedelta(days=cmdb.WARRANTY_SOON_DAYS)).isoformat()]
    return text, kind, status, entity, sort, warranty, where, params


def _opts(pairs, sel):
    return "".join(f"<option value='{t.esc(k)}'{' selected' if k == sel else ''}>{t.esc(v)}</option>"
                   for k, v in pairs)


def _columns_chosen(ctx) -> list[str]:
    """The columns this list shows: ?cols=a,b,c, else the default set. Name
    always; a column the store cannot fill yet (080 not taken) is dropped."""
    raw = ctx.request.query.get("cols", "")
    keys = [k for k in raw.split(",") if k in dict(LIST_COLUMNS)] if raw else list(DEFAULT_COLUMNS)
    if not cmdb.cw_shape(ctx.conn):
        keys = [k for k in keys if k != "tag"]
    return ["name"] + [k for k in dict.fromkeys(keys) if k != "name"]


def index(ctx):
    """The reference PSA's Configurations list (13 Oct 2026): its columns,
    chosen under Columns; counts by type that filter; search, status, company
    and warranty filters; every column sorts; rows ticked and changed
    together. Below it, the form for a machine typed in by hand (AD's own
    arrive by import)."""
    from .. import Response
    _fulfiller(ctx)
    q = ctx.request.query
    text, kind, status, entity, sort, warranty, where, params = _list_filters(ctx)
    cols = _columns_chosen(ctx)
    cw = cmdb.cw_shape(ctx.conn)
    rows = ctx.conn.execute(
        "SELECT c.*, ct.display_name AS contact_name, e.name AS entity_name, s.name AS site_name,"
        "       (SELECT COUNT(*) FROM ticket_configuration tc JOIN ticket t ON t.work_item_id = tc.work_item_id"
        "         WHERE tc.configuration_id = c.configuration_id"
        "           AND t.state NOT IN ('RESOLVED','CLOSED','CANCELLED')) AS open_tickets"
        "  FROM configuration c JOIN entity e ON e.entity_id = c.entity_id"
        "  LEFT JOIN contact ct ON ct.contact_id = c.contact_id LEFT JOIN site s ON s.site_id = c.site_id"
        f" WHERE {' AND '.join(where)} ORDER BY {SORTS[sort]} LIMIT 500", params).fetchall()
    total = ctx.conn.execute(f"SELECT COUNT(*) FROM configuration c WHERE {' AND '.join(where)}", params).fetchone()[0]
    counts = {r["k"]: r["n"] for r in ctx.conn.execute(
        "SELECT COALESCE(type_id, config_type) AS k, COUNT(*) AS n FROM configuration WHERE status = 'ACTIVE' GROUP BY COALESCE(type_id, config_type)")}
    active = sum(counts.values())
    colspec = ",".join(cols)

    def keep(**kw):
        d = {"q": text, "type": kind, "status": status, "company": entity, "sort": sort, "warranty": warranty, "cols": colspec}
        d.update(kw)
        return "/configurations?" + urllib.parse.urlencode({k: v for k, v in d.items() if v and not (k == "status" and v == "ACTIVE")
                                                            and not (k == "cols" and v == ",".join(_columns_chosen_default(ctx)))})
    tiles = (f"<a class='tile{' on' if not kind else ''}' href='{keep(type='')}'><div class=n>{active}</div><div class=l>Active, all types</div></a>"
             + "".join(f"<a class='tile{' on' if kind == ty['type_id'] else ''}' href='{keep(type=ty['type_id'])}'><div class=n>{counts.get(ty['type_id'], 0)}</div>"
                       f"<div class=l>{t.esc(TYPE_WORDS.get(ty['type_id'], ty['name']))}</div></a>"
                       for ty in cmdb.types(ctx.conn) if ty["type_id"] in TYPE_WORDS or counts.get(ty["type_id"])))
    wc = cmdb.warranty_counts(ctx.conn, ctx.now.date())
    tiles += (f"<a class='tile{' on' if warranty == 'expiring' else ''}' href='{keep(warranty='' if warranty == 'expiring' else 'expiring')}'>"
              f"<div class=n>{wc['expiring']}</div><div class=l>Warranty ends in 90 days</div></a>"
              f"<a class='tile{' on' if warranty == 'expired' else ''}' href='{keep(warranty='' if warranty == 'expired' else 'expired')}'>"
              f"<div class=n>{wc['expired']}</div><div class=l>Out of warranty</div></a>")
    companies = ctx.conn.execute("SELECT entity_id, name FROM entity ORDER BY name").fetchall()
    picks = "".join(f"<label class=colopt><input type=checkbox name=col value='{k}'{' checked' if k in cols else ''}{' disabled' if k == 'name' else ''}> {t.esc(v)}</label>"
                    for k, v in LIST_COLUMNS if cw or k != "tag")
    filters = (
        "<form method=get class='row schedbar' id=cfgfilter style='margin-bottom:10px'>"
        f"<input type=hidden name=type value='{t.esc(kind)}'><input type=hidden name=sort value='{t.esc(sort)}'>"
        f"<input type=hidden name=cols value='{t.esc(colspec)}' data-cols>"
        f"<div style='flex:1 1 220px'><input name=q value='{t.esc(text)}' placeholder='name, DNS name, serial, tag or description'></div>"
        f"<div style='flex:0 0 auto'><select name=status aria-label=Status>{_opts([('ACTIVE', 'Active'), ('INACTIVE', 'Inactive'), ('RETIRED', 'Retired'), ('ALL', 'All statuses')], status)}</select></div>"
        f"<div style='flex:0 0 auto'><select name=company aria-label=Company>{_opts([('', 'Every company')] + [(e['entity_id'], e['name']) for e in companies], entity)}</select></div>"
        "<div style='flex:0 0 auto'><button type=submit>Filter</button></div>"
        f"<div style='flex:0 0 auto'><details class=colpick><summary class='btn ghost'>{t.icon('rows')} Columns</summary>"
        f"<div class=colmenu>{picks}<button class='small' type=submit data-applycols>Apply</button></div></details></div></form>")

    def th(key, label):
        cls = " class=num" if key in ("tickets",) else ""
        return f"<th{cls}><a href='{keep(sort=key)}'{' class=on' if sort == key else ''}>{label}</a></th>"

    def cell(r, key):
        if key == "name":
            return (f"<td><a href='/configuration/{t.esc(r['configuration_id'])}'>{t.esc(r['name'])}</a>"
                    + (" <span class=muted>by hand</span>" if r["source"] == "MANUAL" else "") + "</td>")
        if key == "type":
            return f"<td>{t.esc(cmdb.type_word(ctx.conn, r))}</td>"
        if key == "status":
            w = cmdb.status_word(ctx.conn, r)
            return f"<td>{t.esc(w) if r['status'] == 'ACTIVE' else '<span class=chip>' + t.esc(w.lower()) + '</span>'}</td>"
        if key == "company":
            return f"<td>{t.esc(r['entity_name'])}</td>"
        if key == "site":
            return f"<td>{t.esc(r['site_name'] or '—')}</td>"
        if key == "contact":
            return f"<td>{t.esc(r['contact_name'] or '—')}</td>"
        if key == "seen":
            return f"<td>{t.esc((r['last_seen_at'] or '—')[:10])}</td>"
        if key == "warranty":
            return f"<td>{_warranty_cell(ctx, r)}</td>"
        if key == "tickets":
            return f"<td class=num>{r['open_tickets'] or ''}</td>"
        if key == "tag":
            return f"<td>{t.esc((r['tag_number'] if cw else None) or '—')}</td>"
        col = {"serial": "serial_number", "model": "model", "manufacturer": "manufacturer", "vendor": "vendor", "os": "os_name"}[key]
        return f"<td>{t.esc(r[col] or '—')}</td>"
    can = _may_work(ctx)
    body_rows = "".join(
        f"<tr>" + (f"<td><input type=checkbox form=cfgbulk name=ids value='{t.esc(r['configuration_id'])}' aria-label='Tick {t.esc(r['name'])}'></td>" if can else "")
        + "".join(cell(r, k) for k in cols) + f"<td>{links_html(ctx, 'CONFIGURATION', r)}</td></tr>" for r in rows)
    table = ("<div class=tablewrap><table class=cfglist><thead><tr>" + ("<th><input type=checkbox data-tickall aria-label='Tick every row'></th>" if can else "")
             + "".join(th(k, dict(LIST_COLUMNS)[k]) for k in cols) + "<th></th></tr></thead><tbody>" + body_rows + "</tbody></table></div>"
             if rows else "<div class=muted>Nothing matches. Import machines from AD: psaspine import-computers; "
                          "or add one by hand below.</div>")
    bulk = ""
    if can and rows:
        bulk = (f"<form id=cfgbulk method=post action='/configurations/bulk' class='row schedbar bulkbar' style='margin-top:10px'>"
                f"<input type=hidden name=back value='{t.esc(keep())}'>"
                "<div style='flex:0 0 auto'><b><span data-ticked>0</span> ticked:</b></div>"
                f"<div style='flex:0 0 170px'><select name=status aria-label='Change status'>{_opts([('', 'Status: leave')] + [(x['status_id'], x['name']) for x in cmdb.statuses(ctx.conn)], '')}</select></div>"
                f"<div style='flex:0 0 170px'><select name=config_type aria-label='Change type'>{_opts([('', 'Type: leave')] + [(x['type_id'], x['name']) for x in cmdb.types(ctx.conn)], '')}</select></div>"
                f"<div style='flex:0 0 200px'><select name=contact_id aria-label='Change contact'>{_opts([('', 'Contact: leave'), ('-', 'Contact: clear')] + [(p['contact_id'], p['display_name']) for p in ctx.conn.execute('SELECT contact_id, display_name FROM contact WHERE inactive = 0 ORDER BY display_name LIMIT 2000')], '')}</select></div>"
                f"<div style='flex:0 0 auto'><button type=submit>{t.icon('check')} Apply to ticked</button></div></form>")
    script = ("<script>(function(){var f=document.getElementById('cfgfilter');if(f){var h=f.querySelector('[data-cols]');"
              "f.addEventListener('submit',function(){var c=Array.prototype.filter.call(f.querySelectorAll('input[name=col]'),function(i){return i.checked||i.disabled}).map(function(i){return i.value});h.value=c.join(',')});"
              "f.querySelectorAll('input[name=col]').forEach(function(i){i.removeAttribute('name');i.setAttribute('name','col')})}"
              "var tick=document.querySelector('[data-tickall]');var n=document.querySelector('[data-ticked]');"
              "var boxes=function(){return Array.prototype.slice.call(document.querySelectorAll('input[form=cfgbulk][name=ids]'))};"
              "function count(){if(n)n.textContent=boxes().filter(function(b){return b.checked}).length}"
              "if(tick)tick.addEventListener('change',function(){boxes().forEach(function(b){b.checked=tick.checked});count()});"
              "boxes().forEach(function(b){b.addEventListener('change',count)});count()})()</script>")
    export = keep().replace("/configurations?", "/configurations/maintenance.csv?")
    shown = ((f"<p class=why>{len(rows)} of {total} shown." if total > len(rows) else f"<p class=why>{total} configuration(s).")
             + f" <a href='{export}'>Maintenance record (CSV) for these</a>: every ticket on them, with hours and visits.</p>")
    add = ""
    if can:
        add = (
            "<div class=card id=cfgnew><h3>" + t.icon("plus") + "New configuration</h3><p class=sub>A printer, a network "
            "device, a machine Active Directory does not know. AD's own machines arrive by import and are never typed.</p>"
            "<form method=post action='/configurations/new' class=fields><div class=grid2>"
            "<div><label>Name</label><input name=name required maxlength=100 placeholder='PRN-WARD3-01'></div>"
            f"<div><label>Company</label><select name=entity_id>{_opts([(e['entity_id'], e['name']) for e in companies], 'PMC')}</select></div>"
            f"<div><label>Type</label><select name=config_type>{_opts([(x['type_id'], x['name']) for x in cmdb.types(ctx.conn)], 'PRINTER')}</select></div>"
            "<div><label>Serial #</label><input name=serial_number maxlength=100></div>"
            + ("<div><label>Tag #</label><input name=tag_number maxlength=60 placeholder='the asset tag'></div>" if cw else "")
            + "<div><label>Manufacturer</label><input name=manufacturer maxlength=100></div>"
            "<div><label>Model</label><input name=model maxlength=100></div>"
            "<div style='grid-column:1/-1'><label>Description</label><input name=description maxlength=400 placeholder='where it is, what it does'></div>"
            "</div><div style='margin-top:10px'><button type=submit>Add</button></div></form></div>")
    msg, err = q.get("msg", ""), q.get("err", "")
    body = (
        (f"<div class='banner ok'>{t.esc(msg)}</div>" if msg else "")
        + (f"<div class='banner err'>{t.esc(err)}</div>" if err else "")
        + "<h1>Configurations</h1><p class=sub>Every machine, printer and device the desk supports, in the reference PSA's "
          "Configurations list: choose the columns, sort any of them, tick rows to change their status, type or contact together. "
          "Open one for its tickets, its history and its remote session.</p>"
        + f"<div class='tiles' style='grid-template-columns:repeat(auto-fit,minmax(112px,1fr))'>{tiles}</div>"
        + "<div class=card>" + filters + table + bulk + shown + "</div>" + add + script)
    return Response(body=t.page("Configurations", body, user=ctx.user, active="configurations"))


def _columns_chosen_default(ctx) -> list[str]:
    keys = list(DEFAULT_COLUMNS)
    if not cmdb.cw_shape(ctx.conn):
        keys = [k for k in keys if k != "tag"]
    return keys


def bulk(ctx):
    """POST /configurations/bulk: the same change on every ticked row."""
    from .. import HttpError, redirect
    _fulfiller(ctx)
    if not _may_work(ctx):
        raise HttpError("403 Forbidden", "Changing a configuration takes WORK on a board.")
    f = ctx.request.form()
    back = f.get("back") if (f.get("back") or "").startswith("/configurations") else "/configurations"
    sep = "&" if "?" in back else "?"
    contact = f.get("contact_id", "")
    try:
        out = cmdb.bulk_update(ctx.conn, ctx.request.form_list("ids"), at=ctx.now, actor=ctx.user.id,
                               status=f.get("status") or None, config_type=f.get("config_type") or None,
                               contact_id=None if not contact else ("" if contact == "-" else contact))
    except ValueError as exc:
        return redirect(back + sep + urllib.parse.urlencode({"err": f"Nothing changed: {exc}"}))
    ctx.conn.commit()
    words = f"{out['changed']} changed, {out['unchanged']} already so"
    if out["refused"]:
        words += f"; {len(out['refused'])} refused: " + "; ".join(out["refused"][:5])
    return redirect(back + sep + urllib.parse.urlencode({"msg": words}))


def create(ctx):
    from .. import HttpError, redirect
    _fulfiller(ctx)
    if not _may_work(ctx):
        raise HttpError("403 Forbidden", "Adding a configuration takes WORK on a board.")
    f = ctx.request.form()
    try:
        cid = cmdb.create(ctx.conn, name=f.get("name", ""), entity_id=f.get("entity_id", ""),
                          config_type=f.get("config_type", ""), at=ctx.now, actor=ctx.user.id,
                          serial_number=f.get("serial_number"), manufacturer=f.get("manufacturer"),
                          model=f.get("model"), description=f.get("description"), tag_number=f.get("tag_number"))
    except (ValueError, LookupError) as exc:
        return redirect("/configurations?" + urllib.parse.urlencode({"err": str(exc)}))
    ctx.conn.commit()
    return redirect(f"/configuration/{urllib.parse.quote(cid)}?" + urllib.parse.urlencode({"msg": "Added."}))


def _history(ctx, configuration_id: str) -> str:
    """What happened to this machine: the desk's own changes (audit) and the
    tickets it was attached to or removed from (ticket events), newest first."""
    audit = ctx.conn.execute(
        "SELECT occurred_at, actor, action, detail FROM audit_event WHERE subject_kind = 'configuration'"
        " AND subject_id = ? ORDER BY audit_id DESC LIMIT 50", (configuration_id,)).fetchall()
    events = ctx.conn.execute(
        "SELECT occurred_at, actor, work_item_id, detail FROM ticket_event WHERE kind = 'UPDATED'"
        " AND detail LIKE ? ORDER BY ticket_event_id DESC LIMIT 50", (f"configuration % ({configuration_id}) %",)).fetchall()
    lines = ([(a["occurred_at"], a["actor"], t.esc(a["action"].replace("CONFIGURATION_", "").lower()) + ": " + t.esc(a["detail"] or ""))
              for a in audit]
             + [(e["occurred_at"], e["actor"], f"<a href='/ticket/{t.esc(e['work_item_id'])}'>{t.esc(e['work_item_id'])}</a>: "
                                                 + t.esc(e["detail"].split(") ", 1)[-1])) for e in events])
    lines.sort(key=lambda x: x[0], reverse=True)
    if not lines:
        return "<div class=muted>Nothing yet.</div>"
    return "<ul class=plain>" + "".join(
        f"<li><span class=muted>{t.esc(when)} · {t.esc(who)}</span> · {what}</li>" for when, who, what in lines[:50]) + "</ul>"


CFG_TABS = (("", "Configuration"), ("tickets", "Tickets"), ("history", "History"))


def detail(ctx, configuration_id: str):
    """The reference PSA's configuration screen (13 Oct 2026): a header, then
    tabs; the Configuration tab is pods (Configuration, Details, Questions,
    Children, Contact, Change), Tickets the open and recently closed ones,
    History what the desk did to it."""
    from .. import HttpError, Response
    boards = _fulfiller(ctx)
    cw = cmdb.cw_shape(ctx.conn)
    c = ctx.conn.execute(
        "SELECT c.*, e.name AS entity_name, ct.display_name AS contact_name, ct.email AS contact_email,"
        "       ct.department AS contact_department, s.name AS site_name, ag.name AS agreement_name"
        + (", p.name AS parent_name" if cw else ", NULL AS parent_name") + " FROM configuration c"
        " JOIN entity e ON e.entity_id = c.entity_id"
        " LEFT JOIN contact ct ON ct.contact_id = c.contact_id"
        " LEFT JOIN site s ON s.site_id = c.site_id"
        " LEFT JOIN agreement ag ON ag.agreement_id = c.agreement_id"
        + (" LEFT JOIN configuration p ON p.configuration_id = c.parent_configuration_id" if cw else "")
        + " WHERE c.configuration_id = ?", (configuration_id,)).fetchone()
    if c is None:
        raise HttpError("404 Not Found", "No such configuration.")
    q = ctx.request.query
    tab = q.get("tab", "") if q.get("tab", "") in dict(CFG_TABS) else ""
    msg, err = q.get("msg", ""), q.get("err", "")
    cid = t.esc(configuration_id)
    raise_qs = urllib.parse.urlencode({k: v for k, v in {
        "configuration_id": configuration_id, "entity_id": c["entity_id"],
        "requested_by": (c["contact_email"] or "")}.items() if v})
    # The count on the Tickets tab reads only the boards the Tickets tab lists:
    # a ticket on a restricted board is neither listed nor counted here.
    from .companies import _open_boards
    shown_boards, _ = _open_boards(ctx, boards) if boards else ([], 0)
    open_n = ctx.conn.execute(
        "SELECT COUNT(*) FROM ticket_configuration tc JOIN ticket t ON t.work_item_id = tc.work_item_id"
        " WHERE tc.configuration_id = ? AND t.state NOT IN ('RESOLVED','CLOSED','CANCELLED')"
        f" AND t.board_id IN ({','.join('?' * len(shown_boards))})",
        [configuration_id] + shown_boards).fetchone()[0] if shown_boards else 0
    tabs = ("<nav class='tabs ttabs' aria-label='Configuration tabs'>" + "".join(
        f"<a href='/configuration/{cid}" + (f"?tab={k}" if k else "") + "'" + (" class=on aria-current=page" if k == tab else "")
        + f">{v}" + (f" <span class=tcount>{open_n}</span>" if k == "tickets" and open_n else "") + "</a>" for k, v in CFG_TABS) + "</nav>")
    sub = " · ".join(x for x in (
        f"<a href='/company/{t.esc(c['entity_id'])}'>{t.esc(c['entity_name'])}</a>",
        t.esc(c["site_name"]) if c["site_name"] else "", t.esc(c["location"]) if c["location"] else "",
        f"<a href='/contact/{t.esc(c['contact_id'])}'>{t.esc(c['contact_name'])}</a>" if c["contact_id"] else "",
        "typed in by hand" if c["source"] == "MANUAL" else "from Active Directory") if x)
    head = ((f"<div class='banner ok toast'>{t.icon('check')} {t.esc(msg)}</div>" if msg else "")
            + (f"<div class='banner err toast'>{t.icon('alert')} {t.esc(err)}</div>" if err else "")
            + "<a class=backbtn data-back href='/configurations' title='Back to Configurations'>" + t.icon("left")
            + "<span class=lbl>Back to Configurations</span></a>"
            f"<div class=hdr><div class=grow><h1 class=sumline>{t.esc(c['name'])}"
            f" <span class=chip>{t.esc(cmdb.type_word(ctx.conn, c))}</span>"
            + (f" <span class=chip>{t.esc(cmdb.status_word(ctx.conn, c).lower())}</span>" if c["status"] != "ACTIVE" else "")
            + (f" <span class=pill title='Tag number'>{t.icon('tag')}{t.esc(c['tag_number'])}</span>" if cw and c["tag_number"] else "")
            + f"</h1><p class=sub>{sub}</p></div><div class=acts>"
            + links_html(ctx, "CONFIGURATION", c)
            + (f" <a class='btn' href='/ticket/new?{raise_qs}'>{t.icon('plus')} Raise a ticket for this machine</a>" if _may_work(ctx) else "")
            + f" <a class='btn ghost' href='/configuration/{cid}/maintenance.csv'>{t.icon('arrow')} Maintenance record</a>"
            "</div></div>" + tabs)
    if tab == "tickets":
        body = _cfg_tickets(ctx, boards, configuration_id)
    elif tab == "history":
        body = f"<div class=card><h3>{t.icon('clock')}History</h3>{_history(ctx, configuration_id)}</div>"
    else:
        body = _cfg_overview(ctx, c, cw)
    return Response(body=t.page(c["name"], head + body, user=ctx.user, active="configurations"))


def _cfg_tickets(ctx, boards, configuration_id: str) -> str:
    tickets_html, hidden = _tickets(
        ctx, boards, where="t.work_item_id IN (SELECT work_item_id FROM ticket_configuration"
                           " WHERE configuration_id = ?)", params=[configuration_id])
    from .companies import _open_boards
    shown_boards, _ = _open_boards(ctx, boards)
    closed = []
    if shown_boards:
        marks = ",".join("?" * len(shown_boards))
        closed = ctx.conn.execute(
            "SELECT t.work_item_id, w.name AS summary, t.closed_at, b.display_name AS board_name FROM ticket t"
            " JOIN work_item w ON w.work_item_id = t.work_item_id JOIN board b ON b.board_id = t.board_id"
            " JOIN ticket_configuration tc ON tc.work_item_id = t.work_item_id"
            f" WHERE tc.configuration_id = ? AND t.board_id IN ({marks})"
            " AND t.state IN ('RESOLVED','CLOSED','CANCELLED') ORDER BY t.closed_at DESC LIMIT 20",
            [configuration_id] + shown_boards).fetchall()
    closed_html = ("<ul class=plain>" + "".join(
        f"<li><a href='/ticket/{t.esc(r['work_item_id'])}'>{t.esc(r['work_item_id'])}</a> {t.esc(r['summary'])} "
        f"<span class=muted>· {t.esc(r['board_name'])} · closed {t.esc((r['closed_at'] or '')[:10])}</span></li>"
        for r in closed) + "</ul>") if closed else "<div class=muted>None.</div>"
    return (f"<div class=card><h3>{t.icon('ticket')}Open tickets</h3>{tickets_html}{_hidden_note(hidden)}</div>"
            f"<div class=card><h3>{t.icon('check')}Recently closed</h3>{closed_html}</div>")


def _cfg_overview(ctx, c, cw: bool) -> str:
    configuration_id = c["configuration_id"]
    cid = t.esc(configuration_id)
    kids = cmdb.children(ctx.conn, configuration_id)
    dash = lambda v: t.esc(str(v)) if v else "—"
    pod1 = (f"<dt>Type</dt><dd>{t.esc(cmdb.type_word(ctx.conn, c))}</dd><dt>Status</dt><dd>{t.esc(cmdb.status_word(ctx.conn, c))}</dd>"
            f"<dt>Company</dt><dd><a href='/company/{t.esc(c['entity_id'])}'>{t.esc(c['entity_name'])}</a></dd>"
            f"<dt>Site</dt><dd>{dash(c['site_name'])}</dd><dt>Location</dt><dd>{dash(c['location'])}</dd>"
            "<dt>Contact</dt><dd>" + (f"<a href='/contact/{t.esc(c['contact_id'])}'>{t.esc(c['contact_name'])}</a>" if c["contact_id"] else "—") + "</dd>"
            + (f"<dt>Tag #</dt><dd>{dash(c['tag_number'])}</dd>"
               "<dt>Parent</dt><dd>" + (f"<a href='/configuration/{t.esc(c['parent_configuration_id'])}'>{t.esc(c['parent_name'] or c['parent_configuration_id'])}</a>"
                                       if c["parent_configuration_id"] else "—") + "</dd>" if cw else ""))
    pod2 = "".join(f"<dt>{label}</dt><dd>{dash(c[key])}</dd>" for label, key in (
        ("Manufacturer", "manufacturer"), ("Model", "model"), ("Serial #", "serial_number"), ("Vendor", "vendor"),
        ("Purchased", "purchased_on"), ("Installed", "installed_on")))
    pod2 += (f"<dt>Installed by</dt><dd>{dash(c['installed_by'])}</dd>" if cw else "")
    pod2 += (f"<dt>Warranty ends</dt><dd>{_warranty_cell(ctx, c)}</dd><dt>Purchase ref</dt><dd>{dash(c['purchase_ref'])}</dd>"
             "<dt>Agreement</dt><dd>" + (f"<a href='/agreement/{t.esc(c['agreement_id'])}'>{t.esc(c['agreement_id'])}</a> {t.esc(c['agreement_name'] or '')}"
                                         if c["agreement_id"] else "—") + "</dd>")
    pod2 += "".join(f"<dt>{label}</dt><dd>{dash(c[key])}</dd>" for label, key in (
        ("DNS name", "dns_name"), ("Operating system", "os_name"), ("OS version", "os_version"), ("Description", "description"),
        ("ScreenConnect session", "remote_session_id"), ("AD object", "ad_object_guid"), ("Source", "source"),
        ("Added", "created_at"), ("Last synced from AD", "last_synced_at"), ("Last login", "last_seen_at")))
    notes = (f"<div class=card><h3>{t.icon('note')}Notes</h3><div class=note>{t.esc(c['notes'])}</div></div>" if cw and c["notes"] else "")
    kids_html = ("<div class=card><h3>" + t.icon("layers") + f"Child configurations · {len(kids)}</h3>"
                 + ("<ul class=plain>" + "".join(f"<li><a href='/configuration/{t.esc(k['configuration_id'])}'>{t.esc(k['name'])}</a> "
                                                 f"<span class=muted>· {t.esc(cmdb.type_word(ctx.conn, k))}</span></li>" for k in kids) + "</ul>"
                    if kids else "<div class=muted>None. A configuration names its parent in Change.</div>") + "</div>") if cw else ""
    person = ""
    if c["contact_id"]:
        bits = " · ".join(t.esc(x) for x in (c["contact_department"], c["contact_email"]) if x)
        person = (f"<div class=card><h3>{t.icon('users')}Contact</h3><p><a href='/contact/{t.esc(c['contact_id'])}'>"
                  f"{t.esc(c['contact_name'])}</a>" + (f"<br><span class=muted>{bits}</span>" if bits else "") + "</p></div>")
    edit = ""
    if _may_work(ctx):
        people = ctx.conn.execute(
            "SELECT contact_id, display_name FROM contact WHERE entity_id = ? AND inactive = 0"
            " ORDER BY display_name", (c["entity_id"],)).fetchall()
        sites = ctx.conn.execute("SELECT site_id, name FROM site WHERE entity_id = ? ORDER BY name",
                                 (c["entity_id"],)).fetchall()
        manual = c["source"] == "MANUAL"
        deals = ctx.conn.execute("SELECT agreement_id, name FROM agreement WHERE status <> 'CANCELLED' ORDER BY name").fetchall()
        parents = ctx.conn.execute("SELECT configuration_id, name FROM configuration WHERE entity_id = ? AND configuration_id <> ?"
                                   " AND status <> 'RETIRED' ORDER BY name LIMIT 2000", (c["entity_id"], configuration_id)).fetchall() if cw else []
        edit = (
            f"<div class=card><h3>{t.icon('edit')}Change</h3><form method=post action='/configuration/{cid}/update' class=fields>"
            "<div class=grid2>"
            + (f"<div><label>Name</label><input name=name value='{t.esc(c['name'])}' maxlength=100></div>" if manual else "")
            + f"<div><label>Type</label><select name=config_type>{_opts([(x['type_id'], x['name']) for x in cmdb.types(ctx.conn)], c['type_id'] or c['config_type'])}</select></div>"
            f"<div><label>Status</label><select name=status>{_opts([(x['status_id'], x['name']) for x in cmdb.statuses(ctx.conn)], c['status_id'] or c['status'])}</select></div>"
            f"<div><label>Contact</label><select name=contact_id>{_opts([('', '(none)')] + [(p['contact_id'], p['display_name']) for p in people], c['contact_id'] or '')}</select></div>"
            + (f"<div><label>Site</label><select name=site_id>{_opts([('', '(none)')] + [(x['site_id'], x['name']) for x in sites], c['site_id'] or '')}</select></div>" if sites else "")
            + f"<div><label>Location</label><input name=location value='{t.esc(c['location'] or '')}' maxlength=120 placeholder='Ward 3, room 302'></div>"
            + (f"<div><label>Tag #</label><input name=tag_number value='{t.esc(c['tag_number'] or '')}' maxlength=60></div>"
               f"<div><label>Parent configuration</label><select name=parent_configuration_id>{_opts([('', '(none)')] + [(p['configuration_id'], p['name']) for p in parents], c['parent_configuration_id'] or '')}</select></div>" if cw else "")
            + f"<div><label>Manufacturer</label><input name=manufacturer value='{t.esc(c['manufacturer'] or '')}' maxlength=100></div>"
            f"<div><label>Model</label><input name=model value='{t.esc(c['model'] or '')}' maxlength=100></div>"
            f"<div><label>Serial #</label><input name=serial_number value='{t.esc(c['serial_number'] or '')}' maxlength=100></div>"
            f"<div><label>Vendor</label><input name=vendor value='{t.esc(c['vendor'] or '')}' maxlength=100></div>"
            f"<div><label>Purchased on</label><input type=date name=purchased_on value='{t.esc(c['purchased_on'] or '')}'></div>"
            f"<div><label>Installed on</label><input type=date name=installed_on value='{t.esc(c['installed_on'] or '')}'></div>"
            + (f"<div><label>Installed by</label><input name=installed_by value='{t.esc(c['installed_by'] or '')}' maxlength=100></div>" if cw else "")
            + f"<div><label>Warranty ends on</label><input type=date name=warranty_ends_on value='{t.esc(c['warranty_ends_on'] or '')}'></div>"
            f"<div><label>Purchase ref (the PO)</label><input name=purchase_ref value='{t.esc(c['purchase_ref'] or '')}' maxlength=60></div>"
            f"<div><label>Agreement</label><select name=agreement_id>{_opts([('', '(none)')] + [(a['agreement_id'], a['agreement_id'] + ' ' + a['name']) for a in deals], c['agreement_id'] or '')}</select></div>"
            f"<div><label>ScreenConnect session id</label><input name=remote_session_id value='{t.esc(c['remote_session_id'] or '')}' placeholder='the GUID in the session URL'></div>"
            + (f"<div style='grid-column:1/-1'><label>Description</label><input name=description value='{t.esc(c['description'] or '')}' maxlength=400></div>" if manual else
               "<div style='grid-column:1/-1'><p class=why style='margin:8px 0 0'>Name, DNS name, OS and description are Active Directory's: change them there and re-import.</p></div>")
            + (f"<div style='grid-column:1/-1'><label>Notes</label><textarea name=notes rows=3 maxlength=2000>{t.esc(c['notes'] or '')}</textarea></div>" if cw else "")
            + "</div><div style='margin-top:12px'><button type=submit>Save</button></div></form></div>")
    return ("<div class=rail>"
            f"<div><div class=card><h3>{t.icon('monitor')}Configuration</h3><dl class=kv>{pod1}</dl></div>"
            f"<div class=card><h3>{t.icon('info')}Details</h3><dl class=kv>{pod2}</dl></div>{notes}{kids_html}</div>"
            f"<div>{_answers_card(ctx, c)}{person}{edit}</div></div>")


def _answers_card(ctx, c) -> str:
    """The questions the configuration's type asks (056), with their answers;
    a form for a member who may work a board."""
    qs = cmdb.answers(ctx.conn, c["configuration_id"])
    if not qs:
        return ""
    if not _may_work(ctx):
        rows = "".join(f"<dt>{t.esc(q['label'])}</dt><dd>{t.esc(('Yes' if q['value'] == '1' else 'No') if q['field_type'] == 'CHECKBOX' else (q['value'] or '—'))}</dd>" for q in qs)
        return f"<div class=card><h3>{t.icon('note')}{t.esc(cmdb.type_word(ctx.conn, c))} details</h3><dl class=kv>{rows}</dl></div>"
    fields = []
    for q in qs:
        n = f"q{q['question_id']}"
        star = " <span class=muted>(needed)</span>" if q["required"] else ""
        if q["field_type"] == "CHECKBOX":
            fields.append(f"<label><input type=checkbox name='{n}' value=1{' checked' if q['value'] == '1' else ''}> {t.esc(q['label'])}{star}</label>")
        elif q["field_type"] == "DATE":
            fields.append(f"<label>{t.esc(q['label'])}{star}</label><input type=date name='{n}' value='{t.esc(q['value'] or '')}'>")
        elif q["field_type"] == "NUMBER":
            fields.append(f"<label>{t.esc(q['label'])}{star}</label><input name='{n}' inputmode=decimal value='{t.esc(q['value'] or '')}'>")
        else:
            fields.append(f"<label>{t.esc(q['label'])}{star}</label><input name='{n}' maxlength=400 value='{t.esc(q['value'] or '')}'>")
    return (f"<div class=card><h3>{t.icon('note')}{t.esc(cmdb.type_word(ctx.conn, c))} details</h3>"
            f"<form method=post action='/configuration/{t.esc(c['configuration_id'])}/answers' class=fields>" + "".join(fields)
            + "<div style='margin-top:12px'><button type=submit>Save</button></div></form></div>")


def answers(ctx, configuration_id: str):
    from .. import HttpError, redirect
    _fulfiller(ctx)
    if not _may_work(ctx):
        raise HttpError("403 Forbidden", "Changing a configuration takes WORK on a board.")
    f = ctx.request.form()
    base = f"/configuration/{urllib.parse.quote(configuration_id)}?"
    values = {k[1:]: v for k, v in f.items() if k.startswith("q") and k[1:].isdigit()}
    try:
        changed = cmdb.save_answers(ctx.conn, configuration_id, values, at=ctx.now, actor=ctx.user.id)
    except LookupError:
        raise HttpError("404 Not Found", "No such configuration.")
    except ValueError as exc:
        ctx.conn.rollback()
        return redirect(base + urllib.parse.urlencode({"err": str(exc)}))
    ctx.conn.commit()
    return redirect(base + urllib.parse.urlencode({"msg": "Saved." if changed else "Nothing changed."}))


def update(ctx, configuration_id: str):
    from .. import HttpError, redirect
    _fulfiller(ctx)
    if not _may_work(ctx):
        raise HttpError("403 Forbidden", "Changing a configuration takes WORK on a board.")
    f = ctx.request.form()
    base = f"/configuration/{urllib.parse.quote(configuration_id)}?"
    try:
        changed = cmdb.update(
            ctx.conn, configuration_id, at=ctx.now, actor=ctx.user.id,
            config_type=f.get("config_type"), status=f.get("status"),
            contact_id=f.get("contact_id", None), remote_session_id=f.get("remote_session_id"),
            serial_number=f.get("serial_number"), manufacturer=f.get("manufacturer"), model=f.get("model"),
            site_id=f.get("site_id", None), name=f.get("name"), description=f.get("description"),
            purchased_on=f.get("purchased_on"), warranty_ends_on=f.get("warranty_ends_on"), installed_on=f.get("installed_on"),
            vendor=f.get("vendor"), purchase_ref=f.get("purchase_ref"), location=f.get("location"),
            agreement_id=f.get("agreement_id", None), tag_number=f.get("tag_number"), installed_by=f.get("installed_by"),
            notes=f.get("notes"), parent_configuration_id=f.get("parent_configuration_id", None))
    except LookupError as exc:
        if "no configuration" in str(exc):
            raise HttpError("404 Not Found", "No such configuration.")
        return redirect(base + urllib.parse.urlencode({"err": str(exc)}))
    except ValueError as exc:
        return redirect(base + urllib.parse.urlencode({"err": str(exc)}))
    ctx.conn.commit()
    return redirect(base + urllib.parse.urlencode(
        {"msg": "Saved: " + ", ".join(x.replace("_", " ") for x in changed) if changed
         else "Nothing changed."}))


# ------------------------------------------------------ 048: the maintenance record

def _maintenance_response(ctx, rows, filename: str):
    from .. import Response
    common.audit_restricted_reads(ctx, [r["board_id"] for r in rows], detail=f"maintenance export {filename}:")
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\r\n")
    w.writerow(["Configuration", "Type", "Serial", "Ticket", "Summary", "Board", "Ticket type", "State", "Opened", "Closed",
                "Owner", "Hours", "Visits"])
    for r in rows:
        w.writerow(["'" + v if isinstance(v, str) and v[:1] in "=+-@" else v for v in (
            r["configuration"], r["config_type"], r["serial_number"], r["work_item_id"], r["summary"], r["board"],
            r["record_type"], r["state"], r["opened_at"], r["closed_at"], r["owner"], float(r["hours"] or 0), r["visits"])])
    return Response(body=buf.getvalue(), content_type="text/csv; charset=utf-8", headers=[
        ("Content-Disposition", f'attachment; filename="{filename}"'), ("Cache-Control", "no-store")])


def maintenance_csv(ctx, configuration_id: str):
    """One machine's maintenance record: every ticket on it that the reader
    may see, with hours and visits. What a DOH inspection asks for, per asset."""
    from .. import HttpError
    boards = _fulfiller(ctx)
    if ctx.conn.execute("SELECT 1 FROM configuration WHERE configuration_id = ?", (configuration_id,)).fetchone() is None:
        raise HttpError("404 Not Found", "No such configuration.")
    q = ctx.request.query
    rows = cmdb.maintenance(ctx.conn, [configuration_id], boards=boards, since=q.get("from") or None, until=q.get("to") or None)
    return _maintenance_response(ctx, rows, f"maintenance-{configuration_id}.csv")


def maintenance_csv_all(ctx):
    """The same record for every machine the list's filters show."""
    boards = _fulfiller(ctx)
    _text, _kind, _status, _entity, _sort, _warranty, where, params = _list_filters(ctx)
    ids = [r[0] for r in ctx.conn.execute(
        f"SELECT c.configuration_id FROM configuration c WHERE {' AND '.join(where)} ORDER BY c.name LIMIT 500", params)]
    q = ctx.request.query
    rows = cmdb.maintenance(ctx.conn, ids, boards=boards, since=q.get("from") or None, until=q.get("to") or None)
    return _maintenance_response(ctx, rows, "maintenance.csv")


# ------------------------------------------------------ the ticket's card

def ticket_card(ctx, tk, *, can_work: bool) -> str:
    wid = t.esc(tk["work_item_id"])
    rows = ctx.conn.execute(
        "SELECT c.*, NULL AS contact_name FROM ticket_configuration tc"
        " JOIN configuration c ON c.configuration_id = tc.configuration_id"
        " WHERE tc.work_item_id = ? ORDER BY c.name", (tk["work_item_id"],)).fetchall()
    items = "".join(
        f"<li><a href='/configuration/{t.esc(r['configuration_id'])}'>{t.esc(r['name'])}</a> "
        f"<span class=muted>{t.esc(r['config_type'].title())}</span> "
        f"{links_html(ctx, 'CONFIGURATION', r)}"
        + (f"<form method=post action='/ticket/{wid}/config/remove' style='display:inline'>"
           f"<input type=hidden name=configuration_id value='{t.esc(r['configuration_id'])}'>"
           "<button class='ghost small' type=submit title='Remove from this ticket'>×</button></form>"
           if can_work else "") + "</li>" for r in rows)
    add = ""
    if can_work:
        linked = {r["configuration_id"] for r in rows}
        # The company's own machines, the contact's first; if the company has
        # none on record (or the ticket has no company yet), every active
        # machine, named with its company, because the technician on site
        # knows the machine name and should not be stopped by a missing field.
        options = ctx.conn.execute(
            "SELECT configuration_id, name, contact_id, entity_id FROM configuration"
            " WHERE entity_id = ? AND status = 'ACTIVE'"
            " ORDER BY CASE WHEN contact_id = ? THEN 0 ELSE 1 END, name LIMIT 1000",
            (tk["entity_id"] or "", tk["contact_id"])).fetchall()
        scope = "company"
        if not options:
            options = ctx.conn.execute(
                "SELECT configuration_id, name, contact_id, entity_id FROM configuration"
                " WHERE status = 'ACTIVE' ORDER BY name LIMIT 2000").fetchall()
            scope = "all"
        opts = "".join(
            f"<option value='{t.esc(o['name'])}' data-id='{t.esc(o['configuration_id'])}'>"
            + t.esc((" · contact's" if tk["contact_id"] and o["contact_id"] == tk["contact_id"] else "")
                    if scope == "company" else f" · {o['entity_id']}")
            + "</option>" for o in options if o["configuration_id"] not in linked)
        if opts:
            listid = f"cfg-{wid}"
            add = (f"<form method=post action='/ticket/{wid}/config/add' class=row "
                   f"style='margin-top:8px'><div><input name=name list='{listid}' required "
                   f"placeholder='Type a machine name' autocomplete=off><datalist id='{listid}'>{opts}"
                   "</datalist></div><div style='flex:0 0 auto'>"
                   "<button type=submit class=ghost>" + t.icon("plus") + " Attach</button></div></form>"
                   + ("" if scope == "company" else
                      "<p class=why style='margin:6px 0 0'>This ticket's company has no machines on "
                      "record, so every active machine is offered, with its company.</p>"))
        else:
            add = ("<p class=why style='margin:6px 0 0'>No machines on record to attach. Import them "
                   "from Active Directory (Setup › Integrations, <code>import-computers</code>).</p>")
    return ("<div class=card data-pod=configurations><h3><svg class=ic aria-hidden=true><use href=#i-monitor></use></svg>Configurations</h3>"
            + (f"<ul class=plain>{items}</ul>" if items else
               "<div class=muted>None attached.</div>") + add + "</div>")


def _ticket_back(ctx, work_item_id: str) -> str:
    """The ticket, or the ticket tab the form came from (7 Oct: ticket tabs)."""
    base = f"/ticket/{urllib.parse.quote(work_item_id)}"
    back = (ctx.request.form().get("back") or "").strip()
    return back if back.startswith(base + "/") and "//" not in back[1:] and "?" not in back else base


def attach(ctx, work_item_id: str):
    from .. import HttpError, redirect
    tk = ctx.conn.execute("SELECT board_id FROM ticket WHERE work_item_id = ?",
                          (work_item_id,)).fetchone()
    if tk is None:
        raise HttpError("404 Not Found", "No such ticket.")
    common.require_board(ctx, tk["board_id"], need="WORK")
    f = ctx.request.form()
    cid = f.get("configuration_id", "").strip()
    if not cid:
        # The card's search box posts the machine's name (a datalist cannot post
        # the id). Exact name first, then a single case-insensitive match.
        name = f.get("name", "").strip()
        rows = ctx.conn.execute(
            "SELECT configuration_id FROM configuration WHERE status = 'ACTIVE' AND"
            " (name = ? OR LOWER(name) = LOWER(?)) ORDER BY CASE WHEN name = ? THEN 0 ELSE 1 END LIMIT 2",
            (name, name, name)).fetchall()
        if not rows:
            return redirect(f"/ticket/{urllib.parse.quote(work_item_id)}?err="
                            + urllib.parse.quote(f"No machine named {name!r} on record"))
        cid = rows[0]["configuration_id"]
    try:
        cmdb.attach(ctx.conn, work_item_id, cid, at=ctx.now, actor=ctx.user.id)
    except LookupError:
        raise HttpError("404 Not Found", "No such configuration.")
    ctx.conn.commit()
    return redirect(_ticket_back(ctx, work_item_id) + "?msg=" + urllib.parse.quote("Machine attached"))


def detach(ctx, work_item_id: str):
    from .. import HttpError, redirect
    tk = ctx.conn.execute("SELECT board_id FROM ticket WHERE work_item_id = ?",
                          (work_item_id,)).fetchone()
    if tk is None:
        raise HttpError("404 Not Found", "No such ticket.")
    common.require_board(ctx, tk["board_id"], need="WORK")
    cmdb.detach(ctx.conn, work_item_id, ctx.request.form().get("configuration_id", ""),
                at=ctx.now, actor=ctx.user.id)
    ctx.conn.commit()
    return redirect(_ticket_back(ctx, work_item_id))


# ------------------------------------------------- Setup › Integrations

def integrations(ctx):
    from .. import Response
    common.require_sysadmin(ctx)
    msg = ctx.request.query.get("msg", "")
    err = ctx.request.query.get("err", "")
    rows = ctx.conn.execute("SELECT * FROM integration_link ORDER BY applies_to, label").fetchall()
    body_rows = "".join(
        f"<tr><td>{t.esc(r['label'])}</td><td>{t.esc(r['applies_to'].title())}</td>"
        f"<td><code>{t.esc(r['url_template'])}</code></td>"
        f"<td>{'<span class=chip>off</span>' if r['inactive'] else 'on'}</td>"
        f"<td><form method=post action='/admin/integrations/toggle'>"
        f"<input type=hidden name=link_id value='{t.esc(r['link_id'])}'>"
        f"<button class=ghost type=submit>{'Turn on' if r['inactive'] else 'Turn off'}</button>"
        "</form></td></tr>" for r in rows) or \
        "<tr><td colspan=5 class=muted>No links yet.</td></tr>"
    fields = "; ".join(f"{k.title()}: " + ", ".join("{" + f + "}" for f in v)
                       for k, v in cmdb.LINK_FIELDS.items())
    body = (
        (f"<div class='banner ok'>{t.esc(msg)}</div>" if msg else "")
        + (f"<div class='banner err'>{t.esc(err)}</div>" if err else "")
        + "<h1>Integrations</h1><p class=sub>Links out to the tools the desk does not replace, "
        "drawn on every configuration or contact. Each is a URL template: HTTPS, a fixed host, "
        "and fields in braces that are filled in and URL-encoded per record.</p>"
        "<div class=card><div class=tablewrap><table><thead><tr><th>Label</th><th>On</th>"
        "<th>Template</th><th>State</th><th></th></tr></thead>"
        f"<tbody>{body_rows}</tbody></table></div></div>"
        "<div class=card><h3><svg class=ic aria-hidden=true><use href=#i-link></use></svg>Add a link</h3><form method=post action='/admin/integrations/add' "
        "class=fields><label>Label</label><input name=label required placeholder='ScreenConnect'>"
        "<label>Shown on</label><select name=applies_to><option value=CONFIGURATION>"
        "Configurations</option><option value=CONTACT>Contacts</option></select>"
        "<label>URL template</label><input name=url_template required "
        "placeholder='https://INSTANCE.screenconnect.com/Host#Access/All%20Machines//"
        "{remote_session_id}/Join'>"
        f"<p class=why>Fields you can use: {t.esc(fields)}. The ScreenConnect shape is the one "
        "its integrations document (NinjaOne, Syncro); put your own instance in place of "
        "INSTANCE.</p><div><button type=submit>Add link</button></div></form></div>")
    body += _teams_card(ctx)
    return Response(body=t.page("Integrations", body, user=ctx.user, active="admin"))


def _teams_card(ctx) -> str:
    """Setup › Integrations › Teams channels (050): the names the desk posts
    cards to. The address behind a name lives on the host, in the sender's
    webhook file, never here."""
    from ... import channels
    rows = channels.targets(ctx.conn)
    lines = "".join(
        f"<tr><td><code>{t.esc(r['target_id'])}</code></td><td>{t.esc(r['label'])}</td>"
        f"<td><form method=post action='/admin/integrations/teams/pages' class=inline>"
        f"<input type=hidden name=target_id value='{t.esc(r['target_id'])}'><input type=hidden name=pages value={0 if r['pages'] else 1}>"
        f"<button class=ghost type=submit title='Whether pages to the on-call also post here'>{'Pages: yes' if r['pages'] else 'Pages: no'}</button></form></td>"
        f"<td>{'<span class=chip>off</span>' if r['inactive'] else 'on'}</td>"
        f"<td><form method=post action='/admin/integrations/teams/toggle' class=inline>"
        f"<input type=hidden name=target_id value='{t.esc(r['target_id'])}'>"
        f"<button class=ghost type=submit>{'Turn on' if r['inactive'] else 'Turn off'}</button></form></td></tr>"
        for r in rows) or "<tr><td colspan=5 class=muted>No Teams channels yet.</td></tr>"
    return ("<div class=card><h3>" + t.icon("bell") + "Teams channels</h3>"
            "<p class=why>A workflow rule can notify a Teams channel as a card, and a page to the on-call posts to every "
            "channel that carries pages. Name the channel here; the webhook address goes on the host, in the Teams "
            "sender's file, keyed by this name. A card carries the ticket number, board, priority, status and owner and "
            "the rule's words: never the summary, never a note.</p>"
            "<div class=tablewrap><table><thead><tr><th>Name</th><th>Label</th><th>Carries pages</th><th>State</th><th></th></tr></thead>"
            f"<tbody>{lines}</tbody></table></div>"
            "<form method=post action='/admin/integrations/teams/add' class=fields style='margin-top:10px'>"
            "<label>Name (the key in the host's webhook file)</label><input name=target_id required placeholder='helpdesk-alerts' pattern='[a-z0-9][a-z0-9-]{1,39}'>"
            "<label>Label</label><input name=label required placeholder='IT Helpdesk › Alerts'>"
            "<label><input type=checkbox name=pages value=1> Carries pages to the on-call</label>"
            "<div style='margin-top:8px'><button type=submit>Add the channel</button></div></form></div>")


def teams_add(ctx):
    from .. import redirect
    from ... import channels
    common.require_sysadmin(ctx)
    f = ctx.request.form()
    try:
        name = channels.add_target(ctx.conn, f.get("target_id", ""), label=f.get("label", ""),
                                   pages=f.get("pages") == "1", at=ctx.now, actor=ctx.user.id)
    except channels.Refused as exc:
        ctx.conn.rollback()
        return redirect("/admin/integrations?" + urllib.parse.urlencode({"err": str(exc)}))
    ctx.conn.commit()
    return redirect("/admin/integrations?" + urllib.parse.urlencode({"msg": f"Teams channel {name} added; give the host's webhook file its address"}))


def teams_toggle(ctx):
    from .. import redirect
    from ... import channels
    common.require_sysadmin(ctx)
    tid = ctx.request.form().get("target_id", "")
    try:
        row = channels.get(ctx.conn, tid)
        changed = channels.set_active(ctx.conn, tid, bool(row["inactive"]) if row else True, at=ctx.now, actor=ctx.user.id)
    except channels.Refused as exc:
        return redirect("/admin/integrations?" + urllib.parse.urlencode({"err": str(exc)}))
    ctx.conn.commit()
    return redirect("/admin/integrations?msg=" + ("Teams+channel+updated" if changed else "Nothing+changed"))


def teams_pages(ctx):
    from .. import redirect
    from ... import channels
    common.require_sysadmin(ctx)
    f = ctx.request.form()
    try:
        changed = channels.set_pages(ctx.conn, f.get("target_id", ""), f.get("pages") == "1", at=ctx.now, actor=ctx.user.id)
    except channels.Refused as exc:
        return redirect("/admin/integrations?" + urllib.parse.urlencode({"err": str(exc)}))
    ctx.conn.commit()
    return redirect("/admin/integrations?msg=" + ("Teams+channel+updated" if changed else "Nothing+changed"))


def integrations_add(ctx):
    from .. import redirect
    common.require_sysadmin(ctx)
    f = ctx.request.form()
    try:
        cmdb.add_link(ctx.conn, label=f.get("label", ""), applies_to=f.get("applies_to", ""),
                      url_template=f.get("url_template", ""), at=ctx.now, actor=ctx.user.id)
    except ValueError as exc:
        return redirect("/admin/integrations?" + urllib.parse.urlencode({"err": str(exc)}))
    ctx.conn.commit()
    return redirect("/admin/integrations?msg=Link+added")


def integrations_toggle(ctx):
    from .. import redirect
    from ... import db
    common.require_sysadmin(ctx)
    link_id = ctx.request.form().get("link_id", "")
    cur = ctx.conn.execute("UPDATE integration_link SET inactive = 1 - inactive WHERE link_id = ?",
                           (link_id,))
    if cur.rowcount:
        db.audit(ctx.conn, at=ctx.now.isoformat(sep=" ", timespec="minutes"), actor=ctx.user.id,
                 action="INTEGRATION_LINK_TOGGLE", subject_kind="integration_link",
                 subject_id=link_id)
        ctx.conn.commit()
    return redirect("/admin/integrations?msg=Saved")

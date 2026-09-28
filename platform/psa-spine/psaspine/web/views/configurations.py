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

import urllib.parse

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
         "tickets": "open_tickets DESC, c.name", "company": "c.entity_id, c.name"}


def _opts(pairs, sel):
    return "".join(f"<option value='{t.esc(k)}'{' selected' if k == sel else ''}>{t.esc(v)}</option>"
                   for k, v in pairs)


def index(ctx):
    """Dada PSA's Configurations list: counts by type that filter, status
    and company filters, a search box, every column sorts, and how many open
    tickets each machine has. Below it, the form for a machine typed in by
    hand (AD's own arrive by import)."""
    from .. import Response
    _fulfiller(ctx)
    q = ctx.request.query
    text = q.get("q", "").strip()
    kind = q.get("type", "") if q.get("type", "") in cmdb.TYPES else ""
    status = q.get("status", "ACTIVE")
    if status not in cmdb.STATUSES + ("ALL",):
        status = "ACTIVE"
    entity = q.get("company", "")
    sort = q.get("sort", "name") if q.get("sort", "name") in SORTS else "name"
    where, params = ["1 = 1"], []
    if text:
        where.append("(c.name LIKE ? OR c.serial_number LIKE ? OR c.description LIKE ? OR c.dns_name LIKE ?)")
        params += [f"%{text}%"] * 4
    if kind:
        where.append("c.config_type = ?"); params.append(kind)
    if status != "ALL":
        where.append("c.status = ?"); params.append(status)
    if entity:
        where.append("c.entity_id = ?"); params.append(entity)
    rows = ctx.conn.execute(
        "SELECT c.*, ct.display_name AS contact_name, e.name AS entity_name,"
        "       (SELECT COUNT(*) FROM ticket_configuration tc JOIN ticket t ON t.work_item_id = tc.work_item_id"
        "         WHERE tc.configuration_id = c.configuration_id"
        "           AND t.state NOT IN ('RESOLVED','CLOSED','CANCELLED')) AS open_tickets"
        "  FROM configuration c JOIN entity e ON e.entity_id = c.entity_id"
        "  LEFT JOIN contact ct ON ct.contact_id = c.contact_id"
        f" WHERE {' AND '.join(where)} ORDER BY {SORTS[sort]} LIMIT 500", params).fetchall()
    total = ctx.conn.execute(f"SELECT COUNT(*) FROM configuration c WHERE {' AND '.join(where)}", params).fetchone()[0]
    counts = {r["config_type"]: r["n"] for r in ctx.conn.execute(
        "SELECT config_type, COUNT(*) AS n FROM configuration WHERE status = 'ACTIVE' GROUP BY config_type")}
    active = sum(counts.values())

    def keep(**kw):
        d = {"q": text, "type": kind, "status": status, "company": entity, "sort": sort}
        d.update(kw)
        return "/configurations?" + urllib.parse.urlencode({k: v for k, v in d.items() if v and not (k == "status" and v == "ACTIVE")})
    tiles = (f"<a class='tile{' on' if not kind else ''}' href='{keep(type='')}'><div class=n>{active}</div><div class=l>Active, all types</div></a>"
             + "".join(f"<a class='tile{' on' if kind == k else ''}' href='{keep(type=k)}'><div class=n>{counts.get(k, 0)}</div>"
                       f"<div class=l>{v}</div></a>" for k, v in TYPE_WORDS.items()))
    companies = ctx.conn.execute("SELECT entity_id, name FROM entity ORDER BY name").fetchall()
    filters = (
        "<form method=get class=row style='margin-bottom:10px'>"
        f"<input type=hidden name=type value='{t.esc(kind)}'><input type=hidden name=sort value='{t.esc(sort)}'>"
        f"<div><input name=q value='{t.esc(text)}' placeholder='name, DNS name, serial or description'></div>"
        f"<div style='flex:0 0 auto'><select name=status>{_opts([('ACTIVE', 'Active'), ('INACTIVE', 'Inactive'), ('RETIRED', 'Retired'), ('ALL', 'All statuses')], status)}</select></div>"
        f"<div style='flex:0 0 auto'><select name=company>{_opts([('', 'Every company')] + [(e['entity_id'], e['name']) for e in companies], entity)}</select></div>"
        "<div style='flex:0 0 auto'><button type=submit>Filter</button></div></form>")

    def th(key, label):
        return f"<th><a href='{keep(sort=key)}'{' class=on' if sort == key else ''}>{label}</a></th>"
    body_rows = "".join(
        f"<tr><td><a href='/configuration/{t.esc(r['configuration_id'])}'>{t.esc(r['name'])}</a>"
        + (f" <span class=chip>{t.esc(r['status'].lower())}</span>" if r["status"] != "ACTIVE" else "")
        + (" <span class=muted>by hand</span>" if r["source"] == "MANUAL" else "") + "</td>"
        f"<td>{t.esc(r['entity_name'])}</td><td>{t.esc(r['config_type'].title())}</td>"
        f"<td>{t.esc(r['os_name'] or '—')}</td><td>{t.esc(r['contact_name'] or '—')}</td>"
        f"<td>{t.esc((r['last_seen_at'] or '—')[:10])}</td>"
        f"<td class=num>{r['open_tickets'] or ''}</td><td>{links_html(ctx, 'CONFIGURATION', r)}</td></tr>" for r in rows)
    table = ("<div class=tablewrap><table><thead><tr>" + th("name", "Name") + th("company", "Company") + th("type", "Type")
             + th("os", "OS") + th("contact", "Contact") + th("seen", "Last seen") + th("tickets", "Open")
             + "<th></th></tr></thead><tbody>" + body_rows + "</tbody></table></div>"
             if rows else "<div class=muted>Nothing matches. Import machines from AD: psaspine import-computers; "
                          "or add one by hand below.</div>")
    shown = f"<p class=why>{len(rows)} of {total} shown.</p>" if total > len(rows) else f"<p class=why>{total} configuration(s).</p>"
    add = ""
    if _may_work(ctx):
        add = (
            "<div class=card><h3>" + t.icon("plus") + "Add a configuration by hand</h3><p class=sub>A printer, a network "
            "device, a machine Active Directory does not know. AD's own machines arrive by import and are never typed.</p>"
            "<form method=post action='/configurations/new' class=fields><div class=grid2>"
            "<div><label>Name</label><input name=name required maxlength=100 placeholder='PRN-WARD3-01'></div>"
            f"<div><label>Company</label><select name=entity_id>{_opts([(e['entity_id'], e['name']) for e in companies], 'PMC')}</select></div>"
            f"<div><label>Type</label><select name=config_type>{_opts([(x, x.title()) for x in cmdb.TYPES], 'PRINTER')}</select></div>"
            "<div><label>Serial</label><input name=serial_number maxlength=100></div>"
            "<div><label>Manufacturer</label><input name=manufacturer maxlength=100></div>"
            "<div><label>Model</label><input name=model maxlength=100></div>"
            "<div style='grid-column:1/-1'><label>Description</label><input name=description maxlength=400 placeholder='where it is, what it does'></div>"
            "</div><div style='margin-top:10px'><button type=submit>Add</button></div></form></div>")
    msg, err = q.get("msg", ""), q.get("err", "")
    body = (
        (f"<div class='banner ok'>{t.esc(msg)}</div>" if msg else "")
        + (f"<div class='banner err'>{t.esc(err)}</div>" if err else "")
        + "<h1>Configurations</h1><p class=sub>The machines and devices the desk supports, as Dada PSA's "
          "Configurations: from Active Directory, or typed in by hand. Open one to launch its remote session, "
          "see its tickets and its history, or raise a ticket for it.</p>"
        + f"<div class='tiles' style='grid-template-columns:repeat(8,1fr)'>{tiles}</div>"
        + "<div class=card>" + filters + table + shown + "</div>" + add)
    return Response(body=t.page("Configurations", body, user=ctx.user, active="companies"))


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
                          model=f.get("model"), description=f.get("description"))
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


def detail(ctx, configuration_id: str):
    from .. import HttpError, Response
    boards = _fulfiller(ctx)
    c = ctx.conn.execute(
        "SELECT c.*, e.name AS entity_name, ct.display_name AS contact_name, ct.email AS contact_email,"
        "       ct.department AS contact_department, s.name AS site_name FROM configuration c"
        " JOIN entity e ON e.entity_id = c.entity_id"
        " LEFT JOIN contact ct ON ct.contact_id = c.contact_id"
        " LEFT JOIN site s ON s.site_id = c.site_id"
        " WHERE c.configuration_id = ?", (configuration_id,)).fetchone()
    if c is None:
        raise HttpError("404 Not Found", "No such configuration.")
    msg = ctx.request.query.get("msg", "")
    err = ctx.request.query.get("err", "")
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
            " AND t.state IN ('RESOLVED','CLOSED','CANCELLED') ORDER BY t.closed_at DESC LIMIT 10",
            [configuration_id] + shown_boards).fetchall()
    closed_html = ("<ul class=plain>" + "".join(
        f"<li><a href='/ticket/{t.esc(r['work_item_id'])}'>{t.esc(r['work_item_id'])}</a> {t.esc(r['summary'])} "
        f"<span class=muted>· {t.esc(r['board_name'])} · closed {t.esc((r['closed_at'] or '')[:10])}</span></li>"
        for r in closed) + "</ul>") if closed else "<div class=muted>None.</div>"
    facts = "".join(f"<dt>{label}</dt><dd>{t.esc(str(c[key]) if c[key] else '—')}</dd>" for label, key in (
        ("Type", "config_type"), ("Status", "status"), ("DNS name", "dns_name"), ("Operating system", "os_name"),
        ("OS version", "os_version"), ("Manufacturer", "manufacturer"), ("Model", "model"), ("Serial", "serial_number"),
        ("Description", "description"), ("Site", "site_name"), ("ScreenConnect session", "remote_session_id"),
        ("AD object", "ad_object_guid"), ("Source", "source"), ("Added", "created_at"),
        ("Last synced from AD", "last_synced_at"), ("Last seen in AD", "last_seen_at")))
    person = ""
    if c["contact_id"]:
        bits = " · ".join(t.esc(x) for x in (c["contact_department"], c["contact_email"]) if x)
        person = (f"<div class=card><h3>{t.icon('users')}Contact</h3><p><a href='/contact/{t.esc(c['contact_id'])}'>"
                  f"{t.esc(c['contact_name'])}</a>" + (f"<br><span class=muted>{bits}</span>" if bits else "") + "</p></div>")
    raise_qs = urllib.parse.urlencode({k: v for k, v in {
        "configuration_id": configuration_id, "entity_id": c["entity_id"],
        "requested_by": (c["contact_email"] or "")}.items() if v})
    edit = ""
    if _may_work(ctx):
        people = ctx.conn.execute(
            "SELECT contact_id, display_name FROM contact WHERE entity_id = ? AND inactive = 0"
            " ORDER BY display_name", (c["entity_id"],)).fetchall()
        sites = ctx.conn.execute("SELECT site_id, name FROM site WHERE entity_id = ? ORDER BY name",
                                 (c["entity_id"],)).fetchall()
        manual = c["source"] == "MANUAL"
        edit = (
            f"<div class=card><h3>{t.icon('flag')}Change</h3><form method=post action='/configuration/"
            f"{t.esc(configuration_id)}/update' class=fields>"
            + (f"<label>Name</label><input name=name value='{t.esc(c['name'])}' maxlength=100>" if manual else "")
            + f"<label>Type</label><select name=config_type>{_opts([(x, x.title()) for x in cmdb.TYPES], c['config_type'])}</select>"
            f"<label>Status</label><select name=status>{_opts([(x, x.title()) for x in cmdb.STATUSES], c['status'])}</select>"
            f"<label>Contact</label><select name=contact_id>{_opts([('', '(none)')] + [(p['contact_id'], p['display_name']) for p in people], c['contact_id'] or '')}</select>"
            + (f"<label>Site</label><select name=site_id>{_opts([('', '(none)')] + [(x['site_id'], x['name']) for x in sites], c['site_id'] or '')}</select>" if sites else "")
            + f"<label>Manufacturer</label><input name=manufacturer value='{t.esc(c['manufacturer'] or '')}' maxlength=100>"
            f"<label>Model</label><input name=model value='{t.esc(c['model'] or '')}' maxlength=100>"
            f"<label>Serial</label><input name=serial_number value='{t.esc(c['serial_number'] or '')}' maxlength=100>"
            + (f"<label>Description</label><input name=description value='{t.esc(c['description'] or '')}' maxlength=400>" if manual else
               "<p class=why style='margin:8px 0 0'>Name, DNS name, OS and description are Active Directory's: change them there and re-import.</p>")
            + f"<label>ScreenConnect session id</label><input name=remote_session_id "
            f"value='{t.esc(c['remote_session_id'] or '')}' placeholder='the GUID in the session URL'>"
            "<div style='margin-top:12px'><button type=submit>Save</button></div></form></div>")
    body = (
        (f"<div class='banner ok'>{t.esc(msg)}</div>" if msg else "")
        + (f"<div class='banner err'>{t.esc(err)}</div>" if err else "")
        + f"<h1>{t.esc(c['name'])} <span class=chip>{t.esc(c['config_type'].title())}</span>"
        + (f" <span class=chip>{t.esc(c['status'].lower())}</span>" if c["status"] != "ACTIVE" else "")
        + "</h1>"
        f"<p class=sub><a href='/company/{t.esc(c['entity_id'])}'>{t.esc(c['entity_name'])}</a>"
        + (f" · <a href='/contact/{t.esc(c['contact_id'])}'>{t.esc(c['contact_name'])}</a>" if c["contact_id"] else "")
        + (f" · {t.esc(c['os_name'])}" if c["os_name"] else "")
        + (" · typed in by hand" if c["source"] == "MANUAL" else " · from Active Directory") + "</p>"
        + f"<p>{links_html(ctx, 'CONFIGURATION', c)} "
        + (f"<a class='btn' href='/ticket/new?{raise_qs}'>{t.icon('plus')} Raise a ticket for this machine</a>" if _may_work(ctx) else "")
        + "</p><div class=rail>"
        f"<div><div class=card><h3>{t.icon('ticket')}Open tickets</h3>{tickets_html}{_hidden_note(hidden)}</div>"
        f"<div class=card><h3>{t.icon('check')}Recently closed</h3>{closed_html}</div>"
        f"<div class=card><h3>{t.icon('clock')}History</h3>{_history(ctx, configuration_id)}</div></div>"
        f"<div><div class=card><h3>{t.icon('monitor')}Configuration</h3><dl class=kv>{facts}</dl></div>{person}{edit}</div></div>")
    return Response(body=t.page(c["name"], body, user=ctx.user, active="companies"))


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
            site_id=f.get("site_id", None), name=f.get("name"), description=f.get("description"))
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
    return redirect(f"/ticket/{urllib.parse.quote(work_item_id)}?msg="
                    + urllib.parse.quote("Machine attached"))


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
    return redirect(f"/ticket/{urllib.parse.quote(work_item_id)}")


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
    return Response(body=t.page("Integrations", body, user=ctx.user, active="admin"))


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

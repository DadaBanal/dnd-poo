"""Configurations, the ticket's Configurations card, and Setup › Integrations.

ConnectWise's Configurations: the machines under a company, each opening its
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


def index(ctx):
    from .. import Response
    _fulfiller(ctx)
    q = ctx.request.query.get("q", "").strip()
    rows = search(ctx, q, include_inactive=bool(ctx.request.query.get("all")))
    body = (
        "<h1>Configurations</h1><p class=sub>The machines the desk supports, from Active "
        "Directory. Open one to launch its remote session or see its tickets.</p><div class=card>"
        f"<form method=get class=row style='margin-bottom:10px'><div><input name=q value='{t.esc(q)}' "
        "placeholder='name, serial or description'></div>"
        "<div style='flex:0 0 auto'><label style='display:inline'><input type=checkbox name=all value=1"
        + (" checked" if ctx.request.query.get("all") else "") + "> include inactive</label></div>"
        "<div style='flex:0 0 auto'><button type=submit>Search</button></div></form>"
        + table(ctx, rows) + "</div>")
    return Response(body=t.page("Configurations", body, user=ctx.user, active="companies"))


def detail(ctx, configuration_id: str):
    from .. import HttpError, Response
    boards = _fulfiller(ctx)
    c = ctx.conn.execute(
        "SELECT c.*, e.name AS entity_name, ct.display_name AS contact_name FROM configuration c"
        " JOIN entity e ON e.entity_id = c.entity_id"
        " LEFT JOIN contact ct ON ct.contact_id = c.contact_id"
        " WHERE c.configuration_id = ?", (configuration_id,)).fetchone()
    if c is None:
        raise HttpError("404 Not Found", "No such configuration.")
    msg = ctx.request.query.get("msg", "")
    err = ctx.request.query.get("err", "")
    tickets_html, hidden = _tickets(
        ctx, boards, where="t.work_item_id IN (SELECT work_item_id FROM ticket_configuration"
                           " WHERE configuration_id = ?)", params=[configuration_id])
    kv = "".join(f"<dt>{label}</dt><dd>{t.esc(c[key] or '—')}</dd>" for label, key in (
        ("DNS name", "dns_name"), ("Operating system", "os_name"), ("OS version", "os_version"),
        ("Description", "description"), ("Serial", "serial_number"),
        ("ScreenConnect session", "remote_session_id"), ("Source", "source"),
        ("Last seen (AD)", "last_seen_at"), ("Last synced", "last_synced_at")))
    edit = ""
    if _may_work(ctx):
        people = ctx.conn.execute(
            "SELECT contact_id, display_name FROM contact WHERE entity_id = ? AND inactive = 0"
            " ORDER BY display_name", (c["entity_id"],)).fetchall()

        def opts(pairs, sel):
            return "".join(f"<option value='{t.esc(k)}'{' selected' if k == sel else ''}>"
                           f"{t.esc(v)}</option>" for k, v in pairs)
        edit = (
            f"<div class=card><h3><svg class=ic aria-hidden=true><use href=#i-flag></use></svg>Change</h3><form method=post action='/configuration/"
            f"{t.esc(configuration_id)}/update' class=fields>"
            f"<label>Type</label><select name=config_type>"
            f"{opts([(x, x.title()) for x in cmdb.TYPES], c['config_type'])}</select>"
            f"<label>Status</label><select name=status>"
            f"{opts([(x, x.title()) for x in cmdb.STATUSES], c['status'])}</select>"
            f"<label>Contact</label><select name=contact_id>"
            f"{opts([('', '(none)')] + [(p['contact_id'], p['display_name']) for p in people], c['contact_id'] or '')}</select>"
            f"<label>Serial</label><input name=serial_number value='{t.esc(c['serial_number'] or '')}'>"
            f"<label>ScreenConnect session id</label><input name=remote_session_id "
            f"value='{t.esc(c['remote_session_id'] or '')}' placeholder='the GUID in the session URL'>"
            "<div style='margin-top:12px'><button type=submit>Save</button></div></form></div>")
    body = (
        (f"<div class='banner ok'>{t.esc(msg)}</div>" if msg else "")
        + (f"<div class='banner err'>{t.esc(err)}</div>" if err else "")
        + f"<h1>{t.esc(c['name'])} <span class=chip>{t.esc(c['config_type'].title())}</span>"
        + (f" <span class=chip>{t.esc(c['status'].lower())}</span>" if c["status"] != "ACTIVE" else "")
        + "</h1>"
        f"<p class=sub><a href='/company/{t.esc(c['entity_id'])}'>{t.esc(c['entity_name'])}</a>"
        + (f" · <a href='/contact/{t.esc(c['contact_id'])}'>{t.esc(c['contact_name'])}</a>"
           if c["contact_id"] else "") + "</p>"
        + f"<p>{links_html(ctx, 'CONFIGURATION', c)}</p>"
        f"<div class=rail><div><div class=card><h3><svg class=ic aria-hidden=true><use href=#i-ticket></use></svg>Open tickets</h3>{tickets_html}"
        f"{_hidden_note(hidden)}</div></div>"
        f"<div><div class=card><h3><svg class=ic aria-hidden=true><use href=#i-monitor></use></svg>Configuration</h3><dl class=kv>{kv}</dl></div>{edit}</div></div>")
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
            serial_number=f.get("serial_number"))
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
        # The contact's own machines first, then the rest of the company's.
        options = ctx.conn.execute(
            "SELECT configuration_id, name, contact_id FROM configuration"
            " WHERE entity_id = ? AND status = 'ACTIVE'"
            " ORDER BY contact_id IS NOT ? , name LIMIT 1000",
            (tk["entity_id"] or "", tk["contact_id"])).fetchall()
        opts = "".join(
            f"<option value='{t.esc(o['configuration_id'])}'>{t.esc(o['name'])}"
            + (" (contact's)" if tk["contact_id"] and o["contact_id"] == tk["contact_id"] else "")
            + "</option>" for o in options if o["configuration_id"] not in linked)
        if opts:
            add = (f"<form method=post action='/ticket/{wid}/config/add' class=row "
                   "style='margin-top:8px'><div><select name=configuration_id>"
                   f"{opts}</select></div><div style='flex:0 0 auto'>"
                   "<button type=submit class=ghost>Attach</button></div></form>")
    return ("<div class=card><h3><svg class=ic aria-hidden=true><use href=#i-monitor></use></svg>Configurations</h3>"
            + (f"<ul class=plain>{items}</ul>" if items else
               "<div class=muted>None attached.</div>") + add + "</div>")


def attach(ctx, work_item_id: str):
    from .. import HttpError, redirect
    tk = ctx.conn.execute("SELECT board_id FROM ticket WHERE work_item_id = ?",
                          (work_item_id,)).fetchone()
    if tk is None:
        raise HttpError("404 Not Found", "No such ticket.")
    common.require_board(ctx, tk["board_id"], need="WORK")
    cid = ctx.request.form().get("configuration_id", "")
    try:
        cmdb.attach(ctx.conn, work_item_id, cid, at=ctx.now, actor=ctx.user.id)
    except LookupError:
        raise HttpError("404 Not Found", "No such configuration.")
    ctx.conn.commit()
    return redirect(f"/ticket/{urllib.parse.quote(work_item_id)}")


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

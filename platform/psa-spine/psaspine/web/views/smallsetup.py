"""Setup > Knowledge categories and Setup > Companies (057): two short lists a
system administrator keeps, and the words they put on an article or a company.

The reference PSA has KnowledgeBaseCategory, CompanyStatus and CompanyType as
setup tables. Here each is a name, a retire switch and a use count. A
company's status and type are set on the Companies setup page, so the company
page itself stays a reader's page.
"""
from __future__ import annotations

import urllib.parse

from ... import companies as _companies
from ... import knowledge
from ... import priorities as _priorities
from .. import templates as t
from . import common


def _back(path: str, **q):
    from .. import redirect
    q = {k: v for k, v in q.items() if v}
    return redirect(path + ("?" + urllib.parse.urlencode(q) if q else ""))


def _try(ctx, path, fn, ok):
    try:
        out = fn()
        ctx.conn.commit()
    except (ValueError, LookupError) as exc:
        ctx.conn.rollback()
        return _back(path, err=str(exc))
    return _back(path, msg=ok(out) if callable(ok) else ok)


def _banners(q) -> str:
    return ((f"<div class='banner ok'>{t.esc(q.get('msg', ''))}</div>" if q.get("msg") else "")
            + (f"<div class='banner err'>{t.esc(q.get('err', ''))}</div>" if q.get("err") else ""))


def _list_rows(rows, action_base: str, key: str) -> str:
    return "".join(
        f"<tr{' style=opacity:.6' if r['inactive'] else ''}><td><form method=post action='{action_base}/{t.esc(r[key])}' class=row style='margin:0'>"
        f"<div><input name=name value='{t.esc(r['name'])}' maxlength=80 aria-label='Name'></div>"
        "<div style='flex:0 0 auto'><button class='ghost small' type=submit>Save</button></div>"
        f"<div style='flex:0 0 auto'><button class='ghost small' type=submit name=inactive value='{0 if r['inactive'] else 1}'>{'Restore' if r['inactive'] else 'Retire'}</button></div>"
        f"</form></td><td class=num>{r['used']}</td></tr>" for r in rows)


# ------------------------------------------------------------ knowledge categories

KB_PATH = "/admin/kb-categories"


def kb_index(ctx):
    from .. import Response
    common.require_sysadmin(ctx)
    rows = knowledge.categories(ctx.conn, all_rows=True)
    body = (_banners(ctx.request.query)
            + "<h1>Knowledge categories</h1><p class=sub>A name a reader browses the knowledge base by: Printers, Accounts, "
              "Clinical systems. An article may have one; the Knowledge page filters by it. Retiring a category keeps it on "
              "the articles that have it and offers it to no new one. <a href='/admin'>Setup</a> · <a href='/kb'>Knowledge</a></p>"
              "<div class=card><h3>" + t.icon("note") + "Categories</h3><div class=tablewrap><table><thead><tr><th>Category</th>"
              "<th class=num>Articles</th></tr></thead><tbody>"
            + (_list_rows(rows, KB_PATH, "category_id") or "<tr><td colspan=2 class=muted>No category yet.</td></tr>")
            + "</tbody></table></div>"
              f"<form method=post action='{KB_PATH}' class=row style='margin-top:10px'>"
              "<div style='flex:1 1 220px'><input name=name required maxlength=80 placeholder='Printers · Accounts · Clinical systems'></div>"
              "<div style='flex:0 0 auto'><button class=ghost type=submit>Add category</button></div></form></div>")
    return Response(body=t.page("Knowledge categories", body, user=ctx.user, active="admin"))


def kb_add(ctx):
    common.require_sysadmin(ctx)
    f = ctx.request.form()
    return _try(ctx, KB_PATH, lambda: knowledge.add_category(ctx.conn, f.get("name", ""), at=ctx.now, actor=ctx.user.id),
                "Category added.")


def kb_save(ctx, category_id):
    common.require_sysadmin(ctx)
    f = ctx.request.form()
    inactive = f.get("inactive")
    return _try(ctx, KB_PATH, lambda: knowledge.save_category(ctx.conn, category_id, at=ctx.now, actor=ctx.user.id,
                                                              name=f.get("name"), inactive=None if inactive is None else inactive == "1"),
                lambda s: s.capitalize() + ".")


# ------------------------------------------------------------ companies

CO_PATH = "/admin/companies"


def co_index(ctx):
    from .. import Response
    common.require_sysadmin(ctx)
    statuses = _companies.rows(ctx.conn, "status", all_rows=True)
    types = _companies.rows(ctx.conn, "type", all_rows=True)
    live_s = [r for r in statuses if not r["inactive"]]
    live_t = [r for r in types if not r["inactive"]]
    entities = ctx.conn.execute("SELECT entity_id, name, is_covered, status_id, type_id FROM entity"
                                " ORDER BY CASE WHEN entity_id = 'UNCLASSIFIED' THEN 1 ELSE 0 END, name").fetchall()

    def opts(rows, key, selected):
        return "<option value=''>(none)</option>" + "".join(
            f"<option value='{t.esc(r[key])}'{' selected' if r[key] == selected else ''}>{t.esc(r['name'])}</option>" for r in rows)
    co_rows = "".join(
        f"<tr><td><a href='/company/{t.esc(e['entity_id'])}'>{t.esc(e['name'])}</a> <span class=muted>{t.esc(e['entity_id'])}</span></td>"
        f"<td>{'Covered' if e['is_covered'] else '<span class=muted>Not covered</span>'}</td>"
        f"<td colspan=3><form method=post action='{CO_PATH}/{t.esc(e['entity_id'])}' class=row style='margin:0'>"
        f"<div style='flex:1 1 160px'><select name=status_id aria-label='Status'>{opts(live_s, 'status_id', e['status_id'])}</select></div>"
        f"<div style='flex:1 1 160px'><select name=type_id aria-label='Type'>{opts(live_t, 'type_id', e['type_id'])}</select></div>"
        "<div style='flex:0 0 auto'><button class='ghost small' type=submit>Save</button></div></form></td></tr>" for e in entities)

    def list_card(title, what, rows, placeholder):
        return ("<div class=card><h3>" + t.icon("tag") + t.esc(title) + "</h3><div class=tablewrap><table><thead><tr><th>Name</th>"
                "<th class=num>Companies</th></tr></thead><tbody>"
                + (_list_rows(rows, f"{CO_PATH}/{what}", "status_id" if what == "status" else "type_id")
                   or f"<tr><td colspan=2 class=muted>No {what} yet.</td></tr>") + "</tbody></table></div>"
                f"<form method=post action='{CO_PATH}/{what}' class=row style='margin-top:10px'>"
                f"<div style='flex:1 1 220px'><input name=name required maxlength=80 placeholder='{placeholder}'></div>"
                f"<div style='flex:0 0 auto'><button class=ghost type=submit>Add {what}</button></div></form></div>")
    body = (_banners(ctx.request.query)
            + "<h1>Companies</h1><p class=sub>The words on a company: its status (a customer, a former customer, a prospect) "
              "and its type (a hospital department, a supplier, a partner), as the reference PSA's Company Status and Company "
              "Type setup tables. Words, not rules: coverage is still the executed instrument, and a company's tickets are "
              "still its own. <a href='/admin'>Setup</a> · <a href='/companies'>Companies</a></p>"
              "<div class=grid2>" + list_card("Statuses", "status", statuses, "Customer · Former customer · Prospect")
            + list_card("Types", "type", types, "Hospital department · Supplier · Partner") + "</div>"
              "<div class=card><h3>" + t.icon("building") + "Each company</h3><div class=tablewrap><table><thead><tr><th>Company</th>"
              "<th>Agreement</th><th>Status</th><th>Type</th><th></th></tr></thead><tbody>" + co_rows + "</tbody></table></div></div>")
    return Response(body=t.page("Companies setup", body, user=ctx.user, active="admin"))


def co_list_add(ctx, what):
    from .. import HttpError
    common.require_sysadmin(ctx)
    if what not in ("status", "type"):
        raise HttpError("404 Not Found", "No such list.")
    f = ctx.request.form()
    return _try(ctx, CO_PATH, lambda: _companies.add(ctx.conn, what, f.get("name", ""), at=ctx.now, actor=ctx.user.id),
                f"{what.capitalize()} added.")


def co_list_save(ctx, what, ident):
    from .. import HttpError
    common.require_sysadmin(ctx)
    if what not in ("status", "type"):
        raise HttpError("404 Not Found", "No such list.")
    f = ctx.request.form()
    inactive = f.get("inactive")
    return _try(ctx, CO_PATH, lambda: _companies.save(ctx.conn, what, ident, at=ctx.now, actor=ctx.user.id, name=f.get("name"),
                                                      inactive=None if inactive is None else inactive == "1"),
                lambda s: s.capitalize() + ".")


def co_set(ctx, entity_id):
    common.require_sysadmin(ctx)
    f = ctx.request.form()
    return _try(ctx, CO_PATH, lambda: _companies.set_company(ctx.conn, entity_id, at=ctx.now, actor=ctx.user.id,
                                                             status_id=f.get("status_id"), type_id=f.get("type_id")),
                lambda ch: ("Saved: " + "; ".join(ch)) if ch else "Nothing changed.")


def co_list_add_status(ctx):
    return co_list_add(ctx, "status")


def co_list_add_type(ctx):
    return co_list_add(ctx, "type")


def co_list_save_status(ctx, ident):
    return co_list_save(ctx, "status", ident)


def co_list_save_type(ctx, ident):
    return co_list_save(ctx, "type", ident)


# ------------------------------------------------------------ priorities (060)

PR_PATH = "/admin/priorities"


def pr_index(ctx):
    from .. import Response
    common.require_sysadmin(ctx)
    rows = _priorities.rows(ctx.conn)
    colours = lambda sel: "".join(f"<option value='{c}'{' selected' if c == sel else ''}>{c}</option>" for c in _priorities.COLORS)
    trs = "".join(
        f"<tr><td>{t.badge(r['priority_id'])}</td>"
        f"<td><form method=post action='{PR_PATH}/{r['priority_id']}' class=row style='margin:0;gap:6px'>"
        f"<div style='flex:1 1 220px'><input name=name value='{t.esc(r['name'])}' maxlength=50 required aria-label='Name'></div>"
        f"<div style='flex:0 0 120px'><select name=color aria-label='Colour'>{colours(r['color'])}</select></div>"
        f"<div style='flex:0 0 70px'><input name=sort_order type=number value='{r['sort_order']}' aria-label='Order'></div>"
        f"<div style='flex:0 0 auto'><label><input type=radio name=is_default value=1 style='width:auto'{' checked' if r['is_default'] else ''}> default</label></div>"
        "<div style='flex:0 0 auto'><button class=ghost type=submit>Save</button></div></form></td></tr>" for r in rows)
    body = (_banners(ctx.request.query)
            + "<h1>Priorities</h1><p class=sub>The reference PSA's Priority setup table: each priority's name, colour "
              "and order, and which is the default. The codes P1 to P4 are what every SLA target and floor names and "
              "what the matrix computes from <i>who is affected</i> and <i>is a patient waiting</i>; the words are the "
              "hospital's. A person can set a ticket's priority by hand on the ticket, and give it back to the matrix. "
              "<a href='/admin'>Setup</a></p>"
              "<div class=card><h3>" + t.icon("alert") + "Priorities</h3><div class=tablewrap><table><thead><tr><th>Code</th>"
              "<th>Name · colour · order · default</th></tr></thead><tbody>" + trs + "</tbody></table></div></div>")
    return Response(body=t.page("Priorities", body, user=ctx.user, active="admin"))


def pr_save(ctx, code):
    common.require_sysadmin(ctx)
    f = ctx.request.form()
    order = f.get("sort_order", "").strip()
    return _try(ctx, PR_PATH, lambda: _priorities.save(
        ctx.conn, code, name=f.get("name"), color=f.get("color"),
        sort_order=int(order) if order.lstrip("-").isdigit() else None,
        is_default=f.get("is_default") == "1", at=ctx.now, actor=ctx.user.id), lambda s: s.capitalize() + ".")

"""Setup > Configuration types: the types, their statuses, and the questions
each type asks (056).

021 fixed seven types and three statuses. A hospital's CMDB needs more
the day biomedical devices join it, and what it needs of an infusion pump
(an asset tag, a last calibration date) it does not need of a printer.
Here a system administrator adds a type, says which of the seven kinds it
counts as (so every report and filter keeps its meaning), and gives it
questions; adds a status and says which of the three it counts as; renames
and retires. The configuration's page then asks the questions.
"""
from __future__ import annotations

import urllib.parse

from ... import configurations as cmdb
from .. import templates as t
from . import common


def _back(**q):
    from .. import redirect
    q = {k: v for k, v in q.items() if v}
    return redirect("/admin/configuration-types" + ("?" + urllib.parse.urlencode(q) if q else ""))


def _try(ctx, fn, ok):
    try:
        out = fn()
        ctx.conn.commit()
    except (ValueError, LookupError) as exc:
        ctx.conn.rollback()
        return _back(err=str(exc))
    return _back(msg=ok(out) if callable(ok) else ok)


def index(ctx):
    from .. import Response
    common.require_sysadmin(ctx)
    q = ctx.request.query
    types = cmdb.types(ctx.conn, all_rows=True)
    statuses = cmdb.statuses(ctx.conn, all_rows=True)
    kinds = "".join(f"<option value={k}>{t.esc(v)}</option>" for k, v in cmdb.TYPE_WORDS.items())
    field_opts = "".join(f"<option value={k}>{t.esc(v)}</option>" for k, v in cmdb.FIELD_TYPES.items())

    def type_block(ty):
        fixed = ty["type_id"] in cmdb.TYPE_WORDS
        qs = cmdb.questions(ctx.conn, ty["type_id"], all_rows=True)
        q_rows = "".join(
            f"<tr{' style=opacity:.6' if x['inactive'] else ''}><td><form method=post action='/admin/configuration-types/question/{x['question_id']}' class=row style='margin:0'>"
            f"<div><input name=label value='{t.esc(x['label'])}' maxlength=120 aria-label='Question'></div>"
            f"<div style='flex:0 0 auto'><label><input type=checkbox name=required value=1{' checked' if x['required'] else ''}> needed</label></div>"
            "<div style='flex:0 0 auto'><button class='ghost small' type=submit>Save</button></div>"
            f"<div style='flex:0 0 auto'><button class='ghost small' type=submit name=inactive value='{0 if x['inactive'] else 1}'>{'Restore' if x['inactive'] else 'Retire'}</button></div></form></td>"
            f"<td>{t.esc(cmdb.FIELD_TYPES[x['field_type']])}</td></tr>" for x in qs)
        head = (f"<form method=post action='/admin/configuration-types/type/{t.esc(ty['type_id'])}' class=row style='margin:0'>"
                f"<div style='flex:1 1 200px'><input name=name value='{t.esc(ty['name'])}' maxlength=80 aria-label='Type name'></div>"
                + (f"<div style='flex:0 0 auto'><span class=muted>counts as itself</span></div>" if fixed else
                   f"<div style='flex:0 0 160px'><select name=maps_to aria-label='Counts as'>" + "".join(
                       f"<option value={k}{' selected' if k == ty['maps_to'] else ''}>{t.esc(v)}</option>" for k, v in cmdb.TYPE_WORDS.items()) + "</select></div>")
                + "<div style='flex:0 0 auto'><button class='ghost small' type=submit>Save</button></div>"
                + ("" if fixed else f"<div style='flex:0 0 auto'><button class='ghost small' type=submit name=inactive value='{0 if ty['inactive'] else 1}'>{'Restore' if ty['inactive'] else 'Retire'}</button></div>")
                + f"<div style='flex:0 0 auto'><span class=muted>{ty['used']} configuration(s)</span></div></form>")
        add_q = (f"<form method=post action='/admin/configuration-types/type/{t.esc(ty['type_id'])}/question' class=row style='margin-top:8px'>"
                 "<div style='flex:1 1 220px'><input name=label required maxlength=120 placeholder='Asset tag · Last calibration · Under contract'></div>"
                 f"<div style='flex:0 0 140px'><select name=field_type aria-label='Answer type'>{field_opts}</select></div>"
                 "<div style='flex:0 0 auto'><label><input type=checkbox name=required value=1> needed</label></div>"
                 "<div style='flex:0 0 auto'><button class='ghost small' type=submit>Ask</button></div></form>")
        return (f"<div class=card{' style=opacity:.75' if ty['inactive'] else ''}><h3>{t.icon('monitor')}{t.esc(ty['name'])}"
                + (" <span class=pill>retired</span>" if ty["inactive"] else "") + "</h3>" + head
                + "<div class=tablewrap style='margin-top:8px'><table class=compact><thead><tr><th>Question</th><th>Answer</th></tr></thead><tbody>"
                + (q_rows or "<tr><td colspan=2 class=muted>No question yet: the configuration's own fields are all it asks.</td></tr>")
                + "</tbody></table></div>" + add_q + "</div>")

    status_rows = "".join(
        f"<tr{' style=opacity:.6' if s['inactive'] else ''}><td><form method=post action='/admin/configuration-types/status/{t.esc(s['status_id'])}' class=row style='margin:0'>"
        f"<div><input name=name value='{t.esc(s['name'])}' maxlength=80 aria-label='Status'></div>"
        "<div style='flex:0 0 auto'><button class='ghost small' type=submit>Save</button></div>"
        + ("" if s["status_id"] in cmdb.STATUS_WORDS else
           f"<div style='flex:0 0 auto'><button class='ghost small' type=submit name=inactive value='{0 if s['inactive'] else 1}'>{'Restore' if s['inactive'] else 'Retire'}</button></div>")
        + f"</form></td><td>{t.esc(cmdb.STATUS_WORDS[s['maps_to']])}</td><td class=num>{s['used']}</td></tr>" for s in statuses)
    body = ((f"<div class='banner ok'>{t.esc(q.get('msg', ''))}</div>" if q.get("msg") else "")
            + (f"<div class='banner err'>{t.esc(q.get('err', ''))}</div>" if q.get("err") else "")
            + "<h1>Configuration types</h1><p class=sub>What a configuration can be, what state it can be in, and what each "
              "type asks of its configurations. A type counts as one of the seven kinds the reports and the API know, and a "
              "status as active, inactive or retired, so nothing that reads them changes its meaning. <a href='/admin'>Setup</a></p>"
              "<div class=card><h3>" + t.icon("plus") + "Add a type</h3><form method=post action='/admin/configuration-types/type' class=row>"
              "<div style='flex:1 1 220px'><label>Name</label><input name=name required maxlength=80 placeholder='Infusion pump'></div>"
              f"<div style='flex:0 0 180px'><label>Counts as</label><select name=maps_to>{kinds}</select></div>"
              "<div style='flex:0 0 auto;align-self:end'><button type=submit>Add</button></div></form></div>"
            + "".join(type_block(ty) for ty in types)
            + "<div class=card><h3>" + t.icon("tag") + "Statuses</h3><div class=tablewrap><table><thead><tr><th>Status</th><th>Counts as</th><th class=num>Used</th></tr></thead><tbody>"
            + status_rows + "</tbody></table></div>"
              "<form method=post action='/admin/configuration-types/status' class=row style='margin-top:10px'>"
              "<div style='flex:1 1 220px'><input name=name required maxlength=80 placeholder='In repair · On loan · Awaiting disposal'></div>"
              "<div style='flex:0 0 160px'><select name=maps_to aria-label='Counts as'>" + "".join(f"<option value={k}>{t.esc(v)}</option>" for k, v in cmdb.STATUS_WORDS.items())
            + "</select></div><div style='flex:0 0 auto'><button class=ghost type=submit>Add status</button></div></form></div>")
    return Response(body=t.page("Configuration types", body, user=ctx.user, active="admin"))


def type_add(ctx):
    common.require_sysadmin(ctx)
    f = ctx.request.form()
    return _try(ctx, lambda: cmdb.add_type(ctx.conn, f.get("name", ""), f.get("maps_to", ""), at=ctx.now, actor=ctx.user.id),
                lambda tid: "Type added. Now give it its questions.")


def type_save(ctx, type_id):
    common.require_sysadmin(ctx)
    f = ctx.request.form()
    inactive = f.get("inactive")
    return _try(ctx, lambda: cmdb.save_type(ctx.conn, type_id, at=ctx.now, actor=ctx.user.id, name=f.get("name"),
                                            maps_to=f.get("maps_to"), inactive=None if inactive is None else inactive == "1"),
                lambda s: s.capitalize() + ".")


def status_add(ctx):
    common.require_sysadmin(ctx)
    f = ctx.request.form()
    return _try(ctx, lambda: cmdb.add_status(ctx.conn, f.get("name", ""), f.get("maps_to", ""), at=ctx.now, actor=ctx.user.id),
                "Status added.")


def status_save(ctx, status_id):
    common.require_sysadmin(ctx)
    f = ctx.request.form()
    inactive = f.get("inactive")
    return _try(ctx, lambda: cmdb.save_status(ctx.conn, status_id, at=ctx.now, actor=ctx.user.id, name=f.get("name"),
                                              inactive=None if inactive is None else inactive == "1"),
                lambda s: s.capitalize() + ".")


def question_add(ctx, type_id):
    common.require_sysadmin(ctx)
    f = ctx.request.form()
    return _try(ctx, lambda: cmdb.add_question(ctx.conn, type_id, label=f.get("label", ""), field_type=f.get("field_type", ""),
                                               required=f.get("required") == "1", at=ctx.now, actor=ctx.user.id),
                "Question added.")


def question_save(ctx, question_id):
    from .. import HttpError
    common.require_sysadmin(ctx)
    f = ctx.request.form()
    try:
        qid = int(question_id)
    except ValueError:
        raise HttpError("404 Not Found", "No such question.")
    inactive = f.get("inactive")
    return _try(ctx, lambda: cmdb.save_question(ctx.conn, qid, at=ctx.now, actor=ctx.user.id, label=f.get("label"),
                                                required=f.get("required") == "1" if inactive is None else None,
                                                inactive=None if inactive is None else inactive == "1"),
                lambda s: s.capitalize() + ".")

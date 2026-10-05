"""Projects (041): the list, a project with its phases, budget against actual, and its tickets.

Gated by the security role's PROJECTS level: READ to look, WRITE to create and
change, link tickets and phases. A project on a board is shown only to that
board's members; one on no board to everyone with the module.
"""
from __future__ import annotations

import urllib.parse

from ... import bizbox, projects
from .. import templates as t
from . import common
from . import finance as finance_view


def _back(path: str, **q):
    from .. import redirect
    q = {k: v for k, v in q.items() if v}
    return redirect(path + ("?" + urllib.parse.urlencode(q) if q else ""))


def _visible(ctx, row, seen=None) -> bool:
    if row is None:
        return False
    if row["board_id"] is None:
        return True
    return row["board_id"] in (common.board_ids_for(ctx) if seen is None else seen)


def _load(ctx, project_id):
    from .. import HttpError
    row = projects.get(ctx.conn, project_id)
    if not _visible(ctx, row):
        raise HttpError("404 Not Found", "No such project.")
    return row


def _bar(actual: float, budget) -> str:
    if not budget:
        return f"<span class=muted>{actual:.2f} h, no budget</span>"
    pct = actual / budget * 100
    cls = "sla-bad" if pct > 100 else "sla-warn" if pct > 85 else "sla-ok"
    return (f"<span class='chip {cls}'>{actual:.2f} of {budget:.2f} h · {pct:.0f}%</span>")


def index(ctx):
    from .. import Response
    common.require_module(ctx, "PROJECTS")
    q = ctx.request.query
    status = q.get("status", "") if q.get("status", "") in projects.STATUSES else ""
    seen = common.board_ids_for(ctx)
    rows = [r for r in projects.all_projects(ctx.conn, status=status or None, boards=seen) if _visible(ctx, r, seen)]
    hours = projects.hours_by_project(ctx.conn, boards=seen)
    trs = "".join(
        f"<tr><td><a href='/project/{t.esc(r['project_id'])}'>{t.esc(r['project_id'])}</a></td><td><b>{t.esc(r['name'])}</b></td>"
        f"<td>{t.chip(projects.STATUSES[r['status']])}</td><td>{t.esc(r['manager'] or '')}</td>"
        f"<td>{t.esc(r['starts_on'] or '')} → {t.esc(r['ends_on'] or '')}</td>"
        f"<td>{_bar(hours.get(r['project_id'], 0.0), r['budget_hours'])}</td>"
        f"<td class=center>{r['tickets']}</td></tr>" for r in rows)
    opts = "<option value=''>Every status</option>" + "".join(
        f"<option value='{k}'{' selected' if k == status else ''}>{v}</option>" for k, v in projects.STATUSES.items())
    new = ""
    if common.allows(ctx, "PROJECTS", "WRITE"):
        boards = "<option value=''>No board</option>" + "".join(
            f"<option value='{t.esc(b['board_id'])}'>{t.esc(b['display_name'])}</option>" for b in ctx.conn.execute(
                "SELECT board_id, display_name FROM board WHERE COALESCE(inactive, 0) = 0 ORDER BY display_name")
            if b["board_id"] in seen)
        new = ("<div class=card><h3>" + t.icon("plus") + "New project</h3><form method=post action='/projects/new' class=grid2>"
               "<div><label>Name</label><input name=name required maxlength=200 placeholder='Replace ward 3 network switches'></div>"
               f"<div><label>Manager</label><input name=manager value='{t.esc(ctx.user.id)}'></div>"
               "<div><label>Starts</label><input type=date name=starts_on></div><div><label>Ends</label><input type=date name=ends_on></div>"
               "<div><label>Budget hours</label><input name=budget_hours inputmode=decimal placeholder='40'></div>"
               f"<div><label>Board</label><select name=board_id>{boards}</select></div>"
               "<div style='grid-column:1/-1'><label>What it is for</label><textarea name=description></textarea></div>"
               "<div><button type=submit>Create</button></div></form></div>")
    body = ((f"<div class='banner ok'>{t.esc(q.get('msg', ''))}</div>" if q.get("msg") else "")
            + (f"<div class='banner err'>{t.esc(q.get('err', ''))}</div>" if q.get("err") else "")
            + "<h1>Projects</h1><p class=sub>Planned work with a start and an end. Phases break it down and may wait on one "
              "another; tickets are the work, and their time entries are the actual hours against each budget.</p>"
            + "<div class=card><form method=get action='/projects' class='row schedbar'>"
              f"<div style='flex:0 0 220px'><select name=status>{opts}</select></div>"
              "<div style='flex:0 0 auto'><button class=ghost type=submit>Show</button></div></form>"
              "<div class=tablewrap><table><thead><tr><th>Project</th><th>Name</th><th>Status</th><th>Manager</th><th>Dates</th>"
              f"<th>Hours</th><th>Tickets</th></tr></thead><tbody>{trs or '<tr><td colspan=7 class=muted>No projects yet.</td></tr>'}"
              "</tbody></table></div></div>" + new)
    return Response(body=t.page("Projects", body, user=ctx.user, active="projects"))


def create(ctx):
    common.require_module(ctx, "PROJECTS", "WRITE")
    f = ctx.request.form()
    if f.get("board_id") and f["board_id"] not in common.board_ids_for(ctx):
        return _back("/projects", err="You are not on that board.")
    try:
        pid = projects.create(ctx.conn, name=f.get("name", ""), manager=f.get("manager"), board_id=f.get("board_id") or None,
                              starts_on=f.get("starts_on"), ends_on=f.get("ends_on"), budget_hours=f.get("budget_hours"),
                              description=f.get("description"), at=ctx.now, actor=ctx.user.id)
        ctx.conn.commit()
    except projects.Refused as exc:
        ctx.conn.rollback()
        return _back("/projects", err=f"Not created: {exc}")
    return _back(f"/project/{pid}", msg="Project created. Add its phases, then link its tickets.")


def _edit_phase_card(ctx, p, pid, phs, editing) -> str:
    """Edit one phase. It is a card rather than a field inside each row because
    a phase has five things to change and a row has no space for them; Edit on
    the row brings the phase here with `?phase=`, which also means the form
    works with scripting off."""
    if not editing.isdigit():
        return ""
    ph = next((x for x in phs if str(x["phase_id"]) == editing), None)
    if ph is None:
        return ""
    others = "<option value=''>(top level)</option>" + "".join(
        f"<option value={o['phase_id']}{' selected' if o['phase_id'] == ph['parent_id'] else ''}>"
        f"{'— ' * o['depth']}{t.esc(o['name'])}</option>" for o in phs if o["phase_id"] != ph["phase_id"])
    waits = "<option value=''>(add a predecessor)</option>" + "".join(
        f"<option value={o['phase_id']}>{'— ' * o['depth']}{t.esc(o['name'])}</option>"
        for o in phs if o["phase_id"] != ph["phase_id"] and o["phase_id"] not in ph["depends_on"])
    return ("<div class=card id=edit-phase><h3>" + t.icon("edit") + f"Edit {t.esc(ph['name'])}</h3>"
            f"<form method=post action='/project/{pid}/phase/update' class=grid2>"
            f"<input type=hidden name=phase_id value={ph['phase_id']}>"
            "<div style='grid-column:1/-1'><label>Name</label>"
            f"<input name=name required maxlength=200 value='{t.esc(ph['name'])}'></div>"
            f"<div><label>Inside</label><select name=parent_id>{others}</select></div>"
            f"<div><label>Also waits on</label><select name=depends_on>{waits}</select></div>"
            f"<div><label>Starts</label><input type=date name=starts_on value='{t.esc(ph['starts_on'] or '')}'></div>"
            f"<div><label>Ends</label><input type=date name=ends_on value='{t.esc(ph['ends_on'] or '')}'></div>"
            "<div><label>Budget hours</label>"
            f"<input name=budget_hours value='{t.esc(ph['budget_hours'] if ph['budget_hours'] is not None else '')}'></div>"
            "<div style='align-self:end'><button type=submit>Save phase</button> "
            f"<a class='ghost' href='/project/{pid}'>Cancel</a></div></form></div>")


def _remove_card(ctx, p, pid) -> str:
    """Remove the project, when it carries nothing. A project with phases,
    tickets or a BizBox record is **cancelled** instead, because its tickets
    keep their hours and their history; the card says which of the two applies
    and why, rather than offering a button that refuses."""
    w = projects.project_work(ctx.conn, p["project_id"])
    held = [f"{w[k]} {word}" for k, word in (("phases", "phase(s)"), ("tickets", "ticket(s)"),
                                             ("finance", "BizBox record(s)")) if w[k]]
    if held:
        return ("<p class=why style='margin-top:12px'>This project carries " + t.esc(", ".join(held))
                + ". A project with work on it is <b>cancelled</b>, not deleted, so its tickets keep their "
                  "hours and their history \u2014 set its status to Cancelled above. Take the phases, "
                  "tickets and records off it first if it really should be deleted.</p>")
    return (f"<form method=post action='/project/{pid}/remove' style='margin-top:12px'"
            " onsubmit=\"return confirm('Remove this project? It has no phases, tickets or records.')\">"
            "<button class='ghost danger' type=submit>" + t.icon("trash")
            + " Remove this project</button>"
            "<p class=why style='margin:6px 0 0'>It carries no phase, ticket or record \u2014 nothing is lost. "
            "For a project that got going, use Cancelled instead.</p></form>")


def detail(ctx, project_id):
    from .. import Response
    common.require_module(ctx, "PROJECTS")
    p = _load(ctx, project_id)
    q = ctx.request.query
    can = common.allows(ctx, "PROJECTS", "WRITE")
    pid = t.esc(p["project_id"])
    seen = common.board_ids_for(ctx)
    phs = projects.phases(ctx.conn, p["project_id"], boards=seen)
    names = {ph["phase_id"]: ph["name"] for ph in phs}
    editing = q.get("phase", "")
    rows = []
    for ph in phs:
        ph_id = ph["phase_id"]
        # "waits on X" is now "waits on X ×": until today a predecessor set the
        # wrong way round could not be taken off, and set_phase_status refuses
        # to finish a phase whose predecessor is open -- so one wrong click left
        # two phases that could never both be done.
        waits = " ".join(
            f"<span class=chip>{t.esc(names.get(dep, '?'))}"
            + (f" <form method=post action='/project/{pid}/phase/unwait' class=inline>"
               f"<input type=hidden name=phase_id value={ph_id}><input type=hidden name=depends_on value={dep}>"
               f"<button class='linky' type=submit title='Stop waiting on this'>&times;</button></form>" if can else "")
            + "</span>" for dep in ph["depends_on"])
        act = ""
        if can:
            work = projects.phase_work(ctx.conn, ph_id)
            why = ("it has phases inside it" if work["children"] else
                   f"{work['tickets']} ticket(s) are on it" if work["tickets"] else
                   f"{work['hours']:g} hours are booked against it" if work["hours"] else "")
            act = (f"<form method=post action='/project/{pid}/phase/status' class=inline><input type=hidden name=phase_id value={ph_id}>"
                   f"<button class='ghost small' type=submit>{'Reopen' if ph['status'] == 'DONE' else 'Done'}</button></form>"
                   f" <a class='ghost small' href='/project/{pid}?phase={ph_id}#edit-phase'>Edit</a>"
                   f" <form method=post action='/project/{pid}/phase/move' class=inline><input type=hidden name=phase_id value={ph_id}>"
                   "<button class='ghost small' name=dir value=-1 type=submit title='Move up'>&uarr;</button>"
                   "<button class='ghost small' name=dir value=1 type=submit title='Move down'>&darr;</button></form>"
                   + (f" <form method=post action='/project/{pid}/phase/remove' class=inline"
                      " onsubmit=\"return confirm('Remove this phase? It carries no tickets and no hours.')\">"
                      f"<input type=hidden name=phase_id value={ph_id}>"
                      "<button class='ghost small danger' type=submit>Remove</button></form>" if not why
                      else f" <span class=why title='{t.esc(why)}'>kept: {t.esc(why)}</span>"))
        rows.append(f"<tr{' style=opacity:.6' if ph['status'] == 'DONE' else ''}"
                    f"{' class=cur' if str(ph_id) == editing else ''}><td style='padding-left:{8 + ph['depth'] * 22}px'>"
                    f"{'└ ' if ph['depth'] else ''}<b>{t.esc(ph['name'])}</b></td>"
                    f"<td>{t.esc(ph['starts_on'] or '')} → {t.esc(ph['ends_on'] or '')}</td>"
                    f"<td>{_bar(ph['actual_hours'], ph['budget_hours'])}</td>"
                    f"<td>{('waits on ' + waits) if waits else ''}</td><td>{'Done' if ph['status'] == 'DONE' else 'Open'}</td><td>{act}</td></tr>")
    tks = [r for r in projects.tickets(ctx.conn, p["project_id"]) if r["board_id"] in seen]
    common.audit_restricted_reads(ctx, (r["board_id"] for r in tks), detail=f"project {p['project_id']} listed")
    def _unlink(wid):
        if not can:
            return ""
        return (f"<form method=post action='/project/{pid}/ticket/unlink' class=inline>"
                f"<input type=hidden name=work_item_id value='{t.esc(wid)}'>"
                "<button class='ghost small' type=submit title='Take this ticket off the project'>Unlink</button></form>")
    ticket_rows = "".join(
        f"<tr><td><a href='/ticket/{t.esc(r['work_item_id'])}'>{t.esc(r['work_item_id'])}</a></td><td>{t.esc(r['summary'])}</td>"
        f"<td>{t.esc(r['phase_name'] or '')}</td><td>{t.esc(r['state'])}</td><td>{t.esc(r['owner'] or '')}</td>"
        f"<td>{_unlink(r['work_item_id'])}</td></tr>" for r in tks)
    phase_opts = "<option value=''>(no phase)</option>" + "".join(
        f"<option value={ph['phase_id']}>{'— ' * ph['depth']}{t.esc(ph['name'])}</option>" for ph in phs)
    forms = ""
    if can:
        status_opts = "".join(f"<option value='{k}'{' selected' if k == p['status'] else ''}>{v}</option>" for k, v in projects.STATUSES.items())
        forms = (
            "<div class=grid2><div class=card><h3>" + t.icon("plus") + "Add a phase</h3>"
            f"<form method=post action='/project/{pid}/phase' class=grid2>"
            "<div style='grid-column:1/-1'><label>Name</label><input name=name required maxlength=200 placeholder='Survey the ward'></div>"
            f"<div><label>Inside</label><select name=parent_id>{phase_opts.replace('(no phase)', '(top level)')}</select></div>"
            f"<div><label>Waits on</label><select name=depends_on>{phase_opts.replace('(no phase)', '(nothing)')}</select></div>"
            "<div><label>Starts</label><input type=date name=starts_on></div><div><label>Ends</label><input type=date name=ends_on></div>"
            "<div><label>Budget hours</label><input name=budget_hours inputmode=decimal></div>"
            "<div style='align-self:end'><button class=ghost type=submit>Add</button></div></form></div>"
            "<div class=card><h3>" + t.icon("note") + "Link a ticket</h3>"
            f"<form method=post action='/project/{pid}/ticket' class=grid2>"
            f"<div><label>Ticket</label>{t.ticket_pick('work_item_id', 'Search a ticket, or type its number', required=True)}</div>"
            f"<div><label>Phase</label><select name=phase_id>{phase_opts}</select></div>"
            "<div><button class=ghost type=submit>Link</button></div></form>"
            f"<h3 style='margin-top:14px'>{t.icon('setup')}The project itself</h3>"
            f"<form method=post action='/project/{pid}/update' class=grid2>"
            "<div style='grid-column:1/-1'><label>Name</label>"
            f"<input name=name required maxlength=200 value='{t.esc(p['name'])}'></div>"
            f"<div><label>Status</label><select name=status>{status_opts}</select></div>"
            f"<div><label>Manager</label><input name=manager value='{t.esc(p['manager'] or '')}'></div>"
            f"<div><label>Starts</label><input type=date name=starts_on value='{t.esc(p['starts_on'] or '')}'></div>"
            f"<div><label>Ends</label><input type=date name=ends_on value='{t.esc(p['ends_on'] or '')}'></div>"
            f"<div><label>Budget hours</label><input name=budget_hours value='{t.esc(p['budget_hours'] if p['budget_hours'] is not None else '')}'></div>"
            "<div style='align-self:end'><button class=ghost type=submit>Save</button></div>"
            "<div style='grid-column:1/-1'><label>Description</label>"
            f"<textarea name=description rows=4>{t.esc(p['description'] or '')}</textarea></div></form>"
            + _remove_card(ctx, p, pid) + "</div></div>" + _edit_phase_card(ctx, p, pid, phs, editing))
    finance = ""
    if common.allows(ctx, "FINANCE"):
        fl = bizbox.links(ctx.conn, "PROJECT", p["project_id"])
        items = "".join(
            f"<li>{t.esc(r['kind'].replace('_', ' '))} {finance_view._ref_link(r['kind'], r['ext_ref'])}"
            + (f" <form method=post action='/project/{pid}/finance/unlink' class=inline>"
               f"<input type=hidden name=kind value='{t.esc(r['kind'])}'>"
               f"<input type=hidden name=ext_ref value='{t.esc(r['ext_ref'])}'>"
               "<button class='linky' type=submit title='Unlink this record'>&times;</button></form>" if can else "")
            + "</li>" for r in fl)
        link = (f"<form method=post action='/project/{pid}/finance' class=row style='margin-top:6px'>"
                "<div style='flex:0 0 160px'><select name=kind>"
                + "".join(f"<option value={k}>{finance_view.ONE[k]}</option>" for k, _ in finance_view._mirror_tabs(ctx)) + "</select></div>"
                "<div><input name=ext_ref placeholder='BizBox number'></div><div style='flex:0 0 auto'><button class=ghost type=submit>Link</button></div></form>"
                if can else "")
        finance = ("<div class=card><h3>" + t.icon("tag") + "Finance (BizBox)</h3>"
                   + (f"<ul class=plain>{items}</ul>" if items else "<div class=muted>No BizBox record linked.</div>") + link + "</div>")
    actual = projects.actual_hours(ctx.conn, p["project_id"], boards=seen)
    body = ((f"<div class='banner ok'>{t.esc(q.get('msg', ''))}</div>" if q.get("msg") else "")
            + (f"<div class='banner err'>{t.esc(q.get('err', ''))}</div>" if q.get("err") else "")
            + f"<h1>{t.esc(p['name'])}</h1><p class=sub>{pid} · {t.chip(projects.STATUSES[p['status']])} · manager "
              f"{t.esc(p['manager'] or '—')} · {t.esc(p['starts_on'] or '?')} → {t.esc(p['ends_on'] or '?')} · "
              f"{t.esc(p['board_name'] or 'no board')} · {_bar(actual, p['budget_hours'])} · <a href='/projects'>Projects</a></p>"
            + (f"<div class=card><div class=md>{t.md_to_html(p['description'])}</div></div>" if p["description"] else "")
            + "<div class=card><h3>" + t.icon("layers") + "Phases</h3><div class=tablewrap><table><thead><tr><th>Phase</th><th>Dates</th>"
              f"<th>Hours</th><th>Predecessors</th><th>State</th><th></th></tr></thead><tbody>"
            + ("".join(rows) or "<tr><td colspan=6 class=muted>No phases yet.</td></tr>") + "</tbody></table></div></div>"
            + "<div class=card><h3>" + t.icon("note") + "Tickets</h3><div class=tablewrap><table><thead><tr><th>Ticket</th><th>Summary</th>"
              f"<th>Phase</th><th>State</th><th>Owner</th><th></th></tr></thead><tbody>{ticket_rows or '<tr><td colspan=6 class=muted>No tickets linked.</td></tr>'}"
              "</tbody></table></div></div>" + finance + forms)
    return Response(body=t.page(p["name"], body, user=ctx.user, active="projects"))


def _try(ctx, project_id, fn, ok):
    common.require_module(ctx, "PROJECTS", "WRITE")
    _load(ctx, project_id)
    try:
        r = fn()
        ctx.conn.commit()
    except (projects.Refused, bizbox.Refused) as exc:
        ctx.conn.rollback()
        return _back(f"/project/{project_id}", err=str(exc))
    return _back(f"/project/{project_id}", msg=ok(r))


def add_phase(ctx, project_id):
    f = ctx.request.form()

    def go():
        pid = projects.add_phase(ctx.conn, project_id, name=f.get("name", ""),
                                 parent_id=int(f["parent_id"]) if f.get("parent_id", "").isdigit() else None,
                                 starts_on=f.get("starts_on"), ends_on=f.get("ends_on"), budget_hours=f.get("budget_hours"),
                                 at=ctx.now, actor=ctx.user.id)
        if f.get("depends_on", "").isdigit():
            projects.add_dependency(ctx.conn, pid, int(f["depends_on"]), at=ctx.now, actor=ctx.user.id)
        return pid
    return _try(ctx, project_id, go, lambda _: "Phase added")


def phase_status(ctx, project_id):
    f = ctx.request.form()
    ph = f.get("phase_id", "")

    def go():
        row = ctx.conn.execute("SELECT status, project_id FROM project_phase WHERE phase_id = ?",
                               (int(ph) if ph.isdigit() else -1,)).fetchone()
        if row is None or row["project_id"] != project_id:
            raise projects.Refused("No such phase on this project.")
        projects.set_phase_status(ctx.conn, int(ph), row["status"] != "DONE", at=ctx.now, actor=ctx.user.id)
    return _try(ctx, project_id, go, lambda _: "Phase updated")


def link_ticket(ctx, project_id):
    from .ticket import _load as ticket_load
    f = ctx.request.form()
    wid = (f.get("work_item_id", "") or "").strip().upper()

    def go():
        tk = ctx.conn.execute("SELECT board_id FROM ticket WHERE work_item_id = ?", (wid,)).fetchone()
        if tk is None or not common.may_access_board(ctx, tk["board_id"], need="WORK"):
            raise projects.Refused(f"No ticket {wid} that you work.")
        return projects.link_ticket(ctx.conn, wid, project_id, int(f["phase_id"]) if f.get("phase_id", "").isdigit() else None,
                                    at=ctx.now, actor=ctx.user.id)
    del ticket_load
    return _try(ctx, project_id, go, lambda r: f"{wid}: {r}")


def unlink_ticket(ctx, project_id):
    """Take one ticket off the project, from the project's own page. The engine
    could already do it; only the ticket's page had a way to ask."""
    wid = (ctx.request.form().get("work_item_id", "") or "").strip().upper()

    def go():
        tk = ctx.conn.execute("SELECT board_id FROM ticket WHERE work_item_id = ?", (wid,)).fetchone()
        if tk is None or not common.may_access_board(ctx, tk["board_id"], need="WORK"):
            raise projects.Refused(f"No ticket {wid} that you work.")
        return projects.link_ticket(ctx.conn, wid, None, at=ctx.now, actor=ctx.user.id)
    return _try(ctx, project_id, go, lambda r: f"{wid}: {r}")


def update(ctx, project_id):
    f = ctx.request.form()
    fields = {"status": f.get("status"), "manager": f.get("manager"), "starts_on": f.get("starts_on"),
              "ends_on": f.get("ends_on"), "budget_hours": f.get("budget_hours")}
    # Name and description are only sent by the full form; the older form had
    # neither, so a post without them must not blank them.
    for k in ("name", "description"):
        if k in f:
            fields[k] = f.get(k)
    return _try(ctx, project_id, lambda: projects.update(
        ctx.conn, project_id, at=ctx.now, actor=ctx.user.id, **fields), lambda r: f"Project: {r}")


def _phase_of(ctx, project_id, raw: str) -> int:
    """A phase id from the form, proven to be on *this* project before anything
    is done with it: the project is what the viewer was allowed to see."""
    if not str(raw or "").isdigit():
        raise projects.Refused("No such phase.")
    row = ctx.conn.execute("SELECT project_id FROM project_phase WHERE phase_id = ?", (int(raw),)).fetchone()
    if row is None or row["project_id"] != project_id:
        raise projects.Refused("No such phase on this project.")
    return int(raw)


def update_phase(ctx, project_id):
    f = ctx.request.form()

    def go():
        ph = _phase_of(ctx, project_id, f.get("phase_id", ""))
        words = projects.update_phase(
            ctx.conn, ph, at=ctx.now, actor=ctx.user.id, name=f.get("name"),
            parent_id=int(f["parent_id"]) if f.get("parent_id", "").isdigit() else None,
            starts_on=f.get("starts_on"), ends_on=f.get("ends_on"), budget_hours=f.get("budget_hours"))
        if f.get("depends_on", "").isdigit():
            projects.add_dependency(ctx.conn, ph, _phase_of(ctx, project_id, f["depends_on"]),
                                    at=ctx.now, actor=ctx.user.id)
            words = (words + "; " if words != "nothing changed" else "") + "predecessor added"
        return words
    return _try(ctx, project_id, go, lambda r: f"Phase: {r}")


def remove_phase(ctx, project_id):
    f = ctx.request.form()
    return _try(ctx, project_id,
                lambda: projects.remove_phase(ctx.conn, _phase_of(ctx, project_id, f.get("phase_id", "")),
                                              at=ctx.now, actor=ctx.user.id),
                lambda r: r)


def move_phase(ctx, project_id):
    f = ctx.request.form()
    return _try(ctx, project_id,
                lambda: projects.move_phase(ctx.conn, _phase_of(ctx, project_id, f.get("phase_id", "")),
                                            -1 if f.get("dir") == "-1" else 1, at=ctx.now, actor=ctx.user.id),
                lambda r: r)


def unwait_phase(ctx, project_id):
    f = ctx.request.form()

    def go():
        return projects.remove_dependency(ctx.conn, _phase_of(ctx, project_id, f.get("phase_id", "")),
                                          _phase_of(ctx, project_id, f.get("depends_on", "")),
                                          at=ctx.now, actor=ctx.user.id)
    return _try(ctx, project_id, go, lambda r: r)


def remove(ctx, project_id):
    """Delete a project that carries nothing. `_try` would send the person back
    to a page that no longer exists, so this one answers for itself."""
    common.require_module(ctx, "PROJECTS", "WRITE")
    _load(ctx, project_id)
    try:
        words = projects.remove(ctx.conn, project_id, at=ctx.now, actor=ctx.user.id)
        ctx.conn.commit()
    except projects.Refused as exc:
        ctx.conn.rollback()
        return _back(f"/project/{project_id}", err=str(exc))
    return _back("/projects", msg=words)


def unlink_finance(ctx, project_id):
    f = ctx.request.form()
    common.require_module(ctx, "FINANCE")
    return _try(ctx, project_id, lambda: bizbox.unlink(
        ctx.conn, "PROJECT", project_id, f.get("kind", ""), f.get("ext_ref", ""),
        at=ctx.now, actor=ctx.user.id), lambda r: "Unlinked" if r else "nothing changed")


def link_finance(ctx, project_id):
    common.require_module(ctx, "FINANCE")
    f = ctx.request.form()
    return _try(ctx, project_id, lambda: bizbox.link(ctx.conn, "PROJECT", project_id, f.get("kind", ""), f.get("ext_ref", ""),
                                                     at=ctx.now, actor=ctx.user.id), lambda _: "Linked to BizBox")


def ticket_card(ctx, tk, *, can_work: bool) -> str:
    if not common.allows(ctx, "PROJECTS"):
        return ""
    wid = t.esc(tk["work_item_id"])
    on = projects.of_ticket(ctx.conn, tk["work_item_id"])
    line = (f"<div><a href='/project/{t.esc(on['project_id'])}'>{t.esc(on['project_id'])}</a> {t.esc(on['project_name'])}"
            + (f" · {t.esc(on['phase_name'])}" if on["phase_name"] else "") + "</div>") if on else "<div class=muted>Not on a project.</div>"
    form = ""
    if can_work and common.allows(ctx, "PROJECTS", "WRITE"):
        seen = common.board_ids_for(ctx)
        opts = "<option value=''>(take off the project)</option>" + "".join(
            f"<option value='{t.esc(p['project_id'])}'{' selected' if on and on['project_id'] == p['project_id'] else ''}>"
            f"{t.esc(p['project_id'])} {t.esc(p['name'])}</option>"
            for p in projects.all_projects(ctx.conn) if p["status"] in ("PLANNED", "ACTIVE", "ON_HOLD") and _visible(ctx, p, seen))
        form = (f"<form method=post action='/ticket/{wid}/project' class=row style='margin-top:6px'>"
                f"<div><select name=project_id aria-label='Project'>{opts}</select></div>"
                "<div style='flex:0 0 auto'><button class=ghost type=submit>Save</button></div></form>")
    return f"<div class=card data-pod=project><h3>{t.icon('layers')}Project</h3>{line}{form}</div>"


def ticket_set(ctx, work_item_id):
    from .ticket import _back as ticket_back, _load as ticket_load
    common.require_module(ctx, "PROJECTS", "WRITE")
    tk = ticket_load(ctx, work_item_id)
    common.require_board(ctx, tk["board_id"], need="WORK")
    pid = ctx.request.form().get("project_id") or None
    if pid and not _visible(ctx, projects.get(ctx.conn, pid)):
        return ticket_back(work_item_id, err="No such project")
    try:
        what = projects.link_ticket(ctx.conn, work_item_id, pid, None, at=ctx.now, actor=ctx.user.id)
        ctx.conn.commit()
    except projects.Refused as exc:
        return ticket_back(work_item_id, err=str(exc))
    return ticket_back(work_item_id, msg=f"Project: {what}")

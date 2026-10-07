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
    tpls = [r for r in rows if projects.is_template(r)]            # 069: templates are listed apart
    rows = [r for r in rows if not projects.is_template(r)]
    # "My projects" (068): the ones a person manages or is on the team of; Every project shows the rest
    mine = projects.projects_of(ctx.conn, ctx.user.id)
    scope = q.get("show", "")
    if scope == "mine":
        rows = [r for r in rows if r["project_id"] in mine]
    hours = projects.hours_by_project(ctx.conn, boards=seen)
    names = {r[0]: r[1] for r in ctx.conn.execute("SELECT entity_id, name FROM entity")}
    team_n = {r[0]: r[1] for r in ctx.conn.execute("SELECT project_id, COUNT(*) FROM project_member GROUP BY project_id")}
    # each project's open tickets under it, the board the viewer may see only: the project board, live
    open_by: dict = {}
    for r in rows:
        for tk in projects.tickets(ctx.conn, r["project_id"]):
            if tk["board_id"] in seen and tk["state"] not in ("RESOLVED", "CLOSED", "CANCELLED"):
                open_by.setdefault(r["project_id"], []).append(tk)
    def under(pid):
        tk = open_by.get(pid, [])
        if not tk:
            return ""
        lis = "".join(f"<li><a href='/ticket/{t.esc(x['work_item_id'])}'>{t.esc(x['work_item_id'])}</a> {t.esc(x['summary'])}"
                      f" <span class=muted>· {t.esc(x['phase_name'] or 'no phase')} · {t.esc(x['owner'] or 'unassigned')}"
                      f" · {t.esc(x['state'].lower().replace('_', ' '))}</span></li>" for x in tk)
        return (f"<tr class=popen><td></td><td colspan=10><details><summary class=muted>{len(tk)} open ticket(s)</summary>"
                f"<ul class=plain>{lis}</ul></details></td></tr>")
    def pct(pid):
        v = projects.percent_complete(ctx.conn, pid, boards=seen)
        return "<span class=muted>—</span>" if v is None else (
            f"<span class=pbar title='{v}% of its tickets closed'><i style='width:{v}%'></i></span> {v}%")
    trs = "".join(
        f"<tr><td><a href='/project/{t.esc(r['project_id'])}'>{t.esc(r['project_id'])}</a></td><td><b>{t.esc(r['name'])}</b></td>"
        f"<td>{t.esc(names.get(r['entity_id'], '') if 'entity_id' in r.keys() and r['entity_id'] else '')}</td>"
        f"<td>{t.chip(projects.STATUSES[r['status']])}</td><td>{_health_chip(ctx, r, seen)}</td><td>{t.esc(r['manager'] or '')}</td>"
        f"<td>{t.esc(r['starts_on'] or '')} → {t.esc(r['ends_on'] or '')}</td>"
        f"<td>{pct(r['project_id'])}</td>"
        f"<td>{_bar(hours.get(r['project_id'], 0.0), r['budget_hours'])}</td>"
        f"<td class=center>{r['tickets']}</td><td class=center>{team_n.get(r['project_id'], 0)}</td></tr>"
        + under(r["project_id"]) for r in rows)
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
               f"<div><label>Company</label><select name=entity_id>{_company_opts(ctx, None)}</select></div>"
               "<div style='grid-column:1/-1'><label>What it is for</label><textarea name=description></textarea></div>"
               "<div><button type=submit>Create</button></div></form></div>")
    body = ((f"<div class='banner ok'>{t.esc(q.get('msg', ''))}</div>" if q.get("msg") else "")
            + (f"<div class='banner err'>{t.esc(q.get('err', ''))}</div>" if q.get("err") else "")
            + "<h1>Projects</h1><p class=sub>Planned work with a start and an end. Phases break it down and may wait on one "
              "another; tickets are the work, and their time entries are the actual hours against each budget.</p>"
            + "<div class=card><form method=get action='/projects' class='row schedbar'>"
              f"<div style='flex:0 0 220px'><select name=status>{opts}</select></div>"
              "<div style='flex:0 0 200px'><select name=show>"
              f"<option value=''{'' if scope == 'mine' else ' selected'}>Every project</option>"
              f"<option value=mine{' selected' if scope == 'mine' else ''}>My projects</option></select></div>"
              "<div style='flex:0 0 auto'><button class=ghost type=submit>Show</button></div></form>"
              "<div class=tablewrap><table><thead><tr><th>Project</th><th>Name</th><th>Company</th><th>Status</th><th>Health</th><th>Manager</th><th>Dates</th>"
              f"<th>Complete</th><th>Hours</th><th>Tickets</th><th>Team</th></tr></thead><tbody>{trs or '<tr><td colspan=11 class=muted>No projects yet.</td></tr>'}"
              "</tbody></table></div></div>" + _templates_list(tpls) + new)
    return Response(body=t.page("Projects", body, user=ctx.user, active="projects", live="projects"))


def _templates_list(tpls) -> str:
    """069: the project templates, each a link to its page where a project is made from it."""
    if not tpls:
        return ""
    lis = "".join(f"<li><a href='/project/{t.esc(r['project_id'])}#ptemplate'>{t.esc(r['name'])}</a>"
                  f" <span class=muted>{t.esc(r['project_id'])}</span></li>" for r in tpls)
    return (f"<div class=card id=ptemplates><h3>{t.icon('layers')}Templates · {len(tpls)}</h3>"
            "<p class=why style='margin-top:0'>Open one to make a project from it: its phases, team, contacts and planned "
            f"tickets come across.</p><ul class=plain>{lis}</ul></div>")


def create(ctx):
    common.require_module(ctx, "PROJECTS", "WRITE")
    f = ctx.request.form()
    if f.get("board_id") and f["board_id"] not in common.board_ids_for(ctx):
        return _back("/projects", err="You are not on that board.")
    try:
        pid = projects.create(ctx.conn, name=f.get("name", ""), manager=f.get("manager"), board_id=f.get("board_id") or None,
                              starts_on=f.get("starts_on"), ends_on=f.get("ends_on"), budget_hours=f.get("budget_hours"),
                              description=f.get("description"), entity_id=f.get("entity_id") or None,
                              at=ctx.now, actor=ctx.user.id)
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


def _people(ctx, p) -> list[str]:
    """Who a project ticket can go to: the team first, then the project board's
    working members, then everyone else with a member record."""
    from ... import board as _board, members as _members
    team = [r["member"] for r in projects.team(ctx.conn, p["project_id"])]
    out, seen = [], set()
    for m in team + ([p["manager"]] if p["manager"] else []) + (
            _board._working_members(ctx.conn, p["board_id"]) if p["board_id"] else []) + _members.identifiers(ctx.conn):
        if m and m.lower() not in seen:
            seen.add(m.lower())
            out.append(m)
    return out


def _team_card(ctx, p, pid, can, tks) -> str:
    """The project's team (068): member, role, dates, planned hours, and the
    hours they have booked on this project's tickets the viewer may see."""
    from ... import members as _members
    booked = {}
    ids = [r["work_item_id"] for r in tks]
    if ids:
        for r in ctx.conn.execute(
                "SELECT LOWER(performed_by) AS m, SUM(COALESCE(actual_hours, band_hours)) AS h FROM time_entry"
                f" WHERE work_item_id IN ({','.join('?' * len(ids))}) GROUP BY LOWER(performed_by)", ids):
            booked[r["m"]] = float(r["h"] or 0)
    rows = projects.team(ctx.conn, p["project_id"])
    trs = "".join(
        f"<tr><td><b>{t.esc(_members.name_of(ctx.conn, r['member']))}</b> <span class=muted>{t.esc(r['member'])}</span></td>"
        f"<td>{t.chip(projects.ROLES.get(r['project_role'], r['project_role']))}</td>"
        f"<td>{t.esc(r['starts_on'] or '')} → {t.esc(r['ends_on'] or '')}</td>"
        f"<td>{_bar(booked.get(r['member'].lower(), 0.0), r['hours'])}</td>"
        + (f"<td><form method=post action='/project/{pid}/member/remove' class=inline"
           " onsubmit=\"return confirm('Take this member off the team? Their tickets and time stay theirs.')\">"
           f"<input type=hidden name=member value='{t.esc(r['member'])}'>"
           "<button class='ghost small' type=submit>Remove</button></form></td>" if can else "<td></td>")
        + "</tr>" for r in rows)
    form = ""
    if can:
        people = "".join(f"<option value='{t.esc(m)}'>{t.esc(_members.name_of(ctx.conn, m))} ({t.esc(m)})</option>"
                         for m in _people(ctx, p))
        roles = "".join(f"<option value='{k}'{' selected' if k == 'TEAM_MEMBER' else ''}>{v}</option>"
                        for k, v in projects.ROLES.items())
        form = (f"<form method=post action='/project/{pid}/member' class='grid2' style='margin-top:10px'>"
                f"<div><label>Member</label><select name=member required>{people}</select></div>"
                f"<div><label>Project role</label><select name=role>{roles}</select></div>"
                "<div><label>From</label><input type=date name=starts_on></div>"
                "<div><label>To</label><input type=date name=ends_on></div>"
                "<div><label>Planned hours</label><input name=hours inputmode=decimal placeholder='16'></div>"
                "<div style='align-self:end'><button type=submit>" + t.icon("plus") + " Add to the team</button></div>"
                "<p class=why style='grid-column:1/-1;margin:0'>Adding someone already on the team changes their role, "
                "dates or hours.</p></form>")
    return (f"<div class=card id=team><h3>{t.icon('companies')}Team · {len(rows)}</h3>"
            "<div class=tablewrap><table><thead><tr><th>Member</th><th>Role</th><th>Dates</th><th>Hours booked</th>"
            f"<th></th></tr></thead><tbody>{trs or '<tr><td colspan=5 class=muted>Nobody on the team yet.</td></tr>'}"
            f"</tbody></table></div>{form}</div>")


def _ticket_board(ctx, p, tks) -> str:
    """The project's tickets by status, the reference PSA's project ticket board:
    one column per status on the project's board, live with the page."""
    if not tks:
        return ""
    names = {}
    if p["board_id"]:
        names = {r["board_status_id"]: r["name"] for r in ctx.conn.execute(
            "SELECT board_status_id, name FROM board_status WHERE board_id = ? AND inactive = 0 ORDER BY sort_order",
            (p["board_id"],))}
    status_of = {r["work_item_id"]: r["board_status_id"] for r in ctx.conn.execute(
        f"SELECT work_item_id, board_status_id FROM ticket WHERE work_item_id IN ({','.join('?' * len(tks))})",
        [r["work_item_id"] for r in tks])}
    cols: dict = {}
    for r in tks:
        sid = status_of.get(r["work_item_id"])
        cols.setdefault(sid, []).append(r)
    order = [sid for sid in names if sid in cols] + [sid for sid in cols if sid not in names]
    hours = projects.ticket_hours(ctx.conn, p["project_id"])
    def card(r):
        b = r["budget_hours"] if "budget_hours" in r.keys() else None
        return (f"<a class=pcard href='/ticket/{t.esc(r['work_item_id'])}'><span class=muted>{t.esc(r['work_item_id'])}</span>"
                f"<b>{t.esc(r['summary'])}</b><span class=muted>{t.esc(r['phase_name'] or 'No phase')} · "
                f"{t.esc(r['owner'] or 'unassigned')} · {hours.get(r['work_item_id'], 0.0):g}"
                + (f" of {b:g}" if b else "") + " h</span></a>")
    lanes = "".join(f"<div class=plane><h4>{t.esc(names.get(sid, sid or 'No status'))} <span class=muted>{len(cols[sid])}</span></h4>"
                    + "".join(card(r) for r in cols[sid]) + "</div>" for sid in order)
    return f"<div class=card id=pboard><h3>{t.icon('board')}Ticket board</h3><div class=planess>{lanes}</div></div>"


def _notes_card(ctx, pid, can) -> str:
    rows = projects.notes(ctx.conn, pid)
    items = "".join(f"<div class=note><div class=h><b>{t.esc(r['written_by'])}</b> {t.esc(r['written_at'])}</div>"
                    f"<div class=md>{t.md_to_html(r['body'])}</div></div>" for r in rows)
    form = (f"<form method=post action='/project/{t.esc(pid)}/note' style='margin-top:8px'>"
            "<textarea name=body rows=3 required placeholder='What was agreed, what changed, what is next'></textarea>"
            "<div style='margin-top:6px'><button class=ghost type=submit>" + t.icon("note") + " Add note</button></div></form>"
            if can else "")
    return (f"<div class=card id=pnotes><h3>{t.icon('note')}Notes · {len(rows)}</h3>"
            + (items or "<div class=muted>No notes yet.</div>") + form + "</div>")


def _new_ticket_dialog(ctx, p, pid, phs) -> str:
    """New project ticket, opened from the project (or from one of its phases,
    which preselects it): summary, phase, who, budget hours."""
    from ... import members as _members
    phase_opts = "<option value=''>(no phase)</option>" + "".join(
        f"<option value={ph['phase_id']}>{'— ' * ph['depth']}{t.esc(ph['name'])}</option>" for ph in phs)
    people = "<option value=''>(unassigned)</option>" + "".join(
        f"<option value='{t.esc(m)}'>{t.esc(_members.name_of(ctx.conn, m))}</option>" for m in _people(ctx, p))
    board = (f"<p class=why style='margin:0 0 8px'>Opened on <b>{t.esc(p['board_name'])}</b>, the project's board.</p>"
             if p["board_id"] else
             "<p class='banner err' style='margin:0 0 8px'>Give the project a board first (The project itself, below).</p>")
    return ("<dialog id=ptdlg class='card tedlg'>"
            f"<form method=post action='/project/{pid}/ticket/new' class=teform>"
            "<div class=tehead data-drag title='Drag to move'><div><h3 style='margin:0'>" + t.icon("plus") + " New project ticket</h3>"
            f"<div class=muted style='font-size:12.5px'>{pid} · {t.esc(p['name'])}</div></div>"
            "<span class=tewin><button type=button class=iconbtn data-close=ptdlg aria-label='Close' title='Close'>"
            "<b style='font-size:16px;line-height:1'>&#8211;</b></button></span></div>" + board
            + "<div class=grid2><div style='grid-column:1/-1'><label>Summary</label>"
              "<input name=summary required maxlength=200 placeholder='Swap the PC at the nurses station'></div>"
              f"<div><label>Phase</label><select name=phase_id>{phase_opts}</select></div>"
              f"<div><label>Assigned to</label><select name=owner>{people}</select></div>"
              "<div><label>Budget hours</label><input name=budget_hours inputmode=decimal placeholder='2'></div><div></div>"
              "<div><label>Estimated start</label><input type=date name=starts_on></div>"
              "<div><label>Required by</label><input type=date name=due_on></div>"
              "<div style='grid-column:1/-1'><label>Description</label><textarea name=description rows=4></textarea></div></div>"
            + "<div class=tefoot><span class=grow></span><button type=button class=ghost data-close=ptdlg>Cancel</button>"
              "<button type=submit>" + t.icon("check") + " Create ticket</button></div></form></dialog>")



def _company_opts(ctx, selected) -> str:
    return "<option value=''>(none)</option>" + "".join(
        f"<option value='{t.esc(r['entity_id'])}'{' selected' if r['entity_id'] == selected else ''}>{t.esc(r['name'])}</option>"
        for r in ctx.conn.execute("SELECT entity_id, name FROM entity ORDER BY name"))


def _board_opts(ctx, selected, seen) -> str:
    return "<option value=''>No board</option>" + "".join(
        f"<option value='{t.esc(b['board_id'])}'{' selected' if b['board_id'] == selected else ''}>{t.esc(b['display_name'])}</option>"
        for b in ctx.conn.execute("SELECT board_id, display_name FROM board WHERE COALESCE(inactive, 0) = 0 ORDER BY display_name")
        if b["board_id"] in seen or b["board_id"] == selected)


def _health_chip(ctx, p, seen) -> str:
    code, why, manual = projects.health(ctx.conn, p["project_id"], boards=seen, today=ctx.now.date())
    cls = {"ON_TRACK": "sla-ok", "AT_RISK": "sla-warn", "HIGH_RISK": "sla-bad", "OFF_TRACK": "sla-bad"}[code]
    return (f"<span class='chip {cls} health' title='{t.esc(why)}'>{projects.HEALTH[code]}"
            + ("" if manual else " <span class=muted style='font-weight:400'>· read by the desk</span>") + "</span>")


def _contacts_card(ctx, p, pid, can) -> str:
    """The project's contacts (069): who it is for or answers to."""
    rows = projects.contacts(ctx.conn, p["project_id"])
    trs = "".join(
        f"<tr><td><b>{t.esc(r['display_name'])}</b></td><td>{t.esc(r['role'] or '')}</td>"
        f"<td>{t.esc(r['email'] or '')}</td><td>{t.esc(r['phone'] or '')}</td><td>{t.esc(r['department'] or '')}</td>"
        + (f"<td><form method=post action='/project/{pid}/contact/remove' class=inline>"
           f"<input type=hidden name=contact_id value='{t.esc(r['contact_id'])}'>"
           "<button class='ghost small' type=submit>Remove</button></form></td>" if can else "<td></td>")
        + "</tr>" for r in rows)
    form = ""
    if can:
        ent = p["entity_id"]
        opts = ctx.conn.execute(
            "SELECT contact_id, display_name, email FROM contact"
            + (" ORDER BY CASE WHEN entity_id = ? THEN 0 ELSE 1 END, display_name LIMIT 500" if ent else
               " ORDER BY display_name LIMIT 500"), (ent,) if ent else ()).fetchall()
        dl = "".join(f"<option value='{t.esc(o['contact_id'])}'>{t.esc(o['display_name'])}"
                     f"{' · ' + t.esc(o['email']) if o['email'] else ''}</option>" for o in opts)
        form = (f"<form method=post action='/project/{pid}/contact' class=grid2 style='margin-top:10px'>"
                "<div><label>Contact</label><input name=contact list=pcontacts required autocomplete=off"
                " placeholder='Search by name, or type an email'>"
                f"<datalist id=pcontacts>{dl}</datalist></div>"
                "<div><label>Role on the project</label><input name=role maxlength=200 placeholder='Ward manager, sign-off'></div>"
                "<div><button class=ghost type=submit>" + t.icon("plus") + " Add contact</button></div></form>")
    return (f"<div class=card id=pcontacts-card><h3>{t.icon('companies')}Contacts · {len(rows)}</h3>"
            "<div class=tablewrap><table><thead><tr><th>Name</th><th>Role</th><th>Email</th><th>Phone</th><th>Department</th>"
            f"<th></th></tr></thead><tbody>{trs or '<tr><td colspan=6 class=muted>No contacts yet.</td></tr>'}"
            f"</tbody></table></div>{form}</div>")


def _gantt(ctx, p, phs, tks) -> str:
    """The plan against time (069): each phase and each dated ticket as a bar,
    with today marked. Drawn from the dates the plan carries; anything undated
    is listed, not guessed."""
    from datetime import date as _date, timedelta as _td
    items = []
    for ph in phs:
        items.append(("phase", ph["depth"], ph["name"], ph["starts_on"], ph["ends_on"], ph["status"] == "DONE", ""))
    for r in tks:
        st, du = r["starts_on"] if "starts_on" in r.keys() else None, r["due_on"] if "due_on" in r.keys() else None
        items.append(("ticket", 1, f"{r['work_item_id']} {r['summary']}", st, du,
                      r["state"] in ("RESOLVED", "CLOSED", "CANCELLED"), r["work_item_id"]))
    dates = [d for it in items for d in (it[3], it[4]) if d] + [d for d in (p["starts_on"], p["ends_on"]) if d]
    if not dates:
        return ("<div class=card id=pgantt><h3>" + t.icon("calendar") + "Gantt</h3><div class=muted>Give the project, its "
                "phases or its tickets start and end dates and the Gantt draws them.</div></div>")
    lo = min(_date.fromisoformat(d) for d in dates)
    hi = max(_date.fromisoformat(d) for d in dates)
    span = max((hi - lo).days + 1, 7)
    def x(d):
        return ((_date.fromisoformat(d) - lo).days / span) * 100
    today = ctx.now.date()
    marker = (f"<i class=gtoday style='left:{((today - lo).days / span) * 100:.2f}%' title='Today'></i>"
              if lo <= today <= lo + _td(days=span) else "")
    ticks, d = [], lo
    step = 7 if span <= 120 else 30
    while d <= hi:
        ticks.append(f"<span style='left:{((d - lo).days / span) * 100:.2f}%'>{d.strftime('%d %b')}</span>")
        d += _td(days=step)
    rows, undated = [], []
    for kind, depth, name, st, en, done, wid in items:
        if not (st or en):
            undated.append(name)
            continue
        a = st or en
        b = en or st
        left, width = x(a), max(x(b) - x(a) + 100 / span, 0.8)
        label = (f"<a href='/ticket/{t.esc(wid)}'>{t.esc(name)}</a>" if wid else t.esc(name))
        rows.append(f"<div class='grow {kind}{' done' if done else ''}'><div class=glabel style='padding-left:{depth * 14}px'>{label}</div>"
                    f"<div class=gtrack>{marker}<b class=gbar style='left:{left:.2f}%;width:{width:.2f}%'"
                    f" title='{t.esc(a)} → {t.esc(b)}'></b></div></div>")
    return ("<div class=card id=pgantt><h3>" + t.icon("calendar") + "Gantt</h3>"
            f"<div class=gantt><div class=grow><div class=glabel></div><div class='gtrack gticks'>{''.join(ticks)}</div></div>"
            + "".join(rows) + "</div>"
            + (f"<p class=why style='margin:8px 0 0'>Not on the chart yet (no dates): {t.esc(', '.join(undated))}.</p>" if undated else "")
            + "</div>")


def _close_dialog(ctx, p, pid) -> str:
    """Close the project as the reference PSA's close dialog does: its status,
    and if asked its open tickets to a closed status and its phases done."""
    closed = []
    if p["board_id"]:
        closed = ctx.conn.execute("SELECT board_status_id, name FROM board_status WHERE board_id = ? AND is_closed = 1"
                                  " AND inactive = 0 ORDER BY sort_order", (p["board_id"],)).fetchall()
    from ...setup import is_cancelled_name
    closed = sorted(closed, key=lambda r: is_cancelled_name(r["name"]))      # Closed before >Cancelled
    opts = ("<option value=''>The board's own closing status</option>"
            + "".join(f"<option value='{t.esc(r['board_status_id'])}'>{t.esc(r['name'].lstrip('>'))}</option>" for r in closed))
    return ("<dialog id=pclose class='card tedlg'>"
            f"<form method=post action='/project/{pid}/close' class=teform>"
            "<div class=tehead data-drag><div><h3 style='margin:0'>" + t.icon("check") + " Close the project</h3>"
            f"<div class=muted style='font-size:12.5px'>{pid} · {t.esc(p['name'])}</div></div>"
            "<span class=tewin><button type=button class=iconbtn data-close=pclose aria-label=Close>"
            "<b style='font-size:16px;line-height:1'>&#8211;</b></button></span></div>"
            "<div class=grid2><div><label>Close as</label><select name=status><option value=DONE>Done</option>"
            "<option value=CANCELLED>Cancelled</option></select></div><div></div>"
            "<label class=tick style='grid-column:1/-1'><input type=checkbox name=close_tickets value=1 checked>"
            " Close its open tickets</label>"
            + (f"<div><label>To the status</label><select name=ticket_status>{opts}</select></div><div></div>" if opts else "")
            + "<label class=tick style='grid-column:1/-1'><input type=checkbox name=close_phases value=1 checked>"
              " Mark its open phases done</label></div>"
              "<p class=why>A ticket on another board goes to that board's first closed status. Tickets and their time "
              "are kept; nothing is deleted.</p>"
              "<div class=tefoot><span class=grow></span><button type=button class=ghost data-close=pclose>Cancel</button>"
              "<button type=submit>" + t.icon("check") + " Close the project</button></div></form></dialog>")


def _ticket_plan_dialog(ctx, pid, tks) -> str:
    """One window for a project ticket's dates, budget and predecessors; the
    work plan's Plan button fills it."""
    opts = "<option value=''>(nothing)</option>" + "".join(
        f"<option value='{t.esc(r['work_item_id'])}'>{t.esc(r['work_item_id'])} {t.esc(r['summary'])}</option>" for r in tks)
    return ("<dialog id=ptplan class='card tedlg'>"
            f"<form method=post action='/project/{pid}/ticket/plan' class=teform>"
            "<div class=tehead data-drag><div><h3 style='margin:0'>" + t.icon("calendar") + " Plan <span data-fill=wid></span></h3>"
            "<div class=muted style='font-size:12.5px' data-fill=summary></div></div>"
            "<span class=tewin><button type=button class=iconbtn data-close=ptplan aria-label=Close>"
            "<b style='font-size:16px;line-height:1'>&#8211;</b></button></span></div>"
            "<input type=hidden name=work_item_id>"
            "<div class=grid2><div><label>Estimated start</label><input type=date name=starts_on></div>"
            "<div><label>Required by</label><input type=date name=due_on></div>"
            "<div><label>Budget hours</label><input name=budget_hours inputmode=decimal></div>"
            f"<div><label>Waits on</label><select name=depends_on>{opts}</select></div></div>"
            "<p class=why>A ticket that waits on another takes no time until that one is done, as the reference PSA has it.</p>"
            "<div class=tefoot><span class=grow></span><button type=button class=ghost data-close=ptplan>Cancel</button>"
            "<button type=submit>" + t.icon("check") + " Save</button></div></form></dialog>")


def _template_card(ctx, p, pid, phs, can) -> str:
    """A template's planned tickets and New project from it; on a project, Copy project (069)."""
    if not can:
        return ""
    who = t.esc(ctx.user.id)
    if projects.is_template(p):
        items = projects.plan_items(ctx.conn, p["project_id"])
        lis = "".join(
            f"<tr><td>{t.esc(i['summary'])}</td><td>{t.esc(i['phase_name'] or '')}</td>"
            f"<td>{'' if i['budget_hours'] is None else format(i['budget_hours'], 'g') + ' h'}</td>"
            f"<td><form method=post action='/project/{pid}/plan/remove' class=inline><input type=hidden name=item_id value={i['item_id']}>"
            "<button class='ghost small' type=submit>Remove</button></form></td></tr>" for i in items)
        phase_opts = "<option value=''>(no phase)</option>" + "".join(
            f"<option value={ph['phase_id']}>{'— ' * ph['depth']}{t.esc(ph['name'])}</option>" for ph in phs)
        return ("<div class=card id=ptemplate><h3>" + t.icon("layers") + "Template: planned tickets</h3>"
                "<p class=why style='margin-top:0'>These become real tickets, in the matching phases, on each project made "
                "from this template. Nothing here sits on a board.</p>"
                "<div class=tablewrap><table><thead><tr><th>Ticket</th><th>Phase</th><th>Budget</th><th></th></tr></thead>"
                f"<tbody>{lis or '<tr><td colspan=4 class=muted>None planned yet.</td></tr>'}</tbody></table></div>"
                f"<form method=post action='/project/{pid}/plan' class=grid2 style='margin-top:8px'>"
                "<div style='grid-column:1/-1'><label>Planned ticket</label><input name=summary required maxlength=200></div>"
                f"<div><label>Phase</label><select name=phase_id>{phase_opts}</select></div>"
                "<div><label>Budget hours</label><input name=budget_hours inputmode=decimal></div>"
                "<div><button class=ghost type=submit>" + t.icon("plus") + " Plan it</button></div></form>"
                f"<h3 style='margin-top:16px'>{t.icon('plus')}New project from this template</h3>"
                f"<form method=post action='/project/{pid}/copy' class=grid2>"
                "<div style='grid-column:1/-1'><label>Name</label><input name=name required maxlength=200></div>"
                "<div><label>Starts</label><input type=date name=starts_on></div>"
                f"<div><label>Manager</label><input name=manager value='{who}'></div>"
                "<div><button type=submit>Create the project</button></div></form></div>")
    return ("<div class=card id=pcopy><h3>" + t.icon("layers") + "Copy project</h3>"
            "<p class=why style='margin-top:0'>A new project with this one's phases, predecessors, team and contacts, and a new "
            "ticket for each of its tickets, unassigned. Dates move to the new start.</p>"
            f"<form method=post action='/project/{pid}/copy' class=grid2>"
            f"<div style='grid-column:1/-1'><label>Name</label><input name=name required maxlength=200 value='{t.esc(p['name'])} (copy)'></div>"
            "<div><label>Starts</label><input type=date name=starts_on></div>"
            f"<div><label>Manager</label><input name=manager value='{who}'></div>"
            "<div><button class=ghost type=submit>Copy</button></div></form>"
            + ("" if projects.tickets(ctx.conn, p["project_id"]) else
               f"<form method=post action='/project/{pid}/template' style='margin-top:10px'><input type=hidden name=on value=1>"
               "<button class='ghost small' type=submit>Make this a template</button>"
               " <span class=why>A template plans tickets instead of holding them.</span></form>")
            + "</div>")


def _plan_ticket_rows(rows, depth: int, hours: dict, heading: str | None = None, *, preds: dict | None = None,
                      pid: str = "", can: bool = False) -> list[str]:
    """A phase's tickets as rows under it in the work plan: the ticket, who has
    it, its hours against its budget, its dates and what it waits on (069)."""
    out = []
    preds = preds or {}
    if rows and heading:
        out.append(f"<tr class=planhead><td colspan=6 class=muted style='padding-left:8px'><b>{t.esc(heading)}</b></td></tr>")
    for r in rows:
        b = r["budget_hours"] if "budget_hours" in r.keys() else None
        st = r["starts_on"] if "starts_on" in r.keys() else None
        du = r["due_on"] if "due_on" in r.keys() else None
        waits = " ".join(
            f"<span class='chip{' sla-warn' if w['state'] not in ('RESOLVED', 'CLOSED', 'CANCELLED') else ''}'>{t.esc(w['depends_on'])}"
            + (f" <form method=post action='/project/{pid}/ticket/unwait' class=inline>"
               f"<input type=hidden name=work_item_id value='{t.esc(r['work_item_id'])}'>"
               f"<input type=hidden name=depends_on value='{t.esc(w['depends_on'])}'>"
               "<button class=linky type=submit title='Stop waiting on this'>&times;</button></form>" if can else "")
            + "</span>" for w in preds.get(r["work_item_id"], []))
        plan = (f"<button type=button class='ghost small' data-open=ptplan data-plan='{t.esc(r['work_item_id'])}'"
                f" data-summary='{t.esc(r['summary'])}' data-starts='{t.esc(st or '')}' data-due='{t.esc(du or '')}'"
                f" data-budget='{'' if b is None else format(b, 'g')}'>" + t.icon("calendar") + " Plan</button>" if can else "")
        out.append(f"<tr class=planticket><td style='padding-left:{8 + depth * 22}px'>{t.icon('note')} "
                   f"<a href='/ticket/{t.esc(r['work_item_id'])}'>{t.esc(r['work_item_id'])}</a> {t.esc(r['summary'])}</td>"
                   f"<td>{t.esc(st or '')} → {t.esc(du or '')}<div class=muted>{t.esc(r['owner'] or 'unassigned')}</div></td>"
                   f"<td>{_bar(hours.get(r['work_item_id'], 0.0), b)}</td>"
                   f"<td>{('waits on ' + waits) if waits else ''}</td><td>{t.esc(r['state'])}</td><td>{plan}</td></tr>")
    return out


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
    # the work plan (068): each phase's tickets under it, the viewer's boards only
    tks = [r for r in projects.tickets(ctx.conn, p["project_id"]) if r["board_id"] in seen]
    by_phase: dict = {}
    for r in tks:
        by_phase.setdefault(r["phase_id"], []).append(r)
    t_hours = projects.ticket_hours(ctx.conn, p["project_id"])
    preds = {r["work_item_id"]: projects.ticket_predecessors(ctx.conn, r["work_item_id"]) for r in tks}
    template = projects.is_template(p)
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
        if can and p["board_id"] and not template:
            act += (f" <button type=button class='ghost small' data-open=ptdlg data-phase='{ph_id}'"
                    " title='A new ticket in this phase'>" + t.icon("plus") + " Ticket</button>")
        rows.append(f"<tr{' style=opacity:.6' if ph['status'] == 'DONE' else ''}"
                    f"{' class=cur' if str(ph_id) == editing else ''}><td style='padding-left:{8 + ph['depth'] * 22}px'>"
                    f"{'└ ' if ph['depth'] else ''}<b>{t.esc(ph['name'])}</b></td>"
                    f"<td>{t.esc(ph['starts_on'] or '')} → {t.esc(ph['ends_on'] or '')}</td>"
                    f"<td>{_bar(ph['actual_hours'], ph['budget_hours'])}</td>"
                    f"<td>{('waits on ' + waits) if waits else ''}</td><td>{'Done' if ph['status'] == 'DONE' else 'Open'}</td><td>{act}</td></tr>")
        rows.extend(_plan_ticket_rows(by_phase.get(ph_id, []), ph["depth"] + 1, t_hours, preds=preds, pid=pid, can=can))
    rows.extend(_plan_ticket_rows(by_phase.get(None, []), 1, t_hours, heading="Not in a phase", preds=preds, pid=pid, can=can))
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
            f"<div><label>Company</label><select name=entity_id>{_company_opts(ctx, p['entity_id'])}</select></div>"
            "<div><label>Health</label><select name=health><option value=''>Read by the desk (budget and dates)</option>"
            + "".join(f"<option value='{k}'{' selected' if k == p['health'] else ''}>{v}</option>" for k, v in projects.HEALTH.items())
            + "</select></div>"
            f"<div><label>Board</label><select name=board_id>{_board_opts(ctx, p['board_id'], seen)}</select></div>"
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
        finance = ("<div class=card id=pfinance><h3>" + t.icon("tag") + "Finance (BizBox)</h3>"
                   + (f"<ul class=plain>{items}</ul>" if items else "<div class=muted>No BizBox record linked.</div>") + link + "</div>")
    actual = projects.actual_hours(ctx.conn, p["project_id"], boards=seen)
    pct = projects.percent_complete(ctx.conn, p["project_id"], boards=seen)
    budget_t = sum((r["budget_hours"] or 0) for r in tks)
    span = ctx.conn.execute(
        "SELECT MIN(te.worked_on), MAX(te.worked_on) FROM project_ticket pt JOIN time_entry te ON te.work_item_id ="
        " pt.work_item_id JOIN ticket tk ON tk.work_item_id = pt.work_item_id WHERE pt.project_id = ?"
        + (f" AND tk.board_id IN ({','.join('?' * len(seen))})" if seen else " AND 1 = 0"),
        [p["project_id"], *sorted(seen)]).fetchone()
    company = ""
    if p["entity_id"]:
        row = ctx.conn.execute("SELECT name FROM entity WHERE entity_id = ?", (p["entity_id"],)).fetchone()
        company = row[0] if row else p["entity_id"]
    dash = ("<div class=tiles style='grid-template-columns:repeat(auto-fit,minmax(150px,1fr))'>"
            f"<div class=tile><div class=n>{'—' if pct is None else str(pct) + '%'}</div><div class=l>Complete (tickets closed)</div></div>"
            f"<div class=tile><div class=n>{actual:g}</div><div class=l>Actual hours</div></div>"
            f"<div class=tile><div class=n>{(p['budget_hours'] or 0):g}</div><div class=l>Budget hours"
            + (f" · tickets {budget_t:g}" if budget_t else "") + "</div></div>"
            f"<div class=tile><div class=n>{len(tks)}</div><div class=l>Tickets</div></div>"
            f"<div class=tile><div class=n style='font-size:18px'>{t.esc(span[0] or '—')}</div><div class=l>Actual start"
            + (f" · last {t.esc(span[1])}" if span[1] else "") + "</div></div></div>")
    tabs = ("<nav class='tabs ptabs'><a href='#plan'>Work plan</a><a href='#pgantt'>Gantt</a><a href='#pboard'>Ticket board</a>"
            "<a href='#team'>Team</a><a href='#pcontacts-card'>Contacts</a><a href='#pnotes'>Notes</a><a href='#ptickets'>All tickets</a>"
            + ("<a href='#pfinance'>Finance</a>" if finance else "")
            + (f"<a href='#{'ptemplate' if template else 'pcopy'}'>{'Template' if template else 'Copy'}</a>" if can else "")
            + ("<a href='#psettings'>Project</a>" if can else "") + "</nav>")
    new_btn = (" <button type=button data-open=ptdlg>" + t.icon("plus") + " New ticket</button>"
               if can and p["board_id"] and not template else "")
    if can and not template and p["status"] not in ("DONE", "CANCELLED"):
        new_btn += " <button type=button class=ghost data-open=pclose>" + t.icon("check") + " Close project</button>"
    body = ((f"<div class='banner ok'>{t.esc(q.get('msg', ''))}</div>" if q.get("msg") else "")
            + (f"<div class='banner err'>{t.esc(q.get('err', ''))}</div>" if q.get("err") else "")
            + f"<div class=row style='align-items:center'><h1 style='flex:1'>{t.esc(p['name'])}</h1>{new_btn}</div>"
              f"<p class=sub>{pid} · " + (t.chip("Template") + " · " if template else "") + f"{t.chip(projects.STATUSES[p['status']])} · "
              + _health_chip(ctx, p, seen) + (f" · {t.esc(company)}" if company else "") + " · manager "
              f"{t.esc(p['manager'] or '—')} · {t.esc(p['starts_on'] or '?')} → {t.esc(p['ends_on'] or '?')} · "
              f"{t.esc(p['board_name'] or 'no board')} · {_bar(actual, p['budget_hours'])} · <a href='/projects'>Projects</a></p>"
            + dash + tabs
            + (f"<div class=card><div class=md>{t.md_to_html(p['description'])}</div></div>" if p["description"] else "")
            + "<div class=card id=plan><h3>" + t.icon("layers") + "Work plan: phases and their tickets</h3><div class=tablewrap><table><thead><tr><th>Phase</th><th>Dates</th>"
              f"<th>Hours</th><th>Predecessors</th><th>State</th><th></th></tr></thead><tbody>"
            + ("".join(rows) or "<tr><td colspan=6 class=muted>No phases yet.</td></tr>") + "</tbody></table></div></div>"
            + _gantt(ctx, p, phs, tks) + _ticket_board(ctx, p, tks) + _team_card(ctx, p, pid, can, tks)
            + _contacts_card(ctx, p, pid, can) + _notes_card(ctx, p["project_id"], can) + _template_card(ctx, p, pid, phs, can)
            + "<div class=card id=ptickets><h3>" + t.icon("note") + "All tickets</h3><div class=tablewrap><table><thead><tr><th>Ticket</th><th>Summary</th>"
              f"<th>Phase</th><th>State</th><th>Owner</th><th></th></tr></thead><tbody>{ticket_rows or '<tr><td colspan=6 class=muted>No tickets linked.</td></tr>'}"
              "</tbody></table></div></div>" + finance + (f"<div id=psettings>{forms}</div>" if forms else "")
            + (_new_ticket_dialog(ctx, p, pid, phs) if can and p["board_id"] and not template else "")
            + (_close_dialog(ctx, p, pid) + _ticket_plan_dialog(ctx, pid, tks) if can and not template else ""))
    return Response(body=t.page(p["name"], body, user=ctx.user, active="projects", live=f"project:{p['project_id']}"))


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
    for k in ("name", "description", "entity_id"):
        if k in f:
            fields[k] = f.get(k)
    if "board_id" in f:                      # 068: a project's board, only one the person is on
        if f.get("board_id") and f["board_id"] not in common.board_ids_for(ctx):
            return _back(f"/project/{project_id}", err="You are not on that board.")
        fields["board_id"] = f.get("board_id")
    def go():
        said = projects.update(ctx.conn, project_id, at=ctx.now, actor=ctx.user.id, **fields)
        if "health" in f:                                    # 069
            h = projects.set_health(ctx.conn, project_id, f.get("health") or None, at=ctx.now, actor=ctx.user.id)
            if h != "nothing changed":
                said = h if said == "nothing changed" else f"{said}; {h}"
        return said
    return _try(ctx, project_id, go, lambda r: f"Project: {r}")


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


# ------------------------------------------------------------- 068 handlers

def add_member(ctx, project_id):
    f = ctx.request.form()
    return _try(ctx, project_id, lambda: projects.add_member(
        ctx.conn, project_id, f.get("member", ""), role=f.get("role") or "TEAM_MEMBER", starts_on=f.get("starts_on"),
        ends_on=f.get("ends_on"), hours=f.get("hours"), at=ctx.now, actor=ctx.user.id), lambda r: r[:1].upper() + r[1:])


def remove_member(ctx, project_id):
    f = ctx.request.form()
    return _try(ctx, project_id, lambda: projects.remove_member(
        ctx.conn, project_id, f.get("member", ""), at=ctx.now, actor=ctx.user.id), lambda r: r[:1].upper() + r[1:])


def new_ticket(ctx, project_id):
    """POST /project/<id>/ticket/new: a ticket opened inside the project."""
    common.require_module(ctx, "PROJECTS", "WRITE")
    p = _load(ctx, project_id)
    if p["board_id"]:
        common.require_board(ctx, p["board_id"], need="WORK")
    f = ctx.request.form()
    try:
        wid = projects.open_ticket(ctx.conn, project_id, summary=f.get("summary", ""),
                                   phase_id=int(f["phase_id"]) if (f.get("phase_id") or "").isdigit() else None,
                                   owner=f.get("owner") or None, budget_hours=f.get("budget_hours"),
                                   description=f.get("description"), starts_on=f.get("starts_on"), due_on=f.get("due_on"),
                                   at=ctx.now, actor=ctx.user.id)
        ctx.conn.commit()
    except (projects.Refused, ValueError, LookupError) as exc:
        ctx.conn.rollback()
        return _back(f"/project/{project_id}", err=f"Ticket not created: {exc}")
    return _back(f"/project/{project_id}", msg=f"Ticket {wid} created in the project.")


def add_note(ctx, project_id):
    f = ctx.request.form()
    return _try(ctx, project_id, lambda: projects.add_note(ctx.conn, project_id, f.get("body", ""),
                                                           at=ctx.now, actor=ctx.user.id), lambda r: "Note added.")


# ------------------------------------------------------------- 069 handlers

def add_contact(ctx, project_id):
    f = ctx.request.form()
    raw = (f.get("contact") or "").strip()
    row = ctx.conn.execute("SELECT contact_id FROM contact WHERE contact_id = ? OR LOWER(COALESCE(email, '')) = LOWER(?)",
                           (raw, raw)).fetchone()
    return _try(ctx, project_id, lambda: projects.add_contact(
        ctx.conn, project_id, row[0] if row else raw, role=f.get("role"), at=ctx.now, actor=ctx.user.id),
        lambda r: r[:1].upper() + r[1:])


def remove_contact(ctx, project_id):
    f = ctx.request.form()
    return _try(ctx, project_id, lambda: projects.remove_contact(
        ctx.conn, project_id, f.get("contact_id", ""), at=ctx.now, actor=ctx.user.id), lambda r: r[:1].upper() + r[1:])


def _project_ticket(ctx, project_id, wid):
    """A ticket proven to be on this project and on a board the person may work."""
    from .. import HttpError
    row = ctx.conn.execute("SELECT pt.work_item_id, t.board_id FROM project_ticket pt JOIN ticket t ON t.work_item_id ="
                           " pt.work_item_id WHERE pt.work_item_id = ? AND pt.project_id = ?", (wid, project_id)).fetchone()
    if row is None:
        raise HttpError("404 Not Found", "That ticket is not on this project.")
    common.require_board(ctx, row["board_id"], need="WORK")
    return row["work_item_id"]


def plan_ticket(ctx, project_id):
    f = ctx.request.form()
    wid = (f.get("work_item_id") or "").strip()

    def go():
        _project_ticket(ctx, project_id, wid)
        said = projects.set_ticket_plan(ctx.conn, wid, starts_on=f.get("starts_on"), due_on=f.get("due_on"),
                                        budget_hours=f.get("budget_hours"), at=ctx.now, actor=ctx.user.id)
        if f.get("depends_on"):
            d = projects.add_ticket_dependency(ctx.conn, wid, f["depends_on"], at=ctx.now, actor=ctx.user.id)
            said = d if said == "nothing changed" else f"{said}; {d}"
        return said
    return _try(ctx, project_id, go, lambda r: r)


def unwait_ticket(ctx, project_id):
    f = ctx.request.form()
    wid = (f.get("work_item_id") or "").strip()

    def go():
        _project_ticket(ctx, project_id, wid)
        return projects.remove_ticket_dependency(ctx.conn, wid, f.get("depends_on", ""), at=ctx.now, actor=ctx.user.id)
    return _try(ctx, project_id, go, lambda r: r)


def close_project(ctx, project_id):
    f = ctx.request.form()
    p = _load(ctx, project_id)
    if f.get("close_tickets") == "1":
        for r in projects.tickets(ctx.conn, project_id):          # closing a ticket is work on its board
            if r["state"] not in ("RESOLVED", "CLOSED", "CANCELLED"):
                common.require_board(ctx, r["board_id"], need="WORK")
    return _try(ctx, project_id, lambda: projects.close(
        ctx.conn, project_id, f.get("status", ""), ticket_status=f.get("ticket_status") or None,
        close_tickets=f.get("close_tickets") == "1", close_phases=f.get("close_phases") == "1",
        at=ctx.now, actor=ctx.user.id), lambda r: f"{p['name']} closed: " + ("; ".join(r) or "nothing else to do"))


def set_template(ctx, project_id):
    f = ctx.request.form()
    return _try(ctx, project_id, lambda: projects.set_template(
        ctx.conn, project_id, f.get("on") == "1", at=ctx.now, actor=ctx.user.id), lambda r: r[:1].upper() + r[1:])


def add_plan_item(ctx, project_id):
    f = ctx.request.form()
    return _try(ctx, project_id, lambda: projects.add_plan_item(
        ctx.conn, project_id, summary=f.get("summary", ""),
        phase_id=int(f["phase_id"]) if (f.get("phase_id") or "").isdigit() else None,
        budget_hours=f.get("budget_hours"), at=ctx.now, actor=ctx.user.id), lambda r: "Planned ticket added.")


def remove_plan_item(ctx, project_id):
    f = ctx.request.form()
    return _try(ctx, project_id, lambda: projects.remove_plan_item(
        ctx.conn, project_id, int(f.get("item_id") or 0), at=ctx.now, actor=ctx.user.id), lambda r: r[:1].upper() + r[1:])


def copy_project(ctx, project_id):
    common.require_module(ctx, "PROJECTS", "WRITE")
    src = _load(ctx, project_id)
    if src["board_id"]:
        common.require_board(ctx, src["board_id"], need="WORK")
    f = ctx.request.form()
    try:
        pid = projects.copy(ctx.conn, project_id, name=f.get("name", ""), manager=f.get("manager") or None,
                            starts_on=f.get("starts_on") or None, at=ctx.now, actor=ctx.user.id)
        ctx.conn.commit()
    except (projects.Refused, ValueError, LookupError) as exc:
        ctx.conn.rollback()
        return _back(f"/project/{project_id}", err=f"Not created: {exc}")
    return _back(f"/project/{pid}", msg=f"Project made from {project_id}.")

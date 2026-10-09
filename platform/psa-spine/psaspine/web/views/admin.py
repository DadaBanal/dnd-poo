"""The admin surface — the §12 fence made operable.

The fence says no rule, floor, SLA or board configuration is hard-coded: if PMC
cannot change it without a deployment, it is in the wrong place. Today all of it
is editable only by SQL, which is the same failure wearing a different hat. This
surface closes that hole for the things Phase B owns: board statuses, board
membership, and disabling a break-glass account.

Access splits the way the data does. Board statuses and membership are
board-scoped, so they take ADMIN on that board. Break-glass accounts are
cross-board, so disabling one takes the sysadmin flag — and creating one is not
here at all: that stays CLI-only, by the auth design, so no web path can mint a
credential.
"""
from __future__ import annotations

import re
import urllib.parse

from ... import db, itil
from ... import intake as _intake
from ... import chat as chat_mod
from .. import templates as t
from . import common

ESCALATIONS = ("NOT_RESPONDED", "RESPONDED", "RESOLUTION_PLAN", "RESOLVED", "NO_ESCALATION")


def _slug(name: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "_", name.upper()).strip("_") or "STATUS"


def _admin_boards(ctx) -> list:
    return ctx.conn.execute(
        "SELECT b.board_id, b.display_name, b.calendar_id, b.restricted, b.is_unrouted,"
        "       b.inactive, b.is_live"
        "  FROM board b JOIN board_member m ON m.board_id = b.board_id"
        " WHERE m.member = ? AND m.access = 'ADMIN' ORDER BY b.display_name",
        (ctx.user.id,)).fetchall()


def index(ctx):
    """Setup home: the boards this user administers, each with what it still
    lacks, and the cross-board cards for a system administrator."""
    from .. import Response
    from ... import setup
    msg = ctx.request.query.get("msg", "")
    rows = []
    for b in _admin_boards(ctx):
        missing = setup.readiness(ctx.conn, b["board_id"])
        n = ctx.conn.execute("SELECT COUNT(*) FROM ticket WHERE board_id = ?",
                             (b["board_id"],)).fetchone()[0]
        state = ("<span class='chip sla-ok'>ready</span>" if not missing else
                 "<span class='chip sla-warn'>needs: " + t.esc("; ".join(missing)) + "</span>")
        flags = (" <span class=pill>restricted</span>" if b["restricted"] else "") + \
                (" <span class=pill>unrouted queue</span>" if b["is_unrouted"] else "") + \
                (" <span class=pill>retired</span>" if b["inactive"] else "") + \
                (" <span class='pill live'>live</span>"
                 if b["is_live"] else "")
        rows.append((itil.profile_of(ctx.conn, b["board_id"]) == "PROJECT",
                     f"<tr><td><a href='/admin/board/{t.esc(b['board_id'])}'><b>"
                     f"{t.esc(b['display_name'])}</b></a>{flags}</td><td>{state}</td>"
                     f"<td>{n}</td><td><a class='btn ghost' href='/admin/board/{t.esc(b['board_id'])}'>"
                     "Set up</a></td></tr>"))
    cards = []
    if ctx.user.is_sysadmin:
        from ... import members as members_engine
        n_members = len(members_engine.all_(ctx.conn))
        cards.append(
            "<div class=card><h3><svg class=ic aria-hidden=true><use href=#i-users></use></svg>Members</h3>"
            "<p class=sub>Everyone who works the desk, one page each: the record, the boards they are on, their "
            "security role, their hours, the break-glass account, and what happens when they leave.</p>"
            f"<div class=row><div style='flex:0 0 auto'><a class=btn href='/admin/members'>Members ({n_members})</a></div></div></div>")
        n_audit = ctx.conn.execute("SELECT COUNT(*) FROM audit_event").fetchone()[0]
        n_tokens = ctx.conn.execute("SELECT COUNT(*) FROM api_token WHERE disabled = 0").fetchone()[0]
        cards.append(
            "<div class=card><h3><svg class=ic aria-hidden=true><use href=#i-shield></use></svg>Audit and API tokens</h3>"
            "<p class=sub>Every change the desk has written: who, when, what, where from; filter and export it. "
            "And the machine credentials: one board and one scope each, minted here and shown once.</p>"
            f"<div class=row><div style='flex:0 0 auto'><a class=btn href='/admin/audit'>Audit ({n_audit})</a></div>"
            f"<div style='flex:0 0 auto'><a class='btn ghost' href='/admin/api-tokens'>API tokens ({n_tokens} live)</a></div>"
            "<div style='flex:0 0 auto'><a class='btn ghost' href='/admin/mail'>Email connector</a></div></div></div>")
        n_items = ctx.conn.execute("SELECT COUNT(*) FROM catalogue_item").fetchone()[0]
        cards.append(
            "<div class=card><h3><svg class=ic aria-hidden=true><use href=#i-layers></use></svg>Boards and the service catalogue</h3>"
            "<p class=sub>Boards are split by who does the work and how it flows, "
            "never by incident versus request. A <b>service</b> board's Types are "
            "Incident, Request, Problem and Event (ITIL's service desk takes both incidents and "
            "requests); a <b>change</b> board runs assessment, approval and scheduling; a "
            "<b>project</b> board runs projects with no SLA clocks. A person can be on as many "
            "boards as they work.</p>"
            "<div class=row><div style='flex:0 0 auto'><a class=btn href='/admin/board/new'>"
            "+ New board</a></div>"
            "<div style='flex:0 0 auto'><form method=post action='/admin/catalogue/template'>"
            "<button class=ghost type=submit>Load the Dada PSA template</button></form></div>"
            f"<div style='flex:0 0 auto'><a class='btn ghost' href='/admin/catalogue'>Catalogue: Type / Subtype / "
            f"Item ({n_items})</a></div>"
            "<div style='flex:0 0 auto'><a class='btn ghost' href='/admin/configuration-types'>Configuration types</a></div>"
            "<div style='flex:0 0 auto'><a class='btn ghost' href='/admin/portal-tiles'>Portal tiles</a></div>"
            "<div style='flex:0 0 auto'><a class='btn ghost' href='/admin/priorities'>Priorities</a></div>"
            "<div style='flex:0 0 auto'><a class='btn ghost' href='/admin/kb-categories'>Knowledge categories</a></div>"
            "<div style='flex:0 0 auto'><a class='btn ghost' href='/admin/projects'>Projects</a></div>"
            "<div style='flex:0 0 auto'><a class='btn ghost' href='/admin/companies'>Company status and type</a></div></div>"
            "<p class=why style='margin-top:10px'>The template is Dada's design on the "
            "ITIL model: IT Help as the service board with his Subtype › Item catalogue, plus an "
            "IT Change board and an IT Projects board. His Request-board SLA numbers become "
            "Request targets on IT Help. Items for boards that do not exist yet wait until those "
            "boards are created. It adds what is missing and never overwrites.</p></div>")
    if ctx.user.is_sysadmin:
        from ... import departments as _departments
        n_dept = ctx.conn.execute("SELECT COUNT(*) FROM department WHERE retired = 0").fetchone()[0]
        n_open = ctx.conn.execute("SELECT COUNT(DISTINCT department) FROM department_board").fetchone()[0]
        cards.append(
            "<div class=card><h3><svg class=ic aria-hidden=true><use href=#i-building></use></svg>Departments</h3><p class=sub>"
            "Which departments may send requests to which boards: the checklist the Employee Portal door "
            "and the portal's form obey.</p>"
            f"<a class='btn ghost' href='/admin/departments'>Departments ({n_open} of {n_dept} open)</a></div>")
        from ... import board as _board
        _board.ensure_time_vocabulary(ctx.conn)
        n_roles = ctx.conn.execute("SELECT COUNT(*) FROM work_role WHERE inactive = 0").fetchone()[0]
        n_types = ctx.conn.execute("SELECT COUNT(*) FROM work_type WHERE inactive = 0").fetchone()[0]
        from ... import security as _sec
        _sec.ensure_roles(ctx.conn)
        n_roles_sec = ctx.conn.execute("SELECT COUNT(*) FROM security_role WHERE inactive = 0").fetchone()[0]
        cards.append(
            "<div class=card><h3><svg class=ic aria-hidden=true><use href=#i-users></use></svg>Security roles</h3><p class=sub>"
            "What each role may do in the knowledge base, projects, reports, the schedule and finance.</p>"
            f"<a class='btn ghost' href='/admin/roles'>Roles ({n_roles_sec})</a></div>")
        from ... import bizbox as _bz
        st = _bz.status(ctx.conn)
        cards.append(
            "<div class=card><h3><svg class=ic aria-hidden=true><use href=#i-tag></use></svg>BizBox</h3><p class=sub>"
            "Agreements, procurement, products and invoices, mirrored read-only by <code>psaspine sync-bizbox</code>.</p>"
            f"<p class=why>{t.esc('Last synced ' + st['last_sync_at']) if st and st['last_sync_at'] else 'Not synced yet.'}</p>"
            "<a class='btn ghost' href='/finance'>Finance</a></div>")
        n_cal = ctx.conn.execute("SELECT COUNT(*) FROM calendar WHERE COALESCE(inactive, 0) = 0").fetchone()[0]
        n_hol = ctx.conn.execute("SELECT COUNT(*) FROM holiday").fetchone()[0]
        cards.append(
            "<div class=card><h3><svg class=ic aria-hidden=true><use href=#i-calendar></use></svg>Calendars</h3><p class=sub>"
            "The working weeks the SLA clocks run on, and the holiday lists that stop them: the reference PSA's "
            "Calendar and Holiday List setup tables.</p>"
            f"<a class='btn ghost' href='/admin/calendars'>Calendars ({n_cal}) and holidays ({n_hol})</a></div>")
        cards.append(
            "<div class=card><h3><svg class=ic aria-hidden=true><use href=#i-calendar></use></svg>Schedule</h3><p class=sub>"
            "What a visit's status and its where can be: the reference PSA's Schedule Status and Service Location "
            "setup tables.</p><a class='btn ghost' href='/admin/schedule'>Statuses and where</a></div>")
        cards.append(
            "<div class=card><h3><svg class=ic aria-hidden=true><use href=#i-clock></use></svg>Time</h3><p class=sub>"
            "The work roles and work types a time entry is written against, as Dada PSA has them.</p>"
            f"<a class='btn ghost' href='/admin/time'>Work roles ({n_roles}) and work types ({n_types})</a></div>")
    if rows or ctx.user.is_sysadmin:
        n_rules = ctx.conn.execute("SELECT COUNT(*) FROM workflow WHERE is_active = 1").fetchone()[0]
        cards.append(
            "<div class=card><h3><svg class=ic aria-hidden=true><use href=#i-sparkle></use></svg>Workflow rules</h3><p class=sub>Escalations, notifications and "
            "routing as rules: an event, conditions, actions. Test, then switch on.</p>"
            f"<a class='btn ghost' href='/admin/rules'>Workflow rules ({n_rules} on)</a></div>")
        n_rec = ctx.conn.execute("SELECT COUNT(*) FROM recurrence WHERE active = 1").fetchone()[0]
        cards.append(
            "<div class=card><h3><svg class=ic aria-hidden=true><use href=#i-calendar></use></svg>Recurring tickets</h3><p class=sub>"
            "A board template raised on a cadence: the monthly analyser check, the quarterly printer care. The minute "
            "runner raises each on its due day.</p>"
            f"<a class='btn ghost' href='/admin/recurring'>Recurring tickets ({n_rec} active)</a></div>")
    service_rows = [r for is_project, r in rows if not is_project]
    project_rows = [r for is_project, r in rows if is_project]
    if service_rows:
        cards.append("<div class=card><h3><svg class=ic aria-hidden=true><use href=#i-layers></use></svg>Your service boards</h3><div class=tablewrap><table>"
                     "<thead><tr><th>Board</th><th>Setup</th><th>Tickets</th><th></th></tr></thead>"
                     "<tbody>" + "".join(service_rows) + "</tbody></table></div></div>")
    # Project boards are their own setup table in the reference PSA (7 Oct 2026): the same
    # tabs as a service board (statuses, types, members, teams) and no SLA clocks, and
    # their tickets never reach the Service Board.
    if project_rows or ctx.user.is_sysadmin:
        cards.append("<div class=card id=project-boards><h3><svg class=ic aria-hidden=true><use href=#i-layers></use></svg>Project boards</h3>"
                     "<p class=sub>Where project tickets live, apart from the service boards: their own statuses, types and "
                     "members, no SLA clocks, and worked from Projects, never from the Service Board.</p>"
                     + ("<div class=tablewrap><table><thead><tr><th>Board</th><th>Setup</th><th>Tickets</th><th></th></tr></thead>"
                        "<tbody>" + "".join(project_rows) + "</tbody></table></div>" if project_rows else
                        "<div class=muted>No project board yet.</div>")
                     + ("<div style='margin-top:10px'><a class=btn href='/admin/board/new?kind=PROJECT'>+ New project board</a></div>"
                        if ctx.user.is_sysadmin else "") + "</div>")
    if ctx.user.is_sysadmin:
        orphans = ctx.conn.execute(
            "SELECT b.board_id, b.display_name FROM board b"
            " WHERE NOT EXISTS (SELECT 1 FROM board_member m WHERE m.board_id = b.board_id)"
            " ORDER BY b.display_name").fetchall()
        if orphans:
            cards.append(
                "<div class=card><h3><svg class=ic aria-hidden=true><use href=#i-layers></use></svg>"
                "Boards with no administrator</h3><p class=sub>A board the seed created has no "
                "members, and board access is membership only: nobody can open it until it has a "
                "first administrator. A system administrator may name one here, once; after that "
                "the board's own administrators manage its members. Audited.</p>"
                "<div class=tablewrap><table><thead><tr><th>Board</th><th>First administrator</th>"
                "</tr></thead><tbody>" + "".join(
                    f"<tr><td><b>{t.esc(o['display_name'])}</b> <span class=muted>{t.esc(o['board_id'])}</span></td>"
                    f"<td><form method=post action='/admin/board/{t.esc(o['board_id'])}/claim' class=row>"
                    f"<input name=member value='{t.esc(ctx.user.id)}' aria-label='account' style='max-width:220px'>"
                    "<button type=submit>Make administrator</button></form></td></tr>"
                    for o in orphans) + "</tbody></table></div></div>")
        n_links = ctx.conn.execute("SELECT COUNT(*) FROM integration_link WHERE inactive = 0").fetchone()[0]
        cards.append(
            "<div class=card><h3><svg class=ic aria-hidden=true><use href=#i-link></use></svg>Integrations</h3><p class=sub>Links out from configurations and "
            "contacts to the tools the desk does not replace: ScreenConnect first.</p>"
            f"<a class='btn ghost' href='/admin/integrations'>Integrations ({n_links} on)</a></div>")
        cards.append(_local_accounts_card(ctx))
        cards.append(_config_overview_card(ctx))
    if not cards:
        cards.append("<div class='card'><div class='empty'>You administer no boards, "
                     "and are not a system administrator. Nothing to configure here.</div></div>")
    body = ((f"<div class='banner ok'>{t.esc(msg)}</div>" if msg else "") +
            "<h1>Setup</h1><p class='sub'>Configuration lives in data, not in a "
            "deployment (§12). Board settings take board admin; break-glass "
            "accounts take a system administrator. Every change is audited.</p>" + "".join(cards))
    return Response(body=t.page("Setup", body, user=ctx.user, active="admin"))


TABS = (("board", "Board"), ("types", "Types"), ("statuses", "Statuses"), ("sla", "SLA"),
        ("templates", "Templates"), ("notes", "Standard notes"), ("members", "Members & roles"),
        ("emails", "Emails"), ("assign", "Auto-assign"))
ROLES = ("SERVICE_MANAGER", "DISPATCH", "ON_CALL", "DUTY_MANAGER")
TYPE_HELP = {
    "INCIDENT": "Something is broken: restore the service.",
    "SERVICE_REQUEST": "Something is needed: access, a new user, a move.",
    "PROBLEM": "The cause behind one or more incidents.",
    "EVENT": "Raised by monitoring, not a person.",
    "CHANGE": "A change to a system: assessed and approved before it is made.",
    "PROJECT": "Planned work with a start and an end. No SLA clocks.",
}
ESC_LABEL = {"NOT_RESPONDED": "Not responded", "RESPONDED": "Responded",
             "RESOLUTION_PLAN": "Resolution plan", "RESOLVED": "Resolved",
             "NO_ESCALATION": "Waiting (pauses resolve)"}


def board_setup(ctx, board_id):
    from .. import HttpError, Response
    from ... import setup
    common.require_board(ctx, board_id, need="ADMIN")
    b = ctx.conn.execute("SELECT * FROM board WHERE board_id = ?", (board_id,)).fetchone()
    if b is None:
        raise HttpError("404 Not Found", "No such board.")
    tab = ctx.request.query.get("tab", "statuses")
    msg = ctx.request.query.get("msg", "")
    bid = t.esc(board_id)
    tabs = "<div class=stabs>" + "".join(
        f"<a class='{'on' if tab == k else ''}' href='/admin/board/{bid}?tab={k}'>{v}</a>"
        for k, v in TABS) + "</div>"
    missing = setup.readiness(ctx.conn, board_id)
    ready = ("" if not missing else
             f"<div class=note-ph>This board still needs {t.esc('; '.join(missing))}. "
             f"<form class=inline method=post action='/admin/board/{bid}/starter'>"
             "<button type=submit style='padding:3px 10px;margin-left:6px'>Apply the starter setup</button>"
             "</form> It adds only what is missing and never overwrites a change.</div>")

    if tab == "board":
        from ... import calendars as _cal
        cals = _cal.live_calendars(ctx.conn, keep=b["calendar_id"])
        cal_opts = "<option value=''>(none — no clocks)</option>" + "".join(
            f"<option value='{t.esc(c['calendar_id'])}'{' selected' if c['calendar_id'] == b['calendar_id'] else ''}>"
            f"{t.esc(c['name'])}</option>" for c in cals)
        def chk(name, v, label):
            return (f"<label style='display:block;margin-top:8px;color:var(--ink);font-weight:500'>"
                    f"<input type=checkbox name={name} value=1 style='width:auto'"
                    f"{' checked' if v else ''}> {label}</label>")
        content = (
            "<div class=card><h3><svg class=ic aria-hidden=true><use href=#i-board></use></svg>Board</h3>"
            f"<form method=post action='/admin/board/{bid}/settings'><div class=grid2>"
            f"<div><label>Name</label><input name=display_name value='{t.esc(b['display_name'])}' required></div>"
            f"<div><label>Fulfiller group</label><input name=fulfiller_group value='{t.esc(b['fulfiller_group'])}'></div>"
            f"<div><label>Owner</label><input name=owner value='{t.esc(b['owner'] or '')}' placeholder='a named person'></div>"
            f"<div><label>Deputy</label><input name=deputy value='{t.esc(b['deputy'] or '')}' placeholder='a named person'></div>"
            f"<div style='grid-column:1/-1'><label>Description</label><input name=description value='{t.esc(b['description'] or '')}'></div>"
            "<div>" + chk("restricted", b["restricted"], "Restricted — members only, every read audited")
            + chk("closed_loop_required", b["closed_loop_required"], "Closed loop required")
            + chk("notify_requester", b["notify_requester"] == 1,
                  "Email the requester when their ticket is opened or updated (no note text;"
                  " needs the portal address on the sender)")
            + chk("notify_owner", b["notify_owner"] == 1,
                  "Email the owner when a ticket is assigned to them, and a member when a visit is booked for them")
            + "</div><div>" + chk("is_live", b["is_live"], "Live (needs an owner and a deputy)")
            + chk("inactive", b["inactive"], "Retired — no new tickets; history kept") + "</div>"
            f"<div><label>Time entries start with this work role</label><select name=default_work_role_id>"
            f"{_time_opts(ctx, 'work_role', b['default_work_role_id'])}</select></div>"
            f"<div><label>… and this work type</label><select name=default_work_type_id>"
            f"{_time_opts(ctx, 'work_type', b['default_work_type_id'])}</select></div>"
            "<div>" + chk("survey_enabled", b["survey_enabled"] != 0,
                          "Ask the requester how we did once their ticket is closed (on the portal, one to five)") + "</div>"
            f"<div><label>The survey's question</label><input name=survey_question maxlength=120"
            f" value='{t.esc(b['survey_question'] or '')}' placeholder='How did we do?'></div>"
            "<div style='grid-column:1/-1'>" + chk("takes_chats", bool(b["takes_chats"] if "takes_chats" in b.keys() else 0),
                                                   "Takes chats from the portal: wards chat with this board, and its "
                                                   "chat operators answer (Setup › Members)") + "</div>"
            "<div style='grid-column:1/-1'><label>Chat welcome: what a ward reads while its chat waits to be picked "
            "up ({board} is this board's name)</label><textarea name=chat_welcome rows=2 maxlength=300 placeholder='"
            + t.esc(chat_mod.DEFAULT_WELCOME) + "'>" + t.esc((b["chat_welcome"] if "chat_welcome" in b.keys() else None) or "") + "</textarea></div>"
            "</div><div style='margin-top:12px'><button type=submit>Save board</button></div></form>"
            + _reply_policy_form(ctx, b) +
            f"<form method=post action='/admin/board/{bid}/calendar' class=row style='margin-top:14px'>"
            f"<div><label>Calendar the SLA clocks run on</label><select name=calendar_id>{cal_opts}</select></div>"
            "<div style='flex:0 0 auto'><button type=submit>Save</button></div>"
            "<div style='flex:0 0 auto'><a class='btn ghost' href='/admin/calendars'>Calendars and holidays</a></div></form>"
            f"<form method=post action='/admin/board/{bid}/starter' style='margin-top:14px'>"
            "<button class=ghost type=submit>Apply the starter setup</button> "
            "<span class=why>Adds any missing statuses, calendars and SLA targets. Never overwrites.</span>"
            "</form></div>")
    elif tab == "templates":
        from ... import setup as _setup
        tpls = ctx.conn.execute(
            "SELECT tt.*, (SELECT COUNT(*) FROM ticket_template_task x WHERE x.template_id ="
            " tt.template_id) AS n FROM ticket_template tt WHERE board_id = ? ORDER BY name",
            (board_id,)).fetchall()
        trs = "".join(
            f"<tr><td><a href='/ticket/new?template={t.esc(x['template_id'])}'>{t.esc(x['name'])}</a>"
            + (" <span class=chip>retired</span>" if x["inactive"] else "") + "</td>"
            f"<td>{t.esc(itil.LABEL.get(x['record_type'], '—'))}</td><td>{x['n']}</td>"
            f"<td><form method=post action='/admin/board/{bid}/template/toggle' class=inline>"
            f"<input type=hidden name=template_id value='{t.esc(x['template_id'])}'>"
            f"<button class=ghost type=submit style='padding:3px 10px'>{'Use' if x['inactive'] else 'Retire'}"
            "</button></form></td></tr>" for x in tpls) or \
            "<tr><td colspan=4 class=muted>No templates yet.</td></tr>"
        types = [(r["record_type"], itil.LABEL[r["record_type"]]) for r in itil.boards_types(ctx.conn, board_id)] \
            or [(k, v) for k, v in itil.LABEL.items()]
        items = [(c["catalogue_item_id"], c["label"]) for c in _setup.catalogue_choices(ctx.conn, board_id)]
        opt = lambda pairs: "".join(f"<option value='{t.esc(k)}'>{t.esc(v)}</option>" for k, v in pairs)  # noqa: E731
        content = (
            "<div class=card><h3><svg class=ic aria-hidden=true><use href=#i-checks></use></svg>Ticket templates</h3><p class=sub>Recipes for repeatable work on this "
            "board, as Dada PSA's service templates: a summary, a Type, a Subtype › Item, a description "
            "and a checklist. Start a ticket from one (New ticket › Use template), apply one to an open "
            "ticket, or have a workflow rule apply one.</p><div class=tablewrap><table><thead><tr>"
            "<th>Template</th><th>Type</th><th>Tasks</th><th></th></tr></thead>"
            f"<tbody>{trs}</tbody></table></div></div>"
            f"<div class=card><h3><svg class=ic aria-hidden=true><use href=#i-plus></use></svg>New template</h3><form method=post action='/admin/board/{bid}/template'>"
            "<div class=grid2><div><label>Name</label><input name=name required placeholder='e.g. New starter'></div>"
            "<div><label>Ticket summary</label><input name=summary placeholder='e.g. New starter: account and badge'></div>"
            f"<div><label>Ticket type</label><select name=record_type><option value=''>(board default)</option>{opt(types)}</select></div>"
            f"<div><label>Subtype › Item</label><select name=catalogue_item_id><option value=''>(not classified)</option>{opt(items)}</select></div>"
            "<div style='grid-column:1/-1'><label>Description</label><textarea name=description "
            "placeholder='What the technician should check first. The ward, room and machine, never a patient.'></textarea></div>"
            "<div style='grid-column:1/-1'><label>Tasks, one per line</label><textarea name=tasks "
            "placeholder='Create the AD account&#10;Add to HIS roles&#10;Issue the badge'></textarea></div>"
            "</div><div style='margin-top:12px'><button type=submit>Save template</button></div></form></div>")
    elif tab == "notes":
        from ... import canned
        notes = canned.notes_for(ctx.conn, board_id, include_inactive=True)
        trs = "".join(
            f"<tr><td><b>{t.esc(n['name'])}</b>" + (" <span class=chip>retired</span>" if n["inactive"] else "")
            + f"</td><td><span class='flag {n['flag']}'>{t.esc(n['flag'].title())}</span></td>"
            f"<td style='white-space:pre-wrap;max-width:520px'>{t.esc(n['body'])}</td>"
            f"<td><form method=post action='/admin/board/{bid}/standard-note/toggle' class=inline>"
            f"<input type=hidden name=note_id value='{n['note_id']}'>"
            f"<button class=ghost type=submit style='padding:3px 10px'>{'Use' if n['inactive'] else 'Retire'}"
            "</button></form></td></tr>" for n in notes) or \
            "<tr><td colspan=4 class=muted>No standard notes yet.</td></tr>"
        content = (
            "<div class=card><h3><svg class=ic aria-hidden=true><use href=#i-note></use></svg>Standard notes</h3>"
            "<p class=sub>Canned replies for this board, as Dada PSA's standard notes: a technician picks "
            "one in the note box and it fills in, flagged the way it was written. Written before any ticket "
            "exists, so never with a patient's details.</p><div class=tablewrap><table><thead><tr>"
            "<th>Name</th><th>Flag</th><th>Text</th><th></th></tr></thead>"
            f"<tbody>{trs}</tbody></table></div></div>"
            f"<div class=card><h3><svg class=ic aria-hidden=true><use href=#i-plus></use></svg>New standard note</h3>"
            f"<form method=post action='/admin/board/{bid}/standard-note'>"
            "<div class=grid2><div><label>Name</label><input name=name required placeholder='e.g. Received, looking now'></div>"
            "<div><label>Flag</label><select name=flag><option value=DISCUSSION>Discussion (the requester reads it)</option>"
            "<option value=INTERNAL>Internal (desk only)</option></select></div>"
            "<div style='grid-column:1/-1'><label>Text</label><textarea name=body required "
            "placeholder='Thank you, we have your request and are looking at it now.'></textarea></div>"
            "</div><div style='margin-top:12px'><button type=submit>Save standard note</button></div></form></div>")
    elif tab == "types":
        kind = itil.profile_of(ctx.conn, board_id) or "SERVICE"
        rows = {r["record_type"]: r["is_default"] for r in itil.boards_types(ctx.conn, board_id)}
        default = next((k for k, v in rows.items() if v), None)
        lines = "".join(
            "<tr><td><label style='color:var(--ink);font-weight:500'>"
            f"<input type=checkbox name=types value={k} style='width:auto'"
            f"{' checked' if k in rows else ''}> {t.esc(itil.LABEL[k])}</label></td>"
            f"<td><input type=radio name=default value={k} style='width:auto'"
            f"{' checked' if k == default else ''} aria-label='default {t.esc(itil.LABEL[k])}'></td>"
            f"<td class=muted>{t.esc(TYPE_HELP[k])}</td></tr>" for k in itil.RECORD_TYPES)
        content = (
            f"<div class=card><h3><svg class=ic aria-hidden=true><use href=#i-tag></use></svg>Types</h3><p class=sub>This is a <b>{t.esc(kind.lower())}</b> "
            "board. Its Types tab: a ticket here reads Type › Subtype › "
            "Item. None ticked means the board takes every Type. The default is what a ticket "
            "gets when nothing else says (an email, say).</p>"
            f"<form method=post action='/admin/board/{bid}/types'><div class=tablewrap><table>"
            "<thead><tr><th>Type</th><th>Default</th><th></th></tr></thead>"
            f"<tbody>{lines}</tbody></table></div>"
            "<div style='margin-top:12px'><button type=submit>Save Types</button></div></form></div>")
    elif tab == "sla":
        targets = {(r["priority"], r["clock"]): r["target_minutes"] for r in ctx.conn.execute(
            "SELECT priority, clock, target_minutes FROM sla_target WHERE board_id = ?", (board_id,))}
        rows = "".join(
            f"<tr><td>{t.badge(p)}</td>" + "".join(
                f"<td><input name='t_{p}_{c}' value='{targets.get((p, c), '')}' inputmode=numeric "
                "style='width:100px'> min</td>" for c in setup.CLOCKS) + "</tr>"
            for p in ("P1", "P2", "P3", "P4"))
        content = (
            "<div class=card><h3><svg class=ic aria-hidden=true><use href=#i-clock></use></svg>SLA targets</h3><div class=note-ph>Measured and reported, "
            "<b>not enforced or promised</b> (every target is enforced = 0). A blank cell means "
            "that clock does not start for that priority. Changes apply to tickets opened after "
            "saving; a ticket's priority change re-targets its running clocks.</div>"
            f"<form method=post action='/admin/board/{bid}/sla'><table class=edit><thead><tr>"
            "<th>Priority</th><th>Respond</th><th>Resolution plan</th><th>Resolve</th></tr></thead>"
            f"<tbody>{rows}</tbody></table><div style='margin-top:12px'>"
            "<button type=submit>Save targets</button></div></form></div>")
    elif tab == "members":
        named = {r["role"]: r["member"] for r in ctx.conn.execute(
            "SELECT role, member FROM board_role WHERE board_id = ?", (board_id,))}
        teams = ctx.conn.execute("SELECT team_id, name, team_leader, is_default FROM board_team"
                                 " WHERE board_id = ? ORDER BY name", (board_id,)).fetchall()
        team_name = {tm["team_id"]: tm["name"] for tm in teams}
        members = ctx.conn.execute("SELECT member, access, team_id FROM board_member WHERE board_id = ?"
                                   " ORDER BY member", (board_id,)).fetchall()
        member_rows = "".join(f"<tr><td>{t.esc(m['member'])}</td><td>{t.esc(m['access'])}</td>"
                              f"<td>{t.esc(team_name.get(m['team_id'], '—'))}</td></tr>"
                              for m in members)
        team_opts = "<option value=''>(no team)</option>" + "".join(
            f"<option value='{t.esc(tm['team_id'])}'>{t.esc(tm['name'])}</option>" for tm in teams)
        team_rows = "".join(f"<tr><td>{t.esc(tm['name'])}</td><td>{t.esc(tm['team_leader'] or '—')}</td>"
                            f"<td>{'default' if tm['is_default'] else ''}</td></tr>" for tm in teams)
        role_rows = "".join(
            f"<div><label>{t.esc(r.replace('_', ' ').title())}</label>"
            f"<input name='{r}' value='{t.esc(named.get(r, ''))}' placeholder='a named person'></div>"
            for r in ROLES)
        content = (
            "<div class=card><h3><svg class=ic aria-hidden=true><use href=#i-users></use></svg>Members</h3><p class=sub>A person can belong to any number of "
            "boards. READ sees the board; WORK works its tickets; ADMIN sets it up.</p>"
            "<div class=tablewrap><table><thead><tr><th>Member</th>"
            f"<th>Access</th><th>Team</th></tr></thead><tbody>{member_rows}</tbody></table></div>"
            "<form method=post action='/admin/member/add' class=row style='margin-top:12px'>"
            f"<input type=hidden name=board_id value='{bid}'><input type=hidden name=back value='members'>"
            "<div><label>Member</label><input name=member required></div>"
            "<div><label>Access</label><select name=access><option>READ</option><option selected>WORK"
            "</option><option>ADMIN</option></select></div>"
            f"<div><label>Team</label><select name=team_id>{team_opts}</select></div>"
            "<div style='flex:0 0 auto'><button type=submit>Add or change</button></div></form></div>"
            "<div class=card><h3><svg class=ic aria-hidden=true><use href=#i-users></use></svg>Teams</h3><p class=sub>Teams inside a board — who a queue "
            "falls to when nobody owns a ticket.</p><div class=tablewrap><table><thead><tr>"
            f"<th>Team</th><th>Leader</th><th></th></tr></thead><tbody>{team_rows or '<tr><td colspan=3 class=muted>No teams yet.</td></tr>'}"
            "</tbody></table></div>"
            f"<form method=post action='/admin/board/{bid}/team' class=row style='margin-top:12px'>"
            "<div><label>Team name</label><input name=name required></div>"
            "<div><label>Team leader</label><input name=team_leader placeholder='a named person'></div>"
            "<div style='flex:0 0 auto'><label>Default</label><select name=is_default><option value=0>no"
            "</option><option value=1>yes</option></select></div>"
            "<div style='flex:0 0 auto'><button type=submit>Add team</button></div></form></div>"
            "<div class=card><h3><svg class=ic aria-hidden=true><use href=#i-users></use></svg>The four board roles</h3><p class=sub>Service "
            "Manager, Dispatch, On-Call and Duty Manager (who is told when On-Call does not "
            "answer). The rota on the On-call page overrides the named On-Call.</p>"
            f"<form method=post action='/admin/board/{bid}/roles'><div class=grid2>{role_rows}</div>"
            "<div style='margin-top:12px'><button type=submit>Save roles</button></div></form></div>")
    elif tab == "emails":
        from ... import outbox as _outbox
        blocks = []
        for kind, label in _outbox.TEMPLATE_KINDS.items():
            tpl = _outbox.template(ctx.conn, board_id, kind)
            blocks.append(
                f"<div class=card><h3>{t.icon('mail')}{t.esc(label)}"
                + (f" <span class=pill>the board's own words · {t.esc(tpl['updated_at'])} · {t.esc(tpl['updated_by'])}</span>"
                   if tpl["custom"] else " <span class=muted style='font-weight:400;font-size:.85em'>the desk's words</span>") + "</h3>"
                f"<form method=post action='/admin/board/{bid}/emails' class=stack style='max-width:none'>"
                f"<input type=hidden name=kind value='{kind}'>"
                f"<label>Subject (after the ticket's reference)<input name=subject required maxlength=120 value='{t.esc(tpl['subject'])}'></label>"
                f"<label>Body<textarea name=body required style='min-height:90px'>{t.esc(tpl['body'])}</textarea></label>"
                "<div><button type=submit>Save</button> "
                + (f"<button class=ghost type=submit name=reset value=1>Back to the desk's words</button>" if tpl["custom"] else "")
                + "</div></form></div>")
        smails = _outbox.status_mails(ctx.conn, board_id)
        pick = _outbox.pickup_mail(ctx.conn, board_id)
        on = sum(1 for m in smails if m["enabled"]) + (1 if pick["enabled"] else 0)
        sblocks = []
        for m in [pick] + smails:
            sid = t.esc(m["board_status_id"])
            sblocks.append(
                f"<div class=card id='st-{sid}'><h3>{t.icon('mail')}{t.esc(m['name'])} "
                + ("<span class=pill>on</span>" if m["enabled"] else "<span class=muted style='font-weight:400;font-size:.85em'>off</span>")
                + (" <span class=muted style='font-weight:400;font-size:.85em'>when someone takes the ticket"
                   if m["shape"] == "PICKUP" else
                   f" <span class=muted style='font-weight:400;font-size:.85em'>a status that {t.esc(_outbox.STATUS_SHAPES[m['shape']])}")
                + (f" · the board's own words · {t.esc(m['updated_at'])} · {t.esc(m['updated_by'])}" if m["custom"] else " · the desk's words")
                + "</span></h3>"
                f"<form method=post action='/admin/board/{bid}/emails/status' class=stack style='max-width:none'>"
                f"<input type=hidden name=board_status_id value='{sid}'>"
                f"<label><input type=checkbox name=enabled value=1 style='width:auto'{' checked' if m['enabled'] else ''}> "
                + ("Email the requester when someone picks the ticket up (its owner is set or changes)"
                   if m["shape"] == "PICKUP" else "Email the requester when a ticket enters this status") + "</label>"
                f"<label>Subject (after the ticket's reference)<input name=subject required maxlength=120 value='{t.esc(m['subject'])}'></label>"
                f"<label>Body<textarea name=body required style='min-height:110px'>{t.esc(m['body'])}</textarea></label>"
                "<div><button type=submit>Save</button> "
                + ("<button class=ghost type=submit name=reset value=1>Back to the desk's words</button>" if m["custom"] else "")
                + "</div></form></div>")
        switch = ("<span class=pill>on</span>" if b["notify_requester"] else
                  "<b>off</b>: nothing below is sent until it is turned on, on the Board tab")
        content = ("<div class=card><h3>" + t.icon("mail") + "What this board's emails say</h3><p class=why>The reference PSA's "
                   "service email templates. Placeholders: <code>{ticket}</code> the reference, <code>{board}</code> "
                   "this board's name, <code>{requester}</code> the requester's name, <code>{owner}</code> who has it "
                   "(else the board's team), <code>{status}</code> the status's name, <code>{status_text}</code> what the "
                   "portal says about that status, <code>{link}</code> the ticket on the portal, <code>{date}</code> the "
                   "day, <code>{hospital}</code> the hospital's name, <code>{actor}</code> who did it, <code>{when}</code> a visit's time. There is no placeholder for "
                   "the summary, a note or the requester's own subject: a subject and a body leave the building, and the "
                   "words stay behind the sign-in. The reference, the portal link and how to reply are added by the "
                   "sender. A board with no words of its own uses the desk's, shown here.</p>"
                   f"<p class=sub>Emails to requesters on this board: {switch}.</p></div>"
                   "<h2 style='margin-top:18px'>An email at each status</h2>"
                   f"<div class=card><p class=why>When a ticket enters a status that is on here, or someone picks it "
                   "up, its requester gets that email, in the hospital's words below. A status that closes the ticket sends its own email instead of the closed email "
                   "below. Two changes before the sender runs send one email, the newer. A reply keeps the reference in "
                   f"the subject and joins the ticket. <b>{on}</b> of {len(smails)} on.</p>"
                   f"<form method=post action='/admin/board/{bid}/emails/status-all' class=inline>"
                   "<button type=submit name=enabled value=1>Turn every status on</button> "
                   "<button class=ghost type=submit name=enabled value=0>Turn every status off</button></form></div>"
                   + "".join(sblocks)
                   + "<h2 style='margin-top:18px'>Emails by event</h2>" + "".join(blocks))
    elif tab == "assign":
        from ... import board as _board
        from ... import setup as _setup
        mode = b["auto_assign"] or "OFF"
        modes = "".join(f"<label style='display:block;margin-top:6px'><input type=radio name=mode value={k} style='width:auto'"
                        f"{' checked' if k == mode else ''}> {t.esc(v)}</label>" for k, v in _board.AUTO_ASSIGN_MODES.items())
        working = _board._working_members(ctx.conn, board_id)
        who = "".join(f"<option value='{t.esc(m)}'>" for m in working)
        rules = _board.auto_assign_rules(ctx.conn, board_id)
        rule_rows = "".join(
            f"<tr><td>{t.esc(r['label'])}</td><td>{t.esc(r['member'])}"
            + ("" if r["member"].lower() in {w.lower() for w in working} else " <span class=pill>no longer works this board</span>")
            + f"</td><td><form method=post action='/admin/board/{bid}/assign/rule/remove' class=inline>"
            f"<input type=hidden name=catalogue_item_id value='{t.esc(r['catalogue_item_id'])}'>"
            "<button class='ghost small' type=submit>Remove</button></form></td></tr>" for r in rules)
        pairs = "".join(f"<option value='{t.esc(c['catalogue_item_id'])}'>{t.esc(c['label'])}</option>"
                        for c in _setup.catalogue_choices(ctx.conn, board_id))
        leader = ctx.conn.execute("SELECT team_leader FROM board_team WHERE board_id = ? AND is_default = 1", (board_id,)).fetchone()
        content = (
            "<div class=card><h3>" + t.icon("users") + "Who a new ticket goes to</h3><p class=why>The reference PSA's "
            "auto-assign: a ticket that arrives on the board with nobody named is given an owner. A rule for its "
            "Subtype › Item pair names the member; with no rule, the board's mode below. A ticket that arrives with an "
            "owner keeps it, and a member who leaves the board is never assigned. The owner is emailed when the board "
            "emails owners.</p>"
            f"<form method=post action='/admin/board/{bid}/assign'>{modes}"
            + (f"<p class=muted style='margin-top:6px'>The default team's leader is {t.esc(leader['team_leader'])}.</p>"
               if leader and leader["team_leader"] else
               "<p class=muted style='margin-top:6px'>No default team names a leader yet (Members &amp; roles).</p>")
            + "<div style='margin-top:10px'><button type=submit>Save</button></div></form></div>"
            "<div class=card><h3>" + t.icon("tag") + "By Subtype › Item</h3>"
            "<div class=tablewrap><table><thead><tr><th>Subtype › Item</th><th>Goes to</th><th></th></tr></thead><tbody>"
            + (rule_rows or "<tr><td colspan=3 class=muted>No rule yet: the mode above decides.</td></tr>") + "</tbody></table></div>"
            f"<form method=post action='/admin/board/{bid}/assign/rule' class=row style='margin-top:10px'>"
            f"<div style='flex:1 1 260px'><label>Subtype › Item</label><select name=catalogue_item_id>{pairs}</select></div>"
            f"<div style='flex:1 1 180px'><label>Goes to</label><input name=member list=assignwho required><datalist id=assignwho>{who}</datalist></div>"
            "<div style='flex:0 0 auto;align-self:end'><button class=ghost type=submit>Add rule</button></div></form></div>")
    else:
        statuses = ctx.conn.execute(
            "SELECT * FROM board_status WHERE board_id = ? ORDER BY inactive, sort_order, name",
            (board_id,)).fetchall()

        def cb(name, v):
            return f"<input type=checkbox name={name} value=1{' checked' if v else ''} style='width:auto'>"

        rows = []
        for st in statuses:
            sid = t.esc(st["board_status_id"])
            esc_opts = "".join(f"<option value='{k}'{' selected' if k == st['escalation_status'] else ''}>"
                               f"{t.esc(v)}</option>" for k, v in ESC_LABEL.items())
            rows.append(
                f"<tr{' style=opacity:.55' if st['inactive'] else ''}>"
                f"<td><form id='s_{sid}' method=post action='/admin/board/{bid}/status/save'>"
                f"<input type=hidden name=board_status_id value='{sid}'></form>"
                f"<input form='s_{sid}' name=sort_order value='{st['sort_order']}' style='width:60px'></td>"
                f"<td><input form='s_{sid}' name=name value='{t.esc(st['name'])}'></td>"
                f"<td><input form='s_{sid}' name=customer_description value='{t.esc(st['customer_description'] or '')}'></td>"
                f"<td><select form='s_{sid}' name=escalation_status>{esc_opts}</select></td>"
                + "".join(f"<td>{cb(n, st[c]).replace('<input', f'<input form=s_{sid}', 1)}</td>" for n, c in (
                    ("is_default", "is_default"), ("is_closed", "is_closed"),
                    ("time_entry_allowed", "time_entry_allowed"), ("display_on_board", "display_on_board"),
                    ("inactive", "inactive")))
                + f"<td><button form='s_{sid}' class=ghost type=submit style='padding:4px 10px'>Save</button></td></tr>")
        esc_opts = "".join(f"<option value='{k}'>{t.esc(v)}</option>" for k, v in ESC_LABEL.items())
        content = (
            "<div class=card><h3><svg class=ic aria-hidden=true><use href=#i-rows></use></svg>Statuses</h3><div class=tablewrap><table class=edit><thead><tr>"
            "<th>Order</th><th>Name (desk)</th><th>Requester sees</th><th>SLA milestone</th>"
            "<th>Default</th><th>Closes</th><th>Time allowed</th><th>On board</th><th>Retired</th>"
            "<th></th></tr></thead><tbody>" + ("".join(rows) or
            "<tr><td colspan=10 class=muted>No statuses yet — apply the starter setup above.</td></tr>")
            + "</tbody></table></div><p class=sub style='margin:10px 0 0'>Statuses are retired, "
            "never deleted: tickets that sat in one keep their history.</p>"
            "<h3 style='margin-top:16px'>Add a status</h3>"
            f"<form method=post action='/admin/board/{bid}/status/add' class=row>"
            "<div><label>Name</label><input name=name required></div>"
            "<div><label>Requester sees</label><input name=customer_description></div>"
            f"<div><label>SLA milestone</label><select name=escalation>{esc_opts}</select></div>"
            "<div style='flex:0 0 auto'><label>Closes</label><select name=is_closed><option value=0>no"
            "</option><option value=1>yes</option></select></div>"
            "<div style='flex:0 0 auto'><button type=submit>Add status</button></div></form></div>")

    body = ((f"<div class='banner ok'>{t.esc(msg)}</div>" if msg else "") +
            f"<h1>Setup · {t.esc(b['display_name'])}</h1><p class=sub>The board's own vocabulary, "
            "as a Dada PSA service board setup table. <a href='/admin'>All boards</a></p>"
            + ready + tabs + content)
    return Response(body=t.page("Setup", body, user=ctx.user, active="admin"))


def _done(board_id, tab, msg):
    from .. import redirect
    import urllib.parse
    return redirect(f"/admin/board/{board_id}?" + urllib.parse.urlencode({"tab": tab, "msg": msg}))


def _audit(ctx, board_id, detail):
    db.audit(ctx.conn, at=ctx.now.isoformat(sep=" ", timespec="minutes"), actor=ctx.user.id,
             action="BOARD_CONFIG", subject_kind="board", subject_id=board_id, detail=detail)


def apply_starter(ctx, board_id):
    from ... import setup
    common.require_board(ctx, board_id, need="ADMIN")
    r = setup.apply_starter(ctx.conn, board_id, actor=ctx.user.id, at=ctx.now)
    ctx.conn.commit()
    return _done(board_id, "statuses", f"Starter applied: {r['statuses']} statuses, "
                                       f"{r['targets']} SLA targets added")


def _reply_policy_form(ctx, b) -> str:
    """Dada PSA's per-board answer to a reply on a closed ticket."""
    bid = t.esc(b["board_id"])
    statuses = ctx.conn.execute(
        "SELECT board_status_id, name FROM board_status WHERE board_id = ? AND is_closed = 0"
        " AND inactive = 0 ORDER BY sort_order", (b["board_id"],)).fetchall()
    pol = b["closed_reply_policy"] or "REOPEN"
    opts = "".join(f"<option value={k}{' selected' if pol == k else ''}>{v}</option>" for k, v in (
        ("REOPEN", "Reopen the ticket"), ("NEW_TICKET", "Open a new ticket, linked to the old one")))
    st = "<option value=''>(the board's default status)</option>" + "".join(
        f"<option value='{t.esc(x['board_status_id'])}'"
        f"{' selected' if x['board_status_id'] == b['reopen_status_id'] else ''}>{t.esc(x['name'])}</option>"
        for x in statuses)
    return (
        f"<form method=post action='/admin/board/{bid}/reply-policy' class=row style='margin-top:14px'>"
        f"<div><label>When someone replies to a closed ticket</label><select name=policy>{opts}</select></div>"
        f"<div><label>Reopen to</label><select name=reopen_status_id>{st}</select></div>"
        f"<div><label>…only within days (blank: always)</label><input name=days type=number min=1 "
        f"value='{t.esc(b['reopen_within_days'] or '')}'></div>"
        f"<div style='flex:2 1 320px'><label>This board's intake addresses</label><input name=intake_address maxlength=1000 "
        f"value='{t.esc(', '.join(_intake.addresses_of(ctx.conn, b['board_id'])))}' "
        "placeholder='helpdesk@pmcne.ph, help@pmcne.ph, support@pmcne.ph'></div>"
        "<div style='flex:0 0 auto'><button type=submit>Save</button></div></form>"
        "<p class=why style='margin-top:8px'>Mail sent to any of these addresses lands on this board, whichever mailbox "
        "delivered it: alias them onto one mailbox in Exchange, or give the board mailboxes of its own. Separate them "
        "with commas. An address belongs to one board. Mail from these addresses never opens a ticket, and a reply to "
        "the requester goes out from the address they wrote to.</p>")


def save_reply_policy(ctx, board_id):
    common.require_board(ctx, board_id, need="ADMIN")
    f = ctx.request.form()
    policy = f.get("policy") if f.get("policy") in ("REOPEN", "NEW_TICKET") else None
    status = f.get("reopen_status_id") or None
    if status and ctx.conn.execute(
            "SELECT 1 FROM board_status WHERE board_status_id = ? AND board_id = ?"
            " AND is_closed = 0", (status, board_id)).fetchone() is None:
        return _done(board_id, "board", "Not saved: that status is not an open status on this board")
    days = f.get("days", "").strip()
    days = int(days) if days.isdigit() and int(days) > 0 else None
    try:
        addresses = _intake.set_addresses(ctx.conn, board_id, f.get("intake_address", ""), at=ctx.now, actor=ctx.user.id)
    except ValueError as exc:
        ctx.conn.rollback()
        return _done(board_id, "board", f"Not saved: {exc}")
    address = ", ".join(addresses) or None
    ctx.conn.execute("UPDATE board SET closed_reply_policy = ?, reopen_status_id = ?,"
                     " reopen_within_days = ? WHERE board_id = ?", (policy, status, days, board_id))
    db.audit(ctx.conn, at=ctx.now.isoformat(sep=" ", timespec="minutes"), actor=ctx.user.id,
             action="BOARD_REPLY_POLICY", subject_kind="board", subject_id=board_id,
             detail=f"{policy or 'REOPEN'} to {status or 'default'}"
                    + (f" within {days} days" if days else "") + (f"; intake {address}" if address else "; no intake address"))
    ctx.conn.commit()
    return _done(board_id, "board", "Reply policy saved")


def save_template(ctx, board_id):
    from ... import tasks
    common.require_board(ctx, board_id, need="ADMIN")
    f = ctx.request.form()
    try:
        tasks.save_template(ctx.conn, board_id=board_id, name=f.get("name", ""), actor=ctx.user.id,
                            at=ctx.now, summary=f.get("summary"), record_type=f.get("record_type") or None,
                            catalogue_item_id=f.get("catalogue_item_id") or None,
                            description=f.get("description"),
                            task_lines=f.get("tasks", "").splitlines())
    except (ValueError, LookupError) as exc:
        ctx.conn.rollback()
        return _done(board_id, "templates", f"Not saved: {exc}")
    ctx.conn.commit()
    return _done(board_id, "templates", "Template saved")


def save_standard_note(ctx, board_id):
    from ... import canned
    common.require_board(ctx, board_id, need="ADMIN")
    f = ctx.request.form()
    try:
        canned.add_note(ctx.conn, board_id=board_id, name=f.get("name", ""), body=f.get("body", ""),
                        flag=f.get("flag", ""), actor=ctx.user.id, at=ctx.now)
        ctx.conn.commit()
    except ValueError as exc:
        return _done(board_id, "notes", f"Not saved: {exc}")
    return _done(board_id, "notes", "Standard note saved")


def toggle_standard_note(ctx, board_id):
    from ... import canned
    common.require_board(ctx, board_id, need="ADMIN")
    nid = ctx.request.form().get("note_id", "")
    row = ctx.conn.execute("SELECT inactive FROM standard_note WHERE note_id = ? AND board_id = ?",
                           (nid, board_id)).fetchone() if nid.isdigit() else None
    if row is None:
        return _done(board_id, "notes", "No such standard note on this board")
    canned.set_note_inactive(ctx.conn, int(nid), not row["inactive"], actor=ctx.user.id, at=ctx.now)
    ctx.conn.commit()
    return _done(board_id, "notes", "Standard note restored" if row["inactive"] else "Standard note retired")


def toggle_template(ctx, board_id):
    common.require_board(ctx, board_id, need="ADMIN")
    tid = ctx.request.form().get("template_id", "")
    cur = ctx.conn.execute("UPDATE ticket_template SET inactive = 1 - inactive WHERE template_id = ?"
                           " AND board_id = ?", (tid, board_id))
    if cur.rowcount:
        db.audit(ctx.conn, at=ctx.now.isoformat(sep=" ", timespec="minutes"), actor=ctx.user.id,
                 action="TEMPLATE_TOGGLE", subject_kind="ticket_template", subject_id=tid)
        ctx.conn.commit()
    return _done(board_id, "templates", "Saved")


def save_types(ctx, board_id):
    from ... import db
    common.require_board(ctx, board_id, need="ADMIN")
    types = [x for x in ctx.request.form_list("types") if x in itil.RECORD_TYPES]
    default = ctx.request.form().get("default") or None
    if default not in types:
        default = None
    itil.set_board_types(ctx.conn, board_id, types, default=default)
    db.audit(ctx.conn, at=ctx.now.isoformat(sep=" ", timespec="minutes"), actor=ctx.user.id,
             action="BOARD_TYPES", subject_kind="board", subject_id=board_id,
             detail=("takes " + "/".join(types) + f"; default {default or types[0]}") if types
             else "takes every Type")
    ctx.conn.commit()
    return _done(board_id, "types", "Types saved")


def save_calendar(ctx, board_id):
    common.require_board(ctx, board_id, need="ADMIN")
    cal = ctx.request.form().get("calendar_id") or None
    if cal and ctx.conn.execute("SELECT 1 FROM calendar WHERE calendar_id = ?", (cal,)).fetchone() is None:
        return _done(board_id, "board", "No such calendar")
    ctx.conn.execute("UPDATE board SET calendar_id = ? WHERE board_id = ?", (cal, board_id))
    _audit(ctx, board_id, f"calendar -> {cal or 'none'}")
    ctx.conn.commit()
    return _done(board_id, "board", "Calendar saved")


def save_status(ctx, board_id):
    common.require_board(ctx, board_id, need="ADMIN")
    f = ctx.request.form()
    sid = f.get("board_status_id", "")
    row = ctx.conn.execute("SELECT * FROM board_status WHERE board_status_id = ? AND board_id = ?",
                           (sid, board_id)).fetchone()
    if row is None:
        return _done(board_id, "statuses", "No such status on this board")
    esc = f.get("escalation_status") if f.get("escalation_status") in ESCALATIONS else row["escalation_status"]
    flags = {k: 1 if f.get(k) == "1" else 0 for k in
             ("is_default", "is_closed", "time_entry_allowed", "display_on_board", "inactive")}
    if flags["is_default"] and (flags["is_closed"] or flags["inactive"]):
        return _done(board_id, "statuses", "Not saved: the default status cannot close or be retired")
    try:
        order = int(f.get("sort_order", row["sort_order"]))
    except ValueError:
        order = row["sort_order"]
    name = f.get("name", "").strip() or row["name"]
    try:
        if flags["is_default"]:
            ctx.conn.execute("UPDATE board_status SET is_default = 0 WHERE board_id = ?", (board_id,))
        ctx.conn.execute(
            "UPDATE board_status SET name = ?, customer_description = ?, escalation_status = ?,"
            " is_default = ?, is_closed = ?, time_entry_allowed = ?, display_on_board = ?,"
            " inactive = ?, sort_order = ? WHERE board_status_id = ?",
            (name, f.get("customer_description", "").strip() or None, esc, flags["is_default"],
             flags["is_closed"], flags["time_entry_allowed"], flags["display_on_board"],
             flags["inactive"], order, sid))
        _audit(ctx, board_id, f"status {sid} saved: {name}, {esc}, {flags}")
        ctx.conn.commit()
    except Exception as exc:                                 # noqa: BLE001
        ctx.conn.rollback()
        return _done(board_id, "statuses", f"Not saved: {exc}")
    return _done(board_id, "statuses", f"Saved {name}")


def add_board_status(ctx, board_id):
    common.require_board(ctx, board_id, need="ADMIN")
    f = ctx.request.form()
    name = f.get("name", "").strip()
    esc = f.get("escalation", "")
    if not name or esc not in ESCALATIONS:
        return _done(board_id, "statuses", "A name and a milestone are required")
    order = (ctx.conn.execute("SELECT MAX(sort_order) FROM board_status WHERE board_id = ?",
                              (board_id,)).fetchone()[0] or 0) + 10
    try:
        ctx.conn.execute(
            "INSERT INTO board_status (board_status_id, board_id, name, customer_description,"
            " escalation_status, is_closed, sort_order) VALUES (?,?,?,?,?,?,?)",
            (f"{board_id}.{_slug(name)}", board_id, name,
             f.get("customer_description", "").strip() or None, esc,
             1 if f.get("is_closed") == "1" else 0, order))
        _audit(ctx, board_id, f"status added: {name} ({esc})")
        ctx.conn.commit()
    except Exception as exc:                                 # noqa: BLE001
        ctx.conn.rollback()
        return _done(board_id, "statuses", f"Not added: {exc}")
    return _done(board_id, "statuses", f"Added {name}")


def save_sla(ctx, board_id):
    from ... import setup
    common.require_board(ctx, board_id, need="ADMIN")
    f = ctx.request.form()
    changed = 0
    for p in ("P1", "P2", "P3", "P4"):
        for c in setup.CLOCKS:
            raw = f.get(f"t_{p}_{c}", "").strip()
            if not raw:
                cur = ctx.conn.execute("DELETE FROM sla_target WHERE board_id = ? AND priority = ?"
                                       " AND clock = ?", (board_id, p, c))
                changed += cur.rowcount
                continue
            try:
                minutes = int(raw)
                if minutes <= 0:
                    raise ValueError
            except ValueError:
                ctx.conn.rollback()
                return _done(board_id, "sla", f"Not saved: {p} {c} must be a whole number of minutes")
            cur = ctx.conn.execute(
                "UPDATE sla_target SET target_minutes = ?, note = 'set on the Setup page'"
                " WHERE board_id = ? AND priority = ? AND clock = ? AND target_minutes <> ?",
                (minutes, board_id, p, c, minutes))
            changed += cur.rowcount
            cur = ctx.conn.execute(
                "INSERT OR IGNORE INTO sla_target (board_id, priority, clock, target_minutes,"
                " calendar, enforced, note) VALUES (?,?,?,?,'CLINICAL_24x7',0,'set on the Setup page')",
                (board_id, p, c, minutes))
            changed += cur.rowcount
    _audit(ctx, board_id, f"SLA targets saved ({changed} change(s))")
    ctx.conn.commit()
    return _done(board_id, "sla", f"Saved: {changed} change(s)")


def save_roles(ctx, board_id):
    common.require_board(ctx, board_id, need="ADMIN")
    f = ctx.request.form()
    for role in ROLES:
        who = f.get(role, "").strip()
        if who:
            ctx.conn.execute("INSERT OR REPLACE INTO board_role (board_id, role, member)"
                             " VALUES (?,?,?)", (board_id, role, who))
        else:
            ctx.conn.execute("DELETE FROM board_role WHERE board_id = ? AND role = ?", (board_id, role))
    _audit(ctx, board_id, "board roles saved")
    ctx.conn.commit()
    return _done(board_id, "members", "Roles saved")


def new_board_form(ctx, *, error: str = "", values: dict | None = None):
    from .. import Response
    common.require_sysadmin(ctx)
    v = values or {}
    if not v and ctx.request.query.get("kind") in itil.PROFILES:      # + New project board
        v = {"kind": ctx.request.query["kind"]}
    boards = ctx.conn.execute("SELECT board_id, display_name FROM board ORDER BY display_name").fetchall()
    copy_opts = ("<option value='starter'>The starter setup (statuses, calendar, SLA placeholders)</option>"
                 + "".join(f"<option value='{t.esc(b['board_id'])}'>Copy the setup of {t.esc(b['display_name'])}</option>"
                           for b in boards) + "<option value=''>Empty — I will set it up</option>")
    body = (
        (f"<div class='banner err'>{t.esc(error)}</div>" if error else "") +
        "<h1>New board</h1><p class=sub>A board is the bucket a group's tickets live in, with its "
        "own statuses, SLA, members and teams. You become its administrator; add the people who "
        "work it on its Members tab.</p><div class=card><form method=post action='/admin/board/new'>"
        "<div class=grid2>"
        f"<div><label>Name</label><input name=display_name required value='{t.esc(v.get('display_name', ''))}' placeholder='e.g. Biomedical & Clinical Equipment'></div>"
        f"<div><label>Board id (optional)</label><input name=board_id value='{t.esc(v.get('board_id', ''))}' placeholder='made from the name'></div>"
        f"<div><label>Fulfiller group</label><input name=fulfiller_group value='{t.esc(v.get('fulfiller_group', ''))}' placeholder='who works it'></div>"
        f"<div><label>Kind</label><select name=kind>"
        + "".join(f"<option value={k}{' selected' if v.get('kind', 'SERVICE') == k else ''}>"
                  f"{t.esc(itil.PROFILE_LABEL[k])}</option>" for k in itil.PROFILES) + "</select></div>"
        f"<div><label>Start from</label><select name=copy_from>{copy_opts}</select></div>"
        f"<div style='grid-column:1/-1'><label>Description</label><input name=description value='{t.esc(v.get('description', ''))}'></div>"
        "<div><label style='color:var(--ink);font-weight:500'><input type=checkbox name=restricted value=1 style='width:auto'> "
        "Restricted — members only, every read audited (PHI-bearing boards)</label></div>"
        "<div><label style='color:var(--ink);font-weight:500'><input type=checkbox name=closed_loop_required value=1 style='width:auto'> "
        "Closed loop required</label></div></div>"
        "<div style='margin-top:14px'><button type=submit>Create board</button> "
        "<a class='btn ghost' href='/admin'>Cancel</a></div></form></div>")
    return Response(body=t.page("New board", body, user=ctx.user, active="admin"))


def new_board_create(ctx):
    from ... import setup
    common.require_sysadmin(ctx)
    f = ctx.request.form()
    try:
        bid = setup.create_board(
            ctx.conn, display_name=f.get("display_name", ""), board_id=f.get("board_id") or None,
            fulfiller_group=f.get("fulfiller_group", ""), creator=ctx.user.id, at=ctx.now,
            restricted=f.get("restricted") == "1",
            closed_loop_required=f.get("closed_loop_required") == "1",
            description=f.get("description", "").strip() or None,
            copy_from=f.get("copy_from") if f.get("copy_from") is not None else "starter",
            profile=f.get("kind") if f.get("kind") in itil.PROFILES else "SERVICE")
        ctx.conn.commit()
    except (ValueError, LookupError) as exc:
        ctx.conn.rollback()
        return new_board_form(ctx, error=str(exc), values=f)
    return _done(bid, "members", "Board created. Add the people who work it.")


def _time_opts(ctx, table: str, selected) -> str:
    from ... import board as _board
    _board.ensure_time_vocabulary(ctx.conn)
    rows = ctx.conn.execute(f"SELECT {table}_id AS id, name FROM {table} WHERE inactive = 0 ORDER BY sort_order, name").fetchall()
    return ("<option value=''>(the first in Setup › Time)</option>" + "".join(
        f"<option value='{t.esc(r['id'])}'{' selected' if r['id'] == selected else ''}>{t.esc(r['name'])}</option>"
        for r in rows))


def save_settings(ctx, board_id):
    common.require_board(ctx, board_id, need="ADMIN")
    f = ctx.request.form()
    name = f.get("display_name", "").strip()
    if not name:
        return _done(board_id, "board", "A board needs a name")
    owner = f.get("owner", "").strip() or None
    deputy = f.get("deputy", "").strip() or None
    live = 1 if f.get("is_live") == "1" else 0
    if live and not (owner and deputy):
        return _done(board_id, "board", "Not saved: a live board needs an owner and a deputy")
    unrouted = ctx.conn.execute("SELECT is_unrouted FROM board WHERE board_id = ?",
                                (board_id,)).fetchone()[0]
    inactive = 1 if f.get("inactive") == "1" else 0
    if inactive and unrouted:
        return _done(board_id, "board", "Not saved: the unrouted queue cannot be retired")
    before = dict(ctx.conn.execute("SELECT * FROM board WHERE board_id = ?", (board_id,)).fetchone())
    try:
        from ... import board as _board
        _board.ensure_time_vocabulary(ctx.conn)
        for key, table in (("default_work_role_id", "work_role"), ("default_work_type_id", "work_type")):
            if f.get(key) and not ctx.conn.execute(f"SELECT 1 FROM {table} WHERE {table}_id = ? AND inactive = 0",
                                                   (f[key],)).fetchone():
                return _done(board_id, "board", f"Not saved: no such {table.replace('_', ' ')} in use")
        ctx.conn.execute(
            "UPDATE board SET display_name = ?, fulfiller_group = ?, owner = ?, deputy = ?,"
            " description = ?, restricted = ?, closed_loop_required = ?, is_live = ?, inactive = ?,"
            " notify_requester = ?, notify_owner = ?, default_work_role_id = ?, default_work_type_id = ?"
            " WHERE board_id = ?",
            (name, f.get("fulfiller_group", "").strip() or "Unassigned", owner, deputy,
             f.get("description", "").strip() or None, 1 if f.get("restricted") == "1" else 0,
             1 if f.get("closed_loop_required") == "1" else 0, live, inactive,
             1 if f.get("notify_requester") == "1" else 0, 1 if f.get("notify_owner") == "1" else 0,
             f.get("default_work_role_id") or None, f.get("default_work_type_id") or None, board_id))
        ctx.conn.execute("UPDATE board SET survey_enabled = ?, survey_question = ? WHERE board_id = ?",
                         (1 if f.get("survey_enabled") == "1" else 0,
                          " ".join(f.get("survey_question", "").split())[:120] or None, board_id))
        if "chat_welcome" in f:                                  # 072: the chat's "please wait" words
            ctx.conn.execute("UPDATE board SET chat_welcome = ? WHERE board_id = ?",
                             (" ".join(f.get("chat_welcome", "").split())[:300] or None, board_id))
        # 073: a tick, read like the survey's: absent from the post is unticked
        ctx.conn.execute("UPDATE board SET takes_chats = ? WHERE board_id = ?",
                         (1 if f.get("takes_chats") == "1" else 0, board_id))
        _audit(ctx, board_id, "settings saved: " + _changes(before, dict(ctx.conn.execute(
            "SELECT * FROM board WHERE board_id = ?", (board_id,)).fetchone())))
        ctx.conn.commit()
    except Exception as exc:                                 # noqa: BLE001
        ctx.conn.rollback()
        return _done(board_id, "board", f"Not saved: {exc}")
    return _done(board_id, "board", "Board saved")


SETTING_WORDS = {"display_name": "name", "fulfiller_group": "group", "owner": "owner", "deputy": "deputy",
                 "description": "description", "restricted": "restricted", "closed_loop_required": "closed loop",
                 "is_live": "live", "inactive": "retired", "notify_requester": "email the requester",
                 "notify_owner": "email the owner", "default_work_role_id": "work role",
                 "default_work_type_id": "work type", "survey_enabled": "survey", "survey_question": "survey question"}


def _changes(before: dict, after: dict) -> str:
    """The audit's words for a settings save: each changed field as old -> new,
    so the row answers "who renamed the board" (SQL01, part 15); "nothing
    changed" when the Save changed nothing."""
    out = []
    flags = {"restricted", "closed_loop_required", "is_live", "inactive", "notify_requester", "notify_owner"}
    for key, word in SETTING_WORDS.items():
        a, b = before.get(key), after.get(key)
        if key in flags:                       # an unset flag reads as its default, off (SQL01, part 16)
            a, b = a or 0, b or 0
        if a != b:
            show = (lambda v: "-" if v is None else repr(v) if isinstance(v, str) else str(v))
            out.append(f"{word} {show(a)} -> {show(b)}")
    return "; ".join(out) or "nothing changed"


def add_team(ctx, board_id):
    common.require_board(ctx, board_id, need="ADMIN")
    f = ctx.request.form()
    name = f.get("name", "").strip()
    if not name:
        return _done(board_id, "members", "A team needs a name")
    team_id = f"{board_id}.{_slug(name)}"
    try:
        if f.get("is_default") == "1":
            ctx.conn.execute("UPDATE board_team SET is_default = 0 WHERE board_id = ?", (board_id,))
        ctx.conn.execute("INSERT INTO board_team (team_id, board_id, name, team_leader, is_default)"
                         " VALUES (?,?,?,?,?)", (team_id, board_id, name,
                                                 f.get("team_leader", "").strip() or None,
                                                 1 if f.get("is_default") == "1" else 0))
        _audit(ctx, board_id, f"team added: {name}")
        ctx.conn.commit()
    except Exception as exc:                                 # noqa: BLE001
        ctx.conn.rollback()
        return _done(board_id, "members", f"Not added: {exc}")
    return _done(board_id, "members", f"Team {name} added")


# ---------------------------------------------------- Setup › Catalogue
#
# The reference PSA's setup tables for Types, Subtypes and Items, on the desk's
# own tree (psaspine/catalogue.py): the Type stays the board's ITIL kind; Areas,
# Subtypes and Items are added, renamed and retired here; a Subtype › Item pair
# is associated with the board it lands on. Server-rendered forms, no script.

CATALOGUE_TABS = (("pairs", "Subtype › Item pairs"), ("types", "Types"), ("areas", "Areas"),
                  ("subtypes", "Subtypes"), ("items", "Items"))


def _cat_back(tab: str, **q):
    from .. import redirect
    q = {k: v for k, v in q.items() if v}
    q["tab"] = tab
    return redirect("/admin/catalogue?" + urllib.parse.urlencode(q))


def _cat_options(pairs, selected="") -> str:
    return "".join(f"<option value='{t.esc(k)}'{' selected' if k == selected else ''}>{t.esc(v)}</option>"
                   for k, v in pairs)


def _retire_button(action: str, key: str, value: str, inactive: int) -> str:
    return (f"<form method=post action='{action}' class=inline>"
            f"<input type=hidden name={key} value='{t.esc(value)}'>"
            f"<input type=hidden name=act value='{'restore' if inactive else 'retire'}'>"
            f"<button class=ghost type=submit style='padding:3px 10px'>{'Restore' if inactive else 'Retire'}"
            "</button></form>")


def catalogue(ctx):
    from .. import Response
    from ... import catalogue as cat
    common.require_sysadmin(ctx)
    msg, err = ctx.request.query.get("msg", ""), ctx.request.query.get("err", "")
    tab = ctx.request.query.get("tab", "pairs")
    if tab not in dict(CATALOGUE_TABS):
        tab = "pairs"
    tabs = "<div class=stabs>" + "".join(
        f"<a class='{'on' if tab == k else ''}' href='/admin/catalogue?tab={k}'>{v}</a>"
        for k, v in CATALOGUE_TABS) + "</div>"
    dim = " style=opacity:.55"
    if tab == "pairs":
        rows = ctx.conn.execute(
            "SELECT i.catalogue_item_id, f.display_name AS type, c.display_name AS subtype,"
            "       a.display_name AS item, a.kind, b.display_name AS board, i.default_contract_basis,"
            "       i.min_priority, i.clinical_impact, i.is_draft, i.record_type, i.needs_approval"
            "  FROM catalogue_item i JOIN service_component c ON c.component_id = i.component_id"
            "  JOIN service_family f ON f.family_id = c.family_id"
            "  JOIN service_action a ON a.action_id = i.action_id"
            "  JOIN board b ON b.board_id = i.default_board_id"
            " ORDER BY f.display_name, c.display_name, a.display_name").fetchall()
        trs = "".join(
            f"<tr{dim if r['is_draft'] else ''}><td>{t.esc(r['type'])}</td>"
            f"<td>{t.esc(r['subtype'])}</td><td>{t.esc(r['item'])}</td>"
            f"<td>{t.esc(itil.LABEL.get(r['record_type']) or ('Incident' if r['kind'] == 'FAULT' else 'Request'))}</td>"
            f"<td>{t.esc(r['board'])}</td><td>{t.esc(r['default_contract_basis'])}</td>"
            f"<td>{t.esc(r['min_priority'] or '')}{' · clinical' if r['clinical_impact'] else ''}</td>"
            f"<td><form method=post action='/admin/catalogue/approval' class=inline>"
            f"<input type=hidden name=catalogue_item_id value='{t.esc(r['catalogue_item_id'])}'>"
            f"<input type=hidden name=needs_approval value={0 if r['needs_approval'] else 1}>"
            f"<button class=ghost type=submit style='padding:3px 10px' title='Whether a ticket with this pair asks the department approver first'>"
            f"{'Approval: yes' if r['needs_approval'] else 'Approval: no'}</button></form></td>"
            f"<td><form method=post action='/admin/catalogue/toggle' class=inline>"
            f"<input type=hidden name=catalogue_item_id value='{t.esc(r['catalogue_item_id'])}'>"
            f"<button class=ghost type=submit style='padding:3px 10px'>{'Use' if r['is_draft'] else 'Retire'}"
            "</button></form></td></tr>" for r in rows)
        subs = [(c["component_id"], f"{c['area']} › {c['display_name']}") for c in cat.subtypes(ctx.conn)
                if not c["inactive"]]
        its = [(a["action_id"], f"{a['display_name']} ({'fault' if a['kind'] == 'FAULT' else 'request'})")
               for a in cat.items(ctx.conn) if not a["inactive"]]
        boards = [(b["board_id"], b["display_name"]) for b in ctx.conn.execute(
            "SELECT board_id, display_name FROM board WHERE COALESCE(inactive, 0) = 0 ORDER BY display_name")]
        scope = [("", "(none)")] + [(str(r["scope_item_id"]), f"{r['scope_item_id']} {r['heading']}")
                                    for r in ctx.conn.execute(
                                        "SELECT scope_item_id, heading FROM scope_item ORDER BY scope_item_id")]
        content = (
            "<div class=card><form method=post action='/admin/catalogue/template' class=inline>"
            "<button type=submit>Load the Dada PSA template</button></form> "
            f"<span class=why>{len(rows)} pair(s). Only a pair is offered on a ticket; retire a pair to "
            "withdraw it and keep every ticket that carries it.</span></div>"
            "<div class=card><div class=tablewrap><table><thead><tr><th>Area</th><th>Subtype</th>"
            "<th>Item</th><th>Default Type</th><th>Board</th><th>Basis</th><th>Floor</th><th>Approval</th><th></th></tr></thead>"
            f"<tbody>{trs or '<tr><td colspan=9 class=muted>Empty. Load the template, or add areas, subtypes and items on the tabs, then pair them here.</td></tr>'}"
            "</tbody></table></div></div>"
            "<div class=card><h3>" + t.icon("plus") + "Associate a subtype with an item</h3>"
            "<form method=post action='/admin/catalogue/associate' class=row>"
            f"<div><label>Subtype</label><select name=component_id required>{_cat_options(subs)}</select></div>"
            f"<div><label>Item</label><select name=action_id required>{_cat_options(its)}</select></div>"
            f"<div><label>Lands on</label><select name=default_board_id required>{_cat_options(boards)}</select></div>"
            "<div><label>Contract basis</label><select name=basis>"
            + _cat_options([("UNKNOWN", "Unknown"), ("BASELINE", "Baseline"), ("VARIATION", "Variation")]) + "</select></div>"
            f"<div><label>Baseline item</label><select name=scope_item_id>{_cat_options(scope)}</select></div>"
            "<div><label>Priority floor</label><select name=min_priority>"
            + _cat_options([("", "(none)"), ("P1", "P1"), ("P2", "P2"), ("P3", "P3"), ("P4", "P4")]) + "</select></div>"
            "<div style='flex:0 0 auto'><label><input type=checkbox name=clinical_impact value=1> Clinical impact</label></div>"
            "<div style='flex:0 0 auto'><label><input type=checkbox name=needs_approval value=1> Needs approval</label></div>"
            "<div style='flex:0 0 auto'><button type=submit class=ghost>Associate</button></div></form></div>")
    elif tab == "types":
        takes: dict[str, list] = {}
        for b in ctx.conn.execute("SELECT board_id, display_name FROM board WHERE COALESCE(inactive, 0) = 0"
                                  " ORDER BY display_name"):
            # no rows means the board takes every Type (itil.accepts)
            kinds = [r["record_type"] for r in itil.boards_types(ctx.conn, b["board_id"])] or list(itil.RECORD_TYPES)
            for k in kinds:
                takes.setdefault(k, []).append((b["board_id"], b["display_name"]))
        trs = "".join(
            f"<tr><td><b>{t.esc(itil.LABEL[k])}</b></td>"
            f"<td>{'Proactive' if k in itil.PROACTIVE else 'Reactive'}</td>"
            f"<td>{', '.join(f'<a href=/admin/board/{t.esc(bid)}?tab=types>{t.esc(name)}</a>' for bid, name in takes.get(k, [])) or '<span class=muted>no board yet</span>'}</td></tr>"
            for k in itil.RECORD_TYPES)
        content = (
            "<div class=card><p class=sub>The Type is the board's ITIL kind. A service board takes Incident, "
            "Request, Problem and Event; a change board takes Change; a project board takes Project. Which of "
            "them a board offers, and its default, is set on that board's <b>Types</b> tab. The six are a fixed "
            "set because the change approval gate and the SLA-by-type targets key on them.</p>"
            "<div class=tablewrap><table><thead><tr><th>Type</th><th>Category</th><th>Boards that take it</th>"
            f"</tr></thead><tbody>{trs}</tbody></table></div></div>")
    elif tab == "areas":
        trs = "".join(
            f"<tr{dim if r['inactive'] else ''}><td><form method=post action='/admin/catalogue/area/save' class=row style='margin:0'>"
            f"<input type=hidden name=family_id value='{t.esc(r['family_id'])}'>"
            f"<div><input name=name value='{t.esc(r['display_name'])}' maxlength=80 required aria-label='Area name'></div>"
            "<div style='flex:0 0 auto'><button type=submit class=ghost style='padding:3px 10px' name=act value=rename>Rename</button></div>"
            f"</form></td><td class=muted>{t.esc(r['family_id'])}</td><td class=center>{r['subtypes']}</td>"
            f"<td>{_retire_button('/admin/catalogue/area/save', 'family_id', r['family_id'], r['inactive'])}</td></tr>"
            for r in cat.areas(ctx.conn))
        content = (
            "<div class=card><p class=sub>An area groups subtypes in the picker (Networking, Servers and storage, "
            "Clinical applications). Retiring an area hides its subtypes from every new ticket and changes no "
            "existing one.</p><div class=tablewrap><table><thead><tr><th>Area</th><th>Id</th><th>Subtypes</th><th></th>"
            f"</tr></thead><tbody>{trs or '<tr><td colspan=4 class=muted>No areas yet.</td></tr>'}</tbody></table></div></div>"
            "<div class=card><h3>" + t.icon("plus") + "Add an area</h3><form method=post action='/admin/catalogue/area' class=row>"
            "<div><input name=name required maxlength=80 placeholder='Clinical applications'></div>"
            "<div><input name=note maxlength=200 placeholder='note (optional)'></div>"
            "<div style='flex:0 0 auto'><button type=submit class=ghost>Add</button></div></form></div>")
    elif tab == "subtypes":
        area_opts = [(a["family_id"], a["display_name"]) for a in cat.areas(ctx.conn) if not a["inactive"]]
        trs = "".join(
            f"<tr{dim if r['inactive'] else ''}><td><form method=post action='/admin/catalogue/subtype/save' class=row style='margin:0'>"
            f"<input type=hidden name=component_id value='{t.esc(r['component_id'])}'>"
            f"<div><input name=name value='{t.esc(r['display_name'])}' maxlength=80 required aria-label='Subtype name'></div>"
            f"<div><select name=family_id aria-label='Area'>{_cat_options(area_opts + ([(r['family_id'], r['area'])] if r['family_id'] not in dict(area_opts) else []), r['family_id'])}</select></div>"
            "<div style='flex:0 0 auto'><button type=submit class=ghost style='padding:3px 10px' name=act value=rename>Save</button></div>"
            f"</form></td><td class=muted>{t.esc(r['component_id'])}</td><td class=center>{r['pairs']}</td>"
            f"<td>{_retire_button('/admin/catalogue/subtype/save', 'component_id', r['component_id'], r['inactive'])}</td></tr>"
            for r in cat.subtypes(ctx.conn))
        content = (
            "<div class=card><p class=sub>A subtype is the thing a ticket is about: Printer, Hyper-V host, "
            "Voicemail. It belongs to one area and is offered on a ticket only through its pairs. Retiring one "
            "withdraws its pairs from new tickets.</p><div class=tablewrap><table><thead><tr><th>Subtype · Area</th>"
            f"<th>Id</th><th>Pairs</th><th></th></tr></thead><tbody>{trs or '<tr><td colspan=4 class=muted>No subtypes yet.</td></tr>'}</tbody></table></div></div>"
            "<div class=card><h3>" + t.icon("plus") + "Add a subtype</h3><form method=post action='/admin/catalogue/subtype' class=row>"
            f"<div><label>Area</label><select name=family_id required>{_cat_options(area_opts)}</select></div>"
            "<div><label>Name</label><input name=name required maxlength=80 placeholder='Label printer'></div>"
            "<div style='flex:0 0 auto'><button type=submit class=ghost>Add</button></div></form></div>")
    else:
        kinds = [("REQUEST", "Request"), ("FAULT", "Fault")]
        impacts = [("", "(none)"), ("I1", "I1 — shared or clinical service down"), ("I2", "I2"), ("I3", "I3 — one device or one user")]
        trs = "".join(
            f"<tr{dim if r['inactive'] else ''}><td><form method=post action='/admin/catalogue/item/save' class=row style='margin:0'>"
            f"<input type=hidden name=action_id value='{t.esc(r['action_id'])}'>"
            f"<div><input name=name value='{t.esc(r['display_name'])}' maxlength=80 required aria-label='Item name'></div>"
            f"<div><select name=kind aria-label='Kind'>{_cat_options(kinds, r['kind'])}</select></div>"
            f"<div><select name=implies_impact aria-label='Implied impact'>{_cat_options(impacts, r['implies_impact'] or '')}</select></div>"
            "<div style='flex:0 0 auto'><button type=submit class=ghost style='padding:3px 10px' name=act value=rename>Save</button></div>"
            f"</form></td><td class=muted>{t.esc(r['action_id'])}</td><td class=center>{r['pairs']}</td>"
            f"<td>{_retire_button('/admin/catalogue/item/save', 'action_id', r['action_id'], r['inactive'])}</td></tr>"
            for r in cat.items(ctx.conn))
        content = (
            "<div class=card><p class=sub>An item is the verb: Install, Modify, Outage, Failure. Its kind decides "
            "whether a fresh ticket is a request or a fault, and an implied impact sets the impact a ticket starts "
            "with (outage = a shared or clinical service is down, I1; failure = one device or one user, I3).</p>"
            "<div class=tablewrap><table><thead><tr><th>Item · kind · impact</th><th>Id</th><th>Pairs</th><th></th>"
            f"</tr></thead><tbody>{trs or '<tr><td colspan=4 class=muted>No items yet.</td></tr>'}</tbody></table></div></div>"
            "<div class=card><h3>" + t.icon("plus") + "Add an item</h3><form method=post action='/admin/catalogue/item' class=row>"
            "<div><label>Name</label><input name=name required maxlength=80 placeholder='Relocate'></div>"
            f"<div><label>Kind</label><select name=kind>{_cat_options(kinds)}</select></div>"
            f"<div><label>Implied impact</label><select name=implies_impact>{_cat_options(impacts)}</select></div>"
            "<div style='flex:0 0 auto'><button type=submit class=ghost>Add</button></div></form></div>")
    body = ((f"<div class='banner ok'>{t.esc(msg)}</div>" if msg else "")
            + (f"<div class='banner err'>{t.esc(err)}</div>" if err else "")
            + "<h1>Catalogue</h1><p class=sub>Dada PSA's setup tables for how a ticket is classified: "
              "Type › Subtype › Item. The Type is the board's (its Types tab); Areas, Subtypes and Items are one "
              "tree across boards (build scope §2.4), edited here; a Subtype › Item pair is what a ticket offers. "
              "Nothing is deleted: retire it and it leaves the pickers, and every ticket keeps what it had. "
              "<a href='/admin'>Setup</a></p>" + tabs + content)
    return Response(body=t.page("Catalogue", body, user=ctx.user, active="admin"))


def catalogue_template(ctx):
    from .. import redirect
    from ... import setup
    import urllib.parse
    common.require_sysadmin(ctx)
    r = setup.apply_template(ctx.conn, actor=ctx.user.id, at=ctx.now)
    ctx.conn.commit()
    waiting = sum(r["waiting"].values())
    msg = (f"Template applied: {r['items']} item(s) loaded, {r['targets']} SLA target(s)"
           + (f", boards created: {', '.join(r['created'])}" if r["created"] else "")
           + (f"; {waiting} item(s) wait for boards not yet created "
              f"({', '.join(sorted(r['waiting']))})" if waiting else ""))
    return redirect("/admin/catalogue?" + urllib.parse.urlencode({"msg": msg}))


def catalogue_toggle(ctx):
    from .. import redirect
    common.require_sysadmin(ctx)
    cid = ctx.request.form().get("catalogue_item_id", "")
    ctx.conn.execute("UPDATE catalogue_item SET is_draft = 1 - is_draft WHERE catalogue_item_id = ?",
                     (cid,))
    db.audit(ctx.conn, at=ctx.now.isoformat(sep=" ", timespec="minutes"), actor=ctx.user.id,
             action="CATALOGUE_CONFIG", subject_kind="catalogue_item", subject_id=cid,
             detail="retired/used toggled")
    ctx.conn.commit()
    return redirect("/admin/catalogue")


def _cat_flag(form) -> bool | None:
    act = form.get("act", "")
    return True if act == "retire" else False if act == "restore" else None


def catalogue_area_add(ctx):
    from ... import catalogue as cat
    common.require_sysadmin(ctx)
    f = ctx.request.form()
    try:
        cat.add_area(ctx.conn, f.get("name", ""), note=f.get("note"), at=ctx.now, actor=ctx.user.id)
    except cat.Refused as exc:
        ctx.conn.rollback()
        return _cat_back("areas", err=str(exc))
    ctx.conn.commit()
    return _cat_back("areas", msg=f"Added {' '.join(f.get('name', '').split())}")


def catalogue_area_save(ctx):
    from ... import catalogue as cat
    common.require_sysadmin(ctx)
    f = ctx.request.form()
    flag = _cat_flag(f)
    try:
        what = cat.save_area(ctx.conn, f.get("family_id", ""), name=f.get("name") if flag is None else None,
                             inactive=flag, at=ctx.now, actor=ctx.user.id)
    except cat.Refused as exc:
        ctx.conn.rollback()
        return _cat_back("areas", err=str(exc))
    ctx.conn.commit()
    return _cat_back("areas", msg=f"Area: {what}")


def catalogue_subtype_add(ctx):
    from ... import catalogue as cat
    common.require_sysadmin(ctx)
    f = ctx.request.form()
    try:
        cat.add_subtype(ctx.conn, f.get("family_id", ""), f.get("name", ""), at=ctx.now, actor=ctx.user.id)
    except cat.Refused as exc:
        ctx.conn.rollback()
        return _cat_back("subtypes", err=str(exc))
    ctx.conn.commit()
    return _cat_back("subtypes", msg=f"Added {' '.join(f.get('name', '').split())}")


def catalogue_subtype_save(ctx):
    from ... import catalogue as cat
    common.require_sysadmin(ctx)
    f = ctx.request.form()
    flag = _cat_flag(f)
    try:
        what = cat.save_subtype(ctx.conn, f.get("component_id", ""),
                                name=f.get("name") if flag is None else None,
                                family_id=f.get("family_id") if flag is None else None,
                                inactive=flag, at=ctx.now, actor=ctx.user.id)
    except cat.Refused as exc:
        ctx.conn.rollback()
        return _cat_back("subtypes", err=str(exc))
    ctx.conn.commit()
    return _cat_back("subtypes", msg=f"Subtype: {what}")


def catalogue_item_add(ctx):
    from ... import catalogue as cat
    common.require_sysadmin(ctx)
    f = ctx.request.form()
    try:
        cat.add_item(ctx.conn, f.get("name", ""), kind=f.get("kind", ""), implies_impact=f.get("implies_impact") or None,
                     at=ctx.now, actor=ctx.user.id)
    except cat.Refused as exc:
        ctx.conn.rollback()
        return _cat_back("items", err=str(exc))
    ctx.conn.commit()
    return _cat_back("items", msg=f"Added {' '.join(f.get('name', '').split())}")


def catalogue_item_save(ctx):
    from ... import catalogue as cat
    common.require_sysadmin(ctx)
    f = ctx.request.form()
    flag = _cat_flag(f)
    try:
        what = cat.save_item(ctx.conn, f.get("action_id", ""),
                             name=f.get("name") if flag is None else None,
                             kind=f.get("kind") if flag is None else None,
                             implies_impact=(f.get("implies_impact") or "") if flag is None else None,
                             inactive=flag, at=ctx.now, actor=ctx.user.id)
    except cat.Refused as exc:
        ctx.conn.rollback()
        return _cat_back("items", err=str(exc))
    ctx.conn.commit()
    return _cat_back("items", msg=f"Item: {what}")


def catalogue_associate(ctx):
    from ... import catalogue as cat
    common.require_sysadmin(ctx)
    f = ctx.request.form()
    try:
        cat.associate(ctx.conn, f.get("component_id", ""), f.get("action_id", ""), f.get("default_board_id", ""),
                      basis=f.get("basis", "UNKNOWN"), scope_item_id=f.get("scope_item_id") or None,
                      min_priority=f.get("min_priority") or None, clinical_impact=f.get("clinical_impact") == "1",
                      needs_approval=f.get("needs_approval") == "1", at=ctx.now, actor=ctx.user.id)
    except cat.Refused as exc:
        ctx.conn.rollback()
        return _cat_back("pairs", err=str(exc))
    ctx.conn.commit()
    return _cat_back("pairs", msg="Pair added; it is offered on tickets now.")


def catalogue_approval(ctx):
    from ... import catalogue as cat
    common.require_sysadmin(ctx)
    f = ctx.request.form()
    try:
        changed = cat.set_needs_approval(ctx.conn, f.get("catalogue_item_id", ""), f.get("needs_approval") == "1",
                                         at=ctx.now, actor=ctx.user.id)
    except cat.Refused as exc:
        ctx.conn.rollback()
        return _cat_back("pairs", err=str(exc))
    ctx.conn.commit()
    return _cat_back("pairs", msg=("Tickets with this pair now ask the department approver first." if f.get("needs_approval") == "1"
                                   else "This pair no longer asks for an approval.") if changed else "Nothing changed.")


# ------------------------------------------------------ Setup › Calendars
#
# The reference PSA's Calendar and Holiday List setup tables (psaspine/calendars.py):
# a calendar is a name, seven day windows and a holiday list; a holiday list is
# dated rows, each a whole day or the hours it closes. Server-rendered, no script.

def _cal_back(tab: str, **q):
    from .. import redirect
    q = {k: v for k, v in q.items() if v}
    q["tab"] = tab
    return redirect("/admin/calendars?" + urllib.parse.urlencode(q))


def _day_inputs(prefix: str, row: dict | None) -> str:
    from ... import clocks
    cells = []
    for day in clocks.DAYS:
        s = t.esc((row or {}).get(f"{day}_start") or "")
        e = t.esc((row or {}).get(f"{day}_end") or "")
        cells.append(f"<span class=day><span class=daylbl>{day[:3].title()}</span>"
                     f"<input name={prefix}{day}_start value='{s}' placeholder='closed' size=5 maxlength=5"
                     f" aria-label='{day.title()} start'> – "
                     f"<input name={prefix}{day}_end value='{e}' placeholder='' size=5 maxlength=5"
                     f" aria-label='{day.title()} end'></span>")
    return "".join(cells)


def calendars(ctx):
    from .. import Response
    from ... import calendars as cal
    common.require_sysadmin(ctx)
    msg, err = ctx.request.query.get("msg", ""), ctx.request.query.get("err", "")
    tab = ctx.request.query.get("tab", "calendars")
    if tab not in ("calendars", "holidays"):
        tab = "calendars"
    tabs = ("<div class=stabs>" + "".join(
        f"<a class='{'on' if tab == k else ''}' href='/admin/calendars?tab={k}'>{v}</a>"
        for k, v in (("calendars", "Calendars"), ("holidays", "Holiday lists"))) + "</div>")
    lists = cal.holiday_lists(ctx.conn)
    list_opts = "<option value=''>(no holidays)</option>" + "".join(
        f"<option value='{t.esc(x['holiday_list_id'])}'>{t.esc(x['name'])}</option>" for x in lists)
    if tab == "calendars":
        rows = []
        for c in cal.calendars(ctx.conn):
            sel = "<option value=''>(no holidays)</option>" + "".join(
                f"<option value='{t.esc(x['holiday_list_id'])}'{' selected' if x['holiday_list_id'] == c['holiday_list_id'] else ''}>"
                f"{t.esc(x['name'])}</option>" for x in lists)
            rows.append(
                f"<div class=card{' style=opacity:.6' if c['retired'] else ''}><form method=post action='/admin/calendars/save'>"
                f"<input type=hidden name=calendar_id value='{t.esc(c['calendar_id'])}'>"
                "<div class=row><div><label>Name</label>"
                f"<input name=name value='{t.esc(c['name'])}' maxlength=60 required></div>"
                f"<div><label>Holiday list</label><select name=holiday_list_id>{sel}</select></div>"
                f"<div style='flex:0 0 auto;align-self:end'><span class=muted>{t.esc(c['calendar_id'])} · on {c['boards']} board(s)"
                f"{' · retired' if c['retired'] else ''}</span></div></div>"
                f"<div class=weekrow>{_day_inputs('', c)}</div>"
                "<div class='row schedbar' style='margin-top:8px'><div style='flex:0 0 auto'><button type=submit name=act value=save>Save</button></div>"
                f"<div style='flex:0 0 auto'><button type=submit class=ghost name=act value={'restore' if c['retired'] else 'retire'}>"
                f"{'Restore' if c['retired'] else 'Retire'}</button></div></div></form></div>")
        content = (
            "<div class=card><p class=sub>A calendar is the working week an SLA clock counts: a start and an end "
            "for each day, blank for closed, <code>24:00</code> for midnight at the end of the day. Its holiday "
            "list stops the clock on those dates. A board picks its calendar on Setup › Board. Retiring a "
            "calendar keeps it on the boards that have it and stops offering it to new ones.</p></div>"
            + "".join(rows) +
            "<div class=card><h3>" + t.icon("plus") + "Add a calendar</h3><form method=post action='/admin/calendars'>"
            "<div class=row><div><label>Name</label><input name=name required maxlength=60 placeholder='Pharmacy counter hours'></div>"
            f"<div><label>Holiday list</label><select name=holiday_list_id>{list_opts}</select></div></div>"
            f"<div class=weekrow>{_day_inputs('', {f'{d}_start': '08:00' for d in ('monday','tuesday','wednesday','thursday','friday')} | {f'{d}_end': '17:00' for d in ('monday','tuesday','wednesday','thursday','friday')})}</div>"
            "<div style='margin-top:8px'><button type=submit class=ghost>Add</button></div></form></div>")
    else:
        cards = []
        for x in lists:
            days = cal.holidays(ctx.conn, x["holiday_list_id"])
            trs = "".join(
                f"<tr><td>{t.esc(h['observed_on'])}</td><td>{t.esc(h['name'])}</td>"
                f"<td>{'all day' if h['all_day'] else t.esc('closed ' + str(h['time_start']) + '–' + str(h['time_end']))}</td>"
                f"<td><form method=post action='/admin/calendars/holiday/remove' class=inline>"
                f"<input type=hidden name=holiday_list_id value='{t.esc(x['holiday_list_id'])}'>"
                f"<input type=hidden name=observed_on value='{t.esc(h['observed_on'])}'>"
                "<button class=ghost type=submit style='padding:3px 10px'>Remove</button></form></td></tr>" for h in days)
            cards.append(
                f"<div class=card><form method=post action='/admin/calendars/holiday-list/save' class=row>"
                f"<input type=hidden name=holiday_list_id value='{t.esc(x['holiday_list_id'])}'>"
                f"<div><label>List</label><input name=name value='{t.esc(x['name'])}' maxlength=60 required></div>"
                "<div style='flex:0 0 auto;align-self:end'><button type=submit class=ghost>Rename</button></div>"
                f"<div style='flex:0 0 auto;align-self:end'><span class=muted>{t.esc(x['holiday_list_id'])} · on {x['calendars']} calendar(s)</span></div></form>"
                "<div class=tablewrap><table class=compact><thead><tr><th>Date</th><th>Holiday</th><th>Closes</th><th></th></tr></thead>"
                f"<tbody>{trs or '<tr><td colspan=4 class=muted>No dates yet.</td></tr>'}</tbody></table></div>"
                f"<form method=post action='/admin/calendars/holiday' class=row style='margin-top:8px'>"
                f"<input type=hidden name=holiday_list_id value='{t.esc(x['holiday_list_id'])}'>"
                "<div><label>Date</label><input name=observed_on type=date required></div>"
                "<div><label>Holiday</label><input name=name required maxlength=50 placeholder='Bonifacio Day'></div>"
                "<div style='flex:0 0 auto;align-self:end'><label><input type=checkbox name=all_day value=1 checked> All day</label></div>"
                "<div><label>Or closed from</label><input name=time_start placeholder='12:00' size=5 maxlength=5></div>"
                "<div><label>until</label><input name=time_end placeholder='24:00' size=5 maxlength=5></div>"
                "<div style='flex:0 0 auto;align-self:end'><button type=submit class=ghost>Add</button></div></form></div>")
        content = (
            "<div class=card><p class=sub>A holiday list is the dates a calendar does not count: a whole day, or "
            "the hours it closes (untick All day and give the hours). PMC's own list from HR is the source; "
            "nothing is compiled in. Load a year at once with "
            "<code>psaspine import-holidays &lt;db&gt; &lt;list id&gt; holidays.csv</code> (columns Date, Name, "
            "optional AllDay, Start, End); a date already on the list is left alone. Removing a date is audited, "
            "and every clock on that list recomputes.</p></div>"
            + "".join(cards) +
            "<div class=card><h3>" + t.icon("plus") + "Add a holiday list</h3><form method=post action='/admin/calendars/holiday-list' class=row>"
            "<div><input name=name required maxlength=60 placeholder='Philippine public holidays'></div>"
            "<div style='flex:0 0 auto'><button type=submit class=ghost>Add</button></div></form></div>")
    body = ((f"<div class='banner ok'>{t.esc(msg)}</div>" if msg else "")
            + (f"<div class='banner err'>{t.esc(err)}</div>" if err else "")
            + "<h1>Calendars</h1><p class=sub>The working weeks the SLA clocks run on, and the holidays that stop "
              "them: the reference PSA's Calendar and Holiday List setup tables. <a href='/admin'>Setup</a></p>"
            + tabs + content)
    return Response(body=t.page("Calendars", body, user=ctx.user, active="admin"))


def _cal_try(ctx, tab, fn, ok):
    from ... import calendars as cal
    try:
        result = fn()
    except cal.Refused as exc:
        ctx.conn.rollback()
        return _cal_back(tab, err=str(exc))
    ctx.conn.commit()
    return _cal_back(tab, msg=ok(result))


def calendars_add(ctx):
    from ... import calendars as cal
    common.require_sysadmin(ctx)
    f = ctx.request.form()
    return _cal_try(ctx, "calendars", lambda: cal.add_calendar(
        ctx.conn, f.get("name", ""), cal.clean_week(f), holiday_list_id=f.get("holiday_list_id") or None,
        at=ctx.now, actor=ctx.user.id), lambda cid: f"Added {' '.join(f.get('name', '').split())} ({cid})")


def calendars_save(ctx):
    from ... import calendars as cal
    common.require_sysadmin(ctx)
    f = ctx.request.form()
    act = f.get("act", "save")
    if act in ("retire", "restore"):
        return _cal_try(ctx, "calendars", lambda: cal.save_calendar(
            ctx.conn, f.get("calendar_id", ""), inactive=(act == "retire"), at=ctx.now, actor=ctx.user.id),
            lambda what: f"Calendar: {what}")
    return _cal_try(ctx, "calendars", lambda: cal.save_calendar(
        ctx.conn, f.get("calendar_id", ""), name=f.get("name"), week=cal.clean_week(f),
        holiday_list_id=f.get("holiday_list_id") or None, set_list=True, at=ctx.now, actor=ctx.user.id),
        lambda what: f"Calendar: {what}")


def holiday_list_add(ctx):
    from ... import calendars as cal
    common.require_sysadmin(ctx)
    f = ctx.request.form()
    return _cal_try(ctx, "holidays", lambda: cal.add_holiday_list(ctx.conn, f.get("name", ""), at=ctx.now, actor=ctx.user.id),
                    lambda lid: f"Added the list ({lid}); now add its dates")


def holiday_list_save(ctx):
    from ... import calendars as cal
    common.require_sysadmin(ctx)
    f = ctx.request.form()
    return _cal_try(ctx, "holidays", lambda: cal.rename_holiday_list(
        ctx.conn, f.get("holiday_list_id", ""), f.get("name", ""), at=ctx.now, actor=ctx.user.id),
        lambda what: f"Holiday list: {what}")


def holiday_add(ctx):
    from ... import calendars as cal
    common.require_sysadmin(ctx)
    f = ctx.request.form()
    return _cal_try(ctx, "holidays", lambda: cal.add_holiday(
        ctx.conn, f.get("holiday_list_id", ""), f.get("observed_on", ""), f.get("name", ""),
        all_day=f.get("all_day") == "1", time_start=f.get("time_start"), time_end=f.get("time_end"),
        at=ctx.now, actor=ctx.user.id), lambda day: f"Added {day}")


def holiday_remove(ctx):
    from ... import calendars as cal
    common.require_sysadmin(ctx)
    f = ctx.request.form()
    return _cal_try(ctx, "holidays", lambda: cal.remove_holiday(
        ctx.conn, f.get("holiday_list_id", ""), f.get("observed_on", ""), at=ctx.now, actor=ctx.user.id),
        lambda day: f"Removed {day}; the clocks on this list recompute")


# ------------------------------------------------------ Setup › Schedule
#
# The reference PSA's Schedule Status and Service Location setup tables.

def schedule_setup(ctx):
    from .. import Response
    from ... import schedule
    common.require_sysadmin(ctx)
    msg, err = ctx.request.query.get("msg", ""), ctx.request.query.get("err", "")
    sts = schedule.statuses(ctx.conn, all_rows=True)
    locs = schedule.locations(ctx.conn, all_rows=True)
    ctx.conn.commit()

    def row(kind, key, r, extra=""):
        k = t.esc(key)
        return (f"<tr{' style=opacity:.55' if r['inactive'] else ''}><td><form method=post action='/admin/schedule/save' class=row style='margin:0'>"
                f"<input type=hidden name=kind value={kind}><input type=hidden name=key value='{k}'>"
                f"<div><input name=name value='{t.esc(r['name'])}' maxlength=50 required aria-label='Name'></div>"
                "<div style='flex:0 0 auto'><button class=ghost type=submit name=act value=rename style='padding:3px 10px'>Rename</button></div>"
                f"</form></td><td class=muted>{k}</td><td>{extra}</td><td>"
                f"<form method=post action='/admin/schedule/save' class=inline><input type=hidden name=kind value={kind}>"
                f"<input type=hidden name=key value='{k}'><button class=ghost type=submit name=act "
                f"value={'restore' if r['inactive'] else 'retire'} style='padding:3px 10px'>{'Restore' if r['inactive'] else 'Retire'}</button></form></td></tr>")

    def default_btn(r):
        if r["is_default"]:
            return "<span class='pill live'>default</span>"
        if r["inactive"]:
            return ""
        return (f"<form method=post action='/admin/schedule/save' class=inline><input type=hidden name=kind value=status>"
                f"<input type=hidden name=key value='{t.esc(r['status_id'])}'>"
                "<button class=ghost type=submit name=act value=default style='padding:3px 10px'>Make default</button></form>")

    body = ((f"<div class='banner ok'>{t.esc(msg)}</div>" if msg else "")
            + (f"<div class='banner err'>{t.esc(err)}</div>" if err else "")
            + "<h1>Schedule</h1><p class=sub>The reference PSA's Schedule Status and Service Location setup "
              "tables: what a visit's status and its where can be. A retired one stays on the visits that have "
              "it. <a href='/admin'>Setup</a> · <a href='/schedule'>The schedule</a></p><div class=grid2>"
              "<div class=card><h3>" + t.icon("tag") + "Statuses</h3><p class=sub>A new visit takes the default. "
              "One called Tentative shows dashed on the schedule.</p><div class=tablewrap><table class=compact><tbody>"
            + "".join(row("status", r["status_id"], r, default_btn(r)) for r in sts)
            + "</tbody></table></div><form method=post action='/admin/schedule/add' class=row style='margin-top:10px'>"
              "<input type=hidden name=kind value=status><div><input name=name required maxlength=50 placeholder='e.g. Waiting on parts'></div>"
              "<div style='flex:0 0 auto'><button class=ghost type=submit>" + t.icon("plus") + " Add status</button></div></form></div>"
              "<div class=card><h3>" + t.icon("building") + "Where</h3><p class=sub>Where the work is done: on the ward, "
              "remotely, or brought to IT.</p><div class=tablewrap><table class=compact><tbody>"
            + "".join(row("location", r["location_id"], r) for r in locs)
            + "</tbody></table></div><form method=post action='/admin/schedule/add' class=row style='margin-top:10px'>"
              "<input type=hidden name=kind value=location><div><input name=name required maxlength=50 placeholder='e.g. Supplier workshop'></div>"
              "<div style='flex:0 0 auto'><button class=ghost type=submit>" + t.icon("plus") + " Add where</button></div></form></div></div>")
    return Response(body=t.page("Schedule setup", body, user=ctx.user, active="admin"))


def _sched_back(**q):
    from .. import redirect
    return redirect("/admin/schedule?" + urllib.parse.urlencode({k: v for k, v in q.items() if v}))


def schedule_setup_add(ctx):
    from ... import schedule
    common.require_sysadmin(ctx)
    f = ctx.request.form()
    try:
        fn = schedule.add_status if f.get("kind") == "status" else schedule.add_location
        fn(ctx.conn, f.get("name", ""), at=ctx.now, actor=ctx.user.id)
    except schedule.Refused as exc:
        ctx.conn.rollback()
        return _sched_back(err=f"Not added: {exc}")
    ctx.conn.commit()
    return _sched_back(msg=f"Added {' '.join(f.get('name', '').split())}")


def schedule_setup_save(ctx):
    from ... import schedule
    common.require_sysadmin(ctx)
    f = ctx.request.form()
    kind = "status" if f.get("kind") == "status" else "location"
    act = f.get("act", "rename")
    try:
        what = schedule.save_vocab(ctx.conn, kind, f.get("key", ""),
                                   name=f.get("name") if act == "rename" else None,
                                   inactive=True if act == "retire" else False if act == "restore" else None,
                                   make_default=act == "default", at=ctx.now, actor=ctx.user.id)
    except schedule.Refused as exc:
        ctx.conn.rollback()
        return _sched_back(err=f"Not saved: {exc}")
    ctx.conn.commit()
    return _sched_back(msg=f"{kind.title()}: {what}")


# ------------------------------------------------------ Setup › Roles
#
# The reference PSA's Security Roles setup table (psaspine/security.py): a grid
# of module by level per role, and which member has which role.

def roles_setup(ctx):
    from .. import Response
    from ... import security
    common.require_sysadmin(ctx)
    q = ctx.request.query
    roles = security.roles(ctx.conn)
    ctx.conn.commit()
    head = "".join(f"<th>{t.esc(v)}</th>" for v in security.MODULES.values())
    words = {"NONE": "None", "READ": "Read", "WRITE": "Add and edit", "ADMIN": "All"}
    rows = []
    for r in roles:
        rid = t.esc(r["role_id"])
        cells = "".join(
            f"<td><select form='f-{rid}' name='{m}' aria-label='{t.esc(security.MODULES[m])} for {t.esc(r['name'])}'>"
            + "".join(f"<option value={lv}{' selected' if r['grants'][m] == lv else ''}>{words[lv]}</option>" for lv in security.LEVELS)
            + "</select></td>" for m in security.MODULES)
        flags = ("<span class='pill live'>default</span>" if r["is_default"] else "") + (" <span class=pill>retired</span>" if r["inactive"] else "")
        acts = []
        if not r["is_default"] and not r["inactive"]:
            acts.append(f"<button form='f-{rid}' class='ghost small' type=submit formaction='/admin/roles/{rid}/default'>Make default</button>")
        if not r["is_default"]:
            acts.append(f"<button form='f-{rid}' class='ghost small' type=submit formaction='/admin/roles/{rid}/{'restore' if r['inactive'] else 'retire'}'>"
                        f"{'Restore' if r['inactive'] else 'Retire'}</button>")
        rows.append(f"<tr{' style=opacity:.6' if r['inactive'] else ''}><td><form id='f-{rid}' method=post action='/admin/roles/{rid}/save'></form>"
                    f"<b>{t.esc(r['name'])}</b> {flags}<div class=muted>{len(r['members'])} member(s)</div></td>"
                    + cells + f"<td><button class=ghost type=submit form='f-{rid}'>Save</button> " + " ".join(acts) + "</td></tr>")
    members = sorted({m["member"] for m in ctx.conn.execute("SELECT DISTINCT member FROM board_member")}, key=str.lower)
    assigned = {r[0].lower(): r[1] for r in ctx.conn.execute("SELECT member, role_id FROM member_role")}
    names = {r["role_id"]: r["name"] for r in roles}
    live = [r for r in roles if not r["inactive"]]
    member_rows = "".join(
        f"<tr><td>{t.esc(m)}</td><td>{t.esc(names.get(assigned.get(m.lower()), 'the default role'))}</td>"
        f"<td><form method=post action='/admin/roles/assign' class=row style='margin:0'><input type=hidden name=member value='{t.esc(m)}'>"
        "<div><select name=role_id aria-label='Role'><option value=''>The default role</option>"
        + "".join(f"<option value='{t.esc(r['role_id'])}'{' selected' if assigned.get(m.lower()) == r['role_id'] else ''}>{t.esc(r['name'])}</option>" for r in live)
        + "</select></div><div style='flex:0 0 auto'><button class='ghost small' type=submit>Set</button></div></form></td></tr>" for m in members)
    body = ((f"<div class='banner ok'>{t.esc(q.get('msg', ''))}</div>" if q.get("msg") else "")
            + (f"<div class='banner err'>{t.esc(q.get('err', ''))}</div>" if q.get("err") else "")
            + "<h1>Security roles</h1><p class=sub>What each role may do in the modules that are not boards. A board's "
              "tickets are still governed by board membership, and a role never opens a restricted board. A member with "
              "no role has the default role; a system administrator has everything. <a href='/admin'>Setup</a></p>"
            + f"<div class=card><div class=tablewrap><table><thead><tr><th>Role</th>{head}<th></th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>"
              "<form method=post action='/admin/roles/add' class=row style='margin-top:10px'>"
              "<div><input name=name required maxlength=60 placeholder='e.g. Biomedical engineer'></div>"
              "<div style='flex:0 0 200px'><select name=copy_from aria-label='Start from'><option value=''>Start from nothing</option>"
              + "".join(f"<option value='{t.esc(r['role_id'])}'>Copy {t.esc(r['name'])}</option>" for r in live)
              + "</select></div><div style='flex:0 0 auto'><button class=ghost type=submit>" + t.icon("plus") + " Add role</button></div></form></div>"
            + "<div class=card><h3>" + t.icon("users") + "Members</h3><div class=tablewrap><table><thead><tr><th>Member</th><th>Role</th>"
              f"<th></th></tr></thead><tbody>{member_rows or '<tr><td colspan=3 class=muted>No board members yet.</td></tr>'}</tbody></table></div></div>")
    return Response(body=t.page("Security roles", body, user=ctx.user, active="admin"))


def _roles_back(**q):
    from .. import redirect
    return redirect("/admin/roles?" + urllib.parse.urlencode({k: v for k, v in q.items() if v}))


def _roles_try(ctx, fn, ok):
    from ... import security
    common.require_sysadmin(ctx)
    try:
        r = fn()
        ctx.conn.commit()
    except security.Refused as exc:
        ctx.conn.rollback()
        return _roles_back(err=str(exc))
    return _roles_back(msg=ok(r))


def roles_add(ctx):
    from ... import security
    f = ctx.request.form()
    return _roles_try(ctx, lambda: security.add_role(ctx.conn, f.get("name", ""), copy_from=f.get("copy_from") or None,
                                                     at=ctx.now, actor=ctx.user.id), lambda rid: f"Added {rid}")


def roles_save(ctx, role_id):
    from ... import security
    f = ctx.request.form()
    return _roles_try(ctx, lambda: security.save_grants(ctx.conn, role_id, {m: f.get(m) for m in security.MODULES},
                                                        at=ctx.now, actor=ctx.user.id), lambda w: f"{role_id}: {w}")


def roles_default(ctx, role_id):
    from ... import security
    return _roles_try(ctx, lambda: security.set_default(ctx.conn, role_id, at=ctx.now, actor=ctx.user.id),
                      lambda _: f"{role_id} is the default role")


def roles_retire(ctx, role_id):
    from ... import security
    return _roles_try(ctx, lambda: security.set_inactive(ctx.conn, role_id, True, at=ctx.now, actor=ctx.user.id),
                      lambda _: f"{role_id} retired")


def roles_restore(ctx, role_id):
    from ... import security
    return _roles_try(ctx, lambda: security.set_inactive(ctx.conn, role_id, False, at=ctx.now, actor=ctx.user.id),
                      lambda _: f"{role_id} restored")


def roles_assign(ctx):
    from ... import security
    f = ctx.request.form()
    return _roles_try(ctx, lambda: security.assign(ctx.conn, f.get("member", ""), f.get("role_id") or None,
                                                   at=ctx.now, actor=ctx.user.id), lambda w: w)


def _local_accounts_card(ctx) -> str:
    rows = ctx.conn.execute(
        "SELECT username, is_sysadmin, disabled, last_login_at FROM local_account"
        " ORDER BY username").fetchall()
    trs = []
    for r in rows:
        disable = ""
        if not r["disabled"]:
            disable = ("<form method='post' action='/admin/local/disable' "
                       "style='display:inline'>"
                       f"<input type='hidden' name='username' value='{t.esc(r['username'])}'>"
                       "<button class='ghost' type='submit'>Disable</button></form>")
        trs.append(
            f"<tr><td>{t.esc(r['username'])}</td>"
            f"<td>{'sysadmin' if r['is_sysadmin'] else ''}</td>"
            f"<td>{'disabled' if r['disabled'] else 'active'}</td>"
            f"<td class='muted'>{t.esc(r['last_login_at'] or 'never')}</td>"
            f"<td>{disable}</td></tr>")
    body = "".join(trs) or "<tr><td colspan=5 class='muted'>No break-glass accounts.</td></tr>"
    return ("<div class='card'><h3><svg class=ic aria-hidden=true><use href=#i-shield></use></svg>Break-glass accounts</h3>"
            "<p class='sub'>Created only by <code>psaspine create-local-account</code>. "
            "Disable here; the web never creates one.</p>"
            "<div class='tablewrap'><table><thead><tr><th>Username</th><th>Role</th>"
            f"<th>State</th><th>Last login</th><th></th></tr></thead><tbody>{body}"
            "</tbody></table></div></div>")


def _config_overview_card(ctx) -> str:
    counts = {}
    for label, table in (("Clinical floors", "clinical_floor"), ("SLA targets", "sla_target")):
        counts[label] = ctx.conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"]
    rows = "".join(f"<dt>{t.esc(k)}</dt><dd>{v}</dd>" for k, v in counts.items())
    return ("<div class='card'><h3><svg class=ic aria-hidden=true><use href=#i-monitor></use></svg>Cross-board configuration</h3>"
            "<p class='sub'>Clinical floors are signed off by the hospital, not edited here; SLA targets are "
            "set on each board's SLA tab. The counts are here so the fence is visible.</p>"
            f"<dl class='kv'>{rows}</dl></div>")


def add_status(ctx):
    from .. import redirect
    f = ctx.request.form()
    board_id = f.get("board_id", "")
    common.require_board(ctx, board_id, need="ADMIN")
    name = f.get("name", "").strip()
    escalation = f.get("escalation", "")
    is_closed = 1 if f.get("is_closed") == "1" else 0
    if name and escalation in ESCALATIONS:
        status_id = f"{board_id}.{_slug(name)}"
        try:
            ctx.conn.execute(
                "INSERT INTO board_status (board_status_id, board_id, name,"
                " escalation_status, is_closed) VALUES (?,?,?,?,?)",
                (status_id, board_id, name, escalation, is_closed))
            ctx.conn.commit()
        except Exception:
            ctx.conn.rollback()
    return redirect("/admin")


def add_member(ctx):
    from .. import redirect
    f = ctx.request.form()
    board_id = f.get("board_id", "")
    common.require_board(ctx, board_id, need="ADMIN")
    member = f.get("member", "").strip()
    access = f.get("access", "READ")
    team_id = f.get("team_id") or None
    if team_id and ctx.conn.execute("SELECT 1 FROM board_team WHERE team_id = ? AND board_id = ?",
                                    (team_id, board_id)).fetchone() is None:
        team_id = None
    if member and access in ("READ", "WORK", "ADMIN"):
        try:
            ctx.conn.execute(
                "INSERT OR REPLACE INTO board_member (board_id, member, team_id, access)"
                " VALUES (?,?,?,?)", (board_id, member, team_id, access))
            _audit(ctx, board_id, f"member {member} -> {access}")
            ctx.conn.commit()
        except Exception:
            ctx.conn.rollback()
    if f.get("back") == "members":
        return _done(board_id, "members", f"{member} saved")
    return redirect("/admin")


def claim_board(ctx, board_id: str):
    """POST /admin/board/<id>/claim: a sysadmin names the first administrator
    of a board that has no members. Refused for any board that has one."""
    from .. import redirect, HttpError
    from ... import setup
    common.require_sysadmin(ctx)
    member = ctx.request.form().get("member", "").strip()
    try:
        given = setup.first_admin(ctx.conn, board_id, member, actor=ctx.user.id, at=ctx.now)
    except LookupError:
        raise HttpError("404 Not Found", "No such board.")
    except ValueError as exc:
        ctx.conn.rollback()
        return redirect("/admin?msg=" + urllib.parse.quote(str(exc)))
    if not given:
        ctx.conn.rollback()
        return redirect("/admin?msg=" + urllib.parse.quote(f"{board_id} already has members"))
    ctx.conn.commit()
    return redirect("/admin?msg=" + urllib.parse.quote(f"{member} is the first administrator of {board_id}"))


def disable_local(ctx):
    from .. import redirect
    common.require_sysadmin(ctx)
    username = ctx.request.form().get("username", "").strip()
    if username:
        ctx.conn.execute("UPDATE local_account SET disabled = 1 WHERE username = ?",
                         (username,))
        db.audit(ctx.conn, at=ctx.now.isoformat(sep=" ", timespec="minutes"),
                 actor=ctx.user.id, action="LOCAL_ACCOUNT_DISABLE",
                 subject_kind="local_account", subject_id=username,
                 detail="disabled via admin surface")
        ctx.conn.commit()
    return redirect("/admin")


# ------------------------------------------------------------ Setup › Time
#
# Dada PSA's Work Roles and Work Types (System › Setup Tables). A role is a
# name; a type is a name and the bill default it carries (WorkType.billTime).
# Neither is deleted: a role that was used stays, switched off, so old time
# entries still say what they were.

_TIME_ID = re.compile(r"[^A-Z0-9]+")


def _time_id(name: str) -> str:
    return _TIME_ID.sub("_", name.strip().upper()).strip("_")[:32]


def time_setup(ctx):
    from .. import Response
    from ... import board as _board
    common.require_sysadmin(ctx)
    _board.ensure_time_vocabulary(ctx.conn)
    ctx.conn.commit()
    msg, err = ctx.request.query.get("msg", ""), ctx.request.query.get("err", "")
    roles = _board.work_roles(ctx.conn, all_rows=True)
    types = _board.work_types(ctx.conn, all_rows=True)
    bill_words = {"BILLABLE": "Billable", "DO_NOT_BILL": "Do not bill", "NO_CHARGE": "No charge"}

    def toggle(kind, key, off):
        return (f"<form method=post action='/admin/time/toggle' class=inline>"
                f"<input type=hidden name=kind value='{kind}'><input type=hidden name=id value='{t.esc(key)}'>"
                f"<button class=ghost type=submit style='padding:3px 10px'>{'Use again' if off else 'Retire'}</button></form>")
    role_rows = "".join(
        f"<tr{' style=opacity:.55' if r['inactive'] else ''}><td>{t.esc(r['name'])}</td>"
        f"<td class=muted>{t.esc(r['work_role_id'])}</td><td>{toggle('role', r['work_role_id'], r['inactive'])}</td></tr>"
        for r in roles)
    type_rows = "".join(
        f"<tr{' style=opacity:.55' if w['inactive'] else ''}><td>{t.esc(w['name'])}</td>"
        f"<td>{t.esc(bill_words.get(w['bill_time'], w['bill_time']))}</td>"
        f"<td class=muted>{t.esc(w['work_type_id'])}</td><td>{toggle('type', w['work_type_id'], w['inactive'])}</td></tr>"
        for w in types)
    body = (
        (f"<div class='banner ok'>{t.esc(msg)}</div>" if msg else "")
        + (f"<div class='banner err'>{t.esc(err)}</div>" if err else "")
        + "<h1>Time</h1><p class=sub>What a time entry is written against, as Dada PSA's setup tables "
          "have it: a <b>work role</b> (who did the work, as a role) and a <b>work type</b> (what kind of "
          "work, with the bill default it carries). A retired one stays on old entries. <a href='/admin'>Setup</a></p>"
          "<div class=grid2>"
          "<div class=card><h3>" + t.icon("users") + "Work roles</h3><div class=tablewrap><table><thead><tr><th>Name</th>"
          f"<th>Id</th><th></th></tr></thead><tbody>{role_rows}</tbody></table></div>"
          "<form method=post action='/admin/time/role' class=row style='margin-top:10px'>"
          "<div><input name=name required maxlength=50 placeholder='e.g. Biomedical engineer'></div>"
          "<div style='flex:0 0 auto'><button type=submit class=ghost>" + t.icon("plus") + " Add role</button></div></form></div>"
          "<div class=card><h3>" + t.icon("tag") + "Work types</h3><div class=tablewrap><table><thead><tr><th>Name</th>"
          f"<th>Bill</th><th>Id</th><th></th></tr></thead><tbody>{type_rows}</tbody></table></div>"
          "<form method=post action='/admin/time/type' class=row style='margin-top:10px'>"
          "<div><input name=name required maxlength=50 placeholder='e.g. Project'></div>"
          "<div style='flex:0 0 auto'><select name=bill_time>"
          + "".join(f"<option value='{k}'>{v}</option>" for k, v in bill_words.items()) +
          "</select></div><div style='flex:0 0 auto'><button type=submit class=ghost>" + t.icon("plus")
          + " Add type</button></div></form></div></div>")
    return Response(body=t.page("Time", body, user=ctx.user, active="admin"))


def _time_back(**q):
    from .. import redirect
    return redirect("/admin/time?" + urllib.parse.urlencode({k: v for k, v in q.items() if v}))


def time_role_add(ctx):
    common.require_sysadmin(ctx)
    name = ctx.request.form().get("name", "").strip()[:50]
    key = _time_id(name)
    if not name or not key:
        return _time_back(err="A work role needs a name.")
    if ctx.conn.execute("SELECT 1 FROM work_role WHERE work_role_id = ?", (key,)).fetchone():
        return _time_back(err=f"There is already a work role {name!r}.")
    n = ctx.conn.execute("SELECT COUNT(*) FROM work_role").fetchone()[0]
    ctx.conn.execute("INSERT INTO work_role (work_role_id, name, sort_order) VALUES (?,?,?)", (key, name, n))
    db.audit(ctx.conn, at=ctx.now.isoformat(sep=" ", timespec="minutes"), actor=ctx.user.id,
             action="WORK_ROLE_ADD", subject_kind="work_role", subject_id=key, detail=name)
    ctx.conn.commit()
    return _time_back(msg=f"Added work role {name}.")


def time_type_add(ctx):
    common.require_sysadmin(ctx)
    f = ctx.request.form()
    name = f.get("name", "").strip()[:50]
    bill = f.get("bill_time", "BILLABLE")
    key = _time_id(name)
    if not name or not key:
        return _time_back(err="A work type needs a name.")
    if bill not in ("BILLABLE", "DO_NOT_BILL", "NO_CHARGE"):
        return _time_back(err="The bill default is Billable, Do not bill or No charge.")
    if ctx.conn.execute("SELECT 1 FROM work_type WHERE work_type_id = ?", (key,)).fetchone():
        return _time_back(err=f"There is already a work type {name!r}.")
    n = ctx.conn.execute("SELECT COUNT(*) FROM work_type").fetchone()[0]
    ctx.conn.execute("INSERT INTO work_type (work_type_id, name, bill_time, sort_order) VALUES (?,?,?,?)",
                     (key, name, bill, n))
    db.audit(ctx.conn, at=ctx.now.isoformat(sep=" ", timespec="minutes"), actor=ctx.user.id,
             action="WORK_TYPE_ADD", subject_kind="work_type", subject_id=key, detail=f"{name} ({bill})")
    ctx.conn.commit()
    return _time_back(msg=f"Added work type {name}.")


def time_toggle(ctx):
    common.require_sysadmin(ctx)
    f = ctx.request.form()
    kind, key = f.get("kind", ""), f.get("id", "")
    table = {"role": "work_role", "type": "work_type"}.get(kind)
    if table is None:
        return _time_back(err="Nothing to change.")
    row = ctx.conn.execute(f"SELECT inactive FROM {table} WHERE {table}_id = ?", (key,)).fetchone()
    if row is None:
        return _time_back(err="No such entry.")
    ctx.conn.execute(f"UPDATE {table} SET inactive = ? WHERE {table}_id = ?", (0 if row["inactive"] else 1, key))
    db.audit(ctx.conn, at=ctx.now.isoformat(sep=" ", timespec="minutes"), actor=ctx.user.id,
             action=f"{table.upper()}_{'RESTORE' if row['inactive'] else 'RETIRE'}", subject_kind=table,
             subject_id=key)
    ctx.conn.commit()
    return _time_back(msg=("Back in use." if row["inactive"] else "Retired; old entries keep it."))


# ------------------------------------------------------ Setup › Departments
#
# Dada's checklist (28 Sep 2026): rows are departments, columns are the live
# service boards, each cell a tick. A tick lets that department's staff SEND
# requests to that board; it never makes them members. One Save for the grid,
# audited as one line per department that changed.

def departments(ctx):
    from .. import Response
    from ... import departments as dept
    common.require_sysadmin(ctx)
    msg, err = ctx.request.query.get("msg", ""), ctx.request.query.get("err", "")
    q = ctx.request.query.get("q", "").strip().lower()
    rows = dept.all_departments(ctx.conn)
    boards = dept.live_boards(ctx.conn)
    have = dept.ticks(ctx.conn)
    shown = [r for r in rows if not q or q in r["name"].lower()]
    fallback = ""
    if not dept.any_configured(ctx.conn) and ctx.config.employee_portal_department_set:
        fallback = ("<div class='banner ok'>No box is ticked yet, so the Employee Portal door is still going by "
                    "the setting PSA_EMPLOYEE_PORTAL_DEPARTMENTS (" + t.esc(", ".join(sorted(
                        ctx.config.employee_portal_department_set))) + "). The first Save here takes over.</div>")
    head = "".join(
        f"<th class=colhead><label title='All departments'><input type=checkbox data-col='{t.esc(b['board_id'])}'"
        f" aria-label='All departments on {t.esc(b['display_name'])}'> {t.esc(b['display_name'])}</label></th>"
        for b in boards)
    trs = []
    for r in shown:
        on = have.get(r["name"], set())
        cells = "".join(
            f"<td class=center><input type=checkbox name='tick' value='{t.esc(r['name'])}|{t.esc(b['board_id'])}'"
            f"{' checked' if b['board_id'] in on else ''} aria-label='{t.esc(r['name'])} to {t.esc(b['display_name'])}'></td>"
            for b in boards)
        trs.append(
            f"<tr data-dept='{t.esc(r['name'].lower())}'{' style=opacity:.55' if r['retired'] else ''}>"
            f"<td><label><input type=checkbox data-row='{t.esc(r['name'])}' aria-label='All boards for {t.esc(r['name'])}'>"
            f" <b>{t.esc(r['name'])}</b></label>"
            + (" <span class=chip>retired</span>" if r["retired"] else "")
            + (" <span class=muted>by hand</span>" if r["source"] == "MANUAL" else "") + "</td>"
            f"<td class=center>{'<span class=chip>open</span>' if on & {b['board_id'] for b in boards} else '<span class=muted>closed</span>'}</td>"
            f"<td><input name='approver|{t.esc(r['name'])}' value='{t.esc(r['approver'] or '')}' placeholder='email' "
            f"aria-label='Approver for {t.esc(r['name'])}' style='min-width:180px'></td>"
            + cells + "</tr>")
    # every known department is submitted, shown or not, so a filtered Save
    # never unticks what is off screen
    hidden = "".join(
        f"<input type=hidden name=tick value='{t.esc(r['name'])}|{t.esc(b)}'>"
        for r in rows if r not in shown for b in have.get(r["name"], set()))
    hidden += "".join(f"<input type=hidden name='approver|{t.esc(r['name'])}' value='{t.esc(r['approver'] or '')}'>"
                      for r in rows if r not in shown)
    body = (
        (f"<div class='banner ok'>{t.esc(msg)}</div>" if msg else "")
        + (f"<div class='banner err'>{t.esc(err)}</div>" if err else "") + fallback
        + "<h1>Departments</h1><p class=sub>Tick which departments may <b>send requests to</b> which boards. "
          "A tick opens My requests on the Employee Portal for that department and offers the board on the "
          "portal's form; it never makes anyone a board member. Unticked, a department's requests land on "
          "Unrouted. Names are exact, as payroll spells them. <a href='/admin'>Setup</a></p>"
          "<div class=card><form method=get class=row><div><input name=q value='" + t.esc(q) + "' placeholder='filter departments'></div>"
          "<div style='flex:0 0 auto'><button type=submit class=ghost>Filter</button></div></form>"
          f"<p class=why>{len(rows)} department(s); {len(boards)} live board(s). Import the list from payroll with "
          "<code>psaspine import-departments &lt;db&gt; departments.csv</code> (one column, Department); a re-run adds and "
          "retires, never deletes.</p></div>"
          "<div class=card><form method=post action='/admin/departments/save' id=deptgrid>" + hidden
        + "<div class=tablewrap><table class=grid><thead><tr><th>Department</th><th>My requests</th><th>Approver</th>" + head
        + "</tr></thead><tbody>" + "".join(trs) + "</tbody></table></div>"
          "<div style='margin-top:12px'><button type=submit>Save the grid</button></div></form></div>"
          "<div class=card><h3>" + t.icon("plus") + "Add a department</h3><form method=post action='/admin/departments/add' class=row>"
          "<div><input name=name required maxlength=100 placeholder='exactly as payroll will spell it'></div>"
          "<div style='flex:0 0 auto'><button type=submit class=ghost>Add</button></div></form></div>")
    return Response(body=t.page("Departments", body, user=ctx.user, active="admin"))


def _dept_back(**q):
    from .. import redirect
    return redirect("/admin/departments?" + urllib.parse.urlencode({k: v for k, v in q.items() if v}))


def departments_save(ctx):
    from ... import departments as dept
    common.require_sysadmin(ctx)
    wanted: dict[str, set[str]] = {}
    for value in ctx.request.form_list("tick"):
        name, _, board_id = value.partition("|")
        if name and board_id:
            wanted.setdefault(name, set()).add(board_id)
    lines = dept.save_grid(ctx.conn, wanted, at=ctx.now, actor=ctx.user.id)
    for key, value in ctx.request.form().items():
        if key.startswith("approver|"):
            try:
                if dept.set_approver(ctx.conn, key[len("approver|"):], value, at=ctx.now, actor=ctx.user.id):
                    lines.append(f"{key[len('approver|'):]}: approver {value.strip().lower() or 'cleared'}")
            except ValueError as exc:
                ctx.conn.rollback()
                return _dept_back(err=str(exc))
    ctx.conn.commit()
    return _dept_back(msg=("Saved: " + "; ".join(lines)) if lines else "Nothing changed.")


def departments_add(ctx):
    from ... import departments as dept
    common.require_sysadmin(ctx)
    try:
        name = dept.add(ctx.conn, ctx.request.form().get("name", ""), at=ctx.now, actor=ctx.user.id)
    except ValueError as exc:
        return _dept_back(err=str(exc))
    ctx.conn.commit()
    return _dept_back(msg=f"Added {name}. Tick its boards and save.")


# 057: the board's emails and its auto-assign.

def save_emails(ctx, board_id):
    from ... import outbox as _outbox
    common.require_board(ctx, board_id, need="ADMIN")
    f = ctx.request.form()
    kind = f.get("kind", "")
    try:
        if f.get("reset") == "1":
            _outbox.reset_template(ctx.conn, board_id, kind, at=ctx.now, actor=ctx.user.id)
            msg = "Back to the desk's words"
        else:
            _outbox.set_template(ctx.conn, board_id, kind, subject=f.get("subject", ""), body=f.get("body", ""),
                                 at=ctx.now, actor=ctx.user.id)
            msg = "Saved: the board's own words from the next email"
        ctx.conn.commit()
    except ValueError as exc:
        ctx.conn.rollback()
        return _done(board_id, "emails", f"Not saved: {exc}")
    return _done(board_id, "emails", msg)


def save_status_email(ctx, board_id):
    from ... import outbox as _outbox
    common.require_board(ctx, board_id, need="ADMIN")
    f = ctx.request.form()
    sid = f.get("board_status_id", "")
    if sid == _outbox.PICKED_UP:
        def put(**kw):
            return _outbox.set_pickup_mail(ctx.conn, board_id, **kw)
    elif ctx.conn.execute("SELECT 1 FROM board_status WHERE board_status_id = ? AND board_id = ?", (sid, board_id)).fetchone():
        def put(**kw):
            return _outbox.set_status_mail(ctx.conn, sid, **kw)
    else:
        return _done(board_id, "emails", "Not saved: that status is not on this board")
    try:
        if f.get("reset") == "1":
            m = put(enabled=f.get("enabled") == "1", desk_words=True, at=ctx.now, actor=ctx.user.id)
        else:
            m = put(enabled=f.get("enabled") == "1", subject=f.get("subject", ""), body=f.get("body", ""),
                    at=ctx.now, actor=ctx.user.id)
        ctx.conn.commit()
    except ValueError as exc:
        ctx.conn.rollback()
        return _done(board_id, "emails", f"Not saved: {exc}")
    return _done(board_id, "emails", f"{m['name']}: email {'on' if m['enabled'] else 'off'}"
                 + (", the board's own words" if m["custom"] else ", the desk's words"))


def save_all_status_emails(ctx, board_id):
    from ... import outbox as _outbox
    common.require_board(ctx, board_id, need="ADMIN")
    enabled = ctx.request.form().get("enabled") == "1"
    n = _outbox.set_all_status_mails(ctx.conn, board_id, enabled=enabled, at=ctx.now, actor=ctx.user.id)
    ctx.conn.commit()
    return _done(board_id, "emails", f"{n} status email(s) turned {'on' if enabled else 'off'}")


def save_auto_assign(ctx, board_id):
    from ... import board as _board
    common.require_board(ctx, board_id, need="ADMIN")
    try:
        _board.set_auto_assign(ctx.conn, board_id, ctx.request.form().get("mode", ""), at=ctx.now, actor=ctx.user.id)
        ctx.conn.commit()
    except ValueError as exc:
        ctx.conn.rollback()
        return _done(board_id, "assign", f"Not saved: {exc}")
    return _done(board_id, "assign", "Saved")


def save_auto_assign_rule(ctx, board_id):
    from ... import board as _board
    common.require_board(ctx, board_id, need="ADMIN")
    f = ctx.request.form()
    try:
        _board.set_auto_assign_rule(ctx.conn, board_id, f.get("catalogue_item_id", ""), f.get("member", ""),
                                    at=ctx.now, actor=ctx.user.id)
        ctx.conn.commit()
    except ValueError as exc:
        ctx.conn.rollback()
        return _done(board_id, "assign", f"Not saved: {exc}")
    return _done(board_id, "assign", "Rule added")


def remove_auto_assign_rule(ctx, board_id):
    from ... import board as _board
    common.require_board(ctx, board_id, need="ADMIN")
    f = ctx.request.form()
    try:
        _board.set_auto_assign_rule(ctx.conn, board_id, f.get("catalogue_item_id", ""), None, at=ctx.now, actor=ctx.user.id)
        ctx.conn.commit()
    except ValueError as exc:
        ctx.conn.rollback()
        return _done(board_id, "assign", f"Not removed: {exc}")
    return _done(board_id, "assign", "Rule removed")

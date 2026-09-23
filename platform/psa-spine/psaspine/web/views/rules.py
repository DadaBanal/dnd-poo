"""Setup › Workflow rules: build, test, switch on. ConnectWise's shape.

A rule is scoped to a board (or every board), and holds events. Each event
fires on a moment (created, status changed, note added, owner changed, moved) or
on time (schedule, SLA threshold), has conditions read left to right, a run mode
(once, N times every T, continuously every T) and actions. Escalation levels are
successive events, as ConnectWise's own guidance builds them.

The ConnectWise rules this copies (VERIFIED, docs.connectwise.com/
ConnectWise_Documentation/090/020/070/130, archived 2025-08-30): a rule is
created off; every event is tested before it can be switched on, and the test
shows how many open tickets match now; any edit switches it off again.

A board's rules take board ADMIN; a rule on every board takes a system
administrator.
"""
from __future__ import annotations

import re
import urllib.parse

from ... import db, workflow
from .. import templates as t
from . import common

FIRES = (("ON_CREATE", "A ticket is created"), ("ON_STATUS_CHANGE", "The status changes"),
         ("ON_NOTE_ADDED", "A note is added"), ("ON_OWNER_CHANGE", "The owner changes"),
         ("ON_HANDOVER", "It moves board"), ("ON_SLA_THRESHOLD", "SLA time passes a mark"),
         ("ON_SCHEDULE", "On a schedule"))
MODES = (("ONCE", "Once per ticket"), ("MULTIPLE_TIMES", "A number of times"),
         ("CONTINUOUSLY", "Every time, no limit"))
OPS = (("EQ", "is"), ("NE", "is not"), ("IN", "is one of"), ("NOT_IN", "is none of"),
       ("GT", ">"), ("GTE", "≥"), ("LT", "<"), ("LTE", "≤"), ("IS_NULL", "is empty"),
       ("IS_NOT_NULL", "is set"), ("CONTAINS", "contains"))
ACTIONS = (("NOTIFY", "Notify"), ("ESCALATE", "Escalate to"), ("SET_STATUS", "Set status"),
           ("SET_BOARD", "Move to board"), ("ASSIGN_OWNER", "Assign owner"),
           ("ADD_NOTE", "Add an internal note"), ("APPLY_TEMPLATE", "Apply a ticket template"),
           ("FLAG", "Flag for review"))
ROLES = ("SERVICE_MANAGER", "DISPATCH", "ON_CALL", "DUTY_MANAGER", "TEAM_LEADER", "OWNER",
         "REQUESTER")
UNITS = ("MINUTES", "HOURS", "DAYS")
ON = "<span class='chip sla-ok'>on</span>"
OFF = "<span class=chip>off</span>"


def _errors(n: int) -> str:
    return f"<span class='chip sla-bad'>{n}</span>" if n else "0"


def _opts(pairs, sel=""):
    return "".join(f"<option value='{t.esc(k)}'{' selected' if k == sel else ''}>{t.esc(v)}</option>"
                   for k, v in pairs)


def _may(ctx, board_id) -> bool:
    if board_id:
        return common.may_access_board(ctx, board_id, need="ADMIN")
    return bool(ctx.user.is_sysadmin)


def _require(ctx, board_id):
    from .. import HttpError
    if not _may(ctx, board_id):
        raise HttpError("403 Forbidden", "Rules on a board take board admin; rules on every "
                                         "board take a system administrator.")


def _admin_boards(ctx):
    return ctx.conn.execute(
        "SELECT b.board_id, b.display_name FROM board b JOIN board_member m ON m.board_id ="
        " b.board_id WHERE m.member = ? AND m.access = 'ADMIN' ORDER BY b.display_name",
        (ctx.user.id,)).fetchall()


def _event_form(ctx, action_url: str, board_id: str | None) -> str:
    workflow.ensure_vocabulary(ctx.conn)
    fields = [(r["trigger_id"], r["display_name"]) for r in ctx.conn.execute(
        "SELECT trigger_id, display_name FROM workflow_trigger WHERE table_type = 'TICKET'"
        " ORDER BY display_name")]
    statuses = [(r["board_status_id"], r["name"]) for r in ctx.conn.execute(
        "SELECT board_status_id, name FROM board_status WHERE board_id = ? AND inactive = 0"
        " ORDER BY sort_order", (board_id or "",))]
    boards = [(r["board_id"], r["display_name"]) for r in ctx.conn.execute(
        "SELECT board_id, display_name FROM board ORDER BY display_name")]
    templates = [(r["template_id"], r["name"]) for r in ctx.conn.execute(
        "SELECT template_id, name FROM ticket_template WHERE inactive = 0 AND"
        " (board_id = ? OR ? = '') ORDER BY name", (board_id or "", board_id or ""))]
    conds = "".join(
        "<div class=row>"
        + (f"<div style='flex:0 0 90px'><select name=conj{i}>{_opts([('AND', 'and'), ('OR', 'or')])}"
           "</select></div>" if i else "<div style='flex:0 0 90px;padding-top:8px'>When</div>")
        + f"<div><select name=field{i}>{_opts([('', '(no condition)')] + fields)}</select></div>"
        f"<div style='flex:0 0 130px'><select name=op{i}>{_opts(OPS)}</select></div>"
        f"<div><input name=value{i} placeholder='value, or a,b,c for one of'></div></div>"
        for i in range(3))
    acts = "".join(
        "<div class=row>"
        f"<div style='flex:0 0 170px'><select name=act{i}>{_opts([('', '(no action)')] + list(ACTIONS))}</select></div>"
        f"<div><select name=role{i}>{_opts([('', '(who)')] + [(r, r.replace('_', ' ').title()) for r in ROLES])}</select></div>"
        f"<div><select name=status{i}>{_opts([('', '(status)')] + statuses)}</select></div>"
        f"<div><select name=board{i}>{_opts([('', '(board)')] + boards)}</select></div>"
        f"<div><select name=template{i}>{_opts([('', '(template)')] + templates)}</select></div>"
        f"<div><input name=member{i} placeholder='a named person (optional)'></div>"
        f"<div><input name=detail{i} placeholder='what it says'></div></div>"
        for i in range(2))
    return (
        f"<form method=post action='{t.esc(action_url)}'>"
        "<div class=grid2>"
        "<div><label>Event name</label><input name=event_name required placeholder='e.g. New for 30 minutes'></div>"
        f"<div><label>Fires when</label><select name=fires_on>{_opts(FIRES)}</select></div>"
        f"<div><label>Runs</label><select name=mode>{_opts(MODES)}</select></div>"
        "<div class=row><div><label>Every</label><input name=frequency type=number min=1></div>"
        f"<div><label>&nbsp;</label><select name=unit>{_opts([(u, u.title()) for u in UNITS])}</select></div>"
        "<div><label>At most (times)</label><input name=max type=number min=1></div></div>"
        "</div><h3 style='margin-top:12px'>Conditions</h3>" + conds +
        "<p class=why>Read left to right, as listed. Status and Type values are the codes shown on "
        "the ticket (e.g. P1, INCIDENT, NOT_RESPONDED). SLA used (%) counts SLA time only: a "
        "waiting status does not add to it.</p>"
        "<h3>Actions</h3>" + acts +
        "<div style='margin-top:12px'><button type=submit>Save event</button> "
        "<span class=why>Saving switches the rule off until it is tested again.</span></div></form>")


def index(ctx):
    from .. import Response
    mine = {b["board_id"] for b in _admin_boards(ctx)}
    if not mine and not ctx.user.is_sysadmin:
        from .. import HttpError
        raise HttpError("403 Forbidden", "Workflow rules take board admin.")
    rows = ctx.conn.execute(
        "SELECT w.*, b.display_name AS board_name,"
        " (SELECT COUNT(*) FROM workflow_event e WHERE e.workflow_id = w.workflow_id) AS events,"
        " (SELECT COUNT(*) FROM workflow_run r JOIN workflow_event e ON e.event_id = r.event_id"
        "   WHERE e.workflow_id = w.workflow_id AND r.outcome = 'ACTED') AS acted,"
        " (SELECT COUNT(*) FROM workflow_run r JOIN workflow_event e ON e.event_id = r.event_id"
        "   WHERE e.workflow_id = w.workflow_id AND r.outcome = 'ERROR') AS errors"
        " FROM workflow w LEFT JOIN board b ON b.board_id = w.board_id"
        " WHERE w.table_type = 'TICKET' ORDER BY w.name").fetchall()
    trs = "".join(
        f"<tr><td><a href='/admin/rules/{t.esc(r['workflow_id'])}'>{t.esc(r['name'])}</a></td>"
        f"<td>{t.esc(r['board_name'] or 'Every board')}</td>"
        f"<td>{ON if r['is_active'] else OFF}</td>"
        f"<td>{r['events']}</td><td>{r['acted']}</td>"
        f"<td>{_errors(r['errors'])}</td></tr>"
        for r in rows if (r["board_id"] in mine or ctx.user.is_sysadmin)) or \
        "<tr><td colspan=6 class=muted>No rules yet.</td></tr>"
    boards = [(b["board_id"], b["display_name"]) for b in _admin_boards(ctx)]
    if ctx.user.is_sysadmin:
        boards = [("", "Every board")] + boards
    body = (
        "<h1>Workflow rules</h1><p class=sub>ConnectWise's workflow rules: an event, conditions, "
        "actions. They run the moment a ticket changes, and every minute for time-based events. "
        "A rule is created off; test each event, then switch it on. <a href='/admin'>Setup</a></p>"
        "<div class=card><div class=tablewrap><table><thead><tr><th>Rule</th><th>Board</th>"
        "<th>State</th><th>Events</th><th>Actions taken</th><th>Errors</th></tr></thead>"
        f"<tbody>{trs}</tbody></table></div></div>"
        "<div class=card><h3>New rule</h3><form method=post action='/admin/rules/new' class=row>"
        "<div><label>Name</label><input name=name required placeholder='e.g. Unowned P1'></div>"
        f"<div><label>Board</label><select name=board_id>{_opts(boards)}</select></div>"
        "<div style='flex:0 0 auto'><button type=submit>Create</button></div></form></div>")
    return Response(body=t.page("Workflow rules", body, user=ctx.user, active="admin"))


def create(ctx):
    from .. import redirect
    f = ctx.request.form()
    board_id = f.get("board_id") or None
    _require(ctx, board_id)
    name = f.get("name", "").strip()
    if not name:
        return redirect("/admin/rules")
    wid = "WF_" + (re.sub(r"[^A-Z0-9]+", "_", name.upper()).strip("_")[:30] or "RULE")
    n, base = 1, wid
    while ctx.conn.execute("SELECT 1 FROM workflow WHERE workflow_id = ?", (wid,)).fetchone():
        n += 1
        wid = f"{base}_{n}"
    ctx.conn.execute("INSERT INTO workflow (workflow_id, board_id, name, table_type, is_active)"
                     " VALUES (?,?,?,'TICKET',0)", (wid, board_id, name))
    db.audit(ctx.conn, at=ctx.now.isoformat(sep=" ", timespec="minutes"), actor=ctx.user.id,
             action="WORKFLOW_CREATE", subject_kind="workflow", subject_id=wid, detail=name)
    ctx.conn.commit()
    return redirect(f"/admin/rules/{wid}")


def _load(ctx, workflow_id):
    from .. import HttpError
    w = ctx.conn.execute("SELECT * FROM workflow WHERE workflow_id = ?", (workflow_id,)).fetchone()
    if w is None:
        raise HttpError("404 Not Found", "No such rule.")
    _require(ctx, w["board_id"])
    return w


def detail(ctx, workflow_id):
    from .. import Response
    w = _load(ctx, workflow_id)
    msg = ctx.request.query.get("msg", "")
    err = ctx.request.query.get("err", "")
    wid = t.esc(workflow_id)
    label = dict(OPS)
    cards = []
    for e in ctx.conn.execute("SELECT * FROM workflow_event WHERE workflow_id = ?"
                              " ORDER BY event_id", (workflow_id,)).fetchall():
        conds = ctx.conn.execute(
            "SELECT c.*, t.display_name FROM workflow_condition c JOIN workflow_trigger t"
            " ON t.trigger_id = c.trigger_id WHERE c.event_id = ? ORDER BY c.sort_order",
            (e["event_id"],)).fetchall()
        when = " ".join(
            (f"<b>{t.esc(c['conjunction'].lower())}</b> " if i else "")
            + f"{t.esc(c['display_name'])} {t.esc(label.get(c['operator'], c['operator']))} "
            f"<code>{t.esc(c['value'] or '')}</code>" for i, c in enumerate(conds)) or "always"
        acts = "".join(
            f"<li>{t.esc(dict(ACTIONS).get(a['action'], a['action']))} "
            f"{t.esc((a['notify_role'] or '').replace('_', ' ').lower())} "
            f"{t.esc(a['target_member'] or '')} {t.esc(a['target_status_id'] or '')} "
            f"{t.esc(a['target_board_id'] or '')} {t.esc(a['target_template_id'] or '')}"
            + (f" <span class=muted>“{t.esc(a['detail'])}”</span>" if a["detail"] else "") + "</li>"
            for a in ctx.conn.execute("SELECT * FROM workflow_action WHERE event_id = ?"
                                      " ORDER BY sort_order", (e["event_id"],)))
        mode = dict(MODES).get(e["execution_time"], e["execution_time"])
        if e["execution_time"] != "ONCE":
            mode += f", every {e['frequency']} {(e['frequency_unit'] or '').lower()}"
        if e["max_executions"]:
            mode += f", at most {e['max_executions']}"
        tested = (f"<span class='chip sla-ok'>tested {t.esc(e['tested_at'])}: "
                  f"{e['tested_matches']} open ticket(s) match now</span>" if e["tested_at"]
                  else "<span class='chip sla-warn'>not tested</span>")
        cards.append(
            f"<div class=card><h3>{t.esc(e['name'] or e['event_id'])}</h3>"
            f"<p><b>{t.esc(dict(FIRES).get(e['fires_on'], e['fires_on']))}</b> · {t.esc(mode)} · {tested}</p>"
            f"<p>When: {when}</p><ul class=plain>{acts or '<li class=muted>No actions.</li>'}</ul>"
            f"<form method=post action='/admin/rules/{wid}/test' class=inline>"
            f"<input type=hidden name=event_id value='{t.esc(e['event_id'])}'>"
            "<button class=ghost type=submit>Test against open tickets</button></form></div>")
    runs = ctx.conn.execute(
        "SELECT r.* FROM workflow_run r JOIN workflow_event e ON e.event_id = r.event_id"
        " WHERE e.workflow_id = ? AND r.outcome IN ('ACTED','ERROR') ORDER BY r.run_id DESC"
        " LIMIT 20", (workflow_id,)).fetchall()
    log = "".join(
        f"<tr><td>{t.esc(r['occurred_at'])}</td><td>{t.esc(r['event_id'])}</td>"
        f"<td><a href='/ticket/{t.esc(r['work_item_id'] or '')}'>{t.esc(r['work_item_id'] or '')}</a></td>"
        f"<td>{t.esc(r['outcome'])}</td><td class=muted>{t.esc(r['detail'] or '')}</td></tr>"
        for r in runs) or "<tr><td colspan=5 class=muted>Nothing yet.</td></tr>"
    switch = (f"<form method=post action='/admin/rules/{wid}/{'deactivate' if w['is_active'] else 'activate'}' "
              "class=inline><button type=submit>"
              + ("Switch off" if w["is_active"] else "Switch on") + "</button></form>")
    body = (
        (f"<div class='banner ok'>{t.esc(msg)}</div>" if msg else "")
        + (f"<div class='banner err'>{t.esc(err)}</div>" if err else "")
        + f"<h1>{t.esc(w['name'])} "
        + ("<span class='chip sla-ok'>on</span>" if w["is_active"] else "<span class=chip>off</span>")
        + f"</h1><p class=sub><a href='/admin/rules'>All rules</a> · {switch}</p>"
        + "".join(cards)
        + f"<div class=card><h3>Add an event</h3>{_event_form(ctx, f'/admin/rules/{workflow_id}/event', w['board_id'])}</div>"
        "<div class=card><h3>What it has done</h3><div class=tablewrap><table><thead><tr>"
        "<th>When</th><th>Event</th><th>Ticket</th><th>Outcome</th><th>Detail</th></tr></thead>"
        f"<tbody>{log}</tbody></table></div></div>")
    return Response(body=t.page(w["name"], body, user=ctx.user, active="admin"))


def _back(workflow_id, **q):
    from .. import redirect
    return redirect(f"/admin/rules/{workflow_id}?" + urllib.parse.urlencode(q))


def add_event(ctx, workflow_id):
    w = _load(ctx, workflow_id)
    workflow.ensure_vocabulary(ctx.conn)
    f = ctx.request.form()
    n = ctx.conn.execute("SELECT COUNT(*) FROM workflow_event WHERE workflow_id = ?",
                         (workflow_id,)).fetchone()[0] + 1
    ev = f"{workflow_id}_E{n}"
    mode = f.get("mode") if f.get("mode") in dict(MODES) else "ONCE"
    freq = int(f["frequency"]) if f.get("frequency", "").isdigit() else None
    cap = int(f["max"]) if f.get("max", "").isdigit() else None
    try:
        ctx.conn.execute(
            "INSERT INTO workflow_event (event_id, workflow_id, name, fires_on, execution_time,"
            " frequency, frequency_unit, max_executions) VALUES (?,?,?,?,?,?,?,?)",
            (ev, workflow_id, f.get("event_name", "").strip() or ev,
             f.get("fires_on") if f.get("fires_on") in dict(FIRES) else "ON_CREATE", mode,
             freq if mode != "ONCE" else None, f.get("unit") if mode != "ONCE" else None,
             cap if mode == "MULTIPLE_TIMES" else None))
        for i in range(3):
            if f.get(f"field{i}"):
                ctx.conn.execute(
                    "INSERT INTO workflow_condition (event_id, trigger_id, operator, value,"
                    " conjunction, sort_order) VALUES (?,?,?,?,?,?)",
                    (ev, f[f"field{i}"], f.get(f"op{i}", "EQ"), f.get(f"value{i}", "").strip() or None,
                     f.get(f"conj{i}", "AND") if i else "AND", i))
        for i in range(2):
            if f.get(f"act{i}"):
                ctx.conn.execute(
                    "INSERT INTO workflow_action (event_id, action, notify_role, target_status_id,"
                    " target_board_id, target_member, detail, sort_order, target_template_id)"
                    " VALUES (?,?,?,?,?,?,?,?,?)",
                    (ev, f[f"act{i}"], f.get(f"role{i}") or None, f.get(f"status{i}") or None,
                     f.get(f"board{i}") or None, f.get(f"member{i}", "").strip() or None,
                     f.get(f"detail{i}", "").strip() or None, i,
                     f.get(f"template{i}") or None))
    except Exception as exc:                                  # noqa: BLE001
        ctx.conn.rollback()
        hint = (" A repeating event needs an interval, and 'a number of times' needs a limit."
                if "CHECK" in str(exc) else "")
        return _back(workflow_id, err=f"Not saved: {exc}.{hint}")
    workflow.edited(ctx.conn, workflow_id)
    db.audit(ctx.conn, at=ctx.now.isoformat(sep=" ", timespec="minutes"), actor=ctx.user.id,
             action="WORKFLOW_EDIT", subject_kind="workflow", subject_id=workflow_id,
             detail=f"event {ev} added; rule switched off until tested")
    ctx.conn.commit()
    return _back(workflow_id, msg="Event saved. The rule is off until every event is tested.")


def test(ctx, workflow_id):
    _load(ctx, workflow_id)
    ev = ctx.request.form().get("event_id", "")
    try:
        r = workflow.test_event(ctx.conn, ev, at=ctx.now)
    except Exception as exc:                                  # noqa: BLE001
        ctx.conn.rollback()
        return _back(workflow_id, err=f"Test failed: {exc}")
    ctx.conn.commit()
    sample = ", ".join(r["sample"][:10])
    return _back(workflow_id, msg=f"{r['matches']} open ticket(s) match now"
                              + (f": {sample}" + ("…" if r["matches"] > 10 else "") if sample else ""))


def activate(ctx, workflow_id):
    _load(ctx, workflow_id)
    try:
        workflow.activate(ctx.conn, workflow_id, actor=ctx.user.id, at=ctx.now)
    except ValueError as exc:
        return _back(workflow_id, err=str(exc))
    ctx.conn.commit()
    return _back(workflow_id, msg="Switched on")


def deactivate(ctx, workflow_id):
    _load(ctx, workflow_id)
    ctx.conn.execute("UPDATE workflow SET is_active = 0 WHERE workflow_id = ?", (workflow_id,))
    db.audit(ctx.conn, at=ctx.now.isoformat(sep=" ", timespec="minutes"), actor=ctx.user.id,
             action="WORKFLOW_DEACTIVATE", subject_kind="workflow", subject_id=workflow_id)
    ctx.conn.commit()
    return _back(workflow_id, msg="Switched off")

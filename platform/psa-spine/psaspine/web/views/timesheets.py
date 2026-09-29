"""Timesheets (046): a member's week of time, submitted and decided.

/time is the member's own week. A time administrator (the TIME module at
ADMIN) sees anyone's week, the sheets waiting for a decision, and sets a
member's hours a week. The owner of a sheet never decides it. Tickets on a
restricted board the viewer is not a member of show as hours only.
"""
from __future__ import annotations

import urllib.parse
from datetime import timedelta

from ... import timesheets
from .. import templates as t
from . import common

CHIP = {"OPEN": "", "SUBMITTED": "sla-warn", "APPROVED": "sla-ok", "REJECTED": "sla-bad"}
DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


def _back(path: str, **q):
    from .. import redirect
    q = {k: v for k, v in q.items() if v}
    return redirect(path + ("?" + urllib.parse.urlencode(q) if q else ""))


def _sheet_url(member: str, week_start) -> str:
    return "/time?" + urllib.parse.urlencode({"member": member, "week": week_start.isoformat()})


def _chip(status: str | None) -> str:
    status = status or "OPEN"
    return f"<span class='chip {CHIP.get(status, '')}'>{t.esc(timesheets.STATUSES.get(status, status))}</span>"


def _words(code: str | None) -> str:
    return (code or "").lower().replace("_", " ")


def _member_and_week(ctx, source: dict):
    """The member and the Monday a request is about; another person's sheet
    is a time administrator's to see."""
    from .. import HttpError
    admin = common.allows(ctx, "TIME", "ADMIN")
    member = (source.get("member") or "").strip() or ctx.user.id
    if member.lower() != ctx.user.id.lower() and not admin:
        raise HttpError("403 Forbidden", "Another person's timesheet is a time administrator's to see.")
    try:
        ws = timesheets.week_of(source.get("week") or ctx.now.date())
    except timesheets.Refused:
        ws = timesheets.week_of(ctx.now.date())
    return member, ws, admin


def index(ctx):
    from .. import Response
    common.require_module(ctx, "TIME")
    q = ctx.request.query
    member, ws, admin = _member_and_week(ctx, q)
    we = timesheets.week_end(ws)
    sheet = timesheets.get(ctx.conn, member, ws)
    rows = timesheets.entries(ctx.conn, member, ws)
    tot = timesheets.totals(rows)
    cap = timesheets.capacity(ctx.conn, member)
    mine = common.board_ids_for(ctx)
    own = member.lower() == ctx.user.id.lower()
    status = sheet["status"] if sheet else "OPEN"
    common.audit_restricted_reads(ctx, [r["board_id"] for r in rows if r["board_id"] and r["board_id"] in mine],
                                  detail=f"timesheet of {member}, week of {ws.isoformat()}:")

    def ticket_cell(r) -> tuple[str, str]:
        if r["board_id"] and r["board_id"] not in mine and common.is_restricted(ctx, r["board_id"]):
            return "<span class=muted>a ticket on a restricted board</span>", ""
        return (f"<a href='/ticket/{t.esc(r['work_item_id'])}'>{t.esc(r['work_item_id'])}</a> {t.esc(r['summary'] or '')}",
                t.esc(r["board_name"] or ""))

    trs = ""
    for r in rows:
        try:
            day = DAYS[timesheets.week_of(r["worked_on"]).weekday()] if False else DAYS[(ws - ws).days]
        except Exception:                                   # noqa: BLE001
            day = ""
        from datetime import date as _date
        try:
            day = DAYS[_date.fromisoformat(r["worked_on"]).weekday()]
        except (TypeError, ValueError):
            day = ""
        tk, bd = ticket_cell(r)
        span = f"{r['time_start'][11:]}–{r['time_end'][11:]}" if r["time_start"] and r["time_end"] else "actual"
        trs += (f"<tr><td>{day} {t.esc(r['worked_on'])}</td><td>{tk}</td><td>{bd}</td>"
                f"<td class=num>{float(r['hours'] or 0):g}</td><td class=muted>{t.esc(span)}</td>"
                f"<td>{t.esc(_words(r['work_role_id']))} · {t.esc(_words(r['work_type_id']))}</td>"
                f"<td>{t.esc(_words(r['charge_method']))}</td><td>{t.esc(r['note'] or '')}</td></tr>")
    day_strip = " · ".join(f"{DAYS[i]} {tot['days'].get((ws + timedelta(days=i)).isoformat(), 0):g}" for i in range(7))
    over = tot["total"] > cap
    summary = (f"<div class='tiles' style='grid-template-columns:repeat(auto-fit,minmax(150px,1fr));margin-bottom:12px'>"
               f"<div class=tile><div class=l>Hours this week</div><div class=n>{tot['total']:g}</div>"
               f"<div class=muted>of {cap:g} a week{' · over' if over else ''}</div></div>"
               f"<div class=tile><div class=l>Entries</div><div class=n>{len(rows)}</div></div>"
               f"<div class=tile><div class=l>Status</div><div class=n style='font-size:18px'>{_chip(status)}</div>"
               + (f"<div class=muted>by {t.esc(sheet['decided_by'])} · {t.esc(sheet['decided_at'])}</div>"
                  if sheet and sheet["decided_by"] else
                  (f"<div class=muted>submitted {t.esc(sheet['submitted_at'])}</div>" if sheet and sheet["submitted_at"] else ""))
               + "</div></div>")
    if sheet and sheet["note"]:
        summary += f"<div class='banner {'err' if status == 'REJECTED' else 'ok'}'>{t.esc(sheet['note'])}</div>"

    acts = ""
    hidden = (f"<input type=hidden name=member value='{t.esc(member)}'><input type=hidden name=week value='{ws.isoformat()}'>")
    can_write = common.allows(ctx, "TIME", "WRITE")
    if status in ("OPEN", "REJECTED") and (own or admin) and can_write and ws <= timesheets.week_of(ctx.now):
        acts += (f"<form method=post action='/time/submit' class=inline>{hidden}"
                 "<button type=submit>Submit for approval</button></form>")
    if sheet and status == "SUBMITTED" and admin and not own:
        acts += (f"<form method=post action='/time/decide' class='row schedbar' style='margin-top:8px'>"
                 f"<input type=hidden name=timesheet_id value={sheet['timesheet_id']}>{hidden}"
                 "<div style='flex:1 1 260px'><input name=note maxlength=500 placeholder='A reason or conditions (needed to reject)'></div>"
                 "<div style='flex:0 0 auto'><button type=submit name=decision value=APPROVE>Approve</button> "
                 "<button class='ghost danger' type=submit name=decision value=REJECT>Reject</button></div></form>")
    elif sheet and status == "SUBMITTED" and own:
        acts += "<p class=muted>Submitted; another time administrator decides it.</p>"
    if sheet and status in timesheets.LOCKED and admin:
        acts += (f"<form method=post action='/time/reopen' class='row schedbar' style='margin-top:8px'>"
                 f"<input type=hidden name=timesheet_id value={sheet['timesheet_id']}>{hidden}"
                 "<div style='flex:1 1 260px'><input name=note maxlength=500 required placeholder='Why it is reopened'></div>"
                 "<div style='flex:0 0 auto'><button class=ghost type=submit>Reopen</button></div></form>")
    hist = ""
    if sheet:
        events = timesheets.history(ctx.conn, sheet["timesheet_id"])
        if events:
            hist = ("<div class=card><h3>" + t.icon("clock") + "History</h3><ul class=plain>" + "".join(
                f"<li>{t.esc(e['occurred_at'])} · {t.esc(e['actor'])} · {t.esc(e['action'].lower())}"
                + (f" · {t.esc(e['note'])}" if e["note"] else "") + "</li>" for e in events) + "</ul></div>")

    prev_w, next_w = ws - timedelta(days=7), ws + timedelta(days=7)
    member_pick = f"<input type=hidden name=member value='{t.esc(member)}'>"
    if admin:
        names = timesheets.members(ctx.conn)
        if member not in names:
            names.append(member)
        member_pick = ("<div style='flex:0 0 220px'><label>Member</label><select name=member aria-label='Member'>" + "".join(
            f"<option value='{t.esc(n)}'{' selected' if n.lower() == member.lower() else ''}>{t.esc(n)}</option>" for n in names)
            + "</select></div>")
    nav = ("<div class=card><form method=get action='/time' class='row schedbar'>"
           f"<div style='flex:0 0 auto'><a class='btn ghost' href='{t.esc(_sheet_url(member, prev_w))}' title='Previous week'>‹</a></div>"
           f"<div style='flex:0 0 170px'><label>Week of</label><input type=date name=week value='{ws.isoformat()}'></div>"
           f"<div style='flex:0 0 auto'><a class='btn ghost' href='{t.esc(_sheet_url(member, next_w))}' title='Next week'>›</a></div>"
           + member_pick +
           "<div style='flex:0 0 auto;align-self:end'><button class=ghost type=submit>Show</button></div>"
           f"<div style='flex:0 0 auto;align-self:end'><a class='btn ghost' href='{t.esc(_sheet_url(member, timesheets.week_of(ctx.now)))}'>This week</a></div>"
           "</form></div>")
    sheet_card = (f"<div class=card><h3>{t.icon('clock')}Week of {ws.isoformat()} to {we.isoformat()} · {t.esc(member)}</h3>"
                  + summary + "<div class=tablewrap><table><thead><tr><th>Day</th><th>Ticket</th><th>Board</th><th class=num>Hours</th>"
                  "<th>When</th><th>Role · type</th><th>Charge</th><th>Note</th></tr></thead><tbody>"
                  + (trs or "<tr><td colspan=8 class=muted>No time recorded this week. Time goes on the ticket it was spent on.</td></tr>")
                  + f"</tbody></table></div><p class=muted style='margin-top:6px'>{t.esc(day_strip)}</p>"
                  + (f"<div style='margin-top:10px'>{acts}</div>" if acts else "") + "</div>")
    waiting = ""
    if admin:
        w = timesheets.waiting(ctx.conn)
        wrows = "".join(
            f"<tr><td><a href='{t.esc(_sheet_url(s['member'], timesheets.week_of(s['week_start'])))}'>{t.esc(s['member'])}</a></td>"
            f"<td>{t.esc(s['week_start'])}</td><td class=num>{float(s['hours'] or 0):g}</td><td class=muted>{t.esc(s['submitted_at'] or '')}</td></tr>"
            for s in w)
        waiting = ("<div class=card><h3>" + t.icon("check") + f"Waiting for a decision · {len(w)}</h3><div class=tablewrap><table><thead><tr>"
                   "<th>Member</th><th>Week of</th><th class=num>Hours</th><th>Submitted</th></tr></thead><tbody>"
                   + (wrows or "<tr><td colspan=4 class=muted>Nothing waiting.</td></tr>") + "</tbody></table></div></div>")
        waiting += ("<div class=card><h3>" + t.icon("users") + "Hours a week</h3>"
                    f"<p class=why>What {t.esc(member)} is expected to record; the utilisation figure on Reports divides by it.</p>"
                    f"<form method=post action='/time/capacity' class=row><input type=hidden name=member value='{t.esc(member)}'>"
                    f"<input type=hidden name=week value='{ws.isoformat()}'>"
                    f"<div style='flex:0 0 140px'><label>Hours a week</label><input name=hours inputmode=decimal value='{cap:g}'></div>"
                    "<div style='flex:0 0 auto;align-self:end'><button class=ghost type=submit>Save</button></div></form></div>")
    body = ((f"<div class='banner ok'>{t.esc(q.get('msg', ''))}</div>" if q.get("msg") else "")
            + (f"<div class='banner err'>{t.esc(q.get('err', ''))}</div>" if q.get("err") else "")
            + "<h1>Timesheets</h1><p class=sub>A week of one person's time, as it went on their tickets. Submit it when the week "
              "is complete; a time administrator who is not you approves or rejects it, and a submitted week takes no more time "
              "until it is reopened.</p>" + nav + sheet_card + hist + waiting)
    return Response(body=t.page("Timesheets", body, user=ctx.user, active="time"))


def _try(ctx, fn, ok, *, member: str, week):
    where = _sheet_url(member, week)
    try:
        r = fn()
        ctx.conn.commit()
    except timesheets.Refused as exc:
        ctx.conn.rollback()
        return _back(where, err=str(exc))
    return _back(where, msg=ok(r))


def submit(ctx):
    common.require_module(ctx, "TIME", "WRITE")
    f = ctx.request.form()
    member, ws, _admin = _member_and_week(ctx, f)
    return _try(ctx, lambda: timesheets.submit(ctx.conn, member, ws, at=ctx.now, actor=ctx.user.id),
                lambda s: "Submitted for approval", member=member, week=ws)


def decide(ctx):
    common.require_module(ctx, "TIME", "ADMIN")
    f = ctx.request.form()
    member, ws, _admin = _member_and_week(ctx, f)
    try:
        sid = int(f.get("timesheet_id", ""))
    except ValueError:
        return _back(_sheet_url(member, ws), err="No such timesheet.")
    return _try(ctx, lambda: timesheets.decide(ctx.conn, sid, f.get("decision", ""), at=ctx.now, actor=ctx.user.id,
                                               note=f.get("note")),
                lambda s: f"{timesheets.STATUSES[s['status']]}", member=member, week=ws)


def reopen(ctx):
    common.require_module(ctx, "TIME", "ADMIN")
    f = ctx.request.form()
    member, ws, _admin = _member_and_week(ctx, f)
    try:
        sid = int(f.get("timesheet_id", ""))
    except ValueError:
        return _back(_sheet_url(member, ws), err="No such timesheet.")
    return _try(ctx, lambda: timesheets.reopen(ctx.conn, sid, at=ctx.now, actor=ctx.user.id, note=f.get("note")),
                lambda s: "Reopened; time can be added again", member=member, week=ws)


def capacity(ctx):
    common.require_module(ctx, "TIME", "ADMIN")
    f = ctx.request.form()
    member, ws, _admin = _member_and_week(ctx, f)
    return _try(ctx, lambda: timesheets.set_capacity(ctx.conn, member, f.get("hours"), at=ctx.now, actor=ctx.user.id),
                lambda h: f"{member} is expected to record {h:g} hours a week", member=member, week=ws)

"""The in/out board (057): where everyone is, said by themselves.

Anyone with the Schedule module sees the people who work the boards they
see, each with their state, a note and when they are back. A person sets
their own line; nobody sets another's. The Schedule page carries the same
word beside each name.
"""
from __future__ import annotations

import urllib.parse

from ... import members as _members
from ... import presence
from .. import templates as t
from . import common


def _people(ctx) -> list[str]:
    boards = sorted(common.board_ids_for(ctx))
    if not boards:
        return [ctx.user.id]
    marks = ",".join("?" * len(boards))
    rows = ctx.conn.execute(
        f"SELECT DISTINCT bm.member FROM board_member bm LEFT JOIN member m ON LOWER(m.member) = LOWER(bm.member)"
        f" WHERE bm.board_id IN ({marks}) AND m.inactive_from IS NULL ORDER BY bm.member", boards).fetchall()
    people = [r["member"] for r in rows]
    if ctx.user.id.lower() not in {p.lower() for p in people}:
        people.append(ctx.user.id)
    return people


def index(ctx):
    from .. import Response
    common.require_module(ctx, "SCHEDULE")
    q = ctx.request.query
    people = _people(ctx)
    states = presence.all_(ctx.conn, people)
    mine = presence.current(ctx.conn, ctx.user.id)
    rows = "".join(
        f"<tr{' class=me' if p.lower() == ctx.user.id.lower() else ''}><td><b>{t.esc(_members.name_of(ctx.conn, p))}</b>"
        + (f"<div class=muted>{t.esc(p)}</div>" if _members.name_of(ctx.conn, p) != p else "") + "</td>"
        f"<td>{t.chip(presence.STATES[states[p]['state']], 'sla-ok' if states[p]['state'] == 'IN' else '') if states[p] else '<span class=muted>not said</span>'}</td>"
        f"<td>{t.esc(states[p]['note'] or '') if states[p] else ''}</td>"
        f"<td>{t.esc(states[p]['back_at'] or '') if states[p] else ''}</td>"
        f"<td class=muted>{t.esc(states[p]['set_at']) if states[p] else ''}</td></tr>" for p in people)
    state_opts = "".join(f"<option value={k}{' selected' if mine and mine['state'] == k else ''}>{t.esc(v)}</option>"
                         for k, v in presence.STATES.items())
    body = ((f"<div class='banner ok'>{t.esc(q.get('msg', ''))}</div>" if q.get("msg") else "")
            + (f"<div class='banner err'>{t.esc(q.get('err', ''))}</div>" if q.get("err") else "")
            + "<h1>In / out</h1><p class=sub>Where everyone is right now, said by themselves. It changes no ticket and no "
              "visit; it is the board by the door. <a href='/schedule'>Schedule</a></p>"
              "<div class=card><h3>" + t.icon("users") + "Where I am</h3>"
              "<form method=post action='/inout/me' class=row>"
              f"<div style='flex:0 0 180px'><label>State</label><select name=state>{state_opts}</select></div>"
              f"<div style='flex:1 1 220px'><label>Note</label><input name=note maxlength=200 value='{t.esc(mine['note'] or '') if mine else ''}'"
              " placeholder='ward 3 · the supplier · a meeting'></div>"
              f"<div style='flex:0 0 200px'><label>Back at</label><input type=datetime-local name=back_at"
              f" value='{t.esc(mine['back_at'].replace(' ', 'T')) if mine and mine['back_at'] else ''}'></div>"
              "<div style='flex:0 0 auto;align-self:end'><button type=submit>Say so</button></div></form></div>"
              "<div class=card><h3>" + t.icon("grip") + "Everyone</h3><div class=tablewrap><table><thead><tr><th>Who</th><th>State</th>"
              "<th>Note</th><th>Back at</th><th>Said</th></tr></thead><tbody>"
            + (rows or "<tr><td colspan=5 class=muted>Nobody works these boards yet.</td></tr>") + "</tbody></table></div></div>")
    return Response(body=t.page("In / out", body, user=ctx.user, active="schedule"))


def me(ctx):
    from .. import redirect
    common.require_module(ctx, "SCHEDULE")
    f = ctx.request.form()
    try:
        presence.set_state(ctx.conn, ctx.user.id, f.get("state", ""), at=ctx.now, note=f.get("note"), back_at=f.get("back_at"))
        ctx.conn.commit()
    except ValueError as exc:
        ctx.conn.rollback()
        return redirect("/inout?" + urllib.parse.urlencode({"err": str(exc)}))
    return redirect("/inout?" + urllib.parse.urlencode({"msg": "Said."}))

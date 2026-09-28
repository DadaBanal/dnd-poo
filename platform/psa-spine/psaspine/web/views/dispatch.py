"""The dispatch / triage view — the unrouted queue, and who answers.

The unrouted queue is where a ticket lands before anyone owns it, and a queue
that ages invisibly is how a P1 waits. So it ages here in plain sight, coloured
by the same SLA logic as the board. Beside it, the four board roles and — over
the top of them — the rota's answer to "who is on call right now", because at
02:00 the name that matters is whoever is on shift, not whoever the org chart
names.
"""
from __future__ import annotations

from .. import templates as t
from . import common

ROLES = ("SERVICE_MANAGER", "DISPATCH", "ON_CALL", "DUTY_MANAGER")


def index(ctx):
    from .. import Response
    from ... import board as engine

    boards = common.board_ids_for(ctx)
    unrouted_rows = []
    if boards:
        unrouted_rows = ctx.conn.execute(
            "SELECT t.work_item_id, t.priority, t.opened_at, t.board_id,"
            "       w.name AS summary, e.name AS entity"
            "  FROM ticket t"
            "  JOIN work_item w ON w.work_item_id = t.work_item_id"
            "  LEFT JOIN entity e ON e.entity_id = w.entity_id"
            "  JOIN board b ON b.board_id = t.board_id"
            " WHERE b.is_unrouted = 1 AND t.board_id IN (%s)"
            "   AND t.state NOT IN ('RESOLVED','CLOSED','CANCELLED')"
            % ",".join("?" * len(boards)), tuple(boards)).fetchall()

    # Where a ticket can be routed TO: boards this user may work, that are not the
    # unrouted queue itself.
    targets = ctx.conn.execute(
        "SELECT b.board_id, b.display_name FROM board b"
        " JOIN board_member m ON m.board_id = b.board_id"
        " WHERE m.member = ? AND m.access IN ('WORK','ADMIN') AND b.is_unrouted = 0"
        " AND COALESCE(b.inactive, 0) = 0"
        " ORDER BY b.display_name", (ctx.user.id,)).fetchall()
    target_opts = "".join(
        f"<option value='{t.esc(b['board_id'])}'>{t.esc(b['display_name'])}</option>"
        for b in targets)

    if unrouted_rows:
        lines = []
        all_states = common.clock_states_many(
            ctx.conn, [r["work_item_id"] for r in unrouted_rows], now=ctx.now)
        for r in sorted(unrouted_rows, key=lambda x: (x["priority"] or "P9", x["opened_at"] or "")):
            states = all_states[r["work_item_id"]]
            assign = ""
            if target_opts:
                assign = (
                    f"<form method='post' action='/dispatch/assign' class='dispatch-route' "
                    "style='display:flex;gap:6px'>"
                    f"<input type='hidden' name='work_item_id' value='{t.esc(r['work_item_id'])}'>"
                    f"<select name='to_board'>{target_opts}</select>"
                    "<input name='owner' placeholder='owner' style='width:120px'>"
                    "<button type='submit'>Route</button></form>")
            lines.append(
                "<tr>"
                f"<td><a href='/ticket/{t.esc(r['work_item_id'])}'>{t.esc(r['work_item_id'])}</a></td>"
                f"<td>{t.badge(r['priority'])}</td>"
                f"<td>{t.esc(common.human_age(r['opened_at'], now=ctx.now))}</td>"
                f"<td>{t.sla_chips(states) or '<span class=pill>no clock</span>'}</td>"
                f"<td>{t.esc(r['summary'])}</td>"
                f"<td class='muted'>{t.esc(r['entity'] or '—')}</td>"
                f"<td>{assign}</td></tr>")
        queue = ("<div class='card'><h3><svg class=ic aria-hidden=true><use href=#i-inbox></use></svg>Unrouted queue</h3><div class='tablewrap'><table>"
                 "<thead><tr><th>ID</th><th>Pri</th><th>Age</th><th>SLA</th>"
                 "<th>Summary</th><th>Entity</th><th>Route to</th></tr></thead><tbody>"
                 + "".join(lines) + "</tbody></table></div></div>")
    else:
        queue = ("<div class='card'><h3><svg class=ic aria-hidden=true><use href=#i-inbox></use></svg>Unrouted queue</h3>"
                 "<div class='empty'>Nothing waiting to be routed.</div></div>")

    # Roles + live on-call, per board the user can see.
    role_cards = []
    for bid in sorted(boards):
        board = ctx.conn.execute("SELECT display_name FROM board WHERE board_id = ?",
                                (bid,)).fetchone()
        named = {r["role"]: r["member"] for r in ctx.conn.execute(
            "SELECT role, member FROM board_role WHERE board_id = ?", (bid,))}
        rows = []
        for role in ROLES:
            oncall = None
            if role in ("ON_CALL", "DUTY_MANAGER"):
                oncall = engine.current_oncall(ctx.conn, bid, role, at=ctx.now)
            who = oncall or named.get(role) or "—"
            tag = " <span class='muted'>(on shift now)</span>" if oncall else ""
            rows.append(f"<dt>{t.esc(role.replace('_',' ').title())}</dt>"
                        f"<dd>{t.esc(who)}{tag}</dd>")
        if rows:
            role_cards.append(f"<div class='card'><h3>{t.esc(board['display_name'])}</h3>"
                              f"<dl class='kv'>{''.join(rows)}</dl></div>")

    # The day: every scheduled visit on the boards this user sees, by person.
    from ... import schedule
    day = ctx.request.query.get("day", "") or ctx.now.date().isoformat()
    try:
        from datetime import date as _date, timedelta as _td
        d0 = _date.fromisoformat(day)
    except ValueError:
        d0 = ctx.now.date()
        day = d0.isoformat()
    entries = schedule.day(ctx.conn, boards, day)
    # §6.1 requirement 4: the day and the queue name tickets (number and the
    # start of the summary); on a restricted board that is a read, audited once
    # per board with a count. Unrestricted boards write nothing.
    listed: dict[str, int] = {}
    for r in list(unrouted_rows) + list(entries):
        listed[r["board_id"]] = listed.get(r["board_id"], 0) + 1
    for board_id, n in sorted(listed.items()):
        common.audit_restricted_read(
            ctx, board_id, detail=f"dispatch listed {n} ticket(s) on restricted board "
                                  f"{board_id} via {ctx.user.via}")
    by_member: dict[str, list] = {}
    for e in entries:
        by_member.setdefault(e["member"], []).append(e)
    # who is away or in a meeting that day, among the people who work these boards
    away: dict[str, list] = {}
    people = schedule.members_of(ctx.conn, sorted(boards)) + sorted(by_member)
    for b in schedule.blocks(ctx.conn, people, f"{day} 00:00", f"{(d0 + _td(days=1)).isoformat()} 00:00"):
        away.setdefault(b["member"], []).append(b)
    rows_html = "".join(
        f"<div class=dayrow><div class=who>{t.esc(m)}</div><div>" + "".join(
            f"<span class='slot away'>{t.esc(schedule.BLOCK_KINDS[b['kind']])}: {t.esc(b['name'])}</span>"
            for b in away.get(m, [])) + "".join(
            f"<a class=slot href='/ticket/{t.esc(e['work_item_id'])}' title='{t.esc(e['note'] or '')}'>"
            f"{t.esc(e['starts_at'][11:])}–{t.esc(e['ends_at'][11:])} · {t.esc(e['work_item_id'])} "
            f"{t.esc((e['summary'] or '')[:40])}"
            + (f" · {t.esc(e['status_name'])}" if e["status_name"] else "") + "</a>"
            for e in by_member.get(m, [])) + "</div></div>"
        for m in sorted(set(by_member) | set(away), key=str.lower)) or "<div class=muted>No visits booked for this day.</div>"
    prev_, next_ = (d0 - _td(days=1)).isoformat(), (d0 + _td(days=1)).isoformat()
    day_card = (
        "<div class=card><h3><svg class=ic aria-hidden=true><use href=#i-calendar></use></svg>The day</h3>"
        "<form method=get action='/dispatch' class=row style='margin-bottom:10px'>"
        f"<div style='flex:0 0 auto'><a class='btn ghost' href='/dispatch?day={prev_}'>‹</a></div>"
        f"<div style='flex:0 0 170px'><input type=date name=day value='{t.esc(day)}'></div>"
        f"<div style='flex:0 0 auto'><a class='btn ghost' href='/dispatch?day={next_}'>›</a></div>"
        "<div style='flex:0 0 auto'><button class=ghost type=submit>Show</button></div>"
        f"<div style='flex:0 0 auto'><a class='btn ghost' href='/schedule?week={t.esc(day)}'>Week view</a></div></form>"
        + rows_html + "</div>")
    body = (
        "<h1>Dispatch</h1><p class='sub'>The unrouted queue, ageing in plain sight, "
        "the day's visits, and who answers each board — the rota over the org chart.</p>"
        + queue + day_card + "".join(role_cards))
    return Response(body=t.page("Dispatch", body, user=ctx.user, active="dispatch"))


def assign(ctx):
    from .. import redirect
    from .. import HttpError
    from ... import board as engine
    f = ctx.request.form()
    work_item_id = f.get("work_item_id", "")
    to_board = f.get("to_board", "")
    owner = f.get("owner", "").strip() or None

    tk = ctx.conn.execute("SELECT board_id FROM ticket WHERE work_item_id = ?",
                         (work_item_id,)).fetchone()
    if tk is None:
        raise HttpError("404 Not Found", "No such ticket.")
    common.require_board(ctx, tk["board_id"])                 # may see the source
    common.require_board(ctx, to_board, need="WORK")          # may route into target

    engine.move(ctx.conn, work_item_id, to_board, at=ctx.now, actor=ctx.user.id,
                owner=owner, reason="routed from dispatch")
    ctx.conn.commit()
    return redirect("/dispatch")

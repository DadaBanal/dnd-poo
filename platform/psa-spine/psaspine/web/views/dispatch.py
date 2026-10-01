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
    owner_pick = common.owner_select(ctx.conn, [b["board_id"] for b in targets], None, me=ctx.user.id, blank="(the board's queue)")

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
                    + owner_pick +
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

    # The day board, in the shape of the reference PSA's Dispatch Portal: one
    # row per person who works the boards you see, one column per hour, every
    # visit and block in its hour, their Outlook busy time beside it. The
    # tickets waiting to be scheduled sit to the left; drag one onto a person's
    # hour and it is booked (the ticket becomes theirs if nobody has it); drag a
    # visit to another person or hour and it moves. Click an hour to book by
    # hand. Everything also works by the forms, without a mouse.
    from ... import calsync, members as _members, schedule
    from .schedule import slot_dialog
    from datetime import date as _date, timedelta as _td
    day = ctx.request.query.get("day", "") or ctx.now.date().isoformat()
    try:
        d0 = _date.fromisoformat(day)
    except ValueError:
        d0 = ctx.now.date()
        day = d0.isoformat()
    board_q = ctx.request.query.get("board", "")
    shown_boards = {board_q} if board_q in boards else boards
    mine = ctx.request.query.get("mine") == "1"
    lo, hi = f"{day} 00:00", f"{(d0 + _td(days=1)).isoformat()} 00:00"
    entries = schedule.day(ctx.conn, sorted(shown_boards), day)
    listed: dict[str, int] = {}
    for r in list(unrouted_rows) + list(entries):
        listed[r["board_id"]] = listed.get(r["board_id"], 0) + 1
    for board_id, n in sorted(listed.items()):
        common.audit_restricted_read(
            ctx, board_id, detail=f"dispatch listed {n} ticket(s) on restricted board "
                                  f"{board_id} via {ctx.user.via}")
    people = schedule.members_of(ctx.conn, sorted(shown_boards))
    for e in entries:
        if e["member"].lower() not in {p.lower() for p in people}:
            people.append(e["member"])
    people.sort(key=str.lower)
    if mine:
        people = [p for p in people if p.lower() == ctx.user.id.lower()] or [ctx.user.id]
    blocks = schedule.blocks(ctx.conn, people, lo, hi)
    outlook = calsync.busy(ctx.conn, people, lo, hi)
    can_book = any(common.may_access_board(ctx, b, need="WORK") for b in boards)
    back = f"/dispatch?day={day}" + (f"&board={board_q}" if board_q in boards else "") + ("&mine=1" if mine else "")
    HOURS = list(range(6, 21))

    def hour_of(stamp: str) -> int:
        return max(HOURS[0], min(HOURS[-1], int(stamp[11:13])))

    def strip(starts_at: str, ends_at: str, lane: int) -> str:
        """Where a chip sits: it starts in its hour's cell at the minute's
        offset and runs across the cells it covers, as the reference PSA's
        dispatch strip does. A chip on a later lane sits below the one above."""
        s_h = hour_of(starts_at) if starts_at >= lo else HOURS[0]
        s_min = int(starts_at[14:16]) if starts_at >= lo and starts_at[:10] == day else 0
        if ends_at[:10] != day or ends_at < lo:
            e_hours = HOURS[-1] + 1
        else:
            e_hours = min(HOURS[-1] + 1, int(ends_at[11:13]) + (int(ends_at[14:16]) / 60))
        left = s_min / 60
        width = max(0.5, e_hours - s_h - left)
        return f" style='left:calc({left:.2f} * 100% + 2px);width:calc({width:.2f} * 100% - 4px);top:{lane * 82 + 2}px'"

    def entry_chip(e, lane: int = 0) -> str:
        cls = ("sch visit" + (" tentative" if e["status_id"] == "TENTATIVE" else "") + (" done" if e["done_at"] else "")
               + (" clash" if e.get("_clash") else ""))
        drag = f" draggable=true data-drag='visit|{e['schedule_id']}'" if can_book and not e["done_at"] else ""
        drag += strip(e["starts_at"], e["ends_at"], lane)
        acts = ""
        if can_book:
            wid = t.esc(e["work_item_id"])
            def act(action, label, title):
                return (f"<form method=post action='/ticket/{wid}/schedule/{action}' class=inline>"
                        f"<input type=hidden name=schedule_id value='{e['schedule_id']}'><input type=hidden name=back value='{t.esc(back)}'>"
                        f"<button class='iconbtn x' type=submit title='{t.esc(title)}'>{label}</button></form>")
            acts = "<span class=acts>" + act("done", "✓" if not e["done_at"] else "↺", "Done" if not e["done_at"] else "Reopen")
            if not e["acknowledged_at"] and e["member"].lower() == ctx.user.id.lower():
                acts += act("ack", "👁", "Acknowledge: I have seen this")
            acts += "</span>"
        return (f"<div class='{cls}'{drag} title='{t.esc(e['note'] or '')}'>"
                f"<b>{t.esc(e['starts_at'][11:])}–{t.esc(e['ends_at'][11:])}</b> "
                f"<a href='/ticket/{t.esc(e['work_item_id'])}'>{t.esc(e['work_item_id'])}</a>"
                + (" ★" if e["is_lead"] else "") + (" <span class=pill>ack</span>" if e["acknowledged_at"] else "")
                + f"<br>{t.esc((e['summary'] or '')[:40])}"
                + (f"<br><span class=muted>{t.esc(e['status_name'] or '')}"
                   f"{' · ' + t.esc(e['location_name']) if e['location_name'] else ''}</span>" if e["status_name"] else "")
                + acts + "</div>")

    def block_chip(b, lane: int = 0) -> str:
        drag = f" draggable=true data-drag='block|{b['block_id']}'" if can_book else ""
        drag += strip(b["starts_at"], b["ends_at"], lane)
        span = (f"{b['starts_at'][11:]}–{b['ends_at'][11:]}" if b["starts_at"][:10] == b["ends_at"][:10] else "all day")
        return (f"<div class='sch block {b['kind'].lower()}{' clash' if b.get('_clash') else ''}'{drag}><b>{t.esc(schedule.BLOCK_KINDS[b['kind']])}</b> "
                f"{t.esc(span)}<br>{t.esc(b['name'])}</div>")

    from .schedule import OUTLOOK_WORD
    rows_html = []
    def lanes(items):
        """Overlapping chips go on separate lanes, first come first on top,
        and both are marked as a clash (the reference PSA outlines a
        conflict in red)."""
        out, ends = [], []
        items = sorted(items, key=lambda x: x["starts_at"])
        for a in items:
            a["_clash"] = any(b is not a and b["starts_at"] < a["ends_at"] and a["starts_at"] < b["ends_at"] for b in items)
        for it in items:
            for i, end in enumerate(ends):
                if end <= it["starts_at"]:
                    ends[i] = it["ends_at"]; out.append((it, i)); break
            else:
                ends.append(it["ends_at"]); out.append((it, len(ends) - 1))
        return out, len(ends)

    CAPACITY = 8.0                                   # hours a person is booked against, as the reference PSA's schedule capacity

    def hours_of(items) -> float:
        total = 0.0
        for it in items:
            s_, e_ = max(it["starts_at"], lo), min(it["ends_at"], hi)
            if e_ > s_:
                total += (schedule.parse_local(e_) - schedule.parse_local(s_)).total_seconds() / 3600
        return total

    def util_bar(booked: float) -> str:
        pct = min(100, int(round(booked / CAPACITY * 100)))
        cls = "lo" if pct < 50 else ("mid" if pct < 75 else "hi")
        return (f"<span class=utilt title='Booked today against {CAPACITY:g} h'>{booked:.1f}/{CAPACITY:.1f} {pct}%</span>"
                f"<span class='util {cls}'><i style='width:{pct}%'></i></span>")

    for m in people:
        mine_b = [b for b in blocks if b["member"].lower() == m.lower()]
        mine_o = [o for o in outlook if o["member"].lower() == m.lower()]
        mine_e = [e for e in entries if e["member"].lower() == m.lower()]
        placed, depth = lanes([dict(b, _k="b") for b in mine_b] + [dict(o, _k="o") for o in mine_o] + [dict(e, _k="e") for e in mine_e])
        cells = []
        for h in HOURS:
            inner = ""
            for it, lane in placed:
                start_h = hour_of(it["starts_at"]) if it["starts_at"] >= lo else HOURS[0]
                if start_h != h:
                    continue
                if it["_k"] == "b":
                    inner += block_chip(it, lane)
                elif it["_k"] == "o":
                    span = (f"{it['starts_at'][11:]}–{it['ends_at'][11:]}" if it["starts_at"][:10] == it["ends_at"][:10] else "all day")
                    inner += (f"<div class='sch block outlook'{strip(it['starts_at'], it['ends_at'], lane)} title='From their Outlook calendar'>"
                              f"<b>Outlook</b> {t.esc(span)}<br>{t.esc(OUTLOOK_WORD[it['show_as']])}</div>")
                else:
                    inner += entry_chip(it, lane)
            slot = f" data-slot='{t.esc(m)}|{day}|{h:02d}:00'" if can_book else ""
            now_cls = " now" if d0 == ctx.now.date() and ctx.now.hour == h else ""
            if now_cls:                              # the reference PSA's red line at the current time
                inner += f"<i class=nowline style='left:{ctx.now.minute / 60 * 100:.0f}%' title='Now'></i>"
            cells.append(f"<td class='hr{now_cls}'{slot}>{inner}</td>")
        me = m.lower() == ctx.user.id.lower()
        rows_html.append(f"<tr style='height:{(depth * 82 + 4) if depth else 48}px'><th class=who>{t.esc(_members.name_of(ctx.conn, m))}"
                         + (" <span class=pill>me</span>" if me else "") + util_bar(hours_of(mine_b + mine_e)) + f"</th>{''.join(cells)}</tr>")
    head = "".join(f"<th>{h:02d}:00</th>" for h in HOURS)
    grid = (f"<div class=schedwrap><table class='schedgrid dispatch'><thead><tr><th class=whoh>Who</th>{head}</tr></thead>"
            f"<tbody>{''.join(rows_html) or '<tr><td colspan=16 class=muted>Nobody works these boards yet.</td></tr>'}</tbody></table></div>")

    # To schedule: open tickets on the boards you work with no visit on this day, oldest first.
    todo_rows = []
    if shown_boards:
        q = ",".join("?" * len(shown_boards))
        todo_rows = ctx.conn.execute(
            "SELECT t.work_item_id, t.priority, t.opened_at, t.owner, t.board_id, w.name AS summary, b.display_name AS board"
            "  FROM ticket t JOIN work_item w ON w.work_item_id = t.work_item_id JOIN board b ON b.board_id = t.board_id"
            f" WHERE t.board_id IN ({q}) AND b.is_unrouted = 0 AND t.merged_into IS NULL"
            "   AND t.state NOT IN ('RESOLVED','CLOSED','CANCELLED')"
            "   AND NOT EXISTS (SELECT 1 FROM ticket_schedule s WHERE s.work_item_id = t.work_item_id AND s.starts_at < ?"
            "                   AND s.ends_at > ?)"
            " ORDER BY t.priority, t.opened_at", (*sorted(shown_boards), hi, lo)).fetchall()
    todo = "".join(
        f"<div class='todo' draggable={'true' if can_book else 'false'} data-drag='ticket|{t.esc(r['work_item_id'])}'>"
        f"{t.badge(r['priority'])} <a href='/ticket/{t.esc(r['work_item_id'])}'>{t.esc(r['work_item_id'])}</a> "
        f"<span class=muted>{t.esc(common.human_age(r['opened_at'], now=ctx.now))}</span>"
        f"<div>{t.esc((r['summary'] or '')[:60])}</div>"
        f"<div class=muted>{t.esc(r['board'])}" + (f" · {t.esc(_members.name_of(ctx.conn, r['owner']))}" if r["owner"] else " · unassigned") + "</div></div>"
        for r in todo_rows) or "<div class=muted>Nothing waiting to be scheduled on this day.</div>"
    board_opts = "<option value=''>All my boards</option>" + "".join(
        f"<option value='{t.esc(b['board_id'])}'{' selected' if b['board_id'] == board_q else ''}>{t.esc(b['display_name'])}</option>"
        for b in ctx.conn.execute("SELECT board_id, display_name FROM board WHERE COALESCE(inactive, 0) = 0 AND is_unrouted = 0"
                                  " ORDER BY display_name") if b["board_id"] in boards)
    prev_, next_ = (d0 - _td(days=1)).isoformat(), (d0 + _td(days=1)).isoformat()
    keep = f"&board={board_q}" if board_q in boards else ""
    keep += "&mine=1" if mine else ""
    bar = ("<form method=get action='/dispatch' class='row schedbar'>"
           f"<div style='flex:0 0 auto'><a class='btn ghost' href='/dispatch?day={prev_}{keep}' title='Previous day'>‹</a></div>"
           f"<div style='flex:0 0 170px'><input type=date name=day value='{t.esc(day)}' aria-label='Day'></div>"
           f"<div style='flex:0 0 auto'><a class='btn ghost' href='/dispatch?day={next_}{keep}' title='Next day'>›</a></div>"
           f"<div style='flex:0 0 200px'><select name=board aria-label='Board'>{board_opts}</select></div>"
           f"<div style='flex:0 0 auto'><label><input type=checkbox name=mine value=1{' checked' if mine else ''}> Only me</label></div>"
           "<div style='flex:0 0 auto'><button class=ghost type=submit>Show</button></div>"
           f"<div style='flex:0 0 auto'><a class='btn ghost' href='/dispatch?day={ctx.now.date().isoformat()}{keep}'>Today</a></div>"
           f"<div style='flex:0 0 auto'><a class='btn ghost' href='/schedule?week={t.esc(day)}'>Week</a></div></form>")
    msg, err = ctx.request.query.get("msg", ""), ctx.request.query.get("err", "")
    day_card = ((f"<div class='banner ok'>{t.esc(msg)}</div>" if msg else "")
                + (f"<div class='banner err'>{t.esc(err)}</div>" if err else "")
                + "<div class=dispatchwrap>"
                "<div class=card><h3>" + t.icon("inbox") + "To schedule</h3><p class=why>Open tickets with no visit on this "
                "day. Drag one onto a person's hour, or open it.</p><div class=todolist>" + todo + "</div></div>"
                "<div class=card><h3>" + t.icon("calendar") + f"The day · {d0.strftime('%A %d %b %Y')}</h3>" + bar + grid
                + "<p class=why style='margin-top:8px'>Drag a ticket onto an hour to book it; drag a visit to move it; "
                  "click an hour to book by hand. ✓ marks a visit done, 👁 acknowledges your own. Dashed is tentative; "
                  "grey Outlook chips are what their Outlook calendar says.</p></div></div>")
    body = (
        "<h1>Dispatch</h1><p class='sub'>Who is where today, what still needs a person, and who answers each board.</p>"
        + day_card + queue + "".join(role_cards))
    if can_book:
        body += slot_dialog(ctx, people, back=back)
    return Response(body=t.page("Dispatch", body, user=ctx.user, active="dispatch", live="schedule"))


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

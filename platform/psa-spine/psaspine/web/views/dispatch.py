"""The dispatch / triage view — the unrouted queue, and who answers.

The unrouted queue is where a ticket lands before anyone owns it, and a queue
that ages invisibly is how a P1 waits. So it ages here in plain sight, coloured
by the same SLA logic as the board. Beside it, the four board roles and — over
the top of them — the rota's answer to "who is on call right now", because at
02:00 the name that matters is whoever is on shift, not whoever the org chart
names.
"""
from __future__ import annotations

import urllib.parse

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

    body = ("<h1>Dispatch</h1><p class='sub'>Who is where today, what still needs a person, and who answers each board.</p>"
            + _board(ctx, boards, unrouted_rows) + queue + "".join(role_cards))
    return Response(body=t.page("Dispatch", body, user=ctx.user, active="dispatch", live="schedule"))


HOURS = list(range(6, 21))          # the day grid's columns, 06:00 to 20:00
CAPACITY = 8.0                      # hours a person is booked against, as the reference PSA's capacity
LANE = 82                           # px per lane of overlapping chips


def _board(ctx, boards, unrouted_rows) -> str:
    """The Dispatch Portal, in the reference PSA's shape (Dada, 8 Oct 2026:
    "make it look like what connectwise looks like and function like
    connectwise"; confirmed: the day grid, a Service Tickets table, Day + Week).

    Resources are rows with their name and hours booked; the day's hours run
    across with half-hour lines; a visit is a block coloured by its status
    (firm filled, tentative outlined, done green with a tick) naming the
    ticket, its summary and its company. A ticket dragged from the Service
    Tickets table onto an hour books it; a visit dragged moves; its right
    edge dragged changes its end; a right-click offers Open, Done,
    Acknowledge and Delete; a double-click opens the ticket. Week: the seven
    days as columns, each day's visits listed. Everything also works by the
    forms, without a mouse.
    """
    from ... import calsync, members as _members, schedule
    from .schedule import OUTLOOK_WORD, slot_dialog
    from datetime import date as _date, timedelta as _td
    q = ctx.request.query
    view = "week" if q.get("view") == "week" else "day"
    day = q.get("day", "") or ctx.now.date().isoformat()
    try:
        d0 = _date.fromisoformat(day)
    except ValueError:
        d0 = ctx.now.date()
        day = d0.isoformat()
    board_q = q.get("board", "")
    shown_boards = {board_q} if board_q in boards else boards
    mine = q.get("mine") == "1"
    monday = d0 - _td(days=d0.weekday())
    if view == "week":
        lo, hi = f"{monday.isoformat()} 00:00", f"{(monday + _td(days=7)).isoformat()} 00:00"
        data = schedule.week(ctx.conn, sorted(shown_boards), monday)
        entries = data["visits"]
    else:
        lo, hi = f"{day} 00:00", f"{(d0 + _td(days=1)).isoformat()} 00:00"
        entries = schedule.day(ctx.conn, sorted(shown_boards), day)
    listed: dict[str, int] = {}
    for r in list(unrouted_rows) + list(entries):
        listed[r["board_id"]] = listed.get(r["board_id"], 0) + 1
    for board_id, n in sorted(listed.items()):
        common.audit_restricted_read(
            ctx, board_id, detail=f"dispatch listed {n} ticket(s) on restricted board {board_id} via {ctx.user.via}")
    people = schedule.members_of(ctx.conn, sorted(shown_boards))
    for e in entries:
        if e["member"].lower() not in {p.lower() for p in people}:
            people.append(e["member"])
    people.sort(key=str.lower)
    everyone = list(people)
    # 063: whose rows. `who=` in the URL shows a set once; the dispatcher's
    # saved view applies when the URL says nothing; "Only me" beats both.
    who_q = [w.strip().lower() for w in q.get("who", "").split(",") if w.strip()]
    saved = schedule.view_of(ctx.conn, ctx.user.id)
    chosen = who_q or (saved["people"] if saved and q.get("who") is None else [])
    if chosen:
        people = [p for p in people if p.lower() in chosen] or people
    if mine:
        people = [p for p in people if p.lower() == ctx.user.id.lower()] or [ctx.user.id]
    blocks = schedule.blocks(ctx.conn, people, lo, hi)
    outlook = calsync.busy(ctx.conn, people, lo, hi)
    can_book = any(common.may_access_board(ctx, b, need="WORK") for b in boards)
    keep = (f"&board={board_q}" if board_q in boards else "") + ("&mine=1" if mine else "") \
        + (f"&who={t.esc(','.join(who_q))}" if who_q else "")
    back = f"/dispatch?day={day}" + (f"&view=week" if view == "week" else "") + keep
    name_of = lambda m: _members.name_of(ctx.conn, m)  # noqa: E731

    def hours_of(items) -> float:
        total = 0.0
        for it in items:
            s_, e_ = max(it["starts_at"], lo), min(it["ends_at"], hi)
            if e_ > s_:
                total += (schedule.parse_local(e_) - schedule.parse_local(s_)).total_seconds() / 3600
        return total

    def who_cell(m, booked: float, capacity: float) -> str:
        pct = min(100, int(round(booked / capacity * 100))) if capacity else 0
        cls = "lo" if pct < 50 else ("mid" if pct < 75 else "hi")
        me = m.lower() == ctx.user.id.lower()
        return (f"<th class=who><b class=rname>{t.esc(name_of(m))}</b>" + (" <span class=pill>me</span>" if me else "")
                + f"<span class=utilt title='Booked against {capacity:g} h'>{booked:.1f} / {capacity:.1f} h · {pct}%</span>"
                f"<span class='util {cls}'><i style='width:{pct}%'></i></span></th>")

    def menu_attrs(e) -> str:
        """What the right-click menu and a double-click need: the ticket, the
        visit, whether it is done, whether this person may work it and
        acknowledge it."""
        can_ack = not e["acknowledged_at"] and e["member"].lower() == ctx.user.id.lower()
        return (f" data-menu='{t.esc(e['work_item_id'])}|{e['schedule_id']}|{1 if e['done_at'] else 0}|{1 if can_book else 0}"
                f"|{1 if can_ack else 0}' data-span='{t.esc(e['starts_at'][:16].replace(' ', 'T'))}|{t.esc(e['ends_at'][:16].replace(' ', 'T'))}'")

    def visit_classes(e) -> str:
        st = (e["status_id"] or "").lower()
        clash = e["_clash"] if "_clash" in e.keys() else False          # set by lanes() on the day's copies only
        return ("sch visit st-" + (st or "firm") + (" tentative" if e["status_id"] == "TENTATIVE" else "")
                + (" done" if e["done_at"] else "") + (" clash" if clash else ""))

    def visit_words(e, *, long: bool = True) -> str:
        tail = " · ".join(x for x in (e["entity"] if "entity" in e.keys() and e["entity"] else "", e["status_name"] or "",
                                     e["location_name"] or "") if x)
        return (f"<b>{t.esc(e['starts_at'][11:16])}–{t.esc(e['ends_at'][11:16])}</b> "
                f"<a href='/ticket/{t.esc(e['work_item_id'])}'>{t.esc(e['work_item_id'])}</a>"
                + (" ★" if e["is_lead"] else "") + (" <span class=pill>ack</span>" if e["acknowledged_at"] else "")
                + f"<br>{t.esc((e['summary'] or '')[:40 if long else 30])}"
                + (f"<br><span class=muted>{t.esc(tail)}</span>" if tail else ""))

    # ------------------------------------------------------------- the day
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
        return f" style='left:calc({left:.2f} * 100% + 2px);width:calc({width:.2f} * 100% - 4px);top:{lane * LANE + 2}px'"

    def entry_chip(e, lane: int = 0) -> str:
        drag = f" draggable=true data-drag='visit|{e['schedule_id']}'" if can_book and not e["done_at"] else ""
        drag += strip(e["starts_at"], e["ends_at"], lane) + menu_attrs(e)
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
            if not e["done_at"]:
                acts += "<i class=rz title='Drag to change when it ends'></i>"
        return (f"<div class='{visit_classes(e)}'{drag} title='{t.esc(e['note'] or '')}'>" + visit_words(e) + acts + "</div>")

    def block_chip(b, lane: int = 0) -> str:
        drag = f" draggable=true data-drag='block|{b['block_id']}'" if can_book else ""
        drag += strip(b["starts_at"], b["ends_at"], lane)
        span = (f"{b['starts_at'][11:]}–{b['ends_at'][11:]}" if b["starts_at"][:10] == b["ends_at"][:10] else "all day")
        return (f"<div class='sch block {b['kind'].lower()}{' clash' if b.get('_clash') else ''}'{drag}><b>{t.esc(schedule.BLOCK_KINDS[b['kind']])}</b> "
                f"{t.esc(span)}<br>{t.esc(b['name'])}</div>")

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

    def day_grid() -> str:
        rows_html = []
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
            rows_html.append(f"<tr style='height:{(depth * LANE + 4) if depth else 48}px'>"
                             + who_cell(m, hours_of(mine_b + mine_e), CAPACITY) + "".join(cells) + "</tr>")
        head = "".join(f"<th>{h:02d}:00</th>" for h in HOURS)
        return (f"<div class=schedwrap><table class='schedgrid dispatch'><thead><tr><th class=whoh>Resource</th>{head}</tr></thead>"
                f"<tbody>{''.join(rows_html) or '<tr><td colspan=16 class=muted>Nobody works these boards yet.</td></tr>'}</tbody></table></div>")

    # ------------------------------------------------------------ the week
    def week_grid() -> str:
        days = [monday + _td(days=i) for i in range(7)]

        def cell(m, d):
            dlo, dhi = f"{d.isoformat()} 00:00", f"{(d + _td(days=1)).isoformat()} 00:00"
            chips = []
            for b in blocks:
                if b["member"].lower() == m.lower() and b["starts_at"] < dhi and b["ends_at"] > dlo:
                    span = (f"{b['starts_at'][11:]}–{b['ends_at'][11:]}" if b["starts_at"][:10] == b["ends_at"][:10]
                            else "all day" if b["starts_at"] <= dlo and b["ends_at"] >= dhi else
                            (f"from {b['starts_at'][11:]}" if b["starts_at"] > dlo else f"until {b['ends_at'][11:]}"))
                    drag = f" draggable=true data-drag='block|{b['block_id']}'" if can_book else ""
                    chips.append(f"<div class='sch block {b['kind'].lower()}'{drag}><b>{t.esc(schedule.BLOCK_KINDS[b['kind']])}</b> "
                                 f"{t.esc(span)}<br>{t.esc(b['name'])}</div>")
            for e in entries:
                if e["member"].lower() == m.lower() and e["starts_at"][:10] == d.isoformat():
                    drag = f" draggable=true data-drag='visit|{e['schedule_id']}'" if can_book and not e["done_at"] else ""
                    chips.append(f"<div class='{visit_classes(e)}'{drag}{menu_attrs(e)} title='{t.esc(e['note'] or '')}'>"
                                 + visit_words(e, long=False) + "</div>")
            for o in outlook:
                if o["member"].lower() == m.lower() and o["starts_at"] < dhi and o["ends_at"] > dlo:
                    span = (f"{o['starts_at'][11:]}–{o['ends_at'][11:]}" if o["starts_at"][:10] == o["ends_at"][:10] else "all day")
                    chips.append(f"<div class='sch block outlook' title='From their Outlook calendar'><b>Outlook</b> {t.esc(span)}"
                                 f"<br>{t.esc(OUTLOOK_WORD[o['show_as']])}</div>")
            slot = f" data-slot='{t.esc(m)}|{d.isoformat()}'" if can_book else ""
            return f"<td class='wk{' today' if d == ctx.now.date() else ''}'{slot}>{''.join(chips)}</td>"

        rows_html = "".join(
            "<tr>" + who_cell(m, hours_of([b for b in blocks if b["member"].lower() == m.lower()]
                                          + [e for e in entries if e["member"].lower() == m.lower()]), CAPACITY * 5)
            + "".join(cell(m, d) for d in days) + "</tr>" for m in people)
        head = "".join(f"<th class='{'today' if d == ctx.now.date() else ''}'>{d.strftime('%a %d %b')}</th>" for d in days)
        return (f"<div class=schedwrap><table class='schedgrid dispatch week'><thead><tr><th class=whoh>Resource</th>{head}</tr></thead>"
                f"<tbody>{rows_html or '<tr><td colspan=8 class=muted>Nobody works these boards yet.</td></tr>'}</tbody></table></div>")

    # ------------------------------------------------ the Service Tickets table
    search = " ".join(q.get("q", "").split())[:80]
    status_q = q.get("st", "")
    include_scheduled = q.get("all") == "1"
    todo_rows, status_names = [], []
    if shown_boards:
        marks = ",".join("?" * len(shown_boards))
        status_names = [r[0] for r in ctx.conn.execute(
            f"SELECT DISTINCT name FROM board_status WHERE board_id IN ({marks}) AND is_closed = 0 ORDER BY name",
            tuple(sorted(shown_boards)))]
        sql = ("SELECT t.work_item_id, t.priority, t.opened_at, t.owner, t.board_id, w.name AS summary, b.display_name AS board,"
               "       e.name AS entity, s.name AS status"
               "  FROM ticket t JOIN work_item w ON w.work_item_id = t.work_item_id JOIN board b ON b.board_id = t.board_id"
               "  LEFT JOIN entity e ON e.entity_id = w.entity_id"
               "  LEFT JOIN board_status s ON s.board_status_id = t.board_status_id"
               f" WHERE t.board_id IN ({marks}) AND b.is_unrouted = 0 AND t.merged_into IS NULL"
               "   AND t.state NOT IN ('RESOLVED','CLOSED','CANCELLED')")
        params: list = [*sorted(shown_boards)]
        if not include_scheduled:
            sql += ("   AND NOT EXISTS (SELECT 1 FROM ticket_schedule x WHERE x.work_item_id = t.work_item_id"
                    "                   AND x.starts_at < ? AND x.ends_at > ?)")
            params += [hi, lo]
        if status_q:
            sql += " AND s.name = ?"
            params.append(status_q)
        if search:
            like = f"%{search.replace('%', '').replace('_', '')}%"
            sql += " AND (t.work_item_id LIKE ? OR w.name LIKE ? OR e.name LIKE ?)"
            params += [like, like, like]
        sql += " ORDER BY t.priority, t.opened_at LIMIT 300"
        todo_rows = ctx.conn.execute(sql, params).fetchall()
    rows = "".join(
        f"<tr draggable={'true' if can_book else 'false'} data-drag='ticket|{t.esc(r['work_item_id'])}' data-q='{t.esc((r['work_item_id'] + ' ' + (r['summary'] or '') + ' ' + (r['entity'] or '')).lower())}'>"
        f"<td><a href='/ticket/{t.esc(r['work_item_id'])}'>{t.esc(r['work_item_id'])}</a></td>"
        f"<td class=stsum title='{t.esc(r['summary'] or '')}'>{t.esc((r['summary'] or '')[:70])}</td>"
        f"<td class=muted>{t.esc(r['entity'] or '—')}</td><td>{t.badge(r['priority'])}</td>"
        f"<td class=muted>{t.esc(r['status'] or '')}</td>"
        f"<td class=muted>{t.esc(name_of(r['owner'])) if r['owner'] else 'unassigned'}</td>"
        f"<td class=muted>{t.esc(common.human_age(r['opened_at'], now=ctx.now))}</td></tr>"
        for r in todo_rows) or ("<tr><td colspan=7 class=muted>" + ("Nothing matches." if (search or status_q) else
                                                                   "Nothing waiting to be scheduled on this day.") + "</td></tr>")
    st_opts = "<option value=''>Any status</option>" + "".join(
        f"<option{' selected' if n == status_q else ''}>{t.esc(n)}</option>" for n in status_names)
    hidden = (f"<input type=hidden name=day value='{t.esc(day)}'>" + (f"<input type=hidden name=view value=week>" if view == "week" else "")
              + (f"<input type=hidden name=board value='{t.esc(board_q)}'>" if board_q in boards else "")
              + ("<input type=hidden name=mine value=1>" if mine else "")
              + (f"<input type=hidden name=who value='{t.esc(','.join(who_q))}'>" if who_q else ""))
    tickets_panel = (
        "<div class='card stpanel' id=stickets><div class=sthead><h3 style='margin:0'>" + t.icon("inbox")
        + f"Service Tickets <span class=muted>{len(todo_rows)}</span></h3>"
        "<button type=button class='iconbtn stfold' title='Hide the tickets' aria-label='Hide the tickets'>‹</button></div>"
        f"<form method=get action='/dispatch' class='row stfilter'>{hidden}"
        f"<div><input name=q value='{t.esc(search)}' placeholder='Search ticket, summary, company' aria-label='Search' id=stsearch></div>"
        f"<div style='flex:0 0 150px'><select name=st aria-label='Status'>{st_opts}</select></div>"
        f"<div style='flex:0 0 auto'><label class=tick><input type=checkbox name=all value=1{' checked' if include_scheduled else ''}> Include scheduled</label></div>"
        "<div style='flex:0 0 auto'><button class='ghost small' type=submit>Filter</button></div></form>"
        "<div class='tablewrap stwrap'><table class=sttable><thead><tr><th>Ticket #</th><th>Summary</th><th>Company</th><th>Pri</th>"
        f"<th>Status</th><th>Owner</th><th>Age</th></tr></thead><tbody>{rows}</tbody></table></div>"
        "<p class=why style='margin:8px 0 0'>Drag a row onto a resource's hour to book it, or open the ticket.</p></div>")

    # --------------------------------------------------------------- the bar
    board_opts = "<option value=''>All my boards</option>" + "".join(
        f"<option value='{t.esc(b['board_id'])}'{' selected' if b['board_id'] == board_q else ''}>{t.esc(b['display_name'])}</option>"
        for b in ctx.conn.execute("SELECT board_id, display_name FROM board WHERE COALESCE(inactive, 0) = 0 AND is_unrouted = 0"
                                  " ORDER BY display_name") if b["board_id"] in boards)
    step = _td(days=7) if view == "week" else _td(days=1)
    prev_, next_ = (d0 - step).isoformat(), (d0 + step).isoformat()
    vq = "&view=week" if view == "week" else ""
    ticks = "".join(
        f"<label class=tick><input type=checkbox name=p value='{t.esc(p)}'{' checked' if p.lower() in {x.lower() for x in people} else ''}>"
        f" {t.esc(name_of(p))}" + (f" <span class=muted>{t.esc(p)}</span>" if name_of(p).lower() != p.lower() else "")
        + "</label>" for p in everyone)
    showing = (f"{len(people)} of {len(everyone)}" if len(people) != len(everyone) else f"all {len(everyone)}")
    people_dlg = (
        "<dialog id=whodlg class=card style='max-width:560px;width:95%'><form method=dialog class=dlghead><h3 style='margin:0'>"
        + t.icon("users") + "Who is on the board</h3><button type=submit class=iconbtn aria-label=Close>" + t.icon("x") + "</button></form>"
        f"<form method=get action='/dispatch' id=whoform><input type=hidden name=day value='{t.esc(day)}'>"
        + ("<input type=hidden name=view value=week>" if view == "week" else "")
        + (f"<input type=hidden name=board value='{t.esc(board_q)}'>" if board_q in boards else "")
        + "<p class=why>Tick the people whose rows you want. <b>Show</b> is for now; <b>Save as my view</b> keeps it "
          "whenever you open Dispatch; <b>Clear</b> goes back to everyone on your boards.</p>"
        "<p class=row style='gap:6px'><button type=button class='ghost small' data-tick=1>All</button>"
        "<button type=button class='ghost small' data-tick=0>None</button></p>"
        f"<div class=ticks>{ticks}</div>"
        "<p class=row style='margin-top:12px;gap:8px'><button type=submit name=show value=1>Show</button>"
        "<button type=submit formmethod=post formaction='/dispatch/view' class=ghost>Save as my view</button>"
        + ("<button type=submit formmethod=post formaction='/dispatch/view' name=clear value=1 class=ghost>Clear my view</button>" if saved else "")
        + "</p></form></dialog>")
    who_btn = (f"<div style='flex:0 0 auto'><button type=button class=ghost data-open=whodlg title='Choose whose rows to show'>"
               + t.icon("users") + f" People <span class=muted>{showing}</span>" + ("" if not saved or who_q else " · saved") + "</button></div>")
    title = d0.strftime("%A %d %b %Y") if view == "day" else f"Week of {monday.strftime('%d %b')} – {(monday + _td(days=6)).strftime('%d %b %Y')}"
    bar = ("<form method=get action='/dispatch' class='row schedbar'>"
           "<div style='flex:0 0 auto'><span class=seg>"
           f"<a class='btn{' on' if view == 'day' else ' ghost'}' href='/dispatch?day={day}{keep}'>Day</a>"
           f"<a class='btn{' on' if view == 'week' else ' ghost'}' href='/dispatch?day={day}&view=week{keep}'>Week</a></span></div>"
           + ("<input type=hidden name=view value=week>" if view == "week" else "")
           + f"<div style='flex:0 0 auto'><a class='btn ghost' href='/dispatch?day={prev_}{vq}{keep}' title='Previous'>‹</a></div>"
           f"<div style='flex:0 0 160px'><input type=date name=day value='{t.esc(day)}' aria-label='Day'></div>"
           f"<div style='flex:0 0 auto'><a class='btn ghost' href='/dispatch?day={next_}{vq}{keep}' title='Next'>›</a></div>"
           f"<div style='flex:0 0 auto'><a class='btn ghost' href='/dispatch?day={ctx.now.date().isoformat()}{vq}{keep}'>Today</a></div>"
           f"<div style='flex:0 0 200px'><select name=board aria-label='Board'>{board_opts}</select></div>"
           f"<div style='flex:0 0 auto'><label class=tick><input type=checkbox name=mine value=1{' checked' if mine else ''}> Only me</label></div>"
           + (f"<input type=hidden name=who value='{t.esc(','.join(who_q))}'>" if who_q else "") + who_btn +
           "<div style='flex:0 0 auto'><button class=ghost type=submit>Show</button></div>"
           "<div style='flex:0 0 auto'><button type=button class='ghost stshow' title='Show the tickets'>" + t.icon("inbox") + " Tickets</button></div>"
           "</form>")
    legend = ("<p class='why dlegend' style='margin-top:8px'><span class='sch visit st-firm'>Firm</span>"
              "<span class='sch visit st-tentative tentative'>Tentative</span><span class='sch visit done'>Done</span>"
              "<span class='sch block outlook'>Outlook</span> Drag a ticket onto an hour to book it; drag a visit to move it; "
              "drag its right edge to change when it ends; right-click a visit for Open, Done, Acknowledge and Delete; "
              "double-click opens the ticket; click an empty hour to book by hand.</p>")
    msg, err = q.get("msg", ""), q.get("err", "")
    out = ((f"<div class='banner ok'>{t.esc(msg)}</div>" if msg else "")
           + (f"<div class='banner err'>{t.esc(err)}</div>" if err else "")
           + "<div class=dispatchwrap>" + tickets_panel
           + "<div class='card dgrid'><h3>" + t.icon("calendar") + f"{t.esc(title)}</h3>" + bar
           + (day_grid() if view == "day" else week_grid()) + legend + "</div></div>")
    if can_book:
        out += slot_dialog(ctx, people, back=back)
    return out + people_dlg


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


def view(ctx):
    """063: keep or forget the dispatcher's own set of people."""
    from .. import redirect
    from ... import schedule
    f = ctx.request.form()
    day = f.get("day", "") or ctx.now.date().isoformat()
    board = f.get("board", "") or None
    back = f"/dispatch?day={urllib.parse.quote(day)}" + (f"&board={urllib.parse.quote(board)}" if board else "")
    if f.get("clear") == "1":
        schedule.clear_view(ctx.conn, ctx.user.id)
        ctx.conn.commit()
        return redirect(back + "&msg=" + urllib.parse.quote("Your view is cleared: everyone on your boards."))
    try:
        kept = schedule.save_view(ctx.conn, ctx.user.id, ctx.request.form_list("p"), board, at=ctx.now)
    except ValueError as exc:
        ctx.conn.rollback()
        return redirect(back + "&err=" + urllib.parse.quote(str(exc)))
    ctx.conn.commit()
    return redirect(back + "&msg=" + urllib.parse.quote(f"Saved: {len(kept)} people on your Dispatch board."))

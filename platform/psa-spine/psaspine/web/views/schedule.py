"""The Schedule: a week of the people who work the boards you see, and what holds them.

The reference PSA's schedule board, server-rendered: one row per member, one
column per day, each visit a chip (its time, ticket, status and where; dashed
while tentative, struck through when done) and each block (time off, a meeting,
an activity) a chip of its own. From here a dispatcher books a visit on any
open ticket they may work, and anyone on a board adds or removes time off and
meetings. No drag and drop: a ward PC and a phone both work it with forms.
"""
from __future__ import annotations

import urllib.parse
from datetime import date, datetime, timedelta

from ... import schedule
from .. import templates as t
from . import common


OUTLOOK_WORD = {"BUSY": "Busy", "TENTATIVE": "Tentative", "OOF": "Out of office", "WORKING_ELSEWHERE": "Working elsewhere"}


def _monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _back(week: str = "", **q):
    from .. import redirect
    q = {k: v for k, v in q.items() if v}
    if week:
        q["week"] = week
    return redirect("/schedule" + ("?" + urllib.parse.urlencode(q) if q else ""))


def index(ctx):
    from .. import Response
    common.require_module(ctx, "SCHEDULE")
    boards = common.board_ids_for(ctx)
    q = ctx.request.query
    try:
        start = _monday(date.fromisoformat(q.get("week", "")))
    except ValueError:
        start = _monday(ctx.now.date())
    board = q.get("board", "")
    shown = {board} if board in boards else boards
    mine = q.get("mine") == "1"
    data = schedule.week(ctx.conn, sorted(shown), start)
    visits, blocks, people = data["visits"], data["blocks"], data["members"]
    if mine:
        people = [p for p in people if p.lower() == ctx.user.id.lower()] or [ctx.user.id]
    # §6.1 requirement 4: visits name tickets; on a restricted board that is a read, audited
    listed: dict[str, int] = {}
    for v in visits:
        listed[v["board_id"]] = listed.get(v["board_id"], 0) + 1
    for board_id, n in sorted(listed.items()):
        common.audit_restricted_read(ctx, board_id, detail=f"schedule listed {n} visit(s) on restricted board "
                                                            f"{board_id} via {ctx.user.via}")
    days = [start + timedelta(days=i) for i in range(7)]
    from ... import calsync
    outlook = calsync.busy(ctx.conn, people, f"{start.isoformat()} 00:00", f"{(start + timedelta(days=7)).isoformat()} 00:00")
    can_book = any(common.may_access_board(ctx, b, need="WORK") for b in boards)

    def cell(member: str, d: date) -> str:
        lo, hi = f"{d.isoformat()} 00:00", f"{(d + timedelta(days=1)).isoformat()} 00:00"
        chips = []
        for b in blocks:
            if b["member"].lower() == member.lower() and b["starts_at"] < hi and b["ends_at"] > lo:
                span = (f"{b['starts_at'][11:]}–{b['ends_at'][11:]}" if b["starts_at"][:10] == b["ends_at"][:10]
                        else "all day" if b["starts_at"] <= lo and b["ends_at"] >= hi else
                        (f"from {b['starts_at'][11:]}" if b["starts_at"] > lo else f"until {b['ends_at'][11:]}"))
                remove = (f"<form method=post action='/schedule/block/remove' class=inline>"
                          f"<input type=hidden name=block_id value='{b['block_id']}'>"
                          f"<input type=hidden name=week value='{start.isoformat()}'>"
                          "<button class='iconbtn x' type=submit title='Remove' aria-label='Remove'>×</button></form>"
                          if can_book else "")
                chips.append(f"<div class='sch block {b['kind'].lower()}'{' draggable=true data-drag=' + chr(39) + 'block|' + str(b['block_id']) + chr(39) if can_book else ''}><b>{t.esc(schedule.BLOCK_KINDS[b['kind']])}</b> "
                             f"{t.esc(span)}<br>{t.esc(b['name'])}{remove}</div>")
        for v in visits:
            if v["member"].lower() == member.lower() and v["starts_at"][:10] == d.isoformat():
                cls = "sch visit" + (" tentative" if v["status_id"] == "TENTATIVE" else "") + (" done" if v["done_at"] else "")
                drag = f" draggable=true data-drag='visit|{v['schedule_id']}'" if can_book and not v["done_at"] else ""
                chips.append(
                    f"<a class='{cls}'{drag} href='/ticket/{t.esc(v['work_item_id'])}' title='{t.esc(v['note'] or '')}'>"
                    f"<b>{t.esc(v['starts_at'][11:])}–{t.esc(v['ends_at'][11:])}</b> {t.esc(v['work_item_id'])}"
                    + (" ★" if v["is_lead"] else "") + f"<br>{t.esc((v['summary'] or '')[:36])}"
                    + (f"<br><span class=muted>{t.esc(v['status_name'] or '')}"
                       f"{' · ' + t.esc(v['location_name']) if v['location_name'] else ''}</span>") + "</a>")
        for o in outlook:
            if o["member"].lower() == member.lower() and o["starts_at"] < hi and o["ends_at"] > lo:
                span = (f"{o['starts_at'][11:]}–{o['ends_at'][11:]}" if o["starts_at"][:10] == o["ends_at"][:10] else "all day")
                chips.append(f"<div class='sch block outlook' title='From their Outlook calendar'><b>Outlook</b> {t.esc(span)}"
                             f"<br>{t.esc(OUTLOOK_WORD[o['show_as']])}</div>")
        slot = f" data-slot='{t.esc(member)}|{d.isoformat()}'" if can_book else ""
        return f"<td class='{'today' if d == ctx.now.date() else ''}'{slot}>{''.join(chips)}</td>"

    head = "".join(f"<th class='{'today' if d == ctx.now.date() else ''}'>{d.strftime('%a %d %b')}</th>" for d in days)
    from ... import presence as _presence
    where = _presence.all_(ctx.conn, people)
    body_rows = "".join(
        f"<tr><th class=who>{t.esc(m)}" + (f"<div class=muted style='font-weight:400'>{t.esc(_presence.word(where[m]))}</div>" if where[m] else "")
        + f"</th>{''.join(cell(m, d) for d in days)}</tr>" for m in people)
    board_opts = "<option value=''>All my boards</option>" + "".join(
        f"<option value='{t.esc(b['board_id'])}'{' selected' if b['board_id'] == board else ''}>{t.esc(b['display_name'])}</option>"
        for b in ctx.conn.execute("SELECT board_id, display_name FROM board WHERE COALESCE(inactive, 0) = 0"
                                  " ORDER BY display_name") if b["board_id"] in boards)
    prev_, next_ = (start - timedelta(days=7)).isoformat(), (start + timedelta(days=7)).isoformat()
    keep = {"board": board, "mine": "1" if mine else ""}
    qs = lambda **k: urllib.parse.urlencode({x: y for x, y in (keep | k).items() if y})
    nav = ("<form method=get action='/schedule' class='row schedbar'>"
           f"<div style='flex:0 0 auto'><a class='btn ghost' href='/schedule?{qs(week=prev_)}' title='Previous week'>‹</a></div>"
           f"<div style='flex:0 0 170px'><input type=date name=week value='{start.isoformat()}' aria-label='Week of'></div>"
           f"<div style='flex:0 0 auto'><a class='btn ghost' href='/schedule?{qs(week=next_)}' title='Next week'>›</a></div>"
           f"<div style='flex:0 0 200px'><select name=board aria-label='Board'>{board_opts}</select></div>"
           f"<div style='flex:0 0 auto'><label><input type=checkbox name=mine value=1{' checked' if mine else ''}> Only me</label></div>"
           "<div style='flex:0 0 auto'><button class=ghost type=submit>Show</button></div>"
           f"<div style='flex:0 0 auto'><a class='btn ghost' href='/schedule?{qs(week=_monday(ctx.now.date()).isoformat())}'>This week</a></div>"
           "<div style='flex:0 0 auto'><a class='btn ghost' href='/inout'>In / out</a></div></form>")
    grid = (f"<div class=schedwrap><table class=schedgrid><thead><tr><th>Who</th>{head}</tr></thead>"
            f"<tbody>{body_rows or '<tr><td colspan=8 class=muted>Nobody works these boards yet.</td></tr>'}</tbody></table></div>")
    forms = ""
    if can_book:
        at0 = (ctx.now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
        statuses = "".join(f"<option value='{t.esc(x['status_id'])}'{' selected' if x['is_default'] else ''}>{t.esc(x['name'])}</option>"
                           for x in schedule.statuses(ctx.conn))
        places = "<option value=''>(not said)</option>" + "".join(
            f"<option value='{t.esc(x['location_id'])}'>{t.esc(x['name'])}</option>" for x in schedule.locations(ctx.conn))
        who = "".join(f"<option value='{t.esc(m)}'>" for m in data["members"])
        forms = (
            "<div class=grid2>"
            "<div class=card><h3>" + t.icon("calendar") + "Book a visit</h3>"
            "<form method=post action='/schedule/book' class=grid2>"
            f"<input type=hidden name=week value='{start.isoformat()}'>"
            f"<div><label>Ticket</label>{t.ticket_pick('work_item_id', 'Search a ticket, or type its number', required=True)}</div>"
            f"<div><label>Who</label><input name=member list=schedwho required><datalist id=schedwho>{who}</datalist></div>"
            f"<div><label>From</label><input type=datetime-local name=starts_at value='{at0.strftime('%Y-%m-%dT%H:%M')}' required></div>"
            f"<div><label>To</label><input type=datetime-local name=ends_at value='{(at0 + timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M')}' required></div>"
            f"<div><label>Status</label><select name=status_id>{statuses}</select></div>"
            f"<div><label>Where</label><select name=location_id>{places}</select></div>"
            "<div style='grid-column:1/-1'><label><input type=checkbox name=allow_conflict value=1> Allow a double booking</label> "
            "<button type=submit>Book</button></div></form></div>"
            "<div class=card><h3>" + t.icon("users") + "Time off, a meeting or an activity</h3>"
            "<form method=post action='/schedule/block' class=grid2>"
            f"<input type=hidden name=week value='{start.isoformat()}'>"
            f"<div><label>Who</label><input name=member list=schedwho value='{t.esc(ctx.user.id)}' required></div>"
            "<div><label>What</label><select name=kind>" + "".join(
                f"<option value='{k}'>{v}</option>" for k, v in schedule.BLOCK_KINDS.items()) + "</select></div>"
            f"<div><label>From</label><input type=datetime-local name=starts_at value='{ctx.now.strftime('%Y-%m-%d')}T08:00' required></div>"
            f"<div><label>To</label><input type=datetime-local name=ends_at value='{ctx.now.strftime('%Y-%m-%d')}T17:00' required></div>"
            "<div style='grid-column:1/-1'><label>Name</label><input name=name maxlength=120 placeholder='Annual leave; vendor meeting; stocktake'></div>"
            "<div style='grid-column:1/-1'><label><input type=checkbox name=allow_conflict value=1> Allow it over a booked visit</label> "
            "<button type=submit class=ghost>Add</button></div></form></div></div>")
    msg, err = q.get("msg", ""), q.get("err", "")
    body = ((f"<div class='banner ok'>{t.esc(msg)}</div>" if msg else "")
            + (f"<div class='banner err'>{t.esc(err)}</div>" if err else "")
            + "<h1>Schedule</h1><p class=sub>The week of everyone who works your boards: visits on tickets "
              "(dashed while tentative, struck through when done, ★ the lead) and time off, meetings and "
              "activities. A booking that clashes is refused unless you allow it; time off is never double-booked. "
              "<a href='/dispatch'>Dispatch</a> · <a href='/admin/schedule'>Setup</a></p>"
            + "<div class=card>" + nav + grid + "</div>" + forms)
    if can_book:
        body += slot_dialog(ctx, people, back=f"/schedule?{qs(week=start.isoformat())}")
    return Response(body=t.page("Schedule", body, user=ctx.user, active="schedule", live="schedule"))


# ------------------------------------------------------------ click a time

def slot_dialog(ctx, people, *, back: str) -> str:
    """The dialog a click on a time opens (Schedule and Calendar): book a visit
    on a ticket, open a new ticket and book it, or put a task (a meeting, an
    activity, time off) on the person's day. The page's own forms still do all
    of it without JavaScript."""
    work_boards = [b for b in ctx.conn.execute(
        "SELECT b.board_id, b.display_name FROM board b JOIN board_member m ON m.board_id = b.board_id"
        " WHERE m.member = ? AND m.access IN ('WORK','ADMIN') AND COALESCE(b.inactive, 0) = 0 AND b.is_unrouted = 0"
        " ORDER BY b.display_name", (ctx.user.id,))]
    from ... import members as _members
    who = "".join(f"<option value='{t.esc(p)}'>{t.esc(_members.name_of(ctx.conn, p))}</option>" for p in people)
    statuses = "".join(f"<option value='{t.esc(x['status_id'])}'{' selected' if x['is_default'] else ''}>{t.esc(x['name'])}</option>"
                       for x in schedule.statuses(ctx.conn))
    kinds = "".join(f"<option value='{k}'>{v}</option>" for k, v in schedule.BLOCK_KINDS.items())
    boards = "".join(f"<option value='{t.esc(b['board_id'])}'>{t.esc(b['display_name'])}</option>" for b in work_boards)
    return (
        "<dialog id=slotdlg class=card style='max-width:560px;width:95%'>"
        "<form method=post action='/schedule/slot' class=grid2>"
        f"<input type=hidden name=back value='{t.esc(back)}'>"
        "<h3 style='grid-column:1/-1;margin:0'>" + t.icon("calendar") + "<span data-slot-title>Add to the day</span></h3>"
        "<div style='grid-column:1/-1' class=radiorow>"
        "<label><input type=radio name=what value=visit checked> A visit on a ticket</label> "
        + ("<label><input type=radio name=what value=ticket> A new ticket</label> " if work_boards else "")
        + "<label><input type=radio name=what value=task> A task, meeting or time off</label></div>"
        f"<div><label>Who</label><select name=member required>{who}</select></div><div></div>"
        "<div><label>From</label><input type=datetime-local name=starts_at required></div>"
        "<div><label>To</label><input type=datetime-local name=ends_at required></div>"
        f"<div data-for=visit><label>Ticket</label>{t.ticket_pick('work_item_id', 'Search a ticket, or type its number')}</div>"
        f"<div data-for='visit ticket'><label>Visit status</label><select name=status_id>{statuses}</select></div>"
        f"<div data-for=ticket><label>Board</label><select name=board_id>{boards}</select></div>"
        "<div data-for=ticket style='grid-column:1/-1'><label>Summary</label><input name=summary maxlength=200 "
        "placeholder='What needs doing, in one line - the ward, the room, the machine'></div>"
        f"<div data-for=task><label>What</label><select name=kind>{kinds}</select></div>"
        "<div data-for=task><label>Name</label><input name=name maxlength=120 placeholder='Vendor meeting; leave; stocktake'></div>"
        "<div style='grid-column:1/-1'><label><input type=checkbox name=allow_conflict value=1> Allow a double booking</label></div>"
        "<div style='grid-column:1/-1;display:flex;gap:8px'><button type=submit>Add</button>"
        "<button class=ghost type=button data-close>Cancel</button></div>"
        "<p class=why style='grid-column:1/-1;margin:0'>It goes on the desk now, and on the person's Outlook calendar "
        "at the next sync.</p></form></dialog>")


def slot(ctx):
    """POST /schedule/slot: what the click-a-time dialog sends."""
    from .. import redirect
    from ... import tickets
    from .ticket import _load
    f = ctx.request.form()
    back = f.get("back", "/schedule")
    if not back.startswith("/") or back.startswith("//"):
        back = "/schedule"
    sep = "&" if "?" in back else "?"

    def done(msg="", err=""):
        return redirect(back + sep + urllib.parse.urlencode({k: v for k, v in (("msg", msg), ("err", err)) if v}))

    what = f.get("what", "visit")
    member = (f.get("member") or "").strip()
    try:
        starts = schedule.parse_local(f.get("starts_at", ""))
        ends = schedule.parse_local(f.get("ends_at", ""))
    except ValueError:
        return done(err="Not added: give a start and an end")
    allow = f.get("allow_conflict") == "1"
    try:
        if what == "task":
            if not any(common.may_access_board(ctx, b, need="WORK") for b in common.board_ids_for(ctx)):
                return done(err="Not added: you do not work a board")
            schedule.add_block(ctx.conn, member=member, kind=f.get("kind", ""), name=f.get("name", "") or "Task",
                               starts_at=starts, ends_at=ends, actor=ctx.user.id, at=ctx.now, allow_conflict=allow)
            msg = f"Added for {member}"
        elif what == "ticket":
            board_id = f.get("board_id", "")
            common.require_board(ctx, board_id, need="WORK")
            summary = " ".join((f.get("summary") or "").split())
            if not summary:
                return done(err="Not added: a new ticket needs a summary")
            wid = tickets.open_ticket(ctx.conn, board_id=board_id, summary=summary, impact="I3", urgency="U3",
                                      requested_by=ctx.user.id, at=ctx.now, actor=ctx.user.id, owner=member,
                                      source="DESK")
            schedule.add(ctx.conn, wid, member=member, starts_at=starts, ends_at=ends, note=None, actor=ctx.user.id,
                         at=ctx.now, status_id=f.get("status_id") or None, allow_conflict=allow)
            msg = f"Opened {wid} and booked it for {member}"
        else:
            wid = (f.get("work_item_id") or "").strip().upper()
            try:
                tk = _load(ctx, wid)
            except Exception:                                # noqa: BLE001
                return done(err=f"Not added: no ticket {wid} that you can see")
            if not common.may_access_board(ctx, tk["board_id"], need="WORK"):
                return done(err=f"Not added: you do not work the board {wid} is on")
            schedule.add(ctx.conn, wid, member=member, starts_at=starts, ends_at=ends, note=None, actor=ctx.user.id,
                         at=ctx.now, status_id=f.get("status_id") or None, allow_conflict=allow)
            msg = f"Booked {wid} for {member}"
        ctx.conn.commit()
    except (schedule.Refused, LookupError, ValueError) as exc:
        ctx.conn.rollback()
        return done(err=f"Not added: {exc}")
    return done(msg=msg)


def book(ctx):
    from .ticket import _load
    common.require_module(ctx, "SCHEDULE", "WRITE")
    f = ctx.request.form()
    week = f.get("week", "")
    wid = (f.get("work_item_id", "") or "").strip().upper()
    try:
        tk = _load(ctx, wid)
    except Exception:                                        # noqa: BLE001
        return _back(week, err=f"No ticket {wid} that you can see")
    if not common.may_access_board(ctx, tk["board_id"], need="WORK"):
        return _back(week, err=f"You do not work the board {wid} is on")
    try:
        schedule.add(ctx.conn, wid, member=f.get("member", ""),
                     starts_at=schedule.parse_local(f.get("starts_at", "")),
                     ends_at=schedule.parse_local(f.get("ends_at", "")), note=f.get("note"),
                     actor=ctx.user.id, at=ctx.now, status_id=f.get("status_id") or None,
                     location_id=f.get("location_id") or None, allow_conflict=f.get("allow_conflict") == "1")
        ctx.conn.commit()
    except (schedule.Refused, LookupError) as exc:
        ctx.conn.rollback()
        return _back(week, err=f"Not booked: {exc}")
    return _back(week, msg=f"Booked {wid} for {f.get('member', '').strip()}")


def _may_block(ctx) -> bool:
    return any(common.may_access_board(ctx, b, need="WORK") for b in common.board_ids_for(ctx))


def block_add(ctx):
    from .. import HttpError
    common.require_module(ctx, "SCHEDULE", "WRITE")
    if not _may_block(ctx):
        raise HttpError("403 Forbidden", "Only someone who works a board keeps the schedule.")
    f = ctx.request.form()
    week = f.get("week", "")
    try:
        schedule.add_block(ctx.conn, member=f.get("member", ""), kind=f.get("kind", ""), name=f.get("name", ""),
                           starts_at=schedule.parse_local(f.get("starts_at", "")),
                           ends_at=schedule.parse_local(f.get("ends_at", "")), actor=ctx.user.id, at=ctx.now,
                           allow_conflict=f.get("allow_conflict") == "1")
        ctx.conn.commit()
    except schedule.Refused as exc:
        ctx.conn.rollback()
        return _back(week, err=f"Not added: {exc}")
    return _back(week, msg="Added to the schedule")


def block_remove(ctx):
    from .. import HttpError
    common.require_module(ctx, "SCHEDULE", "WRITE")
    if not _may_block(ctx):
        raise HttpError("403 Forbidden", "Only someone who works a board keeps the schedule.")
    f = ctx.request.form()
    bid = f.get("block_id", "")
    if not bid.isdigit() or not schedule.remove_block(ctx.conn, int(bid), actor=ctx.user.id, at=ctx.now):
        return _back(f.get("week", ""), err="No such entry")
    ctx.conn.commit()
    return _back(f.get("week", ""), msg="Removed from the schedule")


def move(ctx):
    """POST /schedule/move: a visit or a block dropped on another person or
    time (Dispatch, the Schedule, a calendar). Keeps its length."""
    from .. import redirect
    f = ctx.request.form()
    back = f.get("back", "/dispatch")
    if not back.startswith("/") or back.startswith("//"):
        back = "/dispatch"
    sep = "&" if "?" in back else "?"

    def done(msg="", err=""):
        return redirect(back + sep + urllib.parse.urlencode({k: v for k, v in (("msg", msg), ("err", err)) if v}))

    kind = "VISIT" if f.get("kind", "").lower() == "visit" else "BLOCK"
    try:
        ref_id = int(f.get("id", ""))
    except ValueError:
        return done(err="Not moved: no such entry")
    if kind == "VISIT":
        row = ctx.conn.execute("SELECT t.board_id FROM ticket_schedule s JOIN ticket t ON t.work_item_id = s.work_item_id"
                               " WHERE s.schedule_id = ?", (ref_id,)).fetchone()
        if row is None or not common.may_access_board(ctx, row["board_id"], need="WORK"):
            return done(err="Not moved: no such visit that you can work")
    elif not any(common.may_access_board(ctx, b, need="WORK") for b in common.board_ids_for(ctx)):
        return done(err="Not moved: you do not work a board")
    starts = None
    if f.get("starts_at"):
        try:
            starts = schedule.parse_local(f["starts_at"])
        except ValueError:
            return done(err="Not moved: a bad time")
    try:
        what = schedule.move(ctx.conn, kind, ref_id, member=f.get("member"), starts_at=starts, day=f.get("day") or None,
                             actor=ctx.user.id, at=ctx.now, allow_conflict=f.get("allow_conflict") == "1")
        ctx.conn.commit()
    except (schedule.Refused, LookupError, ValueError) as exc:
        ctx.conn.rollback()
        return done(err=f"Not moved: {exc}")
    return done(msg=f"Moved: {what}" if what != "nothing changed" else "Nothing changed")

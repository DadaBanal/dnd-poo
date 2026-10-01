"""Calendar: one person's day, week or month, and a feed for their phone (053).

The Schedule is the dispatcher's: every member of the boards you see, one
week. This is the person's: their visits, their time off and meetings, and
their on-call shifts, in the shape a calendar app has. Anyone with the
Schedule module sees their own; a member of a board sees the people who
work it. Visits name tickets, so on a restricted board each listing is a
read and is audited, as the Schedule's are.

The feed (`/calendar/feed/<token>.ics`) carries the same three kinds for
the person the token belongs to, 30 days back and 90 ahead, and names the
ticket, the board and the place, never a ticket's summary (§6.1: the
summary stays behind the sign-in).
"""
from __future__ import annotations

import calendar as cal
import urllib.parse
from datetime import date, datetime, timedelta

from ... import members, schedule
from .. import templates as t
from . import common

VIEWS = ("day", "week", "month")


def _monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _span(view: str, on: date) -> tuple[date, date]:
    """First day shown, and the day after the last."""
    if view == "day":
        return on, on + timedelta(days=1)
    if view == "week":
        m = _monday(on)
        return m, m + timedelta(days=7)
    first = on.replace(day=1)
    start = _monday(first)
    last = first.replace(day=cal.monthrange(on.year, on.month)[1])
    end = _monday(last) + timedelta(days=7)
    return start, end


def _items(conn, member: str, boards, first: date, end: date) -> list[dict]:
    """Visits, blocks and on-call slots for one person in [first, end)."""
    lo, hi = f"{first.isoformat()} 00:00", f"{end.isoformat()} 00:00"
    out = []
    for v in schedule._visits(conn, sorted(boards), lo, hi):
        if v["member"].lower() == member.lower():
            out.append({"kind": "visit", "starts_at": v["starts_at"], "ends_at": v["ends_at"], "ticket": v["work_item_id"],
                        "board_id": v["board_id"], "status": v["status_name"], "where": v["location_name"],
                        "tentative": v["status_id"] == "TENTATIVE", "done": bool(v["done_at"]), "lead": bool(v["is_lead"]),
                        "summary": v["summary"], "note": v["note"]})
    for b in schedule.blocks(conn, [member], lo, hi):
        out.append({"kind": "block", "block_kind": b["kind"], "starts_at": b["starts_at"], "ends_at": b["ends_at"], "name": b["name"]})
    for s in conn.execute("SELECT s.*, b.display_name AS board_name FROM oncall_slot s JOIN board b ON b.board_id = s.board_id"
                          " WHERE LOWER(s.member) = LOWER(?) AND s.starts_at < ? AND s.ends_at > ? ORDER BY s.starts_at",
                          (member, hi, lo)):
        out.append({"kind": "oncall", "role": s["role"], "starts_at": s["starts_at"], "ends_at": s["ends_at"],
                    "board_id": s["board_id"], "board_name": s["board_name"]})
    from ... import calsync
    for o in calsync.busy(conn, [member], lo, hi):
        out.append({"kind": "outlook", "starts_at": o["starts_at"], "ends_at": o["ends_at"], "show_as": o["show_as"]})
    out.sort(key=lambda x: x["starts_at"])
    return out


def _who(ctx, boards) -> list[str]:
    """The people whose calendar this person may open: themselves, and those
    who work the boards they see."""
    people = {ctx.user.id.lower(): ctx.user.id}
    for m in schedule.members_of(ctx.conn, sorted(boards)):
        people.setdefault(m.lower(), m)
    return sorted(people.values(), key=str.lower)


def _chip(it: dict, *, day_of: str) -> str:
    def span():
        s, e = it["starts_at"], it["ends_at"]
        if s[:10] == e[:10]:
            return f"{s[11:]}–{e[11:]}"
        if s[:10] < day_of < e[:10]:
            return "all day"
        return f"from {s[11:]}" if s[:10] == day_of else f"until {e[11:]}"
    if it["kind"] == "visit":
        cls = "sch visit" + (" tentative" if it["tentative"] else "") + (" done" if it["done"] else "")
        return (f"<a class='{cls}' href='/ticket/{t.esc(it['ticket'])}' title='{t.esc(it['note'] or '')}'><b>{t.esc(span())}</b> "
                f"{t.esc(it['ticket'])}{' ★' if it['lead'] else ''}<br>{t.esc((it['summary'] or '')[:36])}"
                + (f"<br><span class=muted>{t.esc(it['status'] or '')}{' · ' + t.esc(it['where']) if it['where'] else ''}</span>") + "</a>")
    if it["kind"] == "block":
        return (f"<div class='sch block {it['block_kind'].lower()}'><b>{t.esc(schedule.BLOCK_KINDS[it['block_kind']])}</b> "
                f"{t.esc(span())}<br>{t.esc(it['name'])}</div>")
    if it["kind"] == "outlook":
        from .schedule import OUTLOOK_WORD
        return (f"<div class='sch block outlook' title='From their Outlook calendar'><b>Outlook</b> {t.esc(span())}"
                f"<br>{t.esc(OUTLOOK_WORD[it['show_as']])}</div>")
    word = "On call" if it["role"] == "ON_CALL" else "Duty manager"
    return f"<div class='sch block oncall'><b>{t.esc(word)}</b> {t.esc(span())}<br>{t.esc(it['board_name'])}</div>"


def index(ctx):
    from .. import HttpError, Response
    common.require_module(ctx, "SCHEDULE")
    q = ctx.request.query
    view = q.get("view", "week") if q.get("view", "week") in VIEWS else "week"
    try:
        on = date.fromisoformat(q.get("date", ""))
    except ValueError:
        on = ctx.now.date()
    boards = common.board_ids_for(ctx)
    people = _who(ctx, boards)
    who = q.get("member", "") or ctx.user.id
    match = next((p for p in people if p.lower() == who.lower()), None)
    if match is None:
        if ctx.user.is_sysadmin and members.exists(ctx.conn, who):
            match = who
        else:
            raise HttpError("404 Not Found", "No such calendar.")
    who = match
    first, end = _span(view, on)
    items = _items(ctx.conn, who, boards, first, end)
    listed: dict[str, int] = {}
    for it in items:
        if it["kind"] == "visit":
            listed[it["board_id"]] = listed.get(it["board_id"], 0) + 1
    for board_id, n in sorted(listed.items()):
        common.audit_restricted_read(ctx, board_id, detail=f"calendar listed {n} visit(s) on restricted board {board_id} via {ctx.user.via}")
    today = ctx.now.date()
    can_book = any(common.may_access_board(ctx, b, need="WORK") for b in boards)

    def slot(d: date, hhmm: str = "") -> str:
        return f" data-slot='{t.esc(who)}|{d.isoformat()}{'|' + hhmm if hhmm else ''}'" if can_book else ""

    def on_day(d: date):
        lo, hi = f"{d.isoformat()} 00:00", f"{(d + timedelta(days=1)).isoformat()} 00:00"
        return [it for it in items if it["starts_at"] < hi and it["ends_at"] > lo]

    if view == "month":
        weeks = []
        d = first
        while d < end:
            cells = []
            for i in range(7):
                dd = d + timedelta(days=i)
                cls = ("today" if dd == today else "") + (" other" if dd.month != on.month else "")
                cells.append(f"<td class='{cls}'{slot(dd)}><div class=dnum>{dd.day}</div>{''.join(_chip(it, day_of=dd.isoformat()) for it in on_day(dd))}</td>")
            weeks.append("<tr>" + "".join(cells) + "</tr>")
            d += timedelta(days=7)
        head = "".join(f"<th>{n}</th>" for n in ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"))
        grid = f"<div class=schedwrap><table class='schedgrid month'><thead><tr>{head}</tr></thead><tbody>{''.join(weeks)}</tbody></table></div>"
        title = on.strftime("%B %Y")
        prev_ = (on.replace(day=1) - timedelta(days=1)).replace(day=1)
        next_ = (on.replace(day=28) + timedelta(days=4)).replace(day=1)
    elif view == "week":
        days = [first + timedelta(days=i) for i in range(7)]
        head = "".join(f"<th class='{'today' if d == today else ''}'>{d.strftime('%a %d %b')}</th>" for d in days)
        cells = "".join(f"<td class='{'today' if d == today else ''}'{slot(d)}>{''.join(_chip(it, day_of=d.isoformat()) for it in on_day(d))}</td>" for d in days)
        grid = f"<div class=schedwrap><table class='schedgrid week'><thead><tr>{head}</tr></thead><tbody><tr>{cells}</tr></tbody></table></div>"
        title = f"Week of {first.strftime('%d %b %Y')}"
        prev_, next_ = first - timedelta(days=7), first + timedelta(days=7)
    else:
        todays = on_day(on)
        # The day by the hour: each hour is a row you can click to add something
        # at that time; what starts in an hour sits in its row, what spans the
        # day sits above.
        day_lo = f"{on.isoformat()} 00:00"
        allday = [it for it in todays if it["starts_at"] < day_lo]
        rows = []
        for h in range(6, 21):
            hh = f"{h:02d}:00"
            here = [it for it in todays if it["starts_at"][:10] == on.isoformat()
                    and max(6, min(20, int(it["starts_at"][11:13]))) == h]
            rows.append(f"<tr><th class=who style='width:70px'>{hh}</th><td{slot(on, hh)}>"
                        + "".join(_chip(it, day_of=on.isoformat()) for it in here) + "</td></tr>")
        grid = ((("<div class=card>" + "".join(_chip(it, day_of=on.isoformat()) for it in allday) + "</div>") if allday else "")
                + ("" if todays else "<p class=muted>Nothing on this day." + (" Click an hour to add something." if can_book else "")
                   + "</p>")
                + "<div class=schedwrap><table class='schedgrid day'><tbody>" + "".join(rows) + "</tbody></table></div>")
        title = on.strftime("%A %d %B %Y")
        prev_, next_ = on - timedelta(days=1), on + timedelta(days=1)
    keep = {"member": who if who.lower() != ctx.user.id.lower() else "", "view": view}
    qs = lambda **k: urllib.parse.urlencode({x: y for x, y in (keep | k).items() if y})
    who_opts = "".join(f"<option value='{t.esc(p)}'{' selected' if p.lower() == who.lower() else ''}>{t.esc(members.name_of(ctx.conn, p))}</option>"
                       for p in people)
    if who.lower() not in {p.lower() for p in people}:
        who_opts += f"<option value='{t.esc(who)}' selected>{t.esc(members.name_of(ctx.conn, who))}</option>"
    tabs = "".join(f"<a class='{'on' if v == view else ''}' href='/calendar?{qs(view=v, date=on.isoformat())}'>{v.title()}</a>" for v in VIEWS)
    bar = ("<form method=get action='/calendar' class='row schedbar'>"
           f"<div style='flex:0 0 auto'><a class='btn ghost' href='/calendar?{qs(date=prev_.isoformat())}' title='Previous'>‹</a></div>"
           f"<div style='flex:0 0 170px'><input type=date name=date value='{on.isoformat()}' aria-label='Date'></div>"
           f"<div style='flex:0 0 auto'><a class='btn ghost' href='/calendar?{qs(date=next_.isoformat())}' title='Next'>›</a></div>"
           f"<input type=hidden name=view value='{view}'>"
           f"<div style='flex:0 0 200px'><select name=member aria-label='Whose'>{who_opts}</select></div>"
           "<div style='flex:0 0 auto'><button class=ghost type=submit>Show</button></div>"
           f"<div style='flex:0 0 auto'><a class='btn ghost' href='/calendar?{qs(date=today.isoformat())}'>Today</a></div>"
           f"<div class=tabs style='flex:0 0 auto'>{tabs}</div></form>")
    mine = who.lower() == ctx.user.id.lower()
    body = (f"<h1>{t.esc(members.name_of(ctx.conn, who)) if not mine else 'My calendar'} <span class=muted style='font-size:.6em'>{t.esc(title)}</span></h1>"
            "<p class=sub>Visits, time off, meetings and on-call shifts. Click a day, or an hour in the Day view, to "
            "add a visit, a new ticket or a task; move visits from the ticket or the <a href='/schedule'>Schedule</a>. "
            "A feed for your phone is on <a href='/my/profile'>My profile</a>.</p>"
            + bar + grid)
    if can_book:
        from .schedule import slot_dialog
        body += slot_dialog(ctx, people, back=f"/calendar?{qs(date=on.isoformat())}")
    return Response(body=t.page("Calendar", body, user=ctx.user, active="calendar", live="schedule"))


# ------------------------------------------------------------ the feed

def _ics_escape(s: str) -> str:
    return (s or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _ics_stamp(text: str) -> str:
    """'2026-09-29 10:30' -> '20260929T103000' (floating local time: the desk
    runs in one time zone, and the phone is in the same one)."""
    return text[:10].replace("-", "") + "T" + text[11:16].replace(":", "") + "00"


def feed(ctx, token):
    from .. import HttpError, Response
    if token.endswith(".ics"):
        token = token[:-4]
    who = members.member_for_feed(ctx.conn, token)
    if who is None:
        raise HttpError("404 Not Found", "No such feed.")
    boards = {r["board_id"] for r in ctx.conn.execute("SELECT board_id FROM board_member WHERE LOWER(member) = LOWER(?)", (who,))}
    first = ctx.now.date() - timedelta(days=30)
    end = ctx.now.date() + timedelta(days=90)
    items = [it for it in _items(ctx.conn, who, boards, first, end) if it["kind"] != "outlook"]
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Dada PSA//Calendar feed//EN", "CALSCALE:GREGORIAN",
             f"X-WR-CALNAME:{_ics_escape('Dada PSA · ' + members.name_of(ctx.conn, who))}"]
    stamp = _ics_stamp(ctx.now.isoformat(sep=" ", timespec="minutes")) + "Z"
    for i, it in enumerate(items):
        if it["kind"] == "visit":
            summary = f"{it['ticket']} · {it['board_id']}" + (" · " + it["where"] if it["where"] else "")
            uid = f"visit-{it['ticket']}-{it['starts_at']}"
            status = "TENTATIVE" if it["tentative"] else "CONFIRMED"
            desc = it["status"] or ""
        elif it["kind"] == "block":
            summary = f"{schedule.BLOCK_KINDS[it['block_kind']]}: {it['name']}"
            uid = f"block-{it['starts_at']}-{i}"
            status = "CONFIRMED"
            desc = ""
        else:
            summary = ("On call" if it["role"] == "ON_CALL" else "Duty manager") + f" · {it['board_name']}"
            uid = f"oncall-{it['board_id']}-{it['starts_at']}"
            status = "CONFIRMED"
            desc = ""
        lines += ["BEGIN:VEVENT", f"UID:{_ics_escape(uid)}@dada-psa", f"DTSTAMP:{stamp}",
                  f"DTSTART:{_ics_stamp(it['starts_at'])}", f"DTEND:{_ics_stamp(it['ends_at'])}",
                  f"SUMMARY:{_ics_escape(summary)}", f"STATUS:{status}"]
        if desc:
            lines.append(f"DESCRIPTION:{_ics_escape(desc)}")
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    body = "\r\n".join(lines) + "\r\n"
    return Response(body=body, content_type="text/calendar; charset=utf-8",
                    headers=[("Cache-Control", "private, max-age=300")])

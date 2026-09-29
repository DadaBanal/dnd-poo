"""On-call paging on the ticket (050): page the on-call, acknowledge, stop."""
from __future__ import annotations

import urllib.parse

from ... import paging
from .. import templates as t
from . import common


def _board_of(ctx, work_item_id: str) -> str:
    from .. import HttpError
    row = ctx.conn.execute("SELECT board_id FROM ticket WHERE work_item_id = ?", (work_item_id,)).fetchone()
    if row is None:
        raise HttpError("404 Not Found", "No such ticket.")
    return row[0]


def banner(ctx, tk, *, can_work: bool) -> str:
    """Open pages on the ticket, with Acknowledge and Stop; or the button to
    page the on-call when the ticket is open and nobody is being paged."""
    wid = tk["work_item_id"]
    pages = paging.open_for(ctx.conn, wid)
    out = []
    for p in pages:
        mine = p["member"].lower() == (ctx.user.id or "").lower()
        forms = ""
        if can_work or mine:
            forms = (f"<form method=post action='/ticket/{t.esc(wid)}/page/{p['page_id']}/ack' class=inline>"
                     "<button type=submit>Acknowledge</button></form> ")
        if can_work:
            forms += (f"<form method=post action='/ticket/{t.esc(wid)}/page/{p['page_id']}/stop' class=inline>"
                      "<input name=reason placeholder='why' maxlength=200 style='width:160px'> "
                      "<button class=ghost type=submit>Stop paging</button></form>")
        out.append(f"<div class='banner err' data-page={p['page_id']}>{t.icon('bell')} Paging <b>{t.esc(p['member'])}</b>"
                   f" ({t.esc(p['role'].replace('_', ' ').lower())}): attempt {p['attempts']} of {p['max_attempts']},"
                   f" every {p['every_minutes']} min, since {t.esc(p['started_at'])}."
                   + (f" {t.esc(p['note'])}" if p["note"] else "")
                   + (f"<div style='margin-top:6px'>{forms}</div>" if forms else "") + "</div>")
    if not pages and can_work and tk["state"] not in paging.CLOSED_STATES:
        out.append(f"<form method=post action='/ticket/{t.esc(wid)}/page' class=inline style='margin:0 0 10px'>"
                   "<input name=note placeholder='what they should know (no patient details)' maxlength=300 style='width:280px'> "
                   f"<button class=ghost type=submit title='Email and Teams, every 5 minutes, 3 times, then the duty manager'>"
                   f"{t.icon('bell')} Page the on-call</button></form>")
    return "".join(out)


def _back(work_item_id: str, **q):
    from .. import redirect
    q = {k: v for k, v in q.items() if v}
    return redirect(f"/ticket/{work_item_id}" + ("?" + urllib.parse.urlencode(q) if q else ""))


def page(ctx, work_item_id):
    common.require_board(ctx, _board_of(ctx, work_item_id), need="WORK")
    f = ctx.request.form()
    try:
        pid = paging.page_oncall(ctx.conn, work_item_id, at=ctx.now, actor=ctx.user.id, note=f.get("note"))
        ctx.conn.commit()
    except (paging.Refused, LookupError) as exc:
        ctx.conn.rollback()
        return _back(work_item_id, err=str(exc))
    p = paging.get(ctx.conn, pid)
    return _back(work_item_id, msg=f"Paging {p['member']}; it repeats every {p['every_minutes']} minutes until acknowledged")


def _own(ctx, work_item_id, page_id):
    from .. import HttpError
    try:
        p = paging.get(ctx.conn, int(page_id))
    except ValueError:
        p = None
    if p is None or p["work_item_id"] != work_item_id:
        raise HttpError("404 Not Found", "No such page on this ticket.")
    return p


def ack(ctx, work_item_id, page_id):
    board_id = _board_of(ctx, work_item_id)
    p = _own(ctx, work_item_id, page_id)
    if p["member"].lower() != (ctx.user.id or "").lower():
        common.require_board(ctx, board_id, need="WORK")       # not theirs: a working member may answer for them
    else:
        common.require_board(ctx, board_id, need="READ")
    try:
        paging.acknowledge(ctx.conn, p["page_id"], at=ctx.now, actor=ctx.user.id)
        ctx.conn.commit()
    except paging.Refused as exc:
        ctx.conn.rollback()
        return _back(work_item_id, err=str(exc))
    return _back(work_item_id, msg="Page acknowledged")


def stop(ctx, work_item_id, page_id):
    common.require_board(ctx, _board_of(ctx, work_item_id), need="WORK")
    p = _own(ctx, work_item_id, page_id)
    try:
        paging.stop(ctx.conn, p["page_id"], at=ctx.now, actor=ctx.user.id, reason=ctx.request.form().get("reason"))
        ctx.conn.commit()
    except paging.Refused as exc:
        ctx.conn.rollback()
        return _back(work_item_id, err=str(exc))
    return _back(work_item_id, msg="Paging stopped")

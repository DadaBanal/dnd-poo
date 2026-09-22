"""The on-call rota — who owns a P1 raised at 02:00.

A small table and one question asked of it: who is on shift, for this board and
role, right now. Read is open to any board member; editing the rota takes ADMIN
on the board, because a shift is a commitment somebody is accountable for, not a
note anyone can leave.
"""
from __future__ import annotations

import uuid

from ... import board as engine
from ... import clocks
from .. import templates as t
from . import common


def index(ctx):
    from .. import Response
    boards = common.board_ids_for(ctx)
    if not boards:
        return Response(body=t.page(
            "On-call", "<div class='card'><div class='empty'>No boards to show.</div></div>",
            user=ctx.user, active="oncall"))

    cards = []
    for bid in sorted(boards):
        board = ctx.conn.execute("SELECT display_name FROM board WHERE board_id = ?",
                                (bid,)).fetchone()
        now_line = []
        for role in ("ON_CALL", "DUTY_MANAGER"):
            who = engine.current_oncall(ctx.conn, bid, role, at=ctx.now)
            now_line.append(f"<dt>{t.esc(role.replace('_',' ').title())} now</dt>"
                            f"<dd>{t.esc(who or '— nobody on shift —')}</dd>")

        slots = ctx.conn.execute(
            "SELECT member, role, starts_at, ends_at FROM oncall_slot"
            " WHERE board_id = ? ORDER BY starts_at DESC LIMIT 20", (bid,)).fetchall()
        rows = "".join(
            f"<tr><td>{t.esc(s['role'].replace('_',' ').title())}</td>"
            f"<td>{t.esc(s['member'])}</td><td>{t.esc(s['starts_at'])}</td>"
            f"<td>{t.esc(s['ends_at'])}</td></tr>" for s in slots) or \
            "<tr><td colspan=4 class='muted'>No shifts scheduled.</td></tr>"

        add = ""
        if common.may_access_board(ctx, bid, need="ADMIN"):
            add = (
                "<form method='post' action='/oncall/add' "
                "style='display:flex;gap:8px;flex-wrap:wrap;align-items:end;margin-top:12px'>"
                f"<input type='hidden' name='board_id' value='{t.esc(bid)}'>"
                "<div><label>Role</label><select name='role'>"
                "<option value='ON_CALL'>On-call</option>"
                "<option value='DUTY_MANAGER'>Duty manager</option></select></div>"
                "<div><label>Member</label><input name='member' required></div>"
                "<div><label>Starts</label><input name='starts_at' placeholder='2026-09-17 18:00'></div>"
                "<div><label>Ends</label><input name='ends_at' placeholder='2026-09-18 06:00'></div>"
                "<button type='submit'>Add shift</button></form>")

        cards.append(
            f"<div class='card'><h3>{t.esc(board['display_name'])}</h3>"
            f"<dl class='kv'>{''.join(now_line)}</dl>"
            "<div class='tablewrap' style='margin-top:12px'><table><thead><tr>"
            "<th>Role</th><th>Member</th><th>Starts</th><th>Ends</th></tr></thead>"
            f"<tbody>{rows}</tbody></table></div>{add}</div>")

    body = ("<h1>On-call</h1><p class='sub'>Who is on shift now, and the roster "
            "behind it. Editing a shift takes board admin.</p>" + "".join(cards))
    return Response(body=t.page("On-call", body, user=ctx.user, active="oncall"))


def add(ctx):
    from .. import redirect
    f = ctx.request.form()
    board_id = f.get("board_id", "")
    common.require_board(ctx, board_id, need="ADMIN")
    role = f.get("role", "")
    member = f.get("member", "").strip()
    starts_at = f.get("starts_at", "").strip()
    ends_at = f.get("ends_at", "").strip()

    ok = True
    if role not in ("ON_CALL", "DUTY_MANAGER") or not member:
        ok = False
    else:
        try:
            if clocks.parse_instant(ends_at) <= clocks.parse_instant(starts_at):
                ok = False
        except (ValueError, TypeError):
            ok = False
    if ok:
        ctx.conn.execute(
            "INSERT INTO oncall_slot (slot_id, board_id, member, role, starts_at, ends_at)"
            " VALUES (?,?,?,?,?,?)",
            (f"OC-{uuid.uuid4().hex[:16]}", board_id, member, role, starts_at, ends_at))
        ctx.conn.commit()
    return redirect("/oncall")

"""The closed loop — answering the requester and banding the effort as one act.

§5.2, made mechanical. The fulfiller writes the reply and states the hours in one
form; submitting it writes the loop_reply, books the effort through the variation
gate, and moves the ticket to a closed status — one action, so the numerator of a
capacity claim is captured by construction rather than by remembering. The engine
(board.close_loop) does the work and refuses before writing anything if a gate
forbids it; this view only gathers the form and shows the refusal in words.
"""
from __future__ import annotations

from ... import board as engine
from .. import templates as t
from . import common
from .ticket import _load


def form(ctx, work_item_id, *, error=""):
    from .. import Response
    tk = _load(ctx, work_item_id)
    common.require_board(ctx, tk["board_id"], need="WORK")

    closed = ctx.conn.execute(
        "SELECT board_status_id, name FROM board_status"
        " WHERE board_id = ? AND is_closed = 1 AND inactive = 0"
        " ORDER BY CASE WHEN LOWER(name) LIKE '%cancel%' THEN 1 ELSE 0 END, name",
        (tk["board_id"],)).fetchall()
    if not closed:
        return Response(body=t.page(
            "Close the loop",
            "<div class='card'><div class='empty'>This board has no closed status "
            "configured. An administrator adds one on the Admin surface before the "
            "loop can close a ticket.</div></div>", user=ctx.user))
    status_opts = "".join(
        f"<option value='{t.esc(s['board_status_id'])}'>{t.esc(s['name'])}</option>"
        for s in closed)
    err = f"<div class='banner err'>{t.esc(error)}</div>" if error else ""

    body = (
        err +
        f"<h1>Close the loop · {t.esc(work_item_id)}</h1>"
        "<p class='sub'>Answer the requester and band the effort in one action. "
        "The effort still passes the variation gate — the loop makes the honest "
        "path the easy one, it does not open a way round it.</p>"
        "<div class='card'>"
        f"<form class='stack' method='post' action='/ticket/{t.esc(work_item_id)}/loop'>"
        "<label>Reply to the requester (no PHI — §6.1)"
        "<textarea name='body' required></textarea></label>"
        "<label>Effort banded (hours) — leave blank for a holding reply"
        "<input name='hours' inputmode='decimal' placeholder='e.g. 0.5'></label>"
        f"<label>Close to<select name='to_status'>{status_opts}</select></label>"
        "<div><button type='submit'>Send and close</button> "
        f"<a class='btn ghost' href='/ticket/{t.esc(work_item_id)}'>Cancel</a></div>"
        "</form></div>")
    return Response(body=t.page("Close the loop", body, user=ctx.user, active="board"))


def submit(ctx, work_item_id):
    from .. import redirect
    tk = _load(ctx, work_item_id)
    common.require_board(ctx, tk["board_id"], need="WORK")
    f = ctx.request.form()
    body = f.get("body", "").strip()
    to_status = f.get("to_status", "")
    hours_raw = f.get("hours", "").strip()
    if not body:
        return form(ctx, work_item_id, error="A reply to the requester is required.")

    hours = None
    if hours_raw:
        try:
            hours = float(hours_raw)
            if hours < 0:
                raise ValueError
        except ValueError:
            return form(ctx, work_item_id, error="Effort must be a number of hours.")

    try:
        engine.close_loop(ctx.conn, work_item_id, to_status, body=body,
                          sent_by=ctx.user.id, at=ctx.now, actor=ctx.user.id,
                          band_hours=hours)
        ctx.conn.commit()
    except engine.EffortRefused as exc:
        ctx.conn.rollback()
        return form(ctx, work_item_id, error=str(exc))
    except (engine.NotOnThisBoard, LookupError) as exc:
        ctx.conn.rollback()
        return form(ctx, work_item_id, error=str(exc))
    return redirect(f"/ticket/{work_item_id}")

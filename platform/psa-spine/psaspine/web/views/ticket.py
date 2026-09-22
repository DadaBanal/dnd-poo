"""The ticket view — one screen, no tabs for the common things.

Header carries the id, board, status, priority and why it is that priority. The
body is the event stream, newest last, because a ticket's history is the record.
The right rail carries the commercial basis a fulfiller must not have to hunt
for: contract basis, scope item, variation, banded effort. Status change goes
through board.change_status, the one seam; this view never touches a clock
directly.
"""
from __future__ import annotations

from datetime import datetime

from ... import board as engine
from .. import templates as t
from . import common


def _load(ctx, work_item_id):
    from .. import HttpError
    row = ctx.conn.execute(
        "SELECT t.*, w.name AS summary, w.contract_basis, w.variation_id,"
        "       w.entity_id, e.name AS entity, s.name AS status_name,"
        "       s.escalation_status, b.display_name AS board_name,"
        "       b.closed_loop_required"
        "  FROM ticket t"
        "  JOIN work_item w ON w.work_item_id = t.work_item_id"
        "  LEFT JOIN entity e ON e.entity_id = w.entity_id"
        "  LEFT JOIN board_status s ON s.board_status_id = t.board_status_id"
        "  JOIN board b ON b.board_id = t.board_id"
        " WHERE t.work_item_id = ?", (work_item_id,)).fetchone()
    if row is None:
        raise HttpError("404 Not Found", "No such ticket.")
    # subject_id names the ticket, so a restricted read is auditable to the
    # patient's ticket and not merely to the board (§6.1 requirement 4).
    common.require_board(ctx, row["board_id"], subject_id=work_item_id)
    return row


def detail(ctx, work_item_id):
    from .. import Response
    tk = _load(ctx, work_item_id)

    events = ctx.conn.execute(
        "SELECT occurred_at, kind, actor, detail FROM ticket_event"
        " WHERE work_item_id = ? ORDER BY ticket_event_id", (work_item_id,)).fetchall()
    stream = "".join(
        f"<li><div>{t.esc(e['detail'] or e['kind'])}</div>"
        f"<div class='meta'>{t.esc(e['kind'])} · {t.esc(e['actor'] or '—')} · "
        f"{t.esc(e['occurred_at'])}</div></li>" for e in events) or \
        "<li class='muted'>No events yet.</li>"

    effort = ctx.conn.execute(
        "SELECT COALESCE(SUM(band_hours),0) AS h, COUNT(*) AS n"
        "  FROM time_entry WHERE work_item_id = ?", (work_item_id,)).fetchone()

    statuses = ctx.conn.execute(
        "SELECT board_status_id, name FROM board_status"
        " WHERE board_id = ? AND inactive = 0 ORDER BY sort_order, name",
        (tk["board_id"],)).fetchall()
    status_opts = "".join(
        f"<option value='{t.esc(s['board_status_id'])}'"
        f"{' selected' if s['board_status_id']==tk['board_status_id'] else ''}>"
        f"{t.esc(s['name'])}</option>" for s in statuses)

    may, why = engine.may_book_effort(ctx.conn, work_item_id)

    header = (
        f"<h1>{t.esc(work_item_id)} · {t.esc(tk['summary'])}</h1>"
        f"<p class='sub'>{t.esc(tk['board_name'])} · "
        f"{t.chip(tk['status_name'] or tk['state'])} · "
        f"<span class='pri pri-{t.esc(tk['priority'])}'>{t.esc(tk['priority'])}</span> "
        f"<span class='muted'>({t.esc(tk['priority_source'])})</span></p>")

    can_work = common.may_access_board(ctx, tk["board_id"], need="WORK")
    actions = ""
    if can_work:
        loop_btn = ""
        if tk["closed_loop_required"]:
            loop_btn = (f"<a class='btn ghost' href='/ticket/{t.esc(work_item_id)}/loop'>"
                        "Close the loop</a>")
        actions = (
            "<div class='card'><h3>Act</h3>"
            f"<form method='post' action='/ticket/{t.esc(work_item_id)}/status' "
            "style='display:flex;gap:8px;align-items:end;flex-wrap:wrap'>"
            f"<div><label>Move to status</label><select name='to_status'>{status_opts}"
            "</select></div><button type='submit'>Change status</button>"
            f"{loop_btn}</form>"
            f"<form method='post' action='/ticket/{t.esc(work_item_id)}/note' "
            "class='stack' style='margin-top:12px;max-width:none'>"
            "<label>Add a note</label>"
            "<textarea name='body' placeholder='No PHI in ticket text (§6.1).'></textarea>"
            "<div><button type='submit'>Add note</button></div></form></div>")

    rail_right = (
        "<div class='card'><h3>Commercial basis</h3><dl class='kv'>"
        f"<dt>Contract basis</dt><dd>{t.esc(tk['contract_basis'])}</dd>"
        f"<dt>Path</dt><dd>{t.esc(tk['path'])}</dd>"
        f"<dt>Variation</dt><dd>{t.esc(tk['variation_id'] or '—')}</dd>"
        f"<dt>Entity</dt><dd>{t.esc(tk['entity'] or '—')}</dd>"
        f"<dt>Banded effort</dt><dd>{effort['h']:g} h ({effort['n']} entries)</dd>"
        f"<dt>May book effort</dt><dd>{'yes' if may else t.esc(why)}</dd>"
        "</dl></div>")

    body = (
        header + actions +
        "<div class='rail'>"
        f"<div class='card'><h3>History</h3><ul class='stream'>{stream}</ul></div>"
        f"<div>{rail_right}</div>"
        "</div>")
    return Response(body=t.page(work_item_id, body, user=ctx.user, active="board"))


def change_status(ctx, work_item_id):
    from .. import redirect
    tk = _load(ctx, work_item_id)
    common.require_board(ctx, tk["board_id"], need="WORK")
    to_status = ctx.request.form().get("to_status", "")
    try:
        engine.change_status(ctx.conn, work_item_id, to_status,
                             at=ctx.now, actor=ctx.user.id)
        ctx.conn.commit()
    except (engine.NotOnThisBoard, LookupError):
        ctx.conn.rollback()
    return redirect(f"/ticket/{work_item_id}")


def add_note(ctx, work_item_id):
    from .. import redirect
    tk = _load(ctx, work_item_id)
    common.require_board(ctx, tk["board_id"], need="WORK")
    body = ctx.request.form().get("body", "").strip()
    if body:
        ctx.conn.execute(
            "INSERT INTO ticket_event (work_item_id, occurred_at, kind, actor, detail)"
            " VALUES (?,?,'NOTE',?,?)",
            (work_item_id, ctx.now.isoformat(sep=" ", timespec="minutes"),
             ctx.user.id, body))
        ctx.conn.commit()
    return redirect(f"/ticket/{work_item_id}")

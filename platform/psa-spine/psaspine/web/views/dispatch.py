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
        " ORDER BY b.display_name", (ctx.user.id,)).fetchall()
    target_opts = "".join(
        f"<option value='{t.esc(b['board_id'])}'>{t.esc(b['display_name'])}</option>"
        for b in targets)

    if unrouted_rows:
        lines = []
        for r in sorted(unrouted_rows, key=lambda x: (x["priority"] or "P9", x["opened_at"] or "")):
            state, label = common.ticket_sla(ctx, r["work_item_id"], now=ctx.now)
            assign = ""
            if target_opts:
                assign = (
                    f"<form method='post' action='/dispatch/assign' "
                    "style='display:flex;gap:6px'>"
                    f"<input type='hidden' name='work_item_id' value='{t.esc(r['work_item_id'])}'>"
                    f"<select name='to_board'>{target_opts}</select>"
                    "<input name='owner' placeholder='owner' style='width:120px'>"
                    "<button type='submit'>Route</button></form>")
            lines.append(
                "<tr>"
                f"<td><a href='/ticket/{t.esc(r['work_item_id'])}'>{t.esc(r['work_item_id'])}</a></td>"
                f"<td class='pri pri-{t.esc(r['priority'])}'>{t.esc(r['priority'])}</td>"
                f"<td>{t.esc(common.human_age(r['opened_at'], now=ctx.now))}</td>"
                f"<td>{t.chip(label if state!='NONE' else 'no clock', t.sla_class(state))}</td>"
                f"<td>{t.esc(r['summary'])}</td>"
                f"<td class='muted'>{t.esc(r['entity'] or '—')}</td>"
                f"<td>{assign}</td></tr>")
        queue = ("<div class='card'><h3>Unrouted queue</h3><div class='tablewrap'><table>"
                 "<thead><tr><th>ID</th><th>Pri</th><th>Age</th><th>SLA</th>"
                 "<th>Summary</th><th>Entity</th><th>Route to</th></tr></thead><tbody>"
                 + "".join(lines) + "</tbody></table></div></div>")
    else:
        queue = ("<div class='card'><h3>Unrouted queue</h3>"
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

    body = (
        "<h1>Dispatch</h1><p class='sub'>The unrouted queue, ageing in plain sight, "
        "and who answers each board — the rota over the org chart.</p>"
        + queue + "".join(role_cards))
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

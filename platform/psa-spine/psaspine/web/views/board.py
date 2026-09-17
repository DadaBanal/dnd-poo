"""The board view — the list a fulfiller lives in.

Tickets on the boards they belong to, worst SLA first, then oldest. Colour
carries SLA state and nothing else. The board and status filters are plain query
parameters so the page works with the browser's back button and no script.
"""
from __future__ import annotations

from .. import templates as t
from . import common

PRIORITY_ORDER = {"P1": 0, "P2": 1, "P3": 2, "P4": 3}


def index(ctx):
    boards = common.board_ids_for(ctx)
    if not boards:
        return _response(ctx, "<div class='card'><div class='empty'>You are not a "
                              "member of any board yet. An administrator adds you "
                              "on the Admin surface.</div></div>")

    selected = ctx.request.query.get("board", "")
    status_filter = ctx.request.query.get("status", "open")   # open | all
    search = ctx.request.query.get("q", "").strip()

    board_rows = ctx.conn.execute(
        "SELECT board_id, display_name FROM board WHERE board_id IN (%s)"
        " ORDER BY display_name" % ",".join("?" * len(boards)),
        tuple(boards)).fetchall()

    where = ["t.board_id IN (%s)" % ",".join("?" * len(boards))]
    params: list = list(boards)
    if selected and selected in boards:
        where = ["t.board_id = ?"]
        params = [selected]
    if status_filter == "open":
        where.append("t.state NOT IN ('RESOLVED','CLOSED','CANCELLED')")
    if search:
        where.append("(w.name LIKE ? OR t.work_item_id LIKE ?)")
        params += [f"%{search}%", f"%{search}%"]

    rows = ctx.conn.execute(
        "SELECT t.work_item_id, t.board_id, t.priority, t.priority_source,"
        "       t.state, t.owner, t.opened_at, t.board_status_id,"
        "       w.name AS summary, e.name AS entity,"
        "       s.name AS status_name"
        "  FROM ticket t"
        "  JOIN work_item w ON w.work_item_id = t.work_item_id"
        "  LEFT JOIN entity e ON e.entity_id = w.entity_id"
        "  LEFT JOIN board_status s ON s.board_status_id = t.board_status_id"
        " WHERE " + " AND ".join(where), params).fetchall()

    def sort_key(r):
        return (PRIORITY_ORDER.get(r["priority"], 9), r["opened_at"] or "")
    rows = sorted(rows, key=sort_key)

    body = _filters(ctx, board_rows, selected, status_filter, search)
    if not rows:
        body += "<div class='card'><div class='empty'>No tickets match.</div></div>"
        return _response(ctx, body)

    lines = []
    for r in rows:
        state, label = common.ticket_sla(ctx, r["work_item_id"], now=ctx.now)
        pri = r["priority"] or "—"
        lines.append(
            "<tr>"
            f"<td><a href='/ticket/{t.esc(r['work_item_id'])}'>{t.esc(r['work_item_id'])}</a></td>"
            f"<td class='pri pri-{t.esc(pri)}'>{t.esc(pri)}</td>"
            f"<td>{t.esc(common.human_age(r['opened_at'], now=ctx.now))}</td>"
            f"<td>{t.chip(label if state!='NONE' else 'no clock', t.sla_class(state))}</td>"
            f"<td>{t.esc(r['summary'])}</td>"
            f"<td class='muted'>{t.esc(r['entity'] or '—')}</td>"
            f"<td class='muted'>{t.esc(r['owner'] or 'unassigned')}</td>"
            f"<td>{t.esc(r['status_name'] or r['state'])}</td>"
            "</tr>")
    table = (
        "<div class='card'><div class='tablewrap'><table>"
        "<thead><tr><th>ID</th><th>Pri</th><th>Age</th><th>SLA</th><th>Summary</th>"
        "<th>Entity</th><th>Owner</th><th>Status</th></tr></thead><tbody>"
        + "".join(lines) + "</tbody></table></div></div>")
    return _response(ctx, body + table)


def _filters(ctx, board_rows, selected, status_filter, search) -> str:
    opts = ["<option value=''>All my boards</option>"]
    for b in board_rows:
        sel = " selected" if b["board_id"] == selected else ""
        opts.append(f"<option value='{t.esc(b['board_id'])}'{sel}>"
                    f"{t.esc(b['display_name'])}</option>")
    status_opts = "".join(
        f"<option value='{v}'{' selected' if v==status_filter else ''}>{lab}</option>"
        for v, lab in (("open", "Open only"), ("all", "All states")))
    return (
        "<div class='card'><form method='get' style='display:flex;gap:10px;"
        "flex-wrap:wrap;align-items:end'>"
        f"<div><label>Board</label><select name='board'>{''.join(opts)}</select></div>"
        f"<div><label>Show</label><select name='status'>{status_opts}</select></div>"
        f"<div style='flex:1'><label>Search</label>"
        f"<input name='q' value='{t.esc(search)}' placeholder='summary or id'></div>"
        "<div><button type='submit'>Filter</button></div>"
        "</form></div>")


def _response(ctx, body: str):
    from .. import Response
    heading = ("<h1>Board</h1><p class='sub'>Your tickets, worst SLA first. "
               "Colour is the clock, not decoration.</p>")
    return Response(body=t.page("Board", heading + body, user=ctx.user, active="board"))

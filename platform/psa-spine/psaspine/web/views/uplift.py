"""The uplift evidence screen — a first-class page, not an export (§7).

The whole spine exists to produce this, and until now it was reachable only as a
file written by the CLI. Here it is a page: the same `reports.uplift_evidence`
markdown, rendered. The query names the run and, optionally, an as-of date. The
report is deliberately unflattering where the evidence is thin — that honesty is
the point, so nothing here softens it.
"""
from __future__ import annotations

from datetime import date

from ... import reports
from .. import templates as t
from . import common


def index(ctx):
    from .. import Response
    # The effort totals are cross-board evidence and are not board-scoped. The
    # ticket tables (board, priority, state, summary) are: they name tickets,
    # and a restricted board's tickets are what a non-member never sees (§11
    # test 5). Someone on no board at all is a requester, and this is not
    # their page.
    boards = common.board_ids_for(ctx)
    if not boards:
        return Response(body=t.page("Uplift evidence", (
            "<h1>Uplift evidence</h1><div class='card'><div class='empty'>This page is "
            "for board members. An administrator adds you on the Setup page.</div></div>"),
            user=ctx.user, active="uplift"))
    run_id = ctx.request.query.get("run_id", "").strip() or None
    as_of_raw = ctx.request.query.get("as_of", "").strip()
    capacity_raw = ctx.request.query.get("capacity_hours", "").strip()

    try:
        as_of = date.fromisoformat(as_of_raw) if as_of_raw else ctx.now.date()
    except ValueError:
        as_of = ctx.now.date()
    capacity = None
    if capacity_raw:
        try:
            capacity = float(capacity_raw)
        except ValueError:
            capacity = None

    markdown = reports.uplift_evidence(ctx.conn, as_of=as_of, capacity_hours=capacity,
                                       boards=boards)
    # §6.1 requirement 4: a restricted board's tickets listed here is a read.
    owed = reports.decisions_owed(ctx.conn, boards=boards)
    named: dict[str, int] = {}
    for rows in owed.values():
        for r in rows:
            named[r["board_id"]] = named.get(r["board_id"], 0) + 1
    for board_id, n in sorted(named.items()):
        common.audit_restricted_read(
            ctx, board_id, detail=f"uplift evidence listed {n} ticket(s) on restricted "
                                  f"board {board_id} via {ctx.user.via}")

    controls = (
        "<div class='card'><form method='get' style='display:flex;gap:10px;"
        "flex-wrap:wrap;align-items:end'>"
        f"<div><label>As of</label><input name='as_of' value='{t.esc(as_of.isoformat())}'></div>"
        "<div><label>Capacity hours/month</label>"
        f"<input name='capacity_hours' value='{t.esc(capacity_raw)}' "
        "placeholder='denominator'></div>"
        "<div><button type='submit'>Refresh</button></div>"
        "</form></div>")

    body = ("<h1>Uplift evidence</h1><p class='sub'>The arithmetic behind a "
            "capacity claim. It stays unflattering where the evidence is thin — "
            "that is the point.</p>" + controls +
            "<div class='card'>" + t.md_to_html(markdown) + "</div>")
    return Response(body=t.page("Uplift evidence", body, user=ctx.user, active="uplift"))

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
    # The uplift picture is cross-board evidence; a break-glass sysadmin or any
    # board member may read it, but the numbers themselves are not board-scoped.
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

    markdown = reports.uplift_evidence(ctx.conn, as_of=as_of, capacity_hours=capacity)

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

"""Search for the command palette: tickets, contacts and machines, as JSON.

Cookie-authenticated like every other page (it is not under /api/, which is
token-only by design). It answers only from the boards the person is on, and a
restricted board's hits are a read of restricted data, so they are audited
per board with the count, exactly as the board view audits its list (§6.1
requirement 4). Nothing in the answer is more than the board view shows.
"""
from __future__ import annotations

import json

from . import common

LIMIT = 8


def _like(needle: str) -> str:
    from .board import _like as like        # one escaping rule for the whole desk
    return like(needle)


def search(ctx):
    from .. import Response
    q = ctx.request.query.get("q", "").strip()
    out: dict = {"q": q, "tickets": [], "contacts": [], "configurations": []}
    boards = common.board_ids_for(ctx)
    if len(q) < 2 or not boards:
        return Response(body=json.dumps(out), content_type="application/json; charset=utf-8",
                        headers=[("Cache-Control", "no-store")])
    like = _like(q.lower())
    marks = ",".join("?" * len(boards))
    rows = ctx.conn.execute(
        "SELECT t.work_item_id, t.board_id, t.state, t.priority, w.name AS summary,"
        "       COALESCE((SELECT ct.display_name FROM contact ct WHERE ct.contact_id = t.contact_id),"
        "                t.requested_by) AS who"
        f"  FROM ticket t JOIN work_item w ON w.work_item_id = t.work_item_id WHERE t.board_id IN ({marks})"
        "   AND (LOWER(t.work_item_id) LIKE ? ESCAPE '\\' OR LOWER(w.name) LIKE ? ESCAPE '\\'"
        "        OR LOWER(t.requested_by) LIKE ? ESCAPE '\\')"
        " ORDER BY CASE WHEN t.state IN ('RESOLVED','CLOSED','CANCELLED') THEN 1 ELSE 0 END, t.opened_at DESC LIMIT ?",
        list(boards) + [like, like, like, LIMIT]).fetchall()
    seen: dict[str, int] = {}
    for r in rows:
        seen[r["board_id"]] = seen.get(r["board_id"], 0) + 1
        out["tickets"].append({"id": r["work_item_id"], "summary": r["summary"], "who": r["who"],
                               "state": r["state"], "priority": r["priority"]})
    for bid, n in sorted(seen.items()):
        common.audit_restricted_read(ctx, bid, detail=f"search listed {n} ticket(s)")
    for c in ctx.conn.execute(
            "SELECT contact_id, display_name, department FROM contact WHERE inactive = 0 AND"
            " (LOWER(display_name) LIKE ? ESCAPE '\\' OR LOWER(email) LIKE ? ESCAPE '\\')"
            " ORDER BY display_name LIMIT ?", (like, like, LIMIT)):
        out["contacts"].append({"id": c["contact_id"], "name": c["display_name"],
                                "department": c["department"]})
    for m in ctx.conn.execute(
            "SELECT configuration_id, name, config_type FROM configuration WHERE status = 'ACTIVE'"
            " AND LOWER(name) LIKE ? ESCAPE '\\' ORDER BY name LIMIT ?", (like, LIMIT)):
        out["configurations"].append({"id": m["configuration_id"], "name": m["name"],
                                      "type": m["config_type"]})
    return Response(body=json.dumps(out), content_type="application/json; charset=utf-8",
                    headers=[("Cache-Control", "no-store")])

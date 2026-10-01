"""Real time: the board, Dispatch, the Schedule and a ticket refresh by
themselves when something changes (Dada, 1 Oct 2026: "can it be real time").

The page polls GET /live?scope=... every ten seconds while it is on screen.
The answer is a short stamp, not data: a number that moves when any ticket
event, ticket or visit the person may see changes. The page reloads itself
when the stamp moves, unless the person is typing, in which case it says so
and waits for them. No socket, no push, nothing new on the server's network
surface: the LAN-only host stays as it is.

A restricted ticket's stamp is answered only to someone who may read that
board, and asking for it is not a read of the ticket (nothing in it leaves).
"""
from __future__ import annotations

from . import common


def _in(ids) -> tuple[str, tuple]:
    ids = tuple(sorted(ids))
    return ("(" + ",".join("?" * len(ids)) + ")", ids) if ids else ("(NULL)", ())


def stamp(ctx):
    from .. import Response
    scope = ctx.request.query.get("scope", "")
    conn = ctx.conn
    if scope.startswith("ticket:"):
        wid = scope[7:]
        row = conn.execute("SELECT board_id, updated_at, board_status_id, owner, priority FROM ticket"
                           " WHERE work_item_id = ?", (wid,)).fetchone()
        if row is None or not common.may_access_board(ctx, row["board_id"]):
            return Response("404 Not Found", "", content_type="text/plain; charset=utf-8")
        ev = conn.execute("SELECT COUNT(*), MAX(ticket_event_id) FROM ticket_event WHERE work_item_id = ?",
                          (wid,)).fetchone()
        vis = conn.execute("SELECT COUNT(*), MAX(schedule_id) FROM ticket_schedule WHERE work_item_id = ?",
                           (wid,)).fetchone()
        parts = (row["board_id"], row["updated_at"], row["board_status_id"], row["owner"], row["priority"],
                 ev[0], ev[1], vis[0], vis[1])
    elif scope in ("board", "schedule"):
        frag, ids = _in(common.board_ids_for(ctx))
        tk = conn.execute(f"SELECT COUNT(*), MAX(updated_at) FROM ticket WHERE board_id IN {frag}", ids).fetchone()
        ev = conn.execute(f"SELECT MAX(e.ticket_event_id) FROM ticket_event e JOIN ticket t ON t.work_item_id ="
                          f" e.work_item_id WHERE t.board_id IN {frag}", ids).fetchone()
        vis = conn.execute(f"SELECT COUNT(*), MAX(s.schedule_id) FROM ticket_schedule s JOIN ticket t ON"
                           f" t.work_item_id = s.work_item_id WHERE t.board_id IN {frag}", ids).fetchone()
        parts = (tk[0], tk[1], ev[0], vis[0], vis[1])
    else:
        return Response("400 Bad Request", "", content_type="text/plain; charset=utf-8")
    body = "|".join("" if p is None else str(p) for p in parts)
    return Response(body=body, content_type="text/plain; charset=utf-8",
                    headers=[("Cache-Control", "no-store")])

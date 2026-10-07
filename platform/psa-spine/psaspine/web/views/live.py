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
    elif scope == "projects" or scope.startswith("project:"):
        # 068: the projects list and a project page move when a project, its
        # phases, team, notes or any of its tickets the person may see change.
        pid = scope[8:] if scope.startswith("project:") else None
        if pid is not None:
            row = conn.execute("SELECT board_id FROM project WHERE project_id = ?", (pid,)).fetchone()
            if row is None or (row["board_id"] and not common.may_access_board(ctx, row["board_id"])):
                return Response("404 Not Found", "", content_type="text/plain; charset=utf-8")
        frag, ids = _in(common.board_ids_for(ctx))
        one = " AND pt.project_id = ?" if pid else ""
        arg = (pid,) if pid else ()
        tk = conn.execute(f"SELECT COUNT(*), MAX(t.updated_at), MAX(t.board_status_id) FROM project_ticket pt JOIN ticket t"
                          f" ON t.work_item_id = pt.work_item_id WHERE t.board_id IN {frag}{one}", ids + arg).fetchone()
        te = conn.execute(f"SELECT COUNT(*), MAX(te.time_entry_id) FROM project_ticket pt JOIN ticket t ON t.work_item_id ="
                          f" pt.work_item_id JOIN time_entry te ON te.work_item_id = pt.work_item_id"
                          f" WHERE t.board_id IN {frag}{one}", ids + arg).fetchone()
        w = " WHERE project_id = ?" if pid else ""
        pr = conn.execute(f"SELECT COUNT(*), MAX(name || status || COALESCE(manager, '') || COALESCE(budget_hours, ''))"
                          f" FROM project{w}", arg).fetchone()
        ph = conn.execute(f"SELECT COUNT(*), MAX(phase_id), SUM(CASE WHEN status = 'DONE' THEN 1 ELSE 0 END)"
                          f" FROM project_phase{w}", arg).fetchone()
        tm = conn.execute(f"SELECT COUNT(*), MAX(added_at) FROM project_member{w}", arg).fetchone()
        nt = conn.execute(f"SELECT COUNT(*) FROM project_note{w}", arg).fetchone()
        ct = conn.execute(f"SELECT COUNT(*) FROM project_contact{w}", arg).fetchone()            # 069
        pl = conn.execute(f"SELECT COUNT(*), MAX(item_id) FROM project_plan_item{w}", arg).fetchone()
        dp = conn.execute(f"SELECT COUNT(*) FROM project_ticket_dependency d JOIN project_ticket pt ON pt.work_item_id ="
                          f" d.work_item_id{' WHERE pt.project_id = ?' if pid else ''}", arg).fetchone()
        hl = conn.execute(f"SELECT MAX(COALESCE(health, '') || COALESCE(is_template, 0)) FROM project{w}", arg).fetchone()
        dt = conn.execute(f"SELECT MAX(COALESCE(starts_on, '') || COALESCE(due_on, '') || COALESCE(budget_hours, ''))"
                          f" FROM project_ticket{w}", arg).fetchone()
        parts = (*tk, *te, *pr, *ph, *tm, nt[0], ct[0], *pl, dp[0], hl[0], dt[0])
    else:
        return Response("400 Bad Request", "", content_type="text/plain; charset=utf-8")
    body = "|".join("" if p is None else str(p) for p in parts)
    return Response(body=body, content_type="text/plain; charset=utf-8",
                    headers=[("Cache-Control", "no-store")])

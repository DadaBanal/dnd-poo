"""Path to view, with a matcher small enough to read in one sitting.

No regex and no framework: a route is a method, a pattern split on '/', and a
handler. A segment written '<name>' captures; everything else matches literally.
That is the whole engine, and it is enough for the fixed set of paths the desk
has. Views receive the captured segments as keyword arguments alongside the
context, and return a Response.
"""
from __future__ import annotations

from .views import admin, board, dispatch, loop, oncall, portal, ticket, uplift

# (method, pattern, handler). Order does not matter; patterns do not overlap.
ROUTES = [
    ("GET", "/", board.index),
    ("GET", "/ticket/<work_item_id>", ticket.detail),
    ("POST", "/ticket/<work_item_id>/status", ticket.change_status),
    ("POST", "/ticket/<work_item_id>/note", ticket.add_note),
    ("GET", "/ticket/<work_item_id>/loop", loop.form),
    ("POST", "/ticket/<work_item_id>/loop", loop.submit),
    ("GET", "/dispatch", dispatch.index),
    ("POST", "/dispatch/assign", dispatch.assign),
    ("GET", "/oncall", oncall.index),
    ("POST", "/oncall/add", oncall.add),
    # The requester portal. Ownership, not board membership, is the filter.
    ("GET", "/my", portal.index),
    ("POST", "/my/new", portal.create),
    ("GET", "/my/<work_item_id>", portal.detail),
    ("POST", "/my/<work_item_id>/reply", portal.reply),
    ("GET", "/uplift", uplift.index),
    ("GET", "/admin", admin.index),
    ("POST", "/admin/status/add", admin.add_status),
    ("POST", "/admin/member/add", admin.add_member),
    ("POST", "/admin/local/disable", admin.disable_local),
]


def _match(pattern: str, path: str) -> dict | None:
    pat = pattern.strip("/").split("/") if pattern != "/" else [""]
    got = path.strip("/").split("/") if path != "/" else [""]
    if len(pat) != len(got):
        return None
    captures: dict[str, str] = {}
    for p, g in zip(pat, got):
        if p.startswith("<") and p.endswith(">"):
            captures[p[1:-1]] = g
        elif p != g:
            return None
    return captures


def dispatch(ctx):
    from . import HttpError, Response
    matched_path = False
    for method, pattern, handler in ROUTES:
        caps = _match(pattern, ctx.request.path)
        if caps is None:
            continue
        matched_path = True
        if method == ctx.request.method:
            return handler(ctx, **caps)
    if matched_path:
        raise HttpError("405 Method Not Allowed",
                        f"{ctx.request.method} not allowed on {ctx.request.path}")
    return Response("404 Not Found",
                    "<h1>404 Not Found</h1><p>No such page.</p>")

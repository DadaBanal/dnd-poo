"""Path to view, with a matcher small enough to read in one sitting.

No regex and no framework: a route is a method, a pattern split on '/', and a
handler. A segment written '<name>' captures; everything else matches literally.
That is the whole engine, and it is enough for the fixed set of paths the desk
has. Views receive the captured segments as keyword arguments alongside the
context, and return a Response.
"""
from __future__ import annotations

from .views import (admin, board, companies, configurations, dispatch, files, loop, oncall,
                    portal, reports, rules, search, ticket, uplift)

# (method, pattern, handler). The first pattern that matches the path wins,
# so a literal segment must be listed before a <capture> in the same place.
ROUTES = [
    ("GET", "/", board.index),
    ("POST", "/bulk", board.bulk),
    ("GET", "/search.json", search.search),
    ("GET", "/reports", reports.index),
    ("GET", "/reports.csv", reports.export_csv),
    ("POST", "/views/save", board.view_save),
    ("POST", "/views/delete", board.view_delete),
    # /ticket/new first: the first matching pattern wins, and <work_item_id>
    # would otherwise capture the word "new".
    ("GET", "/ticket/new", ticket.new_form),
    ("POST", "/ticket/new", ticket.new_create),
    ("GET", "/ticket/<work_item_id>", ticket.detail),
    ("POST", "/ticket/<work_item_id>/update", ticket.update),
    ("POST", "/ticket/<work_item_id>/status", ticket.change_status),
    ("POST", "/ticket/<work_item_id>/note", ticket.add_note),
    ("POST", "/ticket/<work_item_id>/time", ticket.add_time),
    ("POST", "/ticket/<work_item_id>/change/decide", ticket.decide_change),
    ("POST", "/ticket/<work_item_id>/task/add", ticket.task_add),
    ("POST", "/ticket/<work_item_id>/task/toggle", ticket.task_toggle),
    ("POST", "/ticket/<work_item_id>/template", ticket.template_apply),
    ("POST", "/ticket/<work_item_id>/link", ticket.link),
    ("POST", "/ticket/<work_item_id>/unlink", ticket.unlink),
    ("POST", "/ticket/<work_item_id>/child/add", ticket.child_add),
    ("POST", "/ticket/<work_item_id>/child/remove", ticket.child_remove),
    ("POST", "/ticket/<work_item_id>/parent/set", ticket.parent_set),
    ("POST", "/ticket/<work_item_id>/parent/remove", ticket.parent_remove),
    ("POST", "/ticket/<work_item_id>/merge", ticket.merge),
    ("POST", "/ticket/<work_item_id>/schedule/add", ticket.schedule_add),
    ("POST", "/ticket/<work_item_id>/schedule/remove", ticket.schedule_remove),
    ("POST", "/ticket/<work_item_id>/attach", files.upload),
    ("GET", "/ticket/<work_item_id>/file/<attachment_id>", files.download),
    ("POST", "/ticket/<work_item_id>/file/<attachment_id>/review", files.review),
    ("POST", "/ticket/<work_item_id>/config/add", configurations.attach),
    ("POST", "/ticket/<work_item_id>/config/remove", configurations.detach),
    ("GET", "/ticket/<work_item_id>/loop", loop.form),
    ("POST", "/ticket/<work_item_id>/loop", loop.submit),
    ("GET", "/companies", companies.index),
    ("GET", "/company/<entity_id>", companies.detail),
    ("GET", "/contacts", companies.contacts_index),
    ("GET", "/contact/<contact_id>", companies.contact_detail),
    ("GET", "/configurations", configurations.index),
    ("GET", "/configuration/<configuration_id>", configurations.detail),
    ("POST", "/configuration/<configuration_id>/update", configurations.update),
    ("GET", "/dispatch", dispatch.index),
    ("POST", "/dispatch/assign", dispatch.assign),
    ("GET", "/oncall", oncall.index),
    ("POST", "/oncall/add", oncall.add),
    # The requester portal. Ownership, not board membership, is the filter.
    ("GET", "/my", portal.index),
    ("POST", "/my/new", portal.create),
    ("GET", "/my/<work_item_id>", portal.detail),
    ("POST", "/my/<work_item_id>/reply", portal.reply),
    ("POST", "/my/<work_item_id>/survey", portal.survey_answer),
    ("GET", "/my/<work_item_id>/file/<attachment_id>", portal.file_download),
    ("GET", "/uplift", uplift.index),
    ("GET", "/admin", admin.index),
    ("POST", "/admin/status/add", admin.add_status),
    ("POST", "/admin/member/add", admin.add_member),
    ("POST", "/admin/local/disable", admin.disable_local),
    ("GET", "/admin/rules", rules.index),
    ("POST", "/admin/rules/new", rules.create),
    ("GET", "/admin/rules/<workflow_id>", rules.detail),
    ("POST", "/admin/rules/<workflow_id>/event", rules.add_event),
    ("POST", "/admin/rules/<workflow_id>/test", rules.test),
    ("POST", "/admin/rules/<workflow_id>/activate", rules.activate),
    ("POST", "/admin/rules/<workflow_id>/deactivate", rules.deactivate),
    ("GET", "/admin/integrations", configurations.integrations),
    ("POST", "/admin/integrations/add", configurations.integrations_add),
    ("POST", "/admin/integrations/toggle", configurations.integrations_toggle),
    ("GET", "/admin/board/new", admin.new_board_form),
    ("POST", "/admin/board/new", admin.new_board_create),
    ("GET", "/admin/catalogue", admin.catalogue),
    ("GET", "/admin/time", admin.time_setup),
    ("POST", "/admin/time/role", admin.time_role_add),
    ("POST", "/admin/time/type", admin.time_type_add),
    ("POST", "/admin/time/toggle", admin.time_toggle),
    ("POST", "/admin/catalogue/template", admin.catalogue_template),
    ("POST", "/admin/catalogue/toggle", admin.catalogue_toggle),
    ("POST", "/admin/board/<board_id>/claim", admin.claim_board),
    ("GET", "/admin/board/<board_id>", admin.board_setup),
    ("POST", "/admin/board/<board_id>/settings", admin.save_settings),
    ("POST", "/admin/board/<board_id>/team", admin.add_team),
    ("POST", "/admin/board/<board_id>/starter", admin.apply_starter),
    ("POST", "/admin/board/<board_id>/types", admin.save_types),
    ("POST", "/admin/board/<board_id>/template", admin.save_template),
    ("POST", "/admin/board/<board_id>/template/toggle", admin.toggle_template),
    ("POST", "/admin/board/<board_id>/standard-note", admin.save_standard_note),
    ("POST", "/admin/board/<board_id>/standard-note/toggle", admin.toggle_standard_note),
    ("POST", "/admin/board/<board_id>/reply-policy", admin.save_reply_policy),
    ("POST", "/admin/board/<board_id>/calendar", admin.save_calendar),
    ("POST", "/admin/board/<board_id>/status/save", admin.save_status),
    ("POST", "/admin/board/<board_id>/status/add", admin.add_board_status),
    ("POST", "/admin/board/<board_id>/sla", admin.save_sla),
    ("POST", "/admin/board/<board_id>/roles", admin.save_roles),
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

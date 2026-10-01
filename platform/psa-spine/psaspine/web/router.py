"""Path to view, with a matcher small enough to read in one sitting.

No regex and no framework: a route is a method, a pattern split on '/', and a
handler. A segment written '<name>' captures; everything else matches literally.
That is the whole engine, and it is enough for the fixed set of paths the desk
has. Views receive the captured segments as keyword arguments alongside the
context, and return a Response.
"""
from __future__ import annotations

from .views import schedule as schedule_view
from .views import timesheets as timesheets_view
from .views import recurring as recurring_view
from .views import approvals as approvals_view
from .views import paging as paging_view
from .views import agreements as agreements_view
from .views import finance as finance_view
from .views import sales as sales_view
from .views import members as members_view
from .views import calendar as calendar_view
from .views import audit as audit_view
from .views import tokens as tokens_view
from .views import mail as mail_view
from .views import cmdbsetup as cmdbsetup_view
from .views import smallsetup as smallsetup_view
from .views import inout as inout_view
from .views import live as live_view
from .views import kb as kb_view
from .views import projects as projects_view
from .views import reportwriter as rw_view
from .views import (admin, board, companies, configurations, dispatch, files, loop, oncall,
                    portal, reports, rules, search, ticket, uplift)

# (method, pattern, handler). The first pattern that matches the path wins,
# so a literal segment must be listed before a <capture> in the same place.
ROUTES = [
    ("GET", "/", board.index),
    ("GET", "/live", live_view.stamp),
    ("POST", "/bulk", board.bulk),
    ("GET", "/search.json", search.search),
    ("GET", "/reports", reports.index),
    ("GET", "/reports.csv", reports.export_csv),
    ("GET", "/reports/custom", rw_view.index),
    ("GET", "/reports/custom/run", rw_view.run_adhoc),
    ("POST", "/reports/custom/new", rw_view.create),
    ("GET", "/reports/custom/<report_id>", rw_view.detail),
    ("GET", "/reports/custom/<report_id>/csv", rw_view.detail_csv),
    ("POST", "/reports/custom/<report_id>/pin", rw_view.pin),
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
    ("POST", "/ticket/<work_item_id>/approval/request", approvals_view.request),
    ("POST", "/ticket/<work_item_id>/approval/withdraw", approvals_view.withdraw),
    ("POST", "/ticket/<work_item_id>/page", paging_view.page),
    ("POST", "/ticket/<work_item_id>/page/<page_id>/ack", paging_view.ack),
    ("POST", "/ticket/<work_item_id>/page/<page_id>/stop", paging_view.stop),
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
    ("POST", "/ticket/<work_item_id>/schedule/update", ticket.schedule_update),
    ("POST", "/ticket/<work_item_id>/schedule/done", ticket.schedule_done),
    ("POST", "/ticket/<work_item_id>/schedule/ack", ticket.schedule_ack),
    ("POST", "/ticket/<work_item_id>/schedule/lead", ticket.schedule_lead),
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
    ("GET", "/configurations/maintenance.csv", configurations.maintenance_csv_all),
    ("GET", "/configuration/<configuration_id>/maintenance.csv", configurations.maintenance_csv),
    ("POST", "/configurations/new", configurations.create),
    ("GET", "/configuration/<configuration_id>", configurations.detail),
    ("POST", "/configuration/<configuration_id>/update", configurations.update),
    ("POST", "/configuration/<configuration_id>/answers", configurations.answers),
    ("GET", "/dispatch", dispatch.index),
    ("GET", "/schedule", schedule_view.index),
    ("GET", "/time", timesheets_view.index),
    ("POST", "/time/submit", timesheets_view.submit),
    ("POST", "/time/decide", timesheets_view.decide),
    ("POST", "/time/reopen", timesheets_view.reopen),
    ("POST", "/time/capacity", timesheets_view.capacity),
    ("GET", "/finance", finance_view.index),
    ("GET", "/finance/<kind>", finance_view.detail),                    # ?ref=<BizBox reference>
    ("POST", "/finance/<kind>/propose", finance_view.propose),
    ("POST", "/finance/change/<change_id>/cancel", finance_view.cancel_change),
    ("POST", "/ticket/<work_item_id>/finance/link", finance_view.ticket_link),
    ("POST", "/ticket/<work_item_id>/finance/unlink", finance_view.ticket_unlink),
    ("POST", "/agreements/new", agreements_view.create),
    ("GET", "/agreement/<agreement_id>", agreements_view.detail),
    ("POST", "/agreement/<agreement_id>/update", agreements_view.update),
    ("POST", "/agreement/<agreement_id>/status", agreements_view.set_status),
    ("POST", "/agreement/<agreement_id>/item", agreements_view.item_add),
    ("POST", "/agreement/<agreement_id>/item/remove", agreements_view.item_remove),
    ("GET", "/admin/configuration-types", cmdbsetup_view.index),
    ("POST", "/admin/configuration-types/type", cmdbsetup_view.type_add),
    ("POST", "/admin/configuration-types/type/<type_id>", cmdbsetup_view.type_save),
    ("POST", "/admin/configuration-types/type/<type_id>/question", cmdbsetup_view.question_add),
    ("POST", "/admin/configuration-types/status", cmdbsetup_view.status_add),
    ("POST", "/admin/configuration-types/status/<status_id>", cmdbsetup_view.status_save),
    ("POST", "/admin/configuration-types/question/<question_id>", cmdbsetup_view.question_save),
    ("GET", "/admin/priorities", smallsetup_view.pr_index),
    ("POST", "/admin/priorities/<code>", smallsetup_view.pr_save),
    ("GET", "/admin/kb-categories", smallsetup_view.kb_index),
    ("POST", "/admin/kb-categories", smallsetup_view.kb_add),
    ("POST", "/admin/kb-categories/<category_id>", smallsetup_view.kb_save),
    ("GET", "/admin/companies", smallsetup_view.co_index),
    ("POST", "/admin/companies/status", smallsetup_view.co_list_add_status),
    ("POST", "/admin/companies/type", smallsetup_view.co_list_add_type),
    ("POST", "/admin/companies/status/<ident>", smallsetup_view.co_list_save_status),
    ("POST", "/admin/companies/type/<ident>", smallsetup_view.co_list_save_type),
    ("POST", "/admin/companies/<entity_id>", smallsetup_view.co_set),
    ("GET", "/inout", inout_view.index),
    ("POST", "/inout/me", inout_view.me),
    ("GET", "/admin/mail", mail_view.index),
    ("POST", "/admin/mail/exclude", mail_view.exclude),
    ("POST", "/admin/mail/exclude/remove", mail_view.exclude_remove),
    ("GET", "/admin/audit", audit_view.index),
    ("GET", "/admin/audit.csv", audit_view.export),
    ("GET", "/admin/api-tokens", tokens_view.index),
    ("POST", "/admin/api-tokens/new", tokens_view.create),
    ("POST", "/admin/api-tokens/<token_id>/toggle", tokens_view.toggle),
    ("GET", "/admin/members", members_view.index),
    ("POST", "/admin/members/add", members_view.add),
    ("GET", "/admin/member/<member>", members_view.detail),
    ("POST", "/admin/member/<member>/save", members_view.save),
    ("POST", "/admin/member/<member>/board", members_view.board),
    ("POST", "/admin/member/<member>/board/remove", members_view.board_remove),
    ("POST", "/admin/member/<member>/sysadmin", members_view.sysadmin),
    ("POST", "/admin/member/<member>/role", members_view.role),
    ("POST", "/admin/member/<member>/capacity", members_view.capacity),
    ("POST", "/admin/member/<member>/deactivate", members_view.deactivate),
    ("POST", "/admin/member/<member>/reactivate", members_view.reactivate),
    ("GET", "/my/profile", members_view.profile),
    ("POST", "/my/profile/save", members_view.profile_save),
    ("POST", "/my/profile/feed", members_view.profile_feed),
    ("GET", "/calendar", calendar_view.index),                          # ?member=&view=day|week|month&date=
    ("GET", "/calendar/feed/<token>", calendar_view.feed),              # <token>.ics; no session: the token is the key
    ("GET", "/sales", sales_view.index),                                # ?stage=OPEN|ALL|<stage>&q=
    ("POST", "/sales/new", sales_view.create),
    ("GET", "/sales/<opportunity_id>", sales_view.detail),
    ("POST", "/sales/<opportunity_id>/update", sales_view.update),
    ("POST", "/sales/<opportunity_id>/stage", sales_view.stage),
    ("POST", "/sales/<opportunity_id>/quote", sales_view.new_quote),
    ("GET", "/quote/<quote_id>", sales_view.quote_detail),
    ("POST", "/quote/<quote_id>/line", sales_view.line_add),
    ("POST", "/quote/<quote_id>/line/remove", sales_view.line_remove),
    ("POST", "/quote/<quote_id>/status", sales_view.quote_status),
    ("GET", "/projects", projects_view.index),
    ("POST", "/projects/new", projects_view.create),
    ("GET", "/project/<project_id>", projects_view.detail),
    ("POST", "/project/<project_id>/phase", projects_view.add_phase),
    ("POST", "/project/<project_id>/phase/status", projects_view.phase_status),
    ("POST", "/project/<project_id>/ticket", projects_view.link_ticket),
    ("POST", "/project/<project_id>/update", projects_view.update),
    ("POST", "/project/<project_id>/finance", projects_view.link_finance),
    ("POST", "/ticket/<work_item_id>/project", projects_view.ticket_set),
    ("GET", "/kb", kb_view.index),
    ("GET", "/kb/new", kb_view.new_form),
    ("POST", "/kb/new", kb_view.create),
    ("GET", "/kb/<article_id>", kb_view.detail),
    ("GET", "/kb/<article_id>/edit", kb_view.edit_form),
    ("POST", "/kb/<article_id>/save", kb_view.save),
    ("POST", "/kb/<article_id>/status", kb_view.set_status),
    ("POST", "/kb/<article_id>/file", kb_view.upload),
    ("GET", "/kb/<article_id>/file/<file_id>", kb_view.file),
    ("POST", "/kb/<article_id>/file/<file_id>/review", kb_view.file_review),
    ("POST", "/kb/<article_id>/file/<file_id>/remove", kb_view.file_remove),
    ("POST", "/ticket/<work_item_id>/kb", kb_view.link_ticket),
    ("GET", "/my/help", kb_view.portal_index),
    ("GET", "/my/help/<article_id>", kb_view.portal_detail),
    ("GET", "/my/help/<article_id>/file/<file_id>", kb_view.portal_file),
    ("POST", "/schedule/book", schedule_view.book),
    ("POST", "/schedule/slot", schedule_view.slot),
    ("POST", "/schedule/move", schedule_view.move),
    ("POST", "/schedule/block", schedule_view.block_add),
    ("POST", "/schedule/block/remove", schedule_view.block_remove),
    ("POST", "/dispatch/assign", dispatch.assign),
    ("POST", "/dispatch/view", dispatch.view),
    ("GET", "/oncall", oncall.index),
    ("POST", "/oncall/add", oncall.add),
    # The requester portal. Ownership, not board membership, is the filter.
    ("GET", "/my", portal.index),
    ("GET", "/my/approvals", approvals_view.portal_index),
    ("POST", "/my/approvals/<approval_id>/decide", approvals_view.portal_decide),
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
    ("GET", "/admin/recurring", recurring_view.index),
    ("POST", "/admin/recurring/add", recurring_view.add),
    ("POST", "/admin/recurring/toggle", recurring_view.toggle),
    ("POST", "/admin/recurring/run", recurring_view.run),
    ("GET", "/admin/integrations", configurations.integrations),
    ("POST", "/admin/integrations/add", configurations.integrations_add),
    ("POST", "/admin/integrations/toggle", configurations.integrations_toggle),
    ("POST", "/admin/integrations/teams/add", configurations.teams_add),
    ("POST", "/admin/integrations/teams/toggle", configurations.teams_toggle),
    ("POST", "/admin/integrations/teams/pages", configurations.teams_pages),
    ("GET", "/admin/board/new", admin.new_board_form),
    ("POST", "/admin/board/new", admin.new_board_create),
    ("GET", "/admin/catalogue", admin.catalogue),
    ("GET", "/admin/departments", admin.departments),
    ("POST", "/admin/departments/save", admin.departments_save),
    ("POST", "/admin/departments/add", admin.departments_add),
    ("GET", "/admin/calendars", admin.calendars),
    ("POST", "/admin/calendars", admin.calendars_add),
    ("POST", "/admin/calendars/save", admin.calendars_save),
    ("POST", "/admin/calendars/holiday-list", admin.holiday_list_add),
    ("POST", "/admin/calendars/holiday-list/save", admin.holiday_list_save),
    ("POST", "/admin/calendars/holiday", admin.holiday_add),
    ("POST", "/admin/calendars/holiday/remove", admin.holiday_remove),
    ("GET", "/admin/roles", admin.roles_setup),
    ("POST", "/admin/roles/add", admin.roles_add),
    ("POST", "/admin/roles/assign", admin.roles_assign),
    ("POST", "/admin/roles/<role_id>/save", admin.roles_save),
    ("POST", "/admin/roles/<role_id>/default", admin.roles_default),
    ("POST", "/admin/roles/<role_id>/retire", admin.roles_retire),
    ("POST", "/admin/roles/<role_id>/restore", admin.roles_restore),
    ("GET", "/admin/schedule", admin.schedule_setup),
    ("POST", "/admin/schedule/add", admin.schedule_setup_add),
    ("POST", "/admin/schedule/save", admin.schedule_setup_save),
    ("GET", "/admin/time", admin.time_setup),
    ("POST", "/admin/time/role", admin.time_role_add),
    ("POST", "/admin/time/type", admin.time_type_add),
    ("POST", "/admin/time/toggle", admin.time_toggle),
    ("POST", "/admin/catalogue/template", admin.catalogue_template),
    ("POST", "/admin/catalogue/toggle", admin.catalogue_toggle),
    ("POST", "/admin/catalogue/area", admin.catalogue_area_add),
    ("POST", "/admin/catalogue/area/save", admin.catalogue_area_save),
    ("POST", "/admin/catalogue/subtype", admin.catalogue_subtype_add),
    ("POST", "/admin/catalogue/subtype/save", admin.catalogue_subtype_save),
    ("POST", "/admin/catalogue/item", admin.catalogue_item_add),
    ("POST", "/admin/catalogue/item/save", admin.catalogue_item_save),
    ("POST", "/admin/catalogue/associate", admin.catalogue_associate),
    ("POST", "/admin/catalogue/approval", admin.catalogue_approval),
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
    ("POST", "/admin/board/<board_id>/emails", admin.save_emails),
    ("POST", "/admin/board/<board_id>/emails/status", admin.save_status_email),
    ("POST", "/admin/board/<board_id>/emails/status-all", admin.save_all_status_emails),
    ("POST", "/admin/board/<board_id>/assign", admin.save_auto_assign),
    ("POST", "/admin/board/<board_id>/assign/rule", admin.save_auto_assign_rule),
    ("POST", "/admin/board/<board_id>/assign/rule/remove", admin.remove_auto_assign_rule),
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

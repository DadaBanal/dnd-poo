from g_common import *
from g_desk import PRIO_WIDGET

RW = {
    "TICKETS": {"label": "Tickets", "date": "opened", "state": True, "hours": False, "cols": ["Ticket", "Summary", "Board", "State", "Priority", "Type", "Owner", "Source", "Opened", "Closed"]},
    "TIME": {"label": "Time entries", "date": "worked on", "state": False, "hours": True, "cols": ["Ticket", "Member", "Worked on", "Board", "Hours", "Work role", "Work type", "Charge method"]},
    "VISITS": {"label": "Scheduled visits", "date": "starts", "state": False, "hours": False, "cols": ["Ticket", "Member", "Starts", "Ends", "Board", "Status", "Where"]},
    "PROJECTS": {"label": "Projects", "date": "starts", "state": True, "hours": False, "cols": ["Project", "Name", "Manager", "Status", "Board", "Starts", "Ends", "Budget hours"]},
    "CONFIGURATIONS": {"label": "Configurations", "date": "created", "state": True, "hours": False, "cols": ["Configuration", "Name", "Type", "Company", "Status", "Contact", "Location", "Vendor", "Purchased", "Warranty ends", "Installed", "Agreement", "Serial", "Model", "Last seen"]},
    "MAINTENANCE": {"label": "Maintenance: tickets by configuration", "date": "opened", "state": True, "hours": True, "cols": ["Configuration", "Type", "Serial", "Ticket", "Summary", "Board", "Ticket type", "State", "Opened", "Closed", "Owner"]},
    "KNOWLEDGE": {"label": "Knowledge articles", "date": "updated", "state": True, "hours": False, "cols": ["Article", "Title", "Status", "For", "Board", "Uses"]},
}


def reports_body():
    return "".join([
        HERO("Reports and the uplift evidence", "The service in numbers, your own saved reports over the desk's datasets, and the uplift evidence page.",
             ["For service managers", "Reports module", "About 8 minutes"]),
        S("r-rep", "Reports", "The Reports page",
          FIG("reports", "Reports: opened and closed by month, backlog, clocks met, median times, the mix by board, type and source, satisfaction and utilisation."),
          UL(["Everything is worked out when you open it, from the tickets and their clocks, never from a stored figure.", "Scoped to the boards you are on; a count never names a ticket.", "Every table downloads as CSV."]),
          who=["Reports: Read"]),
        S("r-rw", "Reports", "Your own reports",
          FIG("reportwriter", "The report writer: saved reports, and a new one from a dataset."),
          WIDGET("Try it: build a report", '<div class="w-row"><label>Dataset<select class="ds"></select></label><label>Group by<select class="grp"></select></label></div><div class="cols"></div><div class="w-out out"></div>', "report", {"datasets": RW}),
          UL(["You pick from each dataset's own columns; no query is ever typed.", "Filters: board, a date range on the dataset's date, and a state where it has one.", "Save it, share it, pin it, and download it as CSV."]),
          who=["Reports: Write to save"]),
        S("r-up", "Uplift", "The uplift evidence",
          FIG("uplift", "Uplift: the evidence behind the service's hours and work by commercial classification, deliberately unflattering where the evidence is thin."),
          who=["Service managers"]),
        S("r-quiz", "Reference", "Check yourself", QUIZ()),
    ])


GUIDES.append({"slug": "Reports", "title": "Reports and Uplift guide", "for": "service managers", "blurb": "The Reports page, the report writer's datasets, saved reports and CSV, and the uplift evidence.",
    "rail_sub": "Reports module", "search": "Search: dataset, CSV, uplift…", "body": reports_body, "tours": {},
    "quiz": [["Can a report show a restricted board you are not on?", ["Yes", "No"], 1, "Every dataset is limited to your boards."],
             ["Do you type SQL in the report writer?", ["Yes", "No"], 1, "You pick columns; the desk writes every query."]]})


def portal_body():
    wording = [("New", "Received — waiting for someone to pick it up"), ("Assigned", "Assigned to a technician"), ("In Progress", "Someone is working on it"),
               ("Scheduled", "A fix is planned — we will tell you when"), ("Waiting on Requester", "We need something from you"), ("Waiting on Vendor", "Waiting on a supplier"),
               ("Awaiting approval", "Waiting for an approval"), ("Resolved", "We think this is fixed — reply if it is not"), ("Closed", "Closed")]
    sel = "<select>" + "".join(f'<option data-p="{E(p)}">{E(s)}</option>' for s, p in wording) + "</select>"
    return "".join([
        HERO("PMC Requests", "How to ask Dada IT for help, follow your request, approve a colleague's, and find a quick answer in Help.",
             ["For every PMC staff member", "About 8 minutes"], "green"),
        S("q-raise", "Asking for help", "Raise a request",
          TOUR("portal"),
          PRIO_WIDGET,
          WIDGET("Practise: would the desk flag this?", '<textarea>Printer in Ward 3, room 302, prints blank labels since 7am. Patient name: J. Cruz is waiting for her wristband.</textarea><div class="w-out out"></div>', "phi"),
          who=["Everyone"]),
        S("q-follow", "Following up", "Follow your request",
          FIG("portal-request", "A request: its status, the updates written for you, and a box to add to it."),
          WIDGET("Try it: what each status tells you", '<div class="w-row"><label>If the desk sets the status to' + sel + '</label></div><div class="w-out out"></div>', "portal"),
          UL(["Add a note or a photo at the foot of the request.", "Reply to the desk's email, keeping the reference in the subject.", "Emails never carry the details; they say something changed and link here."]),
          FIG("portal-closed", "A closed request asks one question once."),
          who=["Everyone"]),
        S("q-approve", "Following up", "Approve a request",
          FIG("portal-approvals2", "Approvals: requests waiting for your yes or no."),
          STEPPER("Try an approval", "WAIT", {
              "WAIT": {"label": "Waiting for you", "tone": "amber", "text": "The ticket is parked in Awaiting approval; its resolve clock is paused; you had one email.", "next": [["YES", "Approve"], ["NO", "Decline", "why", True, "A decline says why, so the desk and the requester know."]]},
              "YES": {"label": "Approved", "tone": "green", "text": "Your decision goes on the ticket as a note the requester reads, and the ticket goes back to where it was.", "end": "Decisions are final and audited."},
              "NO": {"label": "Declined", "tone": "red", "text": "Your reason goes on the ticket as a note the requester reads.", "end": "Decisions are final and audited."}}),
          who=["Department approvers"]),
        S("q-help", "Quick answers", "Help articles",
          FIG("portal-help", "Help: answers written by Dada IT."), FIG("portal-article", "An article, with pictures cleared for requesters."), who=["Everyone"]),
        S("q-quiz", "Reference", "Check yourself", QUIZ()),
    ])


GUIDES.append({"slug": "PMC_Requests", "title": "PMC Requests guide", "kind": "req", "for": "every PMC staff member", "blurb": "Raise a request, follow it, approve a colleague's, and use Help. For ward and office staff.",
    "rail_sub": "For ward and office staff", "search": "Search: request, approve, help…", "body": portal_body,
    "tours": {"portal": [["What do you need?", "One line, like a subject."], ["Where it goes", "Your department's board; choose if there are several."],
                         ["Broken, or a need?", "An incident, or a request for access, a new user, a move."], ["Who is affected?", "With the next question this sets the priority."],
                         ["Anything that would help", "Ward, room, machine, since when. Never a patient's details."], ["Send it", "You get a number at once."]]},
    "quiz": [["What may you write about a patient?", ["Initials", "Nothing: ward, room and machine are enough"], 1, "No patient details anywhere."],
             ["Declining an approval needs…", ["Nothing", "A reason"], 1, "A decline says why."],
             ["Waiting on Requester means…", ["It is closed", "The desk needs something from you"], 1, "Reply or add a note."]]})


ROLES = {"modules": {"KNOWLEDGE": "Knowledge base", "PROJECTS": "Projects", "REPORTS": "Reports", "SCHEDULE": "Schedule", "FINANCE": "Finance (BizBox)", "TIME": "Timesheets"},
         "roles": {"Technician (the default)": {"KNOWLEDGE": "WRITE", "PROJECTS": "WRITE", "REPORTS": "READ", "SCHEDULE": "WRITE", "FINANCE": "READ", "TIME": "WRITE"},
                   "Service manager": {"KNOWLEDGE": "ADMIN", "PROJECTS": "ADMIN", "REPORTS": "ADMIN", "SCHEDULE": "ADMIN", "FINANCE": "WRITE", "TIME": "ADMIN"},
                   "Read only": {"KNOWLEDGE": "READ", "PROJECTS": "READ", "REPORTS": "READ", "SCHEDULE": "READ", "FINANCE": "NONE", "TIME": "READ"},
                   "System administrator": {"KNOWLEDGE": "ADMIN", "PROJECTS": "ADMIN", "REPORTS": "ADMIN", "SCHEDULE": "ADMIN", "FINANCE": "ADMIN", "TIME": "ADMIN"}}}

FIRES = [("ON_CREATE", "A ticket is created"), ("ON_STATUS_CHANGE", "The status changes"), ("ON_NOTE_ADDED", "A note is added"), ("ON_OWNER_CHANGE", "The owner changes"),
         ("ON_HANDOVER", "It moves board"), ("ON_SLA_THRESHOLD", "SLA time passes a mark"), ("ON_SCHEDULE", "On a schedule")]
MODES = [("ONCE", "Once per ticket"), ("MULTIPLE_TIMES", "A number of times"), ("CONTINUOUSLY", "Every time, no limit")]
FIELDS = [("", "(no condition)"), ("TICKET.PRIORITY", "Priority"), ("TICKET.RECORD_TYPE", "Type"), ("TICKET.STATUS", "Status"), ("TICKET.OWNER", "Owner"), ("TICKET.BOARD", "Board"),
          ("TICKET.SOURCE", "Source"), ("TICKET.AGE_MINUTES", "Minutes since opened"), ("TICKET.IDLE_MINUTES", "Minutes since last update"), ("TICKET.SLA_PERCENT", "SLA used (%)")]
OPS = [("EQ", "is"), ("NE", "is not"), ("IN", "is one of"), ("NOT_IN", "is none of"), ("GT", ">"), ("GTE", "≥"), ("LT", "<"), ("LTE", "≤"), ("IS_NULL", "is empty"), ("IS_NOT_NULL", "is set"), ("CONTAINS", "contains")]
ACTIONS = [("NOTIFY", "Notify"), ("ESCALATE", "Escalate to"), ("SET_STATUS", "Set status"), ("SET_BOARD", "Move to board"), ("ASSIGN_OWNER", "Assign owner"),
           ("ADD_NOTE", "Add an internal note"), ("APPLY_TEMPLATE", "Apply a ticket template"), ("FLAG", "Flag for review")]
RROLES = [("SERVICE_MANAGER", "Service manager"), ("DISPATCH", "Dispatch"), ("ON_CALL", "On call"), ("DUTY_MANAGER", "Duty manager"), ("TEAM_LEADER", "Team leader"), ("OWNER", "Owner"), ("REQUESTER", "Requester")]
CH = [("EMAIL", "by email"), ("TEAMS", "as a card in a Teams channel"), ("PAGE", "as a page, repeated until answered")]


def sel(cls, pairs, selected=None):
    return f'<select class="{cls}">' + "".join(f'<option value="{k}"{" selected" if k == selected else ""}>{E(v)}</option>' for k, v in pairs) + "</select>"


def setup_body():
    rule = ('<div class="w-row"><label>Fires when' + sel("ev", FIRES) + '</label><label>Runs' + sel("md", MODES) + "</label></div>"
            '<div class="w-row"><label>When' + sel("fd", FIELDS, "TICKET.PRIORITY") + '</label><label>&nbsp;' + sel("op", OPS) + '</label><label>&nbsp;<input class="val" type="text" value="P1"></label></div>'
            '<div class="w-row"><label>Action' + sel("ac", ACTIONS, "ESCALATE") + '</label><label>Who' + sel("ro", RROLES, "ON_CALL") + '</label><label>How' + sel("ch", CH, "PAGE") + '</label>'
            '<label>Teams channel' + sel("tm", [("", "(none)"), ("desk-alerts", "desk-alerts")]) + "</label></div><div class=\"w-out out\"></div>")
    assign = ('<table class="wt"><thead><tr><th>Member</th><th>Access</th><th>Open tickets</th><th>Active</th></tr></thead><tbody>'
              + "".join(f'<tr data-m="{m}"><td>{m}</td><td><select><option{" selected" if a == "ADMIN" else ""}>ADMIN</option><option{" selected" if a == "WORK" else ""}>WORK</option><option{" selected" if a == "READ" else ""}>READ</option></select></td>'
                        f'<td><input type="number" value="{o}" min="0"></td><td><input type="checkbox"{" checked" if act else ""}></td></tr>'
                        for m, a, o, act in [("alice", "ADMIN", 4, True), ("bob", "WORK", 2, True), ("carol", "WORK", 2, True), ("dave", "READ", 0, True)])
              + '</tbody></table><div class="w-row"><label>Board mode<select class="mode"><option value="OFF">Nobody</option><option value="LEAST_LOADED" selected>Least loaded</option><option value="TEAM_LEADER">The default team\'s leader</option></select></label>'
              '<label>Team leader<select class="lead"><option>alice</option><option>bob</option><option>carol</option><option>dave</option></select></label>'
              '<label>Rule for Printer › Failure<select class="rule"><option value="">(no rule)</option><option>bob</option><option>carol</option><option>dave</option></select></label>'
              '<label>The new ticket is about<select class="pair"><option value="PRINTER">Printer › Failure</option><option value="OTHER">Network › Wi-Fi</option></select></label>'
              '<label style="flex-direction:row;align-items:center;gap:8px"><input class="has" type="checkbox"> It arrives with an owner</label></div><div class="w-out out"></div>')
    return "".join([
        HERO("Setup and administration", "Every page a board administrator or system administrator uses: boards and their tabs, the catalogue, members and security roles, departments, calendars, rules, recurring tickets, integrations, email, audit and API tokens.",
             ["For board and system administrators", "Setup", "About 30 minutes"]),
        S("a-land", "Start here", "Setup at a glance",
          FIG("admin", "Setup: the cards you may open."),
          LEAD("A board's own settings take Admin on that board. Everything else takes a system administrator. Every change is audited."),
          who=["Administrators"]),
        S("a-board", "Boards", "A board's tabs",
          IMGPICK([("board-setup", "Board", "Owner and deputy, restricted, closed loop, emails to requester and owner, the survey and its question, time defaults, calendar, reply policy."),
                   ("board-types", "Types", "Which Types the board takes: Incident, Request, Problem, Event on a service board."),
                   ("board-statuses", "Statuses", "Each status's milestone (which clocks it stops or pauses), default, closed, and what the requester reads."),
                   ("board-sla", "SLA", "Targets per record type × priority × clock. The starter targets are placeholders to set."),
                   ("board-templates", "Templates", "Recipes for repeatable work, with their tasks."),
                   ("board-notes", "Standard notes", "Canned replies with their flag."),
                   ("board-members", "Members & roles", "Members with Read, Work or Admin, teams and the four board roles."),
                   ("board-emails", "Emails", "The words of the six emails the board sends."),
                   ("board-assign", "Auto-assign", "Who a new unowned ticket goes to.")]),
          FIG("new-board", "New board: a service, change or project board."),
          who=["Board admins"]),
        S("a-emails", "Boards", "Emails in the board's own words",
          WIDGET("Try it: write the Opened email", '<div class="w-row" style="flex-direction:column;align-items:stretch"><label>Subject<input class="subj" type="text" value="{board} has your request"></label>'
                 '<label>Body<textarea class="body">Thank you. {board} has your request {ticket} and will update you on the portal. {summary}</textarea></label></div><div class="w-out out"></div>', "tpl"),
          P("Only <code>{ticket}</code>, <code>{board}</code>, <code>{actor}</code> and <code>{when}</code>. Remove <code>{summary}</code> above to see it save: a subject and a body leave the building."),
          H("A different email per status"),
          UL(["As well as the six standing emails, a board can give <b>its own words to any one of its statuses</b>: what the requester reads when a ticket "
              "moves to <i>Waiting on Vendor</i> need not be what they read when it moves to <i>Scheduled</i>.",
              "A status with no words of its own falls back to the board\u2019s standing <i>Updated</i> email, so there is never a status that says nothing.",
              "<b>The reply-from address is the address they wrote to.</b> A board that claims both <code>helpdesk@</code> and <code>biomed@</code> answers each "
              "requester from the one they used, so a reply threads where they expect it."]),
          who=["Board admins"]),
        S("a-assign", "Boards", "Auto-assign", WIDGET("Try it: who gets the next ticket?", assign, "assign"),
          UL(["A rule per Subtype › Item names the member; with no rule the mode decides.", "A ticket that arrives with an owner keeps it.", "A member who left the board, reads only, or was deactivated is never assigned.", "The owner is emailed when the board emails owners."]),
          who=["Board admins"]),
        S("a-cat", "Boards", "The service catalogue",
          FIG("catalogue", "Setup › Catalogue: Type, Subtype and Item, which boards each pair belongs to, and approval."),
          UL(["<b>Load the Dada PSA template</b> adds the starter catalogue; it never overwrites.", "A pair can carry a priority floor and require approval.", "Retire rather than delete; tickets keep what they had."]),
          who=["System administrators"]),
        S("a-prio", "Boards", "Priorities",
          LEAD("Setup \u203a Priorities holds the four priorities: the name a badge shows, its colour, the order they sort in, and which one is the default."),
          UL(["<b>The codes P1 to P4 are fixed</b> and cannot be renamed away, because every SLA target and every catalogue floor names them.",
              "<b>The words and the colours are the hospital\u2019s.</b> Change <i>P1</i> to read <i>Critical</i> and every badge on every page follows.",
              "Nobody types a priority when a ticket is raised \u2014 the two questions work it out. A technician may still set one by hand afterwards; the ticket "
              "then records that it was overridden, with a reason if one was given. Setting it back to <i>from the two questions</i> hands it to the matrix again."]),
          NOTE("info", "A desk that has not yet taken the priorities table reads the four defaults, so every page still opens; the page says so rather than "
                       "looking empty."),
          who=["System administrators"]),
        S("a-roles", "People", "Members and security roles",
          FIG("member", "A member's page: boards and access, role, capacity, and deactivate."),
          WIDGET("Try it: what each starter role opens", '<div class="w-row"><label>Role' + sel("x", [(k, k) for k in ROLES["roles"]]) + '</label></div><div class="out"></div>', "roles", ROLES),
          FIG("roles", "Setup › Security roles: each module at None, Read, Write or Admin; one default role."),
          NOTE("info", "A role never widens a board. Tickets are still governed by board membership, and a restricted board stays members-only."),
          UL(["<b>Deactivate</b> someone who has left: it takes them off every board and future rota slot, and says what it did.", "Each person's hours a week sets their utilisation."]),
          H("Who is a system administrator"),
          UL(["<b>It is a tick on the member\u2019s own page</b>, not a separate list kept somewhere else. One person, one record: the same page that holds "
              "their boards, their role and their hours says whether they administer the desk.",
              "It works the same whether they sign in with Windows or with a desk account \u2014 the answer comes from the member record either way.",
              "<b>The last system administrator cannot be taken off.</b> Make somebody else one first; otherwise the desk could be left with nobody who can "
              "undo it."]),
          who=["System administrators"]),
        S("a-dept", "People", "Departments",
          FIG("departments", "Setup › Departments: which boards each department may raise to, and its approver."),
          UL(["The list arrives as a one-column CSV from payroll (no people), or is typed by hand.", "A department with no board ticked lands on the unrouted queue.", "The approver receives that department's approvals."]),
          who=["System administrators"]),
        S("a-cal", "Clocks", "Calendars and holidays",
          FIG("calendars", "Setup › Calendars: working weeks and holiday lists; a board's clocks run on its calendar."),
          UL(["A blank start or end closes the day; 24:00 is midnight at its end.", "A holiday may close part of a day.", "Calendars are retired, never deleted."]),
          who=["System administrators"]),
        S("a-rules", "Automation", "Workflow rules",
          TOUR("rule"),
          WIDGET("Try it: build a rule", rule, "rule"),
          UL(["Events fire as they happen; timed events (SLA marks, schedules) are checked every minute.", "Every action says which rule did it on the ticket."]),
          who=["Board admins"]),
        S("a-rec", "Automation", "Recurring tickets",
          FIG("recurring", "Setup › Recurring tickets: a template raised on a cadence."),
          WIDGET("Try it: when the next tickets are raised", '<div class="w-row"><label>First due<input class="first" type="date" value="2026-10-31"></label><label>Cadence' + sel("cad", [("DAILY", "Daily"), ("WEEKLY", "Weekly"), ("MONTHLY", "Monthly"), ("QUARTERLY", "Quarterly"), ("YEARLY", "Yearly")], "MONTHLY") + '</label><label>Every<input class="every" type="number" value="1" min="1"></label></div><div class="w-out out"></div>', "recur"),
          who=["Board admins"]),
        S("a-int", "Connections", "Integrations, email, audit and tokens",
          IMGPICK([("integrations", "Integrations", "Links out (remote control) and Teams channels."),
                   ("mail", "Email connector", "The addresses each board claims (a board may claim several, and an address belongs to exactly one board), excluded senders and domains, the last week's mail and whether it became tickets."),
                   ("audit", "Audit", "Every change: who, when, what, where from. Filter and export."),
                   ("tokens", "API tokens", "One board and one scope each; shown once."),
                   ("config-types", "Configuration types", "Types and statuses, and each type's questions."),
                   ("kb-categories", "Knowledge categories", "Names readers browse by."),
                   ("company-setup", "Company status and type", "The words on each company."),
                   ("schedule-setup", "Schedule setup", "Visit statuses and places."),
                   ("time-setup", "Time setup", "Work roles and types.")]),
          who=["System administrators"]),
        S("a-quiz", "Reference", "Check yourself", QUIZ()),
    ])


GUIDES.append({"slug": "Setup", "title": "Setup and Administration guide", "for": "board and system administrators",
    "blurb": "Boards and every tab, the catalogue, members and security roles, departments, calendars, rules, recurring tickets, integrations, email, audit and tokens.",
    "rail_sub": "Setup · for administrators", "search": "Search: role, rule, calendar, token…", "body": setup_body,
    "tours": {"rule": [["Off", "A rule starts off."], ["Switch on", "Only once every event is tested."], ["Not tested", "Test first."],
                       ["The actions", "Escalate to the on-call as a page; notify the service manager."], ["Test against open tickets", "How many open tickets match now."], ["Conditions", "Up to three, read left to right."]]},
    "quiz": [["Does a Service manager role let you see a restricted board you are not on?", ["Yes", "No"], 1, "A role never widens a board."],
             ["A rule was just edited. It is…", ["Still on", "Off until tested again"], 1, "Editing switches it off."],
             ["An email template may include…", ["{summary}", "{ticket}"], 1, "Only {ticket}, {board}, {actor}, {when}."]]})

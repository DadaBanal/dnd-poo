from g_common import *

STATUSES = [["New", "NOT_RESPONDED"], ["Assigned", "NOT_RESPONDED"], ["In Progress", "RESPONDED"], ["Scheduled", "RESOLUTION_PLAN"],
            ["Waiting on Requester", "NO_ESCALATION"], ["Waiting on Vendor", "NO_ESCALATION"], ["Awaiting approval", "NO_ESCALATION"],
            ["Resolved", "RESOLVED"]]

PRIO_WIDGET = WIDGET("Try it: how the two questions set the priority",
    '<div class="q"><b>Who is affected?</b><div class="opts" data-k="i"><button class="opt" data-v="I3">Just me</button><button class="opt" data-v="I2">My ward or department, or several people</button><button class="opt" data-v="I1">The whole hospital, or a clinical service is down</button></div></div>'
    '<div class="q"><b>Is a patient waiting?</b><div class="opts" data-k="u"><button class="opt" data-v="U3">No</button><button class="opt" data-v="U2">Yes, but we have a workaround</button><button class="opt" data-v="U1">Yes: care has stopped, or there is a safety risk</button></div></div>'
    '<div class="result"><div class="big">?</div><div class="prioTxt" style="flex:1 1 280px">Answer both questions.</div></div>'
    '<div class="tw"><table class="matrix"><thead><tr><th></th><th>No patient waiting</th><th>Waiting, with a workaround</th><th>Care stopped or unsafe</th></tr></thead><tbody>'
    '<tr><th>Just me</th><td data-c="I3U3"><span class="p p4">P4</span></td><td data-c="I3U2"><span class="p p4">P4</span></td><td data-c="I3U1"><span class="p p3">P3</span></td></tr>'
    '<tr><th>Ward or several</th><td data-c="I2U3"><span class="p p4">P4</span></td><td data-c="I2U2"><span class="p p3">P3</span></td><td data-c="I2U1"><span class="p p2">P2</span></td></tr>'
    '<tr><th>Whole hospital</th><td data-c="I1U3"><span class="p p3">P3</span></td><td data-c="I1U2"><span class="p p2">P2</span></td><td data-c="I1U1"><span class="p p1">P1</span></td></tr></tbody></table></div>'
    '<p style="font-size:13.5px;color:var(--text-3);margin:0">Nobody types a priority. A catalogue item can carry a floor that lifts it, and work that touches care is never below P2.</p>', "prio")

NOTE_CHOOSER = CHOOSER("Which kind of note should I write?", [
    ("d", "I am telling the requester what happens next", "<b>A Discussion note.</b> The requester reads it on PMC Requests, and gets one email saying there is an update (if the board sends them). A second update before the first email has gone adds nothing."),
    ("i", "It is for colleagues only", "<b>An Internal note.</b> Shaded amber on the ticket. Never emailed, never on PMC Requests."),
    ("r", "I am saying how it was fixed", "<b>A Resolution note.</b> The requester can read it. If the fix will come up again, write a knowledge article from it.")])


def desk_body():
    return "".join([
        HERO("The Service Desk", "Boards, tickets, notes, clocks and everything a technician does to a ticket, from the moment it lands to the moment it closes.",
             ["For technicians and service managers", "Boards and tickets", "About 25 minutes"]),
        S("d-boards", "Boards", "Boards and membership",
          LEAD("A board is one team's queue. You see a board's tickets only if you are its member, with one of three levels."),
          TABLE(["Membership", "You can"], [["Read", "See the board and its tickets."], ["Work", "Also take, note, time, schedule and change tickets."],
                                            ["Admin", "Also run the board's Setup: statuses, SLA, templates, notes, members, emails, auto-assign."]]),
          GRID([("Service board", "Incidents, requests, problems and events, with SLA clocks. The PMO Helpdesk is one."),
                ("Change board", "Changes, with assessment, approval and scheduling. See the Change guide."),
                ("Project board", "Project work with no SLA clocks. See the Projects guide."),
                ("Restricted board", "Only its members see it, and every read of its tickets is audited, a system administrator's included.")]),
          who=["Technicians", "Service managers"]),
        S("d-board", "Boards", "The Service Board",
          LEAD("Every open ticket on your boards, worst clock first."),
          TOUR("board"),
          H("Everyday moves"),
          UL(["<b>Filter</b> by board, status, owner, priority, type, source and words; <b>save the view</b> under a name for tomorrow.",
              "<b>Tick rows</b> to change status, owner or board together, or attach them to a parent ticket.",
              "<b>Keys:</b> <kbd>j</kbd> <kbd>k</kbd> move, <kbd>x</kbd> ticks, <kbd>Enter</kbd> opens, <kbd>n</kbd> new ticket, <kbd>/</kbd> search, <kbd>Ctrl</kbd> <kbd>K</kbd> jumps anywhere."]),
          who=["Technicians"]),
        S("d-prio", "Tickets", "Priority",
          LEAD("Priority is worked out from two plain questions, never typed."), PRIO_WIDGET, who=["Everyone"]),
        S("d-clocks", "Tickets", "The SLA clocks",
          LEAD("Three clocks run on every service ticket, each against a target for its priority, on the board's working hours and holidays."),
          TABLE(["Clock", "Stops when the ticket reaches", "Paused by a waiting status?"],
                [["Respond", "In Progress, Scheduled, Resolved (any status that counts as responded)", "Never: parking a ticket is not a response"],
                 ["Resolution plan", "Scheduled or Resolved", "Yes"], ["Resolve", "Resolved", "Yes"]]),
          WIDGET("Try it: move a ticket and watch its clocks", '<div class="moves"></div><div class="out"></div>', "clocks", {"statuses": STATUSES}),
          H("Reading the chips on the board"),
          TABLE(["Chip", "Means"], [['<span class="sla ok">R ✓</span>', "Respond met."], ['<span class="sla warn">P 40m</span>', "Resolution plan due in 40 minutes."],
                                     ['<span class="sla bad">S -2d</span>', "Resolve target passed by two days."], ['<span class="sla pause">S paused</span>', "Stopped while the ticket waits."]]),
          NOTE("info", "The starter targets are placeholders: P1 respond 15 minutes, plan 1 hour, resolve 4 hours; P4 respond 8 hours, plan 1 day, resolve 3 days. Each board's service manager sets its own on the SLA tab."),
          who=["Technicians", "Service managers"]),
        S("d-ticket", "Tickets", "The ticket page",
          LEAD("One page: the clocks across the top, the activity on the left, and cards on the right you can reorder, fold, and move between columns."),
          TOUR("ticket"),
          FIG("ticket-full", "The whole ticket page, with every card."),
          H("The cards"),
          TABLE(["Card", "What you do there"],
                [["Ticket", "Board, status, owner, company, contact, type and Subtype › Item, and the two priority questions."],
                 ["Time", "Record time: start and end or hours, a deduction, the work role and type, the bill option and the charge method."],
                 ["Tasks", "A checklist; ticking records who and when. A template can add tasks."],
                 ["Schedule", "Book a visit for yourself or a colleague: status, where, lead, done, acknowledged."],
                 ["Family", "Attach child tickets, or merge a duplicate into this one."],
                 ["Files", "Photos and documents, checked for patient details before a requester sees them."],
                 ["Configurations", "The machines the ticket is about, with a remote-control launch where set up."],
                 ["Knowledge", "Articles for this Subtype › Item first; link the one that helped."],
                 ["Finance", "BizBox records the ticket concerns."],
                 ["Approvals", "Ask a person to approve before the work is done."]]),
          who=["Technicians"]),
        S("d-notes", "Tickets", "Notes and emails",
          NOTE_CHOOSER,
          UL(["<b>Standard notes</b> are a board's canned replies. Each carries its flag, so a <i>we have your request</i> reply cannot land as internal by accident.",
              "<b>Emails never carry the summary or a note.</b> They say something changed and link to PMC Requests.",
              "Each board decides whether requesters and owners get emails, and in what words (Setup › the board › Emails)."]),
          who=["Technicians"]),
        S("d-family", "Tickets", "Children, duplicates and templates",
          CHOOSER("The same problem came in several times. What do I do?", [
              ("child", "Several people report one outage", "<b>Attach them as children</b> of the first ticket. One person works the parent; every requester keeps their own ticket. When the parent closes, each child closes on its own board's closed status, and says so. One level only: a child has no children."),
              ("merge", "One person sent the same thing twice", "<b>Merge the duplicate</b> into the original. The duplicate closes, its requester is told on PMC Requests that the work continues on the other ticket, and the notes stay where they were written."),
              ("tpl", "It is routine work we do the same way each time", "<b>Start it from a template</b> (New ticket › template) or apply one to an open ticket: it adds the template's tasks. Applying the same template twice adds nothing twice.")]),
          who=["Technicians"]),
        S("d-files", "Tickets", "Files",
          LEAD("Attach a screenshot, a photo of the machine, a log or a document. Up to 10 MB each."),
          UL(["What is allowed is decided by the file's own bytes: images, PDF, text and logs, CSV, Office documents, email. Programs and scripts are refused.",
              "Photos lose their location and camera details; screenshots lose their hidden text chunks. Nothing visible changes.",
              "Every file is <b>checked for patient details</b> before a requester can see it: Pending, then Cleared or Withheld. A withheld file is served to nobody."]),
          who=["Technicians"]),
        S("d-mail", "Tickets", "Tickets by email",
          CHOOSER("Mail arrives. What happens?", [
              ("new", "A new email to a board's address", "It opens a ticket on the board that claims that address, from the sender, with the subject as the summary and the body as the first note."),
              ("reply", "A reply that keeps [PMC-000123] in the subject", "It is added to that ticket as a note from the sender. No new ticket."),
              ("closed", "A reply to a closed ticket", "On most boards the ticket reopens; a board can instead open a new ticket that mentions the old one (Setup › the board › mail policy)."),
              ("auto", "An out-of-office or a delivery failure", "Recorded, and opens nothing: the desk's own loop guards stop a mail war with an auto-reply."),
              ("excl", "From an excluded sender or domain", "Recorded, and opens nothing; the Email connector page says why.")]),
          who=["Technicians"]),
        S("d-new", "Tickets", "Logging a ticket for someone",
          FIG("new-ticket", "New ticket: the same two questions a requester answers, plus the board, the contact, the company and the Subtype › Item."),
          STEPS(["Press <b>New ticket</b> or <kbd>n</kbd>.", "Choose the board and the contact; the company follows the contact.",
                 "Answer the two questions: the priority is worked out.", "Write the summary and what they told you. No patient details.",
                 "Save. The requester sees it on PMC Requests like any other."]),
          who=["Technicians"]),
        S("d-phone", "Tickets", "On your phone",
          LEAD("Nothing to install. The desk reshapes itself: the board becomes cards; a ticket has Note, Ticket and Call at your thumb."),
          '<div class="phones">' + FIG("phone-board", "The board as cards.") + FIG("phone-ticket", "A ticket, with Call.") + "</div>",
          who=["Technicians"]),
        S("d-quiz", "Reference", "Check yourself", QUIZ()),
    ])


GUIDES.append({
    "slug": "Service_Desk", "title": "Service Desk guide", "for": "technicians and service managers",
    "blurb": "Boards, the Service Board, priority, SLA clocks, the ticket page, notes, children and merges, files, and tickets by email.",
    "rail_sub": "Boards and tickets · September 2026", "search": "Search: clock, note, merge, email…", "body": desk_body,
    "tours": {
        "board": [["The top bar", "Every area of the desk as an icon; hover for its name."], ["New ticket", "Log a call or a walk-up. Shortcut n."],
                  ["The tiles", "Open, SLA breached, due within the hour, unassigned, yours. Click one to filter."],
                  ["Filters", "Board, status, owner, priority, type, source and words; save the set as a view."],
                  ["SLA", "R respond, P resolution plan, S resolve. Worst first."], ["Command palette", "Ctrl K: jump to a page or a ticket."]],
        "ticket": [["The three clocks", "Each clock's target and time left."], ["Page the on-call", "Repeats until acknowledged."],
                   ["Activity tabs", "All, Discussion, Internal, Resolution, System."], ["An internal note", "Shaded amber; never seen by the requester."],
                   ["The Ticket card", "Board, status, owner, company, contact, type."], ["Owner", "Setting someone else emails them when the board says so."]]},
    "quiz": [["One nurse, no patient waiting. Priority?", ["P2", "P3", "P4"], 2, "Just me and no patient waiting is P4."],
             ["A ticket moves to Waiting on Vendor before anyone responded. The Respond clock…", ["Pauses", "Keeps running", "Stops, met"], 1, "Respond is never paused: parking a ticket is not a response."],
             ["Five people report the same outage. You…", ["Merge four into one", "Attach four as children of the first", "Close four"], 1, "Children keep each requester's own ticket and close with the parent."],
             ["An internal note is…", ["Emailed to the requester", "Seen only by the desk", "Shown on PMC Requests"], 1, "Internal notes stay on the desk."],
             ["A reply keeps [PMC-000123] in its subject. It…", ["Opens a new ticket", "Is added to PMC-000123", "Is ignored"], 1, "The reference in the subject threads it onto the ticket."]],
})


# --------------------------------------------------------------------------- DISPATCH & ON-CALL

def dispatch_body():
    return "".join([
        HERO("Dispatch and On-call", "Who picks up what, now: the unrouted queue, today's visits, the people each board names, the on-call rota, and paging that repeats until somebody answers.",
             ["For dispatchers, service managers and whoever is on call", "About 12 minutes"]),
        S("x-dispatch", "Dispatch", "The Dispatch page",
          LEAD("Dispatch answers three questions at a glance: what has landed with nobody owning it, who is out on visits today, and who answers each board."),
          TOUR("dispatch"),
          H("Routing a ticket from the unrouted queue"),
          STEPS(["<b>Read the row:</b> its age and its clocks tell you how long it has waited. The queue ages in plain sight, coloured like the board.",
                 "<b>Choose the board</b> that should own it under Route to.", "<b>Type an owner</b> if you already know who, or leave it for the board's queue or auto-assign.",
                 "<b>Press Route.</b> The ticket moves, its clocks carry on, and the move is on its history."]),
          NOTE("info", "Mail and portal requests land on the unrouted queue when nothing says which board they belong to, for example a department with no board ticked in Setup › Departments."),
          H("The board roles"),
          TABLE(["Role", "Who it is"], [["Service Manager", "Owns the board's service; told of escalations."], ["Dispatch", "Hands out the work."],
                                        ["On Call", "Answers out of hours; the rota overrides the named person."], ["Duty Manager", "Told when the on-call does not answer."]]),
          who=["Dispatchers", "Service managers"]),
        S("x-oncall", "On-call", "The on-call rota",
          LEAD("For each board: who is on call now, who is duty manager now, and the shifts behind it. Any member reads it; editing a shift takes Admin on the board."),
          FIG("oncall", "On-call: each board's current on-call and duty manager, and the rota."),
          STEPS(["Pick the role (On-call or Duty manager), the member, the start and the end.", "Press Add shift. At 02:00 the name that matters is whoever is on shift, not whoever the board names."]),
          who=["Service managers", "Board admins"]),
        S("x-page", "On-call", "Paging",
          LEAD("A page is an urgent call on one ticket. It repeats every 5 minutes, 3 times, until the person acknowledges it on the ticket. If the on-call does not answer, the duty manager is paged the same way."),
          WIDGET("Try it: a page at 02:00", '<div class="w-row"><label>Minutes since the page started: <b class="minlab"></b><input class="min" type="range" min="0" max="35" value="12" style="width:260px"></label>'
                 '<label>The on-call acknowledges at minute (blank = never)<input class="ack" type="number" min="0" max="35" placeholder="never"></label>'
                 '<label style="flex-direction:row;align-items:center;gap:8px"><input class="dm" type="checkbox" checked> A duty manager is on the rota</label></div><div class="w-out out"></div>', "paging"),
          UL(["Each attempt is an email to the person and a card in every Teams channel that carries pages. Neither carries the ticket's summary.",
              "A page also ends when someone writes a note on the ticket, stops it, or the ticket closes.",
              "Start one with <b>Page the on-call</b> on the ticket, or let a workflow rule page for a P1."]),
          FIG("ticket-page", "A ticket with a page running: the page's attempts and the Acknowledge button."),
          who=["Whoever is on call"]),
        S("x-teams", "On-call", "Teams cards",
          LEAD("A workflow rule or a page can post a card to a Teams channel. The card carries the ticket number, board, priority, status, owner, the rule's words and a link to the desk: never the summary, never a note."),
          P("A channel is named in Setup › Integrations › Teams channels; its webhook address lives only on the host."),
          FIG("integrations", "Setup › Integrations: links out, and the Teams channels cards can go to."),
          who=["Service managers", "Administrators"]),
        S("x-quiz", "Reference", "Check yourself", QUIZ()),
    ])


GUIDES.append({
    "slug": "Dispatch_OnCall", "title": "Dispatch and On-call guide", "for": "dispatchers and the on-call",
    "blurb": "The unrouted queue, routing, today's visits, board roles, the rota, paging that repeats, and Teams cards.",
    "rail_sub": "Dispatch · On-call · Paging", "search": "Search: route, rota, page, duty manager…", "body": dispatch_body,
    "tours": {"dispatch": [["Unrouted queue", "Tickets nobody owns yet, oldest first, coloured by their clocks."], ["Its clocks", "How long it has waited against its targets."],
                           ["Route to", "The board that should own it."], ["Route", "Move it, with an owner if you give one."],
                           ["The day", "Today's visits by person; step days or open the week."], ["Board roles", "Who each board names as manager, dispatch, on-call and duty manager."]]},
    "quiz": [["A page goes unanswered by the on-call. Then…", ["It stops", "The duty manager is paged the same way", "It repeats forever"], 1, "After 3 unanswered pages the duty manager is paged."],
             ["How often does a page repeat?", ["Every minute", "Every 5 minutes, 3 times", "Every hour"], 1, "5 minutes, 3 attempts."],
             ["Does a Teams card show the ticket's summary?", ["Yes", "No"], 1, "Never the summary, never a note."],
             ["Who may edit the rota?", ["Any member", "A board admin"], 1, "A shift is a commitment; editing takes Admin on the board."]],
})


# --------------------------------------------------------------------------- CHANGE

def change_body():
    return "".join([
        HERO("Change management", "How a change is assessed, approved, scheduled and carried out on a change board, and what the desk will and will not let you do.",
             ["For technicians and change authorities", "ITIL 4 change enablement", "About 8 minutes"]),
        S("c-types", "Changes", "Three kinds of change",
          CHOOSER("Which kind is this change?", [
              ("std", "Routine, low risk, done the same way every time", "<b>Standard.</b> Pre-authorised: it goes straight through the statuses. Example: adding a printer to a ward's queue."),
              ("nrm", "Planned, with some risk", "<b>Normal.</b> It may not enter Approved, Scheduled, Implementing or Implemented until a change authority has approved it. The owner of a change never approves it."),
              ("emg", "Urgent, cannot wait for approval", "<b>Emergency.</b> It goes ahead, but may not be closed until an authorisation has been recorded afterwards.")]),
          TABLE(["Change authority", "Who"], [["Change authority", "The person named for the board"], ["CAB", "The change advisory board"], ["ECAB", "The emergency CAB"], ["Client", "The requesting department"]]),
          who=["Technicians", "Change authorities"]),
        S("c-flow", "Changes", "The change board's statuses",
          STEPPER("Try a normal change", "NEW", {
              "NEW": {"label": "New", "tone": "grey", "text": "Received; the Respond clock runs.", "next": [["ASSESS", "Assessing"]]},
              "ASSESS": {"label": "Assessing", "tone": "blue", "text": "Risk and impact assessed.", "next": [["AWAIT", "Awaiting Approval"]]},
              "AWAIT": {"label": "Awaiting Approval", "tone": "amber", "text": "Waiting for a change authority. A waiting status: it pauses the resolve clock.", "next": [["APPROVED", "Approved (a change authority records it)"], ["DECLINED", "Declined", None, True]]},
              "APPROVED": {"label": "Approved", "tone": "green", "text": "Authorised: now it may be scheduled.", "next": [["SCHED", "Scheduled"]]},
              "SCHED": {"label": "Scheduled", "tone": "blue", "text": "The window is set; tell the ward.", "next": [["IMPL", "Implementing"]]},
              "IMPL": {"label": "Implementing", "tone": "blue", "text": "Being carried out.", "next": [["DONE", "Implemented"], ["BACK", "Backed Out", None, True]]},
              "DONE": {"label": "Implemented", "tone": "green", "text": "Done. Then Closed.", "end": "Close it when the ward confirms."},
              "BACK": {"label": "Backed Out", "tone": "red", "text": "Undone: it did not work as planned.", "end": "Plan again with a new change."},
              "DECLINED": {"label": "Declined", "tone": "red", "text": "Not approved.", "end": "Declined changes are closed."}},
              "The approved statuses are locked until an approval is recorded; a standard change skips that gate."),
          FIG("change-ticket", "A change ticket: its type, its window, and the approvals recorded on it."),
          who=["Technicians"]),
        S("c-quiz", "Reference", "Check yourself", QUIZ()),
    ])


GUIDES.append({
    "slug": "Change", "title": "Change management guide", "for": "technicians and change authorities",
    "blurb": "Standard, normal and emergency changes, who authorises them, and the change board's statuses.",
    "rail_sub": "Change board · September 2026", "search": "Search: approval, CAB, emergency…", "body": change_body, "tours": {},
    "quiz": [["A normal change is not yet approved. Can it be Scheduled?", ["Yes", "No"], 1, "Authorised statuses wait for an approval."],
             ["Can the change's owner approve it?", ["Yes", "No"], 1, "The owner never authorises their own change."],
             ["An emergency change…", ["Waits for CAB first", "Goes ahead but cannot close until authorised afterwards"], 1, "Authorisation is recorded after the fact."]],
})

from g_common import *


def sched_body():
    return "".join([
        HERO("Scheduling", "Visits on tickets, time off and meetings, the week by person, your own calendar on your phone, and the In / out board.",
             ["For technicians and dispatchers", "Schedule module", "About 12 minutes"], "green"),
        S("sc-visit", "Visits", "A visit",
          LEAD("A visit is a member, a start and an end on a ticket, with a status and a place."),
          TABLE(["Part", "Means"], [["Status", "Firm, or Tentative (Setup › Schedule keeps the list)."], ["Where", "On-site, Remote or In-house."],
                                    ["Lead", "When several go, the one who owns the visit."], ["Done", "The visit happened."],
                                    ["Acknowledged", "Set by the member themselves: they have seen it."]]),
          WIDGET("Try it: book carol for a visit", '<p style="margin:0 0 6px;font-size:14px">carol already has a visit 09:00–10:00 and afternoon leave 13:00–17:00.</p>'
                 '<div class="w-row"><label>From<input class="s" type="time" value="09:30"></label><label>To<input class="e" type="time" value="10:30"></label>'
                 '<label style="flex-direction:row;align-items:center;gap:8px"><input class="allow" type="checkbox"> Allow a double booking</label></div><div class="w-out out"></div>', "conflict"),
          who=["Technicians"]),
        S("sc-week", "The week", "Schedule",
          FIG("schedule", "Schedule: each person's week, with visits, time off and meetings; the word under a name comes from In / out."),
          UL(["<b>Book a visit</b> from the ticket's Schedule card, by clicking the hour in the week, or from the form under the week.",
              "<b>Time off, a meeting or an activity</b> goes in the same week so nobody books you then.",
              "<b>Only me</b> shows your own row; the board filter narrows the people.", "Every visit change is a ticket event; every block is audited."]),
          H("Clicking and dragging the week"),
          UL(["<b>Click an empty hour</b> and choose what to put there: a visit on a ticket, time off or a block, or a brand-new ticket booked at that hour "
              "in one go.",
              "<b>Drag a visit</b> to another hour, another person or another day and it keeps its length. A clash is refused with its reason, exactly as the "
              "form refuses it \u2014 dragging is a shortcut to the same rules, never a way round them.",
              "The <b>Calendar</b> and the <b>Dispatch</b> day drag the same way.",
              "<b>Time off is never overridden</b>, with or without <i>Allow a double booking</i>.",
              "The week does not need reloading: a visit a colleague books while you are looking at it appears on its own."]),
          NOTE("info", "<b>When you book a visit for yourself on a ticket nobody owns, the ticket becomes yours.</b> The desk takes booking yourself to work on "
                       "something as taking it on."),
          who=["Technicians", "Dispatchers"]),
        S("sc-cal", "The week", "Your calendar, and on your phone",
          FIG("calendar-month", "Calendar by month: visits, time off, meetings and on-call shifts."),
          H("What an appointment says in Outlook"),
          TABLE(["Part of the appointment", "What it carries"],
                [["Subject", "The ticket number, the company and the summary \u2014 <i>PMC-000123 \u2013 Ward 3 \u2013 Teams phone not ringing</i>."],
                 ["Body", "The summary, the status, where the visit is, and a link to the ticket on the desk."],
                 ["Never", "A note from the ticket. Notes stay on the desk."]]),
          NOTE("good", "<b>A visit on a restricted board, or one whose summary the patient-details check flags, goes to Outlook by its ticket number and board "
                       "alone.</b> A calendar syncs to phones and watches, so nothing about a patient is allowed to travel with it."),
          STEPS(["Open <b>My profile</b> from your name.", "Press <b>Make a feed address</b> and copy it.", "Add it to your phone's calendar as a subscribed calendar. It names tickets and places, never what a ticket says. A new address stops the old one."]),
          who=["Everyone on the desk"]),
        S("sc-inout", "The week", "In / out",
          FIG("inout", "In / out: where everyone is right now, said by themselves."),
          WIDGET("Try it: what your line will say", '<div class="w-row"><label>State<select class="state"><option value="IN">In</option><option value="OUT" selected>Out</option><option value="ON_SITE">On site</option><option value="REMOTE">Working remotely</option><option value="LEAVE">On leave</option></select></label>'
                 '<label>Note<input class="note" type="text" value="supplier visit"></label><label>Back at<input class="back" type="datetime-local"></label></div><div class="w-out out"></div>', "inout"),
          who=["Everyone on the desk"]),
        S("sc-setup", "Setup", "Schedule setup",
          FIG("schedule-setup", "Setup › Schedule: visit statuses and places."), who=["Administrators"]),
        S("sc-quiz", "Reference", "Check yourself", QUIZ()),
    ])


GUIDES.append({"slug": "Scheduling", "title": "Scheduling guide", "for": "technicians and dispatchers", "kind": "req",
    "blurb": "Visits, conflicts and time off, the week by person, your calendar feed, and In / out.",
    "rail_sub": "Schedule · Calendar · In / out", "search": "Search: visit, leave, feed…", "body": sched_body, "tours": {},
    "quiz": [["Can you book someone during their leave if you tick Allow a double booking?", ["Yes", "No"], 1, "Time off is never overridden."],
             ["Who sets a visit's Acknowledged?", ["The dispatcher", "The member themselves"], 1, "It says the member has seen it."],
             ["Does the calendar feed show what a ticket says?", ["Yes", "No, only the ticket and place"], 1, "Feeds name tickets and places only."]]})


def time_body():
    return "".join([
        HERO("Time and timesheets", "Recording time on tickets as the reference PSA does, submitting your week, approving others', and utilisation.",
             ["For everyone who records time, and approvers", "Timesheets module", "About 10 minutes"], "green"),
        S("t-stopwatch", "Recording time", "The stopwatch",
          LEAD("If you would rather not watch the clock yourself, the ticket will. The Time card has Start, Pause, Resume and Stop."),
          STEPS(["Press <b>Start</b> on the ticket you are about to work on. The card shows a clock counting up, and keeps counting if you close the tab.",
                 "<b>Pause</b> when you are pulled away; <b>Resume</b> when you are back. Only the time it was actually running counts.",
                 "Press <b>Stop</b>. The Add time form opens with the Start and End already filled in from what the stopwatch measured.",
                 "Check it, add the work role, work type and bill option, and save it as any other entry. <b>The stopwatch is evidence; the entry is the claim</b> "
                 "\u2014 you can correct every field before saving."]),
          UL(["The measured time is rounded <b>up</b> to the quarter hour, so a run of sixteen minutes costs the quarter hour it ran into.",
              "A timer belongs to the person who started it. Nobody else can pause, stop or see the inside of yours.",
              "<b>One timer per person per ticket</b> \u2014 two would double-count the same hour. Nothing stops you running timers on three different tickets "
              "at once, which is what carrying three jobs looks like.",
              "<b>Discard</b> throws the run away and records nothing."]),
          NOTE("warn", "<b>The stopwatch is not the SLA clock.</b> The clocks across the top of the ticket measure how long the <i>requester</i> has been waiting, "
                       "and they run whether or not anybody has a stopwatch going. Starting or stopping a stopwatch never touches them."),
          who=["Everyone who records time"]),
        S("t-entry", "Recording time", "A time entry",
          LEAD("Time goes on the ticket it was spent on, from the ticket's Time card: a start and an end, or the actual hours, less any deduction."),
          WIDGET("Try it: what the desk records", '<div class="w-row"><label>Start<input class="start" type="time" value="09:10"></label><label>End<input class="end" type="time" value="11:25"></label>'
                 '<label>Deduct (hours)<input class="deduct" type="number" step="0.25" value="0.25"></label></div><div class="w-out out"></div>', "timecalc"),
          TABLE(["Field", "Means"], [["Work role", "What you were: Technician, Engineer, Service manager, On-call."], ["Work type", "Regular, Remote, On-site, After hours, Internal."],
                                     ["Bill option", "Billable, Do not bill, No charge, or No default (the agreement decides)."],
                                     ["Charge method", "How the uplift counts it: included in the monthly fee, capacity uplift, separate charge, pass-through or non-chargeable. Never assumed."],
                                     ["Band", "The smallest of 0.5, 2, 4, 8 or 20 hours the time fits in. Over 20 hours is refused: one entry per day."]]),
          who=["Everyone who records time"]),
        S("t-week", "Your week", "Timesheets",
          TOUR("time-approve"),
          STEPPER("Try the week's lifecycle", "OPEN", {
              "OPEN": {"label": "Open", "tone": "blue", "text": "You are writing the week. Every entry lands in the week it was worked.", "next": [["SUBMITTED", "Submit for approval"]]},
              "SUBMITTED": {"label": "Submitted", "tone": "amber", "text": "Complete, waiting for a time administrator who is not you. It takes no new entries.", "next": [["APPROVED", "Approve"], ["REJECTED", "Reject", "the reason", True, "A rejection says why."]]},
              "APPROVED": {"label": "Approved", "tone": "green", "text": "Final. It takes no new entries.", "next": [["OPEN", "Reopen", "a note", True, "A week is reopened only with a note."]]},
              "REJECTED": {"label": "Rejected", "tone": "red", "text": "Open again for you to fix, with the approver's reason.", "next": [["SUBMITTED", "Submit again"]]}}),
          WIDGET("Try it: utilisation", '<div class="w-row"><label>Hours recorded this week<input class="hours" type="number" value="31.5"></label><label>Expected a week (Setup, per member)<input class="cap" type="number" value="40"></label></div><div class="w-out out"></div>', "util"),
          who=["Everyone", "Time administrators decide"]),
        S("t-setup", "Setup", "Work roles and work types",
          FIG("time-setup", "Setup › Time: the work roles and types an entry is written against; each type carries its default bill option."), who=["Administrators"]),
        S("t-quiz", "Reference", "Check yourself", QUIZ()),
    ])


GUIDES.append({"slug": "Time", "title": "Time and timesheets guide", "for": "everyone who records time", "kind": "req",
    "blurb": "Time entries with start, end and deduction, bands and charge methods, the weekly timesheet, approval and utilisation.",
    "rail_sub": "Timesheets module", "search": "Search: band, submit, approve…", "body": time_body,
    "tours": {"time-approve": [["Week of", "Pick the week; arrows step a week."], ["Member", "Yours, or someone you approve for."], ["The week's hours", "Against the hours expected."],
                               ["Status", "Open, Submitted, Approved or Rejected."], ["Submit for approval", "When the week is complete."], ["Waiting for a decision", "Weeks others submitted, for an approver."]]},
    "quiz": [["09:00 to 09:07 with no deduction records…", ["Nothing", "0.25 h", "0.07 h"], 0, "0.12 h rounds half up to 0 quarters, and a time that comes to nothing is refused."],
             ["Can you approve your own week?", ["Yes", "No"], 1, "A time administrator who is not you decides."],
             ["3.5 hours falls in which band?", ["2", "4", "8"], 1, "The smallest band it fits in: 4."]]})


def proj_body():
    return "".join([
        HERO("Projects", "Planned work with a manager, dates, a budget in hours, phases that may wait on each other, and tickets as the work.",
             ["For project managers and technicians", "Projects module", "About 8 minutes"]),
        S("p-page", "Projects", "A project",
          TOUR("project"),
          WIDGET("Try it: budget against actual", '<div class="w-row"><label>Budget (hours)<input class="bud" type="number" value="40"></label><label>Hours on its tickets<input class="act" type="number" value="6"></label></div><div class="w-out out"></div>', "budget"),
          UL(["A ticket belongs to one project and optionally one phase; its time entries are the project's actual hours.", "Phases may nest, and a phase can wait on others.",
              "Nothing is deleted: a project is cancelled or done, a phase is done.", "A project on a board is shown only to that board's members."]),
          STEPS(["<b>Projects › New</b>: name, manager, dates, budget hours, board.", "<b>Add phases</b>, with the phases each waits on.", "<b>Link tickets</b> to the project and a phase.", "<b>Close phases</b> as they finish; link BizBox records on the Finance card."]),
          FIG("projects", "Projects: each with its manager, dates and budget against actual."),
          who=["Projects: Write to change", "Read to look"]),
        S("p-fix", "Projects", "Correcting the plan",
          LEAD("A plan is written before the work, so it is written wrong sometimes. Everything on a project can be edited, and anything "
               "carrying no work can be taken off."),
          TABLE(["To", "Do this"],
                [["Rename a phase, or change its dates or budget", "<b>Edit</b> on its row. The form opens under the table with that phase\u2019s values in it."],
                 ["Move a phase inside another, or back to the top", "The same Edit form: <b>Inside</b>. A phase cannot be put inside itself or inside one of its own."],
                 ["Change the order", "The <b>\u2191</b> and <b>\u2193</b> on its row, among its own brothers and sisters."],
                 ["Stop a phase waiting on another", "The <b>\u00d7</b> on the <i>waits on</i> chip."],
                 ["Take a phase off the plan", "<b>Remove</b> on its row \u2014 only if it carries nothing."],
                 ["Take a ticket off the project", "<b>Unlink</b> on its row in the Tickets card."],
                 ["Rename the project, or write its description", "The fields in <b>The project itself</b>."],
                 ["Get rid of a project entirely", "<b>Remove this project</b>, if it never got going. Otherwise set its status to <b>Cancelled</b>."]]),
          NOTE("warn", "<b>A predecessor set the wrong way round is worth fixing straight away.</b> A phase cannot be marked Done while something it "
                       "waits on is still open, so if B waits on C by mistake, neither can be finished until you take the chip off."),
          H("What will not be removed, and why"),
          UL(["<b>A phase with child phases</b> \u2014 move or remove those first, or the whole branch under it would go with it.",
              "<b>A phase with tickets on it</b> \u2014 removing it would quietly take their phase off them. Move them to another phase, or to no phase, first.",
              "<b>A phase with hours booked against it</b> \u2014 hours are the record of work that was done, and are never deleted. Mark the phase <b>Done</b>.",
              "<b>A project with any phase, ticket or BizBox record</b> \u2014 it is <b>cancelled</b>, not deleted, so its tickets keep their hours and their "
              "history. The page says which of the three is holding it."]),
          NOTE("info", "The row tells you before you click: a phase that cannot be removed shows <b>kept: 2 ticket(s) are on it</b> where the Remove button "
                       "would be. And every edit and every removal is on the audit trail \u2014 taking something off is a line in the record, not a silence."),
          who=["Project managers", "Technicians"]),
        S("p-quiz", "Reference", "Check yourself", QUIZ()),
    ])


GUIDES.append({"slug": "Projects", "title": "Projects guide", "for": "project managers", "blurb": "Projects, phases and predecessors, budget against actual from time entries, and linked tickets.",
    "rail_sub": "Projects module", "search": "Search: phase, budget…", "body": proj_body,
    "tours": {"project": [["Budget against actual", "Hours from the project's tickets against its budget."], ["Phases", "The work in stages; a phase may nest."],
                          ["Waits on", "A phase that depends on another."], ["Done", "Close a phase; Reopen undoes it."], ["Tickets", "The work, with its phase."],
                          ["Finance (BizBox)", "The BizBox records the project concerns."]]},
    "quiz": [["Where do a project's actual hours come from?", ["Typed on the project", "Time entries on its tickets"], 1, "Nobody types them twice."],
             ["Can a project be deleted?", ["Yes", "No, it is cancelled or done"], 1, "History is kept."]]})


def kb_body():
    return "".join([
        HERO("Knowledge", "Fixes written once and used again: articles for the desk and for requesters, categories, pictures that wait for a patient-details check, and use counts.",
             ["For technicians and managers", "Knowledge module", "About 8 minutes"], "green"),
        S("k-list", "Knowledge", "Finding an article",
          FIG("kb", "Knowledge, filtered by category, with each article's use count."),
          UL(["Search words in the title and body; filter by status and category.", "A ticket's Knowledge card offers articles for its Subtype › Item and board first.", "Link the one that helped: its use count is how the desk learns which articles earn their keep."]),
          who=["Knowledge: Read"]),
        S("k-write", "Knowledge", "Writing one",
          FIG("kb-new", "Write an article: title, who it is for, board, Subtype › Item, category, and the steps."),
          WIDGET("Try it: the article's text", '<textarea># Label printer prints blank labels\nThe ribbon is in upside down.\n- Open the cover\n- Turn the ribbon so the **ink side** faces the labels\n- Print a test label with `Ctrl+P`\n![the ribbon](file:1)</textarea><div class="mdprev" style="margin-top:8px"></div>', "md"),
          STEPPER("Try an article's life", "DRAFT", {
              "DRAFT": {"label": "Draft", "tone": "grey", "text": "The desk sees it; requesters never do.", "next": [["PUBLISHED", "Publish"], ["RETIRED", "Retire (Admin)", None, True]]},
              "PUBLISHED": {"label": "Published", "tone": "green", "text": "Live. A requester article shows on Help.", "next": [["DRAFT", "Back to draft", None, True], ["RETIRED", "Retire (Admin)", None, True]]},
              "RETIRED": {"label": "Retired", "tone": "red", "text": "Kept for history, hidden from lists unless you filter for it.", "end": "Nothing is deleted."}}),
          who=["Knowledge: Write"]),
        S("k-vis", "Knowledge", "Who sees what",
          WIDGET("Try it: who sees this article and its picture", '<div class="w-row"><label>For<select class="aud"><option value="INTERNAL">The desk only</option><option value="REQUESTER" selected>The desk and requesters</option></select></label>'
                 '<label>Status<select class="stat"><option>DRAFT</option><option selected>PUBLISHED</option><option>RETIRED</option></select></label>'
                 '<label>Board<select class="brd"><option value="" selected>Every board</option><option value="b">One board</option></select></label>'
                 '<label>Its picture<select class="file"><option>PENDING</option><option selected>CLEARED</option><option>WITHHELD</option></select></label></div><div class="out"></div>', "kbvis"),
          FIG("portal-article", "A published requester article on the Help page of PMC Requests."),
          who=["Knowledge: Write"]),
        S("k-quiz", "Reference", "Check yourself", QUIZ()),
    ])


GUIDES.append({"slug": "Knowledge", "title": "Knowledge guide", "for": "technicians", "kind": "req", "blurb": "Finding, writing and publishing articles, categories, pictures and who sees what.",
    "rail_sub": "Knowledge module", "search": "Search: article, publish, picture…", "body": kb_body, "tours": {},
    "quiz": [["A requester article is published but belongs to one board. On Help?", ["Shown", "Not shown"], 1, "Help shows only articles on every board."],
             ["A picture is Pending review. The requester…", ["Sees it", "Does not, until it is cleared"], 1, "Requesters see Cleared files only."],
             ["Who can retire an article?", ["Write", "Admin"], 1, "Retiring takes Knowledge Admin."]]})


def cmdb_body():
    return "".join([
        HERO("Companies and configurations", "Who the desk serves and the machines it looks after: companies and contacts from Active Directory, configurations with their life, warranty and questions.",
             ["For technicians", "About 10 minutes"]),
        S("m-co", "Companies", "Companies and contacts",
          FIG("companies", "Companies: status and type chips, coverage, contacts and open tickets."),
          FIG("contacts", "Contacts: the people who ask, from Active Directory."),
          UL(["A company's <b>status and type</b> are words kept in Setup › Companies; coverage is still the executed instrument.", "Open a company or contact and press New ticket to start one filled in."]),
          who=["Technicians"]),
        S("m-cf", "Configurations", "Configurations",
          FIG("configurations", "Configurations: tiles by type, warranty and status; filters; add one by hand."),
          FIG("configuration", "A configuration: its details and type questions, its life, and every ticket about it."),
          WIDGET("Try it: warranty state", '<div class="w-row"><label>Warranty ends<input class="ends" type="date" value="2026-11-15"></label></div><div class="w-out out"></div>', "warranty"),
          UL(["PCs arrive from Active Directory; printers and devices are added by hand.", "A <b>type</b> counts as one of the seven kinds reports know, and asks its own questions (asset tag, last calibration).",
              "Export the maintenance record as CSV for an inspection, per machine or per list.", "Launch remote control from a configuration where it is set up."]),
          who=["Technicians"]),
        S("m-quiz", "Reference", "Check yourself", QUIZ()),
    ])


GUIDES.append({"slug": "Companies_Configurations", "title": "Companies and Configurations guide", "for": "technicians",
    "blurb": "Companies and contacts from Active Directory, configurations, types and questions, warranty and maintenance records.",
    "rail_sub": "Companies · CMDB", "search": "Search: warranty, contact, type…", "body": cmdb_body, "tours": {},
    "quiz": [["A warranty ends in 60 days. The state is…", ["Covered", "Expiring", "Expired"], 1, "Within 90 days is Expiring."],
             ["Where do PCs come from?", ["Typed by hand", "Active Directory"], 1, "Printers and devices are added by hand."]]})

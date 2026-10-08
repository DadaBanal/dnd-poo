# psa-spine — the commercial half of a PSA

The half no PSA on the market ships: a fixed monthly fee against nine numbered
baseline scope items, with everything else a named variation under Annex B,
notices that condition every commercial right, and client dependencies that are
only claimable once written notice exists.

**The ticket desk is not here and is not being replaced.** That was the
conclusion of WS36 — see [`docs/WS36-psa-recommendation-20260909.md`](../../docs/WS36-psa-recommendation-20260909.md).
The incumbent is USD 88.50 per organisation per month with unlimited users, so
replacing it saves nothing and costs 9×–58× at the seat counts intended. What is
expensive is that nothing records which work is baseline, which is a variation,
and which client delay was ever put in writing. That is what this builds.

## What it produces

Three artefacts, from data, needing no licence and no approval:

| Artefact | What it is |
|---|---|
| **Annex B variation register** | Every workstream the register itself classifies as outside the nine baseline items, in the agreement's own Annex B shape. Discharges an action open since the register was written. |
| **Client dependency notices** | One dated written notice per workstream blocked on the client. The entitlement to relief is conditioned on notice, and today not one is recorded. |
| **Instrument exception report** | Every fee line and covered entity resting on an instrument nobody has signed. |

Plus a data-quality summary, because the standing rule here is that flags are
**counted, never filtered out**.

## Run it

```bash
cd platform/psa-spine
python3 -m psaspine init spine.db
python3 -m psaspine import spine.db /path/to/PMC_Workstream_Register_YYYYMMDD.csv --run-id r1
python3 -m psaspine import-tickets spine.db /path/to/desk-export.csv --run-id desk-1
python3 -m psaspine report spine.db --out ./out --run-id desk-1 --capacity-hours 160
python3 tests/test_spine.py          # 604 tests, on SQLite; PSA_TEST_DB=… runs them on SQL Server
python3 tests/smoke.py               # end to end: imports, reports, intake, backup, desk
```

Python 3.11+, standard library only. No packages and no network; the Phase B
desk adds an optional server, and it too is standard library (`wsgiref`) — see
below. The one exception is deliberate and opt-in: a desk on **SQL Server**
(D7, below) needs `pyodbc` and Microsoft's ODBC Driver for SQL Server, imported
only when the database argument is a connection string instead of a path.

Every command that takes a `database` takes either shape:

```bash
python3 -m psaspine serve spine.db                                   # SQLite, a file
python3 -m psaspine serve "Driver={ODBC Driver 17 for SQL Server};Server=DND-SQL01\PMC_SS;Database=PMC_PSA;Trusted_Connection=yes;Encrypt=yes;TrustServerCertificate=yes" --port 8085
python3 -m psaspine schema-preview "<the same string>"    # the port script's plan, nothing changed
```

Driver 17 is what `DND-SQL01` has (MEASURED, 26 Sep 2026); 18 works the same
where it is installed. On that host the desk binds 8085: 8080 is the live queue
screens' and the estate record says never to take it.

A connection string with `Trusted_Connection=yes` holds no secret — the task
account's Windows identity is the credential — so it may sit in a scheduled
task's arguments. One with a password may not sit anywhere in this repository.

`import-tickets` reads an **export file**. There is no API client in this
repository and nowhere to put a key: the TeamsWork keys were exposed in a
screenshot, neither is ever written down, and both should be rotated. A test
asserts the module contains no credential-shaped code.

## The fulfiller desk (Phase B)

The engine computes every SLA number but a person could only reach it from
Python. Phase B is the desk that puts it in front of Dada IT — the phasing gate
is that *Dada IT runs its own work on it before anyone at PMC is asked to*.

```bash
python3 -m psaspine serve spine.db --host 127.0.0.1 --port 8085
```

A standard-library WSGI app (`psaspine/web/`), run for the pilot by
`wsgiref.simple_server` with one thread per request, so a technician opening a
big board never makes everyone else's click wait. Zero packages, so the same
WSGI callable drops behind a production server in Phase C with no code change;
a test wraps it in `wsgiref.validate.validator()` to prove PEP 3333 conformance. It is **LAN only,
Dada IT only** and refuses to bind to a public interface. Seven surfaces: the
board, one ticket, dispatch/triage, the closed loop, the on-call rota, an admin
surface, and the uplift evidence screen (§7 — a first-class screen, not an
export).

**Two ways in.** Entra SSO is the normal path and the only one for everyone but
the on-call rota; its RS256 token check is written out in pure Python (no crypto
dependency) and is **NOT VERIFIED** against a real tenant — proven against a
synthetic key in the tests, run against Entra by somebody who has a route to it,
the way the SQL Server port is. Break-glass local accounts are the WAN-down
fallback (§11 test 10), sealed and scrypt-hashed:

```bash
python3 -m psaspine create-local-account spine.db --username oncall
```

The password is read from a no-echo prompt, never an argument or an environment
variable; the account is seeded into no repository; every login is audited. The
web offers no way to mint one — creation is CLI-only, and a test asserts there is
no route. The credential table lives in `schema/local/`, outside the `schema/*.sql`
glob, so it is applied to the local pilot database and **never** ported to the
commercial spine on `DND-SQL01`.

**The restricted-board guarantee.** A restricted board's tickets are filtered by
`board_member` at every query, for everyone — the sysadmin flag unlocks
cross-board configuration, never a restricted board's contents. This is §11 test
5, the acceptance test the record wrote and never ran: a non-member is *provably*
excluded, and a test asserts a non-member gets a 404, not a leak.

## The desk: Dada PSA's layout

What a technician uses every day, built to the shape a technician from the reference PSA knows, and
checked against Zammad and HaloPSA:

- **Service Board** (`/`): five counters that also filter (open, SLA breached,
  due within the hour, unassigned, mine), then board, status, owner, priority,
  source and search filters. Every column sorts. Each row shows the last note
  under its summary and one chip per SLA clock: **R**espond, resolution
  **P**lan, re**S**olve. Tick rows to change status, assign or move board in
  bulk. Bulk changes go through the same engine seams as a single ticket.
- **Ticket** (`/ticket/<id>`): the priority and why (computed, never typed).
  `ticket.priority_source` says which rule set it: `MATRIX` (impact ×
  urgency), `CATALOGUE_FLOOR` or `CLINICAL_FLOOR` (a catalogue item's or a
  clinical answer's minimum lifted it), `CLINICAL_IMPACT`. `OVERRIDE` is in
  the CHECK for a manual override that **is not built**: nothing on the desk
  sets it, and the engine leaves an `OVERRIDE` priority alone if one ever
  arrives by import. Reserved, documented, not a feature.
  One box per SLA clock. Notes flagged **Discussion / Internal / Resolution**,
  as Dada PSA flags them. The requester's portal shows Discussion and
  Resolution only. A note can carry a time entry in Dada PSA's shape
  (below), with a charge method the technician must choose, and can move the
  status in the same save. The
  right-hand panel edits board, status, owner, company, contact and the two
  questions. **Every card on the ticket is a pod**, in one of two columns: drag
  a card to either column (onto another card, or onto the column's empty
  space), use its arrows (up, down, across), fold it, and this browser
  remembers; *Reset layout* restores the shipped layout. The activity stream
  and the note composer ship on the left, the rest on the right.
- **New ticket** (`/ticket/new`): for phone calls and walk-ups. It records its
  source.
- **Setup** (`/admin/board/<id>`): Board, Statuses, SLA, and Members & roles
  tabs, as Dada PSA's Service Board setup table. The Board tab also holds
  Dada PSA's *send to resource* (**Email the owner when a ticket is
  assigned to them**: one unsent email per ticket and owner, none when you
  assign it to yourself, no summary in the subject) and the board's default
  work role and type for time entries. The starter setup
  (`psaspine setup-board`) adds what is missing and never overwrites. Every
  change is audited.

### How it looks and feels (25 Sep 2026)

One design system, self-contained by fence: no CDN, no web font, no external
request, and a test that reads every page to prove it. Modelled on the dense,
calm desks of 2025-26 (Linear's surface ladder and hairlines, a ⌘K palette,
keyboard-first rows) and checked against current UI-trend and CSS references
(sources in the commit).

- **Light and dark** follow the OS; the toggle in the header (or `t`)
  remembers a choice in this browser only. One accent colour carries "this is
  the action"; green, amber and red carry an SLA clock's state and nothing
  else.
- **Motion that stays out of the way:** 140–220 ms ease-outs on hover and
  focus, a cross-document view transition between pages with the header held
  still (Chromium and Safari 18.2+; other engines simply navigate), enter
  transitions via `@starting-style`, and all of it off under
  `prefers-reduced-motion`.
- **The board:** a sticky column heading, 40 px rows with tabular numerals and
  a monospace ticket number, the bulk bar only when something is ticked, a
  selected row tinted, 100 rows a page with an explicit total.
- **Keyboard:** `Ctrl/⌘ K` opens the palette (pages, *New ticket*, a ticket
  number such as `pmc 123`, and the rows of the board you are on); `/`
  searches; `n` new ticket; `g` then `b` `d` `c` `s` goes to board, dispatch,
  companies, setup; `j` `k` move down the board, `x` ticks, `Enter` opens;
  `?` shows the list; `Esc` closes.
- **No lag, measured:** over a 3,000-ticket database the board went from
  1,683 ms to 50 ms and `view=all` from 1,690 ms and 2.6 MB to 37 ms and
  103 KB (029 indexes, one query for every row's clocks, filters and paging
  in SQL). A button marks itself busy on submit and refuses a second click;
  hovering a ticket link prefetches it.
- **Icons, not an icon font:** three dozen 24-grid stroke icons drawn in
  `templates.ICONS`, emitted once per page as an SVG sprite and used by id on
  the nav, the counters, every card heading, the action buttons and empty
  states; a favicon as an inline SVG. A test proves every icon a page asks
  for exists.
- **Platform features, used where they degrade cleanly:** the palette is a
  `<dialog>` with `showModal()`; the shortcut list is a `popover`; the header
  gains a shadow through a scroll-driven animation; textareas grow with
  `field-sizing: content`; headings use `text-wrap: balance`; cards are
  container-query roots; action results are toasts that dismiss themselves
  (an error stays until closed); a 2 px progress bar runs while the next
  page loads; rows have a *Comfortable / Compact* density, remembered here.
- **Every page works with the script off.** It only adds.

- **Companies and contacts** (`/companies`, `/company/<id>`, `/contacts`,
  `/contact/<id>`): Dada PSA's Company › Contacts. Contacts come from Active
  Directory, not typing: `scripts/Export-PmcAdContacts.ps1` reads AD as an
  ordinary user and changes nothing in it; `psaspine import-contacts` loads the CSV,
  keyed by the AD objectGUID so a renamed person stays one contact. A disabled
  account becomes an inactive contact, never a deleted one. A new ticket
  whose requester's address is exactly one active contact is filed under that
  person and their company automatically. These pages are for fulfillers only,
  and never list a restricted board's tickets: those are read on their own
  board, where the read is audited.

- **Configurations** (`/configurations`, `/configuration/<id>`, and a card on
  every ticket, company and contact): the machines a ticket is about.
  `scripts/Export-PmcAdComputers.ps1` reads AD's computer objects (no IP
  address, no LAPS or BitLocker attribute, nothing written to AD) and
  `psaspine import-computers` loads them by objectGUID. A printer, a network
  device or anything AD does not know is **typed in by hand** on the
  Configurations page (source MANUAL). The desk owns a configuration's type,
  status, contact, site, manufacturer, model, serial and session id; a
  re-import refreshes only what AD knows, and an imported machine's name,
  DNS name, OS and description are AD's (changed there, re-imported). The
  list (28 Sep) counts by type (each count filters), filters by status and
  company, searches name, DNS name, serial and description, sorts every
  column and shows each machine's open tickets. The page for one machine
  shows every field, its contact, its open and recently closed tickets, its
  history (the desk's changes and every ticket it was attached to or removed
  from) and a **Raise a ticket for this machine** button that opens the new
  ticket form prefilled and attaches the machine on creation.
- **Integrations** (`/admin/integrations`, system administrator): links out
  from a configuration or contact, as URL templates. ScreenConnect's is
  `https://INSTANCE.screenconnect.com/Host#Access/All%20Machines//{remote_session_id}/Join`
  (the shape its NinjaOne and Syncro integrations document). A template must
  be HTTPS to a fixed host and name only known fields. Values are URL-encoded,
  and a link with a missing field is drawn disabled with the reason. The
  ScreenConnect session id is a GUID, set on the configuration page. How to
  export them in bulk from ScreenConnect Cloud is NOT VERIFIED.

### Board kinds and board Types (ITIL, 23 Sep 2026)

Boards are split by who does the work and how it flows, never by incident
versus request. The evidence: ITIL 4's service desk takes both incidents and
requests through one front door. The reference PSA's own "ITIL Example" Types are
**Event, Incident, Problem, Request**, as Types on one board. That is Dada's
workbook column A. (Sources are in `schema/022_record_type.sql`.)

- **Board kind** (`board.kind`): **Service**, **Change** or **Project**, chosen on
  *New board*. It sets the starter statuses. Only a service board gets SLA
  targets; the reference PSA: "SLA timers do not run on project tickets".
- **The board's Types** (Setup › *Types* tab): a service board takes Incident,
  Request, Problem and Event. A ticket reads **Type › Subtype › Item**
  (*Incident › Printer › Fix*). Ticking Change on a service board is Dada's
  other phrasing, and is configuration only. A move to a board that does not
  take the ticket's Type is refused.
- **Requests keep their own SLA.** `sla_target_type` holds targets for one
  Type on a board, so the old Request board's numbers are Request targets on
  the first board (id `IT_HELP`; a fresh install names it **PMO Helpdesk**,
  the name Dada chose in Setup on 28 Sep 2026, and the id stays because ticks,
  settings and tickets refer to it).
- **`init` never overwrites a seeded board.** The two seed rows (`IT_HELP`,
  `UNROUTED`) are insert-if-absent. A replace-seed on SQL Server was an UPDATE
  that put every unlisted column back to its DEFAULT, so each `init` on the
  host was silently undoing Setup on those boards (SQL01, part 14: Unrouted
  lost its calendar). A board that exists is the operator's, whatever the CSV
  says, and a test proves a second `init` leaves name, calendar and kind alone.
- **Change enablement.** Standard changes are pre-authorised. A normal change
  cannot enter Approved, Scheduled, Implementing or Implemented until a
  change authority approves it. An emergency change goes ahead but cannot
  close until someone records an authorisation afterwards. The owner never
  authorises their own change. Each change has a type, risk, window and
  backout plan, and every decision is append-only.
- **Links:** incident *caused by* problem, anything *fixed by* change, or
  *related*. A link closes nothing and moves no clock. That avoids the
  reference PSA's child-ticket SLA trap. It is not handover: one fault stays one
  ticket that moves.
- The commercial path (VARIATION) is derived, never passed in. This closes a
  bypass where a variation item opened as INCIDENT could have time booked
  against it.

### The catalogue setup tables (Setup › Catalogue, 28 Sep 2026)

The reference PSA's Service Board setup table has a Types tab, a Subtypes tab
and an Items tab, each a list a person adds to, renames and inactivates. Dada
PSA has the same three actions on its own tree, at `/admin/catalogue`, for a
sysadmin, with no script:

- **Types** stay the board's ITIL kind (Incident, Request, Problem, Event,
  Change, Project). The tab lists the six, their category (reactive or
  proactive) and which boards take each, linking to that board's own *Types*
  tab where the ticks and the default are set. The six are a closed set because
  the change approval gate and the SLA-by-type targets key on them.
- **Areas** (`service_family`) group subtypes in the picker: add, rename, retire.
- **Subtypes** (`service_component`): add under an area, rename, move to
  another area, retire.
- **Items** (`service_action`): add with a kind (request or fault) and an
  implied impact, rename, change either, retire.
- **Subtype › Item pairs** (`catalogue_item`): the existing list, now with an
  *Associate* form: a subtype, an item, the board it lands on, its contract
  basis (a baseline pair must name its scope item), a priority floor and the
  clinical flag. Only a pair is offered on a ticket.

Nothing is deleted. Retiring an area, subtype, item or pair takes it out of
every picker and leaves every ticket that carries it as it was: the ticket
screen still shows the pair, marked *(retired)*, and a save does not clear it.
Every change is one `CATALOGUE_CONFIG` audit row saying what changed; a save
that changes nothing writes none. Schema `036` adds the retire flag to areas and
items (a subtype already had `is_draft`). Names are unique within their scope,
whatever the case; ids are made from the name and never collide.

### Tasks and templates

- **Tasks:** a ticket has a checklist, as Dada PSA's Tasks tab does.
  Ticking a task records who and when, and unticking it is recorded too.
- **Templates:** each board has templates (Setup › *Templates*). A template
  holds a summary, a Type, a Subtype › Item, a description and tasks.
- **Using a template:** start a ticket from one (*New ticket › Use
  template*), apply one to an open ticket, or have a workflow rule apply one
  (*Apply a ticket template*). Applying the same template twice adds nothing
  twice.

### Reports, merge, visits, survey (032)

- **Reports** (`/reports`): the Service Manager's month, computed now from
  the tickets and their clocks: opened and closed by month, resolve clock
  met %, median working time to respond and to resolve, backlog, and the mix
  by board, Type, source and priority; satisfaction once the survey has
  answers. Charts are inline SVG on a validated two-hue palette (light and
  dark), each mark with its value on hover, and the table sits under them.
  `/reports.csv` for the spreadsheet.
- **Merge** (on the ticket's *Children* pod, or *Merge into* on the board's
  bulk bar): the duplicate closes on its own board with `merged_into` set;
  its notes are copied onto the ticket that stays, its files, links and
  children move. A Discussion note arrives as Internal unless both tickets
  have the same requester (§6.1). The merged ticket's requester sees "combined
  with a related one" on the portal and is not asked to rate it.
- **Visits** (the *Schedule* pod): who, from, to, a note; one person is not
  booked twice at once unless allowed. Dispatch shows the day by person, and
  `/schedule` the week (see *Scheduling* below).
- **Survey:** when a ticket closes (and the board sends requester emails) the
  requester is told and, on the portal, asked once: one to five and a
  sentence, scanned for patient details like every other requester text.
- **Patient details are helped, not policed** (Dada, 28 Sep 2026): every
  requester box has a small "?" that pops out what helps most (ward, room,
  machine, since when) with a worked sample, and the placeholders show an
  example instead of a rule. Nothing is refused; the scan still flags what it
  finds for the desk to tidy, and the thank-you carries one friendly tip.

### Calendars and holidays (Setup › Calendars, 037, 28 Sep 2026)

The reference PSA's Calendar and Holiday List setup tables, at `/admin/calendars`
for a sysadmin. A **calendar** is a name, a start and an end for each of the
seven days (blank is closed; `24:00` is midnight at the end of the day, so 24x7
is seven ordinary rows) and a holiday list. A **holiday list** is dated rows,
each a whole day or, with *All day* unticked, the hours it closes (the
reference PSA's `allDayFlag`, `timeStart`, `timeEnd`): Christmas Eve from noon.
The SLA clocks honour both: a whole-day holiday counts nothing, a part-day one
counts only the hours it leaves open. Add, rename, change hours and retire a
calendar (a retired one stays on the boards that have it and is not offered to
new ones); add and rename lists; add and remove dates. Load a year at once:

```
psaspine import-holidays <db> <list id> holidays.csv   # Date, Name, optional AllDay, Start, End
```

A date already on the list is left alone. Nothing is compiled in: PMC's own
list from HR is the source. Every change is one `CALENDAR_CONFIG` audit row
("hours: Mon 08:00-17:00 -> 07:00-17:00"; "holiday removed: …; the clocks on
this list recompute"). A board picks its calendar on Setup › Board.

### Scheduling (`/schedule`, 038, 28 Sep 2026)

The reference PSA's schedule, kept to what a hospital desk needs:

- **A visit** on a ticket has a **status** (Firm, Tentative: the Schedule
  Status setup table), a **where** (On-site, Remote, In-house: the Service
  Location setup table), a **lead** (the first visit, or whoever is made lead;
  one per ticket), **done** and **acknowledged** (only the booked person can
  acknowledge; moving the visit asks again). The ticket's *Schedule* pod books,
  moves, re-assigns, marks done, reopens and cancels, each a ticket event.
- **Conflicts** are refused unless *Allow a double booking* is ticked, and the
  allowed ones are marked. **Time off is never double-booked**; time off over a
  booked visit needs the same tick, so a visit is never silently orphaned.
- **Blocks** are what is not a ticket: time off, a meeting, an activity. Anyone
  who works a board adds and removes them; each is a `SCHEDULE_BLOCK` audit row.
- **The Schedule page** is the week: one row per person who works your boards,
  one column per day, visits as chips (dashed while tentative, struck through
  when done, ★ the lead) and blocks beside them. Filter by board or *Only me*;
  book a visit on any ticket you work. Dispatch's day view shows who is away.
  Visits on a restricted board are an audited read, as everywhere.
- **Email** to the booked person when the board's owner-mail switch is on, never
  to someone who booked themselves, and no summary in the subject.
- **Setup › Schedule** adds, renames, retires and picks the default status, and
  adds, renames and retires a where.
- **Not built:** reminders and recurring entries. A reminder is an email the
  desk would send on a timer, and a recurring meeting is a Teams invite.

### Knowledge base (`/kb`, 039, 29 Sep 2026)

Articles in Markdown, for the desk or for requesters too, in Draft, Published
or Retired. An article may belong to a board and a Subtype › Item pair; a
ticket's *Knowledge* pod offers the published ones for its pair and board
first, and *It helped* links the article and counts the use. Every save keeps
the text it replaced (history on the article). A board's own articles are
shown only to its members. Published requester articles appear on the
portal's **Help** page (`/my/help`). Patient details are flagged on save, not
refused.

### Security roles (Setup › Roles, 040, 29 Sep 2026)

The reference PSA's Security Roles: each role grants the Knowledge base,
Projects, Reports, the Schedule and Finance a level (None, Read, Add and edit,
All), and each member has one role, or the default. Three starter roles:
**Technician** (the default), **Service manager**, **Read only**. A system
administrator has everything. A role never widens a board: tickets are still
governed by board membership, and a restricted board stays members-only. The
nav shows only what the person may open; a refused page says which module and
level to ask for. Every change is a `SECURITY_ROLE` audit row. The Schedule
level is enforced like the others: Read to see `/schedule`, Write to book or
to block time. The starter roles are written on first use with `INSERT OR
IGNORE`, so two first requests on the threaded server cannot trip each other.

### Projects (`/projects`, 041, 29 Sep 2026)

A project has a manager, dates, a status (Planned, Active, On hold, Done,
Cancelled) and budget hours. Phases break it down, may nest, and may wait on
one another; a phase cannot be marked done while a predecessor is open, and a
loop is refused. Tickets are the work: a ticket's *Project* pod puts it on a
project and phase, and its time entries are the actual hours against each
budget. A project may link BizBox records too.

### Report writer (`/reports/custom`, 042, 29 Sep 2026)

Pick a dataset (tickets, time, visits, projects, knowledge), columns or a
grouping (a count, and hours where the dataset has them), and filters; run
it, download it as CSV, save it, share it. A report administrator pins a
report to the Reports page as a dashboard tile. No SQL is ever typed or
stored: each dataset's code writes the query and limits it to the viewer's
boards. A CSV cell that starts with `=`, `+`, `-` or `@` is quoted so a
spreadsheet cannot run it.

### Finance: agreements, procurement, products, invoices from BizBox (`/finance`, 043, 29 Sep 2026)

Dada's direction: these are BizBox's, and Dada PSA makes way for them. The
Finance pages show a **read-only mirror** of BizBox, in the reference PSA's
shape: Agreements; **Procurement** (purchase orders with a status summary,
their lines, and the tickets and projects each serves); Products; Invoices
(with a status summary, each linked to its agreement where the source has
one). A ticket's *Finance* pod links the PO, agreement, product or invoice it
concerns. Dada PSA issues no invoice.

**What BizBox holds** (SQL01's reading of its catalog, 29 Sep 2026, MEASURED;
`docs/handoffs/HANDOFF-cloud-sql01-WS36-20260929-bizbox.md`), and how the pages
follow it:

- **No supplier agreements.** BizBox's contract tables are patient coverage.
  So agreements are the desk's own (045, below); the mirror's other kinds
  show only when BizBox has given rows for them, and a ticket's Finance pod
  links to mirrored records only.
- **An invoice is BizBox's receiving report**, keyed by the receiving number.
  The supplier's own invoice number is typed by staff and repeats (626
  distinct of 634), so it is never the key; 044 adds `supplier_ref` for it,
  shown as *Supplier's invoice no.* when the map fills it.
- **Paid is not knowable** from those tables (`balance` and `paidamt` are 0 on
  every row), so an invoice's status is BizBox's own word — Draft, Posted or
  Cancelled — and the desk never says paid, unpaid or overdue.
- **Keys are short.** SQL01's views cast them to 20 or 64 characters. SQL
  Server warned at create that the `ext_*` keys *could* exceed its 900-byte
  index limit at the columns' full width; the sync skips and counts any key
  over 64 characters, so no insert can reach that limit. `status`, `currency`
  and `unit` are trimmed to the port's 32 characters for the same reason.
- **At scale.** The lists page by 100 and every count and tile is over the
  whole mirror; a record's page is `/finance/<kind>?ref=<BizBox key>`, the
  key in the query string so that one holding `/`, `%` or an accent opens.
  The Linked column is one query for the page. A refusal from the sync names
  the field, never the cell (the counts-only logging rule).

### Agreements, made on the desk (`/finance?tab=agreement`, 045, 29 Sep 2026)

Dada's direction, 29 Sep: "the agreements need to exist they can add it on
the psa … and add the needed invoices and whatever is exisitng on bizbox".
BizBox holds no supplier agreements, so an agreement is the desk's own record,
in the reference PSA's shape: a name, the party, a term, a status (Draft,
Active, Inactive, Cancelled), an amount and notes. Its page names the
mirrored BizBox **invoices, purchase orders and products** it covers — typed
by number or found in the mirror with a search — and shows them with their
totals against the agreed amount. A mirrored record's page lists the
agreements covering it and adds it to one; the Finance lists show them in the
Linked column. Coverings live in the desk's own table, so the hourly sync
never touches an agreement or a covering: a covered record that BizBox drops
is kept and marked *gone from BizBox*. Nothing here writes to BizBox or to
the mirror. Every create, edit, status change and covering is an `AGREEMENT`
audit row.

**Rights:** Finance *Read* sees agreements; Finance *Write* creates, edits
and covers. Which roles hold Write is set in Setup › Security roles and is
Dada's decision; as shipped, Service manager has it and Technician does not.
A cancelled agreement covers nothing new until it is reopened.

```
psaspine sync-bizbox <db> --map D:\psa\bizbox-map.json --csv-dir <folder>   # from exports
psaspine sync-bizbox <db> --map D:\psa\bizbox-map.json --odbc               # from PSA_BIZBOX_ODBC
                                                                           # add --apply to write
```

- **BizBox holds patient records** (the record, §8.1). The connector reads
  only the views and columns the map names, refuses a name that looks like a
  patient table or field, refuses the `sa` login, asks for read-only intent,
  and keeps the connection string on the host.
- A record gone from BizBox is marked absent, never deleted, so a link to it
  survives; one that comes back is marked present again.
- **Room for edits back to BizBox.** On any record, *Propose the change*
  (Finance, Add and edit) records the field, the new value and why in a change
  log; **BizBox is not touched**, and the page says so. The *Changes to
  BizBox* tab lists them. `psaspine bizbox-changes <db>` prints the pending
  ones as JSON and `--decide <id> --as APPLIED` closes one done in BizBox by
  hand. A future write path plugs in as a `Writer` (psaspine/bizbox.py); the
  one in force today refuses everything.
- The BizBox side (views, a read-only login, the map, the schedule) is
  SQL01's: `docs/handoffs/HANDOFF-cloud-sql01-WS36-20260929-bizbox.md`.

### Search, saved views, standard notes (031)

- **Search** (`Ctrl/⌘ K`): the palette asks `/search.json` as you type and
  answers with tickets, contacts and machines from the boards you are on;
  a hit on a restricted board is audited like the board view's list.
- **My views:** save the board's current filter under a name (the field
  above the counters); your views sit as chips, yours alone; one click
  forgets one.
- **Standard notes** (Setup › *Standard notes*): a board's canned replies,
  each flagged Discussion or Internal. In the note box, pick one and it
  fills in with its flag set; the words stay editable.

### Child tickets (030)

- **What:** Dada PSA's parent/child. Five people report the same
  printer; the first ticket is the parent and the rest are attached as
  children (on the ticket's *Children* pod, or tick rows on the board and
  *Attach to parent*). One person works one ticket; every requester keeps
  their own.
- **Rules, each refused with a sentence:** a ticket is not its own parent;
  one level only (a child has no children, a parent has no parent, so
  nothing loops); only open tickets attach; both tickets must be on boards
  the person works.
- **Closing the parent closes the children,** each on its own board's
  closed status, with an event on both. A child that cannot close (a change
  awaiting approval, a board with no closed status) is left open and its
  ticket says why; the parent's close stands. Detaching gives a child its
  own life back.
- **Not a handover** (005: one ticket changes board) and **not a link**
  (022: a link says why and each ticket keeps its own life).

### Files on a ticket (027)

- **Where:** outside the database, in `<database>.attachments/` (or
  `PSA_ATTACHMENT_DIR`), named by the file's sha256. The same file sent twice
  is kept once, and a file that no longer matches its hash is not served.
  The folder is git-ignored: it may hold screenshots of patient screens.
- **What:** decided by the file's first bytes, never its name: images, PDF,
  text and logs, CSV, email, and Office documents (docx/xlsx/pptx).
  Programs, scripts, web pages, zip archives and anything unidentifiable are
  refused and the person is told why. 10 MB a file; a larger request is
  refused before it is read.
- **Compression, lossless by kind:** PNG image data is re-deflated at
  level 9 with its text and time chunks dropped, and the pixels are compared
  before it is kept; JPEG loses its EXIF, XMP, IPTC and comment segments
  (GPS, device serials) with the scan untouched; text, logs, CSV, email and
  BMP are gzipped when that saves a tenth; PDF, GIF, WebP and Office files
  are already compressed and are stored as sent.
- **Patient information (§6.1):** every file starts *Awaiting review*.
  Anyone who works the board clears it or withholds it; a withheld file is
  flagged `PHI_IN_ATTACHMENT` and served only to the board's
  administrators. A download on a restricted board is audited with the
  file it was. Downloads are always attachments, with `nosniff` and a
  sandbox policy.
- **The requester** attaches files when raising or replying on the portal,
  and sees cleared files and their own, never a withheld one.
- **Email:** files on a message go onto the ticket it became, source
  `EMAIL`. A refused file is written on the ticket and in data quality
  (`ATTACHMENT_REFUSED`); small inline signature images are counted
  (`INLINE_IMAGE_SKIPPED`), not kept.
- **How much (INFERRED, nothing measured yet):** at today's ~700 tickets a
  month, roughly 3 GB a year; hospital-wide at 2,000 a month, roughly
  9 GB; phone photos decide it, because lossless compression only removes
  their metadata. `attachments-usage` gives the measured number once the
  desk is live. Files live outside the database because SQL Server Express
  caps a database at 10 GB (VERIFIED,
  learn.microsoft.com/sql/sql-server/editions-and-components-of-sql-server-2022).
- **Keeping it whole, and not for ever (028):**
  ```bash
  python3 -m psaspine attachments-usage  spine.db                 # by month and board, and on disk
  python3 -m psaspine attachments-verify spine.db [--hashes]      # every live row has its file, every file a row
  python3 -m psaspine attachments-purge  spine.db --withheld-days 30 --closed-days 730   # PREVIEW
  python3 -m psaspine attachments-purge  spine.db --withheld-days 30 --closed-days 730 --apply
  ```
  A withheld file goes N days after its review; any file goes N days after
  its ticket closed; a reopened ticket keeps its files. The periods are
  the operator's arguments, never a default in code, until the Data
  Protection Officer has signed them (§6.1 point 3). The row stays with
  `purged_at`, so the ticket still says what was sent and by whom; the
  bytes go only when no live row points at them. The purge previews unless
  told to apply, commits the rows before it deletes a byte, and refuses to
  run over a store that is not whole -- an unmounted drive looks like every
  file missing, and `attachments-verify --mark-missing` is a person's
  decision. `scripts/Invoke-PmcAttachmentRetention.ps1` runs verify then
  purge on DND-SQL01, preview by default, counts-only log.

### Emails to the requester

- **When:** the ticket is opened (portal, email, phone, walk-up or desk;
  never API or import), and when a fulfiller writes a Discussion or
  Resolution note. Internal notes never send.
- **What:** `[PMC-000123] We have your request` or `… Your request has been
  updated`, one fixed sentence and a link to `/my/PMC-000123` on the
  portal. Never the summary and never the note: those stay behind sign-in
  and the §6.1 controls. Replying to the email threads back onto the ticket
  by its subject token.
- **Not twice:** while one requester email for a ticket is still unsent, a
  further update adds none. Only an address that resolves is queued.
- **Off until turned on:** per board, *Email the requester…* on the board's
  settings. Unset means off, as Dada PSA leaves contact emails until a
  board enables them; turn it on once the portal is reachable over https.
- **The link** is deployment config: `outbox-pending --portal-url https://…`
  or `PSA_PORTAL_URL` (`Send-PmcNotifications.ps1 -PortalUrl`). It must be
  https; without one the email says to sign in to the IT portal.

### Workflow rules (Setup › Workflow rules)

This is the reference PSA's shape, from its archived workflow-rules page:
- **Shape:** a rule is scoped to a board, or to every board. It holds
  events. Each event has conditions read left to right, a run mode (once, N
  times every T, or continuously every T) and actions: notify, escalate, set
  status, move board, assign owner, add an internal note, or flag.
- **Escalation levels** are successive events, for example *50% of the
  respond time used → dispatch*, then *100% → service manager*.
- **Switching on:** a rule is created off. Every event must be tested, which
  shows how many open tickets match now, before it can be switched on. Any
  edit switches it off again.

Where Dada PSA differs from the reference PSA:
- **Timing:** rules fire the moment a ticket is created, changes status,
  gets a note, changes owner or moves board. Only time-based events wait for
  `psaspine run-rules`, which the server runs every minute; the reference PSA waits
  up to ten.
- **SLA time:** "SLA used (%)" follows the board's calendar and leaves out
  time in waiting statuses.
- **Traceability:** every action names its rule and event on the ticket.
  Notify and escalate actions go to a `notification` outbox, with the ticket
  number in the subject.
- **Failures:** an action that fails rolls its whole event back and is
  recorded as ERROR.
- **No chains:** a rule's own actions never fire further rules.
- **Sending:** the desk holds no mail credential.
  `scripts/Send-PmcNotifications.ps1` on DND-SQL01 takes due notifications
  from `psaspine outbox-pending` and sends them through Graph from the
  helpdesk mailbox. It signs in with a certificate, and Exchange RBAC scopes
  `Application Mail.Send` to that one mailbox. It sends only to addresses in
  `pmcne.ph`, and never puts a ticket summary in a subject. Setup:
  `docs/handoffs/HANDOFF-cloud-sql01-WS36-20260923-rules.md`.

Waiting statuses pause the **resolve** clock, never the respond clock. A board
move keeps the ticket id and its clocks. A POST from another site is refused,
on top of the `SameSite=Lax` session cookie.

### A seeded board's first administrator

`IT_HELP` and `UNROUTED` come from the seed with no members, and board access
is membership only (the sysadmin flag never widens it, by design). So the
first administrator of a seeded board is named once, audited as
`BOARD_MEMBER`, either on the server with `psaspine board-admin <db> --board
IT_HELP --member <account>` (or `setup-board … --admin <account>`) or by a
system administrator in Setup under "Boards with no administrator". A board
that has members never takes that road again; its own administrators add the
rest under Members & roles.

## Time, as Dada PSA records it (28 Sep 2026)

A technician who has used the reference PSA expects its time entry, so Dada PSA takes
it (the fields are its `TimeEntry`, VERIFIED 9 Sep 2026 from its
OpenAPI schema in the record's extracted model):

- **Start and end, or actual hours, never both.** Hours are end minus start,
  less a **deduction**, kept to the quarter hour (INFERRED: the reference PSA rounds
  by a per-company setting; a quarter hour is the usual one). Zero or less is
  refused.
- **Work role** and **work type**, from Setup › Time (Dada PSA's setup
  tables). A board names its own default of each on its Board tab
  (Dada PSA's `Board.workRole` / `workType`); otherwise the first of each
  in Setup › Time; a retired one stays on old entries and is refused on new
  ones. A work type carries its bill default (Billable, Do not bill, No
  charge).
- **Bill option**: Billable, Do not bill, No charge, or No default (the
  agreement decides), on every entry.
- **Notes with the Internal / Discussion / Resolution flags**, on the entry
  itself: a time entry written with notes is one note carrying the time, and
  the two are refused together when either is wrong.
- **The "Contact" tick.** On a board that emails requesters, a Discussion
  note (and a time entry with notes) carries *Email the requester*, on by
  default; untick it for the one note that is not news.
- **The Time pod is Dada PSA's Time tab**: one row per entry (date, member,
  start–end, hours, deduct, work role, work type, bill, charged as, band) and
  its own *Add time* form; the note composer carries the same fields under
  *Time on this note*.

Two things are the spine's own and stay. The **charge method** (included in
the monthly fee, capacity uplift, separate charge, pass-through,
non-chargeable) is still chosen on every entry, because it is the commercial
classification an uplift claim is defended on, and the reference PSA leaves that to
the agreement. And **the band is derived**: `band_hours` is the smallest of
0.5 / 2 / 4 / 8 / 20 h the actual hours fit in (more than 20 h is one entry
per day), so §5.2's capacity arithmetic, the uplift evidence and every report
read exactly what they read before. An entry over the loop (`close_loop`)
still records its band as its hours.

## Timesheets and time approval (`/time`, 046, 29 Sep 2026)

The uplift claim rests on time entries, and a finance function reading them
asks who approved them. So every time entry belongs to one **timesheet**: the
week (Monday to Sunday) of the day it was worked, by the person who performed
it.

- **The sheet.** `/time` is your own week: every entry with its ticket, hours,
  role and type, charge method and note; day totals; hours against your hours
  a week (40 unless Setup says otherwise). A time administrator sees anyone's
  week, the sheets waiting for a decision, and sets a member's hours a week.
- **The lifecycle.** OPEN while the week is written; SUBMITTED by its member
  (or an administrator for them) once the week has begun; APPROVED or
  REJECTED by a time administrator **who is not that member**, a rejection
  with a reason; reopened only with a note. Every step is appended to
  `timesheet_event` and audited (`TIMESHEET`).
- **The lock.** A submitted or approved week takes no new entry: `add_time`
  refuses it in a sentence naming the week. A rejected week is open for the
  corrections and goes round again.
- **Who.** A sixth security module, **Timesheets** (`TIME`): WRITE keeps your
  own sheet (every role's default, so a role written before 046 keeps working),
  ADMIN decides other people's and sets hours a week; Service manager ships
  with ADMIN, Read only with READ. Setup › Security roles has the column.
- **The figures.** Reports gains *Utilisation, by member*: hours recorded over
  the period, the hours on an approved sheet, and the share of hours a week.
  The uplift evidence says how many of its hours sit on an approved sheet.
- **Grants moved.** 040's `role_permission` listed its modules in a CHECK, so
  the sixth could not be written into it on either store. 046 adds
  `role_grant` (same key and levels, no list); the rows already in
  `role_permission` are read across the first time a role is looked up, and
  the old table stays, superseded, because the port never drops a table.

## Recurring tickets (Setup › Recurring tickets, 047, 29 Sep 2026)

Preventive maintenance is a ticket that must exist on a day nobody remembered.
A **recurrence** names a board template (026), a cadence (daily, weekly,
monthly, quarterly, yearly, every N), the first due day, an owner or the
board's queue, the company, optionally the requester and the machine.

- **Raising.** `psaspine run-rules`, which the host runs every minute, raises
  every due recurrence through `tasks.open_from_template`: the template's
  summary, description and tasks, the owner, the machine attached, and a line
  on the ticket saying which recurrence raised it (the Details card says
  *Raised by*). Then the due day moves on, past today: a runner that was down
  for weeks raises the ticket once, never once per missed period.
- **The day.** A monthly series set on the 31st lands on the 30th or 28th in
  a short month and returns to the 31st after; the anchor is the day the
  series was set on.
- **All or nothing, each.** One recurrence that cannot raise (its template
  retired, say) is rolled back and audited (`RECURRENCE … failed`), and the
  others still run; the runner's exit code says so.
- **Who.** A board administrator sets up the recurrences on their boards
  (Setup › Recurring tickets): add, *Run now* for one extra ticket without
  moving the due day, *Pause* and *Resume*. Never deleted.

## The life of a machine, and its maintenance record (048, 29 Sep 2026)

021 holds what Active Directory knows about a machine; 048 adds what only the
desk can know, edited on the configuration's page: **purchased on, warranty
ends on, installed on, vendor, purchase ref (the PO), location, and the
agreement** (045) it is under.

- **Warranty.** The Configurations list gains two tiles that filter: *Warranty
  ends in 90 days* and *Out of warranty*, and a Warranty column with the same
  chips. `configurations.warranty_state` says EXPIRED, EXPIRING or COVERED
  and the days.
- **The maintenance record, per asset.** A machine's page exports
  `/configuration/<id>/maintenance.csv`: every ticket on it, with board,
  type, state, opened, closed, owner, hours booked and visits made; the list
  exports the same for every machine its filters show. What a DOH inspection
  asks for. Only the boards the reader is on, and a restricted board's rows
  are audited (`RESTRICTED_READ`) as every other list is.
- **Two report-writer datasets:** *Configurations* (no board: a machine is
  the desk's) and *Maintenance: tickets by configuration* (hours from a joined
  sum, never `SUM` over a subquery, which SQL Server refuses).

## Request approvals on the portal (049, 29 Sep 2026)

A new user account, an access change, a licence: the desk should not do it on
the requester's word alone. The reference PSA approves *changes*; a hospital
also needs a manager's yes on a service request. 049 adds it, in three places:

- **Who approves.** Setup › Departments gains an *Approver* column: one email
  per department (`department.approver`). Setup › Boards and the service
  catalogue, on a Subtype › Item pair, gains an *Approval: yes/no* toggle
  (`catalogue_item.needs_approval`). A technician can also ask anyone by hand
  on the ticket's **Approval** card, which suggests the department's approver.
- **What happens.** A ticket whose pair needs approval asks by itself when it
  is opened with the pair or classified into it (`approvals.maybe_request`);
  when the requester's department names nobody, the ticket says so instead
  and nothing is asked. A request parks the ticket in the board's **Awaiting
  approval** status (a starter status now, a waiting status, so the resolve
  clock pauses; a board without it is not parked), emails the approver one
  line with the portal's Approvals page and no summary (§6.1), and remembers
  where the ticket was. The requester's page shows *Waiting for approval from
  … since …*.
- **Who decides.** The approver signs in to the portal and finds it under
  **Approvals**, with the reason; nobody else can decide it (the check is on
  the signed-in identity, not the URL), and a decline says why. The decision
  goes on the ticket as a Discussion note the requester reads, the requester
  is told, the ticket returns to the status it was in (unless someone has
  moved it since, in which case it stays where they put it), and the desk can
  withdraw an open question. Decisions are appended, never edited, and every
  step is audited (`APPROVAL`, `DEPARTMENT_APPROVER`).

`approval` holds one row per question: approver, asked when and by whom, the
reason, PENDING → APPROVED / DECLINED / WITHDRAWN, decided when and with what
note, and the status to return to.

## The desk on a technician's phone (gap 5, 29 Sep 2026)

The same pages, read on a phone in a ward: no separate app, no second set of
templates. The page reads its width and its pointer (`templates.STYLE`, the
rules under `@media (max-width:640px)` and `@media (pointer:coarse)`):

- **One column, thumb-sized.** Every control is at least 40 px tall on a
  touch screen, fields are 16 px so iOS does not zoom into them, the tiles
  and the board's filter bar go two across, the ticket's two columns become
  one (the pods keep their order), and the SLA strip stacks.
- **The board is a list of cards.** Under 640 px a row keeps the summary, the
  priority and the SLA chips, and folds the number, status, owner and age
  into one line under the summary (`table.grid.cards`); the other columns
  and the header row go. Wider tables elsewhere (Dispatch, Setup) scroll
  sideways inside their card rather than crush their columns.
- **A bottom bar.** Every desk page carries a fixed bar at the foot of a
  phone: Board, Dispatch, Schedule, Time (those the person may see) and New.
  On a ticket the bar is the ticket's: Board, Note (the composer), Ticket
  (the card), and **Call** when the contact has a phone number, as a `tel:`
  link. The header keeps its icons and drops the words, the ⌘K badge becomes
  a search icon, and the keyboard-shortcuts button is not there.
- **The requester's portal** already fitted a phone (part 15); it gains
  nothing here and shows no bar.

MEASURED on 29 Sep with Playwright at an iPhone 13's 390 × 844: fourteen
pages (board, ticket, dispatch, schedule, configurations, time, setup, new
ticket, reports, knowledge, finance, the portal's requests and approvals)
render with no horizontal overflow, no control under 40 px, and the bar
present on every desk page and absent from the portal.

## Beyond email: Teams cards and on-call paging (050, 29 Sep 2026)

The outbox carried one kind of message, an email the host's Graph sender
sends. A ward at 02:00 needs two more things: a card in the IT team's Teams
channel, and a page to the person on call that repeats until they answer.

- **A Teams channel is named on the desk, addressed on the host.** Setup ›
  Integrations › *Teams channels* names a channel (`helpdesk-alerts`) and
  whether it *carries pages*. The webhook address behind the name lives only
  on DND-SQL01, in the Teams sender's file (`D:\psa\teams-webhooks.json`,
  keyed by that name); it is never in the database and never in this
  repository. `scripts/Send-PsaTeamsNotifications.ps1` takes the outbox's
  TEAMS channel (`outbox-pending --channel TEAMS`), posts each card to its
  URL, and marks it; preview by default; it posts only to `https://` on a
  Microsoft host: a Teams Workflows "post to a channel" webhook on
  `*.environment.api.powerplatform.com` (the shape made today; the classic
  `*.webhook.office.com` connector retired on 30 April 2026 and Power
  Automate's `*.logic.azure.com` addresses on 30 November 2025, VERIFIED by
  SQL01 on learn.microsoft.com, 30 Sep; both are still allowed and simply
  fail), and marks anything else FAILED unposted. The three scripts that run
  on the host resolve the repository root themselves rather than in a
  `param()` default (`$PSScriptRoot` is empty there under Windows PowerShell
  5.1 with `-File`), and read `outbox-pending`'s JSON with `foreach`, since
  under 5.1 `'[]' | ConvertFrom-Json` is one object and an idle pass would
  otherwise fail (both MEASURED on DND-SQL01, part 21). The card (an Adaptive Card in the incoming-webhook envelope)
  carries the ticket number, board, priority, status and owner, the rule's
  words and an *Open on the desk* button (`--desk-url`, else
  `PSA_PUBLIC_URL`): **never the summary, never a note.** A channel is
  outside the sign-in, and §6.1 keeps a patient's words behind it. Whether
  Teams renders the envelope exactly as posted is NOT VERIFIED from here; the
  SQL01 sitting posts one card and says.
- **A rule chooses the channel.** A workflow rule's *Notify* or *Escalate*
  action now says how it reaches its target: by email (as before), as a card
  in a named Teams channel, or as a page. The email sender never sees a
  card and the Teams sender never sees an email: the outbox row carries its
  channel and each sender asks for its own.
- **A page repeats until somebody answers.** *Page the on-call* on a ticket
  (or a rule's *Escalate … as a page*) pages whoever the rota says is on
  call for the board now, or the duty manager when nobody is: an email to
  them and a card to every channel that carries pages, again every 5
  minutes, 3 times (`page` holds the episode). It ends when they press
  **Acknowledge** on the ticket, when they write a note on it, when someone
  stops it with a reason, or when the ticket closes. Unanswered after the
  last attempt it is EXHAUSTED and, if it was the on-call, the duty manager
  is paged in turn; if nobody is on the rota the ticket says so. `run-rules`
  (PSA-Rules, every minute) moves the clock. Every step is on the ticket's
  history and in the audit (`PAGE`, `CHANNEL`).

What this is not: an SMS gateway. The hospital has none; a phone number on
the contact reaches the technician's phone as a *Call* link (gap 5), and a
page reaches them by email and Teams, which their phone already shows.

## Pictures on a knowledge article (051, 29 Sep 2026)

A fix is often a picture: where the switch is, what the dialog looks like.
An article (039) now takes files, kept the way a ticket's are (027) and
shown in its text.

- **Kept like a ticket's file.** *Files* on the article page: the media type
  is read from the file's own bytes (a program, a script or a web page is
  refused whatever its name), a PNG is repacked and a JPEG stripped of its
  metadata, the bytes are named by their hash in a store of their own
  (`PSA_KB_DIR`, else the attachment folder's name with `-kb`), so the
  attachment store's verifier and purge, which know only tickets, never take
  an article's picture for an orphan. `kb_file` is the row; a removed file
  keeps its row and its audit line (`KB_FILE`).
- **Reviewed before a requester sees it.** Every file starts *awaiting
  review*. The desk (anyone with Knowledge READ) sees it at once; a
  requester on the portal sees it only once a writer has **cleared** it; a
  **withheld** file is served to nobody, and the text says *[image not
  shown]* where it stood. An administrator removes a file.
- **Shown in the text.** The Markdown-lite renderer (`md_to_html`) gains
  `![caption](file:N)` for a picture, `[words](file:N)` for a download and
  `[words](https://…)` for a link; the code line under each file on the
  page is what to paste. Every address is resolved per reader, so the same
  article renders the picture for the desk and the caption for a requester
  who may not yet see it. A picture is served inline with `Content-Security-
  Policy: sandbox`, `nosniff` and no caching; anything else as a download.

## The machine API reads and updates (gap 8, 29 Sep 2026)

`/api/v1` raised tickets and read the ones it raised. Other systems read and
update: a monitoring dashboard lists a board's open tickets, a runbook tool
adds a note and closes what it fixed. A token now carries a **scope**
(`create-api-token --scope`; `schema/local/api_token_scope.sql`, a row from
before it reads as RAISE):

| Scope | May |
|---|---|
| `RAISE` | `POST /api/v1/tickets` onto its board and `GET` the tickets it raised (as before, the default) |
| `READ` | RAISE, and `GET /api/v1/tickets` (`state=open\|closed\|all`, `since=YYYY-MM-DD`, `limit`, `offset`), `GET /api/v1/tickets/<id>` for any ticket on its board (status, owner, requester, times, description), `GET /api/v1/configurations` (`type`, `status`, `q`) and `GET /api/v1/configurations/<id>` |
| `WRITE` | READ, and `PATCH /api/v1/tickets/<id>` with `note` (and `flag` INTERNAL or DISCUSSION), `status` (a name on the board) and `owner` (a member, or blank to unassign) |

A PATCH is applied the way the desk applies it, so the history, the clocks,
the rules and the pages run the same; a note is scanned for patient
information and flagged, never dropped; the audit says `API_UPDATE` with
what changed. The configurations come without the person on the machine.
Still one board and still a local token: a token for a restricted board is
minted deliberately, and every list and read on that board writes
`RESTRICTED_READ` as a person's does. The wrong scope is a 403 that names
the scope needed; another board's ticket is a 404 a caller cannot tell from
none.

## The small setup tables (057, 30 Sep 2026)

The 29 Sep parity check left six small setup items; each is its own
decision in the reference PSA and each is small here: a table or a column,
a page or a tab, nothing seeded, nothing that changes an existing row. A
board that has said nothing behaves exactly as it did yesterday.

- **Emails per board** (`mail_template`; the board's **Emails** tab). The
  reference PSA's service email templates: the subject and body of each
  kind of email the board sends (opened, updated and closed to the
  requester; assigned to the owner; a visit booked to the member; approval
  asked of the approver). Four placeholders, `{ticket}`, `{board}`,
  `{actor}` and `{when}`, and no other: there is no `{summary}` and no
  `{note}`, because a subject and a body leave the building and the words
  stay behind the sign-in. The sender still adds the reference and the
  portal link. A board with no words of its own uses the desk's, shown on
  the tab; a save with an unknown placeholder is refused; going back to the
  desk's words is one button. Audited as `MAIL_TEMPLATE`.
- **The survey per board** (`board.survey_enabled`, `board.survey_question`;
  the Board tab). A board switches the closing survey off, or asks its own
  question on the portal in place of *How did we do?*. Unset is on, as it
  always was.
- **Knowledge categories** (`kb_category`, `kb_article.category_id`;
  **Setup › Knowledge categories**, `/admin/kb-categories`). A name a
  reader browses by; an article may have one; the Knowledge list filters by
  it and shows it. Retiring a category keeps it on the articles that have
  it and offers it to no new one. Audited as `KB_CATEGORY`.
- **Company status and type** (`company_status`, `company_type`,
  `entity.status_id`, `entity.type_id`; **Setup › Companies**,
  `/admin/companies`). Words on a company (a customer, a former customer, a
  prospect; a hospital department, a supplier, a partner), shown as chips
  on the company's page and the list. Words, not rules: coverage is still
  the executed instrument. Every company's status and type are set on the
  one setup page, so the company page stays a reader's page. Audited as
  `COMPANY_SETUP`; every value is checked before anything is written.
- **Auto-assign** (`board.auto_assign`, `board_auto_assign`; the board's
  **Auto-assign** tab). A ticket that arrives on the board with nobody
  named is given an owner in `board.admit`: a rule for its Subtype › Item
  pair names the member; with no rule, the board's mode, *least loaded*
  (the WORK or ADMIN member with the fewest open tickets on the board,
  then by name) or *the default team's leader*. A ticket that arrives with
  an owner keeps it, a member who has left the board or been deactivated
  is never assigned, the assignment is a ticket event by `auto-assign`,
  and the owner is emailed when the board emails owners. No mode, or OFF,
  assigns nobody, as before.
- **The in/out board** (`member_presence`; `/inout`, under the Schedule
  module). Where each member is right now, said by themselves: in, out, on
  site, working remotely or on leave, a note and when they are back. A
  person sets only their own line. The Schedule page carries the word
  under each name, and My profile links to it. It changes no ticket and no
  visit.

## The mail cut-over (058, 1 Oct 2026)

SQL01's handoff of 1 Oct (`HANDOFF-sql01-cloud-WS36-20261001-mail-cutover.md`):
`helpdesk@pmcne.ph`, its `help@` alias and `support@pmcne.ph` all land on
PMO Helpdesk, and the requester hears at each status change.

- **Several addresses on one board** (`board_intake_address`; the board's
  mail-policy card takes them separated by commas). An address belongs to
  one board; every address is checked before any is written; audited as
  `BOARD_INTAKE_ADDRESS`. Before 058 a board claimed one
  (`board.intake_address`): `init` moves that value into the new table and
  empties the column (`db.move_intake_addresses`, run by every `init`), so
  a claim lives in one place. Mail *from* any claimed address is the desk
  talking and never opens a ticket.
- **The pickup, once per mailbox.** `Invoke-PmcMailPickup.ps1` keeps its
  delta link, log and drop subfolder per `-Mailbox`, so a pickup for
  `helpdesk@` and one for `support@` may share `-StateDir` and `-DropDir`
  and never touch each other's state. `-BoardId` passes `--board-id`: mail
  that no board claims lands there instead of the unrouted queue. Intake
  never imports a `.part` file.
- **An email at each status** (`status_mail`; the board's **Emails** tab,
  *An email at each status*). Per status: on or off, and its words, the
  board's own or the desk's. The desk's words depend on the kind of status
  (INFERRED from its settings, so a board that disagrees writes its own):
  one that waits on the requester asks for a reply that keeps the
  reference in the subject (so it joins the ticket); a resolved one says
  to reply if it is not fixed; a closing one sends its own email in place
  of the closed email; any other says where the request is now. Two
  changes before the sender runs send one email, the newer; a status the
  ticket was already in sends nothing; a merge says nothing. Every gate of
  the other requester emails still holds: the board's *email the
  requester* switch, a ticket that came from a person, an address we can
  resolve. Nothing is on until a board turns it on (one button turns every
  status on). Audited as `STATUS_MAIL`.
- **Picked up** (`status_mail` row `PICKED_UP`; a card on the Emails tab).
  The requester is emailed when their ticket's owner is set or changes to
  a person after it was opened. It shares the status emails' one unsent
  slot, so the newer wins. Auto-assign at opening sends nothing extra: the
  opened email names who has it.
- **The hospital's words.** Every desk default to a requester greets them
  by name, says who has the ticket and when, uses the status's portal
  wording, says to call the helpdesk with the reference if it is stopping
  care on the ward, and signs off with the board and `{hospital}` (PMC's
  name, or `PSA_HOSPITAL_NAME`).
- **`psaspine mail-setup`**: one board's addresses, the requester switch,
  and every status and picked-up email, in one audited step; preview
  unless `--apply`. `--show` prints every email the board sends a
  requester, on or off, with its subject and words.
- **`scripts/Register-PsaMail.ps1`**: the host's tasks, one pass a minute
  as the desk's task account: `PSA-Mail-Helpdesk`, `PSA-Notify`, and
  `PSA-Mail-Support` only with `-IncludeSupport` (after PCSD stops reading
  support@). Preview by default; a task whose first run fails is removed.
  The run order is `docs/handoffs/HANDOFF-cloud-sql01-WS36-20261001-cutover-run.md`.
- **More placeholders, for every email the board words.**
  `{requester}` (the requester's name from AD, else the part of the
  address before the @), `{owner}` (who has it, else *the board's team*),
  `{status}`, `{status_text}` (what the portal says about the status:
  `board_status.customer_description`), `{link}` (the ticket on the
  portal, filled in by the sender from `PSA_PORTAL_URL`), `{date}`, `{hospital}`,
  beside `{ticket}`, `{board}`, `{actor}` and `{when}`. Still no `{summary}`, no
  `{note}`, and no echo of the requester's own subject: whether that may
  come back is Dada's decision under §6.1, not built.
- **Replies come from the address the requester wrote to.** A requester
  email carries `notification.from_address`: the claimed address the
  ticket's first email arrived on (none for a ticket raised any other
  way). `outbox-pending` hands it over as `from`; `Send-PmcNotifications.ps1`
  sends as it only when it is `-Mailbox` or listed in `-SendAs`, and as
  `-Mailbox` otherwise. An alias (`help@`) is not a mailbox Graph sends
  as, so it falls back to the mailbox it aliases (INFERRED; NOT VERIFIED
  on the tenant).

## The desk in the reference PSA's shape: owner, resources, priorities, the dispatch board, Outlook (060, 1 Oct 2026)

Dada, 1 Oct 2026: "if you would look at how connectwise works there is a
ticket owner and a member; it should be unassigned to start with and the
dispatcher would assign the tickets; priorities should match what
connectwise has and can be overridden; scheduling should flow into the
ticket; the calendars should be interactive; what should go in outlook is
the same as the outlook integration from connectwise." Checked against the
reference PSA's own API shape (MEASURED from its OpenAPI schema through the
`pyconnectwise` package: `Ticket.owner`, `Ticket.resources`, `Priority
{name, color, sortOrder, defaultFlag}`, `ScheduleEntry {member, dateStart,
dateEnd, doneFlag, acknowledgedFlag, ownerFlag}`,
`Member.calendarSyncIntegrationFlag`); its documentation is behind a
sign-in, so the dispatch portal's behaviour is from indexed excerpts
(INFERRED) and its default priority names are NOT VERIFIED.

- **A ticket starts unassigned.** `ticket.owner` is empty until a person
  takes it: the owner dropdown on the ticket (Me first, then the board's
  members), the board's bulk owner, **Assign me** (owner only, no visit) or
  **Schedule me** (a visit for me; the ticket becomes mine when nobody has
  it: `schedule.flow_into_ticket`). The people with a visit on the ticket
  are its **resources**, shown beside the owner on the ticket and the
  board, never stored twice.
- **Priorities are a setup table** (`priority`: P1 to P4 with a name, a
  colour, an order and the default; `psaspine/priorities.py`; Setup ›
  Priorities, a sysadmin's page). The codes stay fixed because every SLA
  target and catalogue floor names them; the words and colours are the
  hospital's and paint every badge. A person sets a ticket's priority by
  hand (`priority_source = OVERRIDE`; a reason is recorded when given,
  never demanded, as the reference PSA does it) and gives it back to the
  matrix. A store without 060 reads the defaults so every page still
  opens; the page says so.
- **The Dispatch board** (`/dispatch`) is the day as the reference PSA's
  dispatch portal draws it: people down the side, 06:00 to 20:00 across,
  each visit, block and Outlook busy time a strip across the hours it
  covers (overlaps go on lanes), and a **To schedule** list of the open
  tickets with no visit that day. A ticket dragged onto a person's hour
  books a visit (`POST /schedule/slot`); a visit or block dragged to
  another hour, person or day keeps its length (`POST /schedule/move`,
  `schedule.move`; a clash is refused as the forms refuse it); click an
  hour to book by hand; ✓ marks done and 👁 acknowledges. The Schedule week
  and the Calendar drag the same way. Readers see the day and drag nothing.
- **Outlook carries what the reference PSA's sync writes**: the subject is
  `<ticket> - <company> - <summary>` (the catch-all company is left out),
  the body the summary, status, place and a link to the desk
  (`calsync.event_words`). The one guard the record keeps (§6.1): a visit
  on a restricted board, or whose summary the PHI scan flags as an error,
  goes by its number and board alone, so a patient's details never reach a
  calendar that syncs to a phone. A note on the visit never goes.
- **The summary is editable** (Dada: "ticket summaries cannot be edited"):
  the pencil beside it on the ticket; one line, never empty, PHI-scanned
  like a new ticket, written to the ticket's history, and every Outlook
  event already written for the ticket is rewritten so its subject follows.
- **Files open in place** (Dada: "autoviewer on attachments rather than
  being downloaded"): a picture, a PDF or a plain-text file on a ticket
  (the desk and the requester's portal) opens in a viewer on the page with
  Download and Open-in-a-tab beside it; the link alone still opens it
  inline (`Content-Disposition: inline`), `?dl=1` downloads, and Office
  documents and mail files stay downloads because a browser has no viewer
  for them. Pictures and text keep the `sandbox` policy; a PDF shown inline
  gets `default-src 'none'` instead, because Chromium's own PDF viewer does
  not run inside a sandboxed document (INFERRED from its plugin rules; a
  sandboxed PDF comes up blank or downloads). The restricted-board audit
  says viewed or downloaded.

- **A mega menu** (Dada, 1 Oct 2026: "the menu cuts off use the connectwise
  menu or do a proper mega menu", then "do a mega menu instead or side menu
  whichever fits best"): the reference PSA's modules across the bar (Service
  Desk, Companies, Projects, Time, Finance, Reports, Setup, My requests),
  each a word that opens its pages beneath it with a line on what each is;
  hover, click or keyboard, Escape closes; the module that holds the page is
  underlined. A mega menu over a side rail because the desk's pages are wide
  tables and the Dispatch grid, which a permanent rail would narrow. A
  module the person's access does not cover is absent. It fits at 1280 with
  nothing cut off (MEASURED); from 1180 down the modules show as icons with
  the current one named; on a phone (720 and under) one Menu button opens
  every module stacked, and the quick bar at the bottom stays.
- **The requester's emails** (Dada: "use the first name", "a better
  formatted email", "make sure the replies from the tech gets advised to the
  user on the email or on the portal"): people are addressed by their first
  name (a ward or station by its whole name); every requester email carries
  an HTML layout beside the same words as text (hospital and board header,
  the reference, a button to the request; inline styles, no image, no
  external request); and a technician's reply to the requester (a Discussion
  note) goes into the "has replied" email as written when the PHI scan finds
  nothing in it, else the email says to read it on the portal. `{note}` is
  the placeholder, filled in that email only.
- **The exchange so far rides under every requester email** (Dada, later the
  same evening: "the discussion doesn't get carried over on the replies; the
  reply should be read on the email as well"). What the portal's thread
  shows, the email shows beneath its own words, newest first: the
  requester's first email, their replies by email or on the portal, and the
  desk's Discussion and Resolution notes, each signed with the first name
  and the board. Never an Internal note, never a system event, never what
  the body already says, the last eight only (the portal has them all), and
  the PHI gate runs on every entry on its own, so one that names a case
  number reads "Sign in to the portal to read it." while the rest go as
  written. `outbox.conversation` is the engine call; the HTML lays it out as
  quoted entries.
- **The Dispatch board scrolls inside its card** with the hours and the
  names pinned, empty rows short; the day never pushes the page down.
- **A filter applies the moment it is picked**: any select, checkbox or date
  in a GET form sends it (the button stays for text and the keyboard).
- **Cc on the ticket** (061; Dada: "can we add a cc on the tickets"): the
  reference PSA's Cc field. An email's Cc addresses are kept on the ticket
  it opens and a reply's new ones are added (`ticket_cc`; never the sender,
  never one of the desk's own addresses); a person edits the list on the
  ticket, each address checked; every requester email (opened, status,
  picked up, updated, closed) goes to them as Cc within the allowed domains
  (`outbox-pending` hands `cc` beside `to`; `Send-PmcNotifications.ps1`
  sends `ccRecipients`). They see nothing on the portal, and they get the
  same words the requester gets: never the summary, never a note.
- **The unrouted queue claims `helpdesk@` and `help@`** (Dada: "for the
  unrouted board add helpdesk and help@ emails"): mail to them opens on the
  Unrouted queue, where the dispatcher routes it from the Dispatch page;
  `support@` stays on PMO Helpdesk. An address belongs to one board, so the
  help desk gives the two up first (`mail-setup`, in the handoff). The
  "we have your request" email now goes out from the address the mail came
  to: it was queued before intake had written that address, so it went from
  the sender's own mailbox (`outbox.settle_reply_from`).

Schemas 060 and 061 are one table each. On the live desk SQL01 applies them
as schema steps; `init` seeds the four priority rows and never touches a row
already there.

### Nothing is lost, and "why" is one command (1 Oct 2026)

Dada, 1 Oct 2026, on two mails from yahoo and gmail: "make sure it ingests
all". Intake has no rule on a sender's domain (the public-domain list only
stops company matching); both shapes open tickets here (MEASURED). What was
weak: one unexpected error lost the whole pass, the pickup retried the same
files every minute, and every later message waited behind it. Now each
message is its own transaction: one that cannot be placed is recorded as
`UNCLASSIFIED` with an `INTAKE_ERROR` finding naming the error and the file,
the rest of the drop lands, the pickup keeps that pass's files in `failed\`
and the delta link advances.

- `psaspine mail-why <db> --sender yahoo.com` (or `--subject "..."`): what
  intake did with the matching messages, each with its disposition, ticket
  and findings; whether an exclusion rule catches the sender; or that nothing
  arrived from the pickup, which points at the mailbox's task and its log.
- **Generic senders are requesters.** A DOMAIN exclusion on a public mail
  domain (gmail, yahoo, outlook, ...) is refused: one address can be
  excluded, a whole public domain never. And they hear back: `outbox-pending
  --allowed-domain '*'` (`Send-PmcNotifications.ps1 -AllowedDomain '*'`, which
  `Register-PsaMail.ps1` now passes to `PSA-Notify`) releases every domain;
  the words are the same for everyone, a reference and a link.
- **Three host defects SQL01 measured on 1 Oct 2026 (part 28)**, each fixed
  here: the pickup and sender set `PSA_ATTACHMENT_DIR` themselves
  (`-AttachmentDir`, default `D:\psa\files`); every script runs Python
  with stderr as output and decides by the exit code (a warning failed
  every pass); `data_quality.subject_id` is as wide as a Message-ID in the
  port and a Message-ID over 400 characters is hashed, so neither column
  truncates.
- `psaspine mail-retry <db> --message-id <id> --actor <who> --apply`: forget
  a message that was set aside, once the cause is put right, so a fresh
  pickup sync (delete the mailbox's delta file, run with `-Since`) imports it
  again. A message that opened or joined a ticket is never forgotten. `--all`
  releases every one of them in one command, one audit row each.
- **The audit key is shaped where both stores read the same code** (2 Oct 2026,
  MEASURED on the host): `audit_event.subject_id` is class `ID`, 64 characters,
  because it is a key -- indexed beside `subject_kind`, joined to
  `ticket.work_item_id` by Setup > Audit. A Message-ID is not our key and is
  longer, so releasing a set-aside message failed on SQL Server with *string or
  binary data would be truncated* and released none. `db.audit` now cuts the key
  to that width, marks it cut, and writes the whole identifier into `detail`,
  which is `FREE` and is the field Setup > Audit searches. SQLite would have
  stored the long value silently, which is why the shaping is in the code and
  not left to the host.

## Configuration types, statuses and questions (056, 30 Sep 2026)

021 fixed seven configuration types and three statuses in a CHECK. A
hospital's CMDB outgrows that the day biomedical devices join it: an
infusion pump is not *Other*, and what is asked of it (an asset tag, a last
calibration date) is not asked of a printer. **Setup › Configuration
types** (`/admin/configuration-types`) adds a type and says which of the
seven kinds it **counts as** (`configuration_type.maps_to`), adds a status
and says which of the three it counts as, renames, retires, and gives a
type its **questions** (`configuration_question`: text, number, date or
yes/no, needed or not). The seven and the three are rows too, written on
first use and counting as themselves; they cannot be retired, since they
are what the others count as. A configuration carries both the setup
table's key (`type_id`, `status_id`) and the 021 code it counts as
(`config_type`, `status`), so every report, filter, CSV and API shape that
read the codes keeps its meaning, and a type that changes what it counts
as carries its configurations with it. The configuration's page shows the
type's questions in a *details* card; a member who may work a board
answers them, every answer is checked before any is written, a needed one
cannot be left blank, and the change is audited like any other. The list's
tiles and type filter read the setup table.

## Setup › Email connector (055, 30 Sep 2026)

The reference PSA's Email Connector is a page per board holding the mailbox,
its credential, parsing rules and exclusions. On this desk the mailbox and
its certificate live on the host, in the pickup task, and the page
(`/admin/mail`) holds what belongs to the desk: **which board claims which
address** (053, with the unrouted queue and each board's reply policy),
**what never opens a ticket**, and **how the last seven days' mail was
placed**. An exclusion (`mail_exclusion`) is made once: mail from an address
or a domain, or whose subject contains a phrase (a vendor's newsletter, a
scanner's "document attached", an out-of-office), is still imported and
recorded (intake has always dropped nothing) and opens nothing, with the
reason on the data-quality finding (`MAIL_EXCLUDED`) and counted by
`import-mail` as `excluded`. Delivery-system senders and auto-replies stay
excluded by the desk itself. The page shows senders by domain only and never
a subject: a subject can carry a patient's words, and a system administrator
is not a member of every board.

## Setup › Audit and Setup › API tokens (054, 30 Sep 2026)

The desk has written an audit row for every change since day one; nothing
read it but a ticket's own history. **Setup › Audit** (`/admin/audit`) reads
the trail: who, when, what, on which record, and since 054 **where from**
(`audit_event.source`: DESK, PORTAL, API, INTAKE, RULES, BIZBOX or CLI,
stamped once by the entry point, never by the engine that made the change;
rows from before 054 read as unknown, which is the truth). Filter by person,
action, record kind, record, source, date and words in the detail; page
through; export the answer as CSV, which is itself audited (`AUDIT_EXPORT`).
A row about a ticket on a restricted board the reader is not a member of
shows its number and the action, never its detail: a system administrator
is not a member of a restricted board by being an administrator (§6.1).
Three indexes carry the filters.

**Setup › API tokens** (`/admin/api-tokens`) puts gap 8's tokens on a page:
mint one (label, board, scope; the token is shown once and only its hash is
kept), see every token with its board, scope, maker and last use, and
disable or re-enable one. `create-api-token` on the host still works and
lands in the same list.

## The ticket screen in the reference PSA's shape: Screen layout, Pod configuration, pod height (1 Oct 2026)

Dada: "make the ticket view similar to the ticket view from ConnectWise and
all of its function, making the pods adjustable pod height". VERIFIED 1 Oct
2026 against the vendor's blog and three integrators' guides (Thread,
1Stream, Visionary 360): the reference ticket screen has a **Screen Layout**
gear that opens **Pod Configuration** with Available and Displayed lists,
pods are dragged into place, and notes carry an avatar and a colour per
author. The desk's ticket page now has the same:

- **The gear** at the right of the ticket's actions opens **Pod
  configuration**: every card on the page under Displayed or Available,
  tick to show, untick to hide, arrows to order, Save. Reset layout puts
  everything back.
- **Pod height**: the reference's plus and minus on every card (Dada: "they
  have a plus minus to adjust pod size height"), 80 px a press from where
  the card stands, or drag the card's bottom edge; the rest scrolls inside,
  and the page remembers it.
- With the Size button (Full, Medium, Half, Small), the fold, the move
  arrows, the column swap and drag: order, column, size, height, folded or
  hidden, each per person, in their browser, with one Reset.
- Already there and unchanged: avatars and a colour per author on the
  notes, Discussion / Internal / Resolution, the Contact tick, time on the
  note, standard notes, files with the viewer, tasks, configurations,
  schedule, the audit trail under History.

Not built, said once: issue tags. Rich text in a note was built on 2 Oct
2026 (064) and the email it arrives in on 5 Oct; inline images are still not
shown inside a note, and a file is reviewed beside it, by the PHI fence.

## Pod sizes, and whose rows the Dispatch board shows (063, 1 Oct 2026)

**Pod sizes** (Dada: "size the pods like small half medium full as the
message will go all the way ... don't lose readability"). Every card on the
ticket page has a Size button beside Fold: Full, Medium (two thirds of its
column), Half, Small (a third), in a cycle. Two half cards sit side by side,
so Activity and Add a note share the wide column and a note no longer runs
the width of the screen. The browser remembers sizes with the order and the
folds; Reset layout clears all three; on a narrow screen every card is full
width whatever was chosen. Readability is kept by a rule as well as a
choice: a note, a description and a card's explanatory text never run past
80 characters a line, whatever the card's width.

**Whose rows the Dispatch board shows** (Dada: "an edit view as to who will
be displayed on the dispatch portal"): the reference PSA's dispatch portal
shows a chosen set of resources. The **People** button on the day bar opens
the list of everyone on the boards you see (plus anyone with a visit that
day); tick whose rows you want. **Show** is for now (`who=` in the URL, so
a link carries it); **Save as my view** keeps it (`dispatch_view`, one row
per dispatcher, theirs alone) and applies whenever you open Dispatch;
**Clear my view** goes back to everyone; **Only me** still wins over both.
The button says how many of how many are showing, and "saved" when the
saved view is what you see.

## A note is written the way a Teams message is (064, 2 Oct 2026)

Dada, 2 Oct 2026: *"can we have a text editor so we can properly edit the
replies"*, then *"also copy pasting and a proper text editor via html or like
html or teams text editor"*.

The note box is now an editor, not a text field. Bold, italic, underline,
strikethrough, bulleted and numbered lists, a quote, inline code, a link, and
clear formatting; Ctrl+B, Ctrl+I and Ctrl+U where the hands already are. A
**paste out of Outlook or Word keeps the words and the marks and brings none
of the markup**: the paste is rebuilt in the page out of elements, so Word's
thousand lines of `mso` styling never arrive at all. **Plain** beside
**Rich** writes the same note as plain text for anyone who would rather.

**One gate, and only one.** `psaspine/richtext.py` is the only place a note
becomes HTML. It does not strip what it dislikes from a string; it reads what
arrives and writes a new document made only of the tags and attributes on its
own lists. A script, an event handler, a style, an iframe, a `javascript:`
address: not removed, never written. Badly nested markup comes out well
formed. `richtext.text` goes the other way, and **that** is what the PHI scan
reads, what the plain part of an email carries and what a search matches, so
a patient's name cannot hide inside an attribute.

`ticket_event.body_format` (064) says which a note is. Every note written
before today is plain text and reads exactly as it always did. A note read
back out of the database is cleaned again before it is shown, because a thing
out of a database is a thing from outside. Mail arrived as plain text until
5 Oct 2026; it now comes through the same gate (see below).

**The requester's email carries it as written.** `notification.body_html`
(064) holds the same email with the note's own formatting in it, built when
the note is written; the text of the email is always sent as well. A note the
PHI gate holds back carries no formatting either, because it carries no
words.

**Text size**: an **Aa** button beside light and dark gives Small, Normal and
Large, remembered in that browser.

**The cards sit still.** A pod is no longer draggable at rest: its controls
are hidden and its words select and copy. **Edit layout**, the grip button
beside the gear, turns the handles on, outlines each card and puts a bar at
the foot of the page; Done or Escape turns it off. That is the reference
PSA's own shape, and it means a stray drag cannot move a card while somebody
is reading it.

## A requester could not open their own request (2 Oct 2026)

MEASURED on a live ticket: a requester clicked the link in her own email and
the portal answered "No such request". The portal matched the one address on
her session, and PMC has staff whose mailbox is on one domain and whose
sign-in is on another; intake writes whichever address the mail was sent
from.

The portal now asks the contact and member records for **every** address
they hold for this person, and any of them makes the request theirs. It
never widens past them: each address comes from a row that already matched
their own sign-in name or session address. The refusal, when it is somebody
else's request, now names the address they are signed in as, which is what
tells "there is no such request" apart from "you raised it from your other
address", and tells them neither.

`Invoke-PsaSpine.ps1 -WhoSees PMC-000155 -Person <them>` says which it is:
the address the ticket was raised from, every address the desk knows for
that person, and whether they see it.

### Running a desk command on the host, as the desk (2 Oct 2026)

A SQL sysadmin cannot run one: SQL Server maps every sysadmin to database user
`dbo`, whose default schema cannot be changed, and the desk refuses `dbo` so it
can never write to the wrong schema. `scripts\Invoke-PsaSpine.ps1` runs the
command as the account the desk itself runs as, whose name it reads from the
desk's own scheduled tasks rather than guessing it. One switch per thing it is
for, because PowerShell reads a bare `--word` as a parameter it does not have
and stops to ask, which once swallowed three lines of an operator's session:

    .\Invoke-PsaSpine.ps1 -MailHealth
    .\Invoke-PsaSpine.ps1 -MailRetry                      # lists what was set aside
    .\Invoke-PsaSpine.ps1 -MailRetry -All -Apply          # releases every one
    .\Invoke-PsaSpine.ps1 -SchemaPreview                  # what a new schema file would add
    .\Invoke-PsaSpine.ps1 -SchemaApply                    # adds it; guarded, so a re-run adds nothing
    .\Invoke-PsaSpine.ps1 -Spine "<any psaspine command>" # anything else, as one quoted string

It asks for that account at the Windows prompt and keeps it nowhere. `-OutFile`
puts what the command wrote where a caller can read it without this script's own
lines mixed in. `-ViaTask` needs nothing typed at all -- elevated, it registers a
one-shot task under S4U and removes it again -- but S4U needs that account to be
allowed to log on as a batch job here, and it says so plainly when it is refused
instead of failing three more times afterwards.

`Repair-PsaMailPickup.ps1 -AsDesk` and `Fix-PsaToday.ps1 -AsDesk` put their own
questions to the desk the same way. Without it, those questions are asked under
the caller's login and refused, which is not a fault in the desk or in the mail,
and they now say so rather than reporting it as one.

## Editing a pod leaves the page where it was (3 Oct 2026)

Dada, 3 Oct 2026: *"when editing pods it resets the screen or re-orients the
screen and doesn't stay, it goes back up"*, and *"the drop downs broke when
editing or moving the pods"*. Both were one fault with two faces, MEASURED in
Chromium: **scrollY 294 → 0 on a single pod edit**.

`apply()` re-appended **every** pod on every change, whether or not anything had
moved. Two consequences: the browser cannot anchor a scroll to a node that
moves, so the page jumped to the top; and re-appending a card closes any native
dropdown inside it, which is why a select "broke" while the pods were being
edited. Three things fix it:

- **Move nothing that is already where it belongs.** A fold, a resize or a
  height bump now does no DOM moves at all.
- **Hold the reader's place**, instantly. The stylesheet asks for
  `scroll-behavior: smooth`, which is right for a link and wrong here: an
  animated restore glides the page while the layout is still settling, and
  `scrollY` read mid-flight is not where the page will land. The restore is
  explicitly `behavior: "instant"`.
- **Anchor on the right thing.** An *in-place* change (fold, size, height) holds
  the **card**, since what is above it may change height. A *reorder* (arrows,
  swap, drag) holds the **viewport**: the card is meant to move, and chasing it
  dragged the whole page to the top when a card went to the top of its column.

MEASURED after: size, fold, taller and move-up all hold `scrollY` at 700, and
the cascade still narrows once the pods have been shuffled. `tests/browsercheck.py`
asserts all five.

## A stopwatch on the ticket, which is not the SLA clock (065, 3 Oct 2026)

Dada, 3 Oct 2026: *"there is usually a clock on the ConnectWise ticketing for
time entries, that's apart from the SLA"*. He was right that the desk had none:
a technician could only type a start and an end into the time entry from
memory, afterwards.

**The two clocks are different things, and 065 says so twice so nobody confuses
them:**

| | `ticket_clock` (007) | `time_timer` (065) |
|---|---|---|
| Measures | the hospital's obligation | one person's worked time |
| Starts | itself, on the board's rules | when a technician presses Start |
| Calendar | the board's working hours | none; wall-clock seconds |
| Pauses | on the statuses that pause it | when the person steps away |
| Feeds | the SLA numbers | `time_start` / `time_end` on a time entry |
| By hand | never | always |

**No SLA number is derived from the stopwatch, ever**, and a test asserts that
running one leaves every `ticket_clock` row untouched.

On the Time pod: **Start timer** → it counts in front of you, with **Pause** and
**Stop**. Stopping opens *Add time* with the date, start and end already filled
from what it measured; the hours round **up** to the quarter, because a job that
ran sixteen minutes cost the quarter hour it ran into. The technician can still
correct any of it before saving — the timer is evidence, the entry is the claim.
A timer belongs to the person who started it; one may run per person per ticket
(two would double-count the same hour), and nothing stops one person running
timers on three tickets at once, which is what carrying three jobs looks like.
**Discard** throws it away and records nothing.

## Naming a ticket, and unmaking a mistake on a project (5 Oct 2026)

Two asks in one line from Dada: *"for projects they cant be deleted edited any
elements for the project cant do that also a drop down for the tickets would be
nice or a search function wherein the ticket will be displayed on all ticket
fields"* — the second about the field *where tickets are linked to each other*,
which he clarified: *"there is a field where users can attach tickets or merge
or child or link tickets"*.

### Nine forms wanted a number typed from memory

Link a related ticket, attach a child, make this a child of, merge into, the
board's two bulk fields, put a ticket on a project, and the two ways of booking
a visit all asked for `PMC-000123`. Typing a number from memory is how a ticket
gets linked to the wrong ticket, and nothing in the field stopped it.

`templates.ticket_pick` is now the one control for all nine. It is a text input
with a `datalist`, so **the browser draws its own dropdown with its own keyboard
handling** and nothing here reimplements a listbox; the options are filled from
`/search.json` as you type — the same endpoint the command palette uses, which
answers only from the boards you are on and audits a restricted board's hits.
Each option reads the summary, who it is for, the state, and (see below) where
the match was found. A picker never offers the ticket you are on, because a
ticket cannot be linked to itself and offering it is a trap.

**With scripting off it is the plain text input it always was.** That is also
why the ticket number stays the value: the form posts exactly what it posted
before, and not one view had to learn a new shape. A number typed in any case
(`pmc-1`) is tidied to `PMC-000001` when the field loses focus.

### The search behind it now matches every field

It matched three things — the number, the summary, the requester's address — so
finding a ticket meant already knowing its number. It now also matches the
owner, the company, the status name, the Type › Subtype › Item, the contact's
name and email, the source reference, the record type, the priority, **and the
words of the ticket's notes**. Each hit says which field matched when the field
is not one the dropdown shows, so a result that looks unrelated explains itself
("in a note") instead of looking like a bug.

**The note clause needed a guard.** A note written in the desk's editor, or
arrived as an email's HTML (064), is stored as markup, so a bare SQL `LIKE` on
it matches tag and attribute names: a search for `p`, `br` or `noopener` would
have returned every rich note on the desk. SQL narrows the rows, then
`richtext.text` — the same function the PHI scan reads — decides whether the
needle is really in the *words*. One known limit, stated rather than hidden: a
tag in the middle of a phrase (`Ward <b>3</b>`) splits it, so that exact phrase
will not match.

### A project's plan can be corrected

`projects.py` opened by saying *"Nothing is deleted: a project is cancelled or
done, a phase is done."* That is right about work and wrong about mistakes.
A phase could be added and marked done and that was all — so a typo in a phase
name, a predecessor set the wrong way round, a ticket on the wrong project were
**permanent**. The worst of the three: `set_phase_status` refuses to finish a
phase while something it waits on is open, so one wrong predecessor left two
phases that could never both be done, with no way back.

Now:

| | |
|---|---|
| **Edit a phase** | Its name, dates, budget hours, and where it sits in the breakdown. Everything is checked before anything is written, so a refused edit leaves the phase exactly as it was. A phase cannot be moved inside itself or inside its own descendant. |
| **Reorder a phase** | Up and down among its own siblings. `sort_order` existed from the start and nothing could change it, so the order phases were typed in was the order they stayed in. |
| **Take a predecessor off** | Each "waits on" is a chip with a ×. |
| **Remove a phase** | Only one carrying no work. A phase with child phases, tickets or booked hours is **kept**, and the row says which of the three and why, instead of offering a button that refuses. Pointers *at* a removed phase go with it, so nothing is left waiting on something that no longer exists. |
| **Unlink a ticket** | From the project's own page. The engine could already do it; only the ticket's page had a way to ask. |
| **Edit the project** | Its name and description have fields at last; `update` always supported both. |
| **Unlink a BizBox record** | There was a Link form and no way back. |
| **Remove a project** | Only one that never got going: no phases, no tickets, no BizBox record. A project with any of those is **cancelled**, not deleted, so its tickets keep their hours and their history — and the page says so rather than offering a delete that refuses. |

Every one of those is audited. A removal is a line on the trail, not a silence.
Hours are never deleted: they are the record of work done, and a phase holding
them says so and offers Done instead.

## The ticket shows the email, not Outlook's fallback (5 Oct 2026)

Dada, with a live ticket open: *"can we make html from emails or render the
full emails on the tickets"*, and a screenshot of why. The ticket read:

```
[Speaker phone with solid fill]
The Teams phone on Ward 3 is not ringing...
[cid:image004.jpg@01DD5349.6A321CD0]
Portal <https://portal.pmcne.ph/x> Portal
https://portal.pmcne.ph/x
```

None of that is what the sender typed. An Outlook message carries two bodies —
`text/html`, which is what they composed, and `text/plain`, which Outlook
generates from it — and intake kept only the second. The fallback is where an
icon becomes its own alt text, an inline image becomes its `cid:` reference,
and every link is written twice (once as a label, once as the address).

**Intake now keeps the HTML part and the ticket shows it.** It goes through
`richtext.clean` — the one 064 gate, the same one a technician's own note goes
through — so the page is a new document made only of the tags on its lists.
`ticket_event.body_format` is `'HTML'` on the INTAKE and INTAKE\_REPLY events
that came in that way. A mail sent as plain text is stored and read exactly as
it was before, and so is every note already in the database. **No schema
change**: 064's `body_format` column is already there, so this is code only.

What the gate refuses, which is why this is safe to put on a clinical desk:

- **A script, a style block, an event handler, an iframe, a `javascript:`
  link** — never written, because the gate writes a new document rather than
  editing the one it read.
- **Every image, inline or remote.** `<img>` is not on the allow-list, so a
  tracking pixel cannot phone home and a remote image cannot tell the sender
  that a clinician opened the ticket and when. A file the mail attached is
  still kept on the ticket, through the PHI review it always went through;
  what is *not yet* built is showing it inside the note. *(Built 6 Oct 2026
  for pictures the sender pasted in, by Content-ID only, and still never a
  remote image: see the 066 section below.)*
- **Word's and Outlook's own markup** — `mso` styles, `<o:p>`, conditional
  comments: unwrapped or dropped, words kept.

Two things that come with it:

- **A layout table keeps its words apart.** A table is unwrapped, not kept, and
  unwrapping one without a trace used to run every cell into the next
  (`Sister ReyesWard 3ext 4412`). The end of a cell is now a space and the end
  of a row a line. Email is written in tables, so this is most of a signature.
- **The window is the email's, not a note's.** `richtext.MAX` (60 KB) is the
  right bound for something a person typed; a ward's reply carries the whole
  quoted thread, so the email door and every read-back use `EMAIL_MAX`
  (400 KB). Reading a stored note under the shorter bound would have cut the
  page off mid-sentence.

**The PHI scan reads the words of both parts.** A patient reference can sit in
the HTML and not in the fallback — a link's own text, a cell of a table — and
what reaches the page is what must be scanned. `phi.scan` gives at most one
finding per rule per field, so one name repeated across both parts is still one
row on Setup › Data quality, not two.

**Two places that were already wrong, and are now right.** They were wrong for
desk-written rich notes since 064 and this change would have made them common:
a board row's 90-character preview of the last note spent all 90 on its opening
tags, and merging a duplicate ticket carried a rich note across as plain text,
so it read as its own markup on the ticket it was merged into.

## The email as it was sent: a sealed frame, its pictures, its fold (066, 6 Oct 2026)

Dada, with two screenshots of live tickets: *"ticket replies look like these
and HTML is or emails are not rendering properly on the ticket viewer and images
are not rendering on the ticket"*, and *"can we search on github whats the best
renderer for html so we can beautify the pages more"*. Then: *"lets also add a
way to sort messages by earliest first then to the newest on tickets"*.

What the screenshots showed (MEASURED from them, and reproduced in a test from
a real Outlook reply's shape): every Outlook line a paragraph apart, because
Outlook writes each line as its own `<p class=MsoNormal>` with its margin set
to zero in a `<style>` block the gate rightly drops, and the desk's own `p`
margin then applied to every line; the signature's table run flat; the pasted
screenshot missing; and the whole quoted thread below the reply at full length.

### What "the best renderer" is

The research (VERIFIED 6 Oct 2026) agrees on one answer, and it is not one
library. Products that show untrusted email inside their own page use **three
layers, each assuming the one before it failed**:

1. **An allow-list sanitizer** that rebuilds the document from the tags it
   knows. [DOMPurify](https://github.com/cure53/DOMPurify) in the browser;
   [nh3](https://pypi.org/project/nh3/) (Python bindings to Rust's
   [ammonia](https://github.com/rust-ammonia/ammonia)) on a server, since
   [bleach was deprecated in January 2023](https://github.com/mozilla/bleach/issues/698).
2. **A sandboxed `srcdoc` iframe** without `allow-scripts`, so whatever the
   sanitizer missed has no script and no access to the desk's page.
   [Close](https://making.close.com/posts/rendering-untrusted-html-email-safely)
   and [AgentMail](https://engineering.agentmail.to/blog/rendering-email-safely-preventing-phishing-attacks)
   describe exactly this.
3. **A Content-Security-Policy** inside the frame that fetches nothing from
   outside, so a tracking pixel or a remote stylesheet cannot report that a
   clinician opened the ticket.

For the quoted thread, the libraries
([talon](https://github.com/mailgun/talon),
[quotequail](https://pypi.org/project/quotequail/)) find the point where the
reply ends and the quote begins by the markers mail clients leave.

**No new dependency.** Layer 1 was already here: `richtext.clean` is a
tokenizer-rebuild allow-list, the same design as nh3, and it has carried the
064 notes and the 5 Oct email door. What was missing was layers 2 and 3, and an
email profile for layer 1, because email is written in tables and inline styles
that a note's profile rightly refuses. The desk installs nothing it did not
already have, and the portal artifact rule (no CDN, no external request) still
holds by construction.

### The three layers, as built

- **The gate's email profile** (`richtext.clean(..., profile="email")`): adds
  `table`/`tr`/`td`/`th` and their sections, `div` (kept as a `div`, so
  Outlook's `WordSection1` no longer becomes one tall paragraph), `span`, `hr`,
  `sup`/`sub`, `details`/`summary`, and `img` **only** with a `cid:` source.
  `style` survives only as an allow-list of properties (`CSS_PROPS`: weight,
  size, alignment, margins, padding, borders, widths) with a value pattern of
  letters, digits and `#%., -` up to 80 characters, so no `url(`, no
  `expression(`, no escapes. **No colour and no background**: an email chooses
  neither the text colour nor the page under it, so dark mode stays readable
  and white-on-white cannot hide a line.
- **The frame** (`templates.mail_frame`): `<iframe class=mail
  sandbox="allow-popups allow-popups-to-escape-sandbox allow-same-origin"
  referrerpolicy=no-referrer srcdoc=...>`. Never `allow-scripts`. Same-origin
  is there only so the page can measure the email's height and pass the theme
  and text size in; with no scripts in the frame it grants the email nothing.
  Links open in a new tab (`<base target=_blank>`). In dark mode every border
  takes the theme's line colour, so Outlook's pale rule over a quoted header
  does not read as a white bar.
- **The policy** (`richtext.MAIL_CSP`): `default-src 'none'; img-src 'self';
  style-src 'unsafe-inline'; font-src 'none'; base-uri 'none'; form-action
  'none'`. A picture can come from the desk and from nowhere else.

The frame is exactly as tall as the email: the server sets a first guess (a
line per paragraph, each picture at its stated height; 310 px guessed for an
Outlook reply drawn at 295) and the page then watches the email's body for size
from outside. Opening the fold, a picture arriving and a card being resized all
re-fit it. It fits to the email's own box, never to the frame's
`scrollHeight`, which is never less than the frame itself: fitting to that grew
the frame by 2 px a refit, about 120 px a second, without end. The browser
check that should have caught it compared against the same number; it now
compares against the content and checks the height 1.5 s later too
(MEASURED, 6 Oct 2026, fixed before it shipped). Nothing is listened for *inside* the email, because a sandbox
without scripts runs no listener there, the desk's included. The light/dark
theme and the reader's text size follow the desk's.

### The quoted thread folds

`richtext.split_quote` finds where the reply ends: Outlook on the web's
`appendonsend`/`divRplyFwdMsg`, Gmail's `gmail_quote`, Yahoo's, Thunderbird's
`moz-cite-prefix`, Apple Mail's `blockquote type=cite`, `-----Original
Message-----`, and desktop Outlook's bold **From:** followed by **Sent:** or
**Date:**. Everything from there down sits in a closed `<details>` titled
*Earlier messages in this email*. One click opens it, inside the frame, with
no script.

**Notes already stored get this too.** The fold and the frame are applied when
a note is drawn, not only at intake, so the tickets in the screenshots read
properly on the next page load, with no re-import and no data change. New mail
is stored as `body_format = 'EMAIL'` (the 5 Oct door stored `'HTML'`; an
INTAKE or INTAKE\_REPLY note in `'HTML'` is recognised as an email and drawn
the same way). A note a technician writes in the desk's editor is still `'HTML'`
under the note profile, and is not framed.

### Pictures pasted into an email (schema 066)

A pasted picture is not a link: it travels inside the message as its own part,
and the HTML points at it by that part's Content-ID (`cid:image004.jpg@01DD…`).
Intake already kept the part as an attachment, through the patient-details
review; it threw away the name the HTML uses for it. **066 adds
`attachment.content_id`** and intake now records it. When a note is drawn, each
`cid:` is resolved there and then:

- **On the desk**, any image file of the ticket that is not WITHHELD and not
  purged (a file still awaiting review is shown, as it is on the Files card).
  A withheld one reads *picture image001.png: withheld for patient
  information*, a purged one *removed under the retention rule*, in a dashed
  box where the picture was.
- **On the requester's portal**, only a file the portal already shows
  (`_visible_files`). Anything else reads *a picture, shown here once it has
  been checked*, or *a picture that is not shown here* when it was withheld
  or purged.
- **A signature logo** under `INLINE_LOGO_BYTES` (20 KB) is still not kept at
  intake, as before, so its place is left out rather than drawn broken.

The stored HTML keeps `cid:…`, never a URL. **Mail imported before 066 cannot
show its pictures**: the file is there, but the name that ties it to its place
in the email was not recorded, so the picture is left out of the note and is
still on the Files card.

### What goes out to the requester

The outbound thread (`outbox.conversation`) read `ticket_event.detail` as plain
text, so a rich note went out as its own markup. It now cleans a rich note
under its own profile, sends only the reply above the fold (never the quoted
thread a second time), and runs the PHI gate on the words before anything is
sent. A note the gate flags is still replaced by the portal wording, as before.

**A job title is not a patient (Dada's decision, 6 Oct 2026).** A signature
reading *"Junior Philhealth Associate"* tripped `PHI_PHILHEALTH_MENTION`, so
every reply quoting that signature went out as the portal wording rather than
its text. Dada: fix it. The rule now skips *PhilHealth* when the next word names
a job or an office (Associate, Officer, Clerk, Staff, Section, Department, Unit,
Office, Coordinator, Supervisor, Head, Team, Specialist, Assistant, Personnel,
Desk, In-charge). Any other mention is still flagged (*"his PhilHealth claim"*),
and a PhilHealth-shaped number is flagged beside any word at all
(`test_a_philhealth_job_title_is_not_a_patient_reference`).

### Ethel and "the old menu"

A member who signs in with Microsoft got the requester's layout. The Entra
callback put the token's object id (a GUID) in `user.id`, which matches no
`board_member` row, so the desk saw someone on no board: the requester shell,
and `/` sent to `/my`. That is the "old menu" (INFERRED from the code path and
reproduced in a test; the handoff asks SQL01 to confirm from the audit which
door Ethel uses). **The Entra sign-in now maps to the member** the way the
Windows door does: by the member's email, then by the sign-in name's local
part. The object id stays in the audit detail.

### Procurement and PMO Helpdesk side by side

`python -m psaspine board-compare <database> <board_a> <board_b>` prints what
differs between two boards: settings (kind, calendar, owner, live, requester
emails, survey, closed loop, default work role and type, …), the count of each
part of its set-up (statuses, SLA targets, ticket types it takes, members,
teams, email addresses it claims, per-status emails, standard notes,
templates, workflow and auto-assign rules, departments, on-call shifts),
statuses on only one side, and what each holds (tickets, projects, recurring
tickets) for context. Plain SELECTs on both stores, read-only. On a bare test board it shows
the gaps a board set up by hand usually has (calendar `-`, SLA targets 10 vs 0,
ticket types 4 vs 0). What Procurement actually lacks is for SQL01 to MEASURE;
the handoff has the command.

### Oldest first, or newest first

The Activity card's tabs carry **Oldest first** / **Newest first**. One click
reverses it on the server (so the reading order and keyboard focus are right,
not just the picture), and the browser keeps the choice in a `psa_order`
cookie (Path `/ticket`, a year, `SameSite=Lax`, `Secure` when the desk is
behind HTTPS). `?order=old|new` sets it for a link.

### What a browser proves here

`tests/browsercheck.py` now opens an Outlook reply carrying a table signature,
a pasted screenshot, a script and a tracking pixel, and checks: the frame
exists and its sandbox has no `allow-scripts`; the frame is as tall as the
email and stays that tall; the script never ran; lines are a line apart (21–22 px), not a
paragraph; the table has cells; the picture loads from the desk; the fold
starts closed, opening it grows the frame and closing it gives the room back;
dark mode reaches inside; nothing was fetched from outside; and the sort toggle
reverses and is remembered. 60 checks, 0 failures (MEASURED, 6 Oct 2026).

One trap for whoever extends it: Playwright's own `click()`,
`bounding_box()` and element-level `evaluate()` inside a script-less sandboxed
frame leave a helper there that the sandbox refuses, and Chromium logs
*"Blocked script execution in 'about:srcdoc'"* six times. Those errors are the
harness's, not the desk's: a bare page with the same frame and a plain mouse
click logs none (MEASURED). The checks read the email through the page, as the
desk itself does, and click with the mouse.

## After part 37: resources, >Cancelled, required fields, the time entry window, a Teams note box (067, 6 Oct 2026)

Dada's list once SQL01 had 066 live: *"assigning tickets to multiple members"*,
*"time entry clock like connectwise clicking it launches the time entry or
discussion window"*, *"add a >cancelled status"*, *"add required on the fields
company ticket type type and subtype and item"*, *"color coding for replies one
color for pmo staff and another color for requestor"*, then a Teams-like note
box with fonts, pictures and GIFs, a Back button, and *"futuristic design on
the whole ticketing board and transitions"*.

**Several members on a ticket (schema 067 `ticket_resource`).** The Ticket card
has a **Resources** picker: tick any of the board's working members. They show
beside the owner, together with anyone who has a visit booked (who stay ticked
and fixed: they come off when the visit does). **Mine** on the board includes
tickets you are a resource on. Each member added gets the owner's "assigned"
email on boards that send it. Somebody not working the board cannot be added;
an existing assignment of somebody who has since left is kept, not dropped.

**>Cancelled.** A closed status (the `>` is the desk's mark of closed, as on
`>Closed`) on every new board's starter set and in the PMC pack. A cancelled
ticket asks no satisfaction survey. A close the desk makes for someone (a child
closing with its parent, a merged duplicate) never lands in it; a board whose
only other closed status is retired leaves the child open, as before. Existing
boards get it with `add-cancelled`, which previews unless `--apply`; on a board
with an *open* status called Cancelled (Procurement, from the 1 Oct pack) it
moves those tickets across through `change_status`, so they close the way any
close does, and then retires and renames the open one.

**Required fields.** Company, Ticket type and Type › Subtype › Item carry a red
asterisk and are refused empty by the browser and by the server, on the Ticket
card's Save and on New ticket. One-field forms (Assign me, the summary pencil)
carry no `fields=1` and are not held to them, so assigning an emailed ticket
does not first need it classified. The Item is required only where the board
has a catalogue to choose from.

**Replies coloured by who wrote them.** PMO staff in the desk's blue, the
requester's side in teal, each labelled and with a legend by the tabs; an
Internal note keeps its amber. Staff is anyone the desk knows or a member's
email; the requester on their own ticket is the requester even when they are
staff. The portal shows the same two colours ("You" and the team).

**The time entry window.** The clock in the ticket's header starts this
person's timer (065) -- the start is logged on the server -- and opens a
window laid out as the reference PSA's Time Entry is (field order from
docs.topleft.team/knowledge/editing-connectwise-tickets, VERIFIED 6 Oct 2026):
member, date, start, end, actual hours, deduct; work role, work type, bill,
charged as; the notes in the desk's note box; Discussion / Internal and
Resolution; Email Contact and Resources; Status; Save. Leaving End empty means
"now": Save stops the clock, fills it in, books the time and spends the timer
(which `timers.spend` existed for and nothing called until today). A job the
clock measured at under eight minutes is booked as one quarter hour rather than
rounded to nothing. Closing the window keeps the clock running, and the header
shows it ticking; the Time card keeps the table and offers *Enter time by hand*.

**The note box (a Teams reply box).** Paragraph style (heading, subheading,
monospaced), size, bold / italic / underline / strike, a **text colour** and a
**highlight** from a fixed palette, lists, quote, code, link, emoji, and a
**picture or GIF pasted, dropped or attached**. Colour, size and highlight go
up as the desk's own classes (`tc-*`, `fs-*`, `hl-*`), never a free colour or a
style attribute; the gate (`richtext` note profile) keeps nothing else, and an
email to the requester writes each class as its inline style. Pictures go up as
files, are kept with the ticket's files (so through the patient-details review;
a requester sees one only once it is cleared, or straight away if it is their
own), and the note names each by Content-ID exactly as an email's inline
picture is (066). A GIF is stored as it came, so it still moves. A picture
taken out of the note before Save is not kept. Up to 9 MB of pictures a note.

Not built, on purpose: a GIF search. Teams' is GIPHY, which would send staff
search terms and addresses to a third party, and Tenor's API was shut on
1 July 2026 (VERIFIED 6 Oct 2026, 9to5google.com/2026/06/30/google-tenor-api-gif-updates/).
A GIF on the desk is a file somebody has.

The stray inbox picture in an empty note box (Dada's screenshot) was the
editor reusing the class name `empty`, which the desk's empty-state boxes use;
it is `is-empty` now.

**Back.** The ticket page has *Back to …*, to wherever it was opened from
(the board, a search, Dispatch, a project). Each tab keeps a short trail in
`sessionStorage`; a page that only reloads itself, a ticket after a save,
replaces its own entry, so Back never returns to the same ticket a save ago.

**The look.** A soft aurora behind the page, a gradient rule under the header,
cards with a lit edge that rise into place and lift on hover, gradient primary
buttons with a glow, highlighted board rows and gradient SLA bars, on top of
the page cross-fade the desk already had. Only colour, opacity and transform
move, nothing is blurred (old ward PCs), effects stay under a quarter second,
and all of it is off for a reader who asks for reduced motion.

Research behind these choices (VERIFIED 6 Oct 2026): the editor libraries
(Quill 2.0.3 is the only single-file one with colour and size, last released
Nov 2024; Lexical and TipTap 3 need a bundler; Trix has no colour), so the desk
keeps its own `contenteditable` box; cross-document view transitions run in
Chrome and Edge 126+ and Safari 18.2+, and Firefox simply loads the page.

### Later on 6 Oct: one status alone, a time entry that cancels, a window that moves, a second look

- **`add-status <db> <board> <name> [--escalation …] [--closed] [--portal …] --actor … [--apply]`**:
  one status on one board and nothing else. It previews unless `--apply`, and adding the same
  name again does nothing. It exists because `setup-pmc` would re-add the catalogue rows the
  2 Oct Type restructure retired (SQL01, MEASURED). `setup-pmc --statuses-only` gives the
  pack's statuses alone.
- **Cancel in the time entry window cancels the entry.** It confirms, discards the clock, and
  records no time. **–** minimises the window (the clock keeps running) and **▢** makes it
  larger. The window moves by its title bar and resizes from its corner, and the notes box
  grows with it.
- **A second design pass:**
  - a deeper dark theme and a faint dot grid behind the page;
  - glowing pills on the active menu module, and gradient page titles;
  - KPI tiles with glowing icons;
  - rounder inputs that light up on focus, and pill buttons;
  - glowing SLA bars and thin scrollbars.

  Notes do not rise in like the cards do, because the pod editor keeps the page still by
  measuring them (the browser check caught a 52 px jump).

### Last on 6 Oct: the control-room look, dark by default, the note as a window

Dada, on a screenshot of the second pass: *"there are still so much white and there are dots
on the back … this doesnt look futuristic and modern at all"*, *"add note is still there that
is redundant"*, and *"animations are welcome and transitions as long as they dont lag it"*.

- **Dark is the default.** A browser that never chose a theme opens dark; the sun button still
  switches to light, and the choice is remembered as before. The dot grid is gone.
- **Light is no longer white.** Canvas, panels and lines are a cool tinted grey-blue, so a page
  has depth instead of glare.
- **The control-room look:** a floating glass header with a cyan-to-violet edge; glass panels;
  neon primary buttons and menu pills; inputs that glow cyan on focus; gradient titles; neon SLA
  bars; the activity timeline as a lit line with glowing dots. Windows (time entry, new note)
  are solid, so nothing behind them reads through.
- **The note box left the pods.** It was the "add note" pod Dada called redundant. **New note**
  in the ticket's header opens it as a window, like the time entry: it moves by its title bar,
  grows with **▢**, resizes from its corner, and **–** closes it with the draft kept.
- **Motion, kept cheap.** Buttons and tiles lift on hover, SLA bars sweep in, tile numbers count
  up, windows pop open, the header drops in. Only `transform` and `opacity` move, nothing is
  blurred, and all of it is off under *reduce motion*.
- The browser check's pod-editing checks scrolled to a fixed offset and skipped themselves
  silently once the page got shorter (71 → 67). They now scroll to a pod, and a missing pod fails.

### After that: menus that hold, and depth (6 Oct 2026)

Dada, on a screenshot of the Service Desk menu over the Projects page: *"opacity issues"*; then
*"dont you think the design is too flat"*.

- **Menus were see-through, and at some widths cut off.** They used the translucent panel
  colour, and the menu bar's fade-out edge is a CSS mask, which clips everything inside the bar,
  the open menu included. The mask now lifts while a menu is open. Menus, tips, toasts, the
  command palette and the windows are frosted hard (86% plus a 20 px blur), or solid where the
  browser has no blur. Two browser checks hold both: the menu is drawn whole, and the page does
  not read through it.
- **Depth, in three heights.** The canvas has deeper glows and a vignette. Cards and tiles sit
  above it with a lit top edge, a light-to-dark fill and a real shadow. Menus, windows and the
  bar float highest, frosted. Fields are recessed into their card. Tiles are tinted by what they
  mean (red breached, amber due, cyan selected). Buttons have a lit top and a shaded foot.
  Blur is only on those small floating areas, never on the page.

### Light, with depth (6 Oct 2026)

Dada: *"the light theme is still too flat"*. Light read flat because the page and its cards
were nearly the same pale. Now the canvas is a deeper blue-grey with indigo, cyan and violet
glows; cards are white and stand off it on a three-step shadow with a crisp edge; tables have
a header band and visible row lines; fields have a defined well and a cyan focus ring; tiles
carry their colour further; quiet buttons have an edge. Menus and windows in light are solid
white, because pale on pale shows through even under blur.

### `setup-pmc` made safe, and the hover glow back (6 Oct 2026)

- **`setup-pmc` no longer touches the catalogue unless asked.** SQL01 measured its preview on the
  live desk at 81 lines: On Hold, plus 80 that would rebuild *Hospital systems (BizBox)*, which
  the 2 Oct restructure had retired after moving its Subtypes. Now:
  - the pack adds statuses only, unless `--with-catalogue` is given;
  - even with it, an Area, Subtype or Item the desk has retired, or a Subtype it has moved to
    another Area, is never brought back. Each is printed as `skip: …`, and the count line says
    how many were left alone;
  - `--statuses-only` still works, and is now the default behaviour.

  `test_the_pack_never_rebuilds_what_this_desk_retired_or_moved` builds the 2 Oct shape in
  miniature and asserts that not one catalogue row is added.
- **The hover effects are back.** The depth layers set each theme's resting shadow on cards,
  tiles and buttons, and those rules out-ranked the plain `:hover` glows. The glows are now
  restated last, per theme: cards, tiles (red or amber for a breached or due tile), rows,
  neon and quiet buttons, menu entries, fields and tabs. Four browser checks hold this: a tile,
  a card, a row and the Filter button each change under the pointer.

### Time entries that save, and stay visible (6 Oct 2026)

Dada, on PMC-000331: *"time entries when the time entry has been saved isnt saving anywhere"*; then
*"also remove the charge as dependency"*. Two causes, both reproduced in Chromium before they were
fixed:

- **Save could do nothing at all.** Start and End carried `step=300`. The browser counts those
  5-minute steps from the value the box arrived with, so a clock started at 16:27 made an End of
  16:40 "invalid". Save was then refused by the browser, with only a small bubble beside a box.
  Any minute is valid now (`step=60`); the desk keeps the entry to the quarter hour itself.
- **A refused Save lost the notes.** *Charged as* started blank and the desk refused a blank one,
  but only after the notes were typed, and the page came back empty. On Dada's word it is no
  longer a dependency: blank means **Included in monthly fee** (in-house time), and the box
  starts there. A technician may still pick another. This replaces the earlier rule that a
  charge was never assumed. And if the desk refuses a Save for any other reason, the window now
  reopens with the note and every choice still in it. The draft is kept in the browser tab only,
  and it comes back through the editor's own `rebuild()`, the same allow-list as a paste.
- **Where to find them.** The Activity card has a **Time** tab, and each booking reads as
  *Time entry*, not as a grey system line. The Time card now sits under the Ticket card by default
  (Reset layout brings a saved layout to the new default).

Browser checks hold all of it: Charged as starts on Included and is not required; an End 13
minutes after the clock's start is valid; a refused Save reopens the window with the note and its
colour kept.

## Projects in the reference PSA's shape: team, tickets inside, a live board (7 Oct 2026, schema 068)

Dada, 7 Oct 2026: *"adding project members have not yet added please review connectwise projects and load
everything that is missing from there also the projects board should show the projects and tickets live or
can be created inside of the project itself like connectwise"*, and *"make sure it doesnt mess up or break
anything on the current build"*.

The reference was read from ConnectWise's own documentation (MEASURED via the public `?psa=1` pages:
Project Details, Team Members, Work Plan, Project statuses) and its API models. What it has, and what this
desk now has:

| ConnectWise | Dada PSA, 7 Oct |
|---|---|
| Team: member, project role, est. hours, start, finish; the PM is on the team | **Team** card: member, role (Project manager, Team lead, Team member, Engineer, Consultant, Stakeholder), dates, planned hours against hours booked. The manager joins as Project manager, and so does a new manager; whoever a project ticket is given to joins as a team member (INFERRED from "anyone scheduled is added") |
| New ticket from a phase on the Work Plan; summary and a status from the project board; budget hours | **+ Ticket** on every phase, and **New ticket** at the top, open one window: summary, phase, who, budget hours. The ticket is opened on the project's board through `tickets.open_ticket`, the one door every ticket comes in by |
| Work plan: phases with their tickets, budget against actual | The **Work plan** card lists each phase's tickets under it, with who has each and its hours against its budget |
| Project ticket board by status | A **Ticket board** card: one lane per status on the project's board |
| Project list: company, PM, status, % complete; My projects / all | **Projects**: Company, Complete (share of tickets closed), Hours, Tickets, Team, each project's open tickets under it, and **My projects** (managed or on the team) |
| Notes pod | **Notes** card |
| Company on the project | **Company** on New project and on the project's own form, and the board can be changed there too |
| (live updates NOT VERIFIED in ConnectWise) | The list and the project page refresh themselves when a project, its phases, team, notes or any of its tickets change (`/live?scope=projects`, `project:<id>`), the same quiet poll the board uses |

**Later on 7 Oct (schema 069): the rest, except billing.** Dada: *"add those missing ... except for the billing
bit"*. Additive again: `project_contact`, `project_ticket_dependency`, `project_plan_item`, and nullable
`project.is_template`, `project.health`, `project_ticket.starts_on` / `due_on`.

- **Contacts**: a Contacts card, from the desk's contacts (the project company's first), with a role on the project.
- **Health**: On track / At risk / High risk / Off track, as the reference PSA's status indicator. Left alone, the
  desk reads it: over budget, or past the end with tickets open, is Off track; past 85% of budget, or within a week
  of the end under 80% done, At risk. A person can set it on the project's form; it shows on the project and the list.
- **Close project**: a window that closes the project as Done or Cancelled, and if asked moves its open tickets to a
  closed status and marks its phases done. Closing as Done never uses >Cancelled (the desk's 067 rule); a ticket
  on another board goes to that board's own closing status. Closing a ticket needs WORK on its board.
- **Ticket predecessors and dates**: **Plan** on each work plan ticket sets its estimated start, required date,
  budget, and what it waits on. A loop is refused. As the reference PSA does, a ticket waiting on an open one takes
  no time (`board.may_book_effort` says why), and a predecessor can be taken off with its ×.
- **Gantt**: phases and dated tickets as bars on a day scale with today marked; anything undated is listed, not guessed.
- **Templates and Copy project**: a project with no tickets can be made a template, whose **planned tickets** sit on
  no board. **New project from this template** and **Copy project** carry the phases (nesting, predecessors, budgets,
  dates moved to the new start), the team and the contacts, and open a new unassigned ticket for each planned
  ticket (or each of the copied project's tickets). Templates are listed apart on Projects.

Still not built, on purpose: billing (method, PO, rates), as Dada said.

**What did not change.** 068 is additive: two new tables (`project_member`, `project_note`) and two nullable
columns (`project_ticket.budget_hours`, `project.entity_id`). Every existing page, check and test still passes,
including the restricted-board rule: a ticket on a board the viewer cannot read is in none of the new cards, its
hours are in no total, and the projects list counts only what the viewer may see. Six new browser checks drive it:
+ Ticket opens the window with its phase picked, the ticket lands under its phase and on the board, a member is
added with a role and hours, and the list shows each project's open tickets.

## Project boards apart, a page per tab, converting tickets, project setup (7 Oct 2026, schema 070)

Dada, 7 Oct 2026: *"if u check connectwise the project board isnt a service board ... load each tab on its own
page u added them on a single page ... what will happen in there is that it will be a hodge podge of tickets /
you can convert a service ticket into a project ticket / you havent copied its entire setup"*.

**Project boards are not service boards.** A board's kind was already SERVICE, CHANGE or PROJECT (`itil`); a
PROJECT board runs no SLA clocks and takes only the Project record type. Now:

- The **Service Board** (`/`) and its live stamp show only service (and change) boards
  (`common.service_board_ids`). A project ticket is never on it. A person on project boards only lands on Projects.
- **Projects** is laid out as Dada put it: *"the project board holds the projects the projects hold the tickets"*.
  One card per project board, its projects in it, and each project's open tickets under it. A project not yet on a
  project board is listed apart, to be moved onto one. There is no flat list of project tickets.
- **Setup** shows *Your service boards* and *Project boards* as separate cards, with **+ New project board**.
- New project, and the project's own form, offer **project boards only** (a project already on a service board
  still reads, marked *(service board)*).
- A ticket can be opened inside a project only when the project is on a project board. A project made before
  today on a service board carries a banner and **Move to the project board**: the project and every one of its
  tickets go across (`projects.move_to_project_board`), numbers, notes, time and history kept.

**Converting a ticket**, as the reference PSA converts a service ticket to a project ticket:

- On the ticket, the **Project** pod offers *project › phase* and **Convert to project ticket**. The ticket moves
  to the project's board (`board.move`, record type Project, the board's default status), joins the phase, and its
  running SLA clocks stop (`projects.convert_to_project_ticket`).
- A project ticket's pod offers **Convert to service ticket** with a service board: it leaves the project, its
  predecessor links go, and its stopped clocks stay stopped, so project time is never counted against an SLA target.
- On the Work plan, **Add an existing ticket** converts a service ticket in the same way.
- Each needs WORK on both boards.

**Each tab is its own page**, as the reference PSA's project screen: `/project/<id>` is the Project tab (dashboard,
details, contact overview, notes, template and copy), and `/project/<id>/<tab>` is Work plan, Gantt, Tickets
(the ticket board and list), Issues, Attachments, Team, Contacts, Recap (hours by phase, member and work role),
Time, Configurations, Audit trail and Finance (BizBox links). Billing is still left out, on Dada's word. Every
form posts back to the tab it was on.

**Project setup tables** (Setup › Projects, `/admin/projects`):

- **Project statuses**: name, status indicator (On track, At risk, High risk, Off track), default, closed,
  *No time* (time cannot be booked on the project's tickets) and inactive. A status's indicator is the project's
  health unless a person sets health by hand. The five statuses a project could hold before are seeded with their
  old codes as ids and **none of them holds time**, so nothing already live changes; `project.status` keeps its
  old code (a new open status reads ACTIVE, a new closed one DONE) for every older reader.
- **Project types**: name, default, inactive; a Project type on the project's form.
- **Project roles**: the team roles, editable instead of fixed.
- **Issues** on a project: raised, assigned, closed or reopened, or **Make a ticket** (a project ticket in the
  phase picked; the issue closes and points at it).

Schema 070 is additive: `project_status`, `project_type`, `project_role`, `project_issue`, and nullable
`project.project_status_id` / `project.project_type_id`. The vocabulary is seeded by `init` into empty tables.

## Chat: a requester and the desk, live (7 Oct 2026, schema 071)

Dada, 7 Oct 2026: *"can we do something to connectwise chat?"*. Confirmed before building: requester to desk,
offered on the portal at any time, patient details flagged and warned about, never blocked. Shaped on the reference
PSA's Chat as its product pages describe it: a requester starts a chat from the portal, it waits in a queue, a
technician picks it up, and it becomes a ticket or joins one. That shape is INFERRED; its Chat documentation sits
behind sign-in, NOT VERIFIED.

- **Portal: Chat with the helpdesk** (`/my/chat`). A subject and a first message start a chat. It goes on a board
  the requester's department may use (Setup › Departments), else Unrouted, as a request does. The conversation page
  shows new lines as they arrive. Enter sends. Either side can end it.
- **Desk: Chat** (Service Desk › Chat, `/chat`). The queue shows chats waiting first, then those being answered, then
  the last two days' ended ones, on the boards the person is on. It refreshes itself. On a chat:
  - **Pick it up** or **Take it over**. Replying also picks it up.
  - **End the chat**.
  - **Make a ticket**: on the chat's board, for its requester, the transcript as its description, owned by the
    technician. The chat stays open, and the requester sees the request it became.
  - **Add to a ticket**: the transcript goes on as a Discussion note, so the requester can read it on the portal.
- **Patient details** (§6.1): every requester line is scanned. It is kept, the finding counted in `data_quality`
  for the desk to tidy, and the requester shown a reminder. A line is never refused, because that would send the
  same words to the telephone, where nothing records them.
- **Live without a socket**: the open chat polls `…/messages.json?after=<id>` every three seconds and appends new
  lines, so what someone is typing is never lost to a reload. The queue uses the desk's live stamp
  (`/live?scope=chats`). Nothing new is opened on the server's network surface.
- Who may read a chat: someone on its board (WORK to answer); on the portal, only the requester who started it.

Schema 071 is additive: `chat_session` and `chat_message`.

## Chat, round two: a moving banner and a chime, reactions, files, a rating (7 Oct 2026, schema 072)

Dada, 7 Oct 2026: *"add a banner ... a moving banner like moving from right to left ... and a sound or a chime
... reactions and emojis to the chat and also attachments and a survey at the end"*. Confirmed before building:
Teams-style reactions, pictures and files through the patient-details review, the requester rates the chat.

- **The banner.** On every desk page (never the portal), the chats waiting on the person's boards run across the
  top, right to left, each a link to the chat, with *Open Chat* beside them. A hover holds it still, and it is
  still for anyone whose system asks for less motion. It polls `GET /chat/waiting.json` every 8 seconds and hides
  when nothing waits.
- **The chime.** A new waiting chat chimes: two soft notes made in the page (Web Audio), no sound file. The bell on
  the banner turns it off or on, remembered in that browser. A browser plays sound only after the person has
  clicked once on the page, so the first chime of a fresh tab may wait for that click.
- **Reactions.** 👍 ❤️ 😄 😮 🙏 ✅ on any line, Teams-style. Hover a line and press ☺+; the counts sit under the
  line, yours marked, and a second press takes yours off. Both sides see them change without a reload.
- **Emoji.** 😊 by the box opens a set of forty to put into the message. They are characters, so nothing is fetched.
- **Pictures and files.** The paperclip, a pasted screenshot, or a file dropped on the conversation sends it as its
  own line, with the typed words as its caption. Pictures show in the conversation.
  - Files are kept in the tickets' store, by hash, with the same packing and checks (10 MB at most).
  - A ward's file arrives PENDING: the desk sees it at once with **Clear** and **Withhold**, and the sender sees
    their own. The desk's files are cleared as sent. A withheld file is gone from the requester's side.
  - The store's integrity check counts chat files as live, and a purge keeps their bytes, so retention never takes
    them for orphans.
  - When the chat becomes a ticket, or joins one, its files go onto the ticket with the review they already had;
    a withheld one stays behind.
- **The rating.** When a chat ends, the requester sees *How did we do?*: one to five stars and an optional
  sentence (scanned like every requester text), once. It shows on the desk's chat page, in the queue, and in
  Reports as **Chat rating** beside Satisfaction.

- **"Please wait".** Dada: *"a message to the user ... before a ticket gets picked up like please wait ... similar
  to support chats"*. Confirmed: in the chat, editable per board. The moment a chat starts, the desk's welcome line
  appears in it ("Thanks, you are in the queue. Someone from IT Help will be with you shortly ..."). Above the
  conversation, the ward reads *Please wait, someone will be with you shortly: you are number 2 in the queue*, kept
  current by the poll. When a technician picks it up or replies, a line says who has joined, and the state reads
  *Jun Reyes is with you*. Each board writes its own welcome on its Setup page (*Chat welcome*; `{board}` is its
  name). Unset, it reads the desk's words.

Schema 072 is additive: `chat_reaction`, `chat_file`, `chat_survey`, and the nullable `board.chat_welcome`.

## Peach, purple and pink, each in dark and light (8 Oct 2026, code only)

Dada, 8 Oct 2026: *"add a peach mode a purple mode and a pink mode apart from the dark mode and light mode"*, then
*"make sure all the colors for pink peach and purple also has dark versions ... and make sure the rest of the buttons
the tables and headers match the theme as well ... and make sure it doesnt break anything"*.

The theme button in the bar opens a menu in two parts: **Mode** (Dark, Light) and **Colour** (Classic, Peach, Purple,
Pink), each with its swatch, the current ones marked. Every colour has both modes. The **t** key flips the mode and
keeps the colour; the command palette's *Theme* entry does the same. Both are remembered per browser
(`psa-theme`, `psa-tint`).

How it is built, so that nothing already there changed: every blue and cyan the chrome read as a literal (the glows
and row hovers, the lit edges of cards in the dark, the edges and bands of the light, the title gradient, the active
module, the focus ring, the buttons' gradient, the table header's band) now reads a token whose default is exactly
the literal it replaced. Without a colour chosen, every token holds its old value. MEASURED: a probe that renders the
old and the new stylesheet over the same chrome and compares the computed styles of 23 elements in classic dark and
classic light reports **0 differences**. A colour overrides the tokens, in both modes, and gives the canvas, the
cards, the fields and the table header's band its own cast; ink and the status colours (SLA, priorities, good /
warn / bad) stay as they are, so nothing loses its contrast or its meaning.

## The Dispatch Portal, in the reference PSA's shape (8 Oct 2026, code only)

Dada, 8 Oct 2026: *"we need to fix the dispatch portal and make it look like what connectwise looks like and function
like connectwise"*. Confirmed before building: the day grid, a Service Tickets table with filters, Day + Week. The
reference PSA's Dispatch Portal is INFERRED from its product pages and training material (its docs are behind sign-in,
NOT VERIFIED).

- **The day grid.** Resources are rows, each with their name and the hours booked against the day's capacity
  (*3.5 / 8.0 h · 44%*, with the bar under it). The hours run across with a half-hour line in every cell and the red
  line at now. A visit is a block from its start to its end, named by its ticket, its summary and its company, coloured
  by its status: **firm** filled, **tentative** outlined, **done** green with a tick. Outlook time is striped grey. A
  clash is outlined red. The legend under the grid says all of this.
- **The hands.** Drag a row from Service Tickets onto a resource's hour to book it (an hour, the ticket becomes theirs if
  nobody has it). Drag a visit to another person or hour to move it. Drag its **right edge** to change when it ends, in
  half hours (`POST /schedule/resize`). **Right-click** a visit for *Open ticket*, *Mark done* / *Reopen*,
  *Acknowledge* (your own) and *Delete the visit*. **Double-click** opens the ticket. Click an empty hour to book by
  hand. Every action is one ordinary form post, so the forms still do all of it without a mouse.
- **Service Tickets.** The left panel is a table, as the reference PSA lists them: Ticket #, Summary, Company,
  Priority, Status, Owner, Age, the open tickets on the boards shown with no visit on the day. A search box (filters as
  you type, and on Filter), a status filter, and *Include scheduled* to list the ones already booked. **‹** folds the
  panel away to give the grid the width, remembered in the browser; *Tickets* on the bar brings it back.
- **Day and Week.** The bar switches between the day and the week (`?view=week`): the seven days as columns, each
  day's visits, tasks and Outlook time listed, hours booked against the week (five days' capacity). A visit dragged
  onto another day keeps its time. *Today*, ‹ ›, the date, the board, *Only me* and *People* apply to both.

No schema change. The Unrouted queue and the board roles stay below the portal.

## The email link opens the request (8 Oct 2026, schema 075)

Dada, 8 Oct 2026: *"when users click on the see my requests it goes to a 404"*. MEASURED from Dada's screenshot:
`help.pmcne.ph/my/PMC-000391` answered *No such request, or it was not raised by you. You are signed in as
joseph.marcelo* — a Windows sign-in by name, on a request raised from an email address the desk held no contact row
for. Confirmed before building: the link carries a key, and a sign-in name matches the same name on the hospital's own
domains.

- **The key in the link.** *See your request* now points at `/my/PMC-000391?k=…`. The key is the ticket's own, made
  the first time an email about it goes out and kept for the ticket's life (`ticket.portal_key`). Whoever holds the
  email opens that one request once signed in to the portal, whatever address they signed in with: a shared mailbox
  like *Philhealth Encoder*, a name the desk cannot tie to the address, a second address. It opens that request and
  nothing else, and it is not a sign-in. Every read by key is on the audit trail (`PORTAL_LINK`, with who used it).
  The page's reply form, survey and file links carry the key on, so the next click holds. A wrong key is the same 404
  as before.
- **A Windows name on the hospital's own domains.** `joseph.marcelo` is also `joseph.marcelo@pmcne.ph`, and the same
  on any other domain the staff's addresses are on. The domains are read from the AD contacts and member records the
  desk already holds (the five most common), never typed in, and never a public mail domain. INFERRED: PMC's mailboxes
  are named after the account; a name that is not is still caught by the key. With this, *Your requests* lists
  Joseph's email-raised requests too, and a plain link works.

Schema 075 adds `ticket.portal_key`, NULL until the first email. Handoff: `HANDOFF-cloud-sql01-WS36-20261008-portal-link-075.md`.

## Proving the email link, and mending the old ones (8 Oct 2026, schema 076)

SQL01, 8 Oct 2026, MEASURED on `PMC_PSA` after 075 went in: none of the 894 notifications holds the link, because the
sender puts it together at the moment of sending, so nobody could say which link a person was sent. The only proof of a
link was clicking it in somebody's mailbox, which the host cannot do. PMC-000391 had no key at all: its six emails all
went before 075. Dada: *"find a proper solution for this"*. Confirmed before building: all three parts below.

- **The link is kept on each email.** The sender (`outbox-pending`, run by PSA-Notify) writes the link a requester
  email carries into `notification.portal_link` as it builds it: the same text the person got. Not on a `--dry-run`,
  not for approver, paging or desk emails, and not before 076 is applied (the email goes exactly as before).
- **A check on the host, with no mailbox.** `psaspine portal-check <db> --ticket PMC-000397 [--person joseph.marcelo]
  [--portal-url https://help.pmcne.ph]` signs the person in the way the portal's doors would (a Windows name with their
  contact's address, or an address as Entra gives it), asks the portal's own router for the request on the portal's
  address, and reports the answer for the plain link, the email link, a wrong key and *Your requests*, with why. It
  also lists the last requester emails and the link each one carried. It writes nothing: the key a first email would
  make is rolled back, a read by key is not put on the audit trail (it is the check, not a person, and a rolled-back
  insert on SQL Server would still use up a number), and the session is signed with a throwaway secret that never
  leaves the process. Keys are printed cut to four characters, so the output can be pasted into a handoff.
  `who-sees` now asks the portal's own rule too (the own-domain match), so the two cannot disagree.
- **Mending a link that does not open.** Every email sent before 075 carries a link with no key.
  - On the desk, **Copy the requester's link** under the ticket's Contact gives a technician the link the emails now
    carry, to paste into a reply. It is for whoever works the ticket's board, makes the key if the ticket has none
    yet, and is audited (`PORTAL_LINK_COPIED`).
  - On the portal, the *No such request* page offers **Send a fresh link to the address this request came from**. It
    goes only to the requester the ticket already has, never to the person asking; at most one an hour per request;
    not while another requester email is waiting to go (that one carries the link); only on a board that emails its
    requesters. The page answers the same whether the request exists, whose it is and whether the email went, so
    asking teaches nothing. Each ask is audited (`PORTAL_LINK_REQUEST`, with what happened), and the ticket's
    activity says a fresh link was queued and who asked.

What the check does not prove (INFERRED): the path from a ward PC to the portal's address (DNS, the proxy, TLS). A
browser on the hospital network proves that; 401 from the address proves the desk answers.

Schema 076 adds `notification.portal_link`, NULL for every email sent before it. Handoff:
`HANDOFF-cloud-sql01-WS36-20261008-email-link-076.md`.

## Chat, round six: one chat at a time, "is typing", who is on (8 Oct 2026, code only)

Dada, 8 Oct 2026: *"a user can create a 100 chats at the same time thats not good"* and *"add a ... is typing for
presence and also add to the requests portal and the desk portal presence for the operators"*. Each part was confirmed
before it was built.

- **One open chat a person.** Starting a chat while one is waiting or being answered takes the ward back to the one
  they have (*You already have a chat open with the desk, so you are back in it*). Every address the portal knows
  them by counts as the same person. The check sits inside the statement that makes the chat, so a burst of presses
  makes one. On SQLite that holds even under load; on SQL Server it narrows the gap to one statement (INFERRED). The
  Start button sends once. Chats a person already had open from before are left for the desk to end, as Dada chose.
- **The ward's Chat page with a chat open** shows *You have a chat open* with **Continue the chat** in place of the
  form, the *Paalala* still beside it.
- **"The chat stays."** On the ward's open chat, and on that card: *Your chat stays here. You can leave this page and
  come back any time from Chat; the desk's replies will be waiting.* — *Hindi po mawawala ang chat. Balikan lang dito
  kung may kailangan pa kayo.*
- **"… is typing".** Both ways: the ward reads *Lea Cruz is typing…* while the operator types, and the operator
  reads the ward's name the same way. A page sends one small ping every few seconds while words go in. The line goes
  six seconds after the last key, or as soon as the message is sent.
- **Who is on.** An operator is *Online* while a desk page of theirs is open (every desk page, and the banner's poll,
  counts), *Away* after five minutes without one, and *Offline* after half an hour. They can set **Busy** or **Away** by
  hand, and **Automatic** puts it back. The In/Out board's *Out* or *On leave* shows instead of any of it.
  - **On the portal**, above the Chat form and on the ward's open chat: *2 helpdesk staff online now: Lea, Jun*, with
    a busy one marked *(busy)*. With nobody on: *Nobody from the helpdesk is online right now. Your chat waits until
    someone is in.* It updates with the chat's own poll.
  - **On the desk**, at the top of the Live chats quick view: each operator with a dot and the word, and your own
    Automatic / Busy / Away. The same card sits on the Chat page, so it can be set when no chat is live.

Typing, last seen and a hand-set Busy/Away are kept in PSA-Desk's memory (`psaspine/live.py`), not in the database.
They change every few seconds, mean nothing after a restart, and a table would put a write on every poll. A restart
clears them: operators read offline until their next page loads, and Busy/Away goes back to Automatic. INFERRED from
the code: PSA-Desk is one process, so every page reads the same state. The operator list (names, the In/Out board) is
read at most every 30 seconds; the states themselves are always current.

## Chat, round five: ending a chat, and "how did I do?" (7 Oct 2026, schema 074)

Dada, 7 Oct 2026: *"option to close or end the chat and survey or how i did at the end"*. Confirmed before building:
an end window with a rating tick, a rating per operator, and End from the banner's quick view.

- **The end window.** On the desk, *End the chat* opens a small window. It has a closing message (optional; it is said
  as the operator's last line, e.g. *Salamat po! Message us anytime.*) and **Ask ‹name› how I did**, ticked by default.
  Untick it and the chat ends with no rating card for the ward. The chat page then reads *ended without a rating*.
  The ward's own *End the chat* always asks. A bare post from a page opened before this change also asks.
- **"How did Lea Cruz do?"** The ward's card names the operator who had the chat when it ended, with *Paki-rate po
  ang tulong na natanggap ninyo.* above the stars. A chat nobody picked up asks *How did we do?*. The card appears by
  itself when the chat ends, unless no rating was asked, and a rating that was not asked for is refused.
- **Per operator.** Each rating counts to the operator who had the chat (`chat_session.picked_by`, fixed once it
  ends). A chat nobody had counts to the desk's average only.
  - **Reports:** under the *Chat rating* tile, a table of operators with their average and the number of chats rated
    in the period.
  - **Setup › Members:** each person's page says *Rated 4.6 / 5 by the wards over 12 chats* beside the Chat operator
    tick.
- **End from the quick view.** In *Live chats*, a chat that is yours has **End** beside it. It opens the chat with
  the end window already up (`/chat/<id>?end=1`), so you see the conversation as you close it.

Schema 074 adds one column, `chat_session.ask_rating`. It is added NULL by the port and read as asked, so every chat
that ended before it reads as it did. Handoff: `HANDOFF-cloud-sql01-WS36-20261007-chat-074.md`.

## Chat, round four: a louder ring, chat operators, the operator's time (7 Oct 2026, schema 073)

Dada, 7 Oct 2026: *"change the chat beep to a more audible one ... if the chat is converted into a ticket can it be
that the operators time be recorded ... a chat operator member access atm make sure only PMO Helpdesk members can use
the chat"*. Confirmed before building: a louder phone-style ring, again every 30 seconds while a chat waits; the time
entry pre-filled for the operator to confirm; a *Chat operator* tick, and only PMO Helpdesk takes chats.

- **The ring.** The soft two-note chime is replaced by a desk phone's ring: two tones trilled fast, in two bursts,
  played twice, through a compressor so it is loud without clipping. It is still made in the page, with no sound file.
  - A new waiting chat rings at once, and it rings again about every 30 seconds while any chat still waits.
  - Only one of the person's open tabs rings. The tabs agree through the browser's storage.
  - The banner is polled in a background tab too, because the ring matters most when the desk is not the page in front.
  - 🔔 mutes it. ✕ hides the banner and stops the ring until a new chat arrives.
- **Chat operators.** Two settings decide who answers chats:
  - a board takes chats (*Setup › Boards*, "Takes chats from the portal");
  - a member is a *Chat operator* (*Setup › Members*, set by a sysadmin and audited on the member's history).

  The tick is refused to anyone who does not work (WORK or ADMIN) a board that takes chats. Only ticked members see
  *Chat* in the menu and the banner, and only they can read, pick up, answer or make a ticket from chats on their
  chat boards. Anyone else gets 403 on `/chat` and 404 on a chat. The portal offers chat only with the boards that take
  chats, whatever the ward's department. With none, it says chat is not available.
- **The operator's time.** *Make a ticket* and *Add to a ticket* now land on the ticket with its time entry window
  open. A clock has been run for the operator, stopped, but not booked:
  - **Start** is when they picked the chat up, or their first line in it if someone else picked it up.
  - **End** is now.
  - The notes read *Chat with Jun Reyes · chat 3*.

  They check it and **Save**, which books it like any other entry, to the quarter hour, on their timesheet. Or they
  correct it first, or **Cancel** it. If they already had a clock on that ticket, the window opens on that one.

- **The rest of the chat goes on the ticket.** Dada: *"also the chat is added on the ticket if ever right?"* It
  was, up to the moment of *Make a ticket* (the transcript is the description) or *Add to a ticket* (a Discussion note).
  The chat stays open after that, so what was said next lived only on the chat. Confirmed: when a chat that has a
  ticket ends, everything after that moment goes on the ticket as one Discussion note, *The rest of the chat with
  Jun Reyes · chat 3, 09:31–09:44*. The ward may read it, and no email is sent. The files sent in that part are copied
  with their review. Nothing is added when nothing more was said.

Schema 073 adds two columns, `member.chat_operator` and `board.takes_chats`, both read as 0 until set. The SQL01
handoff (`HANDOFF-cloud-sql01-WS36-20261007-chat-073.md`) sets PMO Helpdesk and ticks its working members in the same
transaction, so chat does not go dark at the restart.

## Chat, round three: chats by name, a quick view, a bigger banner, a Taglish reminder (7 Oct 2026, code only)

Dada, 7 Oct 2026: *"make the banner bigger ... instead of naming it as chat1 so on and so forth can we do the name
of the user and number so we know how many this person end user has done ... a quick view of the live chats ...
a reminder what to add to the chats so the user will follow it ... as taglish"*. Confirmed before building: name
and their Nth chat, a drop-down panel, about twice the size, a card beside the start-a-chat form.

- **Chats go by their person.** The desk no longer shows *Chat 4*. A chat is *Jun Reyes · chat 3*: Jun's third chat.
  The name comes from the member record or the AD contact, falling back to the sign-in. Hover to see *3 chats from
  Jun so far*. This applies on the banner, the quick view, the queue's first column, the chat page's heading and title
  (*their chat 3 of 3*), and the transcript a ticket carries. The chat's number stays in its address.
- **The quick view.** *Live chats (N) ▾* on the banner opens a panel over the page. It lists the waiting chats first,
  each with how long it has waited and **Pick up** (for those who may work the board), then the chats in progress
  and who has them. Each row shows its last line from the ward or the desk. Escape or a click away closes it. On a
  restricted board the last line is left out, because the chat's own page, where reads are audited, shows it.
- **The banner.** It is about twice the size (56 px, 18 px type, a bigger bell) and stays up while any chat is live.
  With chats waiting it reads *New chat* and runs those; with none waiting it reads *Live chats* and runs the ones
  being answered. Only a new waiting chat chimes. ✕ hides it until a chat it has not shown before.
- **Paalala.** Beside *Start a chat* on the portal, a card in Taglish lists what to put in the message: saan kayo,
  anong gamit (PC name o asset tag), ano ang nangyari at ang eksaktong error, kailan pa, ilan ang apektado, paano
  kayo makokontak, and a picture or screenshot. It ends with *Huwag po ilagay ang pangalan o anumang detalye ng
  pasyente*. The boxes carry Taglish hints too.

No schema change: the count is read from `chat_session`. SQL01 pulls and restarts; there is no step to apply.

## Only a project's members see it (7 Oct 2026, code only)

Dada, 7 Oct 2026: *"make sure that they will only have access to projects they are a member of"*. Confirmed before
building: the manager, the team and administrators; a non-member opens a project ticket only when it is assigned
to them. This is the reference PSA's project role set to "My" (MEASURED, its Role setup table).

- `common.may_see_project`: a project is seen by its manager, its Team, a system administrator or the Projects
  module at Admin. Anyone else gets *No such project* on Projects, the project page and every tab, its live
  refresh, the ticket's Project picker and the project forms. A template is planning, readable by anyone who may use
  the module.
- `common.project_ticket_ok`, checked once in the router for every `/ticket/<id>/...` page and form, so no handler
  can forget it: a ticket on a project board, on a project, opens for the project's members and for its own owner
  and resources; anyone else gets 404, as a restricted board answers. Search leaves such tickets out. Service
  tickets are untouched.
- Whoever creates or copies a project is put on its team, so it never disappears from the person who made it.

**The survey, live.** The satisfaction survey (032) is asked on the portal once a ticket closes, and the closing
email points there. Going live is a data step on the live desk (every service board's `survey_enabled` to 1), in
`docs/handoffs/HANDOFF-cloud-sql01-WS36-20261007-project-access-survey.md`.

## The ticket's tabs, and a Configurations menu (7 Oct 2026, code only)

Dada, 7 Oct 2026: *"configurations are not present still and there should be tabs on each ticket similar to
connectwise"*, *"there should also be a configurations menu"*, *"make sure everything is built as per
connectwise"*. Confirmed with Dada before building: every tab except billing, the menu as drafted, and the
Configurations tab in the reference PSA's layout.

**Ticket tabs.** The reference PSA's Service Ticket Tabs (MEASURED, docs.connectwise.com
`ConnectWise_Documentation/060/010/010`): Ticket, Tasks, Configurations, Products, Activity, Time, Expenses,
Schedule, Attachments, Open Tickets, Finance, Audit Trail, Survey, RMA, Conversions. Here `/ticket/<id>` is the
Ticket tab, unchanged, and each other tab is its own page at `/ticket/<id>/<tab>`:

| Tab | What it shows |
|---|---|
| Tasks | The ticket's tasks, add and tick off |
| Configurations | The attached configurations in full, and the company's other machines greyed (the contact's first), each with Attach or Detach; **New configuration** |
| Activity | Every note and email, newest first. The reference PSA's Activity tab holds CRM activities, which this desk does not keep; the notes are the nearest thing (INFERRED) |
| Time | Every time entry; a new one opens from the Ticket tab's clock |
| Schedule | The visits booked, and booking one |
| Attachments | The files, through the patient-details review |
| Open tickets | The company's other open tickets (the contact's first), on boards the viewer may see |
| Finance | The BizBox records linked to the ticket |
| Audit trail | Every system change and audit record naming the ticket, newest first |
| Survey | The requester's answer, or that it is awaited |

Products, Expenses, RMA and Conversions are billing and sales, left out on Dada's word. A form on a tab comes back
to that tab: `ticket._load` takes the form's `back` afresh on every request, which also ends a stale return address
that could carry from one request to the next.

**Configurations menu.** Configurations is its own module across the bar, no longer inside Companies:
Configurations, New configuration, Maintenance record (CSV), and for a system administrator Configuration types
and Integrations.

## One Save, always reachable (3 Oct 2026)

The ticket's own fields were already one form with one **Save changes** — but it
sits at the foot of a long card, out of sight exactly while the dropdowns at the
top are being used. So the moment anything in that form changes, a bar rises and
stays: *"3 changes not saved · Save changes · Discard"*. It submits that same
form and adds no second road to saving; Discard reloads, which is the honest
undo. The count is per control and it knows what a `<select>`'s own mark is —
comparing a select to `defaultValue` (which it does not have) counted every
select on the page and the bar read *9 changes* for one edit, MEASURED in
Chromium before it was fixed.

The page also uses the screen it is given now: `main` was capped at 1320px,
which left a third of a ward PC empty beside a ticket that wanted the room.

## What a browser says, which the suite cannot (3 Oct 2026)

Dada, 3 Oct 2026: *"there is an issue with scheduling"*, *"picking using drop
downs have issues when being clicked"*. The suite proves the HTML a view
returns; it cannot prove a person can click the thing. So `tests/browsercheck.py`
starts a desk on a throwaway database, signs in with a real Chromium, and
clicks what a technician clicks, reporting every console error on the way. It
is not part of `python -m unittest` (CI has no chromium); run it by hand:

    pip install playwright && python tests/browsercheck.py

It found both faults on its first run, and neither was in the dropdowns:

- **Booking a visit was impossible.** `To` is `required` and the page shipped it
  **empty**, so the browser blocked the submit and the button looked dead. It is
  now prefilled an hour after `From`, and a script keeps it following `From`
  whenever that moves (never shortening an end someone has dragged out).
- **Booking then answered HTTP 500.** `CHECK constraint failed: stopped_at IS
  NULL OR stopped_at >= started_at`. 007 states that rule and `change_status`
  never honoured it: a status change stamped earlier than the clock's own start
  took the desk down in front of whoever picked it. The two stamps come from
  different clocks in the ordinary way — intake takes a ticket's time from the
  sender's `Date` header, and a mail server running fast is enough. A clock now
  never stops before it started, nor resumes before it paused; the honest record
  is a clock that ran for no time, which is what a stop at its own start says.

**The dropdowns themselves measured clean**: Type fills Subtype, narrows Item
211 → 73, Subtype narrows 73 → 10, the pick survives Save and comes back showing
its Type, and there were no console errors anywhere on the page.

**One Save, or many?** MEASURED: the ticket page carries 18 submit buttons —
Add, Ask, Assign me, Attach, Link, Merge, Page the on-call, Save, Save changes,
Save note, Schedule the visit. That is close to what the reference PSA does: one
Save for the ticket's own fields (status, owner, company, contact, Cc, Ticket
type, the Type → Subtype → Item cascade, impact, urgency, priority — all in one
form behind **Save changes**), and a separate action for each thing that is its
own record: a note, a time entry, a visit, a link, a merge. The rest are verbs,
not saves.

## The note box is a composer, and the catalogue is three selects (2 Oct 2026)

SQL01's two specs to WS36, 2 Oct 2026, both on the ticket page.

**The composer.** The toolbar and the box are one frame now, the way a Teams
composer is: the border and the focus ring belong to the whole thing, the
buttons sit above it in three groups (marks, lists and blocks, links), and the
box grows as it is written in, to 60% of the window, then scrolls. Rich and
Plain are still the same note written either way, and the textarea is still what
is submitted and still what a browser with no script types into.

**Type, then Subtype, then Item.** The one grouped dropdown is three dependent
selects. Picking a Type shows its Subtypes; picking a Subtype shows its Items;
what is submitted is the same single `catalogue_item_id` it always was, so
nothing behind the page changed. The ITIL record-kind field above the cascade
(Incident, Request, Problem, Event) is labelled **Ticket type**, not "Type", so
it is not confused with the cascade's Type (SQL01's #3, 2 Oct 2026).

The third select is the answer and the only one with a name. It holds every live
pair, each option carrying its Type, Subtype and Item on its own attributes, and
the two narrowing selects are `hidden` until the script has filled them from
those attributes. So the script can never offer a pair the catalogue does not
hold, and a browser that runs no script sees exactly the picker it saw before:
one select, grouped by Type, labelled in full.

**They are not empty.** `apply_template` loads the seed's 20 Areas, 56 Subtypes
and 7 Items, and `setup-pmc` adds the hospital's own on top. MEASURED on a fresh
help desk: **16 Types, 53 Subtypes, 210 pairs** — BizBox HIS, Printer, Wi-Fi,
"Not working", "Password reset or unlock" and the rest. A test holds it there,
because a picker that came up empty would be a desk nobody can classify a ticket
on. On a desk already set up, `psaspine setup-pmc <db> --actor <you>` previews
and answers *nothing to add: the pack is already there*.

To ask the **live** desk rather than trust a seed ran, `psaspine catalogue-health
<db>` (host: `Invoke-PsaSpine.ps1 -CatalogueHealth`) reads the tree and the pairs
each board's picker would offer, and names any board below `setup.THIN` (20
pairs) so a desk that cannot classify a ticket is caught before a technician
meets it. It writes nothing.

## The words in a note can be selected and copied (2 Oct 2026)

Dada, 2 Oct 2026, with a ticket open: *"make sure the text here can be copy
and pasted ... atm copy and paste doesnt work"*. MEASURED in a browser:
selecting across a note returned nothing at all.

The cause was ours and it was one line. A pod card carried `draggable=true`
so it could be dragged into another column, and Chrome's own stylesheet
gives every `[draggable=true]` element `user-select: none`, which its
contents inherit. Dragging the card cost the reader every word in it.

The card is now draggable only while the pointer is held on its heading,
which is the handle it always looked like. At rest it is not draggable, so
its words select and copy as any other text on the page. Dragging a card
between columns is unchanged. Each note also has a **Copy** button in its
header, which puts the note's text on the clipboard as written: useful for
pasting a ward's words into a reply, and the way to get them on a touch
screen. It uses the clipboard API with the older command as a fallback.

Not done, because it is a decision rather than a bug: editing a note's text
after it is saved. A note is the record of what someone said and when, the
requester may have read it already, and the audit trail has no shape for a
changed one yet.

## A mail with no subject is a ticket too (2 Oct 2026)

Dada, 2 Oct 2026, with the support mailbox open: *"if there is no subject it
doesnt go"*. MEASURED: a ward writes the whole request in the body and leaves
the subject empty, and intake refused it, because opening a ticket needed a
board, a sender **and a subject**. Every one of those was recorded
UNCLASSIFIED and nobody saw it.

The ticket's name now comes from the subject when there is one, else the
sender's own first line, shortened to one line, else the plain fact that the
mail carried a file ("Email with an attachment: photo.jpg"). It never invents
words. Only a mail with no subject, no words and no file is set aside, and
the reason now says which of the three it was. The PHI scan runs on that
summary exactly as on a subject, because a first line can name a patient just
as easily.

Two other things follow from it. The weaker duplicate guard matches a sender
and a subject inside a day; on an empty subject it would have filed a ward's
second request as a note on their first, so it never matches an empty
subject. And a reply whose own subject is empty takes its first line rather
than the bare words "Reply to PMC-nnnnnn".

## When inbound mail stops, and a member's mailbox on a second domain (2 Oct 2026)

Dada, 2 Oct 2026: *"add encoder@premieremedicalcenter.net to the calendar
sync"* and *"the emails aren't syncing in again"*.

**A second mail domain.** `calsync.members` only counts a member whose
mailbox is on an allowed domain, and both calendar scripts named one. They
now take a list: `-AllowedDomain pmcne.ph, premieremedicalcenter.net` on
`Grant-PsaCalendars.ps1` and `Sync-PsaCalendars.ps1`, one
`--allowed-domain` passed to the desk for each. A mailbox on no named
domain is still never written to, so the fence is unchanged: naming a
domain is the decision, and it is made once, out loud, on the command.
A person is in the sync only when all three hold: a member record with that
email, WORK or ADMIN on a board, and their domain named.

**A delta link that expired stopped the pickup for ever.** Graph answers
HTTP 410 for a saved delta link it no longer knows, and the pass threw on
every run from then on: mail stopped and nothing started it again. The
pickup now forgets the link on a 410, reads from `-Since` instead, and says
so in its log. Nothing arrives twice, because the import is keyed by the
Message-ID. This was the third different cause of the same symptom, so:

**`scripts\Fix-PsaToday.ps1`** is the one line (Dada: *"is there a line i
can run to run these all"*): it pulls the code, runs the repair below,
asks the desk for its calendar members and grants them, in order, and
ends with what is left for a person to decide. Preview by default. It
never registers a scheduled task, because that asks for the task
account's password, and never grants a members list that is missing the
person it was run for.

**`scripts\Repair-PsaMailPickup.ps1`** reads every place it can be, in one
pass, and says which one it is: the tasks (registered, enabled, last run,
last result), the sign-in certificate (found, and the day it expires, never
the thumbprint), the delta link per mailbox and the tail of its log, the
drop and files folders including anything in `failed\`, **what the desk itself has
taken** (`psaspine mail-health`: when a message last arrived, what came of
the ones since, which addresses a board claims), and one real pass per
mailbox in preview so Graph's own answer is on the record. The desk's side
is what tells the two faults apart: a silent desk with a busy mailbox is
the pickup's, and messages taken but set aside are intake's, which
`mail-why` then names message by message. Preview by
default. With `-Apply` it enables and starts a task that is disabled or
stopped, and with `-ResetDelta` it forgets an expired link, keeping a copy.
It never registers a task, never writes a certificate, never imports mail
and never types a credential; anything else it finds it names, with the one
command that fixes it.

## A desk sysadmin by the member record (062, 1 Oct 2026)

SQL01 part 29, root cause MEASURED: every member action on Setup › Members
needs the cross-board sysadmin flag, and a Windows sign-in never carried it
(it lived only on a break-glass local account and on the Entra claim), so
from the normal sign-in "members cannot be removed" (Dada, 1 Oct). The flag
is now on the member record too (`member.is_sysadmin`, NULL reads as 0) and
is read at every request: a Windows sign-in is a sysadmin exactly when the
record says so, a break-glass account or an Entra claim keeps what its door
said as well. Granting and revoking take effect at the next request, no
sign-out.

- **Setup › Members › the person › Desk sysadmin**: Make sysadmin / Take
  off, by a sysadmin. Never on yourself; the last one cannot be taken off;
  somebody who has left comes back on the desk first. Audited as `MEMBER`.
- **On the host, for the first one:** `psaspine set-sysadmin "<the desk's
  connection>" --member dada.banal --actor sql01` (`--off` takes it back).
  An AD account the desk has not met yet gets a record from its contact.
- Port: one `ALTER TABLE member ADD is_sysadmin INT NULL DEFAULT 0`, guarded
  by `COL_LENGTH`; nothing else changes.

## Members, a calendar, and a board's own address (053, 29 Sep 2026)

Dada, 29 Sep, evening: *"there is no member page as per connectwise"*,
*"there is also no calendar page"*, and *"can we have different intake
emails for the service boards?"* Three things, one schema step.

**Members** (Setup › Members). Until now a member was a string: the sign-in
identifier repeated across board memberships, roles, capacity, the on-call
rota, time entries and break-glass accounts, with a name only when the AD
contact import happened to carry it. Now there is a record (`member`):
name, title, email, phone, mobile, department, location, who they report
to, default board, default work role, who approves their week, notes. The
identifier stays the key everywhere, so 053 changes no existing row. Setup ›
Members lists everyone the desk knows, however it came to know them; the
page per person holds the record, the boards they are on (add, change
access, take off), the security role, the hours a week, the break-glass
account and their history, where before those were four pages and a
command line. **Leaving** (*This person has left*) ends the board
memberships, the future on-call slots, the departments they approve for,
who reports to them, whose time they approve, and the break-glass account,
and lists what it did; tickets, notes and time keep the name. Coming back
gives no membership back: those are given again on purpose. The desk shows
the record's name everywhere the sign-in name used to appear, and the name
in the header opens **My profile** (`/my/profile`): what the desk holds on
you, your own phone numbers, your boards and role, and the calendar feed.

**Calendar** (`/calendar`). The Schedule is the dispatcher's week of everyone;
this is one person's: visits, time off, meetings and on-call shifts, by day,
week or month. Yours by default; a member of a board opens the calendar of
anyone who works it. Visits name tickets, so on a restricted board each
listing is an audited read, as the Schedule's are. **A feed for the phone**:
*Make a feed address* on My profile mints a private `.ics` address
(`/calendar/feed/<token>.ics`, 30 days back, 90 ahead) a phone's calendar app
subscribes to with no sign-in. Only the token's hash is kept, a new one ends
the old, and leaving ends it. The feed names the ticket, the board and the
place, never what a ticket says (§6.1).

**A board's own intake address.** The reference PSA needs an email connector
(a mailbox and a credential) per board. Here a board **claims an address** on
its mail-policy tab (`biomed@pmcne.ph`), and intake routes every message by
its recipients: To and Cc as the sender wrote them, then what the mail
system stamped (Delivered-To, X-Original-To, Envelope-To), so Exchange can
alias `biomed@` onto the one helpdesk mailbox and **one pickup task serves
every board**, or a board can have a mailbox and a pickup of its own with
`--board-id`; both work, and a message copied to two boards' addresses goes
to the first named. An unclaimed address goes to the run's board, else the
unrouted queue, as before. A board's address is the desk's own: mail from it
never opens a ticket. `intake_message.to_address` records which address
decided it, and `import-mail` counts `routed_by_address`. Two addresses
cannot be claimed by two boards.

## Opportunities and quotes (`/sales`, 052, 29 Sep 2026)

Dada IT proposes work before it does it: a ward's endpoint refresh, a
retainer, a workstation for radiology. Until now that lived in email and a
spreadsheet, and the agreement that followed was typed from memory. **Sales**
is the pipeline (what the reference PSA sells separately as Sell, in the
shape this desk needs and no more):

- an **opportunity** (`OPP-0001`) names what is proposed, to which company
  and contact, its owner, an amount, an expected close, and a stage:
  Lead → Qualified → Proposal sent → Won or Lost. Each stage carries a
  default probability (10, 40, 70, 100, 0), which can be typed over. A loss
  says why, so the next one goes better;
- a **quote** (`Q-0001`) hangs under an opportunity with its lines
  (description, quantity, unit price), a tax percentage and a validity date.
  Its subtotal and total are computed from the lines, never typed. A draft
  is edited; a sent one is frozen (or withdrawn back to draft); a sent one is
  accepted, declined or expired, and stays decided. Sending a quote moves a
  lead on to Proposal sent; accepting one makes the opportunity worth the
  quote's total;
- **winning drafts the agreement** (045): its name, its party, the accepted
  quote's total (or the amount, when no quote was accepted) and a note saying
  which opportunity and quote it came from. The desk lands on the agreement
  so its term and what it covers are set there and then. A won or lost
  opportunity is read-only; open a new one.

The Sales page shows the pipeline by stage (count, amount and, for the open
stages, the amount weighted by probability), then the list with a search and
a stage filter. It is gated by the **Finance** level of the security role, as
agreements are: READ to look, WRITE to create, edit, quote and move. Nothing
here writes an invoice or touches BizBox; the audit says `SALES` with what
changed. Tables `opportunity`, `quote`, `quote_line` (`schema/052_sales.sql`).

## HTTPS and the organisation sign-in (26 Sep 2026)

The desk speaks TLS itself when it is given a certificate, so nothing else has
to be installed in front of it on a host that already runs the hospital's
services:

```bash
python3 -m psaspine serve <database> --host <the LAN address> --port 8443 \
    --cert D:\psa\tls\desk.pem --key D:\psa\tls\desk-key.pem
```

Both files are PEM (the portal handoff shows the export from the Windows
certificate store), TLS 1.2 is the floor, and the key file should be readable
by the task account alone. Over HTTPS the session cookie is `Secure`; over the
pilot's plain LAN it cannot be, or the browser would drop it. A certificate
without its key, a missing file, or a pair that does not load is refused in a
sentence before any socket is opened.

**Sign in with your Windows account** is the door for the ~400 staff and the
fulfillers, and it needs no licence and no tenant: the desk hands the username
and password to Windows itself (`LogonUser`, network logon, no privilege
needed) on the domain the host is joined to, keeps nothing, and audits every
outcome as `WINDOWS_LOGIN` or `WINDOWS_LOGIN_REFUSED` with Windows's reason in
words (wrong password, locked out, expired, disabled). One setting switches it
on: `PSA_WINDOWS_DOMAIN`, the domain's short name. The person signed in is the
AD contact the import holds for that account, so the portal's ownership and
the requester's email line up; `DOMAIN\user`, `user@domain` and `user` are the
same person. The door is shown first on the sign-in page; break-glass stays
last, for the rota. The real call runs only on Windows; a test hands the
Config a fake (`windows_logon`). NOT VERIFIED against PMC's domain from here;
the portal handoff's step 6 is that sign-in.

**Sign in with Entra** is the alternative for a tenant that is used (Entra ID
Free covers it, VERIFIED, learn.microsoft.com "Microsoft Entra ID Free"; no
per-user paid licence is needed for the sign-in itself), and the only door for
a staff member who has a cloud identity but no domain account. The desk is
registered in PMC's tenant as a **public client**: no client secret exists
anywhere, and the authorization-code exchange is protected by PKCE. Two
settings switch it on:

| Setting | What |
|---|---|
| `PSA_ENTRA_TENANT` | the tenant id |
| `PSA_ENTRA_CLIENT` | the app registration's client id |
| `PSA_PUBLIC_URL` | optional: the URL staff type, e.g. `https://desk.pmcne.ph`; the redirect URI is built on it and must equal, byte for byte, the one registered on the app. Unset, the request's own scheme and host are used. It is also what tells the desk the world is https when a proxy terminates TLS (next section). |
| `PSA_PORTAL_URL` | optional: the requester portal's own address, e.g. `https://help.pmcne.ph`. A request for that host serves the requester's pages and nothing else (next section); requester emails link to it. |

`/entra/start` sends the browser to Microsoft with a state, a nonce and a code
challenge, remembered in a signed cookie that lives ten minutes and only on
`/entra`; `/entra/callback` trades the code for an ID token (proving it holds
the verifier), verifies the token with the same by-hand RS256 check the API
tokens get against the tenant's published keys (fetched when a key is first
needed, and again when Microsoft rotates them), checks the nonce, writes an
`ENTRA_LOGIN` audit row and opens the ordinary session. A person signed in
this way sees their own requests on `/my`; they see a board only if an
administrator made them a member of it. When the tenant cannot be reached (the
WAN), the sign-in page says so and the break-glass door below it still works,
which is the §6.2 posture. NOT VERIFIED against a real tenant from here; the
portal handoff's last step is that sign-in.

## Behind IIS, and the portal's own address (27 Sep 2026)

On `DND-SQL01` the desk is not reached directly: IIS (URL Rewrite + ARR, which
already front Portal and Payroll there) holds 443 and proxies
`https://desk.pmcne.ph` and `https://help.pmcne.ph` to the desk on
`127.0.0.1:8085` (MEASURED by SQL01, 27 Sep 2026). The desk sees
`Host: 127.0.0.1:8085`, plain http, and whatever the proxy forwards. Three
things follow, and all three are decided from **configuration, never from a
request header a client on the LAN could write**:

- **Origin.** A browser form's `Origin` is the public address, not the Host
  the desk sees, so the same-host rule alone would refuse every sign-in. An
  `Origin` equal to `PSA_PUBLIC_URL`'s or `PSA_PORTAL_URL`'s scheme and host
  is accepted in addition; any other is still refused with a 403.
- **Secure and HSTS.** When either public URL is `https://`, every cookie the
  desk sets is `Secure` and every response carries
  `Strict-Transport-Security: max-age=31536000` (no `includeSubDomains`: the
  desk is one name under `pmcne.ph` and decides nothing for the others). A
  loopback probe of `/login` still answers 200; only a cookie-setting call on
  plain http stops working, which is the point.
- **Which public host.** The proxy says which address it was asked for in
  `X-Forwarded-Host`. The desk believes that header **only from a loopback
  peer** (`127.0.0.1`, `::1`): a LAN client cannot claim to be the portal by
  writing it. With nothing in front, the `Host` header is the public host.

**The portal's address** (`PSA_PORTAL_URL`) serves the requester and nothing
else. On that host `/` goes to `/my`; `/my…`, `/login`, `/logout` and the
Entra pair answer; every other path (the board, Dispatch, Uplift, Setup, the
API, search) is a plain 404 for everyone, signed in or not, decided before
identity is looked at; and sign-in returns to `/my` whatever `next` says. The
requester's shell is drawn for everyone there, technicians included.

**The requester's shell.** Anyone on no board is a requester (a fulfiller who
is not yet on a board is added on Setup by an admin): `/` sends them to `/my`,
the header shows *My requests* alone, and the New ticket button, the command
palette (⌘K), the keyboard sheet and its shortcuts are not drawn, because they
lead to pages that answer 404 or "not a member". The theme toggle and sign out
stay. A board member on `/my` keeps the whole desk.

The desk's own TLS (`--cert/--key`, previous section) is unchanged and is the
road when nothing fronts the desk; the two are not combined on one host.

## The Employee Portal door (28 Sep 2026)

Dada's decision (27 and 28 Sep): the Employee Portal (`portal.pmcne.ph`, the
payroll bridge, Windows sign-in) gets a **My requests** link that opens
`help.pmcne.ph` already signed in, with no second sign-in, because the
employee has signed in to the portal already. `help.pmcne.ph` stays the
separate staff portal with its own Windows door; this is one more way in.

The portal page posts its session token, top-level in a new tab, to
`POST /sso/portal` on the portal host. The desk (`psaspine/web/sso.py`):

1. answers **404** anywhere but the portal host, and while the door is off;
2. applies **its own Origin rule**, stricter than the desk's: exactly one of
   the listed **https** origins. An `http://` origin is refused because the
   token already travelled in the clear. The token never leaves for the
   bridge on a refused origin;
3. asks the bridge **server to server** over the loopback:
   `GET /api/portal/me` with `x-pmc-portal-token`, five-second timeout. Only
   a 200 JSON answer with `impersonated` false and an `ADLogin` shaped like a
   username (`^[a-z0-9._-]{1,20}$`, lower-cased) is a person;
4. applies the **pilot gate**: the employee's `Department` must be one Dada
   has opened. An empty list means nobody passes; the DPO's §6.1 answer gates
   hospital-wide use;
5. signs them in **as the same person the Windows door would**: the
   lower-case sAMAccountName, the AD contact's email if the import holds one,
   `via = portal`, board roles from the database. The cookie is a
   **browser-session cookie** (no `Max-Age`), `HttpOnly; SameSite=Lax; Secure`,
   so closing the browser ends it on a shared ward PC. Then `303` to `/my`
   (or to `next` when it is under `/my`);
6. audits `PORTAL_SSO`, or `PORTAL_SSO_REFUSED` with the reason in words. The
   token is never logged, stored or echoed, and the bridge's answer is not
   kept beyond the request;
7. answers every refusal with a page in the requester's layout, the reason in
   words and *Sign in with your Windows account instead*: the portal session
   has ended (401), an admin preview (403), a record with no Windows account
   or one not shaped like a username (403), a department not yet open (403),
   the bridge not answering (503).

`/logout` clears the cookie with `Secure` when the world is https, so the
portal's *Sign out* can end the desk session too.

Hardened before it reached ward PCs (SQL01's review, 28 Sep): every refusal
is audited and then a **redirect to a GET page** with fixed words
(`/sso/portal?refused=<code>`), so a refused tab reloaded by the next person
on a shared PC cannot re-send a token; a token must look like one (48 hex)
before the bridge is asked; only a bridge 401 or 403 means "session has
ended", anything else is "could not be checked"; the bridge is called with
no proxy and no redirect followed, 64 KB at most; the answer is read
strictly; a Windows account the AD import marks inactive is refused; the
UPN lookup escapes `_` and `%` in both doors; a portal session lasts two
hours. The requester shell is branded **PMC Requests**: a request may be for
any department.

| Setting | What |
|---|---|
| `PSA_EMPLOYEE_PORTAL_ORIGINS` | comma list of the **https** origins the form may come from, e.g. `https://portal.pmcne.ph,https://payroll.pmcne.ph`. Unset: the door is off (404). A non-https entry is dropped, never accepted. |
| `PSA_EMPLOYEE_PORTAL_BRIDGE` | the bridge the desk asks, default `http://127.0.0.1:4100`. |
| `PSA_EMPLOYEE_PORTAL_DEPARTMENTS` | a migration only: comma list of department names, honoured while Setup › Departments has no tick. After the first Save the grid decides and this may go. |

The portal side (the link, the card, *Sign out* also loading `/logout`) is
SQL01's, deployed only after this door passes on the host. NOT VERIFIED
against the real bridge from here: the tests hand the Config a fake
(`bridge_get`), and SQL01's Reply is the proof.

## Departments and boards (28 Sep 2026)

Dada's checklist: **Setup › Departments**, a grid where a system administrator
ticks which departments may **send requests to** which boards. A tick never
makes anyone a board member; it opens *My requests* on the Employee Portal
for that department and offers the board on the portal's raise form. Unticked,
a department's requests land on Unrouted, where Dispatch routes them, as
always.

The list comes from payroll as a one-column CSV (`Department`, exact names,
no people): `psaspine import-departments <db> departments.csv`. A re-run adds
new names, retires names that have gone (their ticks kept) and restores a
name that returns; a department payroll does not have yet is added by hand.
One Save for the grid, audited as one line per department that changed. The
requester's department rides on the session: from payroll for the Employee
Portal door, from the AD contact's `department` attribute for the Windows
door. On `/my`: one ticked board says where the request goes; several ask
"Who is this for?"; the choice is checked on the server.

## Requester intake (Phase C)

Phase C opens the desk to the ~400 staff who raise work, which is what makes the
hospital-wide case evidenceable — and what scales the §6.1 PHI exposure unless
the controls land first. They did:

- **A ticket references a patient record and never carries one.**
  `013_intake.sql` adds `patient_reference`, held only on a restricted board by
  two triggers (insert and update). `psaspine/phi.py` detects identifiers at
  every intake path and flags them in `data_quality` — **naming the shape and
  the field, never the value**, because `detail` is read by reports. The ticket
  still imports: refusing it sends the identifier to the telephone, where
  nothing records it.
- **Every read of a restricted ticket is audited** — `RESTRICTED_READ`, with the
  ticket, the actor and which door they came through. That includes the pages
  that *list* tickets: the board, search, Dispatch (the queue and the day),
  Uplift's ticket tables and a rule test each write one row per restricted
  board with a count. Uplift's ticket tables and an every-board rule's test
  are limited to the boards the reader is a member of; an every-board rule
  never runs on a restricted board at all (its own administrators write its
  rules, on the board), so "Move to board" cannot carry a patient's ticket
  onto an open one.
- **A technician's note is scanned like every other intake path** (SQL01,
  pilot script H3): saved, and flagged by shape, never by value.
- **One ticket sequence (D4).** `PMC-000001`, hospital-wide, never reused; the
  prefix is a row, not a constant (§12). See
  [`docs/WS36-decisions-d4-d5-20260922.md`](../../docs/WS36-decisions-d4-d5-20260922.md).

Three ways in, each idempotent where it can be:

```bash
python3 -m psaspine import-mail spine.db ./drop --channel helpdesk   # RFC 822 files
python3 -m psaspine import-contacts spine.db ad-contacts.csv --company PMC
python3 -m psaspine import-computers spine.db ad-computers.csv --company PMC
python3 -m psaspine create-api-token spine.db --label "orthanc monitoring" --board IT_HELP
```

| Path | Who | The rule that matters |
|---|---|---|
| `/my` (portal, `https://help.pmcne.ph` on the host) | a requester | Ownership, not board membership, is the filter. Reads `customer_description`, never the internal status name. The form never asks for a record number: `phi.py` flags one written beside its label, so the words ask for the ward, the room or the machine instead. |
| `import-mail` | the helpdesk mailboxes | Keyed by Message-ID, so a re-run makes no second ticket; replies thread by In-Reply-To. Kills the MEASURED double-creation at the intake end. |
| `/api/v1/tickets` | monitoring, the archive | A local token (§6.2 — the WAN-down alarm cannot fetch an Entra token), sha256 only, one board, tokens only. Priority computed from impact × urgency, never asserted. A `dedup_key` holds one open ticket per alert. |

API tokens live in `schema/local/` beside the break-glass accounts; since D7 put
the desk on SQL Server the local tables are ported like the rest.

**Email arrives within about 30 seconds.** `scripts/Invoke-PmcMailPickup.ps1`
runs on DND-SQL01. It polls the helpdesk mailbox through Microsoft Graph
(delta query, new messages only), writes each email byte for byte to the drop
folder and runs `import-mail`. It signs in with a certificate in the Windows
store, never a secret, and is scoped by Exchange RBAC for Applications to that
one mailbox. It polls rather than listens, so no inbound port is opened.
Preview unless `-Apply`. Setup: `docs/handoffs/HANDOFF-cloud-sql01-WS36-20260923-mail.md`.
Mail follows the reference PSA's email connector rules (VERIFIED from its archived
setup page):
- **Finding the ticket:** a reply finds its ticket by its thread headers first,
  then by a ticket number anywhere in the subject (`[PMC-000123]`).
- **Replies to closed tickets:** each board decides, on its Setup › Board tab.
  It either reopens the ticket to a chosen status, or opens a new ticket linked
  to the old one once the reply is later than N days after closing.
- **Placing the sender:** exact email, then UPN. Failing those, an email domain
  that belongs to exactly one company, never a public mail domain. After that,
  the catch-all company.
- **Mail that never opens a ticket:** bounces, out-of-office replies and the
  desk's own address (`--own-address`) are recorded, counted and ignored.
  Monitoring and backup alerts still open tickets.
- **Customer updated:** every requester reply sets the flag, a fulfiller's note
  clears it, and the Service Board shows it.

Every ticket records where it came from (`ticket.intake_source`: EMAIL, PHONE,
WALK_UP, PORTAL, API, DESK, IMPORT).

**NOT VERIFIED:** whether a Privacy Impact Assessment is required before
hospital-wide rollout. §6.1 says ask PMC's Data Protection Officer before Phase
C goes live. Building the controls is not the same as being cleared to use them.

## Measured against the real register

35 rows in, 35 work items out. **17 variation · 17 baseline · 1 unknown (WS17).**
11 rows BLOCKED, of which **10 are client dependencies** — WS18 is blocked on the
supplier's own action and correctly gets no notice. 4 compound scope links, 6
data-quality findings.

Two of those numbers contradict the WS36 paper, which said 20 variations and 11
notices. The code is right and the paper carries a correction block.

### The row that gets lost

`WS34.contract_basis` is the literal string **`variation (Amendment 1)`**. An
exact-match filter on `variation` drops it, and that row is an entire covered
entity. `normalise_basis()` exists to make that mistake impossible rather than
something to be remembered, and a test asserts it.

## On SQL Server (D7, 25 Sep 2026)

**The on-premises runbook** is `docs/handoffs/HANDOFF-cloud-sql01-WS36-20260926-runbook.md`:
the order of the sittings, a default for every decision, what to do when a
step does not pass, the kill switch, and the rule that nothing the hospital
already runs on the host may be touched.

The desk runs on the SQL Server instance PMC already has, `DND-SQL01\PMC_SS`, in
a database of its own, **`PMC_PSA`**, schema `psa`. Not inside `PMC_SS`, the
imaging index's database: a separate database has its own backup and restore, its
own 10 GB Express cap, and a restore of one never rolls back the other. Same
instance, same backup regime, same host: what the user asked for, with the two
things that should never share a file kept apart. The decision and its
reasoning are in `docs/WS36-decisions-d7-20260925.md`; the sitting that stands
it up is `docs/handoffs/HANDOFF-cloud-sql01-WS36-20260925-sqlserver.md`.

**One code, two stores.** Nothing above `psaspine/db.py` knows which store it is
on. Every module writes the SQLite dialect the schema is written in and uses
sqlite3's connection surface; `psaspine/mssql.py` opens a pyodbc connection that
translates each statement on the way through and hands rows back in
`sqlite3.Row`'s shape. The translator refuses what it has not decided, with the
statement in the message. What it has decided:

| SQLite | SQL Server | Note |
|---|---|---|
| `INSERT OR IGNORE … VALUES` | the INSERT; what SQLite ignores is swallowed (a unique key 2627/2601, a NOT NULL 515, a CHECK 547), `rowcount` 0; a foreign key is refused on both | `INSERT OR IGNORE … SELECT` is refused: write `WHERE NOT EXISTS`, which both run |
| `INSERT OR REPLACE … VALUES` | an `UPDATE` of the row with that key (unlisted columns back to `DEFAULT`), else the INSERT | SQLite checks foreign keys at statement end, so it can delete-and-reinsert a parent other rows point at; SQL Server checks the delete at once, so the same outcome is written in place. Keys read once from `sys.indexes` |
| `LIMIT n [OFFSET m]` | `OFFSET m ROWS FETCH NEXT n ROWS ONLY`, with `ORDER BY (SELECT NULL)` when the query has no ORDER BY | Valid in a subquery too; a moved `?` moves its parameter |
| `SUM(<predicate>)` | `SUM(CASE WHEN … THEN 1 ELSE 0 END)` | SQL Server has no boolean value to add |
| `substr`, `length`, `ifnull`, `\|\|`, `COLLATE NOCASE`, `CAST(… AS INTEGER/REAL)` | `SUBSTRING`, `LEN`, `ISNULL`, `+`, `COLLATE Latin1_General_CI_AS`, `INT`/`FLOAT` | |
| `lastrowid` | `SCOPE_IDENTITY()` fetched in the INSERT's own batch | |
| `PRAGMA`, `sqlite_master`, `IS ?`, `strftime` and the rest of SQLite's own functions | **refused** | `db.table_exists()` answers the one question the code asked `sqlite_master` |
| `AVG(int)` | — | An integer average on SQL Server; the code averages `CAST(… AS REAL)` where a fraction matters |
| `JOIN … USING (col)` | — | Rewritten as `ON` in the code: T-SQL has no USING |
| `IntegrityError` | the same class: a unique key, CHECK, foreign key or gate trigger (`THROW 5000n`) raises `sqlite3.IntegrityError` from this backend too | No caller has to know which store it is on |

Every request opens its own connection, as on SQLite; on SQL Server that is a
login handshake, so the session settings and the schema check go in one
round trip and the check is remembered per target. Beyond that, connection
pooling is the ODBC driver manager's (`pyodbc.pooling` is on by default; on
Windows the driver manager pools for the process).

Three things a SQL Server desk must be told, because a file told the SQLite one:
`PSA_ATTACHMENT_DIR` (the attachment folder; there is no `<db>.attachments`
beside a connection string), backups are SQL Server's own `BACKUP DATABASE`
(`psaspine backup` refuses with that sentence), and the login's **default schema
must be `psa`** (`connect` refuses otherwise, naming the ALTER USER that fixes
it). `LIKE` patterns escape `[` as well as `%` and `_`, since SQL Server reads
`[` as a character class.

**How it is proven.** The whole suite runs against a real SQL Server:

```bash
PSA_TEST_DB="Driver={ODBC Driver 18 for SQL Server};Server=127.0.0.1,1433;Database=PMC_PSA;UID=…;PWD=…;TrustServerCertificate=yes" \
    python3 tests/test_spine.py
```

Each test empties the database and reseeds it (`db.init(…, reset=True)`, a
test-only path) and the same assertions run unchanged. **MEASURED, 28 Sep 2026,
SQL Server 2022 Express 16.0 in a container: 519 tests, OK, 8 skipped** (the
eight are SQLite's own file settings: WAL, busy timeout, the escrow copy). CI
runs the same job against a service container on every push. NOT VERIFIED on
`DND-SQL01` itself, which no session here can reach; the handoff's step 6 is
that run.

Three things the run taught that no reading of the dialect would have: the
port script's `SET XACT_ABORT ON` outlives the script on the session that ran
it, and with it on a swallowed duplicate key takes the whole transaction down
(the backend turns it off again); a gate trigger's refusal rolls the
transaction back on SQL Server, so a ticket must be committed before anyone is
refused on it (the tests commit their fixture; the desk commits per request);
and a connection left open with a write in it blocks the next schema lock for
ever, where SQLite would have let both proceed (the test reset closes them).

## The SQL Server port

`schema/*.sql` (and `schema/local/`, since D7) is the one schema. The copy that
runs on SQL Server is **generated** from it:

```bash
python3 tools/sqlite_to_tsql.py --write     # regenerate sqlserver/
python3 tools/sqlite_to_tsql.py --check     # drift gate; CI runs this
```

Two copies of a commercial rule drift, and the copy that drifts is the one nobody
reads — which here would be the one on the live server. So there is no
hand-maintained second schema and the build fails if the committed T-SQL is not
what the source produces today.

The translator **refuses rather than guesses**. Every NVARCHAR width and every
DECIMAL precision is a named decision in `tools/tsql-decisions.json`; a column
missing from that file stops the build, as does an unrecognised statement, an
unknown function inside a CHECK, or a width narrower than the CHECK beside it.

| Construct | Port | Why |
|---|---|---|
| `INTEGER PRIMARY KEY` | `INT IDENTITY(1,1)` — unless a CHECK pins the key, when it is a plain `INT` | It is a rowid alias, not an integer column; `ticket_numbering.id = 1` is a chosen value |
| `TEXT` | `NVARCHAR(n)`, `MAX` only for notes and details | The register's free-text cells run to thousands of characters; a name is not a note |
| `REAL` | `DECIMAL` | These numbers reach an invoice |
| dates | `NVARCHAR` **plus** a parsed computed column | `'20260904'` and `'2026-09-09'` both appear, and which shape the source used is itself evidence |
| `(P) = (Q)` in a CHECK | `((P AND Q) OR (NOT P AND NOT Q))` | SQL Server has no boolean value to compare |
| `RAISE(ABORT, …)` | `THROW` in an AFTER trigger that rolls back | SQL Server has no BEFORE trigger. The write is still refused; the blast radius is larger, and the generated file says so |

`sqlserver/PMC_PSA_Spine_SqlServer.sql` previews by default (`@Apply = 0`),
refuses any database but `@Database` (`PMC_PSA`), refuses to run twice over
existing objects unless `@AllowExisting = 1`, verifies its own object counts
inside the transaction before committing, and carries its rollback in the
footer. `psaspine init <connection string>` runs the same file with both
switches on, so on a database that already has the schema it changes nothing.

**VERIFIED on SQL Server 2022 Express (16.0) in a container, 25 Sep 2026**: it
applies, its gate passes, both refusals refuse, and the four triggers fire. The
first run found three things the generator had never been able to learn without
a server, each fixed in the translator: T-SQL nests block comments (the header's
own `schema/*.sql` left the file unterminated), a CHECK cannot compare two
predicates, and an IDENTITY key refuses the one value a CHECK allows.
**NOT VERIFIED on `DND-SQL01`**, which no environment on this account can reach;
the handoff runs it with `@Apply = 0` first and reads the plan.

## Against the reference PSA

[`docs/WS36-connectwise-parity-20260928.md`](../../docs/WS36-connectwise-parity-20260928.md)
is the function-by-function comparison with the reference PSA (superseding the
23 Sep one): what is built the same, what was changed on 28 Sep because a
technician who knows the reference PSA would notice, what stays deliberately
stricter, and what is not built and why.

## Design notes

**Losslessness is the headline invariant.** Every input row produces exactly one
work item. Anything unclassifiable is imported *and* flagged. The CLI exits
non-zero if rows in ≠ rows out.

**Compound scope values become two links each.** The register carries `2->8`,
`3+5`, `1/2`, `4/8`; the separator carries meaning, so it survives as the link
relation rather than being discarded.

**A variation is a state machine, not a flag.** Nine states, including
`PERFORMED_WITHOUT_APPROVAL` — work done on best efforts without waiving the
right to fees. No off-the-shelf PSA can express it, which is why that work
currently disappears.

**A decision note cannot be back-dated.** `CHECK (advisory_at <= decision_at)`.
Advice written after the decision is worth nothing, so the schema refuses it.

**SQLite, deliberately.** No server, no provisioning, no procurement, and one
file that can be escrowed nightly to client-controlled storage -- with
`python3 -m psaspine backup spine.db <dest>`, which uses SQLite's backup API
because the database runs in WAL mode. It is also still
the source of the SQL Server schema rather than a thing that was replaced by it —
see the port above. Nothing here has been run against SQL Server, and that
remains **NOT VERIFIED**; what changed is that the T-SQL is now generated and
drift-checked instead of being a claim about portability.

## What is deliberately not here

Named so the omissions are a decision rather than a gap. Each is Phase 4+ and
none is started:

- **CMDB / configurations** — needed for the per-asset maintenance export a DOH
  inspection would ask for, and for medical devices as configuration items.
- **Service catalogue tables** — the Dada PSA Type/Subtype/Item taxonomy.
- **Contacts, companies, boards** — the desk holds these today.
- **Invoicing** — the spine produces the evidence for an invoice, not the invoice.
- **Effort capture from the desk.** `import-tickets` writes work items and
  tickets, never `time_entry`. Effort is banded by a person — the schema requires
  a performer, an enterer, a charge method and an authority source, and a desk
  export carries none of them reliably. An importer that invented those four
  would be inventing the numerator of an uplift claim.
- **Seeding the SQL Server copy.** The generated script creates structure only.
  No fee amount, no board owner and no signed clinical floor: each is a decision
  with a name attached that nobody has made yet.

The ticket ↔ variation adapter is no longer on this list. `psaspine/tickets.py`
puts tickets in `work_item`, `time_entry` already hangs off a work item, and
`reports.uplift_evidence` produces the claim — see the two triggers in `005`,
which are why a variation-path ticket cannot consume effort or close without a
variation attached.

## The repository fence

The register itself is **not** in this repository. It carries internal network
addresses and at least one filename on the record's inventory denylist, so it is
read at runtime from a path given on the command line. `tests/fixtures/` holds a
**synthetic** register of the same shape — same edge cases, invented content.

Commercial amounts are likewise not seeded. `seed/` carries structure only: the
nine scope-item headings, the entities, the instruments and their execution
status. The fee schedule loads at runtime from a file held outside git.

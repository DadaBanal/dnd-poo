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
python3 tests/test_spine.py          # 489 tests, on SQLite; PSA_TEST_DB=… runs them on SQL Server
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

## The desk, laid out like ConnectWise

What a technician uses every day, built to ConnectWise PSA's shape and
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
  as ConnectWise flags them. The requester's portal shows Discussion and
  Resolution only. A note can carry banded time, with a charge method the
  technician must choose, and can move the status in the same save. The
  right-hand panel edits board, status, owner, company, contact and the two
  questions.
- **New ticket** (`/ticket/new`): for phone calls and walk-ups. It records its
  source.
- **Setup** (`/admin/board/<id>`): Board, Statuses, SLA, and Members & roles
  tabs, as ConnectWise's Service Board setup table. The starter setup
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
  `/contact/<id>`): ConnectWise's Company › Contacts. Contacts come from Active
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
  `psaspine import-computers` loads them by objectGUID. The desk owns a
  configuration's type, contact and retirement; a re-import refreshes only
  what AD knows.
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
requests through one front door. ConnectWise's own "ITIL Example" Types are
**Event, Incident, Problem, Request**, as Types on one board. That is Dada's
workbook column A. (Sources are in `schema/022_record_type.sql`.)

- **Board kind** (`board.kind`): **Service**, **Change** or **Project**, chosen on
  *New board*. It sets the starter statuses. Only a service board gets SLA
  targets; ConnectWise: "SLA timers do not run on project tickets".
- **The board's Types** (Setup › *Types* tab): a service board takes Incident,
  Request, Problem and Event. A ticket reads **Type › Subtype › Item**
  (*Incident › Printer › Fix*). Ticking Change on a service board is Dada's
  other phrasing, and is configuration only. A move to a board that does not
  take the ticket's Type is refused.
- **Requests keep their own SLA.** `sla_target_type` holds targets for one
  Type on a board, so the old Request board's numbers are Request targets on
  IT Help.
- **Change enablement.** Standard changes are pre-authorised. A normal change
  cannot enter Approved, Scheduled, Implementing or Implemented until a
  change authority approves it. An emergency change goes ahead but cannot
  close until someone records an authorisation afterwards. The owner never
  authorises their own change. Each change has a type, risk, window and
  backout plan, and every decision is append-only.
- **Links:** incident *caused by* problem, anything *fixed by* change, or
  *related*. A link closes nothing and moves no clock. That avoids the
  ConnectWise child-ticket SLA trap. It is not handover: one fault stays one
  ticket that moves.
- The commercial path (VARIATION) is derived, never passed in. This closes a
  bypass where a variation item opened as INCIDENT could have time booked
  against it.

### Tasks and templates

- **Tasks:** a ticket has a checklist, as ConnectWise's Tasks tab does.
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
  booked twice at once. Dispatch shows the day by person.
- **Survey:** when a ticket closes (and the board sends requester emails) the
  requester is told and, on the portal, asked once: one to five and a
  sentence, scanned for patient details like every other requester text.

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

- **What:** ConnectWise's parent/child. Five people report the same
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
  settings. Unset means off, as ConnectWise leaves contact emails until a
  board enables them; turn it on once the portal is reachable over https.
- **The link** is deployment config: `outbox-pending --portal-url https://…`
  or `PSA_PORTAL_URL` (`Send-PmcNotifications.ps1 -PortalUrl`). It must be
  https; without one the email says to sign in to the IT portal.

### Workflow rules (Setup › Workflow rules)

This is ConnectWise's shape, from its archived workflow-rules page:
- **Shape:** a rule is scoped to a board, or to every board. It holds
  events. Each event has conditions read left to right, a run mode (once, N
  times every T, or continuously every T) and actions: notify, escalate, set
  status, move board, assign owner, add an internal note, or flag.
- **Escalation levels** are successive events, for example *50% of the
  respond time used → dispatch*, then *100% → service manager*.
- **Switching on:** a rule is created off. Every event must be tested, which
  shows how many open tickets match now, before it can be switched on. Any
  edit switches it off again.

Where this desk differs from ConnectWise:
- **Timing:** rules fire the moment a ticket is created, changes status,
  gets a note, changes owner or moves board. Only time-based events wait for
  `psaspine run-rules`, which the server runs every minute; ConnectWise waits
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

API tokens live in `schema/local/` beside the break-glass accounts and are
never ported to SQL Server.

**Email arrives within about 30 seconds.** `scripts/Invoke-PmcMailPickup.ps1`
runs on DND-SQL01. It polls the helpdesk mailbox through Microsoft Graph
(delta query, new messages only), writes each email byte for byte to the drop
folder and runs `import-mail`. It signs in with a certificate in the Windows
store, never a secret, and is scoped by Exchange RBAC for Applications to that
one mailbox. It polls rather than listens, so no inbound port is opened.
Preview unless `-Apply`. Setup: `docs/handoffs/HANDOFF-cloud-sql01-WS36-20260923-mail.md`.
Mail follows ConnectWise's email connector rules (VERIFIED from its archived
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
test-only path) and the same assertions run unchanged. **MEASURED, 27 Sep 2026,
SQL Server 2022 Express 16.0 in a container: 489 tests, OK, 8 skipped** (the
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
- **Service catalogue tables** — the ConnectWise Type/Subtype/Item taxonomy.
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

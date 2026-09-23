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
python3 tests/test_spine.py          # 389 tests
python3 tests/smoke.py               # end to end: imports, reports, intake, backup, desk
```

Python 3.11+, standard library only. No packages and no network; the Phase B
desk adds an optional server, and it too is standard library (`wsgiref`) — see
below.

`import-tickets` reads an **export file**. There is no API client in this
repository and nowhere to put a key: the TeamsWork keys were exposed in a
screenshot, neither is ever written down, and both should be rotated. A test
asserts the module contains no credential-shaped code.

## The fulfiller desk (Phase B)

The engine computes every SLA number but a person could only reach it from
Python. Phase B is the desk that puts it in front of Dada IT — the phasing gate
is that *Dada IT runs its own work on it before anyone at PMC is asked to*.

```bash
python3 -m psaspine serve spine.db --host 127.0.0.1 --port 8080
```

A standard-library WSGI app (`psaspine/web/`), run for the pilot by
`wsgiref.simple_server`. Zero packages, so the same WSGI callable drops behind a
production server in Phase C with no code change; a test wraps it in
`wsgiref.validate.validator()` to prove PEP 3333 conformance. It is **LAN only,
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
  ticket, the actor and which door they came through.
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
| `/my` (portal) | a requester | Ownership, not board membership, is the filter. Reads `customer_description`, never the internal status name. |
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

## The SQL Server port

`schema/*.sql` is the one schema. The copy that runs on `DND-SQL01\PMC_SS` is
**generated** from it:

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
| `INTEGER PRIMARY KEY` | `INT IDENTITY(1,1)` | It is a rowid alias, not an integer column |
| `TEXT` | `NVARCHAR(n)`, `MAX` only for notes and details | The register's free-text cells run to thousands of characters; a name is not a note |
| `REAL` | `DECIMAL` | These numbers reach an invoice |
| dates | `NVARCHAR` **plus** a parsed computed column | `'20260904'` and `'2026-09-09'` both appear, and which shape the source used is itself evidence |
| `RAISE(ABORT, …)` | `THROW` in an AFTER trigger that rolls back | SQL Server has no BEFORE trigger. The write is still refused; the blast radius is larger, and the generated file says so |

`sqlserver/PMC_PSA_Spine_SqlServer.sql` previews by default (`@Apply = 0`),
refuses to run twice over existing objects, verifies its own object counts inside
the transaction before committing, and carries its rollback in the footer.

**NOT VERIFIED.** It has never been executed. No environment on this account has
a network route to `DND-SQL01`, so it is written to be handed to somebody who
has one. Run it with `@Apply = 0` first and read the plan.

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

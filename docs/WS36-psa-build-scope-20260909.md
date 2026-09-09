# WS36 — Building the PSA: the service board, scoped for PMC

**9 September 2026.** Scope only. No code is written against this until the
decisions in §13 are answered.

Continues `WS36-psa-recommendation-20260909.md` (the catalogue and commercial
design, still current), `WS36-ticketing-handover-20260909.md` (the constraint) and
`WS36-sqlserver-port-20260909.md` (what is built). It **departs** from the
recommendation's headline conclusion, and §1 says exactly how.

---

## 1. The decision being taken, stated accurately

### 1.1 What the record recommended

**[MEASURED]** `WS36-psa-recommendation-20260909.md` says: *"Do not build a ticket
desk and do not buy one this month."* Kitameraki is **USD 88.50 per organisation
per month, unlimited users** [VERIFIED in the record today, teamswork.app], so
replacing it saves nothing on licence cost. The paper names **Jira Service
Management Standard** as the successor when a dated gate fires.

### 1.2 What the same record already found against that

The recommendation does not stand alone. Its own review carries three findings
marked **BLOCKING**, all **[MEASURED]**:

1. **The variation mechanism does not work end to end.** Tickets live in
   Kitameraki, variations and effort live in the spine, and the two meet only in
   a read-only reporting warehouse, after the fact. So no ticket can attach to a
   variation and no effort can be banded against one. The Phase 3 uplift claim
   — **+20% EAC, AUD 2,600/month, AUD 31,200/year** — *can never be evidenced from
   ticket effort*. It can only be asserted, which is the exact failure the paper
   says it is curing.
2. **Kitameraki's capability was never assessed against the design.** Nobody
   tested whether it supports computed priority, per-item P1 floors enforced at
   raise and at close, a clinical-impact floor overridable only by a named role,
   three SLA clocks on two calendars, a pause state that stops the resolve clock,
   per-board SLA ownership, a four-level catalogue whose defaults flow into
   commercial fields, owner and deputy per queue, or the three-path model.
3. **One ticket id across a cross-board handover is already impossible in it.**
   `ITO-` and `PCSD-` are separate key sequences on separate instances. That
   control is the specific thing the paper says prevents another 25-day MRI
   outage.

And the migration gate the paper itself set is **already satisfied**: trigger (d)
fires when more than 25 departmental fulfillers need a new M365 licence, and the
paper's own figure is that **~30 of the 40 do**.

### 1.3 What is actually being decided now

So this is not an overruling of the record on capability — the record's own review
says the capability case is unmade and the gate has fired. **The genuine
departure is choosing to build rather than to buy Jira**, and that is Dada's call
to make. It should be recorded as one.

Three further facts, both **[MEASURED]** in the record, bear on it and are new
weight the recommendation did not carry:

- **A Kitameraki outage was diagnosed as vendor-side, and the support email was
  drafted and never sent.** That matches "it keeps on failing on us". Before any
  migration paper goes to PMC's board, **send that email** — the board may
  reasonably ask why the incumbent was never held to its own SLA first. It costs
  an hour and it is the difference between a considered migration and a whim.
- **Being a Teams app is itself the cost.** ~30 fulfiller identities at ~USD
  6/user/month ≈ **USD 2,160/year**, which is more than the Kitameraki licence.
  Housekeeping, dietary and nursing supervisors do not have M365 licences and
  should not need one to close a ticket about a trolley. A build that does **not**
  use Entra for departmental fulfillers is the only option on the table that
  removes this line rather than moving it. See §8.5 — it is not free either.
- **Retention and export fidelity are NOT VERIFIED.** Whether the vendor returns
  full note threads, internal comments and attachments is unknown, and
  attachments are what an inspector asks for.

### 1.4 What it costs to be wrong

Say it plainly, because a scope that only lists benefits is a sales document.

- The record's build estimate for the **spine alone** was 60–90 hours, INFERRED,
  by the person doing the work. A board engine, a rules engine, an SLA engine, two
  user interfaces and an intake path is a different order of magnitude. §9 phases
  it so the estimate is tested early rather than at the end.
- **The record's own base rate is against us.** BUILT-NOT-RUN is a live status in
  the register. The Power BI collector was fully designed on 3 September and never
  run; the gateway has been two clicks away since 3 September; the Kitameraki
  support email was drafted and never sent. Phase A below exists to hit that base
  rate early, on the smallest thing that can be put in front of a fulfiller.
- The funding line changes. `WS36-psa-recommendation` §4.8 line (b) is *"build the
  spine, one-off change order, AUD 6,500"*. A PSA is not that line, and quoting
  the old number against the new scope is the kind of thing that loses a variation
  argument rather than winning one.

---

## 2. What ConnectWise actually is, structurally

### 2.1 The board is the unit

**[NOT INDEPENDENTLY VERIFIED — page is behind ConnectWise University
authentication; wording below is from the public search summary of
`docs.connectwise.com/ConnectWise_Documentation/060/020/010`, read 9 Sep 2026]**

> A Service Board in PSA is the "bucket" that holds all of your Service Tickets.
> You can create as many Service Boards as you like, and specify the Location and
> Business Unit that the Service Board is for. Separate service boards can be
> created for different problems, which can then be further broken out into
> separate types, sub-types, and items.

And, from the same source: statuses are chosen per board through the Service
Board setup table; the setup table carries an **Auto Assign** tab; workflow rules
live in their own setup table at `System > Setup Tables > Workflow Rules`.

The operative sentence for our design is one line from a third-party integration
guide: **"State, Team and Type are all related to the Board."** A board is not a
label on a ticket. It is the configuration scope for the ticket's whole
vocabulary.

### 2.2 The ticket object, field by field

**[VERIFIED today, http://vc3.github.io/connectwise-rest-api/modules/_api_api_.ticket.html
— a generated mirror of the ConnectWise Manage REST API, not ConnectWise's own
documentation]**

| Group | Fields |
|---|---|
| Identity | `id`, `summary`, `recordType` (`ServiceTicket` \| `ProjectTicket` \| `ProjectIssue`) |
| Board and state | `board`, `status` |
| Classification | `type`, `subType`, `item` |
| Assignment | `team`, `owner`, `resources` |
| Severity axes | `priority`, `severity` (`Low`\|`Medium`\|`High`), `impact` (`Low`\|`Medium`\|`High`) |
| Who and where | `company`, `site`, `contact`, `serviceLocation` |
| Commercial | `sla`, `agreement` |
| Clocks | `dateEntered`, `dateResponded`, `dateResplan`, `dateResolved`, `closedDate` |

Two things fall straight out of that list and both matter.

**First, the three clocks are real and they are ConnectWise's own.**
`dateResponded`, `dateResplan` (resolution plan) and `dateResolved` are three
separate stored timestamps. The three-clock SLA model in
`WS36-psa-recommendation` §5.5 is therefore not an invention we have to defend —
it is the shape the market leader already uses, and we are matching it.

**Second, `priority`, `severity` and `impact` are three independent fields with no
derivation between them.** This corroborates §5.4's claim from a second source.
A fulfiller picks a priority in ConnectWise. Nothing computes it.

**Third, `agreement` is on the ticket.** ConnectWise does link a ticket to a
contract — for rate and coverage. **[INFERRED]** It does not carry a variation
state machine, a notice register, or a contract basis that decides whether the
work is inside a fixed fee. That gap is the whole reason the spine exists, and it
is unchanged.

### 2.3 What ConnectWise does that we must copy

- Boards are cheap and numerous, each with its own statuses, teams and rules.
- A ticket carries its whole context: company, site, contact, location.
- Status is per-board and drives everything else.
- Workflow rules are **data an administrator edits**, not code a developer ships.
- Time entries hang off the ticket, and time is what the business runs on.

### 2.4 What ConnectWise does that we must not copy

**[VERIFIED]** Types, sub-types and items are scoped **per board**. At fourteen
hospital boards that is fourteen maintenance surfaces for one tree. Our catalogue
already rejects this: one shared verb set, one component tree, curated triples.
That decision is already built and seeded (56 components, 7 verbs, 51 items).

---

## 3. What ServiceNow does that ConnectWise does not

**[VERIFIED today,
https://www.servicenow.com/docs/r/washingtondc/application-development/table-administration-and-data-management/task-table-structure.html]**

The `Task` table is *"a base class that provides fields for the core ITSM
applications such as Incident, Problem, and Change Management"*, and *"all
applications that extend the Task table share these fields in common."* Journal
fields *"work together to create a log of changes and comments as tasks are worked
on."*

**This is the single most important idea to take.** One base record with the
common fields; every work type extends it. It is why ServiceNow can add a module
without reshaping the core, and it is precisely what "in the future we could add
procurement and finance" requires.

**We already have it.** `work_item` is our Task table. It already holds register
workstreams *and* desk tickets, `time_entry` already hangs off it, and
`005_ticket.sql` is already an extension table keyed one-to-one on it. The base
class was built in Phase 1 without being named as one.

**[VERIFIED today via servicenow.com community threads — community content, not
product documentation]** ServiceNow's request path is three levels: a Request
(`sc_request`) is a container, a Requested Item (`sc_req_item`, "RITM") is the
individual thing ordered, and Catalog Tasks (`sc_task`) are where the work is
done. It is explicitly not one-to-one-to-one.

**[INFERRED]** For PMC this is over-modelled today and correct later. One nurse
asking for one thing does not need a shopping cart. But "onboard a new ward
clerk" is genuinely one request that fans out to an AD account, an M365 licence, a
BizBox login, a badge and a desk — five fulfilment tasks on four boards. §5.1
keeps the door open by making the fan-out a parent/child relationship on
`work_item`, which already has `parent_id`, rather than a new table now.

---

## 4. What we take, what we leave, what we add

| Capability | ConnectWise | ServiceNow | PMC PSA | Why |
|---|---|---|---|---|
| Board as configuration scope | yes | assignment groups only | **yes** | The user's requirement, and it is the right unit |
| Per-board statuses and workflow | yes | via states + flow | **yes** | A biomedical board does not have an IT board's states |
| Base class for all work types | no | **yes** | **yes** | This is how procurement and finance arrive later without a rewrite |
| Types/subtypes/items | per board | catalogue items | **shared tree, curated triples** | 14 boards must not mean 14 trees |
| Priority | chosen, 3 loose fields | chosen, matrix optional | **computed, never chosen** | The requester answers two questions; the rest is arithmetic |
| Clinical floors | no | no | **yes** | No MSP PSA models a ward oxygen outlet |
| Three SLA clocks | **yes** | yes | yes | Match the market shape |
| Pause state stopping the clock | yes | **yes, as SLA conditions** | yes | Without it, 11 of 35 register rows breach on day one |
| SLA enforced by default | yes | yes | **no — measured, not enforced** | The agreement disclaims any commitment three times |
| Cross-board handover | two linked tickets | two tasks | **one ticket, changing owner** | Two tickets waiting on each other produced a 25-day outage |
| Contract basis on the work | agreement ref only | no | **yes, with a variation state machine** | The half no PSA ships |
| Losslessness as an invariant | no | no | **yes, flags counted** | Already built and tested |
| Rules as editable data | **yes** | yes | yes | PMC must change a rule without a deployment |

---

## 5. The object model

### 5.1 The base class

`work_item` stays the base. Everything that consumes effort is a work item, and
`time_entry.work_item_id` is the only way effort is ever recorded.

```
work_item  (the Task table)
  ├── ticket             built  (005_ticket.sql)
  ├── workstream         built  (the register, source='register')
  ├── change_request     later  — a change board needs approval and a window
  ├── problem            later  — the 25-day MRI outage is one problem, many tickets
  ├── purchase_request   module — procurement
  └── invoice_line_work  module — finance
```

Extending it costs a table and a foreign key. Nothing above it changes. Two
things must be got right **now**, because they are expensive to retrofit:

1. **`work_item_id` stays a string, human-meaningful, and never reused.** Ticket
   numbering is discussed in §5.3.
2. **`parent_id` already exists.** The request fan-out in §3 uses it. Do not add a
   second parent mechanism later.

### 5.2 The board, properly

The current `board` table is seven columns and a note. That is a *label*. A board
in the ConnectWise sense owns its vocabulary, and these are the tables that makes
true:

| Table | Holds | Rule it carries |
|---|---|---|
| `board` (exists) | identity, phase, fulfiller group, owner, deputy, restricted | **no named owner, no live board** — already enforced |
| `board_status` | the status list for this board, ordered | one default status; at least one closed status; a closed status may not also be a default |
| `board_team` | teams within a board | a board has at least one team before it goes live |
| `board_member` | person → team → role (LEAD, MEMBER, DISPATCH, READ_ONLY) | a restricted board's membership is the access control |
| `board_sla` | which SLA target set applies | every target still ships `enforced = 0` |
| `board_intake` | how tickets arrive: mailbox, portal, API, watchdog | the address is data, not code |
| `workflow_rule` | the rules engine (§5.4) | board-scoped or global, never hard-coded |

**Statuses are per board and they are typed, not free text.** Each row carries
flags rather than the engine inferring meaning from a name:

`is_default`, `is_closed`, `stops_resolve_clock`, `customer_visible`,
`requires_note_on_entry`, `escalates_after_minutes`, `sort_order`.

**[INFERRED]** This is where most home-grown desks fail. If "Waiting for parts"
is a string, nothing knows the clock should stop. If it is a row with
`stops_resolve_clock = 1`, the SLA engine needs no special cases and PMC can add
"Waiting for PhilHealth" without a developer.

### 5.3 The ticket

Mostly built. What §5.2 adds is a foreign key from `ticket.state` to
`board_status` instead of the current CHECK constraint — the CHECK was right for a
schema with no board configuration and is wrong once boards own their statuses.

**Numbering.** One sequence across all boards, because one ticket id must survive
a cross-board handover — the control the incumbent structurally cannot offer.
Proposal: `PMC-` + a zero-padded monotonic integer, allocated by the database, with
`external_ref` and a `legacy_ref` carrying the old `ITO-`/`PCSD-` reference so an
inspector can still resolve a citation into the 3,210-message mailbox archive.

**The gate stays.** Both triggers from `005_ticket.sql` survive unchanged, and
the third one — an INSERT-side gate — is on the table in `WS36-sqlserver-port`
§"One thing found on the way".

### 5.4 The rules engine

This is "it has multiple rules in it", and it is the piece most likely to be
under-built.

A rule is a row, not a function:

```
workflow_rule
  rule_id, board_id (NULL = global), name, is_active, sort_order,
  event        ON_CREATE | ON_STATUS_CHANGE | ON_OWNER_CHANGE | ON_SCHEDULE
             | ON_SLA_THRESHOLD | ON_NOTE_ADDED | ON_HANDOVER
  condition    a stored expression over the ticket and its catalogue item
  action       ASSIGN_TEAM | ASSIGN_OWNER | SET_STATUS | NOTIFY | ESCALATE
             | ADD_NOTE | RAISE_CHILD | REQUIRE_APPROVAL | FLAG
  parameters   the action's arguments
```

Four rules that must be expressible on day one, drawn from things that have
already gone wrong **[all MEASURED in the record]**:

- **Unrouted ages.** Triage is one person today, and when she is unavailable the
  path is a personal Teams chat to a CIO in another country. A ticket sitting
  unowned past a threshold pages IT.
- **A P1 on a clinical board notifies the on-call, not a queue.**
- **A handover records `handover_at` and notifies the receiving board's owner** —
  one ticket, changing owner.
- **A duplicate-intake guard.** On 7 Sep 2026 at 07:25:34Z one requester mailed
  two addresses; at 07:26:07Z and 07:26:08Z two tickets opened, with two
  acknowledgements. The rule is: same requester, same subject, inside a window →
  attach to the open ticket and do not create a second.

**Every rule firing writes an `audit_event`.** A rules engine you cannot audit is
a system nobody can explain to an inspector.

**Conditions are the design risk.** A free-text expression evaluated at runtime is
an injection surface and an untestable one. **[INFERRED]** The safe shape is a
small structured condition — field, operator, value, joined by AND/OR — stored as
data and evaluated by code that can only read ticket fields. Not a language.
Decision **D5** in §13.

### 5.5 The SLA engine

Three clocks — respond, resolution plan, resolve — each with its own target,
calendar and attainment percentage, already modelled in `sla_target`. What is
missing is the running clock:

```
ticket_clock
  work_item_id, clock (RESPOND|RESOLUTION_PLAN|RESOLVE|ACKNOWLEDGE|DECISION),
  started_at, paused_total_minutes, stopped_at, target_minutes,
  calendar (CLINICAL_24x7 | MANILA_BUSINESS), breached (computed, never stored)
```

Rules, following ServiceNow's start/pause/stop shape rather than inventing one:

- A clock starts when the ticket enters a status the board marks as starting it.
- A clock **pauses** whenever the ticket sits in a status with
  `stops_resolve_clock = 1`. Elapsed time is computed against the calendar, so
  Manila business hours are honoured without storing business minutes.
- `breached` is derived at read time, never stored. A stored breach flag goes
  stale the moment a target or calendar is corrected.
- **Every target ships `enforced = 0`.** Measured, reported, and not a promise.
- **The auto-responder is replaced.** It currently publishes an uncontracted
  commitment to the whole hospital [MEASURED, ITO-1724]. Its replacement states
  actual hours of cover and that targets are internal measures.

### 5.6 Identity, roles and restricted boards

Four roles, and they are not the same as board membership:

| Role | Can |
|---|---|
| Requester | raise a ticket, see their own, add a note, close their own |
| Fulfiller | see and work tickets on boards they are a member of |
| Board owner | configure their board's statuses, teams, rules, SLA |
| Administrator | boards, catalogue, roles; **cannot** sign a clinical floor or make a board live without an owner |

**A restricted board's membership is a hard filter, not a UI hint.** Every read
path filters by membership at the query, and the test for it is the acceptance
test the record already wrote for the incumbent and never ran: *can a departmental
fulfiller be provably excluded from a PHI-bearing board?* Ours must answer yes,
demonstrably, with a test.

### 5.7 What is already built and does not need rebuilding

The catalogue (§5.1–5.2 of the recommendation, seeded), the commercial spine
(variations, notices, dependencies, reclassification, decision notes), banded
effort, the data-quality discipline, the SQL Server port, the drift gate, and the
uplift evidence report. **83 tests** [MEASURED, `python3 tests/test_spine.py`].

The board engine is built *on* that, not beside it.

---

## 6. What is different because it is a hospital

### 6.1 PHI will arrive in ticket text, and nothing currently stops it

This is the largest new risk in going hospital-wide and it is not in any prior
document as a design requirement.

**[MEASURED, 9 Sep 2026 06:57Z]** A message to `helpdesk@pmcne.ph` from an
external consumer mailbox, titled *"REQUEST TO EDIT CHARGE DATE"*, carried **a
named patient and a PhilHealth case number** in the body — on the same address as
printer faults. **[MEASURED]** Roughly 100 of ~400 staff hold a tenant identity,
and measured intake today includes consumer Gmail and Yahoo mailboxes.

Opening ticketing to 400 clinical staff over that path **scales the RA 10173
exposure rather than containing it**. Four design requirements follow, and they
are requirements, not preferences:

1. **A ticket references a patient record; it does not carry one.** A structured
   `patient_reference` field holding a record number on a restricted board, with
   the summary and description prohibited from carrying identifiers. Enforcement
   is a detection-and-flag at intake, not a promise in a policy.
2. **Restricted boards are enforced at the query.** §5.6.
3. **Retention is designed, not inherited.** The spine plus PMC-controlled escrow
   is the record of system at 10 years; apply the Purview retention policy to
   `helpdesk@` and `support@` regardless of what we build.
4. **Every read of a restricted ticket is audited.** In a hospital, who looked is
   as material as who changed.

**[NOT VERIFIED]** Whether a Privacy Impact Assessment is required before
hospital-wide rollout, and who signs it. That is a question for PMC's Data
Protection Officer, and it should be asked before Phase C, not after.

### 6.2 It has to work when the internet does not

**[INFERRED, and I think this is the strongest technical argument for building.]**
A hospital ticket desk that depends on a WAN link is unavailable exactly when it
is most needed — a network outage is when you most need to raise a network
ticket. A Teams-native SaaS desk cannot meet that. An on-premises primary can.

### 6.3 Wards, shifts and 24×7

Two calendars minimum (clinical 24×7 and Manila business hours) are already
modelled. What is not: **shift handover**. A P1 raised at 02:00 on a ward is
owned by whoever is on, not by a named person who is asleep. The `board_member`
role `DISPATCH` and an on-call schedule are the mechanism; the on-call table is
Phase B, not Phase A.

### 6.4 Clinical floors stay unsigned until they are signed

All four seed PROPOSED. The engine reads them; none binds. Unchanged.

---

## 7. What is different because of the agreement

Every ticket carries `contract_basis`, defaulted from the catalogue, and the
variation-path gate is in the schema rather than the application. That is already
built and tested. Two consequences for the board engine:

- **A board cannot override a contract basis.** Basis comes from the catalogue
  item, and a change is a `reclassification` event with a reason — never an edit.
- **The uplift evidence report is a first-class screen, not an export.** It is the
  thing the whole system exists to produce.

---

## 8. Architecture

### 8.1 Where it runs — and where it must not

**[MEASURED]** `DND-HOST1` is a single Hyper-V host that also runs **the only
domain controller**, has **one 10GbE uplink** and **no host-level backup**.
**[MEASURED]** `DND-SQL01` — a guest on that host — runs the live BizBox HIS with
a **173-finding audit open, `sa` enabled, SSRS running as Enterprise Admin, and
the Domain firewall profile disabled**.

**[INFERRED]** Putting a hospital-wide ticketing system, its web tier and 400
users' traffic onto that host is not a defensible design. It is one power supply
away from taking out the domain controller, the HIS and the system you would use
to report the outage.

Three options, and the scope needs a ruling:

| | Where | For | Against |
|---|---|---|---|
| **A** | New VM on new hardware at PMC, own backup | Works when the WAN is down. No per-identity SaaS cost. PMC owns it. | Capital cost. Somebody patches it. |
| **B** | Azure App Service + Azure SQL, PMC's subscription | No hardware. PITR and LTR come free. Already the spine's stated lift path. | Dies with the WAN. Ongoing cost, in PHP, forever. |
| **C** | On-prem primary, nightly push to Azure for reporting and DR | Both properties. Matches the existing warehouse pattern. | Two places to operate. |

**Recommendation: C**, with the primary explicitly *not* on `DND-HOST1`. Decision
**D1**.

### 8.2 Intake channels PMC already owns

**[MEASURED]** Two were named in the brief and never investigated: the **RDS farm
publishing RemoteApps on `PMC-HIS8-Collection`**, and **`queue.pmcne.ph`**. Both
already reach clinical staff who have no M365 licence. **[MEASURED]**
`helpdesk@pmcne.ph` holds **3,210 messages back to 16 Oct 2024** and is the real
archive.

So intake is: a **web form** on a hospital-reachable name, **email** into
`helpdesk@` (with the duplicate guard from §5.4 and `support@` aliased onto it,
one hour of work that kills the measured double-creation), a **machine/API** path
for the modality watchdog, and a **phone-logged-by-a-fulfiller** path, because in
a hospital that will happen whatever we build.

### 8.3 The stack, and the standard-library rule

`platform/psa-spine` is Python 3.11, **standard library only, no packages, no
network**. That rule was right for Phase 1: it made the spine escrowable and
dependency-free. It cannot survive a web application for 400 users, and pretending
otherwise produces a hand-rolled HTTP server nobody should run in a hospital.

**Proposal:** the rule changes shape rather than being dropped.

- **The engine, schema, importers, reports and rules evaluation stay
  standard-library only, and stay testable with `python3 tests/test_spine.py`.**
  That is the part that must be escrowable and auditable, and it is the part with
  the commercial rules in it.
- **The web tier may take a small, pinned, vendored dependency set**, reviewed and
  committed, with a named licence for each.

Decision **D2**, and it needs Dada's explicit sign-off because it edits a rule in
`CLAUDE.md`'s spirit rather than a preference.

### 8.4 Identity

**[MEASURED]** ~30 of 40 fulfillers would need a new M365 licence for a
Teams-native desk, ~USD 2,160/year. A build can avoid that — but the record is
right that *"a seat is an Entra group membership" is true for the licence and
false for the seat*: local accounts mean password resets, MFA and offboarding
handled by a 2–3 person team, in a hospital, under RA 10173.

Honest options: Entra SSO for everyone (costs the licences, best control); local
accounts for departmental fulfillers only, Entra for IT (saves the money, adds the
burden); or Entra for fulfillers and an unauthenticated-but-attributed intake form
for requesters. Decision **D3**. **I do not think this should be decided on cost.**

---

## 9. How it looks

Four surfaces. Everything else is a report.

**1. The board view** — the fulfiller's home. A filterable list of the tickets on
boards they belong to: id, priority, age, SLA state, summary, company/site, owner,
status. Sorted by priority then age. Colour carries SLA state, never priority
alone. Bulk actions on selection. This is the screen a fulfiller lives in and it
must be fast on a ward PC.

**2. The ticket view** — one screen, no tabs for the things used every time.
Header carries id, board, status, priority *and why it is that priority*. The
note stream is the body. The right rail carries the commercial block: contract
basis, scope item, variation, and banded effort. Handover is a button, not a new
ticket.

**3. The requester portal** — search first, tree second, **at most three clicks
from start to a fileable ticket**. It asks two questions — *who is affected* and
*is a patient waiting* — and never shows a priority dropdown. It shows the
requester their own tickets and nothing else.

**4. The dispatch/triage view** — the Unrouted queue, ageing visibly, with the
rule that pages IT when it ages. Today triage is one person and the fallback is a
personal Teams chat to another country.

**[INFERRED]** The two screens that decide whether this is used are the board view
and the requester portal. Everything else can be ugly for a year.

---

## 10. Phasing

Each phase is independently useful, and each one ends with something a person
uses. This is deliberate: the record's base rate is designs that are never run.

| Phase | Ships | Useful even if the next phase never happens |
|---|---|---|
| **A. Board engine** | `board_status`, `board_team`, `board_member`, `workflow_rule`, `ticket_clock`, the rules evaluator, the SLA evaluator. Headless, CLI, tests, on SQLite **and** SQL Server via the existing translator. | The uplift evidence report gets real SLA and routing data. The importer can replay the mailbox archive. |
| **B. Fulfiller surfaces** | Board view, ticket view, dispatch view. Fulfiller auth. | Dada IT runs its own work on it before anyone at PMC is asked to. |
| **C. Requester intake** | Portal, email intake with the duplicate guard, machine API. PHI controls of §6.1. | The hospital-wide case becomes evidenceable. |
| **D. Modules** | CMDB/configurations, contacts and companies, procurement, invoicing. | Each is a table extending `work_item`, per §5.1. |

### 10.1 The module map, checked against ConnectWise

**[VERIFIED 9 Sep 2026, `university.connectwise.com/University/PageView.aspx?short_name=partner-kit-library`
— read from an authenticated session and relayed by Dada, not read directly]**

ConnectWise PSA's own module set, from its Partner Kit Library index:

| Area | Modules it ships |
|---|---|
| Service delivery | Help Desk, PSA End User Portal, Chat, StreamlineIT |
| Project | Project Management |
| Operations | **Procurement**, Onboarding, Offboarding, Human Resources, Report Writer, QBR |
| Finance and billing | Collections, **UserCentric** (per-user billing), **Unified Billing Intake** |
| Adjacent products | CPQ (quoting, multi-level approvals), Automate (RMM), SIEM |

Three things follow.

**Procurement and finance are first-class PSA modules, not afterthoughts.** The
market leader ships purchasing, receiving and inventory as a module of the same
product. That is the shape Dada asked for, and §5.1's base class is what makes it
reachable — a `purchase_request` extending `work_item` inherits assignment,
status, notes, audit and effort for the cost of one table.

**StreamlineIT is worth reading properly before Phase B.** ConnectWise describes
it as becoming *"an extension of your clients' internal support"* and
*"co-manage alongside a client"*. **[INFERRED]** That is precisely the PMC shape:
of the ~40 fulfillers, most are PMC's own departmental staff — biomedical,
facilities, housekeeping, dietary, nursing — not Dada IT's. A co-management model
is not the same as an MSP servicing a customer, and it changes who owns a board,
who sees a restricted ticket, and who the SLA is between. It bears directly on
decisions **D3** (identity) and §5.6 (roles).

**QBR maps to an obligation we already have.** The agreement's six-monthly review
is the same object. The uplift evidence report of §7 is what it should be built
on.

**Not to copy, at least not now:** Equipment Rental, Campaign, Chat, CPQ. Each is
a real module and none of them is PMC's problem this year.

**Phase A first, and measured against the estimate.** If Phase A is not running
and tested by its own date, the scope reduces rather than the date moving — the
same discipline the record applied to the spine.

**Dual-run, do not cut over.** Kitameraki keeps running through Phase B. It is
USD 88.50/month to not bet a hospital on a first release.

---

## 11. How we will know it is better

Not opinion. Each of these is a test that passes or fails, and each one is
something the incumbent measurably cannot do **[all MEASURED as gaps above]**:

1. One ticket id survives a cross-board handover, with `handover_at` recorded.
2. Priority is computed from impact and urgency and cannot be typed.
3. A clinical floor, once signed, cannot be lowered except by a named role with a
   typed reason and an audit event.
4. The resolve clock stops in a pause state, and attainment is reported per clock,
   per calendar, per board.
5. A restricted board provably excludes a non-member — demonstrated, not asserted.
6. One requester mailing two addresses in one minute produces **one** ticket.
7. Effort banded on a ticket reaches a variation and appears in the uplift
   evidence report, per entity, per month.
8. A variation-path ticket cannot consume effort or close with no variation
   attached. **Already true and tested.**
9. Rows in equal rows out on every import, with flags counted. **Already true.**
10. The desk answers when the WAN is down.

Items 1–7 and 10 are the case for building. If a bought product can pass all ten,
buy it — and the honest position is that **nobody has yet run these ten tests
against Jira Service Management**, which the record named as the successor. That
is a day of work and it should happen before Phase B, not after.

---

## 12. Fences

Carried forward unchanged, plus two new ones.

- **Never** commit patient identifiers or names, credentials, tokens, API keys,
  `.env`, or anything on the record's inventory denylist.
- **Never use or record the Kitameraki/TeamsWork API keys.** They were exposed in
  a screenshot. Both should be rotated. Read an export.
- **No internal IP addresses or network topology.** Hostnames and service names
  are fine.
- Label every claim MEASURED, VERIFIED with a URL read today, INFERRED, or NOT
  VERIFIED.
- **New:** no PHI in a ticket summary or description — §6.1.
- **New:** no rule, floor, SLA or board configuration is hard-coded. If PMC cannot
  change it without a deployment, it is in the wrong place.

**Recorded, not for decision here:** work produced for PMC becomes PMC's on
approval and payment. Dada's instruction, 9 Sep 2026. The only thing worth
separating later is the reusable engine from the PMC-specific configuration, and
that is a conversation for the change order, not for the schema.

---

## 13. Decisions needed before code

| | Decision | Why it blocks |
|---|---|---|
| **D1** | Where the primary runs — A, B or C in §8.1, and confirmation it is **not** on `DND-HOST1` | Changes the deployment, the backup design and the offline story |
| **D2** | Does the standard-library-only rule change shape as proposed in §8.3? | Decides whether Phase B is buildable at all |
| **D3** | Identity: Entra for all, local for departmental fulfillers, or mixed | Decides ~USD 2,160/year, and the RA 10173 posture |
| **D4** | Ticket numbering: one `PMC-` sequence across all boards, with `legacy_ref` | Cheap now, very expensive after the first thousand tickets |
| **D5** | Rule conditions: structured field/operator/value only, no expression language | Security and testability |
| **D6** | Is Phase A funded as a variation, and at what number? | §1.4 — the AUD 6,500 spine line does not cover this |

Three things worth doing this week regardless of any of the above, all
**[MEASURED]** as open in the record, all cheap:

1. **Send the Kitameraki support email.** It has been drafted and unsent since the
   vendor-side outage.
2. **Alias `support@pmcne.ph` onto `helpdesk@pmcne.ph`.** One hour. Kills the
   measured double-creation.
3. **Withdraw or contract the auto-responder**, which publishes a resolution
   commitment the agreement does not contain.

---

## Sources read today

- ConnectWise Manage Ticket object, field list — http://vc3.github.io/connectwise-rest-api/modules/_api_api_.ticket.html *(third-party generated mirror of the REST API, not ConnectWise's own documentation)*
- ConnectWise service board concept and setup tables — public search summaries of `docs.connectwise.com/ConnectWise_Documentation/060/020/010`, `/090/020/170` and `/090/020/070/130`. **The pages themselves are behind ConnectWise University authentication and were not read.**
- ServiceNow Task table structure — https://www.servicenow.com/docs/r/washingtondc/application-development/table-administration-and-data-management/task-table-structure.html
- ServiceNow REQ / RITM / SCTASK relationship — servicenow.com community threads, **community content, not product documentation**.

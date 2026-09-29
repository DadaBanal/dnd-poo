# WS36-connectwise-parity-20260929

**PSA desk against ConnectWise PSA: side-by-side, third pass, after the eight gaps.**

**Branch:** `claude/psa-ticketing-build` at the head this file arrives with (29 Sep 2026).

**Supersedes `docs/WS36-connectwise-parity-20260928.md`**, which is kept as
written. Dada asked, 29 Sep: *"what else needs to be built or missing from the
full ConnectWise PSA"* and then *"do the gaps"*. The gap assessment named
eight; all eight were built today, in the order below, each with its schema
step (046 to 051, and one column on the API token table), its tests on both
stores, its README section and its runbook Pass line for SQL01. ConnectWise
Sell (quotes and opportunities) was named as a later option and is **not**
built.

**How to read it.** As before: each row names a ConnectWise PSA feature, what
this desk does, and a status.

| Status | Meaning |
|---|---|
| **Built** | Works as ConnectWise does |
| **Built differently** | Deliberately not the same, with the reason given |
| **Not built** | Missing |
| **Out of scope** | Not wanted in this build |

**Sources for the ConnectWise side.** Unchanged from the 28 Sep record: the
extracted entity model (`docs/WS36-connectwise-model-20260909.md`, VERIFIED 9
Sep 2026 from ConnectWise's own OpenAPI schemas) and the pages the 23 Sep
record read; docs.connectwise.com still redirects to a sign-in (MEASURED 28
Sep), so where a ConnectWise behaviour is not in the model it is labelled
INFERRED. Claims about the desk are **MEASURED** from the code and the 580
tests.

## Built since 28 September (the eight gaps)

| ConnectWise | This desk | Status |
|---|---|---|
| Time sheets: a member's week, submitted, approved or rejected by an approver (`TimeSheet`, `TimeSheetStatus`); utilisation reports | Timesheets (046): every time entry belongs to the week it was worked; OPEN → SUBMITTED → APPROVED / REJECTED (with a reason) by a Timesheets administrator who is not the member; reopen with a note; a submitted week takes no more time; `/time`; utilisation by member on Reports; the uplift evidence says how many hours sit on an approved sheet | **Built** |
| Security roles per module (`SecurityRole`) | A sixth module, Timesheets (WRITE by default, ADMIN decides others'); `role_grant` supersedes `role_permission`, whose CHECK could not take a sixth module | **Built** |
| Recurring tickets (INFERRED: ConnectWise schedules them through workflow and templates) | Recurring tickets (047): a board template raised on a cadence (daily to yearly, every n) by the rules runner, once per due day however long the runner was down, with the template's tasks, an owner and the machine; Setup › Recurring tickets | **Built** |
| Configuration lifecycle: `purchaseDate`, `warrantyExpirationDate`, `installationDate`, `vendor`, `location`; agreement on a configuration | The life of a machine (048): those fields on the configuration's page, warranty tiles and column on the list, the agreement it is under, and a maintenance-record CSV per asset and per list for a DOH inspection; Configurations and Maintenance datasets in the report writer | **Built** |
| Approvals on a service ticket (ConnectWise approves *changes* and time; a request approval is INFERRED from its workflow) | Request approvals (049): a department names its approver, a catalogue pair can require one, a technician can ask anyone; the ticket parks in *Awaiting approval* (the resolve clock pauses), the approver decides on the portal under Approvals with a reason, the decision goes on the ticket as a note the requester reads, and the ticket returns to where it was | **Built, stricter** (the approver, not the technician, is the only one who can say yes) |
| Mobile app (ConnectWise Manage mobile) | The desk on a technician's phone (gap 5): the same pages read their width; the board as cards, thumb-sized controls, a bar at the foot of every desk page and, on a ticket, Note, Ticket and Call (the contact's number as a `tel:` link) | **Built differently** (a responsive page, not an app store app; nothing to install on a ward phone) |
| Notifications beyond email: Teams, mobile push, on-call escalation | Teams cards and on-call paging (050): a workflow rule notifies a named Teams channel as a card (never the summary, never a note); a page repeats every 5 minutes, 3 times, until the on-call acknowledges it on the ticket, then the duty manager is paged; the webhook address lives only on the host | **Built** (Teams and email; no SMS gateway exists at PMC; whether Teams renders the card as posted is NOT VERIFIED from the cloud) |
| Knowledge base articles with images and attachments | Pictures and documents on an article (051): kept the way a ticket's files are, reviewed before a requester sees them, shown in the text as `![caption](file:N)` | **Built, stricter** (every file waits for a patient-information review before the portal shows it) |
| REST API: read and update tickets, configurations, with API keys and security-role scopes | Token scopes (gap 8): RAISE (as before), READ (list and read every ticket on the token's board, and the configurations), WRITE (a note, a status, an owner), one board per token, every read of a restricted board audited | **Built, stricter** (one board per token; never a person's credential) |

## Built since 23 September (carried from the 28 Sep record, unchanged)

Attachments with review; tasks and templates; child tickets and merge;
schedule entries and Dispatch; surveys; standard notes, saved views and
global search; Reports; outbound mail to requesters; the Customer Portal on
its own address; time entry as ConnectWise records it, with work roles and
work types; Setup tables for types, subtypes and items. See that record.

## Still deliberately stricter than ConnectWise

| ConnectWise | This desk | Why |
|---|---|---|
| Priority typed, or from an SLA matrix of impact × severity | Never typed: two plain questions, catalogue and clinical floors | The record's rule; a nurse answers questions, not a matrix |
| Time is hours; billing follows the agreement | Hours as ConnectWise records them, **and** a charge method on every entry, **and** the band derived from the hours | §5.2: an uplift claim is defended in bands and by commercial classification |
| Any signed-in contact may see the company's tickets | A requester sees their own requests only; a board's tickets need membership; restricted boards audit every read, a machine's included | §6.1 |
| A Teams or email notification carries the ticket's summary | Never: the ticket number, board, priority, status, owner and the rule's words; the summary and the notes stay behind the sign-in | §6.1 |
| An article's picture is visible on publish | Visible to the desk at once, to a requester only once a person has cleared it | §6.1 |
| Custom fields | None | Each would be its own decision; nothing in the record asks for one |

## Not built, and why

| ConnectWise | Status | Why |
|---|---|---|
| ConnectWise Sell: quotes, opportunities, a sales pipeline | **Not built** | Named on 29 Sep as a later option; nothing in the record asks for it yet |
| Invoicing, products, expenses, finance tabs beyond the BizBox mirror and agreements | **Out of scope** | The spine keeps the commercial basis and hands out no invoices; BizBox is the finance system |
| Project phases, WBS, budgets, predecessors | **Partly built** | A Project board kind and projects with phases exist (041); predecessors and a Gantt do not |
| Per-user column choice on the board | **Not built** | Saved views cover the filters; columns are fixed (and fold to cards on a phone) |
| Status indicators (a colour per status) | **Not built** | Colour is the clock's, not the status's |
| Required date, estimated start, budget hours on a ticket | **Not built** | Nothing on the desk reads them; a Change carries its window instead |
| SMS paging | **Not built** | No gateway at PMC; a page reaches the on-call by email and Teams, and the contact's number is a Call link on the phone layout |
| A native mobile app | **Built differently** | The responsive desk; see above |

## Evidence

- Tests at the head this file arrives with: **580** on SQLite (OK, 1 skipped). On SQL Server 2022 in a container, the whole suite ran today with 046 to 049 (569 run, OK, 2 skipped, 13.5 min) and with 046 to 050 (575 run, OK, 2 skipped, 13.8 min); the run with 051 and the API scopes is recorded in the runbook when it finishes. The drift gate passes; CI runs 67 and 68 are green on the pushed heads.
- Screens checked in Chromium on 29 Sep at an iPhone 13's width: fourteen desk and portal pages fit with no sideways scroll and no control under 40 px (the phone layout's MEASURED line in the README).
- Nothing here was verified against a live ConnectWise tenant or a live Teams tenant; the Teams card's rendering is the one item for the SQL01 sitting to confirm.

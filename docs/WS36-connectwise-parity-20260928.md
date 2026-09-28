# WS36-connectwise-parity-20260928

**PSA desk against ConnectWise PSA: side-by-side, second pass.**

**Branch:** `claude/psa-ticketing-build` at the head this file arrives with (28 Sep 2026).

**Supersedes `docs/WS36-connectwise-parity-20260923.md`**, which is kept as
written. Dada asked, 28 Sep: *"double check functions that should be similar
to what ConnectWise does"* and *"regarding the GUI and the time taking, I don't
think it follows what ConnectWise does, make sure it follows it"*. This is
that check, done function by function against ConnectWise's own field model
and the pages the 23 Sep record read, with what was changed today.

**How to read it.** As before: each row names a ConnectWise PSA feature, what
this desk does, and a status.

| Status | Meaning |
|---|---|
| **Built** | Works as ConnectWise does |
| **Built differently** | Deliberately not the same, with the reason given |
| **Not built** | Missing |
| **Out of scope** | Not wanted in this build |

**Sources for the ConnectWise side.** The record's extracted entity model
(`docs/WS36-connectwise-model-20260909.md`, VERIFIED 9 Sep 2026 from
ConnectWise's own OpenAPI schemas: `TimeEntry`, `WorkRole`, `WorkType`,
`Board`, `BoardStatus`, `Ticket`, `ServiceTicketNote`, `Configuration`), and
the pages listed in the 23 Sep record. docs.connectwise.com now redirects
every page to ConnectWise University sign-in (MEASURED 28 Sep), so nothing new
was read there; where a ConnectWise behaviour is not in the model it is
labelled INFERRED. Claims about the desk are **MEASURED** from the code and
the 519 tests.

## Changed today, because a technician who knows ConnectWise would notice

| ConnectWise | Before today | Now | Status |
|---|---|---|---|
| **Time entry**: `timeStart`/`timeEnd` or `actualHours`, `hoursDeduct`, `workRole`, `workType`, `billableOption` (Billable / DoNotBill / NoCharge / NoDefault), notes with the Internal / Discussion / Resolution flags, a Time tab listing entries | A picker of five bands and a charge method on the note | The same fields, the same rule (start and end **or** actual hours, never both; a deduction comes off; kept to the quarter hour, INFERRED as ConnectWise's usual rounding); the Time pod is the Time tab with its own *Add time*; the note composer carries the same fields | **Built** (the spine's charge method stays, and the band is derived: see "Kept stricter") |
| `WorkRole` and `WorkType` setup tables, a type carrying its `billTime` | None | Setup › Time: add and retire, a type with its bill default | **Built** |
| `Board.workRole` / `Board.workType`: the board's default role and type | The first in Setup › Time | Setup › the board › Board tab chooses the board's own; the first in Setup › Time otherwise | **Built** |
| `Board.sendToResourceFlag`: the owner is emailed when a ticket is assigned | Only through a workflow rule | Board setting "Email the owner when a ticket is assigned to them": one unsent email per ticket and owner, none when you assign it to yourself, no summary in the subject | **Built** |
| The "Contact" tick on a note: email the contact this note, or not | Every Discussion note emailed the requester | A tick on the note and on the time entry, on by default, drawn where the board emails requesters | **Built** |
| Ticket screen: pods the technician arranges | Side cards reordered within one column | Every card is a pod in either of two columns: drag, arrows, fold, remembered, reset | **Built, more** (ConnectWise's pods are fixed per screen, INFERRED) |
| Configurations list and page | A search table and a short page | Counts by type that filter, status and company filters, sorting, open-ticket counts, a machine typed in by hand, a page with every field, tickets open and closed, history, and *Raise a ticket for this machine* | **Built** |

## Built since 23 September (the "Not built" list of that record)

| ConnectWise | This desk | Status |
|---|---|---|
| Documents / attachments tab | Attachments on tickets, from the desk, the portal and email; compressed; each waits for a §6.1 review before it is served; usage, integrity and retention tools | **Built, stricter** |
| Tasks tab, ticket templates | Tasks, and templates that carry tasks; a template picker on New ticket | **Built** |
| Child tickets, merge | Parent/child bundling (one level; children close with the parent), merge duplicates | **Built** (the child-ticket SLA trap is avoided by design: a child keeps its own clocks) |
| Schedule entries, Dispatch | Visits on a ticket (who, from, to), Dispatch shows the day; no double booking | **Built** (no drag calendar) |
| Surveys | One question after close, on the portal | **Built** |
| Standard notes, saved views, global search (⌘K) | All three | **Built** |
| Reports | KPIs, monthly charts, CSV | **Built** |
| Outbound mail to requesters | "Your ticket was opened / updated / closed", with the portal link and never the note text | **Built, stricter** |
| Customer Portal | *My requests* on its own address (`help.pmcne.ph`), the requester's own shell, and *My requests* from the Employee Portal with no second sign-in | **Built** |

## Still deliberately stricter than ConnectWise

| ConnectWise | This desk | Why |
|---|---|---|
| Priority typed, or from an SLA matrix of impact × severity | Never typed: two plain questions, catalogue and clinical floors | The record's rule; a nurse answers questions, not a matrix |
| Time is hours; billing follows the agreement | Hours as ConnectWise records them, **and** a charge method on every entry, **and** the band derived from the hours | §5.2: an uplift claim is defended in bands and by commercial classification; ConnectWise leaves that to the agreement |
| Any signed-in contact may see the company's tickets (`allowAllClientsPortalView`) | A requester sees their own requests only; a board's tickets need membership; restricted boards audit every read | §6.1 |
| Custom fields | None | Each would be its own decision; nothing in the record asks for one |
| Subject parsing rules on the email connector | None; a workflow rule reads the subject instead | Simpler, same effect |
| Knowledge base | None | Its own module; out of scope |

## Not built, and why

| ConnectWise | Status | Why |
|---|---|---|
| Agreements, invoicing, procurement, products, expenses, finance tabs | **Out of scope** | The spine keeps the commercial basis and hands out no invoices |
| Project phases, WBS, budgets, predecessors | **Partly built** | A Project board kind exists; phases wait on a decision to run projects here |
| Per-user column choice on the board | **Not built** | Saved views cover the filters; columns are fixed |
| Status indicators (a colour per status), `customerPortalFlag` per status | **Not built** | A status carries its portal wording (`customerPortalDescription`) already; colour is the clock's, not the status's |
| Auto-close after N days resolved (`autoCloseStatus`) | **Built differently** | A workflow rule on "minutes since last update" with a status action does it, per board, tested before it is switched on |
| Required date, estimated start, budget hours on a ticket | **Not built** | Nothing on the desk reads them; a Change carries its window instead |

## Evidence

- Tests at the head this file arrives with: **519** on SQLite (OK, 1 skipped) and on SQL Server 2022 in a container (OK, 8 skipped). The drift gate passes; the smoke test passes 7 of 7.
- Screens checked in Chromium on 28 Sep: the Time pod and the note composer, the pods across columns, Setup › Departments, the Configurations list and page.

# WS36-connectwise-parity-20260923

**PSA desk against ConnectWise PSA: side-by-side.**

**Branch:** `claude/psa-ticketing-build` at `dbd435b`.

This is a new document. It supersedes nothing.

**How to read it.** Each row names a ConnectWise PSA feature, what this desk
does, and a status:

| Status | Meaning |
|---|---|
| **Built** | Works as ConnectWise does |
| **Built differently** | Deliberately not the same, with the reason given |
| **Not built** | Missing |
| **Out of scope** | Not wanted in this build |

**Sources for the ConnectWise side.** All were read 23 Sep 2026.

- **Types workbook:** ConnectWise's public "Service Type Examples" workbook
  (ConnectWise University content).
- **Setup pages:** the Service Board, Types, Project Board, Service Transition,
  Service Operation, Email Connector and Workflow Rules setup pages on
  docs.connectwise.com. The last two were read as Wayback archives.
- **API model:** the public OpenAPI model (Service.json and System.json,
  v2026.13).
- **Partner write-ups:** Visionary 360, DeskDirector, ChangeBreeze.

**Evidence labels.** Claims about ConnectWise are **VERIFIED** unless marked
otherwise. Claims about the desk are **MEASURED**: from the code, the 384
tests, or screenshots taken today. Ticket-screen tab order and the default
board columns are **NOT VERIFIED**: those pages sit behind the ConnectWise
login and were never archived.

## Service boards

| ConnectWise | This desk | Status |
|---|---|---|
| Many boards, divided by team and workflow | Many boards; one person can be on many; each board has its own statuses, SLA, teams and members | Built |
| Service board versus project board (projectFlag) | Board kind: Service, Change or Project (`board.kind`) | Built. Change is an extra kind, see "Change" below. |
| Types tab: Type › Subtype › Item per board | Types tab per board: Incident, Request, Problem, Event (ConnectWise's ITIL example), plus Change and Project. Subtype › Item come from one catalogue shared by all boards. | Built differently. One catalogue, so a subtype means the same thing on every board (build scope §2.4). |
| Statuses: escalation status, closed flag, "no time entry", customer description, default | All of these, plus an approval gate on change statuses | Built |
| Board teams, member access | Teams, and member access at READ, WORK or ADMIN | Built |
| Restricted board | Restricted boards: members only, and every read is audited (§6.1) | Built, stricter |
| Copy setup from another board | Start a new board from the starter or from another board | Built |

## SLA

| ConnectWise | This desk | Status |
|---|---|---|
| Respond, resolution plan and resolve clocks per priority | The same three clocks, shown as chips on the board and as boxes on the ticket | Built |
| Waiting status pauses the SLA | Waiting pauses the resolve clocks; respond is never paused | Built |
| SLA follows a calendar | A calendar per board | Built |
| Priority from impact × urgency | Priority is computed from two plain questions and is never typed. Catalogue and clinical floors apply. | Built, stricter |
| One SLA per board and priority | Targets per board and priority, plus per Type: a Request can run on its own targets | Built, more |
| Child tickets keep SLA clocks running (a known reporting trap) | No parent/child bundling. Links never touch clocks. | Built differently, on purpose |

## Tickets and notes

| ConnectWise | This desk | Status |
|---|---|---|
| Summary, company, contact, board, status, type/subtype/item, priority, owner, source | All of these | Built |
| Notes flagged Discussion, Internal or Resolution, more than one per note | Discussion or Internal, and either can also be the Resolution. An Internal resolution never reaches the portal. | Built |
| Time entries on notes | Banded time on a note. The charge method must be chosen; the variation gate applies. | Built, stricter |
| Configurations tab | Attach and detach configurations, each with a ScreenConnect launch link | Built |
| Related, child and merged tickets | Links: *caused by problem*, *fixed by change*, *related*. No merge, no bundle. | Built differently: ITIL links, without the child-ticket SLA trap |
| Tasks, documents and attachments, products, finance tabs | None | **Not built** |
| Ticket templates | None | **Not built** |
| Custom fields | None | **Not built** |
| Audit trail | Every change is a ticket event; setup changes go to `audit_event` | Built |
| Service board list: filters, sortable columns, bulk actions | Five counter tiles, filters (board, status, owner, priority, Type, source, search), sortable columns, and bulk status, assign and move | Built. Columns are fixed, not chosen per user. |
| "Customer updated" flag | Set by every requester reply; cleared by a technician's note | Built |

## Record types and ITIL

| ConnectWise | This desk | Status |
|---|---|---|
| ITIL types on a board (Event, Incident, Problem, Request) | The same four, as a service board's Types | Built |
| Change: an RFC flag on a Type, with approvals from an add-on module | A Change board kind: standard, normal and emergency changes; risk; window; backout plan; an approval gate on statuses; the owner never approves their own change; append-only decisions | Built, more than base ConnectWise |
| Project boards: phases, WBS, budgets, predecessors | A Project board kind with project statuses and no SLA clocks. No phases, WBS or budgets. | **Partly built** |

## Email connector

| ConnectWise | This desk | Status |
|---|---|---|
| Mailbox to board, with a catch-all company | Graph pickup from the helpdesk mailbox every 30 seconds; unknown senders go to the catch-all company | Built. Runs once the mail handoff is done on DND-SQL01. |
| Reply threading: `Ticket #` token, or Message-ID | Thread headers first, then the ticket number anywhere in the subject | Built, more tolerant |
| Sender matching: address, then unique name, then domain | Address, then UPN, then a domain owned by one company. Never by name. | Built differently: a name can belong to two people |
| Replies to closed tickets: reopen, or new ticket after N days | Per board: reopen to a chosen status, or a new linked ticket after N days | Built |
| Ignore daemon and postmaster mail | Also out-of-office replies and the desk's own address. Alerts still open tickets. | Built, more |
| Subject parsing rules | None: a rule can raise priority from the subject instead | **Not built** |
| Outbound mail to the contact | None to requesters. Rule notifications go out through Graph once the SQL01 handoff is done. | **Partly built** |

## Workflow rules

| ConnectWise | This desk | Status |
|---|---|---|
| Rule scoped by record type and board, holding events, conditions and actions | The same shape. Rules act on tickets only. | Built |
| Run once, N times, or continuously | Built | Built |
| Test before activate; an edit deactivates the rule | Built | Built |
| Runs at most every 10 minutes | Runs the moment the ticket changes; time-based events every minute | Built, faster |
| Age in SLA hours, minus waiting time | "SLA used (%)" from the clocks themselves | Built |
| Actions: email, status, board, assign, note, and others | Notify or escalate (to a role, the on-call, the owner, the requester or a named person), status, board, owner or team leader, internal note, flag | Built. No survey, no Automate script. |
| AND, OR, NOT and brackets | AND and OR, read left to right; NOT through the "is not" and "none of" operators | Built differently: no brackets, on purpose |

## Companies, contacts, configurations, integrations

| ConnectWise | This desk | Status |
|---|---|---|
| Companies and contacts | Companies; contacts imported from AD (by objectGUID); company and contact pages | Built |
| Configurations | Machines imported from AD computers; config pages; per ticket, company and contact | Built. Hostnames only, no IP addresses. |
| ScreenConnect launch from a configuration | Admin-written URL templates, HTTPS only, values URL-encoded | Built. The session ID is entered by hand. |
| RMM / Automate alerts become tickets | Machine API with dedup keys; alerts open as Events | Built |
| Customer Portal | "My requests": raise, follow and reply. Discussion and resolution are shown; Internal never is. | Built |
| Dispatch portal and resource scheduling | Dispatch view and on-call rota. No calendar schedule entries. | **Partly built** |

## Not built, in suggested order

1. **Attachments** on tickets. Screenshots are the most common thing a
   requester sends. This needs a storage decision, and every file needs a
   §6.1 PHI decision.
2. **Ticket tasks and ticket templates**, for repeatable requests (onboarding
   a user, moving a PC).
3. **Outbound mail to requesters** (acknowledgement, and Discussion notes by
   email), reusing the notification sender.
4. **Project phases and budgets**, if projects are to be run here rather than
   only tracked.
5. **Custom fields, surveys and a knowledge base.** Deliberately last: each
   is its own decision.

Commercial modules (agreements, invoicing, procurement) are **out of scope**.
The spine keeps the commercial basis (baseline versus variation, uplift
evidence) and hands out no invoices.

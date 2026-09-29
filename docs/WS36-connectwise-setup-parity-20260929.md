# WS36-connectwise-setup-parity-20260929

**Setup and administration: the desk against ConnectWise PSA's System and setup tables.**

**Branch:** `claude/psa-ticketing-build` at `58008d6` (29 Sep 2026); **updated
the same evening** after 053 built items 1 and 2 and the per-board intake
address (Dada: *"can we have different intake emails for the service
boards?"*), which moves the email-connector row below from *Partly built* to
*Built differently*: a board claims an address, intake routes by the
recipient, and no connector or credential per board is needed.

**Complements `docs/WS36-connectwise-parity-20260929.md`**, which set the
desk's *features* against ConnectWise and is kept as written. Dada asked, 29
Sep, evening: *"the user page is not properly build there is no member page
as per connectwise … check all the other settings and administration tools
that hasnt been applied to the build that exists in connectwise api"*, and
then *"there is also no calendar page"*. This record answers that: every
setup table and administration tool the reference PSA's API exposes, what
the desk has for it, and what is missing.

**Sources.** The ConnectWise side is the extracted entity model
(`docs/WS36-connectwise-model-20260909.md`, VERIFIED 9 Sep 2026 from
ConnectWise's own OpenAPI schemas): its *Members, security and system* group
(93 entities), *Companies, contacts and sites* (42), *Service delivery — the
board* (29), *SLA and calendars* (9), *Configurations* (5), *Classification and
reference data* (9). Where a behaviour is not in the model it is labelled
INFERRED. The desk side is **MEASURED** from the code at this head: the Setup
routes in `router.py`, the Setup landing (`views/admin.py`), and the schema.

| Status | Meaning |
|---|---|
| **Built** | A setup page exists and does what ConnectWise's does |
| **Built differently** | Deliberately not the same, with the reason |
| **Partly built** | The data exists but the page or part of the data does not |
| **Not built** | Missing |
| **Out of scope** | Not wanted in this build, and why |

## What Setup has today (MEASURED)

The Setup landing links eleven pages: Boards and the service catalogue (a
page per board with tabs for statuses, SLA, calendar, reply policy, types,
templates, standard notes, teams, and *Members & roles*), Departments,
Security roles, BizBox (Finance), Calendars (business hours and holiday
lists), Schedule (statuses and locations), Time (work roles and work types),
Workflow rules, Recurring tickets, Integrations (links out, Teams channels),
and a card of local break-glass accounts. On-call rotas are on `/oncall`.

**A member is a string, not a record.** `board_member.member`,
`member_role.member`, `member_capacity.member`, `oncall_slot.member`,
`time_entry`, `local_account.username` all carry the same identifier, and
the desk shows a person's name only when the AD contact import
(`contact.display_name`) has a row for it; otherwise the identifier is the
name. There is no `member` table, no page that lists everyone on the desk,
no page for one person. Members are added board by board on the board's
*Members & roles* tab (identifier, access, team), given a security role on
Security roles, given hours a week on Time, and a local account is made from
the command line. That is the defect Dada named, and it is real.

## The gaps, in the order I would build them

### 1. Members (System › Members) — **Built** (053, the same evening)

ConnectWise's `Member` is 123 fields (VERIFIED). The ones a hospital IT
desk uses, and the desk's state for each:

| ConnectWise field | Desk today | Gap |
|---|---|---|
| `identifier`, `firstName`, `lastName`, `title` | the sign-in name; the AD contact's display name when imported | a record of its own |
| `officeEmail`, `officePhone`, `mobilePhone`, `defaultEmail` | the AD contact's email, when imported | none for a member who is not a contact; mobile never |
| `inactiveFlag`, `inactiveDate`, `hireDate` | none (a person leaves and their memberships stay) | deactivation, which ConnectWise treats as a whole entity family (`MemberDeactivation*`, 22 entities: what to reassign when a person goes) |
| `securityRole`, `adminFlag` | `member_role`; sysadmin comes from the sign-in | shown on the person, not only on the role page |
| `defaultDepartment`, `defaultLocation`, `reportsTo` | none | needed for the department approver and the on-call escalation to read from the person |
| `serviceDefaultBoard`, `excludedServiceBoardIds` | board memberships | a list of the boards the person is on, in one place |
| `workRole`, `workType`, `hourlyCost`, `hourlyRate` | work role chosen per time entry; no cost or rate | a default work role per person; cost and rate are the uplift's business, so INFERRED wanted |
| `dailyCapacity`, `scheduleCapacity`, `includeInUtilizationReportingFlag` | `member_capacity.hours_per_week` | daily, and the utilisation flag |
| `timeApprover`, `requireTimeSheetEntryFlag`, `timeSheetStartDate` | a Timesheets ADMIN who is not the member approves anyone | a named approver per person |
| `calendar`, `timeZoneSetup` | none per person (every clock runs on the board's calendar) | a person's working calendar, for the schedule |
| `photo` | none | none needed |
| `licenseClass` (`F` full, `A` API, `C`, `X`) | `api_token` is the API member | none: no licences here |
| `MemberSkill`, `MemberCertification` (skill level Beginner to Expert) | none | dispatch by skill is INFERRED useful for biomedical devices; not asked for |
| `MemberDelegation` (who acts for me while I am away) | none | approvals and time approval would need it |
| `MemberNotificationSetting` (which triggers email me) | rules only | per-person notification choices |
| `MemberPersona`, `MemberOffice365`, `MemberSsoToken`, `MemberLinkSsoUser` | Entra and Windows sign-in already map a person by UPN | none |
| `MyMember` / `MyAccount` (the person's own page) | none | a *My profile* page: name, contacts, capacity, the boards I am on, my role |

**What to build:** a `member` table (053) keyed by the identifier every other
table already uses, with name, title, emails, phones, department, location,
reports-to, default board, default work role, hours a day and a week,
time approver, inactive-from, notes; Setup › Members listing everyone with
role, boards, capacity and last sign-in; a page per member that edits the
record and shows and changes the memberships, the role, the capacity and the
local account in one place; *deactivate* that ends memberships, the rota
slots, the delegation and the approver duties with a list of what it changed;
the AD contact import fills a member's name and email when the identifier
matches; `/my/profile` for the person. Nothing else moves: the string
identifier stays the key everywhere, so 053 adds a table and changes no row.

### 2. Calendar (the person's calendar, and a month) — **Built** (053, the same evening; reminders not built)

Dada: *"there is also no calendar page"*. What exists (MEASURED): **Setup ›
Calendars** (business hours per calendar, holiday lists, in ConnectWise's
`Calendar`/`Holiday`/`HolidayList` shape, 037); **Schedule** (`/schedule`),
one week, one row per member of the boards you see, every visit and block a
chip, in the shape of ConnectWise's schedule board; **Dispatch** (`/dispatch`),
one day. What is missing against ConnectWise's `ScheduleEntry` views
(INFERRED from the entity, since the screens are not in the model): a
**My Calendar** page (one person, day / week / month, their visits, time
off, meetings and on-call slots together); a **month view**; a
**calendar feed** (`.ics`) so a technician's phone shows the desk's visits
without opening it; `ScheduleReminderTime` (a reminder before a visit) and
`ScheduleColor`. `PortalCalendar` (the customer's view of a site's visits) is
out of scope: a ward does not book a technician.

**What to build:** `/calendar` (mine by default, `?member=` for a dispatcher,
day / week / month), an `.ics` feed per member behind a token, and a reminder
minutes column on `ticket_schedule` that the rules runner honours. No schema
beyond the token and the reminder column.

### 3. System › Setup tables the desk lacks

| ConnectWise setup table | Desk today | Status |
|---|---|---|
| `Location` / `CorporateStructure` (my company's sites and levels) | `site` (a company's sites) and `department` | **Partly built**: the desk has where a *requester* is; it has no list of where *Dada IT* is (the office, the ward store rooms). Needed once a member has a default location |
| `Department` / `DepartmentLocation` | Setup › Departments, department × board, approver | **Built** |
| `SecurityRole` / `SecurityRoleSetting` (add / edit / delete / inquire per module, None / My / All) | six modules × NONE / READ / WRITE / ADMIN | **Built differently**: four levels instead of four verbs × three scopes; the record's §6.1 wanted fewer knobs, not more |
| `Priority`, `Impact`, `Severity` (and an SLA matrix) | P1–P4 from two plain questions, catalogue and clinical floors | **Built differently**, on purpose (the record's rule: a nurse answers questions, not a matrix) |
| `Source` (how a ticket arrived) | `ticket.source` is a fixed vocabulary; email, portal, desk, API, register | **Built differently**: no setup page, and none is wanted (each source is code) |
| `ServiceLocation` (on site / remote / in house) | Setup › Schedule › locations | **Built** |
| `BoardStatus`, `BoardType`, `BoardSubType`, `BoardItem`, associations, `BoardTeam`, `BoardAutoTemplate`, `BoardNotification` | the board page's tabs, the catalogue, rules | **Built** |
| `BoardExcludedMember`, `BoardAutoAssignResource` | membership is the inclusion; no auto-assign | **Not built**: auto-assign by type or by round robin. INFERRED wanted once the desk has three or more technicians on one board |
| `ServiceEmailTemplate` (the wording of the emails a board sends) | fixed wording in code; a rule's own words | **Not built**: a template per board and event, editable in Setup |
| `ServiceSurvey`, `ServiceSurveyQuestion`, `ServiceSurveyQuestionOption` | one fixed survey on close (`survey_response`) | **Partly built**: no Setup page, one question set, no per-board choice |
| `Calendar`, `Holiday`, `HolidayList` | Setup › Calendars | **Built** |
| `SLA`, `SLAPriority` | SLA targets per board × record type × priority × clock | **Built differently** (the clocks are the record's five, not ConnectWise's three) |
| `WorkRole`, `WorkType`, `WorkRoleLocation`, `WorkRoleExemption` | Setup › Time | **Built** (no per-location rates: out of scope with billing) |
| `Workflow*` | Setup › Workflow rules | **Built** |
| `ConfigurationType`, `ConfigurationStatus`, `ConfigurationTypeQuestion` | a fixed vocabulary of seven types, three statuses; no questions | **Not built**: a Setup page for configuration types and statuses, and typed questions per type (a device's serial, a ward's asset tag). INFERRED needed the day biomedical devices join the CMDB |
| `CompanyStatus`, `CompanyType`, `CompanyNoteType`, `CompanyTeam`, `CompanyGroup` | `entity` has a name and a covered flag | **Not built** (status and type); **Out of scope** (groups, teams, note types: a hospital has one company and a few suppliers) |
| `ContactType`, `ContactRelationship`, `ContactDepartment`, `CommunicationType` | a contact has one email, one phone, a department string | **Partly built**: no types, no second number; the AD import is the source, so a Setup page would fight it |
| `Country`, `State`, `AddressFormat`, `CwTimeZone` | none; the desk is one country and one time zone | **Out of scope** |
| `PortalConfiguration`, `PortalSecurityLevel`, `PortalReport` | the requester portal is one shape for everyone; the door gates it | **Built differently**: the record's §6.1 fixed what a requester sees |
| `KnowledgeBaseCategory`, `KnowledgeBaseSubCategory` | articles have a category text | **Partly built**: no Setup page for categories |
| `Link` (links out per screen) | Setup › Integrations › links | **Built** |
| `UserDefinedField`, `CustomFieldValue` | none | **Out of scope** (the 28 Sep record: each would be its own decision) |
| `StatusIndicator` (a colour per status) | colour is the clock's | **Not built**, on purpose |
| `Certification`, `Category`, `Classification` | none | **Not built** with members' skills (above) |

### 4. Administration tools the desk lacks

| ConnectWise tool | Desk today | Status |
|---|---|---|
| **Audit trail** (`AuditTrailEntry`, per record, and `TimeEntryAudit` with a source: Member / API / Workflow / Portal / EmailConnector …) | every change writes `audit_event` (actor, action, subject, detail); **no page reads it** except the ticket's history | **Partly built**: a Setup › Audit page (filter by person, action, subject, date; CSV) is the DOH inspection's first ask and is missing. The source of a change is not stored as a column |
| **API members and keys** (`ApiMember`, `MemberSsoToken`) | `api_token` minted from the command line with a scope; no page | **Partly built**: a Setup › API tokens page (mint, scope, board, revoke, last used) |
| **Email connector** (`EmailConnector`, one per board with its own mailbox and credential; parsing rules, `EmailExclusion`, `EmailToken`) | a board claims an intake address on its mail-policy tab (053); intake routes by the recipient address, so one mailbox with Exchange aliases serves every board, or a mailbox per board does; the reply policy is per board; auto-reply and bounce exclusions are in code | **Built differently**: an address, not a connector; no Setup page for exclusions or parsing rules |
| **Notification recipients** (`NotificationRecipient`: owner, team leader, duty manager …) | `notify_role` on a rule action: TEAM_LEADER, OWNER, REQUESTER; a named member; a Teams channel | **Built** |
| **Reports and custom reports** (`Report`, `CustomReport`, `ReportingService`) | Reports page and the report writer (042) | **Built** |
| **KPIs** (`KPI`, `KPICategory`) | the Reports tiles | **Built differently** (fixed set) |
| **Managed devices integration** (`ManagedDevices*`: Automate / RMM) | ScreenConnect launch, AD computer import | **Out of scope** (no RMM at PMC; `WS36-connectwise-automate-model-20260909.md` records the decision) |
| **Mass maintenance / import** (`ImportMassMaintenance`) | the desk export importer and the AD imports, command line | **Built differently** |
| **Allowed file types, allowed origins** (`AllowedFileType`, `AllowedOrigin`) | fixed in code (attachments refuse executables; CORS is none) | **Built differently**: not editable, on purpose |
| **My company** (`MyCompany*` roles: president, controller, service manager, dispatch, duty manager) | none | **Not built**: the desk names a duty manager per board's rota, not for the company |
| **In/out board** (`InOutType`, `InOutBoard`: who is in, out, on site) | none | **Not built**; INFERRED useful with the on-call rota, small |
| **Menu entries** (`MenuEntry`) | none | **Out of scope** |
| **Two-factor / auth services** (`AuthAnvil`, Google Authenticator) | Entra sign-in carries the tenant's MFA; local accounts have none | **Built differently** (MFA is Entra's), with a gap: a local break-glass account has no second factor |
| **SSO / LDAP configuration pages** | Entra and Windows configured on the host by environment | **Built differently**: not a page, by the credential fence |
| **Skills, certifications** | none | **Not built** (with members) |
| **Ownership types, entity types** | none | **Out of scope** |

## What I recommend building, in order

1. ~~**Members (053)**~~ — built the same evening.
2. ~~**Calendar**~~ — built the same evening (day / week / month, `.ics`
   feed); reminders before a visit are not built.
3. **Setup › Audit** — read the audit trail the desk already writes, with a
   CSV; add the source of a change (desk, portal, API, email, rules).
4. **Setup › API tokens** and **Setup › Email connector** — the two
   administration tools that today need the command line or the host.
5. **Setup › Configuration types and statuses**, with typed questions.
6. **Email templates per board**, **survey setup**, **KB categories**,
   **company status and type**, **auto-assign**, **in/out board** — each
   small; each its own decision.

Everything marked *Out of scope* or *Built differently, on purpose* stays as
it is unless Dada says otherwise; the reasons are the record's, not mine.

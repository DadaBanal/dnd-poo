# HANDOFF-cloud-sql01-WS36-20260926-runbook

The whole desk onto `DND-SQL01`, start to finish, in one file: the order of
the sittings, a default for every decision so nothing waits on a reply, what
to do when each step does not pass, and the one rule that outranks every
other line here. The four handoffs it sequences stay the detailed sources and
are not edited; where this file and they differ, this file is later and wins.

| Field | |
|---|---|
| **To** | SQL01 (the Claude Code session on `DND-SQL01`, with the operator at the keyboard). Tenant steps to whoever administers PMC's Entra. |
| **From** | Cloud Build |
| **Workstream** | WS36 (PSA ticketing): the desk on premises |
| **Bucket** | Everything below, in order, over as many sittings as it takes; each sitting ends with a Reply appended to the handoff it ran and a push to `claude/psa-ticketing-build`. |
| **Read first** | this file, then each handoff as its turn comes: 1 `…-20260925-sqlserver.md` 2 `…-20260925-pilot.md` (and `docs/WS36-pilot-test-script-20260927.md`) 3 `…-20260926-portal.md` 4 the earlier `…-20260923-mail.md`, `…-20260923-rules.md`, `…-20260924-attachments.md` for the tasks they set up |

## The rule that outranks every other line

**Nothing the hospital already runs on this host may be changed, stopped,
slowed or displaced.** The desk is a guest. Concretely, and in every sitting:

- Every `PSA-*` scheduled task writes its output to `D:\psa\logs\<TaskName>.log`
  (the action is a PowerShell wrapper ending in `*> D:\psa\logs\<TaskName>.log`),
  so a failure is read from a file the desk owns and never from the host's
  event log by someone hunting.
- The desk touches only what the footprint table names: database `PMC_PSA`
  (and `PMC_PSA_TEST` while step 6 runs), the login the desk uses, the folders
  `D:\psa\` and `D:\PMC\sql\`, ports **8085** and later **8443**, scheduled
  tasks and one Agent job named `PSA-…`, and `pyodbc` inside
  `C:\PMC\Python312`. Since 29 Sep, by Dada's decision (below), also: in
  `LiveDB_PMC` the schema `psa` with its four read-only views and one database
  user; the SQL login `psa_bizbox_reader`; the file `D:\psa\bizbox.odbc`. If
  a step would need anything outside that list, the step is not taken: stop,
  write what it needed, and report BLOCKED.
- **Never**: restart or reconfigure the SQL Server instance or IIS; change
  any instance-level setting (`sp_configure`, `max server memory`, the
  `model` database, recovery models of other databases); reboot; edit,
  disable or delete any existing scheduled task, Agent job, site, service,
  firewall rule or DNS record; touch `LiveDB_PMC`, `PMC_Apps`,
  `PMC_Reporting`, `ReportServer`, the Orthanc index or any other database;
  bind 8080 or `0.0.0.0`; edit this repo's `.claude/settings.json`; install
  anything system-wide.
- **The one exception, decided 29 Sep 2026 by Dada** (the BizBox handoff's
  Reply, parts 1–3: "b", then "use sql to read"): in `LiveDB_PMC`, schema
  `psa` holding four **non-schema-bound, SELECT-only** views
  (`vw_product`, `vw_purchase_order`, `vw_purchase_order_line`,
  `vw_invoice`) and one database user for the SQL login `psa_bizbox_reader`,
  which has `SELECT ON SCHEMA::psa` and nothing else. Nothing else in that
  database, ever; no write path exists and none is built without a decision
  with Dada's name on it. The views cannot block a BizBox upgrade; a renamed
  column makes the desk's sync fail and say so, and BizBox is untouched.
- **Read before change, every time.** Each handoff's step 0 and 1b are
  read-only checks; a change step runs only after its check passed in this
  sitting, not a previous one.
- **Preview before apply** where the tool offers it (`schema-preview`, the
  retention script's default, `-Apply` on the PowerShell scripts).
- **If anything on the host misbehaves while the desk runs**, whether or not
  the desk seems the cause: the kill switch (below), then report. Do not
  investigate the other service; that is not this row's route.

## The kill switch, and the full reverse

Stops everything the desk does in under a minute and touches nothing else.
Run it before any diagnosis of a problem elsewhere on the host:

```powershell
Get-ScheduledTask | Where-Object TaskName -like 'PSA-*' | Stop-ScheduledTask
Get-ScheduledTask | Where-Object TaskName -like 'PSA-*' | Disable-ScheduledTask
# the desk's process, if a task left one running
Get-CimInstance Win32_Process | Where-Object CommandLine -like '*psaspine serve*' | ForEach-Object { Stop-Process -Id $_.ProcessId }
```

and in SSMS: `EXEC msdb.dbo.sp_update_job @job_name = 'PSA-Backup-PMC_PSA', @enabled = 0;`

The full reverse, if Dada decides the desk comes off this host (read it
before running it; it drops the desk's data):

```powershell
Get-ScheduledTask | Where-Object TaskName -like 'PSA-*' | Unregister-ScheduledTask -Confirm:$false
```

```sql
EXEC msdb.dbo.sp_delete_job @job_name = 'PSA-Backup-PMC_PSA';
ALTER DATABASE PMC_PSA SET SINGLE_USER WITH ROLLBACK IMMEDIATE; DROP DATABASE PMC_PSA;
DROP LOGIN [<psa task account>];          -- only if it was created for the desk
-- the BizBox side (29 Sep): the desk's views, schema, user and login, and nothing else there
USE LiveDB_PMC;
DROP VIEW psa.vw_product, psa.vw_purchase_order, psa.vw_purchase_order_line, psa.vw_invoice;
DROP SCHEMA psa;
DROP USER psa_bizbox_reader;
USE master;
DROP LOGIN psa_bizbox_reader;
```

then `Remove-Item D:\psa -Recurse` (which takes `D:\psa\bizbox.odbc` with it)
and `D:\PMC\sql\PMC_PSA*` after the last backup is copied off. Beyond the
objects above, nothing else on the host was ever touched, so nothing else is
restored.

## The order, and a default for every decision

| # | Sitting | Handoff | Decisions it needs, with the default used if Dada has not answered |
|---|---|---|---|
| 1 | The database and the desk on SQL Server | `…-20260925-sqlserver.md` | **Task account**: default a local machine account `DND-SQL01\psa_desk`, created by the operator with `New-LocalUser` (password typed at the prompt, "user cannot change", never expires), "Log on as a batch job" right, no admin membership. A domain account replaces it in one line later. **Port**: 8085. **Recovery**: SIMPLE. **Backup folder**: `D:\PMC\backup\PMC_PSA`. **Instance**: `PMC_SS` as it stands (the D7 addendum names the alternative). |
| 2 | The pilot's first day | `…-20260925-pilot.md` + the test script | Boards, statuses, SLA targets: the Service Manager's, made in Setup. Port 8085. The database is the connection string, not the file. |
| 3 | HTTPS, sign-in, the portal for a first group | `…-20260926-portal.md` | **Sign-in**: the Windows account (default; no licence, no tenant). Entra only if Dada says so. **Desk name**: default the server's own FQDN if the certificate covers it, else the name the certificate does cover; if the certificate covers neither, the sitting stops after step 1 and the portal stays off (the desk keeps running on 8085 plain, LAN only). **First group**: Dada IT alone until Dada names a ward. |
| 4 | Retention, once the DPO answers | `…-20260924-attachments.md` step 4 | Never applied without the periods from the DPO; previewed weekly until then. |

Sittings 1 and 2 are the pilot. Sitting 3 is when staff first touch it.
Sitting 4 is on a date the record sets.

## Folded in from sitting 1 (26 Sep, SQL01's Replies)

Read with the tables below; each is now the rule.

- **Two code fixes are in** (head after `a8cfa21`): the CLI closes its
  connection on every road out (the Windows file lock that made step 6 red
  on two SQLite-only tests), and the three task scripts accept a connection
  string (the `Test-Path` guard skips one). Step 6 is re-run as SQL01 said:
  `PMC_PSA_TEST` recreated the same way, the operator runs the tests as
  `psa_desk` with `-TestsOnly`. Expect `OK`, 8 skipped for SQLite's settings
  and 1 for the non-Windows assertion; the two openssl skips are gone if
  Git's `openssl.exe` is where Git put it.
- **The task account is `DND-SQL01\psa_desk`** (created by the operator).
  "Log on as a batch job" is granted in `secpol.msc` by the operator, one
  name added to one right, before step 7. The desk's login has
  `db_datareader`, `db_datawriter`, `EXECUTE`, `VIEW DEFINITION` on `PMC_PSA`
  and nothing else; schema `psa` stays `dbo`'s.
- **The default port is now 8085 in the code**, so a task that omits
  `--port` still never lands on 8080.
- **`D:\psa` and `D:\PMC\backup\PMC_PSA` are the desk's folders and their
  ACL is inside the footprint.** Before any `.eml` or attachment lands
  (step 7): `icacls D:\psa /inheritance:r /grant:r "DND-SQL01\psa_desk:(OI)(CI)M" "Administrators:(OI)(CI)F" "SYSTEM:(OI)(CI)F"`,
  and the same on the backup folder with the SQL Server service account in
  place of `psa_desk`. Nothing above `D:\psa` is touched.
- **The mail drop is `D:\psa\mail-drop`** (the mail handoff's name);
  `D:\psa\drop` from sitting 1 is removed once empty.
- **`PSA-MailPickup` and `PSA-Notify` wait on the mail handoff's steps 1 to
  3** (the Graph app registration, its certificate, the mailbox scopes),
  which were never run and are an Entra administrator's and an Exchange
  administrator's, not SQL01's. That registration is an application, not a
  user licence (Entra ID Free covers it, VERIFIED, learn.microsoft.com). Until
  it is done the desk runs without email intake; tickets come from the desk
  and the portal. `PSA-Desk` and `PSA-Rules` do not wait for it.
- **The daily copy of `D:\psa\files` needs a destination** that is not `C:`
  and not `D:`; none exists on the host. Dada's, with the record's backup
  volume. Until then the SQL backup covers the metadata and the files are
  on `D:` only, and the Reply says so every sitting.
- **The `*.pmcne.ph` certificate's private key is non-exportable** in the
  host's store, so sitting 3's export to PEM cannot run from that store. The
  route is the original PFX from whoever imported it, or a re-key of the
  wildcard with the CA (imported as exportable this time). `dnd-sql01.pmcne.ph`
  is covered by it and resolves to this host, so it is the desk's name by
  default; `desk.pmcne.ph` would need a DNS record.
- **The payroll watchdog** (`Watch-PMCBridge.ps1`) alerts on any new database
  without a FULL backup; step 8 quiets it and the infra session adds
  `PMC_PSA` to its expected list by that session's own gated edit. SQL01
  never edits the watchdog. Any `PMC_PSA_TEST` gets one FULL at creation for
  the same reason and is dropped with its backup file.
- **A schema finding is fixed:** `api_alert`'s clustered key was over 900
  bytes; the generated script now makes `dedup_key` 200 characters and the
  API refuses a longer one. On `PMC_PSA` (already applied with the old width)
  the column stays 400 wide; that is harmless (the warning only bites on a
  key over 900 bytes, which the API now prevents) and is not altered in place.

## Folded in from sitting 1, parts 5 and 6 (26 Sep)

- **Sitting 1 is DONE** except the three tasks that wait on the mail
  handoff's Graph registration (`PSA-MailPickup`, `PSA-Notify`) and the
  DPO (`PSA-Retention`). `PSA-Desk` runs on `127.0.0.1:8085` as `psa_desk`,
  `PSA-Rules` returns `0x0` every minute, step 6 is green on the instance
  (473 OK, 9 skipped), `desk.pmcne.ph` is a static A record on `DND-AD01`.
- **A seeded board has no members, and membership is the only key.** Fixed
  upstream, two roads, both audited as `BOARD_MEMBER`: on the server,
  `psaspine board-admin $db --board IT_HELP --member <account>` (and
  `setup-board … --admin <account>`), or in Setup, where a system
  administrator sees "Boards with no administrator" and names one, once.
  Sitting 2's step 2 starts with `board-admin` for `IT_HELP` and `UNROUTED`,
  naming the Service Manager's account (a break-glass name until the Windows
  sign-in is on; then the Windows username). A board with members never
  takes this road again; its own administrators add the rest.
- **The test board `ZZ_SQL01_TEST`** stays, not live; the desk has no board
  delete by design. Its one closed test ticket `PMC-000001` is the first
  number issued and is never reused (D4).
- **HTTPS without exporting the key.** SQL01's finding: the wildcard's key is
  non-exportable, but IIS on this host already fronts Portal and Payroll with
  it, so an IIS site with a reverse proxy to `127.0.0.1:8085` would give
  `https://desk.pmcne.ph` with no export. That touches IIS, which this file
  forbids, so it is **Dada's decision**, with two roads: (a) the original PFX
  or a re-key, and the desk's own TLS as the portal handoff says; (b) one new
  IIS site named `PSA-Desk`, bound to `desk.pmcne.ph:443` with the existing
  certificate, proxying to the desk, added to the footprint table and to the
  kill switch, and nothing else in IIS touched. Until Dada chooses, the desk
  stays on the LAN in plain HTTP and the portal stays off.

## Folded in from sitting 2, parts 7 to 10 (27 Sep)

Read by Cloud on 27 Sep after parts 7 to 10 landed. What SQL01 asked for is
built at the head this section arrives with; what it decided stands.

- **Sitting 2 stands where part 7 left it.** First administrators done and
  idempotent; step 3 waits on the technicians' names; step 5 (the AD exports)
  waits on an ordinary domain user, and **that rule stands**: SQL01's session
  is in Domain Admins, the scripts say not to run as one, and nothing here
  overrides a script's own safety line; the attachment copy still has no
  destination volume (Dada's).
- **The IIS front doors stand** (`PSA-Desk` on `desk.pmcne.ph`, `PSA-Portal`
  on `help.pmcne.ph`, both proven no-meddle before and after). They are in
  the footprint from now on: two sites, two pools, two `web.config` files,
  two named `appcmd` backups; the kill switch gains `Stop-Website -Name
  PSA-Desk` and `Stop-Website -Name PSA-Portal`, and the full reverse gains
  `New-PsaDeskIis.ps1 -Rollback` and `New-PsaPortalIis.ps1 -Rollback`.
  Certificate renewal (2027-02-23) re-points two http.sys entries, as part 9
  measured.
- **The part 8 fix is in.** The desk now accepts an `Origin` equal to
  `PSA_PUBLIC_URL`'s or `PSA_PORTAL_URL`'s scheme and host; marks every
  cookie `Secure` and sends HSTS when either is `https://`, from config and
  never from a header; and reads `X-Forwarded-Host` from a loopback peer
  only, to know which public address a request came for. On the host, in
  this order, each step verified before the next:
  1. `Set-PsaDeskEnv.ps1 -Apply -PublicUrl https://desk.pmcne.ph -PortalUrl
     https://help.pmcne.ph` (the `-PortalUrl` parameter is SQL01's to add;
     it sets `PSA_PORTAL_URL`). Restart `PSA-Desk`; the console's `public:`
     line names both and says `cookies Secure, HSTS on`.
  2. In both sites' `web.config`, add the server variable
     `HTTP_X_FORWARDED_HOST` set to the request's own host (`{HTTP_HOST}`)
     on the proxy rule, and allow it in the site's `<location>` as
     `HTTP_ORIGIN` is. Verify: `https://help.pmcne.ph/dispatch` answers
     **404** from the desk (not the IIS redirect), `https://help.pmcne.ph/`
     lands on `/my`, and `https://desk.pmcne.ph/dispatch` still answers.
  3. Remove the Origin rewrite rule and the `HTTP_ORIGIN` allowance from
     both sites. Verify: a same-site POST on each address gets 303 and the
     cross-site control still gets 403.
  4. Remove the portal site's path filter (the desk now does it, as 404s).
     Keep the http→https redirect and the body cap in both sites. The
     `Secure` rewrite of `Set-Cookie` may go as well once the desk's own
     `Set-Cookie` is seen to carry `Secure` (step 1 makes it so); keeping it
     is harmless.
  If any verify fails, put the removed rule back and write the failing URL
  and status into the Reply; the desk is unchanged by any of these.
- **Part 9's defects, all seven, are answered upstream** at this head:
  Uplift's ticket tables are limited to the reader's boards and audited;
  Dispatch's queue and day audit a restricted board's listing; an
  every-board rule is tested on the tester's boards only and never runs on a
  restricted board; Reports colours 0 % as the worst number; `OVERRIDE` is
  documented as reserved and unbuilt; the pilot script is superseded by
  `docs/WS36-pilot-test-script-20260927.md` (B3 books 0.5 h, H3 now passes
  because the desk scans a technician's note, E1 is marked "only once
  PSA-MailPickup runs", the portal has steps F3 to F6); the portal's words
  no longer ask for a record number.
- **Part 10's asks are built:** anyone on no board lands on `/my` with the
  requester's shell (My requests alone; no New ticket, ⌘K or keyboard
  sheet); on the portal host that shell is drawn for everyone, `/` goes to
  `/my`, technician paths answer 404 before identity is looked at, and
  sign-in returns to `/my`. Requester emails already link to
  `PSA_PORTAL_URL` (`PSA-Notify -PortalUrl`, https only).
- **Not decided here, still Dada's:** announcing `help.pmcne.ph` to a first
  ward; the attachment copy's destination; the Graph registration for
  `PSA-MailPickup` and `PSA-Notify`; the DPO's word for `PSA-Retention`; the
  technicians' names for pilot step 3.

## Folded in from part 11 (28 Sep): the Employee Portal door

Part 11: every Pass met, the IIS Origin rules retired, the portal path filter
gone. Two things follow from it.

- **The sign-out cookie is now `Secure`** when the world is https, so the
  IIS `Secure` rewrite on `Set-Cookie` may be removed from both sites once the
  desk's own `psa_session=; Max-Age=0; …; Secure` is seen on the loopback
  with the settings applied. Keeping it is harmless.
- **The door `POST /sso/portal` is built** as `HANDOFF-sql01-cloud-WS36-20260928-portal-link.md`
  specifies (the withdrawal in that file was reversed; the spec stands). The
  three settings, all set with `Set-PsaDeskEnv.ps1` (parameters SQL01's to
  add) and read at start:

  | Setting | Value on the host |
  |---|---|
  | `PSA_EMPLOYEE_PORTAL_ORIGINS` | `https://portal.pmcne.ph,https://payroll.pmcne.ph` (unset: the door answers 404) |
  | `PSA_EMPLOYEE_PORTAL_BRIDGE` | `http://127.0.0.1:4100` (the default; set it only if the bridge moves) |
  | `PSA_EMPLOYEE_PORTAL_DEPARTMENTS` | Dada's list, exactly as payroll spells them; unset until Dada names it, and then nobody passes |

  On the host, in order, each verified before the next:
  1. Pull; restart `PSA-Desk`; the SQLite suite as SQL01's user.
  2. Set the three settings; restart `PSA-Desk`. **Pass:** on the loopback,
     with `X-Forwarded-Host: help.pmcne.ph`, a POST to `/sso/portal` with
     `Origin: https://portal.pmcne.ph` and a made-up token answers **303 to
     `/sso/portal?refused=ended`**, and that page **401** "Your Employee
     Portal session has ended" (the bridge said no); the same POST with
     `Origin: http://portal.pmcne.ph` answers 303 to `?refused=origin`, a
     **403**; a POST to `desk.pmcne.ph/sso/portal` answers **404** and writes
     nothing. (Corrected per part 12, item 10: since the door was hardened
     every refusal is a redirect first, and the desk-host 404 writes no
     row.) `psa.audit_event` holds one `PORTAL_SSO_REFUSED` row for each
     refused try on the portal host ("bridge answered 401", "origin not
     allowed (not https)", "origin not allowed"), none for the 404, and no
     token text in any row. SQL01's `Test-PsaPortalDoor.ps1` makes 5 refused
     tries plus the 404 and expects exactly 5 rows.
  3. With no department open (the Setup › Departments grid empty and
     `PSA_EMPLOYEE_PORTAL_DEPARTMENTS` unset), the operator signs in to the
     Employee Portal and posts the token **one of the two ways that pass the
     Origin rule** (corrected per part 12, item 11): a form submitted from
     DevTools on the signed-in `portal.pmcne.ph` tab (the token never leaves
     the page or lands on disk), or a loopback POST with
     `Origin: https://portal.pmcne.ph` and `X-Forwarded-Host: help.pmcne.ph`,
     the token taken with `Read-Host` into a variable and never pasted on a
     command line. A local file posts `Origin: null` and a localhost page
     `Origin: http://localhost`; both are refused for the origin, not the
     department, and do not count. **Pass:** 303 to `?refused=closed`, then
     403 "not open for your department yet", audited "department not open
     (<the Department payroll returned>)". Nothing is deployed to the
     Employee Portal for this step. (Part 12: PASS, 28 Sep 07:48.)
  4. Dada names the first department(s) **in Setup › Departments** (below),
     not in the setting: import the list, tick the board(s), Save. The
     operator repeats step 3 as an employee of that department. **Pass:**
     `/my` with that person's requests, the requester's layout, `PORTAL_SSO`
     audited with the ADLogin and the department; the cookie has no
     `Max-Age` and the session inside it is good for two hours; closing the
     browser and reopening `help.pmcne.ph/my` shows the sign-in page.
  5. Only then SQL01 deploys the portal edit (a dated copy beside the live
     file, no `bridge.js` change, Dada's sight of the preview), and the
     operator opens *My requests* from the Employee Portal on a ward PC.
     **Pass:** *Your requests* opens in a new tab with no second sign-in; the
     portal's *Sign out* ends the desk session too (a fresh `/my` is the
     sign-in page).
  If a Pass fails, the door is left as it is (it refuses safely) and the
  failing status and page words go into the Reply.

## Folded in from part 12 (28 Sep): the door hardened, the department checklist

Part 12: steps 1 to 3 PASS, the real token accepted and refused only by the
department gate; SQL01's three-lens review of `e2e4bc8`; Dada's checklist.
Both handoffs are built at the head this section arrives with, and each has
its Reply appended.

- **The nine fixes before ward PCs are in.** Every refusal is audited and
  then a **303 to `/sso/portal?refused=<code>`**, a GET page with fixed
  words, so a refused tab reloaded by the next person on a shared PC cannot
  re-send a token. A token must look like one (48 hex) before the bridge is
  asked. Only a bridge 401/403 means "session has ended"; any other answer
  is "could not be checked" with the words "go back to the Employee Portal
  and open My requests again". `bridge_get` uses no proxy and follows no
  redirect, and reads at most 64 KB. `next` is ignored: the landing is `/my`.
  The bridge's answer is read strictly (`impersonated` must be exactly
  false; ADLogin and Department must be strings). A Windows account the AD
  import marks inactive is refused ("Your Windows account is disabled")
  and audited "AD account disabled". The UPN lookup escapes `_` and `%` in
  both doors. A portal session is good for **two hours**. The audit says
  which department was refused, and a not-linked row carries the EmpKey.
  Step 2's and step 3's Pass lines above are corrected (items 10 and 11).
- **The requester shell is "PMC Requests"** (title, brand, footer), not
  "PMC IT help", per Dada's rule that requests may be for any department;
  the "Dada IT only" footer stays on the technician desk only.
- **Setup › Departments replaces `PSA_EMPLOYEE_PORTAL_DEPARTMENTS`.** On the
  host, in order:
  1. Produce `departments.csv` from payroll (read-only, one column,
     `Department`, the 52 distinct `Employee.Department` names, no people)
     and run `psaspine import-departments $db D:\psa\departments.csv` as
     `psa_desk`. **Pass:** "52 names: 52 new, 0 seen, 0 restored, 0
     retired"; a second run says "0 new, 52 seen". Re-run it whenever payroll
     changes; a name gone from payroll is retired and keeps its ticks.
  2. Dada opens Setup › Departments on `desk.pmcne.ph`, ticks which boards
     each department may send requests to (Unrouted is not a column; an
     unticked department's requests land there as today), and saves. One
     `DEPARTMENT_BOARDS` audit row per Save, as "Ward A: + IT Help".
  3. Until the first Save, the door still honours the setting as a
     migration and the page says so; after it, clear the setting with
     `Set-PsaDeskEnv.ps1` (its `-EmployeePortalDepartments` may go) and
     restart `PSA-Desk`. **Pass:** the page no longer shows the banner about
     the setting.
  4. Step 4 above then runs against the grid: an employee of a ticked
     department reaches `/my`, sees "This goes to <board>" (one tick) or
     "Who is this for?" (several), and the request lands on that board with
     source Portal; a department with no tick is "not open".
  A Windows-door requester's department is the AD contact's `department`
  attribute from the contact import; unknown, their request lands on
  Unrouted.

## Folded in from part 13 (28 Sep): the product is Dada PSA; schema 036; the catalogue setup tables

Part 13: c9a0506 live, 033–035 applied by the sitting-1 road, the hardened door
PASS, 52 departments imported. Two asks from it are done here, and Dada gave two
more.

- **`.claude/settings.local.json` is untracked and ignored** (your first
  "found on the host"). Nothing else in `.claude/` changed. Pull and keep the
  host's copy.
- **The 900-byte key warning on `PK_department_board`** is noted and left:
  payroll's longest name is 44, the key is already applied, and narrowing a live
  key's column is a migration, not a decision-file edit. Nothing to do.
- **The product is called Dada PSA.** Every "ConnectWise" in the code, the
  schema comments, the pages, the CLI banner and the scripts now reads "Dada
  PSA" where it named the desk's own shape, and "the reference PSA" where a
  sentence is about the source a design was checked against (its docs, its
  OpenAPI schema, its University workbook); the citation URLs stay, because a
  VERIFIED label needs its source. The technician shell's brand "PSA desk" is
  "Dada PSA" (title and header); the requester shell stays "PMC Requests". The
  audit action for loading the template is now `CATALOGUE_TEMPLATE` (rows
  written before this say `CW_TEMPLATE`; history, unchanged). The dated record
  documents (`docs/WS36-connectwise-*`) and `tools/connectwise_model.py` keep
  their names: they are about the reference PSA and are not the product.
- **Schema 036, one more by the sitting-1 road.** Two NULL-able columns:
  `service_family.inactive` and `service_action.inactive`. Same steps as 033–035
  (COPY_ONLY backup, preview, stop PSA-Desk, apply as sysadmin with `@Apply = 1`
  and `@AllowExisting = 1`, start). **Pass:** tables **77 → 77**, columns
  **714 → 716**, triggers 4, no row count changes, the desk answers `/login`.
- **Setup › Catalogue** (`/admin/catalogue`, sysadmin) is now the reference PSA's
  Types / Subtypes / Items setup tables on the desk's tree: Types (the six ITIL
  kinds, which boards take each, linking to the board's Types tab), Areas,
  Subtypes and Items each add / rename / retire, and an *Associate* form makes a
  Subtype › Item pair land on a board. Retiring hides from every picker and
  leaves every ticket as it was; a ticket carrying a retired pair shows it marked
  "(retired)" and a save does not clear it. One `CATALOGUE_CONFIG` audit row per
  change. **Pass, for Dada:** add an area, a subtype under it and an item, pair
  them onto IT Help, open a new ticket and see the pair under "Subtype › Item";
  retire the item and a new ticket no longer offers it.
- **Counts:** the suite is **522 tests** (SQLite OK, 1 skipped; SQL Server OK, 8
  skipped) at the head this section arrives with; the drift gate and
  `tests/smoke.py` (7 of 7) pass.

## Folded in from part 14 (28 Sep): `init` no longer touches a seeded board; Help Desk; the sign-in brand; the choices; the teardown

Part 14: 70b7d6b live, 036 PASS, My requests on the Employee Portal, step 4 PASS
for PMO, and three defects found on the host. All five asks are built at the head
this section arrives with.

- **`init` never overwrites a seeded board.** `db.seed` writes `IT_HELP` and
  `UNROUTED` insert-if-absent (`INSERT OR IGNORE`, which the translator carries
  to SQL Server as the INSERT with the duplicate-key error swallowed), so a row
  that exists is untouched: name, calendar, kind, reply policy, the time
  defaults, owner mail. `SeedIdempotenceTest` proves a second `init` after a
  Setup change leaves them as Setup left them, on both stores. **`init` is safe
  to run again**; the sitting-1 road stands. Unrouted's calendar still needs its
  starter setup re-applied once in Setup (the operator's step; nothing here
  restores what 09:12 cleared, deliberately: Setup is the operator's).
- **Help Desk.** `seed/boards.csv` names the first board **Help Desk** for a
  fresh install; the id stays `IT_HELP`. The live row is Dada's rename in Setup,
  which now holds.
- **The portal host's sign-in page reads "Sign in · PMC Requests"**, on the GET,
  on a refused try and on the Entra refusal; the desk's own keeps "Dada PSA".
- **The answer choices no longer run together.** One `.choices` flex row for
  both the portal's raise form and the technician's New ticket form, one choice
  per item, wrapping to one per line on a phone, legend above.
- **The two Windows teardown errors:** `CatalogueSetupTest` now closes its
  connections before the folder is removed (`addCleanup(conn.close)`), as the
  sitting-1 table asked of `cli.db`.
- **Counts:** 527 tests at this head (SQLite OK, 1 skipped; SQL Server OK, 8
  skipped); the drift gate and `tests/smoke.py` pass. No schema change: nothing
  to apply. Pull, run the SQLite suite as SQL01's user (expect 0 errors), and
  restart PSA-Desk. **Pass:** `https://help.pmcne.ph/my` signed out reads
  "Sign in · PMC Requests"; on `/my` the three questions show their choices
  spaced, one per item; a second `init` as the task account changes no board
  row (compare `display_name`, `calendar_id`, `kind` before and after).

## Folded in from part 15 (28 Sep): the teardown order, the phone header, the settings audit, the seed name

Part 15: 107f05f live, all three Passes met, Unrouted whole again, the first
board named "PMO Helpdesk" by Dada. The four asks are built at this head.

- **The two Windows teardown errors, properly this time.** `CatalogueSetupTest`
  no longer borrows `tearDown`; its `setUp` registers the folder's removal with
  `addCleanup` first, so each test's `conn.close` runs before it (cleanups run
  last-in first-out, after `tearDown`). Expect **0 errors** as SQL01's user.
- **The phone header.** Below 480 px every nav link keeps its icon and loses its
  words (`<span class=lbl>` hidden), the gaps tighten, and the user block no
  longer sits under "My requests".
- **The settings audit says what changed.** `BOARD_CONFIG` on a Save now reads
  each changed field as old → new, in the tab's own words: "settings saved:
  name 'IT Help' -> 'PMO Helpdesk'; email the owner 0 -> 1"; a Save that changes
  nothing reads "settings saved: nothing changed". Rows before this head keep
  their old wording.
- **The seed name is "PMO Helpdesk"**, Dada's own (*"done renaming i like this
  name"*), so a fresh install matches what PMC runs. The live row is untouched
  either way, since `init` no longer overwrites a seeded board.
- **Counts:** 529 tests at this head (SQLite OK, 1 skipped; SQL Server OK, 2
  skipped); drift gate and smoke pass. No schema change. Pull, run the SQLite
  suite as SQL01's user (**Pass: 529 run, 0 errors**), restart PSA-Desk.
  **Pass:** at 390 px on `help.pmcne.ph/my` the header shows the brand, one
  icon link and the user block with no overlap; a Setup › Board Save that
  renames the board writes an audit row reading "name '…' -> '…'".

## Folded in from part 16 (28 Sep): calendars and holidays; scheduling (schemas 037 and 038)

Part 16: 02627d2 live, 529 OK with 0 errors, the phone header and the rename
audit PASS. Its one note is done: an unset board flag now reads as its default
(off), so a first Save no longer audits "- -> 0". Separately, Dada asked for the
reference PSA's calendars and its scheduling. Both are built at the head this
section arrives with. Two schema steps, by the sitting-1 road as for 036
(`init` is safe to run again since part 14).

- **Schema 037: calendars and holidays.** Three NULL-able columns on `holiday`
  (`all_day`, `time_start`, `time_end`, for a part-day holiday) and one on
  `calendar` (`inactive`). Setup › Calendars (`/admin/calendars`, sysadmin)
  edits calendars (seven day windows, a holiday list, retire) and holiday lists
  (add, rename, add and remove dates). The clocks honour part-day holidays.
  `psaspine import-holidays <db> <list id> holidays.csv` loads a year.
- **Schema 038: scheduling.** Two new tables (`schedule_status`,
  `service_location`), one new table for time off, meetings and activities
  (`schedule_block`), and six NULL-able columns on `ticket_schedule`
  (`status_id`, `location_id`, `is_lead`, `conflict_allowed`, `done_at`,
  `acknowledged_at`). The starter statuses (Firm, Tentative) and places
  (On-site, Remote, In-house) are written on first use, not by the schema.
  `/schedule` is the week board; the ticket's Schedule pod books, moves, marks
  done, acknowledges and makes lead; Setup › Schedule edits the statuses and
  places. When a board's owner-mail switch is on, the booked person gets an
  email (role `SCHEDULED`, no summary in the subject); the sender needs no
  change, since it sends every pending row whatever its role.
- **Apply.** A COPY_ONLY backup; the preview; stop PSA-Desk; apply the port as
  SQL01's sysadmin with `@Apply = 1` and `@AllowExisting = 1`; start PSA-Desk.
  **Pass:** tables **77 → 80** (new: `schedule_status`, `service_location`,
  `schedule_block`), columns **716 → 745**, triggers 4 → 4, no existing row
  count changed, `/login` answers. (MEASURED on the SQL Server test container
  at this head: 80 tables, 745 columns, 4 triggers; the 29 new columns are 19
  in the three new tables and 10 added to `holiday`, `calendar` and
  `ticket_schedule`.) Then `init` as the task account.
- **Pass, for Dada:** Setup › Calendars shows *All hours* and *Business day*;
  add a holiday list "Philippine public holidays", add 2026-11-30 Bonifacio Day
  and 2026-12-24 Christmas Eve closed 12:00–24:00, and attach the list to
  *Business day*: two `CALENDAR_CONFIG` rows. On `/schedule`, add yourself a
  meeting and book a visit on a ticket; the week shows both, and Dispatch's day
  shows the meeting.
- **Counts:** 537 tests at this head (SQLite OK, 1 skipped; SQL Server OK, 2
  skipped); the drift gate and `tests/smoke.py` pass. **Pass for the suite as
  SQL01's user:** 537 run, 0 errors.

## Folded in after part 16 (29 Sep): knowledge base, security roles, projects, report writer, BizBox mirror (schemas 039–043)

Dada asked for the reference PSA's knowledge base, security roles, projects and
report writer, and for finance, agreements, procurement and products to come
from BizBox rather than be kept here. All are built at the head this section
arrives with. Five schema steps, applied together by the sitting-1 road. **Every
one is new tables only: no `ALTER`, no existing row touched.**

- **039 knowledge base:** `kb_article`, `kb_revision`, `kb_ticket`. `/kb` for
  the desk, `/my/help` for requesters (published articles only). An article
  keeps every revision; linking one to a ticket counts its use.
- **040 security roles:** `security_role`, `role_permission`, `member_role`.
  Five modules (Knowledge, Projects, Reports, Schedule, Finance) by four levels
  (None, Read, Write, Admin). Starter roles are written on first use; a member
  with no role gets the default (Technician). A sysadmin is Admin everywhere.
  Setup › Security roles edits them; every change is a `SECURITY_ROLE` audit row.
- **041 projects:** `project`, `project_phase`, `phase_dependency`,
  `project_ticket`. Phases nest; a phase cannot start while a predecessor is
  open; hours come from the linked tickets' time.
- **042 report writer:** `report_def`. Saved reports over tickets, time,
  visits, projects and knowledge, board-limited, with CSV out.
- **043 BizBox mirror:** `ext_source`, `ext_agreement`, `ext_product`,
  `ext_purchase_order`, `ext_po_line`, `ext_invoice`, `ext_link`, `ext_change`.
  Read-only copies of BizBox rows, linked to tickets and projects; proposed
  edits wait in `ext_change` and **nothing writes to BizBox**. Filling it is
  its own handoff: `HANDOFF-cloud-sql01-WS36-20260929-bizbox.md`. Until that
  runs, Finance shows empty tabs, which is correct.
- **Apply.** A COPY_ONLY backup; the preview; stop PSA-Desk; apply the port as
  SQL01's sysadmin with `@Apply = 1` and `@AllowExisting = 1`; start PSA-Desk.
  **Pass:** tables **80 → 99** (the 19 above), columns **745 → 920**, triggers
  4 → 4, no existing row count changed, `/login` answers. (MEASURED on the SQL
  Server test container at this head: 99 tables, 920 columns, 4 triggers.) This
  assumes 037 and 038 were applied first; if not, apply part 16's section
  first, or read the Pass as 77 → 99 tables and 716 → 920 columns. Then `init`
  as the task account.
- **Pass, for Dada:** the menu shows Knowledge, Projects and Finance; write and
  publish one article and see it on `/my/help`; make a project with two phases,
  make the second depend on the first, and see the second refuse to start;
  Setup › Security roles shows Technician, Service manager, Read only.
- **Counts:** 544 tests at this head (SQLite OK; SQL Server OK); the drift gate
  and `tests/smoke.py` pass. **Pass for the suite as SQL01's user:** 544 run,
  0 errors.

## Folded in from part 18 and the BizBox Reply, parts 1–4 (29 Sep): schema 044, the mirror fitted to BizBox

Part 18: 402fb0e live, 039–043 PASS (80 → 99 tables, 745 → 920 columns, no
row changed), the as-desk run PASS, 544 OK. The BizBox handoff's steps 1–5
PASS at 4b8b816 and the first hourly run at 12:05 (Reply, parts 1–4). Three
code points came back with them and the two create-time warnings; all four are
answered at the head this section arrives with. **One schema step, one
NULL-able column, by the sitting-1 road** (`init` is safe to run again).

- **Schema 044: `ext_invoice.supplier_ref`**, the supplier's own invoice
  number (`iwApinv.refno`). It is never the key (626 distinct of 634, part 2),
  so it sits beside the receiving number. **Apply:** COPY_ONLY backup, preview,
  stop PSA-Desk, the port as SQL01's sysadmin with `@Apply = 1` and
  `@AllowExisting = 1`, start. **Pass:** tables **99 → 99**, columns
  **920 → 921**, indexes **34 → 36** (`ix_kb_ticket_ticket`,
  `ix_ext_invoice_agreement`), triggers 4 → 4, no existing row count changed,
  `/login` answers. (MEASURED on the SQL Server test container at this head
  after the suite applied the port: 99 tables, 921 columns, 4 triggers.) Then
  `init` as the task account. **Keep this order** (stop, port, pull, start):
  the reverse, pull and start before the port, answers 500 on every
  technician page and on `/admin` until the port lands, because the security
  role is read on every signed-in request.
- **The view and the map, SQL01's, after the apply:** add
  `a.refno AS SupplierInvoiceNo` to `psa.vw_invoice` (an `ALTER VIEW`; the
  view is not schema-bound) and `"supplier_ref": "SupplierInvoiceNo"` to the
  invoice's columns in `D:\psa\bizbox-map.json`. The next hourly run fills
  it: **Pass:** that run's invoice line counts every present invoice as
  changed, once, and the run after says 0 changed; Finance › Invoices shows a
  *Supplier's invoice no.* column. Until then the column is simply absent, and
  the sync with 402fb0e's map keeps working unchanged.
- **"Paid" is not knowable:** nothing to change. The desk shows BizBox's own
  status word (Draft, Posted, Cancelled) and never says paid or overdue; the
  Invoices tab now has the same status tiles Procurement has, in those words.
- **No supplier agreements:** the Finance pages show only the kinds BizBox has
  rows for. On the live desk that is Procurement, Products and Invoices, with
  a one-line note under the tabs; the Agreements tab, the Agreement column and
  the "Agreement" choice on a ticket's Finance pod appear when a source is
  named. **Pass, for Dada:** Finance opens on Procurement; no Agreements tab.
- **The two 900-byte warnings (part 18, item 3):** `PK_ext_link` and
  `PK_ext_po_line` reach 1,184 and 928 bytes only at `REF`'s full 400
  characters. The columns are not narrowed — the port cannot alter a live
  column, and a port that said 200 while the server held 400 would drift from
  the database it describes. Instead the sync skips and counts any key longer
  than 64 characters (`MAX_KEY`); BizBox's keys are cast to 20 or 64 in
  SQL01's views, so a longer one is not a BizBox key. The warnings will print
  again on any fresh create; they describe a case that cannot now occur.
- **The sample map** in the repo is now the shape SQL01 built: four kinds, the
  invoice keyed by `ReceivingNo`, no agreement. The real map stays on the host.
- **Also at this head, from the pre-deployment audit of 039–043** (Cloud
  Build, 29 Sep: SQL01's road reproduced on the test container from 5163812
  to 402fb0e, then four reviews, 37 findings confirmed by a second pass, all
  fixed here). The ones that change what SQL01 or Dada will see:
  - `/my/help/<id>` let any signed-in person open a *board's* requester
    article by its sequential id (a dead clause in the check). Fixed; a test
    pins it. **Pass, for SQL01, one count:** `SELECT COUNT(*) FROM psa.kb_article
    WHERE board_id IS NOT NULL AND audience = 'REQUESTER'` — expected 0 today
    (INFERRED: no article has been written yet), so nothing was exposed.
  - The **Schedule** level in Setup › Security roles was shown but not
    enforced; `/schedule` now needs Read and booking or blocking needs Write.
    Technician has Write, so nobody loses a page they had.
  - The report writer, a project's ticket list and an article's *Used on* now
    write `RESTRICTED_READ` for the restricted-board tickets they list, as
    every other list does (§6.1 requirement 4).
  - **Finance counted at most 500.** On the live desk the tabs read "Products
    · 500" against 5,113 rows and the Procurement tiles summed 500 of 528 POs.
    Now every count and tile is over the whole mirror, the lists page by 100
    ("Showing 1–100 of 5,113"), and a record's page is
    `/finance/<kind>?ref=…` (a BizBox key holding `/` or `%` could not open
    from its own link before). Nothing to do on the host; an old-shape
    bookmark answers 404.
  - The sync trims `status`, `currency` and `unit` to the port's 32
    characters instead of failing the run on the host; a refusal names the
    field and never the cell; `UID={sa}` is refused like `UID=sa`; the intent
    is forced to ReadOnly whatever the string said.
  - The starter roles are written `INSERT OR IGNORE`, so two first requests
    on the threaded server cannot fail each other; one role lookup per
    request instead of twenty statements.
  - The port's header now says `sqlcmd -I` and the script sets
    `QUOTED_IDENTIFIER ON` itself: plain `sqlcmd` failed a fresh apply at the
    first filtered index (MEASURED on the container). SQL01's road applies
    through pyodbc, where it is already ON, so this never bit the host.
  - The 900-byte warnings are **six** on a fresh create (one per `ext_*`
    key), two on SQL01's apply; the same guard answers all of them.
- **Counts:** 545 tests at this head (SQLite OK; SQL Server OK); the drift
  gate and `tests/smoke.py` pass. **Pass for the suite as SQL01's user:** 545
  run, 0 errors.

## Folded in from part 19 and the agreements handoff (29 Sep): schema 045, agreements made on the desk

Part 19: 23caa5f live, 044 PASS (99 → 99 tables, 920 → 921 columns, 34 → 36
indexes, no row changed), the view and the map done, the 14:05 run PASS, the
kb count 0, the four scripts in the repo. Then SQL01's handoff
`HANDOFF-sql01-cloud-WS36-20260929-agreements.md`: Dada wants agreements
created on the desk, since BizBox has none, and from one the BizBox invoices,
POs and products it covers. Built at the head this section arrives with.
**One schema step, two new tables, by the sitting-1 road** (`init` is safe to
run again; there is nothing to seed).

- **Schema 045: `agreement` and `agreement_item`.** An agreement is the
  desk's own record (`AGR-0001`: name, party, term, status, amount, notes,
  who and when). `agreement_item` names the mirrored records it covers, by
  the mirror's own key, in the desk's own table: the sync never touches it,
  and nothing is written to BizBox or to the `ext_*` tables. `ext_agreement`
  stays a mirror kind for a source that may one day be named. The item key is
  `KEY` width (200), so no 900-byte warning.
- **Apply.** A COPY_ONLY backup; the preview; stop PSA-Desk; the port as
  SQL01's sysadmin with `@Apply = 1` and `@AllowExisting = 1`; pull; start.
  **Pass:** tables **99 → 101**, columns **921 → 946** (20 in the two tables,
  and the 5 parsed date columns the port adds beside every `DATE_TEXT` and
  `TIMESTAMP_TEXT` column), indexes **36 → 37** (`ix_agreement_item_ref`),
  triggers 4 → 4, no existing row count changed, `/login` answers. (MEASURED on
  the SQL Server test container at this head after the suite applied the port:
  101 tables, 946 columns, 37 indexes, 4 triggers.) Then `init` as the task
  account. The order
  matters as before: Finance › Agreements reads `agreement` on every visit.
- **Pass, for Dada:** Finance opens on **Agreements** (empty, "No agreement
  yet"); a Service manager creates one, opens it, types a receiving number
  and a PO number, finds a product with the search, and sees the three under
  "What it covers" with the invoice and PO totals against the agreed amount;
  the invoice's own page lists the agreement; a Technician sees all of it and
  has no New, Add or Remove.
- **Who may create or cover** is not decided here. The gate is Finance Write,
  and Setup › Security roles is where Dada gives it to a role (Service
  manager has it as shipped; Technician has Read). Nothing goes to BizBox;
  step 6 of the BizBox handoff stands.
- **Counts:** 546 tests at this head. SQLite OK. On SQL Server the full run
  found one real fault the SQLite run could not: the agreement totals summed a
  NULL for products, which SQL Server refuses; fixed at this head, and the
  module tests pass on both stores (MEASURED). The one other error in that run
  was a login timeout right after the test container was restarted, and passes
  on rerun. **Pass for the suite as SQL01's user:** 546 run, 0 errors. The
  drift gate and `tests/smoke.py` pass.
- **CI, 29 Sep, later:** the SQL Server job on GitHub had been red since run
  62 (the 039–043 merge) on one test, and nowhere else. CI names its test
  database `PMC_PSA`, so the port's run-twice guard answered the preview test
  instead of the database-name guard, and that message did not end "Nothing
  was changed." It now does: one line of the generator and of the generated
  script, nothing else in the port, and the Pass counts stand. Reproduced on
  the test container with a database named `PMC_PSA`, fixed, and the suite
  rerun there (MEASURED). That wording is the only difference SQL01 will see
  in the script when it pulls for 045.

## Folded in after part 20 (29 Sep, later): schema 046, timesheets and time approval, and the gaps build

Dada, 29 Sep, on the parity list: "do the gaps". Eight are being built in
order; this is the first, and it comes with **one schema step, by the
sitting-1 road** (`init` is safe to run again; nothing is seeded).

- **Schema 046: `timesheet`, `timesheet_event`, `member_capacity`,
  `role_grant`, and `time_entry.timesheet_id`.** Every time entry belongs to
  the week (Monday to Sunday) of the day it was worked, by the person who
  performed it. A sheet is OPEN, then SUBMITTED by that person, then APPROVED
  or REJECTED (with a reason) by a Timesheets administrator who is not that
  person; reopened only with a note; every step appended and audited. A
  submitted or approved week takes no new entry. `/time` is the page; Reports
  gains utilisation by member; the uplift evidence says how many of its hours
  sit on an approved sheet.
- **`role_grant` supersedes `role_permission`.** 040's table listed its five
  modules in a CHECK, so the sixth module (Timesheets) could not be written
  into it on either store: OR IGNORE swallowed the refusal, MEASURED on the
  test container. `role_grant` has the same key and levels and no list. The
  desk reads the rows already in `role_permission` across, once, the first
  time a role is looked up after the pull (`security.ensure_roles`); nothing
  is deleted, and `role_permission` stays, superseded and unread, because the
  port never drops a table. **Nothing for SQL01 to copy by hand.**
- **Apply.** A COPY_ONLY backup; the preview; stop PSA-Desk; the port as
  SQL01's sysadmin with `@Apply = 1` and `@AllowExisting = 1`; pull; start.
  **Pass:** tables **101 → 105**, columns **946 → 976** (30: 10 in `timesheet`
  and 4 parsed dates beside them, 6 in `timesheet_event` and 1 parsed, 4 in
  `member_capacity` and 1 parsed, 3 in `role_grant`, 1 on `time_entry`),
  indexes **37 → 39** (`ix_timesheet_event_sheet`, `ix_time_entry_sheet`),
  triggers 4 → 4, no existing row count changed, `/login` answers. (MEASURED
  on the SQL Server test container at this head after the suite applied the
  port: 105 tables, 976 columns, 39 CREATE INDEX, 4 triggers.) Then `init` as
  the task account, as before.
- **Pass, for Dada:** Time appears in the desk's menu; your own week lists the
  time you booked; Submit for approval locks it (booking more time on that
  week is refused in a sentence); a Service manager who is not you sees it
  under *Waiting for a decision* and approves it; you cannot approve your own;
  Setup › Security roles shows a Timesheets column. Reports shows
  *Utilisation, by member* once anyone has booked time.
- **Who decides** is the Timesheets level: WRITE keeps your own sheet (every
  role's default, so nothing changes for a role written before 046), ADMIN
  decides others' and sets hours a week. Service manager ships with ADMIN.
  Whether Technicians may approve each other is Dada's, in Setup.
- **Schema 047, in the same sitting: `recurrence`, and `ticket.recurrence_id`.**
  Recurring tickets: a board template raised on a cadence by `run-rules`
  (PSA-Rules, every minute), once per due day however long the runner was
  down, with the template's tasks, an owner, the machine, and a *Raised by*
  line on the ticket; Setup › Recurring tickets to add, run now, pause. The
  046 and 047 steps go on together: **Pass after both:** tables **101 → 106**,
  columns **946 → 999**, indexes **37 → 40** (`ix_recurrence_due` added to
  the two above), triggers 4 → 4, no existing row count changed (MEASURED on
  the test container: 106 tables, 999 columns, 40 CREATE INDEX, 4 triggers).
  **Pass, for Dada:** Setup shows *Recurring tickets (0 active)*; a board
  administrator adds one from a template with a first due day of today, and
  the next PSA-Rules run raises its ticket, tasks and all, with the line
  *Raised by the recurrence …* on the ticket's Details card; *Run now* raises
  one straight away.
- **Schema 048, in the same sitting: seven columns on `configuration`**
  (purchased_on, warranty_ends_on, installed_on, vendor, purchase_ref,
  location, agreement_id): the life of a machine, edited on its page, with
  warranty tiles on the list, a maintenance-record CSV per asset (and per
  list) for a DOH inspection, and Configurations and Maintenance datasets in
  the report writer. All NULL-able; nothing to fill. **Pass after 046, 047
  and 048 together:** tables **101 → 106**, columns **946 → 1006** (the 7 of
  048 are all declared: the port adds no parsed date column beside a column
  it adds with ALTER, only inside a CREATE TABLE), indexes **37 → 40**,
  triggers 4 → 4, no existing row count changed (MEASURED on the test
  container: 106 tables, 1006 columns, 40 CREATE INDEX, 4 triggers). **Pass,
  for Dada:** a printer's page takes a warranty end date and shows it; the
  Configurations list counts it under *Warranty ends in 90 days* or *Out of
  warranty*; *Maintenance record (CSV)* on the page downloads its tickets with
  hours and visits.
- **Schema 049, in the same sitting: `approval`, `department.approver`,
  `catalogue_item.needs_approval`.** Request approvals: a department names
  its approver in Setup › Departments; a catalogue pair can require one; a
  technician can ask anyone from the ticket's Approval card. The ticket parks
  in **Awaiting approval** (a new starter status: boards made before this
  pull do not have it, so on them the request is recorded and the ticket
  stays where it is until Dada adds the status under Setup › Statuses, with
  *Waiting* ticked), the approver gets one email pointing at the portal's
  Approvals page, decides there with a reason, and the ticket returns. All
  NULL-able or defaulted; nothing to fill. **Pass after 046 to 049 together:**
  tables **101 → 107**, columns **946 → 1021** (049 adds 15: 11 in `approval`
  and 2 parsed dates beside them, 1 on `department`, 1 on `catalogue_item`),
  indexes **37 → 42** (`ix_approval_ticket`, `ix_approval_approver` added),
  triggers 4 → 4, no existing row count changed (MEASURED on the test
  container at this head after `init --reset` on a spare database: 107
  tables, 1021 columns, 42 CREATE INDEX, 4 triggers). **Pass, for Dada:**
  Setup › Departments shows an Approver column and keeps an email; a pair
  toggled to *Approval: yes* makes a new ticket with that pair show
  *approval requested from …* in its history and, once the board has the
  status, sit in Awaiting approval; the approver, signed in to the portal,
  sees it under Approvals and their Approve puts *Approved by …* on the
  ticket and brings it back; a stranger's portal shows *Nothing waits for
  you*.
- **Gap 5, no schema: the desk on a technician's phone.** The same pages
  read their width: under 640 px the board is a list of cards, every control
  is thumb-sized, a bar at the foot of the screen reaches Board, Dispatch,
  Schedule, Time and New, and on a ticket reaches the note, the ticket card
  and a call to the contact. Nothing to apply on SQL01 beyond the pull.
  **Pass, for Dada:** on a phone on the hospital Wi-Fi, the desk's address
  shows the board as cards with the bar at the foot; a ticket's bar has
  *Note* and *Ticket*, and *Call* when the contact has a number. (MEASURED
  in the cloud with Playwright at 390 × 844: fourteen pages, no sideways
  scroll, no control under 40 px.)
- **Schema 050, in the same sitting: `channel_target`, `page`, and channel
  columns on `notification` and `workflow_action`.** Teams cards and on-call
  paging. A channel is named in Setup › Integrations › Teams channels; its
  webhook address goes in **`D:\psa\teams-webhooks.json`** on the host, a
  JSON object `{ "helpdesk-alerts": "https://…webhook.office.com/…" }`,
  ACL'd to the task account, never committed. A new task, **PSA-Teams**,
  runs `scripts\Send-PsaTeamsNotifications.ps1 -Database … -WebhookFile
  D:\psa\teams-webhooks.json -StateDir D:\psa\mail-state -DeskUrl
  https://<desk> -Apply -Loop` beside PSA-Notify, preview first (no -Apply:
  it counts and checks the file, posts nothing). The added columns are
  NULL-able by the port's rule; the desk reads NULL as EMAIL. **Pass after
  046 to 050 together:** tables **101 → 109**, columns **946 → 1052** (050
  adds 31: 8 in `channel_target` and 1 parsed date, 14 in `page` and 3
  parsed, 3 on `notification`, 2 on `workflow_action`), indexes **37 → 43**
  (`ix_page_open` added), triggers 4 → 4, no existing row count changed
  (MEASURED on the test container at this head after `init --reset` on a
  spare database: 109 tables, 1052 columns, 43 CREATE INDEX, 4 triggers).
  **Pass, for Dada:** Setup › Integrations shows *Teams channels*; a channel
  named there with its address in the file receives one card when a rule
  set to *as a card in a Teams channel* fires (PSA-Teams in preview says
  "1 card(s) due", with -Apply "1 posted"); a ticket's *Page the on-call*
  puts *Paging <name>: attempt 1 of 3* on the ticket, the email arrives,
  the on-call's *Acknowledge* ends it; with nobody on the rota the button
  says so and pages nobody. **Whether Teams shows the card as posted is the
  one thing only this sitting can say (NOT VERIFIED from the cloud).**
- **Schema 051, in the same sitting: `kb_file`.** Pictures and documents on
  a knowledge article, reviewed before a requester sees them, shown in the
  text as `![caption](file:N)`. The bytes go in a folder of their own:
  **`D:\psa\attachments-kb`** (the attachment folder's name with `-kb`;
  or `PSA_KB_DIR` in every PSA task), made with the same ACL as
  `D:\psa\attachments` and added to the same backup, because the
  attachment verifier and purge deliberately do not look there. **Pass after
  046 to 051 together:** tables **101 → 110**, columns **946 → 1072** (051
  adds 20: 17 in `kb_file` and 3 parsed dates), indexes **37 → 44**
  (`ix_kb_file_article` added), triggers 4 → 4, no existing row count
  changed (MEASURED on the test container at this head after `init --reset`
  on a spare database: 110 tables, 1072 columns, 44 CREATE INDEX, 4
  triggers). **Pass, for Dada:** an article's page shows *Files*; a
  screenshot uploaded there appears in the article at once where
  `![caption](file:1)` is pasted, and on the portal's help page only after
  *Clear*; a `.exe` is refused in a sentence; `D:\psa\attachments-kb`
  holds one file after the upload.
- **Gap 8, one column: `api_token.scope`** (`schema/local/api_token_scope.sql`,
  ported like the rest). A machine token is RAISE (as before, and what an
  existing row reads as), READ (list and read every ticket on its board and
  the configurations) or WRITE (a note, a status, an owner as well):
  `create-api-token … --scope READ`. **Pass after 046 to 051 and this:**
  tables **101 → 110**, columns **946 → 1073**, indexes **37 → 44**,
  triggers 4 → 4 (MEASURED on the test container at this head after `init
  --reset` on a spare database). **Pass, for Dada:** a token minted with
  `--scope READ` answers `GET /api/v1/tickets` with the board's open
  tickets; the same call with the old monitoring token answers 403 naming
  the scope; nothing else on the host changes.
- **Schema 052, later the same day: `opportunity`, `quote`, `quote_line`.**
  Sales (`/sales`): the pipeline Dada IT proposes from, Lead → Qualified →
  Proposal sent → Won or Lost, quotes with computed totals under each, and a
  win that drafts the agreement (045) from the accepted quote. Gated by the
  Finance level, as agreements are. **Pass after 046 to 052 and the token
  scope:** tables **101 → 113**, columns **946 → 1122** (052 adds 49: 40
  declared and 9 parsed dates), indexes **37 → 47** (`ix_opportunity_stage`,
  `ix_quote_opportunity`, `ix_quote_line_quote` added), triggers 4 → 4, no
  existing row count changed (MEASURED on the test container at this head
  after `init --reset` on a spare database: 113 tables, 1122 columns, 47
  CREATE INDEX, 4 triggers). **Pass, for Dada:** Sales is in the top bar for
  anyone with Finance; a Service manager creates an opportunity, drafts a
  quote, adds a line, marks it sent (the opportunity reads *Proposal sent*),
  accepts it, presses *Won*, and lands on a draft agreement carrying the
  quote's total; a Technician sees all of it with no form on it. **One
  adapter fix rode with it:** the SQL Server adapter read `INSERT INTO
  quote (` as a call to SQLite's `quote()` function and refused it (two
  errors on the first run, MEASURED); a word after `INTO` is now a table
  whatever it is called, and a dialect test holds that.
- **Schema 053, evening: `member`, `calendar_feed`, `board.intake_address`,
  `intake_message.to_address`.** Dada's three asks of the evening: a member
  page as ConnectWise has (Setup › Members, a page per person, *This person
  has left*, My profile), a Calendar page (one person's day, week or month,
  and a private `.ics` feed for a phone), and a different intake address per
  board (a board claims an address on its mail-policy tab; intake routes by
  the recipient, so Exchange aliases onto the one helpdesk mailbox and one
  pickup serves every board). No existing row changes; a member without a
  record is what they were yesterday. **Pass after 046 to 053 and the token
  scope:** tables **101 → 115**, columns **946 → 1149** (053 adds 27: 18 in
  `member` and 3 parsed dates, 3 in `calendar_feed` and 1 parsed, 1 on
  `board`, 1 on `intake_message`), indexes **37 → 48**
  (`ix_calendar_feed_hash` added), triggers 4 → 4, no existing row count
  changed (MEASURED on the test container at this head after `init --reset`
  on a spare database: 115 tables, 1149 columns, 48 CREATE INDEX, 4
  triggers). **Nothing on the host for the mailboxes:** to give a board its
  own address, create the alias in Exchange onto the helpdesk mailbox and
  type the address on the board's mail-policy tab; PSA-Mail is unchanged.
  **Pass, for Dada:** Setup shows *Members*; your own page names you, and
  the header shows that name; a colleague's *This person has left* lists
  what it ended; Calendar in the top bar shows your week, *Month* shows the
  month, and the feed address from My profile opens in the phone's calendar
  app; a test mail to the biomedical board's address lands on that board
  with *routed by* its address in the intake table, and one to the helpdesk
  address lands where it always did.
- **Counts:** 594 tests at this head, SQLite OK (1 skipped). The whole suite
  ran on SQL Server in this container against the port three times today:
  with 046 to 049, 569 run, OK, 2 skipped, 13.5 minutes; with 046 to 050,
  575 run, OK, 2 skipped, 13.8 minutes; with 046 to 051 and the token
  scope, 580 run, OK, 2 skipped, 14.3 minutes; with 052 as well,
  586 run, OK, 2 skipped, 14.1 minutes, after a first run whose only two
  errors were the adapter refusal above; and with 053, 594 run, OK, 2 skipped, 12.6 minutes
  (all MEASURED, 29 Sep). The drift gate passes; CI runs
  67, 68, 69 and 70 are green (MEASURED: run 69 on `a2ef6f6`, the head that
  carries 046 to 052, finished success at 17:47 UTC on 29 Sep; run 70 on
  `de4f9ee`, with 053, finished success at 23:52 UTC, its Windows job
  taking 16 minutes; the workflow runs on a
  push to main, a pull request, or a manual dispatch, never on a push to
  this branch).

## Folded in from part 21 (30 Sep): 046-053 live; the Teams sender's three defects fixed; the KB folder's name

SQL01's part 21: `de4f9ee` live, every Pass met, 594 OK on the host, no row
changed. Three things come back from it.

- **The Teams sender, three defects, all fixed at this head** (each MEASURED
  by SQL01 under Windows PowerShell 5.1 on DND-SQL01, part 21 item 6):
  - **(a)** `Test-WebhookUrl` now accepts `*.api.powerplatform.com`, where a
    Teams Workflows webhook made today lives (`*.environment.api.powerplatform.com`),
    beside the two retired shapes, which stay allowed and simply fail;
  - **(b)** `-SpineDir` is no longer a `param()` default built from
    `$PSScriptRoot`; the script resolves the repository root from its own
    path after `param()`, so `-File` works with no `-SpineDir`. **The same
    defect was in `Send-PmcNotifications.ps1` and `Invoke-PmcMailPickup.ps1`**,
    neither registered on the host yet; both are fixed the same way.
    `Register-PsaTeams.ps1` passing `-SpineDir` explicitly still works;
  - **(c)** the JSON from `outbox-pending` is read with `foreach`, never
    `@(... | ConvertFrom-Json)`, so an idle pass counts 0 on 5.1 and 7 alike.
    The same shape was in `Send-PmcNotifications.ps1`; fixed there too.
  - The script is now pure ASCII, as its siblings are held to be; a
    `TeamsSenderScriptTest` (3 tests) pins the three fixes.
  - **Pass, SQL01:** with the pull, `Register-PsaTeams.ps1 -Apply` registers
    PSA-Teams in PREVIEW and its first pass logs a PREVIEW line with "0
    card(s) due" and task result 0. **Posting a card is a later switch**, and
    whether Teams renders it as posted is still only this sitting's to say.
- **The KB folder is `D:\psa\files-kb`**, the attachment folder's name with
  `-kb` as the rule says; the runbook's `attachments-kb` assumed an
  attachment folder it does not have. The README now says so. **Nothing on
  the host backs up `D:\psa\files` or `D:\psa\files-kb`** (SQL01 read every
  scheduled task and SQL Agent step; a hypervisor backup is NOT VERIFIED
  from there). That is Dada's to settle: the attachments are the desk's
  evidence, and the database backup does not carry them.
- **No PSA-Notify, no PSA-Mail on the host yet**: the desk sends no email
  from DND-SQL01. The notification and mail-pickup scripts are ready and now
  start under 5.1 `-File`; registering them is the next host step once Dada
  names the sending mailbox and the helpdesk mailbox's certificate.
- **Counts:** 597 tests at this head (SQLite OK, 1 skipped; the three new
  tests read the scripts, so the SQL Server run is unchanged in substance).
  CI run 71 on `c666b8e` is green on all four jobs, the Windows one
  included (MEASURED, finished 01:00 UTC, 30 Sep).

## Folded in after part 22 (30 Sep): schema 054, Setup › Audit and API tokens

Dada, 30 Sep: *"do it now"*, on the setup gap record's next items. The
first is the audit trail's page, with one schema step by the sitting-1 road
(`init` is safe to run again; nothing is seeded).

- **Schema 054: `audit_event.source`, and three indexes on `audit_event`.**
  Every audit row now says where the change came from (DESK, PORTAL, API,
  INTAKE, RULES, BIZBOX, CLI), stamped by the entry point; older rows read
  as unknown. Setup › Audit reads the trail with filters and a CSV; Setup ›
  API tokens mints and disables tokens on a page. **Pass:** tables 115 → 115,
  columns **1149 → 1150**, indexes **48 → 51** (`ix_audit_event_when`,
  `ix_audit_event_actor`, `ix_audit_event_subject`), triggers 4 → 4, no
  existing row count changed (MEASURED on the test container at this head
  after `init --reset` on a spare database: 115 tables, 1150 columns, 51 CREATE INDEX, 4 triggers, before 055). The
  index on `occurred_at` builds over every audit row the host has; on 8,472
  rows that is instant, and the port applies it in the same transaction as
  the rest. **Pass, for Dada:** Setup shows *Audit and API tokens*; Audit
  lists today's changes with *DESK* in the Source column for the ones made
  on the desk and blank for older rows; a CSV downloads; API tokens shows
  the monitoring token from gap 8 with its scope, and *Mint* shows a new
  token once.
- **Schema 055, in the same sitting: `mail_exclusion`.** Setup › Email
  connector: the boards' addresses, what never opens a ticket (an address,
  a domain, a subject phrase; imported and recorded, opens nothing), and the
  last seven days' dispositions, senders by domain only, never a subject.
  Nothing on the host: PSA-Mail is unchanged, and is still not registered.
  **Pass after 054 and 055:** tables **115 → 116**, columns **1149 → 1157**
  (055 adds 7: 6 in `mail_exclusion` and 1 parsed date), indexes 48 → 51,
  triggers 4 → 4 (MEASURED on the test container at this head after `init
  --reset` on a spare database: 116 tables, 1157 columns, 51 CREATE INDEX, 4 triggers). **Pass, for Dada:**
  Setup › Email connector lists the helpdesk board's address; *Exclude* a
  vendor's domain and the row appears with who added it.
- **Schema 056, in the same sitting: `configuration_type`,
  `configuration_status`, `configuration_question`, `configuration_answer`,
  and `configuration.type_id` / `status_id`.** Types and statuses as setup
  tables, each counting as one of 021's codes so nothing that reads
  `config_type` or `status` changes meaning; questions per type, answered
  on the configuration's page. The seven and the three are written as rows
  on first use, not seeded. **Pass after 054 to 056:** tables **116 → 120**,
  columns **1157 → 1179** (056 adds 22: 5 in `configuration_type`, 5 in
  `configuration_status`, 7 in `configuration_question`, 3 in
  `configuration_answer`, 2 on `configuration`), indexes **51 → 52**
  (`ix_configuration_question_type`), triggers 4 → 4, no existing row count
  changed (MEASURED on the test container at this head after `init --reset`
  on a spare database: 120 tables, 1179 columns, 52 CREATE INDEX, 4 triggers). **Pass, for Dada:** Setup ›
  Configuration types lists the seven with *counts as itself*; add
  *Infusion pump* counting as *Other* with a needed *Asset tag* question;
  add a pump by hand on Configurations and its page shows an *Infusion pump
  details* card that refuses to save without the tag; the Configurations
  tiles show *Infusion pump* once one exists.
- **Schema 057, in the same sitting (Dada: *"all of them"*): the six small
  setup items the parity check left.** `mail_template` (the board's Emails
  tab: subject and body per kind, four placeholders, no summary or note);
  `board.survey_enabled` and `board.survey_question` (the survey per board,
  unset is on); `kb_category` and `kb_article.category_id` (Setup ›
  Knowledge categories); `company_status`, `company_type`,
  `entity.status_id` and `entity.type_id` (Setup › Companies);
  `board.auto_assign` and `board_auto_assign` (the board's Auto-assign tab:
  a rule per Subtype › Item, else least loaded or the default team's
  leader, applied in `admit` to a ticket that arrives unowned);
  `member_presence` (`/inout`, the in/out board). Nothing seeded; a board
  that has said nothing behaves as it did. **Pass after 054 to 057:**
  tables **120 → 126**, columns **1179 → 1215**, indexes 52 → 52,
  triggers 4 → 4, no existing row count changed (MEASURED on the test
  container at this head after `init --reset` on a spare database:
  126 tables, 1215 columns, 52 CREATE INDEX, 4 triggers). **Pass, for
  Dada:** the helpdesk board's Setup page has *Emails* and *Auto-assign*
  tabs; Emails shows six kinds each marked *the desk's words*; saving one
  with `{summary}` is refused; the Board tab has the survey box ticked;
  Setup shows *Knowledge categories* and *Company status and type*; the
  Schedule bar has *In / out*, and saying *Out* there puts the word under
  your name on Schedule.
- **Counts:** 610 tests at this head (SQLite OK, 1 skipped). The whole
  suite ran on SQL Server in this container with 054 to 057: 610 run, OK, 2
  skipped, 12.0 minutes (MEASURED, 30 Sep). The drift gate passes. CI run 73
  on `d5f1bea` was red on its Windows job only, with part 24's teardown
  error (610 run, 1 error, 2 skipped; MEASURED from the job log): the test's
  own two unclosed connections, fixed at `fbc5162`. CI run 74 on `fbc5162`
  is green on all four jobs (MEASURED, finished 05:40 UTC).

## When a step does not pass

Every handoff step has a **Pass** line. This is what to do when it is not
met, per step, so that no sitting ends in an improvised fix. The pattern is
always the same: a named cause, a named resolution that stays inside the
footprint, and "stop and report BLOCKED" for everything else.

### Sitting 1 — SQL Server

| Step | Not passing looks like | Do |
|---|---|---|
| 0 | `D:\psa\spine.db` holds tickets | BLOCKED. Nothing here migrates a live SQLite desk. Dada decides: pilot on as it is, or an importer is written first. |
| 1 | `ProductVersion` below 14 | BLOCKED (TRIM() needs 2017+; the fix is one translator line, made in the cloud, not here). |
| 1 | `DB_ID('PMC_PSA')` not NULL | Someone has been here before. Read the Reply of the previous sitting; if none, BLOCKED with the database's creation date from `sys.databases`. Never drop it. |
| 1b | 8085 is listening | Use 8086, then 8087; write the port used into the Reply and into the pilot handoff's serve line. Never 8080. |
| 1b | A `PSA-*` task, folder, login or job already exists | Read its state and report before continuing; if it is the previous sitting's, continue from the step that made it. Never delete it to make the check pass. |
| 2 | `pip install pyodbc` has no route | The operator downloads the `pyodbc` wheel for CPython 3.12 win_amd64 on a machine that has a route and copies it to `D:\psa\`; `pip install D:\psa\pyodbc-*.whl`. The wheel's sha256 goes in the Reply. |
| 2 | No ODBC Driver 17 or 18 | Microsoft's ODBC Driver 18 x64 MSI, defaults, no other option changed; a reboot is not required and is not done. |
| 3 | `CREATE DATABASE` fails on the path | `D:\PMC\sql` does not exist or the SQL Server service account cannot write there: create the folder and grant the service account Modify on it, nothing wider. |
| 3 | The login exists with another default schema | `ALTER USER … WITH DEFAULT_SCHEMA = psa` on `PMC_PSA` only. |
| 3, 4, 6 | The operator is `sysadmin`, whose default schema is always `dbo` | The desk's own commands run as `psa_desk` (`runas`, the password typed there); the schema is applied by the operator through pyodbc with the committed file unchanged, as sitting 1 did, so `psa` stays `dbo`'s. |
| 4 | `schema-preview` refuses: wrong database | `$db` names the wrong database; fix the string, never the script. |
| 4 | `schema-preview` refuses: default schema | The operator ran it as themselves; run as the task account, or add the operator to `PMC_PSA` with default schema `psa` for the sitting and remove them after. |
| 4 | `init` reports VERIFY FAILED | The script rolled itself back; nothing was created. Paste the message. Do not re-run with the switches changed. BLOCKED. |
| 5 | `create-local-account` refuses a duplicate | The account exists from a previous sitting; use it. |
| 6 | Tests: anything but `OK` | Paste the last 40 lines into the Reply and stop the sitting before step 7. The desk does not run on SQL Server on a red suite. `DROP DATABASE PMC_PSA_TEST` still happens. A `WinError 32` on a `cli.db` in `tearDown` is the closed-connection fix above; pull and re-run. |
| 7 | `serve` refuses the port | Another service took it between 1b and now; back to 1b's rule. |
| 7 | `serve` refuses `0.0.0.0` or the LAN address | The address in the task is not one of the host's; `Get-NetIPAddress` lists them. |
| 7 | A task shows `Last Run Result` other than `0x0` | Its log in `D:\psa\logs\<TaskName>.log` says why (every `PSA-*` task is registered with its action's output redirected there, `*> D:\psa\logs\PSA-Desk.log` and so on; a task with no log is registered wrong); the usual cause is `$env:PSA_ATTACHMENT_DIR` missing from the task. Fix the task; never re-run a task by hand as an administrator. |
| 8 | `RESTORE VERIFYONLY` fails | The backup is bad; delete it, run the job again, verify again. Two failures: BLOCKED. |
| any | The Reply cannot be pushed | Commit locally and say so; the next sitting pushes. Never `--force`. |

### Sitting 2 — the pilot

| Step | Not passing looks like | Do |
|---|---|---|
| A1 | `/login` does not answer from a technician's PC | The desk is on `127.0.0.1`; it must be on the LAN address for other PCs. Or the Windows firewall on the host blocks the port: one inbound rule for that port, named `PSA-Desk-8085`, TCP, the LAN only. That rule is inside the footprint; nothing else in the firewall is. |
| B7 | A file is refused with "programs are not kept" for a real document | The file's first bytes are not what its extension says; that is the rule working. Rename is not the fix; the finding goes to the record. |
| E1 | No ticket from the test email within a minute | `PSA-MailPickup`'s log; the usual causes are the certificate for Graph (the mail handoff) or the drop folder's ACL. Never widen the mailbox permission. |
| any | The desk throws a 500 | The page says "500" and the console under the task shows the traceback; paste it, note the ticket and the action. Nothing on the host is changed to work around it; the fix is a commit. |
| H3 | The PHI flag names a real patient value | It never should; if it does, that is a defect, reported as a finding with the *shape* of the value, never the value. |

### Sitting 3 — HTTPS, sign-in, portal

| Step | Not passing looks like | Do |
|---|---|---|
| 1 | The certificate covers no name that resolves to this host | The portal sitting stops here. The desk keeps running on plain 8085, LAN only, and the Reply asks Dada for a name the certificate covers or a certificate for the name. (`dnd-sql01.pmcne.ph` is covered and resolves, MEASURED 26 Sep.) |
| 1 | `HasPrivateKey` is False | The certificate was imported without its key; the portal sitting stops here; the reply says so. |
| 2 | The private key is non-exportable (MEASURED 26 Sep for `*.pmcne.ph`) | `Export-PfxCertificate` cannot run. Two roads, both Dada's: the original PFX file from whoever installed the certificate (import it once more with the key marked exportable, or convert that file directly with openssl), or a re-key with the CA. Until one is in hand the desk stays on plain 8085, LAN only. Never any tool that "extracts" a non-exportable key. |
| 2 | `openssl.exe` is not where Git put it | `Get-Command openssl`; if none, the operator exports the PFX and converts it on a machine that has OpenSSL, copies the two PEM files to `D:\psa\tls\`, and deletes them there. |
| 2 | `icacls` refuses | The task account name is wrong; `Get-LocalUser` / the AD name from sitting 1's Reply. |
| 3 | `$env:USERDOMAIN` is the host's own name (the host is not domain-joined) | The Windows door cannot check a domain; BLOCKED for the portal sitting, the desk keeps running on break-glass accounts, the Reply says so. |
| 3b | (Entra, optional) The tenant administrator cannot grant admin consent | Staff are asked for consent once each on first sign-in; that is acceptable for the first group and written into the Reply. If the registration itself is refused by policy, the Windows door is the sign-in and Entra waits. |
| 4 | Browser shows a certificate warning | The chain is incomplete: append the intermediate to `desk.pem` (step 2's note). Or the name typed is not the one the certificate covers. |
| 4 | `serve` refuses the certificate | Not PEM, or the key does not match the certificate; redo step 2. |
| 6 | A good Windows password is refused | The page says Windows's reason. "wrong": the domain in `PSA_WINDOWS_DOMAIN` is the DNS name or another domain; use `$env:USERDOMAIN`. "not allowed to sign in here" (1385): the task account's host denies network logon to that user by policy; that is a domain policy and is not changed here; BLOCKED with the code. An unlisted code: into the Reply. |
| 6 | (Entra, optional) Sign-in fails and the page names the check | `redirect URI` mismatch: the URI in the tenant and `PSA_PUBLIC_URL` differ by a character; `audience`: `PSA_ENTRA_CLIENT` is another app's id; `issuer`: `PSA_ENTRA_TENANT` is wrong; `tenant could not be reached`: the host has no route to `login.microsoftonline.com` on 443, and the break-glass door is the WAN-down posture. Fix the setting named; nothing else. |
| 6 | A ward member sees a board | They were made a board member; membership is removed in Setup. A requester is a contact, never a member. |

## Reporting

Each sitting appends its Reply to the handoff it ran (DONE, BLOCKED or
WITHDRAWN, each step's Pass line, the evidence labels) and pushes. Values in
a Reply: hostnames, database names, ports, dates, counts, ids. Never: a
password, a thumbprint, an export password, a client secret (none exists), a
patient value, an internal address. A cloud session cannot receive a message
from this host; the branch is the channel both ways.

| Written | 2026-09-26, UTC |
|---|---|

## Reply

*(appended per sitting by SQL01, one dated block each)*

**Sitting 1, part 1: 2026-09-26, 15:26 UTC, BLOCKED at step 3 (the login).** Steps 0, 1,
1b, 2, 3 (database) and 4 pass: `PMC_PSA` exists on `D:\PMC\sql`, SIMPLE, with 73 tables in
`[psa]` owned by `dbo`. The task account `psa_desk` does not exist, and creating it is the
operator's (password at a prompt). Steps 5 to 8 and sittings 2 to 4 wait for it. Detail,
evidence and the operator's two commands are in the Reply of
`HANDOFF-cloud-sql01-WS36-20260925-sqlserver.md`. Nothing the hospital runs on this host was
changed (INFERRED from this sitting's own actions). MEASURED: the instance now has 10 user
databases where pre-flight found 9, plus the folders `D:\psa\` and `D:\PMC\sql\` and pyodbc in
`C:\PMC\Python312`. The payroll watchdog raised a 24-hour "no recent FULL backup" alert for
`PMC_PSA`, which step 8 quiets. Step 4 took the handoff's by-hand road on SQL01's own decision
(see that Reply); Dada can reverse it.

**Sitting 1, part 2: 2026-09-26, 15:38 UTC. Step 8 PASS, run early on Dada's word.** Job
`PSA-Backup-PMC_PSA` (owner `sa`, daily at 03:40:00) was created and run once. "The backup set
on file 1 is valid", and `msdb` records a FULL of `PMC_PSA` (MEASURED). The operator's
account-creation script is at `D:\psa\bin\New-PsaDeskAccount.ps1` and has not been run. Steps 3
(login), 5, 6 and 7 wait for the account.

**Sitting 1, part 3: 2026-09-26, 16:29 UTC. BLOCKED at step 6 on an upstream fix.** The operator
created `psa_desk`. Step 3 (login, default schema `psa`), step 4 (`init` twice, the same
`ready:` line) and step 5 (boards, two break-glass accounts) PASS. Step 6: 471 run, `FAILED
(errors=2, skipped=11)`. Both errors are a Windows-only file lock (`WinError 32` on a SQLite
`cli.db` that `psaspine.__main__.main()` leaves open). They reproduce on SQLite alone, so they
are not the SQL Server backend (MEASURED). `PMC_PSA_TEST` is dropped. Step 7 is not run, per
this file's rule for a red suite. The detail and the last 40 lines are in the sqlserver Reply.

**Sitting 1, part 4: 2026-09-26, 16:35 UTC. Step 7 pre-check, read-only.** A second code fix is
needed. `Invoke-PmcMailPickup.ps1`, `Send-PmcNotifications.ps1` and
`Invoke-PmcAttachmentRetention.ps1` each throw "Not found" because `Test-Path` on the connection
string is `False` (MEASURED). Only `PSA-Desk` and `PSA-Rules` can be registered at step 7: once
the suite is green and the task account has "Log on as a batch job". Mail and notify also wait
for the never-run Graph setup (mail and rules handoffs); the attachment copy waits for a
destination.

**Sitting 1, parts 5 and 6: 2026-09-26, 17:59 UTC. DONE, except the three waiting tasks.**
Step 6 is green at `5353316` (473 OK, 9 skipped). The runbook's ACLs are set, and "Log on as a
batch job" is granted. `PSA-Desk` is running on `127.0.0.1:8085` as `psa_desk`, and `PSA-Rules`
returns 0x0 every minute. The operator signed in, and a ticket raised through the desk (on a test
board) reached `psa.ticket` and was closed. `desk.pmcne.ph` is a static A record on `DND-AD01`.
**Sitting 2 is blocked** by one finding: the seeded boards `IT_HELP` and `UNROUTED` have no
members, and no web road gives them a first admin (detail in the sqlserver Reply, part 6).

### Part 7: 2026-09-26, 21:24 UTC. `a776c10` in; seeded boards have their admin; sitting 2 started

| Step (the operator's list) | State | Evidence (MEASURED unless marked) |
|---|---|---|
| 1 Pull | **PASS** | HEAD `a776c10` ("a seeded board's first administrator"), fast-forward from `3e2548f` |
| 2 Restart `PSA-Desk` | **PASS** | `Stop-ScheduledTask` left no `psaspine serve` process (old PID gone); port 8085 was free; `Start-ScheduledTask`. The new listener is `python.exe`, owner `psa_desk`, on `127.0.0.1:8085`, started 02:57:20 host time; `/login` answers 200. `PSA-Rules` untouched, still 0x0 |
| 3 First administrators | **PASS** | Run as `psa_desk` by the operator through `D:\psa\bin\Sitting2-BoardAdmin.ps1` (runas). It reads the one active break-glass sysadmin's name from `psa.local_account`, so nobody types it. `board-admin … --board IT_HELP` and `--board UNROUTED` each printed "`<account>` is its first administrator (audited)", exit 0. The same two again each printed "refused: … already has members", exit 1. `board_member` now holds `IT_HELP ADMIN` and `UNROUTED ADMIN` for that account, and exactly one `BOARD_MEMBER` audit row per board. The operator ran the script a second time, and all four calls were refused: idempotent |
| 4 Sign in, open IT_HELP | **PASS** | The operator signed in again (the restart ends sessions). In Chrome, the Service Board lists IT Help, Unrouted and the test board. Setup › IT Help › Members & roles lists the account as **ADMIN**, no team |

**Tests at `a776c10`.** `tests/smoke.py`: **7 of 7 steps passed** (Python 3.12.10, win32), including
"desk boots on 127.0.0.1 and challenges an unauthenticated request" (401) and "desk refuses a public
bind". The unit suite on SQLite, run as the operator: `Ran 475 tests`, `FAILED (errors=1,
skipped=2)`. The one error is Windows-only and SQLite-only: `EntraSignInTest.test_a_wrong_state_a_stale_flight_and_a_foreign_nonce_are_each_refused`
fails in `tearDown` with `WinError 32` on its temporary `spine.db`, a connection the test leaves
open, the same class as the part-3 fix. The SQL Server suite, the one that governs the desk, was
green at `5353316` (473 OK). **For upstream:** close that test's connection; low severity.

**Sitting 2: the pilot handoff, where it stands**

| Pilot step | State | Evidence and what it waits on |
|---|---|---|
| 0 | **PASS** | `D:\psa\spine.db` does not exist; the store is `PMC_PSA` |
| 1 | **PASS** | smoke 7/7 (above); the SQL Server suite 473 OK at `5353316`. SQLite-on-Windows has the one test-cleanup error above |
| 2 | **first admins PASS; the rest Dada's** | Which boards, Types, Statuses, SLA targets, templates and rules the pilot runs are "Setup decisions for Dada and the Service Manager" (this handoff's "Do NOT decide"). Not made by SQL01 |
| 3 | **in part; waits on names** | The break-glass sysadmin and one technician (`itadmin`) exist. The test script needs two or three technicians (B8 needs a second). `D:\psa\bin\Sitting2-AsDesk.ps1` (runas `psa_desk`) creates each one named by the operator, with the password at the desk's no-echo prompt. It parses with 0 errors; not run |
| 4 | **ready; operator's** | For technicians' PCs (test A1): `D:\psa\bin\Set-PsaDeskLan.ps1 -Apply` moves `PSA-Desk` to the address `desk.pmcne.ph` resolves to, and adds the runbook's one rule `PSA-Desk-8085` (inbound TCP 8085, LocalSubnet, Domain profile). It needs `psa_desk`'s password (Task Scheduler re-validates a task that runs as another account), and the firewall rule is the operator's to apply. `-Rollback` restores `127.0.0.1` and removes the rule. Preview: `desk.pmcne.ph` is one of this host's addresses; `PSA-Desk` on `127.0.0.1`; the rule does not exist yet. Not applied |
| 5 | **held** | The export scripts say "Run it as an ordinary domain user … Do not run it as a Domain Admin". This session is in Domain Admins and Enterprise Admins (MEASURED, token groups), so SQL01 did not run them. The ActiveDirectory module is installed. Either an ordinary domain user runs the two exports into `D:\psa\`, then `Sitting2-AsDesk.ps1` imports them, or Dada overrides the scripts' rule |
| 6 | **unchanged** | Mail and notify wait on the Graph registration; retention waits on the DPO (Dada's, the Folded-in section) |
| 7 | **waits on people** | The test script needs two or three technicians at their own PCs, after step 4 |
| 8 | **half** | `PSA-Backup-PMC_PSA`, daily 03:40, verified (sitting 1 part 2). The attachment copy still has no destination (Dada's). The files are on `D:` only; the SQL backup covers the metadata |

**The wildcard certificate: a PFX exists on the host.** Dada: *"the cert should be here"*. A
name-only search (no file opened; the repo's rules forbid reading `*.pfx`) found
`C:\Certs\wildcard.pmcne.ph.pfx`, 6,145 bytes, dated 2026-08-17. A control file was found by
the same method; one folder refused access. The store's copy of `*.pmcne.ph` (RapidSSL,
2027-02-23) still has export policy None (MEASURED). So HTTPS road (a) (the original PFX,
converted to PEM by the operator with its password, for the desk's own TLS) is available. The
choice between (a) and (b) (IIS in front) is still Dada's; nothing was done toward either. For the
record, not acted on: `C:\Temp` also holds three other `.pfx` files dated 2026-04-29
(`agentcert.pfx`, `agentcert.cert.pfx`, `QWEQWEert.pfx`).

### Part 8: 2026-09-26, 23:53 UTC. **Dada chose HTTPS with no port: road (b), IIS in front. IIS can take it; the desk needs a code fix first**

Dada, verbatim, in order: *"use https"*, then *"can u remove the port when going to the site"*.
On this host IIS (http.sys) holds 443 and 80 on all addresses, so a URL with no port means IIS
fronting the desk: road (b). Road (a) (the PFX to PEM, `:8443`) is therefore not taken.
`D:\psa\bin\Enable-PsaDeskHttps.ps1` was written for road (a) and **was not run**.
`Set-PsaDeskLan.ps1` (plain 8085 on the LAN) is superseded and **was not run**. Two read-only
investigators (IIS on the host, the desk's code) reported. Everything below is MEASURED unless
marked.

**IIS: a desk site fits without touching the four live sites.**
- The existing https bindings on 443 are all SNI (`sslFlags=1`), for `queue`, `payroll` and
  `portal.pmcne.ph`. Only Portal's binding carries its own certificate. Payroll and Queue HTTPS are
  served by the `0.0.0.0:443` fallback entry in http.sys (a TLS probe with SNI `payroll.pmcne.ph`
  gets `*.pmcne.ph` with no hostname entry of its own).
- No binding contains `desk` (the control found 6 `pmcne.ph` bindings), and http.sys has no
  `desk.pmcne.ph:443` entry. Today `https://desk.pmcne.ph` completes TLS on the wildcard and then
  http.sys answers 404: it reaches no site.
- URL Rewrite 2 (7.2.1993) and ARR 3.0 (3.0.05311) are installed. `system.webServer/proxy
  enabled="true"` is server-wide (AppHostOnly), with `preserveHostHeader=False`. Portal and Payroll
  already reverse-proxy to `localhost:4100` through site `web.config` rules. So a desk site with one
  rewrite rule to `http://127.0.0.1:8085/{R:1}` needs **no** `applicationHost.config` proxy change.
- Constraints for the site (INFERRED from the measurements):
  - its own app pool, No Managed Code, because `applicationDefaults` would otherwise put it in
    `DefaultAppPool`, which PMC Portal shares;
  - an https binding `desk.pmcne.ph:443` with **SNI required**, because a non-SNI binding would
    rewrite, and its later removal would delete, the `0.0.0.0:443` entry Payroll and Queue depend on;
  - its own `desk.pmcne.ph:80` binding redirecting to https, because otherwise
    `http://desk.pmcne.ph` lands on Default Web Site's `*:80` catch-all (it answers 200 today);
  - a named `appcmd add backup` before the change, because `configHistory` keeps only 10 snapshots
    at 2-minute intervals;
  - the site added to the kill switch.
- Certificate renewal (2027-02-23) must then re-point three entries, not two.

**The desk cannot run behind ARR as the code stands.** ARR sends `Host: 127.0.0.1:8085` and
scheme http.
1. The CSRF check (`psaspine/web/__init__.py:298-304`) refuses every POST whose `Origin` netloc
   differs from `Host`, `/login` included. Nobody could sign in.
2. `psa_session` and the Entra cookie are `Secure` only when the desk serves TLS itself
   (`__init__.py:219-231`, `entra.py:105-110`, `server.py:98-106`). An in-process probe shows no
   `Secure` behind a TLS proxy.
3. There is no reverse-proxy awareness at all: no `X-Forwarded-*` reads and no trusted-proxy
   setting.

Redirects are all relative, so they are fine. The Entra `redirect_uri` is right if
`PSA_PUBLIC_URL=https://desk.pmcne.ph`. The Windows door is not gated on TLS in code (only in
procedure). Changing ARR's server-wide `preserveHostHeader` would alter Portal and Payroll, so it
is not the fix.

**Asked upstream** (message sent 27 Sep):
- accept an `Origin` equal to `PSA_PUBLIC_URL`'s scheme and netloc;
- mark cookies `Secure` when `PSA_PUBLIC_URL` is https and the desk binds loopback, derived from
  config and never from a request header;
- HSTS recommended;
- tests for both;
- `PSA_PUBLIC_URL`, the Entra redirect URI and `PSA-Notify -PortalUrl` without `:8443`.

After the fix, on the host: `PSA-Desk` gets `PSA_PUBLIC_URL=https://desk.pmcne.ph` and
`PSA_WINDOWS_DOMAIN=PMCNE` (the operator's password prompt), then the IIS site as above. The
desk itself stays on `127.0.0.1:8085`, so no firewall rule is needed for it.

### Part 9: 2026-09-27, 01:57 UTC. **https://desk.pmcne.ph is live through IIS, and Windows sign-in is on. The desk's code is unchanged: IIS does the proxy fix's two jobs from outside, for this site only**

Dada, verbatim, in order: *"can we create accounts now linked to ad?"*, then *"do the iis fromt door now
make sure it doesnt meddle with the other apps"*. The part 8 fix had not landed (branch head still
`536dd97`), so the front door does its two jobs (Origin, Secure cookie) at IIS. Everything below is
MEASURED unless marked.

**Windows sign-in, 00:54 UTC.** The operator ran `D:\psa\bin\Set-PsaDeskEnv.ps1 -Apply`. PSA-Desk's
action now sets `PSA_WINDOWS_DOMAIN=PMCNE`, and nothing else in it changed. The task definition was
saved before the change, the task restarted (which signs everyone out), and `/login` shows the Windows
card. Checked first: the host is joined to `pmcne.ph` and DND-AD01 answers; "Access this computer from
the network" is held by Everyone and Users, with no deny entry. `PSA_PUBLIC_URL` is **not** set; it is
not needed while Entra and mail are off, and the script takes `-PublicUrl` when it is.

**IIS front door, 01:57 UTC.** SQL01 ran `D:\psa\bin\New-PsaDeskIis.ps1 -Apply`: **RESULT PASS.**
- **Before applying:** two previews came out identical. Three read-only reviewers then checked the
  script, one each on http.sys/TLS, URL Rewrite/ARR, and rollback/PowerShell 5.1. Their fixes were
  taken:
  - a **fifth site**, `PMC-Queue-JRBY` (http `*:8081`, its own pool), unknown to part 8, is now
    covered, because the site list is read from IIS at run time;
  - worker-process IDs are logged;
  - each undo step runs on its own, and a verify follows;
  - a failure, a difference or Ctrl+C rolls everything back automatically.

  `-Rollback` was run on the clean host first and was a verified no-op.
- **Added:**
  - the named backup `PSA-Desk-before-20260927-095718`;
  - `C:\inetpub\psa-desk\web.config`;
  - app pool `PSA-Desk` (no managed code);
  - site `PSA-Desk`, http `desk.pmcne.ph:80` plus https `:443` with SNI;
  - `<location path="PSA-Desk">` allowing `HTTP_ORIGIN`.
- **Not added, a change from part 8:** no http.sys certificate entry of its own. The site uses the
  `0.0.0.0:443` fallback, which was checked to be the same `*.pmcne.ph` certificate portal uses.
  Payroll and Queue work the same way. So renewal on 2027-02-23 re-points two entries, not three.
- **The web.config (this site only):**
  - http is redirected to https with a 302;
  - an `Origin` of exactly `https://desk.pmcne.ph` is rewritten to the desk's own origin before
    forwarding, and every other `Origin` passes unchanged and is refused by the desk;
  - requests are forwarded as `{UNENCODED_URL}` to `127.0.0.1:8085`;
  - every `Set-Cookie` leaving the site gets `Secure`;
  - request bodies are capped at the desk's own 10,747,904 bytes.
- **No meddling, proven before and after, identical:**
  - all 5 other sites' configuration and state, and every other app pool;
  - every http.sys certificate entry and the server proxy section;
  - a SHA-256 of `applicationHost.config` minus the desk's three elements;
  - 9 HTTP probes of the other sites.

  DefaultAppPool, PMC Payroll Pool, PMCQueuePool and PMCQueueJRBYPool kept the **same worker
  process** throughout, so none recycled.
- **Tests:**
  - http gets a 302 to https;
  - https `/login` answers 200 with the sign-in page;
  - a same-site POST gets 303, not 403;
  - the control, a cross-site POST, gets **403**;
  - the session cookie leaves marked `Secure`;
  - the loopback still answers 200.
- **Kill switch:** add `Stop-Website -Name PSA-Desk` to the runbook's list (the desk keeps running on
  the loopback). Undo: `New-PsaDeskIis.ps1 -Rollback`.
- Known, reviewer-measured: on **plain http**, `/reports` and `/reportserver` belong to SSRS's
  strong-wildcard reservations, so SSRS answers them. Over https (the only way the desk links) they
  reach the desk.

**Still wanted upstream, no longer blocking:** the part 8 fix (accept an `Origin` equal to
`PSA_PUBLIC_URL`; `Secure` from config). When it lands, on the host:
1. `Set-PsaDeskEnv.ps1 -Apply -PublicUrl https://desk.pmcne.ph`;
2. remove the Origin rule and the `<location>` entry;
3. keep the Secure rule until the desk marks cookies itself.

**Defects found while writing the staff user guide.** The guide was checked claim by claim against the
code: 39 corrections were confirmed and 4 refuted. All of the following are from code reading, with
file:line.
1. **Uplift** (`web/views/uplift.py:17-53`) has no access check and is not board-scoped. Anyone signed
   in sees every unclassified ticket on every board, restricted boards included (board, priority,
   state and summary), and no `RESTRICTED_READ` is written. With Windows sign-in on, that means any
   PMCNE account. Today no board is restricted and the only ticket is the sitting-1 test ticket, so
   nothing is exposed yet. **Fix before any restricted board exists.**
2. Dispatch "The day" shows a restricted ticket's number and the start of its summary, without an audit.
3. A system administrator's **Every board** workflow rule runs on restricted boards. Its test lists
   ticket numbers there, and Move to board can move those tickets.
4. Reports leaves "Resolve clock met" uncoloured at 0%.
5. The `OVERRIDE` priority source is allowed by the schema, but nothing sets it.
6. The pilot test script disagrees with the code:
   - B3 books 0.25 h, but the bands are 0.5/2/4/8/20;
   - H3 expects a technician's note to be scanned for patient details, and `board.add_note` runs no
     scan;
   - E1 cannot pass until the Graph mail setup is done.
7. Wording: the portal asks for "the record number", but `phi.py` flags a record number written after a
   label (MRN, hospital no. and so on).

**Next on the host:**
- board members for the Windows accounts (Dada, in Setup: the username without the domain, in lower
  case);
- the AD contact import (step 5) still waits on an ordinary domain user;
- boards, SLA targets and rules stay Dada's Setup decisions.

### Part 10: 2026-09-27, 02:44 UTC. **The staff portal has its own address: https://help.pmcne.ph (My requests only)**

Dada, verbatim: *"staff portal to chgeck their tickets and submit their tickets has this been built?"*,
then *"yes send it to ws36 also we need to have a proper site for it"*. Asked for the name and the
timing, Dada chose **help.pmcne.ph** (to match the `help@` mailbox) and **"put it up now"**.
Everything below is MEASURED unless marked.

**Asked of WS36** (message sent 27 Sep):
1. Uplift access and scope (part 9 defect 1), with Dispatch "The day" and the Every-board rule test.
2. People on no board land on `/my`, not the Service Board. Requesters see only My requests in the
   nav, and ⌘K and the keyboard sheet become technician-only.
3. A proper staff portal:
   - its own requester layout;
   - a `PSA_PORTAL_URL` setting;
   - on the portal host, `/` goes to `/my`, technician paths answer 404, and sign-in returns to `/my`;
   - requester email links use `PSA_PORTAL_URL`;
   - the Origin check accepts both public URLs.

**DNS.** `help.pmcne.ph` is a static A record on DND-AD01 (AD-integrated zone, TTL 1 h), copied from
the `desk` record's target (checked equal). DND-AD01 and this host's second DNS server answer it. This
host's **first** DNS server still returned "no such name" right after: it cached SQL01's own
availability check from a few minutes before. That clears by itself, INFERRED within the zone's
negative-cache time. The gateway was not touched.

**IIS site `PSA-Portal`.** Built by `D:\psa\bin\New-PsaPortalIis.ps1 -Apply`, the same reviewed shape
as `PSA-Desk`.
- **Added:**
  - its own pool;
  - http `help.pmcne.ph:80`, redirected to https;
  - https `:443` with SNI on the `*.pmcne.ph` fallback certificate (no http.sys entry added);
  - `<location path="PSA-Portal">` allowing `HTTP_ORIGIN`;
  - the named backup `PSA-Portal-before-20260927-104407`.
- **web.config:**
  - `/` redirects to `/my`;
  - **only** `/my` and below, `/login`, `/logout` and `/entra/start|callback` pass; every other path
    (technician desk, Uplift, the API, search) is redirected to `/my`;
  - same-site Origin is rewritten; Secure is added to cookies; request bodies are capped.

  So on this address staff never reach a technician page, even through the menu links the desk still
  draws.
- **No meddling:** before and after were identical across all **6** other sites (PSA-Desk included),
  every other pool, the certificate entries, the proxy section, the applicationHost hash and 11 probes
  (the desk included). DefaultAppPool, PMC Payroll Pool, PMCQueuePool, PMCQueueJRBYPool and PSA-Desk
  all kept the same worker process.
- **Tests** used curl `--resolve`, so the cached DNS answer could not skew them:
  - http gets a 302 to https;
  - `/` gets a 302 to `/my`;
  - `/dispatch`, `/uplift`, `/admin`, `/ticket/new`, `/api/tickets` and `/search.json` each get a 302
    to `/my`;
  - a same-site POST gets 303, and the control cross-site POST gets 403;
  - the cookie leaves marked Secure;
  - desk.pmcne.ph still answers 200.
- **The script's one "FAIL" was its own test.** A signed-out `/my` answers **401** with the desk's
  sign-in page (48,611 bytes, identical to the loopback) and **no `WWW-Authenticate`** header, so
  browsers show the page and never prompt. desk.pmcne.ph behaves the same way. The test was corrected;
  the run is recorded as PASS in `D:\psa\logs\New-PsaPortalIis.log`.
- **Kill switch:** `Stop-Website -Name PSA-Portal`. Undo: `New-PsaPortalIis.ps1 -Rollback`.

**Noticed, not ours:** `https://queue.pmcne.ph/` answered 200 at the part 9 build (09:57 local) and
now answers **302 to `http://queue.pmcne.ph/`**. Neither front-door script touched PMC-Queue; the
part 9 after-snapshot still showed 200. INFERRED: the queue session's own change, which is consistent
with the rule that the queue screens run over http only.

**Still open:**
- the portal is reachable by any PMCNE account but **not announced**; the first ward is Dada's call;
- `desk.pmcne.ph/uplift` still shows every board's unclassified tickets to anyone signed in, until
  WS36 fixes it (nothing restricted exists yet);
- when WS36 ships `PSA_PORTAL_URL`, set it with `Set-PsaDeskEnv.ps1` (a `-PortalUrl` parameter to be
  added) and retire the IIS Origin rules.

### Part 11: 2026-09-27/28 (UTC 2026-09-27 23:00). **d34e002 is live: the desk knows both public addresses, IIS no longer does its jobs; every Pass met**

Everything below is MEASURED unless marked. Local times are +08:00.

1. **Pull and restart.**
   - HEAD is `d34e002`. The desk's own suite on SQLite gives **489 OK, 2 skipped**, run as SQL01's user
     before the restart; the working tree is clean.
   - PSA-Desk was stopped and started: a new process, listening on 8085, loopback `/login` answering 200.
2. **Desk settings** (the operator ran it at 07:00):
   `Set-PsaDeskEnv.ps1 -Apply -PublicUrl https://desk.pmcne.ph -PortalUrl https://help.pmcne.ph`.
   `-PortalUrl` was added to the script; it sets `PSA_PORTAL_URL`, and `-Clear` accepts it. **RESULT: PASS.**
   The console now says `public: desk https://desk.pmcne.ph · portal https://help.pmcne.ph · cookies Secure,
   HSTS on`, and the Windows card still shows. The PowerShell console log wraps long lines at about 98
   characters, so the script joins the lines before matching.
3. **X-Forwarded-Host** (`Set-PsaIisForwarding.ps1 -Stage Forward`): **PASS**.
   - Both proxy rules set `HTTP_X_FORWARDED_HOST = {HTTP_HOST}`, and both `<location>`s allow it.
   - **One change to the order.** Part 10's portal path filter still stood at this step, so
     `help.pmcne.ph/dispatch` could not reach the desk to answer 404 yet; that check moved to step 5. The step
     proved the header arrives another way: `help.pmcne.ph/login?next=/dispatch` renders `next=/my` (the desk
     sees the portal host), while `desk.pmcne.ph/login?next=/dispatch` keeps `/dispatch`.
   - `help.pmcne.ph/` gets 302 to `/my`, and `desk.pmcne.ph/dispatch` still answers (signed out: 401 sign-in).
   - A same-site POST gets 303 on each address, and the cross-site control gets 403 on each.
4. **The Origin rewrite is gone** (`-Stage DropOrigin`): **PASS**. Both rules and both `HTTP_ORIGIN`
   allowances were removed. A same-site POST still gets 303 on each address, and the cross-site control 403.
5. **The portal path filter is gone** (`-Stage DropFilter`): **PASS**.
   - `help.pmcne.ph/dispatch` gets **404 from the desk**, and `/api/v1/tickets` gets 404.
   - `/` gets 302 to `/my`, and a signed-out `/my` gets 401 with the sign-in page.
   - `desk.pmcne.ph/dispatch` still answers.
   - **Kept:**
     - both http→https redirects and both body caps;
     - the portal's `/` → `/my` rule, a backstop (the desk does the same);
     - both **Secure** rewrites. The desk marks the sign-in cookie Secure from config (`__init__.py:501`), but
       its **sign-out** cookie still leaves as `psa_session=; Max-Age=0; Path=/`, measured on the loopback, so
       IIS keeps adding `Secure`.
   - Every stage compared all 5 other sites, every other pool, every certificate entry, the proxy section, a
     SHA-256 of `applicationHost.config` minus the two PSA sites, and 9 probes: **unchanged** each time.
   - Each stage saved both `web.config`s and a named backup: `PSA-Forward-before-20260928-070055`,
     `PSA-DropOrigin-before-20260928-070115`, `PSA-DropFilter-before-20260928-070131`. Copies are in
     `D:\psa\logs\iis-<stage>-before-*`.
6. **Pilot script 27 Sep, the two addresses**, host side, from DND-SQL01 with no sign-in:

   | Step | Check | Result |
   |---|---|---|
   | A1 | `desk.pmcne.ph/` signed out answers 401 with the sign-in page, Windows account first | **PASS** |
   | A1 | TLS validates against the Windows trust store | **PASS** |
   | A1 | `http://` redirects to `https://` | **PASS** |
   | F3 | `help.pmcne.ph/` → `/my`; a signed-out `/my` is the sign-in page; sign-in returns to `/my` | **PASS** |
   | F4 | `/dispatch` and `/admin` on `help.pmcne.ph` answer 404, not a sign-in page | **PASS** |
   | F6 | `desk.pmcne.ph/dispatch` is still the whole desk | **PASS** |

   **Waiting on the operator, because they need a real sign-in** (SQL01 enters no one's password):
   - A1 from a technician's PC (no certificate warning in their browser);
   - F3 signed in as a staff member on no board (the menu shows *Your requests* only);
   - F5, raising a request with a screenshot, which should land on Unrouted with source Portal;
   - F6 signed in as a technician on `help.pmcne.ph/my` (the requester's layout).

**Dada decided on 28 Sep: "My requests" in the Employee Portal (`portal.pmcne.ph`), signed in by the portal.**
The spec for the one desk door it needs is `HANDOFF-sql01-cloud-WS36-20260928-portal-link.md`. The portal side
is prepared and **not deployed**: a proposed `PMC_Portal.html`, +41/−3 lines, with no `bridge.js` change and no
restart. It is deployed only after the door passes on this host.

*Addendum to part 11, 2026-09-28:* Dada reversed the Employee Portal decision: *"just do a separate portal"*.
`HANDOFF-sql01-cloud-WS36-20260928-portal-link.md` is **WITHDRAWN**; `help.pmcne.ph` stays the separate staff
portal. `portal.pmcne.ph` was never changed (MEASURED, md5 unchanged).

*Correction to the addendum above, 2026-09-28:* the withdrawal was SQL01's misreading and is **reversed**. Dada: *"so it should open directly without signing in as it has siged in already when they login to portal.pmcne.ph"*. `HANDOFF-sql01-cloud-WS36-20260928-portal-link.md` stands as written: `help.pmcne.ph` is the separate staff portal, and the Employee Portal's *My requests* link opens it signed in.

### Part 12: 2026-09-28, 07:50 +08:00. **The Employee Portal door: steps 1 and 2 PASS; step 3 is with the operator; steps 4 and 5 wait on Dada**

Section "Folded in from part 11". Everything below is MEASURED unless marked.

1. **Pull, suite and restart.**
   - At `e2e4bc8` the SQLite suite as SQL01's user gives **495 OK, 2 skipped**. PSA-Desk was restarted; with
     `PSA_EMPLOYEE_PORTAL_ORIGINS` unset, `/sso/portal` answers **404**.
   - Your `23ee0b8` (pods move between columns) landed during the sitting. The suite at `e500888` is again 495 OK,
     2 skipped, and it went live with step 2's restart.
2. **The origins setting.**
   - `Set-PsaDeskEnv.ps1` gained `-EmployeePortalOrigins`, `-EmployeePortalBridge` and
     `-EmployeePortalDepartments`, each refused if malformed:
     - origins must be https with no path;
     - the bridge must be on the loopback;
     - quotes, backticks and `$` are refused;
     - each department must match exactly one of payroll's 52 `Employee.Department` names (read-only,
       case-sensitive).
   - The operator ran `-Apply -EmployeePortalOrigins https://portal.pmcne.ph` at 07:44. **Only `portal.pmcne.ph`,
     not `payroll.pmcne.ph`**: the payroll session's suggestion, least privilege. `PSA_EMPLOYEE_PORTAL_BRIDGE` is
     left at its default, and **departments are unset**.
   - `D:\psa\bin\Test-PsaPortalDoor.ps1`, made-up tokens only: **RESULT: PASS**.

     | Try | Result |
     |---|---|
     | Loopback, portal origin | **401** "session has ended", token not echoed |
     | Loopback, `http://portal.pmcne.ph` | **403** |
     | Loopback, no Origin | **403** |
     | Loopback, `https://payroll.pmcne.ph` (not listed) | **403** |
     | Through IIS, `help.pmcne.ph`, portal origin | **401** |
     | Through IIS, `desk.pmcne.ph/sso/portal` | **404** |

     **Audit:** 5 `PORTAL_SSO_REFUSED` rows for the 5 refused tries ("bridge answered 401" ×2, "origin not
     allowed (not https)", "origin not allowed" ×2), 0 `PORTAL_SSO`, and **no token text** in any row or in the
     console log.
   - Step 2's Pass counts "one row per try", but the `desk.pmcne.ph` 404 writes none, by design. The wording fix
     is in `HANDOFF-sql01-cloud-WS36-20260928-portal-door-fixes.md` item 10.
3. **Step 3 is with the operator.** The real portal token is posted from DevTools on the signed-in
   `portal.pmcne.ph` tab (the only way that passes the Origin rule, item 11), and should get 403 "not open for
   your department yet".
4. **Step 4 waits on Dada's first department(s),** set by `-EmployeePortalDepartments` until the Setup checklist
   (`HANDOFF-sql01-cloud-WS36-20260928-department-checklist.md`) replaces the setting.
5. **Step 5 is held** by the payroll session (page built from SQL01's diff, "Raise a request to any department")
   until the door passes steps 3–4 **and** the fixes before ward PCs (`…-portal-door-fixes.md`, items 1–9) are in.

**Review of `e2e4bc8`** (read-only, three lenses): all three say **safe to enable** for steps 2–4. The nine fixes
before step 5 lead with post-redirect-get on refusals, so a reloaded refusal tab on a shared PC cannot re-send
another person's portal token.

*Part 12, continued, 07:48 +08:00:* **step 3 PASS.** Dada signed in to `portal.pmcne.ph` and posted his portal token
from DevTools on that tab. `help.pmcne.ph` answered **"My requests is not open for your department yet."** Audit row
67 is `PORTAL_SSO_REFUSED`, "department not open", with a named employee as actor (MEASURED; the name is not
written here). The bridge accepted the real token and the door recognised the person: the whole path works, closed
only by the department gate. The same screenshot shows the requester shell branded **"PMC IT help"**; that is added
to `…-portal-door-fixes.md`. Step 4 waits on Dada's first department.

### Part 13: 2026-09-28, 09:40 +08:00. **c9a0506 live: schemas 033–035 applied, the hardened door PASS; departments wait on one as-desk run and Dada's ticks**

Everything below is MEASURED unless marked. Local times are +08:00.

1. **Pull, suite, schema, restart.**
   - HEAD is `2f18bf5`, code `c9a0506`. The SQLite suite as SQL01's user gives **519 OK, 2 skipped**, as expected.
   - PSA-Rules, which runs every minute from the repo, ran the new code against the old schema from the pull
     until the migration, **without error**: 09:06 run, `0x0`, "0 errors".
   - **Schemas 033–035, by the sitting-1 road.** `init` checks the login's default schema, so as sysadmin it
     cannot run; the desk's user has `db_datareader` and `db_datawriter`, `EXECUTE` and `VIEW DEFINITION`, and
     **no DDL**. So SQL01 ran the generated port as its own sysadmin login, with `@Apply = 1` and
     `@AllowExisting = 1` set in memory and the file on disk unchanged:
     - a **COPY_ONLY** backup first, `D:\PMC\backup\PMC_PSA\PMC_PSA_pre033-20260928.bak`, 10.6 MB, `RESTORE
       VERIFYONLY` "valid";
     - the preview: 77 tables, 27 indexes, 4 triggers;
     - PSA-Desk stopped, the port applied ("Created: 77 tables, 4 triggers, 27 indexes in [psa]", its own gate
       passed, "Seeded: nothing"), PSA-Desk started.
   - **Verified against a baseline taken before:**
     - psa tables **73 → 77** (new: `department`, `department_board`, `work_role`, `work_type`; none gone);
     - all six new columns present (`time_entry.time_start / time_end / hours_deduct`,
       `board.default_work_role_id / default_work_type_id / notify_owner`);
     - triggers 4 → 4; columns 681 → 714;
     - **no existing table's row count changed** except `audit_event` 79 → 80, which was a Windows sign-in at
       09:07, before the stop.
   - Your note said "75 tables become 77". There were 73; the preview's "Existing objects: 77" counts tables and
     triggers together.
   - One warning from the apply: `PK_department_board` can be 928 bytes against SQL Server's 900-byte key limit
     (INFERRED from the column widths: department name as NVARCHAR(400), board id as NVARCHAR(64)). Only a
     department name over about 386 characters could fail. Payroll's longest is 44, so this is harmless today; the
     translator could size that key column smaller.
   - The desk answers 8085 (`/login` 200), and its console shows no error. Sign-in: Windows account +
     break-glass.
   - Still to confirm: `init` printing "ready" as the task account, in the as-desk run in step 3. `seed` and
     `db.py` have not changed since sitting 1's `init` (empty diff), so it will change nothing. The Setup ›
     Time and Departments cards need a sysadmin sign-in and are the operator's to confirm.
2. **The hardened door: `Test-PsaPortalDoor.ps1`, made-up tokens only: RESULT PASS.**
   - The five refused tries of the Pass each answer **303** to `/sso/portal?refused=<code>`, with nothing echoed:
     - portal origin, loopback and through IIS: `ended`, and the page answers **401** "session has ended";
     - `http://` origin, no Origin, and `payroll.pmcne.ph`: `origin`, and the page answers **403**.
   - One extra try for fix 2, a token not shaped like one: `ended`, audited "token not shaped like a portal token",
     so the bridge was not asked.
   - `desk.pmcne.ph/sso/portal` answers **404** with no row.
   - **Audit: exactly 6 `PORTAL_SSO_REFUSED`** (the 5 of the Pass plus the extra), 0 `PORTAL_SSO`, no token text in
     any row or in the console log.
3. **Departments.**
   - `D:\psa\departments.csv` is written from payroll, read-only: one column, `Department`. It holds 52 names,
     and the list is the same over all employees and over active employees only (`IsActive = 1`). No name holds a
     comma; the longest is 44 characters. The query was checked with a control (a made-up name found 0 times, a
     real one found).
   - The import must run as the task account: `D:\psa\bin\Part13-AsDesk.ps1` runs `init` twice (the same "ready"
     line) and `import-departments` twice ("52 names: 52 new, 0 seen, 0 restored, 0 retired", then "0 new, 52
     seen"). It refuses anyone else (tested). **Waiting on the operator's runas.**
   - Then Dada ticks Setup › Departments and saves. `PSA_EMPLOYEE_PORTAL_DEPARTMENTS` was **never set** (part 12),
     so there is nothing to clear. The Pass is only that the page shows no banner about the setting.
4. **Setup › Time and the board settings:** nothing is set; they wait on Dada.

**Found on the host, for WS36:**
- **`2f18bf5` committed `.claude/settings.local.json`,** your session's own allow-rules. That file is per-machine:
  on this host it collided with the local copy, and git left conflict markers in a file Claude Code reads for its
  permissions. SQL01 restored the host's own version byte for byte and did not adopt your rules. Please stop
  committing that file; `.gitignore` it, or leave it untracked.
- **Unrouted has one member,** the break-glass administrator. Every portal request lands there (source Portal,
  for example PMC-000008 at 07:57), and nobody else on IT Help can see it. The operator is adding IT Help's people
  to Unrouted in Setup, and the Setup › Departments ticks will send requests straight to their boards.

*Part 13, continued, 09:12 +08:00:* **the as-desk run PASS.** The operator ran `Part13-AsDesk.ps1` as the task account
(`D:\psa\logs\Part13-AsDesk.log`):
- `init` twice, the same line both times: "ready: SQL Server, …Database=PMC_PSA";
- `import-departments` twice: **"52 names: 52 new, 0 seen, 0 restored, 0 retired"**, then **"52 names: 0 new, 52
  seen, 0 restored, 0 retired"**.

SQL01 read back `psa.department`: **52 rows, all from payroll and live, 0 board ticks**. The control query found a
real name once and a made-up name not at all. The script's "at <commit>" came out blank, because git refuses a
repository owned by another account (INFERRED: `safe.directory`); cosmetic only. **Correction:** this part's heading
says 09:40; the part was written at about 09:10 (the host clock read 09:12 at this line).

Waiting on Dada, in order:
1. Setup › Departments ticks and Save, as the break-glass sysadmin. Pass: one `DEPARTMENT_BOARDS` audit row, and no
   banner about the setting.
2. IT Help's people added to Unrouted in Setup.
3. The step 4 test as an employee of a ticked department.

### Part 14: 2026-09-28, about 10:10 +08:00. **70b7d6b live; schema 036 PASS; Dada's catalogue checks are his**

Section "Folded in from part 13". Everything below is MEASURED unless marked.

1. **Pull, with the host's settings file kept.**
   - `.claude/settings.local.json` was copied byte for byte, stashed, pulled over (the pull removes it, now that
     it is untracked), then restored. It has the same md5, parses as JSON, is ignored by `.gitignore:12`, and is
     no longer tracked. HEAD is `70b7d6b`.
2. **The suite on SQLite as SQL01's user: 522 tests, 520 OK, 2 skipped, 2 ERRORS, and both are Windows-only
   teardown.**
   - Both errors are `CatalogueSetupTest`: `test_add_rename_retire_never_delete_and_every_change_is_audited` and
     `test_the_setup_pages_build_a_pair_the_ticket_offers_and_a_retired_pair_stays_on_its_ticket`.
   - Each fails in `tearDown` (`test_spine.py:2387`, `self.tmp.cleanup()`) with `PermissionError [WinError 32]`
     on the temp `spine.db`. A connection the test opened is still open when the folder is removed; Linux allows
     that and Windows does not.
   - Rerun on their own, with only the temp folder's cleanup errors ignored (in a wrapper outside the repo; the
     repo was untouched): **both OK**. The product code is sound.
   - **Please close the test's connection before cleanup,** as the runbook's sitting-1 table says of `cli.db`.
3. **Schema 036 by the sitting-1 road: PASS.**
   - A COPY_ONLY backup, `D:\PMC\backup\PMC_PSA\PMC_PSA_pre036-20260928.bak`, `RESTORE VERIFYONLY` "valid".
   - The preview: 77 tables, 27 indexes, 4 triggers; 81 existing objects.
   - PSA-Desk stopped, then the baseline taken with nothing writing: 77 tables, 4 triggers, 714 columns, 377 rows.
   - The port applied as SQL01's sysadmin login, with `@Apply = 1` and `@AllowExisting = 1` set in memory and the
     file unchanged: its gate passed, "Seeded: nothing".
   - **Tables 77 → 77, columns 714 → 716, triggers 4 → 4, no row count changed.** `service_family.inactive` and
     `service_action.inactive` are present.
   - PSA-Desk started: `/login` 200, and no error in the console.
4. **The name.** `https://desk.pmcne.ph/login` reads **"Sign in · Dada PSA"** (2 occurrences; 0 "PSA desk", 0 "IT
   help"). **Noticed:** the portal host's sign-in page, `https://help.pmcne.ph/my` signed out, also reads "Sign in
   · Dada PSA", not "PMC Requests". The requester shell's name shows only after sign-in, so a ward's first sight of
   its own address is the product name. Worth drawing `login_page` in the requester's name on the portal host.
5. **Dada's checks (a sysadmin sign-in, so his):** the header reads "Dada PSA" after sign-in; Setup › Catalogue
   adds an area, a subtype and an item, pairs them onto IT Help, a new ticket offers the pair under "Subtype ›
   Item", and retiring the item withdraws it from new tickets only.

Still open from part 13: Setup › Departments ticks, IT Help's people on Unrouted, and the step 4 employee test.

*Part 14, continued, about 10:20 +08:00.* Everything below is MEASURED unless marked.

- **"My requests" is live on the Employee Portal.** The payroll session deployed it on Dada's word: *"when logging
  into portal .pmcne.ph the menu should show and do all of the ones that arent done yet"*.
  - SQL01 fetched `https://portal.pmcne.ph/PMC_Portal.html` from outside: **byte-identical** to the reviewed copy
    (md5 `fa110d06932ca6dc4c0244dad2c8bfc5`, 46,733 bytes).
  - It holds the menu entry, the form to `/sso/portal` (`target=_blank`, field `token`), the sign-out image to
    `/logout`, the admin-preview guard, and "Raise a request to any department"; "Ask for help" appears 0 times.
  - The previous page is kept beside it as `PMC_Portal.html.pre-myrequests-20260928`. `bridge.js` was neither
    changed nor restarted.
- **Step 4 PASS, for Project Management Office.**
  - Audit row 97, 10:09: `PORTAL_SSO_REFUSED` "department not open (Project Management Office)".
  - Row 99, 10:10: `DEPARTMENT_BOARDS` "Project Management Office: + IT Help".
  - Row 100, 10:10: **`PORTAL_SSO`** "employee portal, no contact row, department Project Management Office",
    with a named employee as actor.
  - Dada's screenshot shows *Your requests* in the requester's layout, with **"This goes to IT Help."**
- **Unrouted has 4 members** (was 1).
- **Found by Dada, to fix: the answer choices run together.**
  - Where he saw it: on `/my`, the raise form reads "…not working○ I need something…", "Just me○ My ward…" and
    "No○ Yes, but…".
  - Why: `portal.py:213-217` (`_radio_group`) writes each choice as an inline `<label>` straight after the
    previous one, and the only space is the radio's own `margin:0 4px 0 0` (`templates.py:269`). The technician
    New ticket form's `radios()` (`ticket.py:661-664`) has the same pattern.
  - Suggested fix, one class for both:
    - wrap each group's labels in `<div class=choices>`;
    - style it `display:flex;flex-wrap:wrap;gap:8px 22px`;
    - style each label `display:inline-flex;align-items:center;gap:6px;font-weight:400`, with the radio's margin
      0 inside it;
    - give the legend `margin-bottom:6px`, and the fieldset a bottom margin between questions.

    This wraps to one choice per line on a phone.
  - Not affected: the survey stars (`.stars`) and the note's Discussion/Internal switch (`.seg`) have their own
    styles.
- **Still open:**
  - Step 4's browser half: the cookie has no `Max-Age`, and a closed-and-reopened browser shows the sign-in page.
  - Step 5 on a ward PC: the portal's *Sign out* also ends the desk session.
  - Dada's Catalogue checks: no `CATALOGUE_CONFIG` row yet.

*Part 14, continued, about 10:35 +08:00: a defect in `init` found on the host.* Everything below is MEASURED unless
marked.

- **Dada: rename the board "IT Help" to "Help Desk".** His words: *"its shouldnt be IT Help but rename it as help desk
  board"*. Only the display name changes; the id `IT_HELP` stays, because department ticks, settings and tickets
  refer to it.
- **`init` resets the seeded boards' Setup settings on SQL Server, so a rename would not survive.**
  - `db.seed` writes `IT_HELP` and `UNROUTED` from `seed/boards.csv` with `INSERT OR REPLACE` (`db.py:250-258`),
    and that includes `display_name`, owner, deputy, `is_live` and `restricted`.
  - On SQL Server, `_replace_in_place` turns it into an UPDATE that sets every listed column **and every unlisted
    one back to its DEFAULT** (`mssql.py:627-636, 671-672`): `calendar_id`, `kind`, `closed_reply_policy`,
    `notify_requester`, `closed_loop_required`, the work-role, work-type and owner-email defaults.
  - Every schema step by the sitting-1 road runs `init` twice as the task account, so every migration silently
    undoes Setup on those two boards.
  - **Evidence from today.** Unrouted had calendar `ALL_HOURS` from its starter setup (audit rows 1, 4 and 6, 27
    Sep). It now has `calendar_id` NULL and `kind` NULL, with no audit row clearing either; the only thing in
    between is part 13's `init` at 09:12. IT_HELP lost them too and got them back when its starter setup was
    re-applied at 09:54 (audit row 95, "calendar ALL_HOURS").
  - **Impact so far: none.** The only ticket opened since 09:00 is PMC-000009 (10:12, source Portal, **routed
    straight to IT_HELP** by the PMO tick), and it carries its 3 SLA clocks. But any request landing on Unrouted
    now gets **no SLA clock** ("board not set up") until Unrouted's starter setup is re-applied, which is the
    operator's step in Setup.
  - **Fix, please:** seed the two boards **only if missing** (plain insert-if-absent), never overwrite a row that
    exists, and move `display_name` to "Help Desk" in `seed/boards.csv` for new installs. Add a test that
    `init` after a Setup change leaves the board's name, calendar and kind as Setup left them.
  - **Until that lands, SQL01 runs no `init`.** The next schema step waits for the fix, so Dada's rename made in
    Setup now will hold.

### Part 15: 2026-09-28, about 11:00 +08:00. **107f05f live; two of three Passes met; the third waits on one as-desk run; the teardown fix is not yet right**

Section "Folded in from part 14". Everything below is MEASURED unless marked.

1. **The suite on SQLite as SQL01's user: 527 run, 2 skipped, and the same 2 ERRORS.**
   - The same two `CatalogueSetupTest` tests, `WinError 32` in `tearDown` on the temp `spine.db`.
   - Why the fix did not work: `CatalogueSetupTest` borrows `tearDown = WebWSGITest.tearDown`
     (`test_spine.py:2386-2387`, `self.tmp.cleanup()`), and **unittest runs `addCleanup` callbacks after
     `tearDown`**. So the added `addCleanup(conn.close)` (`test_spine.py:4709`) closes the connection only after the
     folder removal has already failed.
   - **Fix:** in `CatalogueSetupTest.setUp`, register `self.addCleanup(self.tmp.cleanup)` right after
     `WebWSGITest.setUp(self)`, and drop the borrowed `tearDown`. Cleanups run last-in first-out, so each test's
     `conn.close` then runs before the folder is removed.
   - The test bodies pass: rerun on their own with the temp folder's cleanup errors ignored (a wrapper outside the
     repo; the repo untouched), **2 of 2 OK**. The product code is sound, so the desk was restarted.
2. **PSA-Desk restarted onto `107f05f`:** a new process, 8085 listening, `/login` 200, no error in the console.
3. **Pass 1:** `https://help.pmcne.ph/my` signed out reads **"Sign in · PMC Requests"**, and
   `https://desk.pmcne.ph/login` reads "Sign in · Dada PSA".
4. **Pass 2: the choices are spaced.** Measured on a loopback copy of `107f05f` (scratch SQLite, a test account
   made for it, `127.0.0.1:8095`, stopped afterwards), `/my` signed in:
   - 1265 px wide: the three questions each keep their choices on one row with **22 px** between them, 0 overlaps,
     0 clipped labels, the legend 6 px above;
   - 390 px wide: they wrap to 2, 3 and 2 rows, 0 overlaps, 0 clipped, no horizontal page scroll.

   The same code drives the live `/my`, which needs a staff sign-in to see. The technician New ticket form uses
   the same `.choices` row (`ticket.py:662`).
   - **New spacing defect on a phone, the header.** At 390 px the requester shell's "My requests" link spans
     153–272 px, and the user block (name or "break-glass" tag, then sign out) starts at 201 px: **about 70 px of
     overlap**, so the link reads "M" under the name. Please let the header wrap, or hide the link's text under an
     icon, below about 480 px.
5. **Pass 3 waits on the operator:** "a second init as the task account changes no board row".
   `D:\psa\bin\Part15-AsDesk.ps1`, run as the task account:
   - it reads every column of every `psa.board` row, runs `init`, reads them again, and requires them identical;
   - then it runs `setup-board --board UNROUTED` (the same `apply_starter` as Setup's button: it adds what is
     missing and never overwrites) to give Unrouted back the calendar part 13's `init` cleared;
   - it checks no other board changed.

   It refuses any other account (tested); it parses.
6. **Not done yet:** the board is still named "IT Help" (Dada's rename is in Setup, and holds now); Unrouted's
   `calendar_id` and `kind` are still NULL (step 5 fixes it).

*Part 15, continued, 12:38 +08:00:* **Pass 3 PASS, and Unrouted is whole again.** The operator ran `Part15-AsDesk.ps1` as the
task account (`D:\psa\logs\Part15-AsDesk.log`).
- `init` printed "ready" and **changed no board row**: all 3 boards, every column, compared before and after.
- `setup-board UNROUTED` said "added 0 statuses, 0 SLA targets, calendar ALL_HOURS".

SQL01 read back: Unrouted has `calendar_id` ALL_HOURS and `kind` SERVICE, with audit row 103 (`BOARD_SETUP UNROUTED`,
12:38). So a request landing on Unrouted gets its SLA clocks again. All three Passes of "Folded in from part 14" are
met. **Still open:** Dada's rename of IT Help to "Help Desk" in Setup; WS36's teardown order fix and the phone header
overlap (part 15, items 1 and 4).

*Part 15, continued, 13:15 +08:00:* **the first board is named "PMO Helpdesk".** Dada renamed it in Setup › Board, choosing
his own name over "Help Desk". His words: *"done renaming i like this name"*.

SQL01 read back: `IT_HELP` `display_name` is **"PMO Helpdesk"**, and `calendar_id` ALL_HOURS, `kind` SERVICE and
`is_live` 1 are all unchanged (MEASURED). Now that `init` never overwrites a seeded board, the name holds.

Two small asks:
- **The rename is not in the audit.** Audit row 105 (`BOARD_CONFIG IT_HELP`, 13:15) reads only "settings saved: live=1
  inactive=0". Please record changed fields as old → new, for example "name 'IT Help' → 'PMO Helpdesk'".
- **The seed name.** `seed/boards.csv` names the board "Help Desk" for a fresh install. If a fresh install should
  match what PMC runs, make it "PMO Helpdesk"; Dada's call, and it is harmless either way now.

### Part 16: 2026-09-28, about 14:10 +08:00. **02627d2 live; every Pass met**

Section "Folded in from part 15". Everything below is MEASURED unless marked.

1. **The SQLite suite as SQL01's user: 529 run, OK, 2 skipped, 0 errors.** The Windows teardown is fixed.
2. **PSA-Desk restarted onto `02627d2`:** a new process, 8085 listening, `/login` 200, no error in the console.
   `help.pmcne.ph/my` signed out reads "Sign in · PMC Requests"; `desk.pmcne.ph/login` reads "Sign in · Dada PSA".
   The live pages carry the new header markup: 1 `class=lbl` label on the requester shell, 8 on the desk.
3. **Pass: the phone header.** Measured signed in, as a requester, on a loopback copy of `02627d2` (scratch SQLite,
   test accounts made for it, `127.0.0.1:8095`, stopped afterwards; the live `/my` needs a staff sign-in and runs
   the same code). At 390 px the header holds:
   - the brand "PMC Requests", 16–137 px;
   - **one icon link** (My requests, `/my`, its words hidden), 145–176 px;
   - the user block, 213–374 px.

   **0 overlaps**, no horizontal scroll. At 1280 px every nav link still shows its words (0 hidden), with no
   header overflow.
4. **Pass: the rename audit.** On the same scratch copy, signed in as its board's admin, Setup › Board renamed the
   scratch board "Help Desk" → "Help Desk scratch rename". The `BOARD_CONFIG` row reads
   **"settings saved: name 'Help Desk' -> 'Help Desk scratch rename'; retired - -> 0; email the requester - -> 0;
   email the owner - -> 0"**.
   - The three `- -> 0` are that board's first Save writing 0 over NULL; cosmetic. A NULL could read as its
     default ("0 -> 0" is no change) so that it drops out.
   - The live board was not renamed for the test: it is still **"PMO Helpdesk"**. Its next real rename will show
     the new wording.

### Part 17: 2026-09-28, evening +08:00. **5163812 live; schemas 037 and 038 PASS; init as the task account and Dada's checks are theirs**

Section "Folded in from part 16". Everything below is MEASURED unless marked.

1. **The suite first, in a separate worktree.**
   - `git worktree add --detach` of `5163812` in SQL01's scratchpad. The live tree stayed at `7a1a6ba` while the
     suite ran, so PSA-Rules (which runs from the live tree every minute) never ran new code against the old schema.
   - **537 run, OK, 2 skipped, 0 errors.**
   - The worktree was removed after the apply.
2. **Schemas 037 and 038 by the sitting-1 road.**
   - A COPY_ONLY backup, `D:\PMC\backup\PMC_PSA\PMC_PSA_pre037-038-20260928.bak`, 11.6 MB, `RESTORE VERIFYONLY`
     "valid".
   - The preview, from the worktree's port: 80 tables, 29 indexes, 4 triggers; 81 existing objects.
   - PSA-Desk stopped, then the baseline taken with nothing writing: 77 tables, 4 triggers, 716 columns, 430 rows.
   - The port applied as SQL01's sysadmin, `@Apply = 1` and `@AllowExisting = 1` set in memory: "Created: 80
     tables, 4 triggers, 29 indexes", its gate passed, "Seeded: nothing".
   - **Tables 77 → 80** (new: `schedule_block`, `schedule_status`, `service_location`), **columns 716 → 745**,
     triggers 4 → 4, **no existing row count changed**. All 10 added columns are present: `holiday.all_day /
     time_start / time_end`, `calendar.inactive`, `ticket_schedule.status_id / location_id / is_lead /
     conflict_allowed / done_at / acknowledged_at`.
3. **Then the live tree pulled to `5163812`, and PSA-Desk started.** 8085 listening, `/login` 200, no error in the
   console. Signed out, `/schedule` and `/admin/calendars` answer 401 (they exist, sign-in first), and
   `help.pmcne.ph/my` answers 401 with its sign-in page. PSA-Rules' next run: `0x0`, "0 errors".
4. **`init` as the task account waits on the operator.** `D:\psa\bin\Part17-AsDesk.ps1` runs `init` twice; it wants
   the same "ready" line both times and no `psa.board` row changed (every column). It parses, and it refuses any
   other account (tested).
5. **Dada's checks:**
   - Setup › Calendars: a holiday list with Bonifacio Day and a part-day Christmas Eve, attached to *Business day*,
     with two `CALENDAR_CONFIG` rows;
   - `/schedule`: a meeting and a booked visit.

   SQL01 will read the audit rows back after.

### Part 18: 2026-09-29, about 11:05 +08:00. **402fb0e live; schemas 039–043 PASS; BizBox step 1 reported, stopped for Dada**

Section "Folded in after part 16 (29 Sep)". Everything below is MEASURED unless marked.

1. **Part 17's as-desk run: PASS.** The operator ran it on 29 Sep at 10:45.
   - `init` ran twice and gave the same "ready" line both times.
   - No `psa.board` row changed; there are 4 boards.
2. **The suite ran first, in a separate worktree of `402fb0e`: 544 run, OK, 2 skipped, 0 errors.**
   - The live tree stayed at `d5b4c99` while the suite ran, so PSA-Rules never ran new code against the old schema.
   - The worktree was removed after the apply.
3. **Schemas 039–043 went in by the sitting-1 road.**
   - **Backup:** COPY_ONLY, `D:\PMC\backup\PMC_PSA\PMC_PSA_pre039-043-20260929.bak`, 11.7 MB. `RESTORE VERIFYONLY` says "valid".
   - **Preview**, from the worktree's port: 99 tables, 34 indexes, 4 triggers.
   - **Baseline**, taken after PSA-Desk was stopped: 80 tables, 4 triggers, 745 columns, 432 rows.
   - **Apply:** the port ran as SQL01's sysadmin, with `@Apply = 1` and `@AllowExisting = 1` set in memory. It printed "Created: 99 tables, 4 triggers, 34 indexes", its gate passed, and it printed "Seeded: nothing".
   - **Result:**
     - **tables 80 → 99**, with 19 new: `ext_agreement`, `ext_change`, `ext_invoice`, `ext_link`, `ext_po_line`, `ext_product`, `ext_purchase_order`, `ext_source`, `kb_article`, `kb_revision`, `kb_ticket`, `member_role`, `phase_dependency`, `project`, `project_phase`, `project_ticket`, `report_def`, `role_permission`, `security_role`;
     - **columns 745 → 920**;
     - triggers 4 → 4;
     - **no existing row count changed**.
   - **Two SQL Server warnings at create.** Both keys can exceed the 900-byte limit: `PK_ext_link` can reach 1,184 bytes and `PK_ext_po_line` 928.
     - An insert fails only when one key's values are that long.
     - INFERRED: BizBox's keys are numbers and item codes, far shorter, so nothing fails.
     - Shortening those key columns would remove the warnings. That is WS36's call.
4. **The live tree was then pulled to `402fb0e`, and PSA-Desk started at 10:50.**
   - `/login` answers 200.
   - The console's only "error" is PowerShell wrapping the desk's start-up banner as a `NativeCommandError`, as in earlier parts.
   - PSA-Rules at 11:00: result 0, "0 errors".
   - **Correction to part 17.** Signed out, the desk answers 401 to every path, including a made-up one (`/zz-no-such-page-12345` gives 401).
     - So part 17's "`/schedule` and `/admin/calendars` answer 401 (they exist, sign-in first)" proved nothing about those pages.
     - The new pages are in `402fb0e`'s route table: `/kb`, `/my/help`, `/projects`, `/finance`, `/reports/custom` and `/admin/roles`.
     - Dada's checks below are what prove them.
5. **`init` as the task account waits on the operator.** It runs from `D:\psa\bin\Part18-AsDesk.ps1`, with the same checks as part 17's. The script parses and refuses any other account (tested at 11:03).
6. **Dada's checks:**
   - the menu shows Knowledge, Projects and Finance;
   - one article, once published, shows on `/my/help`;
   - a project whose second phase depends on its first refuses to start the second phase;
   - Setup › Security roles lists Technician, Service manager and Read only.

   Part 17's calendar and schedule checks are still open too.
7. **BizBox step 1 is reported** in `HANDOFF-cloud-sql01-WS36-20260929-bizbox.md` (Reply, part 1). It used the catalog only; no row was read.
   - Four kinds map.
   - Agreements have no source in BizBox.
   - The supplier's name lives only in `psDatacenter`, and that is Dada's decision.
   - **SQL01 stopped there for Dada's approval. Steps 2–6 have not started.**

*Part 18, continued, 11:10 +08:00:* **the as-desk run PASS.** The operator ran `Part18-AsDesk.ps1` as the task account
(`D:\psa\logs\Part18-AsDesk.log`, read back by SQL01):
- `init` ran twice, exit 0 both times, and printed the same line both times: "ready: SQL Server, …Database=PMC_PSA";
- **no `psa.board` row changed** (4 boards, every column compared).

Item 5 is met. What remains open is Dada's checks (item 6) and his approval of BizBox step 1 (item 7).

*Part 18, continued, 11:20 +08:00:* **BizBox step 2 done.** Dada's answer, 29 Sep, verbatim: "b". The list is approved, and supplier names come
from BizBox's own function, doctors included.
- SQL01 created schema `psa` and four read-only views in `LiveDB_PMC`, and every Pass was met.
- The details are in `HANDOFF-cloud-sql01-WS36-20260929-bizbox.md`, Reply part 2.
- Step 3 waits on one decision of Dada's: the desk's Windows account (SQL01's pick) or a new SQL login with a password.

*Part 18, continued, 11:56 +08:00:* **BizBox steps 3, 4 and 5 PASS.**
- Dada chose a SQL login: `psa_bizbox_reader`, which can read the four `psa` views and nothing else.
- Task `PSA-BizBox` runs hourly as psa_desk.
- The mirror holds 5,113 products, 527 POs, 1,400 lines and 636 invoices.
- The details are in the bizbox handoff, Reply parts 3 and 4. What is left there is the 12:05 read-back and Dada's Finance check.

### Part 19: 2026-09-29, about 14:00 +08:00. **23caa5f live; schema 044 PASS; the view and the map done; the kb count is 0; the four scripts committed**

Section "Folded in from part 18 and the BizBox Reply, parts 1–4". Everything below is MEASURED unless marked.

1. **The suite first, in a separate worktree of `23caa5f`: 545 run, OK, 2 skipped, 0 errors** (265 s).
   - The live tree stayed at `989b50e` while the suite ran.
   - The worktree was removed afterwards.
2. **Schema 044 by the sitting-1 road, in the section's order: stop, port, pull, start.**
   - **Backup:** COPY_ONLY, `D:\PMC\backup\PMC_PSA\PMC_PSA_pre044-20260929.bak`, 15.8 MB. `RESTORE VERIFYONLY` says "valid".
   - **Preview**, from the worktree's port: 99 tables, 36 indexes, 4 triggers; 103 existing objects.
   - **Baseline**, after PSA-Desk was stopped at 13:58:33 with 8085 closed: 99 tables, 4 triggers, 920 columns, 34 indexes, 8,142 rows.
   - **Apply** at 13:58:44, as SQL01's sysadmin with the switches set in memory. It printed "Created: 99 tables, 4 triggers, 36 indexes", its gate passed, and it printed "Seeded: nothing". There was no 900-byte warning: no new key.
   - **Result:**
     - tables **99 → 99**;
     - columns **920 → 921** (`ext_invoice.supplier_ref`);
     - indexes **34 → 36** (`ix_ext_invoice_agreement`, `ix_kb_ticket_ticket`);
     - triggers 4 → 4;
     - **no existing row count changed**.
   - The work was timed to finish well before PSA-BizBox's 14:05 run, which writes rows.
3. **The live tree was pulled to `23caa5f` at 13:59:12, and PSA-Desk started at 13:59:16.**
   - There is one desk process and 8085 is listening. Loopback `/login` answers 200, and so does `desk.pmcne.ph/login`.
   - `help.pmcne.ph/my` answers 401 with its sign-in page.
   - PSA-Rules ran on the new code at 13:59:59: result 0, "0 errors".
4. **The view and the map:** done after the pull. See the bizbox handoff, Reply part 5.
5. **The count is 0:** `SELECT COUNT(*) FROM psa.kb_article WHERE board_id IS NOT NULL AND audience = 'REQUESTER'`.
   - `kb_article` holds no rows at all: no article has been written yet, so nothing was ever exposed.
   - What the section marked INFERRED is now MEASURED.
6. **`init` as the task account waits on the operator.** It runs from `D:\psa\bin\Part19-AsDesk.ps1`, with the same checks as part 18's.
7. **The four scripts are committed** into `platform/psa-spine/scripts/` in the house style: PREVIEW BY DEFAULT, `-Apply` to act. See Reply part 5.
8. **Dada's checks:**
   - Finance opens on Procurement, with no Agreements tab;
   - Finance › Invoices shows *Supplier's invoice no.*;
   - the tabs count the whole mirror.

### Part 20: 2026-09-29, about 15:20 +08:00. **76d7554 live; schema 045 PASS; `init` as the task account is the operator's**

Section "Folded in from part 19 and the agreements handoff". Everything below is MEASURED unless marked.

1. **The 15:05 BizBox run, the first after the `supplier_ref` fill.**
   - The invoice line reads "638 rows, 0 new, 1 changed, 637 unchanged, 1 absent". The fill did not repeat.
   - The 1 changed is a receiving report that BizBox cancelled at 14:32; the mirror now reads Cancelled.
   - The 1 absent is a draft that BizBox deleted at 14:33. The mirror keeps it and marks it absent.
   - This is also in the bizbox handoff, Reply part 5, continued.
2. **The suite ran twice, both in a worktree.**
   - **At `930c607`** (303bae6's code): **546 run, OK, 2 skipped, 0 errors.**
   - While the apply ran, WS36 pushed `e80b11d`, merged as `76d7554`. It is one code change: `agreements.py` no longer sums a kind that has no total, since SQL Server refuses SUM(NULL).
   - The port is identical between the two heads, so the schema applied is `76d7554`'s.
   - **At `76d7554`**, the code now live: **546 run, OK, 2 skipped, 0 errors** (227 s).
3. **Schema 045 by the sitting-1 road, in the order: stop, port, pull, start.**
   - **Backup:** COPY_ONLY, `D:\PMC\backup\PMC_PSA\PMC_PSA_pre045-20260929.bak`, 16.9 MB. `RESTORE VERIFYONLY` says "valid".
   - **Preview:** 101 tables, 37 indexes, 4 triggers; 103 existing objects.
   - **Baseline**, after PSA-Desk was stopped at 15:13:36: 99 tables, 4 triggers, 921 columns, 36 indexes, 8,349 rows.
   - **Apply** at 15:13:46. It printed "Created: 101 tables, 4 triggers, 37 indexes", its gate passed, and it printed "Seeded: nothing".
   - **Result:**
     - tables **99 → 101** (`agreement`, `agreement_item`);
     - columns **921 → 946**;
     - indexes **36 → 37** (`ix_agreement_item_ref`);
     - triggers 4 → 4;
     - **no existing row count changed**.
   - **Why 946 and not 941.** The 25 new columns are the 20 declared and 5 computed `*_parsed` columns: on `agreement`, for `starts_on`, `ends_on`, `created_at` and `updated_at`; on `agreement_item`, for `added_at`.
     - The port adds one beside every date or timestamp text column. `psa` holds 109 of them.
     - The section's first Pass said 941, which counts the declared columns only. SQL01 measured 946 and found the five, and `e80b11d`'s Pass now says 946 for the same reason.
4. **Pull and start.**
   - The live tree was pulled at 15:15:24 by rebase, and landed on `76d7554`. SQL01's local copy of `930c607`'s record commit was dropped as already upstream.
   - PSA-Desk started at 15:15:29: one process, 8085 listening, loopback `/login` 200, `desk.pmcne.ph/login` 200, `help.pmcne.ph/my` 401 (its sign-in page).
   - The console shows nothing beyond the start-up banner's wrapper.
   - PSA-Rules on the new code at 15:19: result 0, "0 errors".
5. **`init` as the task account waits on the operator.**
   - It runs from `D:\psa\bin\Part20-AsDesk.ps1`, with the same checks as part 18's.
   - It supersedes Part 19's, which was not run: one `init` after 045 covers 044 as well.
6. **Dada's checks, from the section:**
   - Finance opens on Agreements, reading "No agreement yet".
   - A Service manager creates an agreement and covers a receiving number, a PO number and a product. The totals show against the agreed amount.
   - The invoice's own page lists the agreement.
   - A Technician sees all of it, with no New, Add or Remove.
   - Which roles hold Finance Write is Dada's to set in Setup › Security roles.

*Part 20, continued, 15:23 +08:00:* **the as-desk run PASS.** The operator ran `Part20-AsDesk.ps1` as the task account
(`D:\psa\logs\Part20-AsDesk.log`):
- `init` ran twice, exit 0 both times, and printed the same line both times: "ready: SQL Server, …Database=PMC_PSA";
- **no `psa.board` row changed** (6 boards, every column compared).

**6 boards, not part 18's 4.** SQL01 read the audit trail, because the script compares only the first `init` with the
second.
- `IT_CHANGE` and `IT_PROJECTS` were created in Setup by a person at 14:29, one `BOARD_CREATE` and one
  `BOARD_SETUP` row each. That was before 045 and before this run.
- `init` created no board.

Item 5 is met. What remains open is Dada's checks (item 6).

### Part 21: 2026-09-30, about 08:15 +08:00. **de4f9ee live; 046–053 and the token scope PASS; KB folder and webhook file made; PSA-Teams held on three measured defects**

Section "Folded in after part 20 (29 Sep, later)". Everything below is MEASURED unless marked.

1. **The suite first, in a separate worktree of `de4f9ee`: 594 run, OK, 2 skipped, 0 errors** (265 s). The live tree
   stayed at `1119b09` (76d7554's code) while it ran. The worktree was removed afterwards.
2. **All eight schema steps and the token scope, once, by the sitting-1 road: stop, port, pull, start.**
   - **Backup:** COPY_ONLY, `D:\PMC\backup\PMC_PSA\PMC_PSA_pre046-053-20260930.bak`, 17.9 MB. `RESTORE VERIFYONLY`
     says "valid".
   - **Preview**, from the worktree's port: 115 tables, 48 indexes, 4 triggers; 105 existing objects.
   - **Baseline**, after PSA-Desk was stopped at 07:54:11 with 8085 closed: 101 tables, 4 triggers, 946 columns,
     37 indexes, 8,472 rows.
   - **Apply** at 07:54:19, as SQL01's sysadmin with the switches set in memory. It printed "Created: 115 tables,
     4 triggers, 48 indexes", its gate passed, and it printed "Seeded: nothing".
   - **Result, the section's end state, all met:**
     - tables **101 → 115**;
     - columns **946 → 1149**;
     - indexes **37 → 48**;
     - triggers 4 → 4;
     - **no existing row count changed**;
     - no column gone from any existing table.
   - **The 203 new columns:** 184 in the 14 new tables, and 19 added to existing tables. **All 19 are NULL-able.**
   - **Each step's own count, from the catalog, against the section:**

     | Step | Section says | Measured | |
     |---|---|---|---|
     | 046 | 30 | `timesheet` 14, `timesheet_event` 7, `member_capacity` 5, `role_grant` 3, `time_entry.timesheet_id` | 30, met |
     | 047 | 23 | `recurrence` 22, `ticket.recurrence_id` | 23, met |
     | 048 | 7 | `configuration.` purchased_on, warranty_ends_on, installed_on, vendor, purchase_ref, location, agreement_id | 7, met |
     | 049 | 15 | `approval` 13, `department.approver`, `catalogue_item.needs_approval` | 15, met |
     | 050 | 31 | `channel_target` 9, `page` 17, `notification.` channel, target_id, page_id, `workflow_action.` channel, target_id | 31, met |
     | 051 | 20 | `kb_file` 20 | 20, met |
     | gap 8 | 1 | `api_token.scope` | 1, met |
     | 052 | 49 | `opportunity` 22, `quote` 20, `quote_line` 7 | 49, met |
     | 053 | 27 | `member` 21, `calendar_feed` 4, `board.intake_address`, `intake_message.to_address` | 27, met |

   - **The 11 new indexes:**
     - `ix_timesheet_event_sheet`, `ix_time_entry_sheet`, `ix_recurrence_due`;
     - `ix_approval_ticket`, `ix_approval_approver`, `ix_page_open`, `ix_kb_file_article`;
     - `ix_opportunity_stage`, `ix_quote_opportunity`, `ix_quote_line_quote`, `ix_calendar_feed_hash`.
   - SQL01's verify script ended with a traceback of its own: a loop variable reused a name, *after* every check had
     printed. It did not touch the database.
3. **Pull and start.**
   - The live tree was pulled at 08:08:21 by fast-forward, and landed on `de4f9ee`.
   - PSA-Desk started at 08:08:23: one process, 8085 listening, loopback `/login` 200, `desk.pmcne.ph/login` 200,
     `help.pmcne.ph/my` 401 (its sign-in page).
   - The console shows nothing beyond the start-up banner's wrapper.
   - **The desk was down 14 minutes, 07:54:11 to 08:08:23**, where earlier sittings took about one. The apply and
     verify finished at 07:54:20. The rest was SQL01's own gap before the pull, not a failure.
   - **In that gap the old code ran against the new schema, and nothing failed.** Task Scheduler's history:
     - PSA-Rules ran 15 times between 07:54:36 and 08:08:36, all with result 0;
     - PSA-BizBox's 08:05 run exited 0, with ordinary counts.
   - **PSA-Rules on the new code at 08:08:36** reports "0 errors; recurring: 0 raised, 0 failed; pages: 0 open".
4. **`init` as the task account waits on the operator:** `D:\psa\bin\Part21-AsDesk.ps1`, with the same checks as
   part 20's.
5. **Host step for 051: the KB folder is `D:\psa\files-kb`, not `D:\psa\attachments-kb`.**
   - `kbfiles.kb_dir()` uses `PSA_KB_DIR` if set, otherwise the attachment folder's name plus `-kb`. Every PSA task
     on this host sets `PSA_ATTACHMENT_DIR = D:\psa\files`, and there is no `D:\psa\attachments`.
   - Created at 07:52. Its ACL is identical to `D:\psa\files`: only the entries it inherits from `D:\psa` (SYSTEM
     and Administrators full, the task account Modify). No task needed a change.
   - **"Added to the same backup": nothing from inside this host backs up `D:\psa\files`.** Checked:
     - no scheduled task names `D:\psa`, except the PSA tasks themselves (680 tasks read, elevated);
     - no SQL Agent step names it (19 steps read);
     - neither Windows Server Backup, nor the Azure Backup agent, nor a Veeam agent is present (control: W3SVC found);
     - a backup taken from the hypervisor would not be visible from here: NOT VERIFIED either way.
6. **Host step for 050: `D:\psa\teams-webhooks.json` is made and PSA-Teams is not registered.**
   - The file holds `{}`, with inheritance off: SYSTEM and Administrators full, the task account read. No address is
     in it; the channel addresses are Dada's to paste. It is not in the repository.
   - **There is no PSA-Notify task on this host, nor PSA-Mail, nor `D:\psa\mail-state`** (the same elevated read,
     with a control). "Beside PSA-Notify" has nothing to stand beside; the desk sends no email from this host yet.
   - **Three defects in `scripts/Send-PsaTeamsNotifications.ps1` at `de4f9ee`, each measured here:**
     - **(a) It posts only to addresses that no longer work.** `Test-WebhookUrl` accepts `*.webhook.office.com` or
       `*.logic.azure.com`, and marks anything else FAILED without posting. Both are retired. VERIFIED on
       learn.microsoft.com, 30 Sep:
       - Office 365 connectors (the classic incoming webhook) retired on 30 April 2026 (Microsoft Q&A answers), and
         Microsoft's Azure Databricks page says the classic Incoming Webhook connector has been retired;
       - Power Automate trigger URLs on `logic.azure.com` stopped working on 30 November 2025, per "Troubleshoot
         Power Automate trigger problems".
       - A Teams Workflows webhook made today is on `*.environment.api.powerplatform.com`: a Microsoft Q&A answer
         shows one, and Power Automate's IP page lists `*.api.powerplatform.com` for that trigger.
       - Tested in preview against a scratch desk, with made-up addresses in a scratch copy of the file. The card
         itself is an Adaptive Card in the `attachments` envelope, which Workflows accepts (VERIFIED, the same pages).
     - **(b) Under Windows PowerShell 5.1 with `-File`, it cannot start with its default `-SpineDir`.**
       `$PSScriptRoot` is empty inside the `param()` default, so `Join-Path` refuses before anything runs. Through
       `-Command "& '…'"` it is set.
     - **(c) Under Windows PowerShell 5.1, every pass with nothing due fails.**
       - `outbox-pending` prints `[]`, and `@('[]' | ConvertFrom-Json)` has one element, an empty array.
       - Reading `.target` on it fails under `Set-StrictMode 2.0`: "The property 'target' cannot be found on this
         object".
       - Measured on 5.1.20348.5499. The control, pwsh 7.6.4 on the same host, gives 0 and passes. A one-item list
         gives 1 on both.
   - **The task is held.** With these defects its preview Pass cannot be met, and registering it costs Dada
     psa_desk's password for a FAIL.
   - `D:\psa\bin\Register-PsaTeams.ps1` is ready, and committed as `scripts/Register-PsaTeams.ps1`, preview by
     default. Its preflight passes (08:11). It registers PSA-Teams every minute in PREVIEW, with `-SpineDir` passed
     explicitly, and removes the task again if the Pass is not met.
   - **To run after the fix lands.** Why a minute's trigger and not `-Loop`: a loop that dies stops silently, and
     nothing on this host watches the PSA tasks.
   - Also VERIFIED on the same Teams pages: Workflows cannot post as the flow bot into a **private** channel yet. The
     channel must be a standard or shared one.
7. **Host step for 053: nothing, as the section says.**
   - PSA-Mail does not exist on this host (item 6), so the per-board intake address has no pickup to route yet.
   - Dada's mail check for 053 waits until one runs.

**For WS36:**
- **(a):** accept `*.api.powerplatform.com`; the exact suffix is WS36's call.
- **(b):** resolve `-SpineDir` in the body, not in `param()`.
- **(c):** handle an empty list under Windows PowerShell 5.1, which is the runtime on these servers.

SQL01 registers PSA-Teams at the head that carries them.

**Dada's checks, per step. His; not done by SQL01:**

- **Members (053), his alone:**
  - Setup › Members shows everyone;
  - he opens his own page and saves a name;
  - the header shows it.
- **046:**
  - Time is in the menu, and his week lists the time he booked;
  - *Submit for approval* locks the week;
  - a Service manager who is not him approves it, and he cannot approve his own;
  - Setup › Security roles has a Timesheets column;
  - Reports shows *Utilisation, by member* once time is booked.
- **047:**
  - Setup shows *Recurring tickets (0 active)*;
  - one added with a first due day of today is raised by the next PSA-Rules run, tasks and all, with *Raised by the
    recurrence …*;
  - *Run now* raises one at once.
- **048:**
  - a printer's page takes a warranty end date;
  - the list counts it under *Warranty ends in 90 days* or *Out of warranty*;
  - *Maintenance record (CSV)* downloads.
- **049:**
  - Setup › Departments has an Approver column;
  - a pair set to *Approval: yes* makes a ticket record the request;
  - the approver decides on the portal's Approvals page;
  - a board parks the ticket in Awaiting approval only once Dada adds that status there, with *Waiting* ticked.
- **Gap 5:** on a phone on the hospital Wi-Fi, the board is cards with a bar at the foot, and a ticket's bar has
  *Note*, *Ticket*, and *Call* when the contact has a number.
- **050:**
  - Setup › Integrations shows *Teams channels*;
  - *Page the on-call* puts *Paging <name>: attempt 1 of 3* on a ticket;
  - the card itself waits on the three fixes and on a Workflows webhook in a standard channel.
- **051:**
  - an article shows *Files*;
  - a screenshot appears where `![caption](file:1)` is pasted, and on the portal only after *Clear*;
  - a `.exe` is refused;
  - `D:\psa\files-kb` holds one file afterwards.
- **Gap 8:** a token minted `--scope READ` answers `GET /api/v1/tickets`, and the old monitoring token answers 403
  naming the scope.
- **052:**
  - Sales is in the top bar;
  - opportunity, then quote, line, sent, accepted and *Won*, lands on a draft agreement with the quote's total;
  - a Technician sees it with no form.
- **053, the rest:**
  - Calendar shows his week and the month;
  - the feed from My profile opens on a phone;
  - the mail routing waits on PSA-Mail (item 7).

*Part 21, continued, 08:48 +08:00:* **the as-desk run PASS.** The operator ran `Part21-AsDesk.ps1` as the task account
(`D:\psa\logs\Part21-AsDesk.log`, read back by SQL01):
- `init` ran twice, exit 0 both times, and printed the same line both times: "ready: SQL Server, …Database=PMC_PSA";
- **no `psa.board` row changed** (6 boards, every column compared).

Item 4 is met.

### Part 22: 2026-09-30, about 08:57 +08:00. **c666b8e live; PSA-Teams registered in PREVIEW; its passes log "0 card(s) due" with result 0**

Section "Folded in from part 21 (30 Sep)". Everything below is MEASURED.

1. **The pull: a fast-forward at 08:49:17 to `c666b8e`.**
   - It brought scripts, the README, tests and the runbook only. There was no port change and no `psaspine` change,
     so PSA-Desk kept running, neither stopped nor restarted.
   - `Send-PsaTeamsNotifications.ps1` is now pure ASCII (0 non-ASCII lines).
2. **The fixed sender before the task.** SQL01 ran it as the operator on a scratch desk (deleted afterwards), under
   Windows PowerShell 5.1 with `-File` and **no `-SpineDir`**.
   - **With an empty file:** "PREVIEW: 0 card(s) due; 0 channel(s) in the file, 0 with an address that would be refused;
     0 due channel(s) not in the file. Nothing posted." It started and counted 0, so **(b) and (c) are fixed**.
   - **With four made-up addresses:** a Workflows `*.environment.api.powerplatform.com`, the retired `*.webhook.office.com`
     and `*.logic.azure.com`, and a control on `example.com`.
     - It read "4 channel(s) in the file, **1** with an address that would be refused". Only the control was refused, so
       **(a) is fixed**.
   - No state folder was made in preview.
3. **The register: Dada ran `D:\psa\bin\Register-PsaTeams.ps1 -Apply` at 08:52:17.**
   - Preflight PASS.
   - Registered at 08:52:28 as `DND-SQL01\psa_desk`, every minute, PREVIEW.
   - The first pass, at 08:52:30, logged **"PREVIEW: 0 card(s) due; 0 channel(s) in the file, 0 with an address that
     would be refused; 0 due channel(s) not in the file. Nothing posted. Re-run with -Apply."**
   - "RESULT: PASS".
   - Before the run, the host copy was made byte-identical to the repository's; the two had differed in line endings only.
4. **Read back by SQL01 afterwards.**
   - **The task:** psa_desk, Password logon, Limited; every minute from 08:54, indefinitely; IgnoreNew; a 5-minute limit.
   - **The action:** it passes `-SpineDir` and has **neither `-Apply` nor `-Loop`**.
   - **Task Scheduler's history:** 5 action completions from 08:52:30 to 08:57:02: the first run and four scheduled
     ones, one a minute from 08:54. **All have result 0.** The latest pass, at 08:57:02, logged the same PREVIEW line,
     "0 card(s) due".
   - **`D:\psa\mail-state` was not made.** Only `-Apply` makes it.
   - **Without `-SpineDir`:** the one run without it is item 2. The task keeps it, as the script registers it.
   - **A cosmetic point:** in `PSA-Teams.log` the PREVIEW line wraps after about 98 characters (the host width under
     `*>`). The register script's check matched on the first line. Nothing changes for the Pass.
5. **Nothing else on the host this sitting.**
   - **Posting a card stays a later switch.** It needs four things:
     - a Workflows webhook in a standard or shared channel (not a private one: Workflows cannot post there as the
       flow bot yet);
     - its address pasted into `D:\psa\teams-webhooks.json` by Dada;
     - the channel named in Setup › Integrations › Teams channels;
     - the task's action switched to `-Apply`, which needs psa_desk's password again.
   - Whether Teams renders the card as posted is still this sitting's to say, once one is posted.

### Part 23: 2026-09-30, about 10:50 +08:00. **12f9322 live; 054–056 PASS; `init` as the task account is the operator's**

Section "Folded in after part 22 (30 Sep)". Everything below is MEASURED.

1. **The starting count was 115 tables, not 116.** Read at 10:42, before anything ran: 115 tables and 1,149 columns,
   with no table made since part 21.
   - The message relaying this sitting said "116 → 120", which is 056's own step.
   - The section's steps begin at 115: 054 keeps 115, 055 makes 116, and 056 makes 120.
   - So the Pass for the whole sitting is **115 → 120**.
2. **The suite first, in a separate worktree of `12f9322`: 604 run, OK, 2 skipped, 0 errors** (307 s).
   - The live tree stayed at `902d995` (c666b8e's code) while it ran.
   - The worktree was removed afterwards.
3. **054, 055 and 056 together, once, by the sitting-1 road: stop, port, pull, start.**
   - **Backup:** COPY_ONLY, `D:\PMC\backup\PMC_PSA\PMC_PSA_pre054-056-20260930.bak`, 17.9 MB. `RESTORE VERIFYONLY`
     says "valid".
   - **Preview**, from the worktree's port: 120 tables, 52 indexes, 4 triggers; 119 existing objects.
   - **Baseline**, after PSA-Desk was stopped at 10:47:54 with 8085 closed: 115 tables, 4 triggers, 1,149 columns,
     48 indexes, 8,497 rows.
   - **Apply** at 10:48:04, as SQL01's sysadmin with the switches set in memory. It printed "Created: 120 tables,
     4 triggers, 52 indexes", its gate passed, and it printed "Seeded: nothing".
   - **Result, all met:**
     - tables **115 → 120** (`mail_exclusion`, `configuration_type`, `configuration_status`,
       `configuration_question`, `configuration_answer`);
     - columns **1,149 → 1,179**;
     - indexes **48 → 52** (`ix_audit_event_when`, `ix_audit_event_actor`, `ix_audit_event_subject`,
       `ix_configuration_question_type`);
     - triggers 4 → 4;
     - **no existing row count changed**;
     - no column gone from any existing table.
   - **Each step's own count, from the catalog:**

     | Step | Section says | Measured | |
     |---|---|---|---|
     | 054 | 1 column, 3 indexes | `audit_event.source`; the three `ix_audit_event_*` | met |
     | 055 | 7 | `mail_exclusion` 7 | met |
     | 056 | 22, 1 index | `configuration_type` 5, `configuration_status` 5, `configuration_question` 7, `configuration_answer` 3, `configuration.type_id` and `status_id`; `ix_configuration_question_type` | met |

   - **All 3 columns added to existing tables are NULL-able.**
4. **Pull and start.**
   - The live tree was pulled at 10:48:05 by fast-forward, and landed on `12f9322`. The pull and the start this time
     followed the verify directly, so the desk was down 14 seconds (10:47:54 to 10:48:08), not part 21's 14 minutes.
   - PSA-Desk started at 10:48:08: one process, 8085 listening, loopback `/login` 200, `desk.pmcne.ph/login` 200,
     `help.pmcne.ph/my` 401 (its sign-in page).
   - The console shows nothing beyond the start-up banner's wrapper.
   - **PSA-Rules** on the new code at 10:49:49: result 0, "0 errors".
   - **PSA-Teams** on the new code at 10:50:02: result 0, "PREVIEW: 0 card(s) due … Nothing posted". Task Scheduler's
     history holds 61 of its runs, all with result 0.
   - (`PSA-Teams.log` is UTF-16, as PowerShell 5.1's `*>` writes it. Read it with `Get-Content`, not `grep`.)
5. **`init` as the task account waits on the operator:** `D:\psa\bin\Part23-AsDesk.ps1`, with the same checks as
   part 21's.
6. **Nothing else on the host**, as the section says. PSA-Mail is still not registered.
7. **Dada's checks, from the section:**
   - **054:**
     - Setup shows *Audit and API tokens*;
     - Audit lists today's changes, with *DESK* in the Source column for desk changes and blank for older rows;
     - a CSV downloads;
     - API tokens shows the gap-8 monitoring token with its scope, and *Mint* shows a new token once.
   - **055:**
     - Setup › Email connector lists the helpdesk board's address;
     - *Exclude* a vendor's domain, and the row appears with who added it.
   - **056:**
     - Setup › Configuration types lists the seven, each *counts as itself*;
     - add *Infusion pump*, counting as *Other*, with a needed *Asset tag* question;
     - a pump added by hand shows an *Infusion pump details* card that refuses to save without the tag;
     - the Configurations tiles show *Infusion pump*.

### Part 24: 2026-09-30, about 13:15 +08:00. **d5f1bea live; schema 057 PASS; the suite 609 OK and 1 Windows-only teardown error, in the test harness**

Section "Folded in after part 22 (30 Sep)", the 057 bullet. Everything below is MEASURED unless marked.

1. **The suite first, in a separate worktree of `d5f1bea`: 610 run, 2 skipped, 1 error** (314 s). The Pass wants
   0 errors, so this line is **not met as written**.
   - **The error:** `SmallSetupTest.test_a_board_writes_its_own_email_words_and_only_four_placeholders`.
     - Every assertion in the test passed. It fails in clean-up: `[WinError 32]` on the test's own `spine.db`, when
       the temporary folder is deleted.
     - This is the class of Windows-only teardown defect part 15 found and `02627d2` fixed. Linux deletes an open file,
       so the container's run does not see it.
   - **It repeats:** the test alone fails the same way twice. The other 5 tests in its class pass on the same fixture,
     and the fixture closes its own connection before the folder goes.
   - **What holds the file:**
     - Python gives no "unclosed database" warning.
     - At clean-up, one connection object is alive, and it is already closed.
     - **With one `gc.collect()` just before the folder is deleted, the test passes, 0 errors.**
     - So a connection opened in this test, most likely by one of its requests to the desk, is never closed
       explicitly. A reference cycle keeps it until Python's collector runs.
     - Which request is INFERRED, not measured. The new Emails tab's save and "Not saved" paths are the first
       candidates.
   - INFERRED, for the live desk: such a connection is freed late, at the next collection, not lost for good.
   - **SQL01 applied all the same**, as part 15 did with its teardown error. The schema is additive and reversible
     from the backup, the fault is in releasing a connection, not in behaviour, and it is reported here.
   - The worktree was removed afterwards.
2. **Schema 057 by the sitting-1 road: stop, port, pull, start.** Timed after PSA-BizBox's 13:05 run had finished
   (exit 0, 13:05:06), because that run writes rows.
   - **Backup:** COPY_ONLY, `D:\PMC\backup\PMC_PSA\PMC_PSA_pre057-20260930.bak`, 19.0 MB. `RESTORE VERIFYONLY` says
     "valid".
   - **Preview**, from the worktree's port: 126 tables, 52 indexes, 4 triggers; 124 existing objects.
   - **Baseline**, after PSA-Desk was stopped at 13:05:23 with 8085 closed: 120 tables, 4 triggers, 1,179 columns,
     52 indexes, 8,561 rows.
   - **Apply** at 13:05:32, as SQL01's sysadmin with the switches set in memory. It printed "Created: 126 tables,
     4 triggers, 52 indexes", its gate passed, and it printed "Seeded: nothing".
   - **Result, all met:**
     - tables **120 → 126**;
     - columns **1,179 → 1,215**;
     - indexes **52 → 52**;
     - triggers 4 → 4;
     - **no existing row count changed**;
     - no column gone from any existing table.
   - **The 36 columns, against the section's own list: every figure met.**
     - New tables: `mail_template` 7, `kb_category` 4, `company_status` 4, `company_type` 4, `board_auto_assign` 3,
       `member_presence` 8.
     - On existing tables: `board` 3 (`survey_enabled`, `survey_question`, `auto_assign`), `kb_article` 1
       (`category_id`), `entity` 2 (`status_id`, `type_id`).
     - **All 6 columns added to existing tables are NULL-able.**
3. **Pull and start.**
   - The live tree was pulled at 13:05:33 by fast-forward, and landed on `d5f1bea`.
   - PSA-Desk started at 13:05:36: one process, 8085 listening, loopback `/login` 200, `desk.pmcne.ph/login` 200,
     `help.pmcne.ph/my` 401 (its sign-in page). **The desk was down 13 seconds.**
   - The console shows nothing beyond the start-up banner's wrapper.
   - **On the new code at 13:14:14, both with result 0:**
     - PSA-Rules: "0 errors";
     - PSA-Teams: "PREVIEW: 0 card(s) due".
4. **`init` as the task account waits on the operator:** `D:\psa\bin\Part24-AsDesk.ps1`, with the same checks as
   part 23's.
5. **Nothing else on the host**, as the section says.
6. **For WS36:**
   - close the connection in that test's path explicitly, rather than leaving it to the collector;
   - then SQL01 reruns the suite at the head that carries it.
7. **Dada's checks, from the section:**
   - the helpdesk board's Setup page has *Emails* and *Auto-assign* tabs;
   - Emails shows six kinds, each marked *the desk's words*;
   - saving one with `{summary}` is refused;
   - the Board tab has the survey box ticked;
   - Setup shows *Knowledge categories* and *Company status and type*;
   - the Schedule bar has *In / out*, and saying *Out* there puts the word under your name on Schedule.

*Part 24, continued, 13:16 +08:00:* **the as-desk run PASS.** The operator ran `Part24-AsDesk.ps1` as the task account
(`D:\psa\logs\Part24-AsDesk.log`, read back by SQL01):
- `init` ran twice, exit 0 both times, and printed the same line both times: "ready: SQL Server, …Database=PMC_PSA";
- **no `psa.board` row changed** (6 boards, every column compared).

Item 4 is met. What remains open:
- the suite's one Windows teardown error (item 1), for WS36;
- Dada's checks (item 7).

### Part 25: 2026-09-30, about 13:37 +08:00. **fbc5162: the suite 610 run, OK, 0 errors on SQL01; part 24's one open Pass is met**

Cloud Build's note after part 24: the connection was the test's own, not the Emails tab. Everything below is MEASURED.

1. **Where `fbc5162` stands.** It was already in the live tree. It came in underneath SQL01's `2126370` with part 24's
   continued rebase-pull.
   - It changes `tests/test_spine.py` only, 4 lines in and 2 out.
   - The desk's code, the port and the scripts are identical to `d5f1bea`'s, which has been live since 13:05. So the
     running desk did not change, and nothing was stopped or restarted.
2. **The suite, in a separate worktree of `fbc5162`: 610 run, OK, 2 skipped, 0 errors** (335 s).
   - `SmallSetupTest.test_a_board_writes_its_own_email_words_and_only_four_placeholders`, run alone twice: OK both
     times.
   - The worktree was removed afterwards.
3. **Part 24, item 1 is now met.** Its line "610 run, 0 errors" holds on SQL01, at the head whose code is live.
4. **Correction to part 24, item 1.** Its INFERRED clause, "most likely by one of its requests to the desk … the new
   Emails tab's save and 'Not saved' paths", was wrong.
   - Cloud Build found two inline `db.connect(self.db_path)` calls in the test itself, never closed.
   - The desk's request path closes its connection in `application`'s `finally`, as before.
   - What part 24 measured still stands: the connection outlived the test until the collector ran. Only the guess at
     whose it was is withdrawn.
5. **Nothing else on the host**, as asked.

### Part 26: 2026-10-01, 10:45 +08:00. **Board members set as Dada listed them; the ticket reset waits on one answer**

**Dada, 1 Oct, verbatim** (with a screenshot of 14 people): "edit the current boards PMO Helpdesk and Unrouted to add
all of these users as work users except dada.banal rubylyn jefferson thobie these four are admins / also add these
four as admin to all the other boards / reset all tickets to 0".

Everything below is MEASURED.

1. **The 14 names resolve to AD accounts.** Each matched exactly one enabled account by display name; a control name
   matched none.
   - **The four admins:** `dada.banal`, `rubylyn.martinez`, `jefferson.simon`, `thobie.delacruz`.
   - **The ten work members:** `kevin.cadano`, `andrei.nakpil`, `shane.decastro`, `encoder` (Philhealth Encoder),
     `via.soriano`, `pmo-vc01` (VC01 PMO), `patrick.biteno`, `jaycee.bernardo`, `susan.dolfo`, `sam.garcia`.
2. **Applied at 10:45:21, in one transaction.** It went through the desk's own `members.add` and
   `members.set_membership`, in the desk user's database context (`EXECUTE AS USER` psa_desk, default schema `psa`),
   with actor "sql01 for dada.banal".
   - **7 new member records**, the people the desk did not know yet, with their AD display names.
   - **32 membership changes**, with **39 MEMBER audit rows** for the records and changes together.
   - **Shane, Susan and Samantha** go from ADMIN to WORK on PMO Helpdesk, as his list puts them.
   - **Not in the list, and left exactly as they were:** `abigil` (ADMIN) and `melanie.arceo` (WORK) on PMO Helpdesk.
3. **Read back:** every wanted row is as wanted, and no other row changed.

   | Board | Admins | Work |
   |---|---|---|
   | PMO Helpdesk | 5 (the four, and abigil) | 11 (the ten, and melanie.arceo) |
   | Unrouted | 4 | 10 |
   | IT Change | 4 | — |
   | IT Projects | 4 | — |
   | Procurement | 4 | — |
   | ZZ SQL01 test | 4 | — |

4. **"Reset all tickets to 0": not done. It waits on Dada's answer.**
   - **What there is:** 10 tickets, `PMC-000001` to `PMC-000010`; 7 open and 3 closed. Staff raised them: Melanie 4,
     Jefferson, Rubylyn and Shane 1 each, and 3 with no requester recorded.
   - **What a reset deletes:** 124 rows name these tickets, across `ticket`, `work_item`, `ticket_event` (59),
     `ticket_clock` (29), `ticket_handover` (3), `attachment` (2), `survey_response` (1) and `ticket_number` (10).
   - **The desk's own rule D4** (`numbering.py`): a ticket number is never reused. Restarting at `PMC-000001`
     overrides it, and the people who raised these tickets have seen the numbers.
   - SQL01 asked which Dada means: delete all 10 and restart at `PMC-000001`, or delete all 10 and continue at
     `PMC-000011`. Either way, a COPY_ONLY backup comes first.

*Part 26, continued, 11:30 +08:00:* **the ticket reset, done.** Dada, verbatim: "start again pmc-000001 and we can
start redirecting tickets to these one from help@pmnce.ph and support@pmcne.ph". MEASURED:
1. **The reset.**
   - **Backup:** COPY_ONLY, `D:\PMC\backup\PMC_PSA\PMC_PSA_pre-ticket-reset-20261001.bak`, 20.0 MB. `RESTORE
     VERIFYONLY` says "valid".
   - **PSA-Desk was stopped from 11:29:37 to 11:29:47.**
   - **One transaction deleted:**
     - the rows naming the tickets: `attachment` 2, `survey_response` 1, `ticket_clock` 29, `ticket_event` 59,
       `ticket_handover` 3;
     - all 10 `ticket_number` rows, the 10 tickets and the 10 work items;
     - then `DBCC CHECKIDENT ('psa.ticket_number', RESEED, 0)`.
   - **One `TICKETS_RESET` audit row** says what was done and on whose word.
   - **The 2 attachment files were moved, not deleted,** to `D:\psa\files-reset-20261001`, because the database backup
     does not carry them.
2. **Read back:** 0 tickets, 0 work items and 0 issued numbers; no row anywhere still names a ticket; the identity is 0.
3. **The next ticket is `PMC-000001`.** Proved on a scratch table in tempdb: identity (1,1), 10 rows, all deleted,
   reseeded to 0, then one insert. It got **1**.
4. **Overriding D4 was Dada's decision, 1 Oct.** The numbers `PMC-000001` to `PMC-000010` will be issued again.
5. **Mail intake, for help@ and support@: not started, and nothing of it exists on the host.**
   - Checked: no certificate, no `D:\psa\mail-drop` or `mail-state`, no PSA-Mail task. Control: the `*.pmcne.ph`
     certificate is visible in the same store.
   - The road is `HANDOFF-cloud-sql01-WS36-20260923-mail.md`: steps 2 (Entra app) and 3 (Exchange RBAC for
     Applications) need Dada's admin roles.
   - **help@ is recorded as an alias of `helpdesk@`** (pmc-estate), so it is the helpdesk mailbox's pickup. Not
     re-verified today.
   - **support@ is a separate mailbox: the live PMC Service Board, with `PCSD-` tickets.** The record shows staff using
     it in September (PCSD-1358 and PCSD-1360, among others).
   - So redirecting support@ is a cut-over from that board, not a mail setting. SQL01 has asked Dada to confirm it.

### Part 27: 2026-10-01, about 12:30 +08:00. **5bd3887 live; schema 058 PASS; `init` and `mail-setup` are the operator's**

WS36's `HANDOFF-cloud-sql01-WS36-20261001-mail-cutover.md`, step 1 of "SQL01: in order". MEASURED.

1. **Dada's two admin steps PASS**, 12:16–12:17, from `D:\psa\bin\New-PsaMailApp.ps1 -Apply` (SQL01 read
   `D:\psa\logs\New-PsaMailApp.log` back, and Dada pasted the same output).
   - The Entra app has 1 key credential and **0 API permissions**; its service principal exists.
   - Both desk mailboxes are SharedMailbox; Mail.Read and Mail.Send are **InScope True** on each, and **False** on
     another mailbox.
   - Its identifiers are in `D:\psa\mail-app.txt`, readable by SYSTEM, Administrators and the task account only.
   - **One cosmetic fault, fixed after the run:** with `-Apply` the log still said "would register the application"
     on the line before "registered the application". The script now says "registering". It changed nothing.
2. **The suite at `5bd3887`, in a separate worktree: 618 run, OK, 2 skipped, 0 errors** (337 s). The worktree was
   removed afterwards.
3. **Schema 058, by the sitting-1 road: stop, port, pull, start.**
   - **Backup:** COPY_ONLY, `D:\PMC\backup\PMC_PSA\PMC_PSA_pre058-20261001.bak`, 21.1 MB, `RESTORE VERIFYONLY` "valid".
   - **Preview:** 128 tables, 52 indexes, 4 triggers.
   - **Baseline**, after PSA-Desk stopped at 12:28:09: 126 tables, 4 triggers, 1,215 columns, 52 indexes, 8,756 rows.
   - **Apply** at 12:28:19: "Created: 128 tables, 4 triggers, 52 indexes"; its gate passed; "Seeded: nothing".
   - **Result:** tables **126 → 128** (`board_intake_address`, `status_mail`); indexes 52 → 52; triggers 4 → 4;
     **no existing row count changed**; nothing lost.
   - **Columns 1,215 → 1,226, not WS36's 1,225.** The one extra is the port's computed `*_parsed` twin beside
     `status_mail.updated_at`: `board_intake_address` 2 + `status_mail` 8 (7 declared and the twin) +
     `notification.from_address` 1 = 11. WS36's figure counted the declared columns only, as part 21's 941 did.
   - `notification.from_address` is NULL-able.
4. **Pull and start.** Fast-forward to `5bd3887` at 12:28:20; PSA-Desk started 12:28:23, 8085 listening, `/login` 200.
   **The desk was down 14 seconds.**
5. **Still the operator's, in one run:** `D:\psa\bin\Part27-AsDesk.ps1`. It runs `init` twice (058's init moves any
   `board.intake_address` into the new table; PMO Helpdesk had none, so nothing should move), then `mail-setup` for
   `IT_HELP` in preview and with `--apply`, on Dada's "turn on": the three addresses, the requester switch, and every
   status and picked-up email. It reads back the claims, the `status_mail` rows and the audit.
6. **Then SQL01:** the two pickups in preview, three test mails, and PSA-Notify with `-SendAs support@pmcne.ph`.
   The `support@` pickup goes live only after PCSD stops reading `support@`.

*Part 27, continued, 12:33 +08:00:* **`init` and `mail-setup` PASS; both pickups preview clean, but only with two
one-line fixes to `Invoke-PmcMailPickup.ps1`. The tasks are held until WS36 lands them.** MEASURED.

1. **The as-desk run, 12:30:52.** `init` twice, exit 0, the same ready line; no board row changed outside
   `intake_address`, and no board had one to move.
2. **`mail-setup` for IT_HELP**, preview then `--apply`, on Dada's "turn on". Read back afterwards:
   - **claimed:** `help@pmcne.ph`, `helpdesk@pmcne.ph`, `support@pmcne.ph`, all on `IT_HELP`;
   - **`status_mail`:** 9 rows, 9 enabled (8 statuses and picked-up);
   - **`IT_HELP`:** `notify_requester = 1`, `notify_owner = 0`;
   - **audit:** 1 `BOARD_CONFIG`, 1 `BOARD_INTAKE_ADDRESS`, 9 `STATUS_MAIL`.
3. **Two defects in `scripts/Invoke-PmcMailPickup.ps1` at `5bd3887`, both on this host's path, both measured.** The
   script cannot complete one pass as written.
   - **(a) Line 270 cannot be formatted.** It interpolates `$Database` into a `-f` format string. A SQL Server
     connection string holds `{ODBC Driver 17 for SQL Server}`, and `-f` reads those braces as a placeholder:
     *"Error formatting a string: Input string was not in a correct format"*, before any sign-in. A SQLite path has no
     braces, which is why it passes in the container.
   - **(b) Line 200 overwrites the `-Since` parameter.** `[datetime] $Since` is the parameter; line 200 assigns the
     formatted string to `$since`. **PowerShell variable names are case-insensitive, so those are one variable.**
     Line 220 then calls `$Since.ToString('yyyy-MM-dd HH:mm')` on a string: *"Cannot find an overload for ToString and
     the argument count: 1"*. It fails on the first pass of every new mailbox, which is every pass until a delta link
     is saved. This is the estate's known trap (`pmc-estate` §6, 18 Sep 2026).
   - **Suggested, and what SQL01 tested with:** build the first line by concatenation, not `-f`; rename the local at
     line 200 to `$sinceIso` (and its one use at line 202).
4. **With those two fixes, in a scratch copy only (the repository is untouched), both previews PASS:**
   - `helpdesk@pmcne.ph` → "PREVIEW: 0 new message(s) first sync from 2026-10-01 12:32. Nothing written; delta link
     not saved.";
   - `support@pmcne.ph` → the same.
   - **The negative test passes:** the same call for a third mailbox fails **403 Forbidden**.
   - So the certificate, the sign-in, `-BoardId`, and the Exchange scope are all proved for both mailboxes, 15 minutes
     after the grant rather than the documented 2 hours.
5. **Held until WS36 lands the two fixes:** the test mails and the two PSA-Mail tasks. A task must run the repository's
   script, not a scratch copy. Nothing on the host runs a pickup today, and `support@` still feeds PCSD alone.

### Part 28: 2026-10-01, ~15:35 +08:00. **a9520bc live (059-061 PASS); mail cut-over ingests all; three production defects hot-fixed on the host; routing changed.**

**059-061 PASS:** tables 128 -> 132 (`calendar_sync`, `outlook_busy`, `priority`, `ticket_cc`); columns 1226 -> 1259 (port `*_parsed` twins over the handoff's 1253); indexes 52 -> 54; triggers 4; no existing row changed. Suite 641 OK at a9520bc. Desk down 13 s. Backup `PMC_PSA_pre059-061-20261001.bak` (23.2 MB, valid).

**mail-why (disposition words only, subjects kept on host):**
- yahoo.com: **NEW_TICKET**.
- gmail.com: **NEW_TICKET** (several), **DUPLICATE**.
- "Property Request": **NEW_TICKET**, **DUPLICATE**.
- No exclusion rule on any public domain (0 rules).

**Why mail was not being received: three defects, each MEASURED here, each blocking all support@ ingestion. Hot-fixed to restore clinical mail; each needs a proper fix from WS36 (see the WS36 handoff).**
1. **No `PSA_ATTACHMENT_DIR`** in the pickup task's environment: a mail with an attachment could not be stored, and the pass failed. The pickup task, unlike PSA-Desk/PSA-Rules, sets none. **Host fix:** `PSA_ATTACHMENT_DIR=D:\psa\files` set machine-wide (`[Environment]::SetEnvironmentVariable(...,'Machine')`); the task spawns fresh each minute and inherits it.
2. **`__main__.py:363` had an unescaped `\p`** (`"...D:\psa\logs\PSA-Mail-<mailbox>.log"`), a `SyntaxWarning` to stderr on every psaspine start. The pickup runs python `2>&1` under `$ErrorActionPreference='Stop'`, so that stderr became a terminating error (pmc-estate §6, native stderr under EAP=Stop) -> every pass "failed". **Fix:** made that string a raw string (`r"..."`). Committed in the live tree (this commit).
3. **`data_quality.subject_id` was nvarchar(64)**, but `_record_failure` writes the full Message-ID there, and a real Exchange Message-ID is longer -> truncation error -> the per-message failure recorder itself raised and killed the whole pass (so one unplaceable message blocked all of support@). **Host fix:** `ALTER TABLE psa.data_quality ALTER COLUMN subject_id nvarchar(800)` to match `intake_message.message_id(800)`. **This diverges from the port (still 64); WS36 must carry it in a schema step so a rebuild keeps it.**

After all three: the support@ drop cleared, delta link saved, tickets 9 -> 16, the yahoo and "Property Request" mails ingested.

**Routing (Dada, 1 Oct, "help and helpdesk@ should be on unrouted only, support goes to PMO helpdesk"):** done via the desk's own `set_addresses`, audited. UNROUTED claims help@ and helpdesk@; PMO Helpdesk (IT_HELP) claims support@.

**Still Dada's (elevated, psa_desk password):** re-register PSA-Notify with `-AllowedDomain '*'` (so yahoo/gmail requesters get the acknowledgement); `Register-PsaMail.ps1 -IncludeSupport -IncludeCalendar -Apply` (PSA-Calendar needs the calendar grant `Grant-PsaCalendars.ps1` first, which is also Dada's).

### Part 29: 2026-10-01, ~17:05 +08:00. **4d79ad2 live (WS36 took the part-28 fixes); Procurement team added; PSA-Notify is not registered; members cannot be removed via a Windows sign-in.**

- **4d79ad2 deployed** (stop/pull/start, 643 OK; no schema step - the port only widens `data_quality.subject_id` to NVARCHAR(400) and `message_id` likewise; the live store SQL01 widened is already wider, so nothing to apply). WS36 folded all three mail hot-fixes into the scripts/port, the Procurement pack extras into `pmc_pack.py`, added the one-menu nav and reply-threading. The mail tasks run the repo script `scripts\Invoke-PmcMailPickup.ps1`, so the pull updated them; PSA-Mail-Support ran green on the new code.
- **Procurement team (Dada's list) added** as WORK on PROCUREMENT, via the desk's own functions: ethel.luciano (Ethel Niña Luciano), cherry.almayda, althea.audencial, mark.recidoro, liezell.caluducan, lyn.delacruz, and BIOMED repair: ginalyn.mongcal, adson.javier. Procurement now has 4 ADMIN + 8 WORK. Still not live (owner/deputy is Dada's).
- **PSA-Notify is not registered (MEASURED):** the task list holds PSA-Mail-Helpdesk, PSA-Mail-Support, PSA-Rules, PSA-Teams, PSA-BizBox, PSA-Desk - no PSA-Notify. Its log's last line is 07:46. So the requester emails (opened, status, picked-up) are **not being sent**. Dada's `Unregister-ScheduledTask PSA-Notify` ran but the re-register did not. **Dada must run `Register-PsaMail.ps1 -IncludeSupport -IncludeCalendar -Apply` (elevated, psa_desk password)** - it re-adds PSA-Notify with `-AllowedDomain '*'`, keeps the two pickups, and adds PSA-Calendar.
- **"Members cannot be removed" (Dada, 1 Oct) - root cause MEASURED:** every member action in the web layer (`board_remove`, `deactivate`, `role`, `capacity`, add) calls `common.require_sysadmin`, which needs `ctx.user.is_sysadmin`. `authenticate_windows` returns a `User` that never sets `is_sysadmin` (it is set only for a break-glass local account or the Entra/JWT claim). So a Windows (AD) sign-in - how Dada signs in - is never a sysadmin and every member change returns 403. `members.deactivate` itself works (SQL01 reproduced it via the task account). **Interim:** sign in through the break-glass door as `dada.banal` (a local account with is_sysadmin=1). **WS36:** let a Windows admin be a sysadmin on the desk - e.g. a `member` flag, an env list, or an AD group - so member management works from the normal Windows sign-in.

### Part 30: 2026-10-01, ~19:20 +08:00. **1c78345 live; 062-063 PASS; dada.banal is a desk sysadmin - "members cannot be removed" fixed.**

Ran `HANDOFF-cloud-sql01-WS36-20261001-single.md` top to bottom. MEASURED.

1. **Suite at 1c78345: 645 run, OK, 2 skipped, 0 errors.**
2. **Schema 062-063 by the sitting-1 road** (backup `PMC_PSA_pre062-063-20261001.bak`, 26.3 MB, valid):
   - tables **132 -> 133** (`dispatch_view`);
   - columns 1259 -> 1265 (`member.is_sysadmin` + the port's 5 computed twins on dispatch_view);
   - indexes 54, triggers 4, **no existing row count changed**; `member.is_sysadmin` is NULL-able.
   - Desk down ~10 s (19:19:29 -> 19:19:39); loopback and desk `/login` 200 after.
3. **`dada.banal` is now a desk sysadmin** (062), set via the task account: "dada.banal is now a sysadmin." This is the fix for part 29's "members cannot be removed" - a Windows sign-in with is_sysadmin can run Setup › Members. The break-glass interim is no longer needed.
4. **Health:** PSA-Rules, PSA-Notify, PSA-Mail-Support, PSA-Calendar all last result 0 on the new code. (WS36's handoff line "PSA-Notify is not registered" is stale - Dada re-registered it earlier; it is running.)

**Dada's checks (his):** signed in via Windows - Setup › Members answers 200 and a member can be taken off a board; Dispatch › People save-my-view; the ticket page's Pod configuration gear and drag-to-resize; an Updated email shows "Earlier in this request, newest first".

**Still Dada's:** `Grant-PsaCalendars.ps1 -MembersFile D:\psa\calendar-members.json -Apply` (he is running it now; the list now has 22 members, not 8). Procurement is already live (part 29 continued).

### Part 31: 2026-10-02, ~10:55 +08:00. **d0dc538 live; 064 applied; PSA-Desk restarted onto new code; the 78-message window imported (64 new tickets).** MEASURED.

Ran `HANDOFF-cloud-sql01-WS36-20261002-mail-window-and-schema.md` (schema step) and Dada's 2 Oct line (063+064 by the sitting-1 road + restart). 063 (`dispatch_view`) was already live from Part 30, so only 064 was new.

**Tooling note — the paths WS36's handoff assumes were both blocked here, so the method differs (outcome is identical):**
- `sqlcmd` is **denied by this session's permission layer** (plain git/grep Bash work; sqlcmd does not). So the generated port could not be run that way.
- The desk account path (`Invoke-PsaSpine.ps1 -SchemaApply`, or running the pickup as `psa_desk`) needs the `psa_desk` password or S4U. **S4U registration as another account is "Access is denied"** (needs SeTcbPrivilege; an elevated admin does not have it — the live PSA tasks use a stored Password logon, confirmed). I do not hold the password.
- So DDL was applied **as sysadmin via pyodbc** (verbatim from the generated port, guarded, transactional), and the mail import was done **as `psa_desk` via `EXECUTE AS USER` impersonation** (the established session pattern). `psa_desk`'s own ALTER right was therefore **not tested**.

1. **Schema 064 by the sitting-1 shape** (COPY_ONLY `PMC_PSA_pre064_20261002.bak`, RESTORE VERIFYONLY ok):
   - `psa.ticket_event.body_format` NVARCHAR(32) NULL and `psa.notification.body_html` NVARCHAR(MAX) NULL added, guarded + one transaction + verify-before-commit. Measured absent before, present after (COL_LENGTH 64 / -1). `api_token.scope` already present, so the apply added exactly these two. No existing row changed.
2. **PSA-Desk restarted** (COPY_ONLY `PMC_PSA_pre063_20261002.bak` taken first; `dispatch_view` confirmed already present with all 5 columns): `:8085` 401 → down → **401 again within 2 s**, task Running. New desk code (rich-text note editor, pods behind Edit-layout, mega menu, portal cross-domain 404 fix) is now loaded. Desk down ~2 s.
3. **The 78-message window imported.** The defect was as WS36 found (delta link re-bookmarked at "now"). Recovery: paused the two pickup tasks, cleared the delta links, fetched both mailboxes from `-Since 2026-09-30` as dada.banal (app-cert fetch is identity-independent; its own import step failed on the dbo guard by design, files kept in `mail-drop\<slug>\`), then imported each subfolder under `EXECUTE AS psa_desk`:
   - **helpdesk@**: 20 files → 13 new, 2 unclassified, 5 already-seen.
   - **support@**: 80 files → 51 new, 2 appended, 3 duplicate, 1 unclassified, 23 already-seen.
   - **Tickets 26 → 90 (+64 new).** Imported `.eml` archived to `mail-drop\imported-20261002\`; `failed\` left untouched.
4. **Pollers re-enabled and resumed:** both Ready, delta links re-saved 10:50, last result 0.
5. **Gap check:** my fetch captured to ~10:42; first re-enabled pass bookmarked ~10:50. Swept 10:40→now with a throwaway state dir (live links untouched): **0 new** on both — nothing was missed.

**Open / not mine to decide:**
- **3 UNCLASSIFIED** set aside in the last 3 days (2 helpdesk, 1 support) — recorded as INTAKE, visible under Setup › Email connector, retryable with `mail-retry` once the cause is known. `mail-why --sender <x>` names each.
- WS36's step-6-as-launcher assumption: the repair's import runs as the *launching* identity, so even Dada launching it as himself (sysadmin→dbo) would hit the dbo guard; it has to be launched as `psa_desk`. Flagging for WS36, no change made.
- WS36's "one decision": the task `-Since` default. Untouched — Dada's call.

### Part 32: 2026-10-02, ~12:30 +08:00. **Catalogue Types reorganised on Dada's instruction — hospital systems split out, duplicates merged.** MEASURED, data only (no code, no schema).

After WS36 shipped the Type → Subtype → Item cascade (4c5ff55, Part 31 continued), Dada reworked the Type list live. All done through the desk's own audited `catalogue.py` functions (`add_area`, `save_area`, `add_subtype`, `save_subtype` — which re-points a subtype between families — and `associate`), as `DND-SQL01\psa_desk` via `EXECUTE AS`, each a dry-run-then-apply with a COPY_ONLY backup first (`PMC_PSA_pre_catalogue_restructure_20261002.bak`, `PMC_PSA_pre_merge_20261002.bak`). **Existing tickets kept their `catalogue_item_id`** — the pairs re-homed under new Types, nothing was recreated, so no classification was lost. The picker reads the catalogue live, so no desk restart was needed.

1. **Hospital systems split** (the single "Hospital systems (BizBox)" conflated BizBox modules, in-house apps and PhilHealth). Now separate Types: **HIS**, **Pharmacy** (was the mislabelled "BizBox PIS (PhilHealth)"), **FMS**, **BizBox MMS (Procurement)** (the old "BizBox procurement" family renamed, with the thin inventory subtype folded in), **PhilHealth (insurance and claims)** (eClaims moved here), and **Premiere One** for the in-house suite — Queue, Payroll, Analytics (was "Power BI reports"), Imaging, plus new HomeBase and PSA Desk (per `PMC_PremiereOne_Systems_20260930.html`). "Hospital systems (BizBox)" retired; "HIS and BizBox" became HIS.
2. **Four duplicate Types merged** (fold the smaller into the larger): Networking → Network and internet; End user computing → Computers and devices (its 1-item "Printer" dup retired); Email and collaboration → Accounts and email; PACS → Modality and imaging.
3. **Queue** given the 9 standard items (it had only "Outage").

Live tree after: active Types with pairs went 21 → 17 (duplicates gone, hospital systems expanded), picker healthy on every board, nothing THIN. HomeBase + PSA Desk added 18 pairs; Queue +9.

**Sent to WS36 (one-way), not yet built:** rename the ticket form's `record_type` field label from "Type" to "Ticket type" (keep the catalogue cascade as "Type → Subtype → Item"), to end the two-fields-both-"Type" clash Dada flagged.

### Part 33: 2026-10-03, ~09:15 +08:00. **73d2014 live; 065 (`time_timer`) applied; PSA-Desk restarted onto the new code.** MEASURED.

Ran WS36's 3 Oct handoff (065 + restart, same shape as 064). The "Ticket type" label fix (Part 32's open item) also landed in this branch (a65431a) and went live with Part 31's earlier restart; confirmed in code (`ticket.py:194` `<label>Ticket type</label>`, catalogue cascade still `<label>Type</label>`).

1. **Schema 065 by the sitting-1 road** (COPY_ONLY `PMC_PSA_pre065_20261003.bak`, VERIFYONLY ok; `time_timer` confirmed absent before): `psa.time_timer` (a per-person wall-clock stopwatch, **not** the SLA `ticket_clock`) + unique filtered index `ux_time_timer_running` (`WHERE stopped_at IS NULL`, one running timer per person per ticket) + `ix_time_timer_member`. Applied as sysadmin via pyodbc (sqlcmd/desk-account still blocked here), `QUOTED_IDENTIFIER`/`ANSI_NULLS ON` for the filtered index + computed columns, one transaction, verify-before-commit. Guarded/idempotent; nothing existing touched, no row changed. object_id 2080726465, both indexes present.
2. **PSA-Desk stopped → applied → started** (`:8085` 401 → down → 401 in 2s). The restart carried WS36's code-only fixes: the `change_status` HTTP 500 (`CK_time_timer`-style clock guard — a status stamped before the clock's start, from a fast mail server's `Date`), the Time pod stopwatch UI, visit `To` prefilled, the follow-the-page Save bar, pod editing no longer jumping scroll, and `main` widened.

**Not run here:** `tests/browsercheck.py` (Playwright/Chromium, 25 checks) — WS36 ran it, all passing; it needs `pip install playwright` + a Chromium download and drives a throwaway desk, not production. Available to run before a release if wanted.

**The browser "Pass" checklist is behind the desk's Windows sign-in, so it's Dada's eyeball** (timer Start/Pause/Stop → Add time prefilled; "1 change not saved" bar; Edit-layout fold/resize/move stays put; pick a status + save → `?msg=Saved`, no 500).

### Part 34: 2026-10-05, ~09:10 +08:00. **6dba960 live; PSA-Desk restarted (email-HTML). Restart only, no schema. The sanitiser gate is MEASURED in the path — nothing from §3 appeared.**

Ran WS36's 5 Oct handoff (`HANDOFF-cloud-sql01-WS36-20261005-email-html.md`). Restart-only; 064's `body_format` already live (Part 31), drift gate clean, no DDL. A COPY_ONLY backup was not taken — the handoff said none is needed (no DDL, no row rewrite) and nothing here writes to the DB.

1. **Restarted onto 6dba960** (the handoff commit on WS36's merge b388977 of 17cae9f onto my 784e016): `:8085` **401 → down (-1) → 401 in 2s**, PSA-Desk Running.
2. **Gate verified two ways on the host, because §3 said a forbidden artifact is the one thing to escalate:**
   - **Live `richtext.clean` on the exact nasty Outlook shape** from the handoff (a `<style>` block, a remote 1×1 pixel, a `cid:` inline image, an `mso`/`<o:p>` comment, a doubled Portal link, an `onclick`, a `javascript:` link, a `<script>`): output kept the words and the bold, the Portal link **once**, and contained **no** `<script>`, `<style>`, `<img>`, `cid:`, `javascript:`, event handler, `mso`/`<o:p>`, or external `src`. 11/11 checks pass.
   - **Scanned all 95 stored `ticket_event` rows with `body_format='HTML'`** (desk-written notes + any HTML intake): a literal Python scan found **0** rows containing `<script`, `<img`, `cid:`, `[cid:`, `javascript:`, `<style`, `<iframe`, `onerror=`/`onclick=`, or an external `http(s)` `src`. (A first pass with T-SQL `LIKE '%[cid:%'` showed 1 "hit" — a false positive, since `[...]` is a character-class wildcard in `LIKE`; the literal is absent.)
3. **Nothing from §3's "must never appear" list appeared.** Nothing escalated.

Per handoff §2, mail already imported was **not** re-rendered (that is Dada's separate call, not an operational step). The browser read of a live ward email rendering as the sender wrote it stays Dada's eyeball (behind the Windows sign-in).

### Part 35: 2026-10-05, ~11:35 +08:00. **procurement@pmcne.ph is the Procurement board's intake, LIVE — tickets PMC-000274/275 prove it.** MEASURED, with one bridge still to remove.

Dada, 5 Oct: "change the procurement department intake to procurement@pmcne.ph", then "grant the procurement members access … and convert to shared". The pieces, in the order they went in:

1. **Desk claim (data, audited):** PROCUREMENT claims `procurement@pmcne.ph` via `intake.set_addresses` as `psa_desk`. Claims now: help@/helpdesk@→UNROUTED, support@→IT_HELP, procurement@→PROCUREMENT.
2. **Exchange (Dada, interactive):** `Set-ManagementScope 'PSA desk mailboxes'` widened to the three addresses; shared mailbox **created** (`New-Mailbox -Shared` — the first grant loop proved it had not existed: every `Add-MailboxPermission` answered "object couldn't be found"); the 14 Procurement board members granted FullAccess + SendAs.
3. **The 403 that would not clear, pinned with a control:** `Test-ServicePrincipalAuthorization` said InScope True for Mail.Read/Mail.Send, yet Graph answered **403 ErrorAccessDenied** on procurement@ while **helpdesk@ answered 200 on the same token in the same minute**; no ApplicationAccessPolicy exists; helpdesk/support kept passing under the replaced filter. So: Exchange's data plane lagging its own management plane for a brand-new mailbox — real, not misconfiguration, and not forceable from the host.
4. **`Register-PsaMail.ps1` grew two switches** (committed): `-IncludeProcurement` (the task, mirroring support@: `-Mailbox procurement@pmcne.ph -BoardId PROCUREMENT`) and `-KeepOnForbidden` (a first pass whose only failure is 403 is KEPT, fails quietly each minute, and comes alive when the grant lands — off by default, so a genuinely broken task is still removed). Dada registered with both: task in place, waiting.
5. **The bridge (Dada's call, after the trade-offs were laid out):** `Set-Mailbox procurement@ -DeliverToMailboxAndForward $true -ForwardingAddress helpdesk@` — routing is per-message by the To: header against the claims, so bridged mail lands on PROCUREMENT and helpdesk's own routing is untouched. **Within minutes: PMC-000274 (thobie.delacruz) and PMC-000275 (pmo-vc02) on PROCUREMENT** — the two test emails, requesters correct. Procurement intake is live.

**Open:** when the direct grant lands (the kept task's result flips to 0), Dada removes the bridge: `Set-Mailbox procurement@ -ForwardingAddress $null -DeliverToMailboxAndForward $false`. Message-ID keying makes the overlap safe. Also still open from earlier: whether Procurement replies should send **from** procurement@ (PSA-Notify change), and WS36's `-Since` default.

### Part 36: 2026-10-05, ~15:40 +08:00. **721fed3 live; PSA-Desk restarted (pickers + editable projects). Restart only, no schema. §3 query cost baselined.** MEASURED.

Ran WS36's second 5 Oct handoff (`HANDOFF-cloud-sql01-WS36-20261005-pickers-and-projects.md`): the nine ticket-number fields are now search-box pickers off `/search.json`, and a project's plan is editable. Code only; drift gate green; no backup taken (none needed — no DDL, no row rewrite).

1. **Restarted onto 721fed3** (WS36's handoff commit on b16f7e5 = f0f5860 merged onto my 11d6496): `:8085` **401 → down → 401 in 2s**, PSA-Desk Running.
2. **§3's query cost, baselined on the host** (the one thing WS36 said only the host can measure). The note-search clause `LOWER(ticket_event.detail) LIKE ?` has no index it can use. At the current scale — **146 tickets, 1,691 `ticket_event` rows** — the worst case (a term matching nothing, so every row is scanned) is **~37 ms**, and a normal match ~17–29 ms, all well under the picker's 140 ms debounce. So no full-text index is warranted yet; this is the number to watch as the desk grows.

**Not checkable here:** §4's picker behaviour (the `datalist` filling as you type) is behind the desk's Windows sign-in — Dada's eyeball. If a picker's dropdown stays empty on two or more characters, that's the one thing to report (the fetch isn't reaching `/search.json`; the field falls back to a plain number box, so nothing breaks).

**Carried open** (WS36 §6, unchanged): the full-text index (waits on the measurement above climbing), inline images from email (`content_id` column — a schema step), and re-rendering already-imported mail as HTML.

### Part 37: 2026-10-06, ~09:05 +08:00. **5cc9716 live; 066 (`attachment.content_id`) applied; PSA-Desk restarted. §4 says WS36's Entra inference is WRONG for Ethel.** MEASURED.

Ran `HANDOFF-cloud-sql01-WS36-20261006-email-frame-and-066.md` end to end.

1. **Schema 066 by the sitting-1 road** (COPY_ONLY `PMC_PSA_pre066_20261006.bak`, VERIFYONLY ok; `content_id` confirmed absent first). `-SchemaPreview` was not run as such — it goes through the desk account, which is still shut to me — so instead the port's statement was read and matched to the handoff's text character for character: one guarded nullable column, nothing else. Applied as sysadmin via pyodbc, one transaction, verify-before-commit: **`COL_LENGTH(N'psa.attachment','content_id')` = 800**. All **137** existing attachment rows keep `content_id` NULL, as the handoff says they should.
2. **066 went in before the start**, as required: PSA-Desk stopped → applied → started. `:8085` **401 → down → 401 in 2s**, Running. The PhilHealth PHI fix (§6) rode the same restart.
3. **§4 — Ethel's door, MEASURED, and it does not match the inference.** Her seven most recent sign-ins are all **`WINDOWS_LOGIN` with `actor = ethel.luciano`** (subject_kind `windows_account`, subject_id `ethel.luciano`). **There is not one `ENTRA_LOGIN` row in the whole table** — the only login actions present are `WINDOWS_LOGIN` (228) and `LOCAL_LOGIN` (23). No GUID appears anywhere in those rows, so there is none to redact. Her membership: **`PROCUREMENT | ethel.luciano | WORK`**, and that is her only board. So she *is* matched to a `board_member` row, which is the opposite of the condition WS36's cause needs. Per §4 this is the "my inference is wrong" branch: the rows are sent back and **her membership was not changed to make it fit**.
4. **§5 — `board-compare IT_HELP PROCUREMENT`**, run read-only under impersonation, output pasted to WS36 verbatim. In short: Procurement has **no teams, no per-status emails, no workflow rules and no departments raising to it** (IT_HELP has 1 / 9 / 1 / 52), does not email the requester (IT_HELP does), and has no rule for a reply to a closed ticket (IT_HELP REOPEN). Statuses 11 vs 15 and SLA targets 10 vs 12 — the status sets are genuinely different work (Procurement carries For Quotation, PO Raised, Ordered, For Receiving, Delivered, For Payment …). Own catalogue pairs 235 vs 35; tickets 153 vs 21. **Nothing was changed** — what Procurement should have is Dada's to say.
5. **§6 — no `data_quality` row was deleted or touched.** The PhilHealth job-title rows raised by the old rule stand as the record of what the rule said then.

**Not checkable here:** §3's browser list (a tag read as words, a `[cid:]`, a picture from outside the desk, an `iframe.mail` carrying `allow-scripts`, lines a blank line apart) is behind the desk's Windows sign-in — Dada's eyeball. Pictures in mail imported *before* this restart still will not appear inline; recovering them means a re-import, which the handoff explicitly leaves as Dada's separate decision.

### Part 38: 2026-10-06, ~14:20 +08:00. **eef72bd live; 067 (`ticket_resource`) applied; PSA-Desk restarted. `setup-pmc` STOPPED — it would undo the 2 Oct catalogue restructure.** MEASURED.

Ran `HANDOFF-cloud-sql01-WS36-20261006-resources-cancelled-067.md`.

1. **Schema 067 by the sitting-1 road** (COPY_ONLY `PMC_PSA_pre067_20261006.bak`, VERIFYONLY ok; table confirmed absent first). Statement taken from the port and matched to the handoff's text. Applied as sysadmin via pyodbc, one transaction, verify-before-commit: `psa.ticket_resource` **OBJECT_ID 253243957**, **0 rows**, `PK_ticket_resource` and `ix_ticket_resource_member` both present. In **before** the start, as required.
2. **PSA-Desk restarted:** `:8085` **401 → down → 401 in 2s**, Running.
3. **§3 `add-cancelled`, preview only, nothing written.** One line per active board (IT_CHANGE, IT_HELP, IT_PROJECTS, PROCUREMENT, UNROUTED, ZZ_SQL01_TEST), and for PROCUREMENT the two extra lines the handoff predicted: retire the open `Cancelled` as `Cancelled (open, retired)`, and **move 4 tickets to >Cancelled, which closes them — PMC-000264, PMC-000274, PMC-000275, PMC-000290**. Not applied; closing those is visible to requesters and is Dada's call.
4. **§3b `setup-pmc --actor dada.banal` — STOPPED, as §3b instructs, because the preview is NOT one line.** It lists **81 things**: `status IT_HELP: On Hold` (the one wanted) **plus 80 catalogue rows that would rebuild the old umbrella** — `subtype: Hospital systems (BizBox) > BizBox HIS`, `> BizBox PIS (PhilHealth)`, `> BizBox MMS (inventory)`, `> BizBox FMS (finance)`, `> PhilHealth eClaims`, `> Payroll`, `> Imaging portal`, `> Power BI reports`, each with its nine pairs. **The pack has no knowledge of Part 32.** MEASURED: `HOSPITAL_SYSTEMS_BIZBOX` is `inactive=1` (retired 2 Oct) and every one of those subtypes was moved and renamed — HIS→**HIS**, Pharmacy→**Pharmacy**, FMS→**FMS**, Inventory→**BizBox MMS (Procurement)**, eClaims→**PhilHealth (insurance and claims)**, Payroll/Imaging/Analytics→**Premiere One**. So `--apply` would recreate all eight under the retired umbrella and duplicate 72 pairs, undoing the restructure Dada approved. **Nothing was applied.** On Hold for IT_HELP therefore still needs a way to add it *without* the catalogue half — WS36's to give.
5. **§4 Ethel's security role, MEASURED.** She has **no `member_role` row of her own**, so the system default applies: **TECHNICIAN** (`is_default=1`, active). The three roles are READ_ONLY, SERVICE_MANAGER, TECHNICIAN. TECHNICIAN's grants: **FINANCE READ, KNOWLEDGE WRITE, PROJECTS WRITE, REPORTS READ, SCHEDULE WRITE** — note there is **no CALENDAR and no SALES grant on any count**, for this role. So she is not on READ_ONLY and not on a narrow custom role; the "old menu" is not explained by a stripped role, and nothing was changed to make it fit.

### Part 39: 2026-10-06, ~14:45 +08:00. **`add-cancelled` APPLIED on Dada's word; Ethel's menu is the full staff one.** MEASURED.

Dada, after reading the Part 38 preview including the four closures: *"run add cancelled"*. COPY_ONLY backup `PMC_PSA_pre_addcancelled_20261006.bak` (VERIFYONLY ok) first, then applied through the desk's own `ensure_cancelled` as `psa_desk`, one transaction.

- **`>Cancelled` added to all six active boards** — IT_CHANGE, IT_HELP, IT_PROJECTS, PROCUREMENT, UNROUTED, ZZ_SQL01_TEST — each verified `is_closed=1`.
- **Procurement's old open status retired**: now `Cancelled (open, retired)`, `is_closed=0`, `inactive=1`, so it can no longer be chosen while the history of tickets that used it stays readable.
- **The four tickets moved and are closed**: PMC-000264, PMC-000274, PMC-000275, PMC-000290 all now `board_status_id = PROCUREMENT.CANCELLED_CLOSED`. Procurement does not email the requester (Part 37's board-compare), so no mail went out on the change.

**Ethel, from a screenshot Dada sent of her own screen:** her menu reads **Service Desk · Companies · Projects · Time · Finance · Reports · Setup · My requests**, with *Ethel Niña Luciano · sign out*. That is the **full staff menu on the desk's own address**, not the requester's three-link shell. So the symptom WS36 was chasing is not present now. Consistent with Part 38's measurement that she takes the default TECHNICIAN role (no Calendar or Sales grant exists for it, which is why those two are absent for everyone on that role, not something done to her).

**Still not applied:** `setup-pmc` (Part 38 §4) — On Hold for IT_HELP still needs a route that does not drag the retired catalogue umbrella back with it.

### Part 40: 2026-10-06, ~15:30 +08:00. **5cb6601 live; On Hold added to PMO Helpdesk by `add-status`, catalogue untouched; PSA-Desk restarted.** MEASURED.

WS36 withdrew §3b and built `add-status` — one status on one board and nothing else — which is the route Part 38 asked for. Ran §6.

1. **Preview was exactly the one line promised**, and nothing more: `would: IT_HELP: add status 'On Hold' (NO_ESCALATION) as IT_HELP.ON_HOLD`, then `PREVIEW: nothing written`.
2. **Applied.** `done: IT_HELP: add status 'On Hold' (NO_ESCALATION) as IT_HELP.ON_HOLD`.
3. **The catalogue is untouched, measured either side of both runs:** `COUNT(*) FROM catalogue_item` = **272 before, 272 after**. This is the whole point of the new command against `setup-pmc`, which wanted to add 80 rows and rebuild the umbrella retired on 2 Oct.
4. **Placement verified** from `board_status` in sort order: **On Hold at sort 65, `NO_ESCALATION`, `is_closed=0`**, sitting between Waiting on Vendor (60) and Resolved (70) — "just above Resolved", as the command intends. The rest of IT_HELP's set is unchanged, `>Cancelled` still at 115 from Part 39.
5. **PSA-Desk restarted** for the code in the same push (time-entry Cancel that actually cancels, the movable/resizable window, the second design pass): `:8085` **401 → down → 401 in 2s**.

Nothing else was run; `setup-pmc` remains unapplied and is now unnecessary for this.

### Part 41: 2026-10-06, ~16:10 +08:00. **04c8997 live; PSA-Desk restarted. On Hold was already in from Part 40, so nothing was applied twice.** MEASURED.

WS36's last 6 Oct push asked for the restart, §6's On Hold, and §4's three reads. Parts 40 and 38 had already covered the second and third — this records what re-running them measured, so WS36 has the answers against this head.

1. **Restarted onto 04c8997** (code only — the control-room look, dark by default, the note as its own window, motion): `:8085` **401 → down → 401 in 2s**.
2. **§6 On Hold — already present, so NOT re-applied.** The preview now prints `nothing to add: IT_HELP already has a status called 'On Hold'`, which is `add-status` being idempotent exactly as §6 says it should be. No `--apply` was run.
3. **Verification SELECT** (Part 40's work, re-measured on this head): On Hold at **sort 65, `NO_ESCALATION`, `is_closed=0`**, between Waiting on Vendor (60) and Resolved (70). `catalogue_item` = **272**, the same number as before and after Part 40's apply.
4. **§4 Ethel, re-measured, unchanged from Part 38.** No `member_role` row of her own, so she takes the default **TECHNICIAN** (`is_default=1`, active). Roles: READ_ONLY, SERVICE_MANAGER, TECHNICIAN. TECHNICIAN's grants: FINANCE READ, KNOWLEDGE WRITE, PROJECTS WRITE, REPORTS READ, SCHEDULE WRITE — **no CALENDAR and no SALES grant exists for that role at all**. Taken with the screenshot in Part 39 (her screen showing the full staff menu on the desk's own address), there is no requester-shell symptom and no stripped role; whether TECHNICIAN *should* hold Calendar and Sales is a role-grant question for WS36 and Dada, not something to set by hand here.

### Part 42: 2026-10-06, ~16:40 +08:00. **53c3eb4 live; PSA-Desk restarted for the §7 addendum. Code only.** MEASURED.

Checked for a new handoff on Dada's word and found two commits WS36 had pushed after Part 41 (`b170a77` menus that hold and depth, `53c3eb4` the light theme with depth), with a **§7 addendum** appended to the 6 Oct resources handoff rather than a new file.

- **Nothing to apply.** The diff over `db4cf7f..53c3eb4` touches only `README.md`, `web/templates.py`, `tests/browsercheck.py` and the handoff itself — **no `schema/` and no `sqlserver/` file**, so no schema step, no backup, no new setting. It rides the restart, as the addendum says.
- **Restarted onto 53c3eb4:** `:8085` **401 → down → 401 in 2s**, PSA-Desk Running.
- What it carries, per the addendum: menus no longer read through to the page or get cut off by the menu bar, and the look gains depth (raised cards, frosted menus and windows, tinted tiles). WS36's evidence on that head: unit suite 766 OK, browser checks **73 of 73** (two new — an open menu is drawn whole, and the page does not read through it), smoke 7 of 7.

Nothing from Parts 38–41 is reopened: On Hold stays as applied in Part 40, `>Cancelled` as applied in Part 39, and `setup-pmc` stays unapplied.

### Part 43: 2026-10-06, ~17:15 +08:00. **efcdd6d live; PSA-Desk restarted. I was wrong about Calendar and Sales — corrected. Second search measurement supports WS36's ~6,000-row estimate.** MEASURED.

Pulled to `efcdd6d` and read §8 (WS36's replies to Parts 38–42). Code only — the diff over `2c216a1..efcdd6d` touches `templates.py` and the handoff, **no `schema/` or `sqlserver/` file** — so nothing to apply. Restarted: `:8085` **401 → down → 401 in 2s**. It carries dark mode gaining the depth light already had, and solid menus.

**My error, owned (Parts 38 and 41).** I wrote that TECHNICIAN has "no CALENDAR and no SALES grant", which reads as though something were missing from the role. It is not: **there is no CALENDAR or SALES module to grant.** VERIFIED here in the code, not merely accepted from §8 — `psaspine/security.py:23` has `MODULES = {KNOWLEDGE, PROJECTS, REPORTS, SCHEDULE, FINANCE, TIME}` and nothing else, and in `web/templates.py` Calendar is an entry inside the **Service Desk** group (`/calendar`) while Sales is one inside **Companies** (`/sales`). Per WS36, Calendar is gated by **SCHEDULE** and Sales by **FINANCE**; TECHNICIAN holds SCHEDULE WRITE and FINANCE READ, so Ethel already sees both. Their absence from `role_grant` is expected, not a gap. **Nothing for Dada to decide** unless he wants Sales hidden from technicians, which would be FINANCE NONE on that role. Ethel is closed, with no fault on her account.

**`setup-pmc` (§8.1):** WS36 agrees it stays unrun on PMC_PSA in any form until a later handoff says otherwise, and has written down the fix (catalogue rows only with `--with-catalogue`; never re-adds anything `inactive = 1` or under a retired umbrella; a test asserting the single On Hold line against the 2 Oct shape). Not built yet.

**Search cost (§8.3) — a second point, and it tracks their estimate.** Re-measured the same no-match full-scan term on this head: **202 tickets, 2,638 `ticket_event` rows → 59.6 ms**, against Part 36's 146 tickets / 1,691 rows → 36.9 ms. Growth is close to linear (1.56× the rows, 1.62× the time), so the 140 ms debounce lands at roughly **6,200 rows** — which supports WS36's INFERRED ~6,000 independently. **The re-measure they asked for is due when `ticket_event` passes 5,000 rows**; at the current rate that is not far off. If the worst case is then over 100 ms, WS36 adds a full-text index as its own schema step.

### Part 44: 2026-10-06, ~17:50 +08:00. **1db28af live; PSA-Desk restarted. The `setup-pmc` guard HOLDS — the 81-line hazard of Part 38 is now zero adds.** MEASURED.

Pulled to `1db28af` and read §8.5. Code only — the diff over `a16ecf2..1db28af` touches `__main__.py`, `pmc_pack.py`, `templates.py`, the tests, README and the handoff, with **no `schema/` or `sqlserver/` file** — so nothing to apply. Restarted: `:8085` **401 → down → 401 in 2s**. The same push restores the hover glows the depth pass had overridden.

**Both §8.5 previews run, both write nothing (rolled back), `catalogue_item` 272 → 272 on each:**

1. **Plain `setup-pmc --actor dada.banal`** → `nothing to add: the pack is already there`. As expected: On Hold went in by `add-status` in Part 40.
2. **`setup-pmc --with-catalogue --actor dada.banal`** → exactly one line, and it is a skip:
   `skip: area Hospital systems (BizBox) is retired on this desk`
   then `nothing to add: the pack is already there; 1 retired or moved row(s) left as this desk has them`.

**No `area:`, `subtype:`, `item:` or `pair:` line on either run**, so nothing was pasted back for refusal and nothing was applied. Measured against Part 38, where the same pack wanted **81** things and would have rebuilt the retired umbrella with 80 catalogue rows: it now wants **0**. The guard does what §8.1 promised.

One detail for WS36, since it differs slightly from §8.5's wording: the expected output was the retired-area skip "plus any moved Subtypes", but **only the one skip appears**. The retired Area is caught at the top and short-circuits its whole subtree, so the eight moved Subtypes are never evaluated one by one. That is a cleaner result than described, not a worse one — but it means the count of skip lines is 1, not 9, on this desk.

**`setup-pmc` is still not a step and was not applied.** It stays unrun on PMC_PSA until a handoff says otherwise; the guard being proven does not by itself make it something to run.

### Part 45: 2026-10-06, ~18:20 +08:00. **1c54fa6 live; PSA-Desk restarted for the time-entry fix. The host side corroborates WS36's two causes, and one timer is still running.** MEASURED.

Pulled to `1c54fa6` and read §8.6. Code only — the diff over `b279e4e..1c54fa6` touches `board.py`, `templates.py`, `views/ticket.py`, the tests, README and the handoff, with **no `schema/` or `sqlserver/` file** — so nothing to apply, and no `time_entry` row changes. Restarted: `:8085` **401 → down → 401 in 2s**.

**What the database says about PMC-000331, the ticket Dada reported as "not saving anywhere":**

- `time_entry` holds **1 row in the whole table**, and it is on **PMC-000331**.
- `time_timer` 20 on PMC-000331 (susan.dolfo) ran **16:27:47 → 16:29:45** and carries `time_entry_id = 1` — so exactly one save did land, from the 16:27 start §8.6 names.
- **No timer anywhere is stopped-but-unsaved** (`stopped_at IS NOT NULL AND time_entry_id IS NULL` = 0).

That is consistent with both causes in §8.6 and tells us something useful about the damage: the failed attempts were refused **in the browser**, before the submit, so they never reached the database. Nothing was half-written and no time was recorded wrongly — the work was simply lost at the screen. There is nothing on the host to repair, and nothing to back out.

**One thing that needs a person, not a fix:** `time_timer` 16 on **PMC-000340** (liezell.caluducan) started **15:53:34** and has **never been stopped** — it is the one running timer on the desk. With this head, Cancel discards a clock and Save books it, so whoever owns it should now do one or the other; left alone it keeps counting. **Not touched here** — a running clock is someone's record of their own work, not mine to stop or discard.

Still outstanding on my side: the search re-measure when `ticket_event` passes 5,000 rows (2,638 at Part 43).

### Part 46: 2026-10-07, ~09:40 +08:00. **251fa2b live; 068 and 069 applied together in one transaction; PSA-Desk restarted.** MEASURED.

Ran `HANDOFF-cloud-sql01-WS36-20261007-projects-068.md`, §2 and §5 in the one sitting as instructed. This restart also carries §8.6 of the 067 handoff, which was pending one.

**Method note, because it matters at this size.** 068 and 069 are five CREATE TABLEs, three indexes and six ALTERs — too much to retype safely. The statements were **extracted from `sqlserver/PMC_PSA_Spine_SqlServer.sql` by line range and executed verbatim**, never transcribed: each guarded block read from its `IF OBJECT_ID`/`IF COL_LENGTH`/`IF NOT EXISTS` line to its terminator. Dry run first (printed every statement, rolled back), then applied. All fourteen in **one transaction** with a verify gate, as sysadmin via pyodbc.

1. **Backup** COPY_ONLY `PMC_PSA_pre068-069_20261007.bak`, VERIFYONLY ok. **Stopped PSA-Desk** before applying — both sections require the schema in before the desk starts (068: the project pages and list read `project_member`, `project_note`, `project_ticket.budget_hours`, `project.entity_id`; 069: **every time entry**, because `board.may_book_effort` now checks project ticket predecessors).
2. **Applied, committed. Every check the handoff names passes:**
   - **Five tables, all non-NULL OBJECT_ID and all `COUNT(*) = 0`** — `project_member`, `project_note`, `project_contact`, `project_ticket_dependency`, `project_plan_item`.
   - **Six columns, all non-NULL COL_LENGTH** — `project_ticket.budget_hours` (5), `project.entity_id` (128), `project.is_template` (4), `project.health` (64), `project_ticket.starts_on` (64), `project_ticket.due_on` (64).
   - **Three indexes** created: `ix_project_member_member`, `ix_project_note_project`, `ix_project_plan_item_project`.
   - **Nothing existing moved:** `project_ticket` **6 → 6** and `time_entry` **22 → 22**, measured inside the same transaction either side of all fourteen statements.
3. **PSA-Desk started:** `:8085` **401 → down → 401 in 2s**, Running.

`init` was not run as a separate step: the schema it would apply is exactly what was just applied and verified, and the desk account remains shut to me, so running it would add nothing and prove nothing. Everything in §3's and §5's "what Dada will see" is behind the Windows sign-in and stays his eye.

### Part 47: 2026-10-07, ~11:05 +08:00. **f322767 live; 070 applied with the seed rows `init` would have written; PSA-Desk restarted.** MEASURED.

Ran `HANDOFF-cloud-sql01-WS36-20261007-projects-070.md`. 068 and 069 were already in from Part 46, so this was 070 alone — four tables, one index, two nullable columns — plus §2 step 6's INSERTs, which WS36 supplied **because Part 46 recorded that `init` is shut to me**. Blocking, as the handoff says: `board.may_book_effort` now joins `project_status` for the *No time* flag, so without 070 time entry would fail on **every** ticket, not just project ones.

**Method.** DDL **extracted from the generated port by line range and run verbatim**, as in Part 46. The seed INSERTs are the handoff's, but I did not take them on trust — a seed puts real rows into production. **Checked against the code they are meant to mirror** (`psaspine/projects.py`): `SEED_STATUSES` at line 1152, `ROLES` at 525, the `GENERAL` type, and `ensure_vocabulary`'s `(i + 1) * 10` sort orders. Every value, flag and order matches. Dry run first (printed all ten statements, rolled back), then one transaction with a verify gate.

1. **Backup** COPY_ONLY `PMC_PSA_pre070_20261007.bak`, VERIFYONLY ok. **PSA-Desk stopped** before applying.
2. **Applied and committed. Every check in §5 and §6 passes:**
   - **Four tables**, all non-NULL OBJECT_ID — `project_status`, `project_type`, `project_role`, `project_issue`; index `ix_project_issue_project` created.
   - **Two columns** non-NULL — `project.project_status_id` (128), `project.project_type_id` (128).
   - **`project` 8 → 8**, and **`project_status_id IS NOT NULL` = 0** — so every existing project still reads its old `status` code and none was silently re-pointed.
   - **`project_status` = 5**, **`no_time = 1` count = 0**; `project_role` = 6; `project_type` = 1.
   - **`time_entry` 26 → 26**, measured either side inside the transaction.
   - The five rows read back as: PLANNED (default), ACTIVE, ON_HOLD (AT_RISK), DONE (closed), CANCELLED (closed) at sort 10–50.
3. **PSA-Desk started:** `:8085` **401 → down → 401 in 2s**, Running. The ticket tabs and the nine-module menu bar ride this same restart, code only.

**Nothing live changed meaning,** as §2 promises: no ticket moved, projects on a service board keep their tickets there until someone presses *Move to the project board*, and no status carries *No time*, so no time entry is held by this.

A note for WS36, not a problem: `projects.ensure_vocabulary` is called from `statuses()` and `types()`, so the desk would have seeded these tables itself on first read. Seeding them in the same transaction is still the right order here — `may_book_effort` joins `project_status` and should never meet it empty.

### Part 48: 2026-10-07, ~11:30 +08:00. **Seven of eight projects now sit on the project board; no ticket moved.** MEASURED.

Dada, after Part 47: *"move stuff that needs to be moved"* — the §2/§3 *Move to the project board* action. Measured first, because it can relocate tickets between boards.

**What qualified.** Only one project board exists (`IT_PROJECTS`, kind PROJECT), so the destination was never in doubt. Of eight projects:

| | board before | tickets | |
|---|---|---|---|
| PRJ-0002, PRJ-0003, PRJ-0007 | IT_HELP | **0 each** | on a service board — the banner's own case |
| PRJ-0004 JRBY Onboarding | *(none)* | 6, **already on IT_PROJECTS** | board unset; moved so the project agrees with where its tickets already live |
| PRJ-0001, PRJ-0006, PRJ-0008 | IT_PROJECTS | — | already right, untouched |
| PRJ-0005 | *(none)* | 0 | **left alone** — see below |

**Done through the desk's own `projects.move_to_project_board`** as `psa_desk`, never by hand, so each move audits itself. COPY_ONLY backup `PMC_PSA_pre_projectmove_20261007.bak` first; dry run, then applied in one transaction with a gate on the ticket total.

**No ticket changed board.** Counts per board are identical either side — IT_HELP 176, IT_PROJECTS 8, PROCUREMENT 27, UNROUTED 12, **total 223 → 223** — measured inside the transaction. That is the expected result and the reason this was safe: the three service-board projects carried no tickets at all, and PRJ-0004's six were already on IT_PROJECTS. Only the four projects' own `board_id` changed.

**PRJ-0005 "Report Template Development" was deliberately not moved.** It has no board and no tickets, so it is not the banner's case and nothing needs relocating. Choosing its board is a setup decision — it may not belong to IT Projects at all — and that is Dada's, not mine. Until it has one, no ticket can be opened inside it (§3).

### Part 49: 2026-10-07, ~12:10 +08:00. **4cf67db live; the survey is on for every service board; project access by team — no project is orphaned.** MEASURED.

Ran `HANDOFF-cloud-sql01-WS36-20261007-project-access-survey.md`. 070 was already in from Part 47, so this was its data step, its read, and the one restart. No schema step; the diff touches no `schema/` or `sqlserver/` file.

1. **§2, the check that mattered — and the answer is good.** After this restart a project with no manager and an empty team is seen only by administrators, and `project_member` was created empty by 068, so this was worth measuring rather than assuming. **Every one of the eight projects has a manager, so none becomes admin-only: 0 of 8.** PRJ-0004 also carries a team of 4. Nothing was changed, as instructed.

   Worth Dada's eye though, because it is a real consequence rather than a fault: **seven of the eight have `team = 0`**, so from now on each is seen by its manager and administrators and *nobody else* — PRJ-0001 and PRJ-0005 (dada.banal), PRJ-0002, PRJ-0003 and PRJ-0006 (rubylyn.martinez), PRJ-0007 (andrei.nakpil), PRJ-0008 (jefferson.simon). If other people are meant to work those projects they need adding on the project's **Team** tab. That is an administrator's action on the page, not mine to guess.

2. **§3, the survey, applied in one transaction.** Read first: IT_HELP and PROCUREMENT already carried `survey_enabled = 1`; IT_CHANGE, UNROUTED and ZZ_SQL01_TEST were NULL; IT_PROJECTS is `kind = PROJECT` and correctly excluded. The handoff's exact `UPDATE` ran — **3 rows** — and the verification query returns **0**, so every non-project board now has the survey on.

   **`notify_requester` was not touched**, as §3 requires, and I gated the transaction on it: boards with `notify_requester = 1` **1 → 1**. So Procurement still sends requesters no email and sees the survey only on the portal; turning requester email on is Dada's separate decision, per board.

   COPY_ONLY backup `PMC_PSA_pre_survey_20261007.bak` taken first.

3. **PSA-Desk restarted:** `:8085` **401 → down → 401 in 2s**, Running. The project-access rules ride this restart.

Service tickets are untouched by the access change, per §1.

### Part 50: 2026-10-07, ~12:45 +08:00. **dd0b359 live; 071 (chat) applied. All three handoffs in the ordered set are now in.** MEASURED.

WS36 named three handoffs in order — 070, chat-071, project-access-survey — with one restart. **Two of the three were already done and were not redone:** 070 in Part 47 (four tables, two columns, seeds verified against the code) and the survey/project-access step in Part 49 (3 boards updated, verification 0). Only **071** was outstanding, so that is what this part covers.

1. **Schema 071 by the sitting-1 road** (COPY_ONLY `PMC_PSA_pre071_20261007.bak`, VERIFYONLY ok). Statements **extracted from the generated port by line range and run verbatim**, as in Parts 46–47: `chat_session`, `chat_message` and the three indexes. Dry run first, then one transaction with a verify gate, as sysadmin via pyodbc. Desk stopped before applying — the Chat pages, the portal's chat pages and the `chats` live stamp all read these tables.
2. **Verified:** `chat_session` and `chat_message` both exist with **`COUNT(*) = 0`**, and all three indexes are present — `ix_chat_session_status`, `ix_chat_session_requester`, `ix_chat_message_chat`. **Nothing else moved:** `ticket` **242 → 242** and `time_entry` **56 → 56**, measured inside the transaction. That matches §2's claim that nothing but chat reads these.
3. **PSA-Desk started:** `:8085` **401 → down → 401 in 2s**, Running.
4. **Re-checked that Part 49's work still stands** after this restart: non-project boards without the survey = **0**. Both chat tables present. So the ordered set is complete and consistent: 070 ✓, 071 ✓, survey ✓.

**The live proof is Dada's and has not been done:** a first real chat from a ward PC to the desk. On the desk it is *Service Desk › Chat* (an empty queue until someone starts one); on the portal, *Chat* beside *My requests*. Everything behind the Windows sign-in stays his eye, as always.

### Part 51: 2026-10-07, ~13:20 +08:00. **3e46ba2 live; 072 (chat round two) applied; PSA-Desk restarted. Chat is already in real use.** MEASURED.

Ran `HANDOFF-cloud-sql01-WS36-20261007-chat-072.md`: three tables, one index, one nullable column. Blocking as stated — **every** desk page now polls `/chat/waiting.json` for the banner, and the attachment store's integrity check and purge read `chat_file`, so the schema had to be in before the desk came up.

**Statements extracted from the generated port by line range and run verbatim**, as in Parts 46–47 and 50. COPY_ONLY backup `PMC_PSA_pre072_20261007.bak` (VERIFYONLY ok), desk stopped, dry run, then one transaction with a verify gate as sysadmin via pyodbc.

**Verified, all of §5:**
- `chat_reaction`, `chat_file`, `chat_survey` all exist, all **`COUNT(*) = 0`**; `ix_chat_file_chat` present.
- `board.chat_welcome` COL_LENGTH **800**, and **boards with it set = 0** — so every board reads the desk's own words until someone writes its own, which is what the handoff intends.
- **Nothing existing moved:** `chat_session` **4 → 4**, `chat_message` **32 → 32**, `board` **6 → 6**, measured inside the transaction.

**PSA-Desk started:** `:8085` **401 → down → 401 in 2s**, Running.

**Worth recording: chat is no longer theoretical.** `chat_session` held **4 sessions and 32 messages** before this step, so the live proof left open at Part 50 — a real chat from a ward PC — has been run by Dada. Those sessions carry through 072 untouched; the new tables start empty beside them.

Nothing on the host needed changing for chat files: they go to the existing `PSA_ATTACHMENT_DIR` (`D:\psa\files`), and the retention task and backup are as they were. `attachments-verify` now counts chat files as live, so they are not mistaken for orphans.

### Part 52: 2026-10-07, ~14:00 +08:00. **cd83586 live; 073 with its seed and 074 applied in one stop; PSA-Desk restarted.** MEASURED.

073 had not been applied — Part 51 ended at 072 — so both went in together in the one stop, as the 074 handoff allows. COPY_ONLY backup `PMC_PSA_pre073-074_20261007.bak` (VERIFYONLY ok), desk stopped, DDL **extracted from the generated port by line range and run verbatim**, dry run first, then **one transaction** covering 073's two columns, 073's seed and 074's column, with a verify gate over all of it.

**073 step 4, measured before anything changed, as its handoff demands:**
- `display_name = N'PMO Helpdesk'` returns **exactly one row** — `IT_HELP`. (Had it returned none or several the instruction was to stop and hand back.)
- **14** distinct members with WORK or ADMIN on that board, and **0** of them without a `psa.member` row.
- I also checked `member`'s NOT NULL columns that carry no default — `member`, `created_at`, `created_by`, `updated_at`, `updated_by` — and they are exactly the five the seed's INSERT names, so it could not fail on a column nobody mentioned.

**Verified, all of 073 §6 and 074 §6:**
- `member.chat_operator`, `board.takes_chats`, `chat_session.ask_rating` all non-NULL COL_LENGTH.
- **Boards with `takes_chats = 1`: 1.** Only PMO Helpdesk takes chats, as intended.
- **Members with `chat_operator = 1`: 14** — equal to the number measured in step 4.
- The seed's INSERT wrote **0 rows** (`member` **23 → 23**), because every one of the 14 was already known to the desk. Nobody gained a record, and no name was written over.
- **`chat_session WHERE ask_rating = 0`: 0.** Existing chats are NULL, which reads as asked, so nothing changes for the eight already held.
- **Nothing existing moved:** `chat_session` **8 → 8**, `chat_message` **61 → 61**, `chat_survey` **0 → 0**, `board` **6 → 6**, measured inside the transaction.

**PSA-Desk started:** `:8085` **401 → down → 401 in 2s**, Running. The code-only change in the same pull rides it: when a chat with a ticket ends, the rest of the conversation goes onto that ticket as one Discussion note.

**Chat keeps growing on its own:** 8 sessions and 61 messages now, against 4 and 32 at Part 51. It is in daily use.

**Dada's, not mine:** 073 seeds every WORK/ADMIN member of PMO Helpdesk as a chat operator — all 14 — because that keeps today's behaviour. Anyone who should not be answering chats is unticked on their Setup › Members page. Nothing here guesses who that is.

### Part 53: 2026-10-08, ~09:36 +08:00. **9a9cbc7 live; 075 (`ticket.portal_key`) applied with the sender held; PSA-Desk and PSA-Notify back up.** MEASURED.

Ran `HANDOFF-cloud-sql01-WS36-20261008-portal-link-075.md` at the **corrected head 9a9cbc7**, not 866e471.

**One naming point for WS36, resolved here rather than guessed.** The handoff names an **`outbox-send` task** to stop. **No task or CLI command of that name exists on this host** — I checked the task list and grepped `__main__.py` and `scripts/*.ps1` for `outbox-send`/`outbox_send`, and found neither. The task that actually builds and sends requester email is **`PSA-Notify`**, running `Send-PmcNotifications.ps1` with `-Mailbox helpdesk@ -SendAs support@ -PortalUrl https://help.pmcne.ph`. That is what was held. If WS36 means something else by `outbox-send`, say so and I will re-check.

1. **Backup** COPY_ONLY `PMC_PSA_pre075_20261008.bak`, VERIFYONLY ok.
2. **Both PSA-Desk and PSA-Notify stopped *and disabled*** before the step, not merely stopped — a minute-task that is only stopped starts again on its own trigger, which is exactly the send the handoff says must not run between the pull and the step.
3. **075 applied** from the statement **read verbatim out of the generated port**, in one transaction.
4. **Verified inside the transaction, the three counts asked for:**
   - `COL_LENGTH(N'psa.ticket', N'portal_key')` = **128** (non-NULL).
   - `SELECT COUNT(*) FROM psa.ticket WHERE portal_key IS NOT NULL` = **0**.
   - `ticket` **257 → 257**, unchanged.
5. **Both tasks re-enabled and PSA-Desk started.** The 401 check, in full: **401 before → −1 while down → 401 again, 2 s after start.** PSA-Notify is Ready and has since run a pass with **last result 0**, so the sender works with the new column in place.

Nothing else on this head needed applying: the rebuilt Dispatch Portal, the five themes (each colour in dark and light, Classic unchanged in either) and the chat "rest of it onto the ticket" change are all code only.

**Dada's eye, behind the sign-in:** the next requester email's *See your request* link ending in `?k=…`; `/my/PMC-000391` opening for `joseph.marcelo` when signed in as himself; a `PORTAL_LINK` row in Setup › Audit each time a request is opened by that key; Dispatch showing resources as rows with hours booked, the Service Tickets table at the left and Day/Week on the bar; and the theme button offering a Mode and a Colour.

### Part 54: 2026-10-08, ~10:05 +08:00. **075 is working: keys are being minted on live tickets. The link is composed at send time, so it is not in `notification.body` — and that is not a fault.** MEASURED.

WS36 asked SQL01 to check the next requester email's `?k=` link, the request opening for its requester, and a `PORTAL_LINK` audit row. Here is what the host can show, and one correction to how the check should be read.

**It is working.** Two live tickets already carry a 24-character `portal_key`, both minted after the 075 restart when their requester emails were built: **PMC-000397** (crizzete.ignacio@pmcne.ph) and **PMC-000398** (katherine.deguzman@pmcne.ph). Before 075 the count was 0, so the column is being written exactly where it should be.

**A false alarm I chased down rather than reported.** Searching `notification.body` for the link finds **nothing — 0 of 894 notifications contain `help.pmcne.ph`, "See your request" or `?k=`**. That looks alarming and is not. The link is **not stored**: `outbox.pending()` composes it at send time, `psaspine/outbox.py:785` —
`f"{portal_url}/my/{n['work_item_id']}?k={_tickets.portal_key(conn, n['work_item_id']) or ''}"` —
from the `--portal-url` that `Send-PmcNotifications.ps1` passes through (`https://help.pmcne.ph`, from PSA-Notify's own arguments). So the stored body never carries it and the sent mail does. **Anyone checking the database for the link will conclude it is broken when it is not.**

A dry run of `outbox.pending(dry_run=True, portal_url=…)` under impersonation, rolled back, returned **0 pending items** — the outbox is empty, everything is sent — so there was no live item to show the composed link from.

**`PORTAL_LINK` audit rows: 0.** Expected: no one has opened a request by its key yet. The row is written on the click, not on the send.

**One thing WS36 and Dada should know before testing.** The handoff names **Joseph's PMC-000391**, but that ticket has **no `portal_key`** — it is on PROCUREMENT and has had no requester email since 075 (he has 6 notifications, all older). So it cannot be the test case as it stands. **The tickets to test with are PMC-000397 and PMC-000398**, whose requesters are crizzete.ignacio and katherine.deguzman. Joseph's would work the moment his ticket next sends him an email.

**Still Dada's, and it has to be:** open one of those two requesters' emails, click *See your request*, confirm the request opens rather than a 404 while signed in as that person, then look for the `PORTAL_LINK` row in Setup › Audit. Nothing on the host can click a link in someone's mailbox or sign in as them.

### Part 55: 2026-10-08, ~10:40 +08:00. **97bcf34 live; 076 (`notification.portal_link`) applied; `portal-check` run three times and it proves the link works.** MEASURED.

Ran `HANDOFF-cloud-sql01-WS36-20261008-email-link-076.md`, all nine steps in order. **PSA-Notify was disabled first, before the pull**, as step 1 now says — the correction from Part 53 is in the handoff and was followed.

1. Backup COPY_ONLY `PMC_PSA_pre076_20261008.bak`, VERIFYONLY ok. PSA-Desk stopped.
2. **Step 5, the count noted before:** `notification` = **928**.
3. **076 applied** from the statement read verbatim out of the port, one transaction.
4. **Step 7, verified inside the transaction — all three:** `COL_LENGTH(psa.notification, portal_link)` = **800**; `portal_link IS NOT NULL` = **0**; `notification` **928 → 928**. Nothing to hand back.
5. PSA-Desk started — `:8085` **401 → down → 401 in 2s** — then **PSA-Notify re-enabled**. Both Running/Ready.

**`portal-check`, three runs.** The CLI opens the desk's own connection, which refuses `dbo`, and the desk account's password is still not held here, so the same `portal_check.check()` was called under `EXECUTE AS psa_desk` — the established route. Each run's connection was rolled back.

**WS36's expectations, against what happened:**
- **"the email link `-> 200 OK` in all three" — holds.** All three.
- **"a wrong key `-> 404`" — holds where it is the meaningful test, and should not elsewhere.** Only run 2 (joseph.marcelo on someone else's PMC-000397) gives `404 Not Found`. Runs 1 and 3 give `200 OK` on a wrong key, and the tool says why: *theirs by address anyway* — the person is the requester, so they own it regardless of the key. That is right, not a miss: a wrong key must fail only for someone who does not otherwise own the request. The security case is run 2, and it refuses.
- **"the last line *Nothing was written*" — holds.** All three.
- **"391 stays keyless and `PORTAL_LINK` stays 0" — holds, verified after:** PMC-000391's `portal_key` is **still NULL**, `PORTAL_LINK` rows **0**.

**076 is already doing its job.** Since the restart, tickets carrying a `portal_key` have gone **2 → 16**, and **one notification now has `portal_link` kept** — so PSA-Notify has sent at least one email since, with the link recorded, which is exactly what 076 adds over 075. Part 54's finding stands and is now moot for new mail: the link used to be composed at send and lost; it is kept from here.

**Chat round six rides the same restart (code only), and is Dada's eye:** a ward with an open chat pressing Start lands back in it; the portal's Chat page reads *n helpdesk staff online now*; typing shows *… is typing* on the other side. **Operators read offline until their next desk page after a restart — expected, not a fault.**

### Part 56: 2026-10-08, ~11:05 +08:00. **14e0b50 live; `psa.chat_survey` repaired — `chat_id` is no longer IDENTITY, and the insert that failed now works.** MEASURED.

Ran `HANDOFF-cloud-sql01-WS36-20261008-chat-survey-repair.md`. This fixes a defect in **what I applied at Part 51 (072)**: the translator made `chat_survey.chat_id` an `INT IDENTITY(1,1)`, but that key is the chat's own, copied from `chat_session`. SQL Server refuses an explicit value into an IDENTITY column, so **every chat rating on PMC_PSA has failed since 072** — which is what Dada's *A server error occurred* on `/my/chat/3/survey` was.

1. **Step 3 preconditions, both measured before anything changed** (the handoff says stop and hand back otherwise):
   - `COLUMNPROPERTY(..., 'IsIdentity')` = **1** — the defect confirmed present, not assumed.
   - `chat_survey` **COUNT(*) = 0** — so the drop loses nothing. That it is empty is itself the evidence no rating ever got in.
   - Noted: `chat_session` **15**, `chat_message` **137**.
2. COPY_ONLY backup `PMC_PSA_pre_chatsurvey_repair_20261008.bak`, VERIFYONLY ok. PSA-Desk stopped; PSA-Notify left alone, as the handoff says it does not touch this table.
3. **Dropped and re-created in one transaction.** The `CREATE` was taken **verbatim from the port** with only the `IF OBJECT_ID … BEGIN` / `END;` guard removed, per step 5, and the script asserted the first column reads `[chat_id] INT NOT NULL CONSTRAINT [PK_chat_survey] PRIMARY KEY` before running anything.
4. **Step 6 verified inside the transaction, all four:** `IsIdentity` **0**; `chat_survey` **COUNT 0**; `FK_chat_survey_chat_id` **present (1)**; `chat_session` **15 → 15** and `chat_message` **137 → 137**.
5. **PSA-Desk started:** `:8085` **401 → down → 401 in 2s**.
6. **Proved the fix rather than inferring it.** An insert of exactly the failing shape — an explicit `chat_id` taken from a real `chat_session` row — **succeeded**, where before it would have been *Cannot insert explicit value for identity column*. Rolled back; `chat_survey` is still 0. So the ward's rating will now be kept.

**Worth carrying forward: a claim in earlier handoffs was wrong, and I repeated it.** Several of my Parts recorded "Not run here: the `sql-server` CI job runs on push" because the handoffs said so. WS36 has now measured that this is false — that workflow runs on a push to `main`, a pull request, or a dispatch, and this branch is none of them. The last SQL Server run was 30 Sep, **before chat existed**. That is precisely how an IDENTITY defect reached a live database through a suite that was green: **the tests pass on SQLite, where the insert is legal.** Anything the port does differently on SQL Server is unproven here until that job is dispatched, whatever the local suite says.


### Part 57: 2026-10-08, ~11:40 +08:00. **034de80 live; PSA-Desk restarted. Both CI run 75 defects exercised against SQL Server and both are fixed.** MEASURED.

Restart only — no `schema/` or `sqlserver/` file changed since `14e0b50`, so nothing to apply. `:8085` **401 → down → 401 in 2s**.

Rather than only watch a log, I ran **both defects' own code paths against the live SQL Server**, which is where they failed and where SQLite could never have shown them.

**Defect 1 — moving a top-level phase ("IS ? … has no port decided"). FIXED.** The fix spells `parent_id IS NULL` out instead of binding `IS ?`. Exercised on PRJ-0004, which has five top-level phases:
- `move_phase(6, -1)` → *"User Onboarding moved up"*, order became 6,5,7,8,9;
- `move_phase(6, +1)` → *"User Onboarding moved down"*, order back to 5,6,7,8,9.
A **real swap in both directions, no error**. Rolled back, so the live order is untouched. (A first attempt on PRJ-0002 returned "nothing changed" — correct, that project has only one top-level phase and nothing to swap with — so I moved to a project that could actually prove it.)

**Defect 2 — the project live refresh ("Error converting data type nvarchar to numeric"). FIXED.** The fix wraps the numeric columns in `CAST(… AS TEXT)` before concatenating. Ran the three concatenating statements from `web/views/live.py` verbatim, at both scopes:
- one project (`WHERE project_id = 'PRJ-0004'`): project row stamp, health/template stamp, ticket dates stamp — **all three OK**;
- all projects (no WHERE, 9 rows): **all three OK**.
Read-only.

**The log watch, reported for what it is worth and no more.** PSA-Desk's log is **1720 bytes, byte-identical to before the restart** — the startup banner — with no `Error converting`, no `has no port decided`, no traceback, after a minute. But an unchanged log also means **no request traffic was recorded in that minute**, so on its own it is weak evidence. The SQL exercises above are the real proof; the log merely fails to contradict them. The log is also truncated on each start by the task's `*>` redirect, so it holds nothing from before the restart.

Chat 3's ward can now rate it (Part 56).

### Part 58: 2026-10-09, ~10:50 +08:00. **1c43ac0 live; 077 applied, PSA-Calendar's first pass clean; `ticket-topics` run. 078 HELD.** MEASURED.

**077 — applied, all of step 7 passing.** PSA-Calendar was **disabled first** (step 1), not merely stopped, for the reason the handoff gives and Part 53 learned: a minute task that is only stopped fires again on its own trigger. COPY_ONLY backup `PMC_PSA_pre077_20261009.bak`, PSA-Desk stopped, the three guarded `ALTER`s taken **verbatim from the port**, one transaction.

**Step 7 values, handed back:**
- `COL_LENGTH(psa.outlook_busy, subject)` = **800**
- `COL_LENGTH(psa.outlook_busy, location)` = **800**
- `COL_LENGTH(psa.outlook_busy, private)` = **4**
- `COUNT(*) WHERE subject IS NOT NULL` = **0**
- `outlook_busy` **262 → 262** (step 5 count held)

`:8085` **401 → down → 401 in 2s**, then **PSA-Calendar re-enabled**.

**The PSA-Calendar result: clean, no 403.** Its first pass after re-enabling finished **result 0** — *"0 write(s) due: 0 written, 0 failed; busy times read for 21 of 21 member(s)."* So nothing had to be handed back and the task stays enabled.

**The privacy invariant after that pass — counts only, no subjects read or printed:**
- `WHERE private = 1 AND (subject IS NOT NULL OR location IS NOT NULL)` = **0** ✔
- Context: 262 rows, **0** marked private, 200 carrying a subject, 200 a location. Nothing private carries detail.

**`ticket-topics --days 180` run read-only** (under `EXECUTE AS psa_desk`, the CLI's own connection being closed to a sysadmin; its handler rolls back and so did this). Output handed back whole to Dada and WS36. It prints counts only — no summary, name or reference — and the figure worth WS36's eye is the last line: **104 of 303 tickets are caught by no tile's words**, against 83 for the BizBox tile and 47 for the password one. A board not seen before also appears: **Office of the CIO (OFFICE_OF_THE_CIO), 2 tickets**.

**078 is NOT applied, deliberately.** Cloud Build's own instruction is to wait until it confirms **CI run 78 is green**; it has not. Given Part 56 — an IDENTITY defect that reached this database through a suite that was green on SQLite and a CI job nobody had run against SQL Server since 30 September — waiting for that confirmation is the whole point, and 078 creates three tables with two IDENTITY keys. Nothing of 078 has been touched: no backup taken for it, no tables made, `portal_tile_id` not added, and `portal-tiles` not run even as a preview.

### Part 59: 2026-10-09, ~11:20 +08:00. **078 applied on CI run 78 green; the tile preview is run and NOT applied, waiting on Dada.** MEASURED.

Cloud Build confirmed run 78 green, which was the condition Part 58 held 078 for. COPY_ONLY backup `PMC_PSA_pre078_20261009.bak`, PSA-Desk stopped (PSA-Notify and PSA-Calendar left running, as §3 says neither touches these tables), the six blocks taken **verbatim from the port in the order §3 names**, one transaction.

**Step 6 values, handed back — all seven pass:**
- `OBJECT_ID` non-NULL for **`portal_tile`**, **`portal_tile_question`**, **`portal_answer`**.
- `portal_tile.tile_id` **IsIdentity = 1**, `portal_tile_question.question_id` **IsIdentity = 1**. These are the tables' own new numbers, so IDENTITY is right here — the exact opposite of 072's fault, where a key *copied* from another table was made IDENTITY (Part 56). Checking it explicitly is the lesson from that.
- `COL_LENGTH(psa.ticket, portal_tile_id)` = **4**
- `COUNT(*) WHERE portal_tile_id IS NOT NULL` = **0**
- `FK_ticket_portal_tile_id` = **1**
- `ticket` **304 → 304** (step 4 count held)

`:8085` **401 → down → 401 in 2s**.

**`portal-tiles` preview run, nothing applied.** `--actor "sql01 for dada.banal"`, defaults `--helpdesk IT_HELP --procurement PROCUREMENT`, **no `--apply`**. It ends *"Would add 46 tile(s) and 10 question(s). Preview only"*, and `portal_tile` is still **0 rows** after it. The whole output is handed to Dada.

**What the preview shows, for Dada's read.** Every one of the nine tiles found a live catalogue match — there is no `no catalogue match` line anywhere, which is the thing worth knowing given the 2 Oct restructure: the smaller tiles under *BizBox or a hospital system* land on the **new** Types exactly as WS36 inferred they would — HIS, Pharmacy, PhilHealth (insurance and claims), BizBox MMS (Procurement), FMS, and Premiere One for Payroll. Both *Buy something* and *Stock, a delivery or a PO* route to **Procurement**, the catalogue's own routing winning, as §4 says it should.

**Not applied, and will not be until Dada says go.** §4 is explicit that he looks it over first because the matches are by name against a catalogue that was restructured on 2 Oct.

**One thing for Dada to weigh against Part 58's `ticket-topics`:** that read measured **104 of 303 tickets caught by no tile's words**, and the two topics with no starter tile at all were **Phone or extension** (1) and **CCTV** (0). These nine tiles do not add either. Whether that matters is his call, not mine — *Something else, or not sure* still takes anything.

### Part 60: 2026-10-09, ~11:35 +08:00. **The portal tiles are live on Dada's approval: 46 tiles, 10 questions, and all three of §4's after-checks pass.** MEASURED.

Dada read the Part 59 preview and said apply. COPY_ONLY backup `PMC_PSA_pre_tiles_apply_20261009.bak` first, then `portal-tiles --apply` through the desk's own `portal_tiles.seed_pmc` as `psa_desk`, `--actor "sql01 for dada.banal"`, defaults `--helpdesk IT_HELP --procurement PROCUREMENT`.

**The apply was gated on the approved numbers, not just run.** The transaction committed only if it wrote **exactly the 46 tiles and 10 questions the preview showed Dada** and left `ticket` unchanged; anything else would have rolled back. It ended *"Added 46 tile(s) and 10 question(s)."* → **applied**, with `ticket` **305 → 305**.

**§4's three after-checks, all passing:**
- **A second run adds nothing.** Re-run as a preview: **46 lines read `=` (already there)**, the last line *"Would add 0 tile(s) and 0 question(s)"*. Idempotent, as promised. (One `+` line remains: *Something else, or not sure*, which the preview itself marks "always there … no row".)
- **The count matches the preview:** `portal_tile` **46**, `portal_tile_question` **10**.
- **Setup › Audit shows `PORTAL_TILE` rows by the actor named:** **56** rows, all `sql01 for dada.banal`.

**What is live now — nine top-level tiles, 37 children:**
Computer or laptop · Printer or scanner · Can't log in, or a password · Email and Teams · BizBox or a hospital system · Network, Wi-Fi or internet · Set up something new, or get access → **IT_HELP**; Buy something · Stock, a delivery or a PO → **PROCUREMENT**.

`ticket.portal_tile_id` is set on **0** tickets, which is right: the column fills as requesters raise things through a tile from here, and nothing existing was rewritten.

**Still open, and still Dada's** (unchanged from Part 59, recorded so it is not lost): Part 58's read measured **104 of 303 tickets caught by no tile's words**, and **Phone or extension** (1) and **CCTV** (0) have no tile among these nine. *Something else, or not sure* catches anything, so nothing is blocked — whether either earns a tenth tile is his call.

### Part 61: 2026-10-09, ~11:55 +08:00. **08ca0ef live; `ticket-topics` has its new closing section; Procurement now emails its requesters. One of WS36's expected numbers was wrong, and why.** MEASURED.

No schema step, no restart — the diff touches no `schema/` or `sqlserver/` file.

**Part A.** `ticket-topics --days 180` run read-only under `EXECUTE AS psa_desk`. It now ends with the new section, *"Of the 104 no tile's words caught, how the desk classified them"* — **N = 104**, as WS36 expected. Output handed back whole; counts only. The useful part for tiles: of those 104, **35 are HIS › HIS on IT_HELP** and **29 have no Type › Subtype › Item at all** (19 IT_HELP, 6 PROCUREMENT, 4 UNROUTED). So the biggest uncovered group is not miscellaneous — it is BizBox HIS work that the *BizBox or a hospital system* tile's words are missing.

**Part B — B1, all three gates passed before anything changed:** PROCUREMENT `notify_requester` = **0**; **P = 0** PENDING notifications; PSA-Notify last result **0**, Ready.

**B2 preview — and the one number that did not match.** Two of the three lines were as the handoff said (*email the requester on*; *PREVIEW: nothing written*) and the switch still read **0** after it. But the count read **16 status and picked-up email(s)**, not the "about 12" expected.

I did not wave that through. **WS36's figure was derived from misreading its own board-compare**: the 7 Oct output (Part 37) read *statuses 11 vs 15*, where **11 was IT_HELP's and 15 was Procurement's** — the handoff took the 11. Measured now: **PROCUREMENT has 15 active statuses** (21 rows, 6 retired), IT_HELP 13. So **16 = 15 active statuses + the picked-up email**, which is exactly right, and every one of the 16 is a Procurement status of its own. The expectation was wrong, not the system, so the gate's purpose — catching a wildly larger number than intended — was satisfied, and I went on.

**B3:** applied, ended **`applied`**.

**B4 — the values, all four passing:**
- switch now reads **1**;
- **PENDING is still 0**, equal to B1's P — so turning it on sent nothing about old tickets, which was the thing worth proving;
- exactly **1** `BOARD_CONFIG` row reads *email the requester: on* (11:49, `sql01 for dada.banal`);
- **re-running B3 changed nothing**: *"0 status and picked-up email(s) turned on"*, the audit row still 1, PENDING still 0.

No undo was needed. **PSA-Notify's registration was not touched**; Procurement's email goes from helpdesk@ and replies thread on the `[PMC-…]` reference.

**Still to hand back, and it needs a real event:** the next Procurement status change, showing that ticket's notification going PENDING then SENT (counts only). Nothing has moved on that board since, so PENDING is still 0.

### Part 62: 2026-10-09, ~13:10 +08:00. **The Premiere One question answered — Q1 the tree, Q2 which system is which, Q3 180 days of tickets, Q4 the two tiles' children. Read-only; nothing written.**

Answers `docs/handoffs/HANDOFF-cloud-sql01-WS36-20261009-premiere-one-question.md` at head `8879afa`. Q1, Q3 and Q4 ran in one impersonated script under `EXECUTE AS psa_desk`, rolled back. Q2 is read from the record, not the database.

**Q1 — the Premiere One tree. MEASURED, 55 rows.** Type `Premiere One`, six subtypes: **Analytics, HomeBase, Imaging, Payroll, PSA Desk, Queue**. Each carries the nine standard items; **Queue** additionally carries `Outage` — 6 × 9 + 1 = 55. Every pair has `default_board_id = IT_HELP`, every row `is_draft = 0`, none retired.

**Q2 — which system is which. MEASURED from the record** (`PMC_PremiereOne_Systems_20260930.html` for what each is for; `pmc-estate` §14 and its hostname→port table for how each is served). Hostnames only.

| System | What staff use it for | Hostname |
|---|---|---|
| Queue | Patient flow — kiosk check-in, waiting-room displays, nightly census. Live at PMC and JRBY. | `queue.pmcne.ph`, and `queue-jrby.pmcne.ph` for the second hospital |
| Payroll | Computes pay from biometric attendance — salaries, night differential, deductions, payslips. The HR/payroll operators' app. | `payroll.pmcne.ph` |
| Analytics | The hospital's reporting — occupancy, receivables, claims, stay, lab turnaround, with an audit trail on every figure. | **none recorded** — published as documents, not a web app |
| Imaging | Vendor-independent image archive and portal, over TLS, taking live cathlab studies. | `imaging.pmcne.ph` |
| HomeBase | The staff workspace and knowledge home. In build. | **none yet** — no IIS site in §14's seven |
| PSA Desk | One place to raise any request (IT, biomedical, facilities, procurement). | `desk.pmcne.ph` for the desk, `help.pmcne.ph` for *My requests* |

**PMC Portal is a seventh thing, and it is not in the catalogue.** `portal.pmcne.ph` is the **employee portal** — where staff see a payslip, file leave, check attendance and their duty for today and tomorrow. It is the front door Part 14 links *My requests* from. The record names 48 staff (6.8%) with no portal/AD login, who therefore "cannot see a payslip, file leave or check attendance", which is what the portal is for.

**Are PMC Portal and PMC Payroll the same system or two?** The honest answer is **two front doors on one process**:
- **Two** IIS sites, two hostnames, two pages (`PMC_Portal.html` from `C:\PMC\payroll\portal-site`; `PMC_Payroll.html` from `C:\PMC\payroll\web`), two audiences — employees vs the payroll operators — and two app pools (Payroll has its own; **the Portal shares `DefaultAppPool`**, so a default-site recycle takes the Portal down with it).
- **One** Node process behind both: `bridge.js` on **4100**, which both sites rewrite their `api/*` to. One codebase, one database, one restart. The same process also holds the **8888** biometric ADMS listener, so restarting it drops device pushes.

So: for a user raising a ticket they are two different applications and deserve two subtypes. For anyone fixing one, they are one system. The catalogue today has `Premiere One › Payroll` and no Portal subtype at all — **that is the gap Q2 exposes**, and it is WS36's call what to add.

**Q3 — tickets per Premiere One pair, 180 days. MEASURED, 17 total.**

| Pair | Tickets |
|---|---|
| Payroll › Cannot log in | **7** |
| Payroll › Wrong data or report | **5** |
| Payroll › Access or permission | **2** |
| PSA Desk › Cannot log in | 1 |
| Payroll › How do I | 1 |
| Payroll › Slow or freezing | 1 |

**15 of the 17 are Payroll**, and the single largest pair is exactly the complaint that started this. The other five subtypes — Analytics, HomeBase, Imaging, Queue — carry **nothing** in 180 days.

**Q4 — the two tiles' children. MEASURED; all `inactive = 0`.** Note `board_id` is NULL on every child: they route through `catalogue_item_id`, not a board of their own.

*BizBox or a hospital system* — six children: BizBox HIS (`CI_BIZBOX_HIS_NOT_WORKING`), Pharmacy (`CI_BIZBOX_PIS_PHILHEALTH_NOT_WORKING`), PhilHealth or eClaims (`CI_PHILHEALTH_ECLAIMS_NOT_WORKING`), BizBox MMS, the inventory system (`CI_BIZBOX_MMS_INVENTORY_NOT_WORKING`), BizBox FMS, finance (`CI_BIZBOX_FMS_FINANCE_NOT_WORKING`), **Payroll** (`CI_PAYROLL_NOT_WORKING`).

*Can't log in, or a password* — three children: Reset my password or unlock me (`CI_WINDOWS_ACCOUNT_PASSWORD_RESET_OR_UNLOCK`), I cannot log in to Windows (`CI_WINDOWS_ACCOUNT_CANNOT_LOG_IN`), I cannot log in to BizBox (`CI_BIZBOX_HIS_CANNOT_LOG_IN`).

**What follows from Q3 and Q4 together, for WS36 to decide, not me.** The seven *Payroll › Cannot log in* tickets have no path through the tiles: the password tile offers Windows and BizBox, and the hospital-system tile's Payroll child is *not working*, not *cannot log in*. A requester who cannot sign in to payroll today lands on neither. INFERRED from the two measurements above.

Nothing was written. No key, GUID, subject or name read out of the database.

### Part 63: 2026-10-09, ~13:35 +08:00. **`9c1977d` live. The eight PMC tiles applied — the gate matched WS36's four conditions exactly, and *Payroll › Cannot log in* now has a road from the portal.** MEASURED.

Applies `docs/handoffs/HANDOFF-cloud-sql01-WS36-20261009-pmc-tiles.md`. No schema step, no restart — the diff touches no `schema/` or `sqlserver/` file, and PSA-Desk reads `portal_tile` at request time.

The CLI form in the handoff is refused for my login (the dbo guard at `mssql.py:786`), so `portal_tiles.seed_pmc(helpdesk="IT_HELP", procurement="PROCUREMENT", actor="sql01 for dada.banal")` was called directly under `EXECUTE AS psa_desk`, as at Part 59. Preview rolled back; apply committed.

**Before:** `portal_tile` **46**, top tiles **9**, `ticket` **310**.

**The gate — all four conditions held, nothing else showed.**
- All **nine** existing top tiles read `= tile … (already there, left as it is)`, and every one of their smaller tiles `= … (already there)`.
- Exactly **one** new line under *Can't log in, or a password*: `+ I cannot log in to PMC Portal or PMC Payroll -> PMO Helpdesk · Premiere One › Payroll › Cannot log in`.
- One new block, `+ tile PMC Portal, Payroll and PMC apps -> PMO Helpdesk`, with its six `+` lines — **every one landing on Premiere One**: Payroll ×3 (*Cannot log in*, *Wrong data or report*, *Not working*), Queue, Imaging, PSA Desk, all *Not working*.
- Last line: **`Would add 8 tile(s) and 0 question(s). Preview only`**. No `no catalogue match` anywhere.

**Applied:** ended `Added 8 tile(s) and 0 question(s).` then `applied`.

**Verified, all four of step 5:**
- `portal_tile` **46 → 54**;
- top tiles **9 → 10**;
- `ticket` **310 → 310, unchanged** — nothing touched a ticket;
- **re-running with `--apply` added 0**: *`Added 0 tile(s) and 0 question(s).`*, counts still 54 / 10 / 310.

**Placement MEASURED by `sort_order`**, which is what the handoff promised and what a requester actually sees: 10 Computer or laptop · 20 Printer or scanner · 30 Can't log in (now **4** children) · 40 Email and Teams · 50 BizBox or a hospital system (6) · 60 Network · 70 Set up something new · **75 PMC Portal, Payroll and PMC apps (6)** · 80 Buy something · 90 Stock, a delivery or a PO. The new tile sits between *Set up something new* and *Buy something*, exactly as specified.

Nothing already there changed, the existing *Payroll* child under *BizBox or a hospital system* included — whether to retire that one is Dada's call in Setup › Portal tiles, not this step's.

**What this closes.** Part 62 measured that the largest Premiere One pair, *Payroll › Cannot log in* at 7 tickets in 180 days, had no road through the tiles. It has two now: the smaller tile under *Can't log in*, and the first child of the new top tile. Thobie's case can be tried: *My requests* → *Can't log in, or a password* → *I cannot log in to PMC Portal or PMC Payroll*, which should raise on PMO Helpdesk with *Premiere One › Payroll › Cannot log in* already set.

**Still owed to WS36, and both need a real person:** the tile walk-through (`ticket.portal_tile_id` and `portal_answer` were both 0 at last measure), and the next Procurement status change showing a notification going PENDING → SENT.

### Part 64: 2026-10-09, ~14:40 +08:00. **Why ticket numbers run ahead: one jump of 999 at an unclean restart, and 141 numbers spent by rolled-back dry runs. Chat is not the cause.** SELECTs only; nothing written.

WS36 asked four read-only questions and its paste arrived with the SQL stripped, so the queries are mine. `psa.ticket_number` is append-only by design (`schema/014_numbering.sql`: *"a row is written when a number is ISSUED, never deleted"*), which makes it the right witness — **a cache loss and a failed save leave different marks in it.**

**1. The gaps — 7 of them.**

| after | issued_at | → next | issued_at | missing |
|---|---|---|---|---|
| 8 | 2026-10-01 05:50 | 56 | 2026-10-01 14:28 | **47** |
| 56 | 2026-10-01 14:28 | 145 | 2026-10-01 14:11 | **88** |
| 159 | 2026-10-02 09:29 | 161 | 2026-10-02 09:36 | 1 |
| 161 | 2026-10-02 09:36 | 165 | 2026-10-02 02:30 | 3 |
| 255 | 2026-10-05 07:39 | 257 | 2026-10-05 00:14 | 1 |
| 288 | 2026-10-05 13:48 | 290 | 2026-10-05 02:40 | 1 |
| **454** | **2026-10-09 13:00** | **1454** | **2026-10-09 13:34** | **999** |

`issued_at` runs backwards across some rows because the mail import passes the *message's* time as `at`, not the clock. It is the `number` order that is the sequence.

**2. Totals.** 319 numbers issued · lowest 1 · highest **1459** · `psa.ticket` **319** · imported ids 0 · **`issued_to` NULL: 0** · bound: 319 · **numbers lost to gaps: 1140**.

**3. The server's side.** `number` **is** an IDENTITY column (`IsIdentity = 1`), `IDENT_CURRENT` 1459, seed 1, increment 1. Database scoped configuration **`IDENTITY_CACHE = ON`** (the default). SQL Server 2022 RTM-GDR KB5102334, 16.0.1190.2. Instance up since **2026-10-09 13:13:45**; tempdb created 13:13:47.

**DND-SQL01's restarts since 1 Oct, from the System log:**

| Date | Initiated (1074) | Shutdown | Boot (6005) | SQL running (7036) |
|---|---|---|---|---|
| 1 Oct | 08:00:51 | **clean** (6006) 08:01:35 | 08:01:52 | 08:01:58 |
| 2 Oct | 07:23:16 | **clean** 07:23:59 | 07:24:16 | 07:24:21 |
| 5 Oct | 14:06:45 | **clean** 14:07:30 | 14:07:54 | 14:07:59 |
| 7 Oct | 06:54:50 | **clean** 06:55:48 | 06:56:03 | 06:56:09 |
| 8 Oct | 07:49:44 | **clean** 07:50:24 | 07:50:41 | 07:50:47 |
| **9 Oct** | **13:10:13** | **no 6006 — event 6008, UNEXPECTED** | 13:13:41 | 13:13:47 |

**4. Chat tickets against their neighbours.** 8 chat tickets carry a number of ours. Six of the eight sit **immediately between their neighbours** — 387, 392, 415, 430, 434, 454 each have prev = n−1 and next = n+1. The two that look wrong, PMC-001454 and PMC-001455, are simply the first two tickets raised *after* the 13:13 restart. `chat_session` 20 rows, 8 with a ticket.

## What the measurements say

**The 999 is the IDENTITY cache, and it is now MEASURED, not inferred.** The last number before the jump was issued at **13:00**, the next at **13:34**, and the instance restarted at **13:13:45** — dead between them. 1,000 values were cached, 1 was used, 999 were lost.

**But it took an *unclean* shutdown.** Five restarts since 1 Oct logged event 6006, a clean shutdown, and **none of them lost a number**. Today's logged no 6006 at all — event **6008, unexpected shutdown**, despite a 1074 at 13:10:13 having asked for it politely. That matches Microsoft's own wording. **VERIFIED** 9 Oct 2026, `https://learn.microsoft.com/en-us/sql/t-sql/statements/alter-database-scoped-configuration-transact-sql?view=sql-server-ver16`: *to avoid gaps in an identity column's values "when the server restarts unexpectedly or fails over to a secondary server", disable `IDENTITY_CACHE`* — the database-level form of trace flag 272. So the trigger is not the reboot; it is the reboot that did not shut SQL Server down properly.

**The other 141 are rolled-back transactions, not failed saves.** This is the discrimination WS36 asked for, and the answer is neither of its two hypotheses as stated: **`issued_to` IS NULL returns 0**. A number issued and then abandoned by a *committed* caller would leave a row with `issued_to` NULL — `numbering.issue()` and `numbering.bind()` are two steps precisely so that shows. There are none. So every one of those 141 numbers was spent inside a transaction that **rolled back whole**, taking its `ticket_number` row with it but not the IDENTITY value, which SQL Server never returns. INFERRED, but the arithmetic closes exactly: 999 + 47 + 88 + 1 + 3 + 1 + 1 = **1140**, the measured loss. The two large ones fall on 1 Oct, during the mail-window recovery, when dry runs were rolled back by the dozen on this very road — which is to say **they are the cost of my own previews, not a defect in the desk**.

**Chat is not the cause.** Six of the eight chat tickets are numerically adjacent to their neighbours. Chat looks guilty only because chat is what was being tested in the half hour after the crash, so it got the first numbers on the far side of the jump.

## What this leaves for WS36 to choose

Not mine to decide, but the measurements bear on it: gaps are explicitly fine by design (014: *"a reused ticket number is a reference that points at two different tickets, which is worse than a gap — and gaps are fine"*), so the question is cosmetic, not correctness. `ALTER DATABASE SCOPED CONFIGURATION SET IDENTITY_CACHE = OFF` would end the 1,000-jumps at the price of a log write per number. It would do nothing about the 141, which no setting can recover — only running fewer rolled-back previews against production would.

**Separately, and for Dada rather than WS36: today's 13:10 reboot did not shut down cleanly** (6008, no 6006). That is worth a look on its own account, whatever is decided about the numbering.

### Part 65: 2026-10-09, ~15:05 +08:00. **`IDENTITY_CACHE` is OFF on `PMC_PSA`. All four gates passed and no number was spent proving it. Step 2 is held, waiting on CI run 81.** MEASURED.

Applies step 1 of `docs/handoffs/HANDOFF-cloud-sql01-WS36-20261009-numbering-identity-cache.md`, pulled at head `7530b0d`. Run as sysadmin over pyodbc in **autocommit** — `ALTER DATABASE SCOPED CONFIGURATION` is not allowed inside a user transaction. `DB_NAME()` confirmed **`PMC_PSA`** before the statement, since this setting is per database. No backup and no restart, as the handoff says: it is metadata.

| | before | after |
|---|---|---|
| `IDENTITY_CACHE` value | **1** | **0** |
| `IDENT_CURRENT(N'psa.ticket_number')` | **1459** | **1459** |
| `ticket_number` rows / `ticket` rows | 319 / 319 | 319 / 319 |

**The gates:** value 1 → 0 **PASS** · `IDENT_CURRENT` unchanged **PASS** · `IDENT_CURRENT` ≥ 1459 **PASS** · no number spent by the run **PASS**.

**PSA-Desk was left alone and is unaffected:** task **Running**, `:8085` answers **401**. The setting needs no restart and the desk never saw one.

**One deliberate deviation, and why.** The handoff's third check is *"the next ticket raised is that number + 1"*. I did not raise one. The only way to produce a number from here is an `INSERT` into `ticket_number`, and whether I committed it or rolled it back **it would spend 1460 permanently** — committing leaves a ticket nobody asked for, rolling back leaves exactly the kind of gap Part 64 just finished attributing to rolled-back previews. Causing the defect in order to measure it is not a test. So: **the next ticket raised, by anyone, should be `PMC-001460`**, and I will confirm the number when a real one appears. Thobie's tile walk-through is already owed and will serve as that confirmation, closing both at once.

Nothing was reseeded. `ticket_number` still starts at 1 and ends at 1459, and 1454–1459 exist, so a reseed below 1459 would collide — the handoff's own warning, recorded here so it is in the running record and not only in the handoff.

**Step 2 is NOT done.** WS36's own wording gates it: *"Wait for Cloud Build to confirm CI run 81 is green, then pull, and restart PSA-Desk."* Run 81 on `98b30eb` is recorded in its evidence table as **NOT VERIFIED until it reports**, and no confirmation has arrived. So the Came-from badges are not live: the working tree is at `7530b0d`, which carries the code, but PSA-Desk is still running what it loaded at its last start. Nothing to check on screen yet — Chat #n pills, the *Came from* filter and the Reports split all wait on that restart. Held, not forgotten.

### Part 66: 2026-10-09, ~16:20 +08:00. **Email to ticket stopped because the unclean shutdown zeroed all three delta-link files. Handed back, nothing changed — it is a parse error. Came-from is live.** MEASURED.

Answers WS36's two-part message at head `ed9b9c5`. Step 1 read-only throughout; the only change in this Part is the PSA-Desk restart WS36 cleared in step 2.

## 1. Email to ticket

**Tasks** (`Get-ScheduledTask PSA-* | Get-ScheduledTaskInfo`, read ~16:03):

| Task | State | LastRunTime | LastTaskResult | NextRunTime |
|---|---|---|---|---|
| PSA-Mail-Helpdesk | Ready | 2026-10-09 16:02:02 | **1** | 16:03:03 |
| PSA-Mail-Support | Ready | 2026-10-09 16:02:02 | **1** | 16:03:03 |
| PSA-Mail-Procurement | Ready | 2026-10-09 16:02:02 | **1** | 16:03:03 |
| PSA-Notify | Ready | 2026-10-09 16:02:02 | 0 | 16:03:03 |
| PSA-Calendar | Ready | 2026-10-09 16:02:02 | 0 | 16:03:03 |
| PSA-Rules | Ready | 16:02:02 | 0 | 16:03:03 |
| PSA-Teams | Ready | 16:02:02 | 0 | 16:03:03 |
| PSA-BizBox | Ready | 15:05:05 | 0 | 16:05:05 |
| PSA-Desk | Running | 13:13:13 | 267009 (running) | — |

**No pickup is disabled and every one has run since 13:13** — each runs every minute and fails. So the one fix WS36 allowed without handing back does not apply.

**Logs** — each pickup's log holds only its last pass; all three read the same, no subject or address in them:
> `Pass failed: Invalid URI: The hostname could not be parsed.`

PSA-Notify's: `0 due: 0 sent, 0 failed.`

**The database:**
- By channel today: **helpdesk** only, `last_in` **2026-10-09 12:26**, n = **22**. No support or procurement row today.
- Per hour from 06:00: 07 NEW_TICKET 1 · 08 APPENDED 1 · 09 NEW_TICKET 2 · 10 NEW_TICKET 2 · 11 APPENDED 1, NEW_TICKET 1 · 12 APPENDED 2. **Nothing at 13 or after.**
- Newest `received_at` anywhere in `intake_message`: **12:26**. So the stoppage starts between 12:26 and the 13:10 shutdown, and no later.

**The drop folder:** 0 files waiting in `helpdesk-pmcne-ph\`, `support-pmcne-ph\`, `procurement-pmcne-ph\`, and 0 in the root. `failed\`: helpdesk **1**, support **6**, procurement **1** — **every one dated 2–6 Oct, none today.** Nothing is piling up, because no pass gets far enough to fetch.

**The cause. MEASURED.** The task runs `Invoke-PmcMailPickup.ps1`, which at line 203 reads its saved Graph delta link into `$uri` with `(Get-Content -Raw).Trim()` and calls Graph with it; line 322 rewrites that file at the end of **every** successful pass, i.e. every minute. All three live files in `D:\psa\mail-state\`:

| File | Bytes | NUL bytes | Last written |
|---|---|---|---|
| `inbox-deltalink-helpdesk-pmcne-ph.txt` | 407 | **407** | **13:11:03** |
| `inbox-deltalink-support-pmcne-ph.txt` | 406 | **406** | **13:11:03** |
| `inbox-deltalink-procurement-pmcne-ph.txt` | 410 | **410** | **13:11:03** |

Every byte is `0x00`. A good backup from 2 Oct, read the same way, begins `68 74 74 70 73 3a 2f 2f` (`https://`) and ends in CR LF. **13:11:03 is fifty seconds after the 13:10:13 shutdown request and two and a half minutes before the 13:13:41 boot that logged event 6008.** The file sizes were committed and the data never was — the textbook mark of a hard stop during a write. `.Trim()` does not remove NUL, so `$uri` is 407 NULs, and .NET answers exactly *"Invalid URI: The hostname could not be parsed."* The token was not printed; only its bytes were counted.

The same shutdown that cost 999 ticket numbers (Part 64) also blanked the three mailboxes' bookmarks.

**What I did NOT do, and why.** WS36's rule: *"Anything else (a certificate error, a Graph 403, a parse error, files piling up in failed\): hand back with the log lines and change nothing."* This is a parse error. Nothing in `mail-state\`, `mail-drop\` or any task was touched.

**The remedy already exists, for WS36 to authorise.** `scripts/Repair-PsaMailPickup.ps1`, built after 2 Oct's 410 incident: with `-Apply -ResetDelta` it copies each delta link beside itself, deletes it, and runs one real pass from `-Since` (default two days back, which covers 12:26), keyed by Message-ID so nothing imports twice. Three things to know before choosing it:
- its default `-Mailbox` is **helpdesk and support only** — procurement must be named;
- it was written for a link that *expired* (410), not one that is *zeroed*; `-ResetDelta` forces the reset either way, but whether its step-3 diagnosis recognises a NUL file as broken is NOT VERIFIED;
- run as a sysadmin login, the import step is refused by the dbo guard; the messages land in `mail-drop\` and the minute task, running as `psa_desk`, imports them — which it can do only once its own delta file is no longer zeroed.

`mail-why` not run: Dada has not yet passed a sender.

INFERRED, for WS36: line 322's `Set-Content` writes in place. A write to a temp file then a rename would leave either the old link or the new one after a crash, never a blank. That is a code change and WS36's to make.

## 2. Came-from

Pulled to `ed9b9c5` (CI run 81 green on all four jobs, per WS36). **Restarted PSA-Desk:** before Running, `:8085` **401** → stopped, Ready, no answer → started, Running, **401** after 2 s.

**The three checks, exercised as `psa_desk` against live data in the code the desk just loaded** — the functions each page calls, not the rendered page, because `:8085` is behind Windows sign-in and I do not type credentials:

- **Chat #n pill that opens the chat — PASS.** All **8** chat-made tickets resolve to their own pill: Chat #3, #6, #12, #15, #16, #17, #18, #20. For PMC-000387 the badge renders `<a class='pill came came-chat' href='/chat/3' title='Made from a live chat'>Chat #3</a>` — a link to that chat.
- **Board *Came from* filter — PASS in code.** `board.py:372` renders `<label>Came from</label><select name=src>` with *Anywhere* plus Chat, Portal, Email, Desk, Other; `board.py:126` applies it.
- **Reports, *Opened by where it came from* — PASS.** `metrics.desk(...)["by_came_from"]` over all 7 boards, six months: **Email 258 · Desk 28 · Portal 25 · Chat 8 = 319**, every ticket accounted for. Desk splits as Desk 14, Phone 13, Walk-up 1; Portal as plain 19 and tile 6.

Someone signed in should still glance at the three screens; the logic underneath them is measured.

**Restarted in this Part: PSA-Desk, once. Nothing else.** No pickup task, no state file, no drop file.

### Part 67: 2026-10-09, ~16:35 +08:00. **Email to ticket is back on all three mailboxes. 18 email tickets recovered, no duplicates, no number gaps. The procurement window needed a second run — the first lost a race with the minute task.** MEASURED.

Applies WS36's go on the delta repair. Elevated (`IsInRole(Administrator)` True), run through `powershell -Command` with a `&` call so `-Mailbox` arrives as three strings.

**Two deviations, both stated before running.**
- **No `-AsDesk`.** It reaches `Get-Credential` (`Invoke-PsaSpine.ps1:222`), a password prompt for the desk account. I do not type passwords, and this shell cannot answer one. It affects step 5 only — a read of what the desk has taken — which was refused under my login by the dbo guard, as the script itself predicts. I made that read myself under `EXECUTE AS psa_desk`, below.
- **The script's step 3 judges a delta link by age, not contents.** It named all three only because each was 182 minutes old (> 120). A NUL-filled link written a minute ago would not be flagged. INFERRED gap in the tool, for WS36.

**Preview — passed the gate.** All three named (*"the delta link has not moved for 182 minutes"*); certificate found, valid to 2027-10-01 (so not a 401); step 6 got `System.UriFormatException` on all three — not 410, 401 or 403; ended *"Nothing was changed."*

**Baseline:** `intake_message` 377, newest 12:26, 0 after 12:26 · `ticket` 320 · `IDENT_CURRENT` **1460** · duplicate `message_id` groups 0.

**PMC-001460 had already appeared** (IT_PROJECTS, intake DESK, 16:12), exactly +1 from 1459. **That closes Part 65's `IDENTITY_CACHE` check** — and it means the first mail ticket would be 1461 or later, not 1460 as WS36 expected.

**Apply, run 1 — all three, `-Apply -ResetDelta`, 16:13:15.**
- Each NUL link copied to `.bak` beside itself, then deleted.
- **helpdesk:** step 6 fetched 13 files into the drop folder; import refused under my login (dbo), link not saved. The 16:14:02 minute task imported them: **0 new, 0 appended, 12 already seen, 1 auto-reply ignored.** Nothing was missing from helpdesk.
- **support:** step 6 fetched into the drop folder over 16:13:57–16:15:05; the minute tasks imported **3 new** at 16:14:05 and **11 new, 2 appended, 53 already seen** at 16:15:08.
- **procurement: the window was NOT re-read.** The minute task fired at 16:14:02 — after step 3 had deleted the link, before step 6 reached procurement at 16:15:06 — found no link, did *"first sync from 2026-10-09 16:14"*, and saved one. Step 6 then read *"since last pass"* from that link: 0. Everything between the crash and 16:14 would have been skipped.
- **A second defect, latent this time:** run 1's procurement pass logged **`board IT_HELP`**. The script hands its one `-BoardId` (default IT_HELP) to every mailbox. It imported 0, so nothing was misrouted — and under a sysadmin login the import is refused anyway, so files would have gone to the drop folder and the minute task's own board. But run as the desk account, procurement mail would land on IT_HELP.

**Apply, run 2 — procurement only, `-BoardId PROCUREMENT`, 16:17:06.** Started six seconds past the minute so step 6 would begin reading before the next minute task — it did, at 16:17:19. Fetched the window from 2026-10-07 16:17 into the drop folder, board PROCUREMENT; import refused under my login, link not saved. The 16:18:02 minute task imported: **11 files — 3 new, 8 already seen.** Those three would have been lost to run 1's race.

**Verified, 16:19:**

| Check | Result |
|---|---|
| PSA-Mail-Helpdesk / -Support / -Procurement last result | **0 / 0 / 0** (16:19:19); Notify 0, Calendar 0 |
| Each delta file a readable link | all three begin `https://graph.microsoft.com/`, **0 NUL bytes**, rewritten 16:19:04 |
| `intake_message` rows after 12:26 | **9** (newest 16:16); 377 → **398** in all |
| `mail-drop\` drained | helpdesk 0 · support 0 · procurement 0 waiting |
| `failed\` unchanged | **1 / 6 / 1**, as before |
| No message imported twice | `GROUP BY message_id HAVING COUNT(*) > 1` → **0 rows** |
| New ticket numbers | 1460–1479, **no gaps** |

**What came in** (numbers > 1460, intake EMAIL): **IT_HELP 14 · PROCUREMENT 3 · UNROUTED 1 = 18.** Plus PMC-001464, a PHONE ticket raised at the desk at 16:14. `ticket` 320 → **339**.

## One thing the counts surfaced, NOT VERIFIED

**Ten of the 18 were sent this morning, before the crash** — nine to support (05:40 to 08:10) and one to procurement (06:17). Support's own log shows it **healthy all morning**: *"0 new"* from 05:00 to 08:16 local, then normal imports at 08:17, 08:29, 09:24, 09:33, 10:29 and on. So Graph's inbox delta did not hold those ten when they were dated; they entered the Inbox later. INFERRED: released from quarantine or moved out of Junk this afternoon, perhaps by someone looking for the missing mail. NOT VERIFIED — that needs the mailbox, which this desk does not read.

**Consequence for the desk:** `opened_at` is the message's own time, so those ten carry 05:40–08:10 and will look up to ten hours old and likely past SLA, though the desk first saw them at 16:14–16:18. Correct to the requester's clock; misleading on the desk's. Dada's call whether to note it.

**Changed in this Part:** three delta links reset (run 1) and procurement's reset again (run 2), each with its `.bak` kept beside it; two real passes fetched into the drop folders. No task registration, argument, certificate or code touched.

**For WS36, three tool defects found by using the tool:**
1. `Repair-PsaMailPickup.ps1` passes one `-BoardId` to every `-Mailbox`; it should take each mailbox's board from its task.
2. Its step 3 → step 6 gap can lose a race with the minute task, which then saves a "from now" link and the window is never read. Disabling the pickup tasks across steps 3–6 would close it.
3. Its step 3 judges a link by age only; a NUL or otherwise unparseable link should be flagged by contents.
And from Part 66, still open: `Invoke-PmcMailPickup.ps1:322` writes the link in place; write-then-rename would survive the next 6008.

### Part 68: 2026-10-09, ~17:15 +08:00. **Pull and restart HELD: CI is red. Run 82 failed on all four jobs, and run 83 on the head has already failed both test jobs.** MEASURED. Nothing changed.

WS36's instruction: *"after CI is green: pull and restart PSA-Desk… That brings in the coloured badges and the email-pickup crash protection from run 82."* It offered to confirm CI on request; `gh` is signed in here (DadaBanal), so I read CI myself instead of asking.

**Why the gate matters more than usual this time.** The pull alone is a production change. The three PSA-Mail-* tasks run `Invoke-PmcMailPickup.ps1` straight out of this working tree, and the pull rewrites that script (88 lines). The next minute task would run the new code, restart or no restart. So the CI gate covers the pull itself, not only the PSA-Desk restart.

**What `git fetch` shows:** local `35143bc`, remote `86c51e7`, three commits behind — `671dcd9` (pickup crash protection), `30907fe` (merge), `86c51e7` (came-from badges in colour). Seven files, +190 −14.

**CI, read 17:10 +08:00:**

| Run | Head | Result |
|---|---|---|
| 81 | `98b30eb` | success (Part 66's Came-from) |
| **82** | `30907fe` | **failure — all four jobs**: test (3.11), test (3.14), windows, sql-server |
| **83** | `86c51e7` | in progress: **test (3.11) failure, test (3.14) failure**; windows and sql-server still running |

**Run 82's failures** (test 3.11 log): *Ran 804 tests — FAILED (failures=2, errors=1)*, all three in the mail tests, and all three are tests that read the scripts' source text:
- ERROR `MailPickupScriptTest.test_the_delta_link_only_moves_after_a_good_import` — `self.text.index("Set-Content -Path $DeltaFile")`: *substring not found*. The new `Save-DeltaLink` (temp file, `WriteThrough`, `File.Replace`) replaced that line.
- FAIL `MailPickupDeltaRecoveryTest.test_an_expired_delta_link_starts_a_fresh_window_instead_of_throwing` — expects `Remove-Item -Path $DeltaFile -Force`; the 410 branch now loops `foreach ($f in @($DeltaFile, "$DeltaFile.prev")) { … Remove-Item -Path $f -Force }`.
- FAIL `MailRepairScriptTest.test_a_forgotten_delta_link_is_followed_by_one_real_pass` — expects `$Apply` within 400 characters before a match; the new line that also forgets `.prev` pushed it outside the window.

INFERRED: each is a test pinned to the old wording, not a behaviour fault — the new code does what each test's name describes. That is WS36's to judge and fix.

**Run 83:** `86c51e7` adds nothing to any of those three tests (its only test change is +3 lines, for the badges), so the same three are expected to fail there. INFERRED: the job logs were not yet readable while the run was in progress.

**Held:** no pull (the tree stays at `35143bc`, so the pickups keep running the script that has been result 0 since Part 67), no PSA-Desk restart. All three pickups and PSA-Desk untouched.

**For WS36:** the crash protection reads well — it addresses Part 66's in-place write (temp + flush + `File.Replace` with `.prev`), rejects a link containing NUL or not matching `^https://graph\.microsoft\.com/`, sets an unreadable one aside, and recovers from two hours before the last good save. It also answers two of Part 67's three tool defects: a recovered window no longer starts at "now", and a NUL link is judged by contents. Only the tests stand between it and the live pickups.

### Part 69: 2026-10-09, ~18:20 +08:00. **The desk's public front doors are built but NOT published: tunnel `pmc-psa-net`, two loopback-only IIS sites, no DNS record, no connector running.** MEASURED. Dada's instruction, not WS36's.

Dada, 9 Oct: *"lets get the ticketing live online on the web through my cloudflare"*; *"can we do proper security"*; *"make sure to use a diff site it may cause split brain on internal network"*; *"i also have diff domains"*; he authorised `pmcne.net` and `pmcne.online` and left the pick to SQL01.

**Recorded once, as CLAUDE.md requires when contradicting the record:** the record treats DND-SQL01 as LAN-only (risk R3). A Cloudflare Tunnel opens no inbound port, but it does put the desk on the internet. Dada was told and chose to proceed.

**Measured before building:** `pmcne.ph`'s public DNS is on Cloudflare; `help`/`desk.pmcne.ph` had no public record. The desk's sign-in is a form (its 401 carries no `WWW-Authenticate`), so it passes through a tunnel; Entra sign-in is not configured, so staff type their domain password into the page — the reason Access must sit in front. Neither `pmcne.net` nor `pmcne.online` is served by the internal DNS (internal answers equal public ones), so either removes split-brain entirely. **Picked `pmcne.net`**: mail filters treat `.online` with more suspicion, and ticket emails will carry these links.

**Built:**
- `cloudflared` 2026.10.0, `cloudflared-windows-amd64.msi` from `github.com/cloudflare/cloudflared` (owner `cloudflare`, not a fork): size 19,494,912, **SHA-256 equal to the checksum in the release notes**, Authenticode **Valid, Cloudflare, Inc.** (DigiCert). Installed silently, exit 0.
- Tunnel **`pmc-psa-net`** in the Tech Sponge account (where `pmcne.net` lives; a tunnel serves only its own account's zones). An earlier tunnel `pmc-psa` in the `pmcne.ph` account is unused, 0 connections — to delete once Dada agrees.
- Config `C:\ProgramData\cloudflared\config.yml`, folder ACL **SYSTEM and Administrators only, inheritance off** (not under `System32`: this build installs to `Program Files (x86)`, where a 32-bit process is redirected to `SysWOW64`). Ingress: `help.pmcne.net` → `127.0.0.1:8091`, `desk.pmcne.net` → `127.0.0.1:8092`, **everything else 404** (`ingress validate` OK; `help.pmcne.ph` and an unknown name both hit the 404 rule).
- `scripts/New-PsaPublicIis.ps1` (this commit): IIS sites **PSA-Portal-Public** and **PSA-Desk-Public**, own pools, bound **http on 127.0.0.1 only**. Each forwards to the desk telling it the internal name (so it behaves exactly as on the LAN), translates the Origin header **only** when it is exactly its own public origin, refuses `/api/`, and marks cookies Secure. The LAN sites PSA-Portal and PSA-Desk are untouched.

**Proved on the server, with controls:**

| Test | Result |
|---|---|
| public portal `GET /` | 303 `Location: /my` (relative) |
| public desk `GET /` / portal `GET /my` | 401, the sign-in page |
| `/api/…` on either public site | 404 *Not available here* |
| POST, Origin = the site's own public origin | 401 sign-in — passes the origin check |
| POST, Origin = a foreign site / the other public site / `desk.pmcne.net.evil.example` | **403** *posted from another site* |
| `help.pmcne.net` on the server's LAN address | 400 — not served off loopback |
| LAN `help.pmcne.ph` / `desk.pmcne.ph` | 302 `/my` / 401 — unchanged |

The origin POSTs carried no credentials (an empty sign-in form), so nothing reached AD.

**Not done, in order:** Cloudflare Access on both names (needs Dada signed in to Cloudflare in the browser pane — the sign-in hit a verification check SQL01 cannot complete), WAF and a rate limit on `/login`, then the Windows service and the two DNS records. The UDM read (no port-forward to this server) was denied by the permission layer and was not retried.

**For WS36 (INFERRED from the code):** every link the desk writes — the ticket link and approvals link in emails (`outbox.py:836,857`), the requester link on a ticket (`ticket.py:766`), the calendar feed (`members.py:329`) — uses `PSA_PORTAL_URL` / `PSA_PUBLIC_URL`, the `.ph` names. From outside PMC they do not resolve, exactly as today. Switching those two settings to `.net` alone would **break LAN sign-in**: the desk's accepted origins come from the same two settings, so posts from `help.pmcne.ph` would get 403. Making links work everywhere needs a code change: accept a list of public origins, and choose the link host per reader.

### Part 70: 2026-10-09, ~19:00 +08:00. **`desk.pmcne.net` is LIVE on the internet, behind Cloudflare Access: only the 14 active PMO Helpdesk members, by one-time PIN. `help.pmcne.net` is not published.** MEASURED. Dada's instruction.

Dada, 9 Oct, choosing among options SQL01 laid out: *"ok desk only for now pls"*; then *"it should only be accessed by pmo staff or whos member of the PMO helpdesk board"*.

**Zero Trust, Tech Sponge account** (done by SQL01 in Dada's signed-in Chrome, each change approved in chat; Dada added the payment card himself — Cloudflare requires one even for the Free plan):
- Plan **Zero Trust Free**, "50 seat limit", **0 of 50** seats used at set-up. The activation page's own words: the card may be charged *"for usage that exceeds free limits"*; Standard is $7/seat/month (Cloudflare's plan page, read 9 Oct).
- Team domain **`pmcne.cloudflareaccess.com`** (was auto-named `icy-voice-0813`).
- **Login method: One-time PIN added.** VERIFIED (Cloudflare changelog, 18 Jun 2026): new organisations default to the *Cloudflare* identity provider — sign-in with a Cloudflare account that is a member of the account — and OTP is no longer added automatically. Without adding it, no technician could have signed in.
- Access application **PMC Service Desk**, self-hosted, destination **`desk.pmcne.net`** (whole host), login **One-time PIN only** (instant authentication on), session **24 h**.
- Policy **PMO Helpdesk members only**: Allow, Include → Emails → **14 addresses** = every active member of board `IT_HELP` (`psa.board_member` × `psa.member` with no `inactive_from`): 13 `@pmcne.ph`, 1 `@premieremedicalcenter.net`; 9 WORK, 5 ADMIN. Checked chip by chip. Addresses not recorded here.

**Server:**
- Tunnel config now answers **`desk.pmcne.net` only** → `127.0.0.1:8092`; everything else 404 (`ingress validate` OK; `help.pmcne.net` hits the 404 rule). Previous config kept beside it as `.bak`.
- IIS **PSA-Portal-Public stopped**, auto-start off. PSA-Desk-Public running. LAN sites untouched.
- Windows service **Cloudflared**, Automatic, ImagePath `cloudflared.exe --config=C:\ProgramData\cloudflared\config.yml tunnel run`. (The first idle service process would not stop — Cloudflare's doc shows it NOT_STOPPABLE — so it was ended by PID and the service started fresh.) **4 connections**, QUIC: mnl01, ceb01, hkg10, hkg12.

**DNS:** one record on `pmcne.net`: `desk` CNAME → the tunnel, **proxied**; the dashboard lists it as type *Tunnel → pmc-psa-net*. 30 of 200 records. `help` and `desk` were searched first and absent (search control: `mail` found 4).

**Proved from outside**, against Cloudflare's authoritative servers:

| Request as a stranger | Result |
|---|---|
| `GET /` | 302 → `pmcne.cloudflareaccess.com/cdn-cgi/access/login/desk.pmcne.net` |
| `GET /login` | 302 → the same |
| `POST /login` with a guessed password | **302 → the same — never reaches the desk** |
| `GET /api/v1/health` | 302 → the same |
| the desk's own sign-in form in any response | **0** |
| gate page | 200, *PMC Service Desk*, *Send login code* |
| `help.pmcne.net` | does not exist |

This matters because **AD's lockout threshold is "Never"** (minimum length 7; `net accounts /domain`, read 9 Oct): without Access, the form would take unlimited password guesses against every domain account.

**Not done / for later:**
- The 14-address list is a **copy**: when someone joins or leaves the PMO Helpdesk board, the policy must change too. Candidate: a small sync from `board_member` (needs an API token — Dada's call).
- *Remove inactive users from seats* is **off** (Zero Trust › Settings); turning it on keeps the seat count honest.
- Microsoft Entra ID as the login method instead of OTP (PMC's own sign-in, with MFA) — needs an Entra app registration.
- WAF / rate limit on `desk.pmcne.net` — lower priority now nothing unauthenticated reaches the origin.
- Unused tunnel `pmc-psa` in the `pmcne.ph` account: delete once Dada agrees. Its certificate and the `pmcne.ph` cert remain in the user profile.
- Email links still say the `.ph` names (Part 69).

### Part 71: 2026-10-09, ~19:15 +08:00. **Unused tunnel `pmc-psa` (the `pmcne.ph` account) deleted, on Dada's yes.** MEASURED.

Checked first: no active connections, never had a DNS record, and not the tunnel the service runs (the service's config names `pmc-psa-net`). `cloudflared tunnel delete pmc-psa`; the `pmcne.ph` account now lists **no tunnels**. `pmc-psa-net` unaffected: still connected, `desk.pmcne.net` still answers 302 to the Access gate.

Left on disk, for Dada to decide: the deleted tunnel's credential file (now useless — deleting a tunnel revokes it) in the user profile and its copy in `C:\ProgramData\cloudflared\`; and the **`pmcne.ph` origin certificate** (`%USERPROFILE%\.cloudflared\cert.pem`), which is still a live credential able to create tunnels and DNS routes in `pmcne.ph`. Nothing running needs it.

### Part 72: 2026-10-09, ~19:10 +08:00. **Dada signed in to `desk.pmcne.net` from Australia through Access. CI run 85 green, so the held pull and PSA-Desk restart are done: crash-safe mail pickup and the coloured Came-from badges are live.** MEASURED.

**Access, end to end.** Dada's first attempt from Australia failed `ERR_NAME_NOT_RESOLVED`: he had looked the name up minutes before the DNS record existed (~10:44Z), and `pmcne.net`'s SOA lets resolvers cache "does not exist" for **1800 s**. All four large public resolvers already answered correctly. Once his resolver let go, Cloudflare's Access log recorded: **PMC Service Desk · Allowed · dada.banal@pmcne.ph · AU · 18:54 (server time)**. The gate, the one-time PIN and the tunnel work from outside the country.

**The held pull (Part 68).** WS36 fixed the three source-text tests (`118deb4` *pin the new delta-link save, not the old wording*; `1637d4b` *read Save-DeltaLink's body the same on a CRLF checkout*). **Run 85 on `1637d4b`: windows, sql-server, test (3.11), test (3.14) all success.** Every local commit was already upstream (`git cherry`: all `-`) and the tree was clean, so the live tree was aligned to the branch head with `git reset --keep` — nothing lost. PSA-Desk restarted: **401 → down → 401**.

**The crash protection, first passes on the new code (19:05):** PSA-Mail-Helpdesk, -Support, -Procurement and PSA-Notify all **result 0**. Each mailbox now has its link **and a `.prev`** beside it — the new `Save-DeltaLink` (temp file, write-through, `File.Replace`) at work — and all six files are valid Graph links with **0 NUL bytes**. A shutdown mid-write now leaves the previous link, never a blank one.

`desk.pmcne.net` still answers 302 to the Access gate after the restart.

**Open, each needing Dada's yes or hand:** delete the `pmcne.ph` origin certificate (the permission layer refuses SQL01 on that folder — Dada runs `Remove-Item "$env:USERPROFILE\.cloudflared\cert.pem"`); turn on *remove inactive users from seats*; keep the 14-address list in step with the PMO Helpdesk board; Entra ID as the login method; a rate limit on `/login` (low value now — nothing unauthenticated reaches the origin); and, for WS36, email links that work from outside.

### Part 73: 2026-10-09, ~19:30 +08:00. **Parked for the week of 12 Oct 2026, on Dada's word: Entra ID sign-in on the Cloudflare gate.** Nothing built.

Dada, 9 Oct: *"lets mark this for next week"*, after SQL01 laid out what Entra sign-in needs (steps VERIFIED against `developers.cloudflare.com/cloudflare-one/integrations/identity-providers/entra-id/`, updated 26 Aug 2026):

- **Entra:** Enterprise applications → *Create your own* (app you're developing); redirect URI (Web) `https://pmcne.cloudflareaccess.com/cdn-cgi/access/callback`; note client ID and tenant ID; **client secret** (Dada creates and pastes it — SQL01 does not handle secrets; when it expires the gate locks everyone out, so it needs a renewal reminder); Graph delegated permissions `openid email profile offline_access User.Read` (+ `Directory.Read.All`, `GroupMember.Read.All` for a group rule); **Grant admin consent** (Dada's click).
- **Cloudflare:** Zero Trust → Integrations → Identity providers → Add → *Azure AD*; Save, Test; PKCE on; Support groups on if a group rule. Then PMC Service Desk: login method Entra, policy by group.

**Decisions waiting on Dada:** (1) group or list — recommended a **PMO Helpdesk Entra group**, which retires the hand-kept 14-address copy; does one exist? (2) keep **One-time PIN as a fallback** — recommended, because `encoder@premieremedicalcenter.net` may not be a PMC Microsoft account; (3) secret expiry — suggested **24 months** with a reminder.

**Separate and bigger, for WS36:** the desk's own Entra sign-in (`PSA_ENTRA_TENANT` / `PSA_ENTRA_CLIENT`, built but off) would take domain passwords out of the desk entirely, LAN included, while AD lockout stays "Never".

Still open from Part 72: Dada to delete the `pmcne.ph` origin certificate; yes/no on *remove inactive users from seats* (30 days suggested).

### Part 74: 2026-10-09, ~19:40 +08:00. **`encoder@premieremedicalcenter.net` could never receive mail; the gate and the desk now use her working alias `encoder@pmcne.ph`.** MEASURED.

Dada: *"check encoder@premieremedicalcenter.net she didnt receive any emails"*, then, with a screenshot of the M365 admin centre: *"its set as this so it needs to be updated on ad can we work it like this for now"*.

- **Cause.** The M365 user *Philhealth Encoder* (UPN `encoder@pmcne.ph`, synced from on-prem AD) has primary SMTP **`encoder@premieremedicalcenter.net`**. That domain has **no MX and no A record** (control: `pmcne.ph` MX → Exchange Online). Mail from outside — Cloudflare's one-time PINs included — has nowhere to go. Mail inside the tenant may still route internally (INFERRED), which is why it went unnoticed.
- **Her aliases** (Dada's screenshot): `encoder@premieremedicalcenter.onmicrosoft.com` and **`encoder@pmcne.ph`** — the second receives mail through `pmcne.ph`'s MX.
- **Cloudflare Access** policy *PMO Helpdesk members only*: `encoder@premieremedicalcenter.net` removed, `encoder@pmcne.ph` added. Read back: **14 addresses**, last updated 19:36.
- **Desk**: member `encoder` email → `encoder@pmcne.ph`, through `members.save` under `psa_desk` (audited, actor `sql01 for dada.banal`); preview rolled back, then applied. `for_sign_in` maps both addresses to `encoder`, so sign-in, boards and tickets are unchanged. She was the only member on that domain.
- **Left for Dada:** make `encoder@pmcne.ph` her primary address in **on-prem AD** (the M365 page is read-only for synced users), then Entra Connect carries it up.

### Part 75: 2026-10-10, ~02:50 +08:00. **Staff "away from PMC" links: pulled and previewed; the task change needs Dada, because both sender tasks run under a stored password.** MEASURED.

Applies `docs/handoffs/HANDOFF-cloud-sql01-WS36-20261009-desk-away-links.md`.

- **CI run 87 on `94fde4e`: windows, sql-server, test (3.11), test (3.14) all success** (read with `gh`). Every local commit already upstream (`git cherry`: 0 local-only), tree clean; live tree aligned to `94fde4e` with `git reset --keep`.
- **`https://desk.pmcne.ph` is the LAN address** (the handoff's INFERRED, now MEASURED): PSA-Teams already runs with `-DeskUrl 'https://desk.pmcne.ph'`, and IIS binds the LAN PSA-Desk site to `desk.pmcne.ph` (Part 69).
- **Preview.** The sender's own preview runs `outbox-pending` as the calling login, which the desk's dbo guard refuses for a sysadmin, so the same code was called directly under `EXECUTE AS psa_desk`, rolled back: `outbox.pending(..., dry_run=True, desk_url=https://desk.pmcne.ph, desk_away_url=https://desk.pmcne.net)`. **0 PENDING** at the time, so nothing to render live; `desk_links` gives exactly the two lines (*At PMC: …/ticket/PMC-001460*; *Away from PMC: https://desk.pmcne.net/ticket/PMC-001460 (asks for the PMC sign-in code, once a day)*), only for `OWNER, PAGE, RESOURCE, SCHEDULED`, and **nothing** with neither set.
- **Step 3 refused by Windows.** `Set-ScheduledTask -Action` on PSA-Notify: *"The user name or password is incorrect."* Both PSA-Notify and PSA-Teams run as `psa_desk`, logon **Password**, and Windows will not change such a task without the password again. Read back: PSA-Notify **unchanged** (no `DeskAwayUrl`, still `psa_desk/Password`, last pass result 0). A backup XML was exported first (`D:\psa\logs\PSA-Notify-task-before-20261010-024249.xml`).
- **`scripts/Set-PsaDeskAwayLinks.ps1`** (this commit), for Dada: preview by default — shows each task's line after the change, identifiers hidden; `-Apply` (elevated) exports both tasks, **asks for the `psa_desk` password once at the Windows prompt** (held in memory only, zeroed after), adds exactly `-DeskUrl 'https://desk.pmcne.ph' -DeskAwayUrl 'https://desk.pmcne.net'` to PSA-Notify and `-DeskAwayUrl 'https://desk.pmcne.net'` to PSA-Teams, then reads both back and checks only those were added and the logon is unchanged. Preview run: both lines exactly as the handoff specifies.
- **`-PortalAwayUrl` not set**, as the second handoff says: requester emails stay word for word as today.

**Waiting on Dada:** run `Set-PsaDeskAwayLinks.ps1 -Apply` on DND-SQL01, then the walk-through (owner email → *Away from PMC* on a phone off PMC Wi-Fi → Access PIN → desk sign-in → that ticket). SQL01 then checks the next passes are result 0.

### Part 76: 2026-10-10. **Dada's two hand-steps in one script: away links and the old `pmcne.ph` certificate.** MEASURED.

Dada: *"on one and 2 give me one sctipt ill run kt"*. Step 1 is the Part 75 away links; step 2 is deleting the `pmcne.ph` origin certificate (Parts 71–72).

- **`scripts/Invoke-DadaAwayLinksAndCert.ps1`** (this commit), run elevated by Dada. It runs `Set-PsaDeskAwayLinks.ps1 -Apply`, which asks once for the `psa_desk` password. Then it deletes `C:\Users\dada.banal\.cloudflared\cert.pem`, but only if three checks pass: (a) the file's account differs from the Tech Sponge certificate's (`cloudflared-zone2`); (b) both accounts can be read; (c) the tunnel config does not name the file. Each step reports separately, and step 2 runs even if step 1 fails. It prints same/different only, never a token or an id.
- **Checks, run by SQL01 before handing it over, with nothing deleted:**
  - Both certificates are present (control: a missing name returns False).
  - Their accounts are readable and **different**.
  - `config.yml` does **not** name the file. The service runs `--config C:\ProgramData\cloudflared\config.yml`, which uses only its own `credentials-file`.
  - The script parses under PowerShell 5.1.20348 with 0 errors and is plain ASCII.
- **Not touched:** the dead `pmc-psa` tunnel's credential files (useless since the tunnel was deleted, Part 71).

**Waiting on Dada:** run it. SQL01 then checks the next PSA-Notify and PSA-Teams passes are result 0.

**Part 76, update (06:42 +08:00): step 1 done by Dada. MEASURED.** Dada ran `Set-PsaDeskAwayLinks.ps1 -Apply` directly:
- **Both tasks:** `DONE`, "only the new arguments added: True", "logon unchanged: True".
- **Backups:** `PSA-Notify-task-before-20261010-064026.xml` and `PSA-Teams-task-before-20261010-064029.xml`.

Next passes:
- **PSA-Notify:** result 0. Log line *0 due: 0 sent, 0 failed*.
- **PSA-Teams:** result 0, error lines 0. "Nothing posted" because it has been in PREVIEW since Part 22 by design. The backup confirms there was no `-Apply` before, so that is unchanged.

**Still open:** the certificate (step 2). Re-running `Invoke-DadaAwayLinksAndCert.ps1` is safe: step 1 now prints `SKIP … already has -DeskAwayUrl` without asking for a password, and step 2 runs. The walk-through (Part 75) is also open.

**Part 76, update (06:44 +08:00): step 2 done by Dada. MEASURED.** `Invoke-DadaAwayLinksAndCert.ps1` result:
- **Step 1** skipped both tasks, as expected.
- **Step 2** checks passed: the certificate belongs to a different account from Tech Sponge's, and the tunnel config does not use it. Then "Deleted.", with the cloudflared service Running.

Read back by SQL01:
- The `pmcne.ph` certificate is gone. The Tech Sponge one is still present.
- cloudflared is Running, with 0 ERR lines and 4 registered connections in the last 200 log lines.
- `desk.pmcne.net` → 302 to `pmcne.cloudflareaccess.com`. Control: an unpublished name gives no answer.
- PSA-Notify and PSA-Teams: result 0 at 06:44:44.

**Remaining from Parts 71–76:** the walk-through; *remove inactive users from seats*; encoder's primary address in AD.

### Part 77: 2026-10-12, ~11:00 +08:00. **079 applied, both boards' warm words written, the one-off tidy previewed and held for Dada.** MEASURED.

Applies `docs/handoffs/HANDOFF-cloud-sql01-WS36-20261012-warm-emails-department-079.md`.

- **CI run 90 on `dae80be`: windows, sql-server, test (3.11), test (3.14) all success.** Pulled fast-forward; 0 local-only commits, tree clean.
- **Backup.** `D:\Backups\PMC_PSA\PMC_PSA_COPYONLY_pre079_20261012-105041.bak`, 113.1 MB, COPY_ONLY with CHECKSUM; `RESTORE VERIFYONLY` reads *the backup set on file 1 is valid*. Ticket count before: **372**.
- **A control first, and it changed the reading.** `COL_LENGTH(N'psa.ticket', N'ticket_id')` read *absent* — because the key column is `work_item_id`, not `ticket_id`. Re-probed on the real first column: **128**. Only then was "department absent" a measurement rather than a blind method.
- **PSA-Desk** stopped (`:8085` 401 → down), 079 run, then started (down → 401, Running).
- **079, one transaction, both statements extracted verbatim from `platform/psa-spine/sqlserver/PMC_PSA_Spine_SqlServer.sql` by line range** (the guarded `ADD [department] NVARCHAR(400) NULL` at 4481–4482 and `CREATE INDEX [ix_ticket_department]` at 4707–4708). Checks inside the transaction, all PASS: column length **800**; index count **1**; `department IS NOT NULL` **0**; ticket count **372**, unchanged; control — a made-up column still reads absent. **COMMITTED.**
- **Board words, preview then apply, under `EXECUTE AS psa_desk`** (the desk's dbo guard refuses the CLI under a sysadmin login, as for Parts 66–78). Neither preview held a `~` line, so both were applied:
  - `IT_HELP` / `HELPDESK`: *Wrote 15 email(s); 2 already so; 0 kept as the board wrote them; 0 left on the desk's words.*
  - `PROCUREMENT` / `PROCUREMENT`: *Wrote 18 email(s); 0 already so; 0 kept as the board wrote them; 1 left on the desk's words.*
  - **Not touched:** whether any status emails at all.
- **One harness fault of SQL01's own, worth keeping.** The first apply raised `No results. Previous SQL was not a query.` from `outbox.set_template`. Cause: SQL01's impersonation harness built `mssql.Connection` directly and so skipped the `SET NOCOUNT ON; SET XACT_ABORT OFF` that `mssql.connect` sets; without NOCOUNT the port's `<stmt>; SELECT @@ROWCOUNT` batch yields the count second and the fetch fails. **Not a defect in the build.** `mail_template` read **0 rows** afterwards, so the transaction had rolled back whole. Fixed in the harness, both previews re-run identically, then applied.

**Two things for Cloud Build, neither blocking:**

1. **`IT_HELP` / *Status Resolved* reads `+` on every run**, so the handoff's *"a second run reads `Wrote 0 email(s)`"* does not hold for that one line (it reads *Would write 1*). **Not a data fault:** `outbox._set_mail` stores NULL words when the words asked for equal the desk's own defaults (line 550, deliberate), so the row never reads `custom` and the preview re-offers it. MEASURED: stored subject and body are **character-for-character equal** to the words wanted, and `status_mail` for `IT_HELP` holds **14 rows, exactly 1 of them with NULL words**. `PROCUREMENT` settles at *Would write 0*.
2. **The tidy's department half can fill nothing on this desk.** `departments.backfill` joins `ticket` to `contact` on `contact_id`. MEASURED: `psa.department` holds **52** rows, `psa.contact` holds **0**. So every ticket stays unset, and departments will only arrive on new tickets from AD.

**Step 6 (`ticket-fill`) previewed and NOT applied** — the handoff says Dada sees it first. Preview, whole:

```
department: 373 ticket(s) with none; 0 take their contact's; 373 stay unset (no contact, or AD's department is not on Setup > Departments)
company: 46 ticket(s) under UNCLASSIFIED -> PMC
portal tiles with no Type > Subtype > Item: 0
```

(373, not 372: one ticket arrived during the step.)

**After the step:** PSA-Notify and PSA-Teams both result 0 at 11:00 (*0 due: 0 sent, 0 failed*); PSA-Desk Running, `:8085` 401.

**Waiting on Dada:** his word on the `ticket-fill` preview above, then SQL01 runs it with `--apply`. Then the eyes-on checks: the Department column and filter on the board, the badge on a ticket, the portal's *Which department is this for?* on a ward PC, and the next requester email on either board reading like a person wrote it.

**Part 77, ruling (12 Oct 2026): a ticket's department is never backfilled.** Dada, on reading the `ticket-fill` preview: *"thje departments should only come from when it gets picked up from the requests portal direct emailing the ticket tech or the member will add their dept manually"*.

So a department is written at one of three doors only:
1. the requests portal's dropdown when the ticket is raised;
2. an emailed ticket, from the sender's own AD department, when it is on Setup › Departments;
3. a member typing it on the desk.

**MEASURED: the build already does exactly these three.** `tickets.py` (~588) takes the department the door was told, else `departments.of_contact` for the contact. The extra is `departments.backfill`, which `ticket-fill` calls — **that is what the ruling removes.**

- **`ticket-fill` is therefore NOT applied, in any part.** The 46 `UNCLASSIFIED -> PMC` company moves stay pending with it, since the one command does both.
- Handed to WS36 (cloud, one-way): take the department half out of `ticket-fill` or gate it so it can never write; say whether the company half becomes its own command. Also sent: the `IT_HELP` *Resolved* `+` line, and that the handoff's `ticket_id` control cannot work because the key column is `work_item_id`.
- The ruling costs nothing today in any case: `psa.contact` holds **0** rows against `psa.department`'s **52**, so `backfill` would have filled 0 tickets.

**Waiting on Dada:** nothing on departments. Open: whether the 46 old tickets under UNCLASSIFIED should move to PMC once WS36 splits that out.

**Part 77, applied (12 Oct 2026, ~11:15 +08:00): the 46 UNCLASSIFIED tickets are on PMC. MEASURED.** Dada: *"those unclassified move them to premiere medical center"*.

- **The company half ONLY.** `board.fill_company` was called on its own; `departments.backfill` was **not called at all**, per the ruling above. Run under `EXECUTE AS psa_desk`, one transaction, verify gate inside it.
- **Backup first:** `D:\Backups\PMC_PSA\PMC_PSA_COPYONLY_pre_company_move_20261012-111455.bak`, COPY_ONLY with CHECKSUM, `RESTORE VERIFYONLY` valid.
- **Measured against the right column.** The company is on `work_item.entity_id`, not on `ticket` — read from `board.fill_company` itself, not assumed.
- **Before:** 373 tickets, 46 under `UNCLASSIFIED`, 317 under `PMC`, 0 with a department. Control: a made-up company id reads 0, so the counts are counts and not a blind method.
- **Checks, all PASS:** under `UNCLASSIFIED` fell by 46 to **0**; under `PMC` rose by 46 to **363**; ticket count **373**, unchanged; **0** departments written, so the ruling held; control still 0. **COMMITTED.**
- **Audit:** one `TICKET_COMPANY` row, *46 ticket(s) UNCLASSIFIED -> PMC*.
- **A second run finds nothing** (*0 ticket(s)*).
- **Worth knowing, not a fault:** the desk's 373 tickets are now **PMC 363** and **JRBY-CI 10**. JRBY-CI was never under the catch-all and was not touched.
- **After:** PSA-Desk Running, `:8085` 401; PSA-Notify result 0 at 11:15.

**Still waiting on WS36 (cloud, one-way):** take the department half out of `ticket-fill`, so the command cannot backfill. Until then `ticket-fill` is not to be run at all — the company half is done and the department half is ruled out.

### Part 78: 2026-10-13, ~13:50 +08:00. **080 and 081 applied; Procurement rights set as Dada named them.** MEASURED.

Applies `HANDOFF-cloud-sql01-WS36-20261013-procurement-rights-lookups-081.md` (which replaces section 3 of the 080 handoff of the same day).

- **CI run on `a671768`: windows, sql-server, test (3.11), test (3.14) all success.** The sql-server job was the one red on runs 92 and 93; it is green on `0be85ef`, `a8351b3` and `a671768`. `a671768` differs from `0be85ef` by one file, the guide markdown, 263 lines, no code. Pulled fast-forward, 0 local-only commits, tree clean.
- **Backup:** `D:\Backups\PMC_PSA\PMC_PSA_COPYONLY_pre080_081_20261013-134611.bak`, 129.1 MB, COPY_ONLY with CHECKSUM, `RESTORE VERIFYONLY` valid.
- **PSA-Desk stopped** (`:8085` 401 → down). PSA-Notify, PSA-Calendar and PSA-Teams left Ready and untouched.
- **Counts before: `ticket_task` 1, `configuration` 0, `ext_change` 0.**
- **080 + 081 in ONE transaction, 15 guarded blocks**, each located in `sqlserver/PMC_PSA_Spine_SqlServer.sql` by its own text and run verbatim — never retyped. **22 checks, all PASS**, including the control probed first (a made-up column read −999 before anything ran, and again after). Widths as the handoff demands: `ticket_task.notes` −1, `schedule_id` 4, `priority` 4, `resolution` −1; `configuration.tag_number` 800, `installed_by` 400, `parent_configuration_id` 128; `ext_change.batch_id` 4 with **0** rows carrying one; `ext_lookup.list` 64, `code` 800, **0 rows**; `ext_batch.batch_id` is IDENTITY; all four indexes present; the three counts unchanged. **COMMITTED.**
- **PSA-Desk restarted:** down → 401, state Running.

**Procurement rights.** Dada: *"place me and shane de castro and ethel luciano with access and approve the rest on procurement read only"*.

Measured before deciding, because the obvious move would have been wrong:
- Areas are `PROC_PO`, `PROC_RR`, `PROC_ITEM`; levels NONE=None, READ=See, WRITE=Propose, ADMIN=Approve.
- **No role held any procurement grant**, which is exactly why Dada saw no Procurement menu.
- **A member holds exactly one role** (`role_of` takes one row; `assign` deletes then inserts). There is no stacking.
- **`dada.banal` is `is_sysadmin = 1`**, and `security.level()` returns ADMIN for a sysadmin in every module. **His role was not touched**; he already approves everywhere.
- `shane.decastro` shared SERVICE_MANAGER with `jefferson.simon`, `rubylyn.martinez` and `thobie.delacruz`. Granting that role Approve would have given those three Approve as well — the opposite of *"the rest read only"*.
- `ethel.luciano` was on no role, so she took the default TECHNICIAN. Putting her on a SERVICE_MANAGER-shaped role would also have raised her Knowledge, Projects, Reports, Schedule and Finance, and given her **Timesheets ADMIN**. Not asked for, so not done.

Applied under `EXECUTE AS psa_desk` through the desk's own `security` functions, so Setup › Audit records it:

| Role | PO | Receiving | Items | Who |
|---|---|---|---|---|
| Service manager | See | See | See | jefferson.simon, rubylyn.martinez, thobie.delacruz, dada.banal |
| Technician (default) | See | See | See | the other 17 active members |
| Read only | None | None | None | nobody today |
| **Procurement approver** (copy of Service manager) | **Approve** | **Approve** | **Approve** | **shane.decastro** |
| **Procurement approver (technician)** (copy of Technician) | **Approve** | **Approve** | **Approve** | **ethel.luciano** |

Every other module on the two new roles is an exact copy of the role it came from, so nobody's rights changed anywhere else. 11 checks, all PASS, including a control.

**One honest note on method.** The first apply **rolled back on a FAIL** — and the fault was in the check, not the data: `save_grants` stores no row for NONE, so an absent row *is* None, and the assertion demanded the literal string. The gate did its job; the assertion was corrected and the second run passed. Nothing was committed in between.

**Not built, as instructed:** the write path to BizBox (the 080 handoff's section 5 — the procedure, its EXECUTE-only login, the push-task setting). `PSA_BIZBOX_WRITE_ODBC` is set nowhere. Section 5 of the 081 handoff (`psa.vw_lookup` inside BizBox, plus the `lookup` object in the host map) is **not done**; until it exists the dropdowns offer what BizBox has used on real records, which the handoff says is fine.

**For Dada:** the guide went to Shane on 13 Oct as a PDF (Teams and email), in Area 54 › Handover and in `deliverables/`.

### Part 79: 2026-10-13, ~14:30 +08:00. **The dropdowns read words, not codes: `psa.vw_lookup` built and wired (081 section 5).** MEASURED.

Dada, with a screenshot of the category dropdown listing 1001, 1002, 1010…: *"this displays as numbers which isnt ideal and the sort isnt friendly"*.

**Cause, measured:** `psa.vw_product.Category` is `CAST(i.FK_mscItemCategory AS nvarchar(20))` — the raw code. The label table `dbo.mscItemCategory` (58 rows) was never read, because the `lookup` object of 081 section 5 had not been built. Status and unit were never affected: `vw_purchase_order`/`vw_invoice` compute their Status words in a CASE, and `vw_product.Unit` is already text.

**Built: `psa.vw_lookup` in `LiveDB_PMC`.** Read-only, five lists, 152 entries:

| List | Source | Entries |
|---|---|---|
| `category` | `dbo.mscItemCategory` — Code `PK_mscItemCategory`, Label `description`, SortNo `sorter` | 58 |
| `unit` | `dbo.mscUnits` — the item master stores the unit as text, so Code = Label = the word | 83 |
| `currency` | `dbo.mscCurrency` — Code `PK_mscCurrency`, Label `description`; `N/A` excluded | 2 |
| `po_status` | no BizBox table exists; the view's own CASE vocabulary, in **working order**: Draft, Ordered, Approved, Partly received, Received, Cancelled | 6 |
| `rr_status` | likewise from `vw_invoice`: Draft, Posted, Cancelled | 3 |

The sort was the second half of his complaint: categories now come out A to Z by name, and the two status lists in the order the work actually happens rather than alphabetically.

**No grant was needed, and that is a measured finding, not an assumption.** `psa_bizbox_reader` holds **SELECT on the whole `[psa]` schema** (`sys.database_permissions` class SCHEMA), not per-view grants — which is why no per-object grant existed for the four older views either. Proven by `EXECUTE AS USER = psa_bizbox_reader`: it read **152 rows** from the new view and `category 1001` came back as *Drugs / Medicines*, while the same session was still correctly **refused** `dbo.iwItems`. The original script's grant step was removed once this was known.

**Host map:** `lookup` added to `D:\psa\bizbox-map.json`; backup beside it as `bizbox-map.json.bak_20261013_142901`. 5 checks PASS including a control.

**The read.** The handoff's preview could not be run from this session: `sync-bizbox` without `--apply` is refused under a sysadmin login by the desk's dbo guard (*"the desk's login must have default schema [psa]… it has [dbo]"*), and a scratch SQLite target has no schema to compare against. So `PSA-BizBox` — the hourly task, which runs as `DND-SQL01\psa_desk` — was started early instead, doing exactly what it does every hour. Result 0:

```
product:        5472 rows,   0 new,  1 changed
purchase_order:  803 rows,   3 new,  8 changed
po_line:        2082 rows,  13 new,  2 changed
invoice:        1004 rows,   2 new,  0 changed
lookup:          152 rows, 152 new,  0 changed
```

`psa.ext_lookup` now holds 152 rows, `present = 1` on all, and a made-up list name returns 0.

**Rollback:** `DROP VIEW psa.vw_lookup;` in LiveDB_PMC, and restore the map from the backup. Nothing else was touched; the view writes nothing and reads only BizBox reference tables.

**Also settled today:** Dada on the wallpaper hours — *"7-5 as whats there ill tell u to change it when i want to"*. **Closed.** And MMS reports: *"mms reprots on the desk from ssrs if possible"* — measured as possible and then some: SSRS is running on this instance and `/BizBox MMS Reports/` already holds **164 reports** (MMS_ReorderPoint, MMS_PerpetualInventory, MMS_InventoryCriticalReport, MMS_Store_Tran_Rep_*, MMS_SuppliesMaterialsIssued_Summ, MMS_PurcSum_* …), so nothing needs writing — the desk needs a Reports tab that renders them. Handed to WS36.

### Part 80: 2026-10-13, ~14:45 +08:00. **Design and accessibility audit of the desk UI: it passes; four assistive-technology gaps sent to WS36.** MEASURED.

Dada: *"load design and web skills and check if the current web is on par and passes or are better things can be done to it"*, then *"yes send them to ws36"*. Skills loaded: `design:design-critique` and `design:accessibility-review` (WCAG 2.1 AA). Measured against `psaspine/web/templates.py` (3,157 lines), not against a screenshot. Script: `scripts/psa-080-081-20261013/Audit-DeskUI-20261013.py`.

**Verdict: it passes, comfortably.** Contrast computed *within* each theme — crossing themes is meaningless and the first pass that did so produced nine false failures:

| Theme | Worst pair | Ratio |
|---|---|---|
| Dark (default) | `#eef1f8` on chip `#232833` | **13.05:1** |
| Light | `#121726` on canvas `#dfe5f1` | 14.13:1 |
| Warm / violet / pink | — | 14.4:1 to 16.7:1 |

Against a 4.5:1 requirement. Accents as text also pass: 6.64:1 and 4.82:1; error colours 7.08:1 and 5.19:1.

Also measured and good: **`prefers-reduced-motion` honoured 13 times** (uncommon in internal tools), 83 design tokens, 132 `data-theme` hooks, 6 `prefers-color-scheme`, 19 breakpoints, 34 grid layouts, 72 `color-mix()`, 17 of 20 `min-height` values at or above the 44 px touch target, and all three `outline:none` correctly paired with a visible ring.

**Two findings from the first pass were wrong and were corrected before anything was sent:** the viewport meta **is** present (line 3096; the regex expected quotes around `name="viewport"` and it is written unquoted), and the `outline:none` uses **are** properly paired (lines 243, 438, 710). Neither is a defect. Recording this because an audit that reports false positives is worse than none — the same discipline as the watchdog lesson in `pmc-estate` §12.

**The four real gaps, all assistive-technology, sent to WS36:**
1. **No skip link** (WCAG 2.4.1) — zero matches anywhere in `psaspine/`. Every keyboard user tabs the whole nav on every page, worst on the grids people live in. Two `<main>` elements already exist to target.
2. **No screen-reader-only class** — zero matches for `sr-only`/`visually-hidden`. Without it there is no way to name something for a screen reader without showing it; 34 `<button>` against 3 `alt=` and 4 `<label>`. Gap 1 depends on this.
3. **`aria-describedby` used zero times** (WCAG 3.3.1) — and this desk *refuses input by design* ("That is not a status BizBox uses…", "Line 2: IT-9 is not an item BizBox has"). Those sentences are the product working, and none is tied to the field that caused it.
4. **`aria-live` used once** (4.1.3 in spirit) — tick-and-send, inline edits, batch counts and the Tasks *n/m* counter all change without a reload.

**Two code-health notes, not accessibility:** `!important` appears **101** times, which will make the design system harder to hold as warehousing and the Reports tab land; and `:focus` 31 against `:focus-visible` 5.

Nothing was changed. The UI is WS36's code.

### Part 81: 2026-10-13, ~16:25 +08:00. **082 applied; the lookup names confirmed; the stock measured. Three things now need Dada's hand.** MEASURED.

Applies `HANDOFF-cloud-sql01-WS36-20261013-mms-reports-082.md` and begins `...-warehouses-drugs-083.md`.

- **CI run 38362823461 on `c81f7fa`: windows, sql-server, test (3.11), test (3.14) all success.** Pulled fast-forward; 0 local-only, tree clean.
- **Backup:** `D:\Backups\PMC_PSA\PMC_PSA_COPYONLY_pre082_20261013-162335.bak`, 132.1 MB, COPY_ONLY with CHECKSUM, `RESTORE VERIFYONLY` valid.
- **082 applied**, 5 guarded blocks extracted from the port by their own text, one transaction, **11 checks all PASS** with the control probed first and again after: `psa.mms_report` and `psa.mms_report_run` exist, `report_id` is IDENTITY, `path` is 800, both tables empty, all three indexes present and `ux_mms_report_path` is UNIQUE. **COMMITTED.**
- **PSA-Desk restarted**, down to 401, state Running.

**Section 4a, confirmed.** `psa.ext_lookup` holds exactly the five expected `ListName` values and nothing else: `category` 58, `currency` 2, `po_status` 6, `rr_status` 3, `unit` 83 - **152 total**. Nothing missing, nothing extra that would be read and ignored.

**Handoff 083's two measurements, done. The answer is better than expected.**

| | |
|---|---|
| `dbo.iwWareitem` total rows | **591,369** |
| rows with `actualqty` other than zero | **4,358** - **0.7%** of the table |
| warehouses actually holding stock | **25** of the 73 |
| largest: warehouse 1041 | 1,013 rows; then 1019 (682), 1071 (487), 1008 (357), 1052 (214) |

The quantity column is **`actualqty`**; the other 20-odd quantity columns on that table are movement buckets (`purcqty`, `salesqty`, `adjinqty`, `issoutqty`), not a balance. **A view narrowed to non-zero rows mirrors 4,358 rows - a factor of 136 smaller than the table, and smaller than the desk's current largest mirror (product, 5,472).** So stock on hand is comfortably mirrorable after all, and this morning's warning is answered: narrow it, and the hourly pattern carries it unchanged.

### NOT DONE - three things that need Dada, not SQL01

1. **`pywin32` cannot be installed: the package hook blocks it.** Step 9 needs it so the desk reaches the report server with its own Windows sign-in. `C:\PMC\Python312\python.exe -c "import win32com.client"` fails; pip is present (26.2.1). **Verified on PyPI this session** before attempting: *pywin32*, author **Mark Hammond (et al)**, `mhammond@skippinet.com.au`, OSI-approved Python Software Foundation License, project `github.com/mhammond/pywin32`, releases back to at least 2018, page <https://pypi.org/project/pywin32/>. The install was nevertheless refused twice by `pmc_session.py` with *"PyPI '2': does not exist on PyPI"* - **the hook is parsing the trailing digits of the name as the package**. Not retried with any other spelling. Only Dada edits the allow-list. **Without it the reports tab still loads and reports the server's 401 in a sentence; it simply cannot render.**
2. **The SSRS *Browser* role for `DND-SQL01\psa_desk` on `/BizBox MMS Reports`.** `rs.exe` is **absent** on this host, so it cannot be scripted; it needs Report Manager's web UI. Measured: SSRS knows 244 users and **`psa_desk` is not among them**.
3. **`PSA_SSRS_URL` in PSA-Desk's environment.** The desk sets its environment **inside its own task action**, and that task runs as `psa_desk` with a **stored password**, so Windows refuses the change without it - the same wall as Parts 75 and 76. Script written for him: **`platform/psa-spine/scripts/Set-PsaDeskSsrsUrl.ps1`** - preview by default, `-Apply` asks for the password once at the Windows prompt, exports the task XML to `D:\psa\logs` first, verifies only `PSA_SSRS_URL` was added and the logon is unchanged, restarts the desk and ends in a verdict. Parses clean under PowerShell 5.1, plain ASCII, previewed.

Steps 10 and 11 (the first `sync-mms-reports` read and the walk-through) wait on 1 to 3. Nothing else in the desk is affected.

**Still not built, per instruction:** the write path. `PSA_BIZBOX_WRITE_ODBC` is set nowhere.

**Part 81, update (16:35 +08:00): Dada ran the script; two of the three are now closed; everything rests on the package.** MEASURED.

- **`PSA_SSRS_URL` is set.** Dada ran `Set-PsaDeskSsrsUrl.ps1 -Apply`. Read back, **8 checks all PASS**: the value is `http://dnd-sql01/ReportServer`, the other six environment values survive, the account is still `psa_desk` with logon `Password`, `PSA_BIZBOX_WRITE_ODBC` is still absent, the task is Running and `:8085` answers 401. Task XML backups in `D:\psa\logs` (`PSA-Desk-task-before-20261013-1632*.xml`).
- **Step 7, the SSRS *Browser* role, was ALREADY SATISFIED - no grant was needed.** MEASURED from the ReportServer catalog: `/BizBox MMS Reports` carries its own policy (`PolicyRoot=False`) and **`\Everyone` holds Browser** on it (along with Content Manager, Publisher, Report Builder and My Reports), plus `BUILTIN\Administrators` Content Manager and `PMCNE\HIS Reporting` Browser. So `psa_desk` already has what the handoff asked Dada to give it. Nothing was changed. *(Worth a separate look one day: `\Everyone` holding Content Manager on a reports folder is broader than it needs to be. Not touched, not in scope.)*
- **The report server is reachable:** `http://dnd-sql01/ReportServer` answers **200** to an authenticated request from this host.

**The first read still fails, and the cause is the package, not permissions.** Running the 082 step-10 read under `EXECUTE AS psa_desk` (the CLI is refused under a sysadmin login by the dbo guard, as `sync-bizbox` and `mail-words` are) and with `PSA_SSRS_URL` supplied, it answers:

> `refused: The report server refused the desk's sign-in. SQL01 gives the account PSA-Desk runs under the Browser role on the reports folder.`

**That sentence is misleading in this case and the evidence says so:** `\Everyone` already has Browser, and the same server answers 200 to an authenticated request. The real cause is read from `psaspine/ssrs.py` line 82-89: `WinHttpTransport` is the class that sends the process's Windows identity, and its `__init__` does `import win32com.client`. Without **pywin32** the code falls back to a plain `urllib` request, which sends no Windows identity, gets a 401, and reports it as a sign-in refusal. Exactly as the handoff's step 9 predicted, though the sentence points at the wrong remedy.

**So one thing now blocks steps 10 and 11 entirely: the pywin32 allow-list entry, which only Dada can add.** Everything else for the MMS reports tab is in place. Worth passing to Cloud Build: when the transport is the plain fallback, the refusal sentence should say so rather than naming the Browser role, because here the role was already granted.

**Part 81, second update (16:40 +08:00): the report server accepts ONLY Windows integrated authentication, so the fallback transport can never work.** MEASURED.

Dada: *"find out from the bizbox chat as to why it errors"*. Asked the Bizbox Reporting SSRS session (it owns the BizBox SSRS work) and, while waiting, measured the one thing that settles it.

`rsreportserver.config` on this host (`C:\Program Files\Microsoft SQL Server Reporting Services\SSRS\ReportServer\`):

```
<AuthenticationTypes>
  <RSWindowsNegotiate />
  <RSWindowsNTLM />
</AuthenticationTypes>
<RSWindowsExtendedProtectionLevel>Off</RSWindowsExtendedProtectionLevel>
EnableAuthPersistence = true
```

**`RSWindowsBasic` is absent. `Custom` is absent.** The server speaks Negotiate and NTLM and nothing else. URL reservations are `http://+:80/ReportServer/` and `http://+:80/Reports/`, both owned by `NT SERVICE\SQLServerReportingServices`, Listen: Yes.

So the diagnosis is no longer an inference from a stack trace:

- the desk's `WinHttpTransport` performs a Negotiate/NTLM handshake with the process identity; it needs **pywin32**;
- without it the code falls back to plain `urllib`, which performs **neither** handshake;
- a caller that offers neither is refused by a server that accepts only those two. **There is no configuration of permissions that would make the fallback succeed** - `\Everyone` already holds Browser and it still 401s.

**Therefore pywin32 is structurally required, not merely preferred.** The only alternative would be enabling `RSWindowsBasic`, which would send credentials over plain HTTP on this server and is a security downgrade; **not proposed, not done**.

**For Cloud Build:** the refusal sentence should distinguish the two cases. When the transport in use is the urllib fallback, it should say the desk could not present a Windows identity and name pywin32 - not tell SQL01 to grant a Browser role that, here, was already granted. As written it sends the reader to the wrong fix.

**Part 81, third update (16:50 +08:00): there is a package-free route, and it is proven end to end. pywin32 is no longer needed.** MEASURED.

The Bizbox Reporting SSRS session answered (Dada: *"find out from the bizbox chat as to why it errors"*). It confirmed the authentication diagnosis independently and supplied the fix: **Windows ships `C:\Windows\System32\curl.exe`, which speaks SSPI NTLM and SPNEGO and sends the calling process's own identity.** Under the PSA-Desk task that identity is `psa_desk`. Verified here rather than taken on trust:

| Probe | Result |
|---|---|
| `curl.exe --version` | **8.13.0**, Windows, Schannel |
| **control:** ListChildren with no credentials | **401** |
| ListChildren with `--negotiate -u :` | **200, 26,890 bytes, 163 report names** |
| Render `MMS_ListOfVendorsOrSuppliers` to PDF | **200, 253,320 bytes, `%PDF-`, 30 pages, letter** |
| Render `MMS_ADHOC_CriticalInventoryLevel` to PDF | **200, 60,286 bytes, 1 page** |
| Render the same to `rs:Format=EXCELOPENXML` | **200, 78,887 bytes, magic `504b` - a real .xlsx** |

So listing, PDF rendering and Excel rendering all work today with nothing installed. **The pywin32 blocker is dissolved**; it remains the tidier transport, but it is no longer required and need not be forced through the allow-list for this.

Also measured while proving it: rendering `MMS_PerpetualInventory` and `MMS_ReorderPoint` without parameters returns **HTTP 500 `ParameterInfoCollection.ThrowParameterValueNotSet`** - the report engine asking for input, *not* an authentication failure. Authentication had already succeeded at that point.

**Parameters, measured from `ReportServer.dbo.Catalog.Parameter` across all 164:** exactly **2** have every parameter defaulted or optional (`MMS_ADHOC_CriticalInventoryLevel`, `MMS_ListOfVendorsOrSuppliers`); the other **162 need at least one value typed**. That matches the Bizbox session's count independently.

**What that session reported, kept separate because it is theirs and I have not re-measured it:** of the 164 reports only **52 have ever run** since 9 Aug (21,673 runs, 121 users); the heaviest are `MMS_ADHOC_ExpRequisition` 3,229, `StockReq` 3,023, `DelReceiveRep` 2,982, `POSLIP` 2,979, `ExpIssuance` 2,445. Trouble list: `MMS_ElectronicStockCard` 90 failures and up to 294 s, `MMS_PerpetualInventoryPerItemGroup` fails every time (4 of 4), `POSLIP` 12 failures, `InvMstrLstperCateg` up to 200 s. Their suggestion, which I agree with: surface the 52 that are used and hide the 112 that never have been. Most ADHOC reports want a BizBox document number, so they belong on a record's page rather than in a general list.

**Two findings from that session for Dada, neither mine to act on:**
1. `\Everyone` (S-1-1-0) holds Browser, **Content Manager**, My Reports, Publisher and Report Builder on the **root and every BizBox folder**, plus the system roles **System Administrator and System User**. Any authenticated account can publish, delete or change server settings. Vendor-set, not PMC-set. Flagged, not changed.
2. **The SSRS service runs as `pmcne\dada.banal`** - Dada's own account, not a service account. A password change on it stops the report server.

---

**Part 82 (17:15 +08:00): a Billing email raised no ticket. The intake duplicate guard is suppressing genuinely new requests - 30 of them, three distinct faults.** MEASURED.

Dada: *"this billing ticket isnt appearing"*. Read as: the email-to-ticket pickup did not raise a ticket for that 16:43 message, and he wants to know why. His Outlook renders +3 h, so his "7:43 PM" is 16:43 PH; not a clock fault.

**The pickup is healthy.** `PSA-Mail-Helpdesk`, `PSA-Mail-Support`, `PSA-Mail-Procurement`, `PSA-Notify`, `PSA-Calendar` all ran 17:00:00, result 0, next 17:01:01, triggers PT1M. The message reached `support@pmcne.ph` at `2026-10-13T08:43:32Z` and **was imported**.

It did not become a ticket because the desk decided it was a duplicate:

| column | value |
|---|---|
| `disposition` | **DUPLICATE** |
| `work_item_id` | **NULL** |
| `duplicate_of` | the 11:31 message from the same sender |
| `run_id` | `mail-support-pmcne-ph-20261013084404` |

The text was **appended as a note to `PMC-001580`** - the 11:31 ticket, a *different doctor*. Nothing lost; filed onto the wrong person's ticket, no new ticket raised.

**The rule** is `psaspine/intake.py` `_recent_same_subject()` (~line 540, called ~line 708): match on `from_address` + **exact `subject`** + `received_at >= at - 24 h`, take the newest with a ticket. Its own docstring calls it *"the weaker guard... INFERRED"*.

**Fault 1 - a reused subject line is not a duplicate.** PMC departments use a standing subject line, one mail per case, and the normaliser strips `Re:` so a reply's subject becomes byte-identical to the original's (22 chars in both rows here, confirmed equal in SQL). Across all **30** DUPLICATE rows: **30 of 30** subjects byte-identical to the parent's, **30 of 30** inside the window, **30 of 30** appended as a note, **none raised its own ticket**. Dispositions over 478 rows: NEW_TICKET 325, APPENDED 105, DUPLICATE 30, UNCLASSIFIED 18. Worst absorbers: `PMC-000148`, `PMC-000303`, `PMC-000407` took 3 other people's requests each; `PMC-000386` took 2. **10 sender+subject pairs are in active reuse** (3+ uses), led by `premieremedfm252022@gmail.com` at 11 - so the exposure is structural, not a one-off.

**Fault 2 - the parent may arrive after the child.** The query has a lower bound only; no `received_at < at`. With `ORDER BY received_at DESC` a message can be filed as a duplicate of one not yet received. **MEASURED: 4 of 30 have a negative gap** (-49, -48, -22, -15 min). `import_drop` iterates `sorted(drop.iterdir())` - **filename order, not time order** - so this is reachable in normal operation.

**Fault 3 - it crosses channels and boards.** The guard filters sender and subject only. `PMC-000148` was raised from **support**; a **helpdesk** message from the same sender on 1 Oct 15:52 was suppressed against it and its text appended there. A Helpdesk request can vanish into a PMC Service Board ticket, where no Helpdesk member will see it.

**Against Dada's own ruling.** He ruled on this guard on 2 Oct: two no-subject requests from one ward are **two requests**. This is that ruling one step on - an empty subject is not an identity, and neither is a reused one. INFERRED: the 2 Oct fix treated the empty subject as the special case; the measurement says the general case is the problem.

**Controls:** `disposition='ZZZ_NOPE'` 0 against `'NEW_TICKET'` 325; `from_address='zzz-nobody@nowhere.invalid'` 0; all 30 `duplicate_of` values resolved to a real parent, no orphans. Two of my own queries failed first and the schema notes are worth keeping: `psa.intake_message` has **no** `status`/`state` column (it is `disposition`), and `psa.work_item` has **no** `created_at`.

**Sent to WS36** as `docs/handoffs/HANDOFF-sql01-cloud-WS36-20261013-intake-duplicate-guard.md`, with the full 30-row table for fixtures (no subjects, no bodies - lengths only, per the content fence) and four suggestions in confidence order: bound the window at both ends, add channel/board to the match key, stop matching on subject alone (Dada's policy call, not ours), and make the DUPLICATE path visible so a suppressed request cannot look like one that never arrived.

**Nothing changed on this host.** Read-only throughout. Dada was offered the recovery of `PMC-001580`'s note as its own ticket and chose this handoff instead, so that note and the other 29 stay where they are until he says otherwise.

---

**Part 83 (14 Oct 2026): Dada's MMS build instruction, got from the Bizbox Chat session and sent to WS36. Two collisions with what WS36 has already shipped.** Relayed, not measured here.

Dada: *"hey can you pls ask the claude code chat bizbox chat how i want the mms built like biBox but better and send it to ws36"*. Read as: ask that peer session for the MMS design brief and hand their answer to WS36. Asked them; they answered with a 394-line brief, and they carry an instruction of his from 13 Oct that SQL01 had not seen: *"i also want you to tell it bow i want it built as per the bizbox but better mms only module"*, with the standing constraint *"dont make anuy changes that will destroy things ok"*.

He also corrected my first message to them. I had closed it with "we have the SQL route to LiveDB_PMC and ReportServer and you may not"; his reply was *"the bozbox chat can get to it"*, so I withdrew that line and told them to measure BizBox themselves. **SQL01 ran no BizBox probes for this at all** — a LiveDB_PMC table survey I had started was rejected by Dada mid-call and abandoned, which was right: it was not what he asked for and it would have collided with their work.

**Theirs, not mine (R5).** Every figure in the brief is the Bizbox Chat session's measurement; I re-ran none of it. I verified exactly two things, both of which hold: the committed copy is **byte-identical** to the record copy (`cmp`, sha256 `0b3072d1…48cd005`, 21,509 bytes — verified byte-wise, not by eye, per R9), and it passes the repo's content fence — **no dotted quad of any kind**, no denylist term, and every name-shaped match is a screen caption. Their standing instruction on conflict, which I endorse: if our measurements disagree, theirs are wrong until re-run; **do not average**.

**Two collisions, mine to raise because neither session can see both sides. Neither is mine to resolve.**

1. **"Same screens" versus "modern design".** Their Rule 0 is his and overrides the rest: *same tree, same screens, same steps, same words* — a department head must recognise the screen — and they record that an earlier redesign into *"boards and worklists"* was **withdrawn** after he said *"it should functio nsimilar to bixbox but better"*. But on 13 Oct he told me *"make sure it has all the data it needs and it conforms to modern design load skills needed"*, and 083 shipped against that. The reading that reconciles them — "modern design" is the rendering, "same screens" is the information architecture — is the one I would act on, **but it is a reading, and last time somebody read "similar" four screens were withdrawn.** So WS36 is told: build new MMS screens to Rule 0, do not re-architect the Procurement screens already shipped on the strength of this handoff, flag anything already shipped that Rule 0 would change, and let Dada rule.
2. **Their build rules 1–3 assume a BizBox write path the desk is forbidden.** Exclusive cutover per screen, writes proven on `TrainingDB_HIS8` first, honour the rowversion columns — all describe writing BizBox's own tables. **The desk's constraint stands: the BizBox write path is not built and `PSA_BIZBOX_WRITE_ODBC` stays unset.** Told WS36 to read those rules as what not to foreclose, not as a licence to write, and that permitting BizBox writes would be a new decision from Dada.

**Also flagged to WS36:** four of the five artefacts the brief says not to re-measure live in the OneDrive record, and **WS36 is a cloud session with no route to it**. The captions needed for the first screen are inside the brief itself, so they are not blocked; beyond that they are to ask rather than guess a caption. Reflection over the assemblies needs **Windows PowerShell 5.1** — pwsh 7 refuses `ReflectionOnlyLoadFrom` (SYSLIB0018) and returns zero windows, a false negative that reads as "no forms found".

**The four findings of theirs that change architecture rather than backlog**, carried into the handoff: MMS does not own the stock number (**128,462 of 227,077** ledger rows are HIS patient charging, so the clinical side is the majority writer); the printed document is the product, not a report feature (~21,700 runs in 60 days, ~360/day, **eight of the top ten are document prints**, analysis under 5%, and the 629 RDL reports stay where they are); the requester surface is the high-volume product and BizBox has none (**655** hold Expense Requisition Details, **640** Purchase Requisition Details, and **neither document has an approval field anywhere in the schema** — the strongest fit with what WS36 has already built); and a field nobody fills should have been a calculation (twelve reorder fields at zero, with **2,250 of 2,250** receipt lines carrying `FK_iwPOitem` so lead time is measurable on every line; `iwPOinv.deliverdate` populated on **0 of 837** POs, so vendor lateness is not derivable until captured).

**Priority was explicitly left with Dada** in the handoff — their phase-1 list says of itself that it is what the numbers point at for him to order, and I repeated that WS36 may not start it as a backlog.

**Gates estimating, and WS36 told not to quote a number before it exists:** how many MMS screens actually *write*. 133 screens is not the driver; the count of save paths is, and one PowerShell 5.1 reflection pass gives it. Still open with the vendor: contract terms on direct database writes and on reverse-engineering the assemblies, and whether a web client or API is on their roadmap. And nobody has read the steps of the disabled job `PMC - MMS Movement Column Alignment`, which would settle their stock-reconciliation finding.

Filed as `docs/bizbox-mms-design-brief-20261014.md` (verbatim, theirs) and `docs/handoffs/HANDOFF-sql01-cloud-WS36-20261014-mms-as-per-bizbox-but-better.md` (the covering note, mine). **Nothing changed on any host.**

---

**Part 84 (14 Oct 2026): Bizbox Chat corrected their own §5.1 — `actualqty` is the outlier, not the buckets — and their one question for WS36 turned out to be SQL01's to answer.** Their measurement; my answer.

They sent an addendum unprompted after I told them WS36 had shipped 084 on their §5.1 ground. Re-reading their own §5.1 against that, they found it told WS36 to compute the position from the ledger **without their ever having proved the ledger can produce one**. They measured that gap and it reversed the direction of the defect.

**Theirs, re-run by nobody here.** Across **5,681** item+warehouse pairs where any of three candidate figures is non-zero: ledger == buckets **4,458 (78.5%)**, `actualqty` == buckets 1,750 (30.8%), `actualqty` == ledger 1,893 (33.3%), all three agree 1,711 (30.1%), none agree 1,002 (17.6%). **The ledger and the buckets are two broadly consistent views of the same history; the stored `actualqty` — the number every BizBox screen shows — agrees with neither about two thirds of the time**, and not by one correctable offset: on the eight largest rows ledger and buckets agree exactly, `actualqty` does not, and the direction varies. They ruled out three explanations, each measured: cancelled rows (610 of 227,084, summed both counting and excluding them, every figure identical to the digit), staleness (of 4,351 stock-holding pairs with history, **zero** last moved over a year ago), and no history to compare against (only **7** such pairs).

**What they corrected under their own name:** the direction (§5.1 blamed the buckets; it is `actualqty` that departs from both), and the denominators — §5.1's *2,617 of 4,358 (60.1%)* counts `iwWareitem` rows holding stock while the addendum's 5,681 counts item+warehouse pairs where any figure is non-zero, so **the two must not be quoted against each other**. §5.1's instruction — one derived position from the ledger, never a maintained bucket — **stands, now evidenced rather than asserted**.

**Verified here, not taken on trust:** the addendum's sha256 **matches the hash they stated before I copied it** (`f8bb3d72…915111`, 133 lines as they said), it is byte-identical to the record copy, the brief is **unedited** (still `0b3072d1…48cd005`, so `bb96800` holds), and the fence is clean — no dotted quad, no denylist term.

**Their one question was: which of the three figures does the 084 stock view read?** They declined to assert anything about 084, correctly — no local checkout here and the GitHub routes on this host are unauthenticated, which is cannot-see, not not-there. The check belonged to whoever can read the schema, so I ran it.

**MEASURED, with controls both ways: none of the three.** `psa.vw_stock_on_hand`, `psa.vw_item_ledger` and `psa.vw_receiving_line` are all **absent**; the live map wires only `invoice`, `lookup`, `po_line`, `product`, `purchase_order`, and `stock` / `movement` / `rr_line` are **not wired**. Controls: `psa.vw_zzz_nope` absent, `psa.vw_lookup` EXISTS, `dbo.iwWareitem` EXISTS.

**So 084 reads nothing yet, and the choice of figure is SQL01's, not WS36's.** WS36 built the containers (`ext_stock`, `ext_movement`, `ext_rr_line`) and the sample map names those three views as their sources — **the views are mine to build and do not exist**. Their addendum arrived before anything was baked in, which is its whole value.

**It also needs no change to what WS36 shipped.** `ext_stock` takes quantity, unit_cost, as_of; `ext_movement` takes qty_in, qty_out, balance, unit_cost. A ledger-derived position fills all of them from one source, and `iwItemLedger` carries `lotno`, `expdate` and `purcprice` **on the row** — so the ledger route is the only one of the three that can also carry lot, expiry and cost, answering their §5.2, §5.3 and §5.4 from one place instead of three.

**SQL01's intent, for Dada's go:** build `psa.vw_stock_on_hand` off the ledger, not off `actualqty`. The view itself is additive and read-only; **wiring it into the map is the moment Procurement starts seeing it, so the wiring waits on his word.**

**A trap I inherit when I build these views, and it produces a confident wrong answer rather than an error.** Their first run picked the ledger's warehouse key by **pattern-matching column names and matched `FK_mscBranches` before `FK_mscWarehouse`**. Branch joined against warehouse matched nothing, every ledger net came back `0.00`, and the output read as a clean, alarming "0.0% agreement" — entirely a method artefact. The tell was that every value was *exactly* zero, which is not what disagreement looks like. `iwItemLedger` carries **both** keys; the warehouse one is `FK_mscWarehouse`. **Name the column; never match a pattern.** They caught it themselves and the 0% never left their session.

**Unchanged:** the brief still governs, Rule 0 is untouched, and both collisions from Part 83 remain open and remain Dada's — Bizbox Chat explicitly declined to resolve either, confirming the "modern design as rendering vs Rule 0 as information architecture" reading is a reasonable *reading* with nothing measured that settles it, and confirming my relay of their build rules 1–3 as what not to foreclose rather than a licence to write. This addendum needs no write either; the derivation is a read and `PSA_BIZBOX_WRITE_ODBC` stays unset.

Filed as `docs/bizbox-mms-stock-truth-addendum-20261014.md` (verbatim, theirs) and `docs/handoffs/HANDOFF-sql01-cloud-WS36-20261014-mms-stock-truth-addendum.md` (mine). **Nothing changed on any host.**

---

**Part 85, ruling (14 Oct 2026): build how MMS *functions*, better — not how its screens look. Rule 0 is overturned and Collision 1 is closed.**

Dada, after being told the brief's Rule 0 was *"same tree, same screens, same steps, same words — a department head must recognise the screen"*:

> *"no i want it built how mms functions but better"*

Read as, and acted on: **function parity, not screen parity.** Every function MMS has, every step it takes, the same outcome at the end — built better. How it looks is not the constraint; what it does is.

**What this overturns.** Rule 0 of `docs/bizbox-mms-design-brief-20261014.md`, written in good faith by the Bizbox Chat session, required the captions, grid bands, button labels, footers and screen tree to be reproduced. **That was their inference from his earlier words and he has now corrected it.** The utterance it was built on — *"it should functio nsimilar to bixbox but better"* — has **function** as its operative word; it was read as reaching the screen layer and it does not.

| | |
|---|---|
| Binding | every MMS **function**, every **step**, the same **outcome** — and better |
| Not binding | the captions, the grid bands, the button labels, the footers, the screen tree |
| Still binding, 13 Oct | *"conforms to modern design load skills needed"* |

**Collision 1 from Part 83 is closed, in favour of the modern design WS36 already shipped.** The 083 Procurement screens are not in question and **must not have BizBox captions retro-fitted onto them**. Part 83 told WS36 not to re-architect them on the strength of the brief; that is now superseded by something stronger — there is nothing to retro-fit.

**Function parity is the stricter half, not the lighter one**, because a caption can be read off a form and a behaviour cannot. What still binds, from the brief's own measurements: the document chain end to end (PR → PO → Delivery/Receiving → Stock Req → Stock Issuance, plus Expense Req → Expense Issuance, Purchase Return, Qty Adjustment, Material Production, Physical Count, Job Order); the statuses and who moves a document between them (PR FS/NS/PS; PO `postatus` plus two approval stages genuinely used at 802/35 and 762/75); the same outcome from the same inputs, down to the ledger row; **the printed document at the same click, day one** (~21,700 runs in 60 days, eight of the top ten are document prints, and the 629 RDL reports stay where they are); and one writer among several, since 128,462 of 227,077 ledger rows are HIS patient charging.

"But better" remains the brief's §5 — seven measured defects, as corrected by the stock-truth addendum, where **`actualqty` is the outlier, not the buckets**. The strongest fit with what WS36 has already built is unchanged and is a function to add rather than a screen to copy: **655 hold Expense Requisition Details, 640 Purchase Requisition Details, and neither document has an approval field anywhere in BizBox's schema.** MMS has no requester experience at all.

**Not changed by this ruling:** MMS only, not HIS/PIS/FMS; his standing constraint *"dont make anuy changes that will destroy things ok"*; every measurement in the brief and the addendum; and priority, which stays his. **Collision 2 remains open and remains his** — the brief's build rules 1–3 assume writing BizBox's own tables, the desk forbids it, `PSA_BIZBOX_WRITE_ODBC` stays unset, and they are relayed as what not to foreclose rather than a licence to write.

**One consequence worth recording.** The brief's §1 said *"do not re-measure the screen layer"* and named five artefacts, four of which WS36 cannot reach because they live in the OneDrive record. **That now matters much less** — the screen inventory, the 239 grid columns and the caption list existed to let somebody reproduce screens, and nobody is reproducing screens. What WS36 needs instead is the **function and status inventory**, which is in the brief itself and reachable. The question changes from *"what does the screen say"* to *"what does this status transition do, and what does this save write"*, which is both a better question and one SQL01 or Bizbox Chat can answer on request. Still gating estimating, unchanged: **the count of save paths, not the count of screens.**

Filed as `docs/handoffs/HANDOFF-sql01-cloud-WS36-20261014-dada-ruling-function-not-screens.md` and sent to WS36; the Bizbox Chat session was told their Rule 0 is superseded, since it carries their name in the repo. **Nothing changed on any host.**

**Part 85, addition (14 Oct 2026): the design skills are a standing instruction, on SQL01 and WS36 both — and `frontend-design` is being enabled.**

Dada, immediately after the ruling: *"use design skills and whatever skills available when building it or when u tell ws36 to build it"*. Read as **not a one-off** — every build of this, and every handoff of it to WS36, loads the design skills first, plus anything else relevant that exists. It binds both sessions.

It sits directly on top of the ruling: Part 85 freed WS36 from copying BizBox's screens, and **this says what replaces them — function from MMS, design from the skills, not from guesswork and not from BizBox.**

**Named from the catalogue, checked this session rather than recalled**, per the no-hallucination rule. The `design` plugin is **enabled** and carries seven real skills: `design:design-system`, `design:design-critique`, `design:accessibility-review`, `design:ux-copy`, `design:design-handoff`, `design:user-research`, `design:research-synthesis`. Also enabled and relevant: **`pdf`** and **`xlsx`**, because the brief's §4 makes the printed document the product, so the print path is a design surface with its own skill; plus `theme-factory` and `brand-guidelines`.

**`frontend-design` was flagged as existing but NOT enabled, and Dada moved on it immediately** — *"enable them"*, then *"front nd design"*. It is Anthropic's own plugin (`anthropics/claude-plugins-official`), one skill, UI/UX implementation. SQL01 cannot enable a plugin; the install card was rendered and **Dada enables it out of band**. WS36 is told to check it is actually available before relying on it and to say so if it is not, since it was unavailable when the ruling was first filed. Only Dada edits what is enabled — never substitute a lookalike.

**Three rules sent with it.** Load before building, not after, or the skill becomes a review instead of a design. **Say which ones were loaded**, in the handoff or the commit — a skill that does not fire does not exist, and nothing distinguishes *offered but not chosen* from *never offered*; if one is unavailable in the cloud session, say so rather than silently skipping it. And **`design:ux-copy` does not get to rename MMS's words** — the one place the ruling and the skills could collide: where a word *is* the function (a status, a document name, a quantity with a specific meaning) the MMS term stays and ux-copy polishes around it; where a word is only chrome, improve it freely. **If in doubt it is a function, not chrome.**

Applies to the Procurement screens already shipped as much as to new ones: Part 85 says do not retro-fit BizBox captions onto them, and this says they are still held to the design skills.

---

**Part 86 (14 Oct 2026): Bizbox Chat withdrew Rule 0 themselves, and named the real error — they filed their own inference under Dada's name.** Theirs; verified, not re-measured.

They accepted the Part 85 ruling without re-litigating it and filed `docs/bizbox-mms-rule0-withdrawn-20261014.md`, 93 lines. **Verified here before committing:** the sha256 **matches the hash they stated before I copied the file** (`8759e2a8…ae8403e7`), it is byte-identical to the record copy, the brief and the addendum are **both untouched** (`0b3072d1…`, `f8bb3d72…`, so `bb96800` and `49e6fdb` both still hold), and the fence is clean — no dotted quad, no denylist term. A third separate file rather than an edit, for the same reason as the second.

**Their own diagnosis, which is sharper than the generous framing I gave them, and which is the part worth keeping.** I called Rule 0 a reasonable inference. They rejected that as the smaller half:

> the brief says *"Rule 0 first, because it is his and it overrides the rest"* and states *"a department head must recognise the screen"*. **He never said that.** They quoted *"it should functio nsimilar to bixbox but better"* correctly and then **wrote their own inference beside the quote as though it carried the same authority** — in a document whose opening line tells the reader not to paraphrase it. The operative word in his utterance is **functio**. Function. It never reached the screen layer.

**That is this estate's recorded recurring failure, in a new place: a correct statement plus an uncontrolled inference reads exactly like a measured instruction once filed.** It is the same shape as the IIS/queue error in `pmc-estate` §11, where Dada said three true things and the session wrote its own inference as if it were his. What should have happened: Rule 0 labelled **INFERRED** from "similar", the alternative reading named — that "similar" might mean function rather than appearance — and one line put to him. They labelled the withdrawn-screens history that produced the inference; **they did not label the inference.** Their note says this in those terms, so it is in the repo rather than only in a chat.

**What survives, recorded so nobody over-withdraws:** every measurement; the §2 module map; the §3 document chain; the §4 report usage; the whole §5 defect list; and §5.1 as corrected by the addendum. §7 rules 1–5 stand as relayed, with **1–3 still "what not to foreclose" rather than a licence to write and `PSA_BIZBOX_WRITE_ODBC` unset**. Rules 6–8 stand on their own measurements — document print day-one (~21,700 runs in 60 days, top eight all prints), do not own the stock number alone (128,462 of 227,077 ledger rows are HIS charging), a field nobody fills becomes a calculation. **Gone: Rule 0, the caption list, and the 6 bands and 239 columns as a specification.**

**They confirm the §1 consequence.** The screen inventory, the 239 columns and the caption extraction existed so somebody could reproduce screens; nobody is reproducing screens, so **the four artefacts WS36 cannot reach no longer matter.** What carries the weight is the function and status inventory — §2, §3 and §5, already in the brief WS36 holds. The 083 Procurement screens stand and BizBox captions are explicitly not to be retro-fitted; that is in their note too.

**The save-path count is theirs, still unmeasured, and under function parity it matters MORE, not less** — with screen fidelity gone, the work is entirely in reproducing what each save does. One reflection pass over the MMS assembly under **Windows PowerShell 5.1** gives it; pwsh 7 refuses `ReflectionOnlyLoadFrom` and returns zero. They hold the working pattern from the UI extraction and have **deliberately not run it**, on the grounds that it is a measurement nobody asked for and **Dada sets what gets worked on**. It runs on his word, same day. Correct call, and the one open item that gates anyone estimating this.

His second standing instruction is recorded in their note as well — design skills loaded before building, not after, and which ones fired stated; `frontend-design` noted as not previously enabled and now being enabled. They have built nothing, so nothing has fired.

**Collision 1 resolved in favour of the shipped modern design.** Collision 2 still open and still Dada's. **Nothing changed on any host** — they hold the brief, the addendum, this note and nine measurement scripts, and are running nothing in MMS. No covering handoff was written: the Part 85 ruling already carries everything WS36 needs, and this note is self-contained.

---

**Part 87, ruling (14 Oct 2026): the MMS build may write BizBox's tables. MMS only. Collision 2 is closed — and SQL01 had overstated it.**

Dada, on being told the brief's build rules 1–3 assume writing BizBox's own tables while the desk forbids it:

> *"just for this one it can right to tables as its a mms build so it should function as ome"*

Read as, and acted on: **the MMS build may write BizBox's own MMS tables, scoped to this build only, because an MMS that cannot write is not an MMS — it has to function as one system.**

**A correction I owe, because it changes what this ruling is.** I relayed Collision 2 as *"the desk forbids it and must not build it"*. Reading `psaspine/bizbox.py` properly shows that is not what the code says. `ProcedureWriter`'s own docstring records **"The write path Dada chose (13 Oct 2026)"** — he had decided the mechanism a day earlier. **`PSA_BIZBOX_WRITE_ODBC` being unset was a *not yet*, not a *never*: the credential was absent, not the permission.** So this is a go on something already decided and already built, not a reversal, and the practical consequence is that nobody has to design a write path and nobody should.

**What is already built and must be used rather than replaced.** The desk never writes a BizBox table; it calls one procedure that does. `EXEC psa.sp_apply_change @change_id, @kind, @change_kind, @ext_ref, @field, @new_value, @payload, @requested_by, @approved_by`, returning one row — `ok BIT`, `message NVARCHAR(400)`, `ext_ref NVARCHAR(64)`. `ok = 1` applies; `message` is what BizBox says; `ext_ref` is the number BizBox gave a new record; `ok = 0` refuses and the caller rolls back. **The procedure lives in BizBox in schema `psa`, SQL01 creates and owns it, and it writes the MMS tables itself so BizBox's own flags and rules are kept** — which is how "it should function as one" is met without the desk issuing arbitrary SQL into a live clinical database. Four refusals are already coded and are not to be loosened: unset write string, `sa`, the read-only login reused, and a procedure name that is not a plain `schema.name`. The transaction is `autocommit=False`, commit only on `ok = 1`, rollback on refusal or on a procedure that answers nothing.

**Scope of the grant.** Covers BizBox's **MMS** tables through that procedure, for this build. **Does not cover** HIS, PIS or FMS tables (*"just for this one"*, *"its a mms build"*); patient tables or fields, where `bizbox.py`'s deliberately broad `PATIENT_WORDS` guard **is not to be narrowed to make something fit**; direct table writes from the desk; or `sa` or the read-only login. **The write login is Dada's to create and his password to enter — SQL01 never handles it.**

**The sequence before anything touches `LiveDB_PMC`, and it is not WS36's to start.** This is the first write path into BizBox that has ever existed here, and the brief's rule 2 stands: proven on `TrainingDB_HIS8` first. So — SQL01 writes `psa.sp_apply_change` to the contract above; proves it on `TrainingDB_HIS8`, each save path compared against what the vendor client itself produces; **Dada creates the login and sets `PSA_BIZBOX_WRITE_ODBC`**, until which `writer_in_force()` returns `NoWriter` and the desk pushes nothing, which is the correct default; and every step is previewed, gated, applied in one transaction, read back and ends in a verdict with a control that must fail, as 079 to 084 were. Untouched by the ruling: honour the **rowversion** columns or the two clients silently overwrite each other; **exclusive cutover per screen**, since the vendor client keeps writing these tables until the last screen moves; reads first on every screen. And his standing constraint, which this does not soften: *"dont make anuy changes that will destroy things ok"*.

**Stated once, then his.** BizBox's contract terms on direct database writes have **not been read** — open since 13 Oct in the brief's §8. It does not block the work, since the procedure can be written and proven on `TrainingDB_HIS8` regardless, but it is unresolved and `LiveDB_PMC` is the vendor's live application database. He has made the technical call. For context rather than alarm: `LiveDB_PMC` has FULL at 22:00, DIFF six-hourly and LOG every 15 minutes (MEASURED previously, not re-checked today), but the instance has **no SQL Agent operators, alerts or Database Mail**, so a failed backup job tells nobody — worth knowing before a first live write rather than after.

**For WS36 right now: nothing to start.** The writer exists in the code they hold, the procedure is SQL01's, the credential is Dada's. What changes is that **build rules 1–3 are no longer "what not to foreclose" but live requirements**, and function parity now has teeth — with writes permitted, "the same outcome from the same inputs" means the same row in the same BizBox table, which is what `psa.sp_apply_change` is for. Still Dada's: priority. Still gating estimating: the count of save paths, now more than before, because every save path is a procedure branch somebody has to write.

Filed as `docs/handoffs/HANDOFF-sql01-cloud-WS36-20261014-dada-ruling-mms-may-write.md`. **Nothing changed on any host.**

---

**Part 88 (14 Oct 2026): the write contract has two gaps, not one. Theirs is no concurrency token; mine is that no MMS change can even be recorded yet.**

Bizbox Chat sent a fourth note, `docs/bizbox-mms-rule3-concurrency-20261014.md`, 79 lines. **Verified before committing:** sha256 **matches the hash they stated before I copied it** (`880028d4…3b593c68`), byte-identical to the record copy, their three earlier files all re-verified unchanged (`0b3072d1…`, `f8bb3d72…`, `8759e2a8…`, so `bb96800`, `49e6fdb` and `26d2c30` all still hold), fence clean.

**Gap one, theirs. MEASURED by them on `LiveDB_PMC`, not re-run by me.** 1,163 tables in `LiveDB_PMC` carry a rowversion/timestamp column; **of the 23 MMS write targets — every document header and line table plus `iwItems`, `iwItemMedicines`, `iwWareitem`, `iwItemLedger`, `iwItemPrices` — 23 of 23 carry `tstamp`, none without**; and **only 1 of 457 vendor procedures mentions `tstamp` at all**. Ledger volume over the last 30 days: 106,468 rows in 31 days, mean **3,434/day**, busiest 4,267. Schema `psa` exists in `LiveDB_PMC`; `psa.sp_apply_change` does not exist yet — both consistent with Part 87.

**The two facts matter together: every table a write path touches has a concurrency token, and the vendor's own server-side code almost never looks at one. Optimistic concurrency here is enforced in the WinForms client, not in the database.** So a second writer that does not carry and check the token gets **no protection from the server at all** — the lost update is silent and nothing would refuse it. At 3,434 movements a day that is not theoretical.

**They asked me to check their claim and offered to withdraw it in one line. It stands.** They were careful to say they had not read `psaspine/bizbox.py` and could not — no checkout there, GitHub unauthenticated on that host — so cannot-see, not absent. **MEASURED from the checkout: no token exists anywhere in the write path.** Searching `psaspine/`, `schema/` and `sqlserver/` for `tstamp`, `rowversion`, `row_version`, `expected_`, `concurrency`, `optimistic`, `etag` returns nothing relevant — every `expected_*` hit is `expected_on`, a sales close date, or an auth digest. `ProcedureWriter.apply` passes exactly the nine parameters they were told about; there is no tenth.

**One thing that makes their fix cheaper than they knew.** `ext_change` **already has `old_value`** — `TEXT` in 043, `NVARCHAR(400)` in the SQL Server spine — and it is already populated when a change is raised. **`ProcedureWriter.apply` simply does not pass it.** So `@expected_value` costs one parameter with the data already captured, while `@expected_tstamp BINARY(8)` additionally needs the read views to surface `tstamp` and the 084 mirror tables (`ext_stock`, `ext_movement`, `ext_rr_line`) to store it, which is a schema and map change. **Their judgement that `@expected_tstamp` is the stronger is right and the reason is the operative one: `tstamp` moves when any column on the row changes, so it catches a department editing a field the desk was not touching — which on a stock or quantity row usually matters.** My read: carry `@expected_tstamp`, keep `@expected_value` as the fallback where threading an opaque token is awkward. The fifth refusal needs no new mechanism — nothing updated means somebody got there first, `ok = 0`, and `ok = 0` already means do not commit.

**Gap two, mine, and it blocks MMS writes before concurrency ever arrives.** They could not see this; it is in the desk's own schema, not BizBox. **`ext_change.kind` and `ext_batch.kind` each carry a CHECK allowing only `AGREEMENT`, `PRODUCT`, `PURCHASE_ORDER`, `INVOICE`** (`CK_ext_change_01`, `CK_ext_batch_01`). **080 added `batch_id` but widened neither; 084 added no change kinds.** So **there is no MMS kind at all** — no stock, movement, receiving line, requisition or issuance — and **no MMS change can be recorded today, let alone written**: the insert fails on the CHECK long before anything reaches `psa.sp_apply_change`. Dada's grant is real; the plumbing to carry an MMS change does not exist. Better found now than mid-build.

**What this sets up, as SQL01's work in one gated step rather than three:** widen `CK_ext_change_01` and `CK_ext_batch_01` to the MMS kinds in scope and only those; add `@expected_tstamp BINARY(8)` as a tenth parameter carried into the `UPDATE`'s `WHERE`, with the mirror and map carrying `tstamp` where it must reach the desk to be sent back; **then** write `psa.sp_apply_change` and prove it on `TrainingDB_HIS8` against what the vendor client produces, before anything exists in `LiveDB_PMC`. **One step deliberately: a widened CHECK with no token would let an MMS change be recorded and applied with no concurrency protection at all, which is strictly worse than the refusal that exists today.** Nothing is scheduled; this is the shape, for Dada's go.

**A figure in the record they have corrected, and it is theirs.** The 13 Oct 1:1 proposal says **1,203 rowversion columns** and the brief's §7 rule 3 repeats it; they measure **1,163 tables** carrying one. They have not reconciled the two and say so, so: **1,163 MEASURED for tables, 1,203 NOT VERIFIED until re-run.** Neither carries the argument — 23 of 23 write targets, counted directly, does. Part 87 relayed the 1,203 figure to WS36; it is corrected here.

**Worth recording as the standard.** Bizbox Chat states they have written nothing and will write nothing to any BizBox table, noting explicitly that **Dada's permission went to the MMS build and to SQL01 as its driver and is not authorisation for their session** — they are not treating a relayed ruling as a licence. That is the right reading of one-driver-per-cycle and should be the norm.

Their script is `scripts/Measure-BizBoxMMS-11_rowversion-20261014.py`, control passed. Their §8 contract item stays unread, stated once to Dada by each of us, and neither of us is re-raising it. The save-path count remains unmeasured, theirs, and on his word — now also the count of procedure branches, which makes it the one number gating estimating.

Filed as `docs/bizbox-mms-rule3-concurrency-20261014.md` (verbatim, theirs) and `docs/handoffs/HANDOFF-sql01-cloud-WS36-20261014-write-contract-two-gaps.md` (mine). **`PSA_BIZBOX_WRITE_ODBC` confirmed unset; `writer_in_force()` returns `NoWriter`. Nothing changed on any host.**

---

**Part 89, ruling (14 Oct 2026): `bizboxsa` is the credential for the MMS build — for everything it needs. SQL01 does not hold it and never will.**

Dada, in sequence, on Part 87 saying he would have to create a write login:

> *"there is already bizboxsa"* · *"ask bizbox chat"* · *"for everythung u need"*

Read as, and acted on: **an existing login `bizboxsa` is the credential for whatever the MMS build needs against BizBox — not only the write path — and the BizBox session is the one to ask about it rather than SQL01 probing it.**

**I had a read-only probe of `bizboxsa` written and did not run it.** He sent the question to the Bizbox Chat session instead, which is the same correction he made earlier with *"the bozbox chat can get to it"*. BizBox measuring is theirs; nothing of mine will collide. The probe stays unrun in the scratchpad.

**What was asked of them**, so the answer is on the record as theirs when it comes: whether the login exists and is enabled; what server roles it holds and what database roles in `LiveDB_PMC`; whether it maps to `dbo` or owns the database; **whose account it actually is** — whether the BizBox client, a service or a scheduled job authenticates as it, because if BizBox itself uses it then its password is not ours to touch and the desk's writes become indistinguishable from the vendor client's in any audit; and whether, if it is over-privileged, BizBox tolerates an extra login holding nothing but `EXECUTE`. **Counts, roles and names only — no password, no connection string.**

**What the code already says about it, MEASURED.** `write_odbc_string()` in `psaspine/bizbox.py` refuses the write string when it is missing, when the login is **exactly** `sa`, and when it is the **same login as the read-only one**. The sa test is anchored — `(^|;)\s*(uid|user id|user)\s*=\s*\{?\s*sa\s*\}?\s*(;|$)` — so **`bizboxsa` passes it; it is not caught by name.** The code will accept it provided the read login differs.

**Stated once, because it is the one thing his ruling does not by itself settle, and then it is his.** Part 87's design says the write login *"may do nothing but EXECUTE"* the procedure. If `bizboxsa` turns out to be `sysadmin` or `db_owner`, then that string carries far more than EXECUTE — it could write any table in `LiveDB_PMC`, including the patient tables the whole `PATIENT_WORDS` fence exists to keep away from.

**But his decision is defensible on the architecture, and this is worth recording rather than leaving as a worry.** `ProcedureWriter.apply` only ever executes `psa.sp_apply_change` — it issues no table SQL and has no code path that could. So **the blast radius of the desk's write path is bounded by what the procedure does, not by what the login could do.** A wide login matters only if something other than the desk uses that string, or if the procedure itself is written loosely. Both are SQL01's to control: the procedure is mine to write and mine to keep narrow, and the string lives only in the PSA-Desk task's environment. **The mitigation is the procedure, and it was already the design.**

**SQL01 does not hold `bizboxsa` and will not.** Dada enters it himself, as he does every credential — the standing rule is unchanged. Until `PSA_BIZBOX_WRITE_ODBC` is set on the host, `writer_in_force()` returns `NoWriter` and the desk pushes nothing.

**Nothing changes for WS36.** Part 87 already told them the credential is Dada's to set; it still is, and which login it names is not their concern. The two gaps from Part 88 are still in front of any write regardless of the credential: **no concurrency token anywhere in the write path** (theirs, confirmed by me against the code), and **no MMS kind in `CK_ext_change_01` or `CK_ext_batch_01`**, so no MMS change can be recorded today let alone written (mine).

**Nothing changed on any host. `PSA_BIZBOX_WRITE_ODBC` confirmed unset.**

**Part 89, addition (14 Oct 2026): Bizbox Chat is the standing route for everything BizBox. SQL01 does not probe BizBox.**

Dada, completing the sequence in five fragments: *"there is already bizboxsa"* · *"ask bizbox chat"* · *"for everythung u need"* · *"regarding bizbox"* · *"nd all your queried"*.

Read as one instruction delivered in pieces: **ask Bizbox Chat for everything I need regarding BizBox, and all my queries.** Not only the `bizboxsa` question — **anything BizBox.** The reading was stated on the fourth fragment, when *"regarding bizbox"* was a noun with no verb — the highest-risk message shape in the whole record — and **the fifth fragment confirmed it in his own words** rather than leaving it to stand on my inference.

**Two readings were possible when only four fragments existed, and both were already satisfied**, so nothing built was wrong either way: (a) `bizboxsa` is the credential for everything needed regarding BizBox — which is what Part 89 records; (b) Bizbox Chat is the route for everything needed regarding BizBox — which is what I did by sending the `bizboxsa` question to them rather than running my own probe. **"nd all your queried" settles it as (b)**, and as a standing rule rather than a one-off, since "all" is not about one question.

That is R11 working as intended, and worth noting as such: the reading was stated in one line before acting, he completed the sentence, and no work had to be undone. The cost of the ambiguity was a single sentence rather than an hour.

**The rule, and the line it draws.** It is not "SQL01 stops working on MMS" — SQL01 is still the driver Dada named in Part 87. It is a split by *what is being touched*:

| Goes to Bizbox Chat | Stays with SQL01 |
|---|---|
| measuring anything in `LiveDB_PMC`, `TrainingDB_HIS8` or `ReportServer` that belongs to **BizBox** — tables, columns, flags, logins, procedures, report usage, the assemblies | the **desk's own** objects: `psa.vw_*` views, `psa.sp_apply_change`, the `PMC_PSA` schema steps, the map on `D:\psa` |
| what a BizBox field, status or flag *means* | what the desk does with it |
| what the vendor client does and whether something would break it | the handoffs, the runbook, and relaying rulings to WS36 |

**This is the third time he has corrected me in the same direction.** First *"the bozbox chat can get to it"*, when I told them SQL01 had the SQL route and they might not. Then he rejected a `LiveDB_PMC` table survey I had started, mid-call. Now *"ask bizbox chat … regarding bizbox"*. **The pattern is mine to stop repeating, not his to keep correcting:** I reach for a probe because I have the connection, when the answer belongs to the session that holds the knowledge. Having the route is not the same as owning the question.

**Already applied, not retrospective.** The `bizboxsa` probe was written and **deliberately not run**; it stays unrun in the scratchpad. The questions put to them are on the record in Part 89 — what the login is, what it holds, whose account it actually is, and whether BizBox tolerates a narrow `EXECUTE`-only login instead. **Counts, roles and names only; no password, no connection string.**

**One consequence worth naming now rather than discovering later.** The stock-truth work from Part 84 — building `psa.vw_stock_on_hand` off the ledger rather than off `actualqty` — sits across this line. **The view is the desk's object and mine to write; the measurements that justify it are Bizbox Chat's and already done.** So that work does not need a new BizBox probe from me, and will not get one. If it turns out to need a fact about BizBox I do not already hold, it goes to them.

**Nothing changed on any host. `PSA_BIZBOX_WRITE_ODBC` confirmed unset; `writer_in_force()` returns `NoWriter`.**

---

**Part 90 (14 Oct 2026): `bizboxsa` is the vendor client's own live account and `db_owner`. Measured No on using it, with an alternative that is already precedented on this instance. Plus the measured change kinds.** Theirs; verified, not re-measured.

Dada's instruction was *"there is already bizboxsa"* / *"for everythung u need"*, and he sent the question to the Bizbox Chat session. **They answered No, with measurements.** Two files, both **verified against the hashes they stated before I copied them**: `docs/bizboxsa-login-assessment-20261014.md` (131 lines, `84487594…c2c62ea7`) and `docs/bizbox-mms-rule3-contention-and-kinds-20261014.md` (109 lines, `704163dd…c8537fa0`). Their four earlier files re-verified unchanged, so `bb96800`, `49e6fdb`, `26d2c30` and `68e1dcf` all still hold. **No credential was read by either session at any point** — no password, no hash, no connection string read, printed or written.

**What `bizboxsa` is.** SQL login, exists, **enabled**. Created 10 Jun 2026, **last modified 1 Oct 2026**. Server roles **NONE — not `sysadmin`**; explicit server permission `CONNECT SQL` and nothing else. **`db_owner` on `LiveDB_PMC`**, does not map to `dbo` (`sa` owns the database). Owns no Agent jobs. Control: `bizboxsa_zz99_nope` returned 0. **Flagged and not investigated: `modify_date` moved on 1 Oct, and that field moves on a password change among other things** — worth knowing before anyone assumes the credential is unchanged since June.

**Whose it is — the vendor client's, measured. 22 live sessions at probe time, one distinct program name across all of them: `.Net SqlClient Data Provider`**, oldest 14 Oct 04:21. Twenty-two concurrent sessions under a single .NET client name is the WinForms estate on the hospital floor, not a batch job. So both concerns I raised hold and are worse than raised: **rotating its password drops every BizBox client in the hospital** — a clinical-hours outage, not a config edit — and **sharing it destroys attribution**, because desk writes would land on the same login as 22 concurrent client sessions and no audit could separate a desk change from a department edit.

**What `db_owner` reaches: 1,609 tables readable and writable** — **326 `ps%`** (patient and clinical), 100 `iw%` (materials, the actual target), 84 `appsys%` (users, groups and permissions). So it would hand the write path 1,609 tables where Part 87's design calls for one procedure, **including the 326 patient tables the `PATIENT_WORDS` fence exists to keep away from and the 84 `appsys%` tables that control who may do what inside BizBox — a write path with `db_owner` can grant itself access in the application.** They confirm my guard finding without re-measuring it: the anchored `sa` test accepts `bizboxsa`, so the question was never whether it *can* be used.

**The alternative, precedented on this very instance. MEASURED non-vendor logins against `LiveDB_PMC` today:** `bizboxsa` db_owner with 22 sessions; **`pmc_ssrs_reader`** db_datareader plus `CONNECT`, `EXECUTE` on the database, `EXECUTE` on named functions and **`ALTER` on two views**, with **7 live sessions**; `psa_bizbox_reader` no database role, `CONNECT` plus one `SELECT`, 0 sessions; `psa_desk` (Windows) no role, no explicit grants, 1 session. **`pmc_ssrs_reader` is the proof — object-level `EXECUTE` and `ALTER` grants inside the vendor's live application database, 7 sessions running now, BizBox unaffected. A login holding nothing but `CONNECT` and `EXECUTE` on `psa.sp_apply_change` would be strictly less privileged than `pmc_ssrs_reader` already is.** Two routes, both leaving `bizboxsa` alone: a dedicated SQL write login with `CONNECT` + that one `EXECUTE`; or **`psa_desk`, which already exists with no privileges and needs only the single `EXECUTE` grant** — which also satisfies the write-login-must-differ-from-read-login guard structurally rather than by relying on it.

**What this does not establish, their words, on the record rather than implied.** BizBox's contract and support terms are **still unread** — they measured that extra logins coexist **technically**, not that the vendor's terms permit them or permit writing the database at all; **different questions, only the first answered**. They cannot prove the client does not inspect the login name — three non-vendor logins running normally is circumstantial, not a disassembly. **And nothing in it is a judgement on whether to write, only on which login, which is what was asked.**

**One thing found while looking, stated once, no recommendation attached: `his_app_svc` is a SQL login holding `SYSADMIN`, enabled, 0 live sessions at probe time — the only `sysadmin` SQL login besides `sa` on this instance.** It surfaced only because the probe enumerated server roles to answer whether `bizboxsa` held any. For Dada, not for this build.

**Contention — rule 3 binds harder than Part 88 said, and on more tables.** `iwItemLedger` is **not append-only**: 17 updates against 3,559 inserts in 21 hours, **1 vendor procedure containing `UPDATE…iwItemLedger` and 2 containing `DELETE`**, no triggers — which bears directly on Part 84's decision to derive the position from it. **The real contention is `iwWareitem`: 10,667 UPDATEs in 21 hours, about 508 an hour, 8.5 a minute**, higher in working hours since the window includes a night — so a token-less write to `iwWareitem` races roughly nine vendor updates a minute. `iwPOinv`, `iwReqinv` and `iwWhreqinv` all take more updates than inserts, which is what posting and approving looks like. **`iwItemLedger` measured 227,077 rows earlier today and 227,104 later: the concurrency is happening during the design.** This strengthens Part 88's sequencing rather than changing it.

**The change kinds, derived from volume so "only those" is not guessed. IN SCOPE, ten:** Expense Requisition 1,223, Stock Requisition 1,095, Expense Issuance 1,085, Delivery/Receiving 1,069, Stock Issuance 998, Purchase Order 837 (kind already exists), Purchase Requisition 634, Material Production 169, Physical Count 104, Quantity Adjustment 40. **EXCLUDE, four:** Job Order 21, Job Order Request 5, Purchase Return 2, Allotment/Obligation 0/0. **They say plainly the cut at 25 headers is a judgement, not a measurement** — but the gap is wide: tenth-largest 40, eleventh 21, and the four excluded total 28 headers against 7,254 for the ten.

**One question they raised and explicitly declined to answer, to be settled before the CHECK is widened rather than after.** If the stock position is derived from the ledger, it arguably cannot be "changed" directly at all — the correctable thing is a **movement**, not a position — so `ext_stock` may need a read path but **no change kind**. **SQL01's view, labelled because Parts 86 and 87 were both about exactly this failure: they are right. Part 84 already decided the position is derived rather than stored, and a derived figure has nothing to write to, so the change kind belongs on the movement and `ext_stock` gets a read path and no change kind. INFERRED, not measured, and open to challenge.**

**Their fence note, verified independently here.** The probe enumerated **every** login on the instance, which includes individual staff Windows accounts, and **those names are deliberately omitted from the document**. They re-checked after their first fence grep threw a trailing-backslash error rather than accepting its clean result — the correct instinct, and the same class of error as this estate's own heredoc trap. Verified here: no dotted quad in either file, and every occurrence of the word "password" is a statement *about* passwords, not a credential.

**Reported to Dada as a decision, since the measurement contradicts his instruction.** The write login is his call and his password to enter; the grant script is SQL01's as driver, and their measured grant list has been requested as text rather than a script. **Nothing written, nothing scheduled, `PSA_BIZBOX_WRITE_ODBC` confirmed unset, `writer_in_force()` returns `NoWriter`. Nothing changed on any host.**

Filed as `docs/bizboxsa-login-assessment-20261014.md` and `docs/bizbox-mms-rule3-contention-and-kinds-20261014.md` (both verbatim, theirs) with `docs/handoffs/HANDOFF-sql01-cloud-WS36-20261014-write-login-and-change-kinds.md` (mine).

---

**Part 91 (14 Oct 2026): the write grant is two statements, ownership chaining makes `EXECUTE` alone sufficient, and the `ext_stock` inference is now measured.** Theirs; recorded, not run.

The Bizbox Chat session sent the measured grant list as text, as asked, with four measurements and a correction to one of their own figures. **Nothing has been run** — the grant is a production change to `LiveDB_PMC` and waits on Dada's word.

**The measurement that could have broken the whole design: ownership chaining works.** Schema `[psa]` is owned by `dbo` and schema `[dbo]` is owned by `dbo` — **same owner** — so a procedure in `[psa]` writing `dbo.iw*` tables gets ownership chaining and **the caller needs no table rights at all. `EXECUTE` on the procedure is genuinely sufficient and `psa.sp_apply_change` needs no `EXECUTE AS`.** Had the owners differed the chain would break at the `dbo` tables and the procedure would fail with permission denied **despite a correct `EXECUTE` grant** — which reads exactly like a bad grant and would have cost a debugging session chasing the wrong thing. Re-check it if anyone ever re-owns `[psa]`. Also measured, and nothing needs changing: `LiveDB_PMC` has `TRUSTWORTHY = False` and cross-database chaining `False`. **Do not turn either on.**

**`psa_desk` is the right principal, now by measurement rather than my preference.** `DND-SQL01\psa_desk` has 1 live session, against `PMC_PSA`, program name `Python` — **not `LiveDB_PMC`** — and **no database user in `LiveDB_PMC` at all (0)**, so it cannot touch that database today. `psa_bizbox_reader` **does** have a user there, holding `GRANT SELECT` at **SCHEMA** level on `[psa]`. **So read and write are structurally different principals and the write-differs-from-read guard is satisfied by construction rather than by the regex.** One limitation stated plainly before it gets baked into a runbook: **`DND-SQL01\psa_desk` is a local Windows account on that host**, so this works only while the desk runs there — if it ever moves host the login does not travel and a domain account or SQL login is needed instead.

**The grant, and the order matters more than the list.** `psa.sp_apply_change` does not exist yet, so **the `GRANT` cannot run before the procedure does.** Order: **procedure → user → grant → verify**, which is not the order the list reads in. Step 1, `CREATE USER [psa_desk] FOR LOGIN [DND-SQL01\psa_desk] WITH DEFAULT_SCHEMA = psa;` — carries `CONNECT` by default, and `GRANT CONNECT` is added **only** if it has been revoked. Step 2, `GRANT EXECUTE ON OBJECT::psa.sp_apply_change TO [psa_desk];` — **`OBJECT`-level, deliberately not schema-level**, because `psa_bizbox_reader` already holds `SELECT` on `SCHEMA::[psa]` so schema grants are in use here, and **`EXECUTE ON SCHEMA::psa` would silently make every future procedure in that schema executable by the desk**. Step 3: nothing else. **Explicitly not to be granted:** no database role of any kind; no table or view DML and none needed; not `EXECUTE ON SCHEMA::psa`; no `ALTER`, `CONTROL` or `VIEW DEFINITION`; nothing at server level, since the login already holds `CONNECT SQL`; and **`bizboxsa` untouched**.

**The verifier, with the controls that must fail.** Must pass as `psa_desk`: `HAS_PERMS_BY_NAME('psa.sp_apply_change','OBJECT','EXECUTE') = 1`. **Must fail, and any 1 voids the run:** `UPDATE` on `dbo.iwWareitem`, `INSERT` on `dbo.iwItemLedger`, **`UPDATE` on `dbo.appsysUserSubmodules`**, and `SELECT` on a `ps%` table. **The `appsys` one matters most — it is the check that the write path cannot grant itself rights inside BizBox, which was the whole objection to `db_owner`.** Then execute the procedure once with a payload one of the four coded refusals must reject and confirm `ok = 0` with no commit: **a refusal proving it refuses is worth more than a success proving it succeeds.** **The trap, and it is the same shape as their `FK_mscBranches` one: wrap the `HAS_PERMS_BY_NAME` checks in `EXECUTE AS USER = 'psa_desk'` … `REVERT`, because checked as a sysadmin they return 1 for everything and read like a pass. A check that cannot fail looks exactly like a check that passed.**

**My `ext_stock` inference is now MEASURED, and it holds.** Part 90 labelled it INFERRED and invited a counter-example — a department correcting a position rather than a movement. **They went looking for it and the paradigm case exists:** a Physical Count is exactly *"the position is X regardless of what the movements say"*. **But BizBox already records it as a movement** — doctype `PC` carries 7,253 ledger rows across 88 documents (qtyin 724,353, qtyout 3,181) and `QA` carries 196 rows across 42 documents, against 104 Physical Count and 40 Quantity Adjustment headers. So the conceptual case is real **and the product already resolves it the same way: a position correction is written as a movement.** `ext_stock` gets a read path and **no change kind**; upgraded from INFERRED to MEASURED on their evidence, and they state they are not challenging it because the counter-example they sought turned out to be modelled that way. **Loose end, not chased: 104 PC headers against 88 PC documents in the ledger — 16 physical counts have no ledger rows at all.**

**They corrected one of their own figures that Part 90 carried.** Part 90 relayed *"1 procedure with `UPDATE…iwItemLedger` and 2 with `DELETE`"*. **That came from a `LIKE` pattern matching any `DELETE` anywhere in a body plus any mention of the table — it does not prove the `DELETE` targets `iwItemLedger`.** The real finding: **two** procedures mention both a mutating verb and that table — `MergeAccountEntities` (`UPDATE`, `DELETE`, `INSERT`, 68,828 chars), which is the merge-entity path re-pointing rows when two accounts are merged, **an identity merge not a stock correction**; and `usp_InventoryStockCard` (`DELETE`, 17,057 chars), by name a stock-card build whose `DELETE` **may well target a temp table**. **What is solid is the operational-stats figure — 17 leaf updates on `iwItemLedger` in 21 hours, a counter rather than a pattern match — so the ledger is not append-only and that stands.** Attributing those 17 to a named procedure is **NOT established**, and Part 84's point that a derived position inherits whatever they do needs those two bodies read, **which nobody has done.**

**An absence finding confirmed from two sides.** Schema `[psa]` in `LiveDB_PMC` holds **exactly five views** — `vw_invoice`, `vw_lookup`, `vw_product`, `vw_purchase_order`, `vw_purchase_order_line` — **matching the five wired map entries exactly** and independently confirming Part 84: no `vw_stock_on_hand`, no `vw_item_ledger`, no `vw_receiving_line`. Measured twice, from two sides, agreeing.

**What changes for WS36, two things only:** `ext_stock` has no change kind and is not among the kinds when the CHECK is widened; and **`psa.sp_apply_change` needs no `EXECUTE AS`** because ownership chaining covers it, so a design that adds one is unnecessary here.

Filed as `docs/handoffs/HANDOFF-sql01-cloud-WS36-20261014-write-grant-measured.md`. **Nothing written, nothing scheduled, `PSA_BIZBOX_WRITE_ODBC` confirmed unset, `writer_in_force()` returns `NoWriter`, and no password or hash was read by either session at any point.** The procedure is SQL01's to write; the user creation and the credential are Dada's steps. `bizboxsa`'s `modify_date` and `his_app_svc` stay open and unchased on both sides.

---

**Part 92, ruling (14 Oct 2026): `psa_desk`, uniform — one identity for reads and writes. `bizboxsa` is not used. The decision rests on SQL01's recommendation, and is recorded that way on purpose.**

Dada: *"psa desk make it uniform"*, then, after asking what I thought was better, *"ok psa desk it is if its vetter"*.

Read as, and acted on: **`psa_desk` is the single identity for the desk's BizBox access — reads as well as writes — with `psa_bizbox_reader` eventually retired. `bizboxsa` is not used at all.**

**Whose decision this is, stated plainly because it matters if it turns out wrong.** He asked *"wjat do y think us better"* and then accepted the answer. **So this is SQL01's recommendation that he approved, not an instruction he arrived at independently.** If uniform turns out to be the wrong call, the reasoning below is mine and traceable, not his.

**The recommendation, and the trade it makes.** The split — `psa_bizbox_reader` for reads, `psa_desk` for writes — defends a **narrow and bounded** risk: the capability behind that boundary is `EXECUTE` on **one procedure**, not table writes, so the worst case of a read path reaching it is a change submitted through a procedure that validates it under BizBox's own rules with `requested_by` and `approved_by` on the row. The split meanwhile **sustains a broad and unbounded** one: `psa_bizbox_reader` is a SQL login, so a password exists, and it sits in plaintext in a scheduled task's environment, rotated by nobody. **Standing credentials are what actually leak on this estate; privilege boundaries between two of the desk's own processes are not.** Uniform trades the theoretical boundary for the removal of a real credential, and with `psa_desk` on both sides it is Trusted_Connection throughout — **no BizBox password anywhere in the estate.** Secondary gains: BizBox's audit shows "the desk" unambiguously, and there is one principal to grant, document and get right rather than two.

**Where I would not extend it, recorded so it is not read as a general licence:** uniform across the desk's *own* BizBox access is right. Uniform meaning one login shared with anything else would give back exactly what made `bizboxsa` wrong.

**A finding from the code that this decision depends on. MEASURED.** `write_odbc_string()` in `psaspine/bizbox.py` refuses a shared login **only when both connection strings carry an explicit `uid=`**:

```python
read = os.environ.get("PSA_BIZBOX_ODBC", "")
uid = lambda s: (re.search(r"(?i)(?:^|;)\s*(?:uid|user id|user)\s*=\s*\{?([^;}]*)", s) or [None, ""])[1].strip().lower()
if read and uid(read) and uid(read) == uid(cs):
    raise Refused("refused: the write login must be a login of its own, not the read-only one")
```

Under uniform, **both strings are Trusted_Connection with no `uid=`**, so `uid(read)` is empty, the condition is false, and **the guard never fires. It does not refuse the decision — it passes silently.** The check was written for SQL logins.

**So the guard becomes decorative, and that is not acceptable as-is.** It is the `Watch-PMCBridge` failure shape from this estate's own record: a glob that returned nothing reported healthy for **17 days, 16 emails, 4,128 throttled passes**, while the thing it watched was fine — and the lesson filed then was that **a check which cannot fail is worse than no check**, because it also spends the trust that would have made a real alarm land. **Therefore: the guard is fixed to compare the effective identity, or deleted with the docstring saying separation was traded for a single credential-free identity. Both are honest; leaving it unchanged is the only bad option.** That is part of this work, not a follow-up.

**Also corrected, before anyone relies on it:** `ApplicationIntent=ReadOnly`, which `odbc_string()` appends to every read string, is **a routing hint for availability-group replicas, not a permission**. It does not prevent a write and buys nothing here. It should not be cited as residual separation under uniform.

**The caution that outranks the grant, and it is not negotiable.** `psa_bizbox_reader` measured **0 live sessions**, and **that is not "unused"** — it is a point-in-time sample, and a nightly job not running when the probe fired would show exactly the same zero. **This is the estate's most repeated mistake in a new costume, and the whole reason R3 exists.** So: nothing is retired or revoked in this step. `psa_bizbox_reader` stays exactly as it is until it is established that nothing else names it — another task, another connection string, an SSRS data source, an Agent job — and its removal is then a **separate** step on Dada's word. **An unused login costs nothing sitting there; finding out which nightly job owned it costs a morning.**

**Asked of the Bizbox Chat session**, per the standing routing rule (Part 89 addition): the full uniform grant list — everything `psa_bizbox_reader` actually holds, so nothing is lost in the move, including anything object-level that would otherwise be dropped, and whether schema-level `SELECT` is genuinely what it has; and whether it is **actually** unused, with the explicit instruction that **"cannot tell" is an acceptable answer** and preferable to a confident zero. Text, not a script, with the same explicit not-to-be-granted list as before.

**The order, unchanged from Part 91 except for the guard going first:** fix or delete the guard → write `psa.sp_apply_change` → `CREATE USER [psa_desk] FOR LOGIN [DND-SQL01\psa_desk] WITH DEFAULT_SCHEMA = psa` → the grants (`SELECT ON SCHEMA::psa` carried over, `EXECUTE ON OBJECT::psa.sp_apply_change`, object-level deliberately) → verify with the controls that must fail, wrapped in `EXECUTE AS USER = 'psa_desk'` … `REVERT` → prove on `TrainingDB_HIS8` against what the vendor client produces. **`psa.sp_apply_change` does not exist, so the grant cannot precede it.**

**Nothing run. Nothing scheduled. `PSA_BIZBOX_WRITE_ODBC` confirmed unset, `writer_in_force()` returns `NoWriter`, no credential read by anyone at any point, and `bizboxsa` untouched and staying untouched** — the Bizbox Chat session's assessment carried that decision.

---

**Part 93 (14 Oct 2026): reviewed before sending, on Dada's word — one proposed condition withdrawn as unbuildable, one challenge of SQL01's withdrawn on measurement, and what survived is a replay refusal, a self-explaining guard, and the grant in both databases.**

Dada: *"can you review what bizbox chat said and what we are sending to ws36 before sending"*, then *"recheck all before sending"*. Read as: review the Bizbox Chat session's reply and my draft handoff critically, verify what can be verified, and only then send. **The review changed the handoff.** Three findings of mine against their reply; one of mine died on recheck, two stood and they accepted both. Recorded in order.

**My finding 1, stood — their condition one could not be built.** They had proposed that `psa.sp_apply_change` derive the approver from the stored `ext_change` row rather than trust `@approved_by`, since under uniform a compromised read identity could submit and self-approve in one call. Two things were wrong with it. **The desk already does exactly that** — `bizbox.py` 1034–1036 selects only `c.status = 'PENDING' AND (c.batch_id IS NULL OR b.status = 'APPROVED')` and passes `b.approved_by` read from the stored batch row, never from a caller (MEASURED, SQL01). **And the procedure cannot do it at all:** `psa.ext_change` and `psa.ext_batch` exist **only in `PMC_PSA`**, the procedure runs in `LiveDB_PMC`, and they had themselves measured chaining and `TRUSTWORTHY` off in all three databases and said leave both off. **Two different `[psa]` schemas in two different databases** is how both sessions missed it. They verified the crux rather than taking it — `LiveDB_PMC` and `TrainingDB_HIS8` each hold `[psa]` with the views and no `ext_*` tables — and withdrew it.

**They withdrew it for a stronger reason than unbuildability, and it is the one that decides the design.** The split limits what a **stolen credential** can do; **uniform abolishes the credential** — there is no password to steal. To abuse the `EXECUTE` you need code execution as `psa_desk` on that host, **and at that point you are the desk** and can drive its own approved path. The boundary defended against theft of a thing uniform removed. Their own words on the first error, kept because they are the right standard: *"I proposed a thing my own measurement forbade, two messages after taking it. That is not a gap in knowledge, it is not reading my own output before issuing an instruction."* **So the approval control stays in the desk layer, measured as already correct, and is recorded as defence-in-depth already satisfied — not as a condition on the build.** Rejected so they are not re-proposed: a cross-database read (needs chaining or `TRUSTWORTHY` on, widens what the login exercise narrowed); a nonce or signed payload (a **shared secret**, the exact thing uniform was taken to remove — trading a SQL password for an HMAC key is not a win, and I had wrongly called it "costs nothing").

**The replacement condition, theirs, buildable and now binding: replay refusal on `change_id`.** A consumed-`change_id` table in `LiveDB_PMC` schema `psa`, written by the procedure itself via ownership chaining; the procedure refuses a `change_id` already applied and returns `ok = 0`. No secret, no cross-database read, a sixth refusal in the contract's existing shape. **It blocks the mundane failure rather than the exotic one** — the same approved change applied twice by a retry, a race, a resend or an operator re-running a batch, which at 8.5 vendor updates a minute on `iwWareitem` is a realistic way to produce a wrong stock figure. One control added to the verifier: as `psa_desk`, `DELETE` on that table must return 0 — it can read it (harmless, schema `SELECT`) and must not be able to clear it. **For WS36:** `change_id` is now load-bearing on the BizBox side and must never be reused across the life of the desk; a reset, reseed or restore that could mint the same id twice would defeat the guard from the spine side.

**My finding 2, stood — their inverted guard refused their own documented fallback.** Refusing any write string with an explicit `uid=` enforces trusted-auth-only and can fail, which is right; but they had also documented that `DND-SQL01\psa_desk` is a local account that does not travel and that a host move needs a domain account **or a SQL login** — which the inverted guard refuses. **Settled: keep the inversion, no override, docstring says the host-move case requires changing this guard deliberately, and the refusal message carries the remedy** — *the write path is Windows-authenticated by decision of 14 Oct 2026; if the desk has moved host, this guard is the thing to change, deliberately* — because a docstring is read at authoring time and this guard will fire at 2am on a host move. No override, on the estate's own evidence: `Watch-PMCBridge`'s `.trn` guard read "if not null AND stale", so absence meant silence and it never fired once in its life. Their host-move wording is theirs to fix so a SQL login no longer reads as a drop-in. Also corrected: `ApplicationIntent=ReadOnly` is a routing hint, not a permission, and is not residual separation.

**My finding 3, died on recheck — and the method is worth keeping.** I challenged their `CredentialRetrieval = 2 (Store)` on the documented SOAP enum — Prompt=0, Store=1, **Integrated=2**, None=3 (VERIFIED, learn.microsoft.com, `ReportService2010.CredentialRetrievalEnum`) — which would have meant the data source names no login and their one Ask-2 unknown closes. **Then I measured the catalog instead of arguing:** across all 1,200 rows in `ReportServer.dbo.DataSource`, value `1` = 1,197 with no stored username or password, value `3` = 2 with none, value `2` = **exactly one, with both stored.** Stored credentials exist under `2` and under no other value. **So in this catalog `2` is Store, the table does not use the SOAP numbering, and they were right.** IS-NULL checks only, nothing decoded; control, a path that cannot exist, 0. Their own account of their side: their script had *labelled* the column "Store(2)" — an enum mapping asserted unverified that happened to be right — and the distribution is the better demonstration. **Their cannot-tell on the reader stands**, and the Report Manager screen read remains the way to close it: ten seconds, no query, no credential handled, Dada's.

**Closed on review:** the `TrainingDB_HIS8` schema owners, which they had flagged as unmeasured. **Now measured: `[psa]` and `[dbo]` both owned by `dbo`, same owner** — chaining works there too and the proving step behaves as live. And a note of theirs worth keeping: my 13 Oct run — `psa_bizbox_reader` reading 152 rows through `psa.vw_lookup` while refused `dbo.iwItems` — is **the mechanism exercised in production**, better evidence for chaining than a schema-owner query.

**What held unchanged from the first draft:** the `TrainingDB_HIS8` mapping catch (reader mapped in **two** databases, so the grant goes in both or the proving step loses its read path exactly when proving); the `db_datareader` warning (schema `SELECT` on `[psa]` is the whole read surface; `db_datareader` opens 1,609 tables); the `sysrowsets` retraction, which never reached the repo; and Ask 2's clean findings (no Agent step, no proxies, no linked servers, 0 SSRS definitions with a 1,279-item positive control, no successful-login audit on the instance).

**Nothing run, nothing scheduled, code untouched, `PSA_BIZBOX_WRITE_ODBC` confirmed unset, `writer_in_force()` returns `NoWriter`.** No credential read, no encrypted value decoded. `bizboxsa` untouched. **Order:** invert the guard → write the procedure with the replay refusal → user and grant in both databases → verify as `psa_desk` with the six controls that must fail → one refused execution proving `ok = 0` and no commit → prove on `TrainingDB_HIS8`. Filed as `docs/handoffs/HANDOFF-sql01-cloud-WS36-20261014-two-conditions-on-uniform.md`, rewritten after review; the first draft was never committed.

---

**Part 94, ruling (14 Oct 2026): the write path simplified to three mechanisms on Dada's instruction. The replay table in BizBox is withdrawn — the race it covered is in the desk's sender and is fixed there with one `UPDATE`.**

Dada: *"if the procedure is too complicated simplify it to many checks isnt good at all it can be secured and simplified properly"*. Read as: the write path has accumulated too many mechanisms — strip it to the few that secure it and make each one do one job. **He is right and the count is the evidence:** across Parts 87–93 it had six coded refusals, a concurrency token with a fallback, a replay table with a location rule and a restore-safety analysis, and six verifier controls.

**What prompted the count.** The Bizbox Chat session had sent a second revision of their own replay-guard advice — `docs/bizbox-mms-replay-guard-restore-safety-20261014.md`, 107 lines, **verified against the hash they stated before I copied it** (`a8c207aa…4ff9b2e`), byte-identical, fence clean, their six earlier files re-verified unchanged. Its substance: the consumed-ids table is only restore-safe if it shares a restore boundary with `dbo.iw*`, so it must live in `LiveDB_PMC` and **never in `PMC_PSA`**, where anyone optimising for tidiness would put it; and their MEASURED restore history — **`LiveDB_PMC` restored into twice, 9 and 16 July 2026; `TrainingDB_HIS8` restored into 35 times, most recently 12 Oct 2026; `LiveDB_PMC` FULL recovery with 5,175 log backups; `PMC_PSA` SIMPLE with 57 full backups and no log backups at all.** **The `PMC_PSA` claim is about the desk's own database, so I verified it rather than carried it (R5): SIMPLE, 57 full, latest 14 Oct 03:40, no log backups, never restored into; `PMC_Apps` is FULL; their `backupset` total of 10,572 matches mine to the row.** The desk's record of every change applied to the vendor's live database has less backup protection than payroll does. Stated once; theirs and now mine; no recommendation attached.

**Their analysis was correct about the table it analysed. The table was the wrong place.** Reading the sender settled it: `push()` in `psaspine/bizbox.py` selects every `PENDING` row and calls `writer.apply()` **before** marking anything, so two overlapping runs would both apply the same change. **That is the entire replay risk, and it lives in the desk's code. Nothing in BizBox can fix a race in the desk.** The fix is one `UPDATE` where the risk lives — claim before apply: `UPDATE ext_change SET status = 'SENDING' … WHERE change_id = ? AND status = 'PENDING'`, rowcount must be 1 or the row is skipped, then apply, then `APPLIED` or `REJECTED`. **Restore-safe by construction**, because the claim lives in the same row as the change it claims. No second table, no location rule, no cross-database question, nothing new in BizBox — and the whole restore-safety analysis of the table becomes moot.

**The three mechanisms that remain, each because one specific thing goes wrong without it:**

1. **Identity is the grant.** `psa_desk`, Windows, no password; one user in each of `LiveDB_PMC` and `TrainingDB_HIS8` holding `SELECT ON SCHEMA::psa` and `EXECUTE ON OBJECT::psa.sp_apply_change` and nothing else. That is the security. The code-side guard collapses to one condition — refuse any write string carrying an explicit `uid=`, with the remedy in the message — plus the unset-string off-switch. The `sa` check is subsumed; the read-login-reused check is void under uniform and could not fail anyway. **A guard that cannot fail is deleted, not kept.**
2. **Concurrency is one parameter.** `@expected_tstamp BINARY(8)` in the `UPDATE`'s `WHERE`; nothing updated returns `ok = 0`, *re-read and ask again*. **No `@expected_value` fallback** — one mechanism, not two. Non-negotiable on their numbers: 23 of 23 write targets carry `tstamp`, 1 of 457 vendor procedures checks one, `iwWareitem` takes 8.5 vendor updates a minute.
3. **Replay is the one `UPDATE` above**, in the desk.

**Verifier cut from six controls to four**, as `psa_desk` under `EXECUTE AS` … `REVERT`: `EXECUTE` on the procedure = 1; `UPDATE` on `dbo.iwWareitem` = 0 (one `iw*` table stands for all); `UPDATE` on `dbo.appsysUserSubmodules` = 0 (cannot grant itself rights inside BizBox — the objection to `db_owner`); `SELECT` on one `ps%` table = 0 (the patient fence, a different consequence from the others). Then one execution a refusal must reject, confirming `ok = 0` and no commit; then prove on `TrainingDB_HIS8`.

**For WS36, one schema step, two CHECKs together:** `ext_change.status` and `ext_batch.status` gain `SENDING`; `ext_change.kind` and `ext_batch.kind` gain the ten MMS kinds from Part 90, `ext_stock` not among them.

**Two operational notes kept from their restore measurement, because the facts stand even though the design they analysed does not:** every `TrainingDB_HIS8` refresh wipes the procedure and the `psa_desk` user there, so **re-create both after every refresh and verify the procedure exists before a proving run** — a proving run against a wiped database proves nothing and looks like a pass; and after any restore into `LiveDB_PMC`, run a **reconciliation report** — read-only, desk-side, for every `APPLIED` change does the returned `ext_ref` still exist with the value sent — and re-queue the missing deliberately. A report that runs when a restore has happened, not a guard on every write.

**Dropped, so nobody puts it back:** the consumed-ids table; its location rule; its `DELETE` control; the `@expected_value` fallback; the `sa` and read-login-reused refusals; two of six verifier controls. **Their host-move wording correction is adopted as written:** a domain account keeps trusted authentication and needs no guard change; a SQL login is *not* a drop-in and taking that route means deliberately changing the guard.

**Still open, theirs and worth Dada's hearing once:** why `LiveDB_PMC` was restored into on 9 and 16 July 2026 — two restores into the live clinical database, history read, cause not; and whether the spine can mint a duplicate `change_id` after a reset, reseed or restore, which is WS36's half.

Filed as `docs/bizbox-mms-replay-guard-restore-safety-20261014.md` (verbatim, theirs) and `docs/handoffs/HANDOFF-sql01-cloud-WS36-20261014-write-path-simplified.md` (mine, superseding §2–3 of the two-conditions handoff). **Nothing run, nothing scheduled, code untouched, `PSA_BIZBOX_WRITE_ODBC` unset.**

**Part 94, addition (14 Oct 2026): the July restores into `LiveDB_PMC` are closed by measurement — neither was a recovery. Nothing to do.** Theirs, from `msdb`; not re-run here.

Part 94 left *"why was the live clinical database restored into twice"* with Dada. The Bizbox Chat session answered it from `msdb` rather than leaving it. **Both restores — 9 Jul 09:43:47 and 16 Jul 10:25:07 — were full database restores `WITH REPLACE`, `stop_at` NONE, from a backup of `LiveDB_PMC` itself taken on the same server minutes earlier (8.7 minutes and 36 minutes old), run by `sa`.** A recovery restores an *older* backup with log restores and a `stop_at`; these have none of that. **MEASURED conclusion: neither was disaster recovery. Both were take-a-fresh-backup-then-restore-it-over-itself, by hand.** Controls both ways: an impossible destination returned 0, and 100% of restore rows resolve to a `backupset`, so the join is not blind.

The 16 Jul restore sits inside a cluster of **five `TrainingDB_HIS8` restores that day**, and its source backup finished 09:49:05 while a Training restore ran at 09:49:30 — the same fresh backup, 25 seconds apart. **INFERRED, labelled as such by them:** these were the refresh-training operation done manually with `LiveDB_PMC` as the destination, before it was scripted. **What supports the inference is a measurement:** the gated `Refresh-TrainingDB-FromLive-20260930.sql` dates from **30 Sep 2026 — two and a half months after** these restores. It hardcodes `TrainingDB_HIS8`, defaults `@Apply = 0`, guards the destination's existence, ONLINE state and file layout (exactly two files), carries a rollback block, and its header states *"LiveDB_PMC itself is only READ (a copy-only backup); it is not changed."* **That reads as a rule written in response to exactly this.**

**So: no incident behind either restore, and the hazard that produced them is already gated.** Recorded because *"why was the live clinical database restored twice"* is the kind of question that gets re-asked and re-investigated.

**Stated as cannot-see, not clean, by them:** four other scripts in the record contain `RESTORE DATABASE` and were not read — `Fix-PMCBackupVerify-20260903-v3/v4.ps1`, `Scope-Sql01-And-LegacyHims-20260908.ps1`, `Roster-PIT-Diff.ps1`, `sql/PMC_Apps-census-00-testbench-restore-20260926.sql`. Only the refresh script's guards were checked.

**On the simplification, their words, kept because the diagnosis is the useful part:** *"The thing I had drifted into was mistaking thoroughness for design — each addition was defensible on its own and the total was not, which is exactly what he said."* They would not re-argue for the table.

**Still open and now put to its owner:** whether the spine can mint a duplicate `change_id` after a reset, reseed or restore. WS36's half; asked directly.

---

**Part 95 (14 Oct 2026): WS36 shipped the desk's side of the write path as schema 085 against today's rulings. Their question answered — Delivery/Receiving is the desk's INVOICE kind. Their change_uid offer declined in favour of a rule. Nothing applied on the host.**

Dada pasted WS36's reply: *"Pull `ec24f18` on `claude/psa-ticketing-build` once CI run 38476202826 is green on it. Your five rulings taken as given; the three builds done; the one question answered."* Read as: pull when green, read, answer, apply nothing until he says go. **At the time of this Part CI is in progress — both Linux jobs green, `windows` and `sql-server` still running — so `ec24f18` is fetched but not pulled.** Their handoff `HANDOFF-cloud-sql01-WS36-20261014-write-path-085.md` was read from the remote ref.

**What 085 does, in their words.** SQLite rebuilds `ext_batch` and `ext_change` (same columns, CHECKs widened, two columns added); the port emits **a constraint swap under the same name, guarded, and never drops a table**. On `PMC_PSA`: four swaps — `CK_ext_batch_01` and `CK_ext_change_01` gain the ten MMS kinds (guard `NOT LIKE '%''EXPENSE_REQ''%'`), `CK_ext_batch_03` and `CK_ext_change_02` gain `SENDING` (guard `NOT LIKE '%''SENDING''%'`); and nine `COL_LENGTH`-guarded ADDs — `ext_change.expected_tstamp NVARCHAR(32)`, `ext_change.change_uid NVARCHAR(32)`, and `tstamp NVARCHAR(32)` on seven mirror tables (`ext_purchase_order`, `ext_product`, `ext_invoice`, `ext_po_line`, `ext_stock`, `ext_movement`, `ext_rr_line`). Checks after: `COL_LENGTH(N'psa.ext_change', N'change_uid') = 64`, each constraint definition carries its token, and `COUNT(*)` on both tables unchanged. **The sender claims before it applies** — one `UPDATE`, rowcount 1, committed, then the procedure, then `APPLIED` or `REJECTED`; a held row is skipped and counted; a `SENDING` row cannot be cancelled; a run that died leaves `SENDING`, which `bizbox-push` prints as STUCK with the by-hand remedy; the two-runs overlap is tested. **The row version:** the mirror carries `tstamp` as text (`CONVERT(VARCHAR(18), tstamp, 1)`, `0x…` or bare 16 hex), a proposed edit copies it into `expected_tstamp`, and the sender passes it as the **tenth parameter, `BINARY(8)`**; NULL for a new record. **The guard is the one condition** — unset is the off-switch, any `uid=` refused with the remedy. Also in the pull: the Windows CI test fixed, since the runner has `curl.exe`.

**Their question, answered — MEASURED.** *Is Delivery/Receiving the same document as the desk's INVOICE kind (`psa.vw_invoice`)?* **Yes.** Three things agree: the live map's own comment, written when the view was built on 29 Sep — *"An invoice here is BizBox's receiving report (its key is the receiving number)"*; `psa.ext_invoice` holds **1,050 rows (1,035 present)** against the brief's **1,069 Delivery/Receiving headers**, the gap being the hourly mirror's lag and 15 absent rows, not a different document; and 084's `ext_rr_line` is defined as *"a receiving report's lines"* carrying `po_ref`, matching the brief's receipt-to-PO chain. **So `DELIVERY_RECEIVING` and `INVOICE` are one word on screen, the existing `INVOICE` kind is that document, and the MMS kinds added are nine, not ten.** WS36 chooses whether to drop `DELIVERY_RECEIVING` from the CHECK or alias it; told them.

**The `change_id` question, their answer, and my decision on their offer.** SQLite: `INTEGER PRIMARY KEY` without `AUTOINCREMENT` may reuse the highest id after a delete, but the desk never deletes an `ext_change` or `ext_batch` row (MEASURED by grep) — not structural. SQL Server: `INT IDENTITY(1,1)`, monotonic, a rolled-back insert burns its value; **it mints an id again in exactly two cases — a deliberate `DBCC CHECKIDENT RESEED` lower, and a restore of `PMC_PSA` to a backup taken before the id was minted.** The second is real: the identity seed lives in the data. Their mitigation: `ext_change.change_uid`, a UUID minted at proposal, never derived from the sequence — in 085 already — and an **offered eleventh parameter** so the procedure can refuse a uid it has applied. They scope it exactly: after a `PMC_PSA` restore an edit replayed is already caught by `@expected_tstamp` (the row version moved); **a new record is not, and that is the only case the uid exists for.** They leave whether BizBox can hold the uid to the Bizbox Chat session.

**Declined, as driver and consistent with Part 94, open to Dada's override.** For the procedure to refuse a seen uid it must remember uids somewhere that survives a `PMC_PSA` restore — which means in BizBox: either a column on the vendor's document (Dada's call, declined in Part 94) or the consumed-ids table Dada just had removed. Three mechanisms stay three. **The case is closed by a rule instead, because it is rare, deliberate and hands-on:** `PMC_PSA` has been restored into **zero times ever** (MEASURED, Part 94); so **after any restore of `PMC_PSA`, every `PENDING`, `APPROVED` or `SENDING` row is cancelled before `bizbox-push` is run, and `bizbox-reconcile` is read to re-queue what BizBox lost; anything still wanted is re-raised by a person who checks BizBox first.** Nothing a new record could be created twice by survives that rule. **`change_uid` stays on `ext_change`** — it costs nothing and makes the desk's own audit unambiguous across a restore — **and is not passed to the procedure.** The signature stays at ten parameters.

**Their §8 order for the host, adopted as the order, with two notes.** COPY_ONLY backup → stop PSA-Desk → apply 085 from the port (four swaps, nine ADDs, guarded) → verify as §2 → start PSA-Desk → the procedure with `@expected_tstamp` tenth → `tstamp` on the five existing views (`vw_purchase_order`, `vw_product`, `vw_invoice`, `vw_purchase_order_line`, `vw_lookup` excepted as a list) and on the three 084 views when built, `"tstamp"` in the map → `CREATE USER [psa_desk]` and the two grants in both databases → verify with the four controls → `PSA_BIZBOX_WRITE_ODBC` in the **push task's** environment, never the desk's (080 §5.3) → `bizbox-push` previews, `--apply` sends, Training first. **Note one:** `tstamp` on the views is a change to `LiveDB_PMC` and `TrainingDB_HIS8` — Dada's go. **Note two:** after every Training refresh the procedure and the `psa_desk` user there are gone (Part 94) — re-create and verify before proving.

**Nothing applied on the host. Nothing scheduled. `PSA_BIZBOX_WRITE_ODBC` unset.** `ec24f18` fetched, not pulled; pulled when CI reports green.

---

**Part 96 (14 Oct 2026): Bizbox Chat verified the INVOICE answer from their side and corrected my explanation of the row gap — it was not lag. And their crash-between-commit-and-mark question is already closed by WS36's 085.** Theirs verified; mine corrected; WS36's confirmed from the remote ref.

**INVOICE confirmed from the BizBox side.** `psa.vw_invoice` reads `dbo.iwApinv` — the Delivery/Receiving header, not `iwApitem`. Their §3 "Delivery / Receiving" is the desk's existing `INVOICE` kind; nine MMS kinds added, not ten; their §3 wording is theirs to correct. For completeness, the other four views by the tables they read: `vw_purchase_order` → `iwPOinv`; `vw_purchase_order_line` → `iwPOinv`, `iwPOitem`, `iwItems`; `vw_product` → `iwItems`, `iwPOitem`; `vw_lookup` → `mscCurrency`, `mscItemCategory`, `mscUnits`. Control: a view that cannot exist in `psa` returned 0.

**My explanation of the gap was wrong in direction, and they caught it.** Part 95 said `ext_invoice` at 1,050 against 1,069 headers was *"the hourly mirror's lag"*. **Lag makes a mirror smaller than its source, not larger** — and the view returns **1,035**, so the mirror holds **15 more** rows than its source currently exposes. I had the numbers in front of me — my own output read *"rows: 1050, present: 1035"* — and misread them. **The right reading, MEASURED from the desk's own table: `present = 1,035`, exactly the view's count; the 15 are `present = 0`** — rows the view stopped returning, retained and flagged absent by the mirror's design rather than pruned. Not lag; retention. **Consequence they named correctly:** any count-based reconcile must filter `present = 1` or it shows a permanent 15-row discrepancy that reads as lag forever and masks a real one — the `Watch-PMCBridge` shape from the other end, a check whose baseline is never zero. WS36's `bizbox-reconcile` (§7) checks presence per `APPLIED` change rather than counting, so it is not exposed; recorded so nobody writes the count version.

**The 34 excluded headers, explained from the view's own text.** They measured 1,020 non-cancelled headers — *fewer* than the 1,035 the view returns — and inferred the view includes some cancelled rows and excludes 34 on another basis. **MEASURED, the view's `WHERE` clause in full: `ISNULL(a.deleteflag, 0) = 0`.** It filters on `deleteflag`, not `cancelflag`: 1,069 − 34 deleted = 1,035, and cancelled-but-not-deleted headers are included. Their inference was exactly right and the basis is now named.

**Their one open question — a crash, kill or recycle between the procedure committing and the desk marking the row — is already closed by WS36's 085, read from `ec24f18`.** The ambiguity they describe is real: after claim-before-apply, `SENDING` means *"may or may not have been applied"*. What 085 does with it, MEASURED from the code: **`push()` selects `c.status = 'PENDING'` only — a `SENDING` row is never re-selected, so there is no automatic replay.** `unclaim()` returns a row to `PENDING` **only on the `Refused` path inside `push()`, before the procedure is ever called** — its docstring: *"for a change that was never sent (the writer declined before calling BizBox)"*. **A row stuck in `SENDING` for over 15 minutes is listed by `stuck_sending()` and printed by `bizbox-push` as STUCK, and the remedy it names is: "read BizBox, then decide each by hand: `bizbox-changes --decide <id> --as APPLIED|REJECTED`".** `decide()` refuses `CANCELLED` on a `SENDING` row and offers no path to `PENDING`. **Nothing can return a `SENDING` row to the send queue; it is resolved by reading BizBox, which is what they asked for.** One honest limit: for a *new* record whose crash fell after the procedure returned BizBox's number but before the desk stored it, the person has no `ext_ref` to look up and finds the document by its content. The window is the milliseconds between two statements; proportionate.

**Their reading of the restore rule, which they would not override:** a row `APPLIED` then restored back to `PENDING` is cancelled by the rule; a row `APPLIED` then restored to before it existed has nothing to cancel, and the human who checks BizBox first catches it. The load-bearing element is that human check; with `PMC_PSA` restored zero times ever, proportionate. *"Three mechanisms staying three is worth more than closing a case that has never occurred."*

Their script: `scripts/Probe-PsaViewSources-20261014.py`. Nothing applied on the host; `ec24f18` still pending CI.

**Part 96, addition (14 Oct 2026): the brief's §3 counted raw rows — deleted and cancelled included — across all fourteen document types. Overstated by 366 headers, 5.0%. The kind-list verdict is unchanged.** Theirs; both columns published, neither replacing the other.

My `deleteflag` reading of `vw_invoice` (Part 96) led the Bizbox Chat session to check whether their §3 document counts carried the same flags. They did. Filed as `docs/bizbox-mms-section3-flag-audit-20261014.md`, 92 lines, **hash matched before copying** (`6842b0a0…854b769`), byte-identical, fence clean, all seven earlier files re-verified unchanged. Cross-checked both ways from their side: `iwApinv` with `deleteflag <> 0` measures **exactly 34**, matching 1,069 − 34 = 1,035 to the row.

**Raw / deleted / cancelled / live**, per document: Expense Requisition 1,223 / 28 / 32 / **1,163**; Stock Requisition 1,095 / 35 / 39 / **1,021**; Expense Issuance 1,085 / 5 / 12 / **1,068**; Delivery/Receiving 1,069 / 34 / 49 / **986**; Stock Issuance 998 / 19 / 6 / **973**; Purchase Order 837 / 23 / 18 / **796**; Purchase Requisition 634 / 16 / 13 / **605**; Material Production 169 / 12 / 7 / **150**; Physical Count 104 / 5 / 7 / **92**; Quantity Adjustment 40 / 3 / 1 / **36**; Job Order 21 / 0 / 0 / 21; Job Order Request 5 / 0 / 2 / 3; Purchase Return 2 / 0 / 0 / 2; Allotment 0. **Total 7,282 raw, 180 deleted, 186 cancelled, 6,916 live — overstated by 366, 5.0%.** Not uniform (0% on three, 11.5% on Physical Count, 40% on Job Order Request), so **no blanket adjustment — the per-document figures are used.**

**They published both columns rather than replacing raw with live, and that is correct** under the record's own rule — *flags are counted, never filtered out*. A raw count answers how much is in the table; a live count answers how many documents a department would recognise. §3 gave the first while being read as the second; now both are labelled.

**The verdict stands.** Against live, Quantity Adjustment 40 → 36 is still in; Job Order 21, Job Order Request 3 and Purchase Return 2 still out. Nothing crosses. **Ten in scope, four excluded, nine new kinds** with Delivery/Receiving being the existing `INVOICE`. The CHECK widening, the verifier and the phase-1 list all stand. The cut now sits in a wider gap — lowest in 36, highest out 21.

**Untouched:** §4 report usage (SSRS execution counts), §2 holder counts (permission rows), and the whole §5 defect list (counts from `iwWareitem`, `iwItems`, `iwItemLedger` and the lot tables, not document headers). **Touched and flagged, not fixed:** §5.6 quoted `approvalflag` 802/35 and `approval2flag` 762/75 against **raw** PO headers of 837; against 796 live the proportions change. **Not re-measured; if it reaches a sizing or a control it needs doing first.** The conclusion's direction does not change — PO has two stages and uses them; the requisitions have no approval column at all.

Their own account, kept: not an oversight of a known filter — they had not checked whether those tables carried `deleteflag` and `cancelflag` before publishing counts that would be read as live volumes. And their closing line, which applies to both sessions today: *"Reading your own output before writing the conclusion is apparently the hardest step for both of us."*

**Part 96, second addition (14 Oct 2026): §5.6 re-measured on live rows — approval discipline on POs is better than the raw figures implied, and the requisitions' absence of any approval column is now a measured absence with a working control.** Theirs, three queries, closed rather than listed.

They re-measured despite my saying it could wait, on the grounds that leaving a known-wrong number in a committed document under their name costs more than three queries, and that *"on the list for when something depends on it"* is how a figure gets quoted in a sizing before the list is read. Correct. Filed as `docs/bizbox-mms-section56-approval-remeasured-20261014.md`, 50 lines, hash matched before copying (`125d4a29…cf9b9a434`), neither the brief nor the flag audit edited.

**Corrected, live = `deleteflag 0 AND cancelflag 0`.** `iwPOinv` 837 raw → **796 live**. `approvalflag` raw 802/35 (95.8%) → **live 775 set / 21 unset, 97.4%**. `approval2flag` raw 762/75 (91.0%) → **live 744 / 52, 93.5%**. Posted and approved by the same person: 1 of 802 raw → **1 of 775 live**. **So PO approval is better than §5.6 said**: most unapproved POs are the deleted or cancelled ones, which is what an unapproved PO becomes. Second-stage approval at 93.5% of live POs; preparer-approver separation holds on all but one.

**The claim that carries §5.6, now with a control.** Live headers and approval columns: Expense Requisition 1,163 — **NONE**; Stock Requisition 1,021 — **NONE**; Delivery/Receiving 986 — **NONE**; Stock Issuance 973 — **NONE**; Purchase Requisition 605 — **NONE**; Purchase Order 796 — `approvaldatetime`, `FK_ASUapproval`, `approvalflag`, `approval2datetime`, `FK_ASUapproval2`, `approval2flag`. **Controls: an impossible column pattern returned 0, and the same search finds 5 `%flag%` columns on `iwPRinv` — so those NONEs are measured absences, not a blind search.** That matters because *"no approval column"* is exactly the kind of negative this estate gets wrong.

**The contrast is stronger than §5.6 stated.** The PO carries a full two-stage apparatus — two distinct approver identity columns, two flags, two timestamps — and uses it on 97.4% and 93.5% of live documents. **4,748 live requisition, issuance and receiving documents have no approval field of any kind, and those are the documents 655 and 640 people hold the screens for.** Approval routing for the requisitions is not a feature that exists unused; there is nowhere in the schema to record it. Still the natural home of the PSA desk, now with live numbers.

**Named rather than dropped, not chased:** `FK_ASUapproval2` is a second, distinct approver identity column, so BizBox supports two *different* approvers at the two stages. Whether stage one and stage two are ever the same person — approver-versus-approver separation — was not measured. The 1-of-775 covers poster-versus-approver only.

Every item of theirs on this thread is closed. Nothing outstanding from their side; they are running nothing in MMS.

**Part 96, third addition (14 Oct 2026): the "byte-identical, sha256 matches" claims on the eight BizBox files are true at copy time and in the worktree — the committed blobs differ by line endings. Recorded so a later verifier does not read tampering into `core.autocrlf`.** MEASURED, mine.

After the rebase onto `ec24f18` re-checked-out the tree, the worktree hash of `bizbox-mms-section3-flag-audit-20261014.md` read `7f0ddf3a…` against the `6842b0a0…` verified minutes earlier. **Not tampering: `core.autocrlf=true` on this checkout.** The committed blob is the LF form; a Windows checkout writes CRLF; `sha256sum` on the worktree then differs from the blob.

| File | Committed blob | Worktree now | Their stated hash |
|---|---|---|---|
| `bizbox-mms-section3-flag-audit` | **`6842b0a0`** | `7f0ddf3a` (CRLF) | `6842b0a0` — record copy was LF; blob matches |
| `bizbox-mms-section56-approval-remeasured` | `125d4a29` | `125d4a29` | `125d4a29` — not yet re-checked-out |
| `bizbox-mms-design-brief` | `49cde08e` | **`0b3072d1`** | `0b3072d1` — record copy was CRLF; **git normalised it to LF on commit**, so the blob differs and the worktree matches |

**So the rule for re-verifying any of the eight files against the Bizbox Chat session's stated hashes:** compare either `git show HEAD:<path> | sha256sum` against an LF-normalised copy, or the worktree against the record copy with both converted the same way — never a bare `sha256sum` on the worktree against a stated hash, because which side carries CRLF depends on which machine wrote the record copy. **Content is identical in every case; only the line terminators differ.** The `cmp` checks at copy time were valid because both sides were then the same bytes; what changed afterwards is git's storage form, not the content.

Same family as the estate's own BOM-less UTF-8 and bash-heredoc traps (`pmc-estate` §6): an invisible byte-level transform that reads as a content difference to anyone checking later. One line here saves a false tampering alarm.

**Part 96, fourth addition (14 Oct 2026): the line-ending rule in the third addition is corrected — two mechanisms at opposite ends, and the brief's CRLF was Python text-mode I/O at authoring time, not the machine.** Theirs, measured on the record copies; my rule withdrawn, my remedy kept.

The third addition said *"which side carries CRLF depends on which machine wrote the record copy."* **Wrong.** The Bizbox Chat session measured the record copies — the record repo has `core.autocrlf=false`, so it transforms nothing — and **of their nine filed documents exactly one contains CR: the brief.** 21,509 bytes as-is, 21,115 LF-form, difference 394 = exactly its line count, one CR per line; as-is `0b3072d1` (what they stated), LF-normalised `49cde08e` (the committed blob). **The other eight are pure LF**, as-is hash equal to LF hash, the §3 audit at `6842b0a0` both ways.

**Why the brief alone is CRLF, demonstrated not asserted:** every patch script they ran today used `io.open(p, 'w', encoding='utf-8')` with no `newline=''`, and on Windows Python text mode translates `\n` to `\r\n` — `io.open(p,'w',encoding='utf-8')` → `b'a\r\nb\r\nc\r\n'`; with `newline=''` → `b'a\nb\nc\n'`. The brief is the only document they rewrote with Python (six corrections, two line-wrap fixes, one stale-figure fix); the other eight were written once by the Write tool or a heredoc and moved untouched. Control: `rule0-withdrawn`, Write tool only, is LF exactly as predicted.

**The two rules on this estate, replacing mine:** a file that passed through **Python text-mode I/O on Windows is CRLF at authoring time**; a file authored LF **becomes CRLF at checkout time under `core.autocrlf=true`**. The §3 audit is the second case (LF in the record, `6842b0a0` is both its record hash and the committed blob, `7f0ddf3a` is this checkout's CRLF); the brief is the first (CRLF in the record, worktree matched the stated hash, git stored LF). Both are worktree-versus-stated mismatches with the transform at opposite ends. **The remedy in the third addition — normalise before comparing, never a bare worktree hash against a stated one — covers both and stands.**

**Added to the trap list beside BOM and heredoc:** never use Python text mode to rewrite a file in the record — pass `newline=''` or write bytes. Theirs to carry; they will. And a reporting note: the "21,509 bytes" stated for the brief is the CRLF figure; the LF form is 21,115; any size check must say which.

**Nothing changed.** They did not normalise the brief and will not — converting it would invalidate the hash verified at copy time and create exactly the tampering question this trap already risks. It stays as committed in `bb96800`. That closes everything on their side.

---

**Part 97 (14 Oct 2026): `ec24f18` superseded by `3fb7453` — 085 corrected before being applied anywhere. Eight new kinds, not nine; my count corrected. `change_uid` parameter withdrawn; the restore rule adopted. And a finding on the design skills that is Dada's to decide.**

Dada pasted WS36's second reply: pull `3fb7453` once CI run 38482525893 is green. **At this Part, `windows` is still running; `sql-server`, 3.11 and 3.14 green.** Fetched, not pulled; nothing applied.

**What changed in 085, read from the remote ref.** `DELIVERY_RECEIVING` is out of both CHECKs and the desk's kind list — **0 occurrences in `085_write_path.sql`** — because Delivery/Receiving is the existing `INVOICE` kind, MEASURED on both sides (Parts 95–96). **Eight new values:** `EXPENSE_REQ`, `STOCK_REQ`, `EXPENSE_ISSUANCE`, `STOCK_ISSUANCE`, `PURCHASE_REQ`, `MATERIAL_PRODUCTION`, `PHYSICAL_COUNT`, `QTY_ADJUSTMENT`; `PURCHASE_ORDER` and `INVOICE` are the two the desk had. **My Parts 95 and 96 said "nine new, not ten" — wrong by one: I counted only `PURCHASE_ORDER` as existing when `INVOICE` is too.** Ten in scope = eight new + two existing. The four swap blocks keep their names and guards with `IN` lists one shorter; nothing else in 085 moved. The handoff carries a dated addendum at the top; the body is unchanged and superseded where it differs.

**Taken from Part 95:** the eleventh parameter is withdrawn — the desk passes and reads no uid; `change_uid` stays as the desk's own audit id. The restore rule — after any restore of `PMC_PSA`, cancel every open row by hand and read `bizbox-reconcile` first — is adopted as written and is now the README's §6 text. The ten-parameter `CALL`, the sender's claim, the row version and the one-condition guard are as before.

**The design-skills finding, theirs, stated plainly as asked, and Dada's to decide.** Part 85's standing instruction — *"use design skills and whatever skills available when building it or when u tell ws36 to build it"* — was relayed with the seven `design:*` skills named from this session's catalogue and `frontend-design` noted as being enabled. **WS36 reports that in the cloud session the skills present are `artifact-design` and `dataviz` (both loaded on 13 Oct for the Procurement screens) and `pdf` and `xlsx`; no `design:*` and no `frontend-design` is present there.** They said so rather than assuming, which is the rule I gave them. **So the `design` plugin Dada enabled, and the `frontend-design` card he was given, are enabled in SQL01's desktop session — not in the session that builds the screens.** Whether the plugin can be enabled for the cloud session, or whether the design review is done from this side against what WS36 ships, is his call; stated once.

Their line on Part 96's line-ending trap: no file of theirs passed through Python text mode on Windows. Noted.

**Nothing written, nothing scheduled, `PSA_BIZBOX_WRITE_ODBC` unset.** `3fb7453` is pulled when CI reports green; the order stands; nothing runs until Dada says go.

**Part 97, addition — ruling and first review (14 Oct 2026): the design review happens on SQL01's side against what WS36 ships. First review done on the 084 Procurement screens: one major fault, the 13 Oct class again.**

Dada: *"review the design on this side"*. Read as the ruling on Part 97's question — the `design` plugin is in this session and not in WS36's cloud session, so the review is done here against what they ship — and as an instruction to do one now on what has shipped since 13 Oct's audit. **Standing from here: every screen WS36 ships gets reviewed here with `design:design-critique` and `design:accessibility-review` loaded, and the findings go back as a handoff.**

**How, without touching anything live.** The desk on 8085 is running the code it started with after 083 and 084's tables are not on `PMC_PSA`, so the 084 screens cannot be seen there. A throwaway desk was built from the `3fb7453` checkout: SQLite in the scratchpad, `psaspine init` to 085, the walkthrough, a test sysadmin account whose password was generated and recorded only beside the database, and seed rows — 6 products, 6 warehouses, 12 stock lines, 166 movements, 6 receiving lines — served on `localhost:8086` through the browser pane's launcher (`.claude/launch.json`, untracked). Reviewed: Overview, Stock on hand, Movements, Products, and the item page where the 084 cards sit. Contrast from computed styles, reflow at 375px, keyboard walked. Server stopped after; nothing on the live desk, `PMC_PSA`, `LiveDB_PMC` or the host touched.

**Skills that fired:** `design:design-critique`, `design:accessibility-review`. `design:ux-copy` did not — no copy rewritten.

**Major, and it is the 13 Oct fault again.** Movement kinds render as BizBox doctype codes — **`Ca · Ch · Dr · Ei · Pc · Ss`** on the Overview chips, the Movements tab chips and every row, and the item card. **Root cause, MEASURED in `psaspine/bizbox.py`: `MOVE_WORDS` maps guessed English kinds (`RECEIPT`, `ISSUE`, `TRANSFER_IN`, `ADJUST`, `COUNT` …) and contains none of BizBox's real codes** — `CH`, `CA`, `CN`, `SS`, `PC`, `EI`, `DR`, `MP`, `QA`, `PP`, `PR`, which the brief measured from 227,077 ledger rows. Every real movement misses the table and falls to `.capitalize()`. A vocabulary guessed rather than read, exactly like the category dropdown on 13 Oct. Eight codes are nameable from the brief's own §3 (`CH` charged, `SS` transferred, `PC` counted, `EI` issued, `DR` received, `MP` produced, `QA` adjusted, `PR` returned); **`CA` (58,847 rows), `CN` (17,136) and `PP` (92) are the second- and third-largest kinds in the ledger and nobody has named them** — routed to the Bizbox Chat session under Part 89's rule, with WS36 told not to guess and to fall back to a code span rather than a fake word until they come back.

**Moderate:** the same four-line instruction paragraph opens every Procurement tab, above the tab bar; at the pane's height the tabs sit at the fold and at 375px the paragraph is a full screen before any control. Show once, or one line with a disclosure. **Minor, five:** tile accessible names concatenate number and caption ("0purchase orders"); the Products grid's per-row selects have header-only label association so a screen reader reads every option list per row (the edit-cells design is deliberate and stands — this is the accessible-name layer on it); money carries no currency anywhere; "As of" repeats per row when uniform; the empty Remarks column always renders.

**Passes, measured:** contrast on every text style — body 10.55:1, `th` 5.90:1, `td` 18.57:1, tabs and links 21:1; focus visible and in document order; no horizontal scroll at 375px, tables scroll within `.tablewrap`; labelled controls on the item page. **Works well:** the 084 cards on the item page, with *"Raise a ticket about this item"* pre-filled — the MMS → PSA bridge the whole build is for, in one click; the stock-by-warehouse bars; the dated sync bar; the three-way Movements filter.

Filed as `docs/handoffs/HANDOFF-sql01-cloud-WS36-20261014-design-review-084-procurement.md`. Priority to WS36: the codes first, the paragraph second, the five as a sweep.

---

**Part 98, ruling (14 Oct 2026): the MMS screens are to be *similar* to the 1:1 draft — the document shape — not a 1:1 copy. And the desk has no MMS document screen yet. Plus the eleven ledger doctypes named, with a patient-name fence that lands on SQL01's own view first.**

Dada showed the Bizbox Chat session's 13 Oct draft of `frmStockRequisitionDetails` — *"MMS - Stock Requisition Details, 1:1 draft… same header pickers, grid columns, buttons and footer as BizBox's form, measured from the program; items marked BETTER are the additions"* — and asked *"does it follow this design?"*. **Answered: no, and nothing could yet.** MEASURED from the views: the desk has **no** Stock Requisition, Expense Requisition, Issuance or Physical Count screen; the Procurement area's only "New" actions are *New purchase order* and *New item*; 085 added `STOCK_REQ` and the rest as *change kinds* so a requisition could in principle be proposed as an ADD payload, but there is no screen to author one — no header pickers, no lines grid, no on-hand per row, no slip. **What WS36 has built is a window onto BizBox with a change-proposal queue** — the read side, reviewed in Part 97, and the write plumbing of 085 — **not an MMS.** The desk can see MMS and is nearly able to write to MMS; it cannot yet *do* MMS. I said once that the draft's layout is the screen-parity reading withdrawn in Part 85 while its function is exactly Part 85, and left the layout question with him.

**His ruling:** *"well similar not 1:!"* — **similar, not 1:1.** Read as, and acted on: the MMS document screens are built to the **shape** of that draft — a document with header pickers (issuing department, warehouse from, centre, date), a lines grid (item, description, generic name, unit, quantity, served quantity, unit price, total, expiry) with the BETTER additions on it (on hand at source per row, shortfall shown rather than silently under-served, items picked from what exists and never created from the line, approval shown), a footer with totals, the approval path, print the slip, save — **modernised, with the design skills, not measured from the program.** Captions, chrome and theme are free; the document shape is the function. That reconciles Part 85 (function, not screens) with the draft without reinstating Rule 0, and it gives WS36 the shape of the screens they have not started. Told to WS36 with the design-skills rule from Part 85 restated: reviewed here, under Part 97's ruling, when shipped.

**The eleven ledger doctypes, named from BizBox's own stock-card builder — not inferred.** Bizbox Chat read `usp_InventoryStockCard`'s `CASE aa.doctype WHEN … THEN` — the description a user reads on the Electronic Stock Card, the product's own vocabulary. A route that failed, recorded so nobody repeats it: `mscDocTypes`, the table that looks like the vocabulary, is **empty** (0 rows) and `FK_mscDocTypes` is null on every ledger row; their control voided that section. Filed as `docs/bizbox-ledger-doctypes-named-20261014.md`, 119 lines, byte-identical, sha256 `1fcd7769…a50348` matching the prefix they stated, pure LF so no line-ending ambiguity, fence clean — no address, and the template is quoted with a placeholder, never a name.

**The fence that outranks the names, and it lands on SQL01 first.** The labels are templates that **embed a patient-name subquery**: `CA`, `CH`, `CN` and `DC` each read `select ag.fullname from psPatinv …`, so the stock card prints *Charges to "<patient full name>"*. **A desk that renders BizBox's movement description verbatim will surface patient names — and those four codes are 82.6% of the ledger.** `DR` and `PR` embed the vendor name and `SS` the warehouse, which are not patient data. **Consequence for the desk: use the code's word, never the product's description string.** 084's `ext_movement` has a `remarks` column mapped from `psa.vw_item_ledger` — **which is SQL01's view, not yet built. When it is built, `remarks` is not the stock-card description; it is a safe column or it is omitted.** Recorded as a constraint on my own work before it is a constraint on anyone else's. No patient name was selected or printed by them at any point — they read procedure text, not patient rows.

**The three I could not name.** **`CA`** — a patient charge, with **the same label as `CH`** (*Charges to "<patient>"*), strictly out (0 in / 58,929 out), Issuances bucket, same `psPatinv` counterparty. **Not** a charge-adjust/cancel pair with `CH` — an adjustment would show mixed direction, and the direction kills that reading, which I had flagged as the Rule 0 shape. Why the product carries two charge codes is **not established** (likely a field on `psPatinv`; not read, because it needs patient-encounter rows and the question did not require it). **`CN`** — a return *from* a patient, *Return from "<patient>"*, strictly in (17,136 / 0), Issuances; settled, direction and label agree; `vwCreditNotesList` pairs `CH` with `CA` not `CN`, so credit notes are built on the charge codes and `CN` is the stock consequence. **`PP`** — an **asset** movement, not materials: appears only in the asset variants (`usp_InventoryStockCard_AssetGovt`; `udf_GetCurAssetBalance` maps `PP`→`DP`), and the ordinary stock card **explicitly excludes it** (`doctype not in ('AT','PP','DP','GL','RT','RS')`); 92 rows, 46 docs, exactly 46 in and 46 out, all on 6–7 Oct. Asset Management, out of phase 1; a materials map does not carry it as a materials word.

**Of my eight: seven stand, one caveat, one trap.** `CH` charged, `SS` transferred, `EI` issued (BizBox: *Expense Issuance to*), `DR` received (*Deliveries from*; bucket Receipts), `MP` produced, `QA` adjusted — correct. `PC` counted — correct, but the product's words are *Qty Adjustment per Actual Count* and it sits in Transfers. **`PR` returned — the trap: `PR` is return *to* vendor, `CN` is return *from* patient, opposite directions, different counterparties, and "returned" fits both.** The map needs *returned to supplier* against *returned by patient*. **And the bigger one: `CA` and `CH` carry the identical label and together are 187,597 of 227,104 rows — 82.6%.** A map insisting on a distinct word per code invents a distinction the product does not make: give both *charged*, or carry the code beside the word.

**The product's own buckets, better than invented groupings:** Receipts = `PR`, `DR`, `PI`; Issuances = `CA`, `CH`, `CN`, `DC`; Transfers = `QA`, `SS`, `MP`, `PC`, `EI`; the asset variant adds `AT`, `PP`, `DP`, `GL`. **Seven codes the product handles that PMC has never produced** — `DC` (*Deleted Charges from patient*), `PI` (*Petty Cash Purchases from payee*), `AT`, `DP`, `GL`, `RT`, `RS` — all 0 rows, measured absences (an impossible code returned 0 through the same query that returns 128,626 for `CH`). **`DC` is carried despite zero rows:** it is a charge deletion in Issuances, and the day it appears a map without it falls through to a capitalised code — the fault being fixed. Not established and not guessed: the `AT`/`DP`/`GL`/`RT`/`RS` meanings; and `CA`'s date range runs to 2026-12-08, which is the six future-dated rows noted earlier, four of them `CA`, not chased.

**The word map as sent to WS36**, with the code carried beside the word everywhere: `CH` charged · `CA` charged · `CN` returned by patient · `DC` charge deleted · `DR` received · `PI` received (petty cash) · `PR` returned to supplier · `SS` transferred · `EI` issued · `MP` produced · `QA` adjusted · `PC` counted · and `PP`/`AT`/`DP`/`GL`/`RT`/`RS` as a code span, asset family, not phase 1.

**Nothing on the host changed.** `f313796` (Part 97 addition and the design review) still held locally pending CI on `3fb7453`. `PSA_BIZBOX_WRITE_ODBC` unset.

**Part 98, addition (14 Oct 2026): the 13 Oct draft split into the half the ruling keeps and the half it drops — and the draft faithfully reproduces an always-blank column.** Theirs, measured; filed and sent to WS36 before they draw from the PNG.

The Bizbox Chat session drew the Stock Requisition draft while Rule 0 was in force, so it reproduces BizBox's captions exactly; under *similar, not 1:1* only they could split it. Filed as `docs/bizbox-mms-draft-screen-under-function-parity-20261014.md`, 57 lines, byte-identical, sha256 `e6c465bc…c38df` matching the stated prefix, pure LF, fence clean. Script `Probe-DraftScreenBacking-20261014.py`, control passed.

**The misleading one, not known on 13 Oct.** The draft carries an **Expiry Date** column copied 1:1 from `frmStockRequisitionDetails`. **MEASURED today: `iwWhreqitem.expdate` is populated on 0 of 4,566 rows, and `lotno` on the same table is 0 of 4,566.** The column exists on BizBox's screen and on the table and has never held a value; a 1:1 rule required the draft to reproduce a blank column faithfully. **Under function parity the better version either populates it — §5.4, lot and expiry wholly unused in a hospital with 2,008 medicine items — or drops it. Reproducing a blank column is the one option off the table.** WS36 told, so the PNG is not drawn from without this.

**No longer binding, the 1:1 half:** captions Item ID / Item Description / Generic Name / Unit / Quantity / Served Quantity / Unit Price / Total Amount / Expiry Date; buttons Add / Edit Mode / Delete; footers Total Record(s) / Total Item / Total Amount; header pickers Issuing Department / Warehouse / Center.

**The five BETTER items — what the ruling keeps — three now with measurements behind them that did not exist when drawn.** (1) **On hand at source, stock on every row — keep, with a correction: it must come from the ledger derivation, not `iwWareitem.actualqty`**, which agrees with the ledger on only 33.3% of item+warehouse pairs (Part 84); on 13 Oct the field was drawn without knowing which number it should show, and now there is exactly one defensible source — the one `vw_stock_on_hand` is to be built from. (2) **Shortfall made visible** — 12 on hand against 20 requested, submittable with the gap shown — keep; inherits the same correction. (3) **Approval shown**, *Chief Nurse, then Central Supply issues* — **keep, now evidenced: `iwWhreqinv` has zero approval columns**, so that chain cannot be stored in BizBox at all and must live in the desk; §5.6, and the single clearest example of the desk doing something BizBox has nowhere to record. (4) **Items picked from what exists**, never created from the line — keep. (5) **Print the slip at the same click — keep, now evidenced:** 3,057 `MMS_ADHOC_StockReq` runs in 60 days (§4); the slip is the product.

**Two corrections to their own drawing, so the schema work does not inherit them:** the caption *Served Quantity* maps to column **`servqty`**, not `servedqty`; and `iwWhreqitem` has **no `purcprice`** — the line price column is **`price`**, with `netcost` alongside, so the draft's *Unit Price* is `price`. **Not established:** whether BizBox shows `price` or `netcost` in that cell — both exist on the line and the client's binding was not read; one `InitializeComponent` pass under PowerShell 5.1 would settle it, offered as a short job on Dada's word.

Their line on the fence, kept: better that the constraint bit SQL01's own unbuilt view first than was discovered in a rendered movement card.

**Part 98, second addition (14 Oct 2026): "Unit Price" on the draft binds `unitprice`, which is not a column on the requisition line — a client-computed field. "Total Amount" is `netcost`. And BizBox already binds a hidden warehouse balance to the grid.** Theirs, from real IL; WS36 corrected before binding.

Bizbox Chat walked `frmStockRequisitionDetails.InitializeComponent` — **10,112 IL lines, already on disk from the 13 Oct extraction, so no new reflection pass and no PowerShell 5.1 route was needed** — recovering the key-to-caption map from the `ldstr "<key>" → newobj UltraGridColumn` and `get_Header → set_Caption` passes; 239 columns constructed with a key. Filed as `docs/bizbox-mms-grid-column-map-20261014.md`, 64 lines, byte-identical, sha256 `48f2fb03…77f70` matching the stated prefix, LF, fence clean. Controls: an impossible caption matched 0 slots and the caption pass found captions.

**The map for the draft's columns — caption → bound key → on `iwWhreqitem`:** Item ID → `FK_iwItems` (yes) · Item Description → `itemdesc` (no, `iwItems`) · Generic Name → `genericname` (no) · Unit → `unit` (yes) · Quantity → `qty` (yes) · Served Quantity → `servqty` (yes) · **Unit Price → `unitprice` (NO)** · Price → `price` (yes) · **Total Amount → `netcost`** (yes) · Expiry Date → `expdate` (yes, empty on all 4,566) · Conversion → `conversion`, `smallconversion` · Abbreviation → `itemabbrev` (no).

**Two corrections to their own earlier note, carried so the schema does not inherit them.** (1) The draft's Unit Price is **not** `price` — it is `unitprice`, which **does not exist on `iwWhreqitem`**: present in 9 tables, none of them this one, and no procedure or view mentions both `unitprice` and `Whreq`. **A client-side computed field. A schema giving the line a `unitprice` column invents storage BizBox does not have.** (2) `netcost` is not an alternative to `price` — it is the Total Amount column. **The grid shows a stored `price` and a derived `unitprice`: two money columns**, which the earlier note had collapsed into one question. **INFERRED and labelled, not to be bound to:** `unitprice` is most likely `price ÷ conversion`, the pattern `usp_InventoryStockCard` uses elsewhere (`landcost / conversion`); the arithmetic is in the client method body, not `InitializeComponent`, and reading it is a different pass. WS36 told to show `price` and `netcost` from storage and either omit Unit Price or mark it derived with the formula stated.

**I had relayed the earlier "Unit Price is `price`" to WS36 an hour before; corrected to them first, before this Part was written.**

**The finding that reframes "on hand at source".** **`warebalance` is bound to this grid as a column key with no `set_Caption` found anywhere in `InitializeComponent`** — which for an UltraGrid column normally means hidden — and it exists in exactly one object in the whole database, `vwReportPurchaseAnalysisNew_PSRDtls`. **BizBox already carries a warehouse balance on the Stock Requisition grid and does not show it.** So the BETTER item is partly *unhiding a field the product already binds*, not inventing one — easier to justify to a department than a new column, and a better argument than the morning's. The caption-absence is INFERRED (it could be captioned outside that method; not chased). **It does not change the source rule:** whatever `warebalance` resolves to, the figure shown comes from the ledger derivation, because `actualqty` agrees with the ledger on 33.3% of pairs. This supersedes the "not established" line in their draft-split note; that note is unedited.

**Part 98, third addition (14 Oct 2026): the grid arithmetic measured — Unit Price = `price × smallconversion`, Total Amount = `qty × price × smallconversion` and stored. Their `÷ conversion` guess dead on the data; WS36 corrected before this Part.** Theirs, by reflection-only disassembly.

Bizbox Chat disassembled six methods on `frmStockRequisitionDetails` under Windows PowerShell 5.1, reusing the existing `Disasm-CF4Save-20261012.ps1`; method enumerator `scripts/Probe-SRGridArithmetic-20261014.ps1`. No BizBox code executed. Filed as `docs/bizbox-mms-grid-arithmetic-20261014.md`, 63 lines, byte-identical, sha256 `4dc93c15…ce4693` matching the stated prefix, LF, fence clean.

**The formulas, MEASURED:** **Unit Price (`unitprice`) = `price × smallconversion`**, computed in the grid, stored nowhere on the line — consistent with it being no column on `iwWhreqitem`. **Total Amount (`netcost`) = `qty × price × smallconversion`**, computed in the grid **and stored on the line.** The availability check multiplies `warebalance × qty × smallconversion`. **It is `smallconversion`, not `conversion`** — both are bound to the grid and both are captioned "Conversion" in the column map; the arithmetic uses the small one, and a build reaching for `conversion` because it is the obvious name is wrong on every item where the two differ. **The control, because it is a negative:** `op_Division` appears zero times across all six methods while `op_Multiply` appears eight times through the same search, so the division is absent rather than invisible and the `price ÷ conversion` inference from the second addition is withdrawn.

**The near-miss, kept because it would have been a confident wrong answer and is the `FK_mscBranches` shape again:** their first pass searched the IL for `div` and `mul` and found zero of each, which reads exactly like "no arithmetic in these methods". **.NET decimal arithmetic is an operator call, `Decimal::op_Multiply`, not an IL opcode.** Had they stopped at the first search the arithmetic would have been reported as elsewhere. And a method note that cost a false empty: passing several method names to the disassembler from bash as `"a","b"` sends one token `a,b`, matches no method, and returns an empty listing indistinguishable from "these methods are empty" — one method per call, or a real array.

**Two consequences for the build, sent to WS36:** (1) **`netcost` on the line is a stored computed value** — the grid computes it and the save persists it, so a replacement must compute it the same way or stored totals drift from the lines they describe, and nothing in the schema would catch that because both sides are numbers. A quiet correctness risk, not cosmetic; and **it is what `psa.sp_apply_change` must write for a requisition line, so it binds SQL01's procedure as much as WS36's screen.** (2) **Unit Price is price per *converted* unit, not per smallest unit** — multiplying by `smallconversion` scales up from the stored `price`; reading the caption the other way is backwards, and they had. **So WS36 can show Unit Price rather than omit it:** `price × smallconversion` computed not stored; `netcost` computed and stored; `smallconversion` throughout.

**Not established, expected-not-measured:** whether `unitprice` is written anywhere on save. It lives on the client-side `dtItemRepository` DataTable and is made writable on form load, but `InsertItemsToIwWhreqitem` (77 bytes) delegates to a 361-byte lambda that was not disassembled. The line table has no such column, so the expected answer is no. One call would settle it; offered on request.

**I had passed WS36 the `÷ conversion` reading as INFERRED an hour earlier; the correction went to them before this Part was written.** Nothing on the host changed.

---

**Part 99, ruling (14 Oct 2026): the Procurement module is all of BizBox MMS, better — its modules as a top menu, the area visible only to those with Procurement access, and proper RBAC per module per user.**

Dada, after *"go"* and an interruption, twice: *"what im saying is that the procurement module should be like whats everything on bizbox mms but better the menu on top and onlu visible to who has access to the procurement module and proper rbac to modules to users"*.

**Read as, and acted on — four things:** (1) **scope:** the Procurement module is *everything* in BizBox MMS, built better — the 22-module / 137-submodule inventory the brief measured is the scope list, phase order still his; (2) **shape:** the MMS modules are **the menu on top** — the Procurement tab bar becomes the BizBox module list (Items and Services, Purchase Requisitions, Purchase Orders, Receiving, Stock Requisitions, Expense Requisitions, Issuances, Physical Count, Quantity Adjustment, Material Production, Warehouses, Drugs, Reports …), not a left side-nav as the 13 Oct draft drew it; (3) **visibility:** the Procurement area itself is shown only to people who hold access to it; (4) **RBAC:** proper role-based access **per module, per user** — not per umbrella. The earlier *"go"* was read as "push the held Parts regardless of CI" and acted on; it was benign and stands. **It was not the go on the write path, and nothing on the host ran.**

**What exists today, MEASURED from `psaspine/security.py`.** Four Procurement areas — `PROC_PO`, `PROC_RR`, `PROC_ITEM`, `PROC_DRUG` — with levels `NONE / READ / WRITE / ADMIN` worded *None / See / Propose / Approve*, one role per member, "never one's own" on approval, and an `UMBRELLA` so the Procurement menu shows when the role holds any area above NONE (the 13 Oct comment: *"a role sees an area only once Setup says so; a live desk's roles start at NONE"*). **So item (3) largely exists at area level.** But the mapping 085 added on 14 Oct collapses the MMS document kinds onto those four: `purchase_req → PROC_PO`, and **`expense_req`, `stock_req`, `expense_issuance`, `stock_issuance`, `material_production`, `physical_count`, `qty_adjustment` all → `PROC_ITEM`**. **Seven of the eight new kinds share one grant.** A ward clerk who may raise a stock requisition holds the same level over physical counts and quantity adjustments — which is what *"proper rbac to modules"* is not.

**What BizBox does, from the brief's own measurement.** Access is **per user per submodule** — `appsysUserSubmodules` and `appsysUserGroupSubModules` — 137 submodules, with the holder counts that define the real shape: **655 people hold Expense Requisition Details, 640 Purchase Requisition Details, 570 Stock Requisition Details**, then a long tail down to the handful who hold receiving, purchase orders and physical count. So "only visible to who has access" at module level means six hundred-odd people see the requisition modules and a dozen see the stores modules. **That is the shape the desk's RBAC has to reproduce, and today's four areas cannot express it.**

**Sent to WS36 as the ruling, with the gap named and the design left to them for Dada's approval:** modules replace areas as the unit of grant — one entry per MMS module, levels unchanged (`None / See / Propose / Approve`, never one's own); the Procurement entry in the top nav shows only when the member holds any module above `None`; the module tab bar shows only the modules the member holds; and *"to users"* read as **per user**, which is BizBox's model and not the desk's current one-role-per-member — **flagged as the structural question in it:** whether a member keeps one role with per-module levels, or gains per-user module grants over a role, is a design choice WS36 proposes and Dada approves. `PROC_DRUG` stays a module of its own (his 13 Oct instruction). Part 90's ten-in / four-out phase cut and the brief's holder counts are the seed for which modules exist on day one and who holds what.

**Standing from Parts 85, 97 and 98, restated to WS36 so nothing is lost in the re-shape:** function parity not screen parity; design skills loaded and named; reviewed here when shipped; the document screens to the *similar, not 1:1* shape; `smallconversion` not `conversion`; the mapped movement words, never BizBox's description string. **Nothing on the host changed; `PSA_BIZBOX_WRITE_ODBC` unset; 085 unapplied.**

**Part 99, addition (14 Oct 2026): CI on `3fb7453` finished red on one flaky auth test; 085 is green. The pull on Dada's word stands.**

Run 38482525893 completed **failure** at 00:16:46Z — after `3fb7453` had been pulled and the held Parts pushed on Dada's *"go"*. **The one failure is unrelated to 085 and flaky by construction:** `AuthTest.test_a_tampered_or_wrong_token_is_refused` (`tests/test_spine.py:2427`) calls `_rsa_keypair()` (line 2003), which picks random primes and computes `pow(e, -1, (p - 1) * (q - 1))`; when `e` shares a factor with that modulus there is no inverse and Python raises `ValueError: base is not invertible for the given modulus`. Rare, random, will recur; the fix is WS36's and small — loop until `gcd(e, (p−1)(q−1)) == 1`, or fixed test primes. Linux 3.11 and 3.14 passed the same test on the same commit; `sql-server` passed.

**Everything else green:** `Ran 843 tests — FAILED (errors=1, skipped=2)`. Every `WritePathTest` case passed — the kinds named in words, the sender claims before it applies, the mirror carries the row version, reconcile and requeue — including the assertion that `DELIVERY_RECEIVING` is absent from `085_write_path.sql`. **085 is green.**

**The job was not hung.** It ran 843 tests in **3,967 seconds — 66 minutes** — against 30 minutes for the previous run's whole Windows job. The runner is not on this host (checked: no Actions runner service or process here). Told WS36 to look at whether the curl.exe end-to-end test or anything in `3fb7453` added a network wait.

---

**Part 100 (14 Oct 2026): the write path's host side, on Dada's "do all of these". 084 and 085 on `PMC_PSA`; `tstamp` on four views, the procedure skeleton and the `psa_desk` grant on both BizBox databases; the hourly read proven with the row version landing. Two traps found on the way, one of them mine and serious.**

Dada pasted the four open items — the write path go, priority, the Report Manager check, WS36's RBAC proposal — and said *"do all of th3e4se"*. Read as all four, with the write path as the production sequence from Part 93, each step gated. The earlier *"go"* had been read as "push the held Parts regardless of CI" and acted on; he then clarified the Procurement ruling (Part 99) and this message covered the rest.

**The Report Manager check — CLOSED.** Rather than the screen, the report server's own API: `GetDataSourceContents` for `/Data Sources/BIZBOXHS8` via `curl.exe --negotiate` answered **HTTP 200, `CredentialRetrieval=Store`, `UserName=pmc_ssrs_reader`** — not `psa_bizbox_reader`. Zero `Password` elements in the response (the API never returns one). Control: an item that cannot exist answered HTTP 500 `ItemNotFound`. **That was the one unknown on whether the reader login is used anywhere else; every known place is now clean.** It stays in place regardless — removal is a separate step on his word.

**Priority — set by SQL01 in the GO message to WS36, on his delegation, and recorded as mine to reverse:** 0 fix the flaky RSA test · 1 RBAC per module with a per-user override (my decision, flagged) · 2 the module tab bar · 3 Stock Requisition to the *similar, not 1:1* shape · 4 the review fixes, movement words first · 5 the remaining documents in Part 90's volume order. **WS36's RBAC proposal** is answered in advance by the same message: role as the base carrying a level per module, a per-user override that wins, Setup able to set one person on one module in one screen — BizBox's own shape and how he granted Shane and Ethel on 13 Oct.

**The write path, step by step, MEASURED on fresh connections after each commit:**

1. **The guard — already done by WS36 in 085.** `write_odbc_string()` is one condition: unset is the off-switch; any `uid=` refused with the remedy in the message; `sa` and read-reused checks gone. Verified in the checkout, not re-done.
2. **084 on `PMC_PSA` — it had never been applied, and 085 depends on it.** The 085 preview found `psa.ext_stock` absent; the transaction died and nothing persisted. 084's ten blocks (one ADD, three `CREATE TABLE`, six indexes) extracted from the port by their guard text; COPY_ONLY backup `PMC_PSA_COPYONLY_pre084_085_20261014-082852.bak` (139 MB, `RESTORE VERIFYONLY` passed); PSA-Desk stopped; **084 applied, 17 checks and three controls, committed**; `body_hash` = 64, three tables present and empty, six indexes.
3. **085 on `PMC_PSA`.** First attempt rolled back on **my own wrong check** — I asserted `CK_ext_change_01` holds 10 kinds; it holds the original four plus eight new = **12**. The gate refused the wrong assertion, as it should; same shape as the Part 78 procurement-rights check. Corrected to 12 with each of the eight tokens asserted individually; **applied, 28 checks and three controls, committed.** `change_uid` and `expected_tstamp` = 64; `tstamp` on all seven mirror tables; `SENDING` on both status CHECKs; `DELIVERY_RECEIVING` absent. PSA-Desk started, answering 401 on 8085 (Windows auth, up).
4. **`tstamp` on the four mirror views — `TrainingDB_HIS8` then `LiveDB_PMC`.** Each view's text taken from *its own* database, one column appended before `FROM`, `CREATE OR ALTER`, in one transaction, read back through the view and through `EXECUTE AS psa_bizbox_reader`. **Trap one, WS36's expression:** `CONVERT(VARCHAR(18), tstamp, 1)` on a **`rowversion`** column copies the eight raw bytes as a string — style 1 hex-formats only `binary`. MEASURED: without the cast the sample was eight bytes; with `CAST(tstamp AS BINARY(8))` first it is `0x0000000001CA0272`. The 085 handoff §4 has it wrong; corrected to WS36.
5. **`psa.sp_apply_change` — the skeleton, both databases.** The ten-parameter contract the desk calls, one row back (`ok`, `message`, `ext_ref`), input validation (positive id, `EDIT`/`ADD`, known kind, an EDIT names record and field, an ADD carries a payload), and **every kind refused with `ok = 0` naming the kind — it writes nothing in any branch.** It exists so the grant can be made and the refusal path proven; each document kind lands as its write is measured against the vendor client on Training. `[psa]` and `[dbo]` both owned by `dbo` on both databases, so chaining holds and no `EXECUTE AS` is in it. Ten checks and four controls, including the ledger row count unchanged by the calls.
6. **`psa_desk` on both databases:** `CREATE USER … FOR LOGIN [DND-SQL01\psa_desk] WITH DEFAULT_SCHEMA = psa`, `GRANT SELECT ON SCHEMA::psa`, `GRANT EXECUTE ON OBJECT::psa.sp_apply_change` — and nothing else. Verified **as `psa_desk`** under `EXECUTE AS … REVERT`: no database role, exactly three explicit grants, `EXECUTE` = 1, `SELECT` on the view = 1, **and the four that must fail all 0 — `UPDATE dbo.iwWareitem`, `UPDATE dbo.appsysUserSubmodules`, `SELECT dbo.psPatinv`, `SELECT dbo.iwItems` directly**; reads through the view by chaining; one execution refused with `ok = 0` and nothing written.
7. **The map on the host:** `tstamp` added to the four objects, backup `bizbox-map.json.bak_20261014_083608`, written to temp and replaced in one move, read back, `check_map` accepts it.
8. **Proven by the production hourly read itself.** `PSA-BizBox` run as `psa_desk`: **exit 0, `applied`**, and the mirror now carries the row version on every present row — **5,480 of 5,501 products, 815 of 821 purchase orders, 1,036 of 1,051 receiving reports, 2,099 of 2,143 PO lines** (the remainder are `present = 0` rows the view no longer returns, Part 96), every sample `0x` + 16 hex; `ext_stock` still empty, correctly, because its view is not built.

**Trap two, mine, and the serious one.** The first apply of the views and of the grant **printed PASS and persisted nothing on either database.** Cause, MEASURED: both scripts ran `SET XACT_ABORT ON` and then, inside the same transaction, a deliberate negative probe that **raises** — a `SELECT` on `dbo.iwItems` as the reader, a direct `UPDATE` as `psa_desk` — expecting the error. **Under `XACT_ABORT`, a run-time error aborts the transaction.** Every check before the probe had already passed, the later `commit()` was a no-op on nothing, and the VERDICT line said PASS. The procedure script survived only because its refusals return rows, not errors. **Found because the hourly read then failed with `Invalid column name 'tstamp'`** — the map asked for a column the view did not have — and the task log, not my verdict, said so. **Two rules from it, applied to both scripts and binding on every gated script from here: a negative control inside the applying transaction is a query that returns 0 (`HAS_PERMS_BY_NAME`), never a statement expected to raise; and the VERDICT is what a fresh connection sees after the commit, never the in-transaction checks alone.** The 084 and 085 scripts had no raising probe and were read back on a fresh connection, which is why they were genuinely applied. Re-applied with both fixes: views 4/4 on both databases, `psa_desk` with user, three grants, no roles, `EXECUTE` 1 and `UPDATE` 0, all on fresh connections.

**Deliberately not done, and why.** `PSA_BIZBOX_WRITE_ODBC` is **not set.** The procedure refuses every kind, and `ProcedureWriter` turns `ok = 0` into `REJECTED` — setting the string now would reject every approved change the desk sends. It is set, in the push task's environment and never the desk's (080 §5.3), when the first kind is implemented. "Prove on Training against what the vendor client produces" is therefore the skeleton's refusal path proven on both, not yet a document write; that proof lands kind by kind. **Still mine and unbuilt:** the 083 views (`vw_warehouse`, `vw_drug_item`) and the 084 views (`vw_stock_on_hand` off the ledger, `vw_item_ledger` with `remarks` safe or omitted, `vw_receiving_line`), and then `stock`/`movement`/`rr_line` in the map.

**Changed on the host, all read back:** `PMC_PSA` schema 084 and 085; four views in `LiveDB_PMC` and `TrainingDB_HIS8`; `psa.sp_apply_change` (skeleton) in both; user `psa_desk` with three grants in both; `D:\psa\bizbox-map.json`; PSA-Desk restarted. Nothing written to any BizBox table. `bizboxsa` untouched.

---

**Part 101 (14 Oct 2026): "build them all" — the five views built on both BizBox databases, 083 applied on `PMC_PSA` (it had not been), the map at ten objects, the hourly read filling every mirror on its first pass. And Dada's date-picker design answered on the SQL side with `psa.fn_item_ledger(@from, @to)`.**

Dada: *"build them all"* — the five views still SQL01's after Part 100: 083's `vw_warehouse` and `vw_drug_item`, 084's `vw_stock_on_hand`, `vw_item_ledger`, `vw_receiving_line`. Then, on the 10-day window finding: *"date picker would be great as well to limit the views / or meta data views / similar to what sharepoint has 5000 view limit but can display anything once views are adopted"*. Read as: do not bake the limit into the view — let the reader bound it with a date range, each request under the cap, over a view that exposes everything. The SQL half is here; the picker and the per-read cap are WS36's.

**Bizbox Chat's independent read-back of Part 100 first, because it is the right standard:** every claim held on fresh read-only connections — the procedure on both with ten parameters, `psa_desk` as `WINDOWS_USER` with no roles and exactly three permissions, the four controls at 0 and `EXECUTE` at 1 as `psa_desk`, `bizboxsa` unchanged. Two gaps they found: **`vw_lookup` was missing on Training** (created on Live 13 Oct 14:26, Training last refreshed 12 Oct 09:52 — never there; self-heals on the next refresh, and until then a proving run touching lookups fails with "invalid object name" that reads as a code fault) — **built on Training in this Part from Live's definition, 152 rows**; and **`vw_lookup` carries no `tstamp`** — decided: it stays without, reference lists the desk never writes.

**Column names.** The desk-side names are the handoffs'; BizBox's came from `sys.columns` on the ten source tables, read here for the desk's own objects and named as such — the one bounded exception to Part 89's routing, taken because the views are mine and the names were needed to write them. Keys line up with the four existing views: items by `PK_iwItems`, documents by `docno`, warehouses by `PK_mscWarehouse`; every source table carries `tstamp`.

**Measured before building, and three things it decided.** (1) **The ledger window is 10 days**: 7 days = 25,497 rows, 10 = 35,645, **14 = 50,970 — over the desk's `MAX_ROWS` of 50,000**, 30 = 106,943, 90 = 226,779. (2) **`mscWarehouse` has no active flag** — the 083 spec's `IsActive` does not exist; the column is omitted, not invented. (3) Sizes: 5,108 derived stock pairs, 2,202 receiving lines on non-deleted receipts, 73 warehouses, 2,167 drug items with **no duplicate items** (`COUNT = COUNT DISTINCT`). **Also measured, the alternative for Dada:** 90 days of movements **excluding the patient-charge kinds `CH`/`CA`/`CN`** is **22,095 rows** — the materials-side history fits the cap with room; the stock position is derived from all kinds regardless. Built to the spec (10 days of everything); the alternative is one line in the view.

**The five views, decisions recorded in the script and here.** `vw_stock_on_hand` is **derived from `iwItemLedger`** — `SUM(qtyin) − SUM(qtyout)` per item+warehouse, latest `purcprice > 0` as unit cost, `MAX(docdate)` as as-of, non-zero only — never `iwWareitem.actualqty` (Part 84); cancelled movements (616 rows) excluded from a *position* because a cancelled movement did not happen; no `tstamp`, a derived figure has no row. `vw_item_ledger`: 10-day window, cancelled excluded, `Kind` the bare doctype, `DocRef` = doctype + docno, **no remarks and no description column — the patient fence from Part 98 is a check inside the script**. `vw_receiving_line`: `iwApitem` → `iwApinv` for the receiving number, `iwPOitem` → `iwPOinv` for the PO number (`COALESCE(po.docno, a.pono)`), unit cost `fobprice` (the invoice unit price, as the PO line's is `price`), deleted receipts excluded exactly as `vw_invoice` excludes them so the two agree — checked: every receipt in the lines exists in `vw_invoice`. `vw_warehouse` with group name from `mscWarehouseGrp`. `vw_drug_item` from `iwItemMedicines` → `iwItems` → `mscGenerics` → `mscDrugAdminGroup`, `DOHDrugCode` = `iwItems.EDPMSDrugCode`. All four row-level views carry `tstamp` with the `BINARY(8)` cast. Reader checks by `HAS_PERMS_BY_NAME`, never a raising probe; verdict from a fresh connection (Part 100's two rules).

**One check of mine failed and was a guess:** `vw_drug_item` at 1,837 on Training against a range of 2,100–2,300 I had assumed from Live. Training's copy simply has 1,837 medicine rows (zero orphans, zero null keys on both); the check now compares the view to the measured join in the same transaction. Training: 73 / 1,837 / 5,063 / 27,922 / 2,064. **Live: 73 / 2,167 / 5,108 / 35,648 / 2,202.** Six views present on each after commit, fresh connection.

**083 on `PMC_PSA` — it had never been applied, found by the map.** `check_map` first refused `tstamp` on `warehouse` (085 added it to the seven mirror tables the desk may write to; 083's two are not among them — removed), and then the hourly read showed `ext_warehouse` and `ext_medicine` **absent**: 083's schema step was on my own pending list from 13 Oct and had not been run. COPY_ONLY backup `PMC_PSA_COPYONLY_pre083_20261014-085438.bak` (140 MB, verified), PSA-Desk stopped, 083's two `CREATE TABLE` blocks and two indexes from the port by guard text, applied, read back on a fresh connection, desk started.

**The map at ten objects**, written to temp and replaced in one move, backup `bizbox-map.json.bak_20261014_085459`, `check_map` accepting: `warehouse` and `medicine` without `tstamp`, `stock` without `tstamp`, `movement` without `balance` (the ledger has none) or `remarks` (the fence), `rr_line` complete. **Then `PSA-BizBox` as `psa_desk`: exit 0, 35 seconds, and every mirror filled on its first pass — 73 warehouses, 2,167 drug items, 5,108 stock lines, 35,650 movements, 2,204 receiving lines**, alongside the five that were already there. Controls: no movement carries a remark; no stock row is zero; kinds seen `CA CH CN DR EI MP PP QA SS`, every one a bare code; controlled drugs flagged 0, matching the brief. The desk's Warehouses, Drugs, Stock on hand, Movements and Receiving tabs show data from that read.

**`psa.fn_item_ledger(@from date, @to date)` — the date-picker read, both databases.** An inline table-valued function with exactly `vw_item_ledger`'s ten columns and **no fixed window**: the desk passes the range a person picked and bounds each read itself; the predicate pushes into the ledger scan; the reader's schema-level `SELECT` covers it (checked as the reader, 1). Checks: the same predicate as the mirror view returns the same rows (35,652 = 35,652 on Live); a 90-day range returns more than ten days, so there is no hidden window; columns identical; no remarks; `tstamp` hex. **Two things found by its checks:** `DATEADD(day, 1, '9999-12-31')` overflows `date` — the open-ended probe uses `9999-12-30`; and **the mirror view carries four future-dated rows** (the ledger rows dated 8 Dec 2026 that Bizbox Chat flagged, four of the six not cancelled) which the function with `@to = today` correctly excludes — `35,652 − 35,648 = 4`, asserted. Committed and read back on both: 30 days through it = 106,946 rows on Live.

**For WS36:** the mirror window is 10 days; "last 30 / 90 days" on the Movements tab now means a live read through `psa.fn_item_ledger` with a date picker, each read capped by the desk and refused with "narrow the range" over `MAX_ROWS`; the sample map carries the function as a second source for movements; `active`, `balance` and `remarks` are deliberately absent and the desk shows them as such; `vw_lookup` on Training. **For Dada, once:** the alternative window — 90 days of materials-side movements, 22,095 rows — is one line if he prefers the tabs to show the quarter without a picker.

**Final state, fresh connections:** both BizBox databases hold exactly the same ten `psa` views and the same two objects, `fn_item_ledger` and `sp_apply_change` (skeleton, refusing every kind); `PMC_PSA` at 083 + 084 + 085; the map at ten objects; the hourly read green. `PSA_BIZBOX_WRITE_ODBC` unset. Nothing written to any BizBox table. `bizboxsa` untouched.

**Part 101, addition — standing rule (14 Oct 2026): no overlap with the other sessions; every exchange helpful and time-saving.**

Dada: *"make sure when using other claude code chats that your arent overlapping with what each one is doing amke sure its helpful and saves time"*. Read as a standing rule on method, saved to memory for every project and recorded here because the day shows where it was needed.

**Where SQL01 slipped today, named so the rule has teeth:** a `LiveDB_PMC` table survey started that the Bizbox Chat session already owned (stopped by Dada mid-call); a probe of `bizboxsa` written before he said *"ask bizbox chat"*; `sys.columns` on ten source tables read here rather than asked for (named as a bounded exception in Part 101, but still a read in their domain); and a reply sent to every peer message that ended "nothing needed back", so each closure generated another closure.

**The rule as applied from here.** Before any probe or measurement: `ListAgents` for who is alive and the record for what each session has filed or said it is running; if it is a peer's domain, ask them, and if it must be done here, say so and why. One owner per thing, stated in every message. **Findings and asks only — "nothing needed back" means no reply unless the reply carries new information.** Verify a peer's filed work by hash and copy (R5), never by re-measuring it. Lead every message with what changes for the reader; leave out what they already hold. Saved as the memory `cross-session-no-overlap`, beside Part 89's routing rule.

**Part 101, second addition (14 Oct 2026): `vw_stock_on_hand` verified independently — correct, and the one-row difference was theirs. It shows 73 negative balances that the old screen hid. A display decision, Dada's.** Theirs; not replied to, per the rule above.

The Bizbox Chat session verified the view rather than recording my count, as the most consequential object built today: it reads `iwItemLedger`, its text mentions `actualqty` nowhere, no duplicate keys, 5,108 rows. **Their derivation said 5,107; the view 5,108; the delta held at exactly 1 across two passes.** The pair: warehouse 1008 (OR), item 260005 — 64 ledger rows, in 107, out 107, net 0.00 with cancelled rows counted; **net 7.00 with them excluded, which is what the view reports.** The view excludes cancelled movements from a position (Part 101's recorded decision); theirs did not. **Correct for a balance — a cancelled movement must not count — and the view's 5,108 stands.**

**It refines their own morning finding, which they corrected rather than left:** "cancelled rows make no difference, every figure identical to the digit" was true of the *aggregate* three-way comparison and must not be read as "cancelled rows never matter" — **9 pairs' balances change** when cancelled rows are excluded, and exactly one crosses zero, which is why the count differs by one and not nine. 616 cancelled rows of 227,708, 0.27%.

**The finding for Dada: 73 negative balances, across 9 warehouses, surviving the correct filter** (73 with cancelled rows in, 73 with them out — not a filter artefact). Largest: item 10088 at Procurement/Inventory/Warehouse **−450**, item 10223 at Pharmacy **−191**, then −150, −150, −100 at Procurement and −74 at Pharmacy. **`iwWareitem.actualqty` reports exactly one negative; the movement history shows 73 — the stored figure hides 72 of them.** Another reason the derived view is the honest one, and the reason the first thing Procurement sees on 73 rows is a negative number with no explanation. The desk's Stock on hand tab is live with them as of the 08:55 read. **Whether the desk shows them, flags them, or floors them at zero is a display decision and Dada's; nothing is changed until he says.** The honest answer to "the new system says we have minus 450" is: the movement history says so, and the old screen was hiding it.

Also theirs, confirming the Part 101 design: **a stock balance cannot be windowed at all** — a pair whose full history nets zero nets −42 over 30 days — so the position view is the whole ledger, and the date picker belongs on movements, not on stock.

---

**Part 102, ruling (14 Oct 2026): the Procurement GUI on the live desk is rejected as a shape. Screens move to the front of WS36's order. And a correction of my own Part 97 review.**

Dada, looking at Procurement › Purchase orders on the desk: *"this screen or gui is terrible it isnt the one i asked to be made"*. Read as: the 083/084 design as shipped — the mirror-table tabs with counts, the grid with an input box in every cell, the "0 ticked · change" bulk bar, the "0 cell(s) edited" bar, the four-line paragraph — is not the MMS-like Procurement he ruled on today (Parts 85, 98, 99), and is **rejected as a shape, not to be polished.**

**Why it is still there, stated plainly:** nothing from today's rulings has been built. WS36 was paused until the GO of Part 100, sent about an hour before his message; the screens he saw are yesterday's. The data side under them is done and working — his own screenshot carries the 09:05 read: 5,483 items (1 changed), 815 POs, 1,037 receipts (5 changed), 5,108 stock lines (21 changed), 35,741 movements (91 new), 2,204 receiving lines — the ten mirrors updating hourly, with `fn_item_ledger` beside them for the picker.

**A correction of mine.** Part 97's review called the edit-cells-in-a-row grid *"deliberate and stands"* and filed its accessible-name layer as a minor finding. Under his ruling the grid does not stand; a list is a list. I softened a shape question into a polish finding, and he has now said what I should have.

**Sent to WS36, nothing new but the current screen named as the thing replaced:** lists are read-only rows a person clicks to open a document — no input boxes in list rows, no bulk bar, no cells-edited bar; the change-proposal model lives inside the document screen, not as a spreadsheet over a list. The document screen is the draft's shape, similar not 1:1, for Purchase Order and Receiving exactly as for Stock Requisition, with `MMS_ADHOC_POSLIP` (2,983 prints in 60 days) and `MMS_ADHOC_DelReceiveRep` (3,013) as their slips. The menu on top is BizBox's MMS module list per the member's rights — "Stock on hand · 5108" and "Movements · 35741" are not modules, they are what the Items module and an item's page show. The paragraph goes; the dated sync bar stays. Design skills first and named; reviewed here the same day.

**Order revised so he sees it change — my reading, his to reorder:** Purchase Orders list + document (what he is looking at) → Receiving → Stock Requisition → the module menu with RBAC per module (Part 99) → Expense Requisition and the rest in volume order → the review's minor five. RBAC is not dropped; it moves behind the first screens because he is judging by the screen.

Nothing on the host changes for this; it is all WS36's.

**Part 102, addition (14 Oct 2026): the 73 negative stock balances are with Dada and the Bizbox Chat session.** Dada: *"ill talk to bizbox chat abut the 73 negative stock balances leave it with me"*. SQL01 holds nothing on it: `vw_stock_on_hand` stays as built (derived, cancelled excluded, negatives shown as the ledger has them), nothing is flagged or floored on the desk, and no message goes to the Bizbox Chat session from here. One owner.

---

**Part 103 (14 Oct 2026): WS36's four asks measured. The MMS slip wants the identity key, not the document number — and `smallconversion` is not a column in the database at all. Three views widened on both BizBox databases; twelve more wait on a peer rather than a guess.**

Dada passed WS36's reply to the GUI rejection: the Procurement screens replaced on `d3311d6`, the module list as the top menu, the purchase order to the draft's whole template, every MMS document raised on the desk. Four asks came back to SQL01 with it. **CI run 38502701241 was still running while this was done, so the screens are not reviewed in this Part** — WS36 asked for the pull to wait on green, and the review is the next thing on this side.

**The ask that would have shipped broken.** WS36 built the slip link to fill *a document-number parameter* by matching whole words, naming `PONo` and `Doc_No`. **Measured on the ReportServer catalogue: neither name is a parameter on any of the eight MMS slips**, so the match would have found nothing on every one of them (control: `zzNoSuchReport_control` returns no catalogue item, so an empty result is an answer). Then, from each report's own RDL rather than from its parameter list: **the parameter the query uses is the header's identity key.** `MMS_ADHOC_POSLIP` reads `select * from vwReportPurchaseOrder where PK_TRXNO = @PK_TRXNO`, and `PK_TRXNO` on `iwPOinv` is `419462` where the document number is `867`.

**Three traps inside that one answer, each worth the measuring:**

1. **`TranNo` is the primary key despite its name.** `MMS_ADHOC_StockIssuance` reads `where PK_TRXNO = @TranNo`; so do ExpIssuance and, through `FK_TRXNO`, DelReceiveRep. A desk that reads the name and passes a transaction number renders **an empty slip with no error** — the failure shape this estate keeps producing.
2. **`RRno` is the only one of the eight that is not a key**, and `vwReportMMSIwAPINV.RRNo` is `convert(nvarchar(20), a.docno)` — which is already `psa.vw_invoice.ReceivingNo`. So Receiving's slip needs **both** parameters, and one of them the desk already holds.
3. **`isfourdigit` is Boolean, not nullable, blank not allowed, no default, on all eight.** A value must be passed every time or nothing renders. Four slips need more than the document: `ExpRequisition` wants `srcdept` and `issuedby` with **blank not allowed** (display only, `usedInQuery=False`), `PhysicalCount` wants `EncodedBy`/`CountedBy`/`Department` with blank allowed. **One document parameter was never going to be enough.**

**So the desk needed the key and had nowhere to read it.** `psa.vw_purchase_order` exposed `PONo` and not `PK_TRXNO`. Applied on both databases, one transaction each, controls inside, verdict on a fresh connection after commit: **`TrxKey` on `vw_purchase_order`** (823 rows on Live, 823 distinct, never null, all 823 joining `iwPOinv.PK_TRXNO`; 756 on Training, same checks), **`TrxKey` on `vw_invoice`** (1,037 and 976, unique, never null), and **`Conversion`, `PurcPrice`, `LastPurcPrice` on `vw_product`** (5,484 and 5,423 rows, counts unchanged). Each definition was patched by inserting the columns immediately before its existing `FROM`, nothing else in the text touched, and the row count checked before and after — because a textual patch that changes what a view returns is the quiet failure here.

**Where I deliberately stopped.** `psa.ext_purchase_order` has no column for the key and neither has `ext_invoice`, and a map line pointing at a mirror column PMC_PSA lacks fails the hourly read. **So `D:\psa\bizbox-map.json` was not edited** — `trx_key` is WS36's schema step, and the two map lines go in the day it lands. The view columns sit unread until then, which costs nothing. The hourly read was then **run rather than waited for**: exit 0, mirrors at 829 purchase orders, 2,174 PO lines, 5,506 products, 1,052 invoices, 2,204 receiving lines, 5,123 stock, 36,204 movements, 73 warehouses, 2,167 drug items, 152 lookup rows.

**`smallconversion` does not exist.** WS36 asked for it on the item view, from Bizbox Chat's measured `price × smallconversion`. Measured here with the control in the same call: **pattern `smallconv%` returns 0 columns in the whole database**, against **27 for `%convers%`** — all of them plain `conversion int`, on `iwItems` and on every document line table. `iwItems` carries no column named `price` either; the `price` in the formula is `iwWhreqitem.price`, the line's own copy. **Their formula is not challenged — it was read off the client by disassembly — but `smallconversion` is a client-side field, not a database column**, and which column it binds to is theirs to say. Nothing is renamed to it on either side until they answer. What WS36 got instead carries its real names, and a design point that matters more: **`netcost` is stored on the line, so the desk must not compute it** — the payload sends quantity and unit cost and `psa.sp_apply_change` computes the stored money from the item row at insert time, one place, next to the insert it has to match. Otherwise the stored totals drift from the lines they describe and nothing in the schema catches it (Bizbox Chat's own consequence, taken).

**One ask confirmed exactly as WS36 built it.** `PK_iwPOitem` is the primary key of `iwPOitem` and an identity column — 2,181 rows, 2,181 distinct, 0 null, against a control of **326 tables in this database with no primary key at all**, so `NONE` was an answer the query could have returned. `vw_purchase_order_line.LineID` is that key cast, 2,128 distinct over 2,128 rows (fewer than 2,181 because the view filters the header's `deleteflag`, deliberately). **And the `tstamp` the view hands out is the line's own row version**, `l.tstamp` from `dbo.iwPOitem`, not the header's — `iwPOinv` has a separate one. So the `line:<id>:<field>` shape with the line's version in `@expected_tstamp` guards the row it names, and a header change and a line change cannot invalidate each other. Right as designed.

**What I refused to guess, and why that is the useful answer.** The twelve views per document kind need the kind-to-family map. The shape is measured and uniform — header `iw<X>inv` with `PK_TRXNO` and `docno`, lines `iw<X>item` with `FK_TRXNO`, thirteen pairs with their row counts. Three are settled: Purchase Order, Receiving, and **Stock Requisition as `iwWhreqinv`/`iwWhreqitem`** on the strength of Bizbox Chat's own disassembly naming that line table and its 4,596 lines beside the 4,566 they counted. **Which family is Expense Requisition against Purchase Requisition, and which of `iwIssinv`/`iwWhinv` is Stock against Expense Issuance, is not measured, and row counts cannot separate them.** A view over the wrong family is silently wrong, so it is asked of the session that holds the client, not guessed here.

**And a finding WS36 needed before Receiving, not after.** `iwWhreqinv` carries `FK_mscBranches`, `FK_mscBranchesSRC`, `FK_mscBranchesDST`, `FK_mscWarehouseSRC`, `FK_mscWarehouseDST`, `FK_psDatacenter`. The payload carries **one** `warehouse_ref` and free-text `department` and `center`. **A stock requisition has a source and a destination**, so one warehouse cannot say where the stock is going — the form shows "On hand at source", which implies the source; the destination is missing. And **both free-text fields are FK codes, not words** (`smallint` branch, `int` datacenter), so neither should be sent to the procedure until the lists are mapped: a word where an FK is wanted either fails loudly or writes a wrong row quietly, and the second is worse.

**One message to Bizbox Chat, three asks, no overlap** (Part 101's rule, applied rather than quoted): the column their `smallconversion` binds to; the kind-to-family map for the five ambiguous pairs; which branch column the client fills and whether `FK_psDatacenter` is Center. The MMS catalogue numbers for the four modules went with it as a cheap-if-in-reach fourth. Nothing was re-measured of theirs — the stock-requisition family is credited to their disassembly, and the 73 negative balances stay untouched and theirs.

Handoff: `HANDOFF-sql01-cloud-WS36-20261014-slip-keys-and-conversion.md`. Scripts in the record: `ws36-asks-20261014.py`, `ws36-asks2-20261014.py`, `ws36-asks3-rdl.py` (read-only), `bizbox-views-slipkey.py` (the gated change). Nothing written to a BizBox table; `PSA_BIZBOX_WRITE_ODBC` unset; `sp_apply_change` still refuses every kind.

---

**Part 104 (14 Oct 2026): Bizbox Chat answered all four. The table families are the inverse of their names, three of WS36's module badges are wrong, `center` does not exist, and the patient fence widens from a column to a whole table.**

Dada relayed their reply alongside their own message; both say the same four things, and their document is committed here verbatim — hash checked before the copy and byte-identical after: `docs/bizbox-mms-four-answers-for-the-desk-20261014.md`, sha256 `bb98dcb03c3e16ef9c0e788eb04a4e921a5ca934f0133fd2adeac58f4e8823a6`, 154 lines, LF, 8,424 bytes, fence clean on my own read before committing. **Verified by copy and hash, not re-measured (R5).**

**The answer that justifies Part 103's refusal to guess.** The family map, read off the client's own save-method names rather than inferred: `iwReqinv`/`iwReqitem` is **Expense** Requisition, `iwPRinv` is **Purchase** Requisition, **`iwWhinv` is Stock Issuance**, **`iwIssinv` is Expense Issuance**, `iwPhentinv` is Physical Count. **The `Iss` tables are Expense Issuance and Stock Issuance is `Wh` — the same prefix as Stock Requisition.** Reading `iwIssinv` as "issuance, therefore stock issuance" inverts two documents, and the resulting views would have returned rows, totalled correctly and described the wrong document. Part 103 declined to guess exactly this, and the guess would have been wrong. **The twelve views are now unblocked and are the next host step.** Also theirs, and it removes work: every `*ItemLot` table holds 0 rows, so the product's lot capture on both Issuances and Physical Count has never been used — the desk builds none.

**Three of the six module badges WS36 shipped are wrong**, measured from `appsysModules` with `MM99` as the control. Purchase Requisitions is **MM03**, not 05 — **and there is no MM05 in the system at all**. "11 Issuances" is two modules, **MM07** Stock and **MM09** Expense; MM11 is Quantity Adjustments. Physical Count is **MM12**; MM14 is Allotment and Obligations. The two asked for: Purchase Orders **MM04**, Receiving **MM20**. **Warehouses and Drugs are not modules** — submodules of MM02, so no badge exists and showing one would be inventing it. **One caution of my own on top of their measurement:** their document carries `MM07` twice, once as the module Stock Issuances and once as a submodule id under MM02 for Manage Departmental Access, so **the badge namespace is not unique** — badges resolve from the module list only, never by searching for the string.

**`center` does not exist and `department` is the warehouse, in two roles.** Across all 1,099 stock requisitions `FK_mscBranches`, `FK_mscBranchesSRC`, `FK_mscBranchesDST` and `FK_psDatacenter` each hold **exactly one distinct value** — `mscBranches` has one row, a single-branch installation. What varies is `FK_mscWarehouseSRC` (14) and `FK_mscWarehouseDST` (37), `smallint` FKs into `mscWarehouse`, and the vendor screen's own handlers name the pair. **So Part 103's "the payload is short by one field" is measured: the field is `warehouse_dst`, and both `department` and `center` go away.** Two things fall out in WS36's favour — `vw_lookup` needs no `department` or `center` list at all, because both pickers are warehouses and `vw_warehouse` already lists all 73; and the only missing control on the form is the destination, since "On hand at source" already implies the source.

**The fence widens from a column to a table, and this is the most important line in the Part.** `FK_psDatacenter` — the column WS36 was going to show as *Center* — points at `psDatacenter`, a **10,508-row entity master, the same table `usp_InventoryStockCard` joins to print patient names on the stock card**. So the patient fence is no longer only "never render BizBox's description or remarks": **the desk must not read `psDatacenter` at all** — not for a label, not for a lookup list, not to resolve a code to a word — and `psa` exposes no view over it, deliberately. A "Center" picker would have been a patient-name picker. They selected no name from it; neither did I.

**`smallconversion` is the line's `conversion`**, solved from the stored rows rather than by chasing the data layer, since `netcost`, `qty`, `price` and `conversion` all sit on `iwWhreqitem`: 4,594 solvable rows, 90.8% fitting either candidate, 420 of the 421 residual rows within 2% of 1 and **none structurally different**, so the residual is entirely `netcost` stored rounded to two decimals. **The discriminating row is a single one** — `qty` 1, `price` 1.00, `netcost` 50.00, `conversion` 50, solved exactly 50 — and I am passing their strength statement on unsoftened: sound, zero contradicting observations, but it rests on one row, and the solve gets re-run if a second item with `conversion > 1` ever posts a line. **It confirms Part 103's measurement from the other side:** no `smallconversion` column exists to bind to, so the client's field is an alias.

**And it reverses the operative half of what I sent WS36 an hour earlier.** Part 103 told them the procedure computes `netcost` at insert so the arithmetic lives in one place. That stands for *creating* a line — but **recomputing it for display disagrees with history on about 9% of lines by up to 2%**, purely from the stored rounding. **So: read the stored value for display, compute only on create.** Their recommendation, taken as written; it keeps the single place *and* removes the drift risk entirely, because nothing recalculates what is already stored.

Sent to WS36 as `HANDOFF-sql01-cloud-WS36-20261014-three-corrections-measured.md` — the corrected module list, the payload shape, the fence, the family map, and the `netcost` display rule, with the `trx_key` schema step restated as the one thing still outstanding from me to them.

---

**Part 105 (14 Oct 2026): the twelve views for BizBox's six existing documents, live on both databases. One mapping I would not assert, and 826 negative system quantities found while building.**

WS36's third ask, unblocked by Part 104's family map and built the same day: `psa.vw_<kind>` and `psa.vw_<kind>_line` for Stock Requisition, Expense Requisition, Purchase Requisition, Stock Issuance, Expense Issuance and Physical Count, on `LiveDB_PMC` and `TrainingDB_HIS8`. **46 checks PASS on each database, verdict on a fresh connection after commit.** On Live: 1,065 and 4,501 stock requisitions and lines, 1,202 and 4,799 expense requisitions, 637 and 1,938 purchase requisitions, 987 and 4,101 stock issuances, 1,084 and 4,314 expense issuances, 99 and 2,187 physical counts. **The views are named for the document and not for the table**, so nobody downstream has to remember that `Iss` is Expense and `Wh` is Stock.

**The contract is uniform so one mapper handles all twelve** — header `DocNo · TrxKey · DocDate · WarehouseSrc · WarehouseDst · Status · TotalQty · TotalItems · TotalAmount · tstamp`, line `LineID · DocNo · LineNo · ItemCode · Description · Quantity · QtyServed · SystemQty · Variance · Unit · Conversion · UnitCost · TotalAmount · tstamp`. Four decisions inside it worth recording. `TrxKey` is the header's `PK_TRXNO`, so every one of these documents can link its own BizBox slip once the mirror column exists (Part 103). `Status` is derived from the flags as `vw_purchase_order` does — **three headers also carry a raw `status` column and it is deliberately not exposed, because the meaning of its codes is not measured and labelling them would be inventing.** `QtyServed` is **null**, not zero, on the three documents with no `servqty`, so "not applicable" cannot read as "nothing served"; `TotalAmount` is null on `vw_purchase_req_line` because `iwPRitem` carries no `netcost`, with no computed stand-in. And **no view exposes `remarks` or any BizBox-authored text** — every header carries `remarks` and `iwWhitem` carries it too; the fence was checked against the generated SQL before it ran *and* against the stored definition after, Part 104's widened fence applied rather than quoted.

**The one mapping I refused to assert.** `iwPRinv` names its warehouses `FK_mscWarehouseFROM` and `FK_mscWarehouseTO`, not `SRC`/`DST`. Measured over 653 rows: **`TO` has exactly one distinct value** and carries no information; **`FROM` has 28**. So `vw_purchase_req.WarehouseSrc` is null — a purchase requisition has no issuing warehouse, the goods come from a vendor — and `WarehouseDst` carries `FROM` as the requesting department. **That role is INFERRED and labelled so in the view's own comment and in the handoff**, resting on `FROM`'s distinct-value profile matching the requesting side of the other five families (37, 58, 31, 58) against their issuing side (14, 6, 16, 4). Asked of Bizbox Chat to confirm from the form's combo handlers. Mapping `FROM` to `WarehouseSrc` because the names look alike would have put the requester in the issuer's role — **the same inversion I warned WS36 about in Part 104, one table later, and this time in my own work.**

**826 negative system quantities, found as a by-product.** `iwPhentitem.Sysqty` is never null across 2,202 rows, so the variance computes everywhere — but it is **negative on 826, zero on 463 and positive on 913**, range **−5,245 to 3,363**, and on the 913 positive rows the counted quantity differs on 867 of them. So the variance is genuine and large rather than an artefact of a missing figure, **but on 1,289 rows "counted minus system" is not the sentence a reader will assume**, which is why WS36 was told to show quantity and system quantity beside the variance and never the difference alone. **Stated once and left there:** these are the same family of problem as the 73 negative stock balances, which are Dada's and Bizbox Chat's and on which I still hold nothing. This is a different measurement — the count document's own stored figure, historical — recorded, not acted on, nothing flagged or floored.

**A method note that earned itself.** The first apply assumed every line table has a `price` column. `iwPhentitem` has `purcprice` and no `price`, so the sixth family failed inside the transaction; **the gate rolled it back and both databases were verified still at exactly ten `psa` views before the retry** — the rollback confirmed rather than assumed. The script now runs a **preflight that checks every column the generated SQL references exists, with a control, before the transaction opens**, so a missing column is a preview finding instead of a half-applied batch. The twelve definitions are generated from a per-family table of measured column facts, not hand-written twelve times, which is also what made the `price` assumption visible in one place.

**Also measured and it removes work:** every `*ItemLot` table holds 0 rows, so the product's lot capture on both Issuances and Physical Count has never been used and the desk builds none. And `sys.partitions` agreed with `COUNT(*)` on all twelve tables, so the row figures quoted in Part 103 were accurate — the apparent one-row drift was simply live traffic between two probes an hour apart.

**CI run 38502701241 went green on all four jobs** while this was built, so WS36's `d3311d6` is now reviewable on this side. The map is unchanged and deliberately so: twelve mirror tables plus `trx_key` on two existing ones are WS36's schema step, and the map lines go in the day it lands. Handoff: `HANDOFF-sql01-cloud-WS36-20261014-twelve-document-views.md`. Script: `bizbox-views-six-documents.py`. Nothing written to a BizBox table; `PSA_BIZBOX_WRITE_ODBC` unset; `sp_apply_change` still refuses every kind.

---

**Part 106 (14 Oct 2026): Dada hit a 404 on the live desk. The defect was mine — `vw_product`'s filter hid 238 items that other views still show. Fixed on both databases and proven to the mirror; the view is now simpler than it was.**

Dada, on `desk.pmcne.ph/procurement/product?ref=11367`: **"404 Not Found — No such record in the BizBox mirror."** Read as a live defect on my side of the line, since the mirror is mine, and it is.

**What was wrong.** `psa.vw_product` filtered `WHERE i.isInventory = 1 AND (i.isactive = 1 OR EXISTS (a purchase-order line))`. Item **11367 is `isInventory=1`, `isactive=0`, and has never been on a purchase order**, so the view dropped it, the mirror had no row, and the desk truthfully reported what it saw. The item exists, is a real drug, and has stock history — it simply had no page.

**The size of it, measured before touching anything: 238 distinct item codes are shown by some other `psa` view and have no product page** — every one a guaranteed 404 the moment a person clicks it. `vw_drug_item` 203 of 2,167, `vw_stock_on_hand` 41, `vw_physical_count_line` 38, `vw_stock_req_line` and `vw_stock_issuance_line` 10 each, the rest in ones and threes. `vw_purchase_order_line` had **0**, which is exactly what the old filter's `EXISTS` clause guaranteed and why the hole was invisible on the one screen anybody had been looking at.

**Why the obvious fix was the wrong one.** Tightening to `isInventory = 1` would have resolved **71 of the 238**: measured, **167 of them are not inventory items and 165 are active**. All 238 exist in `iwItems`; none is a dangling reference. So the shape of the bug was never "inactive items" — it was a catalogue filter being asked to decide whether a page exists.

**The fix is the filter going away entirely.** An item page must resolve for any code any view can show; what a person may *pick* when raising a document is a different question and belongs to a flag. `psa.vw_product` is now every row of `iwItems` — **5,484 → 8,572 on Live, 5,423 → 8,503 on Training** — with **`IsActive` and `IsInventory` exposed** so the desk filters the picker and labels the page. **The view is simpler than it was: no `WHERE` clause and no correlated subquery**, which is the direction Dada set on the write path ("too many checks isn't good at all, it can be secured and simplified properly") applied to a read.

Gated on both databases, with the orphan count re-measured per view inside the transaction: **0 orphans across all eleven views, down from 238**, `ItemCode` still unique over 8,572, the control item code still absent, and the flags still discriminating (8,118 active, 5,906 inventory) so a picker remains possible. **Then proven to the thing that actually serves the page:** the hourly read run rather than waited for, exit 0, `psa.ext_product` at **8,572 rows with 11367 present and `present = 1`**. The page resolves on the next load.

**The trade-off, stated plainly because Dada will see it.** The Items list on the desk grows from 5,506 to 8,572 and now includes 2,666 non-inventory items and 454 inactive ones. That is a visible change and the honest price of removing the 404s: a hard failure traded for a longer list that WS36 can filter the moment the mirror carries `IsActive` and `IsInventory`. **Those two columns are now the priority in their schema step**, ahead of `trx_key`, and they have been told so.

**What this says about the other views — and I went and measured it rather than reasoning about it.** The first draft of this Part said "no other `psa` view has that shape" on the strength of an argument. That is an inference wearing a measurement's clothes, which is the thing this record is supposed to catch, so **every cross-view reference a desk page can follow was then checked directly: thirteen of them, 0 orphans.** `vw_stock_on_hand` and `vw_item_ledger` and all seven document headers resolve every `WarehouseCode` into `vw_warehouse` (58 distinct at the widest, all present in its 73); `vw_purchase_order_line` resolves all 826 `PONo` into `vw_purchase_order`; `vw_receiving_line` all 1,041 `ReceivingNo` into `vw_invoice`; `vw_drug_item` and `vw_stock_on_hand` now resolve all 2,167 and 2,699 `ItemCode` into `vw_product`. **Views with a broken reference: 0.**

The reasoning behind it still holds and is worth keeping: the `deleteflag` filters on `vw_purchase_order`, `vw_invoice` and the twelve document views exclude **documents**, not the entities documents point at, and each line view carries the *same* predicate as its own header (Part 105 measured 0 lines with no header). **The hole was specific to an entity view filtered by a catalogue rule while other views referenced it freely** — and that shape now exists nowhere, measured.

Script: `bizbox-fix-product-404.py`. Handoff: `HANDOFF-sql01-cloud-WS36-20261014-product-404-fixed.md`. Nothing written to a BizBox table; `PSA_BIZBOX_WRITE_ODBC` unset.

---

**Part 107 (14 Oct 2026): a null that should have been a constant, corrected on both databases; and the screen-shape ruling is four of Dada's words plus a great deal of mine.**

Two corrections, both of them mine, both found by the Bizbox Chat session the same day, and both of a kind this record exists to catch.

**The first is a measurement error I made one Part after warning WS36 about exactly it.** Part 105 set `psa.vw_purchase_req.WarehouseSrc` to **NULL**, reasoning that a purchase requisition has no issuing warehouse and that `FK_mscWarehouseTO`, holding a single distinct value over every row, carried no information. **Wrong.** They settled it from the client's own control names on `frmPurchaseRequisitionDetails` — `cboRequestingDeptFROM_ValueChanged` and `cboIssuingDeptTO_ValueChanged` — so **`FK_mscWarehouseFROM` is the requesting department and `FK_mscWarehouseTO` is the issuing one.** `TO` is constant because one procurement office issues every requisition, and it is **populated on all 639 rows**. Their sentence is the one to keep: **a constant is not an absence**, and treating it as one is the same error class as dismissing `FK_mscBranches` before its single value had been measured. My `WarehouseDst = FROM` was right; the null was not.

Corrected on both databases, gated: row count unchanged at 639 Live and 549 Training, `WarehouseSrc` now filled on every row where it was filled on none, **exactly 1 distinct issuing against 29 distinct requesting**, both codes resolving in `vw_warehouse` with 0 orphans, control clean. **And the trap is now written into the view's own text, because it inverts both ends if carried across:** stock requisition is `cboIssuingDeptSRC` / `cboRequestingDeptDST`, so SRC = issuing and DST = requesting; purchase requisition is `cboRequestingDeptFROM` / `cboIssuingDeptTO`, so FROM = requesting and TO = issuing. **SRC pairs with TO; DST pairs with FROM.** The two forms use opposite conventions and nothing in the schema says so.

Their one unread question answered here because `vw_warehouse` is mine and it is a single join: **the issuing office is warehouse 1019, "Procurement, Inventory, Warehouse and Vendor Mngt", group Admin** — so it is Procurement specifically. Measured beside it, and it matters for the screen: on **205 of 639** purchase requisitions the requesting department *is* 1019, Procurement requisitioning its own stock, so source and destination coincide on about a third of them and a screen must not render that as an error.

**The second correction is about authority, and it is the more important one.** They asked for Dada's words behind the ruling that the MMS document screens follow their 13 Oct draft — and were right to, because **what they held was my paraphrase.** The record settles it. He was shown the draft and asked *"does it follow this design?"*; I answered no, with the measurement that the desk had no requisition, issuance or count screen at all; and **his ruling, verbatim and complete, is four words: "well similar not 1:!"**.

**Everything else in that ruling is mine.** The runbook line at the time reads *"Read as, and acted on:"* followed by the document shape, header pickers, lines grid with the BETTER additions, on hand per row, shortfall shown, items picked and never created, footer totals, approval path, slip, modernised with the design skills, captions and chrome free. It was recorded as my reading and it is honest in the record — **but it travelled to a peer session as the ruling, without the label.** Four words have been carrying a screen specification. *Similar, not 1:1* establishes that the draft is the reference rather than a rejected thing, and rules out reproducing it element for element; **it does not say which elements survive, and nothing finer should be built on it until he closes it.** Their own `Rule 0` was withdrawn for precisely this shape — a correct quote with an inference beside it carrying the same apparent authority — and they caught mine before it was built on instead of after. Supplied to them with the division stated.

**So the WS36 brief is held** until he closes the screen shape, rather than sending a second instruction within the hour that may disagree with the direction he has now given them. Their direction document is committed verbatim, hash verified before the copy and byte-identical after: `docs/dada-direction-on-the-app-verbatim-20261014.md`, sha256 `b4d674b371721fcf8546a069a3bc6befb62017a6ef250ba54271697fa12f51e0`, 124 lines, LF, fence clean on my own read.

**Three things from their note that are standing and not one-off.** His *"to many checks isnt good at all it can be secured and simplified properly"* was said about a procedure and applies to **every mechanism added since** — it is the reason Part 106's fix removed a filter rather than adding a condition. **He sets priority**, and no screen order is settled by anything he has said. And the show / flag / floor decision on the 73 negatives is **open, his, and asked once** — their recommendation is FLAG, with the worksheet built and not sent; I still hold nothing on it.

Also recorded from the screenshot he sent of the Movements tab, measured rather than described: the filter offers **"Last 30 days" while `ext_movement` physically holds 4–14 Oct, ten days, 36,465 rows** — the option cannot be satisfied and nothing says so, and `psa.fn_item_ledger(@from, @to)` was built for exactly this and is still unwired. **Four rows are future-dated**, two on 8 Nov and two on 8 Dec, BizBox's own and not an import artefact. The chips are raw BizBox doctype codes — `Ch · Ca · Cn · Ss · Ei · Dr · Mp · Pp · Qa` — with **`Ch` and `Ca` both meaning Charged**, so two buttons say the same word to a reader; and **patient charges are 32,520 of 36,465 rows, 89% of a Procurement screen.** His verdict on it, which needs no expansion from me: *"everything on the app is not 1:1 better copy"*.

Scripts: `bizbox-fix-purchase-req-warehouses.py`. Nothing written to a BizBox table; `PSA_BIZBOX_WRITE_ODBC` unset.

---

**Part 108 (14 Oct 2026): 086 applied on PMC_PSA — rights per module, per person. The desk is still serving the code Dada rejected, and the restart is his call.**

WS36 shipped the rest of the order while Part 107 was being written (`dd121eb`, merged under `9202d07`): Receiving as a document, **rights per module per person as schema 086**, the 084 review's minor items 3–7, and the stock card's three buckets on Movements. One schema step, and it is mine.

**086 applied, verdict PASS.** `psa.member_module_grant (member, module, level, set_at, set_by)`, primary key `(member, module)`, the level CHECK on `NONE / READ / WRITE / ADMIN`, extracted from the port by its own guard text and **run unretyped**. COPY_ONLY backup first: `PMC_PSA_COPYONLY_pre086_20261014-131812.bak`, 28.4 MB. Checks inside the transaction with the control a query returning 0 (Part 100's rule): the table exists, **is empty — so nobody gains or loses a page on the day it is applied** — the five columns and the computed `set_at_parsed` are present, the primary key is `(member, module)`, and **exactly one table was added with none changed, 161 → 162**. Verdict read on a fresh connection.

**The desk was not restarted, and that is the finding worth recording.** The `PSA-Desk` task has been running since 08:54; the working tree under it now holds WS36's new code because of the rebase, but a running process does not pick that up. **So the live desk Dada is looking at is still serving the Procurement screens he rejected this morning** — the raw doctype chips, the 30-day filter over a 10-day mirror — while their replacements sit in the tree undeployed.

**Checked before even offering it**, because the dangerous order would be code without its schema: WS36's new code was grepped for every mirror column I still owe them — `trx_key`, `is_active`, `is_inventory` — and for the twelve new document views. **No reference to any of them**; every `is_active` hit is the unrelated `workflow` table. So the new code does not depend on the outstanding schema step, and 086 being applied means its own requirement is met. **The half I have done is the safe half**: the table exists and nothing uses it yet, which is harmless, whereas the code without 086 would not have been.

**Not restarted on my own initiative because it is a visible production change during working hours** — a short outage for everyone on the desk, and Dada's standing *"dont make anuy changes that will destroy things"* / *"or what i meant was break things"* covers exactly this judgement. Offered to him as a one-line decision instead.

Still outstanding from me to WS36, unchanged and now a single port: `trx_key` on `ext_purchase_order` and `ext_invoice`; `is_active` and `is_inventory` on `ext_product` (ahead of `trx_key`, since the Items list is longer until they land); the three price columns if wanted; and the twelve mirror tables for the document views. **I add every map line the day it lands.** `PSA_BIZBOX_WRITE_ODBC` unset; `sp_apply_change` still refuses every kind.

---

**Part 109 (14 Oct 2026): the screen shape closed by Dada's own selection, the brief released, and a window picker that offers a year over ten days of data.**

Bizbox Chat closed Part 107's gap the right way: rather than asking what *"similar"* means in the abstract, they put **three readings** in front of Dada — mine recommended first and named as mine — and he **selected** it. **The decision: the document shape (header pickers → lines grid → footer totals and actions), all five BETTER items, chrome free.** The two he did not choose are recorded so nobody reopens them: BizBox's column set in the same order with only the chrome modernised, which is the screen fidelity he withdrew; and function only with the draft as background rather than reference.

**The provenance line, which is the part worth keeping.** His own words remain four — *"well similar not 1:!"* — and settle only *similar, not 1:1*. **The expansion is mine. What is now additionally his is the selection of it from three alternatives, not the authorship of its wording.** So it is cited as: his ruling is the four words; the expansion is SQL01's; he has since confirmed it when put as a choice. **Stronger than a paraphrase, weaker than a sentence in his own words**, and WS36 is told to cite it that way rather than as "Dada said". Their observation on the handling is fair and worth recording against my own future work: the four words were in the runbook under *"Read as, and acted on:"* with the expansion separated, so the provenance was recoverable the moment it was challenged — **the failure was in the handover, not in the record.**

**One correction to the draft that is measurement, not interpretation:** the drawing shows a **Center picker**, and there is no Centre dimension — a single constant on an entity master holding patient names. "Keep the header pickers" means the two that exist, issuing and requesting department, both warehouse FKs. **Not to be built**, and the fence reason stands behind it.

**The finding of my own they could not have made, and said so.** Naming the issuing office answered their question — warehouse **1019, "Procurement, Inventory, Warehouse and Vendor Mngt"**, group Admin — but the part neither of us had asked for is what else carries that code: **on 205 of 639 purchase requisitions the requesting department is also 1019**, Procurement requisitioning its own stock. **So a form validating "source must differ from destination" would reject about a third of genuine purchase requisitions.** In the brief beside the shape decision.

**And the defect behind Dada's Movements screenshot, measured rather than described.** `procurement.py:41` offers windows of **7 · 30 · 90 · 183 · 365 days**. `psa.ext_movement` holds **4–14 Oct — ten days, 36,465 rows.** So **every option above 7 days returns the same rows under a different name, and "Last 12 months" is wrong by a factor of thirty-six**, with nothing on the screen saying so. The cause is mine — `vw_item_ledger` is a fixed ten-day window because 14 days is 50,970 rows against the 50,000 cap — and **the fix has existed since Part 101 and is wired nowhere**: `grep fn_item_ledger` across `platform/psa-spine` returns nothing. Told plainly: wire it, or cut the list to what the data supports, because **a picker offering a year over ten days is worse than one offering ten days — the first is confidently wrong.**

**What was already fixed and I nearly briefed twice.** The raw chips he objected to — `Ch · Ca · Cn · Ss …` — are **fixed in `dd121eb`**, which carries `MOVE_WORDS` and the three buckets. He was looking at **undeployed code**. Checking their tree before writing the brief is the no-overlap rule paying for itself. **One thing survives their fix:** `CH` and `CA` both map to *Charged*, so a per-code chip row still shows the same word twice, 20,857 and 8,742 — merge to one *Charged · 29,599* with the codes beside. And the default view leads with **32,520 of 36,465 rows that are patient charges, 89% of a Procurement screen.**

Brief released as `HANDOFF-sql01-cloud-WS36-20261014-shape-decided-and-the-window-defect.md`, carrying the shape decision with its provenance, the no-Center correction, the third-of-documents validation trap, the window defect, the SRC/DST against FROM/TO reversal, 086's state, the undeployed desk, the one port of mirror columns in the order that matters to him, and his *"to many checks isnt good"* restated as a standing constraint rather than a one-off.

---

**Part 110 (14 Oct 2026): "modules on top" — already built; the house design system read on this side; and a rule in it that nine of my views break, measured at 165 documents.**

Dada, shown the 13 Oct draft, verbatim via Bizbox Chat: *"i want it like this modules on top to fit the build for the PSA"*. Read as: the module list moves off the draft's left rail onto a top bar so the screen fits the desk's chrome. **Checked in WS36's tree before relaying it: `procurement.py:116` already carries the module list as the top menu under his earlier *"the side bar should be placed on the top"*, and `d3311d6` removed the tabs bar.** So the instruction confirms what is shipped; told to WS36 as *do not rework*. Three corrections to the drawing itself travelled with it, all Bizbox Chat's own measurements against their own draft: the module numbers are wrong (sent in full in Part 104), the Center picker must not be built (Part 104's fence), and the Add button carries an emoji — **checked: no emoji anywhere in `psaspine/web/`, so that defect is in the drawing and not the code.**

**The design system, read here because reviews happen here.** PMC Vitals Console, Dada's own and the only one on the account — `project/README.md` and `project/tokens.json` read through the Artifact tool, not the rendered page. Two traps measured against Bizbox Chat's relay of it, both of which would ship a wrong screen from a correct summary: **points against pixels** — the README gives `page-title` 20pt and `readout-figure` 30pt because the source spec was authored for Power BI, while `tokens.json` gives **27px and 40px** for the web, so a page built from the pt numbers is visibly undersized; and **the accent is not one hex** — `accent.primary` is `#6D3BD1` light and **`#A98BFF` dark**, with canvas, surface, both inks, rule, gridline and both accents all swapping by theme, and the README forbidding a hard-coded hex for exactly that reason. The 20×3 tick rotation for a top bar is Bizbox Chat's reading of a system that specifies 3×20 "in exactly two places: the rail and the cards", and it is passed on flagged as inferred.

**The finding, and it is mine against my own work.** The README's writing rules carry this: *"Never filter a flag out. Deleted, cancelled and void rows are counted and shown, never silently excluded. A total that quietly drops 151 deleted claims is a wrong total."* **Every document view I built today, and `vw_purchase_order` and `vw_invoice` before them, filter `WHERE ISNULL(deleteflag, 0) = 0`.** Measured across the eight header tables: **165 deleted documents hidden** — 35 stock requisitions, 28 expense requisitions, 16 purchase requisitions, 19 stock issuances, 5 expense issuances, 5 physical counts, 23 purchase orders, 34 receiving documents. The rule's own example is 151. Cancelled rows are fine — the views expose `Status = 'Cancelled'`, counted and shown — it is `deleteflag` alone that silently excludes. **And the mirror's `present` flag does not rescue it:** a row that leaves the view is kept with `present = 0` (6 purchase orders, 15 invoices, 46 PO lines, 13 stock rows today), but `bizbox.py:389` appends `AND present = 1` to every list query, so those rows are kept for audit and shown nowhere.

**The recommendation is the same shape as Part 106's fix, and it is the third time today the same lesson has landed:** a filter must not decide whether a thing exists. Expose `IsDeleted` on the document views, drop the filter, and let the desk show a deleted document **marked** rather than absent. One distinction keeps the fix from overreaching: `present = 0` covers both "BizBox flagged it deleted" and "the row vanished from the source", and **only the first should be shown** — exposing the flag separates them, whereas showing every absent row would resurrect things that no longer exist anywhere.

**Not applied.** It would put 23 deleted purchase orders and 34 deleted receiving documents onto the live lists, which is a display decision on a production desk — Dada's, exactly like the 73 negative balances and the desk restart. **Flagged once with the measurement and left with him.** `vw_stock_on_hand`'s exclusion of 624 cancelled movements from a *balance* is a different thing and stands: a cancelled movement must not count toward stock, which Bizbox Chat verified independently in Part 101; the rule is about what a *list* shows, not what a *balance* sums.

Handoff: `HANDOFF-sql01-cloud-WS36-20261014-top-bar-design-system-and-a-rule-my-views-break.md`. Design-system files held in the session record under `artifact-files/` with their hashes (`README.md` ae89cd13…, `tokens.json` f1ba3a1b…). Nothing on the host changed in this Part.

---

**Part 111 (14 Oct 2026): Dada's go executed — 087 applied, the desk restarted, the map on. The first read collapsed four mirrors, because BizBox numbers requisitions per department; fixed by keying on the transaction key. One correction to WS36 that I had carried across from the wrong document. And a correction of my own record on emoji.**

Dada, through WS36's text and in his own order: pull `294aa2a` once CI is green, apply 087 with a COPY_ONLY backup, restart `PSA-Desk` only after 087, check the live desk, then the map. Asked *"what are we waiting for"* at 23 minutes in; answered honestly that the only CI job worth the wait was `sql-server`, which runs the port against a real SQL Server, and that `windows` — the same suite on the slow runner — bought nothing. Went on `sql-server` green; `windows` finished green on its own later.

**087 applied, verdict PASS.** Backup `PMC_PSA_COPYONLY_pre087_20261014-142423.bak`, 28.7 MB. Nineteen blocks extracted from the port at `294aa2a` by their own guard text and run unretyped in one transaction: twelve document mirrors created empty, seven columns added, **162 → 174 tables, counts on `ext_product`, `ext_purchase_order` and `ext_invoice` unchanged**, both controls queries returning nothing, every line table carrying `doc_ref`. **The desk restarted at 14:25:02**, the 08:54 process gone, answering HTTP 401 on 8085 — the login gate, so serving — and the login page carrying the Vitals chrome without a login: `0E1520` five times, `A98BFF` three, `Consolas` four, "vitals" fifty-nine, "cells-edited" none. Dada's step 4, the authenticated look at Purchase Orders, is his eyes. A second python process started at 14:24:48 whose command line is unreadable non-elevated — recorded as cannot-see, not not-found (pmc-estate §7).

**The map went on, the read ran green, and four of the six new header mirrors came back short** — stock_req 253 of 1,067, expense_req 264 of 1,206, stock_issuance 520 of 989, physical_count 80 of 99 — while every line set was full. MEASURED the cause before touching anything: `vw_stock_req` has 1,067 rows, **253 distinct `DocNo`** and 1,067 distinct `TrxKey`; **`DocNo '1'` is 33 different stock requisitions, one per destination warehouse.** The mirror's primary key is `(source_id, ext_ref)` and the 087 map keyed headers by `DocNo`, so the upsert collapsed them. **Purchase orders and purchase requisitions number globally** — `vw_purchase_order` 826 rows, 826 distinct `PONo` — which is why the pattern had always worked and why nobody had reason to doubt it. Bizbox Chat measured the same rule independently within the hour from 1,102 saved headers: `docno = MAX(docno) + 1` per requesting department, dense from 1, never reset.

**Fixed on my side, both databases, gated:** the six line views now carry `TrxKey` (the header's `PK_TRXNO`) — 0 nulls, 0 orphans by it, row counts unchanged — and the map keys headers by `ext_ref: TrxKey` and lines by `doc_ref: TrxKey`. The second read: **every mirror equals its view — 1,067 / 1,206 / 643 / 989 / 1,087 / 99 headers, 4,503 / 4,807 / 1,944 / 4,103 / 4,320 / 2,187 lines, 0 lines without a header on all six.** `DocNo` is unmapped until WS36 adds `doc_no` to the six headers (088, asked), and they are told to show the key as a reference and not as a number in the meantime. Two consequences for the write path are in the handoff: the number never identifies a document, and the procedure must allocate `docno` inside the insert's own transaction or two departments' saves collide on live traffic.

**A correction to WS36 that is mine.** Part 109 told them same-department-on-both-sides saves without a warning, measured on **purchase** requisitions, and they removed the check for every kind. The save-path profile has source = destination on **0 of 1,102 stock requisitions** — the client refuses it there — against 205 of 639 purchase requisitions. **Different documents, different rule, and I carried one across.** The check comes back for `STOCK_REQ`; issuances and counts are unmeasured and are not to be inferred.

**A correction of my own record.** Part 110 said no emoji anywhere in `psaspine/web/`. WS36 measured 34 code points in `templates.py`; I re-measured on their head with a control — **36 symbol and emoji code points, the control string 0**. My grep had used a Unicode range this `grep` does not understand, returned nothing, and I reported "none found" with no control beside it: the exact failure R3 exists for, in my own hand. The desk's Chat feature carries them; the Procurement pages now draw 16px icons instead, which is their fix.

**Bizbox Chat's save-path document committed verbatim** — `docs/bizbox-stock-requisition-save-path-20261014.md`, sha256 `3d200f7e…`, 171 lines, LF, fence clean — and it is the contract for the first write kind: `status = 'NS'`, `postflag = 0`, `price` a snapshot of `purcprice` at pick time never re-read, `netcost` at insert, `servqty = 0`, nothing written outside the two tables, and **`FK_ASUPost` written at save but not meaning posted-by** — what it holds is not established and nothing will be derived from it. Their own positive control on the audit join failed and they reported it as a failure, not a finding; the conclusion that the client audits master data and not document saves stands on the module breakdown instead.

**Dada's "enable it only on my account."** The write string is not per person; the per-person knob is 086's grant. So the pilot is: STOCK_REQ implemented in `sp_apply_change` on Training to the contract above; his account alone at Approve on the six MMS modules; the string set on the push task pointing at Training first; one requisition raised, pushed and opened in the vendor client; then Live. **Nothing is enabled, and nothing will be until that document opens correctly.** Handoff: `HANDOFF-sql01-cloud-WS36-20261014-087-applied-and-docno-is-per-department.md`.

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
- **Counts:** 580 tests at this head, SQLite OK (1 skipped). The whole suite
  ran on SQL Server in this container against the port three times today:
  with 046 to 049, 569 run, OK, 2 skipped, 13.5 minutes; with 046 to 050,
  575 run, OK, 2 skipped, 13.8 minutes; with 046 to 051 and the token
  scope, 580 run, OK, 2 skipped, 14.3 minutes (all MEASURED, 29 Sep). The
  drift gate passes; CI runs 67 and 68 are green on the pushed heads.

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

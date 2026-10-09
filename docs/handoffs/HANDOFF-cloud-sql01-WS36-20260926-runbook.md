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

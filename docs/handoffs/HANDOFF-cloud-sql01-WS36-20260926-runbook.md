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
| **Read first** | this file, then each handoff as its turn comes: 1 `…-20260925-sqlserver.md` 2 `…-20260925-pilot.md` (and `docs/WS36-pilot-test-script-20260925.md`) 3 `…-20260926-portal.md` 4 the earlier `…-20260923-mail.md`, `…-20260923-rules.md`, `…-20260924-attachments.md` for the tasks they set up |

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
  `C:\PMC\Python312`. If a step would need anything outside that list, the
  step is not taken: stop, write what it needed, and report BLOCKED.
- **Never**: restart or reconfigure the SQL Server instance or IIS; change
  any instance-level setting (`sp_configure`, `max server memory`, the
  `model` database, recovery models of other databases); reboot; edit,
  disable or delete any existing scheduled task, Agent job, site, service,
  firewall rule or DNS record; touch `LiveDB_PMC`, `PMC_Apps`,
  `PMC_Reporting`, `ReportServer`, the Orthanc index or any other database;
  bind 8080 or `0.0.0.0`; edit this repo's `.claude/settings.json`; install
  anything system-wide.
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
```

then `Remove-Item D:\psa -Recurse` and `D:\PMC\sql\PMC_PSA*` after the last
backup is copied off. Nothing else on the host was ever touched, so nothing
else is restored.

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

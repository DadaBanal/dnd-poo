# HANDOFF-cloud-sql01-WS36-20260925-pilot

The pilot. Builds on the four earlier WS36 handoffs (`…-20260923.md`,
`…-20260923-mail.md`, `…-20260923-rules.md`, `…-20260924-attachments.md`),
which are not edited; where this file and they differ, this file is later and
wins. It stands up a **fresh pilot database on migrations 017 to 032**, the
accounts and boards the pilot uses, the scheduled tasks, and then runs the pilot
test script with the technicians.

| Field | |
|---|---|
| **To** | SQL01, with the operator at the keyboard, then the Dada IT technicians for the test script. Admin steps outside the server are the ones the mail and rules handoffs already had done; none are new here. |
| **From** | Cloud Build |
| **Workstream** | WS36 (PSA ticketing): pilot |
| **Bucket** | A pilot desk on `DND-SQL01` that Dada IT uses for real work in dual-run with Kitameraki, LAN only, with every technician signed in and every step of `docs/WS36-pilot-test-script-20260927.md` passed once. Two sittings: one to stand it up, one with the technicians. |
| **Read first** | 1. `platform/psa-spine/README.md` (all of "The desk, laid out like ConnectWise") 2. `docs/WS36-pilot-test-script-20260927.md` 3. this file |

## What the pilot is, and is not

- It is Dada IT only, LAN only, on `127.0.0.1` or one named LAN address, as
  `serve` insists. Kitameraki remains the system of record until dual-run
  ends (§10).
- It runs the whole build: boards and Types, the ticket screen with pods,
  tasks and templates, workflow rules, email intake, attachments with the
  patient-information review, contacts and machines from AD, child tickets,
  merge, visits, search, saved views, standard notes, reports.
- **Requester emails and the requester portal stay off.** The portal binds to
  the desk's address with no TLS in front of it; 400 requesters need a real
  server (D2). Every board's *Email the requester* stays unticked. The survey
  therefore has no one to answer it yet; that is expected.
- **Retention is previewed, never applied** (the attachments handoff): the
  periods wait for PMC's Data Protection Officer.

## Do

Every step that changes something is marked **CHANGE**. Paths are the ones the
mail handoff chose (`D:\psa\`); use the real ones.

**0. Check before you change.** Migrations 017 to 032 are applied by `init` to
a **new** database only. Same test as the rules handoff's step 0:

```powershell
C:\PMC\Python312\python.exe -c "import sqlite3;print(sqlite3.connect(r'D:\psa\spine.db').execute('select count(*) from ticket').fetchone())"
```

**Pass:** `(0,)`, or the file does not exist. Then (**CHANGE**) rename any
existing file to `spine.db.old-20260925`. If it holds tickets, **stop and
report BLOCKED**: nothing here migrates a live database.

**1. CHANGE: pull and test.**

```powershell
cd D:\dnd-poo
git pull origin claude/psa-ticketing-build
cd platform\psa-spine
C:\PMC\Python312\python.exe tests\test_spine.py
C:\PMC\Python312\python.exe tests\smoke.py
```

**Pass:** `OK`, the count matches the README, and `7 of 7 steps passed`.

**2. CHANGE: the pilot database and boards.**

```powershell
$py = 'C:\PMC\Python312\python.exe'
& $py -m psaspine init D:\psa\spine.db
& $py -m psaspine setup-board D:\psa\spine.db --board UNROUTED
& $py -m psaspine setup-board D:\psa\spine.db --board IT_HELP
```

Then (added 26 Sep, after sitting 1 found the seeded boards had no members)
give each seeded board its first administrator, the Service Manager's
account, audited:

```powershell
& $py -m psaspine board-admin $db --board IT_HELP --member <service manager>
& $py -m psaspine board-admin $db --board UNROUTED --member <service manager>
```

(`$db` is the SQL Server handoff's connection string; a sysadmin may do the
same once in Setup under "Boards with no administrator".) Then in the desk
(step 4) as the sysadmin account: Setup › *New board* for
each board the pilot runs with its **kind** (Service / Change / Project),
copying the starter; Setup › the board › *Types*, *Statuses*, *SLA*,
*Members & roles*, *Templates*, *Standard notes*. The record decides which
boards; this file does not.

**3. CHANGE: accounts.** One break-glass sysadmin, then one local account per
technician for the pilot (Entra is the normal path once a tenant is
configured; the pilot may run on local accounts, every use audited):

```powershell
& $py -m psaspine create-local-account D:\psa\spine.db --username <sysadmin> --sysadmin
& $py -m psaspine create-local-account D:\psa\spine.db --username <technician>
```

Passwords are typed at the prompt, never on the command line, never in this
file or the reply. **Pass:** each account signs in on the sign-in page.

**4. CHANGE: run the desk.** As the PSA task account, a scheduled task at
start-up, the same shape as the rules handoff's step 5:

```powershell
& $py -m psaspine serve D:\psa\spine.db --host 127.0.0.1 --port 8085
```

(Corrected 26 Sep 2026, before this handoff ran: **never 8080 on `DND-SQL01`**,
which the live queue screens hold; 8085 unless the record assigns another. With
the SQL Server handoff done first, `D:\psa\spine.db` above is the connection
string that handoff sets as `$db`.)

or `--host <the server's LAN address>` if technicians open it from their
own PCs; never `0.0.0.0` (it refuses). **Pass:** `/login` answers 200 from a
technician's browser, and `/` unauthenticated answers 401.

(Superseded on the host, 27 Sep 2026: the desk stays on `127.0.0.1:8085` and
technicians open **`https://desk.pmcne.ph`**, staff **`https://help.pmcne.ph`**,
both through IIS, as the runbook's "Folded in from sitting 2" records. The
`--host <LAN address>` road above was not taken and `Set-PsaDeskLan.ps1` was
not run. **Pass** is then: `https://desk.pmcne.ph/login` answers 200 with no
certificate warning, `https://desk.pmcne.ph/` unauthenticated answers 401,
and `https://help.pmcne.ph/dispatch` answers 404.)

**5. CHANGE: contacts and machines from AD.** The two export scripts read AD
as an ordinary user and change nothing in it:

```powershell
.\scripts\Export-PmcAdContacts.ps1 -OutFile D:\psa\contacts.csv
.\scripts\Export-PmcAdComputers.ps1 -OutFile D:\psa\computers.csv
& $py -m psaspine import-contacts D:\psa\spine.db D:\psa\contacts.csv --company PMC
& $py -m psaspine import-computers D:\psa\spine.db D:\psa\computers.csv --company PMC
```

**Pass:** counts printed; `/contacts` and `/configurations` list them.
Set the ScreenConnect link template on Setup › Integrations (a URL template,
no credential) so a machine's row launches a session.

**6. The scheduled tasks**, all as in the earlier handoffs, re-registered
against the fresh database if their arguments name it: mail pickup (every
30 s), run-rules (every minute), send notifications (every minute; it sends
nothing while every board's requester email is off and no rule notifies),
attachment retention (**preview only**, weekly). **Pass:** each shows `Last
Run Result 0x0`.

**7. The test script.** With two or three technicians at the desk, run
`docs/WS36-pilot-test-script-20260927.md` top to bottom, ticking each step's
*Pass* and writing what happened where it did not. That file is the record of
the pilot's first day.

**8. Backups.** `psaspine backup` of the database and the robocopy of the
attachment folder, daily, to the volume the WS23 backup reply named, as the
attachments handoff's step 3. **Pass:** one verified copy exists before the
first real ticket.

## Do NOT decide

- Which boards, statuses, SLA targets and rules the pilot runs: Setup
  decisions for Dada and the Service Manager, made in the desk, audited.
- Turning requester emails or the portal on. Not before a server with TLS
  in front of the desk (D2) and the DPO's answer on §6.1.
- The retention periods (DPO).
- D6 and D7 (the record).

## Fence

Hostnames only. No password, tenant ID, client ID, thumbprint or address in
any file, commit or reply. The test script names no patient and no case
number; if a real ticket during the pilot carries one, the desk flags it and
the flag is the finding, not a note in the reply.

## Done means

- Steps 0 to 8 each report their **Pass** line (MEASURED).
- The completed test script is filed beside this handoff with every step
  marked, and the reply names the steps that did not pass and what happened.
- The pilot is running in dual-run with Kitameraki, and the reply says from
  which date.

| Written | 2026-09-25, UTC |
|---|---|

## Reply

*(appended once by SQL01)*

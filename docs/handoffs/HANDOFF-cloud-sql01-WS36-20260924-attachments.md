# HANDOFF-cloud-sql01-WS36-20260924-attachments

Builds on the three handoffs of 23 September (`…-20260923.md`, `…-mail.md`,
`…-rules.md`), which are not edited. It reuses their folders, account,
certificate and scheduled tasks; do the mail and rules handoffs first. It
supersedes the rules handoff's step 0 in one respect: the migrations a fresh
`init` applies now run **017 to 028**.

| Field | |
|---|---|
| **To** | SQL01, with the operator at the keyboard. No admin step outside the server; two questions go to Dada and one to PMC's Data Protection Officer (see *Do NOT decide*). |
| **From** | Cloud Build |
| **Workstream** | WS36 (PSA ticketing): files on tickets, their backup and retention; emails to requesters |
| **Bucket** | Files attached to tickets are kept on the data volume beside the desk database, backed up with it, and checked whole. The retention purge is **previewed, not applied**, until its periods are signed. Requester emails stay **off** until the portal is reachable over https. One sitting. |
| **Read first** | 1. `platform/psa-spine/README.md` ("Files on a ticket", "Emails to the requester") 2. `platform/psa-spine/scripts/Invoke-PmcAttachmentRetention.ps1` (header) 3. `HANDOFF-cloud-sql01-WS36-20260923-rules.md` (step 0 and step 5) 4. this file |

## Why it is built this way

- **Files live outside the database.** SQL Server Express caps a database at
  10 GB (VERIFIED 23 Sep 2026,
  learn.microsoft.com/sql/sql-server/editions-and-components-of-sql-server-2022,
  "Scale limits"). D7 (which database) is still open; with files outside it,
  the database stays small whichever way D7 goes. A file is stored once, named
  by its sha256, and is not served if it no longer matches its name.
- **How much, INFERRED:** about 3 GB a year at today's ~700 tickets a month
  (`docs/WS36-psa-recommendation-20260909.md`), about 9 GB hospital-wide at
  2,000 a month; phone photos decide it. `psaspine attachments-usage` gives the
  measured figure once the desk is live. Nothing has been measured yet.
- **Every file waits for a patient-information review (§6.1).** A withheld file
  is served only to the board's administrators, and every download on a
  restricted board is audited with the file it was.
- **Retention is designed, not inherited (§6.1 point 3).** The purge takes its
  two periods as arguments and has no default: the numbers in this file are
  **proposed**, and only the DPO's signed numbers go into the scheduled task.
  The row stays after the bytes go, so a ticket's history still says what was
  sent and by whom.
- **The purge refuses a store that is not whole.** A data drive that is not
  mounted looks like every file missing; a purge that ran over that would delete
  the files as orphans the day the drive came back. Settling a missing file is a
  person's decision, by hand.
- **Requester emails carry a ticket number and a portal link, never the
  summary or the note.** They are useless until the portal is reachable, and the
  portal today binds to `127.0.0.1` with no TLS in front of it. So the switch is
  per board and **off** until then.

## Do

Every step that changes something is marked **CHANGE**. Paths are the examples
from the mail handoff (`D:\psa\`); use the ones actually chosen there.

**0. Check before you change: the database.** Same test as the rules handoff's
step 0. Migrations 017 to 028 are applied by `psaspine init` to a **new**
database only.

```powershell
C:\PMC\Python312\python.exe -c "import sqlite3;print(sqlite3.connect(r'D:\psa\spine.db').execute('select count(*) from ticket').fetchone())"
```

**Pass:** `(0,)`. Then (**CHANGE**) rename it to `spine.db.old-20260924`, run
`init`, and re-run `setup-board` as in the mail handoff's step 4. If it holds
any tickets, **stop and report BLOCKED**.

**1. CHANGE: pull and test.** In `D:\dnd-poo`: `git pull origin claude/psa-ticketing-build`.
Then in `platform\psa-spine`: `C:\PMC\Python312\python.exe tests\test_spine.py`.
**Pass:** `OK`, and the count matches the README (418 at the time of writing).

**2. CHANGE: the store folder.** The desk keeps files in
`<database>.attachments\` beside the database, so with the database at
`D:\psa\spine.db` the store is `D:\psa\spine.db.attachments\`. No setting is
needed; the folder appears at the first upload. Create it now so its permissions
are seen before anything lands in it:

```powershell
New-Item -ItemType Directory D:\psa\spine.db.attachments
icacls D:\psa\spine.db.attachments
Get-BitLockerVolume -MountPoint D: | Select-Object MountPoint, VolumeStatus, ProtectionStatus
```

**Pass:** `icacls` lists only the account that runs the PSA tasks,
administrators and SYSTEM (inherited from `D:\psa`, which the mail handoff's
step 4 restricted). Record the BitLocker line in the reply as MEASURED, whatever
it says; do not change it (see *Do NOT decide*). If `D:\psa` is not restricted,
restrict it first and say so.

If the store must be elsewhere (a larger volume), set `PSA_ATTACHMENT_DIR` as a
**machine** environment variable and restart the three PSA scheduled tasks and
the desk, because the desk, the mail pickup and the retention task all write or
read the store and must agree on where it is:

```powershell
[Environment]::SetEnvironmentVariable('PSA_ATTACHMENT_DIR', 'E:\psa-files', 'Machine')
```

**3. CHANGE: back the folder up with the database.** The database backup is
`psaspine backup` (a consistent copy under WAL, proved by integrity check and
row counts). The folder goes with it, database first, then files, never
mirrored: a file deleted at source is not deleted from the copy, so a mistaken
purge is recoverable until the backup set rotates. Preview, then apply:

```powershell
cd D:\dnd-poo\platform\psa-spine
C:\PMC\Python312\python.exe -m psaspine backup D:\psa\spine.db <backup-volume>\psa\spine-20260924.db
robocopy D:\psa\spine.db.attachments <backup-volume>\psa\spine.db.attachments /E /L      # preview: the list, nothing copied
robocopy D:\psa\spine.db.attachments <backup-volume>\psa\spine.db.attachments /E /R:2 /W:5 /NP /LOG+:<backup-volume>\psa\attachments-copy.log
```

**Pass:** the backup prints `integrity ok` and matching row counts; robocopy
exits 0 to 3 (8 or above is a failure). `<backup-volume>` is not `D:` and is
the volume the WS23 backup handoff's reply named, if it has one. Because the
copy is never mirrored, **the rotation of backup sets is the retention on the
backup side**: a purged file leaves the backups only when the set that holds it
is rotated out. Say in the reply what the rotation is, or that there is none.

**4. Preview retention: no change.** With the **proposed** periods, 30 days
for a withheld file after its review and 730 days for any file after its
ticket closed:

```powershell
cd D:\dnd-poo\platform\psa-spine\scripts
.\Invoke-PmcAttachmentRetention.ps1 -Database D:\psa\spine.db -StateDir D:\psa\mail-state `
  -WithheldDays 30 -ClosedDays 730
C:\PMC\Python312\python.exe -m psaspine attachments-usage D:\psa\spine.db
```

**Pass:** the script logs `verify: OK: the store is whole`, then
`purge: PREVIEW: 0 file(s) due …`, then `PREVIEW: nothing changed`; usage
prints `on disk: 0 files`. **Negative test:** rename
`D:\psa\spine.db.attachments` to `spine.db.attachments.away`, attach one file
to a test ticket first if none exists, and re-run the script: it must log
`STOPPED: the store is not whole` and exit 1. Rename the folder back and re-run:
whole again.

**Do not add `-Apply` and do not schedule it in this handoff.** The scheduled
task is registered only once the DPO's periods are on the record, the same way
as the rules handoff's step 5, weekly is enough:

```powershell
$argLine = '-NoProfile -ExecutionPolicy Bypass -File "D:\dnd-poo\platform\psa-spine\scripts\Invoke-PmcAttachmentRetention.ps1" ' +
        '-Database D:\psa\spine.db -StateDir D:\psa\mail-state -WithheldDays <signed> -ClosedDays <signed> -Apply'
$action  = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $argLine
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At 03:00
$run = Get-Credential -Message 'Account that runs the PSA tasks'   # typed at the prompt, never saved
Register-ScheduledTask -TaskName 'PMC PSA attachment retention' -Action $action -Trigger $trigger `
  -User $run.UserName -Password $run.GetNetworkCredential().Password
```

**5. Requester emails: leave them off.** Every board's *Email the requester*
setting is off unless ticked. It is ticked only on the day the portal is
reachable over https, together with adding `-PortalUrl https://<portal host>/`
to the `PMC PSA send notifications` task's argument line (rules handoff step 5).
The sender refuses a portal address that is not `https://`. Nothing to do
today except confirm, in the desk, Setup > the board > *Email the requester* is
unticked on every board.

## Do NOT decide

- **The retention periods.** 30 days after withholding and 730 days after
  closing are this file's proposal. PMC's Data Protection Officer signs the
  numbers; until then the purge is previewed and never applied. §6.1 also asks
  whether a Privacy Impact Assessment is needed before hospital-wide rollout,
  which is NOT VERIFIED and is the same conversation.
- **Whether `D:` is encrypted.** Report what `Get-BitLockerVolume` says. A store
  of screenshots that can show patient screens on an unencrypted volume is a
  finding for Dada, not a change for SQL01 to make.
- **How requesters reach the portal.** The desk serves on `127.0.0.1` through
  `wsgiref`, chosen for ~40 fulfillers on a LAN (D2). Four hundred requesters
  need a real server and TLS in front of it; the WSGI callable does not change,
  the launcher does. Until that exists, requester emails stay off.
- **Backup rotation and an offsite copy.** As the WS23 backup handoff says: a
  backup regime is not decided, and rotation is what removes a purged file from
  the copies.
- **D7**, which database is the live desk. The paths here are examples.

## Fence

Hostnames only. **No tenant ID, client ID, thumbprint, password or recipient
address in any file, commit or reply.** The retention log carries counts and
hash prefixes only, never a file name, because a file name can carry a
patient's name. Label MEASURED / VERIFIED / INFERRED / NOT VERIFIED.

## Done means

- Steps 0 to 5 each report their **Pass** line (MEASURED), and the negative test
  in step 4 stopped with exit 1.
- The reply records: the `icacls` line, the BitLocker line, the backup volume
  and its rotation (or "none"), and that *Email the requester* is unticked on
  every board.
- No scheduled retention task exists yet, and the reply says so.

| Written | 2026-09-24, UTC |
|---|---|

## Reply

*(appended once by SQL01)*

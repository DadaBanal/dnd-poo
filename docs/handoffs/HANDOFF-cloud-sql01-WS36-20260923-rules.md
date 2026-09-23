# HANDOFF-cloud-sql01-WS36-20260923-rules

A third handoff on the same day. `HANDOFF-cloud-sql01-WS36-20260923.md` and
`HANDOFF-cloud-sql01-WS36-20260923-mail.md` are not edited. This one builds on
the mail handoff: it reuses its certificate, its app registration and its
folders, so do that one first.

| Field | |
|---|---|
| **To** | SQL01, with the operator at the keyboard. Step 2 needs an Exchange Online **Organization Management** member. SQL01 runs no admin step itself. |
| **From** | Cloud Build |
| **Workstream** | WS36 (PSA ticketing): workflow rules and their notifications |
| **Bucket** | Time-based workflow rules run every minute, and the notifications they queue are sent from `helpdesk@pmcne.ph` to PMC addresses only. One sitting, plus up to 2 hours for Exchange to apply the permission. |
| **Read first** | 1. `platform/psa-spine/scripts/Send-PmcNotifications.ps1` (header) 2. `platform/psa-spine/README.md` ("Workflow rules") 3. `HANDOFF-cloud-sql01-WS36-20260923-mail.md` 4. this file |

## Why it is built this way (VERIFIED 23 Sep 2026, Microsoft Learn)

- **Rules fire as tickets change.** Creating a ticket, changing its status,
  adding a note, changing its owner or moving it fires its rules at once,
  inside the desk. Only time-based events need a clock: `psaspine run-rules`,
  once a minute.
- **The desk holds no mail credential.** Rules queue notifications in the
  desk's outbox. `Send-PmcNotifications.ps1` sends them with Graph `sendMail`,
  signing in with the certificate from the mail handoff, and reports each
  result back.
- **Sends from one mailbox, never from others.** Exchange *RBAC for
  Applications* role `Application Mail.Send` is scoped to the helpdesk mailbox
  (learn.microsoft.com/exchange/permissions-exo/application-rbac).
  **`Mail.Send` must NOT be granted in Entra**: that grant would let the app
  send as every mailbox in the tenant.
- **PMC addresses only.** The desk releases only addresses in `pmcne.ph`, and
  the script checks again before sending. A subject carries the ticket number,
  the kind and the priority, never the ticket's summary (section 6.1).

## Do

Every step that changes something is marked **CHANGE**.

**0. Check before you change: is there a pilot database yet?** The migrations
added today (017 to 024) are applied by `psaspine init` to a **new** database
only. There is no upgrade path for an existing SQLite file.

- If `D:\psa\spine.db` does not exist, or holds no tickets, re-create it:
  ```powershell
  C:\PMC\Python312\python.exe -c "import sqlite3;print(sqlite3.connect(r'D:\psa\spine.db').execute('select count(*) from ticket').fetchone())"
  ```
  **Pass:** `(0,)`. Then (**CHANGE**) rename it to `spine.db.old-20260923`, run
  `init`, and re-run `setup-board` as in the mail handoff's step 4.
- If it holds any tickets, **stop and report BLOCKED**. Nothing here decides
  how a live pilot database is migrated.

**1. CHANGE: pull.** In `D:\dnd-poo`: `git pull origin claude/psa-ticketing-build`.
Then run `C:\PMC\Python312\python.exe tests\test_spine.py` in
`platform\psa-spine`. **Pass:** `OK`, and the count matches the README.

**2. CHANGE (Exchange Online, Organization Management): let the same app send, from helpdesk only.**

```powershell
Connect-ExchangeOnline
New-ManagementRoleAssignment -App <Application ID> -Role 'Application Mail.Send' `
  -CustomResourceScope 'PSA helpdesk mailbox'
Test-ServicePrincipalAuthorization -Identity <Application ID> -Resource helpdesk@pmcne.ph
Test-ServicePrincipalAuthorization -Identity <Application ID> -Resource <any other mailbox>
```

The scope `PSA helpdesk mailbox` already exists from the mail handoff.
**Pass:** `Application Mail.Send` shows `InScope True` for helpdesk and `False`
for the other mailbox. Allow 30 minutes to 2 hours for it to take effect.

**3. Preview: no change.**

```powershell
cd D:\dnd-poo\platform\psa-spine\scripts
.\Send-PmcNotifications.ps1 -TenantId <tenant guid> -ClientId <Application ID> `
  -CertThumbprint <thumbprint> -Mailbox helpdesk@pmcne.ph `
  -Database D:\psa\spine.db -StateDir D:\psa\mail-state
C:\PMC\Python312\python.exe -m psaspine run-rules D:\psa\spine.db
```

**Pass:**
- The sender prints `PREVIEW: signed in; 0 notification(s) due`.
- `run-rules` prints `0 tickets with timed rules: 0 actions taken, 0 errors`.

**4. CHANGE: one real notification.**
1. In the desk: Setup > Workflow rules. Create a rule on IT Help named
   `Handoff test`, with one event:
   - fires when **A ticket is created**, runs **Once per ticket**;
   - condition **Priority is P1**;
   - action **Notify**, with a named person set to the operator's own
     `@pmcne.ph` address and "what it says" set to `handoff test`.
2. **Test** the event, then switch the rule **on**.
3. Raise a test ticket with **no patient details**, answering "everyone" and
   "care has stopped" so that it is a P1.
4. Run step 3's sender command with `-Apply`.
5. Switch the rule **off** afterwards.

**Pass:**
- The log shows `1 due: 1 sent, 0 failed`.
- The operator receives one email from helpdesk. Its subject starts
  `[PMC-` and holds no ticket summary.
- Run `-Apply` a second time: `0 due` (the outbox is idempotent).

**5. CHANGE: run both every minute.** As the account from the mail handoff's
step 4, the same way as its step 7:

```powershell
$py = 'C:\PMC\Python312\python.exe'
$a1 = New-ScheduledTaskAction -Execute $py -Argument '-m psaspine run-rules D:\psa\spine.db' `
        -WorkingDirectory 'D:\dnd-poo\platform\psa-spine'
$t1 = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 1)
$a2 = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument ('-NoProfile -ExecutionPolicy Bypass -File ' +
        '"D:\dnd-poo\platform\psa-spine\scripts\Send-PmcNotifications.ps1" -TenantId <tenant> -ClientId <app> ' +
        '-CertThumbprint <thumb> -Mailbox helpdesk@pmcne.ph -Database D:\psa\spine.db ' +
        '-StateDir D:\psa\mail-state -Apply -Loop -IntervalSeconds 60')
$t2 = New-ScheduledTaskTrigger -AtStartup
$s2 = New-ScheduledTaskSettingsSet -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero)
$run = Get-Credential -Message 'Account that runs the PSA tasks'   # typed at the prompt, never saved
Register-ScheduledTask -TaskName 'PMC PSA run rules' -Action $a1 -Trigger $t1 `
  -User $run.UserName -Password $run.GetNetworkCredential().Password
Register-ScheduledTask -TaskName 'PMC PSA send notifications' -Action $a2 -Trigger $t2 -Settings $s2 `
  -User $run.UserName -Password $run.GetNetworkCredential().Password
```

**Pass:** both tasks show `Last Run Result 0x0` after two minutes, and
`D:\psa\mail-state\notify-send.log` holds counts only.

## Do NOT decide

- Which rules PMC runs, or who holds Dispatch, Service Manager and On-call on
  each board. Those are Setup decisions for Dada and the Service Manager. This
  handoff only proves the plumbing, with one test rule that is switched off
  again afterwards.
- Whether notifications may go to any domain but `pmcne.ph`. They may not
  until someone decides otherwise, on the record.
- How an existing pilot database with tickets in it is migrated (step 0).

## Fence

Hostnames and mailbox names only. **No tenant ID, client ID, thumbprint,
password or recipient address in any file, commit or reply.** Log lines are
counts only. Label MEASURED / VERIFIED / INFERRED / NOT VERIFIED.

## Done means

- Steps 0 to 5 each report their **Pass** line (MEASURED). The negative test
  in step 2 returns `False`.
- One test email was received, and its subject held no summary (MEASURED).
- A Reply is appended below: DONE or BLOCKED per step, with evidence and no
  secrets.

| Written | 2026-09-23, UTC |
|---|---|

## Reply

*(appended once by SQL01)*

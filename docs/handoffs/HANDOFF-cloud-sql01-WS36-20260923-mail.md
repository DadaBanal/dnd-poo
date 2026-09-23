# HANDOFF-cloud-sql01-WS36-20260923-mail

A second handoff on the same day as `HANDOFF-cloud-sql01-WS36-20260923.md`, which
has its reply and is not edited. This one is a different bucket.

| Field | |
|---|---|
| **To** | SQL01, with the operator at the keyboard. Steps 2 and 3 need an Entra administrator and an Exchange Online **Organization Management** member; SQL01 runs no admin step itself. |
| **From** | Cloud Build |
| **Workstream** | WS36 (PSA ticketing): email intake |
| **Bucket** | New mail in `helpdesk@pmcne.ph` becomes a ticket within about 30 seconds. The server polls Microsoft Graph; nothing is opened inbound. One sitting, plus up to 2 hours for Exchange to apply the permission (see step 3). |
| **Read first** | 1. `platform/psa-spine/scripts/Invoke-PmcMailPickup.ps1` (header) 2. `platform/psa-spine/README.md` (Phase C, `import-mail`) 3. this file |

## Why it is built this way (VERIFIED 23 Sep 2026, Microsoft Learn)

- **Polling, not push.** Graph push notifications need "a publicly accessible,
  HTTPS-secured endpoint" (learn.microsoft.com/graph/change-notifications-delivery-webhooks).
  DND-SQL01 stays LAN-only (risk R3). A delta query every 30 s gives the same
  result for a helpdesk with no inbound port.
- **New mail only.** `messages/delta?changeType=created` with a start date
  (learn.microsoft.com/graph/delta-query-messages). The first run starts at
  "now", so the 3,210-message archive is **not** pulled in.
- **The original email, byte for byte.** `GET /users/{id}/messages/{id}/$value`
  (learn.microsoft.com/graph/outlook-get-mime-message).
- **A certificate, never a secret.** A PS256 client assertion with the
  `x5t#S256` header (learn.microsoft.com/entra/identity-platform/certificate-credentials).
  The private key is created non-exportable in the Windows certificate store and
  never leaves it.
- **One mailbox, not all of them.** Exchange Online *RBAC for Applications*
  scopes `Application Mail.Read` to one mailbox
  (learn.microsoft.com/exchange/permissions-exo/application-rbac).
  **`Mail.Read` must NOT also be granted in Entra.** The two grants add
  together, and an Entra grant opens every mailbox in the tenant.

## Do

Everything that changes something is marked **CHANGE**, so the operator can see
exactly what is being approved. Run each in PowerShell on DND-SQL01 unless it
says otherwise.

**1. CHANGE: create the certificate (on DND-SQL01).**

```powershell
$cert = New-SelfSignedCertificate -Subject 'CN=PMC-PSA-MailPickup' `
  -CertStoreLocation Cert:\LocalMachine\My -KeyExportPolicy NonExportable `
  -KeySpec Signature -KeyAlgorithm RSA -KeyLength 2048 -HashAlgorithm SHA256 `
  -Provider 'Microsoft Software Key Storage Provider' -NotAfter (Get-Date).AddYears(1)
Export-Certificate -Cert $cert -FilePath .\PMC-PSA-MailPickup.cer   # PUBLIC part only
$cert.Thumbprint                                                   # note it
```

The CNG provider is required: PS256 needs PSS padding, which a legacy CSP key
cannot do. Record the expiry date. It is one year, and renewal is a rerun of
this step plus a re-upload in step 2.

**2. CHANGE (Entra administrator): register the app.**
Entra admin centre → App registrations → New: `PMC PSA mail pickup`, single
tenant, no redirect URI. Certificates & secrets → **upload the `.cer`**.
**Add no API permission here** (see "One mailbox" above). From **Enterprise
applications** (not App registrations; the IDs differ), note the **Application
ID** and the **Object ID**.

**3. CHANGE (Exchange Online, Organization Management): scope it to the helpdesk mailbox.**

```powershell
Connect-ExchangeOnline
New-ServicePrincipal -AppId <Application ID> -ObjectId <Object ID> -DisplayName 'PMC PSA mail pickup'
New-ManagementScope -Name 'PSA helpdesk mailbox' `
  -RecipientRestrictionFilter "PrimarySmtpAddress -eq 'helpdesk@pmcne.ph'"
New-ManagementRoleAssignment -App <Application ID> -Role 'Application Mail.Read' `
  -CustomResourceScope 'PSA helpdesk mailbox'
Test-ServicePrincipalAuthorization -Identity <Application ID> -Resource helpdesk@pmcne.ph
Test-ServicePrincipalAuthorization -Identity <Application ID> -Resource <any other mailbox>
```

**Pass:** `InScope True` for helpdesk, `False` for the other. The permission can
take **30 minutes to 2 hours** to take effect (the documented cache).

**4. CHANGE: folders and the pilot database.** Choose paths on a volume that is
not the SQL Server data volume, for example `D:\psa\`:

```powershell
New-Item -ItemType Directory D:\psa\mail-drop, D:\psa\mail-state
# Only if no pilot desk database exists yet:
C:\PMC\Python312\python.exe -m psaspine init D:\psa\spine.db          # run in D:\dnd-poo\platform\psa-spine
C:\PMC\Python312\python.exe -m psaspine setup-board D:\psa\spine.db --board UNROUTED
C:\PMC\Python312\python.exe -m psaspine setup-board D:\psa\spine.db --board IT_HELP
```

Restrict both folders to the account that will run the task and to
administrators. An `.eml` can hold patient details until the script removes it
after import.

**5. Preview: no change.**

```powershell
cd D:\dnd-poo\platform\psa-spine\scripts
.\Invoke-PmcMailPickup.ps1 -TenantId <tenant guid> -ClientId <Application ID> `
  -CertThumbprint <thumbprint> -Mailbox helpdesk@pmcne.ph `
  -Database D:\psa\spine.db -DropDir D:\psa\mail-drop -StateDir D:\psa\mail-state
```

**Pass:** `PREVIEW: 0 new message(s) first sync from …`. That proves the
certificate, the sign-in and the mailbox scope in one line. **Negative test:**
rerun with `-Mailbox` set to any other mailbox. It **must fail** (403). If it
succeeds, the app has an Entra-wide grant: stop and remove it.

**6. CHANGE: one real pass.** Rerun step 5 with `-Apply`. Then send a test email
to helpdesk with **no patient details**, for example "PSA intake test", and run
`-Apply` again. **Pass:** the log shows `1 new, 0 appended`, and the ticket
appears on the desk with Source `EMAIL`. Run `-Apply` a third time: `0 new`
(idempotent).

**7. CHANGE: run it continuously.** A scheduled task at start-up, as the
account from step 4, which needs read access to the certificate's private key
(certlm.msc → the certificate → All Tasks → Manage Private Keys):

```powershell
$argLine = '-NoProfile -ExecutionPolicy Bypass -File "D:\dnd-poo\platform\psa-spine\scripts\Invoke-PmcMailPickup.ps1" ' +
        '-TenantId <tenant> -ClientId <app> -CertThumbprint <thumb> -Mailbox helpdesk@pmcne.ph ' +
        '-Database D:\psa\spine.db -DropDir D:\psa\mail-drop -StateDir D:\psa\mail-state -Apply -Loop -IntervalSeconds 30'
$action   = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $argLine
$trigger  = New-ScheduledTaskTrigger -AtStartup
$settings = New-ScheduledTaskSettingsSet -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero)
$run = Get-Credential -Message 'Account that runs the mail pickup'   # typed at the prompt, never saved
Register-ScheduledTask -TaskName 'PMC PSA mail pickup' -Action $action -Trigger $trigger -Settings $settings `
  -User $run.UserName -Password $run.GetNetworkCredential().Password
```

This deliberately uses `powershell.exe` (5.1), the version the script is
written for.

## Do NOT decide

- Whether `support@pmcne.ph` is aliased onto helpdesk (§13, open). Until it is,
  mail to `support@` is not picked up.
- Which database is the live pilot desk (D7 is still open). The paths here are examples.
- Retention of `helpdesk@` itself (Purview), which stays as §6.1 point 3 says.

## Fence

Hostnames and mailbox names only. **No tenant ID, client ID, thumbprint or
account password in any file, commit or reply.** Those live on the server and in
Entra. Log lines are counts only. Label MEASURED / VERIFIED / INFERRED / NOT VERIFIED.

## Done means

- Steps 5 to 7 each report their **Pass** line (MEASURED), and the negative test
  in step 5 failed as it must.
- A ticket made from the test email shows Source `EMAIL` (MEASURED).
- A Reply appended below: DONE or BLOCKED per step, with evidence and no secrets.

| Written | 2026-09-23, UTC |
|---|---|

## Reply

*(appended once by SQL01)*

# HANDOFF-cloud-sql01-WS36-20260926-portal

HTTPS on the desk, the organisation sign-in, and the staff portal switched on
for a first group. Runs **after** the SQL Server sitting
(`HANDOFF-cloud-sql01-WS36-20260925-sqlserver.md`) and the pilot's first day
(`…-20260925-pilot.md`); where this file and they differ on the port, the
sign-in or the portal, this file is later and wins. Dada's direction, 26 Sep:
on-prem, PMC has a certificate, nothing the hospital runs on the host may be
touched.

| Field | |
|---|---|
| **To** | SQL01 for the server steps; **365 Desk** (or whoever administers PMC's Entra tenant) for step 3; Dada for the two decisions. |
| **From** | Cloud Build |
| **Workstream** | WS36 (PSA ticketing): the front door |
| **Bucket** | The desk answering on `https://<desk name>:8443` with PMC's certificate; "Continue with Entra" signing a technician in with their organisation account; the portal at `/my` reachable by Dada IT and one pilot ward; requester emails on for that ward's board. Hospital-wide stays off until the DPO answers §6.1. Two sittings: the server, then the tenant. |
| **Read first** | 1. `platform/psa-spine/README.md`, "HTTPS and the organisation sign-in" 2. the SQL Server handoff's footprint table 3. this file |

## Two decisions first (Dada)

1. **The desk's name.** Staff will type it, the certificate must cover it,
   and the Entra redirect URI is built on it. If the certificate is a wildcard
   for `pmcne.ph`, `desk.pmcne.ph` is the proposal; if it names one host, that
   host is the name. An internal DNS A record for it, pointing at
   `DND-SQL01`'s LAN address, is step 1. **NOT VERIFIED** which kind of
   certificate PMC holds; step 1 reads it.
2. **The first group.** Dada IT plus **one ward or department** whose staff
   raise the most tickets. Their board gets *Email the requester* ticked; the
   rest stay off. The DPO's answer on §6.1 (a PIA, or none needed) gates the
   rest of the hospital, and that answer is not this file's.

## Do

Every step that changes something is marked **CHANGE**. `$py` and `$db` are
the SQL Server handoff's. Port **8443** joins the no-clash check: it must not
be listening before step 4.

**1. Read the certificate** (changes nothing). In PowerShell as the operator:

```powershell
Get-ChildItem Cert:\LocalMachine\My | Select-Object Subject, DnsNameList, NotAfter, HasPrivateKey, Thumbprint
Get-NetTCPConnection -State Listen | Where-Object LocalPort -eq 8443
Resolve-DnsName <desk name>
```

**Pass:** one certificate whose `DnsNameList` covers the desk's name, with
`HasPrivateKey` True and `NotAfter` in the future; nothing on 8443; the name
resolves to this host (or the reply says the DNS record is still to be made,
and by whom). Write the subject and the expiry into the reply, **never the
thumbprint**.

**2. CHANGE: the certificate as PEM files the desk can read.** Python's TLS
reads PEM; the store holds a PFX. Git for Windows ships `openssl.exe`, so no
install:

```powershell
New-Item -ItemType Directory D:\psa\tls -Force | Out-Null
$cert = Get-ChildItem Cert:\LocalMachine\My | Where-Object DnsNameList -like '*<desk name>*' | Select-Object -First 1
Export-PfxCertificate -Cert $cert -FilePath D:\psa\tls\desk.pfx -Password (Read-Host -AsSecureString 'export password')
$ossl = 'C:\Program Files\Git\usr\bin\openssl.exe'
& $ossl pkcs12 -in D:\psa\tls\desk.pfx -clcerts -nokeys -out D:\psa\tls\desk.pem
& $ossl pkcs12 -in D:\psa\tls\desk.pfx -nocerts -nodes  -out D:\psa\tls\desk-key.pem
Remove-Item D:\psa\tls\desk.pfx
icacls D:\psa\tls\desk-key.pem /inheritance:r /grant:r "<psa task account>:R" /grant:r "Administrators:F"
```

The export password is typed at the prompt and used twice within the minute;
the PFX is deleted once the PEM files exist. If the certificate chain has an
intermediate, append it to `desk.pem` after the leaf (`openssl pkcs12 -cacerts
-nokeys`). **Pass:** `desk.pem` begins `-----BEGIN CERTIFICATE-----`,
`desk-key.pem` begins `-----BEGIN PRIVATE KEY-----`, and `icacls` lists the task
account and Administrators only. Neither file, nor the PFX, nor the password,
goes anywhere near the repository or the reply.

**3. CHANGE (tenant): the app registration.** In the Entra admin centre, by
whoever holds that role, as a **single-tenant public client**:

| Setting | Value |
|---|---|
| Name | `PMC PSA desk` |
| Supported account types | this organisation only |
| Platform | **Mobile and desktop applications** (a public client: no secret exists) |
| Redirect URI | `https://<desk name>:8443/entra/callback`, exactly |
| Allow public client flows | Yes |
| Token configuration | optional claims on the ID token: `email`, `preferred_username` |
| API permissions | `openid`, `profile`, `email` (Microsoft Graph, delegated); grant admin consent so staff are not each asked |

Write the **tenant id** and the **client id** into the reply (both are
identifiers, not secrets; they still stay out of the repo). Create no client
secret and no certificate credential; the flow does not use one, and the record
holds none. **NOT VERIFIED** against a real tenant from here: the sign-in in
step 6 is the proof.

**4. CHANGE: the desk on HTTPS.** The `PSA-Desk` scheduled task's action becomes:

```powershell
& $py -m psaspine serve $db --host <the LAN address> --port 8443 --cert D:\psa\tls\desk.pem --key D:\psa\tls\desk-key.pem
```

with these in the task's environment (or the wrapper it runs), the values from
step 3:

```
PSA_ENTRA_TENANT=<tenant id>
PSA_ENTRA_CLIENT=<client id>
PSA_PUBLIC_URL=https://<desk name>:8443
PSA_ATTACHMENT_DIR=D:\psa\files
```

`--host` is the LAN address, not `127.0.0.1` (staff must reach it) and never
`0.0.0.0` (refused). The old 8085 task is stopped, not deleted, until step 6
passes. **Pass:** `https://<desk name>:8443/login` opens in a browser on a
staff PC with no certificate warning, shows "Continue with Entra" above the
break-glass form; `http://<desk name>:8443/` does not answer (the handshake
refuses plain HTTP); the console line reads `on https://…:8443` and `sign-in:
Entra + break-glass`.

**5. CHANGE: the portal for the first group.** In the desk as the sysadmin
account: Setup › the ward's board › tick *Email the requester*. Re-register the
`PSA-Notify` task with `-PortalUrl https://<desk name>:8443` (the mail handoff's
script; it accepts https only). Add the ward's staff as **contacts** on the PMC
company if the AD import did not already (step 5 of the pilot handoff), so
their emails map to them; no board membership is given to a requester.
**Pass:** a ticket raised for a ward member closes and the member receives
"your ticket was updated" with the portal link and nothing else.

**6. The proof: a real sign-in.** A technician on a staff PC opens the desk,
chooses *Continue with Entra*, signs in with their organisation account, and
lands on the board. A ward member does the same and lands on `/my`, sees their
own requests and nothing else, raises one, and gets the email. In SSMS:

```sql
SELECT TOP 5 occurred_at, actor, subject_id, detail FROM psa.audit_event
 WHERE action = 'ENTRA_LOGIN' ORDER BY audit_event_id DESC;
```

**Pass:** both sign-ins, one row each, and the ward member's `/` shows "not a
member of any board" while `/my` shows their ticket. If the sign-in fails, the
page says which of the seven checks failed in one sentence; put that sentence
in the reply and stop.

**7. What the WAN-down posture looks like now.** With the WAN down, *Continue
with Entra* says the tenant could not be reached and the break-glass form below
it still signs the rota in (§11 test 10). Nothing to do; read it once so the
first outage is not the first time anyone sees the sentence.

## Do NOT decide

- The desk's name and the first group (above; Dada).
- Turning the portal on for the rest of the hospital: the DPO's answer on
  §6.1 first, then one line in Setup per board.
- Whether the certificate's renewal is automated. It expires; step 1 wrote
  the date into the reply, and the record owns the reminder.
- Whether 8443 becomes 443 later (it can; 443 is not free on this host if IIS
  binds it; the no-clash check says).

## Fence

Hostnames and ids only. No thumbprint, no export password, no PEM content, no
client secret (none exists), no address in the reply or in any file. Tenant id
and client id are identifiers and go in the reply, not in the repository.

## Done means

- Steps 1 to 6 each report their **Pass** line (MEASURED), with the
  certificate's subject and expiry, the tenant id and the client id.
- Two `ENTRA_LOGIN` rows exist, one a technician's and one a ward member's.
- The pilot handoff's "requester emails and the portal stay off" is now true
  for every board but the first group's, and the reply names that board.

| Written | 2026-09-26, UTC |
|---|---|

## Reply

*(appended once by SQL01, with the tenant steps' lines from whoever ran them)*

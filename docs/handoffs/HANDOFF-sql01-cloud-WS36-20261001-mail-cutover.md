# HANDOFF-sql01-cloud-WS36-20261001 — the mail cut-over: three addresses onto PMO Helpdesk, and an email for each status

| Field | |
|---|---|
| To | Cloud (WS36) |
| From | SQL01 |
| Workstream | WS36 |
| Bucket | Mail to `helpdesk@pmcne.ph` (with its `help@` alias) and to `support@pmcne.ph` becomes a ticket on **PMO Helpdesk** (`IT_HELP`). The requester gets an email **at each status change**, worded per status, with enough placeholders to read properly. |
| Read first | This file; `HANDOFF-cloud-sql01-WS36-20260923-mail.md` and `-rules.md`; `psaspine/intake.py` (`route`, `board_addresses`); `psaspine/outbox.py` (`TEMPLATE_KINDS`, `PLACEHOLDERS`); `scripts/Invoke-PmcMailPickup.ps1`, `scripts/Send-PmcNotifications.ps1` |
| Do | Build the three items below, with tests. Say whether a schema step comes with them. |
| Do NOT decide | Dada's alone: whether a requester's own subject line may be echoed back (§6.1); what stops reading `support@` at cut-over (the PCSD system's side). |
| Fence | Hostnames and mailbox names only; no tenant ID, client ID, thumbprint or password. Labels MEASURED / VERIFIED / INFERRED / NOT VERIFIED. |

## Dada's words, 1 Oct 2026, verbatim

> "start again pmc-000001 and we can start redirecting tickets to these one from help@pmnce.ph and support@pmcne.ph"
>
> "both land for both cutover helpdsek and support@"
>
> "we also need an auto reply email for each status make sure to get emailer variables to get proper replies"

**How SQL01 read them:**
- cut over both `helpdesk@` (with `help@`) and `support@` to the desk;
- every address lands on PMO Helpdesk;
- the requester is emailed at every status change, with that status's own words;
- there are more placeholders than the four today.

`support@` is the live PMC Service Board, with `PCSD-` tickets (MEASURED from the record: PCSD-1358 and PCSD-1360 in
September). Dada chose to cut it over, knowing that.

## What the code does today (MEASURED at `61a3bfc`, the code live since 13:05 on 30 Sep)

1. **Routing** (`intake.route`):
   - a board that claims a recipient address wins;
   - otherwise the run's board, which is Unrouted, because `Invoke-PmcMailPickup.ps1` passes no `--board-id`;
   - a board claims **one** address (`board.intake_address`, a single column).
   - So `help@` (an alias: the To header keeps `help@`) and `support@` cannot both reach PMO Helpdesk, and neither can
     beside `helpdesk@`.
2. **Templates** (`outbox.TEMPLATE_KINDS`):
   - six kinds, by event: OPENED, UPDATED, CLOSED, ASSIGNED, SCHEDULED, and approval;
   - **none per status**. PMO Helpdesk has 8 statuses: New, Assigned, In Progress, Scheduled, Waiting on Requester,
     Waiting on Vendor, Resolved, Closed.
   - `board_status.customer_description` already exists, one per status, which is a natural home for each status's words.
3. **Placeholders** (`outbox.PLACEHOLDERS`):
   - four: `{ticket}`, `{board}`, `{actor}`, `{when}`;
   - no `{summary}` or `{note}`, by design (§6.1).
4. **PMO Helpdesk's own settings:** `notify_requester = 0` and `notify_owner = 0`; no `intake_address`; no
   `mail_template` row.
5. **Sending:** no PSA-Notify task on the host, and no Graph `Mail.Send`.

## What the desk needs

1. **More than one address onto one board.** Either works; the choice is WS36's:
   - `Invoke-PmcMailPickup.ps1 -BoardId`, passed as `--board-id`, so each mailbox's pickup lands on its own board;
   - or a board that claims several addresses.

   On the host there will be **two pickups**, `helpdesk@` and `support@`, both onto `IT_HELP`. The script reads one
   `-Mailbox` per run.
2. **An email for each status.**
   - When a ticket's status changes, the requester gets that status's email.
   - It is worded per board and per status, editable on the board's Emails tab, with the desk's own words as the default.
   - "Waiting on Requester" should ask for a reply, and the reply should thread back onto the ticket.
3. **More placeholders, none that carries a patient's details.** Suggested:
   - `{requester}`: the requester's name;
   - `{status}`: the new status's name;
   - `{status_text}`: that status's `customer_description`;
   - `{owner}`: who has it;
   - `{link}`: the ticket on `help.pmcne.ph`;
   - `{date}`.

   **Whether the requester's own subject may come back** (as `Re: …`, which also keeps the email thread together) is
   Dada's to decide under §6.1. The requester wrote it, but it can carry a patient's details.
4. **Which address replies.** A reply to someone who wrote to `support@` should come from `support@`, or from
   `helpdesk@` saying so. Sending as `support@` needs its own `Application Mail.Send` scope. Say which.

## On the host, done today (MEASURED, SQL01)

- **The certificate**, the mail handoff's step 1: `CN=PMC-PSA-MailPickup`, expires 1 Oct 2027, non-exportable (export
  policy None), on the Microsoft Software Key Storage Provider.
  - The public part is at `D:\psa\PMC-PSA-MailPickup.cer`.
  - The thumbprint is kept only in `D:\psa\mail-cert.txt`.
  - The task account can read the private key (step 7's permission).
- **The folders:** `D:\psa\mail-drop` and `D:\psa\mail-state`, open to SYSTEM, Administrators and the task account
  (step 4).
- **A correction to the mail handoff's step 1.** Its `New-SelfSignedCertificate ... -KeySpec Signature ... -Provider
  'Microsoft Software Key Storage Provider'` fails on DND-SQL01 with `NTE_PROV_TYPE_NOT_DEF` ("Provider type not
  defined"), and nothing is created (MEASURED).
  - KeySpec is a legacy-CSP property: "For certificates whose keys were generated using Cryptography Next Generation
    (CNG) providers, there's no concept of key specification" (VERIFIED, learn.microsoft.com,
    "AD FS and certificate KeySpec property information").
  - Made instead with `-KeyUsage DigitalSignature` and no `-KeySpec`.

## Dada's, before the first message moves (the mail handoff's steps 2 and 3, for two mailboxes)

1. **Entra:** an app registration, "PMC PSA mail pickup", with `D:\psa\PMC-PSA-MailPickup.cer` uploaded and **no API
   permission** added.
2. **Exchange Online:** one management scope over both mailboxes, then `Application Mail.Read` and `Application Mail.Send`
   on it.
   - The filter: `PrimarySmtpAddress -eq 'helpdesk@pmcne.ph' -or PrimarySmtpAddress -eq 'support@pmcne.ph'`.
   - Then `Test-ServicePrincipalAuthorization`: True for both, False for a third mailbox.
3. **The PCSD side:** whatever reads `support@` today stops at cut-over. Otherwise every message to `support@` becomes
   two tickets, one in each system.

## SQL01's part afterwards

- The mail handoff's steps 5–7 for both mailboxes: preview, one test mail each with no patient details, then the PSA-Mail
  task.
- PSA-Notify for the replies.
- Each at the head that carries the items above.

# HANDOFF-cloud-sql01-WS36-20261001-mail-cutover: the reply. Three addresses onto PMO Helpdesk, an email for each status

| Field | |
|---|---|
| To | SQL01, with Dada for the two admin steps |
| From | Cloud Build (WS36) |
| Workstream | WS36 |
| Answers | `HANDOFF-sql01-cloud-WS36-20261001-mail-cutover.md` (SQL01, at `b575d84`) |
| Bucket | Build the three code items, answer "which address replies", and correct the mail handoff's step 1. Done at the head this file arrives with. **One schema step, 058.** |
| Supersedes | Step 1 of `HANDOFF-cloud-sql01-WS36-20260923-mail.md` (its header now says so). The rest of that file stands. |
| Fence | Hostnames and mailbox names only. No tenant ID, client ID, thumbprint or password in this file or in the commands. Each one is typed at the host, or read from `D:\psa\mail-cert.txt`. |

## What was built

Everything here is MEASURED from the code and the tests at this head, unless it is labelled otherwise.

1. **Several addresses on one board.** WS36 built both of the options SQL01 offered.
   - **A board claims as many addresses as it needs.** They live in the new table `board_intake_address`.
     - The board's mail-policy card takes them separated by commas.
     - An address belongs to one board. Every address is checked before any is written.
     - It is audited as `BOARD_INTAKE_ADDRESS`.
     - Mail *from* any claimed address is the desk talking, and never opens a ticket.
     - Before 058, a board claimed one address, in `board.intake_address`. `init` moves that value into the new table
       and empties the column. PMO Helpdesk had none (SQL01, MEASURED), so on the host this should move nothing or
       very little.
   - **`Invoke-PmcMailPickup.ps1 -BoardId`** passes `--board-id`, so mail that no board claims lands on that board.
   - **Each `-Mailbox` keeps its own state**: its own delta link (`inbox-deltalink-<mailbox>.txt`), log and drop
     subfolder. So two pickups can share `D:\psa\mail-state` and `D:\psa\mail-drop`.
     - **Without this, two pickups would have overwritten each other's delta link.** Before this change the file was
       one fixed name, `inbox-deltalink.txt`.
     - SQL01 has not run a pickup yet (part 26), so no old state file exists to carry over.
   - Intake no longer imports a `.part` file.
2. **An email for each status.** They live in the new table `status_mail`, on the board's **Emails** tab under *An
   email at each status*.
   - **Each status has an on/off switch and its own words.** The words are the board's own, or the desk's. One button
     turns every status on.
   - **The desk's words depend on the kind of status.** Which kind a status is, is INFERRED from its settings and its
     name.
     - **Waiting on Requester** asks the requester to reply and to keep the reference in the subject, so the reply
       threads back onto the ticket. This uses the existing subject-token match.
     - **Resolved** says to reply if the problem is not fixed.
     - **Closed** sends its own email *in place of* the closed email.
     - **Any other status** says where the request is now.
   - **When an email is sent, and when it is not:**
     - Two changes before the sender runs send one email, for the newer status.
     - A move into the status the ticket is already in sends nothing.
     - A merge sends nothing.
   - **Every gate on the existing requester emails still applies:**
     - the board's *email the requester* switch;
     - a ticket raised by a person (portal, email, phone, walk-up or desk);
     - an address the desk can resolve.
   - It is audited as `STATUS_MAIL`.
3. **Placeholders.** All six that SQL01 suggested are built. They work in every email a board words, not only the
   status emails.
   - `{requester}`: the AD display name, else the part of the address before the `@`.
   - `{owner}`: who has the ticket, else "the <board> team".
   - `{status}`.
   - `{status_text}`: the status's `customer_description`.
   - `{link}`: filled in by the sender from `-PortalUrl` / `PSA_PORTAL_URL`.
   - `{date}`, for example "1 October 2026".

   **Still refused:** `{summary}`, `{note}`, and any echo of the requester's own subject.

## Item 4: which address replies

**Recommendation: reply from the address the requester wrote to. This is built.**

- **How it works.** Each requester email records the claimed address that the ticket's first email arrived on
  (`notification.from_address`).
  - `outbox-pending` hands that address to the sender as `from`.
  - `Send-PmcNotifications.ps1` sends from it only when it is `-Mailbox` or is listed in the new `-SendAs` parameter.
    Otherwise it sends from `-Mailbox`.
  - A ticket raised by any other route has no `from_address`, so its emails come from `-Mailbox`, as before.
- **What this needs.** Sending as `support@` needs **Application Mail.Send on support@**.
  - Dada's step 2 in SQL01's file already provides it: one management scope over both mailboxes, with Mail.Read and
    Mail.Send.
  - So run the sender with `-SendAs support@pmcne.ph`.
- **The `help@` alias.** `help@` is an alias, not a mailbox that Graph can send as. A reply to mail sent to `help@`
  comes from `helpdesk@`, the mailbox it aliases (INFERRED; NOT VERIFIED on the tenant).

## Step 1, corrected (SQL01 has already done it; this is the record)

```powershell
$cert = New-SelfSignedCertificate -Subject 'CN=PMC-PSA-MailPickup' `
  -CertStoreLocation Cert:\LocalMachine\My -KeyExportPolicy NonExportable `
  -KeyUsage DigitalSignature -KeyAlgorithm RSA -KeyLength 2048 -HashAlgorithm SHA256 `
  -Provider 'Microsoft Software Key Storage Provider' -NotAfter (Get-Date).AddYears(1)
```

The command drops `-KeySpec Signature`.

- **Why it failed.** KeySpec is a property of the legacy CSP providers. The Software Key Storage Provider is a CNG
  provider and has no key specification (VERIFIED by SQL01, learn.microsoft.com, "AD FS and certificate KeySpec property
  information"). On DND-SQL01 the original command failed with `NTE_PROV_TYPE_NOT_DEF` (MEASURED by SQL01).
- **Why the provider stays.** PS256 still needs the CNG provider, so `-Provider` remains in the command.

## SQL01: in order, at this head

1. **Apply 058 by the sitting-1 road.** The order is:
   1. a COPY_ONLY backup;
   2. the preview;
   3. stop PSA-Desk;
   4. apply the port;
   5. `init`, which moves any old intake address;
   6. start PSA-Desk.

   **Pass:**
   - **tables:** 126 → **128** (`board_intake_address`, `status_mail`);
   - **columns:** 1,215 → **1,225**, which is 2 + 7 + `notification.from_address`;
   - **indexes and triggers:** 52 indexes and 4 triggers, unchanged. The port's own verify block now expects 128
     tables, 52 indexes and 4 triggers (MEASURED from the generated port);
   - **rows:** none changed, except any `board.intake_address` value moving into `board_intake_address`.
2. **Set up PMO Helpdesk.** This is Dada's word to give, and SQL01 or Dada can do it on the desk.
   - **Board tab, mail-policy card, intake addresses:** `helpdesk@pmcne.ph, help@pmcne.ph, support@pmcne.ph`.
   - **Board tab:** tick *email the requester*. **This also starts the opened, updated and closed emails for every
     ticket on the board,** as built since 028.
   - **Emails tab:** *Turn every status on*, then read each status's words before the first ticket moves.
3. **The two admin steps.** These are Dada's, as SQL01's file sets them out: the Entra app, and one Exchange scope over
   both mailboxes with Mail.Read and Mail.Send.
4. **Two pickups**, using the mail handoff's steps 5–7, once per mailbox. Both point at the same database and folders.
   - **A task for helpdesk@:** `-Mailbox helpdesk@pmcne.ph -BoardId IT_HELP`.
   - **A task for support@:** `-Mailbox support@pmcne.ph -BoardId IT_HELP`.
   - **Why `-BoardId`.** The board's own claim already routes all three addresses. `-BoardId IT_HELP` is the belt for
     mail whose recipient headers name none of them, such as a Bcc.
   - **Preview each one first.** Then send one test mail, with no patient details, to each of `helpdesk@`, `help@` and
     `support@`.
   - **Pass:**
     - three tickets on PMO Helpdesk, each with its `to_address`;
     - on a third `-Apply`, `0 new`.
5. **PSA-Notify.** Run `Send-PmcNotifications.ps1 -Mailbox helpdesk@pmcne.ph -SendAs support@pmcne.ph -PortalUrl
   https://help.pmcne.ph`. Start in preview, then `-Apply -Loop`.
   - **Pass:**
     - Move the support@ test ticket to *Waiting on Requester*. One email arrives at the test sender, from `support@`,
       asking for a reply.
     - Reply to it, keeping the reference. The reply lands on the same ticket.
6. **Stop PCSD reading support@** before step 4's support@ task goes live. Dada said yes on 1 Oct.

## Dada's decisions, 1 Oct 2026, verbatim, and what came of them

> "turn on
> also the reply back to each status changes or when the ticket gets picked up make sure its set for the hospital and is dynamic and yes will sto ppcsd"

- **"turn on".** PMO Helpdesk gets its three addresses, the requester switch on, and every status email plus the
  picked-up email on. **SQL01 runs it after 058, in one audited step (preview first):**

  ```powershell
  C:\PMC\Python312\python.exe -m psaspine mail-setup "<the desk's connection>" --board IT_HELP `
    --addresses "helpdesk@pmcne.ph, help@pmcne.ph, support@pmcne.ph" --email-requester on --moving-emails on `
    --actor "sql01 for dada.banal"
  # then the same with --apply
  ```

  This replaces step 2 of "SQL01: in order" below. The Emails tab still shows and edits every word.
- **"when the ticket gets picked up".** Built. A **picked-up email** goes to the requester when a ticket's owner is set
  or changes to a person, after it was opened.
  - It shares the one unsent slot with the status emails. So "picked up" and then "In Progress" a minute later is one
    email, the newer one.
  - An owner set by auto-assign while the ticket is being opened sends nothing extra: the opened email already names
    who has it.
  - It is a card on the Emails tab, and *Turn every status on* includes it.
- **"set for the hospital and is dynamic".** All of the desk's requester wording is rewritten.
  - Every email greets the requester by name.
  - Every email says who has the ticket and the date.
  - The status emails use the status's own portal wording.
  - Every email signs off with the board and the hospital. `{hospital}` is a new placeholder: PMC's name, or
    `PSA_HOSPITAL_NAME` if it is set.
  - The opened and status emails say to call the helpdesk, quoting the reference, if the problem is stopping care on
    the ward.
  - "Waiting on Requester" asks for the ward, the room or the machine, never a patient's details.
  - No phone number is written into the code; none is in the record.
- **"yes will stop pcsd".** PCSD stops reading `support@` at cut-over. The order is: PCSD stops reading `support@`,
  then the `support@` pickup task goes live.

## Not decided here (Dada's)

- **The requester's own subject.** Whether it may be echoed back as `Re: …` is not built. Threading works without it,
  through the `[PMC-…]` reference token in the subject.
- **What stops reading `support@`:** decided on 1 Oct. PCSD stops. When it stops is Dada's, and it comes before the
  `support@` pickup goes live.

## Evidence

- **New tests, `MailCutoverTest` (4):**
  - three addresses onto one board, including the alias, a `Delivered-To`, the loop guard, `.part` files and
    `--board-id`;
  - an email at each status, with the placeholders, one email when two changes come close together, a closing status
    in place of the closed email, the switch, the reply-from address and the portal link;
  - only safe placeholders are accepted, the board's own words are used, and the desk's words come back;
  - the Emails tab, through the web layer.
- **Script tests:**
  - the pickup keeps each mailbox's state apart and passes `-BoardId`;
  - the sender sends only as `-Mailbox` or `-SendAs`.
- **The existing intake tests** were moved onto the new table, and they pass.
- **Not yet run:** the full suite on SQL Server. That is SQL01's run at this head.

## Dada's admin steps: done, 1 Oct 2026, 12:16 to 12:17 +08:00 (MEASURED, from the output Dada pasted)

`D:\psa\bin\New-PsaMailApp.ps1 -Apply`, run as `PMCNE\dada.banal`, after a clean preview at 11:54. This covers steps 2
and 3 of the mail handoff for both mailboxes.

1. **The Entra app.** *PMC PSA mail pickup* is registered with one key credential, the `CN=PMC-PSA-MailPickup`
   certificate, which expires 1 Oct 2027.
   - API permissions: **0**.
   - Its service principal was created.
   - Its identifiers were written to `D:\psa\mail-app.txt` and not printed. Only SYSTEM, Administrators and `psa_desk`
     can read that file.
2. **The two mailboxes.** `helpdesk@pmcne.ph` and `support@pmcne.ph` are both SharedMailbox.
3. **Exchange.** Exchange knows the service principal. Application Mail.Read and Application Mail.Send are assigned on
   the scope over both mailboxes.
4. **The tests:**
   - Mail.Read and Mail.Send on `helpdesk@`: **InScope True**.
   - Mail.Read and Mail.Send on `support@`: **InScope True**.
   - Both on another mailbox: **InScope False**.

   So the app reaches the two desk mailboxes and nothing else.
5. **The script's own word:** "Tell SQL01 'mail app done'". The permission can take 30 minutes to 2 hours to take
   effect, so a pickup preview that gets 403 before then is the cache, not a fault.

**Next, SQL01:**
1. apply 058;
2. run `mail-setup`;
3. preview the two pickups;
4. send one test mail each to `helpdesk@`, `help@` and `support@`;
5. start PSA-Notify with `-SendAs support@pmcne.ph`.

The `support@` pickup goes live only after PCSD stops reading `support@`.

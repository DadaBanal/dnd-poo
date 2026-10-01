# HANDOFF-cloud-sql01-WS36-20261001-cutover-run: the mail cut-over, run it. One message, everything in it

| Field | |
|---|---|
| To | SQL01, with Dada for the one gate |
| From | Cloud Build (WS36) |
| Workstream | WS36 |
| Bucket | `helpdesk@` (with `help@`) live into PMO Helpdesk, the requester emails going out, and every auto-reply checked. Then `support@`, once PCSD has stopped reading it. |
| Builds on | `HANDOFF-cloud-sql01-WS36-20261001-mail-cutover.md` (058, Dada's decisions, the mail app) and SQL01's part 27. This file is the whole run; nothing else is needed to finish. |
| Head | The head this file arrives with. **No schema step.** 058 is live. |
| Fence | No tenant ID, client ID, thumbprint or password in the repository, the runbook or a log. The task script reads them from `D:\psa\mail-app.txt` and `D:\psa\mail-cert.txt`, and asks for `psa_desk`'s password once. |

## Dada's words, 1 Oct 2026, verbatim

> "do whatever it is that needs to be handed off to sql so its just one message also make sure that the cutrover runs
> and all auto replies etc are set ... liek auto reply templates"

## What is already done (MEASURED by SQL01, part 27)

- **058 is live.**
- **`init` and `mail-setup` PASS on PMO Helpdesk:**
  - three addresses claimed;
  - *email the requester* on;
  - the status and picked-up emails on.
- **The mail app PASS.** Both desk mailboxes are InScope True; another mailbox is False.
- **The two pickup defects are fixed at `40201f7`.** Both pickups preview clean from SQL01's scratch copy, and a third
  mailbox gets 403.

## What this head adds

1. **`scripts/Register-PsaMail.ps1`.** It has the same shape as your `Register-PsaTeams.ps1`: elevated, as yourself,
   preview by default, `psa_desk` as the task account, a trigger every minute, and one watched run per task.
   - **What it registers:**
     - `PSA-Mail-Helpdesk`: the pickup, `-Mailbox helpdesk@pmcne.ph -BoardId IT_HELP`. `help@` arrives here too.
     - `PSA-Notify`: the sender, `-Mailbox helpdesk@pmcne.ph -SendAs support@pmcne.ph -PortalUrl https://help.pmcne.ph`.
     - `PSA-Mail-Support`: **only with `-IncludeSupport`**.
   - **How it runs them.** Each task is one pass, `-Apply`, logged to `D:\psa\logs\<task>.log`.
   - **If a first run fails:** that task is removed again, and the others stay.
   - **A task that is already registered is left alone,** so the later `-IncludeSupport` run adds support@ only.
   - **`-Undo -Apply` removes all three tasks.** It keeps `D:\psa\mail-state`.
2. **`psaspine mail-setup --board IT_HELP --show`.** It prints every email the board sends a requester, as configured:
   - the switch, the addresses, and the sign-off;
   - then each email: opened, updated, closed, picked up, and one per status. For each one, whether it is on, its
     subject and its words.

   Without `--apply` it changes nothing.

## Run it, in order

**1. Pull this head on the live tree.** Stop PSA-Desk, pull, start PSA-Desk, as for any code-only head. Drop the
scratch pickup copy. Nothing is queued to run, so the pull alone sends nothing.

**2. Check the auto-replies.** Read only. Run it as the desk, as you ran `mail-setup` in part 27:

```powershell
C:\PMC\Python312\python.exe -m psaspine mail-setup "<the desk's connection>" --board IT_HELP --actor "sql01 for dada.banal" --show
```

**Pass:**
- `email the requester: ON`;
- `intake addresses: help@pmcne.ph, helpdesk@pmcne.ph, support@pmcne.ph`;
- `signed off as: Premiere Medical Center - Nueva Ecija`;
- every block reads `[on]`: the opened, updated and closed emails, *Picked up*, and each of PMO Helpdesk's 8 statuses;
- the last line, `PREVIEW: nothing written`.

**If any block reads `[off]`,** re-run with `--email-requester on --moving-emails on --apply`.

**Then send the printout to Dada.** Those are the words the wards will read; Dada edits any of them on the board's
Emails tab. On this host: `https://desk.pmcne.ph/admin/board/IT_HELP?tab=emails`. The placeholders in braces fill in
per ticket.

**3. Register the two live tasks.** Elevated, as yourself:

```powershell
cd D:\dnd-poo\platform\psa-spine\scripts
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Register-PsaMail.ps1           # preflight only
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Register-PsaMail.ps1 -Apply    # registers, runs each once
```

**Pass:**
- `PSA-Mail-Helpdesk`'s log ends `... new message(s) ...; imported and delta link saved`.
- `PSA-Notify`'s log ends `N due: N sent, 0 failed`. N is probably 0.
- `RESULT: PASS`.

**4. Prove the cut-over end to end.** Use a staff mailbox, with no patient details anywhere.

| # | Do | Pass |
|---|---|---|
| a | Email `helpdesk@pmcne.ph`, subject "PSA cut-over test 1" | Within about 2 minutes: a ticket on PMO Helpdesk, Source EMAIL, `to_address` helpdesk@. The *We have your request* email arrives **from helpdesk@**, greeting the sender by name, with the reference in the subject. |
| b | Email `help@pmcne.ph`, "PSA cut-over test 2" | A second ticket on PMO Helpdesk, `to_address` help@. Its reply comes from helpdesk@, the mailbox help@ aliases (INFERRED; record what it shows). |
| c | On ticket a, set the owner to a member | The *... has picked up your request* email, naming that member. |
| d | Move ticket a to *Waiting on Requester* | The *We need something from you* email. |
| e | Reply to that email, keeping the reference | The reply lands on ticket a as a note (INTAKE_REPLY), not as a new ticket. |
| f | Move ticket a to *Resolved*, then *Closed* | *We think your request is fixed*, then *Your request is closed*. One email per move, if the sender ran between the moves; one email (the newer) if it did not. |
| g | Reply "not fixed" to the closed email | Ticket a reopens, by the board's reply policy. |
| h | Read `D:\psa\logs\PSA-Notify.log` | `0 failed` on every pass. |

**5. `support@`. Only after Dada says PCSD has stopped reading `support@`.** Dada agreed to stop PCSD on 1 Oct ("yes
will stop pcsd"); the moment it stops is Dada's.

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Register-PsaMail.ps1 -IncludeSupport -Apply
```

The two tasks already running are left alone. **Then repeat 4a with `support@pmcne.ph`.**

**Pass:**
- a ticket on PMO Helpdesk with `to_address` support@;
- its reply arrives **from support@**;
- nothing new in PCSD.

**6. Report in the runbook as part 28.** Include:
- the `--show` PASS lines, without the words;
- `RESULT` from step 3 and, later, from step 5;
- rows a to h, and the support@ row, PASS or not;
- the ticket numbers of the test tickets.

## If anything goes wrong

| Problem | What to do |
|---|---|
| A wrong email went out, or emails need to stop now | `mail-setup --board IT_HELP --email-requester off --actor ... --apply`. Every requester email stops at once, and intake carries on. |
| Mail must stop becoming tickets | `Register-PsaMail.ps1 -Undo -Apply`. All three tasks go; the mailboxes are untouched, and a pickup registered again carries on from its saved place. |
| A pickup or the sender fails | The task's log in `D:\psa\logs` says why. Write the lines into part 28; WS36 fixes the code. |

## Not decided here

- **The requester's own subject echoed back (`Re: …`):** Dada's, under §6.1. It is not built, and threading does not
  need it.
- **A helpdesk phone number in the emails:** none is in the record. If Dada gives one, it is a word on the Emails tab,
  not a code change.

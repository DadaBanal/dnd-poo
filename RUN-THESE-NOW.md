# What to run on DND-SQL01, 2 Oct 2026

Everything below is in the repo. Take it with one pull on the host, as the account that owns the checkout:

    cd D:\dnd-poo
    git pull

If the pull refuses because the two scripts saved by hand differ from the repository, throw the hand-saved
copies away and take the tested ones (this touches nothing outside that one folder):

    git checkout -- platform/psa-spine/scripts
    git clean -fd platform/psa-spine/scripts
    git pull

## Where you are now (MEASURED, from your own runs on 2 Oct 2026)

| | |
|---|---|
| The mail plumbing | healthy. All four tasks run every minute with result 0, the certificate is good until 1 Oct 2027, both delta links move. |
| The mailbox | has the mail: **12 on helpdesk@ and 66 on support@** at 10:06, first sync from 30 Sep. The fault was never there. |
| Your own sign-in | cannot talk to the desk, and that is by design: SQL Server maps every sysadmin to database user `dbo`, and the desk refuses `dbo` so it can never write to the wrong schema. `Invoke-PsaSpine.ps1` runs a command as the desk's own account instead, reads that account's name from the PSA-Desk task, and worked. |
| Set aside | **9 messages**, released at 10:0x, exit 0. The audit truncation is fixed and now PROVEN on the host, not just in the suite. |
| The 78 in the mailbox | still not imported, and now explained: a delta reset was being undone by the next task pass within a minute. See step 2. |
| `-ViaTask` | failed with `Access is denied` registering the one-shot task, then buried that error under three more. Fixed to stop at the first one and say why. Use the password prompt, which worked. |

### What was wrong with `-MailRetry -All -Apply`, and what changed

The audit row each release writes names its subject in `audit_event.subject_id`, a key column 64 characters
wide. A mail Message-ID is not our key and is longer than that, so SQL Server refused the whole statement and
nothing was released. (SQLite would have stored it and said nothing, which is why the cloud suite never saw it.
The same defect SQL01 found in part 28 for `data_quality.subject_id`.)

The key is now cut to what the column holds and marked as cut, and the **whole** Message-ID is written into
`detail`, which is unbounded and is the field Setup > Audit searches. Nothing is lost, no schema change is
needed for it, and the index stays as narrow as it was designed to be.

## The order to run them in

Elevated, on DND-SQL01, from `D:\dnd-poo\platform\psa-spine\scripts`, after `git pull`. Two things that
failed at 10:05 are fixed in this pull, so these are not the same lines again.

**1. The schema step, and the restart that goes with it.** The desk does not pick up new code until
PSA-Desk restarts, so the ticket editor, the pods behind the Edit button and the portal 404 fix are all in the
repo but not yet on your screen. The order is the usual one: COPY_ONLY backup, preview, **stop PSA-Desk**,
apply, `init`, **start PSA-Desk**.

`-SchemaPreview` and `-SchemaApply` answered `unrecognized arguments` before: in PowerShell `1..0` counts down,
so a one-word command went in twice. Fixed.

    .\Invoke-PsaSpine.ps1 -SchemaPreview
    .\Invoke-PsaSpine.ps1 -SchemaApply

If `psa_desk` is refused for want of ALTER rights, run the generated port as a sysadmin instead -- it does not
go through the desk's connection guard: `sqlcmd -I -S "DND-SQL01\PMC_SS" -d PMC_PSA -i
D:\dnd-poo\platform\psa-spine\sqlserver\PMC_PSA_Spine_SqlServer.sql`, with `@Apply = 1` and
`@AllowExisting = 1` at the head of that file.

**2. Import the 78 waiting messages.** One line, and this is the whole of it now:

    powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Repair-PsaMailPickup.ps1 -Apply -ResetDelta -AsDesk

Step 6 now says `(importing from <date>)` per mailbox and then how many it took. **Why the last two resets
imported nothing:** the scheduled task runs the pickup with no `-Since`, and that parameter defaults to *now*. So
the first task pass after a reset asked Graph for mail since that minute, found none, and saved a fresh delta link
over the window the reset was meant to re-read -- within 60 seconds, every time. Your own log says it: links
cleared at 09:39, then every pass `0 new message(s) since last pass`, while a preview from `-Since` could still see
12 and 66. The pass that follows a reset is now this script's to run, with the window, for real.

**3. Then the calendar work**, which is section 2 below and still needs Setup > Members first.

### What the restart brings with it

All of this is already on the branch and needs nothing from SQL01 beyond PSA-Desk coming back up: the note box
is a real editor (copy and paste, bold, lists, a link, and a paste out of Outlook that keeps the words and none
of the markup); the side pods are fixed and move only behind the **Edit layout** button, with small/half/medium/
full widths and plus-minus height; the mega menu; and the portal 404 fix for a requester whose mail address and
sign-in are on different domains. The editor needs 064 as well as the restart -- without those two columns a
note will not save.

### Or the one line, for everything that does not need a decision

    powershell.exe -NoProfile -ExecutionPolicy Bypass -File D:\dnd-poo\platform\psa-spine\scripts\Fix-PsaToday.ps1 -AsDesk

That changes nothing: it pulls the code, runs the mail repair in preview, asks the desk what it has taken, and
checks whether encoder is in the calendar list. Read it, then run it again with `-Apply -AsDesk`, which starts a
stopped mail task, clears a delta link Graph says has expired, writes the members list and runs the calendar
grant (a browser window opens for Exchange Online). It ends with a numbered **what is left for you**, which
includes steps 1 and 2 above, because those two are the desk's own account to be asked and it will not guess
whether you have run them.

`-AsDesk` is new and a sysadmin needs it: without it every question this line puts to the desk is put under your
own login, which resolves to `dbo` and is refused. It does not change what the line may write.

It will NOT grant the calendars if encoder is missing from the list, because the list is what it grants. Do
Setup > Members first, then run the line again.

---

## 1. Inbound mail has stopped again: find out which cause it is

    cd D:\dnd-poo\platform\psa-spine\scripts
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Repair-PsaMailPickup.ps1

It changes nothing. It reads, in order: the scheduled tasks (registered, enabled, last run, last result), the
sign-in certificate (found, and the day it expires), the delta link and log for each mailbox, the drop and files
folders including anything in `failed\`, and then runs one real pass per mailbox in preview so Graph's own answer
is on the record. It ends with a numbered list of what is wrong and the one command that fixes each.

Then, elevated, let it fix what is safe:

    powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Repair-PsaMailPickup.ps1 -Apply

If the preview said **410** for a mailbox, its Graph bookmark has expired. Clear it as well:

    powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Repair-PsaMailPickup.ps1 -Apply -ResetDelta

A copy of the old bookmark is kept beside it, and no message is imported twice: the import is keyed by Message-ID.

One of its steps asks the desk itself, and that is the step that tells the two faults apart. Add `-AsDesk` to any
of the three lines above so it is asked under the right account, or ask it alone:

    cd D:\dnd-poo\platform\psa-spine\scripts
    .\Invoke-PsaSpine.ps1 -MailHealth

(Do not type the connection string. `<the desk's connection>` in an earlier note was a placeholder; typed
literally, Python read it as a SQLite filename and said "unable to open database file". These scripts fill it in.)

It prints when the desk last took a message and what became of it, what came of the ones since, and which
addresses a board claims. **A silent desk with a busy mailbox is the pickup's fault**: nothing is reaching the
desk at all, so the task, the certificate or the delta link is the cause. **Messages taken but set aside** is
intake's fault instead, and `psaspine mail-why --sender <them>` names it for one of them.

**Look at PSA-Mail-Helpdesk first.** SQL01's part 30 listed PSA-Rules, PSA-Notify, PSA-Mail-Support and
PSA-Calendar as healthy and did not mention PSA-Mail-Helpdesk at all. If that task is missing or disabled, mail to
helpdesk@ and help@ is not being picked up and nothing else explains it. The script says which it is.

The pickup itself was also fixed: an expired delta link used to throw on every pass from then on, so mail stopped
and nothing ever restarted it. It now forgets the link and reads from `-Since` instead.

---

## 2. Add encoder@premieremedicalcenter.net to the calendar sync

Three things must all be true, and the first two are on the desk, not in a script:

1. **a member record with that email** - Setup > Members > encoder > Email = `encoder@premieremedicalcenter.net`.
   You can do this from your normal Windows sign-in now; SQL01 made you a desk sysadmin in part 30.
2. **WORK or ADMIN on a board** - same page, the Boards card. A member with READ only is not in the sync.
3. **the domain named** - the calendar scripts used to name one domain and filter everything else out. They now
   take a list.

Then regenerate the members file you are already using and check encoder is in it:

    cd D:\dnd-poo\platform\psa-spine
    C:\PMC\Python312\python.exe -m psaspine calendar-members "<the desk's connection>" ^
        --allowed-domain pmcne.ph --allowed-domain premieremedicalcenter.net > D:\psa\calendar-members.json
    findstr /i encoder D:\psa\calendar-members.json

If that findstr prints nothing, step 1 or 2 is not done yet; no script will help until it is.

Then grant, as you were going to:

    cd D:\dnd-poo\platform\psa-spine\scripts
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Grant-PsaCalendars.ps1 -MembersFile D:\psa\calendar-members.json
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Grant-PsaCalendars.ps1 -MembersFile D:\psa\calendar-members.json -Apply

The permission can take 30 minutes to 2 hours to take effect; the script tests it and says InScope True or NOT YET
for each mailbox.

Last, so the scheduled sync keeps naming both domains (otherwise PSA-Calendar still names only pmcne.ph and will
skip encoder's calendar):

    Unregister-ScheduledTask -TaskName 'PSA-Calendar' -Confirm:$false
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Register-PsaMail.ps1 -IncludeSupport -IncludeCalendar ^
        -CalendarDomain pmcne.ph,premieremedicalcenter.net -Apply

(`Register-PsaMail.ps1` leaves an already-registered task as it is, which is why PSA-Calendar is removed first.)

To check it by hand before the task next runs:

    powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Sync-PsaCalendars.ps1 ^
        -TenantId <from mail-app.txt> -ClientId <from mail-app.txt> -CertThumbprint <from mail-app.txt> ^
        -Database "<the desk's connection>" -AllowedDomain pmcne.ph,premieremedicalcenter.net ^
        -DeskUrl https://desk.pmcne.ph

Without `-Apply` it signs in, says how many writes are due and how many calendars it would read, and writes nothing.

---

## Not verified

Nothing here was run against DND-SQL01 or Exchange from the cloud session: there is no PowerShell and no route to
the host here, so every script change is checked as text by the suite (702 tests, OK) and by nothing else. What is
labelled MEASURED above was measured by you, in the output you pasted.

The audit fix is now MEASURED good on the host: 9 messages released, exit 0. Whether `psa_desk` may ALTER in
PMC_PSA, and whether the real pass in step 6 takes all 78 cleanly, is NOT VERIFIED until you run them.

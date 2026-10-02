# Two things to run on DND-SQL01, 2 Oct 2026

Both scripts are in the repo. Get them with one pull on the host, as the account that owns the checkout:

    cd D:\dnd-poo
    git pull

Nothing below needs SQL01 to do anything, and neither changes the schema.

## Where you are now (2 Oct 2026, 08:44 on DND-SQL01, MEASURED from your own run)

The pull worked, the certificate is good until 1 Oct 2027, all four tasks run every minute with result 0, and
both delta links were cleared. The preview straight after said **13 messages waiting on helpdesk@ and 68 on
support@**, first sync from 30 Sep. So mail is reaching those two Inboxes after all; the fault was never there.

Two things still stand between those messages and tickets on the board.

### Your own sign-in cannot talk to the desk

Every `psaspine` command you ran answered:

    the desk's login must have default schema [psa] on this database; it has [dbo].

That is not a fault on your account. SQL Server maps every member of the sysadmin role to the database user
`dbo`, whose default schema is `dbo` and cannot be changed, and the desk refuses `dbo` on purpose so it can
never write to the wrong schema. Run desk commands as the account the desk itself runs as:

    cd D:\dnd-poo\platform\psa-spine\scripts
    .\Invoke-PsaSpine.ps1 -MailHealth

It asks for the psa_desk password once, runs the command as that account, prints what it said, and keeps the
password nowhere. (Where you typed `"<the desk's connection>"` literally, that was a placeholder, which is why
Python fell back to SQLite and said "unable to open database file". This script fills it in for you.)

### The messages already set aside have to be released

Every subjectless mail so far was recorded UNCLASSIFIED, and the pickup will never offer it again on its own
because it remembers the Message-ID. There were about seventy of them, so there is now one command for all:

    .\Invoke-PsaSpine.ps1 -MailRetry
    .\Invoke-PsaSpine.ps1 -MailRetry -All -Apply
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Repair-PsaMailPickup.ps1 -Apply -ResetDelta

The first lists what was set aside and changes nothing. The second releases them all, one audit row each; a
message that already made a ticket is never released, so nothing is duplicated. The third makes the pickup read
back over the last two days, and within a minute or two those requests appear on the Service Board.

---

## First: the pull refused, so the host is still on the old code

MEASURED on DND-SQL01, 2 Oct 2026. The scripts saved into `scripts\` by hand differ from the repository, so
`git pull` would overwrite them and refused. Everything after it read the old code, which is why `mail-health`
came back as an unknown command.

Throw away the hand-saved copies and take the repository's, which are the tested ones:

    cd D:\dnd-poo
    git checkout -- platform/psa-spine/scripts
    git clean -fd platform/psa-spine/scripts
    git pull

`git clean -fd` on that one folder removes files git does not track, which here is exactly the two scripts saved
by hand. It touches nothing outside `platform\psa-spine\scripts`.

---

## The one line

Elevated, on DND-SQL01:

    powershell.exe -NoProfile -ExecutionPolicy Bypass -File D:\dnd-poo\platform\psa-spine\scripts\Fix-PsaToday.ps1

That changes nothing: it pulls the code, runs the mail repair in preview, asks the desk what it has taken, and
checks whether encoder is in the calendar list. Read what it says, then run it again with `-Apply`:

    powershell.exe -NoProfile -ExecutionPolicy Bypass -File D:\dnd-poo\platform\psa-spine\scripts\Fix-PsaToday.ps1 -Apply

With `-Apply` it starts a stopped mail task, clears a delta link that Graph says has expired, writes the members
list, and runs the calendar grant (a browser window opens for Exchange Online). It ends with a numbered list
headed **what is left for you**, which is only ever the things a script may not decide: a member record, and
re-registering a scheduled task, because that asks for the task account's password.

It will NOT grant the calendars if encoder is missing from the list, because the grant is the last step and the
list is what it grants. Do Setup > Members first, then run the line again.

The rest of this file is the same jobs by hand, if you would rather do them one at a time.

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

One of its steps asks the desk itself, and that is the step that tells the two faults apart. You can run it alone,
as the task account:

    cd D:\dnd-poo\platform\psa-spine
    C:\PMC\Python312\python.exe -m psaspine mail-health "<the desk's connection>"

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

Nothing here was run against DND-SQL01 or Exchange from the cloud session. The two script changes and the new
script are covered by the suite as text (652 tests, OK), not by a run on the host.

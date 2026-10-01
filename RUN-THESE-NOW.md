# Two things to run on DND-SQL01, 2 Oct 2026

Both scripts are in the repo. Get them with one pull on the host, as the account that owns the checkout:

    cd D:\dnd-poo
    git pull

Nothing below needs SQL01 to do anything, and neither changes the schema.

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

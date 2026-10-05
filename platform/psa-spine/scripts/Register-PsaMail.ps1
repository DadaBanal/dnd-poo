<#
.SYNOPSIS
    Register the mail cut-over's tasks: PSA-Mail-Helpdesk, PSA-Mail-Support and PSA-Notify, every minute, LIVE.

.DESCRIPTION
    The mail cut-over's host step (docs/handoffs/HANDOFF-cloud-sql01-WS36-20261001-cutover-run.md). Run it elevated,
    as yourself, on DND-SQL01. Same shape as Register-PsaTeams.ps1: one task per job, a time trigger every minute (a
    loop that dies stops silently; a trigger starts a fresh pass whatever happened to the last), the desk's task
    account, and one watched run before it says PASS.

    The tasks:
      PSA-Mail-Helpdesk  Invoke-PmcMailPickup.ps1 -Mailbox helpdesk@pmcne.ph -BoardId IT_HELP -Apply (one pass).
                         Mail to help@ arrives here too: it is an alias of this mailbox.
      PSA-Mail-Support   the same for support@pmcne.ph. Registered ONLY with -IncludeSupport, which is for after
                         PCSD has stopped reading support@ (Dada, 1 Oct: "yes will stop pcsd"); before that, every
                         message to support@ would become two tickets, one in each system.
      PSA-Mail-Procurement  the same for procurement@pmcne.ph -> the Procurement board. Registered ONLY with
                         -IncludeProcurement, which is for after procurement@ exists as a shared mailbox and the
                         app's "PSA desk mailboxes" scope has been widened to include it (Dada, 5 Oct 2026). Its
                         first run 404s until that Exchange grant has propagated, so register it after it does.
      PSA-Calendar       Sync-PsaCalendars.ps1 -Apply (one pass): visits and tasks onto members' Outlook calendars,
                         their busy times back. Registered ONLY with -IncludeCalendar, which is for after Dada has
                         given the app Application Calendars.ReadWrite on the desk members' scope.
      PSA-Notify         Send-PmcNotifications.ps1 -Mailbox helpdesk@pmcne.ph -SendAs support@pmcne.ph
                         -PortalUrl https://help.pmcne.ph -Apply (one pass): the requester emails go out.

    It reads the app's identifiers from D:\psa\mail-app.txt (written by New-PsaMailApp.ps1) and the certificate's
    thumbprint from D:\psa\mail-cert.txt. They are identifiers, not secrets; they go into the task definitions and
    nowhere else, and this script never prints them.

    With -Apply it asks once for DND-SQL01\psa_desk's password (Task Scheduler needs it; it goes nowhere else), then
    registers each task, runs it once and reads its log. A task whose first run does not pass is removed again and
    the others are kept; the result says which.

    PREVIEW BY DEFAULT: without -Apply it runs the preflight and changes nothing.
    A task that is already registered is left as it is, so the later -IncludeSupport run adds PSA-Mail-Support alone.
    -Undo -Apply removes all three tasks (-Undo alone says what it would do). It leaves D:\psa\mail-state alone, so
    a pickup registered again carries on from where it stopped.

.EXAMPLE
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Register-PsaMail.ps1
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Register-PsaMail.ps1 -Apply
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Register-PsaMail.ps1 -IncludeSupport -Apply
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Register-PsaMail.ps1 -IncludeProcurement -Apply
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Register-PsaMail.ps1 -Undo -Apply
#>
[CmdletBinding()]
param([switch]$Apply, [switch]$Undo, [switch]$IncludeSupport, [switch]$IncludeCalendar, [switch]$IncludeProcurement,
      # A task whose first pass fails is normally removed again, so a broken task
      # never stays behind silently. The ONE exception this switch names: a first
      # pass whose only failure is 403 Forbidden, which is what a freshly granted
      # mailbox answers until Exchange's data plane catches up with its own
      # management plane (MEASURED 5 Oct 2026: procurement@ InScope True on
      # Test-ServicePrincipalAuthorization, 403 ErrorAccessDenied from Graph on
      # the same minute, helpdesk@ 200 on the same token). With this switch that
      # task is KEPT: it fails quietly each minute and comes alive by itself the
      # moment the grant lands. Explicit and off by default, so the safety stays.
      [switch]$KeepOnForbidden,
      # The mail domains whose members have an Outlook calendar to sync. Named
      # once, here, so PSA-Calendar's own command carries them (Dada, 2 Oct
      # 2026: a member's mailbox on premieremedicalcenter.net). A mailbox on no
      # named domain is never written to.
      [string[]]$CalendarDomain = @('pmcne.ph'))
$ErrorActionPreference = 'Stop'

$Acct     = 'DND-SQL01\psa_desk'
$Spine    = 'D:\dnd-poo\platform\psa-spine'
$Pickup   = $Spine + '\scripts\Invoke-PmcMailPickup.ps1'
$Notifier = $Spine + '\scripts\Send-PmcNotifications.ps1'
$Calendar = $Spine + '\scripts\Sync-PsaCalendars.ps1'
$AppFile  = 'D:\psa\mail-app.txt'
$CertFile = 'D:\psa\mail-cert.txt'
$Logs     = 'D:\psa\logs'
$LogFile  = $Logs + '\Register-PsaMail.log'
$Db       = 'Driver={ODBC Driver 17 for SQL Server};Server=DND-SQL01\PMC_SS;Database=PMC_PSA;Trusted_Connection=yes;Encrypt=yes;TrustServerCertificate=yes'
$AllTasks = @('PSA-Mail-Helpdesk', 'PSA-Mail-Support', 'PSA-Mail-Procurement', 'PSA-Notify', 'PSA-Calendar')

function Write-Step([string]$Text) {
    $line = (Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + '  ' + $Text
    Write-Host $line
    Add-Content -Path $LogFile -Value $line -Encoding UTF8
}

# --- who is running this
$me = [Security.Principal.WindowsIdentity]::GetCurrent()
if ($me.Name -match '\\psa_desk$') { throw 'Run this as yourself, not as the desk task account. Nothing was done.' }
if (-not ([Security.Principal.WindowsPrincipal]$me).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Run this from an elevated PowerShell (Run as administrator). Nothing was done.'
}
if (-not (Test-Path $Logs)) { New-Item -ItemType Directory -Path $Logs | Out-Null }
Write-Step ('start as ' + $me.Name + $(if ($Undo) { ' (-Undo)' } else { '' }) +
    $(if ($IncludeSupport) { ' (-IncludeSupport)' } else { '' }) + $(if ($IncludeProcurement) { ' (-IncludeProcurement)' } else { '' }) +
    $(if ($Apply) { ' (-Apply)' } else { ' (preview: nothing is changed)' }))

if ($Undo) {
    foreach ($t in $AllTasks) {
        if (-not (Get-ScheduledTask -TaskName $t -ErrorAction SilentlyContinue)) { continue }
        if ($Apply) { Unregister-ScheduledTask -TaskName $t -Confirm:$false; Write-Step ('removed task ' + $t) }
        else { Write-Step ('would remove task ' + $t) }
    }
    Write-Step $(if ($Apply) { 'RESULT: undone.' } else { 'RESULT: preview. -Undo -Apply does it.' })
    return
}

# --- preflight (changes nothing)
$fail = @()
foreach ($f in @($Pickup, $Notifier, $Calendar, $AppFile, $CertFile)) { if (-not (Test-Path $f)) { $fail += $f + ' is missing' } }
$ids = @{}
if (Test-Path $AppFile) {
    foreach ($l in Get-Content $AppFile) { if ($l -match '^\s*(\w+)\s*=\s*(\S+)\s*$') { $ids[$Matches[1]] = $Matches[2] } }
    foreach ($k in 'AppId', 'TenantId') { if (-not $ids[$k]) { $fail += $AppFile + ' has no ' + $k } }
}
$thumb = $null
if (Test-Path $CertFile) {
    $m = [regex]::Match((Get-Content $CertFile -Raw), '\b[0-9A-Fa-f]{40}\b')
    if ($m.Success) { $thumb = $m.Value } else { $fail += $CertFile + ' holds no certificate thumbprint' }
}
if ($thumb -and -not (Test-Path ('Cert:\LocalMachine\My\' + $thumb))) { $fail += 'the mail certificate is not in LocalMachine\My' }
# A task already registered is left exactly as it is, so -IncludeSupport later adds support@ alone.
$want = @()
foreach ($t in @('PSA-Mail-Helpdesk', 'PSA-Notify') + $(if ($IncludeSupport) { @('PSA-Mail-Support') } else { @() }) +
                $(if ($IncludeProcurement) { @('PSA-Mail-Procurement') } else { @() }) +
                $(if ($IncludeCalendar) { @('PSA-Calendar') } else { @() })) {
    if (Get-ScheduledTask -TaskName $t -ErrorAction SilentlyContinue) { Write-Step ('  ' + $t + ' is already registered: left as it is') }
    else { $want += $t }
}
if (-not $want.Count -and -not $fail.Count) { Write-Step 'RESULT: nothing to register. Nothing was changed.'; return }
$rules = Get-ScheduledTask -TaskName 'PSA-Rules' -ErrorAction SilentlyContinue
if (-not $rules -or $rules.Principal.UserId -notmatch 'psa_desk$') { $fail += 'PSA-Rules is not visible as a psa_desk task (is this PowerShell elevated?)' }
if ($fail.Count) { foreach ($f in $fail) { Write-Step ('  BLOCKED: ' + $f) }; Write-Step 'RESULT: BLOCKED. Nothing was changed.'; exit 1 }
Write-Step ('preflight: the scripts, the app identifiers and the certificate are present; to register: ' + ($want -join ', '))
if (-not $IncludeSupport) { Write-Step '  support@ is NOT included: re-run with -IncludeSupport once PCSD has stopped reading it' }
if (-not $Apply) { Write-Step 'RESULT: preflight PASS. Nothing was changed (preview; -Apply registers the tasks).'; return }

# --- the tasks
$cred = Get-Credential -UserName $Acct -Message ('Password for ' + $Acct + ' (Task Scheduler needs it to run the mail tasks; it goes nowhere else)')
if (-not $cred) { Write-Step 'RESULT: no password given. Nothing was changed.'; exit 1 }
$pw = $cred.GetNetworkCredential().Password
$common = " -TenantId '" + $ids['TenantId'] + "' -ClientId '" + $ids['AppId'] + "' -CertThumbprint '" + $thumb +
          "' -Database '" + $Db + "' -StateDir 'D:\psa\mail-state' -SpineDir '" + $Spine + "' -Apply"
$jobs = @{
    'PSA-Mail-Helpdesk' = @{ Script = $Pickup; Args = " -Mailbox 'helpdesk@pmcne.ph' -BoardId 'IT_HELP' -DropDir 'D:\psa\mail-drop'"
                             Pass = 'new message\(s\)'; What = 'mail to helpdesk@ (and help@) becomes tickets on PMO Helpdesk' }
    'PSA-Mail-Support'  = @{ Script = $Pickup; Args = " -Mailbox 'support@pmcne.ph' -BoardId 'IT_HELP' -DropDir 'D:\psa\mail-drop'"
                             Pass = 'new message\(s\)'; What = 'mail to support@ becomes tickets on PMO Helpdesk' }
    'PSA-Mail-Procurement' = @{ Script = $Pickup; Args = " -Mailbox 'procurement@pmcne.ph' -BoardId 'PROCUREMENT' -DropDir 'D:\psa\mail-drop'"
                             Pass = 'new message\(s\)'; What = 'mail to procurement@ becomes tickets on Procurement' }
    'PSA-Calendar'      = @{ Script = $Calendar; Args = " -DeskUrl 'https://desk.pmcne.ph' -AllowedDomain " + (($CalendarDomain | ForEach-Object { "'" + $_ + "'" }) -join ',')
                             Pass = 'write\(s\) due: \d+ written'; What = "the desk's visits and tasks on members' Outlook calendars, and their busy times back" }
    'PSA-Notify'        = @{ Script = $Notifier; Args = " -Mailbox 'helpdesk@pmcne.ph' -SendAs 'support@pmcne.ph' -PortalUrl 'https://help.pmcne.ph' -AllowedDomain '*'"
                             Pass = '\d+ due: \d+ sent, \d+ failed'; What = 'the requester emails go out' }
}
$passed = @(); $failed = @(); $kept = @()
foreach ($t in $want) {
    $j = $jobs[$t]
    $log = $Logs + '\' + $t + '.log'
    $cmd = "`$env:PYTHONDONTWRITEBYTECODE = '1'; & '" + $j.Script + "'" + $common + $j.Args + " *> '" + $log + "'"
    $now = Get-Date
    $reg = @{
        TaskName    = $t
        Action      = (New-ScheduledTaskAction -Execute 'powershell.exe' -Argument ('-NoProfile -ExecutionPolicy Bypass -Command "' + $cmd + '"'))
        Trigger     = (New-ScheduledTaskTrigger -Once -At $now.Date.AddHours($now.Hour).AddMinutes($now.Minute + 2) -RepetitionInterval (New-TimeSpan -Minutes 1))
        Settings    = (New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 5) -StartWhenAvailable)
        User        = $Acct
        Password    = $pw
        RunLevel    = 'Limited'
        Description = ('Dada PSA mail cut-over, LIVE: ' + $j.What + '. One pass a minute.')
    }
    try { Register-ScheduledTask @reg | Out-Null } catch {
        Write-Step ('  FAIL: ' + $t + ' could not be registered: ' + $_.Exception.Message); $failed += $t; continue
    }
    Write-Step ('registered ' + $t + ' as ' + $Acct + ', every minute, LIVE: ' + $j.What)
    $before = (Get-ScheduledTaskInfo -TaskName $t).LastRunTime
    Start-ScheduledTask -TaskName $t
    $deadline = (Get-Date).AddSeconds(150)
    do {
        Start-Sleep -Seconds 3
        $info = Get-ScheduledTaskInfo -TaskName $t
        $state = (Get-ScheduledTask -TaskName $t).State
    } while ((Get-Date) -lt $deadline -and ($state -eq 'Running' -or $info.LastRunTime -eq $before))
    $lines = @()
    if (Test-Path $log) { $lines = @(Get-Content $log | Where-Object { $_.Trim() }) }
    foreach ($l in $lines) { Write-Step ('  | ' + $l) }
    if ($info.LastTaskResult -ne 0 -or -not ($lines -match $j.Pass) -or ($lines -match 'Pass failed')) {
        if ($KeepOnForbidden -and ($lines -match '\(403\) Forbidden')) {
            Write-Step ('  KEPT: ' + $t + "'s first pass answered 403 Forbidden - the Exchange grant has not reached" +
                        ' the data plane yet. The task stays (-KeepOnForbidden), fails quietly each minute, and comes' +
                        ' alive by itself the moment the grant lands; the import is keyed by Message-ID, so nothing' +
                        ' arrives twice.')
            $kept += $t
        } else {
            Write-Step ('  FAIL: ' + $t + "'s first run did not pass (task result " + $info.LastTaskResult + ', state ' + $state + '); removed again')
            Unregister-ScheduledTask -TaskName $t -Confirm:$false
            $failed += $t
        }
    } else {
        $passed += $t
    }
}
$pw = $null
if ($failed.Count) {
    Write-Step ('RESULT: FAILED for ' + ($failed -join ', ') + '; running: ' + $(if ($passed.Count) { $passed -join ', ' } else { 'none' }) + '. Tell WS36 the lines above.')
    exit 2
}
if ($kept.Count) {
    Write-Step ('RESULT: PASS, with ' + ($kept -join ', ') + ' registered and WAITING on the Exchange grant (403 for now).' +
                ' It needs nothing further: it starts importing by itself when the grant lands.' +
                $(if ($passed.Count) { ' Running now: ' + ($passed -join ', ') + '.' } else { '' }))
    exit 0
}
Write-Step ('RESULT: PASS. Running every minute, LIVE: ' + ($passed -join ', ') + '. Tell SQL01 "mail tasks done".')

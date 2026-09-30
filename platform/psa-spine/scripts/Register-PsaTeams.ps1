<#
.SYNOPSIS
    Register task PSA-Teams: the Teams card sender, run every minute as the desk's task account, in PREVIEW.

.DESCRIPTION
    Schema 050's host step (docs/handoffs/HANDOFF-cloud-sql01-WS36-20260926-runbook.md, "Folded in after part 20").
    SQL01, 30 Sep 2026. Run it elevated, as yourself. On DND-SQL01 it lives in D:\psa\bin; this is the same file.

    With -Apply it asks once for DND-SQL01\psa_desk's password (Task Scheduler needs it to run a task as that
    account; it goes nowhere else), then:
      1. registers PSA-Teams as psa_desk, every minute, running the live tree's
         scripts\Send-PsaTeamsNotifications.ps1 WITHOUT -Apply: it counts the cards due and checks every named
         channel has an address in D:\psa\teams-webhooks.json, and posts nothing;
      2. runs it once and reads D:\psa\logs\PSA-Teams.log (the latest pass only; each run replaces it).
    Pass: the log's PREVIEW line, and task result 0. If it does not pass, the task is removed again.

    Why a task every minute and not one -Loop process: a loop that dies stops silently, and nothing on this host
    watches the PSA tasks; a time trigger starts a fresh pass every minute whatever happened to the last.

    What it deliberately does NOT do:
      - post a card. The sender runs without -Apply. Posting is a later, separate switch;
      - write a channel address anywhere. Those are pasted by hand into D:\psa\teams-webhooks.json
        (inheritance off: SYSTEM, Administrators, and the task account read-only);
      - keep the psa_desk password anywhere but Task Scheduler.

    PREVIEW BY DEFAULT. Without -Apply it runs the preflight and changes nothing.
    -Undo -Apply removes the task (-Undo alone says what it would do).

.EXAMPLE
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Register-PsaTeams.ps1
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Register-PsaTeams.ps1 -Apply
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Register-PsaTeams.ps1 -Undo -Apply
#>
[CmdletBinding()]
param([switch]$Apply, [switch]$Undo)
$ErrorActionPreference = 'Stop'

$Acct     = 'DND-SQL01\psa_desk'
$Task     = 'PSA-Teams'
$Sender   = 'D:\dnd-poo\platform\psa-spine\scripts\Send-PsaTeamsNotifications.ps1'
$Hooks    = 'D:\psa\teams-webhooks.json'
$TeamsLog = 'D:\psa\logs\PSA-Teams.log'
$LogFile  = 'D:\psa\logs\Register-PsaTeams.log'
$Db       = 'Driver={ODBC Driver 17 for SQL Server};Server=DND-SQL01\PMC_SS;Database=PMC_PSA;Trusted_Connection=yes;Encrypt=yes;TrustServerCertificate=yes'

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
Write-Step ('start as ' + $me.Name + $(if ($Undo) { ' (-Undo)' } else { '' }) + $(if ($Apply) { ' (-Apply)' } else { ' (preview: nothing is changed)' }))

if ($Undo) {
    if (-not $Apply) { Write-Step ('would remove task ' + $Task + ' (preview; -Undo -Apply does it)'); return }
    if (Get-ScheduledTask -TaskName $Task -ErrorAction SilentlyContinue) { Unregister-ScheduledTask -TaskName $Task -Confirm:$false }
    Write-Step ('undone: task ' + $Task + ' removed (if it was there)')
    return
}

# --- preflight (changes nothing)
$fail = @()
foreach ($f in @($Sender, $Hooks)) { if (-not (Test-Path $f)) { $fail += $f + ' is missing' } }
if (Get-ScheduledTask -TaskName $Task -ErrorAction SilentlyContinue) { $fail += 'task ' + $Task + ' already exists (-Undo -Apply first to start again)' }
$rules = Get-ScheduledTask -TaskName 'PSA-Rules' -ErrorAction SilentlyContinue
if (-not $rules -or $rules.Principal.UserId -notmatch 'psa_desk$') { $fail += 'PSA-Rules is not visible as a psa_desk task (is this PowerShell elevated?)' }
if (Test-Path $Hooks) {
    try { [void](Get-Content $Hooks -Raw | ConvertFrom-Json) } catch { $fail += $Hooks + ' is not valid JSON' }
}
if ($fail.Count) { foreach ($f in $fail) { Write-Step ('  BLOCKED: ' + $f) }; Write-Step 'RESULT: BLOCKED. Nothing was changed.'; exit 1 }
Write-Step 'preflight: the sender and the webhook file present and readable; no PSA-Teams task yet; PSA-Rules runs as psa_desk'
if (-not $Apply) { Write-Step 'RESULT: preflight PASS. Nothing was changed (preview; -Apply registers the task).'; return }

# --- the task, in preview
$cred = Get-Credential -UserName $Acct -Message ('Password for ' + $Acct + ' (Task Scheduler needs it to run ' + $Task + '; it goes nowhere else)')
if (-not $cred) { Write-Step 'RESULT: no password given. Nothing was changed.'; exit 1 }
$pw = $cred.GetNetworkCredential().Password
# -SpineDir is passed, never left to its default: under Windows PowerShell 5.1 with -File, $PSScriptRoot is empty
# inside a param() default (MEASURED on DND-SQL01, 30 Sep 2026).
$cmd = "`$env:PYTHONDONTWRITEBYTECODE = '1'; & '" + $Sender + "' -Database '" + $Db + "' -WebhookFile '" + $Hooks +
       "' -StateDir 'D:\psa\mail-state' -DeskUrl 'https://desk.pmcne.ph' -SpineDir 'D:\dnd-poo\platform\psa-spine' *> '" + $TeamsLog + "'"
$now = Get-Date
$reg = @{
    TaskName    = $Task
    Action      = (New-ScheduledTaskAction -Execute 'powershell.exe' -Argument ('-NoProfile -ExecutionPolicy Bypass -Command "' + $cmd + '"'))
    Trigger     = (New-ScheduledTaskTrigger -Once -At $now.Date.AddHours($now.Hour).AddMinutes($now.Minute + 2) -RepetitionInterval (New-TimeSpan -Minutes 1))
    Settings    = (New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 5) -StartWhenAvailable)
    User        = $Acct
    Password    = $pw
    RunLevel    = 'Limited'
    Description = 'Dada PSA: Teams cards (schema 050), PREVIEW - counts what is due and checks D:\psa\teams-webhooks.json; posts nothing. SQL01, 30 Sep 2026.'
}
try { Register-ScheduledTask @reg | Out-Null } catch {
    Write-Step ('RESULT: FAILED to register the task: ' + $_.Exception.Message + ' Nothing else was changed.')
    exit 2
}
$pw = $null
Write-Step ('registered ' + $Task + ' as ' + $Acct + ', every minute, PREVIEW (posts nothing)')

$before = (Get-ScheduledTaskInfo -TaskName $Task).LastRunTime
Start-ScheduledTask -TaskName $Task
$deadline = (Get-Date).AddSeconds(120)
do {
    Start-Sleep -Seconds 3
    $info = Get-ScheduledTaskInfo -TaskName $Task
    $state = (Get-ScheduledTask -TaskName $Task).State
} while ((Get-Date) -lt $deadline -and ($state -eq 'Running' -or $info.LastRunTime -eq $before))
$lines = @()
if (Test-Path $TeamsLog) { $lines = @(Get-Content $TeamsLog | Where-Object { $_.Trim() }) }
foreach ($l in $lines) { Write-Step ('  | ' + $l) }
if ($info.LastTaskResult -ne 0 -or -not ($lines -match 'PREVIEW: \d+ card\(s\) due')) {
    Write-Step ('  FAIL: the preview did not pass (task result ' + $info.LastTaskResult + ', state ' + $state + ')')
    Unregister-ScheduledTask -TaskName $Task -Confirm:$false
    Write-Step 'RESULT: FAILED. The task was removed again. Tell SQL01 the lines above.'
    exit 2
}
Write-Step ('RESULT: PASS. ' + $Task + ' runs every minute in PREVIEW as psa_desk. Tell SQL01 "teams preview done".')

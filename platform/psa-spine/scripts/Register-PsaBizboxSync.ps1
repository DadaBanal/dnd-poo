<#
.SYNOPSIS
    Register task PSA-BizBox: the hourly BizBox mirror, run as the desk's task account.

.DESCRIPTION
    BizBox steps 4 and 5 on the live desk (docs/handoffs/HANDOFF-cloud-sql01-WS36-20260929-bizbox.md).
    SQL01, 29 Sep 2026; Dada ran it on DND-SQL01 at 11:48 (Reply, part 4). Run it elevated, as yourself. On
    DND-SQL01 it lives in D:\psa\bin; this is the same file.

    With -Apply it asks once for DND-SQL01\psa_desk's password (Task Scheduler needs it to run a task as that
    account; it goes nowhere else), then:
      1. registers PSA-BizBox as psa_desk, hourly at five past, running D:\psa\bin\Invoke-PsaBizboxSync.ps1 in
         PREVIEW, and runs it once. Step 4's Pass: one line per kind with plausible counts, "preview only";
      2. switches the task to -Apply and runs it once. Step 5's Pass: "applied" and one more BIZBOX_SYNC audit row;
      3. leaves it hourly with -Apply.
    If 1 or 2 does not pass, the task is removed again.

    What it deliberately does NOT do:
      - put the BizBox connection string in the task. The wrapper reads D:\psa\bizbox.odbc at run time;
      - write to BizBox. The mirror is the desk's own copy (ext_* tables in PMC_PSA);
      - keep the psa_desk password anywhere but Task Scheduler.

    PREVIEW BY DEFAULT. Without -Apply it runs the preflight and changes nothing.
    -Undo -Apply removes the task; the mirror rows stay (-Undo alone says what it would do).
    Rollback of the whole BizBox link: the handoff's Cloud Build section, "Rollback".

.EXAMPLE
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Register-PsaBizboxSync.ps1
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Register-PsaBizboxSync.ps1 -Apply
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Register-PsaBizboxSync.ps1 -Undo -Apply
#>
[CmdletBinding()]
param([switch]$Apply, [switch]$Undo)
$ErrorActionPreference = 'Stop'

$Acct    = 'DND-SQL01\psa_desk'
$Task    = 'PSA-BizBox'
$Wrapper = 'D:\psa\bin\Invoke-PsaBizboxSync.ps1'
$SyncLog = 'D:\psa\logs\PSA-BizBox.log'
$LogFile = 'D:\psa\logs\Register-PsaBizboxSync.log'

function Write-Step([string]$Text) {
    $line = (Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + '  ' + $Text
    Write-Host $line
    Add-Content -Path $LogFile -Value $line -Encoding UTF8
}

function Get-PsaScalar([string]$Sql) {
    $cn = New-Object System.Data.SqlClient.SqlConnection 'Server=DND-SQL01\PMC_SS;Database=PMC_PSA;Integrated Security=SSPI;Encrypt=True;TrustServerCertificate=True'
    $cn.Open()
    try { $cmd = $cn.CreateCommand(); $cmd.CommandText = $Sql; return $cmd.ExecuteScalar() } finally { $cn.Close() }
}

function Invoke-TaskOnce {
    $before = (Get-ScheduledTaskInfo -TaskName $Task).LastRunTime
    $skip = 0
    if (Test-Path $SyncLog) { $skip = @(Get-Content $SyncLog).Count }
    Start-ScheduledTask -TaskName $Task
    $deadline = (Get-Date).AddSeconds(240)
    do {
        Start-Sleep -Seconds 3
        $info = Get-ScheduledTaskInfo -TaskName $Task
        $state = (Get-ScheduledTask -TaskName $Task).State
    } while ((Get-Date) -lt $deadline -and ($state -eq 'Running' -or $info.LastRunTime -eq $before))
    $lines = @()
    if (Test-Path $SyncLog) { $lines = @(Get-Content $SyncLog | Select-Object -Skip $skip) }
    return @{ Result = $info.LastTaskResult; State = [string]$state; Lines = $lines }
}

function Remove-TaskAgain([string]$Why) {
    Write-Step ('  FAIL: ' + $Why)
    Unregister-ScheduledTask -TaskName $Task -Confirm:$false
    Write-Step 'RESULT: FAILED. The task was removed again. Tell SQL01 the lines above.'
    exit 2
}

# --- who is running this
$me = [Security.Principal.WindowsIdentity]::GetCurrent()
if ($me.Name -match '\\psa_desk$') { throw 'Run this as yourself, not as the desk task account. Nothing was done.' }
if (-not ([Security.Principal.WindowsPrincipal]$me).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Run this from an elevated PowerShell (Run as administrator). Nothing was done.'
}
Write-Step ('start as ' + $me.Name + $(if ($Undo) { ' (-Undo)' } else { '' }) + $(if ($Apply) { ' (-Apply)' } else { ' (preview: nothing is changed)' }))

if ($Undo) {
    if (-not $Apply) { Write-Step ('would remove task ' + $Task + '; the mirror rows would stay (preview; -Undo -Apply does it)'); return }
    if (Get-ScheduledTask -TaskName $Task -ErrorAction SilentlyContinue) { Unregister-ScheduledTask -TaskName $Task -Confirm:$false }
    Write-Step 'undone: task PSA-BizBox removed (if it was there); the mirror rows stay'
    return
}

# --- preflight (changes nothing)
$fail = @()
foreach ($f in @($Wrapper, 'D:\psa\bizbox.odbc', 'D:\psa\bizbox-map.json')) { if (-not (Test-Path $f)) { $fail += $f + ' is missing' } }
if (Get-ScheduledTask -TaskName $Task -ErrorAction SilentlyContinue) { $fail += 'task PSA-BizBox already exists (-Undo -Apply first to start again)' }
$rules = Get-ScheduledTask -TaskName 'PSA-Rules' -ErrorAction SilentlyContinue
if (-not $rules -or $rules.Principal.UserId -notmatch 'psa_desk$') { $fail += 'PSA-Rules is not visible as a psa_desk task (is this PowerShell elevated?)' }
if ((Get-PsaScalar "SELECT COUNT(*) FROM sys.tables t JOIN sys.schemas s ON s.schema_id = t.schema_id WHERE s.name = 'psa' AND t.name IN ('ext_source','ext_product','ext_purchase_order','ext_po_line','ext_invoice','audit_event')") -ne 6) {
    $fail += 'PMC_PSA lacks the mirror tables (schema 043)'
}
if ($fail.Count) { foreach ($f in $fail) { Write-Step ('  BLOCKED: ' + $f) }; Write-Step 'RESULT: BLOCKED. Nothing was changed.'; exit 1 }
$audit0 = [int](Get-PsaScalar "SELECT COUNT(*) FROM psa.audit_event WHERE action = 'BIZBOX_SYNC'")
Write-Step ('preflight: wrapper, connection-string file and map present; no PSA-BizBox task yet; PSA-Rules runs as psa_desk; mirror tables present; BIZBOX_SYNC audit rows so far: ' + $audit0)
if (-not $Apply) { Write-Step 'RESULT: preflight PASS. Nothing was changed (preview; -Apply registers and runs the task).'; return }

# --- the task, first in preview
$cred = Get-Credential -UserName $Acct -Message ('Password for ' + $Acct + ' (Task Scheduler needs it to run PSA-BizBox; it goes nowhere else)')
if (-not $cred) { Write-Step 'RESULT: no password given. Nothing was changed.'; exit 1 }
$pw = $cred.GetNetworkCredential().Password
$argPreview = '-NoProfile -ExecutionPolicy Bypass -File "' + $Wrapper + '"'
$now = Get-Date
$start = $now.Date.AddHours($now.Hour + 1).AddMinutes(5)
$trigger = New-ScheduledTaskTrigger -Once -At $start -RepetitionInterval (New-TimeSpan -Hours 1)
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 10) -StartWhenAvailable
$reg = @{
    TaskName    = $Task
    Action      = (New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $argPreview)
    Trigger     = $trigger
    Settings    = $settings
    User        = $Acct
    Password    = $pw
    RunLevel    = 'Limited'
    Description = 'Dada PSA: mirrors BizBox purchase orders, lines, products and invoices, read-only (HANDOFF-cloud-sql01-WS36-20260929-bizbox.md). SQL01, 29 Sep 2026.'
}
try { Register-ScheduledTask @reg | Out-Null } catch {
    Write-Step ('RESULT: FAILED to register the task: ' + $_.Exception.Message + ' Nothing else was changed.')
    exit 2
}
$rep = (Get-ScheduledTask -TaskName $Task).Triggers[0].Repetition
Write-Step ('registered PSA-BizBox as ' + $Acct + ' (preview for now), from ' + $start.ToString('yyyy-MM-dd HH:mm') + ', every ' + $rep.Interval + ' for ' + $(if ($rep.Duration) { $rep.Duration } else { 'indefinitely' }))

$r = Invoke-TaskOnce
foreach ($l in $r.Lines) { Write-Step ('  | ' + $l.Substring([Math]::Min(21, $l.Length))) }
$kinds = @($r.Lines | Where-Object { $_ -match '(product|purchase_order|po_line|invoice): \d+ rows' })
if ($r.Result -ne 0 -or $kinds.Count -ne 4 -or -not ($r.Lines -match 'preview only')) {
    Remove-TaskAgain ('the preview did not pass (task result ' + $r.Result + ', ' + $kinds.Count + ' of 4 kinds, state ' + $r.State + ')')
}
Write-Step '  PASS (step 4): one line per kind and "preview only", as psa_desk through Task Scheduler'

# --- then apply, once now and hourly after
Set-ScheduledTask -TaskName $Task -Action (New-ScheduledTaskAction -Execute 'powershell.exe' -Argument ($argPreview + ' -Apply')) -User $Acct -Password $pw | Out-Null
$pw = $null
$r = Invoke-TaskOnce
foreach ($l in $r.Lines) { Write-Step ('  | ' + $l.Substring([Math]::Min(21, $l.Length))) }
$audit1 = [int](Get-PsaScalar "SELECT COUNT(*) FROM psa.audit_event WHERE action = 'BIZBOX_SYNC'")
if ($r.Result -ne 0 -or -not ($r.Lines -match '^\S+ \S+\s+applied$|  applied$') -or $audit1 -ne $audit0 + 1) {
    Remove-TaskAgain ('the first apply did not pass (task result ' + $r.Result + ', BIZBOX_SYNC audit rows ' + $audit0 + ' -> ' + $audit1 + ')')
}
$last = Get-PsaScalar "SELECT CONVERT(varchar(16), last_sync_at, 120) FROM psa.ext_source WHERE source_id = 'BIZBOX'"
Write-Step ('  PASS (step 5): applied as psa_desk; BIZBOX_SYNC audit rows ' + $audit0 + ' -> ' + $audit1 + '; last sync ' + $last)
$next = (Get-ScheduledTaskInfo -TaskName $Task).NextRunTime
Write-Step ('RESULT: PASS. PSA-BizBox runs hourly with -Apply; next run ' + $next.ToString('yyyy-MM-dd HH:mm') + '. Tell SQL01 "bizbox sync done".')

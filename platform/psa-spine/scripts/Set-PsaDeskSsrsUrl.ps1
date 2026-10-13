<#
.SYNOPSIS
    Add PSA_SSRS_URL to the PSA-Desk task, so the MMS Reports tab can reach the report server.
    Handoff HANDOFF-cloud-sql01-WS36-20261013-mms-reports-082.md, step 8. Preview by default.

.DESCRIPTION
    PSA-Desk sets its environment inside its own task action (`$env:NAME = 'value'; ...`), so adding a value
    means editing that action. The task runs as DND-SQL01\psa_desk with a STORED PASSWORD, and Windows refuses
    any change to such a task unless the password is supplied again ("The user name or password is incorrect",
    MEASURED by SQL01 on 10 Oct and again today). That is why Dada runs this and not a Claude session. The
    password is asked for at the Windows prompt, held only in memory for the one call, never written or logged.

    PSA_SSRS_FOLDER is not set: '/BizBox MMS Reports' is the desk's default (handoff step 8).

    With -Apply it exports the task's XML beside the other backups in D:\psa\logs, changes the action, then
    reads it back and checks that (a) only PSA_SSRS_URL was added and (b) the account and logon type are
    unchanged. PSA-Desk is then restarted so it picks the value up.

    To undo: re-import the backup XML, or take the one `$env:PSA_SSRS_URL = '...';` off the line by hand.

.EXAMPLE
    .\Set-PsaDeskSsrsUrl.ps1            # preview: shows before and after, changes nothing
    .\Set-PsaDeskSsrsUrl.ps1 -Apply     # elevated; asks for the psa_desk password once
#>
[CmdletBinding()]
param(
    [switch] $Apply,
    [string] $SsrsUrl = 'http://dnd-sql01/ReportServer'
)

$ErrorActionPreference = 'Stop'
$Task    = 'PSA-Desk'
$Account = 'DND-SQL01\psa_desk'
$Add     = "`$env:PSA_SSRS_URL = '$SsrsUrl'; "
$Anchor  = "`$env:PSA_PUBLIC_URL"      # insert immediately before this, among the other env lines

function Hide([string] $s) {
    $s -replace "(?i)(-(TenantId|ClientId|CertThumbprint|WebhookFile))\s+'[^']*'", '$1 ''<hidden>'''
}

$t = Get-ScheduledTask -TaskName $Task -ErrorAction SilentlyContinue
if (-not $t) { throw "$Task is not registered on this host." }
$old = $t.Actions[0].Arguments

"=== $Task  (runs as $($t.Principal.UserId), logon $($t.Principal.LogonType))"
if ($old -match 'PSA_SSRS_URL') {
    'SKIP: PSA_SSRS_URL is already on the line. Nothing to do.'
    '  current value: ' + ([regex]::Match($old, "PSA_SSRS_URL\s*=\s*'([^']*)'").Groups[1].Value)
    return
}
if (-not $old.Contains($Anchor)) { throw "could not find $Anchor on the task's line; nothing changed." }

$new = $old.Replace($Anchor, $Add + $Anchor)
'  adds: ' + $Add.Trim()
'  after: ' + (Hide $new)

if (-not $Apply) {
    ''
    'PREVIEW: nothing changed. Re-run elevated with -Apply.'
    return
}

$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Run this elevated (Run as administrator). Nothing changed.'
}

$sec  = Read-Host -AsSecureString "Password for $Account"
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec)
try {
    $plain = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    $bak = 'D:\psa\logs\PSA-Desk-task-before-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.xml'
    Export-ScheduledTask -TaskName $Task | Out-File -FilePath $bak -Encoding Unicode
    $action = New-ScheduledTaskAction -Execute $t.Actions[0].Execute -Argument $new
    Set-ScheduledTask -TaskName $Task -Action $action -User $Account -Password $plain | Out-Null

    $after = Get-ScheduledTask -TaskName $Task
    $onlyAdded    = ($after.Actions[0].Arguments.Replace($Add, '') -eq $old)
    $samePrincipal = ($after.Principal.LogonType -eq $t.Principal.LogonType -and
                      $after.Principal.UserId   -eq $t.Principal.UserId)
    ''
    "DONE  backup $bak"
    "  only PSA_SSRS_URL added : $onlyAdded"
    "  account and logon kept  : $samePrincipal"

    if (-not ($onlyAdded -and $samePrincipal)) {
        'VERDICT: FAIL. Re-import the backup XML above and tell SQL01. The desk was NOT restarted.'
        return
    }

    '  restarting PSA-Desk so it reads the new value...'
    Stop-ScheduledTask -TaskName $Task -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 4
    Start-ScheduledTask -TaskName $Task
    Start-Sleep -Seconds 8
    $code = try { (Invoke-WebRequest 'http://127.0.0.1:8085/' -UseBasicParsing -TimeoutSec 8 -ErrorAction Stop).StatusCode }
            catch { if ($_.Exception.Response) { [int]$_.Exception.Response.StatusCode } else { 'down' } }
    "  desk :8085 answers $code  (401 is correct: it means the desk is up and asking for sign-in)"
    ''
    if ($code -eq 401) { 'VERDICT: PASS. PSA_SSRS_URL is set and the desk is back up.' }
    else { 'VERDICT: CHECK. The value is set but the desk did not answer 401; tell SQL01 what it says.' }
} finally {
    if ($bstr -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr) }
    $plain = $null
}

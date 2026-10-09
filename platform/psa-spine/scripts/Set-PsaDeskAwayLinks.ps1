<#
.SYNOPSIS
    Add the desk's away-from-PMC address to the two sender tasks (WS36 handoff
    HANDOFF-cloud-sql01-WS36-20261009-desk-away-links.md, steps 3 and 4). Preview by default.

.DESCRIPTION
    PSA-Notify gets  -DeskUrl 'https://desk.pmcne.ph' -DeskAwayUrl 'https://desk.pmcne.net'
    PSA-Teams  gets  -DeskAwayUrl 'https://desk.pmcne.net'   (it already carries -DeskUrl)
    Nothing else on either line changes.

    Why Dada runs it and not a Claude session: both tasks run as DND-SQL01\psa_desk with a stored password, and
    Windows refuses any change to such a task unless the password is supplied again ("The user name or password is
    incorrect", MEASURED by SQL01, 10 Oct 2026, 02:42; the task was left unchanged). The password is asked for at the
    Windows prompt, held only in memory for the two calls, never written, logged or echoed.

    With -Apply: exports each task's XML beside the other task backups in D:\psa\logs, changes the action, then reads
    each task back and checks that (a) only the new arguments were added and (b) the account and logon type are as
    before. The next minute's pass picks the change up; no restart.

    To undo: re-import the backup XML (Register-ScheduledTask -Xml (Get-Content <bak> | Out-String) -TaskName <name>
    -User DND-SQL01\psa_desk -Password <it>), or run this script's arguments off by hand.

.EXAMPLE
    .\Set-PsaDeskAwayLinks.ps1            # preview: shows before and after, changes nothing
    .\Set-PsaDeskAwayLinks.ps1 -Apply     # elevated; asks for the psa_desk password once
#>
[CmdletBinding()]
param([switch] $Apply)

$ErrorActionPreference = 'Stop'
$Account = 'DND-SQL01\psa_desk'
$Plan = @(
    @{ Task = 'PSA-Notify'; Marker = " *> 'D:\psa\logs\PSA-Notify.log'";
       Add = " -DeskUrl 'https://desk.pmcne.ph' -DeskAwayUrl 'https://desk.pmcne.net'" },
    @{ Task = 'PSA-Teams'; Marker = " *> 'D:\psa\logs\PSA-Teams.log'";
       Add = " -DeskAwayUrl 'https://desk.pmcne.net'" }
)

function Hide([string] $s) {
    # Never show identifiers or the webhook file path in the preview.
    $s -replace "(?i)(-(TenantId|ClientId|CertThumbprint|WebhookFile))\s+'[^']*'", '$1 ''<hidden>'''
}

$work = @()
foreach ($p in $Plan) {
    $t = Get-ScheduledTask -TaskName $p.Task -ErrorAction SilentlyContinue
    if (-not $t) { "SKIP  $($p.Task): not registered"; continue }
    $old = $t.Actions[0].Arguments
    if ($old -match 'DeskAwayUrl') { "SKIP  $($p.Task): already has -DeskAwayUrl"; continue }
    if (-not $old.Contains($p.Marker)) { throw "$($p.Task): its log redirect was not found; nothing changed" }
    $new = $old.Replace($p.Marker, $p.Add + $p.Marker)
    "=== $($p.Task)  (runs as $($t.Principal.UserId), logon $($t.Principal.LogonType))"
    "  adds:" + $p.Add
    "  after: " + (Hide $new)
    $work += @{ P = $p; T = $t; Old = $old; New = $new }
}
if (-not $Apply) { ''; 'PREVIEW: nothing changed. Re-run elevated with -Apply.'; return }
if (-not $work) { 'Nothing to do.'; return }

$sec = Read-Host -AsSecureString "Password for $Account"
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec)
try {
    $plain = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    foreach ($w in $work) {
        $name = $w.P.Task
        $bak = 'D:\psa\logs\' + $name + '-task-before-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.xml'
        Export-ScheduledTask -TaskName $name | Out-File -FilePath $bak -Encoding Unicode
        $action = New-ScheduledTaskAction -Execute $w.T.Actions[0].Execute -Argument $w.New
        Set-ScheduledTask -TaskName $name -Action $action -User $Account -Password $plain | Out-Null
        $after = Get-ScheduledTask -TaskName $name
        $onlyAdded = ($after.Actions[0].Arguments.Replace($w.P.Add, '') -eq $w.Old)
        $samePrincipal = ($after.Principal.LogonType -eq $w.T.Principal.LogonType)
        "DONE  $name  backup $bak  | only the new arguments added: $onlyAdded | logon unchanged: $samePrincipal"
    }
} finally {
    if ($bstr -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr) }
    $plain = $null
}
'The next pass of each task uses the new links; no restart.'

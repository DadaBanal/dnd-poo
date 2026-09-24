<#
.SYNOPSIS
    Check the PSA attachment store is whole, then remove files under the retention rule.

.DESCRIPTION
    Runs on DND-SQL01, on a schedule (weekly is enough). Two steps, in order:

      1. `psaspine attachments-verify`: every live row has its file and every
         file has a row. If not, this script STOPS and says so. It never purges
         over a store that is not whole: a data drive that is not mounted looks
         like every file missing, and settling that is a person's decision
         (`attachments-verify --mark-missing`, run by hand).
      2. `psaspine attachments-purge`: a withheld file goes -WithheldDays after
         its review; any file goes -ClosedDays after its ticket closed. The row
         stays, so the ticket still says what was sent and by whom.

    PREVIEW BY DEFAULT. Without -Apply the purge prints its plan and changes
    nothing. There is NO default period: both are mandatory, and they should be
    the numbers PMC's Data Protection Officer signed (section 6.1: retention is
    designed, not inherited).

    Logs counts only. Never a file name: a file name can carry a patient's name.

.PARAMETER Database
    The desk database, e.g. D:\psa\spine.db. The store is beside it
    (spine.db.attachments) unless PSA_ATTACHMENT_DIR is set for this account.

.EXAMPLE
    # Preview: verifies, prints the plan, changes nothing.
    .\Invoke-PmcAttachmentRetention.ps1 -Database D:\psa\spine.db -StateDir D:\psa\mail-state `
        -WithheldDays 30 -ClosedDays 730

.EXAMPLE
    # The scheduled task, once the periods are signed.
    .\Invoke-PmcAttachmentRetention.ps1 ... -Apply
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)] [string] $Database,
    [Parameter(Mandatory = $true)] [string] $StateDir,
    [Parameter(Mandatory = $true)] [int] $WithheldDays,
    [Parameter(Mandatory = $true)] [int] $ClosedDays,
    [string] $SpineDir = (Join-Path $PSScriptRoot '..'),
    [string] $PythonExe = 'C:\PMC\Python312\python.exe',
    [switch] $Apply
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

$LogFile = Join-Path $StateDir 'attachment-retention.log'

function Write-Log([string] $Message) {
    $line = '{0:yyyy-MM-dd HH:mm:ss}Z  {1}' -f (Get-Date).ToUniversalTime(), $Message
    Write-Host $line
    if ($Apply) { Add-Content -Path $LogFile -Value $line -Encoding ASCII }
}

function Invoke-Spine([string[]] $SpineArgs) {
    Push-Location $SpineDir
    try {
        $out = & $PythonExe -m psaspine @SpineArgs 2>&1
        $code = $LASTEXITCODE
    } finally { Pop-Location }
    return @{ Code = $code; Out = (($out | Out-String).Trim()) }
}

# ---------------------------------------------------------------- main
foreach ($p in $Database, $SpineDir) {
    if (-not (Test-Path $p)) { throw "Not found: $p" }
}
if ($WithheldDays -lt 1 -or $ClosedDays -lt 1) { throw 'Both periods are whole days, at least 1.' }
if ($Apply -and -not (Test-Path $StateDir)) { New-Item -ItemType Directory -Path $StateDir | Out-Null }

# 1. Whole? The CLI prints counts and sha prefixes only, so its lines are safe to log.
$v = Invoke-Spine @('attachments-verify', $Database)
foreach ($line in ($v.Out -split "`n")) { Write-Log ('verify: ' + $line.Trim()) }
if ($v.Code -ne 0) {
    Write-Log 'STOPPED: the store is not whole. Nothing purged. Settle it by hand (attachments-verify --mark-missing) and re-run.'
    exit 1
}

# 2. Purge, previewing unless -Apply.
$purgeArgs = @('attachments-purge', $Database, '--withheld-days', "$WithheldDays", '--closed-days', "$ClosedDays")
if ($Apply) { $purgeArgs += '--apply' }
$r = Invoke-Spine $purgeArgs
foreach ($line in ($r.Out -split "`n")) { Write-Log ('purge: ' + $line.Trim()) }
if ($r.Code -ne 0) {
    Write-Log 'STOPPED: the purge refused. Nothing changed.'
    exit 1
}
if (-not $Apply) { Write-Log 'PREVIEW: nothing changed. Re-run with -Apply once the periods are signed.' }
exit 0

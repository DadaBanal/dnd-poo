<#
.SYNOPSIS
    Mirror BizBox purchase orders, lines, products and invoices into Dada PSA. Reads BizBox; never writes to it.

.DESCRIPTION
    BizBox steps 4 and 5 (docs/handoffs/HANDOFF-cloud-sql01-WS36-20260929-bizbox.md). SQL01, 29 Sep 2026.
    Task PSA-BizBox runs it hourly as the desk's task account, with -Apply. On DND-SQL01 it lives in
    D:\psa\bin; this is the same file, kept here so a rebuilt host can be made from the repository.

    It runs `psaspine sync-bizbox <database> --map D:\psa\bizbox-map.json --odbc`. The BizBox side is read
    through the desk's own read-only SQL login (psa_bizbox_reader: SELECT on LiveDB_PMC's psa views, nothing
    else). That login's ODBC connection string is in D:\psa\bizbox.odbc and is loaded here at run time, so it is
    never in a task's arguments (the desk log prints part of those) and never in a log. The mirror is written into
    PMC_PSA by the account running this script, with Windows sign-in.

    What it deliberately does NOT do:
      - write to BizBox. The login can only read, and the desk's writer is NoWriter;
      - carry the connection string or its password. It reads the file on the host and clears the variable after;
      - log a row's content. It logs the counts psaspine prints, with any PWD= masked all the same.

    PREVIEW BY DEFAULT. Without -Apply psaspine reads BizBox, compares, prints one line per kind and writes
    nothing. -Database names another target, such as a scratch SQLite file, for a dry run.

.EXAMPLE
    .\Invoke-PsaBizboxSync.ps1
    .\Invoke-PsaBizboxSync.ps1 -Apply
    .\Invoke-PsaBizboxSync.ps1 -Apply -Database D:\scratch\bizbox-dry.sqlite -LogFile D:\scratch\bizbox-dry.log
#>
[CmdletBinding()]
param(
    [switch]$Apply,
    [string]$Database = 'Driver={ODBC Driver 17 for SQL Server};Server=DND-SQL01\PMC_SS;Database=PMC_PSA;Trusted_Connection=yes;Encrypt=yes;TrustServerCertificate=yes',
    [string]$LogFile = 'D:\psa\logs\PSA-BizBox.log'
)
$ErrorActionPreference = 'Stop'
$py = 'C:\PMC\Python312\python.exe'
$MapFile = 'D:\psa\bizbox-map.json'
$OdbcFile = 'D:\psa\bizbox.odbc'

function Write-Log([string]$Text) {
    $line = (Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + '  ' + ($Text -replace 'PWD=[^;]*', 'PWD=***')
    Add-Content -Path $LogFile -Value $line -Encoding UTF8
    Write-Host $line
}

$who = [Security.Principal.WindowsIdentity]::GetCurrent().Name
$mode = $(if ($Apply) { '--apply' } else { 'preview' })
Set-Location 'D:\dnd-poo\platform\psa-spine'
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PSA_BIZBOX_ODBC = ([IO.File]::ReadAllText($OdbcFile)).Trim()
$a = @('sync-bizbox', $Database, '--map', $MapFile, '--odbc')
if ($Apply) { $a += '--apply' }

# Python writes refusals to stderr; under Stop, Windows PowerShell 5.1 would turn that into a terminating error.
$ErrorActionPreference = 'Continue'
$out = @(& $py -m psaspine @a 2>&1 | ForEach-Object { [string]$_ })
$code = $LASTEXITCODE
$ErrorActionPreference = 'Stop'
Remove-Item Env:\PSA_BIZBOX_ODBC -ErrorAction SilentlyContinue

foreach ($l in $out) { if ($l.Trim()) { Write-Log ('  ' + $l) } }
Write-Log ('sync-bizbox ' + $mode + ' : exit ' + $code + ' : as ' + $who)
exit $code

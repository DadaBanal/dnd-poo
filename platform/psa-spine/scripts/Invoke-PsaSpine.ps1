<#
.SYNOPSIS
    Run a desk command as the task account, because a SQL sysadmin's own connection is refused.

.DESCRIPTION
    Dada, 2 Oct 2026: every `psaspine` command he ran answered

        the desk's login must have default schema [psa] on this database; it has [dbo].

    That is not a fault to fix on the account. SQL Server maps every member of the sysadmin role to the
    database user `dbo`, whose default schema is `dbo` and cannot be changed; the desk refuses `dbo` on
    purpose, so that it can never write to the wrong schema. The answer is to run the command as the
    account the desk itself runs as, which is not a sysadmin.

    This asks for that account once, runs the command as it, and shows what it said. The password is
    read by the Windows credential prompt, is held only for the life of this run, and is written
    nowhere: not to a file, not to the log, not to the command line.

.EXAMPLE
    # the things this is for, each with its own switch: no quoting to get wrong
    .\Invoke-PsaSpine.ps1 -MailHealth
    .\Invoke-PsaSpine.ps1 -MailRetry                       # lists what was set aside
    .\Invoke-PsaSpine.ps1 -MailRetry -All -Apply           # releases every one of them
    .\Invoke-PsaSpine.ps1 -WhoSees PMC-000155 -Person via.soriano
    .\Invoke-PsaSpine.ps1 -MailWhy pmcnicu@gmail.com

.EXAMPLE
    # anything else: the whole command as one quoted string
    .\Invoke-PsaSpine.ps1 -Spine "calendar-members --allowed-domain pmcne.ph"
#>
param(
    # One switch per thing this is actually for. PowerShell reads a bare
    # --word as a parameter it does not have and stops to ask, which swallowed
    # the operator's next three lines (MEASURED on DND-SQL01, 2 Oct 2026). So
    # nothing here asks the caller to type one.
    [switch] $MailHealth,
    [switch] $MailRetry,
    [switch] $All,
    [switch] $Apply,
    [string] $WhoSees,
    [string] $Person,
    [string] $MailWhy,
    [int] $Days,
    [string] $Actor = $env:USERNAME,
    # Anything else: the whole psaspine command as one string, without the
    # connection, e.g. -Spine "calendar-members --allowed-domain pmcne.ph".
    [string] $Spine,
    [string] $Account = 'PMCNE\psa_desk',
    [string] $Database = 'Driver={ODBC Driver 17 for SQL Server};Server=DND-SQL01\PMC_SS;Database=PMC_PSA;Trusted_Connection=yes;Encrypt=yes;TrustServerCertificate=yes',
    [string] $SpineDir,
    [string] $PythonExe = 'C:\PMC\Python312\python.exe',
    [string] $WorkDir = 'D:\psa\logs',
    [System.Management.Automation.PSCredential] $Credential
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'
if (-not $SpineDir) { $SpineDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path) }
if (-not (Test-Path $PythonExe)) { throw ($PythonExe + ' is not there. Correct -PythonExe.') }
if (-not (Test-Path $WorkDir)) { New-Item -ItemType Directory -Path $WorkDir -Force | Out-Null }

# What to run. The database goes in as the command's first argument, exactly
# where every psaspine command takes it, so the caller never types a
# connection string.
$words = @()
if ($MailHealth) {
    $words = @('mail-health')
    if ($Days) { $words += @('--days', "$Days") }
} elseif ($MailRetry) {
    $words = @('mail-retry', '--actor', $Actor)
    if ($All) { $words += '--all' }
    if ($Apply) { $words += '--apply' }
    if ($Days) { $words += @('--days', "$Days") }
} elseif ($WhoSees) {
    $words = @('who-sees', '--ticket', $WhoSees)
    if ($Person) { $words += @('--person', $Person) }
} elseif ($MailWhy) {
    $words = @('mail-why', '--sender', $MailWhy)
    if ($Days) { $words += @('--days', "$Days") }
} elseif ($Spine) {
    $words = @($Spine -split '\s+' | Where-Object { $_ })
} else {
    Write-Host 'Nothing asked for. One of:'
    Write-Host '  -MailHealth                              is mail becoming tickets at all'
    Write-Host '  -MailRetry                               what intake set aside'
    Write-Host '  -MailRetry -All -Apply                   release every one of them'
    Write-Host '  -MailWhy <sender>                        what intake did with their mail'
    Write-Host '  -WhoSees <ticket> -Person <them>         why a requester does or does not see it'
    Write-Host '  -Spine "<any psaspine command>"          anything else, as one quoted string'
    exit 2
}
$cmd = @($words[0], $Database) + @($words[1..($words.Count - 1)] | Where-Object { $null -ne $_ })
Write-Host ('running as ' + $Account + ': psaspine ' + ($words -join ' '))

if (-not $Credential) {
    $Credential = Get-Credential -UserName $Account -Message (
        'Password for ' + $Account + ' (the account the desk runs as; it is used for this command and kept nowhere)')
}
if (-not $Credential) { throw 'No password given. Nothing was run.' }

$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$out = Join-Path $WorkDir ('spine-' + $stamp + '.out')
$err = Join-Path $WorkDir ('spine-' + $stamp + '.err')
# -ArgumentList, never a string: a connection string holds characters a shell
# would otherwise read as its own.
$argline = @('-m', 'psaspine') + $cmd | ForEach-Object { if ($_ -match '[\s{};]') { '"' + $_ + '"' } else { $_ } }

try {
    $p = Start-Process -FilePath $PythonExe -ArgumentList $argline -Credential $Credential `
                       -WorkingDirectory $SpineDir -RedirectStandardOutput $out -RedirectStandardError $err `
                       -Wait -PassThru
    $code = $p.ExitCode
} catch {
    throw ('could not start it as ' + $Account + ': ' + $_.Exception.Message +
           '. If that account may not log on here, run the command from a session opened with' +
           ' runas /user:' + $Account + ' instead.')
}

foreach ($f in @($out, $err)) {
    if ((Test-Path $f) -and (Get-Item $f).Length -gt 0) { Get-Content $f | ForEach-Object { Write-Host $_ } }
}
Remove-Item $out, $err -Force -ErrorAction SilentlyContinue
Write-Host ('exit ' + $code)
exit $code

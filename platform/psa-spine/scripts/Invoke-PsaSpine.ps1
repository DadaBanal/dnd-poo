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
    # what the desk has taken from the mailboxes
    .\Invoke-PsaSpine.ps1 mail-health

    # the messages intake set aside, then release every one of them
    .\Invoke-PsaSpine.ps1 mail-retry --actor dada.banal
    .\Invoke-PsaSpine.ps1 mail-retry --all --actor dada.banal --apply

    # why one message did what it did
    .\Invoke-PsaSpine.ps1 mail-why --sender pmcnicu@gmail.com
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, ValueFromRemainingArguments = $true)]
    [string[]] $SpineArgs,
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

# The database goes in as the command's first argument, exactly where every
# psaspine command takes it, so the caller never types a connection string.
$cmd = @($SpineArgs[0], $Database) + @($SpineArgs[1..($SpineArgs.Count - 1)] | Where-Object { $null -ne $_ })
Write-Host ('running as ' + $Account + ': psaspine ' + ($SpineArgs -join ' '))

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

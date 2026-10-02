<#
.SYNOPSIS
    Run a desk command as the task account, because a SQL sysadmin's own connection is refused.

.DESCRIPTION
    Dada, 2 Oct 2026: every `psaspine` command he ran answered

        the desk's login must have default schema [psa] on this database; it has [dbo].

    That is not a fault to fix on the account. SQL Server maps every member of the sysadmin role to the
    database user `dbo`, whose default schema is `dbo` and cannot be changed; the desk refuses `dbo` on
    purpose, so that it can never write to the wrong schema. The answer is to run the command as the
    account the desk itself runs as, which is not a sysadmin: `DND-SQL01\psa_desk`, a local account on
    the server whose database user in PMC_PSA is the same name with default schema `psa`.

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
    # The schema step. -SchemaPreview prints the generated port's plan and
    # changes nothing; -SchemaApply runs it, which is how a new schema file
    # (064, say) reaches the live store. Both are guarded and idempotent: a
    # re-run adds nothing twice.
    [switch] $SchemaPreview,
    [switch] $SchemaApply,
    [int] $Days,
    [string] $Actor = $env:USERNAME,
    # Anything else: the whole psaspine command as one string, without the
    # connection, e.g. -Spine "calendar-members --allowed-domain pmcne.ph".
    [string] $Spine,
    # Read from the desk's own scheduled tasks when it is not given, so the
    # name is measured rather than guessed (2 Oct 2026: the guess was wrong).
    [string] $Account,
    # Where to put what the command wrote on standard output, as well as showing
    # it. A caller that reads the answer rather than a person (Fix-PsaToday.ps1
    # asking for the members list, which is JSON) needs it without this script's
    # own lines mixed in.
    [string] $OutFile,
    # Run it through a one-shot scheduled task instead, which needs no
    # password at all.
    [switch] $ViaTask,
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

if (-not $Account) {
    foreach ($t in 'PSA-Desk', 'PSA-Mail-Helpdesk', 'PSA-Rules', 'PSA-Notify', 'PSA-Mail-Support') {
        $task = Get-ScheduledTask -TaskName $t -ErrorAction SilentlyContinue
        if ($task -and $task.Principal -and $task.Principal.UserId) {
            $Account = $task.Principal.UserId
            Write-Host ('the desk runs as ' + $Account + ' (read from the ' + $t + ' task)')
            break
        }
    }
}
if (-not $Account) {
    # The desk's task account, told by Dada 2 Oct 2026: a LOCAL account on the
    # server, not a domain one, whose database user in PMC_PSA is the same
    # name with default schema psa. Reading it from a task above is better
    # still, because it cannot go stale.
    $Account = "$env:COMPUTERNAME\psa_desk"
    Write-Host ('no desk task to read it from; using ' + $Account)
}

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
} elseif ($SchemaPreview) {
    $words = @('schema-preview')
} elseif ($SchemaApply) {
    $words = @('init')
} elseif ($Spine) {
    $words = @($Spine -split '\s+' | Where-Object { $_ })
} else {
    Write-Host 'Nothing asked for. One of:'
    Write-Host '  -MailHealth                              is mail becoming tickets at all'
    Write-Host '  -MailRetry                               what intake set aside'
    Write-Host '  -MailRetry -All -Apply                   release every one of them'
    Write-Host '  -MailWhy <sender>                        what intake did with their mail'
    Write-Host '  -WhoSees <ticket> -Person <them>         why a requester does or does not see it'
    Write-Host '  -SchemaPreview                           what the schema step would add, changing nothing'
    Write-Host '  -SchemaApply                             add it (guarded; a re-run adds nothing twice)'
    Write-Host '  -Spine "<any psaspine command>"          anything else, as one quoted string'
    exit 2
}
# $words[1..0] is NOT empty in PowerShell: 1..0 counts DOWN, so a one-word
# command came out as @('init', <db>, 'init') and psaspine answered
# "unrecognized arguments: init" (MEASURED on DND-SQL01, 2 Oct 2026, on
# -SchemaPreview, -SchemaApply and -MailHealth, each of which is one word).
$cmd = @($words[0], $Database)
if ($words.Count -gt 1) { $cmd += @($words[1..($words.Count - 1)] | Where-Object { $null -ne $_ }) }
Write-Host ('running as ' + $Account + ': psaspine ' + ($words -join ' '))

if ($ViaTask) {
    # No password: an administrator registers a one-shot task that runs as the
    # account under S4U, where Windows issues the token and no secret is
    # typed, stored or prompted for. The task runs once and is removed.
    $me = [Security.Principal.WindowsIdentity]::GetCurrent()
    if (-not ([Security.Principal.WindowsPrincipal]$me).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw 'Registering a task to run as another account needs an elevated PowerShell. Nothing was run.'
    }
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $out = Join-Path $WorkDir ('spine-' + $stamp + '.out')
    $runner = Join-Path $WorkDir ('spine-' + $stamp + '.ps1')
    $name = 'PSA-Command-' + $stamp
    # A task has no console, so the command is written as a small script that
    # sends its words to a file this session then reads. The arguments are
    # written as a PowerShell array, never pasted into a command line.
    $lines = @(
        '$ErrorActionPreference = ''Continue''',
        ('Set-Location ' + ("'" + $SpineDir.Replace("'", "''") + "'")),
        ('$a = @(' + (($cmd | ForEach-Object { "'" + ($_ -replace "'", "''") + "'" }) -join ', ') + ')'),
        ('& ' + ("'" + $PythonExe.Replace("'", "''") + "'") + ' -m psaspine @a *> ' +
            ("'" + $out.Replace("'", "''") + "'")),
        'exit $LASTEXITCODE')
    Set-Content -Path $runner -Value $lines -Encoding ASCII
    $action = New-ScheduledTaskAction -Execute 'powershell.exe' `
                -Argument ('-NoProfile -ExecutionPolicy Bypass -File "' + $runner + '"')
    $principal = New-ScheduledTaskPrincipal -UserId $Account -LogonType S4U -RunLevel Highest
    # -ErrorAction Stop, because this one writes a NON-TERMINATING error:
    # MEASURED on DND-SQL01, 2 Oct 2026, 'Access is denied' did not enter the
    # catch, so the run carried on to Start-ScheduledTask and
    # Get-ScheduledTaskInfo on a task that was never registered and failed
    # three more times, burying the one error that mattered.
    try {
        Register-ScheduledTask -TaskName $name -Action $action -Principal $principal `
                               -Description 'Dada PSA: one desk command, then gone' `
                               -ErrorAction Stop | Out-Null
    } catch {
        Remove-Item $runner -Force -ErrorAction SilentlyContinue
        throw ('could not register a task that runs as ' + $Account + ': ' + $_.Exception.Message +
               '. S4U needs the account to be allowed to log on as a batch job on this machine, and an' +
               ' elevated session to register it. Leave -ViaTask off to be asked for that account''s' +
               ' password instead, which is the path that worked.')
    }
    $code = 1
    try {
        Start-ScheduledTask -TaskName $name
        $waited = 0
        while ($waited -lt 300) {
            Start-Sleep -Seconds 2
            $waited += 2
            if ((Get-ScheduledTask -TaskName $name).State -ne 'Running' -and
                (Get-ScheduledTaskInfo -TaskName $name).LastRunTime.Year -gt 1999) { break }
        }
        $code = (Get-ScheduledTaskInfo -TaskName $name).LastTaskResult
    } finally {
        Unregister-ScheduledTask -TaskName $name -Confirm:$false -ErrorAction SilentlyContinue
        Remove-Item $runner -Force -ErrorAction SilentlyContinue
    }
    if (Test-Path $out) {
        Get-Content $out | ForEach-Object { Write-Host $_ }
        if ($OutFile) { Copy-Item -Path $out -Destination $OutFile -Force }
        Remove-Item $out -Force -ErrorAction SilentlyContinue
    } else {
        Write-Host ('the task wrote nothing. ' + $Account + ' may not be allowed to run a task here,' +
                    ' or S4U gave it a token the database would not take; run it with the password instead.')
    }
    Write-Host ('exit ' + $code)
    exit $code
}

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
           '. Either that is not the password, or that account may not log on at this machine' +
           ' (a task account is often allowed to run as a batch job and nothing else).' +
           ' Try the same command with -ViaTask, which needs no password.')
}

foreach ($f in @($out, $err)) {
    if ((Test-Path $f) -and (Get-Item $f).Length -gt 0) { Get-Content $f | ForEach-Object { Write-Host $_ } }
}
if ($OutFile -and (Test-Path $out)) { Copy-Item -Path $out -Destination $OutFile -Force }
Remove-Item $out, $err -Force -ErrorAction SilentlyContinue
Write-Host ('exit ' + $code)
exit $code

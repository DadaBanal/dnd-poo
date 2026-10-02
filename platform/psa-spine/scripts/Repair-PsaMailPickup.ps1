<#
.SYNOPSIS
    Why inbound mail stopped, and the safe fixes, in one pass. Preview by default.

.DESCRIPTION
    Dada, 2 Oct 2026: "the emails aren't syncing in again". Inbound mail has stopped three times now and each
    time the cause was somewhere else, so this reads every place it can be and says which one it is:

      1. the scheduled tasks        PSA-Mail-Helpdesk and PSA-Mail-Support: registered, enabled, running, last
                                    result, how long since the last run. A task that is disabled or has not run
                                    this hour is the commonest cause and the one this script can fix.
      2. the certificate            the app's sign-in certificate, found by the thumbprint in mail-app.txt. An
                                    expired certificate stops every pass with a 401 and nothing else explains it.
                                    Never printed: only found or not, and the day it expires.
      3. the delta link             Graph's bookmark per mailbox. When it expires Graph answers 410 and, before
                                    2 Oct 2026, the pass threw on every run from then on. -ResetDelta forgets it
                                    and the next pass reads from -Since instead; nothing is imported twice,
                                    because the import is keyed by Message-ID.
      4. the drop folder            mail waiting to be imported, and anything moved to failed\ by a pass that
                                    could not place it.
      5. the desk's own side         what the desk has taken in the last two days. With -AsDesk this is asked as
                                    the account the desk runs as, because a SQL sysadmin's own login resolves to
                                    database user [dbo] and the desk refuses that on purpose.
      6. one real pass per mailbox  in PREVIEW, so Graph's own answer is in the log, whatever it is -- EXCEPT for a
                                    mailbox whose delta link step 3 just forgot, where the pass runs for real with
                                    -Since, because that is the only thing that re-reads the window. The task's own
                                    -Since defaults to now, so a reset alone imports nothing. That pass fetches as
                                    whoever ran it and imports as them too, so under a sysadmin's login the placing
                                    is refused; the messages still land in the drop folder and the minute task, which
                                    runs as the desk's own account, imports them from there.

    What it changes, and only with -Apply:
      - enables and starts a task that is registered but disabled or stopped;
      - with -ResetDelta, deletes the saved delta link (after copying it beside itself) and then runs ONE real
        pass from -Since for that mailbox, which is what actually imports the window the link was skipping.
    It never registers a task, never writes a certificate, imports mail only on the one pass that follows a
    -ResetDelta -Apply (and never twice: the import is keyed by Message-ID), and never types a
    credential of its own (with -AsDesk, step 5 hands off to Invoke-PsaSpine.ps1, which does its own asking
    at the Windows prompt). Anything else it finds, it names, with the one command that fixes it.

.EXAMPLE
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Repair-PsaMailPickup.ps1
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Repair-PsaMailPickup.ps1 -Apply
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Repair-PsaMailPickup.ps1 -Apply -ResetDelta
#>
[CmdletBinding()]
param(
    [string[]] $Mailbox = @('helpdesk@pmcne.ph', 'support@pmcne.ph'),
    [string] $AppFile = 'D:\psa\mail-app.txt',
    [string] $CertFile = 'D:\psa\mail-cert.txt',
    [string] $StateDir = 'D:\psa\mail-state',
    [string] $DropDir = 'D:\psa\mail-drop',
    [string] $AttachmentDir = 'D:\psa\files',
    [string] $Database = 'Driver={ODBC Driver 17 for SQL Server};Server=DND-SQL01\PMC_SS;Database=PMC_PSA;Trusted_Connection=yes;Encrypt=yes;TrustServerCertificate=yes',
    [string] $SpineDir,
    [string] $PythonExe = 'C:\PMC\Python312\python.exe',
    [datetime] $Since = (Get-Date).AddDays(-2),
    [string] $BoardId = 'IT_HELP',
    [int] $StaleMinutes = 15,
    [switch] $ResetDelta,
    # Ask the desk as the account the desk runs as. Without this, step 5 is
    # asked under the caller's own login, and a SQL sysadmin's login resolves to
    # database user [dbo], which the desk refuses on purpose -- so step 5 always
    # reported a problem that was not one (MEASURED, 2 Oct 2026). With it, that
    # one step hands off to scripts\Invoke-PsaSpine.ps1, which does its own
    # asking at the Windows prompt; this script still types no credential of its
    # own and holds none.
    [switch] $AsDesk,
    [switch] $Apply
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Continue'
if (-not $SpineDir) { $SpineDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path) }
$LogFile = Join-Path $StateDir 'repair-mail-pickup.log'
$script:Findings = @()
$script:Fixed = @()
$script:Forgot = @()        # mailboxes whose delta link this run forgot

function Write-Step([string] $Text) {
    $line = (Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + '  ' + $Text
    Write-Host $line
    if (Test-Path $StateDir) { Add-Content -Path $LogFile -Value $line -Encoding UTF8 }
}
function Add-Finding([string] $What, [string] $Then) {
    $script:Findings += [PSCustomObject]@{ What = $What; Then = $Then }
    Write-Step ('  PROBLEM: ' + $What)
}
function Slug([string] $Address) {
    # Exactly the pickup's own rule (Invoke-PmcMailPickup.ps1): the repair must
    # agree character for character or it reads somebody else's files, or none.
    return ($Address.ToLowerInvariant() -replace '[^a-z0-9]+', '-').Trim('-')
}

Write-Step ('start' + $(if ($Apply) { ' (-Apply)' } else { ' (preview: nothing is changed)' }))
$me = [Security.Principal.WindowsIdentity]::GetCurrent()
$elevated = ([Security.Principal.WindowsPrincipal]$me).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
Write-Step ('as ' + $me.Name + $(if ($elevated) { ' (elevated)' } else { ' (NOT elevated: tasks can be read, not started)' }))

# ---------------------------------------------------------------- 1. the tasks
Write-Step '1. the scheduled tasks'
$taskFor = @{}
foreach ($mb in $Mailbox) { $taskFor[$mb] = $null }
foreach ($t in @('PSA-Mail-Helpdesk', 'PSA-Mail-Support', 'PSA-Notify', 'PSA-Calendar')) {
    $task = Get-ScheduledTask -TaskName $t -ErrorAction SilentlyContinue
    if (-not $task) {
        if ($t -eq 'PSA-Mail-Helpdesk') {
            Add-Finding ($t + ' is not registered, so no mail is picked up at all.') `
                        'Register-PsaMail.ps1 -Apply (elevated, as the task account''s owner).'
        } else {
            Write-Step ('  ' + $t + ': not registered')
            if ($t -eq 'PSA-Notify') {
                Add-Finding 'PSA-Notify is not registered, so no requester email goes OUT (this is not the inbound fault, but it is still broken).' `
                            'Register-PsaMail.ps1 -IncludeSupport -IncludeCalendar -Apply (elevated).'
            }
        }
        continue
    }
    $info = Get-ScheduledTaskInfo -TaskName $t
    $last = $info.LastRunTime
    $mins = if ($last -and $last.Year -gt 1999) { [int]((Get-Date) - $last).TotalMinutes } else { -1 }
    $res = $info.LastTaskResult
    Write-Step ('  ' + $t + ': state ' + $task.State + ', last run ' +
                $(if ($mins -ge 0) { $last.ToString('yyyy-MM-dd HH:mm') + ' (' + $mins + ' min ago)' } else { 'never' }) +
                ', last result ' + $res)
    if ($task.State -eq 'Disabled') {
        if ($Apply -and $elevated) {
            Enable-ScheduledTask -TaskName $t | Out-Null
            Start-ScheduledTask -TaskName $t
            $script:Fixed += ($t + ' was disabled: enabled and started')
            Write-Step ('  FIXED: ' + $t + ' enabled and started')
        } else {
            Add-Finding ($t + ' is DISABLED, so it never runs.') 'Re-run this script elevated with -Apply, which enables and starts it.'
        }
    } elseif ($mins -lt 0 -or $mins -gt $StaleMinutes) {
        if ($Apply -and $elevated) {
            Start-ScheduledTask -TaskName $t
            $script:Fixed += ($t + ' had not run for ' + $(if ($mins -lt 0) { 'ever' } else { "$mins min" }) + ': started once')
            Write-Step ('  FIXED: ' + $t + ' started once; its own schedule carries on')
        } else {
            Add-Finding ($t + ' has not run for ' + $(if ($mins -lt 0) { 'ever' } else { "$mins minutes" }) +
                         ', and it is meant to run every minute.') 'Re-run this script elevated with -Apply, which starts it.'
        }
    }
    if ($res -ne 0 -and $res -ne 267011) {
        Add-Finding ($t + ' last ended with result ' + $res + ' (not success).') ('Read its log under ' + $StateDir + ' and the pass below.')
    }
}

# -------------------------------------------------------- 2. the certificate
Write-Step '2. the sign-in certificate'
$ids = @{}
if (-not (Test-Path $AppFile)) {
    Add-Finding ($AppFile + ' is missing, so nothing can sign in to Graph.') 'New-PsaMailApp.ps1 made it; restore it from the backup, or re-run that script.'
} else {
    foreach ($l in Get-Content $AppFile) { if ($l -match '^\s*(\w+)\s*=\s*(\S+)\s*$') { $ids[$Matches[1]] = $Matches[2] } }
    foreach ($k in @('TenantId', 'AppId')) {
        if (-not $ids.ContainsKey($k)) { Add-Finding ($AppFile + ' has no ' + $k + '.') 'Re-run New-PsaMailApp.ps1, or restore the file.' }
    }
}
# The thumbprint is NOT in mail-app.txt. New-PsaMailApp.ps1 writes AppId,
# ObjectId and TenantId there, and the certificate's thumbprint goes in
# mail-cert.txt, which Register-PsaMail.ps1 reads with this same regex.
# Looking in the wrong file is how this script reported a certificate fault on
# a host whose certificate was fine (MEASURED on DND-SQL01, 2 Oct 2026).
if (-not (Test-Path $CertFile)) {
    Add-Finding ($CertFile + ' is missing, so the thumbprint cannot be read here.') `
                ('The tasks carry the thumbprint in their own arguments and may be working regardless. ' +
                 'New-PsaMailApp.ps1 writes this file.')
} else {
    $m = [regex]::Match((Get-Content $CertFile -Raw), '\b[0-9A-Fa-f]{40}\b')
    if (-not $m.Success) {
        Add-Finding ($CertFile + ' holds no certificate thumbprint.') 'Re-run New-PsaMailApp.ps1, or restore the file.'
    } else {
        $ids['Thumbprint'] = $m.Value
        $cert = $null
        foreach ($store in 'Cert:\LocalMachine\My', 'Cert:\CurrentUser\My') {
            $c = Get-ChildItem -Path $store -ErrorAction SilentlyContinue | Where-Object { $_.Thumbprint -eq $ids['Thumbprint'] }
            if ($c) { $cert = $c; Write-Step ('  found in ' + $store) ; break }
        }
        if (-not $cert) {
            Add-Finding 'The certificate named in mail-cert.txt is in neither certificate store for this account.' `
                        'The task runs as its own account: check the store of THAT account, or re-run New-PsaMailApp.ps1.'
        } else {
            $days = [int]($cert.NotAfter - (Get-Date)).TotalDays
            Write-Step ('  valid until ' + $cert.NotAfter.ToString('yyyy-MM-dd') + ' (' + $days + ' days)')
            if ($days -lt 0) {
                Add-Finding 'The sign-in certificate HAS EXPIRED. Every pass fails at sign-in and no mail can arrive.' `
                            'New-PsaMailApp.ps1 to make and upload a new one; nothing else will fix it.'
            } elseif ($days -lt 21) {
                Add-Finding ('The sign-in certificate expires in ' + $days + ' days.') 'Renew it with New-PsaMailApp.ps1 before it does.'
            }
        }
    }
}

# --------------------------------------------------------- 3. the delta links
Write-Step '3. the delta link per mailbox'
if (-not (Test-Path $StateDir)) {
    Add-Finding ($StateDir + ' does not exist, so no pass can keep its place.') 'Make the folder, or correct -StateDir.'
} else {
    foreach ($mb in $Mailbox) {
        $slug = Slug $mb
        $df = Join-Path $StateDir ('inbox-deltalink-' + $slug + '.txt')
        if (-not (Test-Path $df)) {
            Write-Step ('  ' + $mb + ': no delta link yet; the next pass reads from -Since')
        } else {
            $age = [int]((Get-Date) - (Get-Item $df).LastWriteTime).TotalMinutes
            Write-Step ('  ' + $mb + ': delta link last saved ' + $age + ' min ago')
            if ($ResetDelta) {
                if ($Apply) {
                    Copy-Item -Path $df -Destination ($df + '.' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.bak') -Force
                    Remove-Item -Path $df -Force
                    $script:Forgot += $mb
                    $script:Fixed += ($mb + ': delta link forgotten (a copy is kept beside it); the pass in step 6 reads from ' + $Since.ToString('yyyy-MM-dd HH:mm'))
                    Write-Step ('  FIXED: ' + $mb + ' delta link forgotten')
                } else {
                    Write-Step ('  would forget the delta link for ' + $mb + ' (-Apply does it)')
                }
            } elseif ($age -gt 120) {
                Add-Finding ($mb + ': the delta link has not moved for ' + $age + ' minutes, so no pass has finished in that time.') `
                            'Read the pass below; if Graph answers 410 the link has expired, and -ResetDelta -Apply clears it.'
            }
        }
        $log = Join-Path $StateDir ('mail-pickup-' + $slug + '.log')
        if (Test-Path $log) {
            Write-Step ('  the last 6 lines of ' + (Split-Path -Leaf $log) + ':')
            foreach ($l in (Get-Content -Path $log -Tail 6)) { Write-Step ('    | ' + $l) }
        } else {
            Write-Step ('  no log at ' + $log + ' yet')
        }
    }
}

# ------------------------------------------------------------ 4. the folders
Write-Step '4. the drop folder and the files folder'
foreach ($d in @($DropDir, $AttachmentDir)) {
    if (-not (Test-Path $d)) {
        Add-Finding ($d + ' does not exist.') 'Make it, or correct the matching parameter on the task.'
    } else {
        $n = @(Get-ChildItem -Path $d -Filter *.eml -ErrorAction SilentlyContinue).Count
        Write-Step ('  ' + $d + ': ' + $n + ' .eml waiting')
    }
}
$failed = Join-Path $DropDir 'failed'
if (Test-Path $failed) {
    $n = @(Get-ChildItem -Path $failed -Filter *.eml -ErrorAction SilentlyContinue).Count
    if ($n -gt 0) {
        Add-Finding ($n + ' message(s) sit in ' + $failed + ': a pass could not place them.') `
                    'psaspine mail-why --sender <the sender> says why for one of them; put the cause right, then mail-retry.'
    }
}

# ------------------------------------------- 5. the desk's own side of it
Write-Step '5. what the desk has taken (its side, not the mailbox''s)'
if (-not (Test-Path $PythonExe)) {
    Write-Step ('  skipped: ' + $PythonExe + ' is not there')
} else {
    $asDeskScript = Join-Path (Join-Path $SpineDir 'scripts') 'Invoke-PsaSpine.ps1'
    Push-Location $SpineDir
    $eap = $ErrorActionPreference; $ErrorActionPreference = 'Continue'
    try {
        if ($AsDesk -and (Test-Path $asDeskScript)) {
            Write-Step '    asking as the desk''s own account (-AsDesk)'
            $h = & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $asDeskScript `
                     -MailHealth -Days 2 -Database $Database -SpineDir $SpineDir -PythonExe $PythonExe 2>&1
            $hc = $LASTEXITCODE
        } else {
            $h = & $PythonExe -m psaspine mail-health $Database --days 2 2>&1
            $hc = $LASTEXITCODE
        }
    } finally { $ErrorActionPreference = $eap; Pop-Location }
    foreach ($l in @($h)) { Write-Step ('    | ' + $l) }
    if ($hc -ne 0 -and (($h | Out-String) -match 'default schema')) {
        # Not a fault in the desk and not a fault in the mail: the question was
        # asked under the wrong login. Say which, and how to ask again.
        Add-Finding 'the desk was asked under this login, and a SQL sysadmin resolves to database user [dbo], which the desk refuses on purpose.' `
                    'Ask as the account the desk runs as: add -AsDesk to this command, or run scripts\Invoke-PsaSpine.ps1 -MailHealth. Step 5 says nothing either way about whether mail is arriving; steps 1-4 and 6 do.'
    } elseif ($hc -ne 0) {
        Add-Finding ('the desk could not be asked what it has taken (exit ' + $hc + ').') `
                    'Run scripts\Invoke-PsaSpine.ps1 -MailHealth, which asks as the account the desk runs as, and read what it says.'
    } elseif (($h | Out-String) -match 'NOTHING arrived in that window') {
        Add-Finding 'The desk has taken NO mail in the last 2 days, so the fault is before the desk: the pickup, not intake.' `
                    'The pass below says what Graph answered; that is the cause.'
    } elseif (($h | Out-String) -match 'were set aside with an error') {
        Add-Finding 'Mail is reaching the desk but some of it was set aside with an error, so those made no ticket.' `
                    'psaspine mail-why --sender <the sender> names the cause; put it right, then psaspine mail-retry.'
    }
}

# --------------------------------------------------- 6. one real pass
# A forgotten delta link on its own imports NOTHING, and this is why: the
# scheduled task runs Invoke-PmcMailPickup.ps1 with no -Since, and that
# parameter defaults to now. So the task's first pass after a reset asks Graph
# for mail that arrived since this minute, finds none, and saves a fresh link
# over the window that was meant to be re-read. MEASURED on DND-SQL01, 2 Oct
# 2026: the links were cleared at 09:39 and every task pass after it logged
# "0 new message(s) since last pass", while a preview from -Since could see 12
# and 66 waiting. So the pass that follows a reset is this script's to run,
# with -Since, and it has to be a real one.
$doImport = @($script:Forgot).Count -gt 0
Write-Step ('6. one pass per mailbox' + $(if ($doImport) { ', FOR REAL where the delta link was just forgotten' } else { ', in preview (nothing is written)' }))
$pickup = Join-Path (Join-Path $SpineDir 'scripts') 'Invoke-PmcMailPickup.ps1'
if (-not (Test-Path $pickup)) {
    Add-Finding ($pickup + ' is not there, so the task has nothing to run.') 'Check -SpineDir, and that the repository is where the tasks expect it.'
} elseif (-not $ids.ContainsKey('Thumbprint')) {
    Write-Step '  skipped: no app details to sign in with'
} else {
    foreach ($mb in $Mailbox) {
        # -BoardId is only the fallback for an address no board claims; a
        # claimed address routes by itself, so this changes nothing in preview.
        $real = $doImport -and ($script:Forgot -contains $mb)
        Write-Step ('  ' + $mb + $(if ($real) { ' (importing from ' + $Since.ToString('yyyy-MM-dd HH:mm') + ') ...' } else { ' ...' }))
        $pass = @('-TenantId', $ids['TenantId'], '-ClientId', $ids['AppId'], '-CertThumbprint', $ids['Thumbprint'],
                  '-Mailbox', $mb, '-Database', $Database, '-DropDir', $DropDir, '-StateDir', $StateDir,
                  '-SpineDir', $SpineDir, '-AttachmentDir', $AttachmentDir, '-BoardId', $BoardId,
                  '-Since', $Since.ToString('yyyy-MM-dd HH:mm:ss'))
        if ($real) { $pass += '-Apply' }
        $out = & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $pickup @pass 2>&1
        $code = $LASTEXITCODE
        foreach ($l in @($out | Select-Object -Last 8)) { Write-Step ('    | ' + $l) }
        if ($code -ne 0) {
            Add-Finding ($mb + ': a pass failed (exit ' + $code + '). The lines above are Graph''s own answer.') `
                        'If it says 410, use -ResetDelta -Apply. If it says 401, the certificate or the grant is the cause. If it says 403, the mail scope does not cover this mailbox.'
        } elseif ($real) {
            # Who ran it decides whether it could place them: the pass imports
            # as the launching identity, and a SQL sysadmin resolves to [dbo],
            # which the desk refuses (SQL01, part 31). That is not a loss -- the
            # messages are fetched and waiting, and the minute task, which runs
            # as the desk's own account, imports them on its next pass.
            $said = ($out | Out-String)
            if ($said -match 'default schema' -or $said -match 'Import FAILED') {
                $script:Fixed += ($mb + ': fetched the window from ' + $Since.ToString('yyyy-MM-dd HH:mm') +
                                  ' into the drop folder. Placing them was refused under this login, so the minute' +
                                  ' task will import them as the desk''s own account within a minute or two;' +
                                  ' nothing is lost and nothing arrives twice.')
            } else {
                $script:Fixed += ($mb + ': one real pass from ' + $Since.ToString('yyyy-MM-dd HH:mm') +
                                  '; what it imported is in the lines above, and the minute task carries on from there.')
            }
        }
    }
}

# ------------------------------------------------------------------ the answer
Write-Step ''
if ($script:Fixed.Count) {
    Write-Step ('CHANGED (' + $script:Fixed.Count + '):')
    foreach ($f in $script:Fixed) { Write-Step ('  - ' + $f) }
}
if (-not $script:Findings.Count) {
    Write-Step 'RESULT: PASS. Nothing here is broken: the tasks run, the certificate is good, the delta links move, no message is stuck.'
    Write-Step 'If mail still does not become a ticket, it never reached the mailbox: check the Exchange rule and the sender.'
    exit 0
}
Write-Step ('RESULT: ' + $script:Findings.Count + ' problem(s), worst first as listed:')
$i = 0
foreach ($f in $script:Findings) {
    $i++
    Write-Step ('  ' + $i + '. ' + $f.What)
    Write-Step ('     -> ' + $f.Then)
}
if (-not $Apply) { Write-Step 'Nothing was changed. Re-run elevated with -Apply to start a stopped task, and add -ResetDelta if Graph answered 410.' }
exit 1

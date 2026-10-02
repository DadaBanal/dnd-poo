<#
.SYNOPSIS
    One line for both of 2 Oct 2026's jobs: why mail is not becoming tickets, and a member's mailbox on a
    second domain into the calendar sync. Preview by default.

.DESCRIPTION
    Dada, 2 Oct 2026: "is there a line i can run to run these all". This runs the others in order and stops
    at the one thing no script may decide for you.

      1. the code       git pull in the repository, so every script below is the one that was tested
                        (-NoPull skips it; nothing else here needs the network).
      2. the mail       Repair-PsaMailPickup.ps1 in preview, which reads the tasks, the certificate, the
                        delta links and logs, the folders, what the desk itself has taken, and runs one
                        real pass per mailbox. With -Apply it runs again and lets it start a stopped task;
                        if that pass reported 410 for a mailbox it runs a third time with -ResetDelta,
                        because an expired delta link is the one fault that never clears itself.
      3. the calendar   asks the desk for the members whose mailbox is on any -CalendarDomain, writes the
                        list to -MembersFile, and says whether -Expect is in it. With -Apply it then runs
                        Grant-PsaCalendars.ps1 against that list.

    What it will not do, and says instead:
      - make a member record, set a member's email, or put a member on a board. That is Setup > Members,
        and a person decides it. Until it is done, no script can put them in the sync.
      - register or re-register a scheduled task: that asks for the task account's password, so it is
        yours to run, and the line to run is printed.
      - type a credential, or print a tenant id, an app id or a thumbprint. With -AsDesk the questions it
        puts to the desk go through Invoke-PsaSpine.ps1, which does its own asking at the Windows prompt;
        this script still holds nothing.

.EXAMPLE
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Fix-PsaToday.ps1
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Fix-PsaToday.ps1 -Apply
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Fix-PsaToday.ps1 -Apply -AsDesk   # a sysadmin needs this
#>
[CmdletBinding()]
param(
    [switch] $Apply,
    [switch] $NoPull,
    [switch] $SkipMail,
    [switch] $SkipCalendar,
    # Ask the desk as the account the desk runs as, through Invoke-PsaSpine.ps1,
    # which asks at the Windows prompt once. Without it, every question put to
    # the desk here is put under the caller's own login, and a SQL sysadmin's
    # login resolves to database user [dbo], which the desk refuses on purpose
    # (MEASURED on DND-SQL01, 2 Oct 2026). It is refused, not answered wrongly,
    # so the steps that only read the mail plumbing are unaffected either way.
    [switch] $AsDesk,
    # The mail domains whose members have a calendar to sync. Both are named because a member's mailbox is
    # on the second one (Dada, 2 Oct 2026: encoder@premieremedicalcenter.net).
    [string[]] $CalendarDomain = @('pmcne.ph', 'premieremedicalcenter.net'),
    [string] $Expect = 'encoder@premieremedicalcenter.net',
    [string] $MembersFile = 'D:\psa\calendar-members.json',
    [string] $RepoDir = 'D:\dnd-poo',
    [string] $Database = 'Driver={ODBC Driver 17 for SQL Server};Server=DND-SQL01\PMC_SS;Database=PMC_PSA;Trusted_Connection=yes;Encrypt=yes;TrustServerCertificate=yes',
    [string] $PythonExe = 'C:\PMC\Python312\python.exe'
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Continue'
$SpineDir = Join-Path (Join-Path $RepoDir 'platform') 'psa-spine'
$ScriptDir = Join-Path $SpineDir 'scripts'
$script:Next = @()

function Say([string] $Text) { Write-Host ((Get-Date -Format 'HH:mm:ss') + '  ' + $Text) }
function Rule([string] $Text) { Write-Host ''; Write-Host ('=== ' + $Text); Write-Host '' }
function Later([string] $Text) { $script:Next += $Text }

Rule ('Dada PSA, both jobs' + $(if ($Apply) { ' (-Apply: it will change what is safe)' } else { ' (preview: nothing is changed)' }))
$me = [Security.Principal.WindowsIdentity]::GetCurrent()
$elevated = ([Security.Principal.WindowsPrincipal]$me).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
Say ('as ' + $me.Name + $(if ($elevated) { ' (elevated)' } else { ' (NOT elevated: a stopped task cannot be started from here)' }))
if ($Apply -and -not $elevated) { Later 'Re-run this elevated: starting a stopped scheduled task needs it.' }

# ------------------------------------------------------------------ 1. the code
if ($NoPull) {
    Say 'skipping the pull (-NoPull)'
} else {
    Rule '1. the code'
    if (-not (Test-Path (Join-Path $RepoDir '.git'))) {
        Say ($RepoDir + ' is not a git checkout; skipping the pull')
        Later ('Put the scripts in ' + $ScriptDir + ' by hand, or correct -RepoDir.')
    } else {
        Push-Location $RepoDir
        try {
            $before = (& git rev-parse --short HEAD 2>&1 | Out-String).Trim()
            $out = & git pull 2>&1
            $pulled = ($LASTEXITCODE -eq 0)
            foreach ($l in @($out)) { Say ('  | ' + $l) }
            $after = (& git rev-parse --short HEAD 2>&1 | Out-String).Trim()
            Say ('head ' + $before + ' -> ' + $after)
            # A pull that refused is not "already up to date": saying so once sent
            # a whole run on with the old code, and every step after it misread the
            # host (MEASURED on DND-SQL01, 2 Oct 2026).
            if (-not $pulled) {
                Say '  THE PULL FAILED: this host is still on the old code, and every step below is reading it.'
                $why = ($out | Out-String)
                if ($why -match 'local changes|untracked working tree') {
                    Later ('The pull refused because files under ' + $ScriptDir + ' differ from the repository: ' +
                           'scripts saved there by hand. To keep the repository''s copies, which are the tested ones: ' +
                           'cd ' + $RepoDir + ' ; git checkout -- platform/psa-spine/scripts ; ' +
                           'git clean -fd platform/psa-spine/scripts ; git pull . Then run this line again.')
                } else {
                    Later ('The pull refused. Read its words above, put it right in ' + $RepoDir + ', and run this line again.')
                }
            } elseif ($after -eq $before) { Say '  (already up to date)' }
        } finally { Pop-Location }
    }
}

# ------------------------------------------------------------------ 2. the mail
if ($SkipMail) { Say 'skipping the mail (-SkipMail)' } else {
    Rule '2. mail is not becoming tickets: which cause is it this time'
    $repair = Join-Path $ScriptDir 'Repair-PsaMailPickup.ps1'
    if (-not (Test-Path $repair)) {
        Say ('MISSING: ' + $repair)
        Later ('Repair-PsaMailPickup.ps1 is not in ' + $ScriptDir + '. Pull the repository, or save it there.')
    } else {
        $asDeskArgs = @(); if ($AsDesk) { $asDeskArgs = @('-AsDesk') }
        $look = & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $repair -Database $Database -SpineDir $SpineDir -PythonExe $PythonExe @asDeskArgs 2>&1
        foreach ($l in @($look)) { Write-Host ('    ' + $l) }
        $said = ($look | Out-String)
        $gone = $said -match '\b410\b'
        if ($Apply) {
            Rule '2b. letting it fix what is safe'
            $fix = & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $repair -Database $Database -SpineDir $SpineDir -PythonExe $PythonExe @asDeskArgs -Apply 2>&1
            foreach ($l in @($fix)) { Write-Host ('    ' + $l) }
            if ($gone -or (($fix | Out-String) -match '\b410\b')) {
                Rule '2c. a delta link has expired (410): forgetting it, keeping a copy'
                $rd = & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $repair -Database $Database -SpineDir $SpineDir -PythonExe $PythonExe @asDeskArgs -Apply -ResetDelta 2>&1
                foreach ($l in @($rd)) { Write-Host ('    ' + $l) }
            }
        } elseif ($gone) {
            Later 'A delta link has expired (410). Re-run with -Apply: it clears it and keeps a copy.'
        }
        if ($said -match 'is not registered') {
            Later ('A mail task is not registered. That needs the task account''s password, so it is yours: ' +
                   'Register-PsaMail.ps1 -IncludeSupport -IncludeCalendar -Apply (elevated).')
        }
        # -cmatch, and the word certificate: -match is case-insensitive, and the
        # repair's own closing advice once said "if a link has expired", which this
        # read as an expired certificate (MEASURED on DND-SQL01, 2 Oct 2026).
        if ($said -cmatch 'certificate HAS EXPIRED') {
            Later 'The sign-in certificate has expired. Nothing else will fix it: New-PsaMailApp.ps1 makes and uploads a new one.'
        }
        if (-not $Apply) { Later 'Re-run this with -Apply to start a stopped task and clear an expired delta link.' }
    }
}

# -------------------------------------------------------------- 3. the calendar
if ($SkipCalendar) { Say 'skipping the calendar (-SkipCalendar)' } else {
    Rule ('3. the calendar sync, for mailboxes on: ' + ($CalendarDomain -join ', '))
    if (-not (Test-Path $PythonExe)) {
        Say ('MISSING: ' + $PythonExe)
        Later 'Correct -PythonExe; the desk cannot be asked for its members without it.'
    } else {
        $domArgs = @(); foreach ($d in $CalendarDomain) { $domArgs += @('--allowed-domain', $d) }
        $asDeskScript = Join-Path $ScriptDir 'Invoke-PsaSpine.ps1'
        $jsonFile = $null
        Push-Location $SpineDir
        try {
            if ($AsDesk -and (Test-Path $asDeskScript)) {
                # -OutFile, so what comes back is the command's own output and
                # not that script's lines about which account it used.
                $jsonFile = Join-Path $env:TEMP ('psa-members-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.json')
                $shown = & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $asDeskScript `
                             -Spine ('calendar-members ' + ($domArgs -join ' ')) -OutFile $jsonFile `
                             -Database $Database -SpineDir $SpineDir -PythonExe $PythonExe 2>&1
                $code = $LASTEXITCODE
                foreach ($l in @($shown)) { Say ('  | ' + $l) }
                $json = if (Test-Path $jsonFile) { Get-Content $jsonFile -Raw } else { '' }
            } else {
                $json = & $PythonExe -m psaspine calendar-members $Database @domArgs 2>&1
                $code = $LASTEXITCODE
            }
        } finally {
            Pop-Location
            if ($jsonFile) { Remove-Item $jsonFile -Force -ErrorAction SilentlyContinue }
        }
        if ($code -ne 0) {
            foreach ($l in @($json)) { Say ('  | ' + $l) }
            Say 'the desk refused to list its members'
            Later ('Ask as the account the desk runs as: add -AsDesk to this line, or run' +
                   ' scripts\Invoke-PsaSpine.ps1 -Spine "calendar-members --allowed-domain pmcne.ph' +
                   ' --allowed-domain premieremedicalcenter.net". A SQL sysadmin''s own connection resolves' +
                   ' to schema [dbo], which the desk refuses on purpose.')
        } else {
            $text = ($json | Out-String).Trim()
            $people = @()
            foreach ($x in ($text | ConvertFrom-Json)) { if ($null -ne $x -and $x.PSObject.Properties['mailbox']) { $people += $x.mailbox.ToLowerInvariant() } }
            Say ('the desk has ' + $people.Count + ' member(s) with a mailbox on those domains')
            $has = $people -contains $Expect.ToLowerInvariant()
            if ($has) {
                Say ('  ' + $Expect + ' IS in the list')
            } else {
                Say ('  ' + $Expect + ' is NOT in the list')
                Later ('Before ' + $Expect + ' can be in the calendar sync, Setup > Members must give that person a ' +
                       'member record with that email AND WORK or ADMIN on a board. A READ-only member is not in the sync. ' +
                       'You can do it from your normal Windows sign-in; then run this line again.')
            }
            if ($Apply) {
                $dir = Split-Path -Parent $MembersFile
                if ($dir -and -not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
                Set-Content -Path $MembersFile -Value $text -Encoding ASCII
                Say ('wrote ' + $MembersFile)
            } else {
                Say ('would write the list to ' + $MembersFile + ' (-Apply does it)')
            }
            if (-not $has) {
                Say 'not granting: the list is missing the person this was for'
            } else {
                $grant = Join-Path $ScriptDir 'Grant-PsaCalendars.ps1'
                if (-not (Test-Path $grant)) {
                    Later ('Grant-PsaCalendars.ps1 is not in ' + $ScriptDir + '.')
                } elseif (-not $elevated) {
                    Later ('The grant must run elevated, and it opens a browser to sign in to Exchange Online: ' +
                           'Grant-PsaCalendars.ps1 -MembersFile ' + $MembersFile + ' -Apply')
                } elseif ($Apply) {
                    Rule '3b. granting the mail app those calendars (a browser window opens)'
                    $g = & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $grant -MembersFile $MembersFile -Apply 2>&1
                    foreach ($l in @($g)) { Write-Host ('    ' + $l) }
                    Later 'The calendar permission can take 30 minutes to 2 hours to take effect; the grant says InScope True or NOT YET per mailbox.'
                } else {
                    Say ('would run: Grant-PsaCalendars.ps1 -MembersFile ' + $MembersFile + ' -Apply (-Apply does it)')
                }
            }
            Later ('So the scheduled sync keeps naming both domains, re-register that one task (it asks for the task ' +
                   'account''s password, so it is yours): Unregister-ScheduledTask -TaskName ''PSA-Calendar'' -Confirm:$false ; ' +
                   'then Register-PsaMail.ps1 -IncludeSupport -IncludeCalendar -CalendarDomain ' +
                   ($CalendarDomain -join ',') + ' -Apply')
        }
    }
}

# ------------------------------- the two the desk's own account has to be asked
# Neither can be run from here under a sysadmin's login, and neither is safe to
# assume: the schema step is what lets the desk store a note written in the new
# editor, and the release is what puts the messages intake set aside onto the
# board. Both are guarded, and a second run of either changes nothing.
Later ('If this pull''s schema step is not applied yet: Invoke-PsaSpine.ps1 -SchemaPreview, then' +
       ' Invoke-PsaSpine.ps1 -SchemaApply. Until it is, a note written in the ticket editor will not save.')
Later ('To put the messages intake set aside onto the board: Invoke-PsaSpine.ps1 -MailRetry to see them,' +
       ' then Invoke-PsaSpine.ps1 -MailRetry -All -Apply. A message that already made a ticket is never' +
       ' released, so nothing is duplicated.')

# ------------------------------------------------------------------- what is left
Rule 'what is left for you'
if (-not $script:Next.Count) {
    Say 'nothing. Both jobs are done as far as a script can take them.'
} else {
    $i = 0
    foreach ($n in $script:Next) { $i++; Write-Host ('  ' + $i + '. ' + $n) }
}
Write-Host ''
Say 'Nothing here was verified against Exchange or the mailbox from anywhere but this host.'

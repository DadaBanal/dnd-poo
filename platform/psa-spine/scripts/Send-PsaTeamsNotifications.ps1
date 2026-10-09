<#
.SYNOPSIS
    Post the desk's pending Teams cards (workflow rules on the TEAMS channel, and pages) to their channels.

.DESCRIPTION
    Runs on DND-SQL01 beside Send-PmcNotifications.ps1, which sends the email
    channel; this one takes the TEAMS channel and nothing else. Once a minute:
      1. asks `psaspine outbox-pending --channel TEAMS` for the cards that are due,
         each keyed by the channel's short name (Setup > Integrations > Teams channels);
      2. looks the name up in -WebhookFile, a JSON object { "<name>": "https://..." }
         that lives only on this host (D:\psa\teams-webhooks.json), never in the
         repository and never in the database;
      3. posts the card to that URL and reports the result with `psaspine outbox-mark`.

    A URL is posted to only when it is https:// and on a Microsoft host: a Teams
    Workflows "post to a channel" webhook on *.environment.api.powerplatform.com
    (the shape made today), or the retired *.webhook.office.com and
    *.logic.azure.com shapes. Anything else is marked FAILED and never posted: a
    card carries a ticket number and a priority, and those do not leave the tenant.

    PREVIEW BY DEFAULT. Without -Apply it counts what is due, checks every named
    channel has a URL in the file, and stops: nothing is posted and the desk is
    not changed.

    Logs counts only. Never a URL, a subject or a card.

    -DeskUrl is the https:// address of the desk, for the "Open on the desk"
    button on the card (else PSA_PUBLIC_URL). -DeskAwayUrl, the desk away from
    PMC (behind the sign-in gate), adds an "Open away from PMC" button beside it
    (else PSA_DESK_AWAY_URL; left out, no second button). Deployment config,
    never committed.

.EXAMPLE
    .\Send-PsaTeamsNotifications.ps1 -Database D:\psa\spine.db -WebhookFile D:\psa\teams-webhooks.json `
        -StateDir D:\psa\mail-state -DeskUrl https://desk.pmcne.ph
.EXAMPLE
    .\Send-PsaTeamsNotifications.ps1 ... -Apply -Loop -IntervalSeconds 60
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)] [string] $Database,
    [Parameter(Mandatory = $true)] [string] $WebhookFile,
    [Parameter(Mandatory = $true)] [string] $StateDir,
    [string] $DeskUrl,
    [string] $DeskAwayUrl,
    [string] $SpineDir,
    [string] $PythonExe = 'C:\PMC\Python312\python.exe',
    [int] $IntervalSeconds = 60,
    [switch] $Loop,
    [switch] $Apply
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'
# The repository root, one above scripts\. Not a param() default: under Windows
# PowerShell 5.1 run with -File, $PSScriptRoot is empty while the defaults are
# evaluated (MEASURED on DND-SQL01, part 21), so the default is resolved here.
if (-not $SpineDir) { $SpineDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path) }
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$LogFile = Join-Path $StateDir 'teams-send.log'

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

function Test-WebhookUrl([string] $Url) {
    # https only, and only a Microsoft host: the card names a ticket and a priority.
    # A Teams Workflows webhook made today is on *.environment.api.powerplatform.com
    # (VERIFIED by SQL01 on learn.microsoft.com, 30 Sep 2026). The classic Office 365
    # connector (*.webhook.office.com) retired on 30 April 2026 and Power Automate's
    # *.logic.azure.com trigger addresses on 30 November 2025; both are still allowed
    # here for a tenant that has not moved, and a post to them will simply fail and
    # be marked FAILED.
    if (-not $Url) { return $false }
    try { $u = [Uri] $Url } catch { return $false }
    if ($u.Scheme -ne 'https') { return $false }
    $h = $u.Host.ToLower()
    return ($h.EndsWith('.api.powerplatform.com') -or $h.EndsWith('.webhook.office.com') -or $h.EndsWith('.logic.azure.com'))
}

function Read-Webhooks {
    if (-not (Test-Path $WebhookFile)) { throw "Webhook file not found: $WebhookFile" }
    $raw = Get-Content -Path $WebhookFile -Raw -Encoding UTF8
    $obj = $raw | ConvertFrom-Json
    $map = @{}
    foreach ($p in $obj.PSObject.Properties) { $map[$p.Name.ToLower()] = [string] $p.Value }
    return $map
}

function Send-Card($Item, [string] $Url) {
    $json = $Item.card | ConvertTo-Json -Depth 20 -Compress
    Invoke-RestMethod -Method Post -Uri $Url -ContentType 'application/json' `
        -Body ([Text.Encoding]::UTF8.GetBytes($json)) | Out-Null
}

function Invoke-Pass {
    $hooks = Read-Webhooks
    $args1 = @('outbox-pending', $Database, '--channel', 'TEAMS', '--allowed-domain', 'unused')
    if (-not $Apply) { $args1 += '--dry-run' }
    if ($DeskUrl) { $args1 += @('--desk-url', $DeskUrl) }
    if ($DeskAwayUrl) { $args1 += @('--desk-away-url', $DeskAwayUrl) }
    $r = Invoke-Spine $args1
    if ($r.Code -ne 0) { throw "outbox-pending failed (exit $($r.Code))" }
    # Under Windows PowerShell 5.1, '[]' | ConvertFrom-Json is ONE object (an
    # empty array), so @(...) counts 1 and .id fails on it (MEASURED on
    # DND-SQL01, part 21). foreach enumerates the array's elements on 5.1 and
    # 7 alike, so an idle pass counts 0 on both.
    $items = @()
    if ($r.Out) {
        foreach ($x in ($r.Out | ConvertFrom-Json)) {
            if ($null -ne $x -and $x.PSObject.Properties['id']) { $items += $x }
        }
    }

    if (-not $Apply) {
        $missing = @($items | Where-Object { -not $hooks.ContainsKey($_.target.ToLower()) } | ForEach-Object { $_.target } | Sort-Object -Unique)
        $bad = @($hooks.Keys | Where-Object { -not (Test-WebhookUrl $hooks[$_]) })
        Write-Log ("PREVIEW: {0} card(s) due; {1} channel(s) in the file, {2} with an address that would be refused; {3} due channel(s) not in the file{4}. Nothing posted. Re-run with -Apply." -f
            $items.Count, $hooks.Count, $bad.Count, $missing.Count, $(if ($missing.Count) { ': ' + ($missing -join ', ') } else { '' }))
        return
    }

    $sent = 0; $failed = 0
    foreach ($item in $items) {
        $url = $null
        if ($hooks.ContainsKey($item.target.ToLower())) { $url = $hooks[$item.target.ToLower()] }
        if (-not (Test-WebhookUrl $url)) {
            [void](Invoke-Spine @('outbox-mark', $Database, '--id', "$($item.id)", '--status', 'FAILED'))
            $failed++
            continue
        }
        try {
            Send-Card $item $url
            [void](Invoke-Spine @('outbox-mark', $Database, '--id', "$($item.id)", '--status', 'SENT'))
            $sent++
        } catch {
            [void](Invoke-Spine @('outbox-mark', $Database, '--id', "$($item.id)", '--status', 'FAILED'))
            $failed++
        }
    }
    Write-Log "$($items.Count) due: $sent posted, $failed failed."
}

# ---------------------------------------------------------------- main
$isConnectionString = $Database -match '(^|;)\s*(Driver|Server|DSN|Data Source)\s*='
foreach ($p in @($SpineDir, $WebhookFile) + $(if ($isConnectionString) { @() } else { @($Database) })) {
    if (-not (Test-Path $p)) { throw "Not found: $p" }
}
if ($DeskUrl -and -not $DeskUrl.ToLower().StartsWith('https://')) { throw 'DeskUrl must be https://' }
if ($DeskAwayUrl -and -not $DeskAwayUrl.ToLower().StartsWith('https://')) { throw 'DeskAwayUrl must be https://' }
if ($Apply -and -not (Test-Path $StateDir)) { New-Item -ItemType Directory -Path $StateDir | Out-Null }
Write-Log ("Teams sender ({0}{1})" -f $(if ($Apply) { 'APPLY' } else { 'PREVIEW' }), $(if ($Loop) { ", every $IntervalSeconds s" } else { '' }))

do {
    try { Invoke-Pass }
    catch { Write-Log ("Pass failed: " + $_.Exception.Message) ; if (-not $Loop) { throw } }
    if ($Loop) { Start-Sleep -Seconds $IntervalSeconds }
} while ($Loop)

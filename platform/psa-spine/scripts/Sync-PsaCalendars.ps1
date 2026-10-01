<#
.SYNOPSIS
    Put the desk's visits and tasks on each member's Outlook calendar, and bring their Outlook busy times back to the desk.

.DESCRIPTION
    Schema 059 (Dada, 1 Oct 2026: "the members should have their accounts calendars synced with the actual
    calendars on outlook or exchange"). Runs on DND-SQL01, one pass a minute, as the desk's task account, with the
    mail app's certificate. Per pass:
      1. asks `psaspine calendar-pending` what changed (a visit booked, moved or cancelled; time off, a meeting or an
         activity added or removed) and writes each to the member's calendar with Microsoft Graph: create, update in
         place, or delete. Each event carries the category "Dada PSA". Reports each back with `calendar-mark`;
      2. for every member who works a board (`calendar-members`), reads their calendar for the next -DaysAhead days
         and hands the busy times back with `calendar-busy`: busy, tentative, out of office or working elsewhere,
         and when. Never a subject, an attendee or a body. Events with the category "Dada PSA" are the desk's own
         and are left out, so nothing echoes.

    What goes onto a calendar: the ticket's reference, its board, the place and a link to the ticket on the desk.
    Never the ticket's summary or a note (section 6.1, as the .ics feed).

    The app needs Exchange RBAC for Applications "Application Calendars.ReadWrite" on a management scope over the
    desk's members (the handoff, Dada's step). Calendars.ReadWrite must NOT be granted in Entra: that would open
    every calendar in the tenant.

    PREVIEW BY DEFAULT. Without -Apply it signs in, counts what is due and how many members it would read, and
    stops: nothing is written to a calendar and the desk is not changed.

    Logs counts only. Never a subject, an address or a time.

.EXAMPLE
    .\Sync-PsaCalendars.ps1 -TenantId <guid> -ClientId <guid> -CertThumbprint <thumb> `
        -Database D:\psa\spine.db -StateDir D:\psa\mail-state -DeskUrl https://desk.pmcne.ph
.EXAMPLE
    .\Sync-PsaCalendars.ps1 ... -Apply
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)] [string] $TenantId,
    [Parameter(Mandatory = $true)] [string] $ClientId,
    [Parameter(Mandatory = $true)] [string] $CertThumbprint,
    [Parameter(Mandatory = $true)] [string] $Database,
    [Parameter(Mandatory = $true)] [string] $StateDir,
    [string] $AllowedDomain = 'pmcne.ph',
    [string] $DeskUrl,
    [string] $SpineDir,
    [string] $PythonExe = 'C:\PMC\Python312\python.exe',
    # The desk keeps local time (UTC+8, no daylight saving). A Windows time zone name, as Graph takes it.
    [string] $TimeZone = 'Singapore Standard Time',
    [int] $DaysAhead = 28,
    [switch] $Apply
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'
# The repository root, one above scripts\. Not a param() default: under Windows
# PowerShell 5.1 run with -File, $PSScriptRoot is empty while the defaults are
# evaluated (MEASURED on DND-SQL01, part 21), so the default is resolved here.
if (-not $SpineDir) { $SpineDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path) }
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$Graph = 'https://graph.microsoft.com/v1.0'
$Category = 'Dada PSA'
$LogFile = Join-Path $StateDir 'calendar-sync.log'
$BusyFile = Join-Path $StateDir 'calendar-busy.json'
$script:Token = $null
$script:TokenExpires = [datetime]::MinValue

function Write-Log([string] $Message) {
    $line = (Get-Date).ToUniversalTime().ToString('yyyy-MM-dd HH:mm:ss') + 'Z  ' + $Message
    Write-Host $line
    if ($Apply) { Add-Content -Path $LogFile -Value $line -Encoding ASCII }
}

function ConvertTo-Base64Url([byte[]] $Bytes) {
    [Convert]::ToBase64String($Bytes).TrimEnd('=').Replace('+', '-').Replace('/', '_')
}

function Get-Certificate {
    foreach ($store in 'Cert:\LocalMachine\My', 'Cert:\CurrentUser\My') {
        $path = Join-Path $store $CertThumbprint
        if (Test-Path $path) { return Get-Item $path }
    }
    throw "No certificate with thumbprint $CertThumbprint in LocalMachine\My or CurrentUser\My."
}

function Get-GraphToken {
    if ($script:Token -and (Get-Date) -lt $script:TokenExpires) { return $script:Token }

    $cert = Get-Certificate
    $rsa = [System.Security.Cryptography.X509Certificates.RSACertificateExtensions]::GetRSAPrivateKey($cert)
    if ($null -eq $rsa) { throw 'The certificate has no RSA private key this account can use.' }

    $sha = [System.Security.Cryptography.SHA256]::Create()
    $x5t = ConvertTo-Base64Url ($sha.ComputeHash($cert.RawData))
    $aud = "https://login.microsoftonline.com/$TenantId/oauth2/v2.0/token"
    # Not Get-Date -UFormat %s: in Windows PowerShell 5.1 that counts from local
    # time, which would skew every claim by the UTC offset.
    $now = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()

    $header = @{ alg = 'PS256'; typ = 'JWT'; 'x5t#S256' = $x5t } | ConvertTo-Json -Compress
    $claims = @{ aud = $aud; iss = $ClientId; sub = $ClientId; jti = [guid]::NewGuid().ToString()
                 nbf = $now; iat = $now; exp = $now + 300 } | ConvertTo-Json -Compress
    $unsigned = (ConvertTo-Base64Url ([Text.Encoding]::UTF8.GetBytes($header))) + '.' +
                (ConvertTo-Base64Url ([Text.Encoding]::UTF8.GetBytes($claims)))
    $sig = $rsa.SignData([Text.Encoding]::ASCII.GetBytes($unsigned),
                         [System.Security.Cryptography.HashAlgorithmName]::SHA256,
                         [System.Security.Cryptography.RSASignaturePadding]::Pss)
    $assertion = $unsigned + '.' + (ConvertTo-Base64Url $sig)

    $body = @{
        client_id             = $ClientId
        scope                 = 'https://graph.microsoft.com/.default'
        grant_type            = 'client_credentials'
        client_assertion_type = 'urn:ietf:params:oauth:client-assertion-type:jwt-bearer'
        client_assertion      = $assertion
    }
    $resp = Invoke-RestMethod -Method Post -Uri $aud -Body $body -ContentType 'application/x-www-form-urlencoded'
    $script:Token = $resp.access_token
    $script:TokenExpires = (Get-Date).AddSeconds([int]$resp.expires_in - 300)
    return $script:Token
}

function Invoke-Spine([string[]] $SpineArgs) {
    Push-Location $SpineDir
    try {
        $out = & $PythonExe -m psaspine @SpineArgs 2>&1
        $code = $LASTEXITCODE
    } finally { Pop-Location }
    return @{ Code = $code; Out = (($out | Out-String).Trim()) }
}

# One Graph call with retries on 429 and 5xx. Returns the parsed answer, $null for 204, and throws with the HTTP
# status in .Data['Status'] for anything else, so a caller can treat 404 as "already gone".
function Invoke-GraphJson([string] $Method, [string] $Uri, $Body, [hashtable] $More) {
    for ($attempt = 1; $attempt -le 3; $attempt++) {
        $headers = @{ Authorization = "Bearer $(Get-GraphToken)" }
        if ($More) { foreach ($k in $More.Keys) { $headers[$k] = $More[$k] } }
        try {
            if ($null -ne $Body) {
                $json = $Body | ConvertTo-Json -Depth 6
                return Invoke-RestMethod -Method $Method -Uri $Uri -Headers $headers -ContentType 'application/json' `
                    -Body ([Text.Encoding]::UTF8.GetBytes($json))
            }
            return Invoke-RestMethod -Method $Method -Uri $Uri -Headers $headers
        } catch {
            $status = 0
            $response = $null
            if ($_.Exception.PSObject.Properties['Response']) { $response = $_.Exception.Response }
            if ($response) { $status = [int]$response.StatusCode }
            if (($status -eq 429 -or $status -ge 500) -and $attempt -lt 3) {
                $wait = 10
                $retry = $response.Headers['Retry-After']
                if ($retry) { $wait = [int]$retry }
                Start-Sleep -Seconds $wait
                continue
            }
            if ($status -eq 401) { $script:Token = $null }
            $_.Exception.Data['Status'] = $status
            throw
        }
    }
}

function Get-Status($ErrorRecord) {
    $d = $ErrorRecord.Exception.Data
    if ($d.Contains('Status')) { return [int]$d['Status'] }
    return 0
}

function ConvertTo-Event($Item) {
    $ev = @{
        subject    = $Item.subject
        body       = @{ contentType = 'Text'; content = $Item.body }
        start      = @{ dateTime = ($Item.start.Replace(' ', 'T') + ':00'); timeZone = $TimeZone }
        end        = @{ dateTime = ($Item.end.Replace(' ', 'T') + ':00'); timeZone = $TimeZone }
        showAs     = $Item.show_as
        categories = @($Category)
    }
    if ($Item.location) { $ev['location'] = @{ displayName = $Item.location } }
    return $ev
}

function Write-One($Item) {
    $mbx = [Uri]::EscapeDataString($Item.mailbox)
    if ($Item.action -eq 'DELETE') {
        try {
            Invoke-GraphJson 'Delete' ("$Graph/users/$mbx/events/" + [Uri]::EscapeDataString($Item.event_id)) $null $null | Out-Null
        } catch {
            if ((Get-Status $_) -ne 404) { throw }      # already gone from their calendar: that is the goal
        }
        return $null
    }
    $ev = ConvertTo-Event $Item
    if ($Item.event_id) {
        try {
            Invoke-GraphJson 'Patch' ("$Graph/users/$mbx/events/" + [Uri]::EscapeDataString($Item.event_id)) $ev $null | Out-Null
            return $Item.event_id
        } catch {
            if ((Get-Status $_) -ne 404) { throw }      # they deleted it in Outlook: write it again
        }
    }
    $made = Invoke-GraphJson 'Post' "$Graph/users/$mbx/events" $ev $null
    return $made.id
}

function Read-Busy($Member, $FromText, $ToText) {
    $mbx = [Uri]::EscapeDataString($Member.mailbox)
    $uri = "$Graph/users/$mbx/calendarView?startDateTime=$FromText&endDateTime=$ToText" +
           '&$select=start,end,showAs,categories,isCancelled&$top=200'
    $more = @{ Prefer = ('outlook.timezone="' + $TimeZone + '"') }
    $out = @()
    while ($uri) {
        $page = Invoke-GraphJson 'Get' $uri $null $more
        foreach ($e in $page.value) {
            if ($e.isCancelled) { continue }
            if (@($e.categories) -contains $Category) { continue }
            if (@('busy', 'tentative', 'oof', 'workingElsewhere') -notcontains [string]$e.showAs) { continue }
            $out += @{ member = $Member.member; start = [string]$e.start.dateTime; end = [string]$e.end.dateTime
                       show_as = [string]$e.showAs }
        }
        $next = $page.PSObject.Properties['@odata.nextLink']
        if ($next) { $uri = $next.Value } else { $uri = $null }
    }
    return ,$out
}

function Invoke-Pass {
    $args1 = @('calendar-pending', $Database, '--allowed-domain', $AllowedDomain)
    if (-not $Apply) { $args1 += '--dry-run' }
    if ($DeskUrl) { $args1 += @('--desk-url', $DeskUrl) }
    $r = Invoke-Spine $args1
    if ($r.Code -ne 0) { throw ('calendar-pending failed (exit ' + $r.Code + ')') }
    $items = @()
    if ($r.Out) { foreach ($x in ($r.Out | ConvertFrom-Json)) { if ($null -ne $x -and $x.PSObject.Properties['id']) { $items += $x } } }

    $m = Invoke-Spine @('calendar-members', $Database, '--allowed-domain', $AllowedDomain)
    if ($m.Code -ne 0) { throw ('calendar-members failed (exit ' + $m.Code + ')') }
    $people = @()
    if ($m.Out) { foreach ($x in ($m.Out | ConvertFrom-Json)) { if ($null -ne $x -and $x.PSObject.Properties['mailbox']) { $people += $x } } }

    if (-not $Apply) {
        Get-GraphToken | Out-Null
        Write-Log ('PREVIEW: signed in; ' + $items.Count + ' calendar write(s) due; ' + $people.Count +
                   ' member calendar(s) to read. Nothing written. Re-run with -Apply.')
        return
    }

    $sent = 0; $failed = 0
    foreach ($item in $items) {
        if (-not $item.mailbox.ToLower().EndsWith('@' + $AllowedDomain.ToLower())) {
            [void](Invoke-Spine @('calendar-mark', $Database, '--id', "$($item.id)", '--status', 'FAILED'))
            $failed++
            continue
        }
        try {
            $eventId = Write-One $item
            $markArgs = @('calendar-mark', $Database, '--id', "$($item.id)", '--status', 'SENT')
            if ($eventId) { $markArgs += @('--event-id', $eventId) }
            [void](Invoke-Spine $markArgs)
            $sent++
        } catch {
            [void](Invoke-Spine @('calendar-mark', $Database, '--id', "$($item.id)", '--status', 'FAILED'))
            $failed++
        }
    }

    $from = (Get-Date).Date
    $to = $from.AddDays($DaysAhead)
    $fromText = $from.ToString('yyyy-MM-ddTHH:mm:ss')
    $toText = $to.ToString('yyyy-MM-ddTHH:mm:ss')
    $busy = @(); $read = @(); $unread = 0
    foreach ($p in $people) {
        try { $busy += Read-Busy $p $fromText $toText; $read += $p.member } catch { $unread++ }
    }
    $payload = @{ members = $read; busy = $busy } | ConvertTo-Json -Depth 4
    [IO.File]::WriteAllText($BusyFile, $payload, (New-Object System.Text.UTF8Encoding $false))
    $b = Invoke-Spine @('calendar-busy', $Database, '--file', $BusyFile, '--from', $from.ToString('yyyy-MM-dd HH:mm'),
                        '--to', $to.ToString('yyyy-MM-dd HH:mm'))
    Remove-Item -Force -Path $BusyFile -ErrorAction SilentlyContinue
    if ($b.Code -ne 0) { throw ('calendar-busy failed (exit ' + $b.Code + ')') }
    Write-Log ($items.Count.ToString() + ' write(s) due: ' + $sent + ' written, ' + $failed + ' failed; busy times read for ' +
               $read.Count + ' of ' + $people.Count + ' member(s)' + $(if ($unread) { ' (' + $unread + ' not readable: is the scope applied?)' } else { '' }) + '.')
}

# ---------------------------------------------------------------- main
$isConnectionString = $Database -match '(^|;)\s*(Driver|Server|DSN|Data Source)\s*='
foreach ($p in @($SpineDir) + $(if ($isConnectionString) { @() } else { @($Database) })) {
    if (-not (Test-Path $p)) { throw ('Not found: ' + $p) }
}
if ($Apply -and -not (Test-Path $StateDir)) { New-Item -ItemType Directory -Path $StateDir | Out-Null }
Write-Log ('Calendar sync (' + $(if ($Apply) { 'APPLY' } else { 'PREVIEW' }) + ', ' + $DaysAhead + ' days ahead)')
try { Invoke-Pass } catch { Write-Log ('Pass failed: ' + $_.Exception.Message); throw }

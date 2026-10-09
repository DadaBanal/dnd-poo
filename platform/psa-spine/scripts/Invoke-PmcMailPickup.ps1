<#
.SYNOPSIS
    Pull new mail from the helpdesk mailbox into Dada PSA, about every 30 seconds.

.DESCRIPTION
    Runs on DND-SQL01. Nothing reaches in: the server polls Microsoft Graph for
    new messages and turns each one into a ticket through `psaspine import-mail`.

    Why polling and not push. Graph change notifications need "a publicly
    accessible, HTTPS-secured endpoint" (VERIFIED 23 Sep 2026,
    https://learn.microsoft.com/graph/change-notifications-delivery-webhooks).
    DND-SQL01 is LAN-only and must stay that way (risk R3). A delta query every
    30 seconds gives the same practical result with no inbound port.

    How it works, per pass:
      1. Get a token with a certificate (client credentials, PS256 assertion,
         x5t#S256 header; VERIFIED, learn.microsoft.com/entra/identity-platform/
         certificate-credentials). The private key never leaves the Windows
         certificate store. There is no secret in this file or on disk.
      2. Ask the Inbox for messages CREATED since the last pass (delta query,
         changeType=created). The first run starts from -Since (default: now),
         so the mailbox's history is not dragged in by accident.
      3. Download each new message as its original MIME ($value) and write it,
         byte for byte, to the drop folder.
      4. Run `psaspine import-mail` on the drop folder -- this pass's files and anything an earlier
         pass fetched but could not place. It is keyed by Message-ID, so a message
         seen twice never makes a second ticket.
      5. Only when the import succeeds: save the new delta link and remove the
         imported .eml files (they may hold patient details; the mailbox itself
         is the retained copy).

    PREVIEW BY DEFAULT. Without -Apply it signs in, counts what is new and stops:
    no file is written, no ticket is made, the delta link is not saved.

    Logs counts only. Never a subject, a sender or a body: those can carry
    patient details (section 6.1).

.PARAMETER Mailbox
    The shared mailbox to read, e.g. helpdesk@pmcne.ph. The app must be scoped
    to this mailbox with Exchange RBAC for Applications; see the handoff.

.PARAMETER BoardId
    The board a message lands on when no board claims any of its recipient
    addresses (passed to import-mail as --board-id). Without it, the unrouted
    queue. A board that claims the address on its page wins either way.

    Two mailboxes, two pickups (the 1 Oct cut-over: helpdesk@ and support@):
    run the script once per -Mailbox. Each keeps its own delta link, log and
    drop subfolder (named from the mailbox), so the two never share state,
    and both may give the same -StateDir and -DropDir.

.EXAMPLE
    # Preview: signs in and counts, changes nothing.
    .\Invoke-PmcMailPickup.ps1 -TenantId <guid> -ClientId <guid> `
        -CertThumbprint <thumb> -Mailbox helpdesk@pmcne.ph `
        -Database D:\psa\spine.db -DropDir D:\psa\mail-drop -StateDir D:\psa\mail-state

.EXAMPLE
    # Run continuously (the scheduled task does this).
    .\Invoke-PmcMailPickup.ps1 ... -Apply -Loop -IntervalSeconds 30
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)] [string] $TenantId,
    [Parameter(Mandatory = $true)] [string] $ClientId,
    [Parameter(Mandatory = $true)] [string] $CertThumbprint,
    [Parameter(Mandatory = $true)] [string] $Mailbox,
    [Parameter(Mandatory = $true)] [string] $Database,
    [Parameter(Mandatory = $true)] [string] $DropDir,
    [Parameter(Mandatory = $true)] [string] $StateDir,
    [string] $SpineDir,
    [string] $AttachmentDir = 'D:\psa\files',
    [string] $PythonExe = 'C:\PMC\Python312\python.exe',
    [string] $Channel = 'helpdesk',
    [string] $BoardId,
    [datetime] $Since = (Get-Date),
    [int] $IntervalSeconds = 30,
    [switch] $Loop,
    [switch] $KeepFiles,
    [switch] $Apply
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'
# The files a mail brings go where the desk keeps every file. The task's own setting, not a
# machine variable it has to inherit (SQL01, part 28: the pickup had none and every mail with an
# attachment failed its pass).
if ($AttachmentDir) { $env:PSA_ATTACHMENT_DIR = $AttachmentDir }
# The repository root, one above scripts\. Not a param() default: under Windows
# PowerShell 5.1 run with -File, $PSScriptRoot is empty while the defaults are
# evaluated (MEASURED on DND-SQL01, part 21), so the default is resolved here.
if (-not $SpineDir) { $SpineDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path) }
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$Graph = 'https://graph.microsoft.com/v1.0'
# One mailbox's state, apart from any other pickup's: a second pickup with the
# same -StateDir must never read or advance this one's delta link, and its
# import must never pick up this one's half-written files.
$Slug = ($Mailbox.ToLowerInvariant() -replace '[^a-z0-9]+', '-').Trim('-')
$DeltaFile = Join-Path $StateDir "inbox-deltalink-$Slug.txt"
$LogFile = Join-Path $StateDir "mail-pickup-$Slug.log"
$DropDir = Join-Path $DropDir $Slug
$script:Token = $null
$script:TokenExpires = [datetime]::MinValue

function Write-Log([string] $Message) {
    $line = '{0:yyyy-MM-dd HH:mm:ss}Z  {1}' -f (Get-Date).ToUniversalTime(), $Message
    Write-Host $line
    if ($Apply) { Add-Content -Path $LogFile -Value $line -Encoding ASCII }
}

# ---------------------------------------------------------------- the delta link, kept safely
# 9 Oct 2026: the unclean shutdown at 13:10 (event 6008) caught all three
# pickups saving their delta links, and each file was left as ~400 NUL bytes.
# Every pass after that failed 'Invalid URI' until somebody noticed (MEASURED by
# SQL01). So a link is now written to a temporary file, forced to disk, and
# swapped in with the previous one kept as .prev; and a link that cannot be read
# is set aside and recovered from, never failed on.
function Test-DeltaLink([string] $Text) {
    if (-not $Text) { return $false }
    if ($Text.IndexOf([char]0) -ge 0) { return $false }
    return ($Text.Trim() -match '^https://graph\.microsoft\.com/\S+$')
}

function Save-DeltaLink([string] $Link) {
    $tmp = "$DeltaFile.tmp"
    $bytes = [Text.Encoding]::ASCII.GetBytes($Link)
    $fs = New-Object IO.FileStream($tmp, [IO.FileMode]::Create, [IO.FileAccess]::Write, [IO.FileShare]::None, 4096,
                                   [IO.FileOptions]::WriteThrough)
    try { $fs.Write($bytes, 0, $bytes.Length); $fs.Flush($true) } finally { $fs.Dispose() }
    if (Test-Path $DeltaFile) { [IO.File]::Replace($tmp, $DeltaFile, "$DeltaFile.prev") }
    else { [IO.File]::Move($tmp, $DeltaFile) }
}

function Get-RecoverFrom([datetime] $LastSaved) {
    # Where to read from when the place is lost: two hours before the link was
    # last saved (that save was the last good pass), never later than -Since and
    # never more than 14 days back. The import is keyed by Message-ID, so the
    # overlap imports nothing twice.
    $from = $LastSaved.AddHours(-2)
    if ($from -gt $Since) { $from = $Since }
    $floor = (Get-Date).AddDays(-14)
    if ($from -lt $floor) { $from = $floor }
    return $from
}

function Read-DeltaLink {
    # @{ Uri; From }: Uri is the link to carry on from, or $null with From the
    # window to read instead ($null From and Uri together mean a first run).
    $lastSaved = $null
    foreach ($f in @($DeltaFile, "$DeltaFile.prev")) {
        if (-not (Test-Path $f)) { continue }
        $item = Get-Item $f
        if (-not $lastSaved -or $item.LastWriteTime -gt $lastSaved) { $lastSaved = $item.LastWriteTime }
        $text = [IO.File]::ReadAllText($f)
        if (Test-DeltaLink $text) {
            if ($f -ne $DeltaFile) {
                Write-Log 'The saved delta link was unreadable; carrying on from the one before it (.prev). Nothing already imported is imported twice.'
            }
            return @{ Uri = $text.Trim(); From = $null }
        }
        $bad = $f + '.bad-' + (Get-Date -Format 'yyyyMMdd-HHmmss')
        Write-Log ("The delta link in $(Split-Path -Leaf $f) is unreadable ($($item.Length) bytes, not a Graph link):" +
                   ' most likely a shutdown while it was being written.' + $(if ($Apply) { " Set aside as $(Split-Path -Leaf $bad)." } else { ' (preview: left in place)' }))
        if ($Apply) { Move-Item -Path $f -Destination $bad -Force }
    }
    if ($lastSaved) { return @{ Uri = $null; From = (Get-RecoverFrom $lastSaved) } }
    return @{ Uri = $null; From = $null }
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

function Invoke-Graph([string] $Uri, [string] $OutFile) {
    for ($attempt = 1; $attempt -le 3; $attempt++) {
        $headers = @{ Authorization = "Bearer $(Get-GraphToken)"; Prefer = 'odata.maxpagesize=50' }
        try {
            if ($OutFile) {
                # -OutFile writes the response bytes unchanged: the MIME is kept exact,
                # which matters because a message with no Message-ID is identified
                # by the sha256 of its raw bytes.
                Invoke-WebRequest -Uri $Uri -Headers $headers -OutFile $OutFile -UseBasicParsing | Out-Null
                return $null
            }
            return Invoke-RestMethod -Uri $Uri -Headers $headers
        } catch {
            $status = 0
            $response = $null
            # StrictMode: not every exception type has .Response, so ask first.
            if ($_.Exception.PSObject.Properties['Response']) { $response = $_.Exception.Response }
            if ($response) { $status = [int]$response.StatusCode }
            if (($status -eq 429 -or $status -ge 500) -and $attempt -lt 3) {
                $wait = 10
                $retry = $response.Headers['Retry-After']
                if ($retry) { $wait = [int]$retry }
                Write-Log "Graph returned $status; waiting $wait s (attempt $attempt of 3)."
                Start-Sleep -Seconds $wait
                continue
            }
            if ($status -eq 401) { $script:Token = $null }
            throw
        }
    }
}

function Get-FileNameFor([string] $GraphId) {
    # Named by a hash of the Graph id: never the subject, which can carry PHI.
    $sha = [System.Security.Cryptography.SHA256]::Create()
    $hex = ($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($GraphId)) | ForEach-Object { $_.ToString('x2') }) -join ''
    return "$hex.eml"
}

function Invoke-Pass {
    $mbx = [Uri]::EscapeDataString($Mailbox)
    $saved = Read-DeltaLink
    $windowFrom = $Since
    if ($saved.Uri) {
        $uri = $saved.Uri
        $first = $false
    } else {
        if ($saved.From) {
            $windowFrom = $saved.From
            Write-Log ("Recovering: reading from $($windowFrom.ToString('yyyy-MM-dd HH:mm')) (two hours before the last" +
                       ' good save) instead of failing. Mail already imported is skipped by Message-ID.')
        }
        # Not $since: PowerShell names ignore case, so that would overwrite the
        # [datetime] $Since parameter with a string (MEASURED by SQL01, part 27).
        $sinceUtc = $windowFrom.ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
        $uri = "$Graph/users/$mbx/mailFolders/inbox/messages/delta?changeType=created" +
               "&`$select=id,receivedDateTime&`$filter=receivedDateTime+ge+$sinceUtc"
        $first = $true
    }

    $newIds = New-Object System.Collections.Generic.List[string]
    $deltaLink = $null
    while ($uri) {
        # A saved delta link expires, and Graph then answers 410 Gone with
        # error code syncStateNotFound: without this the pass threw on every
        # run from then on and no mail was ever picked up again (Dada, 2 Oct
        # 2026: "the emails aren't syncing in again"). Forget the link and
        # start a fresh window from -Since; nothing already imported is
        # imported twice, because the import is keyed by Message-ID.
        try {
            $page = Invoke-Graph $uri
        } catch {
            $st = 0
            if ($_.Exception.PSObject.Properties['Response'] -and $_.Exception.Response) { $st = [int]$_.Exception.Response.StatusCode }
            if ($st -ne 410 -or $first) { throw }
            # 9 Oct 2026: read from the last good save, not from -Since. The
            # task's -Since is "now", which skipped whatever arrived while the
            # link was going stale.
            $windowFrom = $Since
            if (Test-Path $DeltaFile) { $windowFrom = Get-RecoverFrom (Get-Item $DeltaFile).LastWriteTime }
            Write-Log ("Graph says the saved delta link has expired (410). Forgetting it and reading from " +
                       "$($windowFrom.ToString('yyyy-MM-dd HH:mm')) instead.")
            foreach ($f in @($DeltaFile, "$DeltaFile.prev")) { if (Test-Path $f) { Remove-Item -Path $f -Force } }
            $sinceUtc = $windowFrom.ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
            $uri = "$Graph/users/$mbx/mailFolders/inbox/messages/delta?changeType=created" +
                   "&`$select=id,receivedDateTime&`$filter=receivedDateTime+ge+$sinceUtc"
            $first = $true
            $newIds.Clear()
            $deltaLink = $null
            continue
        }
        foreach ($m in $page.value) {
            $removed = $m.PSObject.Properties['@removed']
            if (-not $removed) { $newIds.Add($m.id) }
        }
        $next = $page.PSObject.Properties['@odata.nextLink']
        $delta = $page.PSObject.Properties['@odata.deltaLink']
        if ($next) { $uri = $next.Value } else { $uri = $null }
        if ($delta) { $deltaLink = $delta.Value }
    }

    $label = if ($first) { "first sync from $($windowFrom.ToString('yyyy-MM-dd HH:mm'))" } else { 'since last pass' }
    if (-not $Apply) {
        Write-Log "PREVIEW: $($newIds.Count) new message(s) $label. Nothing written; delta link not saved. Re-run with -Apply."
        return
    }

    $written = @()
    foreach ($id in $newIds) {
        $file = Join-Path $DropDir (Get-FileNameFor $id)
        $tmp = "$file.part"
        Invoke-Graph "$Graph/users/$mbx/messages/$([Uri]::EscapeDataString($id))/`$value" $tmp
        Move-Item -Force -Path $tmp -Destination $file
        $written += $file
    }

    # A pass that fetched nothing still imports what is waiting. Until 2 Oct 2026
    # the import ran only when this pass had written a file, and the drop folder
    # is imported whole, so a pass whose import was refused left its files there
    # and no later pass ever looked at them again: the next pass found 0 new,
    # skipped the import, and the window sat on disk. SQL01 (part 31) found the
    # road into that: the pass imports as whoever launched it, and a SQL
    # sysadmin resolves to [dbo], which the desk refuses -- so a repair run by
    # hand fetches the window and then cannot place it. Now the minute task,
    # which runs as the desk's own account, picks those files up by itself. The
    # import is keyed by Message-ID, so nothing arrives twice.
    $waiting = @()
    if (Test-Path $DropDir) {
        $waiting = @(Get-ChildItem -Path $DropDir -Filter *.eml -File -ErrorAction SilentlyContinue |
                     Where-Object { $written -notcontains $_.FullName })
    }
    if ($written.Count -eq 0 -and $waiting.Count -gt 0) {
        Write-Log ("$($waiting.Count) message(s) from an earlier pass are waiting in the drop folder; importing them.")
    }
    if ($written.Count -gt 0 -or $waiting.Count -gt 0) {
        $runId = "mail-$Slug-" + (Get-Date).ToUniversalTime().ToString('yyyyMMddHHmmss')
        Push-Location $SpineDir
        try {
            $importArgs = @('-m', 'psaspine', 'import-mail', $Database, $DropDir, '--run-id', $runId,
                            '--channel', $Channel, '--own-address', $Mailbox)
            if ($BoardId) { $importArgs += @('--board-id', $BoardId) }
            # Python's stderr (a warning) is not a terminating error: under 'Stop' with 2>&1 it
            # was, and one warning failed every pass (MEASURED by SQL01, part 28). The exit code decides.
            $eap = $ErrorActionPreference; $ErrorActionPreference = 'Continue'
            $out = & $PythonExe @importArgs 2>&1
            $code = $LASTEXITCODE
            $ErrorActionPreference = $eap
        } finally { Pop-Location }
        # import-mail prints counts only ("n files: x new, y appended ...").
        Write-Log ("import-mail exit $code : " + (($out | Out-String).Trim() -replace '\s+', ' '))
        if ($code -ne 0) {
            Write-Log 'Import FAILED: files kept, delta link NOT advanced; the next pass retries (import is idempotent).'
            return
        }
        # A message the importer could not place is recorded on the desk with
        # its error (INTAKE_ERROR) and this pass's files are kept in failed\
        # for a look; the delta link still advances, so the next message is
        # never held behind it.
        $failed = 0
        if ((($out | Out-String) -match '(\d+) could not be placed')) { $failed = [int]$Matches[1] }
        if ($failed -gt 0) {
            $failedDir = Join-Path $DropDir 'failed'
            if (-not (Test-Path $failedDir)) { New-Item -ItemType Directory -Path $failedDir | Out-Null }
            @($written) + @($waiting | ForEach-Object { $_.FullName }) |
                ForEach-Object { Move-Item -Force -Path $_ -Destination $failedDir -ErrorAction SilentlyContinue }
            Write-Log ('{0} message(s) could not be placed: recorded as UNCLASSIFIED with INTAKE_ERROR (Setup > Email connector); the files of this pass are kept in {1}' -f $failed, $failedDir)
        } elseif (-not $KeepFiles) {
            # Both this pass's files and any that were waiting: they are on the
            # desk now, and leaving them would import them again every minute.
            @($written) + @($waiting | ForEach-Object { $_.FullName }) |
                ForEach-Object { Remove-Item -Force -Path $_ -ErrorAction SilentlyContinue }
        }
    }

    if ($deltaLink) { Save-DeltaLink $deltaLink }
    Write-Log "$($newIds.Count) new message(s) $label; imported and delta link saved."
}

# ---------------------------------------------------------------- main
# $Database is a SQLite file or, since D7, an ODBC connection string (Driver=...;
# Server=...); Test-Path knows only the first. The desk itself refuses a bad string.
$isConnectionString = $Database -match '(^|;)\s*(Driver|Server|DSN|Data Source)\s*='
foreach ($p in @($SpineDir) + $(if ($isConnectionString) { @() } else { @($Database) })) {
    if (-not (Test-Path $p)) { throw "Not found: $p" }
}
if ($Apply) {
    foreach ($d in $DropDir, $StateDir) {
        if (-not (Test-Path $d)) { New-Item -ItemType Directory -Path $d | Out-Null }
    }
}
# Every value goes in as a -f argument, never into the format string: an ODBC
# connection string's {ODBC Driver 17 for SQL Server} is a -f placeholder and
# throws before sign-in (MEASURED by SQL01, part 27). Nor is the connection
# string logged: the log says which kind of database, not where it is.
Write-Log ('Mail pickup for {0} -> {1}, board {2} ({3}{4})' -f $Mailbox,
    $(if ($isConnectionString) { 'the SQL Server desk' } else { 'a SQLite file' }),
    $(if ($BoardId) { $BoardId } else { 'by address, else unrouted' }),
    $(if ($Apply) { 'APPLY' } else { 'PREVIEW' }), $(if ($Loop) { ", every $IntervalSeconds s" } else { '' }))

do {
    try { Invoke-Pass }
    catch { Write-Log ("Pass failed: " + $_.Exception.Message) ; if (-not $Loop) { throw } }
    if ($Loop) { Start-Sleep -Seconds $IntervalSeconds }
} while ($Loop)

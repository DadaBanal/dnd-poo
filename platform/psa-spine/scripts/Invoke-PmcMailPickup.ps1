<#
.SYNOPSIS
    Pull new mail from the helpdesk mailbox into the PSA desk, about every 30 seconds.

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
      4. Run `psaspine import-mail`. It is keyed by Message-ID, so a message
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
    [string] $SpineDir = (Join-Path $PSScriptRoot '..'),
    [string] $PythonExe = 'C:\PMC\Python312\python.exe',
    [string] $Channel = 'helpdesk',
    [datetime] $Since = (Get-Date),
    [int] $IntervalSeconds = 30,
    [switch] $Loop,
    [switch] $KeepFiles,
    [switch] $Apply
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$Graph = 'https://graph.microsoft.com/v1.0'
$DeltaFile = Join-Path $StateDir 'inbox-deltalink.txt'
$LogFile = Join-Path $StateDir 'mail-pickup.log'
$script:Token = $null
$script:TokenExpires = [datetime]::MinValue

function Write-Log([string] $Message) {
    $line = '{0:yyyy-MM-dd HH:mm:ss}Z  {1}' -f (Get-Date).ToUniversalTime(), $Message
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
    if (Test-Path $DeltaFile) {
        $uri = (Get-Content -Path $DeltaFile -Raw).Trim()
        $first = $false
    } else {
        $since = $Since.ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
        $uri = "$Graph/users/$mbx/mailFolders/inbox/messages/delta?changeType=created" +
               "&`$select=id,receivedDateTime&`$filter=receivedDateTime+ge+$since"
        $first = $true
    }

    $newIds = New-Object System.Collections.Generic.List[string]
    $deltaLink = $null
    while ($uri) {
        $page = Invoke-Graph $uri
        foreach ($m in $page.value) {
            $removed = $m.PSObject.Properties['@removed']
            if (-not $removed) { $newIds.Add($m.id) }
        }
        $next = $page.PSObject.Properties['@odata.nextLink']
        $delta = $page.PSObject.Properties['@odata.deltaLink']
        if ($next) { $uri = $next.Value } else { $uri = $null }
        if ($delta) { $deltaLink = $delta.Value }
    }

    $label = if ($first) { "first sync from $($Since.ToString('yyyy-MM-dd HH:mm'))" } else { 'since last pass' }
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

    if ($written.Count -gt 0) {
        $runId = 'mail-' + (Get-Date).ToUniversalTime().ToString('yyyyMMddHHmmss')
        Push-Location $SpineDir
        try {
            $out = & $PythonExe -m psaspine import-mail $Database $DropDir --run-id $runId --channel $Channel --own-address $Mailbox 2>&1
            $code = $LASTEXITCODE
        } finally { Pop-Location }
        # import-mail prints counts only ("n files: x new, y appended ...").
        Write-Log ("import-mail exit $code : " + (($out | Out-String).Trim() -replace '\s+', ' '))
        if ($code -ne 0) {
            Write-Log 'Import FAILED: files kept, delta link NOT advanced; the next pass retries (import is idempotent).'
            return
        }
        if (-not $KeepFiles) { $written | ForEach-Object { Remove-Item -Force -Path $_ } }
    }

    if ($deltaLink) { Set-Content -Path $DeltaFile -Value $deltaLink -Encoding ASCII }
    Write-Log "$($newIds.Count) new message(s) $label; imported and delta link saved."
}

# ---------------------------------------------------------------- main
foreach ($p in $Database, $SpineDir) {
    if (-not (Test-Path $p)) { throw "Not found: $p" }
}
if ($Apply) {
    foreach ($d in $DropDir, $StateDir) {
        if (-not (Test-Path $d)) { New-Item -ItemType Directory -Path $d | Out-Null }
    }
}
Write-Log ("Mail pickup for $Mailbox -> $Database ({0}{1})" -f
    $(if ($Apply) { 'APPLY' } else { 'PREVIEW' }), $(if ($Loop) { ", every $IntervalSeconds s" } else { '' }))

do {
    try { Invoke-Pass }
    catch { Write-Log ("Pass failed: " + $_.Exception.Message) ; if (-not $Loop) { throw } }
    if ($Loop) { Start-Sleep -Seconds $IntervalSeconds }
} while ($Loop)

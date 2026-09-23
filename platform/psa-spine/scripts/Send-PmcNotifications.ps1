<#
.SYNOPSIS
    Send the desk's pending notifications (workflow rules: notify, escalate) from the helpdesk mailbox.

.DESCRIPTION
    Runs on DND-SQL01, beside the mail pickup, in the other direction. The desk
    holds no mail credential: it queues notifications in its outbox, and this
    script, once a minute:
      1. asks `psaspine outbox-pending` for what is due (only addresses in
         -AllowedDomain are ever released; anything else is marked NO_SENDER
         by the desk, never guessed);
      2. sends each one with Microsoft Graph sendMail from -Mailbox, signing in
         with the same kind of certificate as the pickup (PS256, x5t#S256); no
         secret in this file or on disk;
      3. reports each result back with `psaspine outbox-mark` (SENT or FAILED).

    The app is scoped to the one mailbox with Exchange RBAC for Applications,
    role "Application Mail.Send" (VERIFIED 23 Sep 2026,
    learn.microsoft.com/exchange/permissions-exo/application-rbac). Mail.Send must
    NOT also be granted in Entra: that would let it send as every mailbox.

    PREVIEW BY DEFAULT. Without -Apply it signs in, counts what is due and
    stops: nothing is sent and the desk is not changed.

    Logs counts only. Never a subject, an address or a body.

.EXAMPLE
    .\Send-PmcNotifications.ps1 -TenantId <guid> -ClientId <guid> -CertThumbprint <thumb> `
        -Mailbox helpdesk@pmcne.ph -Database D:\psa\spine.db -StateDir D:\psa\mail-state
.EXAMPLE
    .\Send-PmcNotifications.ps1 ... -Apply -Loop -IntervalSeconds 60
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)] [string] $TenantId,
    [Parameter(Mandatory = $true)] [string] $ClientId,
    [Parameter(Mandatory = $true)] [string] $CertThumbprint,
    [Parameter(Mandatory = $true)] [string] $Mailbox,
    [Parameter(Mandatory = $true)] [string] $Database,
    [Parameter(Mandatory = $true)] [string] $StateDir,
    [string] $AllowedDomain = 'pmcne.ph',
    [string] $SpineDir = (Join-Path $PSScriptRoot '..'),
    [string] $PythonExe = 'C:\PMC\Python312\python.exe',
    [int] $IntervalSeconds = 60,
    [switch] $Loop,
    [switch] $Apply
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$Graph = 'https://graph.microsoft.com/v1.0'
$LogFile = Join-Path $StateDir 'notify-send.log'
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

function Invoke-Spine([string[]] $SpineArgs) {
    Push-Location $SpineDir
    try {
        $out = & $PythonExe -m psaspine @SpineArgs 2>&1
        $code = $LASTEXITCODE
    } finally { Pop-Location }
    return @{ Code = $code; Out = (($out | Out-String).Trim()) }
}

function Send-One($Item) {
    $headers = @{ Authorization = "Bearer $(Get-GraphToken)" }
    $message = @{
        message = @{
            subject      = $Item.subject
            body         = @{ contentType = 'Text'; content = $Item.body }
            toRecipients = @(@{ emailAddress = @{ address = $Item.to } })
        }
        saveToSentItems = $true
    } | ConvertTo-Json -Depth 6
    $mbx = [Uri]::EscapeDataString($Mailbox)
    Invoke-RestMethod -Method Post -Uri "$Graph/users/$mbx/sendMail" -Headers $headers `
        -ContentType 'application/json' -Body ([Text.Encoding]::UTF8.GetBytes($message)) | Out-Null
}

function Invoke-Pass {
    $args1 = @('outbox-pending', $Database, '--allowed-domain', $AllowedDomain)
    if (-not $Apply) { $args1 += '--dry-run' }
    $r = Invoke-Spine $args1
    if ($r.Code -ne 0) { throw "outbox-pending failed (exit $($r.Code))" }
    $items = @()
    if ($r.Out) { $items = @($r.Out | ConvertFrom-Json) }

    if (-not $Apply) {
        # Signing in proves the certificate and the scope before anything is sent.
        Get-GraphToken | Out-Null
        Write-Log "PREVIEW: signed in; $($items.Count) notification(s) due. Nothing sent. Re-run with -Apply."
        return
    }

    $sent = 0; $failed = 0
    foreach ($item in $items) {
        # The desk released only -AllowedDomain; check again here, because a
        # browser is not a control and neither is one process trusting another.
        if (-not $item.to.ToLower().EndsWith('@' + $AllowedDomain.ToLower())) {
            [void](Invoke-Spine @('outbox-mark', $Database, '--id', "$($item.id)", '--status', 'FAILED'))
            $failed++
            continue
        }
        try {
            Send-One $item
            [void](Invoke-Spine @('outbox-mark', $Database, '--id', "$($item.id)", '--status', 'SENT'))
            $sent++
        } catch {
            [void](Invoke-Spine @('outbox-mark', $Database, '--id', "$($item.id)", '--status', 'FAILED'))
            $failed++
        }
    }
    Write-Log "$($items.Count) due: $sent sent, $failed failed."
}

# ---------------------------------------------------------------- main
foreach ($p in $Database, $SpineDir) {
    if (-not (Test-Path $p)) { throw "Not found: $p" }
}
if ($Apply -and -not (Test-Path $StateDir)) { New-Item -ItemType Directory -Path $StateDir | Out-Null }
Write-Log ("Notification sender for $Mailbox ({0}{1})" -f
    $(if ($Apply) { 'APPLY' } else { 'PREVIEW' }), $(if ($Loop) { ", every $IntervalSeconds s" } else { '' }))

do {
    try { Invoke-Pass }
    catch { Write-Log ("Pass failed: " + $_.Exception.Message) ; if (-not $Loop) { throw } }
    if ($Loop) { Start-Sleep -Seconds $IntervalSeconds }
} while ($Loop)

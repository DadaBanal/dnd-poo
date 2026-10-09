<#
.SYNOPSIS
    Dada's two hand-steps from runbook Parts 71 and 75, in one run (Dada, 10 Oct 2026: "give me one script ill run it").

.DESCRIPTION
    1. Away links: runs Set-PsaDeskAwayLinks.ps1 -Apply beside this file. It shows the before/after, asks once for
       the psa_desk password at the Windows prompt, backs both tasks up, changes them and reads them back.
    2. Old Cloudflare certificate: deletes the pmcne.ph origin certificate in Dada's profile
       (C:\Users\dada.banal\.cloudflared\cert.pem). It is still a live credential that can create tunnels and DNS
       records in pmcne.ph, and nothing running uses it: the pmc-psa-net service reads only its own credentials
       file in C:\ProgramData\cloudflared.
       Refuses, and deletes nothing, if any of these hold:
         - the file's account is the same as the Tech Sponge certificate's (cloudflared-zone2) - wrong file;
         - the account cannot be read from either certificate;
         - the running tunnel's config names that file.
       Prints the account comparison as same/different only, never the token or any id.

    Each step reports on its own; a failure in step 1 does not stop step 2.
    Run elevated:  powershell -ExecutionPolicy Bypass -File .\Invoke-DadaAwayLinksAndCert.ps1
#>
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Run this elevated (Run as administrator). Nothing changed.'
}

# ---------------------------------------------------------------- 1. away links
''
'=== 1. Away-from-PMC links on PSA-Notify and PSA-Teams'
$step1 = 'FAILED'
try {
    & (Join-Path $PSScriptRoot 'Set-PsaDeskAwayLinks.ps1') -Apply
    $step1 = 'done'
} catch {
    "  Step 1 stopped: $($_.Exception.Message)"
    '  The tasks are as they were unless a DONE line above says otherwise.'
}

# ---------------------------------------------------------------- 2. pmcne.ph certificate
''
'=== 2. Delete the old pmcne.ph Cloudflare certificate'
$step2 = 'FAILED'
$Old    = 'C:\Users\dada.banal\.cloudflared\cert.pem'
$Keep   = 'C:\Users\dada.banal\cloudflared-zone2\.cloudflared\cert.pem'
$Config = 'C:\ProgramData\cloudflared\config.yml'

function Get-CertAccount([string] $path) {
    # cert.pem carries a base64 JSON block {zoneID, accountID, apiToken}; read the account only, never print it.
    $text = Get-Content -LiteralPath $path -Raw
    $m = [regex]::Match($text, '-----BEGIN ARGO TUNNEL TOKEN-----\s*(?<b>[A-Za-z0-9+/=\s]+?)\s*-----END ARGO TUNNEL TOKEN-----')
    if (-not $m.Success) { return $null }
    try {
        $json = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String(($m.Groups['b'].Value -replace '\s', '')))
        return ($json | ConvertFrom-Json).accountID
    } catch { return $null }
}

try {
    if (-not (Test-Path -LiteralPath $Old)) {
        '  Already gone - nothing to delete.'
        $step2 = 'already gone'
    } else {
        $oldAcct  = Get-CertAccount $Old
        $keepAcct = if (Test-Path -LiteralPath $Keep) { Get-CertAccount $Keep } else { $null }
        $inConfig = (Get-Content -LiteralPath $Config -Raw) -match [regex]::Escape('.cloudflared\cert.pem')
        if (-not $oldAcct -or -not $keepAcct) {
            '  REFUSED: could not read the account from one of the two certificates. Nothing deleted.'
        } elseif ($oldAcct -eq $keepAcct) {
            '  REFUSED: this file belongs to the same account as the Tech Sponge certificate. Nothing deleted.'
        } elseif ($inConfig) {
            '  REFUSED: the tunnel config names this file. Nothing deleted.'
        } else {
            '  Checked: a different account from the Tech Sponge certificate; the tunnel config does not use it.'
            Remove-Item -LiteralPath $Old -Force
            if (Test-Path -LiteralPath $Old) { '  Delete did not take - the file is still there.' }
            else { '  Deleted.'; $step2 = 'done' }
        }
    }
    $svc = Get-Service -Name Cloudflared -ErrorAction SilentlyContinue
    '  cloudflared service: ' + $(if ($svc) { $svc.Status } else { 'not found' })
} catch {
    "  Step 2 stopped: $($_.Exception.Message)"
}

''
"Summary: away links $step1 | old certificate $step2"
'Tell the SQL01 session it has run; it checks the next PSA-Notify and PSA-Teams passes.'

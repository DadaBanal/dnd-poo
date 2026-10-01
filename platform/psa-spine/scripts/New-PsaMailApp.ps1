<#
.SYNOPSIS
    The mail cut-over's two tenant steps: register the app in Entra with the certificate, and scope it in Exchange
    Online to helpdesk@ and support@ only.

.DESCRIPTION
    HANDOFF-cloud-sql01-WS36-20260923-mail.md steps 2 and 3, and -rules.md step 2, as one script.
    Dada, 1 Oct 2026: "do this for me via scrfipt or do cli hjere". Run it elevated, as yourself, on DND-SQL01.
    It signs you in twice, in a browser window: once to Microsoft Graph (Entra) and once to Exchange Online. You need
    an Entra role that can register an application, and membership of Exchange's Organization Management.

    With -Apply it:
      1. registers the application "PMC PSA mail pickup" (single tenant, no redirect URI, NO API permission) and
         uploads D:\psa\PMC-PSA-MailPickup.cer, made on this host on 1 Oct;
      2. creates its service principal, which is what Exchange and the sign-in both use;
      3. tells Exchange about that service principal, makes a management scope over the two mailboxes, and assigns
         Application Mail.Read and Application Mail.Send on that scope;
      4. tests it: InScope True for helpdesk@ and support@, False for a third mailbox.
    The application id and object id are written to D:\psa\mail-app.txt (D:\psa's ACL: SYSTEM, Administrators and the
    desk's task account), which the pickup task reads. They are identifiers, not secrets, but they stay off the screen
    and out of the repository all the same.

    What it deliberately does NOT do:
      - add any Entra API permission. An Entra Mail.Read grant opens EVERY mailbox in the tenant; the two grants add
        together (the mail handoff, "One mailbox");
      - create or upload any secret. The certificate's private key never leaves this host's certificate store;
      - touch a mailbox, a message, or the PCSD service desk;
      - start the pickup. That is SQL01's step after this one.

    PREVIEW BY DEFAULT. Without -Apply it signs in, reads what exists, prints what it would create, and changes nothing.
    -Undo -Apply removes the role assignments, the scope, the Exchange service principal and the application.

.EXAMPLE
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File D:\psa\bin\New-PsaMailApp.ps1
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File D:\psa\bin\New-PsaMailApp.ps1 -Apply
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File D:\psa\bin\New-PsaMailApp.ps1 -Undo -Apply
#>
[CmdletBinding()]
param(
    [switch]$Apply,
    [switch]$Undo,
    [string]$AppName = 'PMC PSA mail pickup',
    [string]$CerFile = 'D:\psa\PMC-PSA-MailPickup.cer',
    [string[]]$Mailboxes = @('helpdesk@pmcne.ph', 'support@pmcne.ph'),
    [string]$ScopeName = 'PSA desk mailboxes',
    [string]$OutFile = 'D:\psa\mail-app.txt',
    [string]$LogFile = 'D:\psa\logs\New-PsaMailApp.log'
)
$ErrorActionPreference = 'Stop'

function Write-Step([string]$Text) {
    $line = (Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + '  ' + $Text
    Write-Host $line
    Add-Content -Path $LogFile -Value $line -Encoding UTF8
}

$me = [Security.Principal.WindowsIdentity]::GetCurrent()
if (-not ([Security.Principal.WindowsPrincipal]$me).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Run this from an elevated PowerShell (Run as administrator). Nothing was done.'
}
Write-Step ('start as ' + $me.Name + $(if ($Undo) { ' (-Undo)' } else { '' }) + $(if ($Apply) { ' (-Apply)' } else { ' (preview: nothing is changed)' }))

foreach ($m in 'Microsoft.Graph.Authentication', 'Microsoft.Graph.Applications', 'ExchangeOnlineManagement') {
    if (-not (Get-Module -ListAvailable -Name $m)) { throw "The PowerShell module $m is not on this host. Nothing was done." }
    Import-Module $m -ErrorAction Stop
}
if (-not (Test-Path $CerFile)) { throw "$CerFile is missing. Nothing was done." }
$cer = New-Object Security.Cryptography.X509Certificates.X509Certificate2 $CerFile
Write-Step ('certificate to upload: ' + $cer.Subject + ', expires ' + $cer.NotAfter.ToString('yyyy-MM-dd'))

# ---------------------------------------------------------------- Entra
Write-Step 'signing in to Microsoft Graph (a browser window opens) ...'
Connect-MgGraph -Scopes 'Application.ReadWrite.All' -NoWelcome
$ctx = Get-MgContext
Write-Step ('signed in to Graph as ' + $ctx.Account + ', tenant ' + $ctx.TenantId.Substring(0, 8) + '...')

$app = Get-MgApplication -Filter "displayName eq '$AppName'" -ErrorAction SilentlyContinue | Select-Object -First 1

if ($Undo) {
    if (-not $Apply) { Write-Step ("would remove: the Exchange role assignments and scope '$ScopeName', the Exchange service principal, and the application '$AppName' (preview; -Undo -Apply does it)"); Disconnect-MgGraph | Out-Null; return }
    Write-Step 'signing in to Exchange Online ...'
    Connect-ExchangeOnline -ShowBanner:$false
    foreach ($role in 'Application Mail.Read', 'Application Mail.Send') {
        Get-ManagementRoleAssignment -Role $role -ErrorAction SilentlyContinue |
            Where-Object { $_.CustomResourceScope -eq $ScopeName } |
            ForEach-Object { Remove-ManagementRoleAssignment -Identity $_.Identity -Confirm:$false; Write-Step ("removed role assignment: " + $_.Name) }
    }
    if (Get-ManagementScope -Identity $ScopeName -ErrorAction SilentlyContinue) { Remove-ManagementScope -Identity $ScopeName -Confirm:$false; Write-Step "removed management scope: $ScopeName" }
    if ($app) {
        $sp = Get-ServicePrincipal -Identity $app.AppId -ErrorAction SilentlyContinue
        if ($sp) { Remove-ServicePrincipal -Identity $app.AppId -Confirm:$false; Write-Step 'removed the Exchange service principal' }
        Remove-MgApplication -ApplicationId $app.Id
        Write-Step ("removed the application '$AppName'")
    }
    if (Test-Path $OutFile) { Remove-Item $OutFile -Force; Write-Step "removed $OutFile" }
    Disconnect-ExchangeOnline -Confirm:$false | Out-Null
    Disconnect-MgGraph | Out-Null
    Write-Step 'undone.'
    return
}

if ($app) { Write-Step ("the application '$AppName' already exists (app id ends " + $app.AppId.Substring(30) + "); it is used as it is, and no second one is made") }
else { Write-Step ($(if ($Apply) { "registering" } else { "would register" }) + " the application '$AppName': single tenant, no redirect URI, no API permission, with the certificate above") }

if (-not $Apply) {
    Write-Step ('would then: create its service principal; tell Exchange about it; make the scope ' + $ScopeName +
                ' over ' + ($Mailboxes -join ' and ') + '; assign Application Mail.Read and Application Mail.Send on it; and test all three.')
    Write-Step 'RESULT: preview PASS. Nothing was changed (-Apply does it).'
    Disconnect-MgGraph | Out-Null
    return
}

if (-not $app) {
    $app = New-MgApplication -DisplayName $AppName -SignInAudience 'AzureADMyOrg' `
        -KeyCredentials @(@{ Type = 'AsymmetricX509Cert'; Usage = 'Verify'; Key = $cer.RawData; DisplayName = $cer.Subject })
    Write-Step ("registered the application; certificate uploaded: " + (@(Get-MgApplication -ApplicationId $app.Id).KeyCredentials).Count + " key credential(s); API permissions added: " +
                (@(Get-MgApplication -ApplicationId $app.Id).RequiredResourceAccess).Count)
} elseif (-not (@(Get-MgApplication -ApplicationId $app.Id).KeyCredentials | Where-Object { $_.CustomKeyIdentifier -and [Convert]::ToBase64String($_.CustomKeyIdentifier) -eq [Convert]::ToBase64String($cer.GetCertHash()) })) {
    Update-MgApplication -ApplicationId $app.Id -KeyCredentials @(@{ Type = 'AsymmetricX509Cert'; Usage = 'Verify'; Key = $cer.RawData; DisplayName = $cer.Subject })
    Write-Step 'uploaded the certificate to the existing application'
}

$sp = Get-MgServicePrincipal -Filter "appId eq '$($app.AppId)'" -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $sp) { $sp = New-MgServicePrincipal -AppId $app.AppId; Write-Step 'created its service principal (the enterprise application)' }
else { Write-Step 'its service principal already exists' }
[IO.File]::WriteAllText($OutFile, "AppId=$($app.AppId)`r`nObjectId=$($sp.Id)`r`nTenantId=$($ctx.TenantId)`r`n", (New-Object System.Text.UTF8Encoding $false))
Write-Step ("identifiers written to $OutFile (not printed); who can open it: " + (((Get-Acl $OutFile).Access | ForEach-Object { [string]$_.IdentityReference }) -join ', '))

# ---------------------------------------------------------------- Exchange Online
Write-Step 'signing in to Exchange Online (a browser window opens) ...'
Connect-ExchangeOnline -ShowBanner:$false
foreach ($mb in $Mailboxes) {
    $r = Get-Recipient -Identity $mb -ErrorAction SilentlyContinue
    if (-not $r) { throw "$mb is not a recipient in this tenant. Nothing further was changed." }
    Write-Step ("mailbox " + $mb + ": " + $r.RecipientTypeDetails)
}
if (-not (Get-ServicePrincipal -Identity $app.AppId -ErrorAction SilentlyContinue)) {
    New-ServicePrincipal -AppId $app.AppId -ObjectId $sp.Id -DisplayName $AppName | Out-Null
    Write-Step 'Exchange now knows the service principal'
}
$filter = ($Mailboxes | ForEach-Object { "PrimarySmtpAddress -eq '$_'" }) -join ' -or '
if (-not (Get-ManagementScope -Identity $ScopeName -ErrorAction SilentlyContinue)) {
    New-ManagementScope -Name $ScopeName -RecipientRestrictionFilter $filter | Out-Null
    Write-Step ("management scope '$ScopeName' made over " + ($Mailboxes -join ' and '))
}
foreach ($role in 'Application Mail.Read', 'Application Mail.Send') {
    $have = Get-ManagementRoleAssignment -Role $role -ErrorAction SilentlyContinue | Where-Object { $_.CustomResourceScope -eq $ScopeName -and $_.App -eq $app.AppId }
    if (-not $have) {
        New-ManagementRoleAssignment -App $app.AppId -Role $role -CustomResourceScope $ScopeName | Out-Null
        Write-Step "assigned $role on that scope"
    } else { Write-Step "$role was already assigned on that scope" }
}

# ---------------------------------------------------------------- the test
$pass = $true
foreach ($mb in $Mailboxes) {
    foreach ($r in @(Test-ServicePrincipalAuthorization -Identity $app.AppId -Resource $mb)) {
        $ok = $r.InScope -eq $true
        Write-Step ("  " + $(if ($ok) { 'PASS' } else { 'FAIL' }) + ": " + $r.RoleName + " on " + $mb + " InScope " + $r.InScope)
        if (-not $ok) { $pass = $false }
    }
}
$other = Get-Mailbox -ResultSize 50 | Where-Object { $Mailboxes -notcontains $_.PrimarySmtpAddress } | Select-Object -First 1
if ($other) {
    foreach ($r in @(Test-ServicePrincipalAuthorization -Identity $app.AppId -Resource $other.PrimarySmtpAddress)) {
        $ok = $r.InScope -ne $true
        Write-Step ("  " + $(if ($ok) { 'PASS' } else { 'FAIL' }) + ": " + $r.RoleName + " on another mailbox InScope " + $r.InScope + " (must not be True)")
        if (-not $ok) { $pass = $false }
    }
} else { Write-Step '  (no third mailbox found to test against; the negative test did not run)' }

Disconnect-ExchangeOnline -Confirm:$false | Out-Null
Disconnect-MgGraph | Out-Null
if ($pass) { Write-Step 'RESULT: PASS. The permission can take 30 minutes to 2 hours to take effect. Tell SQL01 "mail app done".' }
else { Write-Step 'RESULT: FAIL. Tell SQL01 the FAIL lines; -Undo -Apply puts it all back.'; exit 2 }

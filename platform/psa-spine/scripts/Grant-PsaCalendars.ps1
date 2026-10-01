<#
.SYNOPSIS
    Dada's one step for calendar sync: let the mail app read and write the desk members' calendars, and only theirs.

.DESCRIPTION
    Schema 059 (Dada, 1 Oct 2026: "the members should have their accounts calendars synced with the actual calendars
    on outlook or exchange"). Run it elevated, as yourself, on DND-SQL01, after New-PsaMailApp.ps1 has made the app.
    It needs an Exchange Online Organization Management member at the sign-in.

    With -Apply it:
      1. asks the desk which members work a board (`psaspine calendar-members`): their mailboxes, nothing else;
      2. makes (or reuses) the mail-enabled security group "PSA desk calendars" in Exchange Online and sets its
         members to exactly those mailboxes. Direct members only: RBAC for Applications ignores nested groups
         (VERIFIED 1 Oct 2026, learn.microsoft.com/exchange/permissions-exo/application-rbac, "Limitations");
      3. makes the management scope "PSA desk calendars" with MemberOfGroup -eq <that group's distinguished name>;
      4. assigns "Application Calendars.ReadWrite" to the mail app on that scope;
      5. tests it: InScope True for every member, False for a mailbox that is not a member.

    What it deliberately does NOT do:
      - add Calendars.ReadWrite in Entra: that would open every calendar in the tenant (the grants add together);
      - touch the mail scope "PSA desk mailboxes" or its Mail.Read and Mail.Send.

    Re-run it when the desk's members change: the group is set to the desk's list again. The permission can take
    30 minutes to 2 hours to take effect.

    PREVIEW BY DEFAULT. -Undo -Apply removes the assignment, the scope and the group.

.EXAMPLE
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Grant-PsaCalendars.ps1
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Grant-PsaCalendars.ps1 -Apply
#>
[CmdletBinding()]
param(
    [switch]$Apply,
    [switch]$Undo,
    [string]$AppFile = 'D:\psa\mail-app.txt',
    [string]$GroupName = 'PSA desk calendars',
    [string]$GroupAlias = 'psa-desk-calendars',
    [string]$ScopeName = 'PSA desk calendars',
    [string]$AllowedDomain = 'pmcne.ph',
    [string]$Database = 'Driver={ODBC Driver 17 for SQL Server};Server=DND-SQL01\PMC_SS;Database=PMC_PSA;Trusted_Connection=yes;Encrypt=yes;TrustServerCertificate=yes',
    [string]$SpineDir = 'D:\dnd-poo\platform\psa-spine',
    [string]$PythonExe = 'C:\PMC\Python312\python.exe',
    [string]$LogFile = 'D:\psa\logs\Grant-PsaCalendars.log'
)
$ErrorActionPreference = 'Stop'
$Role = 'Application Calendars.ReadWrite'

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
if (-not (Get-Module -ListAvailable -Name 'ExchangeOnlineManagement')) { throw 'The ExchangeOnlineManagement module is not on this host. Nothing was done.' }
Import-Module ExchangeOnlineManagement -ErrorAction Stop

$ids = @{}
if (-not (Test-Path $AppFile)) { throw ($AppFile + ' is missing: run New-PsaMailApp.ps1 first. Nothing was done.') }
foreach ($l in Get-Content $AppFile) { if ($l -match '^\s*(\w+)\s*=\s*(\S+)\s*$') { $ids[$Matches[1]] = $Matches[2] } }
if (-not $ids['AppId']) { throw ($AppFile + ' has no AppId. Nothing was done.') }

# --- the desk's members and their mailboxes
Push-Location $SpineDir
try { $out = & $PythonExe -m psaspine calendar-members $Database --allowed-domain $AllowedDomain 2>&1; $code = $LASTEXITCODE } finally { Pop-Location }
if ($code -ne 0) { throw ('calendar-members failed (exit ' + $code + '). Nothing was done.') }
$wanted = @()
foreach ($x in (($out | Out-String).Trim() | ConvertFrom-Json)) { if ($null -ne $x -and $x.PSObject.Properties['mailbox']) { $wanted += $x.mailbox.ToLowerInvariant() } }
Write-Step ('the desk has ' + $wanted.Count + ' member(s) with a mailbox in ' + $AllowedDomain)

Write-Step 'signing in to Exchange Online (a browser window opens) ...'
Connect-ExchangeOnline -ShowBanner:$false

if ($Undo) {
    if (-not $Apply) { Write-Step ("would remove: the '" + $Role + "' assignment on '" + $ScopeName + "', the scope, and the group '" + $GroupName + "' (preview)"); Disconnect-ExchangeOnline -Confirm:$false | Out-Null; return }
    Get-ManagementRoleAssignment -Role $Role -ErrorAction SilentlyContinue | Where-Object { $_.CustomResourceScope -eq $ScopeName } |
        ForEach-Object { Remove-ManagementRoleAssignment -Identity $_.Identity -Confirm:$false; Write-Step ('removed role assignment: ' + $_.Name) }
    if (Get-ManagementScope -Identity $ScopeName -ErrorAction SilentlyContinue) { Remove-ManagementScope -Identity $ScopeName -Confirm:$false; Write-Step ('removed scope: ' + $ScopeName) }
    if (Get-DistributionGroup -Identity $GroupAlias -ErrorAction SilentlyContinue) { Remove-DistributionGroup -Identity $GroupAlias -Confirm:$false; Write-Step ('removed group: ' + $GroupName) }
    Disconnect-ExchangeOnline -Confirm:$false | Out-Null
    Write-Step 'undone.'
    return
}

$missing = @()
foreach ($mb in $wanted) { if (-not (Get-Recipient -Identity $mb -ErrorAction SilentlyContinue)) { $missing += $mb } }
if ($missing.Count) { Write-Step ('  ' + $missing.Count + ' member mailbox(es) not found in Exchange Online; they are left out: ' + ($missing -join ', ')) }
$found = @($wanted | Where-Object { $missing -notcontains $_ })
if (-not (Get-ServicePrincipal -Identity $ids['AppId'] -ErrorAction SilentlyContinue)) { throw 'Exchange does not know the mail app. Run New-PsaMailApp.ps1 -Apply first. Nothing was changed.' }

if (-not $Apply) {
    Write-Step ("would: make or reuse the mail-enabled security group '" + $GroupName + "' with exactly " + $found.Count +
                " member(s); make the scope '" + $ScopeName + "' over it; assign '" + $Role + "' to the mail app on it; and test.")
    Write-Step 'RESULT: preview PASS. Nothing was changed (-Apply does it).'
    Disconnect-ExchangeOnline -Confirm:$false | Out-Null
    return
}

$group = Get-DistributionGroup -Identity $GroupAlias -ErrorAction SilentlyContinue
if (-not $group) {
    $group = New-DistributionGroup -Name $GroupName -Alias $GroupAlias -Type Security -MemberDepartRestriction Closed -MemberJoinRestriction Closed
    Write-Step ('made the mail-enabled security group ' + $GroupName)
}
Set-DistributionGroup -Identity $GroupAlias -HiddenFromAddressListsEnabled $true
Update-DistributionGroupMember -Identity $GroupAlias -Members $found -Confirm:$false -BypassSecurityGroupManagerCheck
Write-Step ('group members set: ' + @(Get-DistributionGroupMember -Identity $GroupAlias -ResultSize Unlimited).Count)
$dn = (Get-Group -Identity $GroupAlias).DistinguishedName
$filter = "MemberOfGroup -eq '" + $dn + "'"
if (Get-ManagementScope -Identity $ScopeName -ErrorAction SilentlyContinue) {
    Set-ManagementScope -Identity $ScopeName -RecipientRestrictionFilter $filter
} else {
    New-ManagementScope -Name $ScopeName -RecipientRestrictionFilter $filter | Out-Null
}
Write-Step ('scope ' + $ScopeName + ' is the group, direct members only')
if (-not (Get-ManagementRoleAssignment -Role $Role -ErrorAction SilentlyContinue | Where-Object { $_.CustomResourceScope -eq $ScopeName })) {
    New-ManagementRoleAssignment -App $ids['AppId'] -Role $Role -CustomResourceScope $ScopeName | Out-Null
}
Write-Step ('assigned ' + $Role + ' on that scope')

$bad = 0
foreach ($mb in $found) {
    $t = Test-ServicePrincipalAuthorization -Identity $ids['AppId'] -Resource $mb | Where-Object { $_.RoleName -eq $Role }
    if ($t -and $t.InScope) { Write-Step ('  PASS: ' + $Role + ' on ' + $mb + ' InScope True') } else { Write-Step ('  NOT YET: ' + $mb); $bad++ }
}
$other = Get-Mailbox -ResultSize 50 | Where-Object { $found -notcontains $_.PrimarySmtpAddress.ToString().ToLowerInvariant() } | Select-Object -First 1
if ($other) {
    $t = Test-ServicePrincipalAuthorization -Identity $ids['AppId'] -Resource $other.PrimarySmtpAddress.ToString() | Where-Object { $_.RoleName -eq $Role }
    if ($t -and $t.InScope) { Write-Step '  FAIL: a mailbox that is not a desk member is in scope'; $bad += 100 }
    else { Write-Step ('  PASS: ' + $Role + ' on another mailbox InScope False (must not be True)') }
}
Disconnect-ExchangeOnline -Confirm:$false | Out-Null
if ($bad -ge 100) { Write-Step 'RESULT: FAIL. Run -Undo -Apply and tell WS36.'; exit 2 }
if ($bad) { Write-Step ('RESULT: PASS for the scope; ' + $bad + ' member(s) not yet in scope - Exchange can take 30 minutes to 2 hours. Re-run to test again.'); return }
Write-Step 'RESULT: PASS. The permission can take 30 minutes to 2 hours to take effect. Tell SQL01 "calendar scope done".'

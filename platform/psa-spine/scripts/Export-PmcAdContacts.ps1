<#
.SYNOPSIS
    Export the people in Active Directory as PSA contacts. Reads AD; changes nothing in it.

.DESCRIPTION
    ConnectWise keeps a contact under each company, and every ticket names one.
    PMC's staff are already in Active Directory, so the desk's contacts are
    exported from there rather than typed in again.

    This writes a CSV in exactly the shape `psaspine import-contacts` reads:
        ObjectGUID, DisplayName, Mail, UserPrincipalName, SamAccountName,
        Department, Title, Office, TelephoneNumber, Enabled

    What it deliberately does NOT do:
      - write to AD. There is no Set-, New-, Remove- or Move- AD cmdlet here;
      - export a password, a hash, a group membership or a manager chain;
      - need a privileged account. Run it as an ordinary domain user: reading
        these attributes is what an authenticated user can do by default in AD
        (INFERRED from the AD defaults; NOT VERIFIED on pmcne.ph, where the
        preview below is the check). Do not run it as a Domain Admin, and do not
        copy the pattern of the weekly sync task that does.

    The ObjectGUID is the identity the desk keys on, so a renamed person or a
    changed mailbox stays one contact. A disabled account is exported with
    Enabled = False and becomes an inactive contact, never a deleted one.

    PREVIEW BY DEFAULT. Without -Apply it reads AD and prints counts only: no
    file is written. Logs counts, never names.

    Needs the ActiveDirectory module (RSAT). Where that is missing, run it on a
    machine that has it and copy the CSV to the server.

.PARAMETER SearchBase
    Optional. The OU to read, as a distinguished name. Omit for the whole domain.
    Kept on the command line, never in this file.

.PARAMETER IncludeWithoutMail
    Also export accounts that have no mail address. Off by default: those are
    mostly service and system accounts, and a contact nobody can email is rarely
    a requester.

.EXAMPLE
    # Preview: counts only, writes nothing.
    .\Export-PmcAdContacts.ps1 -OutFile D:\psa\contacts\ad-contacts.csv

.EXAMPLE
    # Write the CSV, then import it under the company PMC.
    .\Export-PmcAdContacts.ps1 -OutFile D:\psa\contacts\ad-contacts.csv -Apply
    C:\PMC\Python312\python.exe -m psaspine import-contacts D:\psa\spine.db `
        D:\psa\contacts\ad-contacts.csv --company PMC
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)] [string] $OutFile,
    [string] $SearchBase,
    [string] $Server,
    [switch] $IncludeWithoutMail,
    [switch] $Apply
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

Import-Module ActiveDirectory

$properties = @('DisplayName', 'Mail', 'UserPrincipalName', 'SamAccountName',
                'Department', 'Title', 'Office', 'TelephoneNumber', 'Enabled', 'ObjectGUID')

$query = @{ Filter = '*'; Properties = $properties }
if ($SearchBase) { $query['SearchBase'] = $SearchBase }
if ($Server)     { $query['Server'] = $Server }

$users = @(Get-ADUser @query)
$kept = @($users | Where-Object { $IncludeWithoutMail -or $_.Mail })

$rows = @($kept | ForEach-Object {
    [pscustomobject]@{
        ObjectGUID        = $_.ObjectGUID.ToString()
        DisplayName       = $_.DisplayName
        Mail              = $_.Mail
        UserPrincipalName = $_.UserPrincipalName
        SamAccountName    = $_.SamAccountName
        Department        = $_.Department
        Title             = $_.Title
        Office            = $_.Office
        TelephoneNumber   = $_.TelephoneNumber
        Enabled           = [bool]$_.Enabled
    }
})

$enabled  = @($rows | Where-Object { $_.Enabled }).Count
$disabled = $rows.Count - $enabled
Write-Output ("{0} accounts read; {1} to export ({2} enabled, {3} disabled); {4} left out for having no mail." -f `
    $users.Count, $rows.Count, $enabled, $disabled, ($users.Count - $kept.Count))

if (-not $Apply) {
    Write-Output 'PREVIEW: nothing written. Rerun with -Apply to write the CSV.'
    return
}

if ($rows.Count -eq 0) {
    throw 'Nothing to export: check -SearchBase, or that this account can read AD.'
}

$dir = Split-Path -Parent $OutFile
if ($dir -and -not (Test-Path -LiteralPath $dir)) {
    throw "The folder for -OutFile does not exist: create it and restrict it first."
}

# Written beside the target, then moved over it, so the importer never reads a
# half-written file.
$partial = "$OutFile.partial"
$rows | Export-Csv -LiteralPath $partial -NoTypeInformation -Encoding UTF8
$check = @(Import-Csv -LiteralPath $partial)
if ($check.Count -ne $rows.Count) {
    Remove-Item -LiteralPath $partial
    throw ("The CSV holds {0} rows, not {1}; nothing replaced." -f $check.Count, $rows.Count)
}
Move-Item -LiteralPath $partial -Destination $OutFile -Force
Write-Output ("Wrote {0} rows. Next: psaspine import-contacts <database> <this file> --company PMC" -f $rows.Count)

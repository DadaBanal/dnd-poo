<#
.SYNOPSIS
    Export AD computer objects as PSA configurations. Reads AD; changes nothing in it.

.DESCRIPTION
    Dada PSA lists the configurations (machines) a ticket concerns, and a
    technician launches the remote session from there. The machines are already
    in Active Directory, so the desk reads them from there.

    Writes a CSV in exactly the shape `psaspine import-computers` reads:
        ObjectGUID, Name, DNSHostName, OperatingSystem, OperatingSystemVersion,
        Description, Enabled, LastLogonDate

    What it deliberately does NOT do:
      - write to AD. There is no Set-, New-, Remove- or Move- AD cmdlet here;
      - read or export an IP address. The desk reaches a machine by its
        remote-support session, not by address, and an address list is network
        topology that stays out of the desk and out of the repository;
      - read LAPS or BitLocker attributes, or any other secret;
      - need a privileged account. Run it as an ordinary domain user (INFERRED
        from the AD defaults; NOT VERIFIED on pmcne.ph, where the preview is the
        check). Not as a Domain Admin.

    PREVIEW BY DEFAULT. Without -Apply it reads AD and prints counts only.
    Logs counts, never names.

.EXAMPLE
    .\Export-PmcAdComputers.ps1 -OutFile D:\psa\contacts\ad-computers.csv
    .\Export-PmcAdComputers.ps1 -OutFile D:\psa\contacts\ad-computers.csv -Apply
    C:\PMC\Python312\python.exe -m psaspine import-computers D:\psa\spine.db `
        D:\psa\contacts\ad-computers.csv --company PMC
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)] [string] $OutFile,
    [string] $SearchBase,
    [string] $Server,
    [switch] $Apply
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

Import-Module ActiveDirectory

$properties = @('DNSHostName', 'OperatingSystem', 'OperatingSystemVersion',
                'Description', 'Enabled', 'LastLogonDate', 'ObjectGUID')

$query = @{ Filter = '*'; Properties = $properties }
if ($SearchBase) { $query['SearchBase'] = $SearchBase }
if ($Server)     { $query['Server'] = $Server }

$computers = @(Get-ADComputer @query)

$rows = @($computers | ForEach-Object {
    $seen = ''
    if ($_.LastLogonDate) { $seen = $_.LastLogonDate.ToString('yyyy-MM-dd HH:mm') }
    [pscustomobject]@{
        ObjectGUID             = $_.ObjectGUID.ToString()
        Name                   = $_.Name
        DNSHostName            = $_.DNSHostName
        OperatingSystem        = $_.OperatingSystem
        OperatingSystemVersion = $_.OperatingSystemVersion
        Description            = $_.Description
        Enabled                = [bool]$_.Enabled
        LastLogonDate          = $seen
    }
})

$enabled = @($rows | Where-Object { $_.Enabled }).Count
$servers = @($rows | Where-Object { $_.OperatingSystem -like '*Server*' }).Count
Write-Output ("{0} computers read ({1} enabled, {2} disabled; {3} servers)." -f `
    $rows.Count, $enabled, ($rows.Count - $enabled), $servers)

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

$partial = "$OutFile.partial"
$rows | Export-Csv -LiteralPath $partial -NoTypeInformation -Encoding UTF8
$check = @(Import-Csv -LiteralPath $partial)
if ($check.Count -ne $rows.Count) {
    Remove-Item -LiteralPath $partial
    throw ("The CSV holds {0} rows, not {1}; nothing replaced." -f $check.Count, $rows.Count)
}
Move-Item -LiteralPath $partial -Destination $OutFile -Force
Write-Output ("Wrote {0} rows. Next: psaspine import-computers <database> <this file> --company PMC" -f $rows.Count)

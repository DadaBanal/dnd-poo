<#
.SYNOPSIS
  First verified backup of the Orthanc imaging index.

.DESCRIPTION
  platform/README.md records that the index has NEVER been backed up. This is
  the script that changes that, and it is deliberately the smallest thing that
  can honestly be called a backup: take it, prove it is restorable, write down
  what was taken.

  IT PREVIEWS BY DEFAULT. Nothing is written until you add -Apply. That is the
  discipline this programme uses for anything touching live clinical data, and
  the index is the thing that knows where every study is.

  What -Apply does, and nothing else:
    1. BACKUP DATABASE ... WITH COPY_ONLY, CHECKSUM     a file in -BackupDir
    2. RESTORE VERIFYONLY ... WITH CHECKSUM             proves it is readable
    3. writes a manifest beside it                      what, when, how big, sha256

  COPY_ONLY is deliberate. This is the first backup and there is no established
  log chain to disturb; a COPY_ONLY full backup cannot become the base of one by
  accident, so taking it changes nothing about whatever backup plan is adopted
  later.

  IT REFUSES rather than guesses:
    - refuses a -BackupDir on the same volume as the database files. A copy on
      the same disk is not a backup; it is a second copy of the thing that fails.
    - refuses an IP address for -ServerInstance. The repository fence forbids
      internal addresses and this script is committed; name the host.
    - refuses to overwrite an existing backup file.

.PARAMETER Apply           Take the backup. Without it you get the plan and nothing else.
.PARAMETER ServerInstance  The index server by NAME, e.g. DND-SQL01\PMC_SS
.PARAMETER Database        The index database name.
.PARAMETER BackupDir       Where the backup goes. Must be a different volume.
.PARAMETER Credential      SQL login. Omit for Windows integrated security.

.EXAMPLE
  .\Backup-PmcImagingIndex.ps1 -ServerInstance DND-SQL01\PMC_SS -Database orthanc -BackupDir E:\PMC\backup
  .\Backup-PmcImagingIndex.ps1 -ServerInstance DND-SQL01\PMC_SS -Database orthanc -BackupDir E:\PMC\backup -Apply

.NOTES
  NOT VERIFIED. This has never been executed: no environment on the authoring
  account has a route to the index server. Written for Windows PowerShell 5.1,
  pure ASCII, using System.Data.SqlClient so it needs no SqlServer module.
  Run it with no -Apply first and read the plan.
#>
[CmdletBinding()]
param(
  [switch] $Apply,
  [Parameter(Mandatory = $true)] [string] $ServerInstance,
  [Parameter(Mandatory = $true)] [string] $Database,
  [Parameter(Mandatory = $true)] [string] $BackupDir,
  [pscredential] $Credential,
  [int] $CommandTimeoutSeconds = 7200
)

$ErrorActionPreference = 'Stop'

function Write-Step { param([string] $Text) Write-Host "  $Text" }
function Write-Head { param([string] $Text) Write-Host ""; Write-Host $Text }

# ---------------------------------------------------------------- the fence
# An IP here would be committed to a private repository that forbids them, and
# a backup script is exactly the kind of file somebody copies into a ticket.
if ($ServerInstance -match '^\s*\d{1,3}(\.\d{1,3}){3}') {
  throw "Name the host, do not address it: '$ServerInstance' looks like an IP. The repository fence forbids internal addresses."
}

$connectionString = "Server=$ServerInstance;Database=master;Application Name=PMC-IndexBackup;"
if ($Credential) {
  $connectionString += "User ID=$($Credential.UserName);Password=$($Credential.GetNetworkCredential().Password);"
} else {
  $connectionString += "Integrated Security=SSPI;"
}

function Invoke-Scalar {
  param([string] $Sql)
  $connection = New-Object System.Data.SqlClient.SqlConnection $connectionString
  try {
    $connection.Open()
    $command = $connection.CreateCommand()
    $command.CommandText = $Sql
    $command.CommandTimeout = $CommandTimeoutSeconds
    return $command.ExecuteScalar()
  } finally { $connection.Dispose() }
}

function Invoke-Rows {
  param([string] $Sql)
  $connection = New-Object System.Data.SqlClient.SqlConnection $connectionString
  try {
    $connection.Open()
    $command = $connection.CreateCommand()
    $command.CommandText = $Sql
    $command.CommandTimeout = $CommandTimeoutSeconds
    $table = New-Object System.Data.DataTable
    $table.Load($command.ExecuteReader())
    # 5.1 note: return the DataTable itself, not the pipeline-unrolled rows.
    return ,$table
  } finally { $connection.Dispose() }
}

function Invoke-NonQuery {
  param([string] $Sql)
  $connection = New-Object System.Data.SqlClient.SqlConnection $connectionString
  try {
    $connection.Open()
    $command = $connection.CreateCommand()
    $command.CommandText = $Sql
    $command.CommandTimeout = $CommandTimeoutSeconds
    [void] $command.ExecuteNonQuery()
  } finally { $connection.Dispose() }
}

Write-Head "PMC imaging index backup"
Write-Step "server   : $ServerInstance"
Write-Step "database : $Database"
Write-Step "target   : $BackupDir"
Write-Step ("mode     : " + $(if ($Apply) { "APPLY" } else { "PREVIEW (nothing will be written)" }))

# --------------------------------------------------------------- reachability
Write-Head "Checking the server answers, and the database exists"
$safeName = $Database.Replace("'", "''")
$exists = Invoke-Scalar "SELECT COUNT(*) FROM sys.databases WHERE name = N'$safeName';"
if ([int] $exists -ne 1) {
  throw "No database named '$Database' on $ServerInstance. Nothing was changed."
}
$sizeMb = Invoke-Scalar @"
SELECT CAST(SUM(CAST(size AS bigint)) * 8.0 / 1024 AS decimal(18,1))
  FROM sys.master_files WHERE database_id = DB_ID(N'$safeName');
"@
Write-Step "database size: $sizeMb MB"

# ------------------------------------------------------- the same-volume rule
Write-Head "Checking the target is not the volume the database lives on"
$files = Invoke-Rows @"
SELECT physical_name FROM sys.master_files WHERE database_id = DB_ID(N'$safeName');
"@
$dataVolumes = @()
foreach ($row in $files.Rows) {
  $path = [string] $row['physical_name']
  if ($path.Length -ge 2 -and $path.Substring(1, 1) -eq ':') {
    $dataVolumes += $path.Substring(0, 1).ToUpperInvariant()
  }
}
$dataVolumes = $dataVolumes | Select-Object -Unique
Write-Step ("database volumes: " + ($dataVolumes -join ', '))

$targetVolume = $null
if ($BackupDir.Length -ge 2 -and $BackupDir.Substring(1, 1) -eq ':') {
  $targetVolume = $BackupDir.Substring(0, 1).ToUpperInvariant()
}
if ($targetVolume -and ($dataVolumes -contains $targetVolume)) {
  throw "Refusing: -BackupDir is on volume $targetVolume, which is where the database files live. A copy on the same disk is not a backup; it is a second copy of the thing that fails."
}
if (-not $targetVolume) {
  Write-Step "target is a UNC or relative path; the same-volume check could not run. Confirm it by hand."
}

# ---------------------------------------------------------------- the plan
$stamp    = (Get-Date).ToString('yyyyMMdd-HHmmss')
$fileName = "$Database-$stamp.bak"
$fullPath = Join-Path $BackupDir $fileName
$manifest = "$fullPath.manifest.txt"

Write-Head "Plan"
Write-Step "1. BACKUP DATABASE [$Database] TO DISK = '$fullPath' WITH COPY_ONLY, CHECKSUM, INIT, STATS = 5"
Write-Step "2. RESTORE VERIFYONLY FROM DISK = '$fullPath' WITH CHECKSUM"
Write-Step "3. write $manifest"

if (-not $Apply) {
  Write-Head "PREVIEW ONLY. Nothing was written. Re-run with -Apply to take the backup."
  return
}

# ---------------------------------------------------------------- do it
if (Test-Path -LiteralPath $fullPath) {
  throw "Refusing: '$fullPath' already exists. A backup that overwrites another backup halves the number of backups."
}

Write-Head "Taking the backup"
$escaped = $fullPath.Replace("'", "''")
Invoke-NonQuery @"
BACKUP DATABASE [$Database] TO DISK = N'$escaped'
  WITH COPY_ONLY, CHECKSUM, INIT, NAME = N'PMC imaging index - first verified backup', STATS = 5;
"@
Write-Step "backup written"

Write-Head "Verifying it is restorable"
Invoke-NonQuery "RESTORE VERIFYONLY FROM DISK = N'$escaped' WITH CHECKSUM;"
Write-Step "RESTORE VERIFYONLY passed"

# A backup nobody checked the size of is a backup nobody checked.
$onDisk = $null
if (Test-Path -LiteralPath $fullPath) {
  $onDisk = Get-Item -LiteralPath $fullPath
  Write-Step ("file size: " + [math]::Round($onDisk.Length / 1MB, 1) + " MB")
} else {
  Write-Step "NOTE: the backup file is not visible from this machine (the server wrote it locally). Check it on the server."
}

Write-Head "Writing the manifest"
$hash = 'not computed (file not reachable from this machine)'
if ($onDisk) { $hash = (Get-FileHash -LiteralPath $fullPath -Algorithm SHA256).Hash }
$lines = @(
  "PMC imaging index backup",
  "taken_at       : $((Get-Date).ToString('o'))",
  "server         : $ServerInstance",
  "database       : $Database",
  "database_size  : $sizeMb MB",
  "backup_file    : $fullPath",
  "backup_bytes   : $(if ($onDisk) { $onDisk.Length } else { 'unknown' })",
  "sha256         : $hash",
  "verified       : RESTORE VERIFYONLY WITH CHECKSUM passed",
  "copy_only      : yes (no log chain was established or disturbed)",
  "taken_by       : $env:USERNAME on $env:COMPUTERNAME"
)
if ($onDisk) {
  Set-Content -LiteralPath $manifest -Value $lines -Encoding ASCII
  Write-Step "manifest: $manifest"
} else {
  Write-Step "manifest not written: the backup path is not reachable from this machine."
  $lines | ForEach-Object { Write-Step $_ }
}

Write-Head "DONE. The index has a verified backup."
Write-Step "This is one backup, not a backup regime. A schedule, a retention rule"
Write-Step "and an offsite copy are still owed; see the handoff that sent you here."

<#
.SYNOPSIS
  Verified copy of the Orthanc study archive to a separate volume.

.DESCRIPTION
  The index knows where every study is; this is the studies themselves. Backing
  up one without the other is not a backup of the archive: an index with no
  pixels restores a catalogue of nothing, and pixels with no index restore a
  disk full of unnamed files. Run this and Backup-PmcImagingIndex.ps1 as a pair,
  and record both in the same manifest.

  IT PREVIEWS BY DEFAULT. Without -Apply this runs robocopy in LIST mode, which
  reads and reports and writes nothing, so the preview is the real file list
  rather than a guess at one.

  What -Apply does:
    1. robocopy <StudyDir> <BackupDir>\studies   /E, no deletes, restartable
    2. writes a manifest: counts, bytes, duration, robocopy exit code

  IT REFUSES rather than guesses:
    - refuses a -BackupDir on the same volume as -StudyDir.
    - refuses to MIRROR. /MIR deletes at the destination to match the source, so
      a study deleted at source by mistake is deleted from the backup too, which
      is precisely the failure a backup exists to survive. This copies and adds;
      it never deletes.

  ON SIZE. A cathlab archive in JPEG-LS is large and the first run is long. It
  is restartable (/Z) and skips files already copied and unchanged (/XO is NOT
  used; robocopy skips same-size-same-time files by default), so a second run
  after an interruption resumes rather than restarting.

.PARAMETER Apply       Do the copy. Without it you get the file list and nothing else.
.PARAMETER StudyDir    Orthanc's storage directory (StorageDirectory in orthanc.json).
.PARAMETER BackupDir   Where the copy goes. Must be a different volume.
.PARAMETER Threads     robocopy /MT. Default 8; raise only if the disk can take it.

.EXAMPLE
  .\Backup-PmcOrthancArchive.ps1 -StudyDir C:\Orthanc\db -BackupDir E:\PMC\backup
  .\Backup-PmcOrthancArchive.ps1 -StudyDir C:\Orthanc\db -BackupDir E:\PMC\backup -Apply

.NOTES
  NOT VERIFIED. Never executed: no environment on the authoring account has a
  route to the archive host. Windows PowerShell 5.1, pure ASCII, robocopy only
  (no module needed). Run with no -Apply first and read the list.

  This does not quiesce Orthanc. Orthanc writes study files once and does not
  rewrite them, so a running copy is safe for completed studies; a study being
  received during the copy may be caught half-written and will be corrected by
  the next run. If you need a strictly point-in-time copy, stop the service
  first and say so in the handoff reply.
#>
[CmdletBinding()]
param(
  [switch] $Apply,
  [Parameter(Mandatory = $true)] [string] $StudyDir,
  [Parameter(Mandatory = $true)] [string] $BackupDir,
  [int] $Threads = 8
)

$ErrorActionPreference = 'Stop'

function Write-Step { param([string] $Text) Write-Host "  $Text" }
function Write-Head { param([string] $Text) Write-Host ""; Write-Host $Text }

if (-not (Test-Path -LiteralPath $StudyDir)) {
  throw "No such study directory: '$StudyDir'. Nothing was changed."
}

$source = (Resolve-Path -LiteralPath $StudyDir).Path
$target = Join-Path $BackupDir 'studies'

Write-Head "PMC Orthanc archive backup"
Write-Step "source : $source"
Write-Step "target : $target"
Write-Step ("mode   : " + $(if ($Apply) { "APPLY" } else { "PREVIEW (robocopy /L, nothing written)" }))

# --------------------------------------------------------- the same-volume rule
$sourceVolume = $null
$targetVolume = $null
if ($source.Length    -ge 2 -and $source.Substring(1, 1)    -eq ':') { $sourceVolume = $source.Substring(0, 1).ToUpperInvariant() }
if ($BackupDir.Length -ge 2 -and $BackupDir.Substring(1, 1) -eq ':') { $targetVolume = $BackupDir.Substring(0, 1).ToUpperInvariant() }
if ($sourceVolume -and $targetVolume -and $sourceVolume -eq $targetVolume) {
  throw "Refusing: source and target are both on volume $sourceVolume. A copy on the same disk is not a backup; it is a second copy of the thing that fails."
}

# robocopy flags, named so the reader does not have to look them up:
#   /E   include subdirectories, empty ones too
#   /Z   restartable, so an interrupted run resumes
#   /MT  multithreaded
#   /R:2 /W:5   two retries, five seconds apart; do not sit on a locked file
#   /NP  no per-file percentage, which is noise in a log
#   /L   LIST ONLY - the preview
$flags = @('/E', '/Z', "/MT:$Threads", '/R:2', '/W:5', '/NP', '/NDL')
if (-not $Apply) { $flags += '/L' }

Write-Head "Running robocopy"
Write-Step ("robocopy `"$source`" `"$target`" " + ($flags -join ' '))
$started = Get-Date
$output = & robocopy $source $target @flags
$code = $LASTEXITCODE
$elapsed = (Get-Date) - $started

# robocopy exit codes are a bit field. 0-7 are success; 8 and above are failures.
#   0 nothing to do   1 files copied   2 extra files   4 mismatched   8 failed
$meaning = switch ($true) {
  { $code -eq 0 }  { 'nothing to copy; source and target already match'; break }
  { $code -lt 8 }  { 'success'; break }
  default          { 'FAILED'; break }
}
Write-Step "robocopy exit code: $code ($meaning)"
Write-Step ("elapsed: " + [string]::Format('{0:hh\:mm\:ss}', $elapsed))

$tail = $output | Select-Object -Last 12
Write-Head "robocopy summary"
$tail | ForEach-Object { Write-Step $_ }

if (-not $Apply) {
  Write-Head "PREVIEW ONLY. Nothing was written. Re-run with -Apply to copy."
  return
}

if ($code -ge 8) {
  throw "robocopy reported failure (exit $code). The backup is NOT complete. Read the summary above."
}

Write-Head "Writing the manifest"
$manifest = Join-Path $BackupDir ("archive-" + (Get-Date).ToString('yyyyMMdd-HHmmss') + ".manifest.txt")
$lines = @(
  "PMC Orthanc archive backup",
  "taken_at     : $((Get-Date).ToString('o'))",
  "source       : $source",
  "target       : $target",
  "robocopy_exit: $code ($meaning)",
  "elapsed      : $([string]::Format('{0:hh\:mm\:ss}', $elapsed))",
  "mirrored     : no (this copy never deletes at the destination)",
  "taken_by     : $env:USERNAME on $env:COMPUTERNAME",
  "",
  "robocopy summary:"
) + ($tail | ForEach-Object { "  $_" })
Set-Content -LiteralPath $manifest -Value $lines -Encoding ASCII
Write-Step "manifest: $manifest"

Write-Head "DONE. Pair this with the index backup taken at the same time."
Write-Step "An archive copy without its index restores a disk of unnamed files."

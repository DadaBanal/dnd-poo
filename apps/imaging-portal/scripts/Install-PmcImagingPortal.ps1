<#
.SYNOPSIS
  One-shot install of the PMC Imaging Portal onto PMC-ORTHANC01.

.DESCRIPTION
  Does the whole job in one run: verifies the page, restores the ServeFolders
  plugin if the 2 Sep cutover dropped it, maps /pmc to it, restarts Orthanc
  safely, and proves the page is being served.

  IT PREVIEWS BY DEFAULT. Nothing is changed until you add -Apply. That is the
  discipline this programme uses for anything touching a live clinical archive,
  and this restarts one.

  What -Apply changes, and nothing else:
    1. writes <PortalDir>\index.html          a new folder, one file in it
    2. adds a ServeFolders mapping            a NEW config file where the service
                                              reads a directory, so orthanc.json
                                              is not touched at all; a backed-up
                                              edit only if it reads a single file
    3. restores ServeFolders.dll              only if a copy is already on this
                                              machine; it never downloads one
    4. restarts the Orthanc service           ONLY if 2 or 3 happened. Replacing
                                              the page alone needs no restart, so
                                              an update costs the archive nothing.

  If Orthanc does not answer by name within the timeout, the configuration change
  is reversed and the service restarted again, without being asked.

.PARAMETER Apply     Make the changes. Without it you get the plan and nothing else.
.PARAMETER Rollback  Remove the mapping this script added, and restart.
.PARAMETER PortalDir Where the page goes. Default C:\PMC\portal
.PARAMETER BaseUrl   The archive, by name, for the proof. Default https://imaging.pmcne.ph

.EXAMPLE
  .\Install-PmcImagingPortal.ps1                    # preview
  .\Install-PmcImagingPortal.ps1 -Apply             # do it
  .\Install-PmcImagingPortal.ps1 -Rollback -Apply   # undo it
#>
[CmdletBinding()]
param(
  [switch] $Apply,
  [switch] $Rollback,
  [string] $PortalDir   = 'C:\PMC\portal',
  [string] $BaseUrl     = 'https://imaging.pmcne.ph',
  [string] $ServiceName = 'Orthanc',
  [int]    $UpTimeoutSeconds = 90,
  # Orthanc answers 401 to an unauthenticated request for ANY path, present or
  # not, so without a credential the final proof cannot tell "served" from
  # "not mapped". Supply one and the proof is real.
  [pscredential] $Credential
)

$ErrorActionPreference = 'Stop'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$BaseUrl = $BaseUrl.TrimEnd('/')
$Here    = Split-Path -Parent $MyInvocation.MyCommand.Path
$Stamp   = Get-Date -Format 'yyyyMMdd-HHmmss'

# The page this script installs, and the only bytes it will accept.
$PortalFile   = Join-Path $Here 'PMC_Imaging_Portal.html'
$ExpectedHash = '45cfe134775f19a3719a603c79deb129a5d06740bf652efae5ad78de4bfefb0c'

$script:Changes = @()
# ServeFolders reads the page off disk on every request, so replacing the file
# needs no restart. Only a configuration or plugin change does. An update should
# not cost a clinical archive a restart it does not need.
$script:NeedsRestart = $false
function Note { param($T, $C = 'Gray') Write-Host $T -ForegroundColor $C }
function Head { param($T) Write-Host ''; Write-Host $T -ForegroundColor Cyan
                Write-Host ('-' * $T.Length) -ForegroundColor DarkGray }
function Plan { param($T) $script:Changes += $T; Note ("  WOULD: {0}" -f $T) Yellow }
function Did  { param($T) $script:Changes += $T; Note ("  DID:   {0}" -f $T) Green }
function Die  { param($T) Write-Host ''; Note "STOPPED: $T" Red
                if (-not $Apply) { Note 'This was a preview; nothing was changed.' DarkGray }
                exit 1 }

if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
      ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
  Die 'Run this in an elevated PowerShell. It edits a service configuration and restarts a service.'
}

Head 'PMC Imaging Portal - one-shot install'
Note ("  mode        : {0}" -f $(if ($Rollback) { 'ROLLBACK' } elseif ($Apply) { 'APPLY' } else { 'PREVIEW - nothing will be changed' })) `
     $(if ($Apply) { 'Yellow' } else { 'Green' })
Note ("  portal dir  : {0}" -f $PortalDir)
Note ("  archive     : {0}" -f $BaseUrl)

# ---------------------------------------------------------------- the service
Head '1. The Orthanc service'
$svc = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if (-not $svc) { Die "No service called '$ServiceName'. Pass -ServiceName with the real one." }
Note ("  {0} is {1}" -f $svc.Name, $svc.Status)

$imagePath = (Get-ItemProperty "HKLM:\SYSTEM\CurrentControlSet\Services\$ServiceName" -Name ImagePath -ErrorAction SilentlyContinue).ImagePath
if (-not $imagePath) { Die "Cannot read the service's ImagePath, so the configuration cannot be located safely." }
Note ("  command     : {0}" -f $imagePath) DarkGray

# The last real path on the service command line is Orthanc's configuration target.
$configTarget = $null
foreach ($m in [regex]::Matches($imagePath, '"([^"]+)"|(\S+)')) {
  $tok = if ($m.Groups[1].Success) { $m.Groups[1].Value } else { $m.Groups[2].Value }
  if ($tok -match '\.exe"?$' -or $tok -match '^(/|--)') { continue }
  if (Test-Path $tok) { $configTarget = $tok }
}
if (-not $configTarget) {
  foreach ($guess in @('C:\Program Files\Orthanc Server\Configuration',
                       'C:\Program Files\Orthanc Server\Configuration\orthanc.json')) {
    if (Test-Path $guess) { $configTarget = $guess; break }
  }
}
if (-not $configTarget) { Die 'Could not find the Orthanc configuration from the service command line or the usual places.' }

$configIsDir = (Get-Item $configTarget).PSIsContainer
Note ("  config      : {0}" -f $configTarget)
Note ("                [{0}]" -f $(if ($configIsDir) { 'a directory, so a new file merges in and orthanc.json is left alone' } else { 'a single file, so it must be edited, with a backup' })) DarkGray

$configDir   = if ($configIsDir) { $configTarget } else { Split-Path -Parent $configTarget }
$orthancRoot = Split-Path -Parent $configDir
$pluginDir   = Join-Path $orthancRoot 'Plugins'
if (-not (Test-Path $pluginDir)) {
  $found = Get-ChildItem 'C:\Program Files' -Directory -Filter 'Orthanc*' -ErrorAction SilentlyContinue |
           ForEach-Object { Join-Path $_.FullName 'Plugins' } | Where-Object { Test-Path $_ } | Select-Object -First 1
  if ($found) { $pluginDir = $found }
}
Note ("  plugins     : {0}" -f $pluginDir)

# ------------------------------------------------------------------ the page
Head '2. The page'
if ($Rollback) { Note '  skipped in rollback' DarkGray }
else {
  if (-not (Test-Path $PortalFile)) { Die 'PMC_Imaging_Portal.html is not next to this script. Unzip the whole package and run it from there.' }
  $actual = (Get-FileHash $PortalFile -Algorithm SHA256).Hash.ToLower()
  if ($actual -ne $ExpectedHash) {
    Note ("  expected {0}" -f $ExpectedHash) DarkGray
    Note ("  found    {0}" -f $actual) DarkGray
    Die 'The page does not hash to the build this script was made for. Do not install it.'
  }
  Note ("  {0:N0} bytes, sha256 verified" -f (Get-Item $PortalFile).Length) Green
}

# ---------------------------------------------------------- ServeFolders plugin
Head '3. ServeFolders'
$dll = @(Get-ChildItem $pluginDir -Filter '*ServeFolders*.dll' -ErrorAction SilentlyContinue)
$restoreFrom = $null
$pluginsFile = $null      # the config file that defines the Plugins list
$pluginsNeedsEntry = $false
if ($dll.Count) { Note ("  on disk: {0}" -f $dll[0].Name) Green }
elseif ($Rollback) { Note '  not present; nothing to do in rollback' DarkGray }
else {
  Note '  NOT in the Plugins folder. The 2 Sep cutover dropped it.' Yellow
  foreach ($root in @($orthancRoot, 'C:\PMC') | Where-Object { Test-Path $_ }) {
    $hit = Get-ChildItem $root -Recurse -Filter '*ServeFolders*.dll' -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($hit) { $restoreFrom = $hit.FullName; break }
  }
  if ($restoreFrom) { Note ("  a copy is already on this machine: {0}" -f $restoreFrom) Green }
  else {
    Note '  No copy on this machine.' Red
    Note '  Take ServeFolders.dll from the Orthanc install media this server was built from,' Yellow
    Note '  put it in the Plugins folder, and run this again. This script will not download a' Yellow
    Note '  plugin onto a clinical box.' Yellow
    Die 'ServeFolders.dll is missing and cannot be restored from anything already here.'
  }
}

# Being in the Plugins folder is not the same as being loaded. Orthanc loads what
# its `Plugins` setting names, and the 2 Sep cutover rewrote that list to 8
# entries. MEASURED 9 Sep 2026: ServeFolders.dll is on this disk and is NOT in
# the loaded set, which is what that looks like from outside.
if ($dll.Count -and -not $Rollback) {
  $dllPath = $dll[0].FullName
  $cfgFiles = if ($configIsDir) { @(Get-ChildItem $configTarget -Filter '*.json' -ErrorAction SilentlyContinue | ForEach-Object FullName) }
              else { @($configTarget) }
  foreach ($f in $cfgFiles) {
    $t = Get-Content $f -Raw
    if ($t -notmatch '"Plugins"\s*:') { continue }
    $pluginsFile = $f
    if ($t -match [regex]::Escape((Split-Path -Leaf $dllPath))) {
      Note ("  named in the Plugins list of {0}" -f (Split-Path -Leaf $f)) Green
    } else {
      $pluginsNeedsEntry = $true
      Note ("  NOT named in the Plugins list of {0} -- Orthanc will not load it." -f (Split-Path -Leaf $f)) Yellow
    }
    break
  }
  if (-not $pluginsFile) {
    Note '  No "Plugins" setting found in the configuration. Orthanc loads nothing by default,' Yellow
    Note '  yet plugins are running, so this script is reading the wrong configuration.' Yellow
    Die 'Could not find the Plugins setting; not guessing at a live archive.'
  }
}

if ($pluginsNeedsEntry) {
  $entry = ($dll[0].FullName -replace '\\','/')
  $backupP = "$pluginsFile.pmcportal-$Stamp"
  $script:NeedsRestart = $true
  if ($Apply) {
    $t = Get-Content $pluginsFile -Raw
    $open = $t.IndexOf('[', $t.IndexOf('"Plugins"'))
    $close = $t.IndexOf(']', $open)
    if ($open -lt 0 -or $close -lt 0) { Die 'The Plugins setting is not a simple array; add ServeFolders.dll to it by hand.' }
    $inner = $t.Substring($open + 1, $close - $open - 1)
    $sep = if ($inner.Trim().Length) { ',' } else { '' }
    Copy-Item $pluginsFile $backupP -Force
    Did ("backed up {0} to {1}" -f (Split-Path -Leaf $pluginsFile), (Split-Path -Leaf $backupP))
    Set-Content -Path $pluginsFile -Value ($t.Insert($close, "$sep`r`n    `"$entry`"`r`n  ")) -Encoding UTF8
    Did ("added ServeFolders.dll to the Plugins list in {0}" -f (Split-Path -Leaf $pluginsFile))
  } else {
    Plan ("back up {0}" -f (Split-Path -Leaf $pluginsFile))
    Plan ("add `"$entry`" to its Plugins list, so Orthanc actually loads ServeFolders")
  }
}

# ------------------------------------------------------------ the config change
Head '4. The /pmc mapping'
$mapPath  = $PortalDir -replace '\\','/'
$dropFile = if ($configIsDir) { Join-Path $configTarget 'pmc-portal-servefolders.json' } else { $null }
$mapJson  = @"
{
  "_comment": "Added by Install-PmcImagingPortal.ps1 on $Stamp. Serves the PMC Imaging Portal at /pmc/. Delete this file and restart Orthanc to remove it.",
  "ServeFolders": {
    "AllowCache": false,
    "GenerateETag": true,
    "Folders": { "/pmc": "$mapPath" }
  }
}
"@

$existingText = ''
if ($configIsDir) {
  foreach ($f in Get-ChildItem $configTarget -Filter '*.json' -ErrorAction SilentlyContinue) {
    $existingText += (Get-Content $f.FullName -Raw)
  }
} else { $existingText = Get-Content $configTarget -Raw }
$alreadyMapped   = $existingText -match '"/pmc"'
$hasServeSection = $existingText -match '"ServeFolders"'

if ($Rollback) {
  if ($dropFile -and (Test-Path $dropFile)) {
    $script:NeedsRestart = $true
    if ($Apply) { Remove-Item $dropFile -Force; Did "removed $dropFile" } else { Plan "remove $dropFile" }
  } elseif (-not $configIsDir) {
    $backups = @(Get-ChildItem $configDir -Filter 'orthanc.json.pmcportal-*' -ErrorAction SilentlyContinue |
                 Sort-Object LastWriteTime -Descending)
    if ($backups.Count) {
      $script:NeedsRestart = $true
      if ($Apply) { Copy-Item $backups[0].FullName $configTarget -Force; Did ("restored {0}" -f $backups[0].Name) }
      else { Plan ("restore {0} over orthanc.json" -f $backups[0].Name) }
    } else { Note '  no backup from this script to restore' Yellow }
  } else { Note '  nothing this script added is present' DarkGray }
}
elseif ($alreadyMapped) { Note '  /pmc is already mapped. Leaving the configuration alone.' Green }
elseif ($hasServeSection) {
  Note '  ServeFolders is already declared somewhere. Two declarations do not merge cleanly,' Yellow
  Note '  so this script will not add a second one.' Yellow
  Note ('  Add   "/pmc": "' + $mapPath + '"   to the existing Folders block, then re-run.') Cyan
  Die 'The existing ServeFolders block needs one line added by hand.'
}
elseif ($configIsDir) {
  $script:NeedsRestart = $true
  if ($Apply) { Set-Content -Path $dropFile -Value $mapJson -Encoding UTF8; Did "wrote $dropFile" }
  else { Plan "write $dropFile, a NEW file; orthanc.json is not touched" }
}
else {
  $script:NeedsRestart = $true
  $backup = "$configTarget.pmcportal-$Stamp"
  $insert = '  "ServeFolders": { "AllowCache": false, "GenerateETag": true, "Folders": { "/pmc": "' + $mapPath + '" } },'
  if ($Apply) {
    # Splice after the opening brace by index. [regex]::Replace has no static
    # overload that takes a count -- passing 1 there binds to RegexOptions and
    # rewrites EVERY brace in the file, which on a live archive's config is the
    # kind of mistake you only get to make once.
    $idx = $existingText.IndexOf('{')
    if ($idx -lt 0) { Die 'orthanc.json does not start with a JSON object; not editing it.' }
    Copy-Item $configTarget $backup -Force; Did ("backed up orthanc.json to {0}" -f (Split-Path -Leaf $backup))
    Set-Content -Path $configTarget -Value ($existingText.Insert($idx + 1, "`r`n$insert")) -Encoding UTF8
    Did 'added the ServeFolders section to orthanc.json'
  } else {
    Plan ("back up orthanc.json to {0}" -f (Split-Path -Leaf $backup))
    Plan 'insert a ServeFolders section at the top of orthanc.json'
  }
}

# --------------------------------------------------------------- write the page
Head '5. Write the page'
if ($Rollback) { Note "  left in place at $PortalDir; it serves nothing on its own" DarkGray }
elseif ($Apply) {
  New-Item $PortalDir -ItemType Directory -Force | Out-Null
  Copy-Item $PortalFile (Join-Path $PortalDir 'index.html') -Force
  Did "wrote $PortalDir\index.html"
  Note '  no pmc-portal.config.json written: the built-in defaults are right for this server' DarkGray
} else { Plan "write $PortalDir\index.html" }

if ($restoreFrom) {
  $script:NeedsRestart = $true
  if ($Apply) { Copy-Item $restoreFrom (Join-Path $pluginDir (Split-Path -Leaf $restoreFrom)) -Force
                Did ("restored {0} to the Plugins folder" -f (Split-Path -Leaf $restoreFrom)) }
  else { Plan "copy $restoreFrom into $pluginDir" }
}

# ------------------------------------------------------------------- restart
function Test-ArchiveUp {
  try {
    $r = Invoke-WebRequest -Uri "$BaseUrl/system" -UseBasicParsing -TimeoutSec 10 -ErrorAction Stop
    return ([int]$r.StatusCode -lt 500)
  } catch {
    # 401 or 403 is the archive answering and asking who you are. That is up.
    if ($_.Exception.Response) { return (([int]$_.Exception.Response.StatusCode) -in @(401,403)) }
    return $false
  }
}
function Restart-OrthancSafely {
  Note '  stopping, and waiting for it to drain'
  # Started BEFORE the stop: Stop-Service blocks until the service reports
  # stopped, so a stopwatch begun after it always reads 0.0 s.
  $sw = [Diagnostics.Stopwatch]::StartNew()
  Stop-Service -Name $ServiceName -Force
  while ((Get-Service $ServiceName).Status -ne 'Stopped' -and $sw.Elapsed.TotalSeconds -lt 60) { Start-Sleep -Milliseconds 300 }
  Note ("  drained in {0:N1} s" -f $sw.Elapsed.TotalSeconds)
  Start-Service -Name $ServiceName
  $sw.Restart()
  while ($sw.Elapsed.TotalSeconds -lt $UpTimeoutSeconds) {
    if (Test-ArchiveUp) { Note ("  answering by name after {0:N1} s" -f $sw.Elapsed.TotalSeconds) Green; return $true }
    Start-Sleep -Seconds 2
  }
  return $false
}

Head '6. Restart'
if (-not $script:NeedsRestart) {
  Note '  Not needed. Nothing changed that Orthanc reads at start-up, and ServeFolders' Green
  Note '  serves the page off disk on every request, so the new file is already live.' Green
}
elseif (-not $Apply) { Plan "restart $ServiceName and prove $BaseUrl/system answers by name" }
else {
  if (-not (Restart-OrthancSafely)) {
    Note '  Orthanc did not answer in time. Reversing the configuration change.' Red
    if ($dropFile -and (Test-Path $dropFile)) { Remove-Item $dropFile -Force; Note '  removed the mapping file' Yellow }
    elseif (-not $configIsDir) {
      $b = @(Get-ChildItem $configDir -Filter "orthanc.json.pmcportal-$Stamp" -ErrorAction SilentlyContinue)
      if ($b.Count) { Copy-Item $b[0].FullName $configTarget -Force; Note '  restored orthanc.json' Yellow }
    }
    Restart-OrthancSafely | Out-Null
    Die 'Rolled back. The archive matters more than the portal; read the Orthanc log before trying again.'
  }
}

# --------------------------------------------------------------------- proof
Head '7. Proof'
function Get-Code {
  param([string]$Url)
  $a = @{ Uri = $Url; UseBasicParsing = $true; TimeoutSec = 15; ErrorAction = 'Stop' }
  if ($Credential) { $a.Credential = $Credential }
  try { return [int](Invoke-WebRequest @a).StatusCode }
  catch { if ($_.Exception.Response) { return [int]$_.Exception.Response.StatusCode }; return 0 }
}
if (-not $Apply) { Note '  nothing to prove in a preview' DarkGray }
else {
  $real = Get-Code "$BaseUrl/pmc/index.html"
  # A control path that cannot exist. If it answers the same as the real one,
  # the answer is about authentication, not about whether the page is served.
  $control = Get-Code ("$BaseUrl/pmc/__not-here-" + [guid]::NewGuid().ToString('N') + '.html')
  if ($real -eq 200) { Note "  $BaseUrl/pmc/ is being served." Green }
  elseif ($real -eq 404) { Note '  404. ServeFolders is not mapping /pmc. Check the Orthanc log for the plugin loading.' Red }
  elseif ($real -eq 0) { Note "  No answer from $BaseUrl. Check DNS and the firewall rule." Red }
  elseif ($real -eq $control) {
    Note ("  HTTP {0} for the page and for a path that cannot exist, so that proves nothing:" -f $real) Yellow
    Note '  Orthanc answers 401 to any unauthenticated request, present or absent.' Yellow
    # Ask for a credential here rather than sending the operator away to re-run
    # the whole thing. Declining just leaves the proof unproven; it changes
    # nothing either way, and the work above is already done.
    if ([Environment]::UserInteractive) {
      Note '  Sign in and it can be proven now. Cancel to skip; nothing further will change.' Cyan
      $Credential = Get-Credential -Message "Orthanc sign-in, to prove $BaseUrl/pmc/ is served"
      if ($Credential) {
        $real2 = Get-Code "$BaseUrl/pmc/index.html"
        if ($real2 -eq 200) { Note "  $BaseUrl/pmc/ is being served." Green }
        elseif ($real2 -eq 404) { Note '  404. ServeFolders is not mapping /pmc. Check the Orthanc log for the plugin loading.' Red }
        elseif ($real2 -eq 401) { Note '  401 with that sign-in. The page is there; those credentials were not accepted.' Yellow }
        else { Note ("  HTTP {0} from {1}/pmc/index.html" -f $real2, $BaseUrl) Yellow }
      } else { Note '  Skipped. Open the page in a browser to see for yourself.' DarkGray }
    } else {
      Note '  Re-run the proof with a credential:' Yellow
      Note '  .\Install-PmcImagingPortal.ps1 -Apply -Credential (Get-Credential)' Cyan
    }
  }
  else { Note ("  HTTP {0} for the page, {1} for a path that cannot exist -- it is being served." -f $real, $control) Green }
}

Head 'Summary'
if (-not $Apply) {
  Note '  This was a preview. Nothing was changed.' Green
  Note ("  {0} change(s) would be made. Re-run with -Apply to make them." -f $script:Changes.Count)
} else {
  Note ("  {0} change(s) made{1}." -f $script:Changes.Count, $(if ($script:NeedsRestart) { ', including a service restart' } else { '; no restart was needed' })) Green
  Note '  Open it signed in as a normal user and check one study per modality:'
  Note ("  {0}/pmc/" -f $BaseUrl) Cyan
  Note '  To undo:  .\Install-PmcImagingPortal.ps1 -Rollback -Apply'
}

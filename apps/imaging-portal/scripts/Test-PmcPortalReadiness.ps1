<#
.SYNOPSIS
  Read-only readiness probe for the PMC Imaging Portal and its built-in viewer.

.DESCRIPTION
  Answers the one question the test suite cannot: will the viewer work on THIS
  archive? Everything in apps/imaging-portal is tested against a stand-in
  Orthanc. This asks the real one.

  It CHANGES NOTHING. No file is written, no configuration is touched, no
  service is restarted, and it never sends OrderBy (the ODBC index answers
  HTTP 500 to it). It issues GET requests and one POST to /tools/find, which is
  what the portal itself does on every page load.

  It prints NO patient identifier: modality, counts, timings and HTTP statuses
  only. Credentials are prompted for and never written anywhere.

  STATUS: NOT VERIFIED — written 9 Sep 2026, never executed.

.PARAMETER BaseUrl
  The archive, by name, with certificate validation. Default https://imaging.pmcne.ph

.PARAMETER Modalities
  Which modalities to sample. One recent study of each is probed.

.EXAMPLE
  .\Test-PmcPortalReadiness.ps1
  .\Test-PmcPortalReadiness.ps1 -BaseUrl https://imaging.pmcne.ph -Modalities XA,CT,CR
#>
[CmdletBinding()]
param(
  [string]   $BaseUrl    = 'https://imaging.pmcne.ph',
  [string[]] $Modalities = @('XA','CT','CR','US','MR','DX'),
  [int]      $DaysBack   = 120,
  [pscredential] $Credential
)

$ErrorActionPreference = 'Stop'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$BaseUrl = $BaseUrl.TrimEnd('/')

if (-not $Credential) {
  $Credential = Get-Credential -Message "Orthanc sign-in for $BaseUrl (read-only use; not stored)"
}

function Invoke-Orthanc {
  param([string]$Path, [string]$Method = 'GET', $Body)
  $uri = "$BaseUrl/$($Path.TrimStart('/'))"
  $sw  = [Diagnostics.Stopwatch]::StartNew()
  $req = @{ Uri = $uri; Method = $Method; Credential = $Credential; TimeoutSec = 60
            UseBasicParsing = $true; ErrorAction = 'Stop' }
  if ($Body) { $req.Body = ($Body | ConvertTo-Json -Depth 6); $req.ContentType = 'application/json' }
  try {
    $r = Invoke-WebRequest @req
    $sw.Stop()
    [pscustomobject]@{ ok = $true; status = [int]$r.StatusCode; ms = [int]$sw.ElapsedMilliseconds
                       bytes = $r.RawContentLength; content = $r.Content; type = $r.Headers['Content-Type'] }
  } catch {
    $sw.Stop()
    $code = 0
    if ($_.Exception.Response) { $code = [int]$_.Exception.Response.StatusCode }
    [pscustomobject]@{ ok = $false; status = $code; ms = [int]$sw.ElapsedMilliseconds
                       bytes = 0; content = $null; type = $null; error = $_.Exception.Message }
  }
}

function Say { param($Text, $Colour = 'Gray') Write-Host $Text -ForegroundColor $Colour }
function Head { param($Text) Write-Host ''; Write-Host $Text -ForegroundColor Cyan
                Write-Host ('-' * $Text.Length) -ForegroundColor DarkGray }

Head "1. The archive"
$sys = Invoke-Orthanc 'system'
if (-not $sys.ok) { Say "  CANNOT REACH $BaseUrl -- $($sys.error)" Red; Say "  Nothing below can be trusted. Stop here." Red; return }
$s = $sys.content | ConvertFrom-Json
Say ("  {0}   Orthanc {1}   API {2}" -f $s.Name, $s.Version, $s.ApiVersion) Green
Say ("  index: {0}" -f ($(if ($s.DatabaseBackendPlugin) { $s.DatabaseBackendPlugin } else { 'built-in SQLite' })))
$ver = $null
try { $ver = [version]($s.Version -replace '[^0-9.].*$','') } catch { Say "  version '$($s.Version)' is not a number -- /numpy support unknown." Yellow }
if ($ver -and $ver -lt [version]'1.11.0') {
  Say "  Orthanc is older than 1.11.0, so /numpy does not exist here." Yellow
  Say "  The viewer will run on the server-rendered path: correct pictures, no Hounsfield probe," Yellow
  Say "  no region statistics, and one round trip per window change." Yellow
}

Head "2. Plugins"
$plugins = @()
$pl = Invoke-Orthanc 'plugins'
if ($pl.ok) { $plugins = $pl.content | ConvertFrom-Json; Say ("  loaded: {0}" -f ($plugins -join ', ')) }
$serve = $plugins -contains 'serve-folders'
if ($serve) { Say "  ServeFolders IS loaded -- the portal can be served." Green }
else {
  Say "  ServeFolders is NOT loaded. Until it is, writing the portal file serves nothing." Yellow
  Say "  Note this is about the Plugins LIST, not the folder: Orthanc loads what its" Yellow
  Say "  `"Plugins`" setting names, and the 2 Sep cutover rewrote that list to 8 entries." Yellow
}
foreach ($want in @('dicom-web','ohif','stone-webviewer','gdcm')) {
  if ($plugins -contains $want) { Say ("  {0}: present" -f $want) }
  else { Say ("  {0}: absent" -f $want) Yellow }
}

Head "3. On disk (this machine only)"
$plugDir = 'C:\Program Files\Orthanc Server\Plugins'
$cfgPath = 'C:\Program Files\Orthanc Server\Configuration\orthanc.json'
if (Test-Path $plugDir) {
  $dll = @(Get-ChildItem $plugDir -Filter '*ServeFolders*' -ErrorAction SilentlyContinue)
  if ($dll.Count) { Say ("  ServeFolders DLL present: {0}" -f $dll[0].Name) Green }
  else { Say "  ServeFolders DLL is NOT in $plugDir -- restore it from the install media or the cutover backup." Yellow }
} else { Say "  $plugDir not found (not running on the Orthanc host?)" DarkGray }
if (Test-Path $cfgPath) {
  $raw = Get-Content $cfgPath -Raw
  if ($raw -match '"ServeFolders"') { Say "  orthanc.json has a ServeFolders section." Green }
  else { Say "  orthanc.json has NO ServeFolders section." Yellow }
  if ($raw -match '(?s)"Plugins"\s*:\s*\[(.*?)\]') {
    $listed = @([regex]::Matches($Matches[1], '"([^"]+)"') | ForEach-Object { Split-Path -Leaf $_.Groups[1].Value })
    Say ("  Plugins list names {0}: {1}" -f $listed.Count, ($listed -join ', '))
    if ($listed -notcontains 'ServeFolders.dll') {
      Say '  ServeFolders.dll is NOT in that list, which is exactly why it is not loaded.' Yellow
      Say '  The installer adds it, with a backup of the file it edits.' Cyan
    }
  } else { Say '  No "Plugins" array found in orthanc.json (it may live in another file in the directory).' DarkGray }
  if ($raw -match '"DataSource"\s*:\s*"([^"]+)"') {
    Say ("  OHIF.DataSource = {0}" -f $Matches[1])
    if ($Matches[1] -eq 'dicom-web') { Say "    -> the portal's default OHIF route is correct for this server." Green }
    else { Say "    -> set viewers.ohif in pmc-portal.config.json to the dicomjson route." Yellow }
  }
} else { Say "  $cfgPath not found (not running on the Orthanc host?)" DarkGray }

Head "4. Can the viewer read pixels from real studies?"
Say "  One recent study per modality. No identifier is printed." DarkGray
$from = (Get-Date).AddDays(-$DaysBack).ToString('yyyyMMdd')
$to   = (Get-Date).ToString('yyyyMMdd')
$rows = @()
foreach ($mod in $Modalities) {
  # Exactly the query shape the portal sends. No OrderBy, ever.
  $find = Invoke-Orthanc 'tools/find' 'POST' @{
    Level = 'Study'; Expand = $true; Limit = 1
    Query = @{ StudyDate = "$from-$to"; ModalitiesInStudy = $mod }
  }
  if (-not $find.ok) {
    if ($find.status -eq 500) { Say ("  {0}: /tools/find returned 500 -- read the Orthanc log before going further." -f $mod) Red }
    else { Say ("  {0}: /tools/find failed ({1})" -f $mod, $find.status) Yellow }
    continue
  }
  $studies = @($find.content | ConvertFrom-Json)
  if (-not @($studies).Count) { Say ("  {0}: no study in the last {1} days" -f $mod, $DaysBack) DarkGray; continue }
  Say ("  {0}: /tools/find returned {1} study(s), {2}" -f $mod, @($studies).Count, (Shape $studies)) DarkGray
  $study = $studies[0]

  # A listing can come back as objects or as bare id strings. Take the id either
  # way, and SAY which shape it was -- a script that reads .ID off a string gets
  # $null, asks for `series//instances`, and reports a 404 that explains nothing.
  function Get-Id { param($Item) if ($Item -is [string]) { $Item } else { $Item.ID } }
  function Shape  { param($Arr) if (-not @($Arr).Count) { 'empty' }
                    elseif ($Arr[0] -is [string]) { 'ids only' } else { 'expanded' } }

  if (-not $study.ID) {
    Say ("  {0}: /tools/find returned {1} -- no study id to follow." -f $mod, (Shape $studies)) Red
    Say ("       raw: {0}" -f $find.content.Substring(0, [Math]::Min(220, $find.content.Length))) DarkGray
    Say '       The portal sends Expand and needs the id. This is the first thing to fix.' Red
    continue
  }

  $ser = Invoke-Orthanc "studies/$($study.ID)/series?expand"
  if (-not $ser.ok) { Say ("  {0}: series listing failed ({1})" -f $mod, $ser.status) Yellow; continue }
  $series = @($ser.content | ConvertFrom-Json)
  if (-not $series.Count) { Say ("  {0}: study has no series" -f $mod) Yellow; continue }
  $serShape = Shape $series
  $sid = Get-Id $series[0]

  $inst = Invoke-Orthanc "series/$sid/instances?expand"
  if (-not $inst.ok) { Say ("  {0}: instance listing failed ({1}) for series {2}" -f $mod, $inst.status, $sid) Yellow; continue }
  $instances = @($inst.content | ConvertFrom-Json)
  if (-not $instances.Count) { Say ("  {0}: series has no instances" -f $mod) Yellow; continue }
  $instShape = Shape $instances
  $iid = Get-Id $instances[[int]($instances.Count / 2)]

  $tags     = Invoke-Orthanc "instances/$iid/simplified-tags"
  $numpy    = Invoke-Orthanc "instances/$iid/frames/0/numpy?rescale=0&compress=0"
  $rendered = Invoke-Orthanc "instances/$iid/frames/0/rendered"
  $preview  = Invoke-Orthanc "instances/$iid/preview"

  $path = if ($numpy.ok) { 'pixel data' } elseif ($rendered.ok) { 'server rendered' } elseif ($preview.ok) { 'preview only' } else { 'NOTHING WORKS' }
  $colour = switch ($path) { 'pixel data' { 'Green' } 'server rendered' { 'Yellow' } 'preview only' { 'Yellow' } default { 'Red' } }

  $spacing = '-'
  if ($tags.ok) {
    $t = $tags.content | ConvertFrom-Json
    if ($t.PixelSpacing) { $spacing = $t.PixelSpacing }
    elseif ($t.ImagerPixelSpacing) { $spacing = "$($t.ImagerPixelSpacing) (detector)" }
  }

  Say ("  {0,-3}  series {1,4} inst   viewer path: {2}   listings: {3}/{4}" -f `
       $mod, $instances.Count, $path, $serShape, $instShape) $colour
  Say ("       list {0,5} ms   tags {1,4} ms   numpy {2,5} ms/{3}   rendered {4,4} ms/{5}   spacing {6}" -f `
       $inst.ms, $tags.ms, $numpy.ms, $(if($numpy.ok){"$([int]($numpy.bytes/1024)) KB"}else{"HTTP $($numpy.status)"}), `
       $rendered.ms, $(if($rendered.ok){"$([int]($rendered.bytes/1024)) KB"}else{"HTTP $($rendered.status)"}), $spacing) DarkGray

  $rows += [pscustomobject]@{ Modality = $mod; Instances = $instances.Count; Path = $path
                              Series = $serShape; Inst = $instShape
                              ListMs = $inst.ms; NumpyMs = $numpy.ms; RenderedMs = $rendered.ms
                              PixelSpacing = $spacing }
}

Head "5. Verdict"
if (-not @($rows).Count) { Say "  Nothing could be probed. Do not deploy on this evidence." Red; return }
$best = $rows | Where-Object { $_.Path -eq 'pixel data' }
Say ("  {0} of {1} modalities reach the pixel-data path (Hounsfield probe, region statistics, instant window/level)." -f @($best).Count, @($rows).Count)
$none = @($rows | Where-Object { $_.Path -eq 'NOTHING WORKS' })
if ($none.Count) { Say ("  NO path works for: {0}. Investigate before deploying." -f (($none.Modality) -join ', ')) Red }
$slow = @($rows | Where-Object { $_.NumpyMs -gt 1500 })
if ($slow.Count) { Say ("  Slow pixel fetch (>1.5 s) for: {0}. Cine and MPR will feel it." -f (($slow.Modality) -join ', ')) Yellow }
if (-not $serve) { Say '  BLOCKER: ServeFolders is not loaded. The installer fixes this; it is not fatal.' Yellow }
$flat = @($rows | Where-Object { $_.Series -eq 'ids only' -or $_.Inst -eq 'ids only' })
if ($flat.Count) {
  Say ('  This archive returns id-only listings even for ?expand on: {0}.' -f (($flat.Modality) -join ', ')) Yellow
  Say '  The portal handles that, at the cost of one request per child. Expect the study' Yellow
  Say '  sheet and the viewer to open more slowly on large series.' Yellow
}
Write-Host ''
$rows | Format-Table -AutoSize
Write-Host ''
Say "  Nothing was changed by this script." DarkGray

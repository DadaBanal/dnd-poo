# The pickup's delta-link safety (9 Oct 2026), exercised on its own functions:
# they are lifted out of Invoke-PmcMailPickup.ps1 itself, so this tests the
# script as shipped. Prints PASS/FAIL lines; exits 1 on any FAIL.
param([Parameter(Mandatory = $true)] [string] $Script, [Parameter(Mandatory = $true)] [string] $Work)
Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'
$errors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile($Script, [ref] $null, [ref] $errors)
if ($errors -and $errors.Count) { Write-Host "FAIL  the script parses: $($errors[0].Message)"; exit 1 }
Write-Host 'PASS  the script parses'
$want = 'Write-Log', 'Test-DeltaLink', 'Save-DeltaLink', 'Get-RecoverFrom', 'Read-DeltaLink'
foreach ($fn in $ast.FindAll({ param($n) $n -is [System.Management.Automation.Language.FunctionDefinitionAst] }, $true)) {
    if ($want -contains $fn.Name) { . ([ScriptBlock]::Create($fn.Extent.Text)) }
}
$script:fails = 0
function Check([bool] $Ok, [string] $What) { if ($Ok) { Write-Host "PASS  $What" } else { Write-Host "FAIL  $What"; $script:fails++ } }

New-Item -ItemType Directory -Force -Path $Work | Out-Null
$DeltaFile = Join-Path $Work 'inbox-deltalink-helpdesk-pmcne-ph.txt'
$LogFile = Join-Path $Work 'mail-pickup.log'
$Since = Get-Date
$Apply = $true
$link1 = 'https://graph.microsoft.com/v1.0/users/x/mailFolders/inbox/messages/delta?$deltatoken=AAA'
$link2 = 'https://graph.microsoft.com/v1.0/users/x/mailFolders/inbox/messages/delta?$deltatoken=BBB'

$r = Read-DeltaLink
Check (-not $r.Uri -and -not $r.From) 'no link at all: a first run, from -Since'

Save-DeltaLink $link1
Save-DeltaLink $link2
Check ((Get-Content $DeltaFile -Raw).Trim() -eq $link2) 'a saved link reads back as written'
Check ((Get-Content "$DeltaFile.prev" -Raw).Trim() -eq $link1) 'the link before is kept as .prev'
Check (-not (Test-Path "$DeltaFile.tmp")) 'no temporary file is left behind'
Check ((Read-DeltaLink).Uri -eq $link2) 'a good link is carried on from'

# what the 6008 shutdown left: the file at its size, every byte NUL
[IO.File]::WriteAllBytes($DeltaFile, (New-Object byte[] 407))
Check (-not (Test-DeltaLink ([IO.File]::ReadAllText($DeltaFile)))) 'a NUL-filled link is not a link'
$Apply = $false
$r = Read-DeltaLink
Check ($r.Uri -eq $link1 -and (Test-Path $DeltaFile)) 'preview: carries on from .prev and moves nothing'
$Apply = $true
$r = Read-DeltaLink
Check ($r.Uri -eq $link1) 'a NUL-filled link: carries on from .prev, no failure'
Check (-not (Test-Path $DeltaFile) -and @(Get-ChildItem $Work -Filter '*.bad-*').Count -eq 1) 'the bad file is set aside, not deleted'

# both lost: read a window from two hours before the last good save
Remove-Item "$DeltaFile.prev"
[IO.File]::WriteAllBytes($DeltaFile, (New-Object byte[] 406))
$saved = (Get-Date).AddHours(-5)
(Get-Item $DeltaFile).LastWriteTime = $saved
$r = Read-DeltaLink
Check (-not $r.Uri -and $r.From -and [Math]::Abs(($r.From - $saved.AddHours(-2)).TotalMinutes) -lt 1) 'nothing readable: reads from two hours before the last save'
Check ($r.From -le $Since) 'and never later than -Since'

Save-DeltaLink $link1
Check ((Read-DeltaLink).Uri -eq $link1) 'the next good save is read again normally'
$old = (Get-Date).AddDays(-30)
Check ((Get-RecoverFrom $old) -ge (Get-Date).AddDays(-14).AddMinutes(-1)) 'a window is never more than 14 days back'
if ($script:fails) { exit 1 }
exit 0

<#
.SYNOPSIS
    Create the desk's own read-only SQL login for BizBox. It never touches BizBox's own logins.

.DESCRIPTION
    BizBox step 3 (docs/handoffs/HANDOFF-cloud-sql01-WS36-20260929-bizbox.md). SQL01, 29 Sep 2026; Dada ran it
    on DND-SQL01 at 11:40 (Reply, part 3). Run it elevated, as yourself (a sysadmin), never as the desk's task
    account. On DND-SQL01 it lives in D:\psa\bin; this is the same file.

    With -Apply it:
      1. creates SQL login psa_bizbox_reader with a random 32-character password that no person sees or types;
      2. gives it a user in LiveDB_PMC with SELECT on schema psa (the four desk views) and nothing else;
      3. writes the ODBC connection string to D:\psa\bizbox.odbc, which takes D:\psa's ACL (SYSTEM,
         Administrators, the desk's task account), and shows who can open it;
      4. proves the Pass by logging in AS the new login through that file: the views read; the base tables,
         psDatacenter and the name function are refused; it is neither sysadmin nor db_owner.

    What it deliberately does NOT do:
      - use or change bizboxsa, BizBox's own login (db_owner, BizBox's live sessions run on it);
      - grant any role, any write, or anything outside schema psa;
      - print or log the password. It exists only in the file on the host.

    PREVIEW BY DEFAULT. Without -Apply it runs the preflight and changes nothing.
    -Undo -Apply drops the user and the login and deletes the file (-Undo alone says what it would do).

.EXAMPLE
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\New-PsaBizboxLogin.ps1
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\New-PsaBizboxLogin.ps1 -Apply
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\New-PsaBizboxLogin.ps1 -Undo -Apply
#>
[CmdletBinding()]
param([switch]$Apply, [switch]$Undo)
$ErrorActionPreference = 'Stop'

$LoginName = 'psa_bizbox_reader'
$Server    = 'DND-SQL01\PMC_SS'
$OdbcFile  = 'D:\psa\bizbox.odbc'
$LogFile   = 'D:\psa\logs\New-PsaBizboxLogin.log'
$Views     = @('vw_product', 'vw_purchase_order', 'vw_purchase_order_line', 'vw_invoice')

function Write-Step([string]$Text) {
    $line = (Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + '  ' + $Text
    Write-Host $line
    Add-Content -Path $LogFile -Value $line -Encoding UTF8
}

function Invoke-AdminSql([string]$Database, [string]$Sql) {
    $cs = 'Server=' + $Server + ';Database=' + $Database + ';Integrated Security=SSPI;Encrypt=True;TrustServerCertificate=True'
    $cn = New-Object System.Data.SqlClient.SqlConnection $cs
    $cn.Open()
    try {
        $cmd = $cn.CreateCommand(); $cmd.CommandText = $Sql; $cmd.CommandTimeout = 60
        $r = $cmd.ExecuteScalar()
        return $r
    } finally { $cn.Close() }
}

# --- who is running this
$me = [Security.Principal.WindowsIdentity]::GetCurrent()
if ($me.Name -match '\\psa_desk$') { throw 'Run this as yourself, not as the desk task account. Nothing was done.' }
$elevated = ([Security.Principal.WindowsPrincipal]$me).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $elevated) { throw 'Run this from an elevated PowerShell (Run as administrator). Nothing was done.' }
Write-Step ('start as ' + $me.Name + $(if ($Undo) { ' (-Undo)' } else { '' }) + $(if ($Apply) { ' (-Apply)' } else { ' (preview: nothing is changed)' }))

# --- undo
if ($Undo) {
    if (-not $Apply) { Write-Step ('would drop user and login ' + $LoginName + ' and delete ' + $OdbcFile + ' (preview; -Undo -Apply does it)'); return }
    Invoke-AdminSql 'LiveDB_PMC' ("IF USER_ID(N'" + $LoginName + "') IS NOT NULL DROP USER [" + $LoginName + "]") | Out-Null
    Invoke-AdminSql 'master' ("IF SUSER_ID(N'" + $LoginName + "') IS NOT NULL DROP LOGIN [" + $LoginName + "]") | Out-Null
    if (Test-Path $OdbcFile) { Remove-Item $OdbcFile -Force }
    Write-Step 'undone: user and login dropped, connection-string file deleted'
    return
}

# --- preflight (changes nothing)
$fail = @()
if ((Invoke-AdminSql 'master' 'SELECT IS_SRVROLEMEMBER(''sysadmin'')') -ne 1) { $fail += 'this account is not sysadmin on ' + $Server }
if ((Invoke-AdminSql 'master' 'SELECT CAST(SERVERPROPERTY(''IsIntegratedSecurityOnly'') AS int)') -ne 0) { $fail += 'the instance accepts Windows logins only' }
if ((Invoke-AdminSql 'master' ("SELECT COUNT(*) FROM sys.server_principals WHERE name = N'" + $LoginName + "'")) -ne 0) { $fail += 'login ' + $LoginName + ' already exists (-Undo -Apply first to start again)' }
if ((Invoke-AdminSql 'LiveDB_PMC' ("SELECT COUNT(*) FROM sys.database_principals WHERE name = N'" + $LoginName + "'")) -ne 0) { $fail += 'a user ' + $LoginName + ' already exists in LiveDB_PMC' }
$viewCount = Invoke-AdminSql 'LiveDB_PMC' ("SELECT COUNT(*) FROM sys.views v JOIN sys.schemas s ON s.schema_id = v.schema_id WHERE s.name = 'psa' AND v.name IN ('" + ($Views -join "','") + "')")
if ($viewCount -ne 4) { $fail += 'LiveDB_PMC has ' + $viewCount + ' of the 4 psa views (step 2 first)' }
if (Test-Path $OdbcFile) { $fail += $OdbcFile + ' already exists' }
if ($fail.Count) { foreach ($f in $fail) { Write-Step ('  BLOCKED: ' + $f) }; Write-Step 'RESULT: BLOCKED. Nothing was changed.'; exit 1 }
Write-Step 'preflight: sysadmin yes; SQL logins accepted; no login or user of that name; 4 psa views; no file yet'
if (-not $Apply) { Write-Step 'RESULT: preflight PASS. Nothing was changed (preview; -Apply creates the login).'; return }

# --- a password nobody sees: 32 characters from a cryptographic generator, none that an ODBC string or T-SQL quotes
$chars = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789-_.!#%+'.ToCharArray()
$rng = New-Object System.Security.Cryptography.RNGCryptoServiceProvider
do {
    $bytes = New-Object byte[] 32; $rng.GetBytes($bytes)
    $pw = -join ($bytes | ForEach-Object { $chars[$_ % $chars.Length] })
} until ($pw -cmatch '[A-Z]' -and $pw -cmatch '[a-z]' -and $pw -match '[0-9]' -and $pw -match '[-_.!#%+]')

# --- the login and its one grant
try {
    Invoke-AdminSql 'master' ("CREATE LOGIN [" + $LoginName + "] WITH PASSWORD = N'" + $pw + "', CHECK_POLICY = ON, CHECK_EXPIRATION = OFF, DEFAULT_DATABASE = [LiveDB_PMC]") | Out-Null
    Write-Step ('login created: ' + $LoginName + ' (policy checked, no expiry, default database LiveDB_PMC)')
    Invoke-AdminSql 'LiveDB_PMC' ("CREATE USER [" + $LoginName + "] FOR LOGIN [" + $LoginName + "] WITH DEFAULT_SCHEMA = psa; GRANT SELECT ON SCHEMA::psa TO [" + $LoginName + "];") | Out-Null
    Write-Step 'LiveDB_PMC: user created, SELECT on schema psa granted, nothing else'
} catch {
    Write-Step ('FAILED: ' + $_.Exception.Message)
    Write-Step 'Putting it back: dropping whatever was created.'
    Invoke-AdminSql 'LiveDB_PMC' ("IF USER_ID(N'" + $LoginName + "') IS NOT NULL DROP USER [" + $LoginName + "]") | Out-Null
    Invoke-AdminSql 'master' ("IF SUSER_ID(N'" + $LoginName + "') IS NOT NULL DROP LOGIN [" + $LoginName + "]") | Out-Null
    Write-Step 'RESULT: FAILED, put back. Tell SQL01 the line above.'
    exit 2
}

# --- the connection string, on the host only
$odbc = 'Driver={ODBC Driver 17 for SQL Server};Server=' + $Server + ';Database=LiveDB_PMC;UID=' + $LoginName + ';PWD=' + $pw + ';Encrypt=yes;TrustServerCertificate=yes;ApplicationIntent=ReadOnly'
[IO.File]::WriteAllText($OdbcFile, $odbc, (New-Object System.Text.UTF8Encoding $false))
$pw = $null
$who = (Get-Acl $OdbcFile).Access | ForEach-Object { [string]$_.IdentityReference + ' ' + $_.FileSystemRights }
Write-Step ('written: ' + $OdbcFile + '; who can open it: ' + ($who -join '; '))

# --- the Pass, as the new login, through the same ODBC driver the desk uses
$pass = $true
$cn = New-Object System.Data.Odbc.OdbcConnection ([IO.File]::ReadAllText($OdbcFile))
$cn.Open()
function Test-Query([string]$Sql) {
    $cmd = $cn.CreateCommand(); $cmd.CommandText = $Sql
    try { return @{ ok = $true; value = $cmd.ExecuteScalar() } } catch { return @{ ok = $false; value = $_.Exception.Message } }
}
foreach ($v in $Views) {
    $r = Test-Query ('SELECT COUNT_BIG(*) FROM psa.' + $v)
    if ($r.ok) { Write-Step ('  PASS: psa.' + $v + ' reads, ' + $r.value + ' rows') } else { Write-Step ('  FAIL: psa.' + $v + ': ' + $r.value); $pass = $false }
}
foreach ($t in @('dbo.iwPOinv', 'dbo.iwItems', 'dbo.faVendors', 'dbo.psDatacenter')) {
    $r = Test-Query ('SELECT TOP 1 1 FROM ' + $t)
    if (-not $r.ok -and $r.value -match 'permission was denied') { Write-Step ('  PASS: ' + $t + ' refused') } else { Write-Step ('  FAIL: ' + $t + ' was not refused'); $pass = $false }
}
$r = Test-Query 'SELECT dbo.udf_GetFullName(1)'
if (-not $r.ok -and $r.value -match 'permission was denied') { Write-Step '  PASS: dbo.udf_GetFullName called directly: refused' } else { Write-Step '  FAIL: dbo.udf_GetFullName was not refused'; $pass = $false }
$r = Test-Query 'SELECT CAST(IS_SRVROLEMEMBER(''sysadmin'') AS int) * 10 + CAST(IS_MEMBER(''db_owner'') AS int)'
if ($r.ok -and [int]$r.value -eq 0) { Write-Step '  PASS: neither sysadmin nor db_owner' } else { Write-Step ('  FAIL: role check gave ' + $r.value); $pass = $false }
$cn.Close()

if ($pass) { Write-Step 'RESULT: PASS. Tell SQL01 "bizbox login done".' } else { Write-Step 'RESULT: FAIL. Tell SQL01 the FAIL lines; -Undo puts everything back.'; exit 4 }

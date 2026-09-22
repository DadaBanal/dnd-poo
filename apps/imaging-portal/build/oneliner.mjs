#!/usr/bin/env node
/**
 * Emit a single-line PowerShell that puts the portal on the server.
 *
 * Deliberately does LESS than the full installer: it writes one file into a new
 * directory and nothing else. No service restart, no config edit, no touching
 * orthanc.json. The blast radius is a folder you can delete.
 *
 * It refuses to write unless the decoded payload hashes to the expected value,
 * so a truncated paste writes nothing rather than half a page.
 *
 * It also LOOKS before it prints the ServeFolders advice. MEASURED 9 Sep 2026
 * from the cutover handoff (`docs/orthanc-cutover-handoff-20260902.md`): the
 * 2 Sep HTTPS cutover kept 8 plugins and dropped 23, and ServeFolders is on the
 * dropped list. So on PMC-ORTHANC01 as it stands, writing the file is not
 * enough -- nothing would serve it. The line now says which of the two states
 * the server is actually in, instead of assuming the happy one.
 *
 *   node build/oneliner.mjs [targetDir]     default C:\PMC\portal
 */
import { readFileSync, writeFileSync } from 'node:fs';
import { gzipSync } from 'node:zlib';
import { createHash } from 'node:crypto';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const manifest = JSON.parse(readFileSync(join(ROOT, 'build/manifest.json'), 'utf8'));
const html = readFileSync(join(ROOT, 'dist', manifest.artifact));
const sha = createHash('sha256').update(html).digest('hex');
const b64 = gzipSync(html, { level: 9, mtime: 0 }).toString('base64');
const dir = (process.argv[2] || 'C:\\PMC\\portal').replace(/\\$/, '');

// PowerShell 5.1, single line, no exit (an exit in a pasted line closes the window).
const ps = [
  `$b='${b64}'`,
  `$d='${dir}'`,
  `$want='${sha}'`,
  `$ms=New-Object IO.MemoryStream(,[Convert]::FromBase64String($b))`,
  `$gz=New-Object IO.Compression.GzipStream($ms,[IO.Compression.CompressionMode]::Decompress)`,
  `$o=New-Object IO.MemoryStream`,
  `$gz.CopyTo($o)`,
  `$by=$o.ToArray()`,
  `$gz.Dispose()`,
  `$ms.Dispose()`,
  `$h=[BitConverter]::ToString([Security.Cryptography.SHA256]::Create().ComputeHash($by)).Replace('-','').ToLower()`,
  `if($h -ne $want){Write-Warning "PAYLOAD MISMATCH - nothing written. got $h want $want"}` +
    `else{New-Item $d -ItemType Directory -Force|Out-Null;` +
    `[IO.File]::WriteAllBytes((Join-Path $d 'index.html'),$by);` +
    `Write-Host "OK  $($by.Length) bytes  sha256 $h" -ForegroundColor Green;` +
    `Write-Host "wrote $d\\index.html";` +
    `Write-Host "";` +
    // Read-only look at the server's own state. No credentials needed, and
    // nothing is changed either way.
    `$pl=@(Get-ChildItem 'C:\\Program Files\\Orthanc Server\\Plugins' -Filter '*ServeFolders*' -EA 0).Count;` +
    `$cf='C:\\Program Files\\Orthanc Server\\Configuration\\orthanc.json';` +
    `$cfg=if(Test-Path $cf){Get-Content $cf -Raw -EA 0}else{''};` +
    `$hasCfg=$cfg -match '\"ServeFolders\"';` +
    `if($pl -eq 0){Write-Warning 'ServeFolders.dll is NOT in the Plugins folder. The 2 Sep cutover dropped it, so nothing will serve this file yet.';` +
    `Write-Host 'Restore it from the Orthanc install media (or Configuration.bak) into the Plugins folder first.' -ForegroundColor Yellow}` +
    `elseif(-not $hasCfg){Write-Host 'ServeFolders.dll is present but orthanc.json has no ServeFolders section.' -ForegroundColor Yellow}` +
    `else{Write-Host 'ServeFolders is loaded and configured.' -ForegroundColor Green};` +
    `Write-Host "";` +
    `Write-Host "Orthanc is NOT changed. To serve it, orthanc.json needs:";` +
    `Write-Host '    \"ServeFolders\": { \"Folders\": { \"/pmc\": \"${dir.replace(/\\/g, '/')}\" } }' -ForegroundColor Cyan;` +
    `Write-Host "then restart the Orthanc service in a quiet window (it drained in 6.9 s on 2 Sep)."}`,
].join(';');

const out = join(ROOT, 'dist', 'Deploy-PmcImagingPortal-OneLine.ps1');
writeFileSync(out, ps + '\n');
console.log(`wrote dist/Deploy-PmcImagingPortal-OneLine.ps1`);
console.log(`  artifact ${html.length} bytes, sha256 ${sha}`);
console.log(`  command  ${ps.length} chars on one line`);
console.log(`  target   ${dir}\\index.html`);

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
    `Write-Host "Orthanc is NOT changed. To serve it, add to the ServeFolders section:";` +
    `Write-Host '    "/pmc": "${dir.replace(/\\/g, '/')}"' -ForegroundColor Cyan;` +
    `Write-Host "then restart the Orthanc service in a quiet window."}`,
].join(';');

const out = join(ROOT, 'dist', 'Deploy-PmcImagingPortal-OneLine.ps1');
writeFileSync(out, ps + '\n');
console.log(`wrote dist/Deploy-PmcImagingPortal-OneLine.ps1`);
console.log(`  artifact ${html.length} bytes, sha256 ${sha}`);
console.log(`  command  ${ps.length} chars on one line`);
console.log(`  target   ${dir}\\index.html`);

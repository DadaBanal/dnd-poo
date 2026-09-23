#!/usr/bin/env node
/**
 * Build the deployment package: one zip an operator can copy to the server,
 * unzip, and run.
 *
 * The zip is written here rather than committed, because it is derived from
 * dist/ and would otherwise be one more thing that can go stale. What IS
 * checked is the link between the two: the install script carries the hash it
 * will accept, and this refuses to package if that hash is not the artifact's.
 * A package whose script rejects its own payload is worse than no package.
 *
 *   node build/package.mjs
 */
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { deflateRawSync } from 'node:zlib';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const manifest = JSON.parse(readFileSync(join(ROOT, 'build/manifest.json'), 'utf8'));
const sha256 = b => createHash('sha256').update(b).digest('hex');
const stamp = new Date().toISOString().slice(0, 10).replace(/-/g, '');

const artifact = readFileSync(join(ROOT, 'dist', manifest.artifact));
const hash = sha256(artifact);
if (hash !== manifest.reference.sha256) {
  console.error('FAIL: dist/ is not a build of src/. Run: npm run build');
  process.exit(1);
}

const installer = readFileSync(join(ROOT, 'scripts/Install-PmcImagingPortal.ps1'), 'utf8');
const declared = (/\$ExpectedHash\s*=\s*'([0-9a-f]{64})'/.exec(installer) || [])[1];
if (declared !== hash) {
  console.error('FAIL: the installer accepts a different build than the one in dist/.');
  console.error(`  installer expects ${declared}`);
  console.error(`  dist/ is          ${hash}`);
  console.error('  Update $ExpectedHash in scripts/Install-PmcImagingPortal.ps1 and re-run.');
  process.exit(1);
}

const readme = `PMC Imaging Portal — deployment package
=======================================

Built ${new Date().toISOString().slice(0, 10)} from source.
  PMC_Imaging_Portal.html   ${artifact.length} bytes
  sha256                    ${hash}

WHAT THIS IS
  The imaging worklist and viewer that Orthanc serves at
  https://imaging.pmcne.ph/pmc/index.html
  One self-contained HTML file. No CDN, no web font, no external request.

  The address is the FILE, not the folder. ServeFolders registers /(pmc)/(.*) and
  serves what is named, so a bare .../pmc/ gets Orthanc's own 404. Bookmark the
  full address above.

BEFORE YOU START
  Copy this whole folder to PMC-ORTHANC01 and run from there. Both scripts must
  sit next to PMC_Imaging_Portal.html; the installer checks its hash and refuses
  anything else.

1. LOOK FIRST — changes nothing, needs no elevation

     .\\Test-PmcPortalReadiness.ps1

   Asks the real archive whether it can feed the viewer: which of the three data
   paths each modality lands on, how fast a series lists, and whether the
   ServeFolders plugin is loaded. Prints no patient identifier. Prompts for your
   Orthanc sign-in and stores nothing.

2. PREVIEW THE INSTALL — changes nothing, needs elevation

     .\\Install-PmcImagingPortal.ps1

   Prints exactly what it would change and stops.

3. DO IT — in a quiet window

     .\\Install-PmcImagingPortal.ps1 -Apply

   Writes C:\\PMC\\portal\\index.html, adds a /pmc mapping for ServeFolders,
   restarts Orthanc, and proves the page is served. If Orthanc does not answer
   by name within 90 seconds it reverses the configuration change and restarts
   again by itself.

4. UNDO, if you want it gone

     .\\Install-PmcImagingPortal.ps1 -Rollback -Apply

UPDATING LATER
  Nothing here updates itself, on purpose. The page makes no external request of
  any kind, so it cannot fetch a new version, and nothing on the server polls for
  one. A change to what clinicians see is always something a person decided to do.

  To update: take the newer zip, unzip it over a copy of this folder, and run
  step 3 again. The installer notices the /pmc mapping is already there and
  DOES NOT restart Orthanc -- ServeFolders reads the page off disk on every
  request, so replacing the file is the whole update. That makes an update safe
  outside a change window.

  To check which build is live, open the portal, go to System, and read the
  Portal row. It shows the build date and a short source id, and it will match
  the line at the top of this file.

KNOWN BEFORE YOU RUN IT
  The 2 Sep HTTPS cutover kept 8 plugins and dropped 23, and ServeFolders was
  one of the 23. If its DLL is still somewhere on the machine the installer puts
  it back; if it is not, the installer stops and tells you to take it from the
  Orthanc install media. It will not download a plugin onto a clinical box.

WHAT HAS AND HAS NOT BEEN PROVEN
  MEASURED: 55 of 55 browser checks pass against a stand-in Orthanc that refuses
  OrderBy the way the ODBC index 1.3 does.
  NOT VERIFIED: nothing here has been run against PMC-ORTHANC01. Step 1 exists
  precisely to close that gap before step 3.
`;

/* ------------------------------------------------------------------ zip ---
   A minimal writer, so the build keeps its no-dependency rule. Deflate plus a
   central directory is the whole of what a reader needs.                     */
const crcTable = Array.from({ length: 256 }, (_, n) => {
  let c = n;
  for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
  return c >>> 0;
});
const crc32 = buf => {
  let c = 0xffffffff;
  for (const b of buf) c = crcTable[(c ^ b) & 0xff] ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
};
function zip(entries) {
  const chunks = [], central = [];
  let offset = 0;
  // 1980-01-01 00:00, so the same inputs always produce the same zip.
  const dosTime = 0, dosDate = (1980 - 1980) << 9 | 1 << 5 | 1;
  for (const { name, data } of entries) {
    const body = deflateRawSync(data, { level: 9 });
    const nameBuf = Buffer.from(name, 'utf8');
    const local = Buffer.alloc(30);
    local.writeUInt32LE(0x04034b50, 0); local.writeUInt16LE(20, 4); local.writeUInt16LE(0, 6);
    local.writeUInt16LE(8, 8); local.writeUInt16LE(dosTime, 10); local.writeUInt16LE(dosDate, 12);
    local.writeUInt32LE(crc32(data), 14); local.writeUInt32LE(body.length, 18);
    local.writeUInt32LE(data.length, 22); local.writeUInt16LE(nameBuf.length, 26);
    chunks.push(local, nameBuf, body);

    const cen = Buffer.alloc(46);
    cen.writeUInt32LE(0x02014b50, 0); cen.writeUInt16LE(20, 4); cen.writeUInt16LE(20, 6);
    cen.writeUInt16LE(0, 8); cen.writeUInt16LE(8, 10); cen.writeUInt16LE(dosTime, 12);
    cen.writeUInt16LE(dosDate, 14); cen.writeUInt32LE(crc32(data), 16);
    cen.writeUInt32LE(body.length, 20); cen.writeUInt32LE(data.length, 24);
    cen.writeUInt16LE(nameBuf.length, 28); cen.writeUInt32LE(offset, 42);
    central.push(cen, nameBuf);
    offset += local.length + nameBuf.length + body.length;
  }
  const centralBuf = Buffer.concat(central);
  const end = Buffer.alloc(22);
  end.writeUInt32LE(0x06054b50, 0);
  end.writeUInt16LE(entries.length, 8); end.writeUInt16LE(entries.length, 10);
  end.writeUInt32LE(centralBuf.length, 12); end.writeUInt32LE(offset, 16);
  return Buffer.concat([...chunks, centralBuf, end]);
}

const folder = `PMC_Imaging_Portal_${stamp}`;
const entries = [
  { name: `${folder}/PMC_Imaging_Portal.html`, data: artifact },
  { name: `${folder}/PMC_Imaging_Portal.html.sha256`, data: Buffer.from(`${hash}  ${manifest.artifact}\n`) },
  { name: `${folder}/Install-PmcImagingPortal.ps1`, data: Buffer.from(installer) },
  { name: `${folder}/Test-PmcPortalReadiness.ps1`, data: readFileSync(join(ROOT, 'scripts/Test-PmcPortalReadiness.ps1')) },
  { name: `${folder}/pmc-portal.config.example.json`, data: readFileSync(join(ROOT, 'config/pmc-portal.config.example.json')) },
  { name: `${folder}/README-DEPLOY.txt`, data: Buffer.from(readme.replace(/\n/g, '\r\n')) }
];

mkdirSync(join(ROOT, 'dist'), { recursive: true });
const out = join(ROOT, 'dist', `PMC_Imaging_Portal_Deploy_${stamp}.zip`);
const bytes = zip(entries);
writeFileSync(out, bytes);

console.log(`wrote dist/PMC_Imaging_Portal_Deploy_${stamp}.zip`);
console.log(`  ${bytes.length} bytes  sha256 ${sha256(bytes)}`);
for (const e of entries) console.log(`  ${String(e.data.length).padStart(8)}  ${e.name}`);

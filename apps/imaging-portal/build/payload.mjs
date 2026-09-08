#!/usr/bin/env node
/**
 * The portal reaches PMC-ORTHANC01 by ONE paste into an elevated PowerShell:
 * the HTML travels inside the installer as gzip+base64 and is checked against a
 * sha256 before a byte is written. Both of those were produced by hand.
 *
 * This emits them from the build instead, so the hash can never drift from the
 * file it is supposed to describe.
 *
 *   node build/payload.mjs                 write dist/payload.*
 *   node build/payload.mjs <installer.ps1> verify what an installer really carries
 */
import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { gzipSync, gunzipSync } from 'node:zlib';
import { createHash } from 'node:crypto';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const manifest = JSON.parse(readFileSync(join(ROOT, 'build/manifest.json'), 'utf8'));
const ARTIFACT = join(ROOT, 'dist', manifest.artifact);
const sha256 = b => createHash('sha256').update(b).digest('hex');

if (!existsSync(ARTIFACT)) { console.error(`No artifact at ${ARTIFACT} — run: npm run build`); process.exit(1); }
const html = readFileSync(ARTIFACT);            // bytes, not text
const hash = sha256(html);

const target = process.argv[2];
if (!target) {
  // deterministic gzip so the same source always yields the same payload
  const gz = gzipSync(html, { level: 9, mtime: 0 });
  const b64 = gz.toString('base64');
  writeFileSync(join(ROOT, 'dist', 'payload.gz.b64'), b64 + '\n');
  writeFileSync(join(ROOT, 'dist', `${manifest.artifact}.sha256`), `${hash}  ${manifest.artifact}\n`);
  console.log(`artifact   ${manifest.artifact}  ${html.length} bytes`);
  console.log(`sha256     ${hash}`);
  console.log(`payload    dist/payload.gz.b64  ${b64.length} base64 chars (${gz.length} bytes gzipped)`);
  console.log(`\nThese are the two values an installer must carry. Paste the hash into the`);
  console.log(`installer's expected-hash constant, or generate the installer from this file.`);
  process.exit(0);
}

// ---- verify mode: what is ACTUALLY inside an installer someone is about to run
const text = readFileSync(target, 'latin1');
const hexes = [...new Set((text.match(/\b[0-9a-f]{64}\b/gi) ?? []).map(h => h.toLowerCase()))];
const blobs = (text.match(/[A-Za-z0-9+/=]{2000,}/g) ?? []).sort((a, b) => b.length - a.length);

console.log(`installer      ${target}  (${text.length} bytes)`);
console.log(`sha256 literals found: ${hexes.length ? hexes.join(', ') : 'none'}`);
if (!blobs.length) { console.error('FAIL: no embedded base64 payload of a plausible size was found.'); process.exit(2); }

let decoded = null, usedLen = 0;
for (const blob of blobs.slice(0, 4)) {
  const buf = Buffer.from(blob, 'base64');
  try { decoded = gunzipSync(buf); usedLen = blob.length; break; }
  catch { if (buf.slice(0, 15).toString('utf8').startsWith('<!doctype html')) { decoded = buf; usedLen = blob.length; break; } }
}
if (!decoded) { console.error('FAIL: the largest embedded blobs are neither gzip nor HTML.'); process.exit(2); }

const embeddedHash = sha256(decoded);
console.log(`embedded payload: ${decoded.length} bytes, sha256 ${embeddedHash}  (from a ${usedLen}-char base64 blob)`);
console.log(`built artifact  : ${html.length} bytes, sha256 ${hash}`);
if (embeddedHash === hash) { console.log('\nMATCH — the installer carries exactly this build.'); process.exit(0); }

console.log('\nDIFFERENT — the installer does NOT carry this build.');
console.log(`  size delta: ${decoded.length - html.length} bytes`);
if (hexes.includes(embeddedHash)) console.log('  (the installer\'s own declared hash does match its payload, so the installer is internally consistent)');
else if (hexes.length) console.log('  WARNING: the installer\'s declared hash does not match its own payload either.');
writeFileSync(join(ROOT, 'dist', 'installer-payload.html'), decoded);
console.log('  the installer\'s payload was written to dist/installer-payload.html so you can diff it.');
process.exit(1);

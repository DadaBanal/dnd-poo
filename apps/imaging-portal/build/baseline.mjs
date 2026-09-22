#!/usr/bin/env node
/**
 * Re-baseline the reference hash in build/manifest.json.
 *
 * The build refuses to produce an artifact that differs from the recorded
 * reference, because that artifact is what passed the browser checks and what
 * goes onto a live clinical archive. When a change to src/ is deliberate, run
 * the checks first, then run this, and commit the manifest with the change.
 */
import { readFileSync, writeFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { assemble } from './build.mjs';

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const mPath = join(ROOT, 'build/manifest.json');
const manifest = JSON.parse(readFileSync(mPath, 'utf8'));
// The build stamp the page will carry is set here, not at build time, so the
// artifact is reproducible from the manifest alone and the date on screen means
// "the build that was signed off", not "the day someone ran the build".
const today = new Date().toISOString().slice(0, 10);
const html = assemble(today);
const bytes = Buffer.byteLength(html, 'utf8');
const sha256 = createHash('sha256').update(html, 'utf8').digest('hex');
if (sha256 === manifest.reference.sha256) { console.log('Reference already matches; nothing to do.'); process.exit(0); }
const prev = manifest.reference;
manifest.build = { date: today };
manifest.reference = { bytes, sha256, source: `re-baselined from src/ on ${today}`, previous: { bytes: prev.bytes, sha256: prev.sha256 } };
writeFileSync(mPath, JSON.stringify(manifest, null, 2) + '\n');
console.log(`reference updated\n  was ${prev.sha256} (${prev.bytes} bytes)\n  now ${sha256} (${bytes} bytes)`);
console.log('Re-run `npm test` and rebuild dist/ before committing.');

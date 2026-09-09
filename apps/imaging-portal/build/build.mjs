#!/usr/bin/env node
/**
 * Assemble the PMC Imaging Portal into ONE self-contained HTML file.
 *
 * The portal is served by Orthanc's ServeFolders plugin on a hospital LAN with
 * no internet route, so the output must carry every byte it needs: no CDN, no
 * web font, no external request of any kind. This script is what guarantees
 * that -- see checkSelfContained() below.
 *
 *   node build/build.mjs           build, then verify
 *   node build/build.mjs --check   verify only; fail if dist/ is stale (CI)
 */
import { readFileSync, writeFileSync, mkdirSync, existsSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const manifest = JSON.parse(readFileSync(join(ROOT, 'build/manifest.json'), 'utf8'));
const read = p => readFileSync(join(ROOT, p), 'utf8');
const sha256 = s => createHash('sha256').update(s, 'utf8').digest('hex');

/** Concatenate the ordered fragments back into the single-file artifact. */
export function assemble() {
  const styles = manifest.styles.map(read).join('');
  const app = manifest.app.map(read).join('');
  const favicon = readFileSync(join(ROOT, manifest.favicon)).toString('base64');

  let html = read('src/index.html');
  for (const [token, value] of [['/*@STYLES@*/\n', styles], ['/*@APP@*/\n', app], ['@FAVICON_BASE64@', favicon]]) {
    if (!html.includes(token)) throw new Error(`index.html is missing the ${token.trim()} token`);
    html = html.replace(token, () => value);   // function form: no $& substitution
  }
  return html;
}

/**
 * The constraint that matters clinically: the page must not reach the network
 * for anything but the archive it is served from. Anything absolute, or any
 * protocol-relative URL, would silently fail on the hospital LAN.
 */
function checkSelfContained(html) {
  const problems = [];
  const externalUrl = /(?:src|href)\s*=\s*["'](?:https?:)?\/\/[^"']+/gi;
  for (const m of html.match(externalUrl) ?? []) problems.push(`external reference: ${m.slice(0, 90)}`);
  for (const m of html.match(/@import\s+url\([^)]*\)/gi) ?? []) problems.push(`css @import: ${m}`);
  // A <link rel=stylesheet|preload> would pull a file that is not in the bundle.
  for (const m of html.match(/<link\b(?![^>]*rel=["']icon["'])[^>]*>/gi) ?? []) problems.push(`<link> other than the icon: ${m.slice(0, 90)}`);
  // A <script src=...> would too. Inline module scripts are fine.
  for (const m of html.match(/<script\b[^>]*\ssrc=[^>]*>/gi) ?? []) problems.push(`<script src>: ${m.slice(0, 90)}`);
  return problems;
}

/** Everything below runs only when this file is executed directly, so that
    build.mjs can also be imported (by baseline.mjs) without side effects. */
if (resolve(process.argv[1] ?? '') !== fileURLToPath(import.meta.url)) {
  // imported: expose assemble() and stop here
} else {
main();
}

function main() {
const html = assemble();
const bytes = Buffer.byteLength(html, 'utf8');
const hash = sha256(html);

const problems = checkSelfContained(html);
if (problems.length) {
  console.error('FAIL: the artifact is not self-contained:');
  for (const p of problems) console.error('  - ' + p);
  process.exit(1);
}

// The artifact must stay byte-identical to the build that passed the browser
// checks, unless someone deliberately re-baselines it (npm run baseline).
const ref = manifest.reference;
const matchesReference = hash === ref.sha256;
if (!matchesReference) {
  console.error(`FAIL: output does not match the recorded reference build.`);
  console.error(`  expected ${ref.sha256} (${ref.bytes} bytes)`);
  console.error(`  produced ${hash} (${bytes} bytes)`);
  console.error(`  If the change is intentional, re-run the browser checks and then: npm run baseline`);
  process.exit(1);
}

const outPath = join(ROOT, 'dist', manifest.artifact);
if (process.argv.includes('--check')) {
  if (!existsSync(outPath)) { console.error(`FAIL: ${outPath} is missing — run the build.`); process.exit(1); }
  const onDisk = readFileSync(outPath, 'utf8');
  if (onDisk !== html) { console.error('FAIL: dist/ is stale — it does not match a build of src/.'); process.exit(1); }
  const sidecar = existsSync(`${outPath}.sha256`) ? readFileSync(`${outPath}.sha256`, 'utf8').trim() : '';
  if (sidecar !== `${hash}  ${manifest.artifact}`) {
    console.error(`FAIL: dist/${manifest.artifact}.sha256 does not match the artifact beside it.`);
    console.error(`  expected ${hash}  ${manifest.artifact}`);
    console.error(`  found    ${sidecar || '(missing)'}`);
    process.exit(1);
  }
  console.log(`OK  dist/ is in step with src/  ${bytes} bytes  sha256 ${hash}`);
} else {
  mkdirSync(join(ROOT, 'dist'), { recursive: true });
  writeFileSync(outPath, html);
  // The sidecar is what an operator checks the pasted file against, so it is
  // written by the same step that writes the file. It had gone stale twice by
  // being a separate command someone had to remember.
  writeFileSync(`${outPath}.sha256`, `${hash}  ${manifest.artifact}\n`);
  console.log(`built dist/${manifest.artifact}`);
  console.log(`  ${bytes} bytes  sha256 ${hash}`);
  console.log(`  self-contained: no external script, style, font or image`);
}
}

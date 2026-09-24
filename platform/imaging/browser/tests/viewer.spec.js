// The platform as a radiologist at a ward PC sees it, signed in (see
// signin.setup.js): Chromium on the edge network, which can reach the front
// door and nothing else. The studies are the synthetic ones tests/seed.py
// stored (their UIDs are in /results/seed.json).
import { test, expect } from '@playwright/test';
import fs from 'node:fs';
import { RESULTS, HOST, seed } from './people.js';
import { dismissOhifNotices, firstImage, transferred } from './ohif.js';

const measured = {};

test.describe.configure({ mode: 'serial' });

test.afterAll(() => {
  const phase = process.env.RUN_PHASE || 'first';
  fs.writeFileSync(`${RESULTS}/measurements-browser-${phase}.json`, JSON.stringify(measured, null, 2));
});

// Everything a page asks for, and every console error it logs.
function watch(page) {
  const seen = { requests: [], responses: [], errors: [] };
  page.on('request', (r) => seen.requests.push(r.url()));
  page.on('response', (r) => seen.responses.push(r));
  page.on('console', (m) => m.type() === 'error' && seen.errors.push(m.text()));
  page.on('pageerror', (e) => seen.errors.push(String(e)));
  return seen;
}

// Open a study the way a link would. The signed-in session has already seen
// OHIF's notice and tour (signin.setup.js), so nothing waits for them, and the
// time to the first image is the viewer's own.
async function open(page, study) {
  const started = Date.now();
  await page.goto(`/viewer?StudyInstanceUIDs=${study}`);
  return started;
}

// The viewport overlay reads "I:<instance> (<position>/<count>)".
async function position(page) {
  const text = await page.locator('[data-cy="viewport-grid"]').innerText();
  const m = text.match(/I:\s*\d+\s*\((\d+)\/(\d+)\)/);
  return m ? { at: Number(m[1]), of: Number(m[2]) } : null;
}

test('the front door speaks TLS 1.3 over HTTP/2, for the site name only', async ({ page }) => {
  const response = await page.goto('/');
  const tls = await response.securityDetails();
  expect(tls.protocol).toBe('TLS 1.3');
  expect(tls.subjectName).toBe(HOST);
  const protocols = await page.evaluate(() =>
    performance.getEntriesByType('navigation').map((e) => e.nextHopProtocol));
  expect(protocols).toEqual(['h2']);
});

test('plain http is sent to https', async ({ request }) => {
  const r = await request.get(`http://${HOST}/viewer`, { maxRedirects: 0 });
  expect(r.status()).toBe(301);
  expect(r.headers().location).toBe(`https://${HOST}/viewer`);
});

test('a cathlab run opens playing', async ({ page }) => {
  const seen = watch(page);
  const started = await open(page, seed.xa.study);
  const shown = await firstImage(page, started);
  expect(shown, 'an image on screen').not.toBeNull();
  await dismissOhifNotices(page);
  await expect.poll(() => position(page), { timeout: 60_000 }).toMatchObject({ of: seed.xa.frames });
  // Playing means the position moves on its own, more than once.
  const positions = new Set();
  for (let i = 0; i < 12 && positions.size < 3; i++) {
    positions.add((await position(page)).at);
    await page.waitForTimeout(750);
  }
  expect(positions.size).toBeGreaterThanOrEqual(3);
  // PMC's mark in the viewer's header, in place of OHIF's (viewer/app-config.js).
  const mark = page.locator('img[src="/brand/pmc-mark-white.png"]');
  await expect(mark).toBeVisible();
  expect(await mark.evaluate((img) => img.naturalWidth)).toBeGreaterThan(0);
  const frames = seen.requests.filter((u) => u.includes('/frames/'));
  expect(new Set(frames).size).toBe(seed.xa.frames);
  expect(seen.errors).toEqual([]);
  // Opened again in the same browser: the viewer's own files come from the
  // PC's cache (kept a year, by content hash), the images do not (no-store).
  const cold = await transferred(page, /[0-9a-f]{16}\.(js|wasm)$/);
  const again = await open(page, seed.xa.study);
  const shownAgain = await firstImage(page, again);
  await dismissOhifNotices(page);
  const warm = await transferred(page, /[0-9a-f]{16}\.(js|wasm)$/);
  const images = await transferred(page, /\/frames\//);
  expect(cold.bytes).toBeGreaterThan(1_000_000);
  expect(warm.count).toBe(cold.count);
  expect(warm.from_cache, 'the viewer, from the cache').toBe(warm.count);
  expect(images.from_cache, 'images, never from the cache').toBe(0);
  measured.xa_cine = {
    frames: seed.xa.frames, first_image_shown_ms: shown, first_image_shown_again_ms: shownAgain,
    frame_requests: frames.length, viewer_files_bytes: cold.bytes, viewer_files_bytes_again: warm.bytes,
  };
});

test('a CT series opens and every slice arrives', async ({ page }) => {
  const seen = watch(page);
  const started = await open(page, seed.ct.study);
  const shown = await firstImage(page, started);
  await dismissOhifNotices(page);
  await expect.poll(() => position(page), { timeout: 60_000 }).toEqual({ at: 1, of: seed.ct.instances });
  await expect.poll(() => new Set(seen.requests.filter((u) => u.includes('/frames/'))).size,
    { timeout: 120_000 }).toBe(seed.ct.instances);
  measured.ct_stack = { slices: seed.ct.instances, first_image_shown_ms: shown, all_slices_ms: Date.now() - started };
  expect(seen.errors).toEqual([]);
});

test('an ultrasound run that arrived as JPEG plays as sent', async ({ page }) => {
  const seen = watch(page);
  await open(page, seed['us-jpeg'].study);
  await dismissOhifNotices(page);
  await expect.poll(() => position(page), { timeout: 60_000 }).toMatchObject({ of: seed['us-jpeg'].frames });
  const positions = new Set();
  for (let i = 0; i < 12 && positions.size < 2; i++) {
    positions.add((await position(page)).at);
    await page.waitForTimeout(750);
  }
  expect(positions.size).toBeGreaterThanOrEqual(2);
  expect(seen.errors).toEqual([]);
});

test('every request stays on the front door, and images are never cached', async ({ page }) => {
  const seen = watch(page);
  await open(page, seed.cr.study);
  await dismissOhifNotices(page);
  // A single image has no position counter; wait for its pixels and its window.
  await expect.poll(() => seen.requests.filter((u) => u.includes('/frames/')).length,
    { timeout: 60_000 }).toBeGreaterThan(0);
  await expect(page.locator('[data-cy="viewport-grid"]')).toContainText('W:');
  await page.waitForLoadState('networkidle');
  const elsewhere = seen.requests.filter((u) => !/^(https:|blob:|data:)/.test(u) || (u.startsWith('https:') && new URL(u).host !== HOST));
  expect(elsewhere).toEqual([]);
  const dicomweb = seen.responses.filter((r) => new URL(r.url()).pathname.startsWith('/dicom-web/'));
  expect(dicomweb.length).toBeGreaterThan(0);
  for (const r of dicomweb) {
    expect(r.headers()['cache-control'], r.url()).toBe('no-store');
  }
});

test('the engine is reachable only through the front door, and only to read', async ({ request }) => {
  // From where people sit, the engine does not exist by name...
  await expect(request.get('http://orthanc:8042/system', { timeout: 10_000 })).rejects.toThrow();
  // ...and the front door routes none of its REST API: this is the viewer's page, not the engine.
  const system = await request.get(`https://${HOST}/system`);
  expect(system.headers()['content-type']).toContain('text/html');
  // DICOMweb is read-only, whoever is signed in, until writing is designed.
  const stow = await request.post(`https://${HOST}/dicom-web/studies`, { data: 'x' });
  expect(stow.status()).toBe(403);
});

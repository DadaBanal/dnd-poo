// The platform as a radiologist at a ward PC sees it, signed in (see
// signin.setup.js): Chromium on the edge network, which can reach the front
// door and nothing else. The studies are the synthetic ones tests/seed.py
// stored (their UIDs are in /results/seed.json).
import { test, expect } from '@playwright/test';
import fs from 'node:fs';
import { RESULTS, HOST, seed } from './people.js';
import { dismissOhifNotices, firstImage, transferred } from './ohif.js';

const base = `https://${HOST}`;
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

// The reading tools (M5.2), on the images as stored (JPEG-LS): window
// presets by key, the CT reformatted in three planes, a length measured, and
// the patient's earlier study offered beside the current one.
async function overlayWindow(page) {
  const text = await page.locator('[data-cy="viewport-overlay-bottom-left"]').first().innerText().catch(() => '');
  const m = text.replace(/\s+/g, ' ').match(/W:\s*(-?\d+)\s*L:\s*(-?\d+)/);
  return m ? { w: Number(m[1]), l: Number(m[2]) } : null;
}

test('window presets by key: 2 is lung, 1 is soft tissue', async ({ page }) => {
  const started = await open(page, seed.ct.study);
  await firstImage(page, started);
  await dismissOhifNotices(page);
  await page.locator('[data-cy="viewport-pane"]').first().click({ position: { x: 40, y: 40 } });
  await page.keyboard.press('2');
  await expect.poll(() => overlayWindow(page), { timeout: 15_000 }).toEqual({ w: 1500, l: -600 });
  await page.keyboard.press('1');
  await expect.poll(() => overlayWindow(page), { timeout: 15_000 }).toEqual({ w: 400, l: 40 });
});

test('the CT reformats in three planes (MPR)', async ({ page }) => {
  const seen = watch(page);
  const started = await open(page, seed.ct.study);
  await firstImage(page, started);
  await dismissOhifNotices(page);
  await page.locator('[data-cy="layout-button"]').click();
  await page.getByText('MPR', { exact: true }).click();
  await expect(page.locator('[data-cy="viewport-pane"]')).toHaveCount(3, { timeout: 60_000 });
  // Each plane draws: three overlays with a window.
  await expect.poll(async () => {
    const texts = await page.locator('[data-cy="viewport-overlay-bottom-left"]').allInnerTexts();
    return texts.filter((t) => /W:\s*-?\d/.test(t.replace(/\s+/g, ' '))).length;
  }, { timeout: 60_000 }).toBe(3);
  expect(seen.errors).toEqual([]);
});

test('a length is measured and listed', async ({ page }) => {
  const started = await open(page, seed.cr.study);
  await firstImage(page, started);
  await dismissOhifNotices(page);
  await page.locator('[data-cy="Length-btn"]').click();
  const pane = page.locator('[data-cy="viewport-pane"]').first();
  const box = await pane.boundingBox();
  const x = box.x + box.width / 2, y = box.y + box.height / 2;
  await page.mouse.move(x - 60, y);
  await page.mouse.down();
  await page.mouse.move(x + 60, y, { steps: 8 });
  await page.mouse.up();
  await page.locator('[data-cy="trackedMeasurements-btn"]').click();
  await expect(page.getByText(/\d+(\.\d+)?\s*mm/).first()).toBeVisible({ timeout: 30_000 });
});

test("the patient's earlier study is offered beside the current one", async ({ page }) => {
  const started = await open(page, seed.cr.study);
  await firstImage(page, started);
  await dismissOhifNotices(page);
  // The study browser lists both of this patient's studies, the prior by its date.
  const browser = page.locator('[data-cy="studyBrowser-panel"]');
  await expect(browser).toContainText('06-Jan-2025', { timeout: 30_000 });
  await expect(browser).toContainText('a year earlier');
});

test("every kind of study PMC's machines make opens in the viewer", async ({ page }) => {
  // One study of each modality code in the archive (the engine's tests
  // stored one of every kind), each opened as a link would open it.
  const r = await page.request.get(`${base}/pmc/api/studies?range=all&limit=200`);
  expect(r.status()).toBe(200);
  const first = new Map();
  for (const s of (await r.json()).studies) for (const m of s.modalities) if (!first.has(m)) first.set(m, s);
  expect([...first.keys()].sort()).toEqual(expect.arrayContaining(['MG', 'RF', 'NM', 'BMD', 'PX', 'OPT', 'ES', 'RTIMAGE']));
  const opened = {};
  for (const [code, s] of first) {
    const started = Date.now();
    await page.goto(`/viewer?StudyInstanceUIDs=${s.studyUid}`);
    const shown = await firstImage(page, started);
    expect(shown, `${code} (${s.description}) shows an image`).not.toBeNull();
    opened[code] = shown;
  }
  measured.every_kind_first_image_ms = opened;
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

// The PMC front door app (M2.3): the worklist a person lands on, as the
// radiologist at a ward PC sees it (signed in by signin.setup.js), plus one
// referrer from no session. The studies are the ones tests/seed.py stored.
import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import fs from 'node:fs';
import { HOST, RESULTS, seed, settled, signIn } from './people.js';
import { dismissOhifNotices, framesSeen, position, transferred } from './ohif.js';

const base = `https://${HOST}`;
const rows = (page) => page.locator('.wl-body [role="row"]');
const rowOf = (page, kind) => rows(page).filter({ hasText: seed[kind].patient_id });
const pane = (page) => page.getByRole('complementary', { name: 'Study preview' });
const measured = {};

test.afterAll(() => {
  if (Object.keys(measured).length) {
    fs.writeFileSync(`${RESULTS}/measurements-home.json`, JSON.stringify(measured, null, 2));
  }
});

test('the address people are given opens the worklist, live, with every study', async ({ page }) => {
  const outside = [];
  page.on('request', (r) => new URL(r.url()).host !== HOST && outside.push(r.url()));
  await page.goto('/');
  await expect(page).toHaveURL(`${base}/pmc/`);
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('PMC imaging studies');
  for (const kind of ['xa', 'ct', 'cr', 'us-jpeg']) await expect(rowOf(page, kind)).toBeVisible();
  // New studies will appear by themselves: the page holds a live stream.
  await expect(page.getByTestId('live')).toHaveText('Live');
  expect(outside).toEqual([]);
});

test("the header is PMC's: the lock-up on PMC Blue, the mark in the tab", async ({ page }) => {
  await page.goto('/pmc/');
  const header = page.getByRole('banner');
  const lockup = header.getByRole('img', { name: 'Premiere Medical Center Nueva Ecija' });
  await expect(lockup).toBeVisible();
  expect(await lockup.evaluate((img) => img.naturalWidth)).toBeGreaterThan(0);
  expect(await header.evaluate((h) => getComputedStyle(h).backgroundColor)).toBe('rgb(11, 63, 138)');
  expect(await page.locator('link[rel="icon"]').getAttribute('href')).toBe('/brand/pmc-mark.png');
});

test('Enter opens the selected study in the viewer, in its own window, playing', async ({ page, context }) => {
  await page.goto('/pmc/');
  await rowOf(page, 'xa').getByRole('rowheader').click();
  const opened = context.waitForEvent('page');
  await page.keyboard.press('Enter');
  const viewer = await opened;
  await expect(viewer).toHaveURL(`${base}/viewer?StudyInstanceUIDs=${seed.xa.study}`);
  await dismissOhifNotices(viewer);
  await expect.poll(() => position(viewer), { timeout: 60_000 }).toMatchObject({ of: seed.xa.frames });
  expect(await framesSeen(viewer)).toBeGreaterThanOrEqual(3);

  // The next study opens in that same window (a second screen keeps the
  // viewer), and the list stays where it is.
  await page.bringToFront();
  await rowOf(page, 'ct').getByRole('rowheader').click();
  await page.keyboard.press('Enter');
  await expect(viewer).toHaveURL(`${base}/viewer?StudyInstanceUIDs=${seed.ct.study}`);
  expect(context.pages()).toHaveLength(2);
  await expect(page).toHaveURL(`${base}/pmc/`);
});

test('filters are part of the address, so a view is a link', async ({ page }) => {
  await page.goto('/pmc/');
  await page.getByRole('button', { name: 'CT', exact: true }).click();
  await expect(page).toHaveURL(/[?&]mod=ct(&|$)/);
  await expect(rowOf(page, 'ct')).toBeVisible();
  await expect(rowOf(page, 'xa')).toHaveCount(0);
  await page.reload();
  await expect(page.getByRole('button', { name: 'CT', exact: true })).toHaveAttribute('aria-pressed', 'true');
  await expect(rowOf(page, 'xa')).toHaveCount(0);
});

test('the keyboard: / finds, Enter searches, j and k move', async ({ page }) => {
  await page.goto('/pmc/');
  await expect(rowOf(page, 'ct')).toBeVisible();
  await page.keyboard.press('/');
  await page.keyboard.type(seed.ct.patient_id);
  await page.keyboard.press('Enter');
  await expect(page).toHaveURL(new RegExp(`[?&]q=${seed.ct.patient_id}`));
  await expect(rows(page)).toHaveCount(1);

  // A numeric search (PMC's patient IDs are numbers) survives the address.
  await page.goto('/pmc/?q=20260924');
  await expect(page.getByRole('searchbox')).toHaveValue('20260924');

  await page.goto('/pmc/');
  await expect(rows(page).nth(1)).toBeVisible();
  await page.keyboard.press('j');
  await expect(rows(page).nth(0)).toBeFocused();
  await page.keyboard.press('j');
  await expect(rows(page).nth(1)).toBeFocused();
  await page.keyboard.press('k');
  await expect(rows(page).nth(0)).toBeFocused();
});

test('A claims a study, and a colleague sees who has it without reloading', async ({ page, browser }) => {
  // A cardiologist already has the worklist open on another PC: a browser of
  // their own, with no session until they sign in.
  const colleague = await browser.newContext({
    baseURL: base, ignoreHTTPSErrors: true, viewport: { width: 1600, height: 900 },
    storageState: { cookies: [], origins: [] },
  });
  const theirs = await colleague.newPage();
  await signIn(theirs, 'cardiologist', '/pmc/');
  await expect(theirs.getByRole('banner')).toContainText('Test Cardiologist');
  await expect(rowOf(theirs, 'us-jpeg')).toBeVisible();
  await expect(theirs.getByTestId('live')).toHaveText('Live');

  // Start from an unclaimed study, whatever an earlier run left behind.
  await page.request.delete(`${base}/pmc/api/studies/${seed['us-jpeg'].study}/claim`, { headers: { Origin: base } });
  await page.goto('/pmc/');
  await expect(rowOf(page, 'us-jpeg').getByRole('button', { name: /^Claim / })).toBeVisible();
  await rowOf(page, 'us-jpeg').getByRole('rowheader').click();
  await page.keyboard.press('a');
  await expect(rowOf(page, 'us-jpeg')).toContainText('You');
  await expect(rowOf(theirs, 'us-jpeg')).toContainText('Test Radiologist', { timeout: 15_000 });

  // "Claimed by me" shows just that study; releasing it empties the list.
  await page.getByRole('button', { name: 'Claimed by me' }).click();
  await expect(page).toHaveURL(/[?&]mine=1(&|$)/);
  await expect(rows(page)).toHaveCount(1);
  await rowOf(page, 'us-jpeg').getByRole('button', { name: /^Release / }).click();
  await expect(page.getByText('No study matches these filters.')).toBeVisible();
  await expect(rowOf(theirs, 'us-jpeg')).not.toContainText('Test Radiologist', { timeout: 15_000 });
  await colleague.close();
});

for (const colorScheme of ['light', 'dark']) {
  test(`the worklist passes an accessibility check (WCAG 2.2 AA), ${colorScheme}`, async ({ page }) => {
    await page.emulateMedia({ colorScheme });
    await page.goto('/pmc/');
    await expect(rowOf(page, 'xa')).toBeVisible();
    await rowOf(page, 'cr').getByRole('rowheader').click();
    await expect(pane(page).getByRole('list', { name: 'Earlier studies' })).toBeVisible();
    await settled(page);
    const found = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'])
      .analyze();
    expect(found.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(', ')}`)).toEqual([]);
  });
}

// ---- the reading list, upgraded (M5.3) --------------------------------------------
test('a row carries its first image; selecting it previews the series and the earlier study', async ({ page }) => {
  const images = [];
  page.on('response', (r) => r.url().includes('/thumbnail?') && images.push(r));
  await page.goto('/pmc/');
  const row = rowOf(page, 'cr');
  await expect(row).toBeVisible();
  const first = row.locator('img.thumb');
  await expect(first).toBeVisible();
  await expect.poll(() => first.evaluate((img) => img.naturalWidth)).toBeGreaterThan(0);

  await row.getByRole('rowheader').click();
  await expect(pane(page)).toBeVisible();
  await expect(pane(page).getByRole('heading', { level: 2 })).toContainText('SYNTHETIC');
  const series = pane(page).getByRole('list', { name: 'Series' });
  await expect(series.getByRole('listitem')).toHaveCount(1);
  await expect(series.getByRole('listitem').first()).toContainText('CR');
  const priors = pane(page).getByRole('list', { name: 'Earlier studies' });
  await expect(priors.getByRole('listitem')).toHaveCount(1);
  await expect(priors).toContainText(/6 Jan 2025|Jan 6, 2025/);
  await expect(priors).toContainText('a year earlier');
  for (const img of await pane(page).locator('img.thumb').all()) {
    await expect.poll(() => img.evaluate((i) => i.naturalWidth)).toBeGreaterThan(0);
  }
  // Every image came through the front door, on the person's own session,
  // and none may be kept on the PC.
  expect(images.length).toBeGreaterThanOrEqual(4);
  for (const r of images) {
    expect(r.status()).toBe(200);
    expect(r.headers()['cache-control']).toBe('no-store');
  }
  // Escape closes the preview.
  await page.keyboard.press('Escape');
  await expect(pane(page)).toHaveCount(0);
});

test('Compare opens the earlier study beside the current one', async ({ page, context }) => {
  await page.goto('/pmc/');
  await rowOf(page, 'cr').getByRole('rowheader').click();
  const opened = context.waitForEvent('page');
  await pane(page).getByRole('link', { name: /^Compare/ }).click();
  const viewer = await opened;
  await expect(viewer).toHaveURL(new RegExp(`StudyInstanceUIDs=${seed.cr.study},${seed.cr.prior.study}`));
  await dismissOhifNotices(viewer);
  // OHIF's compare protocol: the current study on the left, the prior on the
  // right (a 2x2 grid whose lower row fills when each study has more series).
  const panes = viewer.locator('[data-cy="viewport-pane"]');
  const drawn = panes.filter({ hasText: /W:\s*-?\d/ });
  await expect.poll(() => drawn.count(), { timeout: 60_000 }).toBeGreaterThanOrEqual(2);
  await expect(drawn.filter({ hasText: '06-Jan-2025' })).toHaveCount(1);
  await expect(drawn.filter({ hasNotText: '06-Jan-2025' })).toHaveCount(1);
  await viewer.close();
});

test('R marks the study read; "Unread" hides it; the reader can unmark it', async ({ page }) => {
  await page.request.delete(`${base}/pmc/api/studies/${seed.ct.study}/read`, { headers: { Origin: base } });
  await page.goto('/pmc/');
  const row = rowOf(page, 'ct');
  await expect(row.locator('.pill', { hasText: /^Unread$/ })).toBeVisible();
  await expect(page.getByTestId('total')).toContainText(/^\d+ studies$/);
  // Once the page's entrances are over: a row still rising is not where a
  // click aimed at it lands.
  await settled(page);
  await row.getByRole('rowheader').click();
  await page.keyboard.press('r');
  await expect(row.locator('.pill', { hasText: /^Read$/ })).toBeVisible();
  await expect(row).toContainText('You');

  await page.getByRole('button', { name: 'Unread', exact: true }).click();
  await expect(page).toHaveURL(/[?&]unread=1(&|$)/);
  await expect(row).toHaveCount(0);
  await expect(rowOf(page, 'xa')).toBeVisible();
  // The preview closes with its study and comes back with it when the filter
  // comes off; the table then lays itself out again beside it, and the row's
  // buttons move. Act on the row once that has happened, as a person would
  // (a click aimed before the move lands beside the button).
  await expect(pane(page)).toBeHidden();
  await page.getByRole('button', { name: 'Unread', exact: true }).click();
  await expect(row).toBeVisible();
  await expect(pane(page)).toBeVisible();
  await settled(page);
  await row.getByRole('button', { name: /unread$/ }).click();
  await expect(row.locator('.pill', { hasText: /^Unread$/ })).toBeVisible();
});

test('compact rows drop the images, and the choice is remembered on this PC', async ({ page }) => {
  await page.goto('/pmc/');
  await expect(rowOf(page, 'ct').locator('img.thumb')).toHaveCount(1);
  await page.getByRole('button', { name: 'Compact rows' }).click();
  await expect(rowOf(page, 'ct').locator('img.thumb')).toHaveCount(0);
  await page.reload();
  await expect(rowOf(page, 'ct')).toBeVisible();
  await expect(rowOf(page, 'ct').locator('img.thumb')).toHaveCount(0);
  await page.getByRole('button', { name: 'Comfortable rows' }).click();
  await expect(rowOf(page, 'ct').locator('img.thumb')).toHaveCount(1);
});

test('the list does not lag: compressed parts, cached after the first visit, no flash on a filter, no long tasks', async ({ browser }) => {
  // A PC's first visit: a browser with nothing cached, already signed in.
  const fresh = await browser.newContext({
    baseURL: base, storageState: `${RESULTS}/.auth/radiologist.json`, viewport: { width: 1600, height: 900 },
  });
  const page = await fresh.newPage();
  // Every task that held the page's main thread for 50 ms or more.
  await page.addInitScript(() => {
    window.__long = [];
    new PerformanceObserver((list) => list.getEntries().forEach((e) =>
      window.__long.push({ ms: Math.round(e.duration), at: Math.round(e.startTime) })))
      .observe({ type: 'longtask', buffered: true });
  });
  let started = Date.now();
  await page.goto('/pmc/');
  await expect(rowOf(page, 'xa')).toBeVisible();
  const coldMs = Date.now() - started;
  const files = await page.evaluate(() => performance.getEntriesByType('resource')
    .filter((e) => new URL(e.name).pathname.startsWith('/pmc/assets/'))
    .map((e) => ({ name: new URL(e.name).pathname.split('/').pop(), transfer: e.transferSize, encoded: e.encodedBodySize, decoded: e.decodedBodySize })));
  // The page's own code apart from its libraries, every part compressed.
  expect(files.length).toBeGreaterThanOrEqual(5);
  for (const f of files.filter((f) => f.decoded > 4096)) expect(f.encoded, f.name).toBeLessThan(f.decoded / 2);
  // Every row's image arrives.
  const thumbs = page.locator('.wl-body img.thumb');
  const count = await thumbs.count();
  expect(count).toBeGreaterThanOrEqual(4);
  await expect.poll(() => thumbs.evaluateAll((imgs) => imgs.filter((i) => i.complete && i.naturalWidth > 0).length),
    { timeout: 30_000 }).toBe(count);
  const thumbsMs = Date.now() - started;

  // A filter: the rows on screen stay until the new ones arrive, so the list
  // is never empty and never says "loading" in between.
  await page.evaluate(() => {
    window.__empty = 0;
    new MutationObserver(() => {
      if (!document.querySelector('.wl-body [role="row"]')) window.__empty += 1;
    }).observe(document.querySelector('main'), { childList: true, subtree: true, characterData: true });
  });
  started = Date.now();
  await page.getByRole('button', { name: 'CT', exact: true }).click();
  await expect(rowOf(page, 'xa')).toHaveCount(0);
  await expect(rowOf(page, 'ct')).toBeVisible();
  const filterMs = Date.now() - started;
  expect(await page.evaluate(() => window.__empty)).toBe(0);
  const longCold = await page.evaluate(() => window.__long);
  // When the page's own moments fell, to read the long tasks against them.
  const moments = await page.evaluate(() => ({
    first_paint_at: Math.round(performance.getEntriesByName('first-contentful-paint')[0]?.startTime ?? -1),
    scripts_done_at: Math.round(Math.max(...performance.getEntriesByType('resource')
      .filter((e) => new URL(e.name).pathname.startsWith('/pmc/assets/')).map((e) => e.responseEnd))),
    studies_answered_at: performance.getEntriesByType('resource')
      .filter((e) => new URL(e.name).pathname === '/pmc/api/studies').map((e) => Math.round(e.responseEnd)),
  }));

  // A second visit fetches none of the page's files.
  started = Date.now();
  await page.goto('/pmc/');
  await expect(rowOf(page, 'xa')).toBeVisible();
  const warmMs = Date.now() - started;
  const warm = await transferred(page, /^\/pmc\/assets\//);
  expect(warm.count).toBe(files.length);
  expect(warm.from_cache).toBe(warm.count);
  const longWarm = await page.evaluate(() => window.__long);

  measured.list = {
    first_visit_to_rows_ms: coldMs,
    first_visit_every_thumbnail_ms: thumbsMs,
    filter_switch_ms: filterMs,
    second_visit_to_rows_ms: warmMs,
    page_files: files.length,
    page_wire_kb: Math.round(files.reduce((n, f) => n + f.transfer, 0) / 1024),
    page_uncompressed_kb: Math.round(files.reduce((n, f) => n + f.decoded, 0) / 1024),
    ...moments,
    long_tasks_first_visit: longCold,
    long_tasks_second_visit: longWarm,
  };
  // The page's main thread is never held long: at most one task over 100 ms
  // (the page's first render) and none over 300 ms, on a software-rendered
  // 4-CPU build host.
  const heldCold = longCold.map((t) => t.ms);
  const heldWarm = longWarm.map((t) => t.ms);
  expect(heldCold.filter((ms) => ms > 100).length).toBeLessThanOrEqual(1);
  expect(Math.max(0, ...heldCold, ...heldWarm)).toBeLessThan(300);
  await fresh.close();
});

test('the page moves with purpose, and not at all when the PC asks for less motion', async ({ page }) => {
  await page.goto('/pmc/');
  await expect(rowOf(page, 'xa')).toBeVisible();
  const bar = page.locator('.seg-bar');
  expect(await bar.evaluate((el) => getComputedStyle(el).animationName)).toBe('draw');
  // Every animation is a transform or an opacity: nothing that makes the
  // browser lay the page out again.
  const animated = await page.evaluate(() => [...new Set(document.getAnimations()
    .flatMap((a) => a.effect.getKeyframes().flatMap((k) => Object.keys(k)))
    .filter((k) => !['offset', 'computedOffset', 'easing', 'composite'].includes(k)))]);
  expect(animated.every((prop) => ['transform', 'opacity'].includes(prop)), animated.join(', ')).toBe(true);
  // The theme switch is a view transition from the button; the theme flips.
  const before = await page.evaluate(() => document.documentElement.dataset.theme ?? '');
  const toggle = page.getByRole('button', { name: 'Switch between light and dark' });
  await toggle.click();
  await expect.poll(() => page.evaluate(() => document.documentElement.dataset.theme ?? '')).not.toBe(before);
  await toggle.click();
  await expect.poll(() => page.evaluate(() => document.documentElement.dataset.theme ?? '')).not.toBe('');

  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.reload();
  await expect(rowOf(page, 'xa')).toBeVisible();
  expect(await bar.evaluate((el) => getComputedStyle(el).animationName)).toBe('none');
  expect(await page.evaluate(() => document.getAnimations().length)).toBe(0);
});

test.describe('from no session', () => {
  test.use({ storageState: { cookies: [], origins: [] } });

  test("a referrer's worklist shows only studies shared with referrers", async ({ page }) => {
    await signIn(page, 'referrer', '/pmc/');
    await expect(page).toHaveURL(`${base}/pmc/`);
    await expect(page.getByRole('heading', { level: 1 })).toHaveText('Studies shared with you');
    await expect(rowOf(page, 'cr')).toBeVisible();
    await expect(rowOf(page, 'xa')).toHaveCount(0);
    await expect(rowOf(page, 'ct')).toHaveCount(0);
  });
});

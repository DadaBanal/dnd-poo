// The PMC front door app (M2.3): the worklist a person lands on, as the
// radiologist at a ward PC sees it (signed in by signin.setup.js), plus one
// referrer from no session. The studies are the ones tests/seed.py stored.
import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { HOST, seed, signIn } from './people.js';
import { dismissOhifNotices, framesSeen, position } from './ohif.js';

const base = `https://${HOST}`;
const rows = (page) => page.locator('tbody [role="row"]');
const rowOf = (page, kind) => rows(page).filter({ hasText: seed[kind].patient_id });

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
    const found = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'])
      .analyze();
    expect(found.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(', ')}`)).toEqual([]);
  });
}

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

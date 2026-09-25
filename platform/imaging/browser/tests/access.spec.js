// Who gets in, and what each person may see. Every test starts with no
// session. The people are the stand-in Active Directory's invented users; their
// roles come from their AD groups, mapped in Keycloak (identity/realm-pmc.json).
import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import fs from 'node:fs';
import { HOST, RESULTS, seed, settled, signIn } from './people.js';
import { dismissOhifNotices, framesSeen, position } from './ohif.js';

const base = `https://${HOST}`;
const measured = {};

test.afterAll(() => {
  if (Object.keys(measured).length) {
    fs.writeFileSync(`${RESULTS}/measurements-access.json`, JSON.stringify(measured, null, 2));
  }
});

test('without a session, a link goes to sign-in and comes back to the same page', async ({ page }) => {
  const dicomweb = [];
  page.on('request', (r) => r.url().includes('/dicom-web/') && dicomweb.push(r.url()));
  const link = `/viewer?StudyInstanceUIDs=${seed.xa.study}`;
  await page.goto(link);
  // Straight to PMC's sign-in page, which asks for the Windows logon, and not
  // one image request before signing in.
  expect(page.url()).toContain('/auth/realms/pmc/protocol/openid-connect/auth');
  await expect(page.locator('#username')).toBeVisible();
  expect(dicomweb).toEqual([]);
  await signIn(page, 'radiologist', link);
  await expect(page).toHaveURL(`${base}${link}`);
  // The session is a ticket in a cookie the page's scripts cannot read.
  const session = (await page.context().cookies()).filter((c) => c.name.startsWith('__Host-pmc-session'));
  expect(session).toHaveLength(1);
  expect(session[0]).toMatchObject({ httpOnly: true, secure: true, sameSite: 'Lax' });
});

test("the sign-in page is PMC's, and says when Caps Lock is on", async ({ page }) => {
  await page.goto('/pmc/');
  await expect(page.locator('#username')).toBeVisible();
  // PMC's words, and the brand panel: the lock-up (the front door's /brand/)
  // and the tagline on PMC Blue (identity/theme/pmc; the realm's displayNameHtml).
  await expect(page.locator('#kc-page-title')).toHaveText('Sign in with your PMC Windows logon');
  const panel = page.locator('#kc-header');
  const lockup = panel.getByRole('img', { name: 'Premiere Medical Center Nueva Ecija' });
  await expect(lockup).toBeVisible();
  expect(await lockup.evaluate((img) => img.naturalWidth)).toBeGreaterThan(0);
  await expect(panel).toContainText('Better Care. For Every Life.');
  expect(await panel.evaluate((h) => getComputedStyle(h).backgroundColor)).toBe('rgb(11, 63, 138)');
  // Caps Lock on while typing the password: it says so. Off again: it does not.
  const note = page.locator('#pmc-caps-lock');
  await page.locator('#password').dispatchEvent('keyup', { key: 'A', modifierCapsLock: true });
  await expect(note).toHaveText('Caps Lock is on');
  await page.locator('#password').dispatchEvent('keyup', { key: 'a' });
  await expect(note).toHaveText('');
  // Every word on it can be read, in light and in the reading-room theme.
  for (const colorScheme of ['light', 'dark']) {
    await page.emulateMedia({ colorScheme });
    await expect(page.locator('html')).toHaveClass(colorScheme === 'dark' ? /pf-v5-theme-dark/ : /^(?!.*pf-v5-theme-dark)/);
    await settled(page);
    const found = await new AxeBuilder({ page }).withRules(['color-contrast']).analyze();
    expect(found.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(', ')}`), colorScheme).toEqual([]);
  }
});

test('someone in no PMC group gets no session and no images', async ({ page, request }) => {
  await signIn(page, 'nogroup', '/viewer');
  // oauth2-proxy refuses at the door: AD knows them, but no PMC group does.
  await expect(page.locator('body')).toContainText(/forbidden|permission/i);
  const cookies = await page.context().cookies();
  expect(cookies.filter((c) => c.name.startsWith('__Host-pmc-session'))).toEqual([]);
  const r = await page.request.get(`${base}/dicom-web/studies`);
  expect(r.status()).toBe(401);
});

test('a referrer opens a study shared with referrers, and no other', async ({ page }) => {
  test.setTimeout(480_000);
  await signIn(page, 'referrer', '/viewer');
  // Sharing is a label, and the engine's authorization plugin caches what it
  // knows about a study, so a new share takes about a minute to reach a
  // referrer (MEASURED: 64 s, 23 Sep, plugin 0.12.0). Wait for it, and
  // record how long it took.
  const visible = async () => (await page.request.get(
    `${base}/dicom-web/studies?StudyInstanceUID=${seed.cr.study}`,
    { headers: { Accept: 'application/dicom+json' } })).status();
  await expect.poll(visible, { timeout: 300_000, intervals: [5_000] }).toBe(200);
  measured.share_visible_after_s = Math.round((Date.now() - seed.cr.labelled_at_ms) / 1000);

  await page.goto(`/viewer?StudyInstanceUIDs=${seed.cr.study}`);
  await dismissOhifNotices(page);
  // The shared chest plate: its pixels arrive and it is drawn.
  await expect(page.locator('[data-cy="viewport-grid"]')).toContainText('W:', { timeout: 60_000 });

  // A search finds only what is shared (the engine cuts it to the referrer's labels)...
  const qido = await page.request.get(`${base}/dicom-web/studies`, { headers: { Accept: 'application/dicom+json' } });
  expect(qido.status()).toBe(200);
  const found = (await qido.json()).map((s) => s['0020000D'].Value[0]);
  expect(found).toContain(seed.cr.study);
  expect(found).not.toContain(seed.xa.study);
  // ...and an unshared study cannot be read even by its UID.
  const metadata = await page.request.get(
    `${base}/dicom-web/studies/${seed.xa.study}/series/${seed.xa.series}/metadata`,
    { headers: { Accept: 'application/dicom+json' } });
  expect(metadata.status()).toBe(403);
});

test('a cardiologist opens a cathlab run, and it plays', async ({ page }) => {
  await signIn(page, 'cardiologist', `/viewer?StudyInstanceUIDs=${seed.xa.study}`);
  await dismissOhifNotices(page);
  await expect.poll(() => position(page), { timeout: 60_000 }).toMatchObject({ of: seed.xa.frames });
  expect(await framesSeen(page)).toBeGreaterThanOrEqual(3);
});

test('without a session, DICOMweb answers 401, never data and never a sign-in page', async ({ request }) => {
  const r = await request.get(`${base}/dicom-web/studies`, { maxRedirects: 0 });
  expect(r.status()).toBe(401);
});

test('Keycloak administration is not reachable from the front door', async ({ request }) => {
  for (const path of ['/auth/admin/', '/auth/admin/master/console/', '/auth/realms/master/']) {
    const r = await request.get(`${base}${path}`, { maxRedirects: 0 });
    expect(r.status(), path).toBe(404);
  }
});

test('signing out ends the session', async ({ page }) => {
  await signIn(page, 'radiologist', '/viewer');
  expect((await page.request.get(`${base}/dicom-web/studies`)).status()).toBe(200);
  await page.goto('/oauth2/sign_out');
  await expect(page).toHaveURL(`${base}/signed-out`);
  await expect(page.locator('h1')).toContainText('signed out');
  // In PMC's identity: the lock-up on the blue band.
  const lockup = page.getByRole('img', { name: 'Premiere Medical Center Nueva Ecija' });
  await expect(lockup).toBeVisible();
  expect(await lockup.evaluate((img) => img.naturalWidth)).toBeGreaterThan(0);
  expect((await page.request.get(`${base}/dicom-web/studies`)).status()).toBe(401);
});

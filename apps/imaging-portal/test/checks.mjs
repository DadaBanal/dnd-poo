#!/usr/bin/env node
/**
 * Drives the BUILT artifact in a real browser against the stand-in Orthanc.
 *
 * These are the checks the portal was signed off on (recorded as "21 of 21" on
 * 6 Sep 2026), written down so they can be re-run by anyone, plus checks for
 * the three faults this codebase has actually hit:
 *   - previews painting behind their placeholder
 *   - /modalities answering with either shape
 *   - GET /modalities/{name} returning CHILD RESOURCES, not settings
 *
 * Run:  npm test        (from apps/imaging-portal)
 */
import { createRequire } from 'node:module';
import { readFileSync, existsSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { startStandInOrthanc } from './stand-in-orthanc.mjs';

let chromium;
try {
  ({ chromium } = await import('playwright'));
} catch {
  // Some machines carry Playwright only as a global install; resolve it there.
  const { execSync } = await import('node:child_process');
  const globalRoot = execSync('npm root -g', { encoding: 'utf8' }).trim();
  ({ chromium } = createRequire(globalRoot + '/').call(null, 'playwright'));
}

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const ARTIFACT = join(ROOT, 'dist', 'PMC_Imaging_Portal.html');
if (!existsSync(ARTIFACT)) { console.error(`No built artifact at ${ARTIFACT} — run: npm run build`); process.exit(1); }
const portalHtml = readFileSync(ARTIFACT, 'utf8');

const results = [];
const check = (name, fn) => results.push({ name, fn });
const eq = (actual, expected, what) => { if (actual !== expected) throw new Error(`${what}: expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`); };
const ok = (cond, msg) => { if (!cond) throw new Error(msg); };

/** Open the portal, wait for boot to finish, and collect anything the page got wrong. */
async function openPortal(browser, server, { viewport, url } = {}) {
  const ctx = await browser.newContext(viewport ? { viewport } : {});
  const page = await ctx.newPage();
  const pageErrors = [], failedRequests = [], consoleErrors = [], badResponses = [];
  page.on('pageerror', e => pageErrors.push(String(e)));
  page.on('requestfailed', r => failedRequests.push(`${r.method()} ${r.url()} ${r.failure()?.errorText}`));
  page.on('response', r => { if (r.status() >= 400) badResponses.push(`${r.status()} ${new URL(r.url()).pathname}`); });
  // A resource that 404s already shows up in badResponses; do not double-count its console line.
  page.on('console', m => { if (m.type() === 'error' && !/Failed to load resource/.test(m.text())) consoleErrors.push(m.text()); });
  await page.goto(url ?? server.portalUrl, { waitUntil: 'domcontentloaded' });
  // `body.dataset.ready` is set as soon as boot() finishes, but render() hands the
  // DOM write to document.startViewTransition(), which is asynchronous -- so on a
  // View-Transitions browser the flag beats the paint by ~100ms. Wait for the
  // skeletons to be gone as well; that holds for the cards, empty and error states.
  await page.waitForFunction(() => document.body.dataset.ready === '1', null, { timeout: 20000 });
  await page.waitForFunction(() => !document.querySelector('#results .skel'), null, { timeout: 20000 });
  return { ctx, page, pageErrors, failedRequests, consoleErrors, badResponses };
}
const findBodies = server => server.requests.filter(r => r.path === 'tools/find' && r.method === 'POST').map(r => JSON.parse(r.body || '{}'));

// ---------------------------------------------------------------- the checks

check('connects to the archive and names the server', async (b, s) => {
  const { page, ctx } = await openPortal(b, s);
  await eq(await page.textContent('#healthText'), 'PMC-ORTHANC01 (stand-in) · 1.13.0', 'header health text');
  await ctx.close();
});

check("today's worklist renders studies", async (b, s) => {
  const { page, ctx } = await openPortal(b, s);
  const n = await page.locator('#results .card, #results tbody tr').count();
  ok(n > 0, 'no studies rendered on the default (today) scope');
  const today = new Date(); const y = `${today.getFullYear()}${String(today.getMonth()+1).padStart(2,'0')}${String(today.getDate()).padStart(2,'0')}`;
  eq(findBodies(s)[0].Query.StudyDate, y, "first query's StudyDate");
  await ctx.close();
});

check('NEVER sends OrderBy — the whole reason this page works on the ODBC index', async (b, s) => {
  const { page, ctx } = await openPortal(b, s);
  await page.click('#scopeChips .chip[data-scope="30"]');
  await page.waitForTimeout(400);
  await page.fill('#q', 'FIXTURE'); await page.waitForTimeout(600);
  const offending = findBodies(s).filter(q => 'OrderBy' in q);
  eq(offending.length, 0, 'number of /tools/find requests carrying OrderBy');
  ok(findBodies(s).length >= 2, 'expected several find requests to have been made');
  await ctx.close();
});

check('sorts in the browser, not the database', async (b, s) => {
  const { page, ctx } = await openPortal(b, s);
  await page.click('#scopeChips .chip[data-scope="all"]');
  await page.waitForTimeout(500);
  await page.click('[data-layout="rows"]').catch(() => {});
  await page.waitForTimeout(200);
  const before = findBodies(s).length;
  const head = page.locator('#results th', { hasText: 'Patient' }).first();
  if (await head.count()) {
    await head.click(); await page.waitForTimeout(200);
    const names = await page.locator('#results tbody tr td:nth-child(2)').allTextContents();
    const sorted = [...names].sort((a, x) => a.toLowerCase() < x.toLowerCase() ? -1 : 1);
    eq(names.join('|'), sorted.join('|'), 'client-side name sort order');
  }
  eq(findBodies(s).length, before, 'sorting must not issue another query');
  await ctx.close();
});

check('thumbnails load from /instances/{id}/preview and become visible', async (b, s) => {
  const { page, ctx } = await openPortal(b, s);
  await page.waitForFunction(() => document.querySelectorAll('#results img.ready').length > 0, null, { timeout: 15000 });
  // .ready fades the image in over 350ms; wait for the transition to settle.
  await page.waitForFunction(() => {
    const i = document.querySelector('#results img.ready');
    return i && +getComputedStyle(i).opacity > 0.99;
  }, null, { timeout: 5000 });
  const shown = await page.evaluate(() => {
    const img = document.querySelector('#results img.ready');
    const r = img.getBoundingClientRect(); const cs = getComputedStyle(img);
    return { w: r.width, h: r.height, opacity: +cs.opacity, visibility: cs.visibility, natural: img.naturalWidth };
  });
  ok(shown.natural > 0, 'preview image did not decode');
  ok(shown.w > 0 && shown.h > 0, 'preview image has no box');
  ok(shown.opacity > 0.9 && shown.visibility === 'visible', `preview is not actually visible (${JSON.stringify(shown)})`);
  ok(s.requests.some(r => /^instances\/.+\/preview$/.test(r.path)), 'no /instances/{id}/preview request was made');
  await ctx.close();
});

check('searches across patient name, ID and accession at once', async (b, s) => {
  const { page, ctx } = await openPortal(b, s);
  await page.click('#scopeChips .chip[data-scope="all"]'); await page.waitForTimeout(400);
  await page.fill('#q', 'PLACEHOLDER'); await page.waitForTimeout(800);
  const txt = await page.textContent('#results');
  ok(/Placeholder/i.test(txt), 'name search returned nothing for PLACEHOLDER');
  const keys = findBodies(s).slice(-4).flatMap(q => Object.keys(q.Query));
  for (const k of ['PatientName', 'PatientID', 'AccessionNumber']) ok(keys.includes(k), `search did not fan out to ${k}`);
  await ctx.close();
});

check('finds a study by accession number', async (b, s) => {
  const { page, ctx } = await openPortal(b, s);
  await page.click('#scopeChips .chip[data-scope="all"]'); await page.waitForTimeout(400);
  await page.fill('#q', 'ACC100003'); await page.waitForTimeout(900);
  const n = await page.locator('#results .card, #results tbody tr').count();
  eq(n, 1, 'accession search should match exactly one study');
  await ctx.close();
});

check('date-range chips change the window asked of the index', async (b, s) => {
  const { page, ctx } = await openPortal(b, s);
  for (const scope of ['7', '30', 'all']) {
    await page.click(`#scopeChips .chip[data-scope="${scope}"]`); await page.waitForTimeout(400);
  }
  const last = findBodies(s).at(-1);
  ok(!('StudyDate' in last.Query), '"all" must not send a date window');
  const thirty = findBodies(s).find(q => /^\d{8}-\d{8}$/.test(q.Query.StudyDate || ''));
  ok(thirty, 'no ranged StudyDate query was sent for 7/30 days');
  await ctx.close();
});

check('modality filter narrows the query', async (b, s) => {
  const { page, ctx } = await openPortal(b, s);
  await page.click('#scopeChips .chip[data-scope="all"]'); await page.waitForTimeout(400);
  await page.click('#modChips .chip[data-mod="CT"]'); await page.waitForTimeout(600);
  eq(findBodies(s).at(-1).Query.ModalitiesInStudy, 'CT', 'modality filter');
  await ctx.close();
});

check('a study opens with its series', async (b, s) => {
  const { page, ctx } = await openPortal(b, s);
  await page.locator('#results .card, #results tbody tr').first().click();
  await page.waitForSelector('#sheet[open]', { timeout: 8000 });
  await page.waitForTimeout(700);
  const txt = await page.textContent('#sheet');
  ok(/series/i.test(txt), 'study sheet shows no series');
  ok(s.requests.some(r => /^studies\/.+\/series$/.test(r.path)), 'series were never fetched');
  await ctx.close();
});

check('viewer buttons are built from the server\'s own plugin list', async (b, s) => {
  const { page, ctx } = await openPortal(b, s);
  await page.locator('#results .card, #results tbody tr').first().click();
  await page.waitForSelector('#sheet[open]');
  const labels = await page.locator('#sheetFoot a').allTextContents();
  const joined = labels.join(' ');
  ok(/OHIF/i.test(joined), 'OHIF is loaded on the server but was not offered');
  ok(/Stone/i.test(joined), 'Stone is loaded on the server but was not offered');
  ok(!/Osimis/i.test(joined), 'Osimis is NOT loaded but was offered anyway');
  await ctx.close();
});

check('the OHIF link carries the Orthanc study id, the Stone link the StudyInstanceUID', async (b, s) => {
  const { page, ctx } = await openPortal(b, s);
  await page.locator('#results .card, #results tbody tr').first().click();
  await page.waitForSelector('#sheet[open]');
  const hrefs = await page.locator('#sheetFoot a').evaluateAll(as => as.map(a => a.href));
  const ohif = hrefs.find(h => /ohif/i.test(h)), stone = hrefs.find(h => /stone/i.test(h));
  ok(/study-\d{3}/.test(ohif), `OHIF href lacks the Orthanc study id: ${ohif}`);
  ok(/1\.2\.826\.0\.1\.3680043\.8\.498\.\d+/.test(decodeURIComponent(stone)), `Stone href lacks the StudyInstanceUID: ${stone}`);
  await ctx.close();
});

check('Devices reports one modality answering and one silent', async (b, s) => {
  const { page, ctx } = await openPortal(b, s);
  await page.click('.nav a[data-view="devices"], .nav [data-view="devices"]');
  await page.waitForTimeout(1500);
  const badges = await page.locator('#modalityList .js-status').allTextContents();
  ok(badges.some(t => /answers/i.test(t)), `no device reported as answering: ${JSON.stringify(badges)}`);
  ok(badges.some(t => /no answer/i.test(t)), `the dead device was not reported: ${JSON.stringify(badges)}`);
  const txt = await page.textContent('#modalityList');
  ok(/IENGINE_SCU/.test(txt), 'the AE title from ?expand was not shown');
  await ctx.close();
});

check('survives /modalities answering without ?expand (child-resource shape)', async (b, s, browser) => {
  const alt = await startStandInOrthanc({ portalHtml, expandSupported: false });
  try {
    const { page, ctx, pageErrors } = await openPortal(browser, alt);
    await page.click('.nav a[data-view="devices"], .nav [data-view="devices"]');
    await page.waitForTimeout(1500);
    const rows = await page.locator('#modalityList .row').count();
    eq(rows, 2, 'device rows when ?expand is unsupported');
    eq(pageErrors.length, 0, `page errors on the fallback path: ${pageErrors.join(' | ')}`);
    const badges = await page.locator('#modalityList .js-status').allTextContents();
    ok(badges.some(t => /answers/i.test(t)), 'C-ECHO still has to work on the fallback path');
    await ctx.close();
  } finally { await alt.close(); }
});

check('Activity shows arrivals and running jobs', async (b, s) => {
  const { page, ctx } = await openPortal(b, s);
  await page.click('.nav a[data-view="activity"], .nav [data-view="activity"]');
  await page.waitForTimeout(1200);
  ok((await page.locator('#changeList .row').count()) > 0, 'no arrivals listed');
  const jobs = await page.textContent('#jobList');
  ok(/DicomModalityStore/.test(jobs), 'jobs did not render');
  ok(/Running/.test(jobs), 'the running job was not shown');
  await ctx.close();
});

check('System names the index and explains the ordering limitation', async (b, s) => {
  const { page, ctx } = await openPortal(b, s);
  await page.click('.nav a[data-view="system"], .nav [data-view="system"]');
  await page.waitForTimeout(1200);
  const txt = await page.textContent('#view-system');
  ok(/odbc-index/.test(txt), 'the index backend is not named');
  ok(/no server-side ordering/i.test(txt), 'the ODBC ordering limitation is not flagged');
  ok(/sorting in your browser/i.test(txt), 'the explanation of the workaround is missing');
  await ctx.close();
});

check('System publishes the DICOMweb address other systems would use', async (b, s) => {
  const { page, ctx } = await openPortal(b, s);
  await page.click('.nav a[data-view="system"], .nav [data-view="system"]');
  await page.waitForTimeout(1000);
  const txt = await page.textContent('#ifaceList');
  ok(/dicom-web\//.test(txt), 'the DICOMweb endpoint is not shown');
  ok(/PMC-ORTHANC@/.test(txt), 'the C-STORE address is not shown');
  await ctx.close();
});

check('the reading-room dark theme applies', async (b, s) => {
  const { page, ctx } = await openPortal(b, s);
  await page.keyboard.press('t'); await page.waitForTimeout(300);
  eq(await page.evaluate(() => document.documentElement.dataset.theme), 'dark', 'theme after pressing t');
  const bg = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);
  ok(bg !== 'rgba(0, 0, 0, 0)' && bg !== 'rgb(255, 255, 255)', `dark theme did not repaint the body (${bg})`);
  await ctx.close();
});

check('j / k move the cursor and Enter opens the study', async (b, s) => {
  const { page, ctx } = await openPortal(b, s);
  await page.keyboard.press('j'); await page.waitForTimeout(150);
  await page.keyboard.press('j'); await page.waitForTimeout(150);
  ok((await page.locator('.is-cursor').count()) > 0, 'j did not move a cursor onto a row');
  await page.keyboard.press('k'); await page.waitForTimeout(150);
  await page.keyboard.press('Enter');
  await page.waitForSelector('#sheet[open]', { timeout: 8000 });
  await ctx.close();
});

check('g-then-number jumps between screens', async (b, s) => {
  const { page, ctx } = await openPortal(b, s);
  await page.keyboard.press('g'); await page.keyboard.press('3'); await page.waitForTimeout(600);
  eq(await page.evaluate(() => document.querySelector('#view-activity').classList.contains('is-active')), true, 'g3 did not reach Activity');
  await ctx.close();
});

check('no horizontal overflow on a phone', async (b, s) => {
  const { page, ctx } = await openPortal(b, s, { viewport: { width: 390, height: 844 } });
  await page.waitForTimeout(800);
  const over = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  ok(over <= 1, `page scrolls sideways by ${over}px at 390px wide`);
  await ctx.close();
});

check('falls back to clearly-labelled sample data when nothing answers', async (b, s, browser) => {
  const dead = await startStandInOrthanc({ portalHtml });
  const url = dead.portalUrl; await dead.close();      // serve the page, then kill the API
  const live = await startStandInOrthanc({ portalHtml });
  try {
    const { page, ctx } = await openPortal(browser, live, { url: `${live.portalUrl}?api=http://127.0.0.1:1/` });
    eq(await page.textContent('#railEnv'), 'Sample data', 'rail label in fallback mode');
    ok((await page.locator('#results .card, #results tbody tr').count()) > 0, 'sample data produced no rows');
    await ctx.close();
  } finally { await live.close(); }
});

check('the installer\'s config file overrides the defaults', async (b, s, browser) => {
  const cfg = await startStandInOrthanc({ portalHtml,
    config: { siteName: 'PMC Imaging', environment: 'Cathlab archive', viewers: { ohif: 'ohif/viewer?StudyInstanceUIDs={studyUid}' } } });
  try {
    const { page, ctx } = await openPortal(browser, cfg);
    eq(await page.textContent('#railEnv'), 'Cathlab archive', 'environment from pmc-portal.config.json');
    await page.locator('#results .card, #results tbody tr').first().click();
    await page.waitForSelector('#sheet[open]');
    const hrefs = await page.locator('#sheetFoot a').evaluateAll(as => as.map(a => a.href));
    ok(hrefs.some(h => /ohif\/viewer\?StudyInstanceUIDs=/.test(h)), `the configured OHIF template was not used: ${hrefs.join(' ')}`);
    await ctx.close();
  } finally { await cfg.close(); }
});

check('no page errors and nothing unexpected on the wire, across a full walk-through', async (b, s) => {
  const { page, ctx, pageErrors, failedRequests, consoleErrors, badResponses } = await openPortal(b, s);
  for (const v of ['devices', 'activity', 'system', 'worklist']) {
    await page.click(`.nav a[data-view="${v}"], .nav [data-view="${v}"]`); await page.waitForTimeout(900);
  }
  await page.click('#scopeChips .chip[data-scope="all"]'); await page.waitForTimeout(600);
  await page.locator('#results .card, #results tbody tr').first().click();
  await page.waitForSelector('#sheet[open]'); await page.waitForTimeout(600);
  eq(pageErrors.length, 0, `page errors: ${pageErrors.join(' | ')}`);
  // Two expected non-2xx responses, both handled by the page by design:
  //  - the dead modality's C-ECHO (a deliberate 500)
  //  - pmc-portal.config.json, which is optional and 404s until the installer writes it
  const real = failedRequests.filter(f => !/modalities\/.*\/echo/.test(f) && !/pmc-portal\.config\.json/.test(f));
  eq(real.length, 0, `failed requests: ${real.join(' | ')}`);
  eq(consoleErrors.length, 0, `console errors: ${consoleErrors.join(' | ')}`);
  // Exactly two non-2xx responses are expected, and the page handles both:
  //  - 404 /pmc/pmc-portal.config.json : optional, absent until the installer writes it
  //  - 500 /modalities/voyager/echo    : the deliberately silent device
  const unexpected = badResponses.filter(r => !/pmc-portal\.config\.json$/.test(r) && !/\/modalities\/.+\/echo$/.test(r));
  eq(unexpected.length, 0, `unexpected non-2xx responses: ${unexpected.join(' | ')}`);
  await ctx.close();
});

// ---------------------------------------------------------------- the runner
const browser = await chromium.launch();
let pass = 0, fail = 0;
for (const { name, fn } of results) {
  const server = await startStandInOrthanc({ portalHtml });
  try { await fn(browser, server, browser); console.log(`  ok   ${name}`); pass++; }
  catch (e) { console.log(`  FAIL ${name}\n         ${e.message}`); fail++; }
  finally { await server.close(); }
}
await browser.close();
console.log(`\n${pass}/${pass + fail} checks passed`);
process.exit(fail ? 1 : 0);

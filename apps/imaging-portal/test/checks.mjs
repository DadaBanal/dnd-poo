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

check('the worklist still names patients when the index ignores Expand', async (b, s) => {
  // Expand is a request, not a guarantee. An index that does not implement the
  // ExtendedFind keys answers /tools/find with bare ids and no error, and norm()
  // on a string yields a row with no name, no date and no id -- a worklist that
  // looks broken rather than one that says why.
  const flat = await startStandInOrthanc({ portalHtml, findExpandSupported: false });
  try {
    const { page, ctx, pageErrors } = await openPortal(b, flat);
    const rows = await page.locator('#results .card, #results tbody tr').count();
    ok(rows > 0, 'the worklist rendered nothing');
    const text = await page.textContent('#results');
    ok(!/\(no name\)/.test(text), 'the worklist rendered rows with no patient on them');
    ok(/Dela Cruz|Sample|Fixture|Example|Placeholder|Test Patient/i.test(text),
      `no study name reached the worklist: ${text.slice(0, 160)}`);
    eq(pageErrors.length, 0, `page errors: ${pageErrors.join(' | ')}`);
    await ctx.close();
  } finally { await flat.close(); }
});

check('a study still opens when the archive ignores ?expand on child listings', async (b, s) => {
  // Orthanc's OpenAPI says the bare child routes return ids, not objects
  // (VERIFIED 9 Sep 2026). Reading .ID off a string yields undefined, the next
  // request becomes `series//instances`, and the 404 says nothing about why.
  // Here the server ignores ?expand outright, which is the worst case.
  const flat = await startStandInOrthanc({ portalHtml, childExpandSupported: false });
  try {
    const { page, ctx, pageErrors } = await openPortal(b, flat);
    await page.locator('#results .card, #results tbody tr').first().click();
    await page.waitForSelector('#sheet[open]');
    await page.waitForFunction(() => document.querySelectorAll('#seriesWrap .serie').length > 0,
      null, { timeout: 20000 });
    const first = await page.textContent('#seriesWrap .serie b');
    ok(/series/i.test(first), `the series list fell back to something unusable: "${first}"`);
    // and the viewer, which needs the instance list, still opens on it
    await page.click('#openViewer');
    await page.waitForFunction(() => document.querySelector('#viewer')?.dataset.ready === '1', null, { timeout: 30000 });
    await page.waitForFunction(() => document.querySelector('.pane')?.dataset.index !== undefined, null, { timeout: 30000 });
    ok(!/ \/ 0$/.test(await page.textContent('#vwrFoot')), 'the viewer found no frames');
    eq(pageErrors.length, 0, `page errors: ${pageErrors.join(' | ')}`);
    await ctx.close();
  } finally { await flat.close(); }
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

check('the OHIF and Stone links carry the identifier each one actually takes', async (b, s) => {
  const { page, ctx } = await openPortal(b, s);
  await page.locator('#results .card, #results tbody tr').first().click();
  await page.waitForSelector('#sheet[open]');
  const hrefs = await page.locator('#sheetFoot a').evaluateAll(as => as.map(a => a.href));
  const ohif = hrefs.find(h => /ohif/i.test(h)), stone = hrefs.find(h => /stone/i.test(h));
  const uid = /1\.2\.826\.0\.1\.3680043\.8\.498\.\d+/;
  // PMC-ORTHANC01 runs the OHIF plugin with DataSource = dicom-web (MEASURED),
  // whose route takes the StudyInstanceUID. The dicom-json route takes a URL to
  // the plugin's JSON instead; pointing one at the other opens an empty viewer.
  ok(/StudyInstanceUIDs=/.test(decodeURIComponent(ohif)), `OHIF href is not the DICOMweb route: ${ohif}`);
  ok(uid.test(decodeURIComponent(ohif)), `OHIF href lacks the StudyInstanceUID: ${ohif}`);
  ok(uid.test(decodeURIComponent(stone)), `Stone href lacks the StudyInstanceUID: ${stone}`);
  await ctx.close();
});

check('a server configured for dicom-json gets the other OHIF route from its config', async (b, s) => {
  const cfg = await startStandInOrthanc({ portalHtml, config: {
    viewers: { ohif: 'ohif/viewer/dicomjson?url=../studies/{orthancId}/ohif-dicom-json' } } });
  try {
    const { page, ctx } = await openPortal(b, cfg);
    await page.locator('#results .card, #results tbody tr').first().click();
    await page.waitForSelector('#sheet[open]');
    const hrefs = await page.locator('#sheetFoot a').evaluateAll(as => as.map(a => a.href));
    const ohif = hrefs.find(h => /ohif/i.test(h));
    ok(/ohif-dicom-json/.test(decodeURIComponent(ohif)), `the config override did not reach the OHIF link: ${ohif}`);
    ok(/study-\d{3}/.test(ohif), `the dicom-json route needs the Orthanc study id: ${ohif}`);
    await ctx.close();
  } finally { await cfg.close(); }
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

check('the System screen names which build of the portal is running', async (b, s) => {
  // After an update the only honest way to know the new file landed is for the
  // page to say so. Nothing else on this screen is about the page itself.
  const { page, ctx } = await openPortal(b, s);
  await page.click('.nav [data-view="system"]');
  await page.waitForTimeout(600);
  const kv = await page.textContent('#sysKv');
  ok(/Portal/.test(kv), 'the System screen does not name the portal build');
  ok(/\d{4}-\d{2}-\d{2}\s*·\s*[0-9a-f]{12}/.test(kv),
    `the build stamp is missing or malformed: ${kv.slice(0, 200)}`);
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
    const { page, ctx } = await openPortal(browser, live, { url: `${live.portalUrl}?api=/no-archive-here/` });
    eq(await page.textContent('#railEnv'), 'Sample data', 'rail label in fallback mode');
    ok((await page.locator('#results .card, #results tbody tr').count()) > 0, 'sample data produced no rows');
    await ctx.close();
  } finally { await live.close(); }
});

check('a cross-origin ?api= is ignored, not honoured', async (b, s, browser) => {
  // A link like .../pmc/?api=https://evil.example/ must not move the data plane
  // off the hospital's own origin while the address bar still says otherwise.
  const { page, ctx, consoleErrors } = await openPortal(b, s,
    { url: `${s.portalUrl}?api=https://example.invalid/` });
  const base = await page.evaluate(() => document.querySelector('#healthText')?.textContent || '');
  ok(/stand-in/.test(base), `the page did not fall back to the same-origin archive: ${base}`);
  const offOrigin = s.requests.filter(r => /example\.invalid/.test(r.path));
  eq(offOrigin.length, 0, 'requests sent to the attacker origin');
  eq(consoleErrors.length, 0, `console errors: ${consoleErrors.join(' | ')}`);
  await ctx.close();
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


/* ----------------------------------------------------------- the viewer ---
   The portal now carries its own DICOM viewer, so these checks are about the
   things a viewer can get quietly wrong: reading a pixel as the wrong number,
   measuring in the wrong units, showing a stale frame after a scroll, or
   claiming Hounsfield units on a path that cannot produce them.              */

/** Open the portal, find one study by accession, and open it in the viewer. */
async function openViewer(browser, server, accession = 'ACC100001') {
  const opened = await openPortal(browser, server);
  const { page } = opened;
  await page.fill('#q', accession);
  await page.waitForFunction(() => document.querySelectorAll('#results .card, #results tbody tr').length === 1,
    null, { timeout: 15000 });
  await page.locator('#results .card, #results tbody tr').first().click();
  await page.waitForSelector('#sheet[open]');
  await page.click('#openViewer');
  await page.waitForFunction(() => document.querySelector('#viewer')?.dataset.ready === '1', null, { timeout: 20000 });
  await page.waitForFunction(() => document.querySelector('.pane')?.dataset.index !== undefined, null, { timeout: 20000 });
  await page.waitForTimeout(250);
  return opened;
}
/** Centre of the first pane, in page coordinates. */
async function paneCentre(page, n = 0) {
  const box = await page.locator('.pane').nth(n).boundingBox();
  return { x: Math.round(box.x + box.width / 2), y: Math.round(box.y + box.height / 2), box };
}
/** Read the probe readout while the button is held — it hides on release. */
async function probe(page, dx = 0, dy = 0, n = 0) {
  await page.click('#vwrTools [data-tool="probe"]');
  const c = await paneCentre(page, n);
  await page.mouse.move(c.x + dx, c.y + dy);
  await page.mouse.down();
  await page.waitForTimeout(80);
  const text = await page.locator('.pane').nth(n).locator('.pane__probe').innerText();
  await page.mouse.up();
  return text;
}

check('the viewer opens over the worklist and paints the frame', async (b, s) => {
  const { page, ctx, pageErrors } = await openViewer(b, s);
  ok(await page.isVisible('#viewer'), 'the viewer is not visible');
  // Study 001 is a CT with two series, so the modality layout opens it side by
  // side rather than in one pane. A single pane here would mean the hanging
  // rule silently stopped running.
  eq(await page.locator('.pane').count(), 2, 'pane count for a two-series CT');
  // A blank canvas would also "render". Assert the pixels are not all one value.
  const spread = await page.evaluate(() => {
    const c = document.querySelector('.pane canvas');
    const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;
    let min = 255, max = 0;
    for (let i = 0; i < d.length; i += 4) { if (d[i] < min) min = d[i]; if (d[i] > max) max = d[i]; }
    return max - min;
  });
  ok(spread > 40, `the canvas is nearly uniform (spread ${spread}) — nothing was drawn`);
  eq(pageErrors.length, 0, `page errors: ${pageErrors.join(' | ')}`);
  await ctx.close();
});

check('it asks for the stored pixel values, and says so on screen', async (b, s) => {
  const { page, ctx } = await openViewer(b, s);
  ok(s.requests.some(r => /\/numpy$/.test(r.path)), 'the viewer never asked for the pixel array');
  ok((await page.textContent('#vwrFoot')).includes('pixel data'), 'the footer does not report the pixel-data path');
  await ctx.close();
});

check('the pixel probe reports Hounsfield units, not the stored number', async (b, s) => {
  const { page, ctx } = await openViewer(b, s);
  // The phantom's central disc is -100 HU on the first frame. Stored, it is 924.
  // Reporting 924 would be the classic rescale mistake, so assert on the HU.
  const text = await probe(page);
  ok(/-100 HU/.test(text), `probe read "${text}", expected -100 HU`);
  ok(!/924/.test(text), `probe reported the stored value, not the rescaled one: "${text}"`);
  await ctx.close();
});

check('the wheel moves the stack, and the new frame is really new data', async (b, s) => {
  const { page, ctx } = await openViewer(b, s);
  const centre = await paneCentre(page);
  await page.mouse.move(centre.x, centre.y);
  await page.mouse.wheel(0, 120);
  await page.waitForFunction(() => document.querySelector('.pane').dataset.index === '1', null, { timeout: 8000 });
  // Frame 1's disc is -60 HU. If the viewer had merely repainted the old buffer
  // the probe would still read -100, and no pixel comparison would notice.
  const text = await probe(page);
  ok(/-60 HU/.test(text), `after one step the probe read "${text}", expected -60 HU`);
  await ctx.close();
});

check('window and level change the image without going back to the archive', async (b, s) => {
  const { page, ctx } = await openViewer(b, s);
  const before = await page.evaluate(() => document.querySelector('.pane canvas').toDataURL().length);
  const sig = () => page.evaluate(() => {
    const c = document.querySelector('.pane canvas');
    const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;
    let sum = 0; for (let i = 0; i < d.length; i += 4) sum += d[i];
    return Math.round(sum / (d.length / 4));
  });
  const meanBefore = await sig();
  const n = s.requests.length;
  const c = await paneCentre(page);
  await page.mouse.move(c.x, c.y);
  await page.mouse.down({ button: 'right' });
  await page.mouse.move(c.x + 160, c.y + 90, { steps: 8 });
  await page.mouse.up({ button: 'right' });
  await page.waitForTimeout(150);
  const meanAfter = await sig();
  ok(Math.abs(meanAfter - meanBefore) > 4, `window/level did not change the image (${meanBefore} → ${meanAfter})`);
  eq(s.requests.length, n, 'window/level went back to the server — it should be local on the pixel path');
  ok(before > 0, 'canvas produced no data');
  await ctx.close();
});

check('a series the archive cannot decode falls back to the rendered path', async (b, s) => {
  // Study 003 has four series; the stand-in refuses /numpy on the third, the way
  // Orthanc does for a transfer syntax it cannot turn into an array.
  const { page, ctx } = await openViewer(b, s, 'ACC100003');
  await page.locator('#vwrSeries .vseries').nth(2).click();
  await page.waitForFunction(() => document.querySelector('#vwrFoot')?.textContent.includes('server rendered'),
    null, { timeout: 10000 });
  ok(s.requests.some(r => /\/rendered$/.test(r.path)), 'no frame was fetched from /rendered');
  // On that path the ARCHIVE does the windowing, so a window change has to travel
  // with the request. If it did not, the W/L drag would silently do nothing here.
  const box = await page.locator('.pane').first().boundingBox();
  const cx = Math.round(box.x + box.width / 2), cy = Math.round(box.y + box.height / 2);
  await page.mouse.move(cx, cy);
  await page.mouse.down({ button: 'right' });
  await page.mouse.move(cx + 120, cy + 70, { steps: 6 });
  await page.mouse.up({ button: 'right' });
  await page.waitForTimeout(600);
  const windowed = s.requests.filter(r => /\/rendered$/.test(r.path)
    && /window-center=/.test(r.search) && !/window-center=40&/.test(r.search));
  ok(windowed.length > 0, 'the new window never reached the archive on the rendered path');
  await ctx.close();
});

check('a length is measured in millimetres, and twice the line is twice the length', async (b, s) => {
  const { page, ctx } = await openViewer(b, s);
  await page.click('#viewer [data-act="one"]');            // 1:1, so screen px = image px
  await page.click('#vwrTools [data-tool="length"]');
  const c = await paneCentre(page);
  const draw = async (len) => {
    await page.click('#viewer [data-act="clear"]');
    await page.mouse.move(c.x - len / 2, c.y + 20);
    await page.mouse.down();
    await page.mouse.move(c.x + len / 2, c.y + 20, { steps: 6 });
    await page.mouse.up();
    await page.waitForTimeout(120);
    const t = await page.textContent('#vwrNotes');
    const m = /([\d.]+)\s*(mm|cm)/.exec(t);
    ok(m, `no measurement was listed, got "${t}"`);
    return +m[1] * (m[2] === 'cm' ? 10 : 1);
  };
  const short = await draw(20), long = await draw(40);
  // PixelSpacing is 0.6 mm, so 20 image pixels is 12 mm.
  ok(Math.abs(short - 12) < 0.6, `20 px at 0.6 mm/px should read 12 mm, read ${short}`);
  ok(Math.abs(long / short - 2) < 0.06, `doubling the line did not double the length (${short} → ${long})`);
  await ctx.close();
});

check('a region reports the mean of the values inside it, in the modality units', async (b, s) => {
  const { page, ctx } = await openViewer(b, s);
  await page.click('#viewer [data-act="one"]');
  await page.click('#vwrTools [data-tool="ellipse"]');
  const c = await paneCentre(page);
  // Image (38,58) to (58,78): entirely inside the phantom's soft tissue, 40 HU flat.
  await page.mouse.move(c.x - 10, c.y + 10);
  await page.mouse.down();
  await page.mouse.move(c.x + 10, c.y + 30, { steps: 6 });
  await page.mouse.up();
  await page.waitForTimeout(150);
  const text = await page.textContent('#vwrNotes');
  ok(/40 ± 0 HU/.test(text), `region statistics read "${text}", expected a flat 40 HU`);
  ok(/cm²/.test(text), `region did not report an area in cm²: "${text}"`);
  await ctx.close();
});

check('a study opens in the layout its modality is read in', async (b, s) => {
  // ACC100000 is an XA run: angiography is read one pane at a time and played,
  // not tiled. ACC100003 is an ultrasound with four series, same rule.
  const xa = await openViewer(b, s, 'ACC100000');
  eq(await xa.page.locator('.pane').count(), 1, 'XA should open in a single pane');
  await xa.ctx.close();
  const us = await openViewer(b, s, 'ACC100003');
  eq(await us.page.locator('.pane').count(), 1, 'US should open in a single pane');
  await us.ctx.close();
});

check('layouts, linked scroll and cine behave', async (b, s) => {
  const { page, ctx } = await openViewer(b, s, 'ACC100003');
  await page.click('#vwrLayouts [data-layout="2x2"]');
  await page.waitForTimeout(400);
  eq(await page.locator('.pane').count(), 4, 'pane count after 2x2');
  await page.waitForFunction(() => document.querySelectorAll('.pane[data-serie]').length >= 2, null, { timeout: 10000 });
  await page.check('#vwrLinkScroll');
  const before = await page.$$eval('.pane[data-index]', els => els.map(e => e.dataset.index));
  const c = await paneCentre(page);
  await page.mouse.move(c.x, c.y);
  await page.mouse.wheel(0, 120);
  await page.waitForTimeout(500);
  const after = await page.$$eval('.pane[data-index]', els => els.map(e => e.dataset.index));
  ok(after.filter((v, i) => v !== before[i]).length >= 2, `linked scroll moved ${after.filter((v, i) => v !== before[i]).length} pane(s)`);
  await page.click('#vwrLayouts [data-layout="1x1"]');
  await page.click('#vwrCine');
  await page.waitForTimeout(700);
  const moved = await page.getAttribute('.pane', 'data-index');
  await page.click('#vwrCine');
  await page.waitForTimeout(400);
  const stopped = await page.getAttribute('.pane', 'data-index');
  ok(+moved > 0, 'cine did not advance');
  await page.waitForTimeout(400);
  eq(await page.getAttribute('.pane', 'data-index'), stopped, 'cine kept running after being stopped');
  await ctx.close();
});

check('the viewer saves a PNG and closes on Escape', async (b, s) => {
  const { page, ctx } = await openViewer(b, s);
  const [download] = await Promise.all([page.waitForEvent('download'), page.click('#vwrExport')]);
  ok(/\.png$/.test(download.suggestedFilename()), `export filename was ${download.suggestedFilename()}`);
  ok(/PID700001/.test(download.suggestedFilename()), `the export does not name the patient id: ${download.suggestedFilename()}`);
  await page.keyboard.press('Escape');
  await page.waitForTimeout(200);
  ok(!(await page.isVisible('#viewer')), 'Escape did not close the viewer');
  await ctx.close();
});

check('the viewer reaches no origin but the archive it was served from', async (b, s) => {
  const { page, ctx, pageErrors, consoleErrors } = await openViewer(b, s, 'ACC100003');
  const seen = new Set();
  page.on('request', r => seen.add(new URL(r.url()).origin));
  await page.locator('#vwrSeries .vseries').nth(2).click();
  await page.waitForTimeout(600);
  await page.mouse.wheel(0, 240);
  await page.waitForTimeout(600);
  const foreign = [...seen].filter(o => o !== s.origin && o !== 'null');
  eq(foreign.length, 0, `the viewer reached ${foreign.join(', ')}`);
  eq(pageErrors.length, 0, `page errors: ${pageErrors.join(' | ')}`);
  eq(consoleErrors.length, 0, `console errors: ${consoleErrors.join(' | ')}`);
  await ctx.close();
});

check('the sample dataset drives the same viewer, and says it is a sample', async (b, s) => {
  const { page, ctx, pageErrors } = await openPortal(b, s, { url: s.portalUrl + '?demo=1' });
  await page.locator('#results .card, #results tbody tr').first().click();
  await page.waitForSelector('#sheet[open]');
  await page.click('#openViewer');
  await page.waitForFunction(() => document.querySelector('#viewer')?.dataset.ready === '1', null, { timeout: 20000 });
  await page.waitForFunction(() => document.querySelector('.pane')?.dataset.index !== undefined, null, { timeout: 20000 });
  ok((await page.textContent('#vwrFoot')).includes('SAMPLE DATA'),
    'the sample dataset does not announce itself in the viewer');
  eq(pageErrors.length, 0, `page errors: ${pageErrors.join(' | ')}`);
  await ctx.close();
});


check('MPR reslices the stack, and the reconstructed planes carry the same values', async (b, s) => {
  const { page, ctx, pageErrors } = await openViewer(b, s);          // study 001, CT, 40 frames
  await page.click('#vwrMpr');
  await page.waitForFunction(() => document.querySelectorAll('.pane[data-serie]').length === 3, null, { timeout: 30000 });
  const ids = await page.$$eval('.pane[data-serie]', els => els.map(e => e.dataset.serie));
  ok(ids[1].endsWith(':coronal'), `second pane is ${ids[1]}`);
  ok(ids[2].endsWith(':sagittal'), `third pane is ${ids[2]}`);
  // The phantom's disc steps 40 HU per slice from -100, so slice 20 is 700 HU.
  // Both reslices pass through it, and both must read the same number as the
  // axial does -- that is the whole claim a reconstruction makes.
  eq(await page.getAttribute('.pane', 'data-index'), '20', 'axial slice under the crosshair');
  // A reslice puts slice 20 at the vertical centre of the pane, which is the
  // boundary between rows 19 and 20 -- probe a few pixels into row 20 rather
  // than exactly on the edge of it.
  for (const [n, dy] of [[0, 0], [1, 4], [2, 4]]) {
    const text = await probe(page, 0, dy, n);
    ok(/700 HU/.test(text), `pane ${n} probed "${text}", expected 700 HU`);
  }
  // Reconstructed spacing is not the file's spacing, and the footer must say so.
  await page.locator('.pane').nth(1).click();
  ok((await page.textContent('#vwrFoot')).includes('reconstructed'),
    'the footer does not say the spacing is reconstructed');
  eq(pageErrors.length, 0, `page errors: ${pageErrors.join(' | ')}`);
  await ctx.close();
});

check('the crosshair drives every plane from one point', async (b, s) => {
  const { page, ctx } = await openViewer(b, s);
  await page.click('#vwrMpr');
  await page.waitForFunction(() => document.querySelectorAll('.pane[data-serie]').length === 3, null, { timeout: 30000 });
  const before = await page.$$eval('.pane[data-index]', els => els.map(e => e.dataset.index));
  await page.click('#vwrTools [data-tool="cross"]');
  const c = await paneCentre(page, 0);
  await page.mouse.click(c.x + 24, c.y - 18);                        // a different point in the axial plane
  await page.waitForTimeout(500);
  const after = await page.$$eval('.pane[data-index]', els => els.map(e => e.dataset.index));
  ok(after[1] !== before[1] && after[2] !== before[2],
    `coronal and sagittal did not follow the crosshair (${before.join(',')} -> ${after.join(',')})`);
  await ctx.close();
});

check('MPR refuses a series it cannot honestly reconstruct', async (b, s) => {
  // Series 3 of study 003 answers 415 on /numpy, so there are no stored values
  // to stack. A reconstruction built from 8-bit PNGs would look plausible and
  // measure wrong, so the viewer must decline rather than draw one.
  const { page, ctx } = await openViewer(b, s, 'ACC100003');
  await page.locator('#vwrSeries .vseries').nth(2).click();
  await page.waitForFunction(() => document.querySelector('#vwrFoot')?.textContent.includes('server rendered'),
    null, { timeout: 10000 });
  await page.click('#vwrMpr');
  await page.waitForTimeout(700);
  eq(await page.locator('.pane[data-serie]').count(), 1, 'a reconstruction was built anyway');
  ok(/pixel-data path/.test(await page.textContent('#toasts')), 'the refusal did not say why');
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

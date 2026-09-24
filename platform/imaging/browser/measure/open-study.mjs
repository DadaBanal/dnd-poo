// Where the time goes when a study opens in the viewer, phase by phase, on the
// running test platform, without the test runner's tracing (which slows
// Chromium). ci/run.sh runs it after the browser tests and keeps the JSON as
// a measurement. Signed in as the radiologist; synthetic data only.
//
//   node measure/open-study.mjs > /results/measurements-open.json
import fs from 'node:fs';
import { chromium } from '@playwright/test';
import { dismissOhifNotices, firstImage, position } from '../tests/ohif.js';
import trustCa from '../tests/trust-ca.js';

const HOST = process.env.PMC_HOSTNAME;
const base = `https://${HOST}`;
const password = fs.readFileSync(process.env.TEST_USER_PASSWORD_SECRET, 'utf8').trim();
const seed = JSON.parse(fs.readFileSync(`${process.env.RESULTS_DIR || '/results'}/seed.json`, 'utf8'));
const rounds = Number(process.env.ROUNDS || 2);

trustCa();
const browser = await chromium.launch({ args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
const ctx = await browser.newContext({ viewport: { width: 1600, height: 900 } });
const page = await ctx.newPage();
await page.goto(`${base}/pmc/`);
await page.waitForSelector('#username');
await page.fill('#username', 'rad.test');
await page.fill('#password', password);
await page.click('#kc-login');
await page.waitForURL(`${base}/pmc/`);

function phases(entries, t0) {
  // Group every resource by what it is, with first-start and last-end offsets and bytes.
  const groups = {};
  for (const e of entries) {
    const u = new URL(e.name);
    let g = 'other';
    if (/\.js$|\.js\.gz$/.test(u.pathname)) g = 'scripts';
    else if (/\.css$/.test(u.pathname)) g = 'styles';
    else if (/\.wasm$/.test(u.pathname)) g = 'wasm';
    else if (u.pathname.startsWith('/dicom-web/studies') && u.search.includes('StudyInstanceUID') || /^\/dicom-web\/studies\/?$/.test(u.pathname)) g = 'qido';
    else if (/\/dicom-web\/studies\/[^/]+\/series\/[^/]+\/metadata$/.test(u.pathname) || /\/dicom-web\/studies\/[^/]+\/metadata$/.test(u.pathname)) g = 'metadata';
    else if (/\/dicom-web\/studies\/[^/]+\/series$/.test(u.pathname) || /\/dicom-web\/studies\/[^/]+\/series\/[^/]+\/instances$/.test(u.pathname)) g = 'qido';
    else if (/\/frames\//.test(u.pathname)) g = 'frames';
    else if (/\/thumbnail|\/rendered/.test(u.pathname)) g = 'thumbnails';
    else if (/\/bulk\//.test(u.pathname)) g = 'bulkdata';
    else if (u.pathname.startsWith('/oauth2') || u.pathname.startsWith('/auth/')) g = 'session';
    else if (u.pathname.startsWith('/brand/') || /\.(png|svg|woff2?)$/.test(u.pathname)) g = 'assets';
    const x = (groups[g] ||= { n: 0, bytes: 0, transferred: 0, first_start_ms: Infinity, last_end_ms: 0, total_ms: 0 });
    x.n++;
    x.bytes += e.encodedBodySize || 0;      // what the browser used
    x.transferred += e.transferSize || 0;   // what came over the network (0 = from its cache)
    x.first_start_ms = Math.min(x.first_start_ms, Math.round(e.startTime));
    x.last_end_ms = Math.max(x.last_end_ms, Math.round(e.responseEnd));
    x.total_ms += e.duration;
  }
  for (const x of Object.values(groups)) x.total_ms = Math.round(x.total_ms);
  return groups;
}

async function openAndMeasure(kind, expectFrames) {
  const uid = seed[kind].study;
  const t0 = Date.now();
  await page.goto(`${base}/viewer?StudyInstanceUIDs=${uid}`);
  const nav = Date.now() - t0;
  const first = await firstImage(page, t0);
  await dismissOhifNotices(page);
  // Cine: how many distinct frames are shown in 3 seconds.
  let fps = null;
  if (expectFrames) {
    const seen = [];
    const start = Date.now();
    while (Date.now() - start < 3000) {
      const p = await position(page);
      if (p) seen.push(p.at);
      await page.waitForTimeout(20);
    }
    let changes = 0;
    for (let i = 1; i < seen.length; i++) if (seen[i] !== seen[i - 1]) changes++;
    fps = Math.round(changes / 3);
  }
  const timing = await page.evaluate(() => {
    const n = performance.getEntriesByType('navigation')[0];
    return {
      dom_content_loaded_ms: Math.round(n.domContentLoadedEventEnd),
      load_ms: Math.round(n.loadEventEnd),
      resources: performance.getEntriesByType('resource').map((e) => ({
        name: e.name, startTime: e.startTime, responseEnd: e.responseEnd, duration: e.duration,
        transferSize: e.transferSize, encodedBodySize: e.encodedBodySize,
      })),
    };
  });
  return {
    kind, round: undefined, navigation_ms: nav, first_image_ms: first, cine_fps_seen: fps,
    dom_content_loaded_ms: timing.dom_content_loaded_ms, load_ms: timing.load_ms,
    phases: phases(timing.resources),
  };
}

const out = [];
for (let r = 0; r < rounds; r++) {
  for (const [kind, cine] of [['xa', true], ['ct', false]]) {
    const m = await openAndMeasure(kind, cine);
    m.round = r === 0 ? 'cold' : 'warm';
    out.push(m);
  }
}
console.log(JSON.stringify(out, null, 1));
await browser.close();

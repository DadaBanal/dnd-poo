// The reading room (M5.4): the list and the viewer together, the next study
// already loading, the keyboard from the rail to the images and back. As the
// radiologist (signin.setup.js), on the studies tests/seed.py stored.
import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import fs from 'node:fs';
import { HOST, RESULTS, seed, settled } from './people.js';

const base = `https://${HOST}`;
const IMAGE = /W:\s*-?\d|I:\s*\d+\s*\(/; // the viewer's overlay once an image is drawn
const measured = {};

test.afterAll(() => {
  if (Object.keys(measured).length) {
    fs.writeFileSync(`${RESULTS}/measurements-room.json`, JSON.stringify(measured, null, 2));
  }
});

const rail = (page) => page.locator('.wl-rail .wl-body [role="row"]');
const railRow = (page, kind) => rail(page).filter({ hasText: seed[kind].patient_id });
const front = (page) => page.locator('iframe[data-front="true"]');
const back = (page) => page.locator('iframe[data-front="false"]');
const current = (page) => page.getByTestId('current');

// The viewer in a frame has drawn an image (its overlay shows a window or a
// frame position). Watched from inside the page, in one action: each of
// Playwright's own actions snapshots the page for its trace, and two viewer
// documents make that cost more than what is being timed.
function imageIn(page, frame, timeout = 60_000) {
  return page.evaluate(({ frame, timeout, image }) => new Promise((resolve) => {
    const re = new RegExp(image);
    const t0 = performance.now();
    const look = () => {
      const f = document.querySelector(frame);
      const text = f?.contentDocument?.querySelector('[data-cy="viewport-grid"]')?.innerText ?? '';
      if (re.test(text)) return resolve(Math.round(performance.now() - t0));
      if (performance.now() - t0 > timeout) return resolve(null);
      setTimeout(look, 20);
    };
    look();
  }), { frame, timeout, image: IMAGE.source });
}

// Armed before a key is pressed, and read after it: from that key to the
// moment the front viewer shows another study, and to its image, timed
// inside the page (an action that waited on the page would hold the key up).
async function armKeyTimer(page) {
  await page.evaluate((image) => {
    const re = new RegExp(image);
    window.__roomTiming = undefined;
    let pressed = 0;
    const onKey = (e) => { if ((e.key === 'j' || e.key === 'k') && !pressed) pressed = performance.now(); };
    document.addEventListener('keydown', onKey, true);
    const before = document.querySelector('iframe[data-front="true"]')?.dataset.study;
    const t0 = performance.now();
    const done = (value) => { document.removeEventListener('keydown', onKey, true); window.__roomTiming = value; };
    const tick = () => {
      const f = document.querySelector('iframe[data-front="true"]');
      if (f && f.dataset.study !== before) {
        const swapped = performance.now();
        const look = () => {
          // The frame's document must be this study's (a frame that is
          // loading another study still holds the old page for a while).
          const doc = f.contentDocument;
          const here = doc?.location?.href?.includes(f.dataset.study) ?? false;
          const text = here ? doc.querySelector('[data-cy="viewport-grid"]')?.innerText ?? '' : '';
          if (re.test(text)) {
            return done({ study: f.dataset.study, swap_ms: Math.round(swapped - pressed), image_ms: Math.round(performance.now() - pressed) });
          }
          if (performance.now() - t0 > 60_000) return done(null);
          setTimeout(look, 20);
        };
        return look();
      }
      if (performance.now() - t0 > 60_000) return done(null);
      setTimeout(tick, 10);
    };
    tick();
  }, IMAGE.source);
}

async function keyTiming(page) {
  await page.waitForFunction(() => window.__roomTiming !== undefined, null, { timeout: 65_000 });
  return page.evaluate(() => window.__roomTiming);
}

const uid = (kind) => seed[kind].study;

// The studies in the rail's order (newest first), by UID, and the ones
// around the current study: the seeded studies share a minute, so their
// order is the engine's, not the seed's.
async function around(page, kind) {
  const uids = await page.locator('.wl-rail .wl-body [data-study]').evaluateAll((els) => els.map((e) => e.dataset.study));
  const at = uids.indexOf(uid(kind));
  expect(at, `${kind} is in the rail`).toBeGreaterThanOrEqual(0);
  return { next: uids[at + 1], after: uids[at + 2], prev: uids[at - 1] };
}

test('the room shows the study beside the list, with the next one already loading', async ({ page }) => {
  await page.goto(`/pmc/read?study=${uid('cr')}`);
  await expect(railRow(page, 'cr')).toHaveAttribute('aria-selected', 'true');
  await expect(current(page)).toContainText('SYNTHETIC');
  await expect(front(page)).toHaveAttribute('data-study', uid('cr'));
  expect(await imageIn(page, 'iframe[data-front="true"]')).not.toBeNull();
  // The study after it in the rail is loading behind, unseen.
  const { next } = await around(page, 'cr');
  await expect(back(page)).toHaveAttribute('data-study', next);
  await expect(back(page)).toBeHidden();
  expect(await imageIn(page, 'iframe[data-front="false"]')).not.toBeNull();
});

test('J shows the next study at once, K goes back', async ({ page }) => {
  await page.goto(`/pmc/read?study=${uid('cr')}`);
  expect(await imageIn(page, 'iframe[data-front="true"]')).not.toBeNull();
  expect(await imageIn(page, 'iframe[data-front="false"]')).not.toBeNull();
  const { next, after } = await around(page, 'cr');
  await railRow(page, 'cr').click();

  await armKeyTimer(page);
  await page.keyboard.press('j');
  const forward = await keyTiming(page);
  expect(forward).not.toBeNull();
  expect(forward.study).toBe(next);
  await expect(page.locator(`.wl-rail .wl-body [role="row"]:has([data-study="${next}"])`)).toHaveAttribute('aria-selected', 'true');
  await expect(page).toHaveURL(new RegExp(`study=${next}`));
  // And the one after is now loading behind.
  await expect(back(page)).toHaveAttribute('data-study', after);

  // Back: that study is no longer held, so it loads again (the cost of
  // keeping one study ahead, not two).
  await armKeyTimer(page);
  await page.keyboard.press('k');
  const backward = await keyTiming(page);
  expect(backward).not.toBeNull();
  expect(backward.study).toBe(uid('cr'));
  measured.room = {
    j_to_next_study_swapped_ms: forward.swap_ms,
    j_to_next_study_image_ms: forward.image_ms,
    k_to_previous_study_image_ms: backward.image_ms,
  };
  // Preloaded: the next study's image is on screen well inside a second.
  expect(forward.image_ms).toBeLessThan(1_000);
});

test('Enter takes the keyboard to the images, Esc brings it back to the rail', async ({ page }) => {
  await page.goto(`/pmc/read?study=${uid('cr')}`);
  expect(await imageIn(page, 'iframe[data-front="true"]')).not.toBeNull();
  await railRow(page, 'cr').click();
  await page.keyboard.press('Enter');
  await expect.poll(() => page.evaluate(() => document.activeElement?.tagName)).toBe('IFRAME');
  // Esc, pressed inside the viewer, returns to the current row.
  await page.frameLocator('iframe[data-front="true"]').locator('body').press('Escape');
  await expect.poll(() => page.evaluate(() => document.activeElement?.getAttribute('data-key') ?? '')).not.toBe('');
  await expect(railRow(page, 'cr')).toBeFocused();
});

test('R marks the study read and moves on', async ({ page }) => {
  await page.request.delete(`${base}/pmc/api/studies/${uid('cr')}/read`, { headers: { Origin: base } });
  await page.goto(`/pmc/read?study=${uid('cr')}`);
  expect(await imageIn(page, 'iframe[data-front="true"]')).not.toBeNull();
  const { next } = await around(page, 'cr');
  await railRow(page, 'cr').click();
  await page.keyboard.press('r');
  await expect(railRow(page, 'cr')).toContainText('Read');
  await expect(front(page)).toHaveAttribute('data-study', next);
  const r = await page.request.get(`${base}/pmc/api/studies/${uid('cr')}`);
  expect((await r.json()).study.read.reader).toBe('rad.test');
  await page.request.delete(`${base}/pmc/api/studies/${uid('cr')}/read`, { headers: { Origin: base } });
});

for (const colorScheme of ['light', 'dark']) {
  test(`the room passes an accessibility check (WCAG 2.2 AA), ${colorScheme}`, async ({ page }) => {
    await page.emulateMedia({ colorScheme });
    await page.goto(`/pmc/read?study=${uid('cr')}`);
    await expect(railRow(page, 'cr')).toBeVisible();
    await settled(page);
    // The viewer is OHIF's page, not ours: judged by its own tests.
    const found = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'])
      .exclude('iframe')
      .analyze();
    expect(found.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(', ')}`)).toEqual([]);
  });
}

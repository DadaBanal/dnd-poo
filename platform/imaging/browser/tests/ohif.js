// What the tests read off OHIF's screen, in one place.

const IMAGE_ON_SCREEN = /W:\s*-?\d|I:\s*\d+\s*\(/; // the overlay's window, or a frame position

// The viewport overlay reads "I:<instance> (<position>/<count>)".
export async function position(page) {
  const text = await page.locator('[data-cy="viewport-grid"]').first().innerText().catch(() => '');
  const m = text.match(/I:\s*\d+\s*\((\d+)\/(\d+)\)/);
  return m ? { at: Number(m[1]), of: Number(m[2]) } : null;
}

// OHIF's once-a-session investigational-use notice and its first-visit tour:
// click them away if they appear, and return as soon as an image is on screen
// with nothing in the way. Never waits on a dialog that is not there (the old
// fixed timeouts cost 25 s per open, and the tests' timings with it).
export async function dismissOhifNotices(page, timeout = 60_000) {
  const notice = page.getByRole('button', { name: /Confirm and Hide|Accept/i });
  const tour = page.getByText('Skip all');
  const grid = page.locator('[data-cy="viewport-grid"]').first();
  const seen = { notice: false, tour: false };
  const started = Date.now();
  let shownAt = null;
  while (Date.now() - started < timeout) {
    if (!seen.notice && (await notice.isVisible().catch(() => false))) {
      await notice.click().catch(() => {});
      seen.notice = true;
    } else if (!seen.tour && (await tour.isVisible().catch(() => false))) {
      await tour.click().catch(() => {});
      seen.tour = true;
    } else if (IMAGE_ON_SCREEN.test(await grid.innerText().catch(() => ''))) {
      // On a first visit (the notice was shown) the tour can start just after
      // the first image: give it a moment. A session that has seen them is done.
      shownAt ??= Date.now();
      if (!seen.notice || seen.tour || Date.now() - shownAt > 1500) return seen;
    }
    await page.waitForTimeout(50);
  }
  return seen;
}

// When an image is on screen, in ms since `since`.
export async function firstImage(page, since, timeout = 60_000) {
  const grid = page.locator('[data-cy="viewport-grid"]').first();
  while (Date.now() - since < timeout) {
    if (IMAGE_ON_SCREEN.test(await grid.innerText().catch(() => ''))) return Date.now() - since;
    await page.waitForTimeout(25);
  }
  return null;
}

// A cine run is playing when the overlay's frame number keeps moving.
export async function framesSeen(page, tries = 12) {
  const seen = new Set();
  for (let i = 0; i < tries && seen.size < 3; i++) {
    const p = await position(page);
    if (p) seen.add(p.at);
    await page.waitForTimeout(750);
  }
  return seen.size;
}

// What the page transferred for the resources matching `pattern`, in bytes,
// and how many it used from its cache (transferSize 0).
export async function transferred(page, pattern) {
  return page.evaluate((source) => {
    const re = new RegExp(source);
    const hits = performance.getEntriesByType('resource').filter((e) => re.test(new URL(e.name).pathname));
    return {
      count: hits.length,
      bytes: hits.reduce((n, e) => n + (e.transferSize || 0), 0),
      from_cache: hits.filter((e) => e.transferSize === 0).length,
    };
  }, pattern.source);
}

// What the tests read off OHIF's screen, in one place.

// The viewport overlay reads "I:<instance> (<position>/<count>)".
export async function position(page) {
  const text = await page.locator('[data-cy="viewport-grid"]').innerText().catch(() => '');
  const m = text.match(/I:\s*\d+\s*\((\d+)\/(\d+)\)/);
  return m ? { at: Number(m[1]), of: Number(m[2]) } : null;
}

// OHIF's once-a-session investigational-use notice and its first-visit tour.
export async function dismissOhifNotices(page) {
  await page.getByRole('button', { name: /Confirm and Hide|Accept/i }).click({ timeout: 5_000 }).catch(() => {});
  await page.getByText('Skip all').click({ timeout: 20_000 }).catch(() => {});
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

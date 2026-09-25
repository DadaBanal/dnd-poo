// The invented people of the stand-in Active Directory, by Windows logon name
// (identity/test/ad/provision.sh), and how one of them signs in. Every one of
// them shares one test-only password.
import fs from 'node:fs';

export const RESULTS = process.env.RESULTS_DIR || '/results';
export const HOST = process.env.PMC_HOSTNAME;
export const seed = JSON.parse(fs.readFileSync(`${RESULTS}/seed.json`, 'utf8'));
const password = fs.readFileSync(process.env.TEST_USER_PASSWORD_SECRET, 'utf8').trim();

export const people = {
  radiologist: 'rad.test',
  cardiologist: 'card.test',
  referrer: 'ref.test',
  ict: 'ict.test',
  nogroup: 'none.test',
};

// Ask for a page; if it sends us to sign in, sign in as `who`.
export async function signIn(page, who, path = '/') {
  await page.goto(path);
  if (page.url().includes('/auth/realms/pmc/')) {
    await page.fill('#username', people[who]);
    await page.fill('#password', password);
    await page.click('#kc-login');
    await page.waitForLoadState('domcontentloaded');
  }
}

// Wait for the page's entrances to finish before judging it (axe reads the
// colours as they are, and a row still fading in reads too light); the
// endless ones (the live dot, a shimmer) are left alone. A row that mounts
// while the page settles (the table lays itself out again when the preview
// opens beside it) starts its own entrance, so this waits until two frames
// in a row have nothing finite running.
export async function settled(page) {
  await page.evaluate(async () => {
    const running = () => document.getAnimations()
      .filter((a) => a.effect?.getTiming().iterations !== Infinity && a.playState !== 'finished');
    const frame = () => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
    for (let i = 0; i < 40; i++) {
      const now = running();
      if (now.length) {
        await Promise.all(now.map((a) => a.finished.catch(() => {})));
        continue;
      }
      await frame();
      if (!running().length) return;
    }
  });
}

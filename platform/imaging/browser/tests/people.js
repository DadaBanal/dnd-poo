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
// colours as they are); the endless ones (the live dot, a shimmer) are left alone.
export async function settled(page) {
  await page.evaluate(() => Promise.all(document.getAnimations()
    .filter((a) => a.effect?.getTiming().iterations !== Infinity)
    .map((a) => a.finished.catch(() => {}))));
}

// The invented people of the stand-in Entra ID (identity/test/realm-entra-sim.json)
// and how one of them signs in. Every one of them shares one test-only password.
import fs from 'node:fs';

export const RESULTS = process.env.RESULTS_DIR || '/results';
export const HOST = process.env.PMC_HOSTNAME;
export const seed = JSON.parse(fs.readFileSync(`${RESULTS}/seed.json`, 'utf8'));
const password = fs.readFileSync(process.env.TEST_USER_PASSWORD_SECRET, 'utf8').trim();

export const people = {
  radiologist: 'rad.test@pmc.test',
  cardiologist: 'card.test@pmc.test',
  referrer: 'ref.test@pmc.test',
  ict: 'ict.test@pmc.test',
  nogroup: 'none.test@pmc.test',
};

// Ask for a page; if it sends us to sign in, sign in as `who`.
export async function signIn(page, who, path = '/') {
  await page.goto(path);
  if (page.url().includes('/auth/realms/entra-sim/')) {
    await page.fill('#username', people[who]);
    await page.fill('#password', password);
    await page.click('#kc-login');
    await page.waitForLoadState('domcontentloaded');
  }
}

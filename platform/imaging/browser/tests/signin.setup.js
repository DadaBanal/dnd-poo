// Sign in once as the radiologist; the viewer tests reuse the session. Open
// one study here and put OHIF's once-a-session notice and first-visit tour
// behind us: OHIF remembers both in the browser's storage, which is saved with
// the session, so no later test meets them or waits for them.
import { test as setup, expect } from '@playwright/test';
import { RESULTS, HOST, seed, signIn } from './people.js';
import { dismissOhifNotices } from './ohif.js';

setup('the radiologist signs in', async ({ page }) => {
  await signIn(page, 'radiologist', `/viewer?StudyInstanceUIDs=${seed.xa.study}`);
  await expect(page).toHaveURL(new RegExp(`^https://${HOST.replace(/\./g, '\\.')}/viewer`));
  const seen = await dismissOhifNotices(page);
  expect(seen.notice, "OHIF's investigational-use notice, once a session").toBe(true);
  await page.context().storageState({ path: `${RESULTS}/.auth/radiologist.json` });
});

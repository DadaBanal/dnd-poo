// Sign in once as the radiologist; the viewer tests reuse the session.
import { test as setup, expect } from '@playwright/test';
import { RESULTS, HOST, signIn } from './people.js';

setup('the radiologist signs in', async ({ page }) => {
  await signIn(page, 'radiologist', '/viewer');
  await expect(page).toHaveURL(new RegExp(`^https://${HOST.replace(/\./g, '\\.')}/viewer`));
  await page.context().storageState({ path: `${RESULTS}/.auth/radiologist.json` });
});

// The platform through a browser. Chromium runs on the edge network, where
// the front door is the only thing it can reach.
//
//   sign-in  the radiologist signs in once (signin.setup.js)
//   viewer   the viewer, as that radiologist (viewer.spec.js)
//   access   who gets in and what each person may see, each from no session
//            (access.spec.js)
import { defineConfig } from '@playwright/test';

const RESULTS = process.env.RESULTS_DIR || '/results';

export default defineConfig({
  testDir: './tests',
  timeout: 180_000,
  expect: { timeout: 60_000 },
  workers: 1,
  retries: 0,
  reporter: [['list']],
  // Screenshots and traces of a failure land beside the other results.
  outputDir: `${RESULTS}/playwright`,
  use: {
    baseURL: `https://${process.env.PMC_HOSTNAME}`,
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
    // The test certificate comes from a throwaway CA; the tests check the
    // TLS details themselves.
    ignoreHTTPSErrors: true,
    viewport: { width: 1600, height: 900 },
    launchOptions: { args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader'] },
  },
  projects: [
    { name: 'sign-in', testMatch: /signin\.setup\.js/ },
    {
      name: 'viewer',
      testMatch: /viewer\.spec\.js/,
      dependencies: ['sign-in'],
      use: { storageState: `${RESULTS}/.auth/radiologist.json` },
    },
    { name: 'access', testMatch: /access\.spec\.js/ },
  ],
});

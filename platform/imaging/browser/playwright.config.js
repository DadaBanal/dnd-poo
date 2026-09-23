// The platform through a browser. Chromium runs on the edge network, where
// the front door is the only thing it can reach.
import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  timeout: 180_000,
  expect: { timeout: 60_000 },
  workers: 1,
  retries: 0,
  reporter: [['list']],
  // Screenshots and traces of a failure land beside the other results.
  outputDir: `${process.env.RESULTS_DIR || '/results'}/playwright`,
  use: {
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
    baseURL: `https://${process.env.PMC_HOSTNAME}`,
    // The test certificate comes from a throwaway CA; the tests check the
    // TLS details themselves.
    ignoreHTTPSErrors: true,
    viewport: { width: 1600, height: 900 },
    launchOptions: { args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader'] },
  },
});

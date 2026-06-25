import { defineConfig, devices } from '@playwright/test';

/**
 * E2E configuration — validates the REAL stack (Firebase, FastAPI, Postgres,
 * Redis, Celery, S3, InsightFace). Nothing is mocked here; that is the point.
 *
 * Required env (see e2e/.env.e2e.example):
 *   E2E_BASE_URL        frontend origin (default http://localhost:3000)
 *   E2E_STUDIO_EMAIL    a real Firebase studio account
 *   E2E_STUDIO_PASSWORD its password
 *   E2E_EVENT_SLUG      (optional) an existing public event slug for guest tests
 *   E2E_REAL_FACES=1    (optional) enable face-matching happy paths — requires
 *                       real images in e2e/assets/ (see e2e/README.md)
 *
 * Chromium is the default lane. Firefox/WebKit projects are defined but
 * disabled by default — flip E2E_ALL_BROWSERS=1 to fan out.
 */

const BASE_URL = process.env.E2E_BASE_URL ?? 'http://localhost:3000';
const ALL_BROWSERS = process.env.E2E_ALL_BROWSERS === '1';
const CI = !!process.env.CI;

const extraBrowsers = ALL_BROWSERS
  ? [
      { name: 'firefox', use: { ...devices['Desktop Firefox'], storageState: 'e2e/.auth/studio.json' }, dependencies: ['setup'] },
      { name: 'webkit', use: { ...devices['Desktop Safari'], storageState: 'e2e/.auth/studio.json' }, dependencies: ['setup'] },
    ]
  : [];

export default defineConfig({
  testDir: './e2e',
  outputDir: './e2e/.results',
  testIgnore: ['pages/**', 'fixtures/**'],
  fullyParallel: false, // shared backend state — keep ordering deterministic
  forbidOnly: CI,
  retries: CI ? 1 : 0,
  workers: 1, // single worker: real DB/S3 side effects, avoid races
  timeout: 60_000, // face processing + S3 round-trips are slow
  expect: { timeout: 15_000 },
  reporter: [
    ['list'],
    ['html', { outputFolder: 'e2e/.report', open: 'never' }],
    ['json', { outputFile: 'e2e/.report/results.json' }],
  ],
  use: {
    baseURL: BASE_URL,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    actionTimeout: 15_000,
    navigationTimeout: 30_000,
    // Auto-grant camera so the selfie page's getUserMedia path can be exercised
    // when a fake media stream is supplied; file-upload fallback works too.
    permissions: ['camera'],
    launchOptions: {
      args: [
        '--use-fake-ui-for-media-stream',
        '--use-fake-device-for-media-stream',
      ],
    },
  },
  projects: [
    // 1) Logs in via the real Firebase UI once, persists storageState
    //    (incl. IndexedDB, where the Firebase Web SDK keeps its session).
    { name: 'setup', testMatch: /auth\.setup\.ts/ },

    // 2) Authenticated studio lane.
    {
      name: 'chromium',
      testMatch: /(studio|upload|screenshots-studio)\.spec\.ts$/,
      use: { ...devices['Desktop Chrome'], storageState: 'e2e/.auth/studio.json' },
      dependencies: ['setup'],
    },

    // 3) Guest lane — no auth, runs anonymously like a real wedding guest.
    {
      name: 'guest',
      testMatch: /(guest|errors|a11y|screenshots-guest)\.spec\.ts$/,
      use: { ...devices['Desktop Chrome'] },
    },

    ...extraBrowsers,
  ],

  // Optional: let CI boot the frontend itself. Locally we assume it is running.
  webServer: process.env.E2E_START_SERVER
    ? {
        command: 'npm run start',
        url: BASE_URL,
        reuseExistingServer: !CI,
        timeout: 120_000,
      }
    : undefined,
});

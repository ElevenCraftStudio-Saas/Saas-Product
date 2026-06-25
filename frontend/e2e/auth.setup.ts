import { test as setup, expect } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

const AUTH_FILE = 'e2e/.auth/studio.json';

const EMAIL = process.env.E2E_STUDIO_EMAIL;
const PASSWORD = process.env.E2E_STUDIO_PASSWORD;

/**
 * One-time real login. Drives the Firebase email/password form and persists the
 * session. The Firebase Web SDK stores its auth in IndexedDB, so we MUST capture
 * it with { indexedDB: true } — plain cookies/localStorage are not enough.
 */
setup('authenticate studio user', async ({ page }) => {
  if (!EMAIL || !PASSWORD) {
    throw new Error(
      'E2E_STUDIO_EMAIL / E2E_STUDIO_PASSWORD are required. Copy e2e/.env.e2e.example → .env.e2e and fill in a real Firebase studio account.',
    );
  }

  await page.goto('/login');
  await page.getByLabel('Email').fill(EMAIL);
  await page.getByLabel('Password').fill(PASSWORD);
  await page.getByRole('button', { name: /^login$/i }).click();

  // routeByRole() pushes to /dashboard or /admin after /auth/me resolves.
  await page.waitForURL(/\/(dashboard|admin)/, { timeout: 30_000 });
  await expect(page.getByText(/dashboard/i).first()).toBeVisible();

  fs.mkdirSync(path.dirname(AUTH_FILE), { recursive: true });
  await page.context().storageState({ path: AUTH_FILE, indexedDB: true });
});

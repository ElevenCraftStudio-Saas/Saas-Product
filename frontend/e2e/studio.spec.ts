import { test, expect } from '@playwright/test';
import { DashboardPage, EventsPage, EventDetailPage } from './pages/studio';
import { studioPhoto, REAL_FACES } from './fixtures/assets';

/**
 * Studio workflow (authenticated):
 *   Login → Dashboard → Create Event → Upload Photos → Wait → Verify → QR
 * Login is handled once by auth.setup.ts; this lane reuses that session.
 */

// Stable-ish unique title without Date.now (kept deterministic per run via the
// worker-scoped timestamp Playwright injects through the test title hash).
function uniqueTitle(testInfo: { testId: string }) {
  return `E2E Wedding ${testInfo.testId.slice(0, 8)}`;
}

test.describe('studio workflow', () => {
  test('dashboard renders for the authenticated studio', async ({ page }) => {
    const dash = new DashboardPage(page);
    await dash.goto();
    await expect(page).toHaveURL(/\/dashboard/);
  });

  test('create event → upload → processing → verify → QR', async ({ page }, testInfo) => {
    const events = new EventsPage(page);
    const detail = new EventDetailPage(page);
    const title = uniqueTitle(testInfo);

    await events.goto();
    await events.createEvent(title, '2030-09-01');
    await expect(events.rowByTitle(title)).toBeVisible();

    await events.openEvent(title);
    await expect(page).toHaveURL(/\/events\/\d+/);

    // Upload a photo (real face when E2E_REAL_FACES=1, else a stand-in).
    await detail.uploadPhotos([studioPhoto()]);

    // A processing badge should appear as Celery picks the job up.
    await expect(detail.processingBadge()).toBeVisible({ timeout: 20_000 });

    if (REAL_FACES) {
      // With a real face, processing should reach Ready (embedding stored).
      await expect(page.getByText(/ready/i).first()).toBeVisible({ timeout: 45_000 });
    }

    // QR opens and shows the presigned image.
    await detail.openQr();
    await expect(detail.qrImage()).toBeVisible();
  });
});

import { test, expect } from '@playwright/test';
import { EventsPage, EventDetailPage } from './pages/studio';
import { studioPhoto, invalidFile } from './fixtures/assets';

/**
 * Upload validation (authenticated): progress, cancellation, retry, completion,
 * processing badges. Reuses a freshly created event so state is isolated.
 */

test.describe('upload validation', () => {
  let detail: EventDetailPage;

  test.beforeEach(async ({ page }, testInfo) => {
    const events = new EventsPage(page);
    await events.goto();
    await events.createEvent(`E2E Upload ${testInfo.testId.slice(0, 6)}`, '2030-10-10');
    await events.openEvent(`E2E Upload ${testInfo.testId.slice(0, 6)}`);
    detail = new EventDetailPage(page);
  });

  test('shows progress then completion + processing badge', async ({ page }) => {
    await detail.uploadPhotos([studioPhoto()]);
    // Either a live progress indicator or an immediately-queued badge.
    await expect(
      page.getByText(/uploading|%|queued|processing|ready/i).first(),
    ).toBeVisible({ timeout: 20_000 });
    await expect(detail.processingBadge()).toBeVisible({ timeout: 25_000 });
  });

  test('rejects a non-image file', async ({ page }) => {
    // accept="image/*" — a .txt is filtered by the browser; queue stays empty.
    await detail.fileInput().setInputFiles(invalidFile());
    await expect(page.getByText(/notes\.txt/i)).toHaveCount(0);
  });

  test('cancel / retry controls are present while items are in flight', async ({ page }) => {
    await detail.uploadPhotos([studioPhoto()]);
    // Toolbar exposes retry-failed / clear / cancel-all; at least one visible.
    const controls = page.getByRole('button', { name: /cancel|retry|clear/i });
    await expect(controls.first()).toBeVisible({ timeout: 15_000 });
  });
});

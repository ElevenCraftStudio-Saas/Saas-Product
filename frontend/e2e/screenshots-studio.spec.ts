import { test } from '@playwright/test';
import { EventsPage, EventDetailPage } from './pages/studio';
import { studioPhoto } from './fixtures/assets';

/** Release artifacts — authenticated studio screenshots. */

const DIR = 'e2e/screenshots';

test.describe('screenshots: studio surfaces', () => {
  test('dashboard', async ({ page }) => {
    await page.goto('/dashboard');
    await page.getByRole('heading', { name: /dashboard/i }).first().waitFor();
    await page.screenshot({ path: `${DIR}/02-dashboard.png`, fullPage: true });
  });

  test('event detail + upload', async ({ page }, testInfo) => {
    const events = new EventsPage(page);
    const detail = new EventDetailPage(page);
    const title = `E2E Shot ${testInfo.testId.slice(0, 6)}`;

    await events.goto();
    await events.createEvent(title, '2030-11-11');
    await events.openEvent(title);
    await page.screenshot({ path: `${DIR}/03-event.png`, fullPage: true });

    await detail.uploadPhotos([studioPhoto()]);
    await detail.processingBadge().waitFor({ timeout: 20_000 }).catch(() => {});
    await page.screenshot({ path: `${DIR}/04-upload.png`, fullPage: true });
  });
});

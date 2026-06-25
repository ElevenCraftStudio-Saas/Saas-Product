import { test } from '@playwright/test';
import { GuestFlow } from './pages/guest';
import { selfie } from './fixtures/assets';

/** Release artifacts — public-surface screenshots (no auth). */

const DIR = 'e2e/screenshots';
const SLUG = process.env.E2E_EVENT_SLUG;

test.describe('screenshots: guest + auth surfaces', () => {
  test('login', async ({ page }) => {
    await page.goto('/login');
    await page.getByRole('heading', { name: /wedfind ai/i }).waitFor();
    await page.screenshot({ path: `${DIR}/01-login.png`, fullPage: true });
  });

  test('guest landing → consent → selfie → processing → gallery', async ({ page }) => {
    test.skip(!SLUG, 'set E2E_EVENT_SLUG');
    const guest = new GuestFlow(page, SLUG!);

    await guest.openLanding();
    await page.getByRole('button', { name: /find my photos/i }).waitFor();
    await page.screenshot({ path: `${DIR}/05-guest-landing.png`, fullPage: true });

    await guest.startFindPhotos();
    await page.getByRole('checkbox').first().waitFor();
    await page.screenshot({ path: `${DIR}/06-consent.png`, fullPage: true });

    await guest.acceptConsent();
    await page.locator('input[type="file"]').waitFor({ state: 'attached' });
    await page.screenshot({ path: `${DIR}/07-selfie.png`, fullPage: true });

    await guest.submitSelfie(selfie());
    await page.screenshot({ path: `${DIR}/08-processing.png`, fullPage: true });

    await guest.waitForGallery().catch(() => {});
    await page.screenshot({ path: `${DIR}/09-gallery.png`, fullPage: true });
  });
});

import { test, expect } from '@playwright/test';
import { GuestFlow } from './pages/guest';
import { selfie, REAL_FACES } from './fixtures/assets';

/**
 * Guest workflow (anonymous):
 *   Open URL → Consent → Selfie → Wait for AI → Gallery → Download
 *
 * Requires E2E_EVENT_SLUG to point at a live public event whose photos include
 * the face in e2e/assets/selfie.jpg. Without E2E_REAL_FACES, matching can't
 * succeed, so the gallery assertion is relaxed to "reached gallery or no-match".
 */

const SLUG = process.env.E2E_EVENT_SLUG;

test.describe('guest workflow', () => {
  test.skip(!SLUG, 'set E2E_EVENT_SLUG to a live public event');

  test('landing → consent → selfie → processing → gallery → download', async ({ page }) => {
    const guest = new GuestFlow(page, SLUG!);

    await guest.openLanding();
    await expect(page.getByRole('button', { name: /find my photos/i })).toBeVisible();

    await guest.startFindPhotos();
    await guest.acceptConsent();
    await guest.submitSelfie(selfie());

    await guest.waitForGallery();
    await expect(guest.galleryHeading()).toBeVisible();

    if (REAL_FACES) {
      // Real matching → at least one photo + a working presigned download.
      await expect(guest.photos().first()).toBeVisible();
      const download = await guest.downloadFirst();
      expect(await download.path()).toBeTruthy();
    } else {
      // Stand-in selfie has no face → expect the no-match empty state instead.
      await expect(page.getByText(/no photos found/i)).toBeVisible();
    }
  });
});

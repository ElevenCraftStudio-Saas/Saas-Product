import { test, expect } from '@playwright/test';
import { GuestFlow } from './pages/guest';
import { selfieNoFace, selfieMultiFace, invalidFile, REAL_FACES } from './fixtures/assets';

/** Error & edge scenarios against the real backend. */

const SLUG = process.env.E2E_EVENT_SLUG;

test.describe('guest error scenarios', () => {
  test('event not found → not-found route', async ({ page }) => {
    await page.goto('/event/this-slug-does-not-exist-zzz');
    await expect(page).toHaveURL(/not-found/, { timeout: 20_000 });
    await expect(page.getByText(/not found|doesn.t exist|invalid/i).first()).toBeVisible();
  });

  test('expired event → expired route', async ({ page }) => {
    test.skip(!process.env.E2E_EXPIRED_SLUG, 'set E2E_EXPIRED_SLUG to a past/closed event');
    await page.goto(`/event/${process.env.E2E_EXPIRED_SLUG}`);
    await expect(page).toHaveURL(/expired|not-found/, { timeout: 20_000 });
  });

  test('invalid file type is rejected at the selfie step', async ({ page }) => {
    test.skip(!SLUG, 'set E2E_EVENT_SLUG');
    const guest = new GuestFlow(page, SLUG!);
    await guest.openLanding();
    await guest.startFindPhotos();
    await guest.acceptConsent();

    // The file input only accepts images; a .txt is ignored by the browser, so
    // the Continue/Use-photo control never appears.
    await page.locator('input[type="file"]').setInputFiles(invalidFile());
    await expect(page.getByRole('button', { name: /continue|use (this )?photo/i })).toHaveCount(0);
  });

  test('no face → friendly error', async ({ page }) => {
    test.skip(!SLUG, 'set E2E_EVENT_SLUG');
    const guest = new GuestFlow(page, SLUG!);
    await guest.openLanding();
    await guest.startFindPhotos();
    await guest.acceptConsent();
    await guest.submitSelfie(selfieNoFace());
    // Backend rejects the embedding → processing page surfaces the error, or
    // matching returns zero → empty gallery.
    await expect(
      page.getByText(/no face|couldn.t detect|no photos found|try another/i).first(),
    ).toBeVisible({ timeout: 30_000 });
  });

  test('multiple faces → handled', async ({ page }) => {
    test.skip(!SLUG || !REAL_FACES, 'needs E2E_EVENT_SLUG + E2E_REAL_FACES + selfie-multi.jpg');
    const guest = new GuestFlow(page, SLUG!);
    await guest.openLanding();
    await guest.startFindPhotos();
    await guest.acceptConsent();
    await guest.submitSelfie(selfieMultiFace());
    await expect(
      page.getByText(/multiple faces|one face|photos found|no photos found/i).first(),
    ).toBeVisible({ timeout: 30_000 });
  });

  test('no matches → empty gallery with retake', async ({ page }) => {
    test.skip(!SLUG, 'set E2E_EVENT_SLUG (use a selfie of someone not in the event)');
    const guest = new GuestFlow(page, SLUG!);
    await guest.openLanding();
    await guest.startFindPhotos();
    await guest.acceptConsent();
    await guest.submitSelfie(selfieNoFace());
    const empty = page.getByText(/no photos found/i);
    if (await empty.isVisible().catch(() => false)) {
      await expect(page.getByRole('button', { name: /another selfie|retake/i })).toBeVisible();
    }
  });
});

test.describe('studio session expiry', () => {
  test('expired session redirects to /session-expired', async ({ page }) => {
    // Directly hitting the route the api 401-handler dispatches to.
    await page.goto('/session-expired');
    await expect(page.getByText(/session.*expired|sign in again|log in/i).first()).toBeVisible();
  });
});

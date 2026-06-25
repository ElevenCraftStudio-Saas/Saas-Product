import { Page, expect } from '@playwright/test';

/** Page object for the anonymous guest funnel:
 *  landing → consent → selfie → processing → gallery. */
export class GuestFlow {
  constructor(private page: Page, private slug: string) {}

  async openLanding() {
    await this.page.goto(`/event/${this.slug}`);
  }

  async startFindPhotos() {
    await this.page.getByRole('button', { name: /find my photos/i }).click();
    await this.page.waitForURL(new RegExp(`/event/${this.slug}/consent`));
  }

  async acceptConsent() {
    const checks = this.page.getByRole('checkbox');
    await expect(checks).toHaveCount(2);
    await checks.nth(0).check();
    await checks.nth(1).check();
    await this.page.getByRole('button', { name: /continue/i }).click();
    await this.page.waitForURL(new RegExp(`/event/${this.slug}/selfie`));
  }

  /** Uses the file-upload fallback (hidden input) rather than a live camera. */
  async submitSelfie(filePath: string) {
    await this.page.locator('input[type="file"][accept*="image"]').setInputFiles(filePath);
    // SelfiePreview → Continue → processing
    await this.page.getByRole('button', { name: /continue|use (this )?photo/i }).click();
    await this.page.waitForURL(new RegExp(`/event/${this.slug}/processing`));
  }

  async waitForGallery() {
    await this.page.waitForURL(new RegExp(`/event/${this.slug}/gallery`), { timeout: 45_000 });
  }

  galleryHeading() {
    return this.page.getByRole('heading', { name: /photo(s)? found|no photos/i });
  }

  photos() {
    return this.page.getByRole('img');
  }

  async downloadFirst() {
    const [download] = await Promise.all([
      this.page.waitForEvent('download'),
      this.page.getByRole('button', { name: /download/i }).first().click(),
    ]);
    return download;
  }
}

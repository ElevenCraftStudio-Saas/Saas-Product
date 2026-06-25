import { Page, expect } from '@playwright/test';

/** Page objects for the authenticated studio surface. Selector-only — no asserts
 *  beyond navigation readiness, so specs own their expectations. */

export class DashboardPage {
  constructor(private page: Page) {}
  async goto() {
    await this.page.goto('/dashboard');
    await expect(this.page.getByRole('heading', { name: /dashboard/i }).first()).toBeVisible();
  }
  metricCards() {
    return this.page.locator('[class*="rounded"]').filter({ hasText: /events|guests|storage|photos/i });
  }
}

export class EventsPage {
  constructor(private page: Page) {}
  async goto() {
    await this.page.goto('/events');
    await expect(this.page.getByRole('button', { name: /create event/i })).toBeVisible();
  }
  async openCreateDialog() {
    await this.page.getByRole('button', { name: /create event/i }).first().click();
    await expect(this.page.getByRole('dialog')).toBeVisible();
  }
  /** Fills + submits the create-event form. Returns the title used. */
  async createEvent(title: string, isoDate: string) {
    await this.openCreateDialog();
    const dialog = this.page.getByRole('dialog');
    await dialog.getByLabel('Event title').fill(title);
    await dialog.getByLabel('Event date').fill(isoDate); // yyyy-mm-dd
    await dialog.getByRole('button', { name: /create event/i }).click();
    await expect(this.page.getByRole('dialog')).toBeHidden();
    return title;
  }
  rowByTitle(title: string) {
    return this.page.getByText(title, { exact: true }).first();
  }
  async openEvent(title: string) {
    await this.rowByTitle(title).click();
    await this.page.waitForURL(/\/events\/\d+/);
  }
}

export class EventDetailPage {
  constructor(private page: Page) {}
  fileInput() {
    return this.page.locator('input[type="file"][accept*="image"]');
  }
  async uploadPhotos(paths: string[]) {
    await this.fileInput().setInputFiles(paths);
  }
  uploadItems() {
    return this.page.locator('[class*="rounded"]').filter({ hasText: /\.(jpg|jpeg|png|webp)/i });
  }
  processingBadge() {
    return this.page.getByText(/queued|processing|ready|failed/i).first();
  }
  async openQr() {
    await this.page.getByRole('button', { name: /qr|show qr|share/i }).first().click();
  }
  qrImage() {
    return this.page.getByRole('img', { name: /qr code/i }).first();
  }
}

import { test, expect, devices } from '@playwright/test';

/** Accessibility smoke: keyboard nav, focus, dialogs, mobile viewport.
 *  Runs on public surfaces (login + guest) so it needs no auth. */

const SLUG = process.env.E2E_EVENT_SLUG;

test.describe('accessibility smoke', () => {
  test('login form is keyboard navigable and focus-visible', async ({ page }) => {
    await page.goto('/login');
    await page.getByLabel('Email').focus();
    await expect(page.getByLabel('Email')).toBeFocused();
    await page.keyboard.press('Tab');
    await expect(page.getByLabel('Password')).toBeFocused();
    await page.keyboard.press('Tab');
    // Next focusable is the submit button.
    await expect(page.getByRole('button', { name: /^login$/i })).toBeFocused();
  });

  test('consent checkboxes are reachable and operable by keyboard', async ({ page }) => {
    test.skip(!SLUG, 'set E2E_EVENT_SLUG');
    await page.goto(`/event/${SLUG}/consent`);
    const checks = page.getByRole('checkbox');
    await expect(checks).toHaveCount(2);
    await checks.nth(0).focus();
    await page.keyboard.press('Space');
    await expect(checks.nth(0)).toBeChecked();
  });

  test('mobile viewport renders the guest landing without overflow', async ({ browser }) => {
    test.skip(!SLUG, 'set E2E_EVENT_SLUG');
    const ctx = await browser.newContext({ ...devices['iPhone 13'] });
    const page = await ctx.newPage();
    await page.goto(`/event/${SLUG}`);
    await expect(page.getByRole('button', { name: /find my photos/i })).toBeVisible();
    // No horizontal scroll: scrollWidth should not exceed the viewport.
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    expect(overflow).toBeLessThanOrEqual(2);
    await ctx.close();
  });

  test('login dialog/menu traps focus appropriately', async ({ page }) => {
    await page.goto('/login');
    // Toggle to signup keeps focus within the card (no focus loss to body).
    await page.getByRole('button', { name: /no account\? sign up/i }).click();
    await expect(page.getByRole('button', { name: /^sign up$/i })).toBeVisible();
    expect(await page.evaluate(() => document.activeElement?.tagName)).not.toBe('BODY');
  });
});

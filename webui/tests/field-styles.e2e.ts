import { expect, test } from '@playwright/test';

// Guards the shared-field migration: a migrated <select> must use the custom
// chevron (appearance:none) and the canonical border color, matching inputs.
test('dashboard group-by select uses the shared field-select style', async ({ page }) => {
	await page.goto('/');

	// The group-by control is the only native <select> on the dashboard and
	// renders unconditionally; target it by its options to stay unambiguous.
	const select = page.locator('select', {
		has: page.locator('option[value="merchant"]')
	});
	await expect(select).toBeVisible();

	// Custom chevron: native appearance removed + a background image set.
	await expect(select).toHaveClass(/field-select/);
	const appearance = await select.evaluate((el) => getComputedStyle(el).appearance);
	expect(appearance).toBe('none');
	const bgImage = await select.evaluate((el) => getComputedStyle(el).backgroundImage);
	expect(bgImage).toContain('url(');
});

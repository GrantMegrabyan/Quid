import { expect, test } from '@playwright/test';
import { buildSeed, seedApiState } from './helpers.js';

test.describe('import page', () => {
	test.beforeEach(async ({ page }) => {
		await seedApiState(page, buildSeed());
	});

	test('does not show the AI categorise toggle', async ({ page }) => {
		await page.goto('/import');

		await expect(page.getByRole('heading', { name: 'Import transactions' })).toBeVisible();
		await expect(page.getByTestId('ai-categorize-toggle')).toHaveCount(0);
	});
});

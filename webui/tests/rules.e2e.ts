import { expect, test } from '@playwright/test';
import { buildSeed, seedApiState } from './helpers.js';

test.describe('import rules page', () => {
	test.beforeEach(async ({ page }) => {
		await seedApiState(
			page,
			buildSeed({
				categories: [
					{ id: 'uncategorized', name: 'Uncategorized', color: '#9ca3af', icon: 'circle-help' },
					{ id: 'cat-food-drink', name: 'Food & Drink', color: '#f97316', icon: 'utensils' }
				],
				expenses: []
			})
		);
	});

	test('create categorize rule with set note and see it in the edit form', async ({ page }) => {
		await page.goto('/rules');

		await page.getByTestId('show-new-rule-form').click();

		await page.getByLabel('Name', { exact: true }).fill('Coffee shops');
		await page.getByLabel('Target category').selectOption({ label: 'Food & Drink' });
		await page.getByLabel('Name value').fill('coffee');
		await page.getByLabel('Set display name').fill('Coffee');
		await page.getByLabel('Set note').fill('Coffee run');

		await page.getByRole('button', { name: 'Add rule' }).click();

		const card = page
			.locator('[data-testid="rule-card"]')
			.filter({ hasText: 'Coffee shops' });
		await expect(card).toBeVisible();

		await card.getByRole('button', { name: 'Edit rule' }).click();

		await expect(card.getByTestId('rule-set-note')).toHaveValue('Coffee run');
	});
});

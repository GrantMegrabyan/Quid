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
				expenses: [
					{
						id: 'exp-coffee-1',
						name: 'Blue Bottle Coffee',
						amount: '6.50',
						date: '2026-04-01',
						categoryId: 'uncategorized',
						note: ''
					},
					{
						id: 'exp-coffee-2',
						name: 'Coffee Cart',
						amount: '3.25',
						date: '2026-04-02',
						categoryId: 'uncategorized',
						note: ''
					},
					{
						id: 'exp-other',
						name: 'Uber',
						amount: '12.00',
						date: '2026-04-03',
						categoryId: 'uncategorized',
						note: ''
					}
				]
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

	test('preview matches a draft rule before saving without mutating data', async ({ page }) => {
		await page.goto('/rules');

		await page.getByTestId('show-new-rule-form').click();
		await page.getByLabel('Name', { exact: true }).fill('Coffee preview');
		await page.getByLabel('Target category').selectOption({ label: 'Food & Drink' });
		await page.getByLabel('Name value').fill('coffee');

		await page.getByTestId('rule-preview-btn').click();

		const results = page.getByTestId('rule-preview-results');
		await expect(results).toBeVisible();
		await expect(results.getByTestId('rule-preview-count')).toHaveText('2');
		const rows = results.getByTestId('rule-preview-row');
		await expect(rows).toHaveCount(2);
		// Newest transaction first (Coffee Cart 2026-04-02 before Blue Bottle 2026-04-01).
		await expect(rows.nth(0)).toContainText('Coffee Cart');
		await expect(rows.nth(1)).toContainText('Blue Bottle Coffee');
		await expect(results).not.toContainText('Uber');

		// The preview list can be hidden again.
		await results.getByTestId('rule-preview-close').click();
		await expect(page.getByTestId('rule-preview-results')).toHaveCount(0);

		// Preview is a dry run: no rule was created.
		await expect(page.locator('[data-testid="rule-card"]')).toHaveCount(0);
	});

	test('preview button requires at least one condition', async ({ page }) => {
		await page.goto('/rules');

		await page.getByTestId('show-new-rule-form').click();
		await page.getByLabel('Name', { exact: true }).fill('Empty preview');
		// matchNameOp defaults to "contains" but value is empty, no other conditions.
		await page.getByTestId('rule-preview-btn').click();

		await expect(page.getByText('Add at least one match condition.').first()).toBeVisible();
		await expect(page.getByTestId('rule-preview-results')).toHaveCount(0);
	});

	test('per-card preview shows matches for a saved rule', async ({ page }) => {
		await page.goto('/rules');

		await page.getByTestId('show-new-rule-form').click();
		await page.getByLabel('Name', { exact: true }).fill('Coffee shops');
		await page.getByLabel('Target category').selectOption({ label: 'Food & Drink' });
		await page.getByLabel('Name value').fill('coffee');
		await page.getByRole('button', { name: 'Add rule' }).click();

		const card = page.locator('[data-testid="rule-card"]').filter({ hasText: 'Coffee shops' });
		await expect(card).toBeVisible();

		await card.getByTestId('rule-card-preview-btn').click();

		const results = card.getByTestId('rule-preview-results');
		await expect(results).toBeVisible();
		await expect(results.getByTestId('rule-preview-count')).toHaveText('2');
		await expect(results.getByTestId('rule-preview-row')).toHaveCount(2);
	});

	test('can unset day of month after saving it', async ({ page }) => {
		await page.goto('/rules');

		await page.getByTestId('show-new-rule-form').click();

		await page.getByLabel('Name', { exact: true }).fill('Monthly rent');
		await page.getByLabel('Target category').selectOption({ label: 'Food & Drink' });
		await page.getByLabel('Name value').fill('rent');
		await page.getByLabel(/Day of month/).fill('1');

		await page.getByRole('button', { name: 'Add rule' }).click();

		const card = page.locator('[data-testid="rule-card"]').filter({ hasText: 'Monthly rent' });
		await expect(card).toBeVisible();

		// Re-open, clear the day of month, and save.
		await card.getByRole('button', { name: 'Edit rule' }).click();
		const dayInput = card.getByLabel(/Day of month/);
		await expect(dayInput).toHaveValue('1');
		await dayInput.fill('');

		await card.getByRole('button', { name: 'Save rule' }).click();

		// Save should succeed (no validation error) and the day should be gone.
		await expect(page.getByText('Rule saved.')).toBeVisible();
		await expect(card).not.toContainText('day of month');

		await card.getByRole('button', { name: 'Edit rule' }).click();
		await expect(card.getByLabel(/Day of month/)).toHaveValue('');
	});
});

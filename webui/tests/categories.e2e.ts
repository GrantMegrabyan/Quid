import { expect, test } from '@playwright/test';
import type { Locator } from '@playwright/test';
import { buildSeed, seedApiState } from './helpers.js';

async function chooseIcon(picker: Locator, key: string): Promise<void> {
	await picker.getByTestId('icon-picker-search').fill(key);
	await picker.locator(`[data-testid="icon-picker-option"][data-icon="${key}"]`).click();
}

test.describe('categories page', () => {
	test.beforeEach(async ({ page }) => {
		await seedApiState(page, buildSeed());
	});

	test('lists seeded categories with the Uncategorized row marked', async ({ page }) => {
		await page.goto('/categories');

		const rows = page.getByTestId('category-row');
		await expect(rows).toHaveCount(3);
		await expect(page.getByTestId('category-uncategorized')).toBeVisible();
		await expect(page.locator('[data-testid="category-icon"][data-icon="shopping-cart"]')).toHaveCount(1);
	});

	test('Uncategorized row exposes no delete button', async ({ page }) => {
		await page.goto('/categories');

		const uncategorizedRow = page.locator(
			'[data-testid="category-row"][data-category-id="uncategorized"]'
		);
		await expect(uncategorizedRow.getByTestId('category-delete-btn')).toHaveCount(0);
		await expect(uncategorizedRow.getByTestId('category-edit-btn')).toBeVisible();
	});

	test('add new category appends a row', async ({ page }) => {
		await page.goto('/categories');

		await page.getByTestId('show-new-category-form').click();
		await chooseIcon(page.getByTestId('new-category-icon'), 'ticket');
		await page.getByTestId('new-category-name').fill('Coffee');
		await page.getByTestId('new-category-submit').click();

		await expect(page.getByTestId('category-row')).toHaveCount(4);
		await expect(
			page.locator('[data-testid="category-row"]').filter({ hasText: 'Coffee' })
		).toBeVisible();
		await expect(page.locator('[data-testid="category-icon"][data-icon="ticket"]')).toHaveCount(1);

		await page.reload();
		await expect(page.locator('[data-testid="category-icon"][data-icon="ticket"]')).toHaveCount(1);
	});

	test('duplicate category name is rejected with inline error', async ({ page }) => {
		await page.goto('/categories');

		await page.getByTestId('show-new-category-form').click();
		await page.getByTestId('new-category-name').fill('groceries');
		await page.getByTestId('new-category-submit').click();

		await expect(page.getByTestId('new-category-error')).toBeVisible();
		await expect(page.getByTestId('category-row')).toHaveCount(3);
	});

	test('edit existing category renames it inline', async ({ page }) => {
		await page.goto('/categories');

		const targetRow = page.locator(
			'[data-testid="category-row"][data-category-id="cat-groceries"]'
		);
		await targetRow.getByTestId('category-edit-btn').click();
		await chooseIcon(targetRow.getByTestId('category-edit-icon'), 'wallet');
		await page.getByTestId('category-edit-name').fill('Food');
		await page.getByTestId('category-edit-save-btn').click();

		await expect(targetRow).toContainText('Food');
		await expect(targetRow.getByTestId('category-icon')).toHaveAttribute('data-icon', 'wallet');
		await expect(targetRow.getByTestId('category-edit-save-btn')).toHaveCount(0);
	});

	test('delete cascades expenses to Uncategorized and shows notice', async ({ page }) => {
		await page.goto('/');
		await expect(page.getByTestId('expense-row')).toHaveCount(2);

		await page.goto('/categories');
		const targetRow = page.locator(
			'[data-testid="category-row"][data-category-id="cat-groceries"]'
		);
		await targetRow.getByTestId('category-delete-btn').click();
		await targetRow.getByTestId('category-delete-confirm-btn').click();

		const notice = page.getByTestId('cascade-notice');
		await expect(notice).toBeVisible();
		await expect(notice).toContainText('moved to Uncategorized');
		await expect(page.getByTestId('category-row')).toHaveCount(2);

		await page.goto('/');
		await expect(page.getByTestId('expense-row')).toHaveCount(2);
		await expect(
			page
				.locator('[data-testid="expense-row"][data-expense-id="exp-seed-1"]')
				.filter({ hasText: 'Uncategorized' })
		).toHaveCount(1);
	});

	test('icon picker exposes the Lucide catalog and searchable seed icons', async ({ page }) => {
		await page.goto('/categories');

		await page.getByTestId('show-new-category-form').click();
		const picker = page.getByTestId('new-category-icon');
		const summary = await picker.getByTestId('icon-picker-summary').innerText();
		const total = Number(summary.match(/of (\d+)/)?.[1] ?? 0);
		expect(total).toBeGreaterThan(91);

		for (const key of ['car-taxi-front', 'ticket', 'repeat']) {
			await picker.getByTestId('icon-picker-search').fill(key);
			await expect(
				picker.locator(`[data-testid="icon-picker-option"][data-icon="${key}"]`)
			).toBeVisible();
		}
	});
});

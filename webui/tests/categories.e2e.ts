import { expect, test } from '@playwright/test';
import { buildSeed, seedLocalStorage } from './helpers.js';

test.describe('categories page', () => {
	test.beforeEach(async ({ page }) => {
		await seedLocalStorage(page, buildSeed());
	});

	test('lists seeded categories with the Uncategorized row marked', async ({ page }) => {
		await page.goto('/categories');

		const rows = page.getByTestId('category-row');
		await expect(rows).toHaveCount(3);
		await expect(page.getByTestId('category-uncategorized')).toBeVisible();
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

		await page.getByTestId('new-category-name').fill('Coffee');
		await page.getByTestId('new-category-submit').click();

		await expect(page.getByTestId('category-row')).toHaveCount(4);
		await expect(
			page.locator('[data-testid="category-row"]').filter({ hasText: 'Coffee' })
		).toBeVisible();
	});

	test('duplicate category name is rejected with inline error', async ({ page }) => {
		await page.goto('/categories');

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
		await page.getByTestId('category-edit-name').fill('Food');
		await page.getByTestId('category-edit-save-btn').click();

		await expect(targetRow).toContainText('Food');
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
});

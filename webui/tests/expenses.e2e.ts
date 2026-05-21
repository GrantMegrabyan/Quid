import { expect, test } from '@playwright/test';
import { buildSeed, seedLocalStorage, THEME_KEY } from './helpers.js';

test.describe('dashboard', () => {
	test.beforeEach(async ({ page }) => {
		await seedLocalStorage(page, buildSeed());
	});

	test('renders both charts and the expense list', async ({ page }) => {
		await page.goto('/');

		await expect(page.getByTestId('monthly-chart')).toBeVisible();
		await expect(page.getByTestId('category-chart')).toBeVisible();
		await expect(page.getByTestId('add-expense-btn')).toBeVisible();

		const rows = page.getByTestId('expense-row');
		await expect(rows).toHaveCount(2);
	});

	test('add expense flow appends a new row', async ({ page }) => {
		await page.goto('/');

		await page.getByTestId('add-expense-btn').click();
		await expect(page.getByTestId('modal-title')).toHaveText('Add expense');

		await page.getByTestId('amount-input').fill('19.95');
		await page.getByTestId('category-select').selectOption('cat-groceries');
		await page.getByTestId('note-input').fill('Coffee beans');
		await page.getByTestId('modal-submit').click();

		await expect(page.getByTestId('modal-title')).toHaveCount(0);
		await expect(page.getByTestId('expense-row')).toHaveCount(3);
		await expect(
			page.getByTestId('expense-row').filter({ hasText: 'Coffee beans' })
		).toHaveCount(1);
	});

	test('edit expense flow updates the row in place', async ({ page }) => {
		await page.goto('/');

		const targetRow = page.locator('[data-testid="expense-row"][data-expense-id="exp-seed-1"]');
		await targetRow.getByTestId('expense-edit-btn').click();

		await expect(page.getByTestId('modal-title')).toHaveText('Edit expense');
		await page.getByTestId('amount-input').fill('77.77');
		await page.getByTestId('note-input').fill('Updated note');
		await page.getByTestId('modal-submit').click();

		await expect(page.getByTestId('modal-title')).toHaveCount(0);
		await expect(targetRow).toContainText('77.77');
		await expect(targetRow).toContainText('Updated note');
	});

	test('delete expense flow: cancel keeps row, confirm removes it', async ({ page }) => {
		await page.goto('/');

		const targetRow = page.locator('[data-testid="expense-row"][data-expense-id="exp-seed-2"]');
		await targetRow.getByTestId('expense-delete-btn').click();
		await expect(targetRow.getByTestId('expense-delete-cancel-btn')).toBeVisible();

		await targetRow.getByTestId('expense-delete-cancel-btn').click();
		await expect(targetRow.getByTestId('expense-delete-cancel-btn')).toHaveCount(0);
		await expect(targetRow).toBeVisible();

		await targetRow.getByTestId('expense-delete-btn').click();
		await targetRow.getByTestId('expense-delete-confirm-btn').click();

		await expect(
			page.locator('[data-testid="expense-row"][data-expense-id="exp-seed-2"]')
		).toHaveCount(0);
		await expect(page.getByTestId('expense-row')).toHaveCount(1);
	});

	test('amount validation rejects non-positive values without saving', async ({ page }) => {
		await page.goto('/');

		await page.getByTestId('add-expense-btn').click();
		await page.getByTestId('amount-input').fill('0');
		await page.getByTestId('category-select').selectOption('cat-groceries');
		await page.getByTestId('modal-submit').click();

		await expect(page.getByTestId('amount-error')).toBeVisible();
		await expect(page.getByTestId('modal-title')).toBeVisible();
		await expect(page.getByTestId('expense-row')).toHaveCount(2);
	});

	test('category select error fires when no category chosen', async ({ page }) => {
		await page.goto('/');

		await page.getByTestId('add-expense-btn').click();
		await page.getByTestId('amount-input').fill('5');
		await page.getByTestId('modal-submit').click();

		await expect(page.getByTestId('category-error')).toBeVisible();
		await expect(page.getByTestId('modal-title')).toBeVisible();
	});
});

test.describe('empty state', () => {
	test.beforeEach(async ({ page }) => {
		await seedLocalStorage(page, buildSeed({ expenses: [] }));
	});

	test('shows empty placeholder when no expenses exist', async ({ page }) => {
		await page.goto('/');

		await expect(page.getByTestId('empty-state')).toBeVisible();
		await expect(page.getByTestId('expense-row')).toHaveCount(0);
		await expect(page.getByTestId('category-chart')).toContainText('No expenses yet');
	});
});

test.describe('theme toggle', () => {
	test.beforeEach(async ({ page }) => {
		await seedLocalStorage(page, buildSeed(), 'light');
	});

	test('toggling theme persists across reload', async ({ page }) => {
		await page.goto('/');

		await expect(page.locator('html')).not.toHaveClass(/\bdark\b/);

		await page.getByTestId('theme-toggle').click();
		await expect(page.locator('html')).toHaveClass(/\bdark\b/);

		const storedAfterToggle = await page.evaluate((key) => localStorage.getItem(key), THEME_KEY);
		expect(storedAfterToggle).toBe('dark');

		await page.reload();
		await expect(page.locator('html')).toHaveClass(/\bdark\b/);
	});
});

test.describe('mobile layout', () => {
	test.use({ viewport: { width: 375, height: 720 } });

	test.beforeEach(async ({ page }) => {
		await seedLocalStorage(page, buildSeed());
	});

	test('dashboard has no horizontal overflow on a 375px viewport', async ({ page }) => {
		await page.goto('/');
		await expect(page.getByTestId('monthly-chart')).toBeVisible();

		const overflow = await page.evaluate(() => ({
			scroll: document.documentElement.scrollWidth,
			client: document.documentElement.clientWidth
		}));
		expect(overflow.scroll).toBeLessThanOrEqual(overflow.client);
	});
});

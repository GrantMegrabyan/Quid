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

	test('shows three import tabs', async ({ page }) => {
		await page.goto('/import');

		await expect(page.getByTestId('import-tab-csv')).toBeVisible();
		await expect(page.getByTestId('import-tab-single')).toBeVisible();
		await expect(page.getByTestId('import-tab-freeform')).toBeVisible();

		// CSV is the default panel.
		await expect(page.getByTestId('select-import-files')).toBeVisible();
	});

	test('adds a single transaction via the form', async ({ page }) => {
		await page.goto('/import');
		await page.getByTestId('import-tab-single').click();

		await expect(page.getByTestId('import-panel-single')).toBeVisible();
		await page.getByTestId('name-input').fill('Greggs');
		await page.getByTestId('amount-input').fill('4.20');
		// Date defaults to today; leave it.
		await page.getByTestId('category-select').selectOption('cat-groceries');
		await page.getByTestId('importance-select').selectOption('discretionary');
		await page.getByTestId('note-input').fill('Sausage roll');

		const requests: number[] = [];
		page.on('response', (res) => {
			if (res.url().includes('/api/v1/expenses') && res.request().method() === 'POST') {
				requests.push(res.status());
			}
		});

		await page.getByTestId('single-add-submit').click();

		await expect(page.getByTestId('import-banner')).toBeVisible();
		expect(requests.some((status) => status >= 400)).toBe(false);

		// The new transaction shows on the dashboard list.
		await page.goto('/');
		await expect(page.getByText('Greggs').first()).toBeVisible();
	});

	test('freeform tab exposes input and parse control', async ({ page }) => {
		await page.goto('/import');
		await page.getByTestId('import-tab-freeform').click();

		await expect(page.getByTestId('import-panel-freeform')).toBeVisible();
		await expect(page.getByTestId('freeform-input')).toBeVisible();
		await expect(page.getByTestId('freeform-parse')).toBeVisible();
	});
});

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

	test('freeform AI import lets the user edit the amount before saving', async ({ page }) => {
		// Mock the AI preview so the test does not hit OpenRouter. The preview
		// returns a single create row the user can review and edit.
		await page.route('**/api/v1/expenses/import-freeform/preview', async (route) => {
			await route.fulfill({
				status: 200,
				contentType: 'application/json',
				body: JSON.stringify({
					importId: 'imp-freeform-1',
					rows: [
						{
							previewRowId: 'row-0',
							filename: 'AI free-form',
							sourceRow: 2,
							dedupeKeyHash: 'abc123',
							name: 'Coffee',
							amount: 3.5,
							date: '2026-01-15',
							note: '',
							kind: 'create',
							suggestedCategory: { id: 'cat-groceries', name: 'Groceries', exists: true },
							suggestedImportance: 'important'
						}
					],
					summary: {
						creates: 1,
						categoryUpdates: 0,
						hiddenDuplicates: 0,
						excluded: 0,
						invalidRows: 0,
						aiCategorized: 1
					},
					files: [{ filename: 'AI free-form', rows: 1, imported: 1, skippedDuplicates: 0, skippedExcluded: 0, skippedInvalidRows: 0 }]
				})
			});
		});

		// Capture the confirm payload so we can assert the edited amount is sent.
		let confirmedAmount: number | null = null;
		await page.route('**/api/v1/expenses/import-freeform/confirm', async (route) => {
			const body = route.request().postDataJSON() as {
				creates: { amount: number }[];
			};
			confirmedAmount = body.creates[0]?.amount ?? null;
			await route.fulfill({
				status: 201,
				contentType: 'application/json',
				body: JSON.stringify({
					created: 1,
					updated: 0,
					skippedDuplicates: 0,
					skippedStaleUpdates: 0,
					keptExisting: 0,
					categoriesCreated: [],
					expenses: []
				})
			});
		});

		await page.goto('/import');
		await page.getByTestId('import-tab-freeform').click();
		await page.getByTestId('freeform-input').fill('coffee 3.50 yesterday');
		await page.getByTestId('freeform-parse').click();

		// The amount surfaces in an editable input pre-filled with the parsed value.
		const amountInput = page.getByTestId('review-amount-input');
		await expect(amountInput).toBeVisible();
		await expect(amountInput).toHaveValue('3.50');

		// Edit the amount, then confirm.
		await amountInput.fill('9.99');
		await page.getByTestId('freeform-confirm').click();

		await expect(page.getByTestId('import-banner')).toHaveAttribute('data-kind', 'success');
		expect(confirmedAmount).toBe(9.99);
	});

	test('freeform AI import blocks confirm when the amount is invalid', async ({ page }) => {
		await page.route('**/api/v1/expenses/import-freeform/preview', async (route) => {
			await route.fulfill({
				status: 200,
				contentType: 'application/json',
				body: JSON.stringify({
					importId: 'imp-freeform-2',
					rows: [
						{
							previewRowId: 'row-0',
							filename: 'AI free-form',
							sourceRow: 2,
							dedupeKeyHash: 'abc123',
							name: 'Coffee',
							amount: 3.5,
							date: '2026-01-15',
							note: '',
							kind: 'create',
							suggestedCategory: { id: 'cat-groceries', name: 'Groceries', exists: true },
							suggestedImportance: 'important'
						}
					],
					summary: {
						creates: 1,
						categoryUpdates: 0,
						hiddenDuplicates: 0,
						excluded: 0,
						invalidRows: 0,
						aiCategorized: 1
					},
					files: [{ filename: 'AI free-form', rows: 1, imported: 1, skippedDuplicates: 0, skippedExcluded: 0, skippedInvalidRows: 0 }]
				})
			});
		});

		let confirmCalled = false;
		await page.route('**/api/v1/expenses/import-freeform/confirm', async (route) => {
			confirmCalled = true;
			await route.fulfill({ status: 201, contentType: 'application/json', body: '{}' });
		});

		await page.goto('/import');
		await page.getByTestId('import-tab-freeform').click();
		await page.getByTestId('freeform-input').fill('coffee 3.50 yesterday');
		await page.getByTestId('freeform-parse').click();

		const amountInput = page.getByTestId('review-amount-input');
		await expect(amountInput).toBeVisible();
		await amountInput.fill('0');
		await page.getByTestId('freeform-confirm').click();

		await expect(page.getByTestId('import-banner')).toHaveAttribute('data-kind', 'error');
		expect(confirmCalled).toBe(false);
	});
});

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

	test('remembers the active import tab after reload', async ({ page }) => {
		await page.goto('/import');

		await page.getByTestId('import-tab-freeform').click();
		await expect(page.getByTestId('import-panel-freeform')).toBeVisible();

		await page.reload();

		await expect(page.getByTestId('import-panel-freeform')).toBeVisible();
		await expect(page.getByTestId('select-import-files')).toHaveCount(0);
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
							amount: '3.50',
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
		// Money is now transported as a canonical 2dp string ("9.99").
		let confirmedAmount: string | null = null;
		await page.route('**/api/v1/expenses/import-freeform/confirm', async (route) => {
			const body = route.request().postDataJSON() as {
				creates: { amount: string }[];
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
		expect(confirmedAmount).toBe('9.99');
	});

	test('CSV import keeps matched transactions disabled until the user enables the override', async ({
		page
	}) => {
		// Mock the CSV preview so the test does not depend on parsing/AI. It
		// returns one brand-new create row and one matched category_update row.
		await page.route('**/api/v1/expenses/import-csv/preview', async (route) => {
			await route.fulfill({
				status: 200,
				contentType: 'application/json',
				body: JSON.stringify({
					importId: 'imp-csv-1',
					rows: [
						{
							previewRowId: 'row-0',
							filename: 'statement.csv',
							sourceRow: 2,
							dedupeKeyHash: 'newhash',
							name: 'New Cafe',
							amount: '5.25',
							date: '2026-01-10',
							note: '',
							kind: 'create',
							existingExpenseId: null,
							existingCategoryId: null,
							existingCategoryName: null,
							suggestedCategory: { id: 'cat-groceries', name: 'Groceries', exists: true },
							suggestedImportance: 'important',
							existingImportance: null
						},
						{
							previewRowId: 'row-1',
							filename: 'statement.csv',
							sourceRow: 3,
							dedupeKeyHash: 'matchhash',
							name: 'Whole Foods',
							amount: '42.50',
							date: '2026-01-09',
							note: '',
							kind: 'category_update',
							existingExpenseId: 'exp-seed-1',
							existingCategoryId: 'cat-public-transport',
							existingCategoryName: 'Public Transport',
							suggestedCategory: { id: 'cat-groceries', name: 'Groceries', exists: true },
							suggestedImportance: 'discretionary',
							existingImportance: 'important'
						}
					],
					summary: {
						creates: 1,
						categoryUpdates: 1,
						hiddenDuplicates: 0,
						excluded: 0,
						invalidRows: 0,
						aiCategorized: 0
					},
					files: [
						{
							filename: 'statement.csv',
							rows: 2,
							imported: 1,
							skippedDuplicates: 0,
							skippedExcluded: 0,
							skippedInvalidRows: 0
						}
					]
				})
			});
		});

		// Capture the confirm payload so we can assert the matched row's accept flag.
		let categoryUpdates: { accept: boolean }[] | null = null;
		await page.route('**/api/v1/expenses/import-csv/confirm', async (route) => {
			const body = route.request().postDataJSON() as {
				categoryUpdates: { accept: boolean }[];
			};
			categoryUpdates = body.categoryUpdates;
			await route.fulfill({
				status: 201,
				contentType: 'application/json',
				body: JSON.stringify({
					created: 1,
					updated: 1,
					skippedDuplicates: 0,
					skippedStaleUpdates: 0,
					keptExisting: 0,
					categoriesCreated: [],
					expenses: []
				})
			});
		});

		await page.goto('/import');
		await page.getByTestId('import-csv-input').setInputFiles({
			name: 'statement.csv',
			mimeType: 'text/csv',
			buffer: Buffer.from('date,name,amount\n2026-01-10,New Cafe,5.25\n2026-01-09,Whole Foods,42.50\n')
		});

		// Matched row starts disabled: the override toggle reads "Enable to override".
		const toggle = page.getByTestId('toggle-override');
		await expect(toggle).toBeVisible();
		await expect(toggle).toHaveText('Enable to override');
		await expect(toggle).toHaveAttribute('aria-pressed', 'false');

		// Saving now must send accept:false for the matched row (do not override).
		await page.getByTestId('confirm-import').click();
		await expect(page.getByTestId('import-banner')).toHaveAttribute('data-kind', 'success');
		expect(categoryUpdates).not.toBeNull();
		expect(categoryUpdates![0]?.accept).toBe(false);
	});

	test('CSV import sends accept:true once the user enables a matched override', async ({ page }) => {
		await page.route('**/api/v1/expenses/import-csv/preview', async (route) => {
			await route.fulfill({
				status: 200,
				contentType: 'application/json',
				body: JSON.stringify({
					importId: 'imp-csv-2',
					rows: [
						{
							previewRowId: 'row-0',
							filename: 'statement.csv',
							sourceRow: 2,
							dedupeKeyHash: 'matchhash',
							name: 'Whole Foods',
							amount: '42.50',
							date: '2026-01-09',
							note: '',
							kind: 'category_update',
							existingExpenseId: 'exp-seed-1',
							existingCategoryId: 'cat-public-transport',
							existingCategoryName: 'Public Transport',
							suggestedCategory: { id: 'cat-groceries', name: 'Groceries', exists: true },
							suggestedImportance: 'discretionary',
							existingImportance: 'important'
						}
					],
					summary: {
						creates: 0,
						categoryUpdates: 1,
						hiddenDuplicates: 0,
						excluded: 0,
						invalidRows: 0,
						aiCategorized: 0
					},
					files: [
						{
							filename: 'statement.csv',
							rows: 1,
							imported: 0,
							skippedDuplicates: 0,
							skippedExcluded: 0,
							skippedInvalidRows: 0
						}
					]
				})
			});
		});

		let categoryUpdates: { accept: boolean }[] | null = null;
		await page.route('**/api/v1/expenses/import-csv/confirm', async (route) => {
			const body = route.request().postDataJSON() as {
				categoryUpdates: { accept: boolean }[];
			};
			categoryUpdates = body.categoryUpdates;
			await route.fulfill({
				status: 201,
				contentType: 'application/json',
				body: JSON.stringify({
					created: 0,
					updated: 1,
					skippedDuplicates: 0,
					skippedStaleUpdates: 0,
					keptExisting: 0,
					categoriesCreated: [],
					expenses: []
				})
			});
		});

		await page.goto('/import');
		await page.getByTestId('import-csv-input').setInputFiles({
			name: 'statement.csv',
			mimeType: 'text/csv',
			buffer: Buffer.from('date,name,amount\n2026-01-09,Whole Foods,42.50\n')
		});

		// Category select is disabled until the override is enabled.
		const categorySelect = page.locator('.import-row select').first();
		await expect(categorySelect).toBeDisabled();

		const toggle = page.getByTestId('toggle-override');
		await toggle.click();
		await expect(toggle).toHaveText('Disable override');
		await expect(toggle).toHaveAttribute('aria-pressed', 'true');
		await expect(categorySelect).toBeEnabled();

		await page.getByTestId('confirm-import').click();
		await expect(page.getByTestId('import-banner')).toHaveAttribute('data-kind', 'success');
		expect(categoryUpdates).not.toBeNull();
		expect(categoryUpdates![0]?.accept).toBe(true);
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
							amount: '3.50',
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

	test('CSV preview can exclude a brand-new row from the import', async ({ page }) => {
		await page.route('**/api/v1/expenses/import-csv/preview', async (route) => {
			await route.fulfill({
				status: 200,
				contentType: 'application/json',
				body: JSON.stringify({
					importId: 'imp-exclude-1',
					rows: [
						{
							previewRowId: 'row-0',
							filename: 'statement.csv',
							sourceRow: 2,
							dedupeKeyHash: 'hash-a',
							name: 'Keep Me',
							amount: '5.25',
							date: '2026-01-10',
							note: '',
							kind: 'create',
							suggestedCategory: { id: 'cat-groceries', name: 'Groceries', exists: true },
							suggestedImportance: 'important'
						},
						{
							previewRowId: 'row-1',
							filename: 'statement.csv',
							sourceRow: 3,
							dedupeKeyHash: 'hash-b',
							name: 'Drop Me',
							amount: '9.99',
							date: '2026-01-11',
							note: '',
							kind: 'create',
							suggestedCategory: { id: 'cat-groceries', name: 'Groceries', exists: true },
							suggestedImportance: 'important'
						}
					],
					summary: {
						creates: 2,
						categoryUpdates: 0,
						hiddenDuplicates: 0,
						excluded: 0,
						invalidRows: 0,
						aiCategorized: 0
					},
					files: [
						{
							filename: 'statement.csv',
							rows: 2,
							imported: 2,
							skippedDuplicates: 0,
							skippedExcluded: 0,
							skippedInvalidRows: 0
						}
					]
				})
			});
		});

		let creates: { name: string }[] | null = null;
		await page.route('**/api/v1/expenses/import-csv/confirm', async (route) => {
			const body = route.request().postDataJSON() as { creates: { name: string }[] };
			creates = body.creates;
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
		await page.getByTestId('import-csv-input').setInputFiles({
			name: 'statement.csv',
			mimeType: 'text/csv',
			buffer: Buffer.from('date,name,amount\n2026-01-10,Keep Me,5.25\n2026-01-11,Drop Me,9.99\n')
		});

		// Exclude the second (new) row.
		const excludeButtons = page.getByTestId('toggle-exclude');
		await expect(excludeButtons).toHaveCount(2);
		await excludeButtons.nth(1).click();
		await expect(excludeButtons.nth(1)).toHaveText('Include');
		await expect(excludeButtons.nth(1)).toHaveAttribute('aria-pressed', 'true');

		await page.getByTestId('confirm-import').click();
		await expect(page.getByTestId('import-banner')).toHaveAttribute('data-kind', 'success');
		expect(creates).not.toBeNull();
		// Only the kept row is sent; the excluded new row is dropped.
		expect(creates!.map((row) => row.name)).toEqual(['Keep Me']);
	});

	test('CSV preview can hide and show matched rows', async ({ page }) => {
		await page.route('**/api/v1/expenses/import-csv/preview', async (route) => {
			await route.fulfill({
				status: 200,
				contentType: 'application/json',
				body: JSON.stringify({
					importId: 'imp-toggle-1',
					rows: [
						{
							previewRowId: 'row-0',
							filename: 'statement.csv',
							sourceRow: 2,
							dedupeKeyHash: 'hash-new',
							name: 'New Row',
							amount: '5.25',
							date: '2026-01-10',
							note: '',
							kind: 'create',
							suggestedCategory: { id: 'cat-groceries', name: 'Groceries', exists: true },
							suggestedImportance: 'important'
						},
						{
							previewRowId: 'row-1',
							filename: 'statement.csv',
							sourceRow: 3,
							dedupeKeyHash: 'hash-match',
							name: 'Matched Row',
							amount: '42.50',
							date: '2026-01-09',
							note: '',
							kind: 'category_update',
							existingExpenseId: 'exp-seed-1',
							existingCategoryId: 'cat-public-transport',
							existingCategoryName: 'Public Transport',
							suggestedCategory: { id: 'cat-groceries', name: 'Groceries', exists: true },
							suggestedImportance: 'discretionary',
							existingImportance: 'important'
						}
					],
					summary: {
						creates: 1,
						categoryUpdates: 1,
						hiddenDuplicates: 0,
						excluded: 0,
						invalidRows: 0,
						aiCategorized: 0
					},
					files: [
						{
							filename: 'statement.csv',
							rows: 2,
							imported: 1,
							skippedDuplicates: 0,
							skippedExcluded: 0,
							skippedInvalidRows: 0
						}
					]
				})
			});
		});

		await page.goto('/import');
		await page.getByTestId('import-csv-input').setInputFiles({
			name: 'statement.csv',
			mimeType: 'text/csv',
			buffer: Buffer.from('date,name,amount\n2026-01-10,New Row,5.25\n2026-01-09,Matched Row,42.50\n')
		});

		// Both rows visible initially.
		await expect(page.getByText('Matched Row')).toBeVisible();
		await expect(page.getByText('New Row')).toBeVisible();

		// Hide matched: only the new row remains.
		const toggle = page.getByTestId('toggle-show-matched');
		await expect(toggle).toHaveText('Hide 1 matched');
		await toggle.click();
		await expect(page.getByText('Matched Row')).toHaveCount(0);
		await expect(page.getByText('New Row')).toBeVisible();
		await expect(toggle).toHaveText('Show 1 matched');

		// Show again.
		await toggle.click();
		await expect(page.getByText('Matched Row')).toBeVisible();
	});

	test('CSV preview shows the rule-renamed display name instead of the raw merchant', async ({
		page
	}) => {
		// A matching `categorize` rule supplies a display name; the preview must
		// show the FINAL name so the user does not "fix" what the rule fixes.
		await page.route('**/api/v1/expenses/import-csv/preview', async (route) => {
			await route.fulfill({
				status: 200,
				contentType: 'application/json',
				body: JSON.stringify({
					importId: 'imp-rule-name-1',
					rows: [
						{
							previewRowId: 'row-0',
							filename: 'statement.csv',
							sourceRow: 2,
							dedupeKeyHash: 'hash-rule',
							name: 'MARIA ANDREEVA REF 99281',
							displayName: 'Maria Andreeva',
							amount: '500.00',
							date: '2026-04-22',
							note: 'Cleaner',
							kind: 'create',
							suggestedCategory: { id: 'cat-home', name: 'Home', exists: true },
							categoryFromRule: true,
							overriddenCategoryName: 'Shopping',
							suggestedImportance: 'important'
						}
					],
					summary: {
						creates: 1,
						categoryUpdates: 0,
						hiddenDuplicates: 0,
						excluded: 0,
						invalidRows: 0,
						aiCategorized: 0
					},
					files: [
						{
							filename: 'statement.csv',
							rows: 1,
							imported: 1,
							skippedDuplicates: 0,
							skippedExcluded: 0,
							skippedInvalidRows: 0
						}
					]
				})
			});
		});

		await page.goto('/import');
		await page.getByTestId('import-csv-input').setInputFiles({
			name: 'statement.csv',
			mimeType: 'text/csv',
			buffer: Buffer.from('date,name,amount\n2026-04-22,MARIA ANDREEVA REF 99281,500\n')
		});

		// The rule's display name is the primary label, with the raw merchant
		// shown as a "renamed from" hint and the rule's note surfaced.
		await expect(page.getByText('Maria Andreeva', { exact: true })).toBeVisible();
		await expect(page.getByText('renamed from MARIA ANDREEVA REF 99281')).toBeVisible();
		await expect(page.getByText('Cleaner')).toBeVisible();
		// The category cell flags that the category came from a rule and shows
		// what the AI had identified before the rule overrode it.
		await expect(page.getByText('from rule')).toBeVisible();
		await expect(page.getByText('AI suggested: Shopping')).toBeVisible();
	});

	test('CSV preview does not flag the category as rule-driven without a rule', async ({ page }) => {
		await page.route('**/api/v1/expenses/import-csv/preview', async (route) => {
			await route.fulfill({
				status: 200,
				contentType: 'application/json',
				body: JSON.stringify({
					importId: 'imp-no-rule-cat',
					rows: [
						{
							previewRowId: 'row-0',
							filename: 'statement.csv',
							sourceRow: 2,
							dedupeKeyHash: 'hash-norule',
							name: 'Tesco',
							amount: '12.50',
							date: '2026-04-22',
							note: '',
							kind: 'create',
							suggestedCategory: { id: 'cat-groceries', name: 'Groceries', exists: true },
							categoryFromRule: false,
							overriddenCategoryName: null,
							suggestedImportance: 'important'
						}
					],
					summary: {
						creates: 1,
						categoryUpdates: 0,
						hiddenDuplicates: 0,
						excluded: 0,
						invalidRows: 0,
						aiCategorized: 0
					},
					files: [
						{
							filename: 'statement.csv',
							rows: 1,
							imported: 1,
							skippedDuplicates: 0,
							skippedExcluded: 0,
							skippedInvalidRows: 0
						}
					]
				})
			});
		});

		await page.goto('/import');
		await page.getByTestId('import-csv-input').setInputFiles({
			name: 'statement.csv',
			mimeType: 'text/csv',
			buffer: Buffer.from('date,name,amount\n2026-04-22,Tesco,12.50\n')
		});

		await expect(page.getByText('Tesco', { exact: true })).toBeVisible();
		await expect(page.getByText('from rule')).toHaveCount(0);
		await expect(page.getByText(/AI suggested:/)).toHaveCount(0);
	});
});

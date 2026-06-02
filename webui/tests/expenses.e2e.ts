import { expect, test } from '@playwright/test';
import { buildSeed, isoMonthOffset, monthLabelOffset, seedApiState } from './helpers.js';

test.describe('dashboard', () => {
	test.beforeEach(async ({ page }) => {
		await seedApiState(page, buildSeed());
	});

	test('renders cumulative chart and hides optional charts by default', async ({ page }) => {
		await page.goto('/');

		await expect(page.getByTestId('cumulative-chart')).toBeVisible();
		await expect(page.getByTestId('category-chart')).toHaveCount(0);
		await expect(page.getByTestId('selected-month-heading')).toHaveText(monthLabelOffset(0));
		await expect(page.getByTestId('selected-month-total')).toHaveText('£54.50');
		await expect(page.getByTestId('top-category-name')).toHaveText('Groceries');
		await expect(page.getByText('Track spending by month.')).toHaveCount(0);
		await expect(page.getByText('Cumulative monthly expenses')).toHaveCount(0);

		const rows = page.getByTestId('expense-row');
		await expect(rows).toHaveCount(2);
		await expect(rows.filter({ hasText: 'Whole Foods' })).toHaveCount(1);
		await expect(rows.filter({ hasText: 'Uber' })).toHaveCount(1);
		await expect(rows.filter({ hasText: '£42.50' })).toHaveCount(1);
	});

	test('month selector scopes the list and cumulative chart', async ({ page }) => {
		await seedApiState(
			page,
			buildSeed({
				expenses: [
					{
						id: 'exp-current',
						name: 'Current Coffee',
						amount: '10.00',
						date: isoMonthOffset(0, 2),
						categoryId: 'cat-groceries',
						note: ''
					},
					{
						id: 'exp-previous',
						name: 'Previous Train',
						amount: '20.00',
						date: isoMonthOffset(-1, 2),
						categoryId: 'cat-public-transport',
						note: ''
					}
				]
			})
		);

		await page.goto('/');

		await expect(page.getByTestId('month-label')).toHaveText(monthLabelOffset(0));
		await expect(page.getByTestId('selected-month-heading')).toHaveText(monthLabelOffset(0));
		await expect(page.getByTestId('selected-month-total')).toHaveText('£10.00');
		await expect(page.getByText('Current Coffee')).toBeVisible();
		await expect(page.getByText('Previous Train')).toHaveCount(0);
		await expect(page.getByTestId('cumulative-chart')).toBeVisible();

		await page.getByTestId('month-prev').click();

		await expect(page.getByTestId('month-label')).toHaveText(monthLabelOffset(-1));
		await expect(page.getByTestId('selected-month-heading')).toHaveText(monthLabelOffset(-1));
		await expect(page.getByTestId('selected-month-total')).toHaveText('£20.00');
		await expect(page.getByText('Previous Train')).toBeVisible();
		await expect(page.getByText('Current Coffee')).toHaveCount(0);
	});

	test('dashboard requests only the selected month, not other months', async ({ page }) => {
		// The dashboard is a strictly single-month view: it must fetch ONLY the
		// selected month's rows (via date_from/date_to), never other months. We
		// assert the request the page issues is scoped to the current month.
		await seedApiState(
			page,
			buildSeed({
				expenses: [
					{
						id: 'exp-current',
						name: 'Current Coffee',
						amount: '10.00',
						date: isoMonthOffset(0, 2),
						categoryId: 'cat-groceries',
						note: ''
					},
					{
						id: 'exp-previous',
						name: 'Previous Train',
						amount: '20.00',
						date: isoMonthOffset(-1, 2),
						categoryId: 'cat-public-transport',
						note: ''
					}
				]
			})
		);

		const listRequests: URL[] = [];
		page.on('request', (req) => {
			const url = new URL(req.url());
			if (url.pathname.endsWith('/api/v1/expenses')) listRequests.push(url);
		});

		await page.goto('/');
		await expect(page.getByText('Current Coffee')).toBeVisible();

		// Every expense-list request must carry a single-month date range, and the
		// previous month's row must never appear on the current-month dashboard.
		expect(listRequests.length).toBeGreaterThan(0);
		for (const url of listRequests) {
			expect(url.searchParams.get('date_from')).toMatch(/^\d{4}-\d{2}-01$/);
			expect(url.searchParams.get('date_to')).toMatch(/^\d{4}-\d{2}-\d{2}$/);
			// from and to must be within the same month.
			const from = url.searchParams.get('date_from')!.slice(0, 7);
			const to = url.searchParams.get('date_to')!.slice(0, 7);
			expect(from).toBe(to);
		}
		await expect(page.getByText('Previous Train')).toHaveCount(0);
	});

	test('remembers the selected month after reload', async ({ page }) => {
		await page.goto('/');

		await expect(page.getByTestId('month-label')).toHaveText(monthLabelOffset(0));

		await page.getByTestId('month-prev').click();
		await expect(page.getByTestId('month-label')).toHaveText(monthLabelOffset(-1));

		await page.reload();

		// The month must NOT reset to the current month after a reload/update.
		await expect(page.getByTestId('month-label')).toHaveText(monthLabelOffset(-1));
		await expect(page.getByTestId('selected-month-heading')).toHaveText(monthLabelOffset(-1));
	});

	test('optional charts can be enabled and stay enabled after reload', async ({ page }) => {
		await page.goto('/');

		await expect(page.getByTestId('category-chart')).toHaveCount(0);

		await page.getByTestId('toggle-category-chart').check();

		await expect(page.getByTestId('category-chart')).toBeVisible();

		await page.reload();

		await expect(page.getByTestId('category-chart')).toBeVisible();
		await expect(page.getByTestId('toggle-category-chart')).toBeChecked();
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
		await expect(targetRow).toContainText('£77.77');
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
});

test.describe('empty state', () => {
	test.beforeEach(async ({ page }) => {
		await seedApiState(page, buildSeed({ expenses: [] }));
	});

	test('shows empty placeholder when no expenses exist', async ({ page }) => {
		await page.goto('/');

		await expect(page.getByTestId('empty-state')).toBeVisible();
		await expect(page.getByTestId('expense-row')).toHaveCount(0);
		await page.getByTestId('toggle-category-chart').check();
		await expect(page.getByTestId('category-chart')).toContainText('No expenses for this month');
	});
});

test.describe('mobile layout', () => {
	test.use({ viewport: { width: 375, height: 720 } });

	test.beforeEach(async ({ page }) => {
		await seedApiState(page, buildSeed());
	});

	test('dashboard has no horizontal overflow on a 375px viewport', async ({ page }) => {
		await page.goto('/');
		await expect(page.getByTestId('cumulative-chart')).toBeVisible();
		await page.getByTestId('toggle-category-chart').check();
		await expect(page.getByTestId('category-chart')).toBeVisible();
		await page.waitForFunction(
			() => document.documentElement.scrollWidth <= document.documentElement.clientWidth
		);

		const overflow = await page.evaluate(() => ({
			scroll: document.documentElement.scrollWidth,
			client: document.documentElement.clientWidth
		}));
		expect(overflow.scroll).toBeLessThanOrEqual(overflow.client);
	});
});

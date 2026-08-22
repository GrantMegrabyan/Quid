import { expect, test } from '@playwright/test';
import { buildSeed, isoMonthOffset, monthLabelOffset, seedApiState } from './helpers.js';

// The dashboard's window is a SELECTION: a single month (steppable, the
// default) or a rolling period ending today. These tests pin the behaviour
// that distinguishes the two, plus the filter/bulk controls that read from
// whatever window is in view.

const twoMonthSeed = () =>
	buildSeed({
		expenses: [
			{
				id: 'exp-this-month',
				name: 'Current Coffee',
				amount: '10.00',
				date: isoMonthOffset(0, 2),
				categoryId: 'cat-groceries',
				note: ''
			},
			{
				id: 'exp-last-month',
				name: 'Previous Train',
				amount: '20.00',
				date: isoMonthOffset(-1, 2),
				categoryId: 'cat-public-transport',
				note: ''
			}
		]
	});

test.describe('period selection', () => {
	test.beforeEach(async ({ page }) => {
		await seedApiState(page, twoMonthSeed());
	});

	test('a rolling period widens the window past the current month', async ({ page }) => {
		await page.goto('/');

		// Month mode: only this month's row is in the window.
		await expect(page.getByTestId('selected-month-total')).toHaveText('£10.00');
		await expect(page.getByTestId('cumulative-chart')).toBeVisible();

		await page.getByTestId('period-3M').click();

		// Period mode: both rows are in the window, and the chart switches from a
		// cumulative day line to a bar per month.
		await expect(page.getByTestId('selected-month-heading')).toHaveText('Last 3 months');
		await expect(page.getByTestId('selected-month-total')).toHaveText('£30.00');
		await expect(page.getByTestId('monthly-bar-chart')).toBeVisible();
		await expect(page.getByTestId('cumulative-chart')).toHaveCount(0);

		const register = page.getByTestId('transactions-section');
		await expect(register.getByText('Current Coffee')).toBeVisible();
		await expect(register.getByText('Previous Train')).toBeVisible();
	});

	test('the window is in the URL and survives a reload', async ({ page }) => {
		await page.goto('/');
		await page.getByTestId('period-6M').click();
		await expect(page).toHaveURL(/period=6M/);

		await page.reload();
		await expect(page.getByTestId('selected-month-heading')).toHaveText('Last 6 months');

		// A deep link wins over the persisted selection.
		await page.goto(`/?month=${isoMonthOffset(-1).slice(0, 7)}`);
		await expect(page.getByTestId('month-label')).toHaveText(monthLabelOffset(-1));
		await expect(page.getByTestId('selected-month-total')).toHaveText('£20.00');
	});

	test('stepping the month leaves period mode', async ({ page }) => {
		await page.goto('/');
		await page.getByTestId('period-3M').click();
		await expect(page.getByTestId('monthly-bar-chart')).toBeVisible();

		await page.getByTestId('month-prev').click();

		await expect(page.getByTestId('month-label')).toHaveText(monthLabelOffset(-1));
		await expect(page.getByTestId('cumulative-chart')).toBeVisible();
		await expect(page).toHaveURL(/month=/);
	});
});

test.describe('transaction filters', () => {
	test.beforeEach(async ({ page }) => {
		await seedApiState(page, buildSeed());
	});

	test('the category facet narrows the register and reports the count', async ({ page }) => {
		await page.goto('/');
		await expect(page.getByTestId('filter-count')).toHaveText('2 transactions');

		await page.getByTestId('filter-category').click();
		await page.getByRole('option', { name: /Groceries/ }).click();

		await expect(page.getByTestId('filter-count')).toHaveText('Showing 1 of 2');
		const register = page.getByTestId('transactions-section');
		await expect(register.getByText('Whole Foods')).toBeVisible();
		await expect(register.getByText('Uber')).toHaveCount(0);

		await page.getByTestId('filter-clear').click();
		await expect(page.getByTestId('filter-count')).toHaveText('2 transactions');
		await expect(register.getByText('Uber')).toBeVisible();
	});

	test('an amount band excludes rows outside it', async ({ page }) => {
		await page.goto('/');

		await page.getByTestId('filter-amount-min').fill('20');
		await expect(page.getByTestId('filter-count')).toHaveText('Showing 1 of 2');

		const register = page.getByTestId('transactions-section');
		await expect(register.getByText('Whole Foods')).toBeVisible();
		await expect(register.getByText('Uber')).toHaveCount(0);
	});
});

test.describe('bulk actions', () => {
	test.beforeEach(async ({ page }) => {
		await seedApiState(page, buildSeed());
	});

	test('selected rows can be recategorised in one go', async ({ page }) => {
		await page.goto('/');

		const selects = page.getByTestId('expense-select');
		await expect(selects).toHaveCount(2);
		await selects.first().click();
		await selects.nth(1).click();
		await expect(page.getByTestId('bulk-count')).toHaveText('2');

		await page.getByTestId('bulk-categorize').click();
		await page.getByTestId('bulk-category-option').filter({ hasText: 'Public Transport' }).click();

		// Both rows now carry the chosen category, and the selection is released.
		await expect(page.getByTestId('bulk-bar')).toHaveCount(0);
		const pills = page.getByTestId('transactions-section').getByText('Public Transport');
		await expect(pills).toHaveCount(2);
	});

	test('clearing the selection dismisses the bulk bar', async ({ page }) => {
		await page.goto('/');

		await page.getByTestId('expense-select').first().click();
		await expect(page.getByTestId('bulk-bar')).toBeVisible();

		await page.getByTestId('bulk-clear').click();
		await expect(page.getByTestId('bulk-bar')).toHaveCount(0);
	});
});

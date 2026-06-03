import { expect, test } from '@playwright/test';
import { buildSeed, isoMonthOffset, seedApiState } from './helpers.js';

const analyticsSeed = buildSeed({
	categories: [
		{ id: 'uncategorized', name: 'Uncategorized', color: '#9ca3af', icon: 'circle-help' },
		{ id: 'cat-groceries', name: 'Groceries', color: '#22c55e', icon: 'shopping-cart' },
		{ id: 'cat-transport', name: 'Public Transport', color: '#3b82f6', icon: 'train-front' }
	],
	expenses: [
		// Current month
		{
			id: 'exp-a1',
			name: 'Whole Foods',
			amount: '42.50',
			date: isoMonthOffset(0, 4),
			categoryId: 'cat-groceries',
			note: ''
		},
		{
			id: 'exp-a2',
			name: 'Uber',
			amount: '25.00',
			date: isoMonthOffset(0, 6),
			categoryId: 'cat-transport',
			note: ''
		},
		{
			id: 'exp-a3',
			name: 'Tesco',
			amount: '18.75',
			date: isoMonthOffset(0, 9),
			categoryId: 'cat-groceries',
			note: ''
		},
		// Previous month (for MoM + trend data)
		{
			id: 'exp-b1',
			name: 'Whole Foods',
			amount: '30.00',
			date: isoMonthOffset(-1, 5),
			categoryId: 'cat-groceries',
			note: ''
		},
		{
			id: 'exp-b2',
			name: 'Uber',
			amount: '10.00',
			date: isoMonthOffset(-1, 8),
			categoryId: 'cat-transport',
			note: ''
		},
		// A recurring subscription: same name + amount across 4 distinct months
		// (>= 3 months => detected as recurring).
		{
			id: 'exp-sub-0',
			name: 'Netflix',
			amount: '10.99',
			date: isoMonthOffset(0, 2),
			categoryId: 'cat-groceries',
			note: ''
		},
		{
			id: 'exp-sub-1',
			name: 'Netflix',
			amount: '10.99',
			date: isoMonthOffset(-1, 2),
			categoryId: 'cat-groceries',
			note: ''
		},
		{
			id: 'exp-sub-2',
			name: 'Netflix',
			amount: '10.99',
			date: isoMonthOffset(-2, 2),
			categoryId: 'cat-groceries',
			note: ''
		},
		{
			id: 'exp-sub-3',
			name: 'Netflix',
			amount: '10.99',
			date: isoMonthOffset(-3, 2),
			categoryId: 'cat-groceries',
			note: ''
		},
		// A big-ticket outlier so "Biggest purchases" has a clear top row.
		{
			id: 'exp-big',
			name: 'Flights',
			amount: '450.00',
			date: isoMonthOffset(-1, 15),
			categoryId: 'cat-transport',
			note: ''
		}
	]
});

test.describe('analytics page', () => {
	test.beforeEach(async ({ page }) => {
		await seedApiState(page, analyticsSeed);
	});

	test('renders heading, KPIs, movers, and trend chart', async ({ page }) => {
		const consoleErrors: string[] = [];
		page.on('console', (msg) => {
			if (msg.type() === 'error') consoleErrors.push(msg.text());
		});

		await page.goto('/analytics');

		await expect(page.getByRole('heading', { name: 'Analytics', level: 1 })).toBeVisible();
		await expect(page.getByTestId('analytics-period-selector')).toBeVisible();

		// KPI total renders a currency value.
		const total = page.getByTestId('analytics-kpi-total');
		await expect(total).toBeVisible();
		await expect(total).toHaveText(/£\d/);

		// Projection hero KPI is present.
		await expect(page.getByTestId('analytics-kpi-projected')).toBeVisible();

		// Month-over-month KPI renders a signed currency delta.
		await expect(page.getByTestId('analytics-kpi-mom')).toContainText('£');

		// Monthly trend chart container is present.
		await expect(page.getByTestId('analytics-monthly-trend')).toBeVisible();

		// "What changed" attribution: at least one mover row with content.
		await expect(page.getByTestId('analytics-movers')).toBeVisible();
		const moverRows = page.getByTestId('analytics-mover-row');
		await expect(moverRows.first()).toBeVisible();
		await expect(page.getByTestId('analytics-mover-badge').first()).toBeVisible();

		// Actionable core: recurring + biggest purchases.
		await expect(page.getByTestId('analytics-recurring')).toBeVisible();
		await expect(page.getByTestId('analytics-large-transactions')).toBeVisible();

		// Composition + supporting cards.
		await expect(page.getByTestId('analytics-importance-trend')).toBeVisible();
		await expect(page.getByTestId('analytics-category-trend')).toBeVisible();
		await expect(page.getByTestId('analytics-top-merchants')).toBeVisible();
		await expect(page.getByTestId('analytics-distribution')).toBeVisible();

		expect(consoleErrors).toEqual([]);
	});

	test('switching the period keeps the page working', async ({ page }) => {
		const consoleErrors: string[] = [];
		page.on('console', (msg) => {
			if (msg.type() === 'error') consoleErrors.push(msg.text());
		});

		await page.goto('/analytics');
		await expect(page.getByTestId('analytics-kpi-total')).toBeVisible();

		await page.getByTestId('analytics-period-3m').click();
		await expect(page.getByTestId('analytics-period-3m')).toHaveAttribute('aria-pressed', 'true');
		await expect(page.getByTestId('analytics-kpi-total')).toHaveText(/£\d/);

		await page.getByTestId('analytics-period-all').click();
		await expect(page.getByTestId('analytics-period-all')).toHaveAttribute('aria-pressed', 'true');
		await expect(page.getByTestId('analytics-monthly-trend')).toBeVisible();
		await expect(page.getByTestId('analytics-movers')).toBeVisible();

		expect(consoleErrors).toEqual([]);
	});

	test('surfaces recurring payments and biggest purchases', async ({ page }) => {
		await page.goto('/analytics');

		// The recurring panel detects the 4-month Netflix subscription.
		const recurring = page.getByTestId('analytics-recurring');
		await expect(recurring).toBeVisible();
		const recurringRows = page.getByTestId('analytics-recurring-row');
		await expect(recurringRows.first()).toBeVisible();
		await expect(recurring).toContainText('Netflix');

		// The biggest-purchases list leads with the £450 outlier.
		const large = page.getByTestId('analytics-large-transactions');
		await expect(large).toBeVisible();
		const largeRows = page.getByTestId('analytics-large-row');
		await expect(largeRows.first()).toContainText('Flights');
	});

	test('persists the selected period across reloads', async ({ page }) => {
		await page.goto('/analytics');
		await page.getByTestId('analytics-period-12m').click();
		await expect(page.getByTestId('analytics-period-12m')).toHaveAttribute('aria-pressed', 'true');

		await page.reload();
		await expect(page.getByTestId('analytics-period-12m')).toHaveAttribute('aria-pressed', 'true');
	});
});

test.describe('analytics empty state', () => {
	test.beforeEach(async ({ page }) => {
		await seedApiState(page, buildSeed({ expenses: [] }));
	});

	test('shows a friendly empty state with an import link', async ({ page }) => {
		await page.goto('/analytics');

		await expect(page.getByTestId('analytics-empty')).toBeVisible();
		await expect(page.getByRole('link', { name: 'Import transactions' })).toHaveAttribute(
			'href',
			'/import'
		);
	});
});

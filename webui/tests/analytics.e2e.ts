import { expect, test } from '@playwright/test';
import { buildSeed, isoMonthOffset, seedApiState, type SeedExpense } from './helpers.js';

function expense(
	id: string,
	name: string,
	amount: string,
	monthOffset: number,
	day: number,
	categoryId: string
): SeedExpense {
	return { id, name, amount, date: isoMonthOffset(monthOffset, day), categoryId, note: '' };
}

const expenses: SeedExpense[] = [];
let n = 0;
const add = (name: string, amount: string, monthOffset: number, day: number, categoryId: string) =>
	expenses.push(expense(`exp-${n++}`, name, amount, monthOffset, day, categoryId));

// Groceries: £50/mo baseline (months -7..-2), then £120 in the latest
// complete month (-1) split across an old and a NEW merchant.
for (let m = -7; m <= -2; m++) add('Tesco', '50.00', m, 10, 'cat-groceries');
add('Tesco', '60.00', -1, 10, 'cat-groceries');
add('Waitrose', '60.00', -1, 12, 'cat-groceries');

// Transport: £30/mo baseline, absent in -1 -> a decrease.
for (let m = -7; m <= -2; m++) add('TfL', '30.00', m, 5, 'cat-transport');

// Utilities: £100/mo baseline (months -7..-2), then £105 in -1.
// +£5 / +5% is under both floors (£10 and 10%) -> rolls into "other increases".
for (let m = -7; m <= -2; m++) add('Energy Co', '100.00', m, 6, 'cat-utilities');
add('Energy Co', '105.00', -1, 6, 'cat-utilities');

// Netflix price creep: 10.99 in -7..-4, then 12.99 in -3..-1.
for (let m = -7; m <= -4; m++) add('Netflix', '10.99', m, 3, 'cat-subs');
for (let m = -3; m <= -1; m++) add('Netflix', '12.99', m, 3, 'cat-subs');

// iCloud new recurring: first ever in -3, recurring -3..-1.
for (let m = -3; m <= -1; m++) add('iCloud', '2.99', m, 4, 'cat-subs');

// Pret habit: 7 small visits in the latest complete month.
for (let day = 2; day <= 8; day++) add('Pret', '3.50', -1, day, 'cat-eating');

const analyticsSeed = buildSeed({
	categories: [
		{ id: 'uncategorized', name: 'Uncategorized', color: '#9ca3af', icon: 'circle-help' },
		{ id: 'cat-groceries', name: 'Groceries', color: '#22c55e', icon: 'shopping-cart' },
		{ id: 'cat-transport', name: 'Public Transport', color: '#3b82f6', icon: 'train-front' },
		{ id: 'cat-subs', name: 'Subscriptions', color: '#a855f7', icon: 'repeat' },
		{ id: 'cat-eating', name: 'Eating Out', color: '#f97316', icon: 'utensils' },
		{ id: 'cat-utilities', name: 'Utilities', color: '#eab308', icon: 'zap' }
	],
	expenses
});

test.describe('analytics page', () => {
	test.beforeEach(async ({ page }) => {
		await seedApiState(page, analyticsSeed);
	});

	test('renders verdict, went-up zone with drill-down, and savings zone', async ({ page }) => {
		const consoleErrors: string[] = [];
		page.on('console', (msg) => {
			if (msg.type() === 'error') consoleErrors.push(msg.text());
		});

		await page.goto('/analytics');

		await expect(page.getByRole('heading', { name: 'Analytics', level: 1 })).toBeVisible();

		// Verdict header: a currency total and a vs-average badge.
		await expect(page.getByTestId('analytics-verdict-total')).toHaveText(/£\d/);
		await expect(page.getByTestId('analytics-verdict-badge')).toBeVisible();

		// What went up: Groceries is an increase; expanding shows contributors
		// (new-merchant Waitrose) and the month's transactions.
		await expect(page.getByTestId('analytics-wentup')).toBeVisible();
		const groceriesToggle = page.getByTestId('analytics-wentup-toggle-cat-groceries');
		await expect(groceriesToggle).toContainText('Groceries');
		await groceriesToggle.click();
		const detail = page.getByTestId('analytics-wentup-detail-cat-groceries');
		await expect(detail).toContainText('Waitrose');
		await expect(detail).toContainText('(new)');
		await expect(
			page.getByTestId('analytics-wentup-transactions-cat-groceries').locator('li')
		).toHaveCount(2);

		// What went down: Transport decreased.
		await expect(page.getByTestId('analytics-wentdown-toggle')).toContainText('Public Transport');

		// Noise-floor rollup: Energy Co +£5/+5% is under both floors → other increases.
		await expect(page.getByTestId('analytics-wentup-other')).toBeVisible();
		await expect(page.getByTestId('analytics-wentup-other')).toContainText('1 small increase totalling');

		// Savings: creep, new recurring, habit, stack total.
		await expect(page.getByTestId('analytics-creep-item')).toContainText('Netflix');
		await expect(page.getByTestId('analytics-creep-item')).toContainText('£10.99 → £12.99');
		await expect(page.getByTestId('analytics-newrecurring-item')).toContainText('iCloud');
		await expect(page.getByTestId('analytics-habit-item')).toContainText('Pret');
		await expect(page.getByTestId('analytics-habit-item')).toContainText('7 visits');
		await expect(page.getByTestId('analytics-stack-total')).toContainText('/mo');

		// Click-through coverage: stack expand shows Netflix.
		await page.getByTestId('analytics-stack-toggle').click();
		await expect(page.getByTestId('analytics-stack-list')).toBeVisible();
		await expect(page.getByTestId('analytics-stack-list')).toContainText('Netflix');

		// Click-through coverage: went-down expand shows Public Transport.
		await page.getByTestId('analytics-wentdown-toggle').click();
		await expect(page.getByTestId('analytics-wentdown-list')).toBeVisible();
		await expect(page.getByTestId('analytics-wentdown-list')).toContainText('Public Transport');

		// Trend chart present.
		await expect(page.getByTestId('analytics-monthly-trend')).toBeVisible();

		expect(consoleErrors).toEqual([]);
	});

	test('narrative strip is on-demand and surfaces the missing-key error inline', async ({
		page
	}) => {
		await page.goto('/analytics');

		const strip = page.getByTestId('analytics-narrative');
		await expect(strip).toBeVisible();
		// Nothing generated yet — button text is exactly "Generate" (not "Regenerate").
		await expect(page.getByTestId('analytics-narrative-generate')).toHaveText(/^Generate$/);

		// The e2e API has no OpenRouter key: clicking surfaces the API error inline.
		await page.getByTestId('analytics-narrative-generate').click();
		await expect(page.getByTestId('analytics-narrative-error')).toContainText(
			'QUID_OPENROUTER_API_KEY'
		);
	});

	test('period selector toggles without errors and persists', async ({ page }) => {
		const consoleErrors: string[] = [];
		page.on('console', (msg) => {
			if (msg.type() === 'error') consoleErrors.push(msg.text());
		});

		await page.goto('/analytics');
		await expect(page.getByTestId('analytics-monthly-trend')).toBeVisible();

		await page.getByTestId('analytics-period-3m').click();
		await expect(page.getByTestId('analytics-period-3m')).toHaveAttribute('aria-pressed', 'true');
		await expect(page.getByTestId('analytics-monthly-trend')).toBeVisible();

		await page.getByTestId('analytics-period-all').click();
		await expect(page.getByTestId('analytics-period-all')).toHaveAttribute('aria-pressed', 'true');
		await expect(page.getByTestId('analytics-monthly-trend')).toBeVisible();

		// Persist: reload should restore the last-selected period from localStorage.
		await page.reload();
		await expect(page.getByTestId('analytics-period-all')).toHaveAttribute('aria-pressed', 'true');

		expect(consoleErrors).toEqual([]);
	});

	test('empty state shows import CTA', async ({ page }) => {
		await seedApiState(page, { categories: analyticsSeed.categories, expenses: [] });
		await page.goto('/analytics');
		await expect(page.getByTestId('analytics-empty')).toBeVisible();
		await expect(page.getByRole('link', { name: 'Import transactions' })).toBeVisible();
		await expect(page.getByRole('link', { name: 'Import transactions' })).toHaveAttribute(
			'href',
			'/import'
		);
	});
});

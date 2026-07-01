import { expect, test } from '@playwright/test';
import { buildSeed, isoMonthOffset, monthLabelOffset, seedApiState } from './helpers.js';

test.describe('dashboard', () => {
	test.beforeEach(async ({ page }) => {
		await seedApiState(page, buildSeed());
	});

	test('renders the trend chart and category breakdown', async ({ page }) => {
		await page.goto('/');

		await expect(page.getByTestId('cumulative-chart')).toBeVisible();
		await expect(page.getByTestId('selected-month-heading')).toHaveText(monthLabelOffset(0));
		await expect(page.getByTestId('selected-month-total')).toHaveText('£54.50');
		await expect(page.getByTestId('top-category-name')).toHaveText('Groceries');
		await expect(page.getByText('Track spending by month.')).toHaveCount(0);
		await expect(page.getByText('Cumulative monthly expenses')).toHaveCount(0);

		// Category breakdown is always visible, ranked by spend (no toggle).
		const breakdownRows = page.getByTestId('category-breakdown-row');
		await expect(breakdownRows).toHaveCount(2);
		await expect(breakdownRows.first()).toContainText('Groceries');
		await expect(breakdownRows.first()).toContainText('£42.50');
		await expect(breakdownRows.last()).toContainText('Public Transport');

		// No previous-month data seeded → the delta chip must not render.
		await expect(page.getByTestId('month-delta')).toHaveCount(0);

		const rows = page.getByTestId('expense-row');
		await expect(rows).toHaveCount(2);
		await expect(rows.filter({ hasText: 'Whole Foods' })).toHaveCount(1);
		await expect(rows.filter({ hasText: 'Uber' })).toHaveCount(1);
		await expect(rows.filter({ hasText: '£42.50' })).toHaveCount(1);

		// Flat view is bucketed by day with a subtotal per day header.
		const dayHeaders = page.getByTestId('expense-day-header');
		await expect(dayHeaders).toHaveCount(2);
		await expect(dayHeaders.first()).toContainText('£42.50');
		await expect(dayHeaders.last()).toContainText('£12.00');
	});

	test('grouped view shows share bars and expandable child rows', async ({ page }) => {
		await page.goto('/');

		await page.locator('select').selectOption('category');

		// Groups sorted by amount desc: Groceries (£42.50) before Public Transport.
		const groups = page.getByTestId('expense-group-toggle');
		await expect(groups).toHaveCount(2);
		await expect(groups.first()).toContainText('Groceries');
		await expect(page.getByTestId('expense-group-amount').first()).toHaveText('£42.50');

		await groups.first().click();
		const nested = page.getByTestId('expense-nested-row');
		await expect(nested).toHaveCount(1);
		await expect(nested).toContainText('Whole Foods');
		await expect(nested.getByTestId('expense-note')).toHaveText('Weekly groceries');
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

	test('shows the spend delta against the previous month', async ({ page }) => {
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

		// £10 this month vs £20 last month → 50% down.
		const delta = page.getByTestId('month-delta');
		await expect(delta).toContainText('50%');
		await expect(delta).toContainText(`vs ${monthLabelOffset(-1)}`);
	});

	test('Today button jumps back to the current month', async ({ page }) => {
		await page.goto('/');

		// Not shown while already on the current month.
		await expect(page.getByTestId('month-label')).toHaveText(monthLabelOffset(0));
		await expect(page.getByTestId('month-current')).toHaveCount(0);

		await page.getByTestId('month-prev').click();
		await page.getByTestId('month-prev').click();
		await expect(page.getByTestId('month-label')).toHaveText(monthLabelOffset(-2));

		await page.getByTestId('month-current').click();
		await expect(page.getByTestId('month-label')).toHaveText(monthLabelOffset(0));
		await expect(page.getByTestId('month-current')).toHaveCount(0);
	});

	test('search filters the transaction list', async ({ page }) => {
		await page.goto('/');

		await expect(page.getByTestId('expense-row')).toHaveCount(2);

		await page.getByTestId('expense-search').fill('uber');
		await expect(page.getByTestId('expense-row')).toHaveCount(1);
		await expect(page.getByTestId('expense-row')).toContainText('Uber');
		await expect(page.getByTestId('search-summary')).toHaveText('1 transaction matching · £12.00');

		// Notes are searchable too.
		await page.getByTestId('expense-search').fill('weekly groceries');
		await expect(page.getByTestId('expense-row')).toHaveCount(1);
		await expect(page.getByTestId('expense-row')).toContainText('Whole Foods');

		// No matches → search-specific empty state (not the month empty state).
		await page.getByTestId('expense-search').fill('zzz-no-match');
		await expect(page.getByTestId('expense-row')).toHaveCount(0);
		await expect(page.getByTestId('empty-state')).toContainText('No transactions match');

		await page.getByTestId('expense-search').fill('');
		await expect(page.getByTestId('expense-row')).toHaveCount(2);
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

	test('delete expense flow: undo restores the row, commit removes it', async ({ page }) => {
		await page.goto('/');

		const targetRow = page.locator('[data-testid="expense-row"][data-expense-id="exp-seed-2"]');

		// Delete hides the row immediately and shows an undo toast.
		await targetRow.getByTestId('expense-delete-btn').click();
		const toast = page.getByTestId('app-toast').filter({ has: page.getByTestId('toast-undo') });
		await expect(toast).toBeVisible();
		await expect(targetRow).toHaveCount(0);

		// Undo brings it back; nothing was deleted.
		await toast.getByTestId('toast-undo').click();
		await expect(targetRow).toBeVisible();
		await expect(page.getByTestId('expense-row')).toHaveCount(2);

		// Delete again and commit now (dismiss the undo toast) — gone for good.
		await targetRow.getByTestId('expense-delete-btn').click();
		const toast2 = page.getByTestId('app-toast').filter({ has: page.getByTestId('toast-undo') });
		await expect(toast2).toBeVisible();
		// Wait for the actual DELETE to land before reloading, so the persistence
		// check can't race the deferred commit.
		const deleted = page.waitForResponse(
			(r) => r.request().method() === 'DELETE' && /\/expenses\//.test(r.url())
		);
		await toast2.getByLabel('Dismiss').click();
		await deleted;

		await expect(
			page.locator('[data-testid="expense-row"][data-expense-id="exp-seed-2"]')
		).toHaveCount(0);
		await expect(page.getByTestId('expense-row')).toHaveCount(1);

		// Persisted across a reload.
		await page.reload();
		await expect(page.getByTestId('expense-row')).toHaveCount(1);
	});

	test('hovering the undo toast pauses the countdown; leaving resumes it', async ({ page }) => {
		await page.goto('/');

		const targetRow = page.locator('[data-testid="expense-row"][data-expense-id="exp-seed-2"]');
		await targetRow.getByTestId('expense-delete-btn').click();

		const toast = page.getByTestId('app-toast').filter({ has: page.getByTestId('toast-undo') });
		await expect(toast).toBeVisible();

		// The progress bar's animation runs by default. Park the mouse away first:
		// the delete button can land exactly where the toast pops up, which would
		// count as an (unintended) hover and pause it immediately.
		await page.mouse.move(0, 0);
		const progress = toast.locator('.toast-progress');
		await expect(progress).toHaveCSS('animation-play-state', 'running');

		// Hover pauses both the visual progress bar and the underlying commit timer.
		await toast.hover();
		await expect(progress).toHaveCSS('animation-play-state', 'paused');

		// Wait well past the 6s undo window: while paused, the DELETE must NOT fire
		// and the toast must remain.
		let deleteFired = false;
		page.on('request', (req) => {
			if (req.method() === 'DELETE' && /\/expenses\//.test(req.url())) deleteFired = true;
		});
		await page.waitForTimeout(7000);
		expect(deleteFired).toBe(false);
		await expect(toast).toBeVisible();
		await expect(progress).toHaveCSS('animation-play-state', 'paused');

		// Leaving resumes the countdown; the commit then lands and the toast clears.
		const deleted = page.waitForResponse(
			(r) => r.request().method() === 'DELETE' && /\/expenses\//.test(r.url())
		);
		await page.mouse.move(0, 0);
		await expect(progress).toHaveCSS('animation-play-state', 'running');
		await deleted;
		await expect(toast).toHaveCount(0);
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
		await expect(page.getByTestId('category-breakdown')).toContainText(
			'No expenses for this month'
		);
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
		// The category breakdown is desktop-only (xl+): stacked on mobile it eats
		// vertical space, and Group by → Category covers the same need.
		await expect(page.getByTestId('category-breakdown')).toBeHidden();
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

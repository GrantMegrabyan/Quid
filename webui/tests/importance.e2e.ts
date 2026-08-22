import { expect, test } from '@playwright/test';
import { buildSeed, seedApiState } from './helpers.js';

const CATEGORIES = [
	{ id: 'uncategorized', name: 'Uncategorized', color: '#9ca3af', icon: 'circle-help' },
	{ id: 'cat-groceries', name: 'Groceries', color: '#22c55e', icon: 'shopping-cart' }
];

test.describe('importance triage', () => {
	test.beforeEach(async ({ page }) => {
		await seedApiState(
			page,
			buildSeed({
				categories: CATEGORIES,
				expenses: [
					{
						id: 'exp-tesco-1',
						name: 'Tesco',
						amount: '40.00',
						date: '2026-04-01',
						categoryId: 'cat-groceries',
						note: ''
					},
					{
						id: 'exp-tesco-2',
						name: 'TESCO',
						amount: '60.00',
						date: '2026-04-02',
						categoryId: 'cat-groceries',
						note: ''
					},
					{
						id: 'exp-netflix',
						name: 'Netflix',
						amount: '15.00',
						date: '2026-04-03',
						categoryId: 'uncategorized',
						note: ''
					},
					{
						id: 'exp-pret',
						name: 'Pret',
						amount: '5.00',
						date: '2026-04-04',
						categoryId: 'uncategorized',
						note: ''
					}
				]
			})
		);
	});

	test('ranks unlabelled merchants by spend and groups name variants', async ({ page }) => {
		await page.goto('/importance');

		const rows = page.getByTestId('triage-row');
		await expect(rows).toHaveCount(3);
		await expect(page.getByTestId('triage-merchant')).toHaveText(['Tesco', 'Netflix', 'Pret']);
		// "Tesco" and "TESCO" are one merchant, £100 between them.
		await expect(rows.first()).toContainText('£100.00');
		await expect(rows.first()).toContainText('2 transactions');
	});

	test('labelling a merchant clears it from the queue and grows coverage', async ({ page }) => {
		await page.goto('/importance');
		await expect(page.getByTestId('triage-row')).toHaveCount(3);
		await expect(page.getByTestId('coverage-labelled-amount')).toHaveText('£0.00');

		await page
			.getByTestId('triage-row')
			.first()
			.getByTestId('triage-set-essential')
			.click();

		await expect(page.getByTestId('app-toast')).toHaveAttribute('data-kind', 'success');
		await expect(page.getByTestId('triage-merchant')).toHaveText(['Netflix', 'Pret']);
		await expect(page.getByTestId('coverage-labelled-amount')).toHaveText('£100.00');
		await expect(page.getByTestId('coverage-merchants')).toHaveText('1');

		// The decision survives a reload — it is stored, not just local state.
		await page.reload();
		await expect(page.getByTestId('triage-merchant')).toHaveText(['Netflix', 'Pret']);
	});

	test('a fully labelled history shows the empty state', async ({ page }) => {
		await page.goto('/importance');
		for (const remaining of [2, 1, 0]) {
			await page.getByTestId('triage-row').first().getByTestId('triage-set-important').click();
			// Wait on the queue shrinking, not on the toast: the previous toast is
			// still on screen, so it would satisfy the assertion instantly and the
			// next click would land on a locked row.
			await expect(page.getByTestId('triage-row')).toHaveCount(remaining);
		}
		await expect(page.getByTestId('triage-empty')).toBeVisible();
		await expect(page.getByTestId('triage-list')).toHaveCount(0);
	});

	test('a triaged importance shows on the transactions it labelled', async ({ page }) => {
		await page.goto('/importance');
		await page
			.getByTestId('triage-row')
			.first()
			.getByTestId('triage-set-discretionary')
			.click();
		await expect(page.getByTestId('app-toast')).toBeVisible();

		await page.goto('/?month=2026-04');
		const transactions = page.getByTestId('transactions-section');
		await expect(transactions.getByText('Tesco').first()).toBeVisible();
		// Each row renders two badges — a mobile one and a desktop one; the
		// desktop copy is last in the DOM and is the visible one at this width.
		await expect(
			transactions.getByTestId('importance-badge').filter({ hasText: 'Discretionary' }).last()
		).toBeVisible();
	});
});

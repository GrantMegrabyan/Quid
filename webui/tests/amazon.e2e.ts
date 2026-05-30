import { expect, test } from '@playwright/test';
import { buildSeed, isoMonthOffset, seedApiState } from './helpers.js';

test('transaction subheading shows date and note on one line', async ({ page }) => {
	await seedApiState(page, buildSeed());
	await page.goto('/');

	const wholeFoodsRow = page.getByTestId('expense-row').filter({ hasText: 'Whole Foods' });
	await expect(wholeFoodsRow.getByTestId('expense-subheading')).toContainText('Weekly groceries');
	await expect(wholeFoodsRow.getByTestId('expense-subheading')).toContainText(' · ');

	const uberRow = page.getByTestId('expense-row').filter({ hasText: 'Uber' });
	await expect(uberRow.getByTestId('expense-subheading')).not.toContainText(' · ');
	await expect(page.getByTestId('amazon-linked-badge')).toHaveCount(0);
});

test('imports Amazon order, shows fallback short name, edits it, and reflects on dashboard', async ({ page }) => {
	const orderDate = isoMonthOffset(0, 10);
	await seedApiState(
		page,
		buildSeed({
			expenses: [
				{
					id: 'exp-amz',
					name: 'AMZN Mktp',
					amount: '19.99',
					date: orderDate,
					categoryId: 'cat-groceries',
					note: ''
				}
			]
		})
	);

	const csv =
		`Order ID,Order Date,Total Owed,Currency,Product Name,Quantity,Item Subtotal,Order Status,Last 4 Digits\n` +
		`123-4567890-1234567,${orderDate},19.99,GBP,Wireless Mouse,1,19.99,Delivered,4242\n`;

	await page.goto('/amazon');
	await page.getByTestId('amazon-csv-input').setInputFiles({
		name: 'orders.csv',
		mimeType: 'text/csv',
		buffer: Buffer.from(csv)
	});

	// The e2e DB is shared across tests and Amazon orders are not wiped by the
	// seed-state reset, so scope to this order's row by its id.
	const row = page
		.getByTestId('amazon-order-row')
		.filter({ hasText: '123-4567890-1234567' });
	await expect(row).toHaveCount(1);
	await expect(row.getByTestId('amazon-link-status')).toHaveAttribute('data-link-status', 'linked');
	await expect(row).toContainText('Wireless mouse');

	await row.getByTestId('amazon-short-name-edit').click();
	await row.getByTestId('amazon-short-name-input').fill('Gaming mouse');
	await row.getByRole('button', { name: /save/i }).click();
	await expect(row).toContainText('Gaming mouse');

	await page.reload();
	await expect(
		page.getByTestId('amazon-order-row').filter({ hasText: '123-4567890-1234567' })
	).toContainText('Gaming mouse');

	await page.goto('/');
	const expenseRow = page.getByTestId('expense-row').filter({ hasText: 'AMZN Mktp' });
	await expect(expenseRow.getByTestId('expense-subheading')).toContainText('Gaming mouse');
	await expect(expenseRow.getByTestId('expense-subheading')).toContainText(' · ');
});

test('shows and edits an Amazon order category', async ({ page }) => {
	const orderDate = isoMonthOffset(0, 12);
	await seedApiState(page, buildSeed());

	// Disable AI categorisation so the imported order deterministically starts
	// with no category (the e2e API may have a live OpenRouter key configured).
	await page.goto('/settings');
	const aiToggle = page.getByTestId('settings-ai-categorize-toggle');
	if (await aiToggle.isChecked()) {
		await aiToggle.uncheck();
		await page.getByTestId('settings-save-button').click();
		await expect(page.getByTestId('settings-message')).toBeVisible();
	}

	const csv =
		`Order ID,Order Date,Total Owed,Currency,Product Name,Quantity,Item Subtotal,Order Status,Last 4 Digits\n` +
		`555-1112223-3334445,${orderDate},31.50,GBP,Travel Adapter,1,31.50,Delivered,4242\n`;

	await page.goto('/amazon');
	await page.getByTestId('amazon-csv-input').setInputFiles({
		name: 'orders.csv',
		mimeType: 'text/csv',
		buffer: Buffer.from(csv)
	});

	// The e2e DB is shared across tests; scope to this order's row by its id.
	const row = page
		.getByTestId('amazon-order-row')
		.filter({ hasText: '555-1112223-3334445' });
	await expect(row).toHaveCount(1);

	// Starts uncategorised (AI off).
	const categoryBadge = row.getByTestId('amazon-order-category');
	await expect(categoryBadge).toHaveAttribute('data-category-id', '');

	// Open the editor and pick a category.
	await categoryBadge.click();
	await row.getByTestId('amazon-category-select').selectOption('cat-groceries');

	await expect(row.getByTestId('amazon-order-category')).toHaveAttribute(
		'data-category-id',
		'cat-groceries'
	);
	await expect(row.getByTestId('amazon-order-category')).toContainText('Groceries');

	// Persists across reload.
	await page.reload();
	const reloadedRow = page
		.getByTestId('amazon-order-row')
		.filter({ hasText: '555-1112223-3334445' });
	await expect(reloadedRow.getByTestId('amazon-order-category')).toHaveAttribute(
		'data-category-id',
		'cat-groceries'
	);

	// Restore the AI toggle so we don't leak state into other tests sharing
	// the e2e DB (e.g. settings.e2e.ts asserts it defaults on).
	await page.goto('/settings');
	const restoreToggle = page.getByTestId('settings-ai-categorize-toggle');
	if (!(await restoreToggle.isChecked())) {
		await restoreToggle.check();
		await page.getByTestId('settings-save-button').click();
		await expect(page.getByTestId('settings-message')).toBeVisible();
	}
});

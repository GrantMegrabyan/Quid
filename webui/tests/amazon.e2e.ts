import { expect, test } from '@playwright/test';
import { buildSeed, isoMonthOffset, seedApiState } from './helpers.js';

test('transaction subheading shows date and note on one line', async ({ page }) => {
	await seedApiState(page, buildSeed());
	await page.goto('/');

	const wholeFoodsRow = page.getByTestId('expense-row').filter({ hasText: 'Whole Foods' });
	await expect(wholeFoodsRow.getByTestId('expense-subheading')).toContainText('Weekly groceries');
	await expect(wholeFoodsRow.getByTestId('expense-subheading')).toContainText('●');

	const uberRow = page.getByTestId('expense-row').filter({ hasText: 'Uber' });
	await expect(uberRow.getByTestId('expense-subheading')).not.toContainText('●');
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
					amount: 19.99,
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

	const row = page.getByTestId('amazon-order-row');
	await expect(row).toHaveCount(1);
	await expect(row.getByTestId('amazon-link-status')).toHaveAttribute('data-link-status', 'linked');
	await expect(row).toContainText('Wireless mouse');

	await row.getByTestId('amazon-short-name-edit').click();
	await row.getByTestId('amazon-short-name-input').fill('Gaming mouse');
	await page.getByRole('button', { name: /save/i }).click();
	await expect(row).toContainText('Gaming mouse');

	await page.reload();
	await expect(page.getByTestId('amazon-order-row')).toContainText('Gaming mouse');

	await page.goto('/');
	const expenseRow = page.getByTestId('expense-row').filter({ hasText: 'AMZN Mktp' });
	await expect(expenseRow.getByTestId('expense-subheading')).toContainText('Gaming mouse');
	await expect(expenseRow.getByTestId('expense-subheading')).toContainText('●');
});

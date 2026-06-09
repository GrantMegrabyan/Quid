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

	// Disable AI short names so the imported order deterministically shows the
	// product-title fallback ("Wireless Mouse") rather than a non-deterministic
	// AI-generated description (the e2e API may have a live OpenRouter key).
	await page.goto('/settings');
	const aiShortNames = page.getByTestId('settings-ai-short-names-toggle');
	if (await aiShortNames.isChecked()) {
		await aiShortNames.uncheck();
		await page.getByTestId('settings-save-button').click();
		await expect(page.getByTestId('settings-message')).toBeVisible();
	}

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
	// The "Linked to ..." label is rendered from the linked-expense label data
	// embedded in the orders response (the page no longer fetches every expense
	// just to resolve these labels). Confirm it resolves the id to name+amount.
	await expect(row).toContainText('Linked to AMZN Mktp');
	await expect(row).toContainText('19.99');
	// AI short names are disabled above, so the row shows the product-title fallback.
	await expect(row).toContainText('Wireless Mouse');

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

test('unlinks an order, then finds and re-links a match in the compact row', async ({ page }) => {
	const orderDate = isoMonthOffset(0, 16);
	await seedApiState(
		page,
		buildSeed({
			expenses: [
				{
					id: 'exp-amz-relink',
					name: 'AMZN Mktp',
					amount: '27.30',
					date: orderDate,
					categoryId: 'cat-groceries',
					note: ''
				}
			]
		})
	);

	const csv =
		`Order ID,Order Date,Total Owed,Currency,Product Name,Quantity,Item Subtotal,Order Status,Last 4 Digits\n` +
		`888-2223334-4445556,${orderDate},27.30,GBP,USB Cable,1,27.30,Delivered,4242\n`;

	await page.goto('/amazon');
	await page.getByTestId('amazon-csv-input').setInputFiles({
		name: 'orders.csv',
		mimeType: 'text/csv',
		buffer: Buffer.from(csv)
	});

	// The e2e DB is shared across tests; scope to this order's row by its id.
	const row = page.getByTestId('amazon-order-row').filter({ hasText: '888-2223334-4445556' });
	await expect(row).toHaveCount(1);

	// Auto-matched on import: linked status + compact "Linked to ..." secondary line.
	await expect(row.getByTestId('amazon-link-status')).toHaveAttribute(
		'data-link-status',
		'linked'
	);
	await expect(row).toContainText('Linked to AMZN Mktp');

	// Unlink from the compact secondary line.
	await row.getByRole('button', { name: 'Unlink transaction' }).click();
	await expect(row.getByTestId('amazon-link-status')).toHaveAttribute(
		'data-link-status',
		'unlinked'
	);
	await expect(row).not.toContainText('Linked to AMZN Mktp');

	// Find matches surfaces the suggestion sub-panel below the row.
	await row.getByRole('button', { name: 'Find matches' }).click();
	const suggestion = row.getByRole('button', { name: 'Link to this transaction' });
	await expect(suggestion).toBeVisible();

	// Re-link from the suggestion panel.
	await suggestion.click();
	await expect(row.getByTestId('amazon-link-status')).toHaveAttribute(
		'data-link-status',
		'linked'
	);
	await expect(row).toContainText('Linked to AMZN Mktp');
});

test('AI re-categorise button previews suggestions or fails gracefully', async ({ page }) => {
	// The preview endpoint calls OpenRouter, whose key + output are not
	// deterministic in CI. This test verifies the UI wiring end-to-end: the
	// button triggers a request and the page resolves into a valid state —
	// either the preview panel (key present) or a banner (no key / no eligible
	// orders) — without an unhandled error breaking the page.
	const orderDate = isoMonthOffset(0, 14);
	await seedApiState(page, buildSeed());

	const csv =
		`Order ID,Order Date,Total Owed,Currency,Product Name,Quantity,Item Subtotal,Order Status,Last 4 Digits\n` +
		`777-8889990-0001112,${orderDate},44.00,GBP,Desk Lamp,1,44.00,Delivered,4242\n`;

	await page.goto('/amazon');
	await page.getByTestId('amazon-csv-input').setInputFiles({
		name: 'orders.csv',
		mimeType: 'text/csv',
		buffer: Buffer.from(csv)
	});
	await expect(
		page.getByTestId('amazon-order-row').filter({ hasText: '777-8889990-0001112' })
	).toHaveCount(1);

	await page.getByTestId('amazon-recategorize-button').click();

	// Either the preview panel renders, or a banner explains why not. Both are
	// valid terminal states; the page must not be left in the "Thinking…" spinner
	// nor throw.
	const panel = page.getByTestId('amazon-recategorize-panel');
	const banner = page.getByTestId('amazon-banner');
	await expect(panel.or(banner).first()).toBeVisible({ timeout: 30_000 });

	// If the panel rendered, its core controls must be present and the toggle
	// must reveal/hide rows without error.
	if (await panel.isVisible()) {
		await expect(page.getByTestId('amazon-recategorize-confirm')).toBeVisible();
		await page.getByTestId('amazon-recategorize-show-unchanged').check();
		await page.getByTestId('amazon-recategorize-cancel').click();
		await expect(panel).toHaveCount(0);
	}
});

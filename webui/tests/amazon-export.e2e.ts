import { expect, test } from '@playwright/test';
import { buildSeed, isoMonthOffset, seedApiState } from './helpers.js';

/**
 * Drives the "Import from browser" panel end-to-end: uploads a `.json` export
 * payload (the same shape the bookmarklet/scraper emits and the backend's
 * `api/tests/fixtures/amazon_export_sample.json` documents), and asserts the
 * order row appears + auto-links to a seeded expense, with no 4xx/5xx and no
 * console errors. Also covers the skipped-order path (missing total).
 */

test('imports orders from a browser-export .json upload and auto-links a seeded expense', async ({
	page
}) => {
	const consoleErrors: string[] = [];
	page.on('console', (msg) => {
		if (msg.type() === 'error') consoleErrors.push(msg.text());
	});
	const badResponses: string[] = [];
	page.on('response', (res) => {
		if (res.status() >= 400) badResponses.push(`${res.status()} ${res.url()}`);
	});

	const orderDate = isoMonthOffset(0, 9);
	await seedApiState(
		page,
		buildSeed({
			expenses: [
				{
					id: 'exp-export',
					name: 'AMZN Mktp',
					amount: '27.45',
					date: orderDate,
					categoryId: 'cat-groceries',
					note: ''
				}
			]
		})
	);

	const payload = {
		scraperVersion: '1.0.0',
		domain: 'amazon.co.uk',
		orders: [
			{
				orderId: '901-1112223-3334445',
				orderDate,
				total: '27.45',
				currency: 'GBP',
				status: 'Delivered',
				items: [{ title: 'Noise-cancelling Earbuds', quantity: 1, price: '27.45' }],
				shipments: [],
				paymentLast4: '4242',
				orderUrl: 'https://www.amazon.co.uk/gp/css/order-details?orderID=901-1112223-3334445'
			}
		]
	};

	await page.goto('/amazon');
	await page.getByTestId('amazon-export-import-button').click();
	await expect(page.getByTestId('amazon-export-panel')).toBeVisible();

	await page.getByTestId('amazon-export-file-input').setInputFiles({
		name: 'amazon-orders.json',
		mimeType: 'application/json',
		buffer: Buffer.from(JSON.stringify(payload))
	});

	const row = page
		.getByTestId('amazon-order-row')
		.filter({ hasText: '901-1112223-3334445' });
	await expect(row).toHaveCount(1);
	await expect(row.getByTestId('amazon-link-status')).toHaveAttribute(
		'data-link-status',
		'linked'
	);
	await expect(row).toContainText('AMZN Mktp');

	await expect(page.getByTestId('amazon-banner')).toHaveAttribute('data-kind', 'success');

	expect(badResponses, `unexpected 4xx/5xx: ${badResponses.join(', ')}`).toEqual([]);
	expect(consoleErrors, `console errors: ${consoleErrors.join(' | ')}`).toEqual([]);
});

test('reports skipped orders (missing total) while importing the good ones', async ({
	page
}) => {
	const orderDate = isoMonthOffset(0, 14);
	await seedApiState(page, buildSeed());

	const payload = {
		scraperVersion: '1.0.0',
		domain: 'amazon.co.uk',
		orders: [
			{
				orderId: '902-2223334-4445556',
				orderDate,
				total: '15.00',
				currency: 'GBP',
				status: 'Delivered',
				items: [{ title: 'Desk Lamp', quantity: 1, price: '15.00' }],
				shipments: []
			},
			{
				// No total -> the server skips this order and reports a reason.
				orderId: '903-3334445-5556667',
				orderDate,
				total: null,
				currency: 'GBP',
				status: 'Delivered',
				items: [{ title: 'Mystery Box', quantity: 1, price: null }],
				shipments: []
			}
		]
	};

	await page.goto('/amazon');
	await page.getByTestId('amazon-export-import-button').click();
	await page.getByTestId('amazon-export-textarea').fill(JSON.stringify(payload));
	await page.getByTestId('amazon-export-submit').click();

	// Good order imported.
	const goodRow = page
		.getByTestId('amazon-order-row')
		.filter({ hasText: '902-2223334-4445556' });
	await expect(goodRow).toHaveCount(1);

	// Skipped list renders the bad order with its reason.
	const skipped = page.getByTestId('amazon-export-skipped');
	await expect(skipped).toBeVisible();
	await expect(skipped).toContainText('903-3334445-5556667');
	await expect(skipped.getByTestId('amazon-export-skipped-row')).toHaveCount(1);

	// Success banner mentions the skip.
	await expect(page.getByTestId('amazon-banner')).toContainText('1 skipped');
});

test('shows an error banner for invalid pasted JSON', async ({ page }) => {
	await seedApiState(page, buildSeed());
	await page.goto('/amazon');
	await page.getByTestId('amazon-export-import-button').click();
	await page.getByTestId('amazon-export-textarea').fill('{ not valid json');
	await page.getByTestId('amazon-export-submit').click();

	const banner = page.getByTestId('amazon-banner');
	await expect(banner).toHaveAttribute('data-kind', 'error');
	await expect(banner).toContainText('Invalid JSON');
});

import { expect, test } from '@playwright/test';
import { readFile } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { transformWithOxc } from 'vite';
import type { AmazonExportRequest } from '../src/lib/types/domain.js';

/**
 * Parser tests for the CANONICAL scraper (`src/lib/amazon/scraper.ts`).
 *
 * This project has no Vitest, so the pure parser is exercised in a real browser
 * DOM via Playwright: we transform the TS module to a browser IIFE that exposes
 * the parser on `window`, inject it with `addScriptTag`, load a sanitized HTML
 * fixture via `setContent`, then run `parseOrdersFromDocument(document, domain)`
 * inside the page. Asserted output aligns with the BACKEND fixture
 * `api/tests/fixtures/amazon_export_sample.json` (S5 — one JSON contract).
 */

const here = dirname(fileURLToPath(import.meta.url));
const fixturesDir = resolve(here, 'fixtures');
const scraperPath = resolve(here, '..', 'src', 'lib', 'amazon', 'scraper.ts');

/**
 * Transform the canonical TS parser into classic-script source that exposes the
 * parser on `window.__quidScraper`. The module's only imports are type-only
 * (erased), so after stripping the `import type` line and the `export`
 * keywords, the transpiled body is valid top-level script for `addScriptTag`.
 */
async function browserScraperSource(): Promise<string> {
	const ts = await readFile(scraperPath, 'utf8');
	const withoutTypeImport = ts.replace(/import type \{[\s\S]*?\} from '\$types';/, '');
	const out = await transformWithOxc(withoutTypeImport, 'scraper.ts', { lang: 'ts' });
	// Drop ESM `export` markers so this runs as a classic script, then expose
	// the parser API as a global the page can call.
	const asScript = out.code
		.replace(/^export\s+(class|function|const|let|var)\s/gm, '$1 ')
		.replace(/^export\s+\{[^}]*\};?\s*$/gm, '');
	return (
		asScript +
		`\nwindow.__quidScraper = { parseOrdersFromDocument, AmazonScrapeError, SCRAPER_VERSION, extractMoneyString, normalizeOrderDate };`
	);
}

async function loadFixture(name: string): Promise<string> {
	return readFile(resolve(fixturesDir, name), 'utf8');
}

async function runParser(
	page: import('@playwright/test').Page,
	html: string,
	domain: string
): Promise<AmazonExportRequest> {
	await page.setContent(html);
	await page.addScriptTag({ content: await browserScraperSource() });
	return page.evaluate(
		(d) => (window as unknown as { __quidScraper: { parseOrdersFromDocument: (doc: Document, domain: string) => AmazonExportRequest } }).__quidScraper.parseOrdersFromDocument(document, d),
		domain
	) as Promise<AmazonExportRequest>;
}

test('parses a .co.uk order-history page matching the backend export contract', async ({
	page
}) => {
	const html = await loadFixture('amazon-orders-couk.html');
	const result = await runParser(page, html, 'amazon.co.uk');

	expect(result.scraperVersion).toBe('1.1.0');
	expect(result.domain).toBe('amazon.co.uk');
	expect(result.orders).toHaveLength(3);

	const [first, second, third] = result.orders;

	// Order ids + normalised dates + totals as EXACT strings (never numbers).
	expect(first.orderId).toBe('111-2223334-4445556');
	expect(first.orderDate).toBe('2026-05-05');
	expect(first.total).toBe('19.99');
	expect(typeof first.total).toBe('string');
	expect(first.status).toBe('Delivered');
	expect(first.paymentLast4).toBe('1234');
	expect(first.orderUrl).toContain('111-2223334-4445556');
	expect(first.items).toHaveLength(1);
	expect(first.items[0].title).toBe('USB-C to USB-C Cable 2m');
	expect(first.items[0].price).toBe('19.99');
	expect(first.shipments).toEqual([]);

	expect(second.orderId).toBe('222-3334445-5556667');
	expect(second.orderDate).toBe('2026-05-08');
	expect(second.total).toBe('42.50');
	expect(second.items.map((i) => i.title)).toEqual(['Mechanical Keyboard', 'Keycap Puller']);
	expect(second.items.map((i) => i.price)).toEqual(['35.00', '7.50']);

	expect(third.orderId).toBe('333-4445556-6667778');
	expect(third.orderDate).toBe('2026-05-11');
	expect(third.total).toBe('8.75');
	expect(third.paymentLast4).toBe('9876');
});

test('parses a .com order-history page (legacy cards, US dates, $ + thousands)', async ({
	page
}) => {
	const html = await loadFixture('amazon-orders-com.html');
	const result = await runParser(page, html, 'amazon.com');

	expect(result.domain).toBe('amazon.com');
	expect(result.orders).toHaveLength(2);

	const [first, second] = result.orders;
	expect(first.orderId).toBe('100-1112223-3334445');
	expect(first.orderDate).toBe('2026-05-12');
	expect(first.total).toBe('24.00');
	expect(first.items[0].title).toBe('Stainless Water Bottle 1L');

	expect(second.orderId).toBe('200-2223334-4445556');
	expect(second.orderDate).toBe('2026-05-20');
	// Thousands separator stripped, decimal kept as an exact string.
	expect(second.total).toBe('1299.00');
	expect(second.status).toBe('Shipped');
});

test('bookmarklet stays in sync with the canonical parser (version + payload)', async ({
	page
}) => {
	// Guards the manual scraper.ts <-> bookmarklet.ts sync the architecture
	// leans on. (1) Version can never drift — the bookmarklet sources its
	// version from scraper.ts. (2) Run the bookmarklet's ACTUAL parse logic
	// against the same fixture and assert payload parity with the canonical
	// parser, minus the download/clipboard side effects.
	const { BOOKMARKLET_SCRAPER_VERSION, BOOKMARKLET_SOURCE } = await import(
		'../src/lib/amazon/bookmarklet.js'
	);
	const { SCRAPER_VERSION } = await import('../src/lib/amazon/scraper.js');
	expect(BOOKMARKLET_SCRAPER_VERSION).toBe(SCRAPER_VERSION);

	const html = await loadFixture('amazon-orders-couk.html');
	const canonical = await runParser(page, html, 'amazon.co.uk');

	// The bookmarklet body is `(function(){ ... try{<side effects>}catch{} })();`.
	// Replace the whole IIFE-invoking tail with one that captures the internal
	// `parse` onto window, so we exercise the real parse logic without firing
	// the download/alert side effects.
	const marker = '  try{';
	const idx = BOOKMARKLET_SOURCE.indexOf(marker);
	expect(idx).toBeGreaterThan(0);
	const capture =
		BOOKMARKLET_SOURCE.slice(0, idx) + '  window.__quidBookmarkletParse = parse;\n})();';

	await page.setContent(html);
	const fromBookmarklet = await page.evaluate((src: string) => {
		eval(src);
		const fn = (
			window as unknown as {
				__quidBookmarkletParse: (doc: Document, domain: string) => unknown;
			}
		).__quidBookmarkletParse;
		return fn(document, 'amazon.co.uk');
	}, capture);

	expect(fromBookmarklet).toEqual(canonical);
});

test('throws AmazonScrapeError on an orders shell with zero cards (layout drift)', async ({
	page
}) => {
	const html = await loadFixture('amazon-orders-empty-shell.html');
	await page.setContent(html);
	await page.addScriptTag({ content: await browserScraperSource() });

	const thrown = await page.evaluate(() => {
		const api = (window as unknown as {
			__quidScraper: {
				parseOrdersFromDocument: (doc: Document, domain: string) => unknown;
				AmazonScrapeError: new (m: string) => Error;
			};
		}).__quidScraper;
		try {
			api.parseOrdersFromDocument(document, 'amazon.co.uk');
			return { threw: false, name: '', message: '' };
		} catch (e) {
			const err = e as Error;
			return {
				threw: true,
				name: err.name,
				isScrapeError: err instanceof api.AmazonScrapeError,
				message: err.message
			};
		}
	});

	expect(thrown.threw).toBe(true);
	expect(thrown.name).toBe('AmazonScrapeError');
	expect(thrown.message).toContain('layout not recognised');
});

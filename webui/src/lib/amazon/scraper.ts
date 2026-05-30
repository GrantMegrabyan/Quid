/**
 * Canonical, pure Amazon order-history parser.
 *
 * `parseOrdersFromDocument(doc, domain)` takes a DOM `Document` for an Amazon
 * order-history page and returns the `AmazonExportRequest` JSON shape (camelCase,
 * money as STRINGS) accepted by `POST /api/v1/amazon-orders/import-export`.
 *
 * This module is the SINGLE SOURCE OF TRUTH for the scrape logic and is the
 * thing the Playwright parser tests exercise against sanitized HTML fixtures.
 * The bookmarklet (`webui/src/lib/amazon/bookmarklet.ts`) inlines a trimmed,
 * self-contained copy of this logic because a bookmarklet cannot import app
 * modules at runtime — KEEP THE TWO IN SYNC when changing selectors or money
 * handling.
 *
 * Design notes:
 * - FAIL LOUD on layout drift (`AmazonScrapeError`) rather than silently
 *   emitting a truncated/garbage history. Re-import is idempotent server-side,
 *   so failing the whole scrape and asking the user to retry is safe.
 * - Money is kept as the exact decimal STRING the page displays ("£19.99" ->
 *   "19.99"). NEVER `parseFloat` — a float round-trips faithfully through JSON
 *   and then silently fails the server's exact-`Decimal` match.
 */

import type {
	AmazonExportItem,
	AmazonExportOrder,
	AmazonExportRequest
} from '$types';

/** Bump when the emitted contract or parse logic changes materially. */
export const SCRAPER_VERSION = '1.2.0';

/**
 * Thrown when the page looks like an orders page but the layout can't be
 * parsed (Amazon changed their DOM), or an individual order card is missing a
 * required field. Fail loud — never import partial/garbage data.
 */
export class AmazonScrapeError extends Error {
	constructor(message: string) {
		super(message);
		this.name = 'AmazonScrapeError';
	}
}

function layoutError(detail: string): AmazonScrapeError {
	return new AmazonScrapeError(
		`Amazon page layout not recognised (scraper v${SCRAPER_VERSION}) — ${detail} ` +
			`The format may have changed.`
	);
}

const MONTHS: Record<string, string> = {
	january: '01',
	february: '02',
	march: '03',
	april: '04',
	may: '05',
	june: '06',
	july: '07',
	august: '08',
	september: '09',
	october: '10',
	november: '11',
	december: '12'
};

/**
 * Extract a decimal money STRING from displayed text, stripping currency
 * symbols/thousands separators/whitespace. Returns null when no amount is
 * present. NEVER returns a number — the money-as-strings contract is
 * load-bearing for exact-`Decimal` matching server-side.
 */
export function extractMoneyString(raw: string | null | undefined): string | null {
	if (!raw) return null;
	// Grab the first number-with-optional-decimal, allowing thousands commas.
	// e.g. "£1,299.00" -> "1,299.00", "EUR 19,99" stays "19,99" (handled below).
	const match = raw.replace(/\s+/g, ' ').match(/[0-9][0-9.,]*[0-9]|[0-9]/);
	if (!match) return null;
	let value = match[0];
	// Decide whether comma is a decimal separator (de/fr style "19,99") or a
	// thousands separator ("1,299.00"). If there's a dot, commas are thousands.
	if (value.includes('.')) {
		value = value.replace(/,/g, '');
	} else if (value.includes(',')) {
		// No dot: a single trailing comma group of 2 digits is a decimal comma.
		const parts = value.split(',');
		if (parts.length === 2 && parts[1].length === 2) {
			value = `${parts[0]}.${parts[1]}`;
		} else {
			value = value.replace(/,/g, '');
		}
	}
	// Reject if it didn't reduce to a plain decimal.
	if (!/^[0-9]+(\.[0-9]+)?$/.test(value)) return null;
	return value;
}

/**
 * Normalise an Amazon order date string to `YYYY-MM-DD`. Supports the common
 * "12 May 2026" / "May 12, 2026" / already-ISO forms. Returns null when it
 * can't be confidently normalised (the server also re-validates + skips).
 */
export function normalizeOrderDate(raw: string | null | undefined): string | null {
	if (!raw) return null;
	const text = raw.replace(/\s+/g, ' ').trim();

	// Already ISO.
	const iso = text.match(/\b(\d{4})-(\d{2})-(\d{2})\b/);
	if (iso) return `${iso[1]}-${iso[2]}-${iso[3]}`;

	// "12 May 2026" (.co.uk style)
	const dmy = text.match(/\b(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})\b/);
	if (dmy) {
		const month = MONTHS[dmy[2].toLowerCase()];
		if (month) return `${dmy[3]}-${month}-${dmy[1].padStart(2, '0')}`;
	}

	// "May 12, 2026" (.com style)
	const mdy = text.match(/\b([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})\b/);
	if (mdy) {
		const month = MONTHS[mdy[1].toLowerCase()];
		if (month) return `${mdy[3]}-${month}-${mdy[2].padStart(2, '0')}`;
	}

	return null;
}

function textOf(el: Element | null | undefined): string {
	return (el?.textContent ?? '').replace(/\s+/g, ' ').trim();
}

/** First element matching any of the selectors (in priority order). */
function pick(root: ParentElement, selectors: string[]): Element | null {
	for (const sel of selectors) {
		const found = root.querySelector(sel);
		if (found) return found;
	}
	return null;
}

type ParentElement = Document | Element;

/** Order-card container selectors across .com / .co.uk / legacy layouts. */
const ORDER_CARD_SELECTORS = [
	'.order-card',
	'.a-box-group.order',
	'.js-order-card',
	'.order'
];

/** Markers that mean "this really is an orders page" even with zero cards. */
const ORDERS_PAGE_MARKERS = [
	'#ordersContainer',
	'.your-orders-content-container',
	'[data-testid="orders-container"]',
	'.a-section.your-orders-content'
];

/** Empty-state markers ("you have no orders") — a legitimate zero-card page. */
const EMPTY_STATE_MARKERS = [
	'.no-orders',
	'#emptyOrdersList',
	'[data-testid="no-orders"]'
];

const ORDER_ID_SELECTORS = [
	'bdi[dir="ltr"]',
	'.yohtmlc-order-id bdi',
	'[data-testid="order-id"]'
];

const ORDER_TOTAL_SELECTORS = [
	'[data-testid="order-total"] .a-text-bold',
	'.yohtmlc-order-total .a-text-bold',
	'.order-total .value',
	'[data-testid="order-total"]'
];

const ORDER_DATE_SELECTORS = [
	'[data-testid="order-date"]',
	'.yohtmlc-order-date .a-color-secondary',
	'.order-date .value',
	'.a-color-secondary.value'
];

/**
 * Current amazon.co.uk / .com "order header" layout puts each summary field in
 * a `.a-column` whose first line is a `.a-text-caps` LABEL ("Order placed",
 * "Total", "Order #") and whose value sits in a following `.a-row`. The value
 * spans share generic classes (date and total are both
 * `a-size-base a-color-secondary aok-break-word`), so we must anchor on the
 * label text and read the value from the same column, not select by class.
 *
 * Returns the value text for the column whose label matches `labelRe`, or null.
 */
function valueByLabel(card: Element, labelRe: RegExp): string | null {
	const labels = Array.from(card.querySelectorAll('.a-text-caps'));
	for (const label of labels) {
		if (!labelRe.test(textOf(label))) continue;
		const column = label.closest('.a-column, .a-fixed-right-grid-col, li') ?? label.parentElement;
		if (!column) continue;
		const labelText = textOf(label);
		// The label itself is wrapped in a `.a-row` (e.g. "Order placed"), and
		// the VALUE is in a SEPARATE `.a-row` sibling ("24 May 2026"). Pick the
		// first `.a-row` whose text isn't just the label.
		const rows = Array.from(column.querySelectorAll('.a-row'));
		for (const row of rows) {
			const text = textOf(row);
			if (text && text !== labelText && !labelRe.test(text)) return text;
		}
		// Fallback: the column's text minus the label.
		const stripped = textOf(column).replace(labelText, '').trim();
		if (stripped) return stripped;
	}
	return null;
}

const ITEM_TITLE_SELECTORS = [
	'.yohtmlc-product-title',
	'.a-link-normal.yohtmlc-product-title',
	'[data-testid="item-title"]',
	'.a-row .a-link-normal'
];

const ORDER_ID_RE = /\d{3}-\d{7}-\d{7}/;

/** Pull the order id out of a card, trying selectors then a text fallback. */
function parseOrderId(card: Element): string | null {
	// Current layout: a `.yohtmlc-order-id` container holding an "Order #"
	// label span and the id value span (the id is a plain span[dir="ltr"],
	// NOT a <bdi>). Read the container text and pull the id pattern out.
	const idContainer = card.querySelector('.yohtmlc-order-id');
	if (idContainer) {
		const fromContainer = textOf(idContainer).match(ORDER_ID_RE);
		if (fromContainer) return fromContainer[0];
	}

	// Label-anchored fallback (handles layouts where the label/value sit in a
	// shared column rather than a `.yohtmlc-order-id` wrapper).
	const byLabel = valueByLabel(card, /order\s*#/i);
	const fromLabel = byLabel?.match(ORDER_ID_RE);
	if (fromLabel) return fromLabel[0];

	for (const sel of ORDER_ID_SELECTORS) {
		const value = textOf(card.querySelector(sel));
		if (ORDER_ID_RE.test(value)) {
			return value.match(ORDER_ID_RE)![0];
		}
	}
	// Fallback: scan the card text for an Amazon order id pattern.
	const fromText = textOf(card).match(ORDER_ID_RE);
	return fromText ? fromText[0] : null;
}

function parseItems(card: Element): AmazonExportItem[] {
	const items: AmazonExportItem[] = [];
	const seen = new Set<string>();
	for (const sel of ITEM_TITLE_SELECTORS) {
		for (const node of Array.from(card.querySelectorAll(sel))) {
			const title = textOf(node);
			if (!title || seen.has(title)) continue;
			seen.add(title);
			// Item price is best-effort; the order total is what matters for
			// matching, so a missing item price is fine.
			const priceEl = node
				.closest('.a-fixed-left-grid, .item-box, [data-testid="item-row"]')
				?.querySelector(
					'.a-price .a-offscreen, .item-price, [data-testid="item-price"]'
				);
			const price = extractMoneyString(textOf(priceEl));
			items.push({ title, quantity: 1, price });
		}
		if (items.length > 0) break;
	}
	return items;
}

function parseOrderUrl(card: Element, domain: string): string | null {
	const link = card.querySelector<HTMLAnchorElement>(
		'a[href*="order-details"], a[href*="orderID"], a[href*="css/order-details"]'
	);
	if (!link) return null;
	const href = link.getAttribute('href') ?? '';
	if (!href) return null;
	if (/^https?:\/\//.test(href)) return href;
	return `https://www.${domain}${href.startsWith('/') ? '' : '/'}${href}`;
}

// Statuses the server's `_ACCEPTED_STATUSES` imports (lower-cased). The .co.uk
// delivery box reads e.g. "Delivered 7 May", so we extract the leading keyword.
const ACCEPTED_STATUS = /\b(delivered|shipped|closed|complete|completed)\b/i;
// Explicit not-importable states (cancelled/returned/refunded) — emit these so
// the server SKIPS them with a reason.
const REJECTED_STATUS = /\b(cancelled|canceled|returned|refunded)\b/i;

/**
 * Extract a status the server will act on. The order TOTAL is what gates
 * import; status only matters for excluding cancelled/returned orders. So:
 * emit an accepted keyword ("Delivered") or an explicit rejected one
 * ("Cancelled"); for in-flight states the server doesn't list (e.g.
 * "Dispatched", "Preparing"), emit null so a still-valid order isn't wrongly
 * skipped by the status filter.
 */
function parseStatus(card: Element): string | null {
	const el = pick(card, [
		'[data-testid="order-status"]',
		'.delivery-box__primary-text',
		'.delivery-box .a-text-bold',
		'.shipment-top-row .a-text-bold'
	]);
	const value = textOf(el);
	if (!value) return null;
	const rejected = value.match(REJECTED_STATUS);
	if (rejected) return rejected[1];
	const accepted = value.match(ACCEPTED_STATUS);
	if (accepted) return accepted[1];
	return null;
}

function parseLast4(card: Element): string | null {
	const text = textOf(card);
	const match = text.match(/(?:ending in|ending|••••|\*{4})\s*(\d{4})/i);
	return match ? match[1] : null;
}

/**
 * Parse one order card into the export shape. Throws `AmazonScrapeError` when a
 * required field (order id or total) can't be parsed — a strong signal the
 * layout changed.
 */
function parseOrderCard(card: Element, domain: string, index: number): AmazonExportOrder {
	const orderId = parseOrderId(card);
	if (!orderId) {
		throw layoutError(`order card #${index + 1} has no recognisable order id.`);
	}

	// Total: anchor on the "Total" label's column (current layout), then fall
	// back to the legacy selectors.
	const total =
		extractMoneyString(valueByLabel(card, /^\s*total\s*$/i)) ??
		extractMoneyString(textOf(pick(card, ORDER_TOTAL_SELECTORS)));
	if (!total) {
		throw layoutError(`order ${orderId} has no parseable total.`);
	}

	// Date: anchor on the "Order placed" label's column, then legacy selectors.
	// Normalised here but the server also re-validates + skips, so a null here
	// is non-fatal: emit it raw-empty and let the server skip it.
	const orderDate =
		normalizeOrderDate(valueByLabel(card, /order\s*placed/i)) ??
		normalizeOrderDate(textOf(pick(card, ORDER_DATE_SELECTORS))) ??
		'';

	return {
		orderId,
		orderDate,
		total,
		currency: null,
		status: parseStatus(card),
		items: parseItems(card),
		shipments: [],
		paymentLast4: parseLast4(card),
		orderUrl: parseOrderUrl(card, domain)
	};
}

/**
 * Parse all order cards on an Amazon order-history `Document`.
 *
 * Fail-loud invariants (concrete, testable):
 * - Page looks like an orders page (has an orders-container marker) but yields
 *   0 cards AND has no empty-state marker -> throw (layout changed).
 * - Any card missing a parseable order id OR total -> throw, failing the WHOLE
 *   scrape (re-import is idempotent), reporting how many parsed first.
 */
export function parseOrdersFromDocument(
	doc: Document,
	domain: string
): AmazonExportRequest {
	let cards: Element[] = [];
	for (const sel of ORDER_CARD_SELECTORS) {
		const found = Array.from(doc.querySelectorAll(sel));
		if (found.length > 0) {
			cards = found;
			break;
		}
	}

	if (cards.length === 0) {
		const isOrdersPage = ORDERS_PAGE_MARKERS.some((m) => doc.querySelector(m));
		const isEmptyState = EMPTY_STATE_MARKERS.some((m) => doc.querySelector(m));
		if (isOrdersPage && !isEmptyState) {
			throw layoutError('no order cards were found on the orders page.');
		}
		// Genuinely empty (or not an orders page at all): emit an empty payload.
		return { scraperVersion: SCRAPER_VERSION, domain, orders: [] };
	}

	const orders: AmazonExportOrder[] = [];
	for (let i = 0; i < cards.length; i++) {
		try {
			orders.push(parseOrderCard(cards[i], domain, i));
		} catch (cause) {
			if (cause instanceof AmazonScrapeError) {
				throw new AmazonScrapeError(
					`${cause.message} (parsed ${orders.length} of ${cards.length} orders before ` +
						`failing — re-run after Amazon's layout is supported again).`
				);
			}
			throw cause;
		}
	}

	return { scraperVersion: SCRAPER_VERSION, domain, orders };
}

/** Infer the Amazon domain from a location host (e.g. "www.amazon.co.uk"). */
export function inferDomain(host: string): string {
	const match = host.match(/amazon\.[a-z.]+$/i);
	return match ? match[0].toLowerCase() : host.toLowerCase();
}

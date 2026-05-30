const formatterByCurrency = new Map<string, Intl.NumberFormat>();

function formatterFor(currency: string): Intl.NumberFormat {
	const normalized = currency.trim().toUpperCase() || 'GBP';
	const existing = formatterByCurrency.get(normalized);
	if (existing) return existing;

	const formatter = new Intl.NumberFormat('en-US', {
		style: 'currency',
		currency: normalized,
		minimumFractionDigits: 2,
		maximumFractionDigits: 2
	});
	formatterByCurrency.set(normalized, formatter);
	return formatter;
}

function isDigits(value: string): boolean {
	return value.length > 0 && Array.from(value).every((character) => character >= '0' && character <= '9');
}

/**
 * Format a monetary value for display. Accepts the canonical decimal STRING
 * ("19.99") returned by the API or a plain number. Precision loss in DISPLAY is
 * acceptable — the formatter only renders 2 decimal places. Non-finite input
 * (e.g. a malformed string) falls back to a zero-valued currency string.
 */
export function formatAmount(amount: string | number, currency = 'GBP'): string {
	const numeric = typeof amount === 'number' ? amount : Number(amount);
	const safe = Number.isFinite(numeric) ? numeric : 0;
	return formatterFor(currency).format(safe);
}

/**
 * Parse raw user input into a CANONICAL 2-decimal money string the API accepts
 * ("3.5" → "3.50", "42" → "42.00"), or `null` when invalid. Validation: no
 * leading +/-, at most one ".", digits only, at most 2 fraction digits.
 */
export function parseAmountInput(raw: string): string | null {
	const value = raw.trim();

	if (value.length === 0 || value.startsWith('-') || value.startsWith('+')) {
		return null;
	}

	const parts = value.split('.');

	if (parts.length > 2) {
		return null;
	}

	const [whole, fraction = ''] = parts;

	if (!isDigits(whole) || (parts.length === 2 && (!isDigits(fraction) || fraction.length > 2))) {
		return null;
	}

	const amount = Number(value);

	return Number.isFinite(amount) ? amount.toFixed(2) : null;
}

/**
 * Parse a money value (canonical string or number) to a JS number for chart /
 * aggregation arithmetic. Non-finite input yields 0.
 */
export function amountToNumber(amount: string | number): number {
	const numeric = typeof amount === 'number' ? amount : Number(amount);
	return Number.isFinite(numeric) ? numeric : 0;
}

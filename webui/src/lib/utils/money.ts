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

export function formatAmount(amount: number, currency = 'GBP'): string {
	return formatterFor(currency).format(amount);
}

export function parseAmountInput(raw: string): number | null {
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

	return Number.isFinite(amount) ? amount : null;
}

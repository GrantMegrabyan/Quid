const MONEY_FORMATTER = new Intl.NumberFormat('en-US', {
	minimumFractionDigits: 2,
	maximumFractionDigits: 2
});

function isDigits(value: string): boolean {
	return value.length > 0 && Array.from(value).every((character) => character >= '0' && character <= '9');
}

export function formatAmount(amount: number): string {
	return MONEY_FORMATTER.format(amount);
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

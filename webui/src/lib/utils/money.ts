const MONEY_FORMATTER = new Intl.NumberFormat('en-US', {
	minimumFractionDigits: 2,
	maximumFractionDigits: 2
});

export function formatMoney(amount: number): string {
	return MONEY_FORMATTER.format(amount);
}

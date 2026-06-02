function pad(value: number): string {
	return String(value).padStart(2, '0');
}

function toLocalDate(value: string | Date): Date {
	if (value instanceof Date) {
		return new Date(value.getTime());
	}

	if (/^\d{4}-\d{2}-\d{2}/.test(value)) {
		const [year, month, day] = value.slice(0, 10).split('-').map(Number);
		return new Date(year, month - 1, day);
	}

	return new Date(value);
}

function monthKeyFromDate(date: Date): string {
	return `${date.getFullYear()}-${pad(date.getMonth() + 1)}`;
}

function parseMonthKey(key: string): { year: number; monthIndex: number } {
	const [year, month] = key.split('-').map(Number);
	return { year, monthIndex: month - 1 };
}

export function monthKey(date: string | Date): string {
	return monthKeyFromDate(toLocalDate(date));
}

export function currentMonthKey(reference: Date = new Date()): string {
	return monthKeyFromDate(toLocalDate(reference));
}

export function addMonths(key: string, offset: number): string {
	const { year, monthIndex } = parseMonthKey(key);
	return monthKeyFromDate(new Date(year, monthIndex + offset, 1));
}

export function previousMonthKey(key: string): string {
	return addMonths(key, -1);
}

export function nextMonthKey(key: string): string {
	return addMonths(key, 1);
}

export function daysInMonth(key: string): number {
	const { year, monthIndex } = parseMonthKey(key);
	return new Date(year, monthIndex + 1, 0).getDate();
}

export function dateKeyForMonthDay(key: string, day: number): string {
	return `${key}-${pad(day)}`;
}

/**
 * The inclusive `YYYY-MM-DD` date range for a single month key (`YYYY-MM`).
 * This is the range the dashboard fetches: the dashboard is strictly a
 * single-month view, so all of its analytics are derived client-side from just
 * this one month's rows. `from` is the first of the month, `to` is the last day.
 */
export function monthDateRange(monthKey: string): { from: string; to: string } {
	return {
		from: `${monthKey}-01`,
		to: `${monthKey}-${pad(daysInMonth(monthKey))}`
	};
}

export function formatMonthLabel(key: string): string {
	const [year, month] = key.split('-').map(Number);
	const date = new Date(year, month - 1, 1);

	return new Intl.DateTimeFormat('en-US', { month: 'short', year: 'numeric' }).format(date);
}

export function todayIso(): string {
	const today = new Date();
	return `${today.getFullYear()}-${pad(today.getMonth() + 1)}-${pad(today.getDate())}`;
}

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

export function centered12MonthWindow(selectedKey: string, todayKey = currentMonthKey()): string[] {
	let start = addMonths(selectedKey, -6);
	let end = addMonths(start, 11);

	if (end > todayKey) {
		end = todayKey;
		start = addMonths(end, -11);
	}

	return Array.from({ length: 12 }, (_, index) => addMonths(start, index));
}

export function last12MonthKeys(reference: Date = new Date()): string[] {
	const base = toLocalDate(reference);
	const year = base.getFullYear();
	const month = base.getMonth();

	return Array.from({ length: 12 }, (_, index) => {
		const offset = index - 11;
		return monthKeyFromDate(new Date(year, month + offset, 1));
	});
}

/**
 * The inclusive `YYYY-MM-DD` date range that bounds the centered 12-month
 * window for a selected month. This is the SINGLE range the dashboard needs to
 * fetch: it covers the selected month, the previous month (for the month-change
 * stat), and both 12-month charts in one request. `from` is the first day of
 * the earliest window month; `to` is the last day of the latest window month
 * (note the window extends up to 5 months PAST the selected month, capped at
 * today — so `to` is NOT simply the end of the selected month).
 */
export function windowDateRange(
	selectedKey: string,
	todayKey = currentMonthKey()
): { from: string; to: string } {
	const months = centered12MonthWindow(selectedKey, todayKey);
	const first = months[0];
	const last = months[months.length - 1];
	const lastDay = daysInMonth(last);
	return {
		from: `${first}-01`,
		to: `${last}-${pad(lastDay)}`
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

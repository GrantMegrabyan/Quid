import {
	addMonths,
	currentMonthKey,
	daysInMonth,
	formatMonthLabel,
	monthDateRange,
	monthKey,
	previousMonthKey,
	todayIso
} from '$utils/dates';

/**
 * How the dashboard's window is chosen.
 *
 * The view is either a single calendar MONTH (steppable with ‹ ›, the default
 * and the shape most of Quid's analytics assume) or a rolling PERIOD ending
 * today. A month selection remembers the period code it came from
 * (`restoreCode`) so leaving month mode returns you to the range you were on,
 * rather than to an arbitrary default.
 */
export type PeriodCode = '3M' | '6M' | 'YTD' | '1Y' | 'ALL';

export type PeriodSelection =
	| { kind: 'month'; monthKey: string; restoreCode: PeriodCode }
	| { kind: 'period'; code: PeriodCode };

/** Bucket width the trend chart should draw for a given selection. */
export type Granularity = 'day' | 'month';

export type ResolvedPeriod = {
	/** Inclusive `YYYY-MM-DD` bounds of the window being viewed. */
	from: string;
	to: string;
	/** The comparable window immediately before this one, if one exists. */
	prior: { from: string; to: string } | null;
	/** Short label for the window ("Aug 2026", "Last 6 months"). */
	label: string;
	/** Label for the comparison window ("Jul 2026", "prior 6 months"). */
	priorLabel: string;
	granularity: Granularity;
	/** True when the window is still filling up, i.e. it ends today. */
	inProgress: boolean;
};

export const PERIOD_CODES: PeriodCode[] = ['3M', '6M', 'YTD', '1Y', 'ALL'];

/** How the comparison window is described next to the delta. */
export const PRIOR_LABELS: Record<PeriodCode, string> = {
	'3M': 'prior 3 months',
	'6M': 'prior 6 months',
	YTD: 'prior period',
	'1Y': 'prior 12 months',
	ALL: ''
};

export const PERIOD_LABELS: Record<PeriodCode, string> = {
	'3M': 'Last 3 months',
	'6M': 'Last 6 months',
	YTD: 'Year to date',
	'1Y': 'Last 12 months',
	ALL: 'All time'
};

/** The earliest date Quid will ask the API for when the window is "all time". */
const EPOCH = '1970-01-01';

export const DEFAULT_PERIOD_CODE: PeriodCode = '6M';

export function isPeriodCode(value: unknown): value is PeriodCode {
	return typeof value === 'string' && (PERIOD_CODES as string[]).includes(value);
}

export function isPeriodSelection(value: unknown): value is PeriodSelection {
	if (typeof value !== 'object' || value === null) return false;
	const candidate = value as Partial<PeriodSelection>;
	if (candidate.kind === 'period') return isPeriodCode((candidate as { code?: unknown }).code);
	if (candidate.kind === 'month') {
		const month = (candidate as { monthKey?: unknown }).monthKey;
		return typeof month === 'string' && /^\d{4}-\d{2}$/.test(month);
	}
	return false;
}

export function defaultSelection(): PeriodSelection {
	return { kind: 'month', monthKey: currentMonthKey(), restoreCode: DEFAULT_PERIOD_CODE };
}

/** The period code a selection should restore to when leaving month mode. */
export function restoreCodeOf(selection: PeriodSelection): PeriodCode {
	return selection.kind === 'month' ? selection.restoreCode : selection.code;
}

function daysBetweenInclusive(from: string, to: string): number {
	const start = Date.parse(`${from}T00:00:00`);
	const end = Date.parse(`${to}T00:00:00`);
	return Math.round((end - start) / 86_400_000) + 1;
}

function shiftIso(iso: string, days: number): string {
	const date = new Date(`${iso}T00:00:00`);
	date.setDate(date.getDate() + days);
	const pad = (value: number) => String(value).padStart(2, '0');
	return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

function periodStart(code: PeriodCode, today: string): string {
	const thisMonth = monthKey(today);
	switch (code) {
		case '3M':
			return `${addMonths(thisMonth, -2)}-01`;
		case '6M':
			return `${addMonths(thisMonth, -5)}-01`;
		case 'YTD':
			return `${today.slice(0, 4)}-01-01`;
		case '1Y':
			return `${addMonths(thisMonth, -11)}-01`;
		case 'ALL':
			return EPOCH;
	}
}

/**
 * Turn a selection into the concrete window to fetch and chart, plus the window
 * to compare it against.
 *
 * The comparison rule mirrors what the user would draw by hand: a month is
 * compared with the previous calendar month; a rolling period is compared with
 * the equally long window ending the day before it starts. "All time" has
 * nothing before it, so it has no comparison.
 */
export function resolvePeriod(
	selection: PeriodSelection,
	today: string = todayIso()
): ResolvedPeriod {
	if (selection.kind === 'month') {
		const { from, to } = monthDateRange(selection.monthKey);
		const prev = previousMonthKey(selection.monthKey);
		const isCurrent = selection.monthKey === monthKey(today);
		return {
			from,
			to,
			prior: monthDateRange(prev),
			label: formatMonthLabel(selection.monthKey),
			priorLabel: formatMonthLabel(prev),
			granularity: 'day',
			inProgress: isCurrent
		};
	}

	const from = periodStart(selection.code, today);
	const to = today;
	const span = daysBetweenInclusive(from, to);
	const prior =
		selection.code === 'ALL' || span <= 0
			? null
			: { from: shiftIso(from, -span), to: shiftIso(from, -1) };

	return {
		from,
		to,
		prior,
		label: PERIOD_LABELS[selection.code],
		priorLabel: PRIOR_LABELS[selection.code],
		granularity: 'month',
		inProgress: true
	};
}

/**
 * Number of days of the window that have actually elapsed — the denominator for
 * a daily average. A past month has elapsed entirely; a window ending today has
 * only run to today.
 */
export function elapsedDays(resolved: ResolvedPeriod, today: string = todayIso()): number {
	const end = resolved.to > today ? today : resolved.to;
	if (end < resolved.from) return 0;
	return daysBetweenInclusive(resolved.from, end);
}

/** Total days in the window, used to project an in-progress month to its end. */
export function totalDays(resolved: ResolvedPeriod): number {
	return daysBetweenInclusive(resolved.from, resolved.to);
}

/** The month keys the window spans, oldest first — the x-axis of a month chart. */
export function monthsInRange(from: string, to: string): string[] {
	const months: string[] = [];
	let cursor = monthKey(from);
	const last = monthKey(to);
	// Guard against a malformed range spinning forever; no real window is
	// longer than a few decades of months.
	for (let i = 0; i < 1200 && cursor <= last; i += 1) {
		months.push(cursor);
		cursor = addMonths(cursor, 1);
	}
	return months;
}

/** Days in the window when it is a single month (the cumulative chart's axis). */
export function daysInSelectionMonth(selection: PeriodSelection): number {
	return selection.kind === 'month' ? daysInMonth(selection.monthKey) : 0;
}

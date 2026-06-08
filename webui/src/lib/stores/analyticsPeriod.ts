import { persisted } from '$lib/stores/persisted';
import type { AnalyticsWindow, CategoryComparisonQuery } from '$lib/repos/types';
import { addMonths, currentMonthKey, monthDateRange, todayIso } from '$utils/dates';

/** The selectable analytics period presets. */
export type AnalyticsPeriod = '3m' | '6m' | '12m' | 'all';

export const ANALYTICS_PERIODS: AnalyticsPeriod[] = ['3m', '6m', '12m', 'all'];

const PERIOD_MONTHS: Record<Exclude<AnalyticsPeriod, 'all'>, number> = {
	'3m': 3,
	'6m': 6,
	'12m': 12
};

function isAnalyticsPeriod(value: unknown): value is AnalyticsPeriod {
	return typeof value === 'string' && (ANALYTICS_PERIODS as string[]).includes(value);
}

/**
 * The analytics period the user is viewing, persisted across reloads. Defaults
 * to a rolling 6-month window. A stored value that is not one of the known
 * presets falls back to the default.
 */
export const analyticsPeriod = persisted<AnalyticsPeriod>(
	'quid:analytics-period:v1',
	'6m',
	isAnalyticsPeriod
);

/**
 * Convert a period preset into the inclusive `YYYY-MM-DD` window the analytics
 * API accepts. `'all'` is the whole history (an empty window). The bounded
 * presets span N calendar months ending today: `dateFrom` is the first day of
 * the month `N-1` months before the current month, so `'6m'` covers the current
 * month plus the five prior months.
 */
export function periodToWindow(period: AnalyticsPeriod): AnalyticsWindow {
	if (period === 'all') {
		return {};
	}
	const months = PERIOD_MONTHS[period];
	const fromMonth = addMonths(currentMonthKey(), -(months - 1));
	return {
		dateFrom: `${fromMonth}-01`,
		dateTo: todayIso()
	};
}

/**
 * The month-over-month comparison query that feeds the category-movers view.
 * Independent of the selected period preset — movers are always a single-month
 * comparison.
 *
 * Pass `referenceMonth` (a `YYYY-MM` key) to anchor the comparison on the LAST
 * COMPLETE month (the API's `summary.latestMonth`, which now excludes the
 * in-progress month when `asOf` is supplied) instead of the literal calendar
 * month. Without this, the comparison would use the current calendar month,
 * which is partial early in a month (or empty when the data lags), making every
 * category read as a fake collapse / "-100%". Defaults to the current calendar
 * month when no reference is given.
 */
export function monthOverMonthComparisonQuery(
	referenceMonth?: string | null
): CategoryComparisonQuery {
	const anchor = referenceMonth ?? currentMonthKey();
	const current = monthDateRange(anchor);
	const previous = monthDateRange(addMonths(anchor, -1));
	return {
		currentFrom: current.from,
		currentTo: current.to,
		previousFrom: previous.from,
		previousTo: previous.to
	};
}

import { derived, get, type Readable } from 'svelte/store';
import { persisted } from '$lib/stores/persisted';
import { currentMonthKey, addMonths, monthKey } from '$utils/dates';
import {
	defaultSelection,
	isPeriodSelection,
	resolvePeriod,
	restoreCodeOf,
	type PeriodCode,
	type PeriodSelection,
	type ResolvedPeriod
} from '$utils/period';

/**
 * The window the dashboard is showing — a single month or a rolling period.
 * Persisted across reloads so the app doesn't snap back to the current month
 * after a refresh; a stored value of the wrong shape falls back to the default
 * (this month). Supersedes the old `quid:selected-month:v1` key, which is no
 * longer read.
 */
export const selection = persisted<PeriodSelection>(
	'quid:period:v2',
	defaultSelection(),
	isPeriodSelection
);

/** The concrete date range, comparison window and labels for the selection. */
export const resolvedPeriod: Readable<ResolvedPeriod> = derived(selection, ($selection) =>
	resolvePeriod($selection)
);

/**
 * The month in view. In month mode this is the selected month; in period mode
 * it is the month the window ends in. Read-only: write through `setMonth` /
 * `stepMonth` / `setPeriod` so the selection stays the single source of truth.
 */
export const selectedMonth: Readable<string> = derived(selection, ($selection) =>
	$selection.kind === 'month' ? $selection.monthKey : monthKey(resolvePeriod($selection).to)
);

/** True when a single month is in view (the shape month-only analytics need). */
export const isMonthMode: Readable<boolean> = derived(
	selection,
	($selection) => $selection.kind === 'month'
);

export function setPeriod(code: PeriodCode): void {
	selection.set({ kind: 'period', code });
}

export function setMonth(month: string): void {
	selection.set({ kind: 'month', monthKey: month, restoreCode: restoreCodeOf(get(selection)) });
}

/** Step the month in view; entering month mode from a period lands on its last month. */
export function stepMonth(offset: number): void {
	const current = get(selection);
	const base = current.kind === 'month' ? current.monthKey : monthKey(resolvePeriod(current).to);
	setMonth(addMonths(base, offset));
}

export function goCurrentMonth(): void {
	setMonth(currentMonthKey());
}

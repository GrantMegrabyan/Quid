import { derived, type Readable } from 'svelte/store';
import { clampToData, type ResolvedPeriod } from '$utils/period';
import type { Expense } from '$lib/types';
import { expenses } from './expenses.js';
import { resolvedPeriod } from './ui.js';

/**
 * The window as the DATA sees it.
 *
 * `resolvedPeriod` is what we ask the API for, and for "all time" that starts
 * at an epoch sentinel. Displaying that bound directly is what stretched the
 * trend chart across five empty decades. This narrows it to the earliest
 * transaction actually loaded; every other window passes through untouched.
 *
 * It lives here rather than in `ui.ts` for two reasons: `expenses.ts` already
 * imports `ui.ts` (so the reverse would be a cycle), and — more importantly —
 * `resolvedPeriod` must NOT depend on the loaded rows, since the fetch is keyed
 * off it and would chase its own tail.
 */
function earliestDate(rows: Expense[]): string | null {
	let earliest: string | null = null;
	// Lexical comparison is correct for both stored date shapes (`YYYY-MM-DD`
	// and `YYYY-MM-DDTHH:MM:SS`).
	for (const row of rows) {
		if (earliest === null || row.date < earliest) earliest = row.date;
	}
	return earliest;
}

export const viewWindow: Readable<ResolvedPeriod> = derived(
	[resolvedPeriod, expenses],
	([$resolvedPeriod, $expenses]) => clampToData($resolvedPeriod, earliestDate($expenses))
);

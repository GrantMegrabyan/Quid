import { get, writable } from 'svelte/store';
import { expenseRepository } from '$lib/repos';
import { resolvedPeriod } from '$lib/stores/ui';
import type { Expense, ImportCsvResult } from '$lib/types';

/**
 * Expenses currently loaded into the UI. NOTE: this is NOT the full table — it
 * holds only the rows inside the SELECTED PERIOD (a month, or a rolling window
 * such as the last 6 months). Consumers must not assume it contains every
 * expense; anything needing a row from outside the window (e.g. resolving an
 * Amazon order's linked bank charge of any date) must fetch it directly rather
 * than reading from this store.
 */
export const expenses = writable<Expense[]>([]);

/**
 * Monotonic request token. Month navigation can fire overlapping fetches; only
 * the most recent one is allowed to write to the store, so a slow earlier
 * response can't clobber newer data (out-of-order responses).
 */
let latestRequest = 0;

/**
 * Fetch the selected period's expenses in ONE ranged request and publish them
 * to the store. All dashboard analytics are derived client-side from just these
 * rows, so the window the user picked is exactly the window that is fetched.
 */
export async function refreshExpenses(
	range: { from: string; to: string } = get(resolvedPeriod)
): Promise<void> {
	const requestId = ++latestRequest;
	const { from, to } = range;
	const rows = await expenseRepository.list({ dateFrom: from, dateTo: to });
	// Drop stale responses: a newer refresh has superseded this one.
	if (requestId !== latestRequest) return;
	expenses.set(rows);
}

type ExpenseCreateInput = Parameters<typeof expenseRepository.create>[0];
type ExpenseUpdatePatch = Parameters<typeof expenseRepository.update>[1];

export async function addExpense(input: ExpenseCreateInput): Promise<void> {
	await expenseRepository.create(input);
	await refreshExpenses();
}

export async function editExpense(id: string, patch: ExpenseUpdatePatch): Promise<void> {
	await expenseRepository.update(id, patch);
	await refreshExpenses();
}

export async function deleteExpense(id: string): Promise<void> {
	await expenseRepository.delete(id);
	await refreshExpenses();
}

export async function importCsvFiles(files: File[]): Promise<ImportCsvResult> {
	const result = await expenseRepository.importCsv(files);
	await refreshExpenses();
	return result;
}

import { get, writable } from 'svelte/store';
import { expenseRepository } from '$lib/repos';
import { selectedMonth } from '$lib/stores/ui';
import { windowDateRange } from '$lib/utils/dates';
import type { Expense, ImportCsvResult } from '$lib/types';

/**
 * Expenses currently loaded into the UI. NOTE: this is NOT the full table — it
 * holds only a SCOPED WINDOW keyed by the selected month (the centered
 * 12-month window around it, see `windowDateRange`). Consumers must not assume
 * it contains every expense; anything needing an out-of-window expense (e.g.
 * resolving an Amazon order's linked bank charge of any date) must fetch it
 * directly rather than reading from this store.
 */
export const expenses = writable<Expense[]>([]);

/**
 * Monotonic request token. Month navigation can fire overlapping fetches; only
 * the most recent one is allowed to write to the store, so a slow earlier
 * response can't clobber newer data (out-of-order responses).
 */
let latestRequest = 0;

/**
 * Fetch only the window of expenses needed for the given month (defaults to the
 * currently selected month) and publish it to the store. We deliberately fetch
 * the bounded 12-month window span in ONE request instead of the whole table.
 */
export async function refreshExpenses(monthKey: string = get(selectedMonth)): Promise<void> {
	const requestId = ++latestRequest;
	const { from, to } = windowDateRange(monthKey);
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

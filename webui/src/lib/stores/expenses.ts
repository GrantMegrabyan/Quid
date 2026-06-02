import { get, writable } from 'svelte/store';
import { expenseRepository } from '$lib/repos';
import { selectedMonth } from '$lib/stores/ui';
import { monthDateRange } from '$lib/utils/dates';
import type { Expense, ImportCsvResult } from '$lib/types';

/**
 * Expenses currently loaded into the UI. NOTE: this is NOT the full table — it
 * holds only the rows for the SELECTED MONTH. Consumers must not assume it
 * contains every expense; anything needing an out-of-month expense (e.g.
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
 * Fetch only the selected month's expenses (defaults to the currently selected
 * month) and publish them to the store. We deliberately fetch a single month in
 * ONE request instead of the whole table — all dashboard analytics are derived
 * client-side from just this month's rows.
 */
export async function refreshExpenses(monthKey: string = get(selectedMonth)): Promise<void> {
	const requestId = ++latestRequest;
	const { from, to } = monthDateRange(monthKey);
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

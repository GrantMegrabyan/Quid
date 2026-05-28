import { writable } from 'svelte/store';
import { expenseRepository } from '$lib/repos';
import type { Expense, ImportCsvResult } from '$lib/types';

export const expenses = writable<Expense[]>([]);

export async function refreshExpenses(): Promise<void> {
	const rows = await expenseRepository.list();
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

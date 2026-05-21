import type { Expense } from '$types';
import { getStore, setStore } from './mockStore.js';
import { RepositoryError } from './types.js';
import type { ExpenseRepository, ListExpensesQuery } from './types.js';

function byDateDesc(a: Expense, b: Expense): number {
	return b.date.localeCompare(a.date);
}

class MockExpenseRepository implements ExpenseRepository {
	async list(query?: ListExpensesQuery): Promise<Expense[]> {
		const { expenses } = getStore();
		const sorted = expenses.slice().sort(byDateDesc);
		const offset = query?.offset ?? 0;
		const sliced = query?.limit !== undefined ? sorted.slice(offset, offset + query.limit) : sorted.slice(offset);
		return sliced;
	}

	async create(input: Omit<Expense, 'id'>): Promise<Expense> {
		let created: Expense | undefined;
		setStore((s) => {
			const expense: Expense = { id: crypto.randomUUID(), ...input };
			s.expenses.push(expense);
			created = expense;
		});
		return created!;
	}

	async update(id: string, patch: Partial<Omit<Expense, 'id'>>): Promise<Expense> {
		let updated: Expense | undefined;
		setStore((s) => {
			const idx = s.expenses.findIndex((e) => e.id === id);
			if (idx === -1) {
				throw new RepositoryError('NOT_FOUND', `Expense not found: ${id}`);
			}
			const existing = s.expenses[idx];
			const patched: Expense = {
				id: existing.id,
				amount: patch.amount ?? existing.amount,
				date: patch.date ?? existing.date,
				categoryId: patch.categoryId ?? existing.categoryId,
				note: patch.note ?? existing.note,
			};
			s.expenses[idx] = patched;
			updated = patched;
		});
		return updated!;
	}

	async delete(id: string): Promise<void> {
		setStore((s) => {
			const idx = s.expenses.findIndex((e) => e.id === id);
			if (idx !== -1) {
				s.expenses.splice(idx, 1);
			}
		});
	}
}

export const expenseRepository: ExpenseRepository = new MockExpenseRepository();

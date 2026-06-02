import type {
	Expense,
	ImportCsvConfirmRequest,
	ImportCsvConfirmResult,
	ImportCsvPreviewResult,
	ImportCsvResult,
	ImportFreeformConfirmRequest,
	ImportLog
} from '$types';
import { getStore, setStore } from './mockStore.js';
import { RepositoryError } from './types.js';
import type { ExpenseRepository, ListExpensesQuery } from './types.js';

function byDateDesc(a: Expense, b: Expense): number {
	return b.date.localeCompare(a.date);
}

/** First day (as `YYYY-MM-DD`) after the given `YYYY-MM-DD` date. */
function dayAfter(dateOnly: string): string {
	const [year, month, day] = dateOnly.split('-').map(Number);
	const next = new Date(year, month - 1, day + 1);
	const pad = (n: number) => String(n).padStart(2, '0');
	return `${next.getFullYear()}-${pad(next.getMonth() + 1)}-${pad(next.getDate())}`;
}

export class MockExpenseRepository implements ExpenseRepository {
	async list(query?: ListExpensesQuery): Promise<Expense[]> {
		const { expenses } = getStore();
		let rows = expenses.slice();
		// Half-open lexical range, mirroring the backend: inclusive lower bound
		// and an exclusive upper bound at the start of the day AFTER `dateTo`, so
		// `YYYY-MM-DDTHH:MM:SS` rows on the boundary day are kept.
		if (query?.dateFrom !== undefined) {
			const from = query.dateFrom;
			rows = rows.filter((e) => e.date >= from);
		}
		if (query?.dateTo !== undefined) {
			const exclusiveUpper = dayAfter(query.dateTo);
			rows = rows.filter((e) => e.date < exclusiveUpper);
		}
		const sorted = rows.sort(byDateDesc);
		const offset = query?.offset ?? 0;
		return query?.limit !== undefined
			? sorted.slice(offset, offset + query.limit)
			: sorted.slice(offset);
	}

	async create(input: Omit<Expense, 'id'>): Promise<Expense> {
		const id = crypto.randomUUID();
		const newState = setStore((s) => {
			s.expenses.push({ id, ...input });
		});
		return newState.expenses.find((e) => e.id === id)!;
	}

	async update(id: string, patch: Partial<Omit<Expense, 'id'>>): Promise<Expense> {
		const newState = setStore((s) => {
			const idx = s.expenses.findIndex((e) => e.id === id);
			if (idx === -1) {
				throw new RepositoryError('NOT_FOUND', `Expense not found: ${id}`);
			}
			const existing = s.expenses[idx];
			s.expenses[idx] = {
				id: existing.id,
				name: patch.name ?? existing.name,
				amount: patch.amount ?? existing.amount,
				date: patch.date ?? existing.date,
				categoryId: patch.categoryId ?? existing.categoryId,
				note: patch.note ?? existing.note,
				displayName: patch.displayName !== undefined ? patch.displayName : existing.displayName,
				importance: patch.importance ?? existing.importance,
			};
		});
		return newState.expenses.find((e) => e.id === id)!;
	}

	async delete(id: string): Promise<void> {
		setStore((s) => {
			const idx = s.expenses.findIndex((e) => e.id === id);
			if (idx !== -1) {
				s.expenses.splice(idx, 1);
			}
		});
	}

	async importCsv(files: File[]): Promise<ImportCsvResult> {
		throw new RepositoryError(
			'VALIDATION',
			`CSV import is only supported by the HTTP backend (received ${files.length} file(s)).`
		);
	}

	async previewImportCsv(files: File[]): Promise<ImportCsvPreviewResult> {
		throw new RepositoryError(
			'VALIDATION',
			`CSV import preview is only supported by the HTTP backend (received ${files.length} file(s)).`
		);
	}

	async confirmImportCsv(input: ImportCsvConfirmRequest): Promise<ImportCsvConfirmResult> {
		throw new RepositoryError(
			'VALIDATION',
			`CSV import confirmation is only supported by the HTTP backend (${input.importId}).`
		);
	}

	async previewImportFreeform(_rawInput: string): Promise<ImportCsvPreviewResult> {
		throw new RepositoryError(
			'VALIDATION',
			'AI free-form import is only supported by the HTTP backend.'
		);
	}

	async confirmImportFreeform(_input: ImportFreeformConfirmRequest): Promise<ImportCsvConfirmResult> {
		throw new RepositoryError(
			'VALIDATION',
			'AI free-form import is only supported by the HTTP backend.'
		);
	}

	async listImportLogs(): Promise<ImportLog[]> {
		return [];
	}
}

export const expenseRepository: ExpenseRepository = new MockExpenseRepository();

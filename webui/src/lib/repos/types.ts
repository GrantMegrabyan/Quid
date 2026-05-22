import type { Category, Expense, ImportCsvResult } from '$types';

/**
 * Repository contracts stay HTTP-shaped so callers can swap transports later.
 */
export interface ListExpensesQuery {
	limit?: number;
	offset?: number;
}

/**
 * Expense repository contract for future HTTP-backed CRUD operations.
 */
export interface ExpenseRepository {
	list(query?: ListExpensesQuery): Promise<Expense[]>;
	create(input: Omit<Expense, 'id'>): Promise<Expense>;
	update(id: string, patch: Partial<Omit<Expense, 'id'>>): Promise<Expense>;
	delete(id: string): Promise<void>;
	importCsv(files: File[]): Promise<ImportCsvResult>;
}

/**
 * Category repository contract for future HTTP-backed CRUD operations.
 */
export interface CategoryRepository {
	list(): Promise<Category[]>;
	create(input: Omit<Category, 'id'>): Promise<Category>;
	update(id: string, patch: Partial<Omit<Category, 'id'>>): Promise<Category>;
	delete(id: string): Promise<void>;
}

export type RepositoryErrorCode = 'NOT_FOUND' | 'IMMUTABLE' | 'VALIDATION';

export class RepositoryError extends Error {
	constructor(
		public readonly code: RepositoryErrorCode,
		message: string
	) {
		super(message);
		this.name = 'RepositoryError';
	}
}

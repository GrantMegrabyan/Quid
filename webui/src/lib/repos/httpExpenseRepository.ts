import type {
	Expense,
	ImportCsvConfirmRequest,
	ImportCsvConfirmResult,
	ImportCsvPreviewResult,
	ImportCsvResult,
	ImportLog
} from '$types';
import { httpClient, HttpClient } from './httpClient.js';
import type { ExpenseRepository, ListExpensesQuery } from './types.js';

export class HttpExpenseRepository implements ExpenseRepository {
	constructor(private readonly client: HttpClient = httpClient) {}

	async list(query?: ListExpensesQuery): Promise<Expense[]> {
		return this.client.request<Expense[]>('api/v1/expenses', {
			query: { limit: query?.limit, offset: query?.offset }
		});
	}

	async create(input: Omit<Expense, 'id'>): Promise<Expense> {
		return this.client.request<Expense>('api/v1/expenses', {
			method: 'POST',
			body: input
		});
	}

	async update(id: string, patch: Partial<Omit<Expense, 'id'>>): Promise<Expense> {
		return this.client.request<Expense>(`api/v1/expenses/${encodeURIComponent(id)}`, {
			method: 'PATCH',
			body: patch
		});
	}

	async delete(id: string): Promise<void> {
		await this.client.request<void>(`api/v1/expenses/${encodeURIComponent(id)}`, {
			method: 'DELETE'
		});
	}

	async importCsv(
		files: File[],
		options: { aiCategorize?: boolean } = {}
	): Promise<ImportCsvResult> {
		const form = new FormData();
		for (const file of files) {
			form.append('files', file, file.name);
		}
		form.append('ai_categorize', options.aiCategorize ? 'true' : 'false');
		return this.client.request<ImportCsvResult>('api/v1/expenses/import-csv', {
			method: 'POST',
			formData: form
		});
	}

	async previewImportCsv(
		files: File[],
		options: { aiCategorize?: boolean } = {}
	): Promise<ImportCsvPreviewResult> {
		const form = new FormData();
		for (const file of files) {
			form.append('files', file, file.name);
		}
		form.append('ai_categorize', options.aiCategorize === false ? 'false' : 'true');
		return this.client.request<ImportCsvPreviewResult>('api/v1/expenses/import-csv/preview', {
			method: 'POST',
			formData: form
		});
	}

	async confirmImportCsv(input: ImportCsvConfirmRequest): Promise<ImportCsvConfirmResult> {
		return this.client.request<ImportCsvConfirmResult>('api/v1/expenses/import-csv/confirm', {
			method: 'POST',
			body: input
		});
	}

	async listImportLogs(): Promise<ImportLog[]> {
		return this.client.request<ImportLog[]>('api/v1/import-logs');
	}
}

export const httpExpenseRepository: ExpenseRepository = new HttpExpenseRepository();

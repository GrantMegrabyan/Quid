import type { Expense } from '$types';
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
}

export const httpExpenseRepository: ExpenseRepository = new HttpExpenseRepository();

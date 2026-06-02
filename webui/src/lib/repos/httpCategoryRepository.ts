import type { Category } from '$types';
import { httpClient, HttpClient } from './httpClient.js';
import type { CategoryDeleteResult, CategoryRepository } from './types.js';

export class HttpCategoryRepository implements CategoryRepository {
	constructor(private readonly client: HttpClient = httpClient) {}

	async list(): Promise<Category[]> {
		return this.client.request<Category[]>('api/v1/categories');
	}

	async create(input: Omit<Category, 'id'>): Promise<Category> {
		return this.client.request<Category>('api/v1/categories', {
			method: 'POST',
			body: input
		});
	}

	async update(id: string, patch: Partial<Omit<Category, 'id'>>): Promise<Category> {
		return this.client.request<Category>(`api/v1/categories/${encodeURIComponent(id)}`, {
			method: 'PATCH',
			body: patch
		});
	}

	async delete(id: string): Promise<CategoryDeleteResult> {
		return this.client.request<CategoryDeleteResult>(
			`api/v1/categories/${encodeURIComponent(id)}`,
			{ method: 'DELETE' }
		);
	}
}

export const httpCategoryRepository: CategoryRepository = new HttpCategoryRepository();

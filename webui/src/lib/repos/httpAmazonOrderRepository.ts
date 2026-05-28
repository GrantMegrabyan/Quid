import type {
	AmazonImportResult,
	AmazonMatchAllResult,
	AmazonOrder,
	Expense
} from '$types';
import { httpClient, HttpClient } from './httpClient.js';
import type { AmazonOrderRepository } from './types.js';

export class HttpAmazonOrderRepository implements AmazonOrderRepository {
	constructor(private readonly client: HttpClient = httpClient) {}

	async list(): Promise<AmazonOrder[]> {
		return this.client.request<AmazonOrder[]>('api/v1/amazon-orders');
	}

	async get(id: string): Promise<AmazonOrder> {
		return this.client.request<AmazonOrder>(
			`api/v1/amazon-orders/${encodeURIComponent(id)}`
		);
	}

	async importCsv(files: File[]): Promise<AmazonImportResult> {
		const form = new FormData();
		for (const file of files) {
			form.append('files', file, file.name);
		}
		return this.client.request<AmazonImportResult>('api/v1/amazon-orders/import-csv', {
			method: 'POST',
			formData: form
		});
	}

	async matchAll(): Promise<AmazonMatchAllResult> {
		return this.client.request<AmazonMatchAllResult>('api/v1/amazon-orders/match-all', {
			method: 'POST'
		});
	}

	async suggestedMatches(id: string): Promise<Expense[]> {
		return this.client.request<Expense[]>(
			`api/v1/amazon-orders/${encodeURIComponent(id)}/suggested-matches`
		);
	}

	async link(orderId: string, expenseId: string): Promise<Expense> {
		return this.client.request<Expense>(
			`api/v1/amazon-orders/${encodeURIComponent(orderId)}/link`,
			{ method: 'POST', body: { expenseId } }
		);
	}

	async unlink(orderId: string, expenseId: string): Promise<Expense> {
		return this.client.request<Expense>(
			`api/v1/amazon-orders/${encodeURIComponent(orderId)}/unlink`,
			{ method: 'POST', body: { expenseId } }
		);
	}

	async updateShortName(orderId: string, shortName: string): Promise<AmazonOrder> {
		return this.client.request<AmazonOrder>(
			`api/v1/amazon-orders/${encodeURIComponent(orderId)}/short-name`,
			{ method: 'PATCH', body: { shortName } }
		);
	}

	async delete(id: string): Promise<void> {
		await this.client.request<void>(`api/v1/amazon-orders/${encodeURIComponent(id)}`, {
			method: 'DELETE'
		});
	}
}

export const httpAmazonOrderRepository: AmazonOrderRepository = new HttpAmazonOrderRepository();

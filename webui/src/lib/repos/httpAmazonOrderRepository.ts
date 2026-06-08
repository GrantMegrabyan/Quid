import type {
	AmazonExportRequest,
	AmazonImportResult,
	AmazonMatchAllResult,
	AmazonOrder,
	AmazonOrderList,
	AmazonOrderListQuery,
	AmazonRecategorizeConfirmRow,
	AmazonRecategorizeConfirmResult,
	AmazonRecategorizePreviewResult,
	Expense
} from '$types';
import { httpClient, HttpClient } from './httpClient.js';
import type { AmazonOrderRepository } from './types.js';

export class HttpAmazonOrderRepository implements AmazonOrderRepository {
	constructor(private readonly client: HttpClient = httpClient) {}

	async list(query: AmazonOrderListQuery = {}): Promise<AmazonOrderList> {
		return this.client.request<AmazonOrderList>('api/v1/amazon-orders', {
			query: {
				limit: query.limit,
				offset: query.offset,
				linked: query.linked === undefined ? undefined : String(query.linked),
				categoryId: query.categoryId,
				search: query.search?.trim() || undefined
			}
		});
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

	async importExport(payload: AmazonExportRequest): Promise<AmazonImportResult> {
		return this.client.request<AmazonImportResult>('api/v1/amazon-orders/import-export', {
			method: 'POST',
			body: payload
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

	async updateCategory(orderId: string, categoryId: string | null): Promise<AmazonOrder> {
		return this.client.request<AmazonOrder>(
			`api/v1/amazon-orders/${encodeURIComponent(orderId)}/category`,
			{ method: 'PATCH', body: { categoryId } }
		);
	}

	async recategorizePreview(): Promise<AmazonRecategorizePreviewResult> {
		return this.client.request<AmazonRecategorizePreviewResult>(
			'api/v1/amazon-orders/recategorize/preview',
			{ method: 'POST' }
		);
	}

	async recategorizeConfirm(
		rows: AmazonRecategorizeConfirmRow[]
	): Promise<AmazonRecategorizeConfirmResult> {
		return this.client.request<AmazonRecategorizeConfirmResult>(
			'api/v1/amazon-orders/recategorize/confirm',
			{ method: 'POST', body: { rows } }
		);
	}

	async delete(id: string): Promise<void> {
		await this.client.request<void>(`api/v1/amazon-orders/${encodeURIComponent(id)}`, {
			method: 'DELETE'
		});
	}
}

export const httpAmazonOrderRepository: AmazonOrderRepository = new HttpAmazonOrderRepository();

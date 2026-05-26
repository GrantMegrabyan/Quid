import type { ImportRule, ImportRuleApplyResult, ImportRuleCreate, ImportRuleUpdate } from '$types';
import { httpClient, HttpClient } from './httpClient.js';
import type { ImportRuleRepository } from './types.js';

export class HttpImportRuleRepository implements ImportRuleRepository {
	constructor(private readonly client: HttpClient = httpClient) {}

	async list(): Promise<ImportRule[]> {
		return this.client.request<ImportRule[]>('api/v1/import-rules');
	}

	async create(input: ImportRuleCreate): Promise<ImportRule> {
		return this.client.request<ImportRule>('api/v1/import-rules', {
			method: 'POST',
			body: input
		});
	}

	async update(id: string, patch: ImportRuleUpdate): Promise<ImportRule> {
		return this.client.request<ImportRule>(`api/v1/import-rules/${encodeURIComponent(id)}`, {
			method: 'PATCH',
			body: patch
		});
	}

	async delete(id: string): Promise<void> {
		await this.client.request<void>(`api/v1/import-rules/${encodeURIComponent(id)}`, {
			method: 'DELETE'
		});
	}

	async apply(id: string): Promise<ImportRuleApplyResult> {
		return this.client.request<ImportRuleApplyResult>(
			`api/v1/import-rules/${encodeURIComponent(id)}/apply`,
			{ method: 'POST' }
		);
	}

	async applyAll(): Promise<ImportRuleApplyResult> {
		return this.client.request<ImportRuleApplyResult>('api/v1/import-rules/apply-all', {
			method: 'POST'
		});
	}
}

export const httpImportRuleRepository: ImportRuleRepository = new HttpImportRuleRepository();

import type { AiRule, AiRuleCreate, AiRuleUpdate } from '$types';
import { httpClient, HttpClient } from './httpClient.js';
import type { AiRuleRepository } from './types.js';

export class HttpAiRuleRepository implements AiRuleRepository {
	constructor(private readonly client: HttpClient = httpClient) {}

	async list(): Promise<AiRule[]> {
		return this.client.request<AiRule[]>('api/v1/ai-rules');
	}

	async create(input: AiRuleCreate): Promise<AiRule> {
		return this.client.request<AiRule>('api/v1/ai-rules', { method: 'POST', body: input });
	}

	async update(id: string, patch: AiRuleUpdate): Promise<AiRule> {
		return this.client.request<AiRule>(`api/v1/ai-rules/${encodeURIComponent(id)}`, {
			method: 'PATCH',
			body: patch
		});
	}

	async delete(id: string): Promise<void> {
		await this.client.request<void>(`api/v1/ai-rules/${encodeURIComponent(id)}`, {
			method: 'DELETE'
		});
	}
}

export const httpAiRuleRepository: AiRuleRepository = new HttpAiRuleRepository();

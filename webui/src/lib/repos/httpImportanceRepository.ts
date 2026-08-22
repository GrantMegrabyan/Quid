import type { ExpenseImportance, ImportanceTriageApplied, ImportanceTriageResult } from '$types';
import { httpClient, HttpClient } from './httpClient.js';
import type { ImportanceRepository } from './types.js';

export class HttpImportanceRepository implements ImportanceRepository {
	constructor(private readonly client: HttpClient = httpClient) {}

	async triage(limit?: number): Promise<ImportanceTriageResult> {
		return this.client.request<ImportanceTriageResult>('api/v1/importance/triage', {
			query: { limit: limit === undefined ? undefined : String(limit) }
		});
	}

	async applyTriage(input: {
		merchantKey: string;
		importance: ExpenseImportance;
	}): Promise<ImportanceTriageApplied> {
		return this.client.request<ImportanceTriageApplied>('api/v1/importance/triage', {
			method: 'POST',
			body: input
		});
	}
}

export const httpImportanceRepository: ImportanceRepository = new HttpImportanceRepository();

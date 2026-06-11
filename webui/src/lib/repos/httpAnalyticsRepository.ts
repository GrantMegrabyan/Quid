import type {
	AnalyticsSummary,
	DiagnosisResult,
	MonthlyTotalsResult,
	NarrativeResult,
	SavingsResult
} from '$types';
import { httpClient, HttpClient } from './httpClient.js';
import type { AnalyticsRepository, AnalyticsWindow } from './types.js';

function windowQuery(window?: AnalyticsWindow): Record<string, string | undefined> {
	return {
		date_from: window?.dateFrom,
		date_to: window?.dateTo
	};
}

export class HttpAnalyticsRepository implements AnalyticsRepository {
	constructor(private readonly client: HttpClient = httpClient) {}

	async summary(window?: AnalyticsWindow & { asOf?: string }): Promise<AnalyticsSummary> {
		return this.client.request<AnalyticsSummary>('api/v1/analytics/summary', {
			query: { ...windowQuery(window), as_of: window?.asOf }
		});
	}

	async monthlyTotals(window?: AnalyticsWindow): Promise<MonthlyTotalsResult> {
		return this.client.request<MonthlyTotalsResult>('api/v1/analytics/monthly-totals', {
			query: windowQuery(window)
		});
	}

	async diagnosis(asOf: string): Promise<DiagnosisResult> {
		return this.client.request<DiagnosisResult>('api/v1/analytics/diagnosis', {
			query: { as_of: asOf }
		});
	}

	async savings(asOf: string): Promise<SavingsResult> {
		return this.client.request<SavingsResult>('api/v1/analytics/savings', {
			query: { as_of: asOf }
		});
	}

	async narrative(): Promise<NarrativeResult> {
		return this.client.request<NarrativeResult>('api/v1/analytics/narrative');
	}

	async generateNarrative(input: { asOf: string }): Promise<NarrativeResult> {
		return this.client.request<NarrativeResult>('api/v1/analytics/narrative', {
			method: 'POST',
			body: { asOf: input.asOf }
		});
	}
}

export const httpAnalyticsRepository: AnalyticsRepository = new HttpAnalyticsRepository();

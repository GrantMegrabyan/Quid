import type {
	AnalyticsSummary,
	CategoryComparisonResult,
	CategoryTrendsResult,
	ImportanceBreakdownResult,
	MonthlyTotalsResult,
	TopMerchantsResult,
	WeekdayBreakdownResult
} from '$types';
import { httpClient, HttpClient } from './httpClient.js';
import type {
	AnalyticsRepository,
	AnalyticsWindow,
	CategoryComparisonQuery
} from './types.js';

function windowQuery(window?: AnalyticsWindow): Record<string, string | undefined> {
	return {
		date_from: window?.dateFrom,
		date_to: window?.dateTo
	};
}

export class HttpAnalyticsRepository implements AnalyticsRepository {
	constructor(private readonly client: HttpClient = httpClient) {}

	async summary(window?: AnalyticsWindow): Promise<AnalyticsSummary> {
		return this.client.request<AnalyticsSummary>('api/v1/analytics/summary', {
			query: windowQuery(window)
		});
	}

	async monthlyTotals(window?: AnalyticsWindow): Promise<MonthlyTotalsResult> {
		return this.client.request<MonthlyTotalsResult>('api/v1/analytics/monthly-totals', {
			query: windowQuery(window)
		});
	}

	async categoryTrends(window?: AnalyticsWindow): Promise<CategoryTrendsResult> {
		return this.client.request<CategoryTrendsResult>('api/v1/analytics/category-trends', {
			query: windowQuery(window)
		});
	}

	async categoryComparison(query: CategoryComparisonQuery): Promise<CategoryComparisonResult> {
		return this.client.request<CategoryComparisonResult>('api/v1/analytics/category-comparison', {
			query: {
				current_from: query.currentFrom,
				current_to: query.currentTo,
				previous_from: query.previousFrom,
				previous_to: query.previousTo
			}
		});
	}

	async topMerchants(
		window?: AnalyticsWindow & { limit?: number }
	): Promise<TopMerchantsResult> {
		return this.client.request<TopMerchantsResult>('api/v1/analytics/top-merchants', {
			query: { ...windowQuery(window), limit: window?.limit }
		});
	}

	async importanceBreakdown(window?: AnalyticsWindow): Promise<ImportanceBreakdownResult> {
		return this.client.request<ImportanceBreakdownResult>(
			'api/v1/analytics/importance-breakdown',
			{ query: windowQuery(window) }
		);
	}

	async weekdayBreakdown(window?: AnalyticsWindow): Promise<WeekdayBreakdownResult> {
		return this.client.request<WeekdayBreakdownResult>('api/v1/analytics/weekday-breakdown', {
			query: windowQuery(window)
		});
	}
}

export const httpAnalyticsRepository: AnalyticsRepository = new HttpAnalyticsRepository();

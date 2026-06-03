import type {
	AmazonExportRequest,
	AmazonImportResult,
	AmazonMatchAllResult,
	AmazonOrder,
	AmazonRecategorizeConfirmRow,
	AmazonRecategorizeConfirmResult,
	AmazonRecategorizePreviewResult,
	AnalyticsSummary,
	AppSettings,
	AppSettingsUpdate,
	Category,
	CategoryComparisonResult,
	CategoryTrendsResult,
	DistributionResult,
	Expense,
	ImportanceBreakdownResult,
	ImportanceTrendResult,
	LargeTransactionsResult,
	MonthlyTotalsResult,
	RecurringResult,
	TopMerchantsResult,
	WeekdayBreakdownResult,
	ImportCsvConfirmRequest,
	ImportCsvConfirmResult,
	ImportCsvPreviewResult,
	ImportCsvResult,
	ImportFreeformConfirmRequest,
	ImportLog,
	AiRule,
	AiRuleCreate,
	AiRuleUpdate,
	ImportRule,
	ImportRuleApplyResult,
	ImportRuleCreate,
	ImportRulePreviewRequest,
	ImportRulePreviewResult,
	ImportRuleUpdate
} from '$types';

/**
 * Repository contracts stay HTTP-shaped so callers can swap transports later.
 */
export interface ListExpensesQuery {
	limit?: number;
	offset?: number;
	/** Inclusive lower bound, `YYYY-MM-DD`. */
	dateFrom?: string;
	/** Inclusive upper bound, `YYYY-MM-DD` (the API treats it as inclusive). */
	dateTo?: string;
}

/** Result of deleting a category: how many expenses were reassigned to Uncategorized. */
export interface CategoryDeleteResult {
	reassigned: number;
}

/**
 * Expense repository contract for future HTTP-backed CRUD operations.
 */
export interface ExpenseRepository {
	list(query?: ListExpensesQuery): Promise<Expense[]>;
	create(input: Omit<Expense, 'id'>): Promise<Expense>;
	update(id: string, patch: Partial<Omit<Expense, 'id'>>): Promise<Expense>;
	delete(id: string): Promise<void>;
	importCsv(files: File[]): Promise<ImportCsvResult>;
	previewImportCsv(files: File[]): Promise<ImportCsvPreviewResult>;
	confirmImportCsv(input: ImportCsvConfirmRequest): Promise<ImportCsvConfirmResult>;
	previewImportFreeform(rawInput: string): Promise<ImportCsvPreviewResult>;
	confirmImportFreeform(input: ImportFreeformConfirmRequest): Promise<ImportCsvConfirmResult>;
	listImportLogs(): Promise<ImportLog[]>;
}

/**
 * Category repository contract for future HTTP-backed CRUD operations.
 */
export interface CategoryRepository {
	list(): Promise<Category[]>;
	create(input: Omit<Category, 'id'>): Promise<Category>;
	update(id: string, patch: Partial<Omit<Category, 'id'>>): Promise<Category>;
	delete(id: string): Promise<CategoryDeleteResult>;
}

export interface ImportRuleRepository {
	list(): Promise<ImportRule[]>;
	create(input: ImportRuleCreate): Promise<ImportRule>;
	update(id: string, patch: ImportRuleUpdate): Promise<ImportRule>;
	delete(id: string): Promise<void>;
	apply(id: string): Promise<ImportRuleApplyResult>;
	applyAll(): Promise<ImportRuleApplyResult>;
	preview(input: ImportRulePreviewRequest): Promise<ImportRulePreviewResult>;
}

export interface AiRuleRepository {
	list(): Promise<AiRule[]>;
	create(input: AiRuleCreate): Promise<AiRule>;
	update(id: string, patch: AiRuleUpdate): Promise<AiRule>;
	delete(id: string): Promise<void>;
}

export interface AppSettingsRepository {
	get(): Promise<AppSettings>;
	update(patch: AppSettingsUpdate): Promise<AppSettings>;
}

export interface AmazonOrderRepository {
	list(): Promise<AmazonOrder[]>;
	get(id: string): Promise<AmazonOrder>;
	importCsv(files: File[]): Promise<AmazonImportResult>;
	importExport(payload: AmazonExportRequest): Promise<AmazonImportResult>;
	matchAll(): Promise<AmazonMatchAllResult>;
	suggestedMatches(id: string): Promise<Expense[]>;
	link(orderId: string, expenseId: string): Promise<Expense>;
	unlink(orderId: string, expenseId: string): Promise<Expense>;
	updateShortName(orderId: string, shortName: string): Promise<AmazonOrder>;
	updateCategory(orderId: string, categoryId: string | null): Promise<AmazonOrder>;
	recategorizePreview(): Promise<AmazonRecategorizePreviewResult>;
	recategorizeConfirm(
		rows: AmazonRecategorizeConfirmRow[]
	): Promise<AmazonRecategorizeConfirmResult>;
	delete(id: string): Promise<void>;
}

/** Optional inclusive `YYYY-MM-DD` date window shared by most analytics calls. */
export interface AnalyticsWindow {
	dateFrom?: string;
	dateTo?: string;
}

/** The two explicit periods compared by `categoryComparison`. */
export interface CategoryComparisonQuery {
	currentFrom: string;
	currentTo: string;
	previousFrom: string;
	previousTo: string;
}

export interface AnalyticsRepository {
	/** `asOf` (a `YYYY-MM-DD` "today") unlocks complete-month averages + run-rate fields. */
	summary(window?: AnalyticsWindow & { asOf?: string }): Promise<AnalyticsSummary>;
	monthlyTotals(window?: AnalyticsWindow): Promise<MonthlyTotalsResult>;
	categoryTrends(window?: AnalyticsWindow & { limit?: number }): Promise<CategoryTrendsResult>;
	categoryComparison(query: CategoryComparisonQuery): Promise<CategoryComparisonResult>;
	topMerchants(window?: AnalyticsWindow & { limit?: number }): Promise<TopMerchantsResult>;
	importanceBreakdown(window?: AnalyticsWindow): Promise<ImportanceBreakdownResult>;
	weekdayBreakdown(window?: AnalyticsWindow): Promise<WeekdayBreakdownResult>;
	recurring(window?: AnalyticsWindow): Promise<RecurringResult>;
	largeTransactions(window?: AnalyticsWindow & { limit?: number }): Promise<LargeTransactionsResult>;
	distribution(window?: AnalyticsWindow): Promise<DistributionResult>;
	importanceTrend(window?: AnalyticsWindow): Promise<ImportanceTrendResult>;
}

export type RepositoryErrorCode = 'NOT_FOUND' | 'IMMUTABLE' | 'VALIDATION';

export class RepositoryError extends Error {
	constructor(
		public readonly code: RepositoryErrorCode,
		message: string
	) {
		super(message);
		this.name = 'RepositoryError';
	}
}

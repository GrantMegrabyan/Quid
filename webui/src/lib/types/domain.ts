/**
 * API contract assumptions:
 * - `id` values are strings (UUID-shaped in the mock, but any string is allowed).
 * - `date` is an ISO `YYYY-MM-DD` string.
 * - Monetary values (`amount`, Amazon `total`/`price`, rule `matchAmountValue*`)
 *   are canonical DECIMAL STRINGS like "19.99" (always exactly 2 decimals) in
 *   API responses, never JSON numbers. Request bodies may send either a string
 *   or a number — the backend coerces both to Decimal — but the frontend sends
 *   canonical 2dp strings. For arithmetic (charts, sorting, aggregation) parse
 *   with `amountToNumber` from `$utils/money`. `amount` is positive; the form
 *   layer enforces that rule.
 */

export interface Expense {
	id: string;
	name: string;
	/** Canonical decimal string ("19.99") in responses; sent as a 2dp string. */
	amount: string;
	date: string;
	categoryId: string;
	note: string;
	displayName?: string | null;
	importance: ExpenseImportance;
	/** Provenance of `categoryId`, controlling whether a linked Amazon order's
	 *  category may override it. Read-only (set server-side). Optional in mocks
	 *  and creation payloads. */
	categorySource?: ExpenseCategorySource;
	/** Provenance of `importance` — who chose it. Only `manual` (and `rule`)
	 *  reflect a real decision; the rest are guesses. Read-only (set
	 *  server-side). Optional in mocks and creation payloads. */
	importanceSource?: ExpenseImportanceSource;
	/** Amazon orders this expense is linked to. Multiple when Amazon bills
	 *  several orders together as a single bank charge. Optional in mocks
	 *  and creation payloads; the API always returns at least []. */
	amazonOrderIds?: string[];
	/** Effective note for display: the expense's own `note`, else a linked
	 *  Amazon order's short name (resolved server-side). Optional in mocks;
	 *  the API always returns it (possibly ""). */
	resolvedNote?: string;
}

export type ExpenseImportance = 'essential' | 'important' | 'discretionary';

export type ExpenseCategorySource = 'manual' | 'rule' | 'amazon' | 'ai' | 'import';

/** `learned` is reserved for a future automatic pass; nothing writes it yet. */
export type ExpenseImportanceSource = 'manual' | 'rule' | 'learned' | 'ai' | 'import';

export interface Category {
	id: string;
	name: string;
	color: string;
	icon: string;
	description?: string;
}

export const UNCATEGORIZED_ID = 'uncategorized' as const;

export interface ImportCsvFileReport {
	filename: string;
	rows: number;
	imported: number;
	skippedDuplicates: number;
	skippedExcluded: number;
	skippedInvalidRows: number;
}

export interface ImportCsvResult {
	imported: number;
	skippedDuplicates: number;
	skippedExcluded: number;
	skippedInvalidRows: number;
	transactionsFound: number;
	aiCategorized: number;
	categoriesCreated: Category[];
	expenses: Expense[];
	files: ImportCsvFileReport[];
}

export type ImportPreviewKind = 'create' | 'category_update' | 'duplicate_same_category' | 'excluded';

export interface ImportPreviewCategory {
 	id: string | null;
 	name: string;
 	exists: boolean;
}

export interface ImportPreviewRow {
 	previewRowId: string;
 	filename: string;
 	sourceRow: number;
 	dedupeKeyHash: string;
 	name: string;
 	/**
 	 * Name a matching `categorize` import rule will apply on confirm
 	 * (rule `set_display_name`). `null` when no rule overrides it.
 	 */
 	displayName: string | null;
 	/** Canonical decimal string ("19.99"). */
 	amount: string;
 	date: string;
 	note: string;
 	kind: ImportPreviewKind;
 	/**
 	 * Human-readable explanation for `kind === 'excluded'` rows (why the row
 	 * won't be imported by default): AI exclusion, a matching exclude rule, a
 	 * detected refund, or detected incoming money. `null` for other rows.
 	 */
 	reason: string | null;
 	existingExpenseId: string | null;
 	existingCategoryId: string | null;
 	existingCategoryName: string | null;
 	suggestedCategory: ImportPreviewCategory;
 	/**
 	 * True when `suggestedCategory` came from a matching `categorize` import
 	 * rule (not AI/heuristic). Lets the preview flag the category as rule-driven.
 	 */
 	categoryFromRule: boolean;
 	/**
 	 * The AI/CSV-derived category a matching rule overrode, set only when it
 	 * differs from `suggestedCategory`. `null` otherwise.
 	 */
 	overriddenCategoryName: string | null;
	suggestedImportance: ExpenseImportance;
	existingImportance: ExpenseImportance | null;
}

export interface ImportCsvPreviewSummary {
 	creates: number;
 	categoryUpdates: number;
 	hiddenDuplicates: number;
 	excluded: number;
 	invalidRows: number;
 	aiCategorized: number;
}

/**
 * A row dropped during CSV parsing, with a human-readable reason. Free-form
 * import produces no invalid rows (malformed AI output is dropped upstream).
 */
export interface ImportPreviewInvalidRow {
 	filename: string;
 	sourceRow: number;
 	reason: string;
 	name: string;
 	amount: string;
 	date: string;
}

export interface ImportCsvPreviewResult {
 	importId: string;
 	rows: ImportPreviewRow[];
 	invalid: ImportPreviewInvalidRow[];
 	summary: ImportCsvPreviewSummary;
 	files: ImportCsvFileReport[];
}

export interface ImportCsvConfirmCreateRow {
 	previewRowId: string;
 	dedupeKeyHash: string;
 	name: string;
 	/** Canonical decimal string ("19.99"). */
 	amount: string;
 	date: string;
 	note: string;
 	categoryName: string;
	importance: ExpenseImportance;
	/** What the preview proposed. Sent back unchanged so the server can tell a
	 *  deliberate override (a training label) from an untouched suggestion. */
	suggestedImportance?: ExpenseImportance;
}

export interface ImportCsvConfirmCategoryUpdateRow {
  	previewRowId: string;
  	dedupeKeyHash: string;
  	existingExpenseId: string;
  	categoryName: string;
	importance: ExpenseImportance;
	suggestedImportance?: ExpenseImportance;
  	accept: boolean;
}

export interface ImportCsvConfirmRequest {
 	importId: string;
 	files: string[];
 	creates: ImportCsvConfirmCreateRow[];
 	categoryUpdates: ImportCsvConfirmCategoryUpdateRow[];
}

export interface ImportFreeformPreviewRequest {
	rawInput: string;
}

export interface ImportFreeformConfirmRequest {
	importId: string;
	rawInput: string;
	files?: string[];
	creates: ImportCsvConfirmCreateRow[];
	categoryUpdates: ImportCsvConfirmCategoryUpdateRow[];
}

export interface ImportCsvConfirmResult {
 	created: number;
 	updated: number;
 	skippedDuplicates: number;
 	skippedStaleUpdates: number;
 	keptExisting: number;
 	categoriesCreated: Category[];
 	expenses: Expense[];
}

export type RuleAction = 'exclude' | 'categorize';
export type NameMatchOp = 'contains' | 'equals' | 'starts_with' | 'ends_with';
export type AmountMatchOp = 'gte' | 'lte' | 'eq' | 'between';

export interface ImportRule {
	id: string;
	name: string;
	enabled: boolean;
	priority: number;
	action: RuleAction;
	targetCategoryId: string | null;
	matchNameOp: NameMatchOp | null;
	matchNameValue: string | null;
	matchAmountOp: AmountMatchOp | null;
	/** Canonical decimal string ("19.99") in responses; sent as a 2dp string. */
	matchAmountValue: string | null;
	matchAmountValue2: string | null;
	matchDateFrom: string | null;
	matchDateTo: string | null;
	matchDayOfMonth: number | null;
	setDisplayName: string | null;
	setNote: string | null;
	/** Overrides the imported/AI importance on match. `null` leaves it alone. */
	setImportance: ExpenseImportance | null;
	createdAt: string;
}

export type ImportRuleCreate = Omit<ImportRule, 'id' | 'createdAt'>;
export type ImportRuleUpdate = Partial<ImportRuleCreate>;

export interface ImportRuleApplyResult {
	matched: number;
	updated: number;
	deleted: number;
}

/** Match-condition fields used to dry-run a (possibly unsaved) rule. */
export type ImportRulePreviewRequest = Pick<
	ImportRule,
	| 'matchNameOp'
	| 'matchNameValue'
	| 'matchAmountOp'
	| 'matchAmountValue'
	| 'matchAmountValue2'
	| 'matchDateFrom'
	| 'matchDateTo'
	| 'matchDayOfMonth'
>;

export interface ImportRulePreviewResult {
	matched: number;
	expenses: Expense[];
}

export interface AiRule {
	id: string;
	text: string;
	enabled: boolean;
	priority: number;
	createdAt: string;
}

export type AiRuleCreate = Omit<AiRule, 'id' | 'createdAt'>;
export type AiRuleUpdate = Partial<AiRuleCreate>;

export interface ImportLog {
	id: string;
	importedAt: string;
	source: 'csv' | 'freeform';
	rawInput: string | null;
	files: string[];
	imported: number;
	updated: number;
	skippedDuplicates: number;
	skippedExcluded: number;
	skippedInvalidRows: number;
}

export interface AppSettings {
	currency: string;
	categorizeModel: string;
	showImportanceBadge: boolean;
	aiCategorizeEnabled: boolean;
	aiShortNamesEnabled: boolean;
	updatedAt: string;
}

export interface AppSettingsUpdate {
	currency?: string;
	categorizeModel?: string;
	showImportanceBadge?: boolean;
	aiCategorizeEnabled?: boolean;
	aiShortNamesEnabled?: boolean;
}

export interface AmazonOrderItem {
	title: string;
	quantity: number;
	/** Canonical decimal string ("9.99"); null when not parseable. */
	price: string | null;
}

export interface AmazonOrderShipment {
	shipDate: string | null;
	tracking: string | null;
	/** Canonical decimal string ("9.99"). */
	total: string;
	items: AmazonOrderItem[];
}

/**
 * Minimal expense fields embedded in an Amazon order so the `/amazon` page can
 * render "Linked to ..." labels without fetching the full expense table.
 */
export interface AmazonLinkedExpense {
	id: string;
	name: string;
	/** Canonical decimal string ("19.99"). */
	amount: string;
	displayName: string | null;
}

export interface AmazonOrder {
	id: string;
	orderDate: string;
	/** Canonical decimal string ("19.99"). */
	total: string;
	currency: string;
	items: AmazonOrderItem[];
	shipments: AmazonOrderShipment[];
	paymentLast4: string | null;
	orderUrl: string | null;
	/** Brief AI-generated (or user-edited) description of what was purchased. */
	shortName: string | null;
	/**
	 * AI-derived spending category for the order, generated once at import.
	 * When the order is linked to an uncategorised expense, that expense
	 * inherits this category.
	 */
	categoryId: string | null;
	importedAt: string;
	linkedExpenseIds: string[];
	/**
	 * Label data for each id in `linkedExpenseIds` (server-resolved). May omit
	 * ids whose expense was concurrently deleted; render the raw id as fallback.
	 */
	linkedExpenses: AmazonLinkedExpense[];
}

/** Server-driven filters for the Amazon orders list. */
export interface AmazonOrderListQuery {
	limit?: number;
	offset?: number;
	/** `true` = only linked orders, `false` = only not-linked, undefined = all. */
	linked?: boolean;
	/** A category id, or `''`/`'uncategorized'` to mean "no category". */
	categoryId?: string;
	/** Case-insensitive substring over order id, short name, and item titles. */
	search?: string;
}

/** A page of Amazon orders plus the total count matching the active filters. */
export interface AmazonOrderList {
	items: AmazonOrder[];
	total: number;
	limit: number;
	offset: number;
}

export interface AmazonImportSkippedOrder {
	orderId: string;
	reason: string;
}

export interface AmazonImportFileReport {
	filename: string;
	ordersParsed: number;
	skippedRows: number;
	/** Per-order skip reasons. Populated by the browser-export import; left
	 *  empty/undefined by CSV import (additive + backwards compatible). */
	skipped?: AmazonImportSkippedOrder[];
}

export interface AmazonImportResult {
	created: number;
	updated: number;
	autoMatched: number;
	ambiguous: number;
	/** Of the auto-matched count, how many came from the combined-order
	 *  pass (multiple Amazon orders linked to one bank charge). */
	combinedMatched?: number;
	files: AmazonImportFileReport[];
}

export interface AmazonMatchAllResult {
	autoMatched: number;
	ambiguous: number;
	totalOrders: number;
	combinedMatched?: number;
}

/** One order's AI re-categorisation suggestion (read-only preview row). */
export interface AmazonRecategorizePreviewRow {
	orderId: string;
	name: string;
	/** Canonical decimal string ("19.99"). */
	total: string;
	orderDate: string;
	currentCategoryId: string | null;
	currentCategoryName: string | null;
	suggestedCategoryName: string;
	/** True when the suggested name maps to an existing category (else confirm
	 *  would create a new one). */
	suggestedCategoryExists: boolean;
	/** True when the suggestion differs from the order's current category. */
	changed: boolean;
}

export interface AmazonRecategorizePreviewResult {
	rows: AmazonRecategorizePreviewRow[];
	eligible: number;
	changed: number;
	unchanged: number;
}

export interface AmazonRecategorizeConfirmRow {
	orderId: string;
	categoryName: string;
}

export interface AmazonRecategorizeConfirmResult {
	updated: number;
	categoriesCreated: number;
	expensesUpdated: number;
}

/**
 * Browser-export payload shape POSTed to `POST /api/v1/amazon-orders/import-export`.
 *
 * MONEY-AS-STRINGS CONTRACT: every monetary field (order `total`, item
 * `price`, shipment `total`) is a JSON STRING ("19.99"), never a number — the
 * backend does exact `Decimal` matching, and a JSON number produced by float
 * arithmetic would silently fail to match. The scraper emits the exact scraped
 * text; never `parseFloat` a price. See `webui/src/lib/amazon/scraper.ts`.
 */
export interface AmazonExportItem {
	title: string;
	quantity: number;
	/** Money STRING ("9.99"), never a number. Null when not parseable. */
	price: string | null;
}

export interface AmazonExportShipment {
	/** Money STRING ("9.99"), never a number. */
	total: string | null;
	shipDate: string | null;
	tracking: string | null;
	items: AmazonExportItem[];
}

export interface AmazonExportOrder {
	orderId: string;
	/** Normalised `YYYY-MM-DD`. */
	orderDate: string;
	/** Money STRING ("19.99"), never a number. Null when not parseable. */
	total: string | null;
	currency?: string | null;
	status?: string | null;
	items: AmazonExportItem[];
	shipments: AmazonExportShipment[];
	paymentLast4?: string | null;
	orderUrl?: string | null;
}

export interface AmazonExportRequest {
	/** Version of the scraper that produced this payload (e.g. "1.0.0"). */
	scraperVersion?: string;
	/** Source domain (e.g. "amazon.co.uk"); used for provenance/logging. */
	domain?: string;
	orders: AmazonExportOrder[];
}

/* -------------------------------------------------------------------------- */
/* Analytics                                                                  */
/* -------------------------------------------------------------------------- */
/* All `total`/`amount`/`delta` fields are canonical decimal STRINGS ("19.99")
 * (deltas may be negative, e.g. "-12.00"). Parse with `amountToNumber` for
 * charting/sorting. `percentChange`/`currentMonthPaceVsAverage` are JS numbers
 * (e.g. 25 = +25%) or `null` when there is no previous baseline. `month`
 * values are `YYYY-MM`. */

export interface MonthlyTotal {
	/** `YYYY-MM`. */
	month: string;
	total: string;
	count: number;
}

export interface MonthlyTotalsResult {
	months: MonthlyTotal[];
	total: string;
	average: string;
	count: number;
}

export interface AnalyticsSummary {
	total: string;
	transactionCount: number;
	monthsCovered: number;
	completeMonthsCovered: number;
	averagePerCompleteMonth: string;
	latestMonth: string | null;
	latestMonthTotal: string;
	currentMonth: string | null;
	currentMonthToDate: string;
	currentMonthProjected: string;
	currentMonthPaceVsAverage: number | null;
}

export interface DiagnosisTransaction {
	id: string;
	name: string;
	displayName: string | null;
	amount: string;
	date: string;
}

export interface DiagnosisContributor {
	merchant: string;
	current: string;
	baseline: string;
	delta: string;
	isNew: boolean;
}

export interface DiagnosisIncrease {
	categoryId: string;
	categoryName: string;
	color: string;
	current: string;
	baseline: string;
	delta: string;
	percentChange: number | null;
	isNew: boolean;
	contributors: DiagnosisContributor[];
	transactions: DiagnosisTransaction[];
}

export interface DiagnosisDecrease {
	categoryId: string;
	categoryName: string;
	color: string;
	current: string;
	baseline: string;
	delta: string;
}

export interface DiagnosisResult {
	latestMonth: string | null;
	baselineFrom: string | null;
	baselineTo: string | null;
	baselineMonthCount: number;
	totalCurrent: string;
	totalBaseline: string;
	increases: DiagnosisIncrease[];
	otherIncreasesTotal: string;
	otherIncreasesCount: number;
	decreases: DiagnosisDecrease[];
}

export interface PriceCreepItem {
	name: string;
	oldAmount: string;
	newAmount: string;
	monthlyDelta: string;
	annualDelta: string;
	sinceMonth: string;
}

export interface NewRecurringItem {
	name: string;
	amount: string;
	firstMonth: string;
	annualCost: string;
}

export interface HabitItem {
	name: string;
	count: number;
	total: string;
	average: string;
}

/** Recurring merchant in the savings stack — omits the occurrence count and carries a span-scaled monthlyEstimate. */
export interface RecurringStackItem {
	name: string;
	amount: string;
	monthsCovered: number;
	firstMonth: string;
	lastMonth: string;
	monthlyEstimate: string;
}

export interface RecurringStack {
	items: RecurringStackItem[];
	monthlyTotal: string;
	annualTotal: string;
}

export interface SavingsResult {
	latestMonth: string | null;
	windowFrom: string | null;
	priceCreep: PriceCreepItem[];
	newRecurring: NewRecurringItem[];
	habits: HabitItem[];
	recurringStack: RecurringStack;
}

export interface AnalyticsNarrative {
	month: string;
	content: string;
	generatedAt: string;
	model: string;
}

export interface NarrativeResult {
	narrative: AnalyticsNarrative | null;
}

/**
 * Importance triage: merchants with no hand-set importance yet, ranked by
 * total spend so a handful of decisions covers most of the money.
 */
export interface TriageMerchant {
	/** `lower(trim(name))` — the grouping key, and what POST /triage takes. */
	merchantKey: string;
	merchantName: string;
	transactionCount: number;
	/** Canonical decimal string ("19.99"). */
	totalAmount: string;
	/** Spend-weighted majority of what these rows currently hold — a guess. */
	currentImportance: ExpenseImportance;
	categoryId: string | null;
	lastDate: string;
}

export interface ImportanceCoverage {
	labelledMerchants: number;
	unlabelledMerchants: number;
	/** Canonical decimal string ("19.99"). */
	labelledAmount: string;
	totalAmount: string;
	corrections: number;
	/** Corrections that flipped the value; the rest are confirmations. */
	overrides: number;
}

export interface ImportanceTriageResult {
	merchants: TriageMerchant[];
	coverage: ImportanceCoverage;
}

export interface ImportanceTriageApplied {
	updated: number;
	coverage: ImportanceCoverage;
}

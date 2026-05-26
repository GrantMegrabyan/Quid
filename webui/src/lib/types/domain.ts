/**
 * API contract assumptions:
 * - `id` values are strings (UUID-shaped in the mock, but any string is allowed).
 * - `date` is an ISO `YYYY-MM-DD` string.
 * - `amount` is positive; the form layer enforces that rule.
 */

export interface Expense {
	id: string;
	name: string;
	amount: number;
	date: string;
	categoryId: string;
	note: string;
	displayName?: string | null;
	importance: ExpenseImportance;
	amazonOrderId?: string | null;
}

export type ExpenseImportance = 'essential' | 'important' | 'discretionary';

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
 	amount: number;
 	date: string;
 	note: string;
 	kind: ImportPreviewKind;
 	existingExpenseId: string | null;
 	existingCategoryId: string | null;
 	existingCategoryName: string | null;
 	suggestedCategory: ImportPreviewCategory;
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

export interface ImportCsvPreviewResult {
 	importId: string;
 	rows: ImportPreviewRow[];
 	summary: ImportCsvPreviewSummary;
 	files: ImportCsvFileReport[];
}

export interface ImportCsvConfirmCreateRow {
 	previewRowId: string;
 	dedupeKeyHash: string;
 	name: string;
 	amount: number;
 	date: string;
 	note: string;
 	categoryName: string;
	importance: ExpenseImportance;
}

export interface ImportCsvConfirmCategoryUpdateRow {
  	previewRowId: string;
  	dedupeKeyHash: string;
  	existingExpenseId: string;
  	categoryName: string;
	importance: ExpenseImportance;
  	accept: boolean;
}

export interface ImportCsvConfirmRequest {
 	importId: string;
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
	matchAmountValue: number | null;
	matchAmountValue2: number | null;
	matchDateFrom: string | null;
	matchDateTo: string | null;
	setDisplayName: string | null;
	createdAt: string;
}

export type ImportRuleCreate = Omit<ImportRule, 'id' | 'createdAt'>;
export type ImportRuleUpdate = Partial<ImportRuleCreate>;

export interface ImportRuleApplyResult {
	matched: number;
	updated: number;
	deleted: number;
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
	files: string[];
	imported: number;
	updated: number;
	skippedDuplicates: number;
	skippedExcluded: number;
	skippedInvalidRows: number;
}

export interface AppSettings {
	currency: string;
	showImportanceBadge: boolean;
	updatedAt: string;
}

export interface AppSettingsUpdate {
	currency?: string;
	showImportanceBadge?: boolean;
}

export interface AmazonOrderItem {
	title: string;
	quantity: number;
	price: number | null;
}

export interface AmazonOrder {
	id: string;
	orderDate: string;
	total: number;
	currency: string;
	items: AmazonOrderItem[];
	paymentLast4: string | null;
	orderUrl: string | null;
	importedAt: string;
	linkedExpenseIds: string[];
}

export interface AmazonImportFileReport {
	filename: string;
	ordersParsed: number;
	skippedRows: number;
}

export interface AmazonImportResult {
	created: number;
	updated: number;
	autoMatched: number;
	ambiguous: number;
	files: AmazonImportFileReport[];
}

export interface AmazonMatchAllResult {
	autoMatched: number;
	ambiguous: number;
	totalOrders: number;
}

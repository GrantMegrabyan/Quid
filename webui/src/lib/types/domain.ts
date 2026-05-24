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
}

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

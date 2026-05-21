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
}

export const UNCATEGORIZED_ID = 'uncategorized' as const;

import type { Page } from '@playwright/test';

/**
 * Mirrors `src/lib/repos/mockStore.ts` LS_KEY exactly. Kept inline (not imported)
 * so the Playwright config does not need Vite alias resolution.
 */
export const LS_KEY = 'expense-tracker:store:v2';
export const THEME_KEY = 'theme';
export const UNCATEGORIZED_ID = 'uncategorized';

export interface SeedCategory {
	id: string;
	name: string;
	color: string;
	icon: string;
}

export interface SeedExpense {
	id: string;
	name: string;
	amount: number;
	date: string;
	categoryId: string;
	note: string;
}

export interface SeedState {
	categories: SeedCategory[];
	expenses: SeedExpense[];
}

function isoDaysAgo(days: number): string {
	const now = new Date();
	const then = new Date(now.getFullYear(), now.getMonth(), now.getDate() - days);
	const pad = (n: number) => String(n).padStart(2, '0');
	return `${then.getFullYear()}-${pad(then.getMonth() + 1)}-${pad(then.getDate())}`;
}

export function isoMonthOffset(offset: number, day = 1): string {
	const now = new Date();
	const date = new Date(now.getFullYear(), now.getMonth() + offset, day);
	const pad = (n: number) => String(n).padStart(2, '0');
	return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

export function monthLabelOffset(offset: number): string {
	const now = new Date();
	const date = new Date(now.getFullYear(), now.getMonth() + offset, 1);
	return new Intl.DateTimeFormat('en-US', { month: 'short', year: 'numeric' }).format(date);
}

/** Deterministic minimal seed that always contains current-month data so charts populate. */
export function buildSeed(overrides: Partial<SeedState> = {}): SeedState {
	const base: SeedState = {
		categories: [
			{ id: UNCATEGORIZED_ID, name: 'Uncategorized', color: '#9ca3af', icon: 'circle-help' },
			{ id: 'cat-groceries', name: 'Groceries', color: '#22c55e', icon: 'shopping-cart' },
			{ id: 'cat-transport', name: 'Transport', color: '#3b82f6', icon: 'train-front' }
		],
		expenses: [
			{
				id: 'exp-seed-1',
				name: 'Whole Foods',
				amount: 42.5,
				date: isoDaysAgo(2),
				categoryId: 'cat-groceries',
				note: 'Weekly groceries'
			},
			{
				id: 'exp-seed-2',
				name: 'Uber',
				amount: 12,
				date: isoDaysAgo(5),
				categoryId: 'cat-transport',
				note: ''
			}
		]
	};
	return { ...base, ...overrides };
}

/**
 * Install an init script + theme preference for every page in the context BEFORE
 * any app script runs, so `mockStore.loadFromStorage()` picks up the seed on first
 * read. Always call this in `beforeEach` so tests start from a known state.
 */
export async function seedLocalStorage(
	page: Page,
	state: SeedState,
	theme?: 'light' | 'dark',
	overwrite = false
): Promise<void> {
	await page.addInitScript(
		({ key, value, themeKey, themeValue, shouldOverwrite }) => {
			try {
				if (shouldOverwrite || window.localStorage.getItem(key) === null) {
					window.localStorage.setItem(key, value);
				}
				if (themeValue !== null && window.localStorage.getItem(themeKey) === null) {
					window.localStorage.setItem(themeKey, themeValue);
				}
			} catch {
				// Storage unavailable; tests that depend on seed will surface the failure.
			}
		},
		{
			key: LS_KEY,
			value: JSON.stringify(state),
			themeKey: THEME_KEY,
			themeValue: theme ?? null,
			shouldOverwrite: overwrite
		}
	);
}

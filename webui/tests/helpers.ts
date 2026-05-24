import type { Page } from '@playwright/test';

export const THEME_KEY = 'theme';
export const UNCATEGORIZED_ID = 'uncategorized';

export const API_BASE_URL = process.env.QUID_API_URL ?? 'http://localhost:8001';

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

export function buildSeed(overrides: Partial<SeedState> = {}): SeedState {
	const base: SeedState = {
		categories: [
			{ id: UNCATEGORIZED_ID, name: 'Uncategorized', color: '#9ca3af', icon: 'circle-help' },
			{ id: 'cat-groceries', name: 'Groceries', color: '#22c55e', icon: 'shopping-cart' },
			{ id: 'cat-public-transport', name: 'Public Transport', color: '#3b82f6', icon: 'train-front' }
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
				categoryId: 'cat-public-transport',
				note: ''
			}
		]
	};
	return { ...base, ...overrides };
}

async function postSeedState(state: SeedState): Promise<void> {
	const response = await fetch(`${API_BASE_URL}/api/v1/testing/seed-state`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({
			categories: state.categories,
			expenses: state.expenses
		})
	});
	if (!response.ok) {
		const text = await response.text();
		throw new Error(
			`seed-state POST failed: ${response.status} ${response.statusText}\n${text}`
		);
	}
}

export async function seedApiState(
	page: Page,
	state: SeedState,
	theme?: 'light' | 'dark'
): Promise<void> {
	await postSeedState(state);
	if (theme !== undefined) {
		await page.addInitScript(
			({ key, value }) => {
				try {
					if (window.localStorage.getItem(key) === null) {
						window.localStorage.setItem(key, value);
					}
				} catch {
					/* storage unavailable */
				}
			},
			{ key: THEME_KEY, value: theme }
		);
	}
}

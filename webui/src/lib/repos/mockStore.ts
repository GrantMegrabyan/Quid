import type { Category, Expense, ExpenseImportance } from '$types';
import { normalizeCategoryIcon } from '$utils/categoryIcons';
import { defaultCategories, sampleExpenses } from './seed.js';

export const LS_KEY = 'expense-tracker:store:v2';

export interface MockStoreState {
	categories: Category[];
	expenses: Expense[];
}

type StoredExpense = Omit<Expense, 'name' | 'importance'> & {
	name?: unknown;
	importance?: unknown;
};
type StoredCategory = Omit<Category, 'icon'> & { icon?: unknown };

interface NormalizeResult {
	state: MockStoreState;
	changed: boolean;
}

function deepCopy<T>(value: T): T {
	return JSON.parse(JSON.stringify(value)) as T;
}

function freshSeed(): MockStoreState {
	return {
		categories: defaultCategories(),
		expenses: sampleExpenses(),
	};
}

function normalizeStoredState(state: MockStoreState): NormalizeResult {
	let changed = false;
	const seedIconById = new Map(defaultCategories().map((category) => [category.id, category.icon]));
	const categories = (state.categories as StoredCategory[]).map((category) => {
		const icon = normalizeCategoryIcon(category.icon, seedIconById.get(category.id));
		if (category.icon === icon) {
			return category as Category;
		}

		changed = true;
		return {
			...category,
			icon
		} as Category;
	});

	const seedNameById = new Map(sampleExpenses().map((expense) => [expense.id, expense.name]));
	const expenses = (state.expenses as StoredExpense[]).map((expense) => {
		const name =
			typeof expense.name === 'string' && expense.name.trim().length > 0
				? expense.name
				: (seedNameById.get(expense.id) ?? 'Unknown merchant');
		const importance =
			expense.importance === 'essential' ||
			expense.importance === 'important' ||
			expense.importance === 'discretionary'
				? expense.importance
				: 'important';

		if (expense.name === name && expense.importance === importance) {
			return expense as Expense;
		}

		changed = true;
		return {
			...expense,
			name,
			importance: importance as ExpenseImportance
		} as Expense;
	});

	return {
		state: { ...state, categories, expenses },
		changed
	};
}

function getStorage(): Storage | null {
	try {
		return typeof window !== 'undefined' ? window.localStorage : null;
	} catch {
		return null;
	}
}

function loadFromStorage(): MockStoreState | null {
	const storage = getStorage();
	if (storage === null) return null;
	try {
		const raw = storage.getItem(LS_KEY);
		if (raw === null) return null;
		const parsed: unknown = JSON.parse(raw);
		if (
			parsed !== null &&
			typeof parsed === 'object' &&
			Array.isArray((parsed as { categories?: unknown }).categories) &&
			Array.isArray((parsed as { expenses?: unknown }).expenses)
		) {
			return parsed as MockStoreState;
		}
		// Malformed — fall through to reseed.
		return null;
	} catch {
		return null;
	}
}

function persistToStorage(state: MockStoreState): void {
	const storage = getStorage();
	if (storage === null) return;
	try {
		storage.setItem(LS_KEY, JSON.stringify(state));
	} catch {
		// Quota exceeded or storage unavailable; continue with in-memory state.
	}
}

let _store: MockStoreState | null = null;

function internalStore(): MockStoreState {
	if (_store === null) {
		const persisted = loadFromStorage();
		const normalized = persisted === null ? null : normalizeStoredState(persisted);
		_store = normalized?.state ?? freshSeed();
		if (persisted === null) {
			persistToStorage(_store);
		} else if (normalized?.changed) {
			persistToStorage(_store);
		}
	}
	return _store;
}

export function getStore(): MockStoreState {
	return deepCopy(internalStore());
}

/**
 * Applies `updater` to a deep-copy draft of the current state.
 * If `updater` throws, the internal state is left unchanged (transactional).
 * On success, persists and returns a deep copy of the new state.
 */
export function setStore(updater: (s: MockStoreState) => void): MockStoreState {
	const draft = deepCopy(internalStore());
	updater(draft);
	_store = draft;
	persistToStorage(draft);
	return deepCopy(draft);
}

export function resetStore(): void {
	const storage = getStorage();
	if (storage !== null) {
		try {
			storage.removeItem(LS_KEY);
		} catch {
			// Storage unavailable; reset in-memory only.
		}
	}
	_store = freshSeed();
	persistToStorage(_store);
}

import type { Category, Expense } from '$types';
import { defaultCategories, sampleExpenses } from './seed.js';

export const LS_KEY = 'expense-tracker:store:v2';

export interface MockStoreState {
	categories: Category[];
	expenses: Expense[];
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
		_store = persisted ?? freshSeed();
		if (persisted === null) {
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

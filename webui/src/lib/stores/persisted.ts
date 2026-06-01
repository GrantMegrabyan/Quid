import { writable, type Writable } from 'svelte/store';
import { browser } from '$app/environment';

/**
 * A writable Svelte store whose value is mirrored to `localStorage`, so view
 * state (e.g. the selected month, the active tab) survives a page reload.
 *
 * SSR-safe: on the server the store behaves like a plain `writable` and never
 * touches `localStorage`. Reads/writes are wrapped in try/catch so a disabled
 * or full storage (or malformed JSON from an older app version) degrades to the
 * provided default instead of throwing.
 *
 * @param key      Storage key. Prefer a namespaced, versioned key, e.g.
 *                 `quid:selected-month:v1`, so a future shape change is a no-op
 *                 fallback rather than a crash.
 * @param initial  Default value when nothing valid is stored yet.
 * @param validate Optional guard; if it returns false the stored value is
 *                 discarded and `initial` is used. Use this to reject stale or
 *                 out-of-range values.
 */
export function persisted<T>(
	key: string,
	initial: T,
	validate?: (value: T) => boolean
): Writable<T> {
	const start = browser ? read(key, initial, validate) : initial;
	const store = writable<T>(start);

	if (browser) {
		store.subscribe((value) => {
			try {
				localStorage.setItem(key, JSON.stringify(value));
			} catch {
				// Storage unavailable/full — keep the in-memory value working.
			}
		});
	}

	return store;
}

function read<T>(key: string, initial: T, validate?: (value: T) => boolean): T {
	try {
		const raw = localStorage.getItem(key);
		if (raw === null) return initial;
		const parsed = JSON.parse(raw) as T;
		if (validate && !validate(parsed)) return initial;
		return parsed;
	} catch {
		return initial;
	}
}

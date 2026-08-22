import { get, writable, type Writable } from 'svelte/store';
import { browser } from '$app/environment';

/**
 * Appearance: the Paper theme ships in two tones — `light` (ink on paper) and
 * `dark` (paper on ink) — plus `system`, which follows the OS preference and
 * keeps following it while the app is open.
 *
 * The resolved tone is applied as the `dark` class on <html> (the Tailwind
 * `@custom-variant`) and mirrored to `localStorage` under `quid:theme:v2`.
 * `src/app.html` reads the same key before first paint, so a reload never
 * flashes the wrong tone.
 */
export type ThemeId = 'light' | 'dark' | 'system';

export const STORAGE_KEY = 'quid:theme:v2';

export const THEMES: { id: ThemeId; label: string }[] = [
	{ id: 'light', label: 'Paper' },
	{ id: 'dark', label: 'Ink' },
	{ id: 'system', label: 'System' }
];

const THEME_IDS: ThemeId[] = ['light', 'dark', 'system'];

function isThemeId(value: unknown): value is ThemeId {
	return typeof value === 'string' && (THEME_IDS as string[]).includes(value);
}

function readStored(): ThemeId {
	if (!browser) return 'light';
	try {
		const raw = localStorage.getItem(STORAGE_KEY);
		return isThemeId(raw) ? raw : 'light';
	} catch {
		return 'light';
	}
}

function systemPrefersDark(): boolean {
	if (!browser) return false;
	return window.matchMedia('(prefers-color-scheme: dark)').matches;
}

function resolve(id: ThemeId): 'light' | 'dark' {
	if (id === 'system') return systemPrefersDark() ? 'dark' : 'light';
	return id;
}

function apply(id: ThemeId): void {
	if (!browser) return;
	const tone = resolve(id);
	document.documentElement.classList.toggle('dark', tone === 'dark');
	document.documentElement.setAttribute('data-theme', tone);
}

const store: Writable<ThemeId> = writable<ThemeId>(readStored());

if (browser) {
	apply(get(store));

	// While on `system`, track the OS flipping between light and dark.
	window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
		if (get(store) === 'system') apply('system');
	});
}

export const theme = {
	subscribe: store.subscribe,
	setTheme(id: ThemeId): void {
		if (!isThemeId(id)) return;
		store.set(id);
		if (!browser) return;
		apply(id);
		try {
			localStorage.setItem(STORAGE_KEY, id);
		} catch {
			// Storage unavailable — the in-memory choice still applies.
		}
	},
	/** Flip between the two explicit tones; `system` resolves first. */
	toggle(): void {
		theme.setTheme(resolve(get(store)) === 'dark' ? 'light' : 'dark');
	},
	/** The tone actually on screen, for consumers that need the concrete value. */
	resolved(): 'light' | 'dark' {
		return resolve(get(store));
	}
};

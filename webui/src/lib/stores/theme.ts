import { writable } from 'svelte/store';

export type ThemeId =
	| 'default-light'
	| 'default-dark'
	| 'latte'
	| 'frappe'
	| 'macchiato'
	| 'mocha';

export const THEMES: { id: ThemeId; label: string }[] = [
	{ id: 'default-light', label: 'Default Light' },
	{ id: 'default-dark', label: 'Default Dark' },
	{ id: 'latte', label: 'Catppuccin Latte' },
	{ id: 'frappe', label: 'Catppuccin Frappé' },
	{ id: 'macchiato', label: 'Catppuccin Macchiato' },
	{ id: 'mocha', label: 'Catppuccin Mocha' },
];

const DARK_THEMES: ThemeId[] = ['default-dark', 'frappe', 'macchiato', 'mocha'];

function readCurrentTheme(): ThemeId {
	if (typeof document === 'undefined') return 'default-dark';
	return (document.documentElement.getAttribute('data-theme') as ThemeId) || 'default-dark';
}

const { subscribe, set } = writable<ThemeId>(readCurrentTheme());

export const theme = {
	subscribe,
	setTheme(id: ThemeId) {
		document.documentElement.setAttribute('data-theme', id);
		if (DARK_THEMES.includes(id)) {
			document.documentElement.classList.add('dark');
		} else {
			document.documentElement.classList.remove('dark');
		}
		try {
			localStorage.setItem('theme', id);
		} catch {
			/* noop */
		}
		set(id);
	},
};

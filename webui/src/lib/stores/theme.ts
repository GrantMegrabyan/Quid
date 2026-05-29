import { readable } from 'svelte/store';

// Dasher ships a single dark theme. This store is kept as a safe no-op so that
// any lingering imports continue to type-check.
export type ThemeId = 'dasher';

export const THEMES: { id: ThemeId; label: string }[] = [];

export const theme = {
	...readable<ThemeId>('dasher'),
	setTheme(_id: ThemeId): void {
		/* no-op: theme switching has been removed */
	},
};

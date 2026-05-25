import { icons as LucideIcons } from '@lucide/svelte';
import type { LucideIcon } from '@lucide/svelte';

export const FALLBACK_CATEGORY_ICON = 'circle-help';

type LucideExports = Record<string, unknown>;

export type CategoryIconOption = {
	key: string;
	label: string;
	component: LucideIcon;
};

export type CategoryIconKey = string;

const LABEL_OVERRIDES = new Map<string, string>([[FALLBACK_CATEGORY_ICON, 'Other']]);

function exportNameToIconKey(name: string): string {
	return name
		.replace(/^Lucide/, '')
		.replace(/Icon$/, '')
		.replace(/([A-Z]+)([A-Z][a-z])/g, '$1-$2')
		.replace(/([a-z0-9])([A-Z])/g, '$1-$2')
		.replace(/([a-zA-Z])([0-9])/g, '$1-$2')
		.replace(/([0-9])([a-zA-Z])/g, '$1-$2')
		.toLowerCase();
}

function iconKeyToLabel(key: string): string {
	return (
		LABEL_OVERRIDES.get(key) ??
		key
			.split('-')
			.map((part) => part.charAt(0).toUpperCase() + part.slice(1))
			.join(' ')
	);
}

function isExportedIcon(name: string, exported: unknown): exported is LucideIcon {
	return (
		/^[A-Z]/.test(name) &&
		typeof exported === 'function'
	);
}

function buildCategoryIconOptions(exports: LucideExports): readonly CategoryIconOption[] {
	const options = new Map<string, CategoryIconOption>();

	for (const [name, exported] of Object.entries(exports)) {
		if (!isExportedIcon(name, exported)) continue;

		const key = exportNameToIconKey(name);
		if (options.has(key)) continue;

		options.set(key, {
			key,
			label: iconKeyToLabel(key),
			component: exported,
		});
	}

	return Array.from(options.values()).sort((a, b) => a.label.localeCompare(b.label));
}

export const CATEGORY_ICON_OPTIONS = buildCategoryIconOptions(LucideIcons as LucideExports);

const KNOWN_ICON_KEYS = new Set<string>(CATEGORY_ICON_OPTIONS.map((option) => option.key));
const ICON_COMPONENT_BY_KEY = new Map<string, LucideIcon>(
	CATEGORY_ICON_OPTIONS.map((option) => [option.key, option.component]),
);

const LEGACY_ICON_BY_EMOJI = new Map<string, string>([
	['•', FALLBACK_CATEGORY_ICON],
	['🛒', 'shopping-cart'],
	['🚇', 'train-front'],
	['🏠', 'house'],
	['🍽️', 'utensils'],
	['🍽', 'utensils'],
	['🧾', 'receipt'],
	['☕', 'coffee'],
	['🍎', 'shopping-cart'],
	['🥑', 'shopping-cart'],
]);

export function normalizeCategoryIcon(value: unknown, fallback = FALLBACK_CATEGORY_ICON): string {
	if (typeof value !== 'string') return fallback;
	const trimmed = value.trim();
	if (KNOWN_ICON_KEYS.has(trimmed)) return trimmed;
	return LEGACY_ICON_BY_EMOJI.get(trimmed) ?? fallback;
}

export function getCategoryIconComponent(value: unknown): LucideIcon {
	const key = normalizeCategoryIcon(value);
	return ICON_COMPONENT_BY_KEY.get(key) ?? ICON_COMPONENT_BY_KEY.get(FALLBACK_CATEGORY_ICON)!;
}

/**
 * Filter category icon options by a free-text query. Matches against label and key
 * (case-insensitive, substring match). Empty query returns the full list.
 */
export function filterCategoryIcons(query: string): readonly CategoryIconOption[] {
	const q = query.trim().toLowerCase();
	if (q === '') return CATEGORY_ICON_OPTIONS;
	return CATEGORY_ICON_OPTIONS.filter(
		(opt) => opt.label.toLowerCase().includes(q) || opt.key.toLowerCase().includes(q),
	);
}

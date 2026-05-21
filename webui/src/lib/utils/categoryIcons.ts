export const FALLBACK_CATEGORY_ICON = 'circle-help';

export const CATEGORY_ICON_OPTIONS = [
	{ key: 'shopping-cart', label: 'Groceries' },
	{ key: 'train-front', label: 'Transport' },
	{ key: 'house', label: 'Housing' },
	{ key: 'utensils', label: 'Dining' },
	{ key: 'receipt', label: 'Bills' },
	{ key: 'wallet', label: 'Wallet' },
	{ key: 'coffee', label: 'Coffee' },
	{ key: 'car', label: 'Car' },
	{ key: FALLBACK_CATEGORY_ICON, label: 'Other' },
] as const;

const KNOWN_ICON_KEYS = new Set<string>(CATEGORY_ICON_OPTIONS.map((option) => option.key));
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

export type CategoryIconKey = (typeof CATEGORY_ICON_OPTIONS)[number]['key'];

export function normalizeCategoryIcon(value: unknown, fallback = FALLBACK_CATEGORY_ICON): string {
	if (typeof value !== 'string') return fallback;
	const trimmed = value.trim();
	if (KNOWN_ICON_KEYS.has(trimmed)) return trimmed;
	return LEGACY_ICON_BY_EMOJI.get(trimmed) ?? fallback;
}

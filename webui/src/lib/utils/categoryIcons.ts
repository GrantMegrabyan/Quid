export const FALLBACK_CATEGORY_ICON = 'circle-help';

export const CATEGORY_ICON_OPTIONS = [
	// Food & drink
	{ key: 'shopping-cart', label: 'Groceries' },
	{ key: 'shopping-bag', label: 'Shopping' },
	{ key: 'utensils', label: 'Dining' },
	{ key: 'coffee', label: 'Coffee' },
	{ key: 'pizza', label: 'Pizza' },
	{ key: 'sandwich', label: 'Fast food' },
	{ key: 'wine', label: 'Wine' },
	{ key: 'beer', label: 'Beer' },
	{ key: 'martini', label: 'Cocktails' },
	{ key: 'cup-soda', label: 'Soda' },
	{ key: 'ice-cream-bowl', label: 'Ice cream' },
	{ key: 'cookie', label: 'Snacks' },
	{ key: 'cake', label: 'Desserts' },
	{ key: 'popcorn', label: 'Popcorn' },
	{ key: 'apple', label: 'Fruit' },
	{ key: 'banana', label: 'Banana' },
	{ key: 'carrot', label: 'Produce' },
	{ key: 'fish', label: 'Seafood' },
	{ key: 'beef', label: 'Meat' },

	// Transport
	{ key: 'car', label: 'Car' },
	{ key: 'fuel', label: 'Fuel' },
	{ key: 'train-front', label: 'Transport' },
	{ key: 'bus', label: 'Bus' },
	{ key: 'bike', label: 'Bike' },
	{ key: 'plane', label: 'Flights' },
	{ key: 'truck', label: 'Moving' },
	{ key: 'map-pin', label: 'Travel' },

	// Home & utilities
	{ key: 'house', label: 'Housing' },
	{ key: 'building-2', label: 'Rent' },
	{ key: 'landmark', label: 'Mortgage' },
	{ key: 'bed', label: 'Bedroom' },
	{ key: 'wrench', label: 'Maintenance' },
	{ key: 'hammer', label: 'Repairs' },
	{ key: 'paint-bucket', label: 'Decor' },
	{ key: 'zap', label: 'Electricity' },
	{ key: 'flame', label: 'Gas' },
	{ key: 'droplets', label: 'Water' },
	{ key: 'wifi', label: 'Internet' },
	{ key: 'smartphone', label: 'Phone' },

	// Tech & entertainment
	{ key: 'tv', label: 'TV' },
	{ key: 'monitor', label: 'Streaming' },
	{ key: 'laptop', label: 'Tech' },
	{ key: 'headphones', label: 'Audio' },
	{ key: 'gamepad-2', label: 'Games' },
	{ key: 'music', label: 'Music' },
	{ key: 'film', label: 'Movies' },
	{ key: 'camera', label: 'Photography' },

	// Money & work
	{ key: 'receipt', label: 'Bills' },
	{ key: 'wallet', label: 'Wallet' },
	{ key: 'credit-card', label: 'Credit card' },
	{ key: 'banknote', label: 'Cash' },
	{ key: 'coins', label: 'Coins' },
	{ key: 'hand-coins', label: 'Income' },
	{ key: 'piggy-bank', label: 'Savings' },
	{ key: 'shield', label: 'Insurance' },
	{ key: 'briefcase', label: 'Work' },

	// Health & family
	{ key: 'heart-pulse', label: 'Health' },
	{ key: 'stethoscope', label: 'Doctor' },
	{ key: 'pill', label: 'Pharmacy' },
	{ key: 'dumbbell', label: 'Fitness' },
	{ key: 'baby', label: 'Baby' },
	{ key: 'dog', label: 'Dog' },
	{ key: 'cat', label: 'Cat' },
	{ key: 'paw-print', label: 'Pets' },

	// Personal & hobbies
	{ key: 'shirt', label: 'Clothing' },
	{ key: 'scissors', label: 'Personal care' },
	{ key: 'brush', label: 'Beauty' },
	{ key: 'palette', label: 'Hobbies' },
	{ key: 'book', label: 'Books' },
	{ key: 'graduation-cap', label: 'Education' },
	{ key: 'flower', label: 'Garden' },

	// Outdoors & weather
	{ key: 'leaf', label: 'Eco' },
	{ key: 'sun', label: 'Summer' },
	{ key: 'moon', label: 'Night' },
	{ key: 'cloud', label: 'Cloud' },
	{ key: 'snowflake', label: 'Winter' },
	{ key: 'umbrella', label: 'Rainy day' },
	{ key: 'mountain', label: 'Outdoors' },

	// Misc
	{ key: 'gift', label: 'Gifts' },
	{ key: 'sparkles', label: 'Special' },
	{ key: 'star', label: 'Favorites' },
	{ key: 'trophy', label: 'Achievement' },
	{ key: 'flag', label: 'Goals' },
	{ key: 'bell', label: 'Reminders' },
	{ key: 'clock', label: 'Subscriptions' },
	{ key: 'calendar', label: 'Recurring' },
	{ key: 'tag', label: 'Tag' },
	{ key: 'package', label: 'Packages' },
	{ key: 'key', label: 'Keys' },
	{ key: 'lock', label: 'Security' },
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

/**
 * Filter category icon options by a free-text query. Matches against label and key
 * (case-insensitive, substring match). Empty query returns the full list.
 */
export function filterCategoryIcons(
	query: string,
): readonly (typeof CATEGORY_ICON_OPTIONS)[number][] {
	const q = query.trim().toLowerCase();
	if (q === '') return CATEGORY_ICON_OPTIONS;
	return CATEGORY_ICON_OPTIONS.filter(
		(opt) => opt.label.toLowerCase().includes(q) || opt.key.toLowerCase().includes(q),
	);
}

import { UNCATEGORIZED_ID, type Category, type Expense } from '$lib/types';
import { colorForCategoryId, UNCATEGORIZED_COLOR } from '$lib/utils/categoryColor';

type CategorySeed = {
	id: string;
	name: string;
	icon: string;
};

type ExpenseSeed = {
	id: `exp-${string}`;
	name: string;
	amount: number;
	categoryId: string;
	note: string;
	monthsAgo: number;
	day: number;
};

const CATEGORY_SEEDS: readonly CategorySeed[] = [
	{ id: UNCATEGORIZED_ID, name: 'Uncategorized', icon: 'circle-help' },
	{ id: 'cat-groceries', name: 'Groceries', icon: 'shopping-cart' },
	{ id: 'cat-transport', name: 'Transport', icon: 'train-front' },
	{ id: 'cat-housing', name: 'Housing', icon: 'house' },
	{ id: 'cat-dining', name: 'Dining Out', icon: 'utensils' },
	{ id: 'cat-bills', name: 'Bills', icon: 'receipt' },
];

const EXPENSE_SEEDS: readonly ExpenseSeed[] = [
	{ id: 'exp-001', name: 'Whole Foods', amount: 58.24, categoryId: 'cat-groceries', note: 'Weekly groceries', monthsAgo: 0, day: 3 },
	{ id: 'exp-002', name: 'Transport for London', amount: 14.5, categoryId: 'cat-transport', note: 'Bus fare', monthsAgo: 0, day: 7 },
	{ id: 'exp-003', name: 'Starbucks', amount: 42.8, categoryId: 'cat-dining', note: 'Coffee and lunch', monthsAgo: 1, day: 11 },
	{ id: 'exp-004', name: 'Greystar Rent', amount: 1200, categoryId: 'cat-housing', note: '', monthsAgo: 1, day: 1 },
	{ id: 'exp-005', name: 'Comcast Xfinity', amount: 96.12, categoryId: 'cat-bills', note: 'Internet bill', monthsAgo: 2, day: 5 },
	{ id: 'exp-006', name: 'Trader Joe’s', amount: 33.75, categoryId: 'cat-groceries', note: 'Pantry restock', monthsAgo: 2, day: 13 },
	{ id: 'exp-007', name: 'Uber', amount: 22, categoryId: 'cat-transport', note: 'Rideshare', monthsAgo: 3, day: 9 },
	{ id: 'exp-008', name: 'Deliveroo', amount: 68.4, categoryId: 'cat-dining', note: 'Dinner out', monthsAgo: 3, day: 19 },
	{ id: 'exp-009', name: 'Sainsbury’s', amount: 48.9, categoryId: 'cat-groceries', note: 'Farmers market', monthsAgo: 4, day: 6 },
	{ id: 'exp-010', name: 'Pacific Gas & Electric', amount: 74.3, categoryId: 'cat-bills', note: 'Electricity', monthsAgo: 4, day: 16 },
	{ id: 'exp-011', name: 'NCP Parking', amount: 15.2, categoryId: 'cat-transport', note: 'Parking', monthsAgo: 5, day: 4 },
	{ id: 'exp-012', name: 'Chipotle', amount: 89.95, categoryId: 'cat-dining', note: 'Team lunch', monthsAgo: 5, day: 10 },
	{ id: 'exp-013', name: 'Amazon Prime', amount: 27.6, categoryId: 'cat-groceries', note: 'Snacks', monthsAgo: 0, day: 21 },
	{ id: 'exp-014', name: 'Thames Water', amount: 110.4, categoryId: 'cat-bills', note: 'Water bill', monthsAgo: 2, day: 24 },
	{ id: 'exp-015', name: 'IKEA', amount: 210.85, categoryId: 'cat-housing', note: 'Maintenance supplies', monthsAgo: 3, day: 27 },
	{ id: 'exp-016', name: 'Patreon', amount: 12, categoryId: UNCATEGORIZED_ID, note: 'Monthly membership', monthsAgo: 1, day: 14 },
	{ id: 'exp-017', name: 'Netflix', amount: 17.99, categoryId: 'cat-bills', note: 'Streaming', monthsAgo: 0, day: 18 },
];

function pad(value: number): string {
	return String(value).padStart(2, '0');
}

function isoDateForMonthsAgo(reference: Date, monthsAgo: number, day: number): string {
	const date = new Date(reference.getFullYear(), reference.getMonth() - monthsAgo, day);
	return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

export function defaultCategories(): Category[] {
	return CATEGORY_SEEDS.map((seed) => ({
		id: seed.id,
		name: seed.name,
		color: seed.id === UNCATEGORIZED_ID ? UNCATEGORIZED_COLOR : colorForCategoryId(seed.id),
		icon: seed.icon,
	}));
}

export function sampleExpenses(): Expense[] {
	const reference = new Date();
	return EXPENSE_SEEDS.map((seed) => ({
		id: seed.id,
		name: seed.name,
		amount: seed.amount,
		date: isoDateForMonthsAgo(reference, seed.monthsAgo, seed.day),
		categoryId: seed.categoryId,
		note: seed.note,
	}));
}

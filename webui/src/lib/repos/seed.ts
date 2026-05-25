import { UNCATEGORIZED_ID, type Category, type Expense } from '$lib/types';
import { colorForCategoryId, UNCATEGORIZED_COLOR } from '$lib/utils/categoryColor';

type CategorySeed = {
	id: string;
	name: string;
	icon: string;
	description?: string;
};

type ExpenseSeed = {
	id: `exp-${string}`;
	name: string;
	amount: number;
	categoryId: string;
	note: string;
	importance?: Expense['importance'];
	monthsAgo: number;
	day: number;
};

const CATEGORY_SEEDS: readonly CategorySeed[] = [
	{
		id: UNCATEGORIZED_ID,
		name: 'Uncategorized',
		icon: 'circle-help',
		description: 'Transactions that have not been assigned to any category yet.',
	},
	{
		id: 'cat-housing',
		name: 'Housing',
		icon: 'house',
		description:
			'Home-related expenses and utilities: rent, mortgage, electricity, water, gas, internet, maintenance, furniture, and household items.',
	},
	{
		id: 'cat-groceries',
		name: 'Groceries',
		icon: 'shopping-cart',
		description:
			'Food and household consumables bought for home use, including supermarkets, baby food, cleaning supplies, and toiletries bought with groceries. Do not use for restaurants, cafes, or delivery.',
	},
	{
		id: 'cat-health',
		name: 'Health',
		icon: 'heart-pulse',
		description:
			'Medical and healthcare spending: pharmacy, doctor, dental, vitamins, supplements, tests, and health-related products.',
	},
	{
		id: 'cat-childcare',
		name: 'Childcare',
		icon: 'baby',
		description:
			'Direct child care costs: nursery, kindergarten, nanny, babysitter, child activities, and school-related care. Do not use for toys, clothes, or baby food.',
	},
	{
		id: 'cat-car',
		name: 'Car',
		icon: 'car',
		description:
			'Car ownership and maintenance: fuel, insurance, parking, repairs, car wash, registration, and vehicle taxes.',
	},
	{
		id: 'cat-public-transport',
		name: 'Public Transport',
		icon: 'train-front',
		description:
			'Daily non-taxi transport: bus, metro, train, tram, and similar public transit fares.',
	},
	{
		id: 'cat-eating-out',
		name: 'Eating Out',
		icon: 'utensils',
		description:
			'Food and drinks bought outside the home: restaurants, cafes, coffee shops, food delivery, fast food, and outside snacks.',
	},
	{
		id: 'cat-taxi',
		name: 'Taxi',
		icon: 'car-taxi-front',
		description:
			'Taxi and ride-sharing convenience transport, including Uber, Bolt, local taxis, and similar services.',
	},
	{
		id: 'cat-shopping',
		name: 'Shopping',
		icon: 'shopping-bag',
		description:
			'General personal and household shopping: clothes, shoes, cosmetics, toys, small household purchases, and non-essential purchases. Do not use for technology purchases.',
	},
	{
		id: 'cat-technology-gadgets',
		name: 'Technology & Gadgets',
		icon: 'smartphone',
		description:
			'Technology purchases and accessories: phones, laptops, tablets, smart watches, smart home devices, headphones, and computer accessories.',
	},
	{
		id: 'cat-sports-fitness',
		name: 'Sports & Fitness',
		icon: 'dumbbell',
		description:
			'Fitness and sports spending: gym memberships, fitness classes, sporting equipment, running shoes, sports clubs, and fitness apps.',
	},
	{
		id: 'cat-entertainment-leisure',
		name: 'Entertainment & Leisure',
		icon: 'ticket',
		description:
			'Entertainment, hobbies, and leisure: cinema, concerts, video games, books, hobbies, events, and recreational activities. Do not use for recurring subscriptions.',
	},
	{
		id: 'cat-subscriptions',
		name: 'Subscriptions',
		icon: 'repeat',
		description:
			'Recurring digital or membership payments only: Netflix, Spotify, iCloud, YouTube Premium, software subscriptions, and Amazon Prime.',
	},
	{
		id: 'cat-travel',
		name: 'Travel',
		icon: 'plane',
		description:
			'Non-daily travel and vacation costs: flights, hotels, vacation transportation, travel activities, and travel bookings.',
	},
	{
		id: 'cat-gifts',
		name: 'Gifts',
		icon: 'gift',
		description:
			'Gifts and celebrations: birthday gifts, holiday gifts, flowers, celebration expenses, and special occasions.',
	},
];

const EXPENSE_SEEDS: readonly ExpenseSeed[] = [
	{ id: 'exp-001', name: 'Whole Foods', amount: 58.24, categoryId: 'cat-groceries', note: 'Weekly groceries', monthsAgo: 0, day: 3 },
	{ id: 'exp-002', name: 'Transport for London', amount: 14.5, categoryId: 'cat-public-transport', note: 'Bus fare', monthsAgo: 0, day: 7 },
	{ id: 'exp-003', name: 'Starbucks', amount: 42.8, categoryId: 'cat-eating-out', note: 'Coffee and lunch', monthsAgo: 1, day: 11 },
	{ id: 'exp-004', name: 'Greystar Rent', amount: 1200, categoryId: 'cat-housing', note: '', monthsAgo: 1, day: 1 },
	{ id: 'exp-005', name: 'Comcast Xfinity', amount: 96.12, categoryId: 'cat-housing', note: 'Internet bill', monthsAgo: 2, day: 5 },
	{ id: 'exp-006', name: 'Trader Joe’s', amount: 33.75, categoryId: 'cat-groceries', note: 'Pantry restock', monthsAgo: 2, day: 13 },
	{ id: 'exp-007', name: 'Uber', amount: 22, categoryId: 'cat-taxi', note: 'Rideshare', monthsAgo: 3, day: 9 },
	{ id: 'exp-008', name: 'Deliveroo', amount: 68.4, categoryId: 'cat-eating-out', note: 'Dinner out', monthsAgo: 3, day: 19 },
	{ id: 'exp-009', name: 'Sainsbury’s', amount: 48.9, categoryId: 'cat-groceries', note: 'Farmers market', monthsAgo: 4, day: 6 },
	{ id: 'exp-010', name: 'Pacific Gas & Electric', amount: 74.3, categoryId: 'cat-housing', note: 'Electricity', monthsAgo: 4, day: 16 },
	{ id: 'exp-011', name: 'NCP Parking', amount: 15.2, categoryId: 'cat-car', note: 'Parking', monthsAgo: 5, day: 4 },
	{ id: 'exp-012', name: 'Chipotle', amount: 89.95, categoryId: 'cat-eating-out', note: 'Team lunch', monthsAgo: 5, day: 10 },
	{ id: 'exp-013', name: 'Amazon Prime', amount: 27.6, categoryId: 'cat-groceries', note: 'Snacks', monthsAgo: 0, day: 21 },
	{ id: 'exp-014', name: 'Thames Water', amount: 110.4, categoryId: 'cat-housing', note: 'Water bill', monthsAgo: 2, day: 24 },
	{ id: 'exp-015', name: 'IKEA', amount: 210.85, categoryId: 'cat-housing', note: 'Maintenance supplies', monthsAgo: 3, day: 27 },
	{ id: 'exp-016', name: 'Patreon', amount: 12, categoryId: UNCATEGORIZED_ID, note: 'Monthly membership', monthsAgo: 1, day: 14 },
	{ id: 'exp-017', name: 'Netflix', amount: 17.99, categoryId: 'cat-subscriptions', note: 'Streaming', monthsAgo: 0, day: 18 },
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
		description: seed.description,
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
		importance: seed.importance ?? 'important',
	}));
}

import type { Expense, Category } from '../../webui/src/lib/types';
import { UNCATEGORIZED_ID } from '../../webui/src/lib/types';

const expense: Expense = {
	id: 'x',
	amount: 1,
	date: '2026-01-01',
	categoryId: UNCATEGORIZED_ID,
	note: ''
};

const category: Category = {
	id: 'c1',
	name: 'Food',
	color: '#000000'
};

console.log(expense, category, UNCATEGORIZED_ID);

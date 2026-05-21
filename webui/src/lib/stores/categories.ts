import { writable } from 'svelte/store';
import { categoryRepository } from '$lib/repos/mockCategoryRepository.js';
import type { Category } from '$lib/types';
import { refreshExpenses } from './expenses.js';

export const categories = writable<Category[]>([]);

export async function refreshCategories(): Promise<void> {
	const rows = await categoryRepository.list();
	categories.set(rows);
}

type CategoryCreateInput = Parameters<typeof categoryRepository.create>[0];
type CategoryUpdatePatch = Parameters<typeof categoryRepository.update>[1];

export async function addCategory(input: CategoryCreateInput): Promise<void> {
	await categoryRepository.create(input);
	await refreshCategories();
}

export async function editCategory(id: string, patch: CategoryUpdatePatch): Promise<void> {
	await categoryRepository.update(id, patch);
	await refreshCategories();
}

export async function deleteCategoryWithCascade(id: string): Promise<void> {
	await categoryRepository.delete(id);
	await refreshCategories();
	await refreshExpenses();
}

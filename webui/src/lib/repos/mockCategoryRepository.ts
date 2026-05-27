import type { Category } from '$lib/types';
import { UNCATEGORIZED_ID } from '$lib/types';
import { colorForCategoryId } from '$lib/utils/categoryColor';
import { normalizeCategoryIcon } from '$lib/utils/categoryIcons';
import { getStore, setStore } from './mockStore.js';
import { RepositoryError, type CategoryRepository } from './types.js';

export class MockCategoryRepository implements CategoryRepository {
	async list(): Promise<Category[]> {
		return getStore().categories;
	}

	async create(input: Omit<Category, 'id'>): Promise<Category> {
		const name = input.name.trim();
		if (name === '') {
			throw new RepositoryError('VALIDATION', 'Category name cannot be blank.');
		}

		const nameLower = name.toLowerCase();
		const store = getStore();
		const duplicate = store.categories.find(
			(c) => c.name.trim().toLowerCase() === nameLower
		);
		if (duplicate) {
			throw new RepositoryError('VALIDATION', `A category named "${name}" already exists.`);
		}

		const id = `cat-${crypto.randomUUID()}`;
		const color = input.color || colorForCategoryId(id);
		const icon = normalizeCategoryIcon(input.icon);

		const newState = setStore((s) => {
			s.categories.push({ id, name, color, icon, description: input.description ?? '' });
		});

		const created = newState.categories.find((c) => c.id === id);
		if (!created) {
			throw new RepositoryError('NOT_FOUND', `Category "${id}" was not stored correctly.`);
		}
		return created;
	}

	async update(id: string, patch: Partial<Omit<Category, 'id'>>): Promise<Category> {
		const store = getStore();
		const existing = store.categories.find((c) => c.id === id);
		if (!existing) {
			throw new RepositoryError('NOT_FOUND', `Category "${id}" not found.`);
		}

		if (
			id === UNCATEGORIZED_ID &&
			patch.name !== undefined &&
			patch.name.trim() !== existing.name.trim()
		) {
			throw new RepositoryError('IMMUTABLE', 'The Uncategorized category name cannot be changed.');
		}

		const newState = setStore((s) => {
			const idx = s.categories.findIndex((c) => c.id === id);
			if (idx === -1) {
				throw new RepositoryError('NOT_FOUND', `Category "${id}" not found.`);
			}

			if (patch.name !== undefined) {
				const newName = patch.name.trim();
				const nameLower = newName.toLowerCase();
				const duplicate = s.categories.find(
					(c) => c.id !== id && c.name.trim().toLowerCase() === nameLower
				);
				if (duplicate) {
					throw new RepositoryError('VALIDATION', `A category named "${newName}" already exists.`);
				}
				s.categories[idx].name = newName;
			}

			if (patch.color !== undefined) {
				s.categories[idx].color = patch.color;
			}

			if (patch.icon !== undefined) {
				s.categories[idx].icon = normalizeCategoryIcon(patch.icon);
			}

			if (patch.description !== undefined) {
				s.categories[idx].description = patch.description;
			}
		});

		const updated = newState.categories.find((c) => c.id === id);
		if (!updated) {
			throw new RepositoryError('NOT_FOUND', `Category "${id}" not found.`);
		}
		return updated;
	}

	async delete(id: string): Promise<void> {
		if (id === UNCATEGORIZED_ID) {
			throw new RepositoryError('IMMUTABLE', 'The Uncategorized category cannot be deleted.');
		}

		const store = getStore();
		const existing = store.categories.find((c) => c.id === id);
		if (!existing) {
			throw new RepositoryError('NOT_FOUND', `Category "${id}" not found.`);
		}

		setStore((s) => {
			s.categories = s.categories.filter((c) => c.id !== id);
			for (const expense of s.expenses) {
				if (expense.categoryId === id) {
					expense.categoryId = UNCATEGORIZED_ID;
				}
			}
		});
	}
}

export const categoryRepository: CategoryRepository = new MockCategoryRepository();

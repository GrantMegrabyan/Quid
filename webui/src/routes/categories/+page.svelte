<script lang="ts">
	import { onMount } from 'svelte';
	import CategoryIcon from '$components/CategoryIcon.svelte';
	import IconPicker from '$components/IconPicker.svelte';
	import {
		categories,
		refreshCategories,
		addCategory,
		editCategory,
		deleteCategoryWithCascade
	} from '$lib/stores/categories';
	import { expenses, refreshExpenses } from '$lib/stores/expenses';
	import { UNCATEGORIZED_ID } from '$lib/types';
	import { colorForCategoryId, UNCATEGORIZED_COLOR } from '$lib/utils/categoryColor';
	import { FALLBACK_CATEGORY_ICON, normalizeCategoryIcon } from '$utils/categoryIcons';
	import type { Category } from '$lib/types';

	const NAME_MAX = 50;
	const CASCADE_NOTICE_MS = 5000;
	const FALLBACK_COLOR = '#6b7280';

	let showAddForm = $state(false);
	let newName = $state('');
	let newColor = $state(FALLBACK_COLOR);
	let newIcon = $state(FALLBACK_CATEGORY_ICON);
	let newError = $state('');
	let newDescription = $state('');
	let submittingNew = $state(false);

	function openAddForm(): void {
		showAddForm = true;
		newError = '';
	}

	function closeAddForm(): void {
		showAddForm = false;
		newName = '';
		newIcon = FALLBACK_CATEGORY_ICON;
		newDescription = '';
		newError = '';
		newColor = pickRandomDefaultColor();
	}

	let editingId: string | null = $state(null);
	let editName = $state('');
	let editColor = $state('');
	let editIcon = $state(FALLBACK_CATEGORY_ICON);
	let editError = $state('');
	let editDescription = $state('');
	let savingEdit = $state(false);

	let confirmingDeleteId: string | null = $state(null);
	let deleting = $state(false);

	let cascadeMessage = $state('');
	let cascadeTimer: ReturnType<typeof setTimeout> | null = null;

	function pickRandomDefaultColor(): string {
		if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
			return colorForCategoryId(crypto.randomUUID());
		}
		return FALLBACK_COLOR;
	}

	function nameAvailable(name: string, exceptId: string | null = null): boolean {
		const lower = name.trim().toLowerCase();
		for (const cat of $categories) {
			if (cat.id === exceptId) continue;
			if (cat.name.trim().toLowerCase() === lower) {
				return false;
			}
		}
		return true;
	}

	function validateName(name: string, exceptId: string | null = null): string {
		const trimmed = name.trim();
		if (trimmed === '') {
			return 'Name is required.';
		}
		if (trimmed.length > NAME_MAX) {
			return `Name must be ${NAME_MAX} characters or fewer.`;
		}
		if (!nameAvailable(trimmed, exceptId)) {
			return `A category named "${trimmed}" already exists.`;
		}
		return '';
	}

	function showCascadeNotice(count: number): void {
		const noun = count === 1 ? 'expense' : 'expenses';
		cascadeMessage = `${count} ${noun} moved to Uncategorized`;
		if (cascadeTimer !== null) {
			clearTimeout(cascadeTimer);
		}
		cascadeTimer = setTimeout(() => {
			cascadeMessage = '';
			cascadeTimer = null;
		}, CASCADE_NOTICE_MS);
	}

	async function handleAdd(event: SubmitEvent): Promise<void> {
		event.preventDefault();
		if (submittingNew) return;

		const err = validateName(newName);
		if (err) {
			newError = err;
			return;
		}

		submittingNew = true;
		newError = '';
		try {
			await addCategory({ name: newName.trim(), color: newColor, icon: newIcon, description: newDescription.replace(/\s+/g, ' ').trim() });
			newName = '';
			newColor = pickRandomDefaultColor();
			newIcon = FALLBACK_CATEGORY_ICON;
			newDescription = '';
			showAddForm = false;
		} catch (error) {
			newError = error instanceof Error ? error.message : 'Could not add category.';
		} finally {
			submittingNew = false;
		}
	}

	function startEdit(cat: Category): void {
		editingId = cat.id;
		editName = cat.name;
		editColor = cat.color || (cat.id === UNCATEGORIZED_ID ? UNCATEGORIZED_COLOR : FALLBACK_COLOR);
		editIcon = normalizeCategoryIcon(cat.icon);
		editDescription = cat.description ?? '';
		editError = '';
		confirmingDeleteId = null;
	}

	function cancelEdit(): void {
		editingId = null;
		editName = '';
		editColor = '';
		editIcon = FALLBACK_CATEGORY_ICON;
		editDescription = '';
		editError = '';
	}

	async function saveEdit(id: string): Promise<void> {
		if (savingEdit) return;
		const original = $categories.find((c) => c.id === id);
		if (!original) {
			cancelEdit();
			return;
		}

		const trimmed = editName.trim();
		if (id === UNCATEGORIZED_ID) {
			if (trimmed !== original.name.trim()) {
				editError = 'The Uncategorized name cannot be changed.';
				return;
			}
		} else {
			const err = validateName(editName, id);
			if (err) {
				editError = err;
				return;
			}
		}

		savingEdit = true;
		editError = '';
		try {
			const patch: Partial<Omit<Category, 'id'>> = {
				color: editColor,
				icon: editIcon,
				description: editDescription.replace(/\s+/g, ' ').trim()
			};
			if (id !== UNCATEGORIZED_ID) {
				patch.name = trimmed;
			}
			await editCategory(id, patch);
			cancelEdit();
		} catch (error) {
			editError = error instanceof Error ? error.message : 'Could not save category.';
		} finally {
			savingEdit = false;
		}
	}

	function requestDelete(id: string): void {
		if (id === UNCATEGORIZED_ID) return;
		confirmingDeleteId = id;
		if (editingId === id) {
			cancelEdit();
		}
	}

	function cancelDelete(): void {
		confirmingDeleteId = null;
	}

	async function confirmDelete(id: string): Promise<void> {
		if (deleting || id === UNCATEGORIZED_ID) return;
		const affected = $expenses.filter((e) => e.categoryId === id).length;
		deleting = true;
		try {
			await deleteCategoryWithCascade(id);
			confirmingDeleteId = null;
			showCascadeNotice(affected);
		} finally {
			deleting = false;
		}
	}

	onMount(() => {
		newColor = pickRandomDefaultColor();
		void refreshCategories();
		void refreshExpenses();

		return () => {
			if (cascadeTimer !== null) {
				clearTimeout(cascadeTimer);
				cascadeTimer = null;
			}
		};
	});
</script>

<svelte:head>
	<title>Categories</title>
</svelte:head>

<section class="flex flex-col gap-6">
	<header class="flex flex-wrap items-start justify-between gap-3">
		<div class="flex flex-col gap-1">
			<h1 class="text-2xl font-semibold tracking-tight text-ctp-text">
				Categories
			</h1>
			<p class="text-sm text-ctp-overlay1">
				Add, rename, recolor, choose an icon. Deleting a category moves its expenses to Uncategorized.
			</p>
		</div>
		{#if !showAddForm}
			<button
				type="button"
				data-testid="show-new-category-form"
				onclick={openAddForm}
				class="inline-flex items-center justify-center rounded-md bg-ctp-accent px-4 py-2 text-sm font-medium text-ctp-on-accent transition-colors hover:bg-ctp-accent-hover"
			>
				+ Add category
			</button>
		{/if}
	</header>

	{#if showAddForm}
	<form
		onsubmit={handleAdd}
		novalidate
		class="flex flex-col gap-3 rounded-lg border border-ctp-surface1 bg-ctp-base p-4 sm:p-5"
	>
		<div class="flex flex-col gap-3 sm:flex-row sm:items-stretch">
			<div class="flex flex-col gap-1 sm:w-80">
				<label
					for="new-category-icon"
					class="text-sm font-medium text-ctp-subtext0"
				>
					Icon
				</label>
				<div class="flex items-start gap-2">
					<span
						data-testid="new-category-icon-preview"
						data-icon={newIcon}
						class="flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-ctp-accent text-ctp-on-accent"
					>
						<CategoryIcon name={newIcon} />
					</span>
					<div class="min-w-0 flex-1" data-testid="new-category-icon">
						<IconPicker
							id="new-category-icon"
							value={newIcon}
							onselect={(key) => (newIcon = key)}
						/>
					</div>
				</div>
			</div>

			<div class="flex min-w-0 flex-1 flex-col gap-3">
				<div class="flex flex-col gap-1">
					<label
						for="new-category-name"
						class="text-sm font-medium text-ctp-subtext0"
					>
						Name
					</label>
					<input
						id="new-category-name"
						data-testid="new-category-name"
						type="text"
						maxlength={NAME_MAX}
						autocomplete="off"
						placeholder="e.g. Coffee"
						bind:value={newName}
						oninput={() => (newError = '')}
						class="w-full rounded-md border border-ctp-surface2 bg-ctp-base px-3 py-2 text-sm text-ctp-text placeholder:text-ctp-overlay0 focus:border-ctp-accent focus:outline-none"
					/>
				</div>

				<div class="flex min-h-0 flex-1 flex-col gap-1">
					<label
						for="new-category-description"
						class="text-sm font-medium text-ctp-subtext0"
					>
						Description
					</label>
					<textarea
						id="new-category-description"
						data-testid="new-category-description"
						name="description"
						maxlength="1000"
						placeholder="e.g. Daily food shopping. Excludes restaurants."
						bind:value={newDescription}
						class="min-h-[80px] w-full flex-1 rounded-md border border-ctp-surface2 bg-ctp-base px-3 py-2 text-sm text-ctp-text placeholder:text-ctp-overlay0 focus:border-ctp-accent focus:outline-none resize-none"
					></textarea>
					<p class="text-xs text-ctp-subtext0">Used by AI when categorising transactions. Describe what belongs here and what doesn't.</p>
				</div>
			</div>

			<div class="flex flex-col gap-1">
				<label
					for="new-category-color"
					class="text-sm font-medium text-ctp-subtext0"
				>
					Color
				</label>
				<input
					id="new-category-color"
					data-testid="new-category-color"
					type="color"
					bind:value={newColor}
					class="h-10 w-14 cursor-pointer rounded-md border border-ctp-surface2 bg-ctp-base p-1"
				/>
			</div>

			<div class="flex flex-wrap items-center gap-2 sm:self-start">
				<button
					type="submit"
					data-testid="new-category-submit"
					disabled={submittingNew}
					class="inline-flex items-center justify-center rounded-md bg-ctp-accent px-4 py-2 text-sm font-medium text-ctp-on-accent transition-colors hover:bg-ctp-accent-hover disabled:opacity-60"
				>
					Add category
				</button>
				<button
					type="button"
					data-testid="new-category-cancel"
					onclick={closeAddForm}
					class="inline-flex items-center justify-center rounded-md border border-ctp-surface2 bg-ctp-base px-4 py-2 text-sm font-medium text-ctp-subtext0 transition-colors hover:bg-ctp-surface1"
				>
					Cancel
				</button>
			</div>
		</div>

		{#if newError}
			<p
				data-testid="new-category-error"
				class="text-sm text-red-600 dark:text-red-400"
			>
				{newError}
			</p>
		{/if}
	</form>
	{/if}

	{#if cascadeMessage}
		<div
			data-testid="cascade-notice"
			role="status"
			aria-live="polite"
			class="rounded-md border border-amber-200 bg-amber-50 px-4 py-2 text-sm text-amber-900 dark:border-amber-900/60 dark:bg-amber-950/40 dark:text-amber-200"
		>
			{cascadeMessage}
		</div>
	{/if}

	<ul
		class="divide-y divide-ctp-surface1 overflow-hidden rounded-lg border border-ctp-surface1"
	>
		{#each $categories as category (category.id)}
			{@const isUncategorized = category.id === UNCATEGORIZED_ID}
			{@const isEditing = editingId === category.id}
			{@const isConfirmingDelete = confirmingDeleteId === category.id}
			<li
				data-testid="category-row"
				data-category-id={category.id}
				class="flex flex-col gap-3 bg-ctp-base px-4 py-3 sm:px-5"
			>
				<div
					data-testid={isUncategorized ? 'category-uncategorized' : undefined}
					class="flex flex-wrap items-center gap-x-4 gap-y-2 sm:flex-nowrap"
				>
					<div class="flex min-w-0 flex-1 items-center gap-3">
						<span
							aria-hidden="true"
							data-testid="category-icon"
							data-icon={normalizeCategoryIcon(category.icon)}
							class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-white ring-1 ring-black/5"
							style="background-color: {category.color || FALLBACK_COLOR};"
						><CategoryIcon name={category.icon} size={16} /></span>
						<div class="min-w-0 flex-1">
							<p
								class="truncate text-sm font-medium text-ctp-text"
							>
								{category.name}
							</p>
							{#if isUncategorized}
								<p class="text-xs text-ctp-overlay1">
									Default fallback · cannot be deleted
								</p>
							{/if}
						</div>
					</div>

					{#if isConfirmingDelete}
						<div class="ml-auto flex items-center gap-1.5">
							<button
								type="button"
								data-testid="category-delete-confirm-btn"
								disabled={deleting}
								onclick={() => confirmDelete(category.id)}
								class="rounded-md bg-red-600 px-2.5 py-1 text-xs font-medium text-white transition-colors hover:bg-red-700 disabled:opacity-60"
							>
								Delete
							</button>
							<button
								type="button"
								data-testid="category-delete-cancel-btn"
								onclick={cancelDelete}
								class="rounded-md border border-ctp-surface1 px-2.5 py-1 text-xs font-medium text-ctp-subtext0 transition-colors hover:bg-ctp-surface1"
							>
								Cancel
							</button>
						</div>
					{:else if !isEditing}
						<div class="ml-auto flex items-center gap-1">
							<button
								type="button"
								data-testid="category-edit-btn"
								aria-label={`Edit ${category.name}`}
								onclick={() => startEdit(category)}
								class="inline-flex h-8 w-8 items-center justify-center rounded-md text-base text-ctp-overlay1 transition-colors hover:bg-ctp-surface1 hover:text-ctp-text"
							>
								✎
							</button>
							{#if !isUncategorized}
								<button
									type="button"
									data-testid="category-delete-btn"
									aria-label={`Delete ${category.name}`}
									onclick={() => requestDelete(category.id)}
									class="inline-flex h-8 w-8 items-center justify-center rounded-md text-base text-ctp-overlay1 transition-colors hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-950/40 dark:hover:text-red-400"
								>
									🗑
								</button>
							{/if}
						</div>
					{/if}
				</div>

				{#if isEditing}
					<div class="flex flex-col gap-2 rounded-md border border-ctp-surface1 bg-ctp-surface0 p-3">
						<div class="flex flex-col gap-2 sm:flex-row sm:items-stretch">
							<div class="flex flex-col gap-1 sm:w-72">
								<label
									for={`edit-icon-${category.id}`}
									class="text-xs font-medium text-ctp-subtext0"
								>
									Icon
								</label>
								<div class="flex items-start gap-2">
									<span class="flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-ctp-accent text-ctp-on-accent">
										<CategoryIcon name={editIcon} />
									</span>
									<div class="min-w-0 flex-1" data-testid="category-edit-icon">
										<IconPicker
											id={`edit-icon-${category.id}`}
											value={editIcon}
											onselect={(key) => (editIcon = key)}
										/>
									</div>
								</div>
							</div>

							<div class="flex min-w-0 flex-1 flex-col gap-2">
								<div class="flex flex-col gap-1">
									<label
										for={`edit-name-${category.id}`}
										class="text-xs font-medium text-ctp-subtext0"
									>
										Name
									</label>
									<input
										id={`edit-name-${category.id}`}
										data-testid="category-edit-name"
										type="text"
										maxlength={NAME_MAX}
										autocomplete="off"
										disabled={isUncategorized}
										bind:value={editName}
										oninput={() => (editError = '')}
										class="w-full rounded-md border border-ctp-surface2 bg-ctp-base px-3 py-2 text-sm text-ctp-text focus:border-ctp-accent focus:outline-none disabled:cursor-not-allowed disabled:bg-ctp-surface0 disabled:text-ctp-overlay1"
									/>
								</div>

								<div class="flex min-h-0 flex-1 flex-col gap-1">
									<label
										for={`edit-description-${category.id}`}
										class="text-xs font-medium text-ctp-subtext0"
									>
										Description
									</label>
									<textarea
										id={`edit-description-${category.id}`}
										data-testid="category-edit-description"
										name="description"
										maxlength="1000"
										placeholder="e.g. Daily food shopping. Excludes restaurants."
										bind:value={editDescription}
										class="min-h-[80px] w-full flex-1 rounded-md border border-ctp-surface2 bg-ctp-base px-3 py-2 text-sm text-ctp-text placeholder:text-ctp-overlay0 focus:border-ctp-accent focus:outline-none resize-none"
									></textarea>
									<p class="text-xs text-ctp-subtext0">Used by AI when categorising transactions. Describe what belongs here and what doesn't.</p>
								</div>
							</div>

							<div class="flex flex-col gap-1">
								<label
									for={`edit-color-${category.id}`}
									class="text-xs font-medium text-ctp-subtext0"
								>
									Color
								</label>
								<input
									id={`edit-color-${category.id}`}
									data-testid="category-edit-color"
									type="color"
									bind:value={editColor}
									class="h-10 w-14 cursor-pointer rounded-md border border-ctp-surface2 bg-ctp-base p-1"
								/>
							</div>

							<div class="flex items-center gap-1.5 sm:self-start">
								<button
									type="button"
									data-testid="category-edit-save-btn"
									disabled={savingEdit}
									onclick={() => saveEdit(category.id)}
									class="rounded-md bg-ctp-accent px-3 py-1.5 text-xs font-medium text-ctp-on-accent transition-colors hover:bg-ctp-accent-hover disabled:opacity-60"
								>
									Save
								</button>
								<button
									type="button"
									data-testid="category-edit-cancel-btn"
									onclick={cancelEdit}
									class="rounded-md border border-ctp-surface1 px-3 py-1.5 text-xs font-medium text-ctp-subtext0 transition-colors hover:bg-ctp-surface1"
								>
									Cancel
								</button>
							</div>
						</div>
						{#if editError}
							<p
								data-testid="category-edit-error"
								class="text-sm text-red-600 dark:text-red-400"
							>
								{editError}
							</p>
						{/if}
					</div>
				{/if}
			</li>
		{/each}
	</ul>
</section>

<script lang="ts">
	import { onMount, untrack } from 'svelte';
	import { slide } from 'svelte/transition';
	import { flip } from 'svelte/animate';
	import { cubicOut } from 'svelte/easing';
	import CategoryIcon from '$components/CategoryIcon.svelte';
	import TweenedAmount from '$components/TweenedAmount.svelte';
	import { expenses, deleteExpense, refreshExpenses } from '$lib/stores/expenses';
	import { categories, refreshCategories } from '$lib/stores/categories';
	import { selectedMonth } from '$lib/stores/ui';
	import { formatMonthLabel, monthKey } from '$lib/utils/dates';
	import { formatAmount } from '$lib/utils/money';
	import type { Category, Expense, ExpenseImportance } from '$lib/types';

	type EditCallback = (expense: Expense) => void;
	type ExpenseGroupBy = 'transaction' | 'merchant' | 'category' | 'importance';
	type ExpenseGroup = {
		id: string;
		name: string;
		count: number;
		amount: number;
		category?: Category;
		importance?: ExpenseImportance;
	};

	let { groupBy = 'transaction', onedit }: { groupBy?: ExpenseGroupBy; onedit?: EditCallback } =
		$props();

	const DATE_FORMATTER = new Intl.DateTimeFormat('en-US', {
		year: 'numeric',
		month: 'short',
		day: 'numeric'
	});

	const FLIP_DURATION = 280;
	const SLIDE_DURATION = 220;
	const IMPORTANCE_ORDER: ExpenseImportance[] = ['essential', 'important', 'discretionary'];

	let confirmingId: string | null = $state(null);
	let expandedGroups: Set<string> = $state(new Set());

	// Reset expanded groups when groupBy mode changes (IDs no longer comparable).
	let lastGroupBy: ExpenseGroupBy = untrack(() => groupBy);
	$effect(() => {
		if (groupBy !== lastGroupBy) {
			expandedGroups = new Set();
			lastGroupBy = groupBy;
		}
	});

	let categoryById = $derived.by(() => {
		const map = new Map<string, Category>();
		for (const category of $categories) {
			map.set(category.id, category);
		}
		return map;
	});

	const visibleExpenses = $derived(
		$expenses.filter((expense) => monthKey(expense.date) === $selectedMonth)
	);

	function groupIdFor(expense: Expense): string {
		if (groupBy === 'merchant') return expense.name;
		if (groupBy === 'importance') return expense.importance;
		return expense.categoryId;
	}

	function importanceLabel(value: ExpenseImportance): string {
		return value === 'essential' ? 'Essential' : value === 'important' ? 'Important' : 'Discretionary';
	}

	function importanceBadgeClass(value: ExpenseImportance): string {
		if (value === 'essential') return 'bg-emerald-50 text-emerald-700 ring-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-200 dark:ring-emerald-900/70';
		if (value === 'important') return 'bg-blue-50 text-blue-700 ring-blue-200 dark:bg-blue-950/40 dark:text-blue-200 dark:ring-blue-900/70';
		return 'bg-amber-50 text-amber-700 ring-amber-200 dark:bg-amber-950/40 dark:text-amber-200 dark:ring-amber-900/70';
	}

	function importanceColor(value: ExpenseImportance | undefined): string {
		if (value === 'essential') return '#059669';
		if (value === 'discretionary') return '#d97706';
		return '#2563eb';
	}

	const transactionsByGroupId = $derived.by(() => {
		const map = new Map<string, Expense[]>();
		if (groupBy === 'transaction') return map;
		for (const expense of visibleExpenses) {
			const id = groupIdFor(expense);
			const arr = map.get(id);
			if (arr) {
				arr.push(expense);
			} else {
				map.set(id, [expense]);
			}
		}
		for (const arr of map.values()) {
			arr.sort((a, b) => b.date.localeCompare(a.date) || b.amount - a.amount);
		}
		return map;
	});

	const groupedExpenses = $derived.by(() => {
		if (groupBy === 'transaction') return [] as ExpenseGroup[];
		const groups: ExpenseGroup[] = [];
		for (const [id, items] of transactionsByGroupId) {
			const first = items[0];
			const category = categoryById.get(first.categoryId);
			const name = groupBy === 'merchant'
				? (first.displayName ?? first.name)
				: groupBy === 'importance'
					? importanceLabel(first.importance)
					: (category?.name ?? 'Uncategorized');
			let amount = 0;
			for (const item of items) amount += item.amount;
			groups.push({ id, name, count: items.length, amount, category, importance: first.importance });
		}
		if (groupBy === 'importance') {
			return groups.sort((a, b) => IMPORTANCE_ORDER.indexOf(a.importance ?? 'important') - IMPORTANCE_ORDER.indexOf(b.importance ?? 'important'));
		}
		return groups.sort((a, b) => b.amount - a.amount || a.name.localeCompare(b.name));
	});

	// Prune expanded IDs that no longer exist (e.g. group emptied after edits).
	$effect(() => {
		if (expandedGroups.size === 0) return;
		const validIds = new Set(groupedExpenses.map((g) => g.id));
		let changed = false;
		const next = new Set<string>();
		for (const id of expandedGroups) {
			if (validIds.has(id)) {
				next.add(id);
			} else {
				changed = true;
			}
		}
		if (changed) {
			expandedGroups = next;
		}
	});

	const emptyMessage = $derived(`No expenses for ${formatMonthLabel($selectedMonth)}.`);
	const isGrouped = $derived(groupBy !== 'transaction');
	const hasRows = $derived(
		isGrouped ? groupedExpenses.length > 0 : visibleExpenses.length > 0
	);

	function formatDate(iso: string): string {
		const [yearPart, monthPart, dayPart] = iso.split('-');
		const year = Number(yearPart);
		const month = Number(monthPart);
		const day = Number(dayPart);

		if (!Number.isFinite(year) || !Number.isFinite(month) || !Number.isFinite(day)) {
			return iso;
		}

		return DATE_FORMATTER.format(new Date(year, month - 1, day));
	}

	function handleEdit(expense: Expense): void {
		confirmingId = null;
		onedit?.(expense);
	}

	function requestDelete(id: string): void {
		confirmingId = id;
	}

	function cancelDelete(): void {
		confirmingId = null;
	}

	async function confirmDelete(id: string): Promise<void> {
		await deleteExpense(id);
		if (confirmingId === id) {
			confirmingId = null;
		}
	}

	function toggleGroup(id: string): void {
		const next = new Set(expandedGroups);
		if (next.has(id)) {
			next.delete(id);
		} else {
			next.add(id);
		}
		expandedGroups = next;
	}

	onMount(() => {
		void refreshExpenses();
		void refreshCategories();
	});
</script>

{#snippet importanceBadge(value: ExpenseImportance)}
	<span
		data-testid="expense-importance-badge"
		class="inline-flex rounded-full px-2 py-0.5 text-[11px] font-medium ring-1 ring-inset {importanceBadgeClass(value)}"
	>
		{importanceLabel(value)}
	</span>
{/snippet}

{#snippet rowActions(expense: Expense)}
	{@const isConfirming = confirmingId === expense.id}
	{#if isConfirming}
		<div class="flex items-center gap-1.5">
			<button
				type="button"
				data-testid="expense-delete-confirm-btn"
				onclick={(event) => {
					event.stopPropagation();
					void confirmDelete(expense.id);
				}}
				class="rounded-md bg-red-600 px-2.5 py-1 text-xs font-medium text-white transition-colors hover:bg-red-700"
			>
				Delete
			</button>
			<button
				type="button"
				data-testid="expense-delete-cancel-btn"
				onclick={(event) => {
					event.stopPropagation();
					cancelDelete();
				}}
				class="rounded-md border border-gray-200 px-2.5 py-1 text-xs font-medium text-gray-700 transition-colors hover:bg-gray-100 dark:border-gray-700 dark:text-gray-300 dark:hover:bg-gray-800"
			>
				Cancel
			</button>
		</div>
	{:else}
		<div class="flex items-center gap-1">
			<button
				type="button"
				data-testid="expense-edit-btn"
				aria-label="Edit expense"
				onclick={(event) => {
					event.stopPropagation();
					handleEdit(expense);
				}}
				class="inline-flex h-6 w-6 items-center justify-center rounded-md text-xs text-gray-500 transition-colors hover:bg-gray-100 hover:text-gray-900 dark:text-gray-500 dark:hover:bg-gray-800 dark:hover:text-gray-100"
			>
				✎
			</button>
			<button
				type="button"
				data-testid="expense-delete-btn"
				aria-label="Delete expense"
				onclick={(event) => {
					event.stopPropagation();
					requestDelete(expense.id);
				}}
				class="inline-flex h-6 w-6 items-center justify-center rounded-md text-xs text-gray-500 transition-colors hover:bg-red-50 hover:text-red-600 dark:text-gray-500 dark:hover:bg-red-950/40 dark:hover:text-red-400"
			>
				🗑
			</button>
		</div>
	{/if}
{/snippet}

{#if !hasRows}
	<div
		data-testid="empty-state"
		class="flex flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-gray-300 px-6 py-16 text-center dark:border-gray-700"
	>
		<p class="text-base font-medium text-gray-900 dark:text-gray-100">{emptyMessage}</p>
		<p class="text-sm text-gray-500 dark:text-gray-400">
			Click + Add expense to add one for this month.
		</p>
	</div>
{:else}
	<ul
		class="overflow-hidden rounded-lg border border-gray-200 bg-white dark:border-gray-800 dark:bg-[#111114]"
	>
		{#if !isGrouped}
			{#each visibleExpenses as expense (expense.id)}
				{@const category = categoryById.get(expense.categoryId)}
				{@const color = category?.color ?? '#9ca3af'}
				{@const categoryName = category?.name ?? 'Uncategorized'}
				{@const categoryIcon = category?.icon ?? '•'}
				<li
					data-testid="expense-row"
					data-expense-id={expense.id}
					class="flex items-center gap-2.5 border-b border-gray-100 px-3 py-2 last:border-b-0 sm:px-3.5 dark:border-gray-900"
				>
					<div
						data-testid="expense-category-icon"
						data-icon={categoryIcon}
						class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-sm font-semibold text-white shadow-sm sm:h-9 sm:w-9"
						style="background-color: {color};"
						aria-label={categoryName}
					>
						<CategoryIcon name={categoryIcon} size={15} />
					</div>

					<div class="min-w-0 flex-1">
					<p
						class="truncate text-sm font-semibold leading-tight text-gray-900 sm:text-base dark:text-gray-100"
					>
						{expense.displayName ?? expense.name}
					</p>
					<p class="mt-0.5 truncate text-xs text-gray-500 dark:text-gray-400">
						{formatDate(expense.date)}
					</p>
					<div class="mt-1 flex flex-wrap items-center gap-1.5">
						{@render importanceBadge(expense.importance)}
					</div>
					<span class="sr-only">{categoryName}</span>
						{#if expense.note}
							<span class="sr-only">{expense.note}</span>
						{/if}
					</div>

					<div class="ml-auto flex shrink-0 items-center gap-2">
						<span
							class="text-right text-sm font-semibold tabular-nums text-gray-900 sm:text-base dark:text-gray-100"
						>
							{formatAmount(expense.amount)}
						</span>
						{@render rowActions(expense)}
					</div>
				</li>
			{/each}
		{:else}
			{#each groupedExpenses as group (group.id)}
				{@const color = groupBy === 'importance' ? importanceColor(group.importance) : (group.category?.color ?? '#64748b')}
				{@const categoryIcon = groupBy === 'importance' ? 'tag' : (group.category?.icon ?? (groupBy === 'merchant' ? '🏬' : '•'))}
				{@const expanded = expandedGroups.has(group.id)}
				{@const items = transactionsByGroupId.get(group.id) ?? []}
				{@const panelId = `group-panel-${group.id}`}
				<li
					data-testid="expense-row"
					data-group-id={group.id}
					data-group-expanded={expanded}
					class="border-b border-gray-100 last:border-b-0 dark:border-gray-900"
					animate:flip={{ duration: FLIP_DURATION }}
					transition:slide={{ duration: SLIDE_DURATION, easing: cubicOut }}
				>
					<button
						type="button"
						data-testid="expense-group-toggle"
						aria-expanded={expanded}
						aria-controls={panelId}
						onclick={() => toggleGroup(group.id)}
						class="flex w-full items-center gap-2.5 px-3 py-2 text-left transition-colors hover:bg-gray-50 sm:px-3.5 dark:hover:bg-gray-900/60"
					>
						<svg
							class="h-3.5 w-3.5 shrink-0 text-gray-400 transition-transform duration-200 ease-out dark:text-gray-500"
							style:transform={expanded ? 'rotate(90deg)' : 'rotate(0deg)'}
							viewBox="0 0 12 12"
							fill="none"
							aria-hidden="true"
						>
							<path
								d="M4.5 3l3 3-3 3"
								stroke="currentColor"
								stroke-width="1.5"
								stroke-linecap="round"
								stroke-linejoin="round"
							/>
						</svg>

						<div
							data-testid="expense-category-icon"
							class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-sm font-semibold text-white shadow-sm sm:h-9 sm:w-9"
							style="background-color: {color};"
							aria-label={group.name}
						>
							<CategoryIcon name={categoryIcon} size={15} />
						</div>

						<div class="min-w-0 flex-1">
							<p
								class="truncate text-sm font-semibold leading-tight text-gray-900 sm:text-base dark:text-gray-100"
							>
								{group.name}
							</p>
							<p class="mt-0.5 truncate text-xs text-gray-500 dark:text-gray-400">
								{group.count}
								{group.count === 1 ? 'transaction' : 'transactions'}
							</p>
						</div>

						<TweenedAmount
							value={group.amount}
							testid="expense-group-amount"
							class="ml-auto text-right text-sm font-semibold tabular-nums text-gray-900 sm:text-base dark:text-gray-100"
						/>
					</button>

					{#if expanded}
						<div
							id={panelId}
							data-testid="expense-group-panel"
							transition:slide={{ duration: SLIDE_DURATION, easing: cubicOut }}
							class="border-t border-gray-100 bg-gray-50/60 dark:border-gray-900 dark:bg-gray-950/40"
						>
							<ul class="pl-8 sm:pl-10">
								{#each items as expense (expense.id)}
									{@const itemCategory = categoryById.get(expense.categoryId)}
									{@const itemColor = itemCategory?.color ?? '#9ca3af'}
									{@const itemCategoryName = itemCategory?.name ?? 'Uncategorized'}
									{@const itemCategoryIcon = itemCategory?.icon ?? '•'}
									<li
										data-testid="expense-nested-row"
										data-expense-id={expense.id}
										class="flex items-center gap-2.5 border-b border-gray-100 px-3 py-1.5 last:border-b-0 sm:px-3.5 dark:border-gray-900"
										animate:flip={{ duration: FLIP_DURATION }}
										transition:slide={{ duration: SLIDE_DURATION, easing: cubicOut }}
									>
										{#if groupBy === 'merchant'}
											<div
												data-testid="expense-category-icon"
												data-icon={itemCategoryIcon}
												class="flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-[10px] font-semibold text-white shadow-sm"
												style="background-color: {itemColor};"
												aria-label={itemCategoryName}
											>
												<CategoryIcon name={itemCategoryIcon} size={11} />
											</div>
										{/if}

										<div class="min-w-0 flex-1">
										{#if groupBy === 'category' || groupBy === 'importance'}
											<p
												class="truncate text-sm font-medium leading-tight text-gray-900 dark:text-gray-100"
											>
												{expense.displayName ?? expense.name}
											</p>
												<p class="mt-0.5 truncate text-xs text-gray-500 dark:text-gray-400">
													{formatDate(expense.date)}{groupBy === 'importance' ? ` · ${itemCategoryName}` : ''}
												</p>
												{#if groupBy === 'category'}
													<div class="mt-1 flex flex-wrap items-center gap-1.5">
														{@render importanceBadge(expense.importance)}
													</div>
												{/if}
											{:else}
												<p
													class="truncate text-sm font-medium leading-tight text-gray-900 dark:text-gray-100"
												>
													{itemCategoryName}
												</p>
												<p class="mt-0.5 truncate text-xs text-gray-500 dark:text-gray-400">
													{formatDate(expense.date)}
												</p>
												<div class="mt-1 flex flex-wrap items-center gap-1.5">
													{@render importanceBadge(expense.importance)}
												</div>
											{/if}
											{#if expense.note}
												<span class="sr-only">{expense.note}</span>
											{/if}
										</div>

										<div class="ml-auto flex shrink-0 items-center gap-2">
											<span
												class="text-right text-sm font-semibold tabular-nums text-gray-900 dark:text-gray-100"
											>
												{formatAmount(expense.amount)}
											</span>
											{@render rowActions(expense)}
										</div>
									</li>
								{/each}
							</ul>
						</div>
					{/if}
				</li>
			{/each}
		{/if}
	</ul>
{/if}

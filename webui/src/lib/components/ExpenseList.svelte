<script lang="ts">
	import { untrack } from 'svelte';
	import { slide } from 'svelte/transition';
	import { flip } from 'svelte/animate';
	import { cubicOut } from 'svelte/easing';
	import CategoryIcon from '$components/CategoryIcon.svelte';
	import ImportanceBadge from '$components/ImportanceBadge.svelte';
	import TweenedAmount from '$components/TweenedAmount.svelte';
	import { expenses, deleteExpense } from '$lib/stores/expenses';
	import { pendingDeletes, pendingKey, softDelete } from '$lib/stores/toasts';
	import { categories } from '$lib/stores/categories';
	import { settings } from '$lib/stores/settings';
	import { selectedMonth } from '$lib/stores/ui';
	import { formatMonthLabel, monthKey } from '$lib/utils/dates';
	import { amountToNumber, formatAmount } from '$lib/utils/money';
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

	let {
		groupBy = 'transaction',
		searchQuery = '',
		onedit
	}: { groupBy?: ExpenseGroupBy; searchQuery?: string; onedit?: EditCallback } = $props();

	const DATE_FORMATTER = new Intl.DateTimeFormat('en-US', {
		year: 'numeric',
		month: 'short',
		day: 'numeric'
	});
	const DAY_FORMATTER = new Intl.DateTimeFormat('en-US', {
		weekday: 'short',
		month: 'short',
		day: 'numeric'
	});
	const SHORT_DATE_FORMATTER = new Intl.DateTimeFormat('en-US', {
		month: 'short',
		day: 'numeric'
	});

	const FLIP_DURATION = 280;
	const SLIDE_DURATION = 220;
	const IMPORTANCE_ORDER: ExpenseImportance[] = ['essential', 'important', 'discretionary'];

	// Desktop register columns. Flat rows lead with the category icon; grouped
	// child rows lead with the date instead (their day context lives per-row).
	// Both share the remaining columns so amounts/actions align across modes.
	const FLAT_ROW_GRID =
		'grid grid-cols-[2.25rem_minmax(0,1fr)_auto_auto] items-center gap-x-3 lg:grid-cols-[2.25rem_minmax(10rem,1.1fr)_13.5rem_minmax(0,1.4fr)_6.5rem_3.75rem]';
	const CHILD_ROW_GRID =
		'grid grid-cols-[minmax(0,1fr)_auto_auto] items-center gap-x-3 lg:grid-cols-[5rem_minmax(10rem,1.1fr)_13.5rem_minmax(0,1.4fr)_6.5rem_3.75rem]';

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

	// The note shown for a transaction. The server resolves this
	// (`resolvedNote`): the expense's own note, or, for an Amazon-linked
	// transaction without one, the linked order's short name. Falls back to the
	// raw note for mocks/older payloads that predate the field.
	function noteFor(expense: Expense): string {
		return expense.resolvedNote ?? expense.note ?? '';
	}

	const normalizedQuery = $derived(searchQuery.trim().toLowerCase());

	function matchesQuery(expense: Expense): boolean {
		if (!normalizedQuery) return true;
		const haystack =
			`${expense.displayName ?? ''} ${expense.name} ${noteFor(expense)}`.toLowerCase();
		return haystack.includes(normalizedQuery);
	}

	const visibleExpenses = $derived(
		$expenses.filter(
			(expense) =>
				monthKey(expense.date) === $selectedMonth &&
				!$pendingDeletes.has(pendingKey('expense', expense.id)) &&
				matchesQuery(expense)
		)
	);

	const visibleTotal = $derived.by(() => {
		let total = 0;
		for (const expense of visibleExpenses) {
			total += amountToNumber(expense.amount);
		}
		return total;
	});

	type DayGroup = { date: string; items: Expense[]; total: number };

	// Flat view: transactions bucketed per day (store order is date-desc, and
	// Map preserves insertion order, so days come out newest-first).
	const dayGroups = $derived.by(() => {
		if (groupBy !== 'transaction') return [] as DayGroup[];
		const map = new Map<string, DayGroup>();
		for (const expense of visibleExpenses) {
			const date = expense.date.slice(0, 10);
			const group = map.get(date);
			if (group) {
				group.items.push(expense);
				group.total += amountToNumber(expense.amount);
			} else {
				map.set(date, { date, items: [expense], total: amountToNumber(expense.amount) });
			}
		}
		return [...map.values()];
	});

	function groupIdFor(expense: Expense): string {
		if (groupBy === 'merchant') return expense.displayName ?? expense.name;
		if (groupBy === 'importance') return expense.importance;
		return expense.categoryId;
	}

	function importanceLabel(value: ExpenseImportance): string {
		return value === 'essential' ? 'Essential' : value === 'important' ? 'Important' : 'Discretionary';
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
			arr.sort(
				(a, b) =>
					b.date.localeCompare(a.date) || amountToNumber(b.amount) - amountToNumber(a.amount)
			);
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
			for (const item of items) amount += amountToNumber(item.amount);
			groups.push({ id, name, count: items.length, amount, category, importance: first.importance });
		}
		if (groupBy === 'importance') {
			return groups.sort((a, b) => IMPORTANCE_ORDER.indexOf(a.importance ?? 'important') - IMPORTANCE_ORDER.indexOf(b.importance ?? 'important'));
		}
		return groups.sort((a, b) => b.amount - a.amount || a.name.localeCompare(b.name));
	});

	// Group headers carry a share bar sized against the largest group, so the
	// header's middle space shows each group's relative weight in the month.
	const maxGroupAmount = $derived(
		groupedExpenses.reduce((max, group) => Math.max(max, group.amount), 0)
	);

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

	const emptyMessage = $derived(
		normalizedQuery
			? `No transactions match “${searchQuery.trim()}”.`
			: `No expenses for ${formatMonthLabel($selectedMonth)}.`
	);
	const isGrouped = $derived(groupBy !== 'transaction');
	const hasRows = $derived(
		isGrouped ? groupedExpenses.length > 0 : visibleExpenses.length > 0
	);

	function parseDay(iso: string): Date | null {
		// `iso` may carry a time component (YYYY-MM-DDTHH:MM:SS); only the date
		// part is shown, so slice to the first 10 chars before parsing.
		const [yearPart, monthPart, dayPart] = iso.slice(0, 10).split('-');
		const year = Number(yearPart);
		const month = Number(monthPart);
		const day = Number(dayPart);
		if (!Number.isFinite(year) || !Number.isFinite(month) || !Number.isFinite(day)) {
			return null;
		}
		return new Date(year, month - 1, day);
	}

	function formatDate(iso: string): string {
		const date = parseDay(iso);
		return date ? DATE_FORMATTER.format(date) : iso;
	}

	function formatDayHeading(iso: string): string {
		const date = parseDay(iso);
		return date ? DAY_FORMATTER.format(date) : iso;
	}

	function formatShortDate(iso: string): string {
		const date = parseDay(iso);
		return date ? SHORT_DATE_FORMATTER.format(date) : iso;
	}

	function sharePercent(amount: number): string {
		if (visibleTotal <= 0) return '';
		const percent = (amount / visibleTotal) * 100;
		return percent > 0 && percent < 1 ? '<1%' : `${Math.round(percent)}%`;
	}

	function handleEdit(expense: Expense): void {
		onedit?.(expense);
	}

	function deleteWithUndo(expense: Expense): void {
		const label = expense.displayName ?? expense.name;
		const shortLabel = label.length > 40 ? `${label.slice(0, 39)}…` : label;
		softDelete({
			kind: 'expense',
			id: expense.id,
			message: `Deleted “${shortLabel}”.`,
			commit: () => deleteExpense(expense.id)
		});
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

</script>

{#snippet categoryPill(category: Category | undefined)}
	{@const color = category?.color ?? '#9ca3af'}
	<span
		class="inline-flex max-w-full items-center gap-1.5 truncate rounded-full px-2 py-0.5 text-xs font-medium"
		style="background-color: {color}26; color: {color};"
	>
		<CategoryIcon name={category?.icon ?? '•'} size={11} />
		<span class="truncate">{category?.name ?? 'Uncategorized'}</span>
	</span>
{/snippet}

{#snippet rowActions(expense: Expense)}
	<div
		class="flex items-center justify-end gap-1 transition-opacity lg:opacity-0 lg:group-hover:opacity-100 lg:focus-within:opacity-100"
	>
		<button
			type="button"
			data-testid="expense-edit-btn"
			aria-label="Edit expense"
			onclick={(event) => {
				event.stopPropagation();
				handleEdit(expense);
			}}
			class="inline-flex h-6 w-6 items-center justify-center rounded-md text-xs text-ctp-overlay1 transition-colors hover:bg-ctp-surface1 hover:text-ctp-text"
		>
			✎
		</button>
		<button
			type="button"
			data-testid="expense-delete-btn"
			aria-label="Delete expense"
			onclick={(event) => {
				event.stopPropagation();
				deleteWithUndo(expense);
			}}
			class="inline-flex h-6 w-6 items-center justify-center rounded-md text-xs text-ctp-overlay1 transition-colors hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-950/40 dark:hover:text-red-400"
		>
			🗑
		</button>
	</div>
{/snippet}

{#if !hasRows}
	<div
		data-testid="empty-state"
		class="flex flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-ctp-surface2 px-6 py-16 text-center"
	>
		<p class="text-base font-medium text-ctp-text">{emptyMessage}</p>
		{#if normalizedQuery}
			<p class="text-sm text-ctp-overlay1">Try a different search.</p>
		{:else}
			<p class="text-sm text-ctp-overlay1">
				Add transactions from the <a
					href="/import"
					class="font-medium text-ctp-accent hover:underline">Import</a
				> page.
			</p>
		{/if}
	</div>
{:else}
	{#if normalizedQuery}
		<p data-testid="search-summary" class="-mt-3 text-sm text-ctp-overlay1">
			{visibleExpenses.length}
			{visibleExpenses.length === 1 ? 'transaction' : 'transactions'} matching · {formatAmount(
				visibleTotal,
				$settings.currency
			)}
		</p>
	{/if}
	<div class="overflow-hidden rounded-lg border border-ctp-surface1 bg-ctp-base">
		{#if !isGrouped}
			{#each dayGroups as day (day.date)}
				<section animate:flip={{ duration: FLIP_DURATION }}>
					<header
						data-testid="expense-day-header"
						class="flex items-baseline justify-between gap-3 border-b border-ctp-surface0 bg-ctp-surface0/50 px-3 py-1.5 sm:px-4"
					>
						<p class="text-xs font-semibold text-ctp-subtext0">
							{formatDayHeading(day.date)}
							<span class="ml-1 font-normal text-ctp-overlay0">· {day.items.length}</span>
						</p>
						<p class="text-xs font-semibold tabular-nums text-ctp-subtext0">
							{formatAmount(day.total, $settings.currency)}
						</p>
					</header>
					<ul>
						{#each day.items as expense (expense.id)}
							{@const category = categoryById.get(expense.categoryId)}
							{@const color = category?.color ?? '#9ca3af'}
							{@const categoryName = category?.name ?? 'Uncategorized'}
							{@const categoryIcon = category?.icon ?? '•'}
							{@const noteText = noteFor(expense)}
							<li
								data-testid="expense-row"
								data-expense-id={expense.id}
								class="{FLAT_ROW_GRID} group border-b border-ctp-surface0 px-3 py-2 transition-colors last:border-b-0 hover:bg-ctp-surface0/40 sm:px-4 lg:py-1.5"
								animate:flip={{ duration: FLIP_DURATION }}
								transition:slide={{ duration: SLIDE_DURATION, easing: cubicOut }}
							>
								<div
									data-testid="expense-category-icon"
									data-icon={categoryIcon}
									class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-sm font-semibold text-white shadow-sm"
									style="background-color: {color};"
									aria-label={categoryName}
								>
									<CategoryIcon name={categoryIcon} size={15} />
								</div>

								<div class="min-w-0">
									<p class="truncate text-sm font-medium leading-tight text-ctp-text">
										{expense.displayName ?? expense.name}
									</p>
									<!-- Mobile-only subline: date · note, like the pre-register list. -->
									<p class="mt-0.5 truncate text-xs text-ctp-overlay1 lg:hidden">
										{formatDate(expense.date)}{#if noteText}<span class="text-ctp-overlay0"
												>&nbsp;·&nbsp;</span
											>{noteText}{/if}
									</p>
									{#if $settings.showImportanceBadge}
										<div class="mt-1 flex flex-wrap items-center gap-1.5 lg:hidden">
											<ImportanceBadge importance={expense.importance} />
										</div>
									{/if}
									<span class="sr-only">{categoryName}</span>
								</div>

								<div class="hidden min-w-0 items-center gap-1.5 lg:flex">
									{@render categoryPill(category)}
									{#if $settings.showImportanceBadge}
										<ImportanceBadge importance={expense.importance} />
									{/if}
								</div>

								<p
									data-testid="expense-note"
									class="hidden truncate text-xs text-ctp-overlay1 lg:block"
									title={noteText || undefined}
								>
									{noteText}
								</p>

								<span class="text-right text-sm font-semibold tabular-nums text-ctp-text">
									{formatAmount(expense.amount, $settings.currency)}
								</span>

								{@render rowActions(expense)}
							</li>
						{/each}
					</ul>
				</section>
			{/each}
		{:else}
			<ul>
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
						class="border-b border-ctp-surface0 last:border-b-0"
						animate:flip={{ duration: FLIP_DURATION }}
						transition:slide={{ duration: SLIDE_DURATION, easing: cubicOut }}
					>
						<button
							type="button"
							data-testid="expense-group-toggle"
							aria-expanded={expanded}
							aria-controls={panelId}
							onclick={() => toggleGroup(group.id)}
							class="grid w-full grid-cols-[1rem_2.25rem_minmax(0,1fr)_auto] items-center gap-x-3 px-3 py-2 text-left transition-colors hover:bg-ctp-surface0 sm:px-4 lg:grid-cols-[1rem_2.25rem_minmax(10rem,16rem)_minmax(0,1fr)_3rem_6.5rem_3.75rem]"
						>
							<svg
								class="h-3.5 w-3.5 shrink-0 text-ctp-overlay0 transition-transform duration-200 ease-out"
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
								class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-sm font-semibold text-white shadow-sm"
								style="background-color: {color};"
								aria-label={group.name}
							>
								<CategoryIcon name={categoryIcon} size={15} />
							</div>

							<div class="min-w-0">
								<p class="truncate text-sm font-semibold leading-tight text-ctp-text">
									{group.name}
								</p>
								<p class="mt-0.5 truncate text-xs text-ctp-overlay1">
									{group.count}
									{group.count === 1 ? 'transaction' : 'transactions'}
								</p>
							</div>

							<!-- Desktop-only: proportional share of the month, filling the
							     header's middle instead of leaving it empty. -->
							<div
								class="hidden h-1.5 overflow-hidden rounded-full bg-ctp-surface1 lg:block"
								aria-hidden="true"
							>
								<div
									class="h-full rounded-full transition-[width] duration-300 ease-out"
									style="width: {maxGroupAmount > 0 ? (group.amount / maxGroupAmount) * 100 : 0}%; background-color: {color};"
								></div>
							</div>
							<span class="hidden text-right text-xs tabular-nums text-ctp-overlay1 lg:block">
								{sharePercent(group.amount)}
							</span>

							<TweenedAmount
								value={group.amount}
								currency={$settings.currency}
								testid="expense-group-amount"
								class="text-right text-sm font-semibold tabular-nums text-ctp-text"
							/>

							<!-- Spacer so the amount column lines up with child-row amounts. -->
							<span class="hidden lg:block" aria-hidden="true"></span>
						</button>

						{#if expanded}
							<div
								id={panelId}
								data-testid="expense-group-panel"
								transition:slide={{ duration: SLIDE_DURATION, easing: cubicOut }}
								class="border-t border-ctp-surface0 bg-ctp-surface0/60"
							>
								<ul class="pl-4 lg:pl-0">
									{#each items as expense (expense.id)}
										{@const itemCategory = categoryById.get(expense.categoryId)}
										{@const itemCategoryName = itemCategory?.name ?? 'Uncategorized'}
										{@const noteText = noteFor(expense)}
										<li
											data-testid="expense-nested-row"
											data-expense-id={expense.id}
											class="{CHILD_ROW_GRID} group border-b border-ctp-surface0 px-3 py-1.5 last:border-b-0 hover:bg-ctp-surface0/60 sm:px-4"
											animate:flip={{ duration: FLIP_DURATION }}
											transition:slide={{ duration: SLIDE_DURATION, easing: cubicOut }}
										>
											<span class="hidden text-xs tabular-nums text-ctp-overlay1 lg:block">
												{formatShortDate(expense.date)}
											</span>

											<div class="min-w-0">
												<p class="truncate text-sm font-medium leading-tight text-ctp-text">
													{expense.displayName ?? expense.name}
												</p>
												<!-- Mobile-only subline: date, category (when not implied by
												     the group), and note. -->
												<p class="mt-0.5 truncate text-xs text-ctp-overlay1 lg:hidden">
													{formatDate(expense.date)}{groupBy !== 'category'
														? ` · ${itemCategoryName}`
														: ''}{#if noteText}<span class="text-ctp-overlay0">&nbsp;·&nbsp;</span
														>{noteText}{/if}
												</p>
												{#if $settings.showImportanceBadge}
													<div class="mt-1 flex flex-wrap items-center gap-1.5 lg:hidden">
														<ImportanceBadge importance={expense.importance} />
													</div>
												{/if}
											</div>

											<div class="hidden min-w-0 items-center gap-1.5 lg:flex">
												<!-- Under a category header every child has that category —
												     repeating the pill is noise; other groupings need it. -->
												{#if groupBy !== 'category'}
													{@render categoryPill(itemCategory)}
												{/if}
												{#if $settings.showImportanceBadge}
													<ImportanceBadge importance={expense.importance} />
												{/if}
											</div>

											<p
												data-testid="expense-note"
												class="hidden truncate text-xs text-ctp-overlay1 lg:block"
												title={noteText || undefined}
											>
												{noteText}
											</p>

											<span class="text-right text-sm font-semibold tabular-nums text-ctp-text">
												{formatAmount(expense.amount, $settings.currency)}
											</span>

											{@render rowActions(expense)}
										</li>
									{/each}
								</ul>
							</div>
						{/if}
					</li>
				{/each}
			</ul>
		{/if}
	</div>
{/if}

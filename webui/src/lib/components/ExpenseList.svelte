<script lang="ts">
	import { onMount } from 'svelte';
	import CategoryIcon from '$components/CategoryIcon.svelte';
	import { expenses, deleteExpense, refreshExpenses } from '$lib/stores/expenses';
	import { categories, refreshCategories } from '$lib/stores/categories';
	import { selectedMonth } from '$lib/stores/ui';
	import { formatMonthLabel, monthKey } from '$lib/utils/dates';
	import { formatAmount } from '$lib/utils/money';
	import type { Category, Expense } from '$lib/types';

	type EditCallback = (expense: Expense) => void;

	let { onedit }: { onedit?: EditCallback } = $props();

	const DATE_FORMATTER = new Intl.DateTimeFormat('en-US', {
		year: 'numeric',
		month: 'short',
		day: 'numeric'
	});

	let confirmingId: string | null = $state(null);

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
	const emptyMessage = $derived(`No expenses for ${formatMonthLabel($selectedMonth)}.`);

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

	onMount(() => {
		void refreshExpenses();
		void refreshCategories();
	});
</script>

{#if visibleExpenses.length === 0}
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
	<ul class="overflow-hidden rounded-lg border border-gray-200 bg-white dark:border-gray-800 dark:bg-[#111114]">
		{#each visibleExpenses as expense (expense.id)}
			{@const category = categoryById.get(expense.categoryId)}
			{@const color = category?.color ?? '#9ca3af'}
			{@const categoryName = category?.name ?? 'Uncategorized'}
			{@const categoryIcon = category?.icon ?? '•'}
			{@const isConfirming = confirmingId === expense.id}
			<li
				data-testid="expense-row"
				data-expense-id={expense.id}
				class="flex items-center gap-3 border-b border-gray-100 px-3 py-3 last:border-b-0 sm:px-4 dark:border-gray-900"
			>
				<div
					data-testid="expense-category-icon"
					data-icon={categoryIcon}
					class="flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-base font-semibold text-white shadow-sm sm:h-11 sm:w-11"
					style="background-color: {color};"
					aria-label={categoryName}
				>
					<CategoryIcon name={categoryIcon} size={18} />
				</div>

				<div class="min-w-0 flex-1">
					<p class="truncate text-base font-semibold leading-tight text-gray-900 sm:text-lg dark:text-gray-100">
						{expense.name}
					</p>
					<p class="mt-0.5 truncate text-xs text-gray-500 sm:text-sm dark:text-gray-400">
						{formatDate(expense.date)}
					</p>
					<span class="sr-only">{categoryName}</span>
					{#if expense.note}
						<span class="sr-only">{expense.note}</span>
					{/if}
				</div>

				<div class="ml-auto flex shrink-0 flex-col items-end gap-1.5">
					<span
						class="text-right text-base font-semibold tabular-nums text-gray-900 sm:text-lg dark:text-gray-100"
					>
						{formatAmount(expense.amount)}
					</span>

					{#if isConfirming}
						<div class="flex items-center gap-1.5">
							<button
								type="button"
								data-testid="expense-delete-confirm-btn"
								onclick={() => confirmDelete(expense.id)}
								class="rounded-md bg-red-600 px-2.5 py-1 text-xs font-medium text-white transition-colors hover:bg-red-700"
							>
								Delete
							</button>
							<button
								type="button"
								data-testid="expense-delete-cancel-btn"
								onclick={cancelDelete}
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
								onclick={() => handleEdit(expense)}
								class="inline-flex h-7 w-7 items-center justify-center rounded-md text-sm text-gray-500 transition-colors hover:bg-gray-100 hover:text-gray-900 dark:text-gray-500 dark:hover:bg-gray-800 dark:hover:text-gray-100"
							>
								✎
							</button>
							<button
								type="button"
								data-testid="expense-delete-btn"
								aria-label="Delete expense"
								onclick={() => requestDelete(expense.id)}
								class="inline-flex h-7 w-7 items-center justify-center rounded-md text-sm text-gray-500 transition-colors hover:bg-red-50 hover:text-red-600 dark:text-gray-500 dark:hover:bg-red-950/40 dark:hover:text-red-400"
							>
								🗑
							</button>
						</div>
					{/if}
				</div>
			</li>
		{/each}
	</ul>
{/if}

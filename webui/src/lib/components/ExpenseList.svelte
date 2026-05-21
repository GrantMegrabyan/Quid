<script lang="ts">
	import { onMount } from 'svelte';
	import { expenses, deleteExpense, refreshExpenses } from '$lib/stores/expenses';
	import { categories, refreshCategories } from '$lib/stores/categories';
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

{#if $expenses.length === 0}
	<div
		data-testid="empty-state"
		class="flex flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-gray-300 px-6 py-16 text-center dark:border-gray-700"
	>
		<p class="text-base font-medium text-gray-900 dark:text-gray-100">No expenses yet.</p>
		<p class="text-sm text-gray-500 dark:text-gray-400">
			Click + Add expense to get started.
		</p>
	</div>
{:else}
	<ul class="divide-y divide-gray-200 overflow-hidden rounded-lg border border-gray-200 dark:divide-gray-800 dark:border-gray-800">
		{#each $expenses as expense (expense.id)}
			{@const category = categoryById.get(expense.categoryId)}
			{@const color = category?.color ?? '#9ca3af'}
			{@const categoryName = category?.name ?? 'Uncategorized'}
			{@const isConfirming = confirmingId === expense.id}
			<li
				data-testid="expense-row"
				data-expense-id={expense.id}
				class="flex flex-wrap items-center gap-x-4 gap-y-2 bg-white px-4 py-3 sm:flex-nowrap sm:px-5 dark:bg-transparent"
			>
				<div class="min-w-0 flex-1 sm:basis-auto">
					<div class="flex items-baseline gap-2">
						<p class="truncate text-base font-semibold text-gray-900 dark:text-gray-100">
							{expense.name}
						</p>
						<p class="shrink-0 text-xs text-gray-500 dark:text-gray-400">
							{formatDate(expense.date)}
						</p>
					</div>
					<div class="mt-0.5 flex items-center gap-1.5">
						<span
							aria-hidden="true"
							class="h-2 w-2 shrink-0 rounded-full"
							style="background-color: {color};"
						></span>
						<p class="truncate text-xs text-gray-500 dark:text-gray-400">
							{categoryName}
						</p>
					</div>
					{#if expense.note}
						<p class="mt-0.5 truncate text-xs text-gray-500 dark:text-gray-400">
							{expense.note}
						</p>
					{/if}
				</div>

				<div class="ml-auto flex items-center gap-3 sm:gap-4">
					<span
						class="text-right text-sm font-semibold tabular-nums text-gray-900 dark:text-gray-100"
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
								class="inline-flex h-8 w-8 items-center justify-center rounded-md text-base text-gray-600 transition-colors hover:bg-gray-100 hover:text-gray-900 dark:text-gray-400 dark:hover:bg-gray-800 dark:hover:text-gray-50"
							>
								✎
							</button>
							<button
								type="button"
								data-testid="expense-delete-btn"
								aria-label="Delete expense"
								onclick={() => requestDelete(expense.id)}
								class="inline-flex h-8 w-8 items-center justify-center rounded-md text-base text-gray-600 transition-colors hover:bg-red-50 hover:text-red-600 dark:text-gray-400 dark:hover:bg-red-950/40 dark:hover:text-red-400"
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

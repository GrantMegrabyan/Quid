<script lang="ts">
	import { onMount } from 'svelte';
	import ExpenseList from '$components/ExpenseList.svelte';
	import ExpenseFormModal from '$components/ExpenseFormModal.svelte';
	import MonthSelector from '$components/MonthSelector.svelte';
	import CumulativeChart from '$components/CumulativeChart.svelte';
	import MonthlyBarChart from '$components/MonthlyBarChart.svelte';
	import CategoryDoughnutChart from '$components/CategoryDoughnutChart.svelte';
	import { expenses } from '$lib/stores/expenses';
	import { refreshExpenses } from '$lib/stores/expenses';
	import { refreshCategories } from '$lib/stores/categories';
	import { selectedMonth } from '$lib/stores/ui';
	import { formatMonthLabel, monthKey } from '$utils/dates';
	import { formatAmount } from '$utils/money';
	import type { Expense } from '$types';

	let modalOpen = $state(false);
	let editingExpense: Expense | undefined = $state(undefined);
	let showMonthlyChart = $state(false);
	let showCategoryChart = $state(false);

	const CHART_PREFS_KEY = 'expense-tracker:dashboard-charts:v1';
	const selectedMonthLabel = $derived(formatMonthLabel($selectedMonth));
	const selectedMonthTotal = $derived.by(() => {
		let total = 0;
		for (const expense of $expenses) {
			if (monthKey(expense.date) === $selectedMonth) {
				total += expense.amount;
			}
		}
		return total;
	});
	const selectedMonthTotalLabel = $derived(formatAmount(selectedMonthTotal));

	function openAdd(): void {
		editingExpense = undefined;
		modalOpen = true;
	}

	function openEdit(expense: Expense): void {
		editingExpense = expense;
		modalOpen = true;
	}

	function closeModal(): void {
		modalOpen = false;
		editingExpense = undefined;
	}

	onMount(() => {
		void refreshExpenses();
		void refreshCategories();

		const saved = localStorage.getItem(CHART_PREFS_KEY);
		if (saved) {
			const prefs = JSON.parse(saved) as { monthly?: boolean; category?: boolean };
			showMonthlyChart = Boolean(prefs.monthly);
			showCategoryChart = Boolean(prefs.category);
		}
	});

	$effect(() => {
		localStorage.setItem(
			CHART_PREFS_KEY,
			JSON.stringify({ monthly: showMonthlyChart, category: showCategoryChart })
		);
	});
</script>

<svelte:head>
	<title>Expenses</title>
</svelte:head>

<section class="flex flex-col gap-6">
	<header class="flex flex-wrap items-center justify-between gap-3">
		<div>
			<h1
				data-testid="selected-month-total"
				class="text-2xl font-semibold tracking-tight text-gray-900 dark:text-gray-50"
			>
				{selectedMonthTotalLabel}
			</h1>
			<p
				data-testid="selected-month-heading"
				class="mt-1 text-sm text-gray-500 dark:text-gray-400"
			>
				{selectedMonthLabel}
			</p>
		</div>
		<button
			type="button"
			data-testid="add-expense-btn"
			onclick={openAdd}
			class="inline-flex items-center justify-center rounded-md bg-gray-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-gray-700 dark:bg-gray-100 dark:text-gray-900 dark:hover:bg-gray-300"
		>
			+ Add expense
		</button>
	</header>

	<div class="flex flex-wrap items-center justify-between gap-3">
		<MonthSelector />
		<div class="flex flex-wrap items-center gap-2 text-sm">
			<span class="text-gray-500 dark:text-gray-400">Charts</span>
			<label class="inline-flex items-center gap-2 rounded-full border border-gray-200 bg-white px-3 py-1.5 text-gray-700 dark:border-gray-800 dark:bg-[#111114] dark:text-gray-300">
				<input
					type="checkbox"
					data-testid="toggle-monthly-chart"
					bind:checked={showMonthlyChart}
					class="h-4 w-4 accent-gray-900 dark:accent-gray-100"
				/>
				Monthly totals
			</label>
			<label class="inline-flex items-center gap-2 rounded-full border border-gray-200 bg-white px-3 py-1.5 text-gray-700 dark:border-gray-800 dark:bg-[#111114] dark:text-gray-300">
				<input
					type="checkbox"
					data-testid="toggle-category-chart"
					bind:checked={showCategoryChart}
					class="h-4 w-4 accent-gray-900 dark:accent-gray-100"
				/>
				By category
			</label>
		</div>
	</div>

	<div
		class="rounded-lg border border-gray-200 bg-white p-4 sm:p-5 dark:border-gray-800 dark:bg-[#111114]"
	>
		<CumulativeChart />
	</div>

	{#if showMonthlyChart || showCategoryChart}
	<div class="grid grid-cols-1 gap-4 lg:grid-cols-2">
		{#if showMonthlyChart}
		<div
			class="rounded-lg border border-gray-200 bg-white p-4 sm:p-5 dark:border-gray-800 dark:bg-[#111114]"
		>
			<h2 class="mb-3 text-sm font-medium text-gray-700 dark:text-gray-300">
				Monthly total (12-month window)
			</h2>
			<MonthlyBarChart />
		</div>
		{/if}

		{#if showCategoryChart}
		<div
			class="rounded-lg border border-gray-200 bg-white p-4 sm:p-5 dark:border-gray-800 dark:bg-[#111114]"
		>
			<h2 class="mb-3 text-sm font-medium text-gray-700 dark:text-gray-300">
				By category
			</h2>
			<CategoryDoughnutChart />
		</div>
		{/if}
	</div>
	{/if}

	<ExpenseList onedit={openEdit} />
</section>

<ExpenseFormModal open={modalOpen} expense={editingExpense} on:close={closeModal} />

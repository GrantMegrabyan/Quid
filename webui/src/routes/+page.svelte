<script lang="ts">
	import { onMount } from 'svelte';
	import ExpenseList from '$components/ExpenseList.svelte';
	import ExpenseFormModal from '$components/ExpenseFormModal.svelte';
	import MonthSelector from '$components/MonthSelector.svelte';
	import CumulativeChart from '$components/CumulativeChart.svelte';
	import MonthlyBarChart from '$components/MonthlyBarChart.svelte';
	import CategoryDoughnutChart from '$components/CategoryDoughnutChart.svelte';
	import MonthlyByCategoryChart from '$components/MonthlyByCategoryChart.svelte';
	import CategoryMultiSelect from '$components/CategoryMultiSelect.svelte';
	import TweenedAmount from '$components/TweenedAmount.svelte';
	import { expenses } from '$lib/stores/expenses';
	import { refreshExpenses } from '$lib/stores/expenses';
	import { categories, refreshCategories } from '$lib/stores/categories';
	import { refreshSettings, settings } from '$lib/stores/settings';
	import { selectedMonth } from '$lib/stores/ui';
	import { formatMonthLabel, monthKey } from '$utils/dates';
	import type { Expense } from '$types';

	let modalOpen = $state(false);
	let editingExpense: Expense | undefined = $state(undefined);
	let showMonthlyChart = $state(false);
	let showCategoryChart = $state(false);
	let showCategoryMonthlyChart = $state(false);
	let selectedCategoryIds = $state<string[]>([]);
	let categoryMonthlyInitialised = $state(false);
	type ExpenseGroupBy = 'transaction' | 'merchant' | 'category' | 'importance';
	let expenseGroupBy = $state<ExpenseGroupBy>('transaction');

	const CHART_PREFS_KEY = 'expense-tracker:dashboard-charts:v1';
	const GROUP_BY_KEY = 'expense-tracker:expense-group-by:v1';
	const GROUP_BY_VALUES: ExpenseGroupBy[] = ['transaction', 'merchant', 'category', 'importance'];
	let groupByLoaded = $state(false);
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
		void refreshSettings();

		const savedGroupBy = localStorage.getItem(GROUP_BY_KEY);
		if (savedGroupBy && GROUP_BY_VALUES.includes(savedGroupBy as ExpenseGroupBy)) {
			expenseGroupBy = savedGroupBy as ExpenseGroupBy;
		}
		groupByLoaded = true;

		const saved = localStorage.getItem(CHART_PREFS_KEY);
		if (saved) {
			const prefs = JSON.parse(saved) as {
				monthly?: boolean;
				category?: boolean;
				categoryMonthly?: boolean;
				categoryMonthlySelected?: string[];
			};
			showMonthlyChart = Boolean(prefs.monthly);
			showCategoryChart = Boolean(prefs.category);
			showCategoryMonthlyChart = Boolean(prefs.categoryMonthly);
			if (Array.isArray(prefs.categoryMonthlySelected)) {
				selectedCategoryIds = prefs.categoryMonthlySelected;
				categoryMonthlyInitialised = true;
			}
		}
	});

	$effect(() => {
		if (categoryMonthlyInitialised) return;
		if ($categories.length === 0) return;
		selectedCategoryIds = $categories.map((category) => category.id);
		categoryMonthlyInitialised = true;
	});

	$effect(() => {
		localStorage.setItem(
			CHART_PREFS_KEY,
			JSON.stringify({
				monthly: showMonthlyChart,
				category: showCategoryChart,
				categoryMonthly: showCategoryMonthlyChart,
				categoryMonthlySelected: selectedCategoryIds
			})
		);
	});

	$effect(() => {
		if (!groupByLoaded) return;
		localStorage.setItem(GROUP_BY_KEY, expenseGroupBy);
	});
</script>

<svelte:head>
	<title>Expenses</title>
</svelte:head>

<section class="flex flex-col gap-6">
	<header class="flex flex-wrap items-center justify-between gap-3">
		<div>
			<h1 class="text-2xl font-semibold tracking-tight text-ctp-text">
				<TweenedAmount
					value={selectedMonthTotal}
					currency={$settings.currency}
					testid="selected-month-total"
				/>
			</h1>
			<p
				data-testid="selected-month-heading"
				class="mt-1 text-sm text-ctp-overlay1"
			>
				{selectedMonthLabel}
			</p>
		</div>
		<div class="flex flex-wrap items-center gap-2">
			<a
				href="/import"
				data-testid="import-csv-btn"
				class="inline-flex items-center justify-center rounded-md border border-ctp-surface2 bg-ctp-base px-4 py-2 text-sm font-medium text-ctp-text transition-colors hover:bg-ctp-surface1 disabled:cursor-not-allowed disabled:opacity-60"
			>
				Import CSV
			</a>
			<button
				type="button"
				data-testid="add-expense-btn"
				onclick={openAdd}
				class="inline-flex items-center justify-center rounded-md bg-ctp-accent px-4 py-2 text-sm font-medium text-ctp-on-accent transition-colors hover:bg-ctp-accent-hover"
			>
				+ Add expense
			</button>
		</div>
	</header>

	<div class="flex flex-wrap items-center justify-between gap-3">
		<MonthSelector />
		<div class="flex flex-wrap items-center gap-2 text-sm">
			<span class="text-ctp-overlay1">Charts</span>
			<label class="inline-flex items-center gap-2 rounded-full border border-ctp-surface1 bg-ctp-base px-3 py-1.5 text-ctp-subtext0">
				<input
					type="checkbox"
					data-testid="toggle-monthly-chart"
					bind:checked={showMonthlyChart}
					class="h-4 w-4 accent-ctp-accent"
				/>
				Monthly totals
			</label>
			<label class="inline-flex items-center gap-2 rounded-full border border-ctp-surface1 bg-ctp-base px-3 py-1.5 text-ctp-subtext0">
				<input
					type="checkbox"
					data-testid="toggle-category-chart"
					bind:checked={showCategoryChart}
					class="h-4 w-4 accent-ctp-accent"
				/>
				By category
			</label>
			<label class="inline-flex items-center gap-2 rounded-full border border-ctp-surface1 bg-ctp-base px-3 py-1.5 text-ctp-subtext0">
				<input
					type="checkbox"
					data-testid="toggle-category-monthly-chart"
					bind:checked={showCategoryMonthlyChart}
					class="h-4 w-4 accent-ctp-accent"
				/>
				By category over time
			</label>
		</div>
	</div>

	<div
		class="rounded-lg border border-ctp-surface1 bg-ctp-base p-4 sm:p-5"
	>
		<CumulativeChart />
	</div>

	{#if showMonthlyChart || showCategoryChart}
	<div class="grid grid-cols-1 gap-4 lg:grid-cols-2">
		{#if showMonthlyChart}
		<div
			class="rounded-lg border border-ctp-surface1 bg-ctp-base p-4 sm:p-5"
		>
			<h2 class="mb-3 text-sm font-medium text-ctp-subtext0">
				Monthly total (12-month window)
			</h2>
			<MonthlyBarChart />
		</div>
		{/if}

		{#if showCategoryChart}
		<div
			class="rounded-lg border border-ctp-surface1 bg-ctp-base p-4 sm:p-5"
		>
			<h2 class="mb-3 text-sm font-medium text-ctp-subtext0">
				By category
			</h2>
			<CategoryDoughnutChart />
		</div>
		{/if}
	</div>
	{/if}

	{#if showCategoryMonthlyChart}
	<div
		data-testid="category-monthly-chart-card"
		class="rounded-lg border border-ctp-surface1 bg-ctp-base p-4 sm:p-5"
	>
		<div class="mb-3 flex flex-wrap items-center justify-between gap-3">
			<h2 class="text-sm font-medium text-gray-700 dark:text-gray-300">
				Monthly expenses by category
			</h2>
			<CategoryMultiSelect bind:selectedIds={selectedCategoryIds} />
		</div>
		<MonthlyByCategoryChart {selectedCategoryIds} />
	</div>
	{/if}

	<div class="flex flex-wrap items-center justify-between gap-3">
		<h2 class="text-sm font-medium text-ctp-subtext0">Transactions</h2>
		<label class="inline-flex items-center gap-2 text-sm text-ctp-overlay1">
			Group by
			<select
				bind:value={expenseGroupBy}
				class="rounded-md border border-ctp-surface1 bg-ctp-base px-3 py-1.5 text-sm text-ctp-text"
			>
				<option value="transaction">Transaction</option>
				<option value="merchant">Merchant</option>
				<option value="category">Category</option>
				<option value="importance">Importance</option>
			</select>
		</label>
	</div>

	<ExpenseList groupBy={expenseGroupBy} onedit={openEdit} />
</section>

<ExpenseFormModal open={modalOpen} expense={editingExpense} on:close={closeModal} />

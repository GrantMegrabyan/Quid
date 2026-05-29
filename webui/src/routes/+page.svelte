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
	import { formatAmount } from '$utils/money';
	import { Wallet, Receipt, Tags, TrendingUp, TrendingDown } from '@lucide/svelte';
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
	const monthExpenses = $derived(
		$expenses.filter((expense) => monthKey(expense.date) === $selectedMonth)
	);
	const selectedMonthTotal = $derived.by(() => {
		let total = 0;
		for (const expense of monthExpenses) {
			total += expense.amount;
		}
		return total;
	});
	const transactionCount = $derived(monthExpenses.length);
	const avgPerTransaction = $derived(
		transactionCount > 0 ? selectedMonthTotal / transactionCount : 0
	);

	type StatChange = { value: string; direction: 'up' | 'down' } | null;

	function previousMonthOf(key: string): string {
		const [year, month] = key.split('-').map(Number);
		const date = new Date(year, month - 1, 1);
		date.setMonth(date.getMonth() - 1);
		return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`;
	}

	const previousMonthTotal = $derived.by(() => {
		const prevKey = previousMonthOf($selectedMonth);
		let total = 0;
		for (const expense of $expenses) {
			if (monthKey(expense.date) === prevKey) total += expense.amount;
		}
		return total;
	});

	const monthChange = $derived.by<StatChange>(() => {
		if (previousMonthTotal <= 0) return null;
		const pct = ((selectedMonthTotal - previousMonthTotal) / previousMonthTotal) * 100;
		if (!Number.isFinite(pct) || pct === 0) return null;
		return {
			value: `${Math.abs(pct).toFixed(1)}%`,
			direction: pct > 0 ? 'up' : 'down'
		};
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
	<!-- Hero greeting banner -->
	<div
		class="relative overflow-hidden rounded-2xl border border-ctp-surface1 bg-gradient-to-r from-emerald-600/90 via-emerald-700/40 to-ctp-base p-6 shadow-lg shadow-emerald-900/20 sm:p-8"
	>
		<div
			class="pointer-events-none absolute -right-10 -top-16 h-56 w-56 rounded-full bg-emerald-400/20 blur-3xl"
		></div>
		<div class="relative flex flex-wrap items-center justify-between gap-4">
			<div class="max-w-lg">
				<h1 class="text-2xl font-bold tracking-tight text-white sm:text-3xl">
					👋 Welcome back
				</h1>
				<p class="mt-2 text-sm text-emerald-50/80">
					Here's your spending overview for {selectedMonthLabel}.
				</p>
			</div>
			<div class="flex flex-wrap items-center gap-2">
				<a
					href="/import"
					data-testid="import-csv-btn"
					class="inline-flex items-center justify-center rounded-lg border border-white/30 bg-white/10 px-4 py-2 text-sm font-medium text-white backdrop-blur transition-colors hover:bg-white/20"
				>
					Import CSV
				</a>
				<button
					type="button"
					data-testid="add-expense-btn"
					onclick={openAdd}
					class="inline-flex items-center justify-center rounded-lg bg-white px-4 py-2 text-sm font-semibold text-emerald-700 shadow-sm transition-colors hover:bg-emerald-50"
				>
					+ Add expense
				</button>
			</div>
		</div>
	</div>

	<!-- Stat cards -->
	<div class="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
		<!-- This month total -->
		<div class="rounded-xl border border-ctp-surface1 bg-ctp-base p-5 shadow-lg shadow-black/20">
			<div class="flex items-center justify-between">
				<span class="flex h-11 w-11 items-center justify-center rounded-full bg-ctp-accent/15 text-ctp-accent">
					<Wallet class="h-5 w-5" />
				</span>
				{#if monthChange}
					<span
						class="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold {monthChange.direction ===
						'up'
							? 'bg-ctp-red/15 text-ctp-red'
							: 'bg-ctp-accent/15 text-ctp-accent'}"
					>
						{#if monthChange.direction === 'up'}
							<TrendingUp class="h-3 w-3" />
						{:else}
							<TrendingDown class="h-3 w-3" />
						{/if}
						{monthChange.value}
					</span>
				{/if}
			</div>
			<p class="mt-4 text-sm text-ctp-subtext0">This month</p>
			<p class="mt-1 text-2xl font-bold tracking-tight text-ctp-text">
				<TweenedAmount
					value={selectedMonthTotal}
					currency={$settings.currency}
					testid="selected-month-total"
				/>
			</p>
			<p data-testid="selected-month-heading" class="mt-1 text-xs text-ctp-overlay0">
				{selectedMonthLabel}
			</p>
		</div>

		<!-- Transactions -->
		<div class="rounded-xl border border-ctp-surface1 bg-ctp-base p-5 shadow-lg shadow-black/20">
			<span class="flex h-11 w-11 items-center justify-center rounded-full bg-ctp-blue/15 text-ctp-blue">
				<Receipt class="h-5 w-5" />
			</span>
			<p class="mt-4 text-sm text-ctp-subtext0">Transactions</p>
			<p class="mt-1 text-2xl font-bold tracking-tight text-ctp-text">{transactionCount}</p>
			<p class="mt-1 text-xs text-ctp-overlay0">This month</p>
		</div>

		<!-- Categories -->
		<div class="rounded-xl border border-ctp-surface1 bg-ctp-base p-5 shadow-lg shadow-black/20">
			<span class="flex h-11 w-11 items-center justify-center rounded-full bg-ctp-peach/15 text-ctp-peach">
				<Tags class="h-5 w-5" />
			</span>
			<p class="mt-4 text-sm text-ctp-subtext0">Categories</p>
			<p class="mt-1 text-2xl font-bold tracking-tight text-ctp-text">{$categories.length}</p>
			<p class="mt-1 text-xs text-ctp-overlay0">Active</p>
		</div>

		<!-- Avg per transaction -->
		<div class="rounded-xl border border-ctp-surface1 bg-ctp-base p-5 shadow-lg shadow-black/20">
			<span class="flex h-11 w-11 items-center justify-center rounded-full bg-ctp-mauve/15 text-ctp-mauve">
				<TrendingUp class="h-5 w-5" />
			</span>
			<p class="mt-4 text-sm text-ctp-subtext0">Avg / transaction</p>
			<p class="mt-1 text-2xl font-bold tracking-tight text-ctp-text">
				{formatAmount(avgPerTransaction, $settings.currency)}
			</p>
			<p class="mt-1 text-xs text-ctp-overlay0">This month</p>
		</div>
	</div>

	<!-- Month selector + chart toggles -->
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

	<!-- Spending chart card -->
	<div class="rounded-xl border border-ctp-surface1 bg-ctp-base p-5 shadow-lg shadow-black/20 sm:p-6">
		<h2 class="mb-4 text-base font-semibold text-ctp-text">Spending this month</h2>
		<CumulativeChart />
	</div>

	{#if showMonthlyChart || showCategoryChart}
	<div class="grid grid-cols-1 gap-4 lg:grid-cols-2">
		{#if showMonthlyChart}
		<div
			class="rounded-xl border border-ctp-surface1 bg-ctp-base p-5 shadow-lg shadow-black/20 sm:p-6"
		>
			<h2 class="mb-4 text-base font-semibold text-ctp-text">
				Monthly total (12-month window)
			</h2>
			<MonthlyBarChart />
		</div>
		{/if}

		{#if showCategoryChart}
		<div
			class="rounded-xl border border-ctp-surface1 bg-ctp-base p-5 shadow-lg shadow-black/20 sm:p-6"
		>
			<h2 class="mb-4 text-base font-semibold text-ctp-text">
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
		class="rounded-xl border border-ctp-surface1 bg-ctp-base p-5 shadow-lg shadow-black/20 sm:p-6"
	>
		<div class="mb-4 flex flex-wrap items-center justify-between gap-3">
			<h2 class="text-base font-semibold text-ctp-text">
				Monthly expenses by category
			</h2>
			<CategoryMultiSelect bind:selectedIds={selectedCategoryIds} />
		</div>
		<MonthlyByCategoryChart {selectedCategoryIds} />
	</div>
	{/if}

	<div class="flex flex-wrap items-center justify-between gap-3">
		<h2 class="text-base font-semibold text-ctp-text">Transactions</h2>
		<label class="inline-flex items-center gap-2 text-sm text-ctp-overlay1">
			Group by
			<select
				bind:value={expenseGroupBy}
				class="rounded-lg border border-ctp-surface1 bg-ctp-surface0 px-3 py-1.5 text-sm text-ctp-text"
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

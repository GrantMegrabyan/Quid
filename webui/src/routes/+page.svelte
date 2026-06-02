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
	import CategoryIcon from '$components/CategoryIcon.svelte';
	import TweenedAmount from '$components/TweenedAmount.svelte';
	import { expenses } from '$lib/stores/expenses';
	import { refreshExpenses } from '$lib/stores/expenses';
	import { categories, refreshCategories } from '$lib/stores/categories';
	import { refreshSettings, settings } from '$lib/stores/settings';
	import { selectedMonth } from '$lib/stores/ui';
	import { formatMonthLabel, monthKey } from '$utils/dates';
	import { amountToNumber, formatAmount } from '$utils/money';
	import { UNCATEGORIZED_COLOR } from '$utils/categoryColor';
	import { Wallet, Receipt, TrendingUp, TrendingDown } from '@lucide/svelte';
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
			total += amountToNumber(expense.amount);
		}
		return total;
	});
	const transactionCount = $derived(monthExpenses.length);
	const avgPerTransaction = $derived(
		transactionCount > 0 ? selectedMonthTotal / transactionCount : 0
	);

	type TopCategory = {
		name: string;
		total: number;
		color: string;
		icon?: string;
	} | null;

	const topCategory = $derived.by<TopCategory>(() => {
		if (monthExpenses.length === 0) return null;
		const totals = new Map<string, number>();
		for (const expense of monthExpenses) {
			totals.set(
				expense.categoryId,
				(totals.get(expense.categoryId) ?? 0) + amountToNumber(expense.amount)
			);
		}
		let topId: string | null = null;
		let topTotal = 0;
		for (const [id, total] of totals) {
			if (total > topTotal) {
				topTotal = total;
				topId = id;
			}
		}
		if (topId === null) return null;
		const category = $categories.find((c) => c.id === topId);
		return {
			name: category?.name ?? 'Uncategorized',
			total: topTotal,
			color: category?.color ?? UNCATEGORIZED_COLOR,
			icon: category?.icon
		};
	});

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
			if (monthKey(expense.date) === prevKey) total += amountToNumber(expense.amount);
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


	function openEdit(expense: Expense): void {
		editingExpense = expense;
		modalOpen = true;
	}

	function closeModal(): void {
		modalOpen = false;
		editingExpense = undefined;
	}

	// Re-fetch the scoped expense window whenever the selected month changes.
	// `refreshExpenses` reads the current month itself; we just depend on the
	// store so the effect re-runs on navigation. The store keeps the previous
	// data visible until the new response lands (no empty flash) and guards
	// against out-of-order responses.
	$effect(() => {
		void $selectedMonth;
		void refreshExpenses();
	});

	onMount(() => {
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
	<!-- Stat cards -->
	<div class="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
		<!-- This month total -->
		<div class="rounded-xl border border-ctp-surface1 bg-ctp-base p-4 shadow-lg shadow-black/20">
			<div class="flex items-center gap-3">
				<span class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-ctp-accent/15 text-ctp-accent">
					<Wallet class="h-[18px] w-[18px]" />
				</span>
				<div class="min-w-0 flex-1">
					<div class="flex min-h-5 items-center justify-between gap-2">
						<p class="text-xs font-medium text-ctp-subtext0">This month</p>
						{#if monthChange}
							<span
								class="inline-flex items-center gap-1 rounded-full px-1.5 py-0.5 text-[11px] font-semibold {monthChange.direction ===
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
					<p class="text-xl font-bold leading-tight tracking-tight text-ctp-text">
						<TweenedAmount
							value={selectedMonthTotal}
							currency={$settings.currency}
							testid="selected-month-total"
						/>
					</p>
				</div>
			</div>
			<p data-testid="selected-month-heading" class="sr-only">
				{selectedMonthLabel}
			</p>
		</div>

		<!-- Transactions -->
		<div class="rounded-xl border border-ctp-surface1 bg-ctp-base p-4 shadow-lg shadow-black/20">
			<div class="flex items-center gap-3">
				<span class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-ctp-blue/15 text-ctp-blue">
					<Receipt class="h-[18px] w-[18px]" />
				</span>
				<div class="min-w-0">
					<p class="text-xs font-medium text-ctp-subtext0">Transactions</p>
					<p class="text-xl font-bold leading-tight tracking-tight text-ctp-text">{transactionCount}</p>
				</div>
			</div>
		</div>

		<!-- Top category -->
		<div class="rounded-xl border border-ctp-surface1 bg-ctp-base p-4 shadow-lg shadow-black/20">
			<div class="flex items-center gap-3">
				<span
					class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full"
					style={topCategory
						? `background-color: ${topCategory.color}26; color: ${topCategory.color};`
						: undefined}
					class:bg-ctp-peach={!topCategory}
					class:text-ctp-peach={!topCategory}
				>
					{#if topCategory}
						<CategoryIcon name={topCategory.icon} size={18} />
					{:else}
						<TrendingUp class="h-[18px] w-[18px]" />
					{/if}
				</span>
				<div class="min-w-0 flex-1">
					<p class="text-xs font-medium text-ctp-subtext0">Top category</p>
					{#if topCategory}
						<p class="flex items-baseline gap-1.5 leading-tight">
							<span
								class="truncate text-xl font-bold tracking-tight text-ctp-text"
								data-testid="top-category-name"
								title={topCategory.name}
							>
								{topCategory.name}
							</span>
							<span class="shrink-0 text-xs text-ctp-overlay0">
								{formatAmount(topCategory.total, $settings.currency)}
							</span>
						</p>
					{:else}
						<p class="text-xl font-bold leading-tight tracking-tight text-ctp-overlay0">—</p>
					{/if}
				</div>
			</div>
		</div>

		<!-- Avg per transaction -->
		<div class="rounded-xl border border-ctp-surface1 bg-ctp-base p-4 shadow-lg shadow-black/20">
			<div class="flex items-center gap-3">
				<span class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-ctp-mauve/15 text-ctp-mauve">
					<TrendingUp class="h-[18px] w-[18px]" />
				</span>
				<div class="min-w-0">
					<p class="text-xs font-medium text-ctp-subtext0">Avg / transaction</p>
					<p class="text-xl font-bold leading-tight tracking-tight text-ctp-text">
						{formatAmount(avgPerTransaction, $settings.currency)}
					</p>
				</div>
			</div>
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

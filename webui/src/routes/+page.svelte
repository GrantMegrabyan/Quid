<script lang="ts">
	import { onMount } from 'svelte';
	import ExpenseList from '$components/ExpenseList.svelte';
	import ExpenseFormModal from '$components/ExpenseFormModal.svelte';
	import MonthSelector from '$components/MonthSelector.svelte';
	import CumulativeChart from '$components/CumulativeChart.svelte';
	import CategoryBreakdown from '$components/CategoryBreakdown.svelte';
	import CategoryIcon from '$components/CategoryIcon.svelte';
	import HeroAmount from '$components/HeroAmount.svelte';
	import { expenses } from '$lib/stores/expenses';
	import { refreshExpenses } from '$lib/stores/expenses';
	import { categories, refreshCategories } from '$lib/stores/categories';
	import { refreshSettings, settings } from '$lib/stores/settings';
	import { selectedMonth } from '$lib/stores/ui';
	import { persisted } from '$lib/stores/persisted';
	import { analyticsRepository } from '$lib/repos';
	import {
		currentMonthKey,
		daysInMonth,
		formatMonthLabel,
		monthDateRange,
		monthKey,
		previousMonthKey,
		todayIso
	} from '$utils/dates';
	import { amountToNumber, formatAmount } from '$utils/money';
	import { UNCATEGORIZED_COLOR } from '$utils/categoryColor';
	import { TrendingUp, TrendingDown, Search } from '@lucide/svelte';
	import type { Expense } from '$types';

	let modalOpen = $state(false);
	let editingExpense: Expense | undefined = $state(undefined);
	let searchQuery = $state('');

	type ExpenseGroupBy = 'transaction' | 'merchant' | 'category' | 'importance';
	const GROUP_BY_VALUES: ExpenseGroupBy[] = ['transaction', 'merchant', 'category', 'importance'];
	const expenseGroupBy = persisted<ExpenseGroupBy>(
		'quid:expense-group-by:v1',
		'transaction',
		(value) => GROUP_BY_VALUES.includes(value)
	);

	const selectedMonthLabel = $derived(formatMonthLabel($selectedMonth));
	const isCurrentMonth = $derived($selectedMonth === currentMonthKey());
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

	// Daily average over elapsed days (current month) or the whole month (past
	// months); the projection extrapolates that pace to month end.
	const elapsedDays = $derived.by(() => {
		const total = daysInMonth($selectedMonth);
		if (!isCurrentMonth) return total;
		return Math.min(Number(todayIso().slice(8, 10)), total);
	});
	const dailyAverage = $derived(elapsedDays > 0 ? selectedMonthTotal / elapsedDays : 0);
	const projectedTotal = $derived(dailyAverage * daysInMonth($selectedMonth));
	// A one-or-two-day sample extrapolates to nonsense (one big shop reads as a
	// five-figure month); hold the projection back until there's some signal.
	const showProjection = $derived(isCurrentMonth && elapsedDays >= 3 && selectedMonthTotal > 0);

	// Previous month's total for the "vs last month" delta. Fetched via the
	// analytics monthly-totals endpoint (a single aggregate row), NOT by loading
	// another month of expenses — the expense store stays strictly single-month.
	let prevMonthTotal: number | null = $state(null);
	let prevMonthRequest = 0;
	$effect(() => {
		const month = $selectedMonth;
		const requestId = ++prevMonthRequest;
		prevMonthTotal = null;
		const prev = previousMonthKey(month);
		const { from, to } = monthDateRange(prev);
		analyticsRepository
			.monthlyTotals({ dateFrom: from, dateTo: to })
			.then((result) => {
				if (requestId !== prevMonthRequest) return;
				const entry = result.months.find((m) => m.month === prev);
				prevMonthTotal = entry ? amountToNumber(entry.total) : 0;
			})
			.catch(() => {
				// The delta is decorative; a failed lookup just hides it.
				if (requestId === prevMonthRequest) prevMonthTotal = null;
			});
	});

	const monthDelta = $derived.by(() => {
		if (prevMonthTotal === null || prevMonthTotal <= 0) return null;
		const diff = selectedMonthTotal - prevMonthTotal;
		return {
			up: diff > 0,
			percent: Math.round(Math.abs(diff / prevMonthTotal) * 100),
			label: formatMonthLabel(previousMonthKey($selectedMonth))
		};
	});

	type TopCategory = {
		name: string;
		total: number;
		color: string;
		icon?: string;
		share: number;
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
			icon: category?.icon,
			share: selectedMonthTotal > 0 ? topTotal / selectedMonthTotal : 0
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

	// Searching within a month you just navigated to is rarely what you want;
	// clear the query on month change so counts always match the visible month.
	$effect(() => {
		void $selectedMonth;
		searchQuery = '';
	});

	onMount(() => {
		void refreshCategories();
		void refreshSettings();
	});
</script>

<svelte:head>
	<title>Expenses</title>
</svelte:head>

<section class="flex flex-col gap-8">
	<!-- Hero: the month's total is the page's headline; everything else is
	     support type underneath it (Wealthfolio's balance-first header). -->
	<header class="flex flex-col gap-5 border-b border-ctp-surface1 pb-6">
		<div class="flex flex-wrap items-start justify-between gap-4">
			<div class="min-w-0">
				<p class="text-[11px] font-semibold uppercase tracking-[0.14em] text-ctp-overlay1">
					<span data-testid="selected-month-heading">{selectedMonthLabel}</span>
					<span aria-hidden="true"> · </span>{isCurrentMonth ? 'so far' : 'total'}
				</p>
				<h1 class="mt-1.5 text-4xl font-black leading-none text-ctp-text sm:text-5xl">
					<HeroAmount
						value={selectedMonthTotal}
						currency={$settings.currency}
						testid="selected-month-total"
					/>
				</h1>
				<div class="mt-2 flex min-h-5 flex-wrap items-center gap-x-3 gap-y-1 text-sm">
					{#if monthDelta}
						<span
							data-testid="month-delta"
							class="inline-flex items-center gap-1.5 font-medium {monthDelta.up
								? 'text-ctp-red'
								: 'text-ctp-green'}"
						>
							{#if monthDelta.up}
								<TrendingUp class="h-4 w-4" />
							{:else}
								<TrendingDown class="h-4 w-4" />
							{/if}
							<span class="tabular-nums">{monthDelta.up ? '+' : '−'}{monthDelta.percent}%</span>
							<span class="font-normal text-ctp-overlay1">vs {monthDelta.label}</span>
						</span>
					{:else}
						<span class="text-ctp-overlay1">
							{isCurrentMonth ? 'Spending so far this month' : 'Spending overview'}
						</span>
					{/if}
				</div>
			</div>
			<MonthSelector />
		</div>

		<!-- Support stats: a quiet ruled strip, not four competing cards. -->
		<dl class="grid grid-cols-2 gap-x-6 gap-y-4 sm:gap-x-8 lg:grid-cols-3">
			<div class="border-l border-ctp-surface1 pl-4">
				<dt class="text-[11px] font-semibold uppercase tracking-wider text-ctp-overlay1">
					Transactions
				</dt>
				<dd class="numeral mt-1 text-xl font-bold text-ctp-text">{transactionCount}</dd>
				{#if transactionCount > 0}
					<dd class="mt-0.5 text-xs text-ctp-subtext0">
						{formatAmount(avgPerTransaction, $settings.currency)} avg
					</dd>
				{/if}
			</div>

			<div class="border-l border-ctp-surface1 pl-4">
				<dt class="text-[11px] font-semibold uppercase tracking-wider text-ctp-overlay1">
					Daily average
				</dt>
				<dd class="numeral mt-1 text-xl font-bold text-ctp-text">
					{formatAmount(dailyAverage, $settings.currency)}
				</dd>
				{#if showProjection}
					<dd data-testid="projected-total" class="mt-0.5 text-xs text-ctp-subtext0">
						On pace for {formatAmount(projectedTotal, $settings.currency)}
					</dd>
				{/if}
			</div>

			<div class="border-l border-ctp-surface1 pl-4">
				<dt class="text-[11px] font-semibold uppercase tracking-wider text-ctp-overlay1">
					Top category
				</dt>
				{#if topCategory}
					<dd class="mt-1 flex items-center gap-2">
						<span
							class="cat-chip flex h-6 w-6 shrink-0 items-center justify-center rounded-md"
							style="--cat: {topCategory.color};"
						>
							<CategoryIcon name={topCategory.icon} size={14} />
						</span>
						<span
							data-testid="top-category-name"
							title={topCategory.name}
							class="truncate text-base font-semibold text-ctp-text"
						>
							{topCategory.name}
						</span>
					</dd>
					<dd class="mt-0.5 text-xs text-ctp-subtext0">
						{formatAmount(topCategory.total, $settings.currency)} · {Math.round(
							topCategory.share * 100
						)}% of total
					</dd>
				{:else}
					<dd class="numeral mt-1 text-xl font-bold text-ctp-overlay0">—</dd>
				{/if}
			</div>

		</dl>
	</header>

	<!-- Charts: trend + category breakdown side by side on wide screens -->
	<div class="grid grid-cols-1 gap-6 xl:grid-cols-3">
		<div class="card p-5 sm:p-6 xl:col-span-2">
			<h2 class="mb-4 text-sm font-semibold text-ctp-subtext1">Spending this month</h2>
			<CumulativeChart />
		</div>

		<!-- Only shown when it fits beside the chart: stacked under it on
		     narrower screens it eats vertical space, and the same view is
		     available via Group by → Category. -->
		<div class="card hidden p-5 sm:p-6 xl:block">
			<h2 class="mb-4 text-sm font-semibold text-ctp-subtext1">By category</h2>
			<CategoryBreakdown />
		</div>
	</div>

	<!-- Transactions -->
	<div class="flex flex-wrap items-center gap-3">
		<h2 class="text-sm font-semibold uppercase tracking-wider text-ctp-subtext0">Transactions</h2>
		<div class="relative ml-auto w-full sm:w-64">
			<Search
				class="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ctp-overlay0"
			/>
			<input
				type="search"
				data-testid="expense-search"
				placeholder="Search transactions…"
				bind:value={searchQuery}
				class="field w-full pl-9"
			/>
		</div>
		<label class="inline-flex items-center gap-2 text-sm text-ctp-overlay1">
			Group by
			<select bind:value={$expenseGroupBy} class="field field-select">
				<option value="transaction">Transaction</option>
				<option value="merchant">Merchant</option>
				<option value="category">Category</option>
				<option value="importance">Importance</option>
			</select>
		</label>
	</div>

	<ExpenseList groupBy={$expenseGroupBy} {searchQuery} onedit={openEdit} />
</section>

<ExpenseFormModal open={modalOpen} expense={editingExpense} on:close={closeModal} />

<script lang="ts">
	import { onMount } from 'svelte';
	import { analyticsRepository } from '$lib/repos';
	import { refreshSettings, settings } from '$lib/stores/settings';
	import {
		analyticsPeriod,
		ANALYTICS_PERIODS,
		periodToWindow,
		monthOverMonthComparisonQuery,
		type AnalyticsPeriod
	} from '$lib/stores/analyticsPeriod';
	import { formatAmount, amountToNumber } from '$utils/money';
	import { UNCATEGORIZED_COLOR } from '$utils/categoryColor';
	import MonthlyTrendChart from '$components/analytics/MonthlyTrendChart.svelte';
	import CategoryTrendChart from '$components/analytics/CategoryTrendChart.svelte';
	import CategoryMoversList from '$components/analytics/CategoryMoversList.svelte';
	import TopMerchantsChart from '$components/analytics/TopMerchantsChart.svelte';
	import ImportanceBreakdownCard from '$components/analytics/ImportanceBreakdownCard.svelte';
	import WeekdayBreakdownChart from '$components/analytics/WeekdayBreakdownChart.svelte';
	import { Wallet, CalendarDays, Receipt, Tag, TrendingUp, TrendingDown } from '@lucide/svelte';
	import type {
		AnalyticsSummary,
		CategoryComparisonResult,
		CategoryTrendsResult,
		ImportanceBreakdownResult,
		MonthlyTotalsResult,
		TopMerchantsResult,
		WeekdayBreakdownResult
	} from '$types';

	const PERIOD_LABELS: Record<AnalyticsPeriod, string> = {
		'3m': '3M',
		'6m': '6M',
		'12m': '12M',
		all: 'All'
	};

	let summary = $state<AnalyticsSummary | null>(null);
	let monthly = $state<MonthlyTotalsResult | null>(null);
	let trends = $state<CategoryTrendsResult | null>(null);
	let comparison = $state<CategoryComparisonResult | null>(null);
	let merchants = $state<TopMerchantsResult | null>(null);
	let importance = $state<ImportanceBreakdownResult | null>(null);
	let weekday = $state<WeekdayBreakdownResult | null>(null);

	let loaded = $state(false);
	let loadError = $state<string | null>(null);

	// Monotonic request id guards against out-of-order responses when the user
	// flips the period quickly: a stale response is dropped if a newer fetch has
	// started since it was issued.
	let requestSeq = 0;

	async function loadAnalytics(period: AnalyticsPeriod): Promise<void> {
		const seq = ++requestSeq;
		const window = periodToWindow(period);
		const comparisonQuery = monthOverMonthComparisonQuery();
		try {
			const [
				summaryRes,
				monthlyRes,
				trendsRes,
				comparisonRes,
				merchantsRes,
				importanceRes,
				weekdayRes
			] = await Promise.all([
				analyticsRepository.summary(window),
				analyticsRepository.monthlyTotals(window),
				analyticsRepository.categoryTrends(window),
				analyticsRepository.categoryComparison(comparisonQuery),
				analyticsRepository.topMerchants({ ...window, limit: 8 }),
				analyticsRepository.importanceBreakdown(window),
				analyticsRepository.weekdayBreakdown(window)
			]);

			// Drop stale responses; keep the previous data visible meanwhile.
			if (seq !== requestSeq) return;

			summary = summaryRes;
			monthly = monthlyRes;
			trends = trendsRes;
			comparison = comparisonRes;
			merchants = merchantsRes;
			importance = importanceRes;
			weekday = weekdayRes;
			loadError = null;
			loaded = true;
		} catch (error) {
			if (seq !== requestSeq) return;
			loadError = error instanceof Error ? error.message : 'Failed to load analytics.';
			loaded = true;
		}
	}

	onMount(() => {
		void refreshSettings();
	});

	// Re-fetch whenever the period changes. Keeps previous data on screen until
	// the new response lands (no empty flash).
	$effect(() => {
		void loadAnalytics($analyticsPeriod);
	});

	const totalNum = $derived(summary ? amountToNumber(summary.total) : 0);
	const isEmpty = $derived(loaded && summary !== null && summary.transactionCount === 0);

	// Month-over-month: for expenses, an INCREASE is bad (red/up), a DECREASE is
	// good (green/down).
	const momDelta = $derived(summary ? amountToNumber(summary.monthOverMonthDelta) : 0);
	const momIsUp = $derived(momDelta > 0);
	const momPercentLabel = $derived.by(() => {
		if (!summary || summary.monthOverMonthPercent === null) return null;
		const sign = summary.monthOverMonthPercent > 0 ? '+' : '';
		return `${sign}${Math.round(summary.monthOverMonthPercent)}%`;
	});

	function selectPeriod(period: AnalyticsPeriod): void {
		analyticsPeriod.set(period);
	}
</script>

<svelte:head>
	<title>Analytics</title>
</svelte:head>

<section class="flex flex-col gap-6">
	<!-- Header + period selector -->
	<div class="flex flex-wrap items-center justify-between gap-3">
		<div>
			<h1 class="text-2xl font-bold tracking-tight text-ctp-text">Analytics</h1>
			<p class="text-sm text-ctp-subtext0">Where your money goes, and how it's trending.</p>
		</div>
		<div
			class="inline-flex items-center gap-1 rounded-full border border-ctp-surface1 bg-ctp-base p-1 shadow-lg shadow-black/20"
			data-testid="analytics-period-selector"
			role="group"
			aria-label="Select analytics period"
		>
			{#each ANALYTICS_PERIODS as period (period)}
				{@const active = $analyticsPeriod === period}
				<button
					type="button"
					data-testid={`analytics-period-${period}`}
					aria-pressed={active}
					onclick={() => selectPeriod(period)}
					class="rounded-full px-3 py-1.5 text-sm font-medium transition-colors {active
						? 'bg-ctp-accent text-ctp-on-accent shadow-sm'
						: 'text-ctp-subtext0 hover:bg-ctp-surface0/60 hover:text-ctp-text'}"
				>
					{PERIOD_LABELS[period]}
				</button>
			{/each}
		</div>
	</div>

	{#if loadError}
		<div
			class="rounded-xl border border-ctp-red/40 bg-ctp-red/10 p-4 text-sm text-ctp-red"
			data-testid="analytics-error"
		>
			Couldn't load analytics: {loadError}
		</div>
	{:else if isEmpty}
		<div
			class="flex flex-col items-center justify-center gap-3 rounded-xl border border-ctp-surface1 bg-ctp-base p-12 text-center shadow-lg shadow-black/20"
			data-testid="analytics-empty"
		>
			<span class="flex h-12 w-12 items-center justify-center rounded-full bg-ctp-accent/15 text-ctp-accent">
				<TrendingUp class="h-6 w-6" />
			</span>
			<p class="text-base font-semibold text-ctp-text">No data yet</p>
			<p class="max-w-sm text-sm text-ctp-subtext0">
				Import some transactions and your spending trends, movers, and breakdowns will appear here.
			</p>
			<a
				href="/import"
				class="mt-1 inline-flex items-center gap-2 rounded-lg bg-ctp-accent px-4 py-2 text-sm font-semibold text-ctp-on-accent transition-opacity hover:opacity-90"
			>
				Import transactions
			</a>
		</div>
	{:else}
		<!-- KPI cards -->
		<div class="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-5">
			<!-- Total spend -->
			<div class="rounded-xl border border-ctp-surface1 bg-ctp-base p-4 shadow-lg shadow-black/20">
				<div class="flex items-center gap-3">
					<span class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-ctp-accent/15 text-ctp-accent">
						<Wallet class="h-[18px] w-[18px]" />
					</span>
					<div class="min-w-0 flex-1">
						<p class="text-xs font-medium text-ctp-subtext0">Total spend</p>
						<p
							class="text-xl font-bold leading-tight tracking-tight text-ctp-text"
							data-testid="analytics-kpi-total"
						>
							{formatAmount(totalNum, $settings.currency)}
						</p>
					</div>
				</div>
			</div>

			<!-- Avg / month -->
			<div class="rounded-xl border border-ctp-surface1 bg-ctp-base p-4 shadow-lg shadow-black/20">
				<div class="flex items-center gap-3">
					<span class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-ctp-blue/15 text-ctp-blue">
						<CalendarDays class="h-[18px] w-[18px]" />
					</span>
					<div class="min-w-0 flex-1">
						<p class="text-xs font-medium text-ctp-subtext0">Avg / month</p>
						<p class="text-xl font-bold leading-tight tracking-tight text-ctp-text">
							{formatAmount(summary?.averagePerMonth ?? '0', $settings.currency)}
						</p>
					</div>
				</div>
			</div>

			<!-- Transactions -->
			<div class="rounded-xl border border-ctp-surface1 bg-ctp-base p-4 shadow-lg shadow-black/20">
				<div class="flex items-center gap-3">
					<span class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-ctp-mauve/15 text-ctp-mauve">
						<Receipt class="h-[18px] w-[18px]" />
					</span>
					<div class="min-w-0 flex-1">
						<p class="text-xs font-medium text-ctp-subtext0">Transactions</p>
						<p class="text-xl font-bold leading-tight tracking-tight text-ctp-text">
							{summary?.transactionCount ?? 0}
						</p>
					</div>
				</div>
			</div>

			<!-- Top category -->
			<div class="rounded-xl border border-ctp-surface1 bg-ctp-base p-4 shadow-lg shadow-black/20">
				<div class="flex items-center gap-3">
					<span class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-ctp-peach/15 text-ctp-peach">
						<Tag class="h-[18px] w-[18px]" />
					</span>
					<div class="min-w-0 flex-1">
						<p class="text-xs font-medium text-ctp-subtext0">Top category</p>
						{#if summary?.topCategoryName}
							<p class="flex items-baseline gap-1.5 leading-tight">
								<span
									class="truncate text-xl font-bold tracking-tight text-ctp-text"
									title={summary.topCategoryName}
								>
									{summary.topCategoryName}
								</span>
								<span class="shrink-0 text-xs text-ctp-overlay0">
									{formatAmount(summary.topCategoryTotal, $settings.currency)}
								</span>
							</p>
						{:else}
							<p class="text-xl font-bold leading-tight tracking-tight text-ctp-overlay0">—</p>
						{/if}
					</div>
				</div>
			</div>

			<!-- Month over month -->
			<div class="rounded-xl border border-ctp-surface1 bg-ctp-base p-4 shadow-lg shadow-black/20">
				<div class="flex items-center gap-3">
					<span
						class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full {momIsUp
							? 'bg-ctp-red/15 text-ctp-red'
							: 'bg-ctp-green/15 text-ctp-green'}"
					>
						{#if momIsUp}
							<TrendingUp class="h-[18px] w-[18px]" />
						{:else}
							<TrendingDown class="h-[18px] w-[18px]" />
						{/if}
					</span>
					<div class="min-w-0 flex-1">
						<p class="text-xs font-medium text-ctp-subtext0">vs last month</p>
						<p
							class="flex items-baseline gap-1.5 text-xl font-bold leading-tight tracking-tight {momIsUp
								? 'text-ctp-red'
								: 'text-ctp-green'}"
							data-testid="analytics-kpi-mom"
						>
							<span>{momDelta >= 0 ? '+' : '-'}{formatAmount(Math.abs(momDelta), $settings.currency)}</span>
							{#if momPercentLabel}
								<span class="text-xs font-medium opacity-80">{momPercentLabel}</span>
							{/if}
						</p>
					</div>
				</div>
			</div>
		</div>

		<!-- Charts grid -->
		<div class="grid grid-cols-1 gap-6 lg:grid-cols-2">
			<!-- Monthly trend: full width -->
			{#if monthly}
				<div class="lg:col-span-2">
					<MonthlyTrendChart months={monthly.months} />
				</div>
			{/if}

			<!-- Movers + importance: two-up -->
			{#if comparison}
				<CategoryMoversList movers={comparison.movers} />
			{/if}
			{#if importance}
				<ImportanceBreakdownCard breakdown={importance.breakdown} total={importance.total} />
			{/if}

			<!-- Category trend: full width -->
			{#if trends}
				<div class="lg:col-span-2">
					<CategoryTrendChart data={trends} />
				</div>
			{/if}

			<!-- Merchants + weekday: two-up -->
			{#if merchants}
				<TopMerchantsChart merchants={merchants.merchants} />
			{/if}
			{#if weekday}
				<WeekdayBreakdownChart breakdown={weekday.breakdown} />
			{/if}
		</div>
	{/if}
</section>

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
	import { addMonths, formatMonthLabel, todayIso } from '$utils/dates';
	import MonthlyTrendChart from '$components/analytics/MonthlyTrendChart.svelte';
	import CategoryTrendChart from '$components/analytics/CategoryTrendChart.svelte';
	import CategoryMoversList from '$components/analytics/CategoryMoversList.svelte';
	import TopMerchantsChart from '$components/analytics/TopMerchantsChart.svelte';
	import ImportanceTrendChart from '$components/analytics/ImportanceTrendChart.svelte';
	import RecurringPanel from '$components/analytics/RecurringPanel.svelte';
	import LargeTransactionsList from '$components/analytics/LargeTransactionsList.svelte';
	import DistributionCard from '$components/analytics/DistributionCard.svelte';
	import {
		Wallet,
		CalendarDays,
		Receipt,
		CalendarCheck,
		TrendingUp,
		TrendingDown
	} from '@lucide/svelte';
	import type {
		AnalyticsSummary,
		CategoryComparisonResult,
		CategoryTrendsResult,
		DistributionResult,
		ImportanceTrendResult,
		LargeTransactionsResult,
		MonthlyTotalsResult,
		RecurringResult,
		TopMerchantsResult
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
	let importanceTrend = $state<ImportanceTrendResult | null>(null);
	let recurring = $state<RecurringResult | null>(null);
	let largeTransactions = $state<LargeTransactionsResult | null>(null);
	let distribution = $state<DistributionResult | null>(null);

	let loaded = $state(false);
	let loadError = $state<string | null>(null);

	// Plain, NON-reactive bookkeeping. In runes mode a bare `let` is never a
	// dependency, so reading/writing these can neither be tracked nor schedule a
	// re-run.
	//
	// `requestSeq` drops out-of-order responses: the load does two serial
	// round-trips (the movers comparison needs the summary's latestMonth), so a
	// superseded run can resolve late. Only the newest issued request
	// (`seq === requestSeq`) is allowed to commit.
	//
	// `loadedPeriod` is the period the most-recent load was STARTED for. The
	// driver below dedupes on it, so a duplicate emission of the same value never
	// stacks a second in-flight load — the exact failure that lets `requestSeq`
	// outrun every response and hang the spinner forever.
	let requestSeq = 0;
	let loadedPeriod: AnalyticsPeriod | null = null;

	async function loadAnalytics(period: AnalyticsPeriod): Promise<void> {
		const seq = ++requestSeq;
		const window = periodToWindow(period);
		// Capture the clock once so `dateTo` and `asOf` can't straddle midnight.
		const asOf = todayIso();
		try {
			const [
				summaryRes,
				monthlyRes,
				trendsRes,
				merchantsRes,
				importanceTrendRes,
				recurringRes,
				largeRes,
				distributionRes
			] = await Promise.all([
				// `asOf` lets the summary exclude the in-progress month from the
				// averages / latestMonth / MoM, and surface the projection fields.
				analyticsRepository.summary({ ...window, asOf }),
				analyticsRepository.monthlyTotals(window),
				analyticsRepository.categoryTrends({ ...window, limit: 5 }),
				analyticsRepository.topMerchants({ ...window, limit: 8 }),
				analyticsRepository.importanceTrend(window),
				analyticsRepository.recurring(window),
				analyticsRepository.largeTransactions({ ...window, limit: 5 }),
				analyticsRepository.distribution(window)
			]);

			// Superseded by a newer load during phase 1? Don't even fire the
			// dependent comparison request.
			if (seq !== requestSeq) return;

			// Movers compare the latest COMPLETE month (from the summary) vs the
			// month before it — not the literal calendar month, which is often
			// partial/empty and would make every category read "-100%".
			const comparisonRes = await analyticsRepository.categoryComparison(
				monthOverMonthComparisonQuery(summaryRes.latestMonth)
			);

			// Superseded during phase 2? Drop it; keep the previous data on screen.
			if (seq !== requestSeq) return;

			summary = summaryRes;
			monthly = monthlyRes;
			trends = trendsRes;
			comparison = comparisonRes;
			merchants = merchantsRes;
			importanceTrend = importanceTrendRes;
			recurring = recurringRes;
			largeTransactions = largeRes;
			distribution = distributionRes;
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

		// Drive loads from an explicit store subscription, NOT a `$effect`.
		//
		// `loadAnalytics` writes reactive `$state` (`loaded`, `summary`, …). A
		// `$effect` that read any of that state — directly or transitively — would
		// re-invalidate itself; combined with the serial two-RTT load, `requestSeq`
		// could outrun every response so nothing ever satisfies `seq === requestSeq`
		// at commit (permanent spinner). A plain `subscribe` callback is NOT a
		// tracked reaction, so no write inside the load can ever schedule another
		// run.
		//
		// `subscribe` fires once synchronously with the current value, then only on
		// genuine changes (`writable` suppresses equal-value emits). The value
		// dedupe is belt-and-braces: even a duplicate/leaked emission issues at most
		// one load per distinct period. The returned unsubscribe tears the driver
		// down on unmount, so client-side navigations / HMR can't stack drivers.
		return analyticsPeriod.subscribe((period) => {
			if (period === loadedPeriod) return;
			loadedPeriod = period;
			void loadAnalytics(period);
		});
	});

	const totalNum = $derived(summary ? amountToNumber(summary.total) : 0);
	const isEmpty = $derived(loaded && summary !== null && summary.transactionCount === 0);

	// --- Last-complete-month hero ---------------------------------------------
	// Analytics is retrospective: we lead with the most recent COMPLETE month
	// (the in-progress month is excluded by the API when `asOf` is passed) and
	// frame it against the trailing average, so the headline number is always a
	// full month you can actually analyse — never a few days of partial data.
	const hasLatestMonth = $derived(summary?.latestMonth != null);

	const latestVsAvgDelta = $derived.by(() => {
		if (!summary) return 0;
		return amountToNumber(summary.latestMonthTotal) - amountToNumber(summary.averagePerCompleteMonth);
	});
	const latestVsAvgIsOver = $derived(latestVsAvgDelta > 0);
	const latestVsAvgLabel = $derived.by(() => {
		if (!summary) return null;
		const avg = amountToNumber(summary.averagePerCompleteMonth);
		if (avg <= 0) return null;
		const pct = Math.round((latestVsAvgDelta / avg) * 100);
		const sign = pct > 0 ? '+' : '';
		return `${sign}${pct}%`;
	});

	// --- Month over month ------------------------------------------------------
	// For expenses, an INCREASE is bad (red/up), a DECREASE is good (green/down).
	const momDelta = $derived(summary ? amountToNumber(summary.monthOverMonthDelta) : 0);
	const momIsUp = $derived(momDelta > 0);
	const momPercentLabel = $derived.by(() => {
		if (!summary || summary.monthOverMonthPercent === null) return null;
		const sign = summary.monthOverMonthPercent > 0 ? '+' : '';
		return `${sign}${Math.round(summary.monthOverMonthPercent)}%`;
	});

	// --- "What changed" attribution -------------------------------------------
	// Reframe the movers as the explanation of the MoM KPI: net delta + the top
	// few drivers behind it.
	const moversSubtitle = $derived.by(() => {
		if (!summary || !comparison) return 'Categories that changed the most month over month.';
		const latest = summary.latestMonth;
		if (!latest) return 'Not enough history yet to compare months.';
		const prevLabel = formatMonthLabel(addMonths(latest, -1));

		const net = momDelta;
		const sign = net > 0 ? '+' : net < 0 ? '-' : '';
		const netStr = `${sign}${formatAmount(Math.abs(net), $settings.currency)}`;

		// Top increases (the drivers of an overspend) by descending delta.
		const drivers = comparison.movers
			.filter((m) => amountToNumber(m.delta) > 0)
			.slice(0, 3)
			.map((m) => m.categoryName);

		if (drivers.length === 0) {
			return `${netStr} vs ${prevLabel}.`;
		}
		return `${netStr} vs ${prevLabel} — driven by ${drivers.join(', ')}.`;
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
	{:else if !loaded}
		<div
			class="flex items-center justify-center gap-3 rounded-xl border border-ctp-surface1 bg-ctp-base p-12 text-sm text-ctp-subtext0 shadow-lg shadow-black/20"
			data-testid="analytics-loading"
		>
			<span class="h-4 w-4 animate-spin rounded-full border-2 border-ctp-surface2 border-t-ctp-accent"></span>
			Loading analytics…
		</div>
	{:else if isEmpty}
		<div
			class="flex flex-col items-center justify-center gap-3 rounded-xl border border-ctp-surface1 bg-ctp-base p-12 text-center shadow-lg shadow-black/20"
			data-testid="analytics-empty"
		>
			<span
				class="flex h-12 w-12 items-center justify-center rounded-full bg-ctp-accent/15 text-ctp-accent"
			>
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
		<!-- KPI row: projection hero first, then supporting metrics. -->
		<div class="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
			<!-- HERO: Last complete month vs the trailing average -->
			<div
				class="rounded-xl border-2 border-ctp-accent/50 bg-gradient-to-br from-ctp-accent/[0.07] to-ctp-base p-4 shadow-lg shadow-black/20 sm:col-span-2 sm:row-span-1"
				data-testid="analytics-kpi-latest-month"
			>
				<div class="flex items-start gap-3">
					<span
						class="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-ctp-accent/20 text-ctp-accent"
					>
						<CalendarCheck class="h-5 w-5" />
					</span>
					<div class="min-w-0 flex-1">
						{#if hasLatestMonth && summary}
							<p class="text-xs font-medium text-ctp-subtext0">
								Last complete month
								{#if summary.latestMonth}
									<span class="text-ctp-overlay0">· {formatMonthLabel(summary.latestMonth)}</span>
								{/if}
							</p>
							<p class="text-2xl font-bold leading-tight tracking-tight text-ctp-text">
								{formatAmount(summary.latestMonthTotal, $settings.currency)}
							</p>
							<div class="mt-1.5 flex flex-wrap items-baseline gap-x-2 gap-y-0.5 text-sm">
								<span class="text-ctp-subtext0">
									vs <span class="font-semibold text-ctp-text"
										>{formatAmount(summary.averagePerCompleteMonth, $settings.currency)}</span
									> avg
								</span>
								{#if latestVsAvgLabel}
									<span
										class="inline-flex items-center gap-0.5 rounded-full px-1.5 py-0.5 text-xs font-semibold tabular-nums {latestVsAvgIsOver
											? 'bg-ctp-red/15 text-ctp-red'
											: 'bg-ctp-green/15 text-ctp-green'}"
									>
										{#if latestVsAvgIsOver}
											<TrendingUp class="h-3 w-3" />
										{:else}
											<TrendingDown class="h-3 w-3" />
										{/if}
										{latestVsAvgLabel} vs avg
									</span>
								{/if}
							</div>
						{:else if summary}
							<p class="text-xs font-medium text-ctp-subtext0">Last complete month</p>
							<p class="text-2xl font-bold leading-tight tracking-tight text-ctp-overlay0">—</p>
							<p class="mt-1.5 text-sm text-ctp-overlay0">
								Not enough history yet — a full month is needed.
							</p>
						{/if}
					</div>
				</div>
			</div>

			<!-- Avg / month (complete months) -->
			<div class="rounded-xl border border-ctp-surface1 bg-ctp-base p-4 shadow-lg shadow-black/20">
				<div class="flex items-center gap-3">
					<span
						class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-ctp-blue/15 text-ctp-blue"
					>
						<CalendarDays class="h-[18px] w-[18px]" />
					</span>
					<div class="min-w-0 flex-1">
						<p class="text-xs font-medium text-ctp-subtext0">Avg / month</p>
						<p class="text-xl font-bold leading-tight tracking-tight text-ctp-text">
							{formatAmount(summary?.averagePerCompleteMonth ?? '0', $settings.currency)}
						</p>
						<p class="text-[11px] text-ctp-overlay0">(complete months)</p>
					</div>
				</div>
			</div>

			<!-- vs last month -> links down to "What changed" -->
			<a
				href="#analytics-movers"
				class="group rounded-xl border border-ctp-surface1 bg-ctp-base p-4 shadow-lg shadow-black/20 transition-colors hover:border-ctp-surface2"
			>
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
							<span
								>{momDelta >= 0 ? '+' : '-'}{formatAmount(
									Math.abs(momDelta),
									$settings.currency
								)}</span
							>
							{#if momPercentLabel}
								<span class="text-xs font-medium opacity-80">{momPercentLabel}</span>
							{/if}
						</p>
						<p
							class="text-[11px] text-ctp-overlay0 transition-colors group-hover:text-ctp-subtext0"
						>
							see what changed ↓
						</p>
					</div>
				</div>
			</a>

			<!-- Total spend -->
			<div class="rounded-xl border border-ctp-surface1 bg-ctp-base p-4 shadow-lg shadow-black/20">
				<div class="flex items-center gap-3">
					<span
						class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-ctp-accent/15 text-ctp-accent"
					>
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

			<!-- Avg transaction -->
			<div class="rounded-xl border border-ctp-surface1 bg-ctp-base p-4 shadow-lg shadow-black/20">
				<div class="flex items-center gap-3">
					<span
						class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-ctp-mauve/15 text-ctp-mauve"
					>
						<Receipt class="h-[18px] w-[18px]" />
					</span>
					<div class="min-w-0 flex-1">
						<p class="text-xs font-medium text-ctp-subtext0">Avg transaction</p>
						<p class="text-xl font-bold leading-tight tracking-tight text-ctp-text">
							{formatAmount(summary?.averagePerTransaction ?? '0', $settings.currency)}
						</p>
						<p class="text-[11px] text-ctp-overlay0">
							across {summary?.transactionCount ?? 0} txns
						</p>
					</div>
				</div>
			</div>
		</div>

		<!-- Monthly trend: full width -->
		{#if monthly}
			<MonthlyTrendChart months={monthly.months} currentMonth={summary?.currentMonth ?? null} />
		{/if}

		<!-- What changed: attribution for the MoM KPI -->
		{#if comparison}
			<div id="analytics-movers" class="scroll-mt-6">
				<CategoryMoversList
					movers={comparison.movers}
					subtitle={moversSubtitle}
					title="What changed"
					limit={6}
				/>
			</div>
		{/if}

		<!-- Actionable core: recurring + biggest purchases -->
		<div class="grid grid-cols-1 gap-6 lg:grid-cols-2">
			{#if recurring}
				<RecurringPanel data={recurring} />
			{/if}
			{#if largeTransactions}
				<LargeTransactionsList data={largeTransactions} />
			{/if}
		</div>

		<!-- Composition over time -->
		{#if importanceTrend}
			<ImportanceTrendChart data={importanceTrend} />
		{/if}
		{#if trends}
			<CategoryTrendChart data={trends} />
		{/if}

		<!-- Merchants + distribution: two-up -->
		<div class="grid grid-cols-1 gap-6 lg:grid-cols-2">
			{#if merchants}
				<TopMerchantsChart merchants={merchants.merchants} />
			{/if}
			{#if distribution}
				<DistributionCard data={distribution} />
			{/if}
		</div>
	{/if}
</section>

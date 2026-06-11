<script lang="ts">
	import { onMount } from 'svelte';
	import { analyticsRepository } from '$lib/repos';
	import { refreshSettings } from '$lib/stores/settings';
	import {
		analyticsPeriod,
		ANALYTICS_PERIODS,
		periodToWindow,
		type AnalyticsPeriod
	} from '$lib/stores/analyticsPeriod';
	import { todayIso } from '$utils/dates';
	import MonthlyTrendChart from '$components/analytics/MonthlyTrendChart.svelte';
	import VerdictHeader from '$components/analytics/VerdictHeader.svelte';
	import AiNarrativeStrip from '$components/analytics/AiNarrativeStrip.svelte';
	import WentUpZone from '$components/analytics/WentUpZone.svelte';
	import SavingsZone from '$components/analytics/SavingsZone.svelte';
	import { TrendingUp } from '@lucide/svelte';
	import type {
		AnalyticsSummary,
		DiagnosisResult,
		MonthlyTotalsResult,
		NarrativeResult,
		SavingsResult
	} from '$types';

	const PERIOD_LABELS: Record<AnalyticsPeriod, string> = {
		'3m': '3M',
		'6m': '6M',
		'12m': '12M',
		all: 'All'
	};

	let summary = $state<AnalyticsSummary | null>(null);
	let monthly = $state<MonthlyTotalsResult | null>(null);
	let diagnosis = $state<DiagnosisResult | null>(null);
	let savings = $state<SavingsResult | null>(null);
	let narrative = $state<NarrativeResult | null>(null);

	let loaded = $state(false);
	let loadError = $state<string | null>(null);

	onMount(() => {
		void refreshSettings();
		void load();
	});

	// One parallel load on mount. The period selector below filters the trend
	// chart CLIENT-SIDE from the all-history monthly totals, so there is no
	// reload on period change (and no request-ordering hazards).
	async function load(): Promise<void> {
		const asOf = todayIso();
		try {
			const [summaryRes, monthlyRes, diagnosisRes, savingsRes, narrativeRes] = await Promise.all([
				analyticsRepository.summary({ asOf }),
				analyticsRepository.monthlyTotals(),
				analyticsRepository.diagnosis(asOf),
				analyticsRepository.savings(asOf),
				analyticsRepository.narrative()
			]);
			summary = summaryRes;
			monthly = monthlyRes;
			diagnosis = diagnosisRes;
			savings = savingsRes;
			narrative = narrativeRes;
			loadError = null;
		} catch (error) {
			loadError = error instanceof Error ? error.message : 'Failed to load analytics.';
		} finally {
			loaded = true;
		}
	}

	const isEmpty = $derived(loaded && summary !== null && summary.transactionCount === 0);

	// Trend chart months, windowed by the persisted period preset.
	const trendMonths = $derived.by(() => {
		if (!monthly) return [];
		const window = periodToWindow($analyticsPeriod);
		if (!window.dateFrom) return monthly.months;
		const fromMonth = window.dateFrom.slice(0, 7);
		return monthly.months.filter((m) => m.month >= fromMonth);
	});

	function selectPeriod(period: AnalyticsPeriod): void {
		analyticsPeriod.set(period);
	}
</script>

<svelte:head>
	<title>Analytics</title>
</svelte:head>

<section class="flex flex-col gap-6">
	<div>
		<h1 class="text-2xl font-bold tracking-tight text-ctp-text">Analytics</h1>
		<p class="text-sm text-ctp-subtext0">What went up, and where you can claw it back.</p>
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
			<span
				class="h-4 w-4 animate-spin rounded-full border-2 border-ctp-surface2 border-t-ctp-accent"
			></span>
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
				Import some transactions and your spending insights will appear here.
			</p>
			<a
				href="/import"
				class="mt-1 inline-flex items-center gap-2 rounded-lg bg-ctp-accent px-4 py-2 text-sm font-semibold text-ctp-on-accent transition-opacity hover:opacity-90"
			>
				Import transactions
			</a>
		</div>
	{:else}
		{#if diagnosis && summary && monthly}
			<VerdictHeader {diagnosis} {summary} months={monthly.months} />
		{/if}

		<AiNarrativeStrip initial={narrative?.narrative ?? null} />

		{#if diagnosis}
			<WentUpZone {diagnosis} />
		{/if}

		{#if savings}
			<SavingsZone {savings} />
		{/if}

		<!-- Context: spend trend, windowed by the period selector. -->
		{#if monthly}
			<div class="flex flex-col gap-3">
				<div class="flex items-center justify-between gap-3">
					<h2 class="text-xs font-bold uppercase tracking-wider text-ctp-subtext0">Context</h2>
					<div
						class="inline-flex items-center gap-1 rounded-full border border-ctp-surface1 bg-ctp-base p-1 shadow-lg shadow-black/20"
						data-testid="analytics-period-selector"
						role="group"
						aria-label="Select trend period"
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
				<MonthlyTrendChart months={trendMonths} currentMonth={summary?.currentMonth ?? null} />
			</div>
		{/if}
	{/if}
</section>

<script lang="ts">
	import { browser } from '$app/environment';
	import { onDestroy } from 'svelte';
	import { Line } from 'svelte-chartjs';
	import type { ChartData, ChartOptions } from 'chart.js';
	import { chartThemeColors, ensureChartJsRegistered } from '$lib/chart/chartSetup';
	import { settings } from '$lib/stores/settings';
	import { formatMonthLabel } from '$utils/dates';
	import { amountToNumber, formatAmount } from '$utils/money';
	import type { ImportanceTrendResult, ExpenseImportance } from '$types';

	let { data: trend }: { data: ImportanceTrendResult } = $props();

	if (browser) {
		ensureChartJsRegistered();
	}

	let themeVersion = $state(0);
	let themeObserver: MutationObserver | null = null;

	if (browser) {
		themeObserver = new MutationObserver(() => {
			themeVersion++;
		});
		themeObserver.observe(document.documentElement, {
			attributes: true,
			attributeFilter: ['class', 'data-theme']
		});
	}

	onDestroy(() => {
		themeObserver?.disconnect();
		themeObserver = null;
	});

	// Fixed, semantic palette: essential = calm blue, important = warm peach,
	// discretionary = mauve (the "nice-to-have" tier). Stacked bottom→top in
	// this order so the must-pay base sits underneath.
	const TIER_META: Record<
		ExpenseImportance,
		{ label: string; cssVar: string; fallback: string }
	> = {
		essential: { label: 'Essential', cssVar: '--ctp-blue', fallback: '#89b4fa' },
		important: { label: 'Important', cssVar: '--ctp-peach', fallback: '#fab387' },
		discretionary: { label: 'Discretionary', cssVar: '--ctp-mauve', fallback: '#cba6f7' }
	};

	const TIER_ORDER: ExpenseImportance[] = ['essential', 'important', 'discretionary'];

	const labels = $derived(trend.months.map((m) => formatMonthLabel(m)));
	const hasData = $derived(
		trend.series.some((s) => s.points.some((p) => amountToNumber(p.total) > 0))
	);

	const data: ChartData<'line'> = $derived.by(() => {
		void themeVersion;
		const s = browser ? getComputedStyle(document.documentElement) : null;
		const byTier = new Map(trend.series.map((series) => [series.importance, series]));
		return {
			labels,
			datasets: TIER_ORDER.map((tier) => {
				const meta = TIER_META[tier];
				const series = byTier.get(tier);
				const color = s?.getPropertyValue(meta.cssVar).trim() || meta.fallback;
				const points = series ? series.points.map((p) => amountToNumber(p.total)) : [];
				return {
					label: meta.label,
					data: points,
					borderColor: color,
					backgroundColor: color + '55',
					fill: true,
					tension: 0.3,
					pointRadius: 0,
					pointHoverRadius: 4,
					pointHitRadius: 8,
					borderWidth: 2
				};
			})
		};
	});

	const options: ChartOptions<'line'> = $derived.by(() => {
		void themeVersion;
		const theme = chartThemeColors();
		const currency = $settings.currency;
		return {
			responsive: true,
			maintainAspectRatio: false,
			interaction: { mode: 'index', intersect: false },
			plugins: {
				legend: {
					position: 'bottom',
					labels: { color: theme.legend, boxWidth: 12, usePointStyle: true, pointStyle: 'circle' }
				},
				tooltip: {
					callbacks: {
						label: (ctx) => `${ctx.dataset.label}: ${formatAmount(ctx.parsed.y ?? 0, currency)}`
					}
				}
			},
			scales: {
				x: {
					stacked: true,
					ticks: { color: theme.tick, maxTicksLimit: 8 },
					grid: { color: theme.grid }
				},
				y: {
					stacked: true,
					beginAtZero: true,
					ticks: { color: theme.tick },
					grid: { color: theme.grid }
				}
			}
		};
	});
</script>

<div
	class="rounded-xl border border-ctp-surface1 bg-ctp-base p-4 shadow-lg shadow-black/20 sm:p-5"
	data-testid="analytics-importance-trend"
>
	<h2 class="mb-1 text-base font-semibold text-ctp-text">Spend by importance</h2>
	<p class="mb-4 text-xs text-ctp-subtext0">
		How your essential, important, and discretionary spend stacks up over time.
	</p>
	<div class="h-72 w-full">
		{#if !hasData}
			<div class="flex h-full items-center justify-center text-sm text-ctp-overlay1">
				No spend recorded for this period yet.
			</div>
		{:else if browser}
			<Line {data} {options} />
		{/if}
	</div>
</div>

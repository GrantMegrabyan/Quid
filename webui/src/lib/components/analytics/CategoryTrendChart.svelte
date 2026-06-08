<script lang="ts">
	import { browser } from '$app/environment';
	import { onDestroy } from 'svelte';
	import { Line } from 'svelte-chartjs';
	import type { ChartData, ChartOptions } from 'chart.js';
	import { chartThemeColors, ensureChartJsRegistered } from '$lib/chart/chartSetup';
	import { settings } from '$lib/stores/settings';
	import { formatMonthLabel } from '$utils/dates';
	import { amountToNumber, formatAmount } from '$utils/money';
	import type { CategoryTrendsResult } from '$types';

	let { data: trends }: { data: CategoryTrendsResult } = $props();

	const MAX_SERIES = 8;

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

	const visibleSeries = $derived(trends.series.slice(0, MAX_SERIES));
	const truncated = $derived(trends.series.length > MAX_SERIES);
	const hasData = $derived(
		visibleSeries.some((s) => s.points.some((p) => amountToNumber(p.total) > 0))
	);
	const labels = $derived(trends.months.map((m) => formatMonthLabel(m)));

	const data: ChartData<'line'> = $derived({
		labels,
		datasets: visibleSeries.map((series) => ({
			label: series.categoryName,
			data: series.points.map((p) => amountToNumber(p.total)),
			borderColor: series.color,
			backgroundColor: series.color + '66',
			tension: 0.3,
			pointRadius: 0,
			pointHoverRadius: 4,
			pointHitRadius: 8,
			borderWidth: 1.5,
			// Stacked composition: each series fills down to the one below it.
			fill: true
		}))
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
	data-testid="analytics-category-trend"
>
	<h2 class="mb-1 text-base font-semibold text-ctp-text">Category composition</h2>
	<p class="mb-4 text-xs text-ctp-subtext0">
		How your spend splits across top categories over time{truncated ? ' (rest grouped as Other)' : ''}.
	</p>
	<div class="h-80 w-full">
		{#if !hasData}
			<div class="flex h-full items-center justify-center text-sm text-ctp-overlay1">
				No category spend recorded for this period yet.
			</div>
		{:else if browser}
			<Line {data} {options} />
		{/if}
	</div>
</div>

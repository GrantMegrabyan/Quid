<script lang="ts">
	import { browser } from '$app/environment';
	import { onDestroy } from 'svelte';
	import { Line } from 'svelte-chartjs';
	import type { ChartData, ChartOptions } from 'chart.js';
	import { chartThemeColors, ensureChartJsRegistered } from '$lib/chart/chartSetup';
	import { settings } from '$lib/stores/settings';
	import { formatMonthLabel } from '$utils/dates';
	import { amountToNumber, formatAmount } from '$utils/money';
	import type { MonthlyTotal } from '$types';

	let { months }: { months: MonthlyTotal[] } = $props();

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

	const hasData = $derived(months.some((m) => amountToNumber(m.total) > 0));
	const labels = $derived(months.map((m) => formatMonthLabel(m.month)));
	const values = $derived(months.map((m) => amountToNumber(m.total)));

	const data: ChartData<'line'> = $derived.by(() => {
		void themeVersion;
		const s = browser ? getComputedStyle(document.documentElement) : null;
		const accent = s?.getPropertyValue('--ctp-accent').trim() || '#a6e3a1';
		return {
			labels,
			datasets: [
				{
					label: 'Monthly spend',
					data: values,
					borderColor: accent,
					backgroundColor: accent + '26',
					fill: true,
					tension: 0.3,
					pointRadius: 3,
					pointHoverRadius: 5,
					pointBackgroundColor: accent,
					borderWidth: 2
				}
			]
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
				legend: { display: false },
				tooltip: {
					callbacks: {
						label: (ctx) => formatAmount(ctx.parsed.y ?? 0, currency)
					}
				}
			},
			scales: {
				x: {
					ticks: { color: theme.tick, maxTicksLimit: 8 },
					grid: { color: theme.grid }
				},
				y: {
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
	data-testid="analytics-monthly-trend"
>
	<h2 class="mb-1 text-base font-semibold text-ctp-text">Monthly spend</h2>
	<p class="mb-4 text-xs text-ctp-subtext0">Total spend per month over the selected period.</p>
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

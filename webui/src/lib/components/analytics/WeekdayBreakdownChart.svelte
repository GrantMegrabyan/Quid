<script lang="ts">
	import { browser } from '$app/environment';
	import { onDestroy } from 'svelte';
	import { Bar } from 'svelte-chartjs';
	import type { ChartData, ChartOptions } from 'chart.js';
	import { chartThemeColors, ensureChartJsRegistered } from '$lib/chart/chartSetup';
	import { settings } from '$lib/stores/settings';
	import { amountToNumber, formatAmount } from '$utils/money';
	import type { WeekdayBreakdownPoint } from '$types';

	let { breakdown }: { breakdown: WeekdayBreakdownPoint[] } = $props();

	const WEEKDAY_LABELS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

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

	// Map by weekday index so we render Mon..Sun regardless of array order.
	const values = $derived.by(() => {
		const byDay = new Map(breakdown.map((b) => [b.weekday, amountToNumber(b.total)]));
		return WEEKDAY_LABELS.map((_, index) => byDay.get(index) ?? 0);
	});
	const hasData = $derived(values.some((v) => v > 0));
	const maxValue = $derived(Math.max(...values, 0));

	const data: ChartData<'bar'> = $derived.by(() => {
		void themeVersion;
		const s = browser ? getComputedStyle(document.documentElement) : null;
		const mauve = s?.getPropertyValue('--ctp-mauve').trim() || '#cba6f7';
		const accent = s?.getPropertyValue('--ctp-accent').trim() || '#a6e3a1';
		return {
			labels: WEEKDAY_LABELS,
			datasets: [
				{
					label: 'Spend',
					data: values,
					// Highlight the heaviest day with the accent colour.
					backgroundColor: values.map((v) =>
						v > 0 && v === maxValue ? accent : mauve + 'cc'
					),
					borderRadius: 6,
					borderSkipped: false,
					maxBarThickness: 40
				}
			]
		};
	});

	const options: ChartOptions<'bar'> = $derived.by(() => {
		void themeVersion;
		const theme = chartThemeColors();
		const currency = $settings.currency;
		return {
			responsive: true,
			maintainAspectRatio: false,
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
					ticks: { color: theme.tick },
					grid: { display: false }
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
	data-testid="analytics-weekday"
>
	<h2 class="mb-1 text-base font-semibold text-ctp-text">Spend by weekday</h2>
	<p class="mb-4 text-xs text-ctp-subtext0">Which days you tend to spend the most.</p>
	<div class="h-72 w-full">
		{#if !hasData}
			<div class="flex h-full items-center justify-center text-sm text-ctp-overlay1">
				No spend recorded for this period yet.
			</div>
		{:else if browser}
			<Bar {data} {options} />
		{/if}
	</div>
</div>

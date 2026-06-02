<script lang="ts">
	import { browser } from '$app/environment';
	import { onDestroy } from 'svelte';
	import { Bar } from 'svelte-chartjs';
	import type { ChartData, ChartOptions } from 'chart.js';
	import { chartThemeColors, ensureChartJsRegistered } from '$lib/chart/chartSetup';
	import { settings } from '$lib/stores/settings';
	import { amountToNumber, formatAmount } from '$utils/money';
	import type { TopMerchant } from '$types';

	let { merchants }: { merchants: TopMerchant[] } = $props();

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

	const hasData = $derived(merchants.some((m) => amountToNumber(m.total) > 0));
	const labels = $derived(merchants.map((m) => m.merchant));
	const values = $derived(merchants.map((m) => amountToNumber(m.total)));

	const data: ChartData<'bar'> = $derived.by(() => {
		void themeVersion;
		const s = browser ? getComputedStyle(document.documentElement) : null;
		const blue = s?.getPropertyValue('--ctp-blue').trim() || '#89b4fa';
		return {
			labels,
			datasets: [
				{
					label: 'Spend',
					data: values,
					backgroundColor: blue + 'cc',
					hoverBackgroundColor: blue,
					borderRadius: 6,
					borderSkipped: false,
					barThickness: 'flex',
					maxBarThickness: 26
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
			indexAxis: 'y',
			plugins: {
				legend: { display: false },
				tooltip: {
					callbacks: {
						label: (ctx) => formatAmount(ctx.parsed.x ?? 0, currency)
					}
				}
			},
			scales: {
				x: {
					beginAtZero: true,
					ticks: { color: theme.tick },
					grid: { color: theme.grid }
				},
				y: {
					ticks: { color: theme.tick },
					grid: { display: false }
				}
			}
		};
	});
</script>

<div
	class="rounded-xl border border-ctp-surface1 bg-ctp-base p-4 shadow-lg shadow-black/20 sm:p-5"
	data-testid="analytics-top-merchants"
>
	<h2 class="mb-1 text-base font-semibold text-ctp-text">Top merchants</h2>
	<p class="mb-4 text-xs text-ctp-subtext0">Where the most money went this period.</p>
	<div class="h-72 w-full">
		{#if !hasData}
			<div class="flex h-full items-center justify-center text-sm text-ctp-overlay1">
				No merchant spend recorded for this period yet.
			</div>
		{:else if browser}
			<Bar {data} {options} />
		{/if}
	</div>
</div>

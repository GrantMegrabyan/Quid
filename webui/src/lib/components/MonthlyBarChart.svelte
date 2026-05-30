<script lang="ts">
	import { browser } from '$app/environment';
	import { onDestroy } from 'svelte';
	import { Bar } from 'svelte-chartjs';
	import type { ChartData, ChartOptions } from 'chart.js';
	import { chartThemeColors, ensureChartJsRegistered } from '$lib/chart/chartSetup';
	import { expenses } from '$lib/stores/expenses';
	import { selectedMonth } from '$lib/stores/ui';
	import { centered12MonthWindow, formatMonthLabel, monthKey } from '$utils/dates';
	import { amountToNumber } from '$utils/money';

	if (browser) {
		ensureChartJsRegistered();
	}

	const monthKeys = $derived(centered12MonthWindow($selectedMonth));
	const labels = $derived(monthKeys.map(formatMonthLabel));

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

	const totals = $derived.by(() => {
		const buckets = new Map<string, number>(monthKeys.map((key) => [key, 0]));
		for (const expense of $expenses) {
			const key = monthKey(expense.date);
			if (buckets.has(key)) {
				buckets.set(key, (buckets.get(key) ?? 0) + amountToNumber(expense.amount));
			}
		}
		return monthKeys.map((key) => buckets.get(key) ?? 0);
	});

	const data: ChartData<'bar'> = $derived.by(() => {
		void themeVersion;
		const s = getComputedStyle(document.documentElement);
		const blue = s.getPropertyValue('--ctp-blue').trim() || '#89b4fa';
		return {
			labels,
			datasets: [
				{
					label: 'Monthly total',
					data: totals,
					backgroundColor: blue,
					borderRadius: 4,
					maxBarThickness: 28
				}
			]
		};
	});

	const options: ChartOptions<'bar'> = $derived.by(() => {
		void themeVersion;
		const theme = chartThemeColors();
		return {
			responsive: true,
			maintainAspectRatio: false,
			plugins: {
				legend: { display: false }
			},
			scales: {
				x: {
					ticks: { color: theme.tick },
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

<div data-testid="monthly-chart" class="h-64 w-full">
	{#if browser}
		<Bar {data} {options} />
	{/if}
</div>

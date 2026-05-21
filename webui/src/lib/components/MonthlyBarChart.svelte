<script lang="ts">
	import { browser } from '$app/environment';
	import { onDestroy } from 'svelte';
	import { Bar } from 'svelte-chartjs';
	import type { ChartData, ChartOptions } from 'chart.js';
	import { chartThemeColors, ensureChartJsRegistered } from '$lib/chart/chartSetup';
	import { expenses } from '$lib/stores/expenses';
	import { selectedMonth } from '$lib/stores/ui';
	import { centered12MonthWindow, formatMonthLabel, monthKey } from '$utils/dates';

	if (browser) {
		ensureChartJsRegistered();
	}

	const monthKeys = $derived(centered12MonthWindow($selectedMonth));
	const labels = $derived(monthKeys.map(formatMonthLabel));

	let isDark = $state(browser && document.documentElement.classList.contains('dark'));

	let themeObserver: MutationObserver | null = null;

	if (browser) {
		themeObserver = new MutationObserver(() => {
			const next = document.documentElement.classList.contains('dark');
			if (next !== isDark) {
				isDark = next;
			}
		});
		themeObserver.observe(document.documentElement, {
			attributes: true,
			attributeFilter: ['class']
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
				buckets.set(key, (buckets.get(key) ?? 0) + expense.amount);
			}
		}
		return monthKeys.map((key) => buckets.get(key) ?? 0);
	});

	const data: ChartData<'bar'> = $derived({
		labels,
		datasets: [
			{
				label: 'Monthly total',
				data: totals,
				backgroundColor: isDark ? '#60a5fa' : '#2563eb',
				borderRadius: 4,
				maxBarThickness: 28
			}
		]
	});

	const options: ChartOptions<'bar'> = $derived.by(() => {
		const theme = chartThemeColors(isDark);
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

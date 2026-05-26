<script lang="ts">
	import { browser } from '$app/environment';
	import { onDestroy } from 'svelte';
	import { Bar } from 'svelte-chartjs';
	import type { ChartData, ChartOptions } from 'chart.js';
	import { chartThemeColors, ensureChartJsRegistered } from '$lib/chart/chartSetup';
	import { categories } from '$lib/stores/categories';
	import { expenses } from '$lib/stores/expenses';
	import { selectedMonth } from '$lib/stores/ui';
	import { centered12MonthWindow, formatMonthLabel, monthKey } from '$utils/dates';

	let { selectedCategoryIds = [] as string[] }: { selectedCategoryIds?: string[] } = $props();

	if (browser) {
		ensureChartJsRegistered();
	}

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

	const monthKeys = $derived(centered12MonthWindow($selectedMonth));
	const labels = $derived(monthKeys.map(formatMonthLabel));
	const selectedSet = $derived(new Set(selectedCategoryIds));

	const visibleCategories = $derived(
		$categories.filter((category) => selectedSet.has(category.id))
	);

	const datasets = $derived.by(() => {
		const monthIndex = new Map(monthKeys.map((key, idx) => [key, idx]));
		return visibleCategories.map((category) => {
			const totals = new Array<number>(monthKeys.length).fill(0);
			for (const expense of $expenses) {
				if (expense.categoryId !== category.id) continue;
				const idx = monthIndex.get(monthKey(expense.date));
				if (idx === undefined) continue;
				totals[idx] += expense.amount;
			}
			return {
				label: category.name,
				data: totals,
				backgroundColor: category.color,
				borderRadius: 4,
				maxBarThickness: 36,
				stack: 'totals'
			};
		});
	});

	const hasData = $derived(
		visibleCategories.length > 0 && datasets.some((dataset) => dataset.data.some((v) => v > 0))
	);

	const data: ChartData<'bar'> = $derived({
		labels,
		datasets
	});

	const options: ChartOptions<'bar'> = $derived.by(() => {
		const theme = chartThemeColors(isDark);
		return {
			responsive: true,
			maintainAspectRatio: false,
			interaction: {
				mode: 'index',
				intersect: false
			},
			plugins: {
				legend: {
					position: 'top',
					labels: { color: theme.legend, boxWidth: 14, boxHeight: 14 }
				},
				tooltip: {
					enabled: true,
					mode: 'index',
					intersect: false
				}
			},
			scales: {
				x: {
					stacked: true,
					ticks: { color: theme.tick },
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

<div data-testid="category-monthly-chart" class="h-72 w-full">
	{#if visibleCategories.length === 0}
		<div class="flex h-full items-center justify-center text-sm text-gray-500 dark:text-gray-400">
			Pick one or more categories to see monthly totals.
		</div>
	{:else if !hasData}
		<div class="flex h-full items-center justify-center text-sm text-gray-500 dark:text-gray-400">
			No expenses recorded for the selected categories in this window.
		</div>
	{:else if browser}
		<Bar {data} {options} />
	{/if}
</div>

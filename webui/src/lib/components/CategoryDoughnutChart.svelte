<script lang="ts">
	import { browser } from '$app/environment';
	import { onDestroy } from 'svelte';
	import { Doughnut } from 'svelte-chartjs';
	import type { ChartData, ChartOptions } from 'chart.js';
	import { chartThemeColors, ensureChartJsRegistered } from '$lib/chart/chartSetup';
	import { expenses } from '$lib/stores/expenses';
	import { categories } from '$lib/stores/categories';
	import { selectedMonth } from '$lib/stores/ui';
	import { UNCATEGORIZED_COLOR } from '$utils/categoryColor';
	import { monthKey } from '$utils/dates';

	if (browser) {
		ensureChartJsRegistered();
	}

	const FALLBACK_LABEL = 'Uncategorized';

	let themeVersion = $state(0);
	let isWide = $state(browser && window.matchMedia('(min-width: 768px)').matches);

	let themeObserver: MutationObserver | null = null;
	let widthQuery: MediaQueryList | null = null;

	function handleWidthChange(event: MediaQueryListEvent) {
		isWide = event.matches;
	}

	if (browser) {
		themeObserver = new MutationObserver(() => {
			themeVersion++;
		});
		themeObserver.observe(document.documentElement, {
			attributes: true,
			attributeFilter: ['class', 'data-theme']
		});

		widthQuery = window.matchMedia('(min-width: 768px)');
		widthQuery.addEventListener('change', handleWidthChange);
	}

	onDestroy(() => {
		themeObserver?.disconnect();
		themeObserver = null;
		widthQuery?.removeEventListener('change', handleWidthChange);
		widthQuery = null;
	});

	const slices = $derived.by(() => {
		const totals = new Map<string, number>();
		for (const expense of $expenses) {
			if (monthKey(expense.date) !== $selectedMonth) continue;
			totals.set(expense.categoryId, (totals.get(expense.categoryId) ?? 0) + expense.amount);
		}

		const byId = new Map($categories.map((category) => [category.id, category]));
		const rows: Array<{ label: string; color: string; total: number }> = [];
		for (const [categoryId, total] of totals) {
			if (total === 0) continue;
			const category = byId.get(categoryId);
			rows.push({
				label: category?.name ?? FALLBACK_LABEL,
				color: category?.color ?? UNCATEGORIZED_COLOR,
				total
			});
		}
		return rows;
	});

	const data: ChartData<'doughnut'> = $derived({
		labels: slices.map((slice) => slice.label),
		datasets: [
			{
				data: slices.map((slice) => slice.total),
				backgroundColor: slices.map((slice) => slice.color),
				borderWidth: 0
			}
		]
	});

	const options: ChartOptions<'doughnut'> = $derived.by(() => {
		void themeVersion;
		const theme = chartThemeColors();
		return {
			responsive: true,
			maintainAspectRatio: false,
			plugins: {
				legend: {
					position: isWide ? 'right' : 'bottom',
					labels: { color: theme.legend }
				}
			}
		};
	});
</script>

<div data-testid="category-chart" class="h-64 w-full">
	{#if slices.length === 0}
		<div class="flex h-full w-full items-center justify-center text-sm text-ctp-overlay1">
			No expenses for this month — chart will populate as you add them.
		</div>
	{:else if browser}
		<Doughnut {data} {options} />
	{/if}
</div>

<script lang="ts">
	import { browser } from '$app/environment';
	import { onDestroy } from 'svelte';
	import { Line } from 'svelte-chartjs';
	import type { ChartData, ChartOptions } from 'chart.js';
	import { chartThemeColors, ensureChartJsRegistered } from '$lib/chart/chartSetup';
	import { expenses } from '$lib/stores/expenses';
	import { selectedMonth } from '$lib/stores/ui';
	import { currentMonthKey, daysInMonth, monthKey, todayIso } from '$utils/dates';

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

	const dailyTotals = $derived.by(() => {
		const days = daysInMonth($selectedMonth);
		const totals = Array.from({ length: days }, () => 0);

		for (const expense of $expenses) {
			if (monthKey(expense.date) === $selectedMonth) {
				const day = Number(expense.date.slice(8, 10));
				if (Number.isInteger(day) && day >= 1 && day <= days) {
					totals[day - 1] += expense.amount;
				}
			}
		}

		const isCurrentMonth = $selectedMonth === currentMonthKey();
		const cutoffDay = isCurrentMonth ? Number(todayIso().slice(8, 10)) : days;

		let runningTotal = 0;
		return totals.map((amount, index) => {
			runningTotal += amount;
			return index + 1 <= cutoffDay ? runningTotal : null;
		});
	});

	const total = $derived(
		dailyTotals.reduce<number>((acc, value) => (value === null ? acc : value), 0)
	);
	const labels = $derived(
		Array.from({ length: daysInMonth($selectedMonth) }, (_, index) => String(index + 1))
	);

	const data: ChartData<'line'> = $derived({
		labels,
		datasets: [
			{
				label: 'Cumulative expenses',
				data: dailyTotals,
				borderColor: isDark ? '#60a5fa' : '#2563eb',
				backgroundColor: isDark ? 'rgba(96, 165, 250, 0.14)' : 'rgba(37, 99, 235, 0.12)',
				fill: true,
				tension: 0.28,
				pointRadius: 0,
				pointHitRadius: 8,
				borderWidth: 2,
				spanGaps: false
			}
		]
	});

	const options: ChartOptions<'line'> = $derived.by(() => {
		const theme = chartThemeColors(isDark);
		return {
			responsive: true,
			maintainAspectRatio: false,
			plugins: {
				legend: { display: false }
			},
			scales: {
				x: {
					ticks: {
						color: theme.tick,
						maxTicksLimit: 6
					},
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

<div data-testid="cumulative-chart" class="h-72 w-full">
	{#if total === 0}
		<div class="flex h-full items-center justify-center text-sm text-gray-500 dark:text-gray-400">
			No expenses recorded for this month yet.
		</div>
	{:else if browser}
		<Line {data} {options} />
	{/if}
</div>

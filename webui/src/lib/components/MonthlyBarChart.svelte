<script lang="ts">
	import { onDestroy } from 'svelte';
	import { browser } from '$app/environment';
	import { Chart, type ChartData, type ChartOptions } from 'chart.js';
	import { ensureChartJsRegistered, chartThemeColors } from '$lib/chart/chartSetup';
	import { expenses } from '$lib/stores/expenses';
	import { settings } from '$lib/stores/settings';
	import { resolvedPeriod } from '$lib/stores/ui';
	import { currentMonthKey, formatMonthLabel, monthKey } from '$utils/dates';
	import { monthsInRange } from '$utils/period';
	import { amountToNumber, formatAmount } from '$utils/money';

	/**
	 * Spend per month across a multi-month window — the period-mode counterpart
	 * to the single month's cumulative line. The month still in progress is
	 * drawn hollow so a partial bar is never read as a real drop.
	 */
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

	const months = $derived(monthsInRange($resolvedPeriod.from, $resolvedPeriod.to));

	const totals = $derived.by(() => {
		const byMonth = new Map(months.map((month) => [month, 0]));
		for (const expense of $expenses) {
			const key = monthKey(expense.date);
			const current = byMonth.get(key);
			if (current !== undefined) byMonth.set(key, current + amountToNumber(expense.amount));
		}
		return months.map((month) => byMonth.get(month) ?? 0);
	});

	const labels = $derived(months.map((month) => formatMonthLabel(month)));
	const inProgressIndex = $derived(months.indexOf(currentMonthKey()));

	const data: ChartData<'bar'> = $derived.by(() => {
		void themeVersion;
		const styles = browser ? getComputedStyle(document.documentElement) : null;
		const fill = styles?.getPropertyValue('--ctp-chart-1').trim() || '#355c4c';
		const inProgress = inProgressIndex;
		return {
			labels,
			datasets: [
				{
					label: 'Spend',
					data: totals,
					backgroundColor: totals.map((_, index) =>
						index === inProgress ? fill + '33' : fill
					),
					borderColor: fill,
					borderWidth: totals.map((_, index) => (index === inProgress ? 1.5 : 0)),
					borderRadius: 3,
					maxBarThickness: 44
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
						label: (context) => formatAmount(context.parsed.y ?? 0, currency)
					}
				}
			},
			scales: {
				x: { ticks: { color: theme.tick, maxRotation: 0, autoSkipPadding: 12 }, grid: { display: false } },
				y: { beginAtZero: true, ticks: { color: theme.tick }, grid: { color: theme.grid } }
			}
		};
	});

	let canvas: HTMLCanvasElement | null = $state(null);
	let chart: Chart<'bar'> | null = null;

	$effect(() => {
		if (!canvas) return;
		const instance = new Chart(canvas, { type: 'bar', data, options });
		chart = instance;
		return () => {
			instance.destroy();
			chart = null;
		};
	});
</script>

<div data-testid="monthly-bar-chart" class="relative h-72 w-full">
	<canvas bind:this={canvas} aria-label="Spend per month"></canvas>
</div>

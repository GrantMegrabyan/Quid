<script lang="ts">
	import { browser } from '$app/environment';
	import { onDestroy } from 'svelte';
	import { Line } from 'svelte-chartjs';
	import type { Chart, ChartData, ChartOptions } from 'chart.js';
	import { chartThemeColors, ensureChartJsRegistered } from '$lib/chart/chartSetup';
	import { expenses } from '$lib/stores/expenses';
	import { settings } from '$lib/stores/settings';
	import { selectedMonth } from '$lib/stores/ui';
	import { currentMonthKey, daysInMonth, monthKey, todayIso } from '$utils/dates';
	import { formatAmount } from '$utils/money';

	if (browser) {
		ensureChartJsRegistered();
	}

	let isDark = $state(browser && document.documentElement.classList.contains('dark'));
	let themeObserver: MutationObserver | null = null;
	let chart: Chart<'line'> | null = $state(null);
	let activeTooltip:
		| { x: number; y: number; date: string; daily: string; cumulative: string }
		| null = $state(null);

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

	const dailyAmounts = $derived.by(() => {
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

		return totals.map((amount, index) => (index + 1 <= cutoffDay ? amount : null));
	});

	const cumulativeTotals = $derived.by(() => {
		let runningTotal = 0;
		return dailyAmounts.map((amount) => {
			if (amount === null) return null;
			runningTotal += amount;
			return runningTotal;
		});
	});

	const total = $derived(
		cumulativeTotals.reduce<number>((acc, value) => (value === null ? acc : value), 0)
	);
	const labels = $derived(
		Array.from({ length: daysInMonth($selectedMonth) }, (_, index) => String(index + 1))
	);

	function ordinal(day: number): string {
		if (day >= 11 && day <= 13) return `${day}th`;
		const lastDigit = day % 10;
		if (lastDigit === 1) return `${day}st`;
		if (lastDigit === 2) return `${day}nd`;
		if (lastDigit === 3) return `${day}rd`;
		return `${day}th`;
	}

	function tooltipDate(index: number): string {
		const [yearPart, monthPart] = $selectedMonth.split('-');
		const year = Number(yearPart);
		const month = Number(monthPart);
		const day = index + 1;

		if (!Number.isFinite(year) || !Number.isFinite(month)) {
			return `Day ${day}`;
		}

		const monthName = new Intl.DateTimeFormat('en-US', { month: 'long' }).format(
			new Date(year, month - 1, day)
		);
		return `${monthName} ${ordinal(day)}, ${year}`;
	}

	function handlePointerMove(event: PointerEvent): void {
		if (!chart) return;

		const canvasRect = chart.canvas.getBoundingClientRect();
		const chartArea = chart.chartArea;
		const xInCanvas = event.clientX - canvasRect.left;
		const yInCanvas = event.clientY - canvasRect.top;

		if (
			xInCanvas < chartArea.left ||
			xInCanvas > chartArea.right ||
			yInCanvas < chartArea.top ||
			yInCanvas > chartArea.bottom
		) {
			activeTooltip = null;
			return;
		}

		const rawIndex = chart.scales.x.getValueForPixel(xInCanvas);
		const dataIndex = Math.round(Number(rawIndex));
		const cumulative = cumulativeTotals[dataIndex];

		if (!Number.isInteger(dataIndex) || dataIndex < 0 || cumulative === null) {
			activeTooltip = null;
			return;
		}

		const wrapperRect = (event.currentTarget as HTMLElement).getBoundingClientRect();
		const tooltipWidth = 172;
		const x = Math.min(
			Math.max(event.clientX - wrapperRect.left + 14, 12),
			wrapperRect.width - tooltipWidth - 12
		);

		activeTooltip = {
			x,
			y: 12,
			date: tooltipDate(dataIndex),
			daily: formatAmount(dailyAmounts[dataIndex] ?? 0, $settings.currency),
			cumulative: formatAmount(cumulative, $settings.currency)
		};
	}

	const data: ChartData<'line'> = $derived({
		labels,
		datasets: [
			{
				label: 'Cumulative expenses',
				data: cumulativeTotals,
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
			interaction: {
				mode: 'index',
				intersect: false
			},
			plugins: {
				legend: { display: false },
				tooltip: {
					enabled: false
				}
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

<div
	data-testid="cumulative-chart"
	role="img"
	aria-label="Cumulative expenses chart"
	class="relative h-72 w-full"
	onpointermove={handlePointerMove}
	onpointerleave={() => (activeTooltip = null)}
>
	{#if total === 0}
		<div class="flex h-full items-center justify-center text-sm text-gray-500 dark:text-gray-400">
			No expenses recorded for this month yet.
		</div>
	{:else if browser}
		<Line bind:chart {data} {options} />
		{#if activeTooltip}
			<div
				data-testid="cumulative-chart-tooltip"
				class="pointer-events-none absolute z-10 w-[172px] rounded-2xl border border-blue-200/70 bg-white/95 px-3 py-2.5 text-xs shadow-xl shadow-blue-950/10 backdrop-blur dark:border-blue-400/30 dark:bg-gray-950/95 dark:shadow-black/30"
				style:left={`${activeTooltip.x}px`}
				style:top={`${activeTooltip.y}px`}
			>
				<p class="mb-2 font-semibold text-gray-950 dark:text-gray-50">{activeTooltip.date}</p>
				<div class="space-y-1.5 text-gray-700 dark:text-gray-200">
					<div class="flex items-center justify-between gap-3">
						<span aria-label="Day expenses">💳</span>
						<span class="font-semibold tabular-nums">{activeTooltip.daily}</span>
					</div>
					<div class="flex items-center justify-between gap-3">
						<span aria-label="Cumulative expenses">📈</span>
						<span class="font-semibold tabular-nums">{activeTooltip.cumulative}</span>
					</div>
				</div>
			</div>
		{/if}
	{/if}
</div>

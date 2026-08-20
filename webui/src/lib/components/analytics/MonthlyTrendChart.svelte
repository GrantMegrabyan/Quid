<script lang="ts">
	import { browser } from '$app/environment';
	import { onDestroy } from 'svelte';
	import { Line } from 'svelte-chartjs';
	import type { ChartData, ChartOptions } from 'chart.js';
	import { chartThemeColors, ensureChartJsRegistered } from '$lib/chart/chartSetup';
	import { settings } from '$lib/stores/settings';
	import { addMonths, formatMonthLabel } from '$utils/dates';
	import { amountToNumber, formatAmount } from '$utils/money';
	import type { MonthlyTotal } from '$types';

	let {
		months,
		currentMonth = null
	}: { months: MonthlyTotal[]; currentMonth?: string | null } = $props();

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

	// Build a DENSE ascending month spine from the first→last reported month so
	// the line never interpolates across gaps (a missing month reads as £0, not
	// a straight line bridging two distant months).
	type SpinePoint = { month: string; value: number };

	const spine = $derived.by<SpinePoint[]>(() => {
		if (months.length === 0) return [];
		const byMonth = new Map(months.map((m) => [m.month, amountToNumber(m.total)]));
		const keys = months.map((m) => m.month).sort();
		const first = keys[0];
		const last = keys[keys.length - 1];
		const out: SpinePoint[] = [];
		let cursor = first;
		// Guard against pathological input (max ~600 months / 50yr).
		for (let i = 0; i < 600; i++) {
			out.push({ month: cursor, value: byMonth.get(cursor) ?? 0 });
			if (cursor === last) break;
			cursor = addMonths(cursor, 1);
		}
		return out;
	});

	// Trailing 3-month rolling average (inclusive of the current point). Uses
	// only the months available so far so the first points aren't dragged to 0.
	const rollingAvg = $derived.by<number[]>(() =>
		spine.map((_, i) => {
			const start = Math.max(0, i - 2);
			const slice = spine.slice(start, i + 1);
			const sum = slice.reduce((acc, p) => acc + p.value, 0);
			return sum / slice.length;
		})
	);

	const labels = $derived(spine.map((p) => formatMonthLabel(p.month)));
	const values = $derived(spine.map((p) => p.value));
	const hasData = $derived(spine.some((p) => p.value > 0));

	// The last spine month is "in progress" when it matches the supplied
	// currentMonth; we render its point distinctly and dash its trailing segment.
	const inProgressIndex = $derived.by(() => {
		if (!currentMonth || spine.length === 0) return -1;
		return spine[spine.length - 1].month === currentMonth ? spine.length - 1 : -1;
	});
	const hasInProgress = $derived(inProgressIndex >= 0);

	const data: ChartData<'line'> = $derived.by(() => {
		void themeVersion;
		const s = browser ? getComputedStyle(document.documentElement) : null;
		const accent = s?.getPropertyValue('--ctp-accent').trim() || '#a6e3a1';
		// The 3-month average is a supporting series: sage, not a second accent.
		const blue = s?.getPropertyValue('--ctp-chart-2').trim() || '#7e9f8c';
		const inProg = inProgressIndex;
		return {
			labels,
			datasets: [
				{
					label: 'Monthly spend',
					data: values,
					borderColor: accent,
					backgroundColor: accent + '1f',
					fill: true,
					tension: 0.3,
					pointRadius: values.map((_, i) => (i === inProg ? 5 : 3)),
					pointHoverRadius: 5,
					pointBackgroundColor: values.map((_, i) =>
						i === inProg ? 'transparent' : accent
					),
					pointBorderColor: accent,
					pointBorderWidth: 2,
					// Dash the final segment leading into the in-progress month.
					segment: {
						borderDash: (ctx) =>
							inProg >= 0 && ctx.p1DataIndex === inProg ? [6, 4] : undefined
					},
					borderWidth: 2
				},
				{
					label: '3-mo avg',
					data: rollingAvg,
					borderColor: blue,
					backgroundColor: 'transparent',
					fill: false,
					tension: 0.3,
					pointRadius: 0,
					pointHoverRadius: 4,
					pointHitRadius: 6,
					borderDash: [4, 4],
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
				legend: {
					position: 'bottom',
					labels: { color: theme.legend, boxWidth: 12, usePointStyle: true, pointStyle: 'circle' }
				},
				tooltip: {
					callbacks: {
						label: (ctx) => `${ctx.dataset.label}: ${formatAmount(ctx.parsed.y ?? 0, currency)}`
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
	class="card rounded-lg border border-ctp-surface1 bg-ctp-base p-4 sm:p-5"
	data-testid="analytics-monthly-trend"
>
	<h2 class="mb-1 text-base font-semibold text-ctp-text">Monthly spend</h2>
	<p class="mb-4 text-xs text-ctp-subtext0">
		Total per month with a 3-month trailing average.{hasInProgress
			? ' Dashed = month in progress.'
			: ''}
	</p>
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

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

	type SortMode = 'spend' | 'visits';
	let sortMode = $state<SortMode>('spend');

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

	// Re-sort by the active mode; the API sorts by spend, so "visits" needs a
	// local resort.
	const sorted = $derived.by(() =>
		[...merchants].sort((a, b) =>
			sortMode === 'visits' ? b.count - a.count : amountToNumber(b.total) - amountToNumber(a.total)
		)
	);

	const hasData = $derived(
		sortMode === 'visits'
			? sorted.some((m) => m.count > 0)
			: sorted.some((m) => amountToNumber(m.total) > 0)
	);
	const labels = $derived(sorted.map((m) => m.merchant));
	const values = $derived(
		sorted.map((m) => (sortMode === 'visits' ? m.count : amountToNumber(m.total)))
	);

	const data: ChartData<'bar'> = $derived.by(() => {
		void themeVersion;
		const s = browser ? getComputedStyle(document.documentElement) : null;
		const blue = s?.getPropertyValue('--ctp-blue').trim() || '#89b4fa';
		const mauve = s?.getPropertyValue('--ctp-mauve').trim() || '#cba6f7';
		const color = sortMode === 'visits' ? mauve : blue;
		return {
			labels,
			datasets: [
				{
					label: sortMode === 'visits' ? 'Visits' : 'Spend',
					data: values,
					backgroundColor: color + 'cc',
					hoverBackgroundColor: color,
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
		const mode = sortMode;
		const rows = sorted;
		return {
			responsive: true,
			maintainAspectRatio: false,
			indexAxis: 'y',
			plugins: {
				legend: { display: false },
				tooltip: {
					callbacks: {
						label: (ctx) =>
							mode === 'visits'
								? `${ctx.parsed.x ?? 0} visits`
								: formatAmount(ctx.parsed.x ?? 0, currency),
						afterLabel: (ctx) => {
							const m = rows[ctx.dataIndex];
							if (!m) return '';
							const avg = m.count > 0 ? amountToNumber(m.total) / m.count : 0;
							const lines = [`${m.count} ${m.count === 1 ? 'visit' : 'visits'}`];
							if (m.count > 0) {
								lines.push(`avg ${formatAmount(avg, currency)} / visit`);
							}
							return lines;
						}
					}
				}
			},
			scales: {
				x: {
					beginAtZero: true,
					ticks: {
						color: theme.tick,
						precision: mode === 'visits' ? 0 : undefined
					},
					grid: { color: theme.grid }
				},
				y: {
					ticks: { color: theme.tick },
					grid: { display: false }
				}
			}
		};
	});

	const SORT_MODES: { value: SortMode; label: string }[] = [
		{ value: 'spend', label: 'By spend' },
		{ value: 'visits', label: 'By visits' }
	];
</script>

<div
	class="rounded-xl border border-ctp-surface1 bg-ctp-base p-4 shadow-lg shadow-black/20 sm:p-5"
	data-testid="analytics-top-merchants"
>
	<div class="mb-1 flex flex-wrap items-center justify-between gap-2">
		<h2 class="text-base font-semibold text-ctp-text">Top merchants</h2>
		<div
			class="inline-flex items-center gap-1 rounded-full border border-ctp-surface1 bg-ctp-mantle p-0.5"
			role="group"
			aria-label="Sort merchants"
		>
			{#each SORT_MODES as mode (mode.value)}
				{@const active = sortMode === mode.value}
				<button
					type="button"
					data-testid={`analytics-merchants-sort-${mode.value}`}
					aria-pressed={active}
					onclick={() => (sortMode = mode.value)}
					class="rounded-full px-2.5 py-1 text-xs font-medium transition-colors {active
						? 'bg-ctp-accent text-ctp-on-accent shadow-sm'
						: 'text-ctp-subtext0 hover:bg-ctp-surface0/60 hover:text-ctp-text'}"
				>
					{mode.label}
				</button>
			{/each}
		</div>
	</div>
	<p class="mb-4 text-xs text-ctp-subtext0">
		{sortMode === 'visits'
			? 'Where you shop the most often.'
			: 'Where the most money went this period.'}
	</p>
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

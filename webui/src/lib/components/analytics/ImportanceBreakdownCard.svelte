<script lang="ts">
	import { browser } from '$app/environment';
	import { onDestroy } from 'svelte';
	import { Doughnut } from 'svelte-chartjs';
	import type { ChartData, ChartOptions } from 'chart.js';
	import { ensureChartJsRegistered } from '$lib/chart/chartSetup';
	import { settings } from '$lib/stores/settings';
	import { amountToNumber, formatAmount } from '$utils/money';
	import type { ImportanceBreakdownPoint, ExpenseImportance } from '$types';

	let {
		breakdown,
		total
	}: { breakdown: ImportanceBreakdownPoint[]; total: string } = $props();

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

	// Fixed, intentional palette for the three tiers: essential = calm blue,
	// important = warm peach, discretionary = mauve (the "nice-to-have" spend).
	const TIER_META: Record<ExpenseImportance, { label: string; cssVar: string; fallback: string }> = {
		essential: { label: 'Essential', cssVar: '--ctp-blue', fallback: '#89b4fa' },
		important: { label: 'Important', cssVar: '--ctp-peach', fallback: '#fab387' },
		discretionary: { label: 'Discretionary', cssVar: '--ctp-mauve', fallback: '#cba6f7' }
	};

	const TIER_ORDER: ExpenseImportance[] = ['essential', 'important', 'discretionary'];

	const rows = $derived.by(() => {
		void themeVersion;
		const s = browser ? getComputedStyle(document.documentElement) : null;
		const byTier = new Map(breakdown.map((b) => [b.importance, b]));
		return TIER_ORDER.map((tier) => {
			const meta = TIER_META[tier];
			const point = byTier.get(tier);
			const color = (s?.getPropertyValue(meta.cssVar).trim() || meta.fallback) as string;
			return {
				tier,
				label: meta.label,
				color,
				total: amountToNumber(point?.total ?? '0'),
				count: point?.count ?? 0
			};
		});
	});

	const totalNum = $derived(amountToNumber(total));
	const hasData = $derived(rows.some((r) => r.total > 0));

	const data: ChartData<'doughnut'> = $derived({
		labels: rows.map((r) => r.label),
		datasets: [
			{
				data: rows.map((r) => r.total),
				backgroundColor: rows.map((r) => r.color),
				borderWidth: 0,
				hoverOffset: 6
			}
		]
	});

	const options: ChartOptions<'doughnut'> = $derived.by(() => {
		const currency = $settings.currency;
		return {
			responsive: true,
			maintainAspectRatio: false,
			cutout: '62%',
			plugins: {
				legend: { display: false },
				tooltip: {
					callbacks: {
						label: (ctx) => `${ctx.label}: ${formatAmount(ctx.parsed ?? 0, currency)}`
					}
				}
			}
		};
	});

	function pct(value: number): string {
		if (totalNum <= 0) return '0%';
		return `${Math.round((value / totalNum) * 100)}%`;
	}
</script>

<div
	class="rounded-xl border border-ctp-surface1 bg-ctp-base p-4 shadow-lg shadow-black/20 sm:p-5"
	data-testid="analytics-importance"
>
	<h2 class="mb-1 text-base font-semibold text-ctp-text">Spend by importance</h2>
	<p class="mb-4 text-xs text-ctp-subtext0">How essential your spending was this period.</p>

	{#if !hasData}
		<div class="flex h-56 items-center justify-center text-sm text-ctp-overlay1">
			No spend recorded for this period yet.
		</div>
	{:else}
		<div class="flex flex-col items-center gap-5 sm:flex-row sm:items-center">
			<div class="relative h-44 w-44 shrink-0">
				{#if browser}
					<Doughnut {data} {options} />
				{/if}
				<div
					class="pointer-events-none absolute inset-0 flex flex-col items-center justify-center"
				>
					<span class="text-[11px] font-medium uppercase tracking-wide text-ctp-overlay0">Total</span>
					<span class="text-lg font-bold tabular-nums text-ctp-text">
						{formatAmount(total, $settings.currency)}
					</span>
				</div>
			</div>
			<ul class="flex w-full flex-col gap-2">
				{#each rows as row (row.tier)}
					<li class="flex items-center gap-2.5 text-sm" data-testid="analytics-importance-row">
						<span
							class="h-2.5 w-2.5 shrink-0 rounded-full"
							style:background-color={row.color}
						></span>
						<span class="flex-1 text-ctp-subtext0">{row.label}</span>
						<span class="tabular-nums font-medium text-ctp-text">
							{formatAmount(row.total, $settings.currency)}
						</span>
						<span class="w-10 shrink-0 text-right text-xs tabular-nums text-ctp-overlay0">
							{pct(row.total)}
						</span>
					</li>
				{/each}
			</ul>
		</div>
	{/if}
</div>

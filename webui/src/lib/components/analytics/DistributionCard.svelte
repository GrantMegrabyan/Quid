<script lang="ts">
	import { settings } from '$lib/stores/settings';
	import { amountToNumber, formatAmount } from '$utils/money';
	import { Scale } from '@lucide/svelte';
	import type { DistributionResult } from '$types';

	let { data }: { data: DistributionResult } = $props();

	const medianNum = $derived(amountToNumber(data.median));
	const meanNum = $derived(amountToNumber(data.mean));
	const hasData = $derived(data.count > 0);

	const insight = $derived.by(() => {
		const median = formatAmount(data.median, $settings.currency);
		const mean = formatAmount(data.mean, $settings.currency);
		if (medianNum <= 0) {
			return `Across ${data.count} transactions, a typical spend is ${median}.`;
		}
		const ratio = meanNum / medianNum;
		if (ratio >= 1.5) {
			return `Median ${median} · mean ${mean} — a few big buys skew your average up.`;
		}
		if (ratio <= 0.75) {
			return `Median ${median} · mean ${mean} — your spending leans toward larger, steady amounts.`;
		}
		return `Median ${median} · mean ${mean} — your spending is fairly even.`;
	});

	// Position of median between min and max, for the tiny inline bar marker.
	const markerPct = $derived.by(() => {
		const min = amountToNumber(data.min);
		const max = amountToNumber(data.max);
		if (max <= min) return 50;
		const clamped = Math.min(Math.max(medianNum, min), max);
		return ((clamped - min) / (max - min)) * 100;
	});

	const p90Pct = $derived.by(() => {
		const min = amountToNumber(data.min);
		const max = amountToNumber(data.max);
		const p90 = amountToNumber(data.p90);
		if (max <= min) return 50;
		const clamped = Math.min(Math.max(p90, min), max);
		return ((clamped - min) / (max - min)) * 100;
	});
</script>

<div
	class="rounded-xl border border-ctp-surface1 bg-ctp-base p-4 shadow-lg shadow-black/20 sm:p-5"
	data-testid="analytics-distribution"
>
	<div class="mb-4 flex items-start gap-3">
		<span
			class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-ctp-blue/15 text-ctp-blue"
		>
			<Scale class="h-[18px] w-[18px]" />
		</span>
		<div class="min-w-0 flex-1">
			<h2 class="text-base font-semibold text-ctp-text">Transaction sizes</h2>
			<p class="text-xs text-ctp-subtext0">How big a typical purchase is.</p>
		</div>
	</div>

	{#if !hasData}
		<div class="flex h-32 items-center justify-center text-center text-sm text-ctp-overlay1">
			No transactions recorded for this period yet.
		</div>
	{:else}
		<p class="mb-5 text-sm leading-relaxed text-ctp-subtext1">{insight}</p>

		<div class="grid grid-cols-3 gap-3">
			<div class="rounded-lg bg-ctp-surface0/50 p-3 text-center">
				<p class="text-[11px] font-medium uppercase tracking-wide text-ctp-overlay0">Median</p>
				<p class="mt-0.5 text-lg font-bold tabular-nums text-ctp-text">
					{formatAmount(data.median, $settings.currency)}
				</p>
			</div>
			<div class="rounded-lg bg-ctp-surface0/50 p-3 text-center">
				<p class="text-[11px] font-medium uppercase tracking-wide text-ctp-overlay0">Mean</p>
				<p class="mt-0.5 text-lg font-bold tabular-nums text-ctp-text">
					{formatAmount(data.mean, $settings.currency)}
				</p>
			</div>
			<div class="rounded-lg bg-ctp-surface0/50 p-3 text-center">
				<p class="text-[11px] font-medium uppercase tracking-wide text-ctp-overlay0">90th pct</p>
				<p class="mt-0.5 text-lg font-bold tabular-nums text-ctp-text">
					{formatAmount(data.p90, $settings.currency)}
				</p>
			</div>
		</div>

		<!-- min ───●(median)──┊(p90)── max -->
		<div class="mt-5">
			<div class="relative h-1.5 w-full rounded-full bg-ctp-surface1">
				<div
					class="absolute top-1/2 h-3.5 w-1 -translate-x-1/2 -translate-y-1/2 rounded-full bg-ctp-peach/70"
					style:left={`${p90Pct}%`}
					title="90th percentile"
				></div>
				<div
					class="absolute top-1/2 h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full bg-ctp-blue ring-2 ring-ctp-base"
					style:left={`${markerPct}%`}
					title="Median"
				></div>
			</div>
			<div class="mt-1.5 flex justify-between text-[11px] tabular-nums text-ctp-overlay0">
				<span>{formatAmount(data.min, $settings.currency)}</span>
				<span>{formatAmount(data.max, $settings.currency)}</span>
			</div>
		</div>
	{/if}
</div>

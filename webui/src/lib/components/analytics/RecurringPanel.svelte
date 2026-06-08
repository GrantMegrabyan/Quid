<script lang="ts">
	import { settings } from '$lib/stores/settings';
	import { formatAmount } from '$utils/money';
	import { formatMonthLabel } from '$utils/dates';
	import { Repeat } from '@lucide/svelte';
	import type { RecurringResult } from '$types';

	let { data }: { data: RecurringResult } = $props();

	const hasData = $derived(data.items.length > 0);

	const headerLine = $derived.by(() => {
		const monthly = formatAmount(data.monthlyTotal, $settings.currency);
		const noun = data.count === 1 ? 'item' : 'items';
		return `${monthly}/mo across ${data.count} ${noun}`;
	});

	function span(firstMonth: string, lastMonth: string): string {
		if (firstMonth === lastMonth) return formatMonthLabel(firstMonth);
		return `${formatMonthLabel(firstMonth)} → ${formatMonthLabel(lastMonth)}`;
	}
</script>

<div
	class="rounded-xl border border-ctp-surface1 bg-ctp-base p-4 shadow-lg shadow-black/20 sm:p-5"
	data-testid="analytics-recurring"
>
	<div class="mb-4 flex items-start gap-3">
		<span
			class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-ctp-mauve/15 text-ctp-mauve"
		>
			<Repeat class="h-[18px] w-[18px]" />
		</span>
		<div class="min-w-0 flex-1">
			<h2 class="text-base font-semibold text-ctp-text">Recurring spend</h2>
			{#if hasData}
				<p class="text-xs text-ctp-subtext0">{headerLine}</p>
			{:else}
				<p class="text-xs text-ctp-subtext0">Subscriptions and repeat payments we spotted.</p>
			{/if}
		</div>
	</div>

	{#if !hasData}
		<div
			class="flex h-40 items-center justify-center text-center text-sm text-ctp-overlay1"
			data-testid="analytics-recurring-empty"
		>
			No recurring payments detected for this period yet.
		</div>
	{:else}
		<ul class="flex flex-col divide-y divide-ctp-surface0">
			{#each data.items as item (item.name + '|' + item.amount + '|' + item.firstMonth)}
				<li class="flex items-center gap-3 py-2.5" data-testid="analytics-recurring-row">
					<div class="min-w-0 flex-1">
						<p class="truncate text-sm font-medium text-ctp-text" title={item.name}>
							{item.name}
						</p>
						<p class="text-xs text-ctp-overlay0">
							seen in {item.monthsCovered}
							{item.monthsCovered === 1 ? 'month' : 'months'} ({span(item.firstMonth, item.lastMonth)})
						</p>
					</div>
					<div class="shrink-0 text-right">
						<p class="text-sm font-semibold tabular-nums text-ctp-text">
							{formatAmount(item.monthlyEstimate, $settings.currency)}<span
								class="text-xs font-normal text-ctp-overlay0">/mo</span
							>
						</p>
						<p class="text-xs text-ctp-overlay0 tabular-nums">
							{formatAmount(item.amount, $settings.currency)} × {item.occurrences}
						</p>
					</div>
				</li>
			{/each}
		</ul>
	{/if}
</div>

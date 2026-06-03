<script lang="ts">
	import { settings } from '$lib/stores/settings';
	import { formatAmount } from '$utils/money';
	import { UNCATEGORIZED_COLOR } from '$utils/categoryColor';
	import { Flame } from '@lucide/svelte';
	import type { LargeTransaction, LargeTransactionsResult } from '$types';

	let { data }: { data: LargeTransactionsResult } = $props();

	const hasData = $derived(data.transactions.length > 0);

	const shareLine = $derived.by(() => {
		if (data.topShare === null) return 'Your biggest single purchases this period.';
		const count = data.transactions.length;
		const pct = Math.round(data.topShare * 100);
		return `Your top ${count} were ${pct}% of this period's spend.`;
	});

	function txnName(txn: LargeTransaction): string {
		return txn.displayName || txn.name;
	}

	function formatDate(iso: string): string {
		const [year, month, day] = iso.slice(0, 10).split('-').map(Number);
		const date = new Date(year, month - 1, day);
		return new Intl.DateTimeFormat('en-US', {
			day: 'numeric',
			month: 'short',
			year: 'numeric'
		}).format(date);
	}
</script>

<div
	class="rounded-xl border border-ctp-surface1 bg-ctp-base p-4 shadow-lg shadow-black/20 sm:p-5"
	data-testid="analytics-large-transactions"
>
	<div class="mb-4 flex items-start gap-3">
		<span
			class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-ctp-peach/15 text-ctp-peach"
		>
			<Flame class="h-[18px] w-[18px]" />
		</span>
		<div class="min-w-0 flex-1">
			<h2 class="text-base font-semibold text-ctp-text">Biggest purchases</h2>
			<p class="text-xs text-ctp-subtext0">{shareLine}</p>
		</div>
	</div>

	{#if !hasData}
		<div
			class="flex h-40 items-center justify-center text-center text-sm text-ctp-overlay1"
			data-testid="analytics-large-empty"
		>
			No transactions recorded for this period yet.
		</div>
	{:else}
		<ul class="flex flex-col divide-y divide-ctp-surface0">
			{#each data.transactions as txn (txn.id)}
				<li class="flex items-center gap-3 py-2.5" data-testid="analytics-large-row">
					<div class="min-w-0 flex-1">
						<p class="truncate text-sm font-medium text-ctp-text" title={txnName(txn)}>
							{txnName(txn)}
						</p>
						<p class="flex items-center gap-1.5 text-xs text-ctp-overlay0">
							<span
								class="h-2 w-2 shrink-0 rounded-full"
								style:background-color={txn.categoryColor || UNCATEGORIZED_COLOR}
							></span>
							<span class="truncate">{txn.categoryName || 'Uncategorized'}</span>
							<span class="text-ctp-overlay1">·</span>
							<span class="shrink-0 tabular-nums">{formatDate(txn.date)}</span>
						</p>
					</div>
					<p class="shrink-0 text-sm font-semibold tabular-nums text-ctp-text">
						{formatAmount(txn.amount, $settings.currency)}
					</p>
				</li>
			{/each}
		</ul>
	{/if}
</div>

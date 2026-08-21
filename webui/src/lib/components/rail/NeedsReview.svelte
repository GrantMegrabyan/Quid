<script lang="ts">
	import { expenses } from '$lib/stores/expenses';
	import { UNCATEGORIZED_ID } from '$lib/types';

	/**
	 * The window's categorisation debt: rows still sitting in Uncategorized, and
	 * rows a machine put where they are (AI or a bare import) and that a human
	 * has never confirmed. Both are answerable from the list below, so this is a
	 * count and a nudge, not another view.
	 */
	type Props = { onreview?: (filter: 'uncategorized' | 'unconfirmed') => void };
	let { onreview }: Props = $props();

	const counts = $derived.by(() => {
		let uncategorized = 0;
		let unconfirmed = 0;
		for (const expense of $expenses) {
			if (expense.categoryId === UNCATEGORIZED_ID) uncategorized += 1;
			const source = expense.categorySource ?? 'import';
			if (source === 'ai' || source === 'import') unconfirmed += 1;
		}
		return { uncategorized, unconfirmed, total: $expenses.length };
	});
</script>

<div class="flex flex-col gap-3" data-testid="needs-review">
	<div class="flex items-baseline gap-2">
		<span class="numeral text-3xl font-bold text-ctp-text">{counts.uncategorized}</span>
		<span class="text-sm text-ctp-subtext0">uncategorised</span>
	</div>
	{#if counts.uncategorized > 0}
		<button
			type="button"
			data-testid="needs-review-uncategorized"
			onclick={() => onreview?.('uncategorized')}
			class="w-fit rounded-md border border-ctp-surface2 px-2.5 py-1 text-xs font-medium text-ctp-subtext0 transition-colors hover:bg-ctp-surface0 hover:text-ctp-text"
		>
			Show them
		</button>
	{:else}
		<p class="text-sm text-ctp-overlay1">Everything in this window has a category.</p>
	{/if}
	<div class="border-t border-ctp-surface1 pt-3 text-sm text-ctp-subtext0">
		<span class="font-semibold tabular-nums text-ctp-text">{counts.unconfirmed}</span>
		of
		<span class="tabular-nums">{counts.total}</span>
		categorised automatically
		{#if counts.unconfirmed > 0}
			<button
				type="button"
				data-testid="needs-review-unconfirmed"
				onclick={() => onreview?.('unconfirmed')}
				class="ml-1 text-ctp-accent underline underline-offset-2 hover:text-ctp-accent-hover"
			>
				review
			</button>
		{/if}
	</div>
</div>

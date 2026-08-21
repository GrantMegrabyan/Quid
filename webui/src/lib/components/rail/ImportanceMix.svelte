<script lang="ts">
	import { expenses } from '$lib/stores/expenses';
	import { settings } from '$lib/stores/settings';
	import { amountToNumber, formatAmount } from '$utils/money';
	import type { ExpenseImportance } from '$lib/types';

	/**
	 * How much of the window was spend you had to make. Quid already classifies
	 * every transaction as essential / important / discretionary; this is the
	 * one place that classification is summed into an answer.
	 */
	const BANDS: { key: ExpenseImportance; label: string; class: string }[] = [
		{ key: 'essential', label: 'Essential', class: 'bg-ctp-chart-1' },
		{ key: 'important', label: 'Important', class: 'bg-ctp-chart-2' },
		{ key: 'discretionary', label: 'Discretionary', class: 'bg-ctp-chart-4' }
	];

	const totals = $derived.by(() => {
		const sums: Record<ExpenseImportance, number> = {
			essential: 0,
			important: 0,
			discretionary: 0
		};
		let all = 0;
		for (const expense of $expenses) {
			const amount = amountToNumber(expense.amount);
			const band = expense.importance ?? 'important';
			sums[band] += amount;
			all += amount;
		}
		return { sums, all };
	});
</script>

{#if totals.all === 0}
	<p class="text-sm text-ctp-overlay1">No transactions in this window.</p>
{:else}
	<div class="flex flex-col gap-3" data-testid="importance-mix">
		<div class="flex h-2.5 w-full overflow-hidden rounded-full bg-ctp-surface1">
			{#each BANDS as band (band.key)}
				{@const share = totals.sums[band.key] / totals.all}
				{#if share > 0}
					<div class={band.class} style="width: {share * 100}%" title={band.label}></div>
				{/if}
			{/each}
		</div>
		<dl class="flex flex-col gap-1.5">
			{#each BANDS as band (band.key)}
				{@const value = totals.sums[band.key]}
				<div class="flex items-baseline justify-between gap-2 text-sm">
					<dt class="flex items-center gap-2 text-ctp-subtext0">
						<span class="h-2 w-2 shrink-0 rounded-full {band.class}"></span>
						{band.label}
					</dt>
					<dd class="tabular-nums text-ctp-text">
						{formatAmount(value, $settings.currency)}
						<span class="ml-1 text-xs text-ctp-overlay1">
							{Math.round((value / totals.all) * 100)}%
						</span>
					</dd>
				</div>
			{/each}
		</dl>
	</div>
{/if}

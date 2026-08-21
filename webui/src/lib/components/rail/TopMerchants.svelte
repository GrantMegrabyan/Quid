<script lang="ts">
	import { expenses } from '$lib/stores/expenses';
	import { settings } from '$lib/stores/settings';
	import { amountToNumber, formatAmount } from '$utils/money';

	/**
	 * Where the money actually goes, by counterparty rather than by category —
	 * the question a category breakdown can't answer ("Eating Out" is a bucket;
	 * "Cafe Fino, eleven times" is a habit).
	 */
	const LIMIT = 6;

	type MerchantRow = { name: string; total: number; count: number; share: number };

	const rows = $derived.by<MerchantRow[]>(() => {
		const totals = new Map<string, { total: number; count: number; label: string }>();
		let grandTotal = 0;
		for (const expense of $expenses) {
			const amount = amountToNumber(expense.amount);
			grandTotal += amount;
			const label = expense.displayName ?? expense.name;
			const key = label.trim().toLowerCase();
			const entry = totals.get(key);
			if (entry) {
				entry.total += amount;
				entry.count += 1;
			} else {
				totals.set(key, { total: amount, count: 1, label });
			}
		}
		return [...totals.values()]
			.sort((a, b) => b.total - a.total)
			.slice(0, LIMIT)
			.map((entry) => ({
				name: entry.label,
				total: entry.total,
				count: entry.count,
				share: grandTotal > 0 ? entry.total / grandTotal : 0
			}));
	});

	const maxTotal = $derived(rows.length > 0 ? rows[0].total : 0);
</script>

{#if rows.length === 0}
	<p class="text-sm text-ctp-overlay1">No transactions in this window.</p>
{:else}
	<ul class="flex flex-col gap-2.5" data-testid="top-merchants">
		{#each rows as row (row.name)}
			<li class="flex flex-col gap-1">
				<div class="flex items-baseline justify-between gap-2">
					<span class="truncate text-sm font-medium text-ctp-text" title={row.name}>{row.name}</span>
					<span class="shrink-0 text-sm font-semibold tabular-nums text-ctp-text">
						{formatAmount(row.total, $settings.currency)}
					</span>
				</div>
				<div class="flex items-center gap-2">
					<div class="h-1 flex-1 overflow-hidden rounded-full bg-ctp-surface1">
						<div
							class="h-full rounded-full bg-ctp-accent/70"
							style="width: {maxTotal > 0 ? (row.total / maxTotal) * 100 : 0}%"
						></div>
					</div>
					<span class="w-20 shrink-0 text-right text-xs tabular-nums text-ctp-overlay1">
						{row.count}
						{row.count === 1 ? 'txn' : 'txns'}
					</span>
				</div>
			</li>
		{/each}
	</ul>
{/if}

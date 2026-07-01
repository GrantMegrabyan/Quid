<script lang="ts">
	import CategoryIcon from '$components/CategoryIcon.svelte';
	import { expenses } from '$lib/stores/expenses';
	import { categories } from '$lib/stores/categories';
	import { settings } from '$lib/stores/settings';
	import { selectedMonth } from '$lib/stores/ui';
	import { UNCATEGORIZED_COLOR } from '$utils/categoryColor';
	import { monthKey } from '$utils/dates';
	import { amountToNumber, formatAmount } from '$utils/money';

	const FALLBACK_LABEL = 'Uncategorized';
	const COLLAPSED_COUNT = 6;

	let showAll = $state(false);

	type BreakdownRow = {
		id: string;
		name: string;
		color: string;
		icon?: string;
		total: number;
		count: number;
		share: number;
	};

	const rows = $derived.by<BreakdownRow[]>(() => {
		const totals = new Map<string, { total: number; count: number }>();
		let monthTotal = 0;
		for (const expense of $expenses) {
			if (monthKey(expense.date) !== $selectedMonth) continue;
			const amount = amountToNumber(expense.amount);
			monthTotal += amount;
			const entry = totals.get(expense.categoryId);
			if (entry) {
				entry.total += amount;
				entry.count += 1;
			} else {
				totals.set(expense.categoryId, { total: amount, count: 1 });
			}
		}

		const byId = new Map($categories.map((category) => [category.id, category]));
		const result: BreakdownRow[] = [];
		for (const [categoryId, { total, count }] of totals) {
			if (total === 0) continue;
			const category = byId.get(categoryId);
			result.push({
				id: categoryId,
				name: category?.name ?? FALLBACK_LABEL,
				color: category?.color ?? UNCATEGORIZED_COLOR,
				icon: category?.icon,
				total,
				count,
				share: monthTotal > 0 ? total / monthTotal : 0
			});
		}
		return result.sort((a, b) => b.total - a.total || a.name.localeCompare(b.name));
	});

	const maxTotal = $derived(rows.length > 0 ? rows[0].total : 0);
	const visibleRows = $derived(showAll ? rows : rows.slice(0, COLLAPSED_COUNT));
	const hiddenCount = $derived(rows.length - COLLAPSED_COUNT);

	// Collapse again when the month changes so a long-tail month doesn't leak
	// its expanded state into the next one.
	$effect(() => {
		void $selectedMonth;
		showAll = false;
	});

	function sharePercent(share: number): string {
		const percent = share * 100;
		return percent > 0 && percent < 1 ? '<1%' : `${Math.round(percent)}%`;
	}
</script>

<div data-testid="category-breakdown">
	{#if rows.length === 0}
		<div class="flex h-48 items-center justify-center text-center text-sm text-ctp-overlay1">
			No expenses for this month — the breakdown will populate as you add them.
		</div>
	{:else}
		<ul class="flex flex-col gap-3">
			{#each visibleRows as row (row.id)}
				<li data-testid="category-breakdown-row" class="flex items-center gap-3">
					<div
						class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-white shadow-sm"
						style="background-color: {row.color};"
						aria-hidden="true"
					>
						<CategoryIcon name={row.icon ?? '•'} size={14} />
					</div>
					<div class="min-w-0 flex-1">
						<div class="flex items-baseline justify-between gap-2">
							<p class="truncate text-sm font-medium text-ctp-text" title={row.name}>{row.name}</p>
							<p class="shrink-0 text-sm font-semibold tabular-nums text-ctp-text">
								{formatAmount(row.total, $settings.currency)}
							</p>
						</div>
						<div class="mt-1 flex items-center gap-2">
							<div class="h-1.5 flex-1 overflow-hidden rounded-full bg-ctp-surface1">
								<div
									class="h-full rounded-full transition-[width] duration-300 ease-out"
									style="width: {maxTotal > 0 ? (row.total / maxTotal) * 100 : 0}%; background-color: {row.color};"
								></div>
							</div>
							<span class="w-9 shrink-0 text-right text-xs tabular-nums text-ctp-overlay1">
								{sharePercent(row.share)}
							</span>
						</div>
					</div>
				</li>
			{/each}
		</ul>
		{#if hiddenCount > 0}
			<button
				type="button"
				data-testid="category-breakdown-toggle"
				onclick={() => (showAll = !showAll)}
				class="mt-3 w-full rounded-md border border-ctp-surface1 px-3 py-1.5 text-xs font-medium text-ctp-subtext0 transition-colors hover:bg-ctp-surface0 hover:text-ctp-text"
			>
				{showAll ? 'Show fewer' : `Show all (${rows.length})`}
			</button>
		{/if}
	{/if}
</div>

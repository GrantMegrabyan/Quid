<script lang="ts">
	import { settings } from '$lib/stores/settings';
	import { amountToNumber, formatAmount } from '$utils/money';
	import { UNCATEGORIZED_COLOR } from '$utils/categoryColor';
	import type { CategoryMover } from '$types';

	let { movers, limit = 8 }: { movers: CategoryMover[]; limit?: number } = $props();

	type MoverView = {
		mover: CategoryMover;
		deltaNum: number;
		currentNum: number;
		isUp: boolean;
		isNew: boolean;
		percentLabel: string | null;
	};

	const rows = $derived.by<MoverView[]>(() =>
		movers.slice(0, limit).map((mover) => {
			const deltaNum = amountToNumber(mover.delta);
			const currentNum = amountToNumber(mover.current);
			const isNew = mover.percentChange === null && currentNum > 0;
			let percentLabel: string | null = null;
			if (mover.percentChange !== null) {
				const sign = mover.percentChange > 0 ? '+' : '';
				percentLabel = `${sign}${Math.round(mover.percentChange)}%`;
			}
			return {
				mover,
				deltaNum,
				currentNum,
				isUp: deltaNum > 0,
				isNew,
				percentLabel
			};
		})
	);

	const hasData = $derived(rows.length > 0);

	function signedAmount(value: number, currency: string): string {
		const formatted = formatAmount(Math.abs(value), currency);
		if (value > 0) return `+${formatted}`;
		if (value < 0) return `-${formatted}`;
		return formatted;
	}
</script>

<div
	class="rounded-xl border border-ctp-surface1 bg-ctp-base p-4 shadow-lg shadow-black/20 sm:p-5"
	data-testid="analytics-movers"
>
	<h2 class="mb-1 text-base font-semibold text-ctp-text">Biggest movers</h2>
	<p class="mb-4 text-xs text-ctp-subtext0">
		Categories that changed the most this month vs last month.
	</p>

	{#if !hasData}
		<div
			class="flex h-40 items-center justify-center text-center text-sm text-ctp-overlay1"
			data-testid="analytics-movers-empty"
		>
			Not enough history yet to compare months.
		</div>
	{:else}
		<ul class="flex flex-col divide-y divide-ctp-surface0">
			{#each rows as row (row.mover.categoryId)}
				<li
					class="flex items-center gap-3 py-2.5"
					data-testid="analytics-mover-row"
					data-category-id={row.mover.categoryId}
				>
					<span
						class="h-2.5 w-2.5 shrink-0 rounded-full ring-2 ring-inset ring-black/10"
						style:background-color={row.mover.color || UNCATEGORIZED_COLOR}
					></span>
					<div class="min-w-0 flex-1">
						<p class="truncate text-sm font-medium text-ctp-text" title={row.mover.categoryName}>
							{row.mover.categoryName}
						</p>
						<p class="text-xs text-ctp-overlay0 tabular-nums">
							{formatAmount(row.mover.previous, $settings.currency)}
							<span class="px-0.5 text-ctp-overlay1">→</span>
							{formatAmount(row.mover.current, $settings.currency)}
						</p>
					</div>
					<div class="shrink-0 text-right">
						{#if row.isNew}
							<span
								class="inline-flex items-center gap-1 rounded-full bg-ctp-green/15 px-2 py-0.5 text-xs font-semibold text-ctp-green"
								data-testid="analytics-mover-badge"
							>
								new
							</span>
						{:else}
							<span
								class="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold tabular-nums {row.isUp
									? 'bg-ctp-red/15 text-ctp-red'
									: 'bg-ctp-green/15 text-ctp-green'}"
								data-testid="analytics-mover-badge"
							>
								<span aria-hidden="true">{row.isUp ? '▲' : '▼'}</span>
								{signedAmount(row.deltaNum, $settings.currency)}
								{#if row.percentLabel}
									<span class="font-normal opacity-80">({row.percentLabel})</span>
								{/if}
							</span>
						{/if}
					</div>
				</li>
			{/each}
		</ul>
	{/if}
</div>

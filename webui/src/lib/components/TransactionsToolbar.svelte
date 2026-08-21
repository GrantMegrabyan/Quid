<script lang="ts">
	import { Search, X } from '@lucide/svelte';
	import FacetedFilter from '$components/FacetedFilter.svelte';
	import type { Category } from '$lib/types';

	/**
	 * The filter bar above the register. Everything that narrows the list lives
	 * here — search, categories, amount band, review status — next to a running
	 * "N of M" count, so the list below is always explained by the controls
	 * above it rather than by remembered state.
	 */
	export type ReviewStatus = 'all' | 'uncategorized' | 'unconfirmed';
	export type TransactionFilter = {
		query: string;
		categories: Set<string>;
		min: string;
		max: string;
		status: ReviewStatus;
	};

	type Props = {
		filter: TransactionFilter;
		onchange: (next: TransactionFilter) => void;
		categories: Category[];
		categoryCounts: Map<string, number>;
		visibleCount: number;
		totalCount: number;
		groupBy: string;
		ongroupby: (next: string) => void;
	};

	let {
		filter,
		onchange,
		categories,
		categoryCounts,
		visibleCount,
		totalCount,
		groupBy,
		ongroupby
	}: Props = $props();

	const STATUS_LABELS: Record<ReviewStatus, string> = {
		all: 'All',
		uncategorized: 'Uncategorised',
		unconfirmed: 'Auto-categorised'
	};

	const categoryOptions = $derived(
		categories
			.map((category) => ({
				value: category.id,
				label: category.name,
				color: category.color,
				count: categoryCounts.get(category.id) ?? 0
			}))
			.filter((option) => option.count > 0)
			.sort((a, b) => b.count - a.count)
	);

	const active = $derived(
		filter.query.trim() !== '' ||
			filter.categories.size > 0 ||
			filter.min !== '' ||
			filter.max !== '' ||
			filter.status !== 'all'
	);

	function patch(next: Partial<TransactionFilter>): void {
		onchange({ ...filter, ...next });
	}

	function clearAll(): void {
		onchange({ query: '', categories: new Set(), min: '', max: '', status: 'all' });
	}
</script>

<div class="flex flex-col gap-3">
	<div class="flex flex-wrap items-center gap-2">
		<div class="relative w-full sm:w-64">
			<Search
				class="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ctp-overlay0"
			/>
			<input
				type="search"
				data-testid="expense-search"
				placeholder="Search transactions…"
				value={filter.query}
				oninput={(event) => patch({ query: event.currentTarget.value })}
				class="field w-full py-1.5 pl-9"
			/>
		</div>

		<FacetedFilter
			title="Category"
			testid="filter-category"
			options={categoryOptions}
			selected={filter.categories}
			onchange={(next) => patch({ categories: next })}
		/>

		<div
			class="inline-flex items-center gap-1 rounded-md border border-ctp-surface2 bg-ctp-mantle px-2 py-1 text-sm"
		>
			<span class="text-xs font-medium text-ctp-overlay1">Amount</span>
			<input
				type="text"
				inputmode="decimal"
				data-testid="filter-amount-min"
				placeholder="min"
				value={filter.min}
				oninput={(event) => patch({ min: event.currentTarget.value })}
				class="w-14 bg-transparent px-1 py-0.5 text-sm tabular-nums text-ctp-text placeholder:text-ctp-overlay0 focus:outline-none"
			/>
			<span class="text-ctp-overlay0">–</span>
			<input
				type="text"
				inputmode="decimal"
				data-testid="filter-amount-max"
				placeholder="max"
				value={filter.max}
				oninput={(event) => patch({ max: event.currentTarget.value })}
				class="w-14 bg-transparent px-1 py-0.5 text-sm tabular-nums text-ctp-text placeholder:text-ctp-overlay0 focus:outline-none"
			/>
		</div>

		<select
			data-testid="filter-status"
			value={filter.status}
			onchange={(event) => patch({ status: event.currentTarget.value as ReviewStatus })}
			class="field field-select py-1.5 text-sm"
			aria-label="Review status"
		>
			{#each Object.entries(STATUS_LABELS) as [value, label] (value)}
				<option {value}>{label}</option>
			{/each}
		</select>

		<label class="ml-auto inline-flex items-center gap-2 text-sm text-ctp-overlay1">
			Group by
			<select
				data-testid="filter-groupby"
				value={groupBy}
				onchange={(event) => ongroupby(event.currentTarget.value)}
				class="field field-select py-1.5"
			>
				<option value="transaction">Transaction</option>
				<option value="merchant">Merchant</option>
				<option value="category">Category</option>
				<option value="importance">Importance</option>
			</select>
		</label>
	</div>

	<div class="flex items-center gap-3 text-xs text-ctp-overlay1">
		<span data-testid="filter-count" class="tabular-nums">
			{#if active}
				Showing {visibleCount} of {totalCount}
			{:else}
				{totalCount}
				{totalCount === 1 ? 'transaction' : 'transactions'}
			{/if}
		</span>
		{#if active}
			<button
				type="button"
				data-testid="filter-clear"
				onclick={clearAll}
				class="inline-flex items-center gap-1 rounded px-1.5 py-0.5 font-medium text-ctp-subtext0 transition-colors hover:bg-ctp-surface0 hover:text-ctp-text"
			>
				<X class="h-3 w-3" /> Clear filters
			</button>
		{/if}
	</div>
</div>

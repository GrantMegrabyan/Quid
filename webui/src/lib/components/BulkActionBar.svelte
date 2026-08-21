<script lang="ts">
	import { Check, Tag, Trash2, X } from '@lucide/svelte';
	import CategoryIcon from '$components/CategoryIcon.svelte';
	import type { Category } from '$lib/types';

	/**
	 * Acts on a selection of transactions. It appears in place of nothing — the
	 * row-level affordance is the only way to get here — and offers only the two
	 * operations that are worth doing in bulk: recategorise, and delete.
	 */
	type Props = {
		count: number;
		categories: Category[];
		oncategorize: (categoryId: string) => void;
		ondelete: () => void;
		onclear: () => void;
	};

	let { count, categories, oncategorize, ondelete, onclear }: Props = $props();

	let pickerOpen = $state(false);
	let root: HTMLDivElement | null = $state(null);

	function choose(categoryId: string): void {
		pickerOpen = false;
		oncategorize(categoryId);
	}
</script>

<svelte:window
	onpointerdown={(event) => {
		if (pickerOpen && root && !root.contains(event.target as Node)) pickerOpen = false;
	}}
	onkeydown={(event) => {
		if (event.key === 'Escape') pickerOpen = false;
	}}
/>

<div
	role="region"
	aria-label="Bulk actions"
	data-testid="bulk-bar"
	class="flex flex-wrap items-center justify-between gap-2 rounded-md border border-ctp-accent/40 bg-ctp-accent/10 px-3 py-2"
>
	<span class="inline-flex items-center gap-2 text-sm font-medium text-ctp-text">
		<Check class="h-4 w-4 text-ctp-accent" aria-hidden="true" />
		<span data-testid="bulk-count" class="tabular-nums">{count}</span>
		{count === 1 ? 'transaction' : 'transactions'} selected
	</span>

	<div class="flex items-center gap-2" bind:this={root}>
		<div class="relative">
			<button
				type="button"
				data-testid="bulk-categorize"
				aria-expanded={pickerOpen}
				onclick={() => (pickerOpen = !pickerOpen)}
				class="inline-flex items-center gap-1.5 rounded-md bg-ctp-accent px-2.5 py-1.5 text-sm font-medium text-ctp-on-accent transition-colors hover:bg-ctp-accent-hover"
			>
				<Tag class="h-3.5 w-3.5" /> Categorise
			</button>
			{#if pickerOpen}
				<div
					role="listbox"
					aria-label="Choose a category"
					tabindex="-1"
					class="absolute right-0 z-40 mt-1 max-h-80 w-60 overflow-y-auto rounded-md border border-ctp-surface2 bg-ctp-mantle p-1"
					style="box-shadow: 0 8px 24px rgb(0 0 0 / 0.12)"
				>
					{#each categories as category (category.id)}
						<button
							type="button"
							role="option"
							aria-selected="false"
							data-testid="bulk-category-option"
							onclick={() => choose(category.id)}
							class="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-sm text-ctp-text transition-colors hover:bg-ctp-surface0"
						>
							<span
								class="cat-chip flex h-5 w-5 shrink-0 items-center justify-center rounded"
								style="--cat: {category.color};"
							>
								<CategoryIcon name={category.icon} size={11} />
							</span>
							<span class="truncate">{category.name}</span>
						</button>
					{/each}
				</div>
			{/if}
		</div>

		<button
			type="button"
			data-testid="bulk-delete"
			onclick={ondelete}
			class="inline-flex items-center gap-1.5 rounded-md border border-ctp-surface2 bg-ctp-mantle px-2.5 py-1.5 text-sm font-medium text-ctp-red transition-colors hover:bg-ctp-red/10"
		>
			<Trash2 class="h-3.5 w-3.5" /> Delete
		</button>

		<button
			type="button"
			data-testid="bulk-clear"
			onclick={onclear}
			class="inline-flex items-center gap-1 rounded-md px-2 py-1.5 text-sm font-medium text-ctp-subtext0 transition-colors hover:bg-ctp-surface0 hover:text-ctp-text"
		>
			<X class="h-3.5 w-3.5" /> Clear
		</button>
	</div>
</div>

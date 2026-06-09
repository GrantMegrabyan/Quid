<script lang="ts">
	import CategoryIcon from '$components/CategoryIcon.svelte';
	import { CATEGORY_ICON_OPTIONS, filterCategoryIcons } from '$utils/categoryIcons';

	const DEFAULT_VISIBLE = 24;
	const SEARCH_VISIBLE = 180;

	let {
		value,
		onselect,
		id,
		placeholder = 'Search icons…',
	}: {
		value: string;
		onselect: (key: string) => void;
		id?: string;
		placeholder?: string;
	} = $props();

	let query = $state('');

	const filtered = $derived(filterCategoryIcons(query));
	const isEmptyQuery = $derived(query.trim() === '');
	const visible = $derived(
		isEmptyQuery ? filtered.slice(0, DEFAULT_VISIBLE) : filtered.slice(0, SEARCH_VISIBLE),
	);
	const totalCount = CATEGORY_ICON_OPTIONS.length;
	const hiddenWhenEmpty = $derived(
		isEmptyQuery && totalCount > DEFAULT_VISIBLE ? totalCount - DEFAULT_VISIBLE : 0,
	);
	const hiddenSearchMatches = $derived(
		!isEmptyQuery && filtered.length > visible.length ? filtered.length - visible.length : 0,
	);

	function handleSelect(key: string): void {
		onselect(key);
	}
</script>

<div class="flex flex-col gap-2">
	<input
		{id}
		data-testid="icon-picker-search"
		type="search"
		autocomplete="off"
		spellcheck="false"
		{placeholder}
		bind:value={query}
		class="field w-full"
	/>

	{#if visible.length === 0}
		<p
			data-testid="icon-picker-empty"
			class="px-1 py-4 text-center text-xs text-ctp-overlay1"
		>
			No icons match "{query.trim()}".
		</p>
	{:else}
		<div
			role="listbox"
			aria-label="Category icon"
			data-testid="icon-picker-grid"
			class="grid max-h-56 grid-cols-4 gap-1 overflow-y-auto rounded-md border border-ctp-surface1 bg-ctp-surface0 p-2 sm:grid-cols-6"
		>
			{#each visible as option (option.key)}
				{@const isSelected = option.key === value}
				<button
					type="button"
					role="option"
					aria-selected={isSelected}
					data-testid="icon-picker-option"
					data-icon={option.key}
					data-selected={isSelected ? 'true' : undefined}
					title={option.label}
					onclick={() => handleSelect(option.key)}
					class="flex aspect-square flex-col items-center justify-center gap-1 rounded-md border p-1 text-[10px] leading-tight transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-ctp-accent {isSelected
						? 'border-ctp-accent bg-ctp-accent text-ctp-on-accent'
						: 'border-transparent text-ctp-subtext0 hover:border-ctp-surface2 hover:bg-ctp-base'}"
				>
					<CategoryIcon name={option.key} size={18} />
					<span class="line-clamp-1 w-full truncate text-center">{option.label}</span>
				</button>
			{/each}
		</div>
		{#if hiddenWhenEmpty > 0 || hiddenSearchMatches > 0}
			<p data-testid="icon-picker-summary" class="px-1 text-[11px] text-ctp-overlay1">
				{#if isEmptyQuery}
					Showing {visible.length} of {totalCount}. Type to search the rest.
				{:else}
					Showing {visible.length} of {filtered.length} matches. Narrow your search to reveal
					{hiddenSearchMatches} more.
				{/if}
			</p>
		{/if}
	{/if}
</div>

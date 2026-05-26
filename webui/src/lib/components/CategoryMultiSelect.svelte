<script lang="ts">
	import { onDestroy, onMount } from 'svelte';
	import CategoryIcon from '$components/CategoryIcon.svelte';
	import { categories } from '$lib/stores/categories';

	let {
		selectedIds = $bindable<string[]>([])
	}: { selectedIds?: string[] } = $props();

	let open = $state(false);
	let panel: HTMLDivElement | null = $state(null);
	let trigger: HTMLButtonElement | null = $state(null);

	const selectedSet = $derived(new Set(selectedIds));
	const allSelected = $derived(
		$categories.length > 0 && selectedIds.length === $categories.length
	);

	const buttonLabel = $derived.by(() => {
		if ($categories.length === 0) return 'No categories';
		if (selectedIds.length === 0) return 'No categories';
		if (allSelected) return 'All categories';
		if (selectedIds.length === 1) {
			const onlyId = selectedIds[0];
			const cat = $categories.find((c) => c.id === onlyId);
			return cat?.name ?? '1 selected';
		}
		return `${selectedIds.length} selected`;
	});

	function toggle(id: string): void {
		if (selectedSet.has(id)) {
			selectedIds = selectedIds.filter((existing) => existing !== id);
		} else {
			selectedIds = [...selectedIds, id];
		}
	}

	function selectAll(): void {
		selectedIds = $categories.map((category) => category.id);
	}

	function clear(): void {
		selectedIds = [];
	}

	function handleDocumentClick(event: MouseEvent): void {
		if (!open) return;
		const target = event.target as Node | null;
		if (!target) return;
		if (panel?.contains(target)) return;
		if (trigger?.contains(target)) return;
		open = false;
	}

	function handleKeydown(event: KeyboardEvent): void {
		if (event.key === 'Escape' && open) {
			open = false;
			trigger?.focus();
		}
	}

	onMount(() => {
		document.addEventListener('mousedown', handleDocumentClick);
		document.addEventListener('keydown', handleKeydown);
	});

	onDestroy(() => {
		if (typeof document !== 'undefined') {
			document.removeEventListener('mousedown', handleDocumentClick);
			document.removeEventListener('keydown', handleKeydown);
		}
	});
</script>

<div data-testid="category-multi-select" class="relative inline-block w-full max-w-xs">
	<button
		bind:this={trigger}
		type="button"
		data-testid="category-multi-select-trigger"
		aria-haspopup="listbox"
		aria-expanded={open}
		onclick={() => (open = !open)}
		class="inline-flex w-full items-center justify-between gap-2 rounded-md border border-gray-200 bg-white px-3 py-2 text-sm text-gray-800 transition-colors hover:bg-gray-50 dark:border-gray-800 dark:bg-[#111114] dark:text-gray-100 dark:hover:bg-gray-900"
	>
		<span class="truncate">{buttonLabel}</span>
		<svg
			class="h-4 w-4 shrink-0 text-gray-500 transition-transform"
			style:transform={open ? 'rotate(180deg)' : 'rotate(0deg)'}
			viewBox="0 0 12 12"
			fill="none"
			aria-hidden="true"
		>
			<path d="M3 4.5l3 3 3-3" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" />
		</svg>
	</button>

	{#if open}
		<div
			bind:this={panel}
			role="listbox"
			aria-multiselectable="true"
			data-testid="category-multi-select-panel"
			class="absolute z-20 mt-1 max-h-72 w-72 overflow-y-auto rounded-md border border-gray-200 bg-white p-2 shadow-lg dark:border-gray-800 dark:bg-[#111114]"
		>
			<div class="mb-1 flex items-center justify-between gap-2 px-1 pb-2">
				<button
					type="button"
					data-testid="category-multi-select-all"
					class="text-xs font-medium text-blue-600 hover:underline dark:text-blue-400"
					onclick={selectAll}
				>
					Select all
				</button>
				<button
					type="button"
					data-testid="category-multi-select-clear"
					class="text-xs font-medium text-gray-500 hover:underline dark:text-gray-400"
					onclick={clear}
				>
					Clear
				</button>
			</div>

			{#each $categories as category (category.id)}
				{@const checked = selectedSet.has(category.id)}
				<button
					type="button"
					role="option"
					aria-selected={checked}
					data-testid="category-multi-select-option"
					data-category-id={category.id}
					onclick={() => toggle(category.id)}
					class="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm transition-colors hover:bg-gray-100 dark:hover:bg-gray-800"
				>
					<input
						type="checkbox"
						tabindex="-1"
						{checked}
						readonly
						class="h-4 w-4 accent-gray-900 dark:accent-gray-100"
					/>
					<span
						class="flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-white"
						style="background-color: {category.color};"
						aria-hidden="true"
					>
						<CategoryIcon name={category.icon} size={12} />
					</span>
					<span class="truncate text-gray-800 dark:text-gray-100">{category.name}</span>
				</button>
			{/each}
		</div>
	{/if}
</div>

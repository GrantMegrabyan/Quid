<script lang="ts">
	import { Check, ChevronDown } from '@lucide/svelte';

	/**
	 * A multi-select filter that reads as a chip: closed it shows the facet name
	 * and how many values are picked; open it lists the values with their row
	 * counts, so the user can see what a filter would cost them before applying
	 * it.
	 */
	type Option = { value: string; label: string; count?: number; color?: string };
	type Props = {
		title: string;
		options: Option[];
		selected: Set<string>;
		onchange: (next: Set<string>) => void;
		testid?: string;
	};

	let { title, options, selected, onchange, testid }: Props = $props();

	let open = $state(false);
	let root: HTMLDivElement | null = $state(null);

	function toggle(value: string): void {
		const next = new Set(selected);
		if (next.has(value)) {
			next.delete(value);
		} else {
			next.add(value);
		}
		onchange(next);
	}

	function onWindowPointerDown(event: PointerEvent): void {
		if (!open || !root) return;
		if (!root.contains(event.target as Node)) open = false;
	}
</script>

<svelte:window
	onpointerdown={onWindowPointerDown}
	onkeydown={(event) => {
		if (event.key === 'Escape') open = false;
	}}
/>

<div class="relative" bind:this={root}>
	<button
		type="button"
		data-testid={testid}
		aria-expanded={open}
		aria-haspopup="listbox"
		onclick={() => (open = !open)}
		class="inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1.5 text-sm transition-colors {selected.size >
		0
			? 'border-ctp-accent/50 bg-ctp-accent/10 font-medium text-ctp-text'
			: 'border-ctp-surface2 bg-ctp-mantle text-ctp-subtext0 hover:bg-ctp-surface0 hover:text-ctp-text'}"
	>
		{title}
		{#if selected.size > 0}
			<span class="rounded bg-ctp-accent/20 px-1.5 text-xs font-semibold tabular-nums text-ctp-text">
				{selected.size}
			</span>
		{/if}
		<ChevronDown class="h-3.5 w-3.5 text-ctp-overlay1" />
	</button>

	{#if open}
		<div
			role="listbox"
			aria-label={title}
			tabindex="-1"
			class="absolute left-0 z-40 mt-1 max-h-80 w-64 overflow-y-auto rounded-md border border-ctp-surface2 bg-ctp-mantle p-1 shadow-lg"
			style="box-shadow: 0 8px 24px rgb(0 0 0 / 0.12)"
		>
			{#each options as option (option.value)}
				{@const isSelected = selected.has(option.value)}
				<button
					type="button"
					role="option"
					aria-selected={isSelected}
					onclick={() => toggle(option.value)}
					class="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-sm transition-colors hover:bg-ctp-surface0"
				>
					<span
						class="flex h-4 w-4 shrink-0 items-center justify-center rounded border {isSelected
							? 'border-ctp-accent bg-ctp-accent text-ctp-on-accent'
							: 'border-ctp-surface2'}"
					>
						{#if isSelected}<Check class="h-3 w-3" />{/if}
					</span>
					{#if option.color}
						<span class="cat-bar h-2 w-2 shrink-0 rounded-full" style="--cat: {option.color}"></span>
					{/if}
					<span class="min-w-0 flex-1 truncate text-ctp-text">{option.label}</span>
					{#if option.count !== undefined}
						<span class="shrink-0 text-xs tabular-nums text-ctp-overlay1">{option.count}</span>
					{/if}
				</button>
			{:else}
				<p class="px-2 py-3 text-sm text-ctp-overlay1">Nothing to filter by.</p>
			{/each}
		</div>
	{/if}
</div>

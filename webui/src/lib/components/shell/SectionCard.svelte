<script lang="ts">
	import type { Snippet } from 'svelte';

	/**
	 * A titled section: a small caption line above the card rather than a heavy
	 * header inside it, so a column of these reads as a list of sections instead
	 * of a stack of boxes.
	 */
	type Props = {
		title: string;
		/** Muted qualifier next to the title ("Aug 2026", "12 shown"). */
		subtitle?: string;
		/** Right-aligned control on the caption line. */
		action?: Snippet;
		/** Drop the card's padding for full-bleed bodies (lists, tables). */
		padded?: boolean;
		class?: string;
		children: Snippet;
	};

	let { title, subtitle, action, padded = true, class: className = '', children }: Props = $props();
</script>

<section class="flex min-w-0 flex-col">
	<div class="flex items-baseline justify-between gap-3 pb-2">
		<div class="flex min-w-0 items-baseline gap-2">
			<h2 class="text-sm font-semibold tracking-tight text-ctp-text">{title}</h2>
			{#if subtitle}
				<span class="truncate text-xs text-ctp-overlay1">{subtitle}</span>
			{/if}
		</div>
		{#if action}
			<div class="flex shrink-0 items-center gap-2">{@render action()}</div>
		{/if}
	</div>
	<div class="card {padded ? 'p-4 sm:p-5' : ''} {className}">
		{@render children()}
	</div>
</section>

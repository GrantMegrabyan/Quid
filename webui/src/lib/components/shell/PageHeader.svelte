<script lang="ts">
	import type { Snippet } from 'svelte';

	/**
	 * The page's sticky title bar. It rides the page's own scroll: the border
	 * and the frosted background only appear once the content has moved under
	 * it, so a page at rest reads as one uninterrupted sheet.
	 */
	type Props = {
		heading?: string;
		text?: string;
		/** Right-aligned controls: buttons, selectors, toggles. */
		actions?: Snippet;
		/** Replaces the heading block entirely when a page needs custom chrome. */
		children?: Snippet;
	};

	let { heading, text, actions, children }: Props = $props();

	let scrolled = $state(false);
</script>

<svelte:window onscroll={() => (scrolled = window.scrollY > 8)} />

<header
	data-testid="page-header"
	data-scrolled={scrolled ? 'true' : undefined}
	class="sticky top-0 z-30 -mx-4 mb-6 border-b px-4 py-3 backdrop-blur transition-colors duration-200 sm:-mx-6 sm:px-6 {scrolled
		? 'border-ctp-surface1 bg-ctp-mantle/85'
		: 'border-transparent bg-ctp-mantle'}"
>
	<div class="flex flex-wrap items-end justify-between gap-3">
		{#if children}
			{@render children()}
		{:else}
			<div class="min-w-0">
				<h1 class="truncate font-serif text-xl font-bold tracking-tight text-ctp-text">
					{heading}
				</h1>
				{#if text}
					<p class="mt-0.5 truncate text-sm text-ctp-overlay1">{text}</p>
				{/if}
			</div>
		{/if}
		{#if actions}
			<div class="flex flex-wrap items-center gap-2">{@render actions()}</div>
		{/if}
	</div>
</header>

<script lang="ts">
	import type { Snippet } from 'svelte';

	/** The body of a page: one rhythm of stacked sections, set by the shell. */
	let { class: className = '', children }: { class?: string; children: Snippet } = $props();
</script>

<div class="flex flex-col gap-6 pb-10 {className}">
	{@render children()}
</div>

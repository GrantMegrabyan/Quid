<script lang="ts">
	import { untrack } from 'svelte';
	import { tweened } from 'svelte/motion';
	import { cubicOut } from 'svelte/easing';
	import { formatAmount } from '$lib/utils/money';

	/**
	 * The one big number on a page. Serif + tabular figures, with the decimal
	 * fraction dropped to a muted tone so the pounds carry the line and the
	 * number stays readable at display size.
	 */
	type Props = {
		value: number;
		currency?: string;
		duration?: number;
		class?: string;
		testid?: string;
	};

	let { value, currency = 'GBP', duration = 500, class: className = '', testid }: Props = $props();

	const display = tweened(untrack(() => value), {
		duration: untrack(() => duration),
		easing: cubicOut
	});

	$effect(() => {
		void display.set(value);
	});

	// Split on the LAST separator so a thousands separator is never mistaken for
	// the decimal point; a locale without a fraction just renders whole.
	const parts = $derived.by(() => {
		const formatted = formatAmount($display, currency);
		const index = formatted.lastIndexOf('.');
		if (index === -1) return { whole: formatted, fraction: '' };
		return { whole: formatted.slice(0, index), fraction: formatted.slice(index) };
	});
</script>

<span class="numeral {className}" data-testid={testid}>
	{parts.whole}{#if parts.fraction}<span class="text-ctp-overlay1">{parts.fraction}</span>{/if}
</span>

<script lang="ts">
	import { untrack } from 'svelte';
	import { tweened } from 'svelte/motion';
	import { cubicOut } from 'svelte/easing';
	import { formatAmount } from '$lib/utils/money';

	type Props = {
		value: number;
		currency?: string;
		duration?: number;
		class?: string;
		testid?: string;
	};

	let { value, currency = 'GBP', duration = 400, class: className = '', testid }: Props = $props();

	const display = tweened(untrack(() => value), {
		duration: untrack(() => duration),
		easing: cubicOut
	});

	$effect(() => {
		void display.set(value);
	});
</script>

<span class={className} data-testid={testid}>{formatAmount($display, currency)}</span>

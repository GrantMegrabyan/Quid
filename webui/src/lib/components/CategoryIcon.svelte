<script lang="ts">
	import ShoppingCart from '@lucide/svelte/icons/shopping-cart';
	import TrainFront from '@lucide/svelte/icons/train-front';
	import House from '@lucide/svelte/icons/house';
	import Utensils from '@lucide/svelte/icons/utensils';
	import Receipt from '@lucide/svelte/icons/receipt';
	import Wallet from '@lucide/svelte/icons/wallet';
	import Coffee from '@lucide/svelte/icons/coffee';
	import Car from '@lucide/svelte/icons/car';
	import CircleHelp from '@lucide/svelte/icons/circle-help';
	import { normalizeCategoryIcon } from '$utils/categoryIcons';

	let {
		name,
		size = 18,
		strokeWidth = 2.25
	}: { name?: string; size?: number; strokeWidth?: number } = $props();

	const iconName = $derived(normalizeCategoryIcon(name));
</script>

{#if iconName === 'shopping-cart'}
	<ShoppingCart {size} {strokeWidth} aria-hidden="true" />
{:else if iconName === 'train-front'}
	<TrainFront {size} {strokeWidth} aria-hidden="true" />
{:else if iconName === 'house'}
	<House {size} {strokeWidth} aria-hidden="true" />
{:else if iconName === 'utensils'}
	<Utensils {size} {strokeWidth} aria-hidden="true" />
{:else if iconName === 'receipt'}
	<Receipt {size} {strokeWidth} aria-hidden="true" />
{:else if iconName === 'wallet'}
	<Wallet {size} {strokeWidth} aria-hidden="true" />
{:else if iconName === 'coffee'}
	<Coffee {size} {strokeWidth} aria-hidden="true" />
{:else if iconName === 'car'}
	<Car {size} {strokeWidth} aria-hidden="true" />
{:else}
	<CircleHelp {size} {strokeWidth} aria-hidden="true" />
{/if}

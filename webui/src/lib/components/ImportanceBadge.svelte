<script lang="ts">
	import type { ExpenseImportance } from '$types';

	let { importance }: { importance: ExpenseImportance } = $props();

	const label = $derived(
		importance === 'essential' ? 'Essential' : importance === 'important' ? 'Important' : 'Discretionary'
	);
</script>

<span
	data-testid="importance-badge"
	class="inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium"
	class:bg-emerald-50={importance === 'essential'}
	class:text-emerald-700={importance === 'essential'}
	class:dark:bg-emerald-950={importance === 'essential'}
	class:dark:text-emerald-300={importance === 'essential'}
	class:bg-blue-50={importance === 'important'}
	class:text-blue-700={importance === 'important'}
	class:dark:bg-blue-950={importance === 'important'}
	class:dark:text-blue-300={importance === 'important'}
	class:bg-amber-50={importance === 'discretionary'}
	class:text-amber-700={importance === 'discretionary'}
	class:dark:bg-amber-950={importance === 'discretionary'}
	class:dark:text-amber-300={importance === 'discretionary'}
>
	{label}
</span>

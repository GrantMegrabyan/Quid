<script lang="ts">
	import { selectedMonth } from '$lib/stores/ui';
	import { currentMonthKey, formatMonthLabel, nextMonthKey, previousMonthKey } from '$utils/dates';

	const currentKey = currentMonthKey();
	const canGoNext = $derived($selectedMonth < currentKey);
	const label = $derived(formatMonthLabel($selectedMonth));

	function goPrevious(): void {
		selectedMonth.set(previousMonthKey($selectedMonth));
	}

	function goNext(): void {
		if (canGoNext) {
			selectedMonth.set(nextMonthKey($selectedMonth));
		}
	}
</script>

<div
	class="inline-flex items-center overflow-hidden rounded-lg border border-ctp-surface1 bg-ctp-base text-sm shadow-sm"
	aria-label="Selected month"
>
	<button
		type="button"
		data-testid="month-prev"
		onclick={goPrevious}
		class="px-3 py-2 text-ctp-subtext0 transition-colors hover:bg-ctp-surface1 hover:text-ctp-text"
		aria-label="Previous month"
	>
		‹
	</button>
	<div
		data-testid="month-label"
		class="min-w-36 border-x border-ctp-surface1 px-4 py-2 text-center font-medium text-ctp-text"
	>
		{label}
	</div>
	<button
		type="button"
		data-testid="month-next"
		onclick={goNext}
		disabled={!canGoNext}
		class="px-3 py-2 text-ctp-subtext0 transition-colors hover:bg-ctp-surface1 hover:text-ctp-text disabled:cursor-not-allowed disabled:text-ctp-overlay0 disabled:hover:bg-transparent"
		aria-label="Next month"
	>
		›
	</button>
</div>

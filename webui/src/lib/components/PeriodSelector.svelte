<script lang="ts">
	import {
		goCurrentMonth,
		isMonthMode,
		selectedMonth,
		selection,
		setPeriod,
		stepMonth
	} from '$lib/stores/ui';
	import { currentMonthKey, formatMonthLabel } from '$utils/dates';
	import { PERIOD_CODES, restoreCodeOf } from '$utils/period';

	/**
	 * The dashboard's window control: a month stepper on the left and the
	 * rolling-period codes on the right. The two are one control, not two —
	 * stepping months leaves period mode, and picking a code leaves month mode
	 * (restoring the code the month was entered from).
	 */
	const currentKey = currentMonthKey();
	const canGoNext = $derived($isMonthMode && $selectedMonth < currentKey);
	const monthLabel = $derived(formatMonthLabel($selectedMonth));
	const activeCode = $derived($isMonthMode ? null : restoreCodeOf($selection));
</script>

<div class="flex flex-wrap items-center gap-2">
	<div
		class="inline-flex items-center overflow-hidden rounded-md border border-ctp-surface2 bg-ctp-mantle text-sm"
		aria-label="Selected month"
	>
		<button
			type="button"
			data-testid="month-prev"
			onclick={() => stepMonth(-1)}
			class="px-2.5 py-1.5 text-ctp-subtext0 transition-colors hover:bg-ctp-surface0 hover:text-ctp-text"
			aria-label="Previous month"
		>
			‹
		</button>
		<div
			data-testid="month-label"
			class="min-w-28 border-x border-ctp-surface2 px-3 py-1.5 text-center text-sm font-medium {$isMonthMode
				? 'text-ctp-text'
				: 'text-ctp-overlay1'}"
		>
			{monthLabel}
		</div>
		<button
			type="button"
			data-testid="month-next"
			onclick={() => stepMonth(1)}
			disabled={!canGoNext && $isMonthMode}
			class="px-2.5 py-1.5 text-ctp-subtext0 transition-colors hover:bg-ctp-surface0 hover:text-ctp-text disabled:cursor-not-allowed disabled:text-ctp-overlay0 disabled:hover:bg-transparent"
			aria-label="Next month"
		>
			›
		</button>
	</div>

	{#if canGoNext}
		<button
			type="button"
			data-testid="month-current"
			onclick={goCurrentMonth}
			class="rounded-md border border-ctp-surface2 bg-ctp-mantle px-3 py-1.5 text-sm font-medium text-ctp-subtext0 transition-colors hover:bg-ctp-surface0 hover:text-ctp-text"
		>
			Today
		</button>
	{/if}

	<div
		role="radiogroup"
		aria-label="Period"
		data-testid="period-selector"
		class="inline-flex items-center gap-0.5 rounded-md border border-ctp-surface2 bg-ctp-mantle p-0.5"
	>
		{#each PERIOD_CODES as code (code)}
			<button
				type="button"
				role="radio"
				aria-checked={activeCode === code}
				data-testid="period-{code}"
				onclick={() => setPeriod(code)}
				class="rounded px-2.5 py-1 text-xs font-semibold transition-colors {activeCode === code
					? 'bg-ctp-accent text-ctp-on-accent'
					: 'text-ctp-subtext0 hover:bg-ctp-surface0 hover:text-ctp-text'}"
			>
				{code}
			</button>
		{/each}
	</div>
</div>

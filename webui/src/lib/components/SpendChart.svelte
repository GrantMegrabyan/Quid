<script lang="ts">
	import CumulativeChart from '$components/CumulativeChart.svelte';
	import MonthlyBarChart from '$components/MonthlyBarChart.svelte';
	import { isMonthMode } from '$lib/stores/ui';

	/**
	 * The trend chart follows the window's granularity: a single month is a
	 * cumulative day-by-day line (is this month tracking above the last one?),
	 * a multi-month window is a bar per month (which months were expensive?).
	 */
</script>

{#if $isMonthMode}
	<CumulativeChart />
{:else}
	<MonthlyBarChart />
{/if}

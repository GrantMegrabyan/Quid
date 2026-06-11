<script lang="ts">
	import { settings } from '$lib/stores/settings';
	import { amountToNumber, formatAmount } from '$utils/money';
	import { formatMonthLabel } from '$utils/dates';
	import { CalendarCheck, TrendingDown, TrendingUp } from '@lucide/svelte';
	import type { AnalyticsSummary, DiagnosisResult, MonthlyTotal } from '$types';

	let {
		diagnosis,
		summary,
		months
	}: { diagnosis: DiagnosisResult; summary: AnalyticsSummary; months: MonthlyTotal[] } = $props();

	const totalCurrent = $derived(amountToNumber(diagnosis.totalCurrent));
	const totalBaseline = $derived(amountToNumber(diagnosis.totalBaseline));
	const delta = $derived(totalCurrent - totalBaseline);
	const isOver = $derived(delta > 0);
	const hasBaseline = $derived(diagnosis.baselineMonthCount > 0);
	const pctLabel = $derived.by(() => {
		if (!hasBaseline || totalBaseline <= 0) return null;
		const pct = Math.round((delta / totalBaseline) * 100);
		return `${pct > 0 ? '+' : ''}${pct}%`;
	});

	// Inline SVG sparkline over the last 7 COMPLETE months.
	const SPARK_W = 140;
	const SPARK_H = 36;
	const sparkPoints = $derived.by(() => {
		const complete = months.filter((m) => m.month !== summary.currentMonth).slice(-7);
		if (complete.length < 2) return '';
		const values = complete.map((m) => amountToNumber(m.total));
		const max = Math.max(...values, 1);
		const pad = 2;
		return values
			.map((v, i) => {
				const x = pad + (i * (SPARK_W - 2 * pad)) / (values.length - 1);
				const y = SPARK_H - pad - (v / max) * (SPARK_H - 2 * pad);
				return `${x.toFixed(1)},${y.toFixed(1)}`;
			})
			.join(' ');
	});

	const paceLabel = $derived.by(() => {
		if (!summary.currentMonth || amountToNumber(summary.currentMonthToDate) <= 0) return null;
		const monthName = formatMonthLabel(summary.currentMonth);
		const toDate = formatAmount(summary.currentMonthToDate, $settings.currency);
		const projected = formatAmount(summary.currentMonthProjected, $settings.currency);
		return `${monthName} so far: ${toDate}, on pace for ~${projected}`;
	});
</script>

<div
	class="rounded-xl border-2 border-ctp-accent/50 bg-gradient-to-br from-ctp-accent/[0.07] to-ctp-base p-4 shadow-lg shadow-black/20"
	data-testid="analytics-verdict"
>
	{#if diagnosis.latestMonth}
		<div class="flex flex-wrap items-start justify-between gap-3">
			<div class="flex items-start gap-3">
				<span
					class="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-ctp-accent/20 text-ctp-accent"
				>
					<CalendarCheck class="h-5 w-5" />
				</span>
				<div>
					<p class="text-xs font-medium text-ctp-subtext0">
						{formatMonthLabel(diagnosis.latestMonth)} — your last complete month
					</p>
					<p
						class="text-3xl font-bold leading-tight tracking-tight text-ctp-text"
						data-testid="analytics-verdict-total"
					>
						{formatAmount(diagnosis.totalCurrent, $settings.currency)}
					</p>
					{#if hasBaseline}
						<div class="mt-1.5 flex flex-wrap items-baseline gap-x-2 gap-y-0.5 text-sm">
							<span class="text-ctp-subtext0">
								vs <span class="font-semibold text-ctp-text"
									>{formatAmount(diagnosis.totalBaseline, $settings.currency)}</span
								>
								{diagnosis.baselineMonthCount}-month average
							</span>
							{#if pctLabel}
								<span
									class="inline-flex items-center gap-0.5 rounded-full px-1.5 py-0.5 text-xs font-semibold tabular-nums {isOver
										? 'bg-ctp-red/15 text-ctp-red'
										: 'bg-ctp-green/15 text-ctp-green'}"
									data-testid="analytics-verdict-badge"
								>
									{#if isOver}
										<TrendingUp class="h-3 w-3" />
									{:else}
										<TrendingDown class="h-3 w-3" />
									{/if}
									{pctLabel}
								</span>
							{/if}
						</div>
					{:else}
						<p class="mt-1.5 text-sm text-ctp-overlay0">
							Not enough history for a baseline yet — one more complete month needed.
						</p>
					{/if}
					{#if paceLabel}
						<p class="mt-1 text-xs text-ctp-overlay0">{paceLabel}</p>
					{/if}
				</div>
			</div>
			{#if sparkPoints}
				<svg
					viewBox="0 0 {SPARK_W} {SPARK_H}"
					class="h-9 w-36 shrink-0 self-center text-ctp-accent"
					aria-hidden="true"
				>
					<polyline
						points={sparkPoints}
						fill="none"
						stroke="currentColor"
						stroke-width="2"
						stroke-linejoin="round"
						stroke-linecap="round"
					/>
				</svg>
			{/if}
		</div>
	{:else}
		<p class="text-sm text-ctp-overlay0">
			No complete month of data yet — insights appear after your first full month.
		</p>
	{/if}
</div>

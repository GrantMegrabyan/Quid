<script lang="ts">
	import { settings } from '$lib/stores/settings';
	import { formatAmount, amountToNumber } from '$utils/money';
	import { formatMonthLabel } from '$utils/dates';
	import { ChevronDown, TrendingDown, TrendingUp } from '@lucide/svelte';
	import type { DiagnosisResult } from '$types';

	let { diagnosis }: { diagnosis: DiagnosisResult } = $props();

	let expanded = $state<Set<string>>(new Set());
	let showDecreases = $state(false);

	function toggle(categoryId: string): void {
		const next = new Set(expanded);
		if (next.has(categoryId)) {
			next.delete(categoryId);
		} else {
			next.add(categoryId);
		}
		expanded = next;
	}

	const decreasesSummary = $derived(
		diagnosis.decreases
			.slice(0, 4)
			.map(
				(d) =>
					`${d.categoryName} −${formatAmount(Math.abs(amountToNumber(d.delta)), $settings.currency)}`
			)
			.join(' · ')
	);

	function pctBadge(pct: number | null): string | null {
		if (pct === null) return null;
		return `+${Math.round(pct)}%`;
	}
</script>

<section
	class="rounded-xl border border-ctp-surface1 bg-ctp-base p-4 shadow-lg shadow-black/20"
	data-testid="analytics-wentup"
>
	<h2 class="text-xs font-bold uppercase tracking-wider text-ctp-subtext0">What went up</h2>
	{#if diagnosis.baselineMonthCount === 0}
		<p class="mt-3 text-sm text-ctp-overlay0" data-testid="analytics-wentup-empty">
			Not enough history to compare yet — this fills in after two complete months.
		</p>
	{:else if diagnosis.increases.length === 0}
		<p class="mt-3 text-sm text-ctp-overlay0" data-testid="analytics-wentup-empty">
			Nothing went up meaningfully vs your average. Nice.
		</p>
	{:else}
		<ul class="mt-2 divide-y divide-ctp-surface0">
			{#each diagnosis.increases as inc (inc.categoryId)}
				{@const isOpen = expanded.has(inc.categoryId)}
				<li data-testid="analytics-wentup-row">
					<button
						type="button"
						class="flex w-full flex-wrap items-baseline gap-x-3 gap-y-1 py-2.5 text-left transition-colors hover:bg-ctp-surface0/40"
						data-testid={`analytics-wentup-toggle-${inc.categoryId}`}
						aria-expanded={isOpen}
						onclick={() => toggle(inc.categoryId)}
					>
						<span class="inline-flex items-center gap-2 text-sm font-semibold text-ctp-text">
							<span
								class="h-2.5 w-2.5 shrink-0 rounded-full"
								style="background-color: {inc.color}"
							></span>
							<TrendingUp class="h-4 w-4 text-ctp-red" />
							{inc.categoryName}
							{#if inc.isNew}
								<span
									class="rounded-full bg-ctp-mauve/15 px-1.5 py-0.5 text-[10px] font-semibold text-ctp-mauve"
									>new</span
								>
							{/if}
						</span>
						<span class="text-sm tabular-nums text-ctp-text"
							>{formatAmount(inc.current, $settings.currency)}</span
						>
						{#if !inc.isNew}
							<span class="text-xs text-ctp-subtext0"
								>vs {formatAmount(inc.baseline, $settings.currency)} avg</span
							>
						{/if}
						<span class="ml-auto inline-flex items-center gap-1.5">
							<span class="text-sm font-semibold tabular-nums text-ctp-red"
								>+{formatAmount(inc.delta, $settings.currency)}</span
							>
							{#if pctBadge(inc.percentChange)}
								<span class="text-xs tabular-nums text-ctp-red/80">{pctBadge(inc.percentChange)}</span>
							{/if}
							<ChevronDown
								class="h-4 w-4 text-ctp-overlay0 transition-transform {isOpen ? 'rotate-180' : ''}"
							/>
						</span>
					</button>
					{#if isOpen}
						<div class="pb-3 pl-5" data-testid={`analytics-wentup-detail-${inc.categoryId}`}>
							{#if inc.contributors.length > 0}
								<ul class="flex flex-col gap-1">
									{#each inc.contributors as c (c.merchant)}
										<li class="text-xs text-ctp-subtext0">
											<span class="font-semibold text-ctp-text">{c.merchant}</span>
											{formatAmount(c.current, $settings.currency)}
											{#if c.isNew}
												<span class="text-ctp-mauve">(new)</span>
											{:else}
												vs {formatAmount(c.baseline, $settings.currency)} avg
											{/if}
											<span class="font-semibold text-ctp-red"
												>+{formatAmount(c.delta, $settings.currency)}</span
											>
										</li>
									{/each}
								</ul>
							{/if}
							<ul
								class="mt-2 flex flex-col gap-0.5"
								data-testid={`analytics-wentup-transactions-${inc.categoryId}`}
							>
								{#each inc.transactions as t (t.id)}
									<li class="flex items-baseline gap-2 text-xs text-ctp-subtext0">
										<span class="tabular-nums text-ctp-overlay0">{t.date.slice(0, 10)}</span>
										<span class="truncate">{t.displayName ?? t.name}</span>
										<span class="ml-auto tabular-nums text-ctp-text"
											>{formatAmount(t.amount, $settings.currency)}</span
										>
									</li>
								{/each}
							</ul>
						</div>
					{/if}
				</li>
			{/each}
		</ul>
		{#if diagnosis.otherIncreasesCount > 0}
			<p class="mt-2 text-xs text-ctp-overlay0" data-testid="analytics-wentup-other">
				Everything else: {diagnosis.otherIncreasesCount} small increases totalling +{formatAmount(
					diagnosis.otherIncreasesTotal,
					$settings.currency
				)}
			</p>
		{/if}
	{/if}
	{#if diagnosis.decreases.length > 0}
		<button
			type="button"
			class="mt-3 flex items-center gap-1.5 text-xs text-ctp-green transition-colors hover:text-ctp-text"
			data-testid="analytics-wentdown-toggle"
			aria-expanded={showDecreases}
			onclick={() => (showDecreases = !showDecreases)}
		>
			<TrendingDown class="h-3.5 w-3.5" />
			What went down: {decreasesSummary}
			<ChevronDown class="h-3.5 w-3.5 transition-transform {showDecreases ? 'rotate-180' : ''}" />
		</button>
		{#if showDecreases}
			<ul class="mt-1.5 flex flex-col gap-1 pl-5" data-testid="analytics-wentdown-list">
				{#each diagnosis.decreases as d (d.categoryId)}
					<li class="text-xs text-ctp-subtext0">
						<span class="font-semibold text-ctp-text">{d.categoryName}</span>
						{formatAmount(d.current, $settings.currency)} vs
						{formatAmount(d.baseline, $settings.currency)} avg
						<span class="font-semibold text-ctp-green"
							>−{formatAmount(Math.abs(amountToNumber(d.delta)), $settings.currency)}</span
						>
					</li>
				{/each}
			</ul>
		{/if}
	{/if}
	{#if diagnosis.latestMonth && diagnosis.baselineFrom && diagnosis.baselineTo}
		<p class="mt-3 text-[11px] text-ctp-overlay0">
			{formatMonthLabel(diagnosis.latestMonth)} vs your monthly average over
			{formatMonthLabel(diagnosis.baselineFrom)}–{formatMonthLabel(diagnosis.baselineTo)}.
		</p>
	{/if}
</section>

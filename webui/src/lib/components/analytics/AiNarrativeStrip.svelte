<script lang="ts">
	import { analyticsRepository } from '$lib/repos';
	import { todayIso, formatMonthLabel } from '$utils/dates';
	import { Sparkles } from '@lucide/svelte';
	import type { AnalyticsNarrative } from '$types';

	let { initial = null }: { initial?: AnalyticsNarrative | null } = $props();

	// Seed-once by design: the prop provides the stored narrative at load;
	// later updates come only from generate().
	// svelte-ignore state_referenced_locally
	let narrative = $state<AnalyticsNarrative | null>(initial);
	let generating = $state(false);
	let error = $state<string | null>(null);

	const generatedLabel = $derived.by(() => {
		if (!narrative) return null;
		const day = narrative.generatedAt.slice(0, 10);
		return `Generated ${day} · about ${formatMonthLabel(narrative.month)}`;
	});

	async function generate(): Promise<void> {
		generating = true;
		error = null;
		try {
			const res = await analyticsRepository.generateNarrative({ asOf: todayIso() });
			narrative = res.narrative;
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to generate insights.';
		} finally {
			generating = false;
		}
	}
</script>

<div
	class="rounded-xl border border-ctp-surface1 bg-ctp-base p-4 shadow-lg shadow-black/20"
	data-testid="analytics-narrative"
>
	<div class="flex flex-wrap items-center justify-between gap-2">
		<p class="flex items-center gap-2 text-sm font-semibold text-ctp-text">
			<Sparkles class="h-4 w-4 text-ctp-mauve" />
			AI summary
		</p>
		<button
			type="button"
			class="inline-flex items-center gap-2 rounded-lg border border-ctp-surface1 px-3 py-1.5 text-xs font-semibold text-ctp-text transition-colors hover:border-ctp-surface2 disabled:opacity-50"
			data-testid="analytics-narrative-generate"
			onclick={generate}
			disabled={generating}
		>
			{#if generating}
				<span
					class="h-3 w-3 animate-spin rounded-full border-2 border-ctp-surface2 border-t-ctp-accent"
				></span>
				Generating…
			{:else}
				{narrative ? 'Regenerate' : 'Generate'}
			{/if}
		</button>
	</div>
	{#if error}
		<p class="mt-2 text-sm text-ctp-red" data-testid="analytics-narrative-error">{error}</p>
	{:else if narrative}
		<p class="mt-2 text-sm leading-relaxed text-ctp-subtext0" data-testid="analytics-narrative-content">
			{narrative.content}
		</p>
		{#if generatedLabel}
			<p class="mt-1.5 text-[11px] text-ctp-overlay0">{generatedLabel}</p>
		{/if}
	{:else}
		<p class="mt-2 text-sm text-ctp-overlay0">
			A short plain-language read on what changed and where you can save. Uses your OpenRouter
			key; nothing is generated until you click.
		</p>
	{/if}
</div>

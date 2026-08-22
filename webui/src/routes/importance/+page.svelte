<script lang="ts">
	import { onMount } from 'svelte';
	import PageHeader from '$components/shell/PageHeader.svelte';
	import PageContent from '$components/shell/PageContent.svelte';
	import SectionCard from '$components/shell/SectionCard.svelte';
	import { categories, refreshCategories } from '$lib/stores/categories';
	import { refreshExpenses } from '$lib/stores/expenses';
	import { refreshSettings, settings } from '$lib/stores/settings';
	import { notify } from '$lib/stores/toasts';
	import { importanceRepository } from '$lib/repos';
	import { amountToNumber, formatAmount } from '$lib/utils/money';
	import type { ExpenseImportance, ImportanceCoverage, TriageMerchant } from '$types';

	/**
	 * Importance triage.
	 *
	 * Importance is the one classification quid asks the user to own, but until
	 * something is hand-set the whole history is unattributed — a stored
	 * "important" is indistinguishable from the untouched default. Correcting
	 * transactions one at a time would take months to add up, so this ranks the
	 * merchants with nothing labelled yet by how much money they carry: the top
	 * handful usually accounts for most of the spend, which is what makes the
	 * classification mean something long before every row has been reviewed.
	 */

	const PAGE_SIZE = 20;
	const CHOICES: { value: ExpenseImportance; label: string; hint: string }[] = [
		{ value: 'essential', label: 'Essential', hint: 'Spend you cannot avoid' },
		{ value: 'important', label: 'Important', hint: 'Worth it, but not fixed' },
		{ value: 'discretionary', label: 'Discretionary', hint: 'Nice to have' }
	];

	let merchants = $state<TriageMerchant[]>([]);
	let coverage = $state<ImportanceCoverage | null>(null);
	let limit = $state(PAGE_SIZE);
	let loading = $state(true);
	let error = $state<string | null>(null);
	// The merchant currently being written, so its row can lock without
	// freezing the rest of the queue.
	let busyKey = $state<string | null>(null);

	const categoryById = $derived(new Map($categories.map((category) => [category.id, category])));

	const labelledPercent = $derived.by(() => {
		if (!coverage) return 0;
		const total = amountToNumber(coverage.totalAmount);
		if (total <= 0) return 0;
		return Math.round((amountToNumber(coverage.labelledAmount) / total) * 100);
	});

	async function load(): Promise<void> {
		loading = true;
		error = null;
		try {
			const result = await importanceRepository.triage(limit);
			merchants = result.merchants;
			coverage = result.coverage;
		} catch (err) {
			error = err instanceof Error ? err.message : 'Could not load the triage queue.';
		} finally {
			loading = false;
		}
	}

	onMount(async () => {
		await Promise.all([refreshCategories(), refreshSettings()]);
		await load();
	});

	async function label(merchant: TriageMerchant, importance: ExpenseImportance): Promise<void> {
		if (busyKey) return;
		busyKey = merchant.merchantKey;
		try {
			const result = await importanceRepository.applyTriage({
				merchantKey: merchant.merchantKey,
				importance
			});
			coverage = result.coverage;
			// Drop the row rather than reloading: the queue is ordered by spend,
			// so a refetch would reshuffle everything under the user's cursor.
			merchants = merchants.filter((row) => row.merchantKey !== merchant.merchantKey);
			// The dashboard reads importance straight off the expenses store.
			await refreshExpenses();
			notify(
				'success',
				`${merchant.merchantName} marked ${importance} (${result.updated} ${
					result.updated === 1 ? 'transaction' : 'transactions'
				}).`
			);
		} catch (err) {
			notify('error', err instanceof Error ? err.message : 'Could not save that.');
		} finally {
			busyKey = null;
		}
	}

	async function showMore(): Promise<void> {
		limit += PAGE_SIZE;
		await load();
	}
</script>

<PageHeader
	heading="Importance"
	text="Teach quid which spending you can't avoid, biggest merchants first."
/>

<PageContent>
	<SectionCard title="What quid knows" subtitle={coverage ? `${labelledPercent}% of spend` : ''}>
		{#if coverage}
			<div class="flex flex-col gap-3" data-testid="importance-coverage">
				<div class="h-2.5 w-full overflow-hidden rounded-full bg-ctp-surface1">
					<div class="h-full bg-ctp-accent" style="width: {labelledPercent}%"></div>
				</div>
				<div class="flex flex-wrap gap-x-6 gap-y-1 text-sm text-ctp-overlay1">
					<span>
						<span class="font-medium text-ctp-text" data-testid="coverage-labelled-amount">
							{formatAmount(coverage.labelledAmount, $settings.currency)}
						</span>
						of {formatAmount(coverage.totalAmount, $settings.currency)} labelled
					</span>
					<span>
						<span class="font-medium text-ctp-text" data-testid="coverage-merchants">
							{coverage.labelledMerchants}
						</span>
						of {coverage.labelledMerchants + coverage.unlabelledMerchants} merchants
					</span>
					{#if coverage.corrections > 0}
						<span>
							<span class="font-medium text-ctp-text">{coverage.overrides}</span>
							of {coverage.corrections} decisions changed what quid proposed
						</span>
					{/if}
				</div>
			</div>
		{:else if loading}
			<p class="text-sm text-ctp-overlay1">Loading…</p>
		{/if}
	</SectionCard>

	<SectionCard
		title="Unlabelled merchants"
		subtitle={merchants.length ? `${merchants.length} shown` : ''}
		padded={false}
	>
		{#if error}
			<p class="p-4 text-sm text-ctp-red" data-testid="triage-error">{error}</p>
		{:else if loading}
			<p class="p-4 text-sm text-ctp-overlay1">Loading…</p>
		{:else if merchants.length === 0}
			<p class="p-4 text-sm text-ctp-overlay1" data-testid="triage-empty">
				Every merchant has an importance you set yourself. New ones will show up here after
				your next import.
			</p>
		{:else}
			<ul class="divide-y divide-ctp-surface1" data-testid="triage-list">
				{#each merchants as merchant (merchant.merchantKey)}
					{@const category = merchant.categoryId ? categoryById.get(merchant.categoryId) : null}
					<li
						class="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between"
						data-testid="triage-row"
						data-merchant={merchant.merchantKey}
					>
						<div class="min-w-0">
							<div class="flex min-w-0 items-center gap-2">
								{#if category}
									<span
										class="cat-chip shrink-0 rounded-md px-2 py-0.5 text-xs font-medium"
										style="--cat: {category.color};"
									>
										{category.name}
									</span>
								{/if}
								<span class="truncate font-medium text-ctp-text" data-testid="triage-merchant">
									{merchant.merchantName}
								</span>
							</div>
							<p class="mt-1 text-sm text-ctp-overlay1">
								<span class="font-medium text-ctp-subtext0">
									{formatAmount(merchant.totalAmount, $settings.currency)}
								</span>
								· {merchant.transactionCount}
								{merchant.transactionCount === 1 ? 'transaction' : 'transactions'}
								· currently {merchant.currentImportance}
							</p>
						</div>
						<div class="flex shrink-0 flex-wrap gap-2">
							{#each CHOICES as choice (choice.value)}
								<button
									type="button"
									title={choice.hint}
									class="rounded-md border px-3 py-1.5 text-sm font-medium transition-colors disabled:opacity-60 {merchant.currentImportance ===
									choice.value
										? 'border-ctp-accent text-ctp-accent'
										: 'border-ctp-surface2 text-ctp-subtext0 hover:border-ctp-accent hover:text-ctp-text'}"
									data-testid="triage-set-{choice.value}"
									disabled={busyKey !== null}
									onclick={() => label(merchant, choice.value)}
								>
									{choice.label}
								</button>
							{/each}
						</div>
					</li>
				{/each}
			</ul>
			{#if coverage && merchants.length < coverage.unlabelledMerchants}
				<div class="border-t border-ctp-surface1 p-4">
					<button
						type="button"
						class="text-sm text-ctp-blue underline"
						data-testid="triage-show-more"
						onclick={showMore}
					>
						Show more
					</button>
				</div>
			{/if}
		{/if}
	</SectionCard>
</PageContent>

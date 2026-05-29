<script lang="ts">
	import { onMount } from 'svelte';
	import {
		amazonOrders,
		deleteAmazonOrder,
		importAmazonCsv,
		linkAmazonOrder,
		matchAllAmazonOrders,
		refreshAmazonOrders,
		suggestedAmazonMatches,
		unlinkAmazonOrder,
		updateAmazonShortName
	} from '$lib/stores/amazonOrders';
	import { expenses, refreshExpenses } from '$lib/stores/expenses';
	import { refreshSettings, settings } from '$lib/stores/settings';
	import { formatAmount } from '$lib/utils/money';
	import type { AmazonOrder, Expense } from '$types';
	import { Check, Link2, Link2Off, Pencil, Search, Trash2, X } from '@lucide/svelte';

	let fileInputEl: HTMLInputElement | null = $state(null);
	let loading = $state(false);
	let actionOrderId: string | null = $state(null);
	let suggestionsByOrderId = $state<Record<string, Expense[]>>({});
	let banner: { kind: 'success' | 'error'; message: string } | null = $state(null);
	let editingOrderId: string | null = $state(null);
	let shortNameDraft = $state('');

	const expenseById = $derived.by(() => {
		const map = new Map<string, Expense>();
		for (const expense of $expenses) map.set(expense.id, expense);
		return map;
	});

	function orderSummary(order: AmazonOrder): string {
		if (order.items.length === 0) return 'No item details';
		const [first, ...rest] = order.items;
		return rest.length === 0 ? first.title : `${first.title} + ${rest.length} more`;
	}

	function orderHeading(order: AmazonOrder): string {
		const trimmed = order.shortName?.trim();
		return trimmed ? trimmed : orderSummary(order);
	}

	function startEditShortName(order: AmazonOrder): void {
		banner = null;
		editingOrderId = order.id;
		shortNameDraft = order.shortName ?? '';
	}

	function cancelEditShortName(): void {
		editingOrderId = null;
		shortNameDraft = '';
	}

	async function saveShortName(orderId: string): Promise<void> {
		actionOrderId = orderId;
		banner = null;
		try {
			await updateAmazonShortName(orderId, shortNameDraft.trim());
			editingOrderId = null;
			shortNameDraft = '';
		} catch (cause) {
			banner = {
				kind: 'error',
				message: cause instanceof Error ? cause.message : 'Could not update name.'
			};
		} finally {
			actionOrderId = null;
		}
	}

	function openFilePicker(): void {
		banner = null;
		fileInputEl?.click();
	}

	async function handleFilesSelected(event: Event): Promise<void> {
		const input = event.target as HTMLInputElement;
		const picked = input.files ? Array.from(input.files) : [];
		input.value = '';
		if (picked.length === 0) return;

		loading = true;
		banner = null;
		try {
			const result = await importAmazonCsv(picked);
			banner = {
				kind: 'success',
				message: `Imported ${result.created}, updated ${result.updated}, auto-linked ${result.autoMatched}. ${result.ambiguous} need review.`
			};
		} catch (cause) {
			banner = { kind: 'error', message: cause instanceof Error ? cause.message : 'Import failed.' };
		} finally {
			loading = false;
		}
	}

	async function matchAll(): Promise<void> {
		loading = true;
		banner = null;
		try {
			const result = await matchAllAmazonOrders();
			banner = {
				kind: 'success',
				message: `Checked ${result.totalOrders} orders, auto-linked ${result.autoMatched}. ${result.ambiguous} remain ambiguous.`
			};
		} catch (cause) {
			banner = { kind: 'error', message: cause instanceof Error ? cause.message : 'Match failed.' };
		} finally {
			loading = false;
		}
	}

	async function loadSuggestions(orderId: string): Promise<void> {
		actionOrderId = orderId;
		banner = null;
		try {
			const suggestions = await suggestedAmazonMatches(orderId);
			suggestionsByOrderId = { ...suggestionsByOrderId, [orderId]: suggestions };
			if (suggestions.length === 0) {
				banner = { kind: 'success', message: 'No likely transaction matches found for that order.' };
			}
		} catch (cause) {
			banner = { kind: 'error', message: cause instanceof Error ? cause.message : 'Could not load matches.' };
		} finally {
			actionOrderId = null;
		}
	}

	async function link(orderId: string, expenseId: string): Promise<void> {
		actionOrderId = orderId;
		banner = null;
		try {
			await linkAmazonOrder(orderId, expenseId);
			const suggestions = await suggestedAmazonMatches(orderId);
			suggestionsByOrderId = { ...suggestionsByOrderId, [orderId]: suggestions };
			banner = { kind: 'success', message: 'Amazon order linked.' };
		} catch (cause) {
			banner = { kind: 'error', message: cause instanceof Error ? cause.message : 'Link failed.' };
		} finally {
			actionOrderId = null;
		}
	}

	async function unlink(orderId: string, expenseId: string): Promise<void> {
		actionOrderId = orderId;
		banner = null;
		try {
			await unlinkAmazonOrder(orderId, expenseId);
			banner = { kind: 'success', message: 'Amazon order unlinked.' };
		} catch (cause) {
			banner = { kind: 'error', message: cause instanceof Error ? cause.message : 'Unlink failed.' };
		} finally {
			actionOrderId = null;
		}
	}

	async function remove(orderId: string): Promise<void> {
		actionOrderId = orderId;
		banner = null;
		try {
			await deleteAmazonOrder(orderId);
			banner = { kind: 'success', message: 'Amazon order deleted.' };
		} catch (cause) {
			banner = { kind: 'error', message: cause instanceof Error ? cause.message : 'Delete failed.' };
		} finally {
			actionOrderId = null;
		}
	}

	onMount(() => {
		void refreshAmazonOrders();
		void refreshExpenses();
		void refreshSettings();
	});
</script>

<svelte:head>
	<title>Amazon orders</title>
</svelte:head>

<section class="flex flex-col gap-6">
	<header class="flex flex-wrap items-start justify-between gap-4">
		<div>
			<h1 class="text-2xl font-semibold tracking-tight text-ctp-text">Amazon orders</h1>
			<p class="mt-1 max-w-2xl text-sm text-ctp-overlay1">
				Import Amazon order CSVs and link orders to matching transactions.
			</p>
		</div>
		<div class="flex flex-wrap items-center gap-2">
			<input
				bind:this={fileInputEl}
				type="file"
				accept=".csv,text/csv"
				multiple
				data-testid="amazon-csv-input"
				class="hidden"
				onchange={handleFilesSelected}
			/>
			<button
				type="button"
				data-testid="amazon-import-button"
				onclick={openFilePicker}
				disabled={loading}
				class="rounded-md bg-ctp-accent px-4 py-2 text-sm font-medium text-ctp-on-accent transition-colors hover:bg-ctp-accent-hover disabled:opacity-60"
			>
				{loading ? 'Working…' : 'Import CSV'}
			</button>
			<button
				type="button"
				data-testid="amazon-match-all-button"
				onclick={matchAll}
				disabled={loading || $amazonOrders.length === 0}
				class="rounded-md border border-ctp-surface2 bg-ctp-base px-4 py-2 text-sm font-medium text-ctp-text transition-colors hover:bg-ctp-surface1 disabled:opacity-60"
			>
				Re-match all
			</button>
		</div>
	</header>

	{#if banner}
		<div
			data-testid="amazon-banner"
			data-kind={banner.kind}
			class="rounded-md border px-4 py-3 text-sm {banner.kind === 'success'
				? 'border-ctp-accent/40 bg-ctp-accent/10 text-ctp-accent'
				: 'border-ctp-red/40 bg-ctp-red/10 text-ctp-red'}"
		>
			{banner.message}
		</div>
	{/if}

	{#if $amazonOrders.length === 0}
		<div class="rounded-lg border border-dashed border-ctp-surface2 px-6 py-16 text-center">
			<p class="font-medium text-ctp-text">No Amazon orders imported yet.</p>
			<p class="mt-1 text-sm text-ctp-overlay1">Upload a CSV export to start matching orders.</p>
		</div>
	{:else}
		<div class="overflow-hidden rounded-lg border border-ctp-surface1 bg-ctp-base">
			{#each $amazonOrders as order (order.id)}
				{@const suggestions = suggestionsByOrderId[order.id] ?? []}
				{@const isLinked = order.linkedExpenseIds.length > 0}
				{@const isEditing = editingOrderId === order.id}
				<li
					class="list-none border-b border-l-2 border-ctp-surface0 p-4 transition-colors last:border-b-0 {isLinked
						? 'border-l-ctp-accent bg-ctp-accent/5'
						: 'border-l-ctp-surface1'}"
					data-testid="amazon-order-row"
				>
					<div class="flex flex-wrap items-start justify-between gap-4">
						<div class="min-w-0 flex-1">
							<div class="mb-2 flex flex-wrap items-center gap-2">
								{#if isLinked}
									<span
										data-testid="amazon-link-status"
										data-link-status="linked"
										class="inline-flex items-center gap-1 rounded-full bg-ctp-accent/15 px-2 py-0.5 text-xs font-medium text-ctp-accent"
									>
										<Check size={12} aria-hidden="true" />
										Linked
									</span>
								{:else}
									<span
										data-testid="amazon-link-status"
										data-link-status="unlinked"
										class="inline-flex items-center gap-1 rounded-full bg-ctp-surface1 px-2 py-0.5 text-xs font-medium text-ctp-overlay1"
									>
										<Link2Off size={12} aria-hidden="true" />
										Not linked
									</span>
								{/if}
								<span class="rounded-full bg-ctp-surface1 px-2 py-0.5 text-xs font-semibold text-ctp-text">
									{formatAmount(order.total, order.currency || $settings.currency)}
								</span>
							</div>

							{#if isEditing}
								<div class="flex items-center gap-1.5">
									<input
										data-testid="amazon-short-name-input"
										type="text"
										maxlength="60"
										bind:value={shortNameDraft}
										placeholder={orderSummary(order)}
										onkeydown={(event) => {
											if (event.key === 'Enter') {
												event.preventDefault();
												void saveShortName(order.id);
											} else if (event.key === 'Escape') {
												event.preventDefault();
												cancelEditShortName();
											}
										}}
										class="min-w-0 flex-1 rounded-md border border-ctp-surface2 bg-ctp-base px-2 py-1 text-sm text-ctp-text focus:border-ctp-accent focus:outline-none"
									/>
									<button
										type="button"
										aria-label="Save name"
										title="Save name"
										onclick={() => void saveShortName(order.id)}
										disabled={actionOrderId === order.id}
										class="rounded-md p-1.5 text-ctp-accent hover:bg-ctp-surface1 disabled:opacity-60"
									>
										<Check size={16} aria-hidden="true" />
									</button>
									<button
										type="button"
										aria-label="Cancel"
										title="Cancel"
										onclick={cancelEditShortName}
										disabled={actionOrderId === order.id}
										class="rounded-md p-1.5 text-ctp-overlay1 hover:bg-ctp-surface1 disabled:opacity-60"
									>
										<X size={16} aria-hidden="true" />
									</button>
								</div>
							{:else}
								<div class="flex items-center gap-1.5">
									<h2 class="truncate text-sm font-semibold text-ctp-text">{orderHeading(order)}</h2>
									<button
										type="button"
										data-testid="amazon-short-name-edit"
										aria-label="Edit name"
										title="Edit name"
										onclick={() => startEditShortName(order)}
										disabled={actionOrderId === order.id}
										class="shrink-0 rounded-md p-1 text-ctp-overlay0 hover:bg-ctp-surface1 hover:text-ctp-text disabled:opacity-60"
									>
										<Pencil size={14} aria-hidden="true" />
									</button>
								</div>
							{/if}

							<p class="mt-1 text-xs text-ctp-overlay1">
								{order.orderDate} · <span class="font-mono">{order.id}</span>
							</p>
							{#if isLinked}
								<div class="mt-2 flex flex-col gap-1 text-xs text-ctp-subtext0">
									{#each order.linkedExpenseIds as expenseId}
										{@const linkedExpense = expenseById.get(expenseId)}
										<div class="flex flex-wrap items-center gap-2">
											<span>
												Linked to {linkedExpense ? `${linkedExpense.displayName ?? linkedExpense.name} (${formatAmount(linkedExpense.amount, $settings.currency)})` : expenseId}
											</span>
											<button
												type="button"
												aria-label="Unlink transaction"
												title="Unlink transaction"
												onclick={() => void unlink(order.id, expenseId)}
												disabled={actionOrderId === order.id}
												class="rounded-md p-1 text-ctp-overlay1 hover:bg-ctp-surface1 hover:text-ctp-text disabled:opacity-60"
											>
												<Link2Off size={14} aria-hidden="true" />
											</button>
										</div>
									{/each}
								</div>
							{/if}
						</div>
						<div class="flex flex-wrap items-center gap-1">
							<button
								type="button"
								aria-label="Find matches"
								title="Find matches"
								onclick={() => void loadSuggestions(order.id)}
								disabled={actionOrderId === order.id}
								class="rounded-md border border-ctp-surface2 p-2 text-ctp-subtext0 transition-colors hover:bg-ctp-surface1 hover:text-ctp-text disabled:opacity-60"
							>
								<Search size={16} aria-hidden="true" />
							</button>
							<button
								type="button"
								aria-label="Delete order"
								title="Delete order"
								onclick={() => void remove(order.id)}
								disabled={actionOrderId === order.id}
								class="rounded-md p-2 text-ctp-red transition-colors hover:bg-ctp-red/10 disabled:opacity-60"
							>
								<Trash2 size={16} aria-hidden="true" />
							</button>
						</div>
					</div>

					{#if suggestions.length > 0}
						<div class="mt-3 rounded-md border border-ctp-surface1">
							{#each suggestions as expense (expense.id)}
								<div class="flex flex-wrap items-center justify-between gap-2 border-b border-ctp-surface0 px-3 py-2 text-sm last:border-b-0">
									<div>
										<p class="font-medium text-ctp-text">{expense.displayName ?? expense.name}</p>
										<p class="text-xs text-ctp-overlay1">{expense.date} · {formatAmount(expense.amount, $settings.currency)}</p>
									</div>
									<button
										type="button"
										aria-label="Link to this transaction"
										title="Link to this transaction"
										onclick={() => void link(order.id, expense.id)}
										disabled={actionOrderId === order.id}
										class="inline-flex items-center gap-1.5 rounded-md bg-ctp-accent px-3 py-1.5 text-sm font-medium text-ctp-on-accent transition-colors hover:bg-ctp-accent-hover disabled:opacity-60"
									>
										<Link2 size={16} aria-hidden="true" />
										Link
									</button>
								</div>
							{/each}
						</div>
					{/if}
				</li>
			{/each}
		</div>
	{/if}
</section>

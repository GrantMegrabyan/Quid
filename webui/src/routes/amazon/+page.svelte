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
		unlinkAmazonOrder
	} from '$lib/stores/amazonOrders';
	import { expenses, refreshExpenses } from '$lib/stores/expenses';
	import { refreshSettings, settings } from '$lib/stores/settings';
	import { formatAmount } from '$lib/utils/money';
	import type { AmazonOrder, Expense } from '$types';

	let fileInputEl: HTMLInputElement | null = $state(null);
	let loading = $state(false);
	let actionOrderId: string | null = $state(null);
	let suggestionsByOrderId = $state<Record<string, Expense[]>>({});
	let banner: { kind: 'success' | 'error'; message: string } | null = $state(null);

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
				? 'border-emerald-200 bg-emerald-50 text-emerald-800 dark:border-emerald-900/60 dark:bg-emerald-950/40 dark:text-emerald-200'
				: 'border-red-200 bg-red-50 text-red-800 dark:border-red-900/60 dark:bg-red-950/40 dark:text-red-200'}"
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
				<li class="list-none border-b border-ctp-surface0 p-4 last:border-b-0" data-testid="amazon-order-row">
					<div class="flex flex-wrap items-start justify-between gap-4">
						<div class="min-w-0 flex-1">
							<div class="flex flex-wrap items-center gap-2">
								<h2 class="truncate text-sm font-semibold text-ctp-text">{orderSummary(order)}</h2>
								<span class="rounded-full bg-orange-50 px-2 py-0.5 text-xs font-medium text-orange-700 dark:bg-orange-950 dark:text-orange-300">
									{formatAmount(order.total, order.currency || $settings.currency)}
								</span>
							</div>
							<p class="mt-1 text-xs text-ctp-overlay1">
								{order.orderDate} · <span class="font-mono">{order.id}</span>
							</p>
							{#if order.linkedExpenseIds.length > 0}
								<div class="mt-2 flex flex-col gap-1 text-xs text-ctp-subtext0">
									{#each order.linkedExpenseIds as expenseId}
										{@const linkedExpense = expenseById.get(expenseId)}
										<div class="flex flex-wrap items-center gap-2">
											<span>
												Linked to {linkedExpense ? `${linkedExpense.displayName ?? linkedExpense.name} (${formatAmount(linkedExpense.amount, $settings.currency)})` : expenseId}
											</span>
											<button
												type="button"
												onclick={() => void unlink(order.id, expenseId)}
												disabled={actionOrderId === order.id}
												class="rounded border border-ctp-surface1 px-2 py-0.5 text-xs hover:bg-ctp-surface1 disabled:opacity-60"
											>
												Unlink
											</button>
										</div>
									{/each}
								</div>
							{/if}
						</div>
						<div class="flex flex-wrap items-center gap-2">
							<button
								type="button"
								onclick={() => void loadSuggestions(order.id)}
								disabled={actionOrderId === order.id}
								class="rounded-md border border-ctp-surface2 px-3 py-1.5 text-sm text-ctp-subtext0 hover:bg-ctp-surface1 disabled:opacity-60"
							>
								Find matches
							</button>
							<button
								type="button"
								onclick={() => void remove(order.id)}
								disabled={actionOrderId === order.id}
								class="rounded-md px-3 py-1.5 text-sm text-red-600 hover:bg-red-50 disabled:opacity-60 dark:text-red-400 dark:hover:bg-red-950/40"
							>
								Delete
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
										onclick={() => void link(order.id, expense.id)}
										disabled={actionOrderId === order.id}
										class="rounded-md bg-ctp-accent px-3 py-1.5 text-sm font-medium text-ctp-on-accent hover:bg-ctp-accent-hover disabled:opacity-60"
									>
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

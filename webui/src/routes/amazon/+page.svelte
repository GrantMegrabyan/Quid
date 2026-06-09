<script lang="ts">
	import { onMount } from 'svelte';
	import {
		AMAZON_ORDERS_PAGE_SIZE,
		amazonOrders,
		amazonOrderQuery,
		amazonOrdersLoading,
		amazonOrdersTotal,
		confirmRecategorizeAmazon,
		deleteAmazonOrder,
		importAmazonCsv,
		importAmazonExport,
		linkAmazonOrder,
		matchAllAmazonOrders,
		previewRecategorizeAmazon,
		refreshAmazonOrders,
		setAmazonOrderFilters,
		setAmazonOrderPage,
		suggestedAmazonMatches,
		unlinkAmazonOrder,
		updateAmazonOrderCategory,
		updateAmazonShortName
	} from '$lib/stores/amazonOrders';
	import { buildBookmarkletHref } from '$lib/amazon/bookmarklet';
	import { categories, refreshCategories } from '$lib/stores/categories';
	import { refreshSettings, settings } from '$lib/stores/settings';
	import { formatAmount } from '$lib/utils/money';
	import { UNCATEGORIZED_ID } from '$lib/types';
	import type {
		AmazonImportResult,
		AmazonImportSkippedOrder,
		AmazonExportRequest,
		AmazonLinkedExpense,
		AmazonOrder,
		AmazonRecategorizePreviewRow,
		Category,
		Expense
	} from '$types';
	import { Check, Link2, Link2Off, Pencil, Search, Sparkles, Trash2, X } from '@lucide/svelte';

	let fileInputEl: HTMLInputElement | null = $state(null);
	let exportFileInputEl: HTMLInputElement | null = $state(null);
	let loading = $state(false);
	let actionOrderId: string | null = $state(null);
	let suggestionsByOrderId = $state<Record<string, Expense[]>>({});
	let banner: { kind: 'success' | 'error'; message: string } | null = $state(null);
	let editingOrderId: string | null = $state(null);
	let shortNameDraft = $state('');
	let categoryEditingOrderId: string | null = $state(null);

	// Filter / search / pagination controls. Single source of truth for the
	// three filter values; `applyFilters()` pushes them to the store (which
	// resets to page 0 and re-fetches). Search is debounced.
	let searchText = $state('');
	let linkedFilter = $state<'all' | 'linked' | 'unlinked'>('all');
	let categoryFilter = $state<string | undefined>(undefined);
	let searchDebounce: ReturnType<typeof setTimeout> | null = null;

	function linkedFilterValue(): boolean | undefined {
		if (linkedFilter === 'linked') return true;
		if (linkedFilter === 'unlinked') return false;
		return undefined;
	}

	function applyFilters(): void {
		void setAmazonOrderFilters({
			linked: linkedFilterValue(),
			categoryId: categoryFilter,
			search: searchText.trim()
		});
	}

	function onSearchInput(value: string): void {
		searchText = value;
		if (searchDebounce) clearTimeout(searchDebounce);
		searchDebounce = setTimeout(() => {
			searchDebounce = null;
			applyFilters();
		}, 300);
	}

	function onLinkedFilterChange(value: string): void {
		linkedFilter = value === 'linked' ? 'linked' : value === 'unlinked' ? 'unlinked' : 'all';
		applyFilters();
	}

	function onCategoryFilterChange(value: string): void {
		// '__all__' -> undefined (all), '' -> '' (no category), else a real id.
		categoryFilter = value === '__all__' ? undefined : value;
		applyFilters();
	}

	function clearFilters(): void {
		if (searchDebounce) {
			clearTimeout(searchDebounce);
			searchDebounce = null;
		}
		searchText = '';
		linkedFilter = 'all';
		categoryFilter = undefined;
		void setAmazonOrderFilters({});
	}

	const filtersActive = $derived(
		$amazonOrderQuery.linked !== undefined ||
			$amazonOrderQuery.categoryId !== undefined ||
			($amazonOrderQuery.search ?? '') !== ''
	);

	// Pagination math derived from the active query window + total count.
	const pageLimit = $derived($amazonOrderQuery.limit ?? AMAZON_ORDERS_PAGE_SIZE);
	const currentPage = $derived(Math.floor(($amazonOrderQuery.offset ?? 0) / pageLimit));
	const pageCount = $derived(Math.max(1, Math.ceil($amazonOrdersTotal / pageLimit)));
	const showingFrom = $derived(
		$amazonOrders.length === 0 ? 0 : ($amazonOrderQuery.offset ?? 0) + 1
	);
	const showingTo = $derived(($amazonOrderQuery.offset ?? 0) + $amazonOrders.length);

	// Browser-export import panel.
	let exportPanelOpen = $state(false);
	let exportPasteText = $state('');
	let skippedOrders = $state<AmazonImportSkippedOrder[]>([]);
	const bookmarkletHref = buildBookmarkletHref();

	// AI re-categorise preview/confirm.
	type RecategorizeRow = AmazonRecategorizePreviewRow & { accept: boolean };
	let recategorizing = $state(false);
	let recategorizeRows = $state<RecategorizeRow[] | null>(null);
	let recategorizeSummary = $state<{ changed: number; unchanged: number } | null>(null);
	let showUnchanged = $state(false);
	let confirmingRecategorize = $state(false);

	const visibleRecategorizeRows = $derived.by(() =>
		(recategorizeRows ?? []).filter((row) => showUnchanged || row.changed)
	);
	const acceptedRecategorizeCount = $derived.by(
		() => (recategorizeRows ?? []).filter((row) => row.accept).length
	);

	// Linked Amazon charges can be from ANY date, so this page can't rely on the
	// dashboard's scoped expense window. Each order carries its linked expenses'
	// label data inline (server-resolved), so we build the lookup from the
	// orders themselves instead of fetching the whole expense table.
	const expenseById = $derived.by(() => {
		const map = new Map<string, AmazonLinkedExpense>();
		for (const order of $amazonOrders) {
			for (const linked of order.linkedExpenses) map.set(linked.id, linked);
		}
		return map;
	});

	const categoryById = $derived.by(() => {
		const map = new Map<string, Category>();
		for (const category of $categories) map.set(category.id, category);
		return map;
	});

	function orderCategory(order: AmazonOrder): Category | null {
		if (!order.categoryId || order.categoryId === UNCATEGORIZED_ID) return null;
		return categoryById.get(order.categoryId) ?? null;
	}

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

	function startEditCategory(order: AmazonOrder): void {
		banner = null;
		categoryEditingOrderId = order.id;
	}

	function cancelEditCategory(): void {
		categoryEditingOrderId = null;
	}

	async function saveCategory(orderId: string, rawValue: string): Promise<void> {
		const categoryId = rawValue === '' || rawValue === UNCATEGORIZED_ID ? null : rawValue;
		actionOrderId = orderId;
		banner = null;
		try {
			await updateAmazonOrderCategory(orderId, categoryId);
			categoryEditingOrderId = null;
		} catch (cause) {
			banner = {
				kind: 'error',
				message: cause instanceof Error ? cause.message : 'Could not update category.'
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
		skippedOrders = [];
		try {
			const result = await importAmazonCsv(picked);
			applyImportResult(result);
		} catch (cause) {
			banner = { kind: 'error', message: cause instanceof Error ? cause.message : 'Import failed.' };
		} finally {
			loading = false;
		}
	}

	function toggleExportPanel(): void {
		banner = null;
		exportPanelOpen = !exportPanelOpen;
	}

	function applyImportResult(result: AmazonImportResult): void {
		const report = result.files[0];
		skippedOrders = report?.skipped ?? [];
		const skippedNote =
			skippedOrders.length > 0 ? ` ${skippedOrders.length} skipped (see details).` : '';
		banner = {
			kind: 'success',
			message: `Imported ${result.created}, updated ${result.updated}, auto-linked ${result.autoMatched}. ${result.ambiguous} need review.${skippedNote}`
		};
	}

	function parseExportPayload(raw: string): AmazonExportRequest {
		const trimmed = raw.trim();
		if (!trimmed) throw new Error('Paste the exported JSON first.');
		let parsed: unknown;
		try {
			parsed = JSON.parse(trimmed);
		} catch {
			throw new Error('Invalid JSON — paste the file the bookmarklet downloaded.');
		}
		if (
			typeof parsed !== 'object' ||
			parsed === null ||
			!Array.isArray((parsed as { orders?: unknown }).orders)
		) {
			throw new Error('Invalid JSON — expected an object with an "orders" array.');
		}
		return parsed as AmazonExportRequest;
	}

	async function submitExportPayload(payload: AmazonExportRequest): Promise<void> {
		loading = true;
		banner = null;
		skippedOrders = [];
		try {
			const result = await importAmazonExport(payload);
			applyImportResult(result);
			exportPasteText = '';
		} catch (cause) {
			banner = {
				kind: 'error',
				message: cause instanceof Error ? cause.message : 'Import failed.'
			};
		} finally {
			loading = false;
		}
	}

	function openExportFilePicker(): void {
		banner = null;
		exportFileInputEl?.click();
	}

	async function handleExportFileSelected(event: Event): Promise<void> {
		const input = event.target as HTMLInputElement;
		const picked = input.files?.[0] ?? null;
		input.value = '';
		if (!picked) return;
		banner = null;
		skippedOrders = [];
		let payload: AmazonExportRequest;
		try {
			payload = parseExportPayload(await picked.text());
		} catch (cause) {
			banner = {
				kind: 'error',
				message: cause instanceof Error ? cause.message : 'Invalid JSON.'
			};
			return;
		}
		await submitExportPayload(payload);
	}

	async function handleExportPasteSubmit(): Promise<void> {
		banner = null;
		skippedOrders = [];
		let payload: AmazonExportRequest;
		try {
			payload = parseExportPayload(exportPasteText);
		} catch (cause) {
			banner = {
				kind: 'error',
				message: cause instanceof Error ? cause.message : 'Invalid JSON.'
			};
			return;
		}
		await submitExportPayload(payload);
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

	async function startRecategorize(): Promise<void> {
		recategorizing = true;
		banner = null;
		recategorizeRows = null;
		recategorizeSummary = null;
		showUnchanged = false;
		try {
			const result = await previewRecategorizeAmazon();
			recategorizeRows = result.rows.map((row) => ({ ...row, accept: row.changed }));
			recategorizeSummary = { changed: result.changed, unchanged: result.unchanged };
			if (result.eligible === 0) {
				banner = {
					kind: 'success',
					message: 'No orders have enough detail to re-categorise.'
				};
				recategorizeRows = null;
			} else if (result.changed === 0) {
				banner = {
					kind: 'success',
					message: 'AI suggests no category changes — everything already matches.'
				};
			}
		} catch (cause) {
			banner = {
				kind: 'error',
				message: cause instanceof Error ? cause.message : 'Could not generate suggestions.'
			};
		} finally {
			recategorizing = false;
		}
	}

	function cancelRecategorize(): void {
		recategorizeRows = null;
		recategorizeSummary = null;
	}

	function toggleAllAccepted(next: boolean): void {
		if (!recategorizeRows) return;
		recategorizeRows = recategorizeRows.map((row) =>
			showUnchanged || row.changed ? { ...row, accept: next } : row
		);
	}

	async function confirmRecategorize(): Promise<void> {
		if (!recategorizeRows) return;
		const accepted = recategorizeRows.filter((row) => row.accept);
		if (accepted.length === 0) {
			banner = { kind: 'error', message: 'Select at least one order to re-categorise.' };
			return;
		}
		confirmingRecategorize = true;
		banner = null;
		try {
			const result = await confirmRecategorizeAmazon(
				accepted.map((row) => ({ orderId: row.orderId, categoryName: row.suggestedCategoryName }))
			);
			recategorizeRows = null;
			recategorizeSummary = null;
			banner = {
				kind: 'success',
				message: `Re-categorised ${result.updated} order${result.updated === 1 ? '' : 's'}${
					result.categoriesCreated > 0
						? `, created ${result.categoriesCreated} categor${result.categoriesCreated === 1 ? 'y' : 'ies'}`
						: ''
				}, updated ${result.expensesUpdated} linked transaction${
					result.expensesUpdated === 1 ? '' : 's'
				}.`
			};
		} catch (cause) {
			banner = {
				kind: 'error',
				message: cause instanceof Error ? cause.message : 'Re-categorise failed.'
			};
		} finally {
			confirmingRecategorize = false;
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
		void refreshSettings();
		void refreshCategories();
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
				Import Amazon orders — from a CSV export or straight from your browser — and
				link them to matching transactions.
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
			<input
				bind:this={exportFileInputEl}
				type="file"
				accept=".json,application/json"
				data-testid="amazon-export-file-input"
				class="hidden"
				onchange={handleExportFileSelected}
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
				data-testid="amazon-export-import-button"
				onclick={toggleExportPanel}
				disabled={loading}
				aria-expanded={exportPanelOpen}
				class="rounded-md border border-ctp-surface2 bg-ctp-base px-4 py-2 text-sm font-medium text-ctp-text transition-colors hover:bg-ctp-surface1 disabled:opacity-60"
			>
				Import from browser
			</button>
			<button
				type="button"
				data-testid="amazon-match-all-button"
				onclick={matchAll}
				disabled={loading || $amazonOrdersTotal === 0}
				class="rounded-md border border-ctp-surface2 bg-ctp-base px-4 py-2 text-sm font-medium text-ctp-text transition-colors hover:bg-ctp-surface1 disabled:opacity-60"
			>
				Re-match all
			</button>
			<button
				type="button"
				data-testid="amazon-recategorize-button"
				onclick={startRecategorize}
				disabled={loading || recategorizing || $amazonOrdersTotal === 0}
				class="inline-flex items-center gap-1.5 rounded-md border border-ctp-surface2 bg-ctp-base px-4 py-2 text-sm font-medium text-ctp-text transition-colors hover:bg-ctp-surface1 disabled:opacity-60"
			>
				<Sparkles size={15} aria-hidden="true" />
				{recategorizing ? 'Thinking…' : 'Re-categorise (AI)'}
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

	{#if exportPanelOpen}
		<div
			data-testid="amazon-export-panel"
			class="flex flex-col gap-4 rounded-lg border border-ctp-surface1 bg-ctp-base p-5"
		>
			<div>
				<h2 class="text-sm font-semibold text-ctp-text">Import from your browser</h2>
				<p class="mt-1 text-sm text-ctp-overlay1">
					Drag the button below to your bookmarks bar. Open your Amazon orders page
					(<span class="text-ctp-subtext0">Returns &amp; Orders</span>), click the
					bookmark, then upload the downloaded <span class="font-mono">.json</span> here.
					No Amazon password or session is ever sent to quid.
				</p>
			</div>

			<div class="flex flex-wrap items-center gap-3">
				<a
					href={bookmarkletHref}
					data-testid="amazon-bookmarklet-link"
					onclick={(event) => event.preventDefault()}
					class="inline-flex cursor-grab items-center gap-2 rounded-md border border-dashed border-ctp-accent/50 bg-ctp-accent/10 px-4 py-2 text-sm font-medium text-ctp-accent active:cursor-grabbing"
					title="Drag me to your bookmarks bar"
				>
					Sync Amazon → quid
				</a>
				<span class="text-xs text-ctp-overlay1">
					Drag this to your bookmarks bar. Can't drag it? Create a bookmark manually
					and paste this link's address as the URL.
				</span>
			</div>

			<div class="flex flex-col gap-2">
				<span class="text-xs font-medium uppercase tracking-wide text-ctp-overlay1">
					1 · Upload the downloaded file
				</span>
				<button
					type="button"
					data-testid="amazon-export-upload-button"
					onclick={openExportFilePicker}
					disabled={loading}
					class="self-start rounded-md bg-ctp-accent px-4 py-2 text-sm font-medium text-ctp-on-accent transition-colors hover:bg-ctp-accent-hover disabled:opacity-60"
				>
					{loading ? 'Working…' : 'Upload .json'}
				</button>
			</div>

			<div class="flex flex-col gap-2">
				<span class="text-xs font-medium uppercase tracking-wide text-ctp-overlay1">
					2 · Or paste the JSON
				</span>
				<textarea
					data-testid="amazon-export-textarea"
					bind:value={exportPasteText}
					rows="4"
					placeholder={'{ "orders": [ … ] }'}
					class="field w-full font-mono text-xs"
				></textarea>
				<button
					type="button"
					data-testid="amazon-export-submit"
					onclick={handleExportPasteSubmit}
					disabled={loading || exportPasteText.trim() === ''}
					class="self-start rounded-md border border-ctp-surface2 bg-ctp-base px-4 py-2 text-sm font-medium text-ctp-text transition-colors hover:bg-ctp-surface1 disabled:opacity-60"
				>
					Import pasted JSON
				</button>
			</div>
		</div>
	{/if}

	{#if skippedOrders.length > 0}
		<div
			data-testid="amazon-export-skipped"
			class="rounded-md border border-ctp-yellow/40 bg-ctp-yellow/10 px-4 py-3 text-sm text-ctp-text"
		>
			<p class="font-medium text-ctp-yellow">
				{skippedOrders.length} order{skippedOrders.length === 1 ? '' : 's'} skipped
			</p>
			<ul class="mt-2 flex flex-col gap-1 text-xs text-ctp-subtext0">
				{#each skippedOrders as skipped, i (skipped.orderId + skipped.reason + i)}
					<li data-testid="amazon-export-skipped-row">
						<span class="font-mono">{skipped.orderId || '(no order id)'}</span> —
						{skipped.reason}
					</li>
				{/each}
			</ul>
		</div>
	{/if}

	{#if recategorizeRows}
		<div
			data-testid="amazon-recategorize-panel"
			class="flex flex-col gap-4 rounded-lg border border-ctp-surface1 bg-ctp-base p-5"
		>
			<div class="flex flex-wrap items-start justify-between gap-3">
				<div>
					<h2 class="flex items-center gap-2 text-sm font-semibold text-ctp-text">
						<Sparkles size={15} aria-hidden="true" class="text-ctp-accent" />
						Review AI re-categorisation
					</h2>
					<p class="mt-1 text-sm text-ctp-overlay1">
						{recategorizeSummary?.changed ?? 0} order{(recategorizeSummary?.changed ?? 0) === 1
							? ''
							: 's'} would change category.
						{#if (recategorizeSummary?.unchanged ?? 0) > 0}
							{recategorizeSummary?.unchanged} already match and are hidden.
						{/if}
						Tick the rows to apply, then confirm.
					</p>
				</div>
				<label
					class="inline-flex cursor-pointer items-center gap-2 text-xs font-medium text-ctp-subtext0"
				>
					<input
						type="checkbox"
						data-testid="amazon-recategorize-show-unchanged"
						bind:checked={showUnchanged}
						class="h-3.5 w-3.5 rounded border-ctp-surface2 text-ctp-accent focus:ring-ctp-accent"
					/>
					Show unchanged ({recategorizeSummary?.unchanged ?? 0})
				</label>
			</div>

			{#if visibleRecategorizeRows.length === 0}
				<p
					data-testid="amazon-recategorize-empty"
					class="rounded-md border border-dashed border-ctp-surface2 px-4 py-6 text-center text-sm text-ctp-overlay1"
				>
					Nothing to show. {(recategorizeSummary?.unchanged ?? 0) > 0
						? 'Toggle “Show unchanged” to see orders that already match.'
						: ''}
				</p>
			{:else}
				<div class="overflow-hidden rounded-md border border-ctp-surface1">
					<table class="w-full text-left text-sm">
						<thead class="bg-ctp-surface0/50 text-xs uppercase tracking-wide text-ctp-overlay1">
							<tr>
								<th class="w-10 px-3 py-2">
									<input
										type="checkbox"
										data-testid="amazon-recategorize-select-all"
										aria-label="Select all visible"
										checked={visibleRecategorizeRows.every((row) => row.accept)}
										onchange={(event) => toggleAllAccepted(event.currentTarget.checked)}
										class="h-3.5 w-3.5 rounded border-ctp-surface2 text-ctp-accent focus:ring-ctp-accent"
									/>
								</th>
								<th class="px-3 py-2 font-medium">Order</th>
								<th class="px-3 py-2 text-right font-medium">Total</th>
								<th class="px-3 py-2 font-medium">Current</th>
								<th class="px-3 py-2 font-medium">Suggested</th>
							</tr>
						</thead>
						<tbody>
							{#each visibleRecategorizeRows as row (row.orderId)}
								<tr
									data-testid="amazon-recategorize-row"
									data-changed={row.changed}
									class="border-t border-ctp-surface0 {row.accept ? 'bg-ctp-accent/5' : ''}"
								>
									<td class="px-3 py-2 align-top">
										<input
											type="checkbox"
											data-testid="amazon-recategorize-accept"
											aria-label="Apply this suggestion"
											bind:checked={row.accept}
											class="mt-0.5 h-3.5 w-3.5 rounded border-ctp-surface2 text-ctp-accent focus:ring-ctp-accent"
										/>
									</td>
									<td class="px-3 py-2 align-top">
										<p class="font-medium text-ctp-text">{row.name}</p>
										<p class="text-xs text-ctp-overlay1">
											{row.orderDate} · <span class="font-mono">{row.orderId}</span>
										</p>
									</td>
									<td class="px-3 py-2 text-right align-top font-mono text-ctp-subtext0">
										{formatAmount(row.total, $settings.currency)}
									</td>
									<td class="px-3 py-2 align-top text-ctp-subtext0">
										{row.currentCategoryName ?? '—'}
									</td>
									<td class="px-3 py-2 align-top">
										<span class="inline-flex items-center gap-1.5 font-medium text-ctp-text">
											{row.suggestedCategoryName}
											{#if !row.suggestedCategoryExists}
												<span
													data-testid="amazon-recategorize-new-badge"
													class="rounded-full bg-ctp-accent/15 px-1.5 py-0.5 text-[10px] font-semibold uppercase text-ctp-accent"
												>
													New
												</span>
											{/if}
										</span>
									</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			{/if}

			<div class="flex flex-wrap items-center justify-end gap-2">
				<button
					type="button"
					data-testid="amazon-recategorize-cancel"
					onclick={cancelRecategorize}
					disabled={confirmingRecategorize}
					class="rounded-md border border-ctp-surface2 bg-ctp-base px-4 py-2 text-sm font-medium text-ctp-text transition-colors hover:bg-ctp-surface1 disabled:opacity-60"
				>
					Cancel
				</button>
				<button
					type="button"
					data-testid="amazon-recategorize-confirm"
					onclick={confirmRecategorize}
					disabled={confirmingRecategorize || acceptedRecategorizeCount === 0}
					class="rounded-md bg-ctp-accent px-4 py-2 text-sm font-medium text-ctp-on-accent transition-colors hover:bg-ctp-accent-hover disabled:opacity-60"
				>
					{confirmingRecategorize
						? 'Applying…'
						: `Apply ${acceptedRecategorizeCount} change${acceptedRecategorizeCount === 1 ? '' : 's'}`}
				</button>
			</div>
		</div>
	{/if}

	<div
		class="flex flex-col gap-3 rounded-lg border border-ctp-surface1 bg-ctp-base p-3 sm:flex-row sm:items-center sm:gap-3"
	>
		<div class="relative flex-1">
			<Search
				size={16}
				aria-hidden="true"
				class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ctp-overlay1"
			/>
			<input
				data-testid="amazon-search-input"
				type="search"
				placeholder="Search orders, items, names…"
				value={searchText}
				oninput={(event) => onSearchInput(event.currentTarget.value)}
				class="field w-full pl-9 pr-3"
			/>
		</div>
		<select
			data-testid="amazon-linked-filter"
			value={linkedFilter}
			onchange={(event) => onLinkedFilterChange(event.currentTarget.value)}
			class="field field-select"
		>
			<option value="all">All</option>
			<option value="linked">Linked</option>
			<option value="unlinked">Not linked</option>
		</select>
		<select
			data-testid="amazon-category-filter"
			value={categoryFilter === undefined ? '__all__' : categoryFilter}
			onchange={(event) => onCategoryFilterChange(event.currentTarget.value)}
			class="field field-select"
		>
			<option value="__all__">All categories</option>
			<option value="">No category</option>
			{#each $categories as cat (cat.id)}
				{#if cat.id !== UNCATEGORIZED_ID}
					<option value={cat.id}>{cat.name}</option>
				{/if}
			{/each}
		</select>
	</div>

	{#if $amazonOrders.length === 0 && !filtersActive && $amazonOrdersTotal === 0}
		<div class="rounded-lg border border-dashed border-ctp-surface2 px-6 py-16 text-center">
			<p class="font-medium text-ctp-text">No Amazon orders imported yet.</p>
			<p class="mt-1 text-sm text-ctp-overlay1">Upload a CSV export to start matching orders.</p>
		</div>
	{:else if $amazonOrders.length === 0}
		<div class="rounded-lg border border-dashed border-ctp-surface2 px-6 py-16 text-center">
			<p class="font-medium text-ctp-text">No orders match your filters.</p>
			<p class="mt-1 text-sm text-ctp-overlay1">
				Try a different search or clear the filters to see everything.
			</p>
			<button
				type="button"
				data-testid="amazon-clear-filters"
				onclick={clearFilters}
				class="mt-4 rounded-md border border-ctp-surface2 bg-ctp-base px-4 py-2 text-sm font-medium text-ctp-text transition-colors hover:bg-ctp-surface1"
			>
				Clear filters
			</button>
		</div>
	{:else}
		<div class="flex flex-col gap-3">
			{#each $amazonOrders as order (order.id)}
				{@const suggestions = suggestionsByOrderId[order.id] ?? []}
				{@const isLinked = order.linkedExpenseIds.length > 0}
				{@const isEditing = editingOrderId === order.id}
				{@const isEditingCategory = categoryEditingOrderId === order.id}
				{@const category = orderCategory(order)}
				<div
					class="rounded-lg border border-ctp-surface1 border-l-2 bg-ctp-base px-3 py-2 transition-colors {isLinked
						? 'border-l-ctp-accent bg-ctp-accent/5'
						: 'border-l-ctp-surface1'}"
					data-testid="amazon-order-row"
				>
					<div class="flex flex-wrap items-center gap-3">
						{#if isLinked}
							<span
								data-testid="amazon-link-status"
								data-link-status="linked"
								title="Linked"
								class="inline-flex shrink-0 items-center justify-center rounded-full bg-ctp-accent/15 p-1 text-ctp-accent"
							>
								<Check size={14} aria-hidden="true" />
							</span>
						{:else}
							<span
								data-testid="amazon-link-status"
								data-link-status="unlinked"
								title="Not linked"
								class="inline-flex shrink-0 items-center justify-center rounded-full bg-ctp-surface1 p-1 text-ctp-overlay1"
							>
								<Link2Off size={14} aria-hidden="true" />
							</span>
						{/if}

						{#if isEditing}
							<div class="flex min-w-0 flex-1 items-center gap-1.5">
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
							<div class="flex min-w-0 flex-1 items-center gap-1.5">
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

						{#if isEditingCategory}
							<select
								data-testid="amazon-category-select"
								value={order.categoryId ?? ''}
								onchange={(event) => void saveCategory(order.id, event.currentTarget.value)}
								onkeydown={(event) => {
									if (event.key === 'Escape') {
										event.preventDefault();
										cancelEditCategory();
									}
								}}
								disabled={actionOrderId === order.id}
								class="shrink-0 rounded-full border border-ctp-surface2 bg-ctp-base px-2 py-0.5 text-xs text-ctp-text focus:border-ctp-accent focus:outline-none disabled:opacity-60"
							>
								<option value="">— No category —</option>
								{#each $categories as cat (cat.id)}
									{#if cat.id !== UNCATEGORIZED_ID}
										<option value={cat.id}>{cat.name}</option>
									{/if}
								{/each}
							</select>
							<button
								type="button"
								aria-label="Cancel category"
								title="Cancel"
								onclick={cancelEditCategory}
								disabled={actionOrderId === order.id}
								class="shrink-0 rounded-md p-1 text-ctp-overlay1 hover:bg-ctp-surface1 disabled:opacity-60"
							>
								<X size={14} aria-hidden="true" />
							</button>
						{:else if category}
							<button
								type="button"
								data-testid="amazon-order-category"
								data-category-id={category.id}
								onclick={() => startEditCategory(order)}
								disabled={actionOrderId === order.id}
								class="inline-flex shrink-0 items-center gap-1.5 rounded-full border border-ctp-surface2 bg-ctp-surface1 px-2 py-0.5 text-xs font-medium text-ctp-text transition-colors hover:bg-ctp-surface2 disabled:opacity-60"
								title="Change category"
							>
								<span
									aria-hidden="true"
									class="h-2 w-2 shrink-0 rounded-full"
									style="background-color: {category.color || '#9ca3af'};"
								></span>
								{category.name}
								<Pencil
									data-testid="amazon-category-edit"
									size={11}
									aria-hidden="true"
									class="text-ctp-overlay0"
								/>
							</button>
						{:else}
							<button
								type="button"
								data-testid="amazon-order-category"
								data-category-id=""
								onclick={() => startEditCategory(order)}
								disabled={actionOrderId === order.id}
								class="inline-flex shrink-0 items-center gap-1.5 rounded-full border border-dashed border-ctp-surface2 px-2 py-0.5 text-xs font-medium text-ctp-overlay1 transition-colors hover:bg-ctp-surface1 hover:text-ctp-text disabled:opacity-60"
								title="Set category"
							>
								<span aria-hidden="true" class="h-2 w-2 shrink-0 rounded-full bg-ctp-overlay0"></span>
								No category
								<Pencil
									data-testid="amazon-category-edit"
									size={11}
									aria-hidden="true"
									class="text-ctp-overlay0"
								/>
							</button>
						{/if}

						<span
							class="shrink-0 rounded-full bg-ctp-surface1 px-2 py-0.5 text-xs font-semibold text-ctp-text"
						>
							{formatAmount(order.total, order.currency || $settings.currency)}
						</span>

						<span class="shrink-0 text-xs text-ctp-overlay1">
							{order.orderDate} · <span class="font-mono">{order.id}</span>
						</span>

						<div class="ml-auto flex shrink-0 items-center gap-1">
							<button
								type="button"
								aria-label="Find matches"
								title="Find matches"
								onclick={() => void loadSuggestions(order.id)}
								disabled={actionOrderId === order.id}
								class="rounded-md border border-ctp-surface2 p-1.5 text-ctp-subtext0 transition-colors hover:bg-ctp-surface1 hover:text-ctp-text disabled:opacity-60"
							>
								<Search size={16} aria-hidden="true" />
							</button>
							<button
								type="button"
								aria-label="Delete order"
								title="Delete order"
								onclick={() => void remove(order.id)}
								disabled={actionOrderId === order.id}
								class="rounded-md p-1.5 text-ctp-red transition-colors hover:bg-ctp-red/10 disabled:opacity-60"
							>
								<Trash2 size={16} aria-hidden="true" />
							</button>
						</div>
					</div>

					{#if isLinked}
						<div class="mt-2 flex flex-col gap-1 text-xs text-ctp-subtext0">
							{#each order.linkedExpenseIds as expenseId}
								{@const linkedExpense = expenseById.get(expenseId)}
								<div class="flex flex-wrap items-center gap-2">
									<span>
										Linked to {linkedExpense
											? `${linkedExpense.displayName ?? linkedExpense.name} (${formatAmount(linkedExpense.amount, $settings.currency)})`
											: expenseId}
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

					{#if suggestions.length > 0}
						<div class="mt-3 rounded-md border border-ctp-surface1">
							{#each suggestions as expense (expense.id)}
								<div class="flex flex-wrap items-center justify-between gap-2 border-b border-ctp-surface0 px-3 py-2 text-sm last:border-b-0">
									<div>
										<p class="font-medium text-ctp-text">{expense.displayName ?? expense.name}</p>
										<p class="text-xs text-ctp-overlay1">{expense.date.slice(0, 10)} · {formatAmount(expense.amount, $settings.currency)}</p>
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
				</div>
			{/each}
		</div>
	{/if}

	{#if $amazonOrdersTotal > 0}
		<div
			class="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-ctp-surface1 bg-ctp-base px-4 py-3 text-sm text-ctp-subtext0"
		>
			<p data-testid="amazon-pagination-summary">
				Showing <span class="font-medium text-ctp-text">{showingFrom}</span>–<span
					class="font-medium text-ctp-text">{showingTo}</span
				>
				of <span class="font-medium text-ctp-text">{$amazonOrdersTotal}</span>
			</p>
			<div class="flex items-center gap-2">
				<span class="text-xs text-ctp-overlay1">Page {currentPage + 1} of {pageCount}</span>
				<button
					type="button"
					data-testid="amazon-prev-page"
					onclick={() => void setAmazonOrderPage(currentPage - 1)}
					disabled={$amazonOrdersLoading || currentPage <= 0}
					class="rounded-md border border-ctp-surface2 bg-ctp-base px-3 py-1.5 text-sm font-medium text-ctp-text transition-colors hover:bg-ctp-surface1 disabled:opacity-50"
				>
					Previous
				</button>
				<button
					type="button"
					data-testid="amazon-next-page"
					onclick={() => void setAmazonOrderPage(currentPage + 1)}
					disabled={$amazonOrdersLoading || currentPage >= pageCount - 1}
					class="rounded-md border border-ctp-surface2 bg-ctp-base px-3 py-1.5 text-sm font-medium text-ctp-text transition-colors hover:bg-ctp-surface1 disabled:opacity-50"
				>
					Next
				</button>
			</div>
		</div>
	{/if}
</section>

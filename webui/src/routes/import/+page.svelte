<script lang="ts">
	import { onMount } from 'svelte';
	import { RepositoryError, expenseRepository } from '$lib/repos';
	import { categories, refreshCategories } from '$lib/stores/categories';
	import { refreshExpenses } from '$lib/stores/expenses';
	import type { Category, ImportCsvPreviewResult, ImportPreviewRow } from '$types';

	type ReviewRow = ImportPreviewRow & {
		selectedCategoryName: string;
		acceptUpdate: boolean;
	};

	let fileInputEl: HTMLInputElement | null = $state(null);
	let aiCategorize = $state(true);
	let loading = $state(false);
	let saving = $state(false);
	let preview: ImportCsvPreviewResult | null = $state(null);
	let rows: ReviewRow[] = $state([]);
	let banner: { kind: 'success' | 'error'; message: string } | null = $state(null);

	const createRows = $derived(rows.filter((row) => row.kind === 'create'));
	const updateRows = $derived(rows.filter((row) => row.kind === 'category_update'));
	const visibleRows = $derived(rows.filter((row) => row.kind !== 'excluded'));

	function openFilePicker(): void {
		banner = null;
		fileInputEl?.click();
	}

	function formatAmount(amount: number): string {
		return new Intl.NumberFormat('en-GB', { style: 'currency', currency: 'GBP' }).format(amount);
	}

	function categoryOptions(row: ReviewRow): Category[] {
		const options = $categories.slice();
		if (!options.some((category) => category.name === row.suggestedCategory.name)) {
			options.push({
				id: row.suggestedCategory.id ?? row.suggestedCategory.name,
				name: row.suggestedCategory.name,
				color: '#9ca3af',
				icon: 'tag',
				description: 'New category from import preview'
			});
		}
		return options;
	}

	async function handleFilesSelected(event: Event): Promise<void> {
		const input = event.target as HTMLInputElement;
		const picked = input.files ? Array.from(input.files) : [];
		input.value = '';
		if (picked.length === 0) return;

		loading = true;
		preview = null;
		rows = [];
		banner = null;
		try {
			const result = await expenseRepository.previewImportCsv(picked, { aiCategorize });
			preview = result;
			rows = result.rows.map((row) => ({
				...row,
				selectedCategoryName: row.suggestedCategory.name,
				acceptUpdate: row.kind === 'category_update'
			}));
			if (result.rows.length === 0) {
				banner = {
					kind: 'success',
					message: 'Nothing needs review. Existing transactions with unchanged categories were hidden.'
				};
			}
		} catch (err) {
			const message = err instanceof RepositoryError ? err.message : (err as Error).message;
			banner = { kind: 'error', message: `Preview failed: ${message}` };
		} finally {
			loading = false;
		}
	}

	async function confirmImport(): Promise<void> {
		if (!preview) return;
		saving = true;
		banner = null;
		try {
			const result = await expenseRepository.confirmImportCsv({
				importId: preview.importId,
				creates: createRows.map((row) => ({
					previewRowId: row.previewRowId,
					dedupeKeyHash: row.dedupeKeyHash,
					name: row.name,
					amount: row.amount,
					date: row.date,
					note: row.note,
					categoryName: row.selectedCategoryName
				})),
				categoryUpdates: updateRows.map((row) => ({
					previewRowId: row.previewRowId,
					dedupeKeyHash: row.dedupeKeyHash,
					existingExpenseId: row.existingExpenseId ?? '',
					categoryName: row.selectedCategoryName,
					accept: row.acceptUpdate
				}))
			});
			await refreshExpenses();
			await refreshCategories();
			preview = null;
			rows = [];
			banner = {
				kind: 'success',
				message: `Imported ${result.created}, updated ${result.updated}, kept ${result.keptExisting}. ${result.skippedDuplicates} duplicates and ${result.skippedStaleUpdates} stale updates skipped.`
			};
		} catch (err) {
			const message = err instanceof RepositoryError ? err.message : (err as Error).message;
			banner = { kind: 'error', message: `Import failed: ${message}` };
		} finally {
			saving = false;
		}
	}

	onMount(() => {
		void refreshCategories();
	});
</script>

<svelte:head>
	<title>Import transactions</title>
</svelte:head>

<section class="flex flex-col gap-6">
	<header class="flex flex-wrap items-start justify-between gap-4">
		<div>
			<h1 class="text-2xl font-semibold tracking-tight text-gray-900 dark:text-gray-50">
				Import transactions
			</h1>
			<p class="mt-1 max-w-2xl text-sm text-gray-500 dark:text-gray-400">
				Preview CSV transactions before saving. Existing transactions with unchanged categories are
				hidden; category changes are shown for approval.
			</p>
		</div>
		<div class="flex flex-wrap items-center gap-2">
			<label class="inline-flex items-center gap-2 rounded-md border border-gray-200 bg-white px-3 py-2 text-sm text-gray-700 dark:border-gray-800 dark:bg-[#111114] dark:text-gray-300">
				<input
					type="checkbox"
					data-testid="ai-categorize-toggle"
					bind:checked={aiCategorize}
					disabled={loading || saving}
					class="h-4 w-4 accent-gray-900 disabled:cursor-not-allowed disabled:opacity-60 dark:accent-gray-100"
				/>
				AI categorise
			</label>
			<input
				bind:this={fileInputEl}
				type="file"
				accept=".csv,text/csv"
				multiple
				data-testid="import-csv-input"
				class="hidden"
				onchange={handleFilesSelected}
			/>
			<button
				type="button"
				data-testid="select-import-files"
				onclick={openFilePicker}
				disabled={loading || saving}
				class="inline-flex items-center justify-center rounded-md bg-gray-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-gray-700 disabled:cursor-not-allowed disabled:opacity-60 dark:bg-gray-100 dark:text-gray-900 dark:hover:bg-gray-300"
			>
				{loading ? 'Previewing…' : 'Select CSV'}
			</button>
		</div>
	</header>

	{#if banner}
		<div
			data-testid="import-banner"
			data-kind={banner.kind}
			class="rounded-md border px-4 py-3 text-sm {banner.kind === 'success'
				? 'border-emerald-200 bg-emerald-50 text-emerald-800 dark:border-emerald-900/60 dark:bg-emerald-950/40 dark:text-emerald-200'
				: 'border-red-200 bg-red-50 text-red-800 dark:border-red-900/60 dark:bg-red-950/40 dark:text-red-200'}"
		>
			{banner.message}
		</div>
	{/if}

	{#if preview}
		<div class="import-summary rounded-lg border border-gray-200 bg-white p-4 text-sm dark:border-gray-800 dark:bg-[#111114]">
			<div><strong>{preview.summary.creates}</strong><br />new</div>
			<div><strong>{preview.summary.categoryUpdates}</strong><br />category changes</div>
			<div><strong>{preview.summary.hiddenDuplicates}</strong><br />unchanged hidden</div>
			<div><strong>{preview.summary.excluded}</strong><br />excluded</div>
			<div><strong>{preview.summary.invalidRows}</strong><br />invalid</div>
			<div><strong>{preview.summary.aiCategorized}</strong><br />AI categorised</div>
		</div>

		{#if visibleRows.length > 0}
			<div class="overflow-hidden rounded-lg border border-gray-200 bg-white dark:border-gray-800 dark:bg-[#111114]">
				<div class="import-row import-row-header border-b border-gray-200 px-4 py-2 text-xs font-medium uppercase tracking-wide text-gray-500 dark:border-gray-800 dark:text-gray-400">
					<div>Transaction</div>
					<div>Amount</div>
					<div>Category</div>
					<div>Decision</div>
				</div>
				{#each visibleRows as row (row.previewRowId)}
					<div class="import-row border-b border-gray-100 px-4 py-3 text-sm last:border-b-0 dark:border-gray-800">
						<div>
							<div class="font-medium text-gray-900 dark:text-gray-100">{row.name}</div>
							<div class="text-xs text-gray-500 dark:text-gray-400">
								{row.date} · {row.filename}:{row.sourceRow}
							</div>
							{#if row.note}
								<div class="text-xs text-gray-500 dark:text-gray-400">{row.note}</div>
							{/if}
						</div>
						<div class="text-gray-700 dark:text-gray-300">{formatAmount(row.amount)}</div>
						<div>
							<select
								bind:value={row.selectedCategoryName}
								disabled={row.kind === 'category_update' && !row.acceptUpdate}
								class="h-10 w-full rounded-md border border-gray-200 bg-white px-3 py-2 text-sm text-gray-800 disabled:opacity-50 dark:border-gray-800 dark:bg-[#0b0b0c] dark:text-gray-100"
							>
								{#each categoryOptions(row) as category (category.id)}
									<option value={category.name}>{category.name}</option>
								{/each}
							</select>
						</div>
						<div>
							{#if row.kind === 'create'}
								<span class="rounded-full bg-emerald-100 px-2 py-1 text-xs font-medium text-emerald-800 dark:bg-emerald-950 dark:text-emerald-200">New transaction</span>
							{:else if row.kind === 'category_update'}
								<label class="flex items-start gap-2 text-sm text-gray-700 dark:text-gray-300">
									<input type="checkbox" bind:checked={row.acceptUpdate} class="mt-1 h-4 w-4 accent-gray-900 dark:accent-gray-100" />
									<span>Change from {row.existingCategoryName} to {row.selectedCategoryName}</span>
								</label>
							{:else}
								<span class="rounded-full bg-gray-100 px-2 py-1 text-xs font-medium text-gray-700 dark:bg-gray-800 dark:text-gray-300">Excluded</span>
							{/if}
						</div>
					</div>
				{/each}
			</div>

			<div class="flex justify-end gap-2">
				<button
					type="button"
					onclick={() => {
						preview = null;
						rows = [];
					}}
					disabled={saving}
					class="rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-800 hover:bg-gray-100 disabled:opacity-60 dark:border-gray-700 dark:bg-[#111114] dark:text-gray-100 dark:hover:bg-gray-800"
				>
					Cancel
				</button>
				<button
					type="button"
					data-testid="confirm-import"
					onclick={confirmImport}
					disabled={saving}
					class="rounded-md bg-gray-900 px-4 py-2 text-sm font-medium text-white hover:bg-gray-700 disabled:opacity-60 dark:bg-gray-100 dark:text-gray-900 dark:hover:bg-gray-300"
				>
					{saving ? 'Saving…' : `Save ${createRows.length} new and review ${updateRows.length} updates`}
				</button>
			</div>
		{/if}
	{/if}
</section>

<style>
	.import-summary {
		display: grid;
		grid-template-columns: repeat(6, minmax(0, 1fr));
		gap: 0.75rem;
	}

	.import-row {
		display: grid;
		grid-template-columns: minmax(18rem, 1.6fr) minmax(6rem, 0.55fr) minmax(12rem, 1fr) minmax(
				14rem,
				1fr
			);
		gap: 0.75rem;
		align-items: center;
	}

	.import-row-header {
		align-items: end;
	}

	@media (max-width: 900px) {
		.import-summary {
			grid-template-columns: repeat(2, minmax(0, 1fr));
		}

		.import-row,
		.import-row-header {
			grid-template-columns: 1fr;
			align-items: start;
		}
	}
</style>

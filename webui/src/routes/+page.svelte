<script lang="ts">
	import { onMount } from 'svelte';
	import ExpenseList from '$components/ExpenseList.svelte';
	import ExpenseFormModal from '$components/ExpenseFormModal.svelte';
	import MonthSelector from '$components/MonthSelector.svelte';
	import CumulativeChart from '$components/CumulativeChart.svelte';
	import MonthlyBarChart from '$components/MonthlyBarChart.svelte';
	import CategoryDoughnutChart from '$components/CategoryDoughnutChart.svelte';
	import TweenedAmount from '$components/TweenedAmount.svelte';
	import { expenses } from '$lib/stores/expenses';
	import { refreshExpenses, importCsvFiles } from '$lib/stores/expenses';
	import { refreshCategories } from '$lib/stores/categories';
	import { selectedMonth } from '$lib/stores/ui';
	import { formatMonthLabel, monthKey } from '$utils/dates';
	import { RepositoryError } from '$lib/repos';
	import type { Expense, ImportCsvResult } from '$types';

	let modalOpen = $state(false);
	let editingExpense: Expense | undefined = $state(undefined);
	let showMonthlyChart = $state(false);
	let showCategoryChart = $state(false);
	type ExpenseGroupBy = 'transaction' | 'merchant' | 'category';
	let expenseGroupBy = $state<ExpenseGroupBy>('transaction');

	let fileInputEl: HTMLInputElement | null = $state(null);
	let importing = $state(false);
	let aiCategorize = $state(true);
	let importBanner: { kind: 'success' | 'error'; message: string } | null = $state(null);
	type ImportStepStatus = 'pending' | 'active' | 'complete' | 'skipped';
	type ImportStep = { id: string; label: string; status: ImportStepStatus };
	let importSteps: ImportStep[] = $state([]);

	const CHART_PREFS_KEY = 'expense-tracker:dashboard-charts:v1';
	const selectedMonthLabel = $derived(formatMonthLabel($selectedMonth));
	const selectedMonthTotal = $derived.by(() => {
		let total = 0;
		for (const expense of $expenses) {
			if (monthKey(expense.date) === $selectedMonth) {
				total += expense.amount;
			}
		}
		return total;
	});


	function openAdd(): void {
		editingExpense = undefined;
		modalOpen = true;
	}

	function openEdit(expense: Expense): void {
		editingExpense = expense;
		modalOpen = true;
	}

	function closeModal(): void {
		modalOpen = false;
		editingExpense = undefined;
	}

	function openFilePicker(): void {
		importBanner = null;
		fileInputEl?.click();
	}

	function summarize(result: ImportCsvResult): string {
		const parts: string[] = [];
		parts.push(`Imported ${result.imported}`);
		parts.push(`${result.transactionsFound} transactions found`);
		if (result.aiCategorized > 0) parts.push(`${result.aiCategorized} AI categorised`);
		if (result.skippedDuplicates > 0) parts.push(`${result.skippedDuplicates} duplicates skipped`);
		if (result.skippedExcluded > 0) parts.push(`${result.skippedExcluded} excluded by rules`);
		if (result.skippedInvalidRows > 0)
			parts.push(`${result.skippedInvalidRows} invalid rows skipped`);
		if (result.categoriesCreated.length > 0)
			parts.push(`${result.categoriesCreated.length} new categories`);
		const fileList = result.files.map((f) => `${f.filename} (+${f.imported})`).join(', ');
		return `${parts.join(', ')}. Files: ${fileList}`;
	}

	function setImportSteps(steps: ImportStep[]): void {
		importSteps = steps;
	}

	async function estimateTransactions(files: File[]): Promise<number> {
		let rows = 0;
		for (const file of files) {
			const text = await file.text();
			const nonEmptyLines = text.split(/\r?\n/).filter((line) => line.trim() !== '').length;
			rows += Math.max(0, nonEmptyLines - 1);
		}
		return rows;
	}

	async function handleFilesSelected(event: Event): Promise<void> {
		const input = event.target as HTMLInputElement;
		const picked = input.files ? Array.from(input.files) : [];
		input.value = '';
		if (picked.length === 0) return;

		importing = true;
		importBanner = null;
		try {
			setImportSteps([
				{ id: 'uploaded', label: `${picked.length} file${picked.length === 1 ? '' : 's'} uploaded`, status: 'complete' },
				{ id: 'found', label: 'Counting transactions…', status: 'active' },
				{ id: 'ai', label: 'AI categorisation pending', status: aiCategorize ? 'pending' : 'skipped' },
				{ id: 'saved', label: 'Saving transactions pending', status: 'pending' }
			]);
			const estimatedRows = await estimateTransactions(picked);
			setImportSteps([
				{ id: 'uploaded', label: `${picked.length} file${picked.length === 1 ? '' : 's'} uploaded`, status: 'complete' },
				{ id: 'found', label: `${estimatedRows} transaction${estimatedRows === 1 ? '' : 's'} found`, status: 'complete' },
				{ id: 'ai', label: aiCategorize ? 'AI categorisation started' : 'AI categorisation skipped', status: aiCategorize ? 'active' : 'skipped' },
				{ id: 'saved', label: 'Saving transactions pending', status: 'pending' }
			]);

			const result = await importCsvFiles(picked, { aiCategorize });
			if (result.categoriesCreated.length > 0) {
				await refreshCategories();
			}
			setImportSteps([
				{ id: 'uploaded', label: `${picked.length} file${picked.length === 1 ? '' : 's'} uploaded`, status: 'complete' },
				{ id: 'found', label: `${result.transactionsFound} transaction${result.transactionsFound === 1 ? '' : 's'} found`, status: 'complete' },
				{ id: 'ai', label: aiCategorize ? `${result.aiCategorized} transaction${result.aiCategorized === 1 ? '' : 's'} AI categorised` : 'AI categorisation skipped', status: aiCategorize ? 'complete' : 'skipped' },
				{ id: 'saved', label: `${result.imported} transaction${result.imported === 1 ? '' : 's'} saved`, status: 'complete' }
			]);
			importBanner = { kind: 'success', message: summarize(result) };
		} catch (err) {
			const message = err instanceof RepositoryError ? err.message : (err as Error).message;
			importBanner = { kind: 'error', message: `Import failed: ${message}` };
		} finally {
			importing = false;
		}
	}

	onMount(() => {
		void refreshExpenses();
		void refreshCategories();

		const saved = localStorage.getItem(CHART_PREFS_KEY);
		if (saved) {
			const prefs = JSON.parse(saved) as { monthly?: boolean; category?: boolean };
			showMonthlyChart = Boolean(prefs.monthly);
			showCategoryChart = Boolean(prefs.category);
		}
	});

	$effect(() => {
		localStorage.setItem(
			CHART_PREFS_KEY,
			JSON.stringify({ monthly: showMonthlyChart, category: showCategoryChart })
		);
	});
</script>

<svelte:head>
	<title>Expenses</title>
</svelte:head>

<section class="flex flex-col gap-6">
	<header class="flex flex-wrap items-center justify-between gap-3">
		<div>
			<h1 class="text-2xl font-semibold tracking-tight text-gray-900 dark:text-gray-50">
				<TweenedAmount
					value={selectedMonthTotal}
					testid="selected-month-total"
				/>
			</h1>
			<p
				data-testid="selected-month-heading"
				class="mt-1 text-sm text-gray-500 dark:text-gray-400"
			>
				{selectedMonthLabel}
			</p>
		</div>
		<div class="flex flex-wrap items-center gap-2">
			<label class="inline-flex items-center gap-2 rounded-md border border-gray-200 bg-white px-3 py-2 text-sm text-gray-700 dark:border-gray-800 dark:bg-[#111114] dark:text-gray-300">
				<input
					type="checkbox"
					data-testid="ai-categorize-toggle"
					bind:checked={aiCategorize}
					disabled={importing}
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
				data-testid="import-csv-btn"
				onclick={openFilePicker}
				disabled={importing}
				class="inline-flex items-center justify-center rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-800 transition-colors hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-60 dark:border-gray-700 dark:bg-[#111114] dark:text-gray-100 dark:hover:bg-gray-800"
			>
				{importing ? 'Importing…' : 'Import CSV'}
			</button>
			<button
				type="button"
				data-testid="add-expense-btn"
				onclick={openAdd}
				class="inline-flex items-center justify-center rounded-md bg-gray-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-gray-700 dark:bg-gray-100 dark:text-gray-900 dark:hover:bg-gray-300"
			>
				+ Add expense
			</button>
		</div>
	</header>

	{#if importBanner}
		<div
			data-testid="import-banner"
			data-kind={importBanner.kind}
			class="rounded-md border px-4 py-3 text-sm {importBanner.kind === 'success'
				? 'border-emerald-200 bg-emerald-50 text-emerald-800 dark:border-emerald-900/60 dark:bg-emerald-950/40 dark:text-emerald-200'
				: 'border-red-200 bg-red-50 text-red-800 dark:border-red-900/60 dark:bg-red-950/40 dark:text-red-200'}"
		>
			<div class="flex items-start justify-between gap-3">
				<span>{importBanner.message}</span>
				<button
					type="button"
					class="text-xs underline opacity-70 hover:opacity-100"
					onclick={() => (importBanner = null)}
				>
					Dismiss
				</button>
			</div>
		</div>
	{/if}

	{#if importSteps.length > 0}
		<ol
			data-testid="import-progress"
			class="grid gap-2 rounded-md border border-gray-200 bg-white p-3 text-sm dark:border-gray-800 dark:bg-[#111114] sm:grid-cols-4"
		>
			{#each importSteps as step (step.id)}
				<li
					class="relative overflow-hidden rounded-md px-2 py-2 text-gray-700 dark:text-gray-300 {step.status ===
					'active'
						? 'bg-blue-50 ring-1 ring-blue-200 dark:bg-blue-950/30 dark:ring-blue-900/60'
						: ''}"
				>
					{#if step.status === 'active'}
						<span class="absolute inset-x-0 bottom-0 h-1 overflow-hidden bg-blue-100 dark:bg-blue-950">
							<span class="block h-full w-1/2 animate-pulse rounded-full bg-blue-500"></span>
						</span>
					{/if}
					<div class="relative flex items-center gap-2">
						<span
							class="flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[10px] font-bold {step.status === 'complete'
							? 'bg-emerald-500'
							: step.status === 'active'
								? 'animate-pulse bg-blue-600 text-white shadow-sm shadow-blue-500/30'
							: step.status === 'skipped'
								? 'bg-gray-300 text-gray-600 dark:bg-gray-600 dark:text-gray-300'
								: 'bg-gray-200 text-gray-500 dark:bg-gray-700'}"
						>
							{#if step.status === 'complete'}✓{:else if step.status === 'active'}…{:else}·{/if}
						</span>
						<span>{step.label}</span>
					</div>
				</li>
			{/each}
		</ol>
	{/if}

	<div class="flex flex-wrap items-center justify-between gap-3">
		<MonthSelector />
		<div class="flex flex-wrap items-center gap-2 text-sm">
			<span class="text-gray-500 dark:text-gray-400">Charts</span>
			<label class="inline-flex items-center gap-2 rounded-full border border-gray-200 bg-white px-3 py-1.5 text-gray-700 dark:border-gray-800 dark:bg-[#111114] dark:text-gray-300">
				<input
					type="checkbox"
					data-testid="toggle-monthly-chart"
					bind:checked={showMonthlyChart}
					class="h-4 w-4 accent-gray-900 dark:accent-gray-100"
				/>
				Monthly totals
			</label>
			<label class="inline-flex items-center gap-2 rounded-full border border-gray-200 bg-white px-3 py-1.5 text-gray-700 dark:border-gray-800 dark:bg-[#111114] dark:text-gray-300">
				<input
					type="checkbox"
					data-testid="toggle-category-chart"
					bind:checked={showCategoryChart}
					class="h-4 w-4 accent-gray-900 dark:accent-gray-100"
				/>
				By category
			</label>
		</div>
	</div>

	<div
		class="rounded-lg border border-gray-200 bg-white p-4 sm:p-5 dark:border-gray-800 dark:bg-[#111114]"
	>
		<CumulativeChart />
	</div>

	{#if showMonthlyChart || showCategoryChart}
	<div class="grid grid-cols-1 gap-4 lg:grid-cols-2">
		{#if showMonthlyChart}
		<div
			class="rounded-lg border border-gray-200 bg-white p-4 sm:p-5 dark:border-gray-800 dark:bg-[#111114]"
		>
			<h2 class="mb-3 text-sm font-medium text-gray-700 dark:text-gray-300">
				Monthly total (12-month window)
			</h2>
			<MonthlyBarChart />
		</div>
		{/if}

		{#if showCategoryChart}
		<div
			class="rounded-lg border border-gray-200 bg-white p-4 sm:p-5 dark:border-gray-800 dark:bg-[#111114]"
		>
			<h2 class="mb-3 text-sm font-medium text-gray-700 dark:text-gray-300">
				By category
			</h2>
			<CategoryDoughnutChart />
		</div>
		{/if}
	</div>
	{/if}

	<div class="flex flex-wrap items-center justify-between gap-3">
		<h2 class="text-sm font-medium text-gray-700 dark:text-gray-300">Transactions</h2>
		<label class="inline-flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400">
			Group by
			<select
				bind:value={expenseGroupBy}
				class="rounded-md border border-gray-200 bg-white px-3 py-1.5 text-sm text-gray-800 dark:border-gray-800 dark:bg-[#111114] dark:text-gray-100"
			>
				<option value="transaction">Transaction</option>
				<option value="merchant">Merchant</option>
				<option value="category">Category</option>
			</select>
		</label>
	</div>

	<ExpenseList groupBy={expenseGroupBy} onedit={openEdit} />
</section>

<ExpenseFormModal open={modalOpen} expense={editingExpense} on:close={closeModal} />

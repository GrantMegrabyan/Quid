<script lang="ts">
	import { onMount } from 'svelte';
	import ExpenseList from '$components/ExpenseList.svelte';
	import ExpenseFormModal from '$components/ExpenseFormModal.svelte';
	import MonthSelector from '$components/MonthSelector.svelte';
	import CumulativeChart from '$components/CumulativeChart.svelte';
	import MonthlyBarChart from '$components/MonthlyBarChart.svelte';
	import CategoryDoughnutChart from '$components/CategoryDoughnutChart.svelte';
	import { expenses } from '$lib/stores/expenses';
	import { refreshExpenses, importCsvFiles } from '$lib/stores/expenses';
	import { refreshCategories } from '$lib/stores/categories';
	import { selectedMonth } from '$lib/stores/ui';
	import { formatMonthLabel, monthKey } from '$utils/dates';
	import { formatAmount } from '$utils/money';
	import { RepositoryError } from '$lib/repos';
	import type { Expense, ImportCsvResult } from '$types';

	let modalOpen = $state(false);
	let editingExpense: Expense | undefined = $state(undefined);
	let showMonthlyChart = $state(false);
	let showCategoryChart = $state(false);

	let fileInputEl: HTMLInputElement | null = $state(null);
	let importing = $state(false);
	let importBanner: { kind: 'success' | 'error'; message: string } | null = $state(null);

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
	const selectedMonthTotalLabel = $derived(formatAmount(selectedMonthTotal));

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
		if (result.skippedDuplicates > 0) parts.push(`${result.skippedDuplicates} duplicates skipped`);
		if (result.skippedExcluded > 0) parts.push(`${result.skippedExcluded} excluded by rules`);
		if (result.skippedInvalidRows > 0)
			parts.push(`${result.skippedInvalidRows} invalid rows skipped`);
		if (result.categoriesCreated.length > 0)
			parts.push(`${result.categoriesCreated.length} new categories`);
		const fileList = result.files.map((f) => `${f.filename} (+${f.imported})`).join(', ');
		return `${parts.join(', ')}. Files: ${fileList}`;
	}

	async function handleFilesSelected(event: Event): Promise<void> {
		const input = event.target as HTMLInputElement;
		const picked = input.files ? Array.from(input.files) : [];
		input.value = '';
		if (picked.length === 0) return;

		importing = true;
		importBanner = null;
		try {
			const result = await importCsvFiles(picked);
			if (result.categoriesCreated.length > 0) {
				await refreshCategories();
			}
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
			<h1
				data-testid="selected-month-total"
				class="text-2xl font-semibold tracking-tight text-gray-900 dark:text-gray-50"
			>
				{selectedMonthTotalLabel}
			</h1>
			<p
				data-testid="selected-month-heading"
				class="mt-1 text-sm text-gray-500 dark:text-gray-400"
			>
				{selectedMonthLabel}
			</p>
		</div>
		<div class="flex flex-wrap items-center gap-2">
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

	<ExpenseList onedit={openEdit} />
</section>

<ExpenseFormModal open={modalOpen} expense={editingExpense} on:close={closeModal} />

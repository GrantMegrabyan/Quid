<script lang="ts">
	import { onMount } from 'svelte';
	import ExpenseList from '$components/ExpenseList.svelte';
	import ExpenseFormModal from '$components/ExpenseFormModal.svelte';
	import MonthlyBarChart from '$components/MonthlyBarChart.svelte';
	import CategoryDoughnutChart from '$components/CategoryDoughnutChart.svelte';
	import { refreshExpenses } from '$lib/stores/expenses';
	import { refreshCategories } from '$lib/stores/categories';
	import type { Expense } from '$types';

	let modalOpen = $state(false);
	let editingExpense: Expense | undefined = $state(undefined);

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

	onMount(() => {
		void refreshExpenses();
		void refreshCategories();
	});
</script>

<svelte:head>
	<title>Expenses</title>
</svelte:head>

<section class="flex flex-col gap-6">
	<header class="flex flex-wrap items-center justify-between gap-3">
		<h1 class="text-2xl font-semibold tracking-tight text-gray-900 dark:text-gray-50">
			Expenses
		</h1>
		<button
			type="button"
			data-testid="add-expense-btn"
			onclick={openAdd}
			class="inline-flex items-center justify-center rounded-md bg-gray-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-gray-700 dark:bg-gray-100 dark:text-gray-900 dark:hover:bg-gray-300"
		>
			+ Add expense
		</button>
	</header>

	<div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
		<div
			class="rounded-lg border border-gray-200 bg-white p-4 sm:p-5 dark:border-gray-800 dark:bg-[#111114]"
		>
			<h2 class="mb-3 text-sm font-medium text-gray-700 dark:text-gray-300">
				Monthly total (last 12 months)
			</h2>
			<MonthlyBarChart />
		</div>

		<div
			class="rounded-lg border border-gray-200 bg-white p-4 sm:p-5 dark:border-gray-800 dark:bg-[#111114]"
		>
			<h2 class="mb-3 text-sm font-medium text-gray-700 dark:text-gray-300">
				By category
			</h2>
			<CategoryDoughnutChart />
		</div>
	</div>

	<ExpenseList onedit={openEdit} />
</section>

<ExpenseFormModal open={modalOpen} expense={editingExpense} on:close={closeModal} />

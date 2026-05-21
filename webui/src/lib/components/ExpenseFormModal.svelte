<script lang="ts">
	import { addExpense, editExpense } from '$lib/stores/expenses';
	import { categories, refreshCategories } from '$lib/stores/categories';
	import { parseAmountInput } from '$utils/money';
	import { todayIso } from '$utils/dates';
	import type { Expense } from '$types';

	type Props = {
		open: boolean;
		expense?: Expense;
		onClose?: () => void;
	};

	let { open, expense, onClose }: Props = $props();

	let amountInput = $state('');
	let dateInput = $state('');
	let categoryInput = $state('');
	let noteInput = $state('');

	let amountError = $state('');
	let dateError = $state('');
	let categoryError = $state('');

	let submitting = $state(false);

	let amountFieldEl: HTMLInputElement | null = $state(null);

	const isEdit = $derived(Boolean(expense));
	const title = $derived(isEdit ? 'Edit expense' : 'Add expense');

	function resetForm() {
		amountError = '';
		dateError = '';
		categoryError = '';
		submitting = false;

		if (expense) {
			amountInput = expense.amount.toFixed(2);
			dateInput = expense.date;
			categoryInput = expense.categoryId;
			noteInput = expense.note;
		} else {
			amountInput = '';
			dateInput = todayIso();
			categoryInput = '';
			noteInput = '';
		}
	}

	$effect(() => {
		if (open) {
			resetForm();
			void refreshCategories();
			queueMicrotask(() => amountFieldEl?.focus());
		}
	});

	function isValidIsoDate(value: string): boolean {
		if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
		const [year, month, day] = value.split('-').map(Number);
		const date = new Date(year, month - 1, day);
		return (
			date.getFullYear() === year &&
			date.getMonth() === month - 1 &&
			date.getDate() === day
		);
	}

	function close() {
		onClose?.();
	}

	function handleBackdropClick(event: MouseEvent) {
		if (event.target === event.currentTarget) {
			close();
		}
	}

	function handleWindowKeydown(event: KeyboardEvent) {
		if (open && event.key === 'Escape') {
			event.preventDefault();
			close();
		}
	}

	async function handleSubmit(event: SubmitEvent) {
		event.preventDefault();

		amountError = '';
		dateError = '';
		categoryError = '';

		const parsedAmount = parseAmountInput(amountInput);
		if (parsedAmount === null || parsedAmount <= 0) {
			amountError = 'Enter an amount greater than 0.';
		}

		const trimmedDate = dateInput.trim();
		if (!isValidIsoDate(trimmedDate)) {
			dateError = 'Enter a valid date (YYYY-MM-DD).';
		}

		const availableCategories = $categories;
		if (
			!categoryInput ||
			!availableCategories.some((category) => category.id === categoryInput)
		) {
			categoryError = 'Choose a category.';
		}

		const trimmedNote = noteInput.slice(0, 200);

		if (amountError || dateError || categoryError) {
			return;
		}

		submitting = true;
		try {
			const payload = {
				amount: parsedAmount as number,
				date: trimmedDate,
				categoryId: categoryInput,
				note: trimmedNote
			};

			if (expense) {
				await editExpense(expense.id, payload);
			} else {
				await addExpense(payload);
			}

			close();
		} finally {
			submitting = false;
		}
	}
</script>

<svelte:window onkeydown={handleWindowKeydown} />

{#if open}
	<div
		data-testid="modal-backdrop"
		role="presentation"
		onclick={handleBackdropClick}
		class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-sm"
	>
		<div
			role="dialog"
			aria-modal="true"
			aria-labelledby="expense-modal-title"
			class="w-full max-w-md rounded-lg border border-gray-200 bg-white p-6 shadow-xl dark:border-gray-800 dark:bg-[#111114]"
		>
			<h2
				id="expense-modal-title"
				data-testid="modal-title"
				class="text-lg font-semibold text-gray-900 dark:text-gray-50"
			>
				{title}
			</h2>

			<form class="mt-4 flex flex-col gap-4" onsubmit={handleSubmit} novalidate>
				<div class="flex flex-col gap-1">
					<label
						for="expense-amount"
						class="text-sm font-medium text-gray-700 dark:text-gray-300"
					>
						Amount
					</label>
					<input
						id="expense-amount"
						bind:this={amountFieldEl}
						bind:value={amountInput}
						data-testid="amount-input"
						type="text"
						inputmode="decimal"
						autocomplete="off"
						placeholder="0.00"
						class="rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 placeholder:text-gray-400 focus:border-gray-900 focus:outline-none dark:border-gray-700 dark:bg-[#0b0b0c] dark:text-gray-100 dark:focus:border-gray-100"
					/>
					{#if amountError}
						<p
							data-testid="amount-error"
							class="text-sm text-red-600 dark:text-red-400"
						>
							{amountError}
						</p>
					{/if}
				</div>

				<div class="flex flex-col gap-1">
					<label
						for="expense-date"
						class="text-sm font-medium text-gray-700 dark:text-gray-300"
					>
						Date
					</label>
					<input
						id="expense-date"
						bind:value={dateInput}
						data-testid="date-input"
						type="date"
						autocomplete="off"
						class="rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 focus:border-gray-900 focus:outline-none dark:border-gray-700 dark:bg-[#0b0b0c] dark:text-gray-100 dark:focus:border-gray-100"
					/>
					{#if dateError}
						<p
							data-testid="date-error"
							class="text-sm text-red-600 dark:text-red-400"
						>
							{dateError}
						</p>
					{/if}
				</div>

				<div class="flex flex-col gap-1">
					<label
						for="expense-category"
						class="text-sm font-medium text-gray-700 dark:text-gray-300"
					>
						Category
					</label>
					<select
						id="expense-category"
						bind:value={categoryInput}
						data-testid="category-select"
						class="rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 focus:border-gray-900 focus:outline-none dark:border-gray-700 dark:bg-[#0b0b0c] dark:text-gray-100 dark:focus:border-gray-100"
					>
						<option value="" disabled>Select a category</option>
						{#each $categories as category (category.id)}
							<option value={category.id}>{category.name}</option>
						{/each}
					</select>
					{#if categoryError}
						<p
							data-testid="category-error"
							class="text-sm text-red-600 dark:text-red-400"
						>
							{categoryError}
						</p>
					{/if}
				</div>

				<div class="flex flex-col gap-1">
					<label
						for="expense-note"
						class="text-sm font-medium text-gray-700 dark:text-gray-300"
					>
						Note
					</label>
					<textarea
						id="expense-note"
						bind:value={noteInput}
						data-testid="note-input"
						maxlength="200"
						rows="2"
						class="rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 placeholder:text-gray-400 focus:border-gray-900 focus:outline-none dark:border-gray-700 dark:bg-[#0b0b0c] dark:text-gray-100 dark:focus:border-gray-100"
					></textarea>
					<p class="text-right text-xs text-gray-500 dark:text-gray-400">
						{noteInput.length}/200
					</p>
				</div>

				<div class="mt-2 flex items-center justify-end gap-2">
					<button
						type="button"
						data-testid="cancel-button"
						onclick={close}
						class="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100 dark:border-gray-700 dark:text-gray-300 dark:hover:bg-gray-800"
					>
						Cancel
					</button>
					<button
						type="submit"
						data-testid="submit-button"
						disabled={submitting}
						class="rounded-md bg-gray-900 px-4 py-2 text-sm font-medium text-white hover:bg-gray-700 disabled:opacity-60 dark:bg-gray-100 dark:text-gray-900 dark:hover:bg-gray-300"
					>
						{isEdit ? 'Save' : 'Add'}
					</button>
				</div>
			</form>
		</div>
	</div>
{/if}

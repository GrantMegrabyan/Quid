<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import { addExpense, editExpense } from '$lib/stores/expenses';
	import { categories, refreshCategories } from '$lib/stores/categories';
	import { parseAmountInput } from '$utils/money';
	import { todayIso } from '$utils/dates';
	import type { Expense, ExpenseImportance } from '$types';

	type Props = {
		open: boolean;
		expense?: Expense;
	};

	let { open, expense }: Props = $props();

	const dispatch = createEventDispatcher<{ close: void }>();

	let nameInput = $state('');
	let amountInput = $state('');
	let dateInput = $state('');
	let categoryInput = $state('');
	let noteInput = $state('');
	let displayNameInput = $state('');
	let importanceInput = $state<ExpenseImportance>('important');

	let nameError = $state('');
	let amountError = $state('');
	let dateError = $state('');
	let categoryError = $state('');

	let submitting = $state(false);

	let nameFieldEl: HTMLInputElement | null = $state(null);

	const isEdit = $derived(Boolean(expense));
	const title = $derived(isEdit ? 'Edit expense' : 'Add expense');

	function resetForm() {
		nameError = '';
		amountError = '';
		dateError = '';
		categoryError = '';
		submitting = false;

		if (expense) {
			nameInput = expense.name;
			amountInput = expense.amount.toFixed(2);
			dateInput = expense.date;
			categoryInput = expense.categoryId;
			noteInput = expense.note;
			displayNameInput = expense.displayName ?? '';
			importanceInput = expense.importance;
		} else {
			nameInput = '';
			amountInput = '';
			dateInput = todayIso();
			categoryInput = '';
			noteInput = '';
			displayNameInput = '';
			importanceInput = 'important';
		}
	}

	$effect(() => {
		if (open) {
			resetForm();
			void refreshCategories();
			queueMicrotask(() => nameFieldEl?.focus());
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
		dispatch('close');
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

		nameError = '';
		amountError = '';
		dateError = '';
		categoryError = '';

		const trimmedName = nameInput.trim();
		if (trimmedName.length === 0) {
			nameError = 'Enter a merchant name.';
		} else if (trimmedName.length > 80) {
			nameError = 'Merchant name must be 80 characters or fewer.';
		}

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

		if (nameError || amountError || dateError || categoryError) {
			return;
		}

		submitting = true;
		try {
			const payload = {
				name: trimmedName,
				amount: parsedAmount as number,
				date: trimmedDate,
				categoryId: categoryInput,
				note: trimmedNote,
				importance: importanceInput
			};

			if (expense) {
				await editExpense(expense.id, {
					...payload,
					displayName: displayNameInput.trim() || null
				});
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
		class="fixed inset-0 z-50 flex bg-black/50 backdrop-blur-sm sm:items-center sm:justify-center sm:p-4"
	>
		<div
			role="dialog"
			aria-modal="true"
			aria-labelledby="expense-modal-title"
			class="flex h-full w-full flex-col overflow-y-auto border-gray-200 bg-white p-6 shadow-xl sm:h-auto sm:max-w-md sm:rounded-lg sm:border dark:border-gray-800 dark:bg-[#111114]"
		>
			<h2
				id="expense-modal-title"
				data-testid="modal-title"
				class="text-lg font-semibold text-gray-900 dark:text-gray-50"
			>
				{title}
			</h2>

			<form
				class="mt-4 flex flex-1 flex-col gap-4"
				onsubmit={handleSubmit}
				novalidate
			>
				<div class="flex flex-col gap-1">
					<label
						for="expense-name"
						class="text-sm font-medium text-gray-700 dark:text-gray-300"
					>
						Merchant
					</label>
					<input
						id="expense-name"
						bind:this={nameFieldEl}
						data-testid="name-input"
						type="text"
						maxlength="80"
						autocomplete="off"
						placeholder="e.g. Starbucks"
						value={nameInput}
						oninput={(event) => (nameInput = event.currentTarget.value)}
						class="rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 placeholder:text-gray-400 focus:border-gray-900 focus:outline-none dark:border-gray-700 dark:bg-[#0b0b0c] dark:text-gray-100 dark:focus:border-gray-100"
					/>
					{#if nameError}
						<p
							data-testid="name-error"
							class="text-sm text-red-600 dark:text-red-400"
						>
							{nameError}
						</p>
					{/if}
				</div>

				<div class="flex flex-col gap-1">
					<label
						for="expense-amount"
						class="text-sm font-medium text-gray-700 dark:text-gray-300"
					>
						Amount
					</label>
					<input
						id="expense-amount"
						data-testid="amount-input"
						type="number"
						step="0.01"
						min="0"
						inputmode="decimal"
						autocomplete="off"
						placeholder="0.00"
						value={amountInput}
						oninput={(event) => (amountInput = event.currentTarget.value)}
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
					class="h-10 rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 focus:border-gray-900 focus:outline-none dark:border-gray-700 dark:bg-[#0b0b0c] dark:text-gray-100 dark:focus:border-gray-100"
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
						for="expense-importance"
						class="text-sm font-medium text-gray-700 dark:text-gray-300"
					>
						Importance
					</label>
					<select
						id="expense-importance"
						bind:value={importanceInput}
						data-testid="importance-select"
						class="rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 focus:border-gray-900 focus:outline-none dark:border-gray-700 dark:bg-[#0b0b0c] dark:text-gray-100 dark:focus:border-gray-100"
					>
						<option value="essential">Essential</option>
						<option value="important">Important</option>
						<option value="discretionary">Discretionary</option>
					</select>
				</div>

			<div class="flex flex-col gap-1">
				<label
					for="expense-note"
					class="text-sm font-medium text-gray-700 dark:text-gray-300"
				>
					Note
				</label>
				<input
					id="expense-note"
					bind:value={noteInput}
					data-testid="note-input"
					type="text"
					maxlength="200"
					autocomplete="off"
					class="rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 placeholder:text-gray-400 focus:border-gray-900 focus:outline-none dark:border-gray-700 dark:bg-[#0b0b0c] dark:text-gray-100 dark:focus:border-gray-100"
				/>
				<p class="text-right text-xs text-gray-500 dark:text-gray-400">
					{noteInput.length}/200
				</p>
			</div>

			{#if isEdit}
				<div class="flex flex-col gap-1">
					<label
						for="expense-display-name"
						class="text-sm font-medium text-gray-700 dark:text-gray-300"
					>
						Display name
					</label>
					<input
						id="expense-display-name"
						bind:value={displayNameInput}
						data-testid="display-name-input"
						type="text"
						maxlength="200"
						autocomplete="off"
						placeholder="Leave blank to use merchant name"
						class="rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 placeholder:text-gray-400 focus:border-gray-900 focus:outline-none dark:border-gray-700 dark:bg-[#0b0b0c] dark:text-gray-100 dark:focus:border-gray-100"
					/>
				</div>
			{/if}

				<div
					class="mt-auto flex items-center justify-end gap-2 pt-2 sm:mt-2"
				>
					<button
						type="button"
						data-testid="modal-cancel"
						onclick={close}
						class="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100 dark:border-gray-700 dark:text-gray-300 dark:hover:bg-gray-800"
					>
						Cancel
					</button>
					<button
						type="submit"
						data-testid="modal-submit"
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

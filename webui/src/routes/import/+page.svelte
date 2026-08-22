<script lang="ts">
	import PageHeader from '$components/shell/PageHeader.svelte';
	import PageContent from '$components/shell/PageContent.svelte';
	import { onMount } from 'svelte';
	import { RepositoryError, expenseRepository } from '$lib/repos';
	import { categories, refreshCategories } from '$lib/stores/categories';
	import { addExpense, refreshExpenses } from '$lib/stores/expenses';
	import { refreshSettings, settings } from '$lib/stores/settings';
	import { persisted } from '$lib/stores/persisted';
	import { get } from 'svelte/store';
	import { formatAmount, parseAmountInput } from '$lib/utils/money';
	import { todayIso } from '$lib/utils/dates';
	import type {
		Category,
		ExpenseImportance,
		ImportCsvPreviewResult,
		ImportLog,
		ImportPreviewRow
	} from '$types';

	type ReviewRow = ImportPreviewRow & {
		selectedCategoryName: string;
		selectedImportance: ExpenseImportance;
		selectedAmountInput: string;
		amountError: boolean;
		acceptUpdate: boolean;
		// User-set: drop this row from the import entirely. Applies to ANY
		// reviewable row, including brand-new ('create') transactions.
		userExcluded: boolean;
	};

	type ReviewState = {
		preview: ImportCsvPreviewResult;
		rows: ReviewRow[];
	};

	type ImportTab = 'csv' | 'single' | 'freeform';

	const IMPORT_TABS: ImportTab[] = ['csv', 'single', 'freeform'];
	// Remember the active import tab across reloads.
	const tabStore = persisted<ImportTab>(
		'quid:import-tab:v1',
		'csv',
		(value): value is ImportTab => IMPORT_TABS.includes(value)
	);
	let tab = $state<ImportTab>(get(tabStore));
	$effect(() => {
		tabStore.set(tab);
	});

	// --- Shared state -------------------------------------------------------
	let banner: { kind: 'success' | 'error'; message: string } | null = $state(null);
	let importLogs: ImportLog[] = $state([]);
	let expandedLogs = $state<Record<string, boolean>>({});
	// Disclosure toggles for the preview summary bar's "excluded"/"invalid"
	// detail panels. Collapsed by default; only one review (CSV or free-form) is
	// ever on screen at a time, so a shared pair of flags is sufficient.
	let showExcludedDetails = $state(false);
	let showInvalidDetails = $state(false);

	// --- CSV tab state ------------------------------------------------------
	let fileInputEl: HTMLInputElement | null = $state(null);
	let loading = $state(false);
	let saving = $state(false);
	let csvReview = $state<ReviewState | null>(null);
	// Show/hide the matched ('category_update') rows in the preview table.
	// They're kept-by-default so users often want them collapsed away.
	let csvShowMatched = $state(true);

	const csvCreateRows = $derived(
		csvReview ? csvReview.rows.filter((row) => row.kind === 'create' && !row.userExcluded) : []
	);
	const csvUpdateRows = $derived(
		csvReview
			? csvReview.rows.filter((row) => row.kind === 'category_update' && !row.userExcluded)
			: []
	);
	const csvMatchedCount = $derived(
		csvReview ? csvReview.rows.filter((row) => row.kind === 'category_update').length : 0
	);
	const csvVisibleRows = $derived(
		csvReview
			? csvReview.rows.filter(
					(row) =>
						row.kind !== 'excluded' && (csvShowMatched || row.kind !== 'category_update')
				)
			: []
	);

	// --- Single transaction tab state ---------------------------------------
	let nameInput = $state('');
	let amountInput = $state('');
	let dateInput = $state(todayIso());
	let categoryInput = $state('');
	let noteInput = $state('');
	let importanceInput = $state<ExpenseImportance>('important');

	let nameError = $state('');
	let amountError = $state('');
	let dateError = $state('');
	let categoryError = $state('');
	let singleSubmitting = $state(false);

	// --- Free-form tab state ------------------------------------------------
	let freeformInput = $state('');
	let freeformParsing = $state(false);
	let freeformSaving = $state(false);
	let freeformReview = $state<ReviewState | null>(null);
	let freeformShowMatched = $state(true);

	const freeformCreateRows = $derived(
		freeformReview
			? freeformReview.rows.filter((row) => row.kind === 'create' && !row.userExcluded)
			: []
	);
	const freeformUpdateRows = $derived(
		freeformReview
			? freeformReview.rows.filter((row) => row.kind === 'category_update' && !row.userExcluded)
			: []
	);
	const freeformMatchedCount = $derived(
		freeformReview
			? freeformReview.rows.filter((row) => row.kind === 'category_update').length
			: 0
	);
	const freeformVisibleRows = $derived(
		freeformReview
			? freeformReview.rows.filter(
					(row) =>
						row.kind !== 'excluded' &&
						(freeformShowMatched || row.kind !== 'category_update')
				)
			: []
	);

	// --- Helpers ------------------------------------------------------------
	function toReviewRows(result: ImportCsvPreviewResult): ReviewRow[] {
		return result.rows.map((row) => ({
			...row,
			selectedCategoryName: row.suggestedCategory.name,
			selectedImportance: row.suggestedImportance,
			selectedAmountInput: row.amount,
			amountError: false,
			// Matched (existing) transactions are NOT updated by default: a prior
			// import may have been intentionally edited, so we never silently
			// override it. The user opts in per-row via the Enable button.
			acceptUpdate: false,
			userExcluded: false
		}));
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

	function onAmountInput(row: ReviewRow, value: string): void {
		row.selectedAmountInput = value;
		const parsed = parseAmountInput(value);
		row.amountError = parsed === null || Number(parsed) <= 0;
	}

	function hasAmountErrors(rows: ReviewRow[]): boolean {
		let invalid = false;
		for (const row of rows) {
			const parsed = parseAmountInput(row.selectedAmountInput);
			if (parsed === null || Number(parsed) <= 0) {
				row.amountError = true;
				invalid = true;
			}
		}
		return invalid;
	}

	function importanceLabel(value: ExpenseImportance): string {
		return value === 'essential'
			? 'Essential'
			: value === 'important'
				? 'Important'
				: 'Discretionary';
	}

	function isValidIsoDate(value: string): boolean {
		if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
		const [year, month, day] = value.split('-').map(Number);
		const date = new Date(year, month - 1, day);
		return (
			date.getFullYear() === year && date.getMonth() === month - 1 && date.getDate() === day
		);
	}

	function setTab(next: ImportTab): void {
		tab = next;
		banner = null;
	}

	// --- CSV handlers -------------------------------------------------------
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
		csvReview = null;
		banner = null;
		try {
			const result = await expenseRepository.previewImportCsv(picked);
			csvReview = { preview: result, rows: toReviewRows(result) };
			showExcludedDetails = false;
			showInvalidDetails = false;
			if (result.rows.length === 0) {
				banner = {
					kind: 'success',
					message:
						'Nothing needs review. Existing transactions with unchanged categories were hidden.'
				};
			}
		} catch (err) {
			const message = err instanceof RepositoryError ? err.message : (err as Error).message;
			banner = { kind: 'error', message: `Preview failed: ${message}` };
		} finally {
			loading = false;
		}
	}

	async function confirmCsvImport(): Promise<void> {
		if (!csvReview) return;
		const review = csvReview;
		if (hasAmountErrors(csvCreateRows)) {
			banner = { kind: 'error', message: 'Fix the highlighted amounts before saving.' };
			return;
		}
		saving = true;
		banner = null;
		try {
			const result = await expenseRepository.confirmImportCsv({
				importId: review.preview.importId,
				files: review.preview.files.map((file) => file.filename),
				creates: csvCreateRows.map((row) => ({
					previewRowId: row.previewRowId,
					dedupeKeyHash: row.dedupeKeyHash,
					name: row.name,
					amount: parseAmountInput(row.selectedAmountInput) as string,
					date: row.date,
					note: row.note,
					categoryName: row.selectedCategoryName,
					importance: row.selectedImportance,
					// Report what was proposed so the server can tell a deliberate
					// override (which it stores as a hand-set label) from an
					// untouched suggestion.
					suggestedImportance: row.suggestedImportance
				})),
				categoryUpdates: csvUpdateRows.map((row) => ({
					previewRowId: row.previewRowId,
					dedupeKeyHash: row.dedupeKeyHash,
					existingExpenseId: row.existingExpenseId ?? '',
					categoryName: row.selectedCategoryName,
					importance: row.selectedImportance,
					suggestedImportance: row.suggestedImportance,
					accept: row.acceptUpdate
				}))
			});
			await refreshExpenses();
			await refreshCategories();
			importLogs = await expenseRepository.listImportLogs();
			csvReview = null;
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

	// --- Single transaction handler -----------------------------------------
	function resetSingleForm(): void {
		nameInput = '';
		amountInput = '';
		dateInput = todayIso();
		categoryInput = '';
		noteInput = '';
		importanceInput = 'important';
		nameError = '';
		amountError = '';
		dateError = '';
		categoryError = '';
	}

	async function handleSingleSubmit(event: SubmitEvent): Promise<void> {
		event.preventDefault();
		banner = null;

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
		if (parsedAmount === null || Number(parsedAmount) <= 0) {
			amountError = 'Enter an amount greater than 0.';
		}

		const trimmedDate = dateInput.trim();
		if (!isValidIsoDate(trimmedDate)) {
			dateError = 'Enter a valid date (YYYY-MM-DD).';
		}

		const availableCategories = $categories;
		if (!categoryInput || !availableCategories.some((category) => category.id === categoryInput)) {
			categoryError = 'Choose a category.';
		}

		const trimmedNote = noteInput.slice(0, 200);

		if (nameError || amountError || dateError || categoryError) {
			return;
		}

		singleSubmitting = true;
		try {
			await addExpense({
				name: trimmedName,
				amount: parsedAmount as string,
				date: trimmedDate,
				categoryId: categoryInput,
				note: trimmedNote,
				importance: importanceInput
			});
			resetSingleForm();
			banner = { kind: 'success', message: `Added “${trimmedName}”.` };
		} catch (err) {
			const message = err instanceof RepositoryError ? err.message : (err as Error).message;
			banner = { kind: 'error', message: `Could not add transaction: ${message}` };
		} finally {
			singleSubmitting = false;
		}
	}

	// --- Free-form handlers -------------------------------------------------
	async function parseFreeform(): Promise<void> {
		const raw = freeformInput.trim();
		if (raw.length === 0) {
			banner = { kind: 'error', message: 'Enter some transactions to parse.' };
			return;
		}

		freeformParsing = true;
		freeformReview = null;
		banner = null;
		try {
			const result = await expenseRepository.previewImportFreeform(raw);
			freeformReview = { preview: result, rows: toReviewRows(result) };
			showExcludedDetails = false;
			showInvalidDetails = false;
			if (result.rows.length === 0) {
				banner = {
					kind: 'success',
					message: 'Nothing needs review. Nothing new was found in your text.'
				};
			}
		} catch (err) {
			const message = err instanceof RepositoryError ? err.message : (err as Error).message;
			banner = { kind: 'error', message: `Parse failed: ${message}` };
		} finally {
			freeformParsing = false;
		}
	}

	async function confirmFreeformImport(): Promise<void> {
		if (!freeformReview) return;
		const review = freeformReview;
		if (hasAmountErrors(freeformCreateRows)) {
			banner = { kind: 'error', message: 'Fix the highlighted amounts before saving.' };
			return;
		}
		freeformSaving = true;
		banner = null;
		try {
			const result = await expenseRepository.confirmImportFreeform({
				importId: review.preview.importId,
				rawInput: freeformInput,
				creates: freeformCreateRows.map((row) => ({
					previewRowId: row.previewRowId,
					dedupeKeyHash: row.dedupeKeyHash,
					name: row.name,
					amount: parseAmountInput(row.selectedAmountInput) as string,
					date: row.date,
					note: row.note,
					categoryName: row.selectedCategoryName,
					importance: row.selectedImportance,
					// Report what was proposed so the server can tell a deliberate
					// override (which it stores as a hand-set label) from an
					// untouched suggestion.
					suggestedImportance: row.suggestedImportance
				})),
				categoryUpdates: freeformUpdateRows.map((row) => ({
					previewRowId: row.previewRowId,
					dedupeKeyHash: row.dedupeKeyHash,
					existingExpenseId: row.existingExpenseId ?? '',
					categoryName: row.selectedCategoryName,
					importance: row.selectedImportance,
					suggestedImportance: row.suggestedImportance,
					accept: row.acceptUpdate
				}))
			});
			await refreshExpenses();
			await refreshCategories();
			importLogs = await expenseRepository.listImportLogs();
			freeformReview = null;
			freeformInput = '';
			banner = {
				kind: 'success',
				message: `Imported ${result.created}, updated ${result.updated}, kept ${result.keptExisting}. ${result.skippedDuplicates} duplicates and ${result.skippedStaleUpdates} stale updates skipped.`
			};
		} catch (err) {
			const message = err instanceof RepositoryError ? err.message : (err as Error).message;
			banner = { kind: 'error', message: `Import failed: ${message}` };
		} finally {
			freeformSaving = false;
		}
	}

	// --- History helpers ----------------------------------------------------
	function toggleLog(id: string): void {
		expandedLogs = { ...expandedLogs, [id]: !expandedLogs[id] };
	}

	onMount(() => {
		void refreshCategories();
		void refreshSettings();
		void expenseRepository.listImportLogs().then((logs) => {
			importLogs = logs;
		});
	});
</script>

{#snippet reviewTable(
	rows: ReviewRow[],
	createRows: ReviewRow[],
	updateRows: ReviewRow[],
	preview: ImportCsvPreviewResult,
	busy: boolean,
	confirmTestId: string,
	matchedCount: number,
	showMatched: boolean,
	onToggleMatched: () => void,
	onCancel: () => void,
	onConfirm: () => void
)}
	{@const overrideCount = updateRows.filter((row) => row.acceptUpdate).length}
	{@const excludedCount = rows.filter((row) => row.userExcluded).length}
	{@const excludedDetailRows = preview.rows.filter((row) => row.kind === 'excluded')}
	{@const invalidDetailRows = preview.invalid ?? []}
	{@const hasExcludedDetails = excludedDetailRows.length > 0}
	{@const hasInvalidDetails = invalidDetailRows.length > 0}
	<div class="import-summary rounded-lg border border-ctp-surface1 bg-ctp-base p-4 text-sm">
		<div><strong>{preview.summary.creates}</strong><br />new</div>
		<div><strong>{preview.summary.categoryUpdates}</strong><br />existing (kept)</div>
		<div><strong>{preview.summary.hiddenDuplicates}</strong><br />unchanged hidden</div>
		{#if hasExcludedDetails}
			<button
				type="button"
				data-testid="toggle-excluded-details"
				aria-pressed={showExcludedDetails}
				aria-expanded={showExcludedDetails}
				onclick={() => (showExcludedDetails = !showExcludedDetails)}
				class="cursor-pointer rounded-md text-left transition-colors hover:bg-ctp-surface0 focus:outline-none focus-visible:ring-2 focus-visible:ring-ctp-accent"
			>
				<strong class="underline decoration-dotted underline-offset-2">
					{preview.summary.excluded}
				</strong><br />excluded
			</button>
		{:else}
			<div><strong>{preview.summary.excluded}</strong><br />excluded</div>
		{/if}
		{#if hasInvalidDetails}
			<button
				type="button"
				data-testid="toggle-invalid-details"
				aria-pressed={showInvalidDetails}
				aria-expanded={showInvalidDetails}
				onclick={() => (showInvalidDetails = !showInvalidDetails)}
				class="cursor-pointer rounded-md text-left transition-colors hover:bg-ctp-surface0 focus:outline-none focus-visible:ring-2 focus-visible:ring-ctp-accent"
			>
				<strong class="underline decoration-dotted underline-offset-2">
					{preview.summary.invalidRows}
				</strong><br />invalid
			</button>
		{:else}
			<div><strong>{preview.summary.invalidRows}</strong><br />invalid</div>
		{/if}
		<div><strong>{preview.summary.aiCategorized}</strong><br />AI categorised</div>
	</div>

	{#if hasExcludedDetails && showExcludedDetails}
		<div
			data-testid="excluded-details-panel"
			class="rounded-lg border border-ctp-surface1 bg-ctp-base p-4 text-sm"
		>
			<p class="mb-3 text-xs text-ctp-overlay1">
				These transactions won't be imported. They were excluded automatically (AI,
				import rule, refund, or incoming money).
			</p>
			<ul class="flex flex-col gap-2">
				{#each excludedDetailRows as row (row.previewRowId)}
					<li
						data-testid="excluded-detail-row"
						class="flex flex-wrap items-start justify-between gap-2 rounded-md border border-ctp-surface0 px-3 py-2"
					>
						<div class="min-w-0">
							<div class="font-medium text-ctp-text">{row.displayName ?? row.name}</div>
							<div class="text-xs text-ctp-overlay1">
								{formatAmount(row.amount, $settings.currency)} · {row.date} · {row.filename}:{row.sourceRow}
							</div>
						</div>
						{#if row.reason}
							<span
								class="rounded-full bg-ctp-surface1 px-2 py-1 text-xs font-medium text-ctp-subtext0"
								>{row.reason}</span
							>
						{/if}
					</li>
				{/each}
			</ul>
		</div>
	{/if}

	{#if hasInvalidDetails && showInvalidDetails}
		<div
			data-testid="invalid-details-panel"
			class="rounded-lg border border-ctp-surface1 bg-ctp-base p-4 text-sm"
		>
			<p class="mb-3 text-xs text-ctp-overlay1">
				These rows couldn't be parsed and won't be imported.
			</p>
			<ul class="flex flex-col gap-2">
				{#each invalidDetailRows as invalidRow, i (`${invalidRow.filename}:${invalidRow.sourceRow}:${i}`)}
					<li
						data-testid="invalid-detail-row"
						class="flex flex-wrap items-start justify-between gap-2 rounded-md border border-ctp-surface0 px-3 py-2"
					>
						<div class="min-w-0">
							<div class="font-medium text-ctp-text">{invalidRow.name || '—'}</div>
							<div class="text-xs text-ctp-overlay1">
								{invalidRow.amount || '—'} · {invalidRow.date || '—'} · {invalidRow.filename}:{invalidRow.sourceRow}
							</div>
						</div>
						<span
							class="rounded-full bg-red-100 px-2 py-1 text-xs font-medium text-red-800 dark:bg-red-950 dark:text-red-200"
							>{invalidRow.reason}</span
						>
					</li>
				{/each}
			</ul>
		</div>
	{/if}

	{#if matchedCount > 0}
		<div class="flex items-center justify-end">
			<button
				type="button"
				data-testid="toggle-show-matched"
				aria-pressed={showMatched}
				onclick={onToggleMatched}
				class="text-xs font-medium text-ctp-accent underline decoration-dotted underline-offset-2 hover:no-underline"
			>
				{showMatched
					? `Hide ${matchedCount} matched`
					: `Show ${matchedCount} matched`}
			</button>
		</div>
	{/if}

	{#if rows.length > 0}
		<div class="overflow-hidden rounded-lg border border-ctp-surface1 bg-ctp-base">
			<div
				class="import-row import-row-header border-b border-ctp-surface1 px-4 py-2 text-xs font-medium uppercase tracking-wide text-ctp-overlay1"
			>
				<div>Transaction</div>
				<div>Amount</div>
				<div>Category</div>
				<div>Importance</div>
				<div>Decision</div>
			</div>
			{#each rows as row (row.previewRowId)}
				{@const matchedDisabled =
					row.userExcluded || (row.kind === 'category_update' && !row.acceptUpdate)}
				<div
					class="import-row border-b border-ctp-surface0 px-4 py-3 text-sm last:border-b-0 {row.userExcluded
						? 'opacity-40'
						: matchedDisabled
							? 'opacity-55'
							: ''}"
				>
					<div>
						<div class="font-medium text-ctp-text">{row.displayName ?? row.name}</div>
						{#if row.displayName}
							<div class="text-xs text-ctp-overlay1">
								<span
									class="rounded bg-ctp-surface1 px-1.5 py-0.5 font-medium text-ctp-subtext0"
									>Rule</span
								>
								renamed from {row.name}
							</div>
						{/if}
						<div class="text-xs text-ctp-overlay1">
							{row.date} · {row.filename}:{row.sourceRow}
						</div>
						{#if row.note}
							<div class="text-xs text-ctp-overlay1">{row.note}</div>
						{/if}
					</div>
					<div>
						{#if row.kind === 'category_update'}
							<div class="text-ctp-subtext0">{formatAmount(row.amount, $settings.currency)}</div>
						{:else}
							<input
								type="text"
								inputmode="decimal"
								data-testid="review-amount-input"
								value={row.selectedAmountInput}
								disabled={row.userExcluded}
								oninput={(event) => onAmountInput(row, event.currentTarget.value)}
								aria-invalid={row.amountError}
								class="h-10 w-full rounded-md border bg-ctp-base px-3 py-2 text-sm text-ctp-text focus:outline-none disabled:opacity-50 {row.amountError
									? 'border-red-500 focus:border-red-500'
									: 'border-ctp-surface1 focus:border-ctp-accent'}"
							/>
							{#if row.amountError}
								<p class="mt-1 text-xs text-red-600 dark:text-red-400">Enter an amount &gt; 0</p>
							{/if}
						{/if}
					</div>
					<div>
						<select
							bind:value={row.selectedCategoryName}
							disabled={matchedDisabled}
							class="field field-select h-10 w-full disabled:opacity-50"
						>
							{#each categoryOptions(row) as category (category.id)}
								<option value={category.name}>{category.name}</option>
							{/each}
						</select>
						{#if row.categoryFromRule && row.overriddenCategoryName}
							<div class="mt-1 text-xs text-ctp-overlay1">
								AI suggested: {row.overriddenCategoryName}
							</div>
						{/if}
					</div>
					<div>
						<select
							bind:value={row.selectedImportance}
							disabled={matchedDisabled}
							class="field field-select h-10 w-full disabled:opacity-50"
						>
							<option value="essential">Essential</option>
							<option value="important">Important</option>
							<option value="discretionary">Discretionary</option>
						</select>
						{#if row.existingImportance && row.existingImportance !== row.selectedImportance}
							<p class="mt-1 text-xs text-ctp-overlay1">
								Was {importanceLabel(row.existingImportance)}
							</p>
						{/if}
					</div>
					<div class="flex flex-col items-start gap-1">
						{#if row.userExcluded}
							<span
								class="rounded-full bg-ctp-surface1 px-2 py-1 text-xs font-medium text-ctp-subtext0"
								>Excluded</span
							>
						{:else if row.kind === 'create'}
							<span
								class="rounded-full bg-emerald-100 px-2 py-1 text-xs font-medium text-emerald-800 dark:bg-emerald-950 dark:text-emerald-200"
								>New transaction</span
							>
						{:else if row.kind === 'category_update'}
							<span
								class="rounded-full px-2 py-1 text-xs font-medium {row.acceptUpdate
									? 'bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-200'
									: 'bg-ctp-surface1 text-ctp-subtext0'}"
							>
								{row.acceptUpdate ? 'Will override existing' : 'Existing kept'}
							</span>
							<button
								type="button"
								data-testid="toggle-override"
								aria-pressed={row.acceptUpdate}
								onclick={() => (row.acceptUpdate = !row.acceptUpdate)}
								class="text-xs font-medium text-ctp-accent underline decoration-dotted underline-offset-2 hover:no-underline"
							>
								{row.acceptUpdate ? 'Disable override' : 'Enable to override'}
							</button>
						{/if}
						<button
							type="button"
							data-testid="toggle-exclude"
							aria-pressed={row.userExcluded}
							onclick={() => (row.userExcluded = !row.userExcluded)}
							class="text-xs font-medium text-ctp-overlay1 underline decoration-dotted underline-offset-2 hover:text-ctp-text hover:no-underline"
						>
							{row.userExcluded ? 'Include' : 'Exclude'}
						</button>
					</div>
				</div>
			{/each}
		</div>

		<div class="flex justify-end gap-2">
			<button
				type="button"
				onclick={onCancel}
				disabled={busy}
				class="rounded-md border border-ctp-surface2 bg-ctp-base px-4 py-2 text-sm font-medium text-ctp-text hover:bg-ctp-surface1 disabled:opacity-60"
			>
				Cancel
			</button>
			<button
				type="button"
				data-testid={confirmTestId}
				onclick={onConfirm}
				disabled={busy}
				class="rounded-md bg-ctp-accent px-4 py-2 text-sm font-medium text-ctp-on-accent hover:bg-ctp-accent-hover disabled:opacity-60"
			>
				{busy
					? 'Saving…'
					: `Save ${createRows.length} new${overrideCount > 0 ? ` and override ${overrideCount} existing` : ''}${excludedCount > 0 ? ` (${excludedCount} excluded)` : ''}`}
			</button>
		</div>
	{/if}
{/snippet}

<svelte:head>
	<title>Import transactions</title>
</svelte:head>

<PageHeader heading="Import transactions" text="Add transactions from a CSV, one at a time, or by pasting free-form text for AI to parse."></PageHeader>

<PageContent>

	<div
		role="tablist"
		aria-label="Import mode"
		class="inline-flex w-full max-w-xl gap-1 rounded-lg border border-ctp-surface1 bg-ctp-mantle p-1 sm:w-auto"
	>
		<button
			type="button"
			role="tab"
			aria-selected={tab === 'csv'}
			data-testid="import-tab-csv"
			onclick={() => setTab('csv')}
			class="flex-1 rounded-md px-4 py-2 text-sm font-medium transition-colors {tab === 'csv'
				? 'bg-ctp-accent text-ctp-on-accent shadow-sm'
				: 'text-ctp-subtext0 hover:bg-ctp-surface0 hover:text-ctp-text'}"
		>
			CSV file
		</button>
		<button
			type="button"
			role="tab"
			aria-selected={tab === 'single'}
			data-testid="import-tab-single"
			onclick={() => setTab('single')}
			class="flex-1 rounded-md px-4 py-2 text-sm font-medium transition-colors {tab === 'single'
				? 'bg-ctp-accent text-ctp-on-accent shadow-sm'
				: 'text-ctp-subtext0 hover:bg-ctp-surface0 hover:text-ctp-text'}"
		>
			Single transaction
		</button>
		<button
			type="button"
			role="tab"
			aria-selected={tab === 'freeform'}
			data-testid="import-tab-freeform"
			onclick={() => setTab('freeform')}
			class="flex-1 rounded-md px-4 py-2 text-sm font-medium transition-colors {tab === 'freeform'
				? 'bg-ctp-accent text-ctp-on-accent shadow-sm'
				: 'text-ctp-subtext0 hover:bg-ctp-surface0 hover:text-ctp-text'}"
		>
			AI free-form
		</button>
	</div>

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

	<!-- TAB 1 — CSV ------------------------------------------------------- -->
	{#if tab === 'csv'}
		<div data-testid="import-panel-csv" class="flex flex-col gap-6">
			<div
				class="flex flex-wrap items-center justify-between gap-4 rounded-lg border border-ctp-surface1 bg-ctp-base p-4"
			>
				<p class="max-w-xl text-sm text-ctp-overlay1">
					Preview CSV transactions before saving. Transactions that already exist are never
					overwritten by default — they're shown disabled so your earlier edits are kept. Use
					“Enable to override” on a row to apply the imported category / importance, “Exclude”
					to skip any row (including new ones), and “Hide matched” to collapse the existing
					rows away.
				</p>
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
						data-testid="select-import-files"
						onclick={openFilePicker}
						disabled={loading || saving}
						class="inline-flex items-center justify-center rounded-md bg-ctp-accent px-4 py-2 text-sm font-medium text-ctp-on-accent transition-colors hover:bg-ctp-accent-hover disabled:cursor-not-allowed disabled:opacity-60"
					>
						{loading ? 'Previewing…' : 'Select CSV'}
					</button>
				</div>
			</div>

			{#if csvReview}
				{@render reviewTable(
					csvVisibleRows,
					csvCreateRows,
					csvUpdateRows,
					csvReview.preview,
					saving,
					'confirm-import',
					csvMatchedCount,
					csvShowMatched,
					() => (csvShowMatched = !csvShowMatched),
					() => (csvReview = null),
					confirmCsvImport
				)}
			{/if}
		</div>
	{/if}

	<!-- TAB 2 — Single transaction --------------------------------------- -->
	{#if tab === 'single'}
		<div data-testid="import-panel-single">
			<form
				class="flex max-w-md flex-col gap-4 rounded-lg border border-ctp-surface1 bg-ctp-base p-6"
				onsubmit={handleSingleSubmit}
				novalidate
			>
				<div class="flex flex-col gap-1">
					<label for="single-name" class="text-sm font-medium text-ctp-subtext0">Merchant</label>
					<input
						id="single-name"
						data-testid="name-input"
						type="text"
						maxlength="80"
						autocomplete="off"
						placeholder="e.g. Starbucks"
						bind:value={nameInput}
						class="field"
					/>
					{#if nameError}
						<p data-testid="name-error" class="text-sm text-red-600 dark:text-red-400">{nameError}</p>
					{/if}
				</div>

				<div class="flex flex-col gap-1">
					<label for="single-amount" class="text-sm font-medium text-ctp-subtext0">Amount</label>
					<input
						id="single-amount"
						data-testid="amount-input"
						type="number"
						step="0.01"
						min="0"
						inputmode="decimal"
						autocomplete="off"
						placeholder="0.00"
						value={amountInput}
						oninput={(event) => (amountInput = event.currentTarget.value)}
						class="field"
					/>
					{#if amountError}
						<p data-testid="amount-error" class="text-sm text-red-600 dark:text-red-400">
							{amountError}
						</p>
					{/if}
				</div>

				<div class="flex flex-col gap-1">
					<label for="single-date" class="text-sm font-medium text-ctp-subtext0">Date</label>
					<input
						id="single-date"
						data-testid="date-input"
						type="date"
						autocomplete="off"
						bind:value={dateInput}
						class="field"
					/>
					{#if dateError}
						<p data-testid="date-error" class="text-sm text-red-600 dark:text-red-400">{dateError}</p>
					{/if}
				</div>

				<div class="flex flex-col gap-1">
					<label for="single-category" class="text-sm font-medium text-ctp-subtext0">Category</label>
					<select
						id="single-category"
						data-testid="category-select"
						bind:value={categoryInput}
						class="field field-select"
					>
						<option value="" disabled>Select a category</option>
						{#each $categories as category (category.id)}
							<option value={category.id}>{category.name}</option>
						{/each}
					</select>
					{#if categoryError}
						<p data-testid="category-error" class="text-sm text-red-600 dark:text-red-400">
							{categoryError}
						</p>
					{/if}
				</div>

				<div class="flex flex-col gap-1">
					<label for="single-importance" class="text-sm font-medium text-ctp-subtext0"
						>Importance</label
					>
					<select
						id="single-importance"
						data-testid="importance-select"
						bind:value={importanceInput}
						class="field field-select"
					>
						<option value="essential">Essential</option>
						<option value="important">Important</option>
						<option value="discretionary">Discretionary</option>
					</select>
				</div>

				<div class="flex flex-col gap-1">
					<label for="single-note" class="text-sm font-medium text-ctp-subtext0">Note</label>
					<input
						id="single-note"
						data-testid="note-input"
						type="text"
						maxlength="200"
						autocomplete="off"
						bind:value={noteInput}
						class="field"
					/>
					<p class="text-right text-xs text-ctp-overlay1">{noteInput.length}/200</p>
				</div>

				<div class="flex items-center justify-end gap-2 pt-2">
					<button
						type="submit"
						data-testid="single-add-submit"
						disabled={singleSubmitting}
						class="rounded-md bg-ctp-accent px-4 py-2 text-sm font-medium text-ctp-on-accent hover:bg-ctp-accent-hover disabled:opacity-60"
					>
						{singleSubmitting ? 'Adding…' : 'Add transaction'}
					</button>
				</div>
			</form>
		</div>
	{/if}

	<!-- TAB 3 — AI free-form --------------------------------------------- -->
	{#if tab === 'freeform'}
		<div data-testid="import-panel-freeform" class="flex flex-col gap-6">
			<div class="flex flex-col gap-3 rounded-lg border border-ctp-surface1 bg-ctp-base p-4">
				<p class="max-w-xl text-sm text-ctp-overlay1">
					Paste transactions in plain English — one per line. AI will parse the merchant, amount,
					and date, then suggest categories for you to review before saving.
				</p>
				<textarea
					data-testid="freeform-input"
					rows="6"
					bind:value={freeformInput}
					placeholder={'coffee 3.50 yesterday\nTesco 42.10 on the 3rd\nNetflix 12.99'}
					class="field w-full resize-y font-mono"
				></textarea>
				<div class="flex justify-end">
					<button
						type="button"
						data-testid="freeform-parse"
						onclick={parseFreeform}
						disabled={freeformParsing || freeformSaving}
						class="inline-flex items-center justify-center rounded-md bg-ctp-accent px-4 py-2 text-sm font-medium text-ctp-on-accent transition-colors hover:bg-ctp-accent-hover disabled:cursor-not-allowed disabled:opacity-60"
					>
						{freeformParsing ? 'Parsing…' : 'Parse with AI'}
					</button>
				</div>
			</div>

			{#if freeformReview}
				{@render reviewTable(
					freeformVisibleRows,
					freeformCreateRows,
					freeformUpdateRows,
					freeformReview.preview,
					freeformSaving,
					'freeform-confirm',
					freeformMatchedCount,
					freeformShowMatched,
					() => (freeformShowMatched = !freeformShowMatched),
					() => (freeformReview = null),
					confirmFreeformImport
				)}
			{/if}
		</div>
	{/if}

	<!-- Shared import history -------------------------------------------- -->
	{#if importLogs.length > 0}
		<div class="overflow-hidden rounded-lg border border-ctp-surface1 bg-ctp-base">
			<div class="border-b border-ctp-surface1 px-4 py-3">
				<h2 class="text-sm font-medium text-ctp-text">Import history</h2>
			</div>
			<div
				class="import-log-row border-b border-ctp-surface1 px-4 py-2 text-xs font-medium uppercase tracking-wide text-ctp-overlay1"
			>
				<div>Date / Time</div>
				<div>Source</div>
				<div>Files</div>
				<div>Imported</div>
				<div>Updated</div>
				<div>Skipped</div>
			</div>
			{#each importLogs as log (log.id)}
				<div class="border-b border-ctp-surface0 last:border-b-0">
					<div class="import-log-row px-4 py-3 text-sm">
						<div class="text-ctp-subtext0">
							{new Date(log.importedAt).toLocaleString('en-GB', {
								dateStyle: 'medium',
								timeStyle: 'short'
							})}
						</div>
						<div>
							{#if log.source === 'freeform'}
								<span
									class="inline-flex items-center gap-1 rounded-full bg-ctp-accent/15 px-2 py-1 text-xs font-medium text-ctp-accent"
								>
									AI
									{#if log.rawInput}
										<button
											type="button"
											onclick={() => toggleLog(log.id)}
											class="ml-1 underline decoration-dotted underline-offset-2 hover:no-underline"
										>
											{expandedLogs[log.id] ? 'hide' : 'view'}
										</button>
									{/if}
								</span>
							{:else}
								<span
									class="inline-flex items-center rounded-full bg-ctp-surface1 px-2 py-1 text-xs font-medium text-ctp-subtext0"
									>CSV</span
								>
							{/if}
						</div>
						<div class="text-ctp-overlay1">
							{log.files.length > 0 ? log.files.join(', ') : '—'}
						</div>
						<div class="text-ctp-subtext0">{log.imported}</div>
						<div class="text-ctp-subtext0">{log.updated}</div>
						<div class="text-xs text-ctp-overlay1">
							{#if log.skippedDuplicates > 0}
								<span>{log.skippedDuplicates} dup</span>
							{/if}
							{#if log.skippedExcluded > 0}
								<span>{log.skippedExcluded} excl</span>
							{/if}
							{#if log.skippedInvalidRows > 0}
								<span>{log.skippedInvalidRows} invalid</span>
							{/if}
							{#if log.skippedDuplicates === 0 && log.skippedExcluded === 0 && log.skippedInvalidRows === 0}
								<span>—</span>
							{/if}
						</div>
					</div>
					{#if log.source === 'freeform' && log.rawInput && expandedLogs[log.id]}
						<div class="px-4 pb-3">
							<pre
								data-testid="import-log-rawinput-{log.id}"
								class="overflow-x-auto whitespace-pre-wrap rounded-md border border-ctp-surface1 bg-ctp-mantle px-3 py-2 font-mono text-xs text-ctp-subtext0">{log.rawInput}</pre>
						</div>
					{/if}
				</div>
			{/each}
		</div>
	{/if}
</PageContent>

<style>
	.import-summary {
		display: grid;
		grid-template-columns: repeat(6, minmax(0, 1fr));
		gap: 0.75rem;
	}

	.import-row {
		display: grid;
		grid-template-columns: minmax(18rem, 1.6fr) minmax(6rem, 0.55fr) minmax(12rem, 1fr) minmax(10rem, 0.8fr) minmax(
				14rem,
				1fr
			);
		gap: 0.75rem;
		/* Top-align so the amount/category/importance controls share one line
		   even when a cell carries a hint (e.g. "AI suggested: …") below it. */
		align-items: start;
	}

	.import-row-header {
		align-items: end;
	}

	.import-log-row {
		display: grid;
		grid-template-columns: minmax(10rem, 1.2fr) minmax(5rem, 0.6fr) minmax(10rem, 2fr) 6rem 6rem minmax(
				8rem,
				1fr
			);
		gap: 0.75rem;
		align-items: center;
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

		.import-log-row {
			grid-template-columns: 1fr;
			align-items: start;
		}
	}
</style>

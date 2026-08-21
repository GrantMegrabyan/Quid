<script lang="ts">
	import PageHeader from '$components/shell/PageHeader.svelte';
	import PageContent from '$components/shell/PageContent.svelte';
	import { onMount, tick } from 'svelte';
	import { categories, refreshCategories } from '$lib/stores/categories';
	import {
		addImportRule,
		applyAllImportRules,
		applyImportRule,
		deleteImportRule,
		editImportRule,
		importRules,
		previewImportRule,
		refreshImportRules
	} from '$lib/stores/importRules';
	import { refreshSettings, settings } from '$lib/stores/settings';
	import { pendingDeletes, pendingKey, softDelete } from '$lib/stores/toasts';
	import { formatAmount } from '$lib/utils/money';
	import type {
		AmountMatchOp,
		ImportRule,
		ImportRuleCreate,
		ImportRulePreviewRequest,
		ImportRulePreviewResult,
		NameMatchOp,
		RuleAction
	} from '$types';
	import { Eye, Pencil, Power, RefreshCw, Trash2, X } from '@lucide/svelte';

	type FormState = {
		name: string;
		enabled: boolean;
		priority: number;
		action: RuleAction;
		targetCategoryId: string;
		matchNameOp: NameMatchOp | '';
		matchNameValue: string;
		matchAmountOp: AmountMatchOp | '';
		matchAmountValue: string;
		matchAmountValue2: string;
		matchDateFrom: string;
		matchDateTo: string;
		matchDayOfMonth: string;
		setDisplayName: string;
		setNote: string;
	};

	type RuleResult = { kind: 'message' | 'error'; text: string };

	const emptyForm = (): FormState => ({
		name: '',
		enabled: true,
		priority: 100,
		action: 'categorize',
		targetCategoryId: '',
		matchNameOp: 'contains',
		matchNameValue: '',
		matchAmountOp: '',
		matchAmountValue: '',
		matchAmountValue2: '',
		matchDateFrom: '',
		matchDateTo: '',
		matchDayOfMonth: '',
		setDisplayName: '',
		setNote: ''
	});

	let form = $state<FormState>(emptyForm());
	let editingId: string | null = $state(null);
	let showAddForm = $state(false);
	let error = $state('');
	let message = $state('');
	let saving = $state(false);
	let applyingId: string | null = $state(null);
	let applyingAll = $state(false);
	let ruleResults = $state<Record<string, RuleResult>>({});
	let highlightedId: string | null = $state(null);
	let highlightTimer: ReturnType<typeof setTimeout> | null = null;

	function categoryName(id: string | null): string {
		return $categories.find((c) => c.id === id)?.name ?? 'Unknown category';
	}

	/** Normalise a rule amount field to a canonical 2dp string the API accepts.
	 *  Falls back to the trimmed raw value if it isn't a plain decimal (the
	 *  backend coerces it). */
	function amountString(raw: string): string {
		const trimmed = raw.trim();
		const parsed = Number(trimmed);
		return Number.isFinite(parsed) ? parsed.toFixed(2) : trimmed;
	}

	function amountText(rule: ImportRule): string | null {
		if (!rule.matchAmountOp || rule.matchAmountValue === null) return null;
		const value = formatAmount(rule.matchAmountValue, $settings.currency);
		if (rule.matchAmountOp === 'gte') return `amount ≥ ${value}`;
		if (rule.matchAmountOp === 'lte') return `amount ≤ ${value}`;
		if (rule.matchAmountOp === 'eq') return `amount = ${value}`;
		return `amount between ${value} and ${formatAmount(rule.matchAmountValue2 ?? 0, $settings.currency)}`;
	}

	function summary(rule: ImportRule): string {
		const parts: string[] = [];
		if (rule.matchNameOp && rule.matchNameValue) {
			parts.push(`name ${rule.matchNameOp.replace('_', ' ')} "${rule.matchNameValue}"`);
		}
		const amount = amountText(rule);
		if (amount) parts.push(amount);
		if (rule.matchDateFrom) parts.push(`date from ${rule.matchDateFrom}`);
		if (rule.matchDateTo) parts.push(`date to ${rule.matchDateTo}`);
		if (rule.matchDayOfMonth) parts.push(`day of month = ${rule.matchDayOfMonth}`);
		return parts.join(' · ');
	}

	function startEdit(rule: ImportRule): void {
		editingId = rule.id;
		form = {
			name: rule.name,
			enabled: rule.enabled,
			priority: rule.priority,
			action: rule.action,
			targetCategoryId: rule.targetCategoryId ?? '',
			matchNameOp: rule.matchNameOp ?? '',
			matchNameValue: rule.matchNameValue ?? '',
			matchAmountOp: rule.matchAmountOp ?? '',
			matchAmountValue: rule.matchAmountValue === null ? '' : String(rule.matchAmountValue),
			matchAmountValue2: rule.matchAmountValue2 === null ? '' : String(rule.matchAmountValue2),
			matchDateFrom: rule.matchDateFrom ?? '',
			matchDateTo: rule.matchDateTo ?? '',
			matchDayOfMonth: rule.matchDayOfMonth === null ? '' : String(rule.matchDayOfMonth),
			setDisplayName: rule.setDisplayName ?? '',
			setNote: rule.setNote ?? ''
		};
		error = '';
		message = '';
		clearFormPreview();
	}

	function flashRule(ruleId: string): void {
		// Retrigger cleanly if the same card is flashed again before the last one finished.
		if (highlightTimer) clearTimeout(highlightTimer);
		highlightedId = null;
		// Defer one frame so the smooth scroll is underway (and the animation restarts) before it shows.
		requestAnimationFrame(() => {
			highlightedId = ruleId;
			highlightTimer = setTimeout(() => {
				if (highlightedId === ruleId) highlightedId = null;
				highlightTimer = null;
			}, 1400);
		});
	}

	async function scrollRuleIntoViewIfNeeded(ruleId: string): Promise<void> {
		await tick();
		const card = document.querySelector<HTMLElement>(`[data-rule-id="${ruleId}"]`);
		if (!card) return;
		const rect = card.getBoundingClientRect();
		const fullyVisible = rect.top >= 0 && rect.bottom <= window.innerHeight;
		if (!fullyVisible) card.scrollIntoView({ behavior: 'smooth', block: 'start' });
		flashRule(ruleId);
	}

	function cancelEdit(): void {
		const closingId = editingId;
		editingId = null;
		form = emptyForm();
		error = '';
		if (closingId) void scrollRuleIntoViewIfNeeded(closingId);
	}

	function openAddForm(): void {
		showAddForm = true;
		form = emptyForm();
		error = '';
	}

	function closeAddForm(): void {
		showAddForm = false;
		form = emptyForm();
		error = '';
	}

	function toPayload(): ImportRuleCreate {
		const name = form.name.trim();
		if (!name) throw new Error('Rule name is required.');
		if (form.action === 'categorize' && !form.targetCategoryId) {
			throw new Error('Choose a target category for categorize rules.');
		}
		const hasName = form.matchNameOp !== '' && form.matchNameValue.trim() !== '';
		const hasAmount = form.matchAmountOp !== '' && form.matchAmountValue !== '';
		const hasDate = form.matchDateFrom !== '' || form.matchDateTo !== '';
		const dayInput = (form.matchDayOfMonth ?? '').trim();
		const hasDay = dayInput !== '';
		if (!hasName && !hasAmount && !hasDate && !hasDay) {
			throw new Error('Add at least one match condition.');
		}
		if (form.matchAmountOp === 'between' && !form.matchAmountValue2) {
			throw new Error('Between amount rules require a second amount.');
		}
		let dayOfMonth: number | null = null;
		if (hasDay) {
			const parsed = Number(dayInput);
			if (!Number.isInteger(parsed) || parsed < 1 || parsed > 31) {
				throw new Error('Day of month must be a whole number between 1 and 31.');
			}
			dayOfMonth = parsed;
		}
		return {
			name,
			enabled: form.enabled,
			priority: Number(form.priority),
			action: form.action,
			targetCategoryId: form.action === 'categorize' ? form.targetCategoryId : null,
			matchNameOp: hasName ? (form.matchNameOp as NameMatchOp) : null,
			matchNameValue: hasName ? form.matchNameValue.trim() : null,
			matchAmountOp: hasAmount ? (form.matchAmountOp as AmountMatchOp) : null,
			matchAmountValue: hasAmount ? amountString(form.matchAmountValue) : null,
			matchAmountValue2:
				hasAmount && form.matchAmountOp === 'between'
					? amountString(form.matchAmountValue2)
					: null,
			matchDateFrom: form.matchDateFrom || null,
			matchDateTo: form.matchDateTo || null,
			matchDayOfMonth: dayOfMonth,
			setDisplayName: form.setDisplayName.trim() || null,
			setNote: form.setNote.trim() || null
		};
	}

	async function saveRule(event: SubmitEvent): Promise<void> {
		event.preventDefault();
		if (saving) return;
		saving = true;
		error = '';
		message = '';
		try {
			const payload = toPayload();
			if (editingId) {
				await editImportRule(editingId, payload);
				message = 'Rule saved.';
				cancelEdit();
			} else {
				await addImportRule(payload);
				message = 'Rule added.';
				closeAddForm();
			}
		} catch (err) {
			error = err instanceof Error ? err.message : 'Could not save rule.';
		} finally {
			saving = false;
		}
	}

	async function toggleEnabled(rule: ImportRule): Promise<void> {
		await editImportRule(rule.id, { enabled: !rule.enabled });
	}

	async function applyRule(rule: ImportRule): Promise<void> {
		applyingId = rule.id;
		delete ruleResults[rule.id];
		ruleResults = { ...ruleResults };
		try {
			const result = await applyImportRule(rule.id);
			ruleResults = {
				...ruleResults,
				[rule.id]: {
					kind: 'message',
					text: `Matched ${result.matched}; updated ${result.updated}; deleted ${result.deleted}.`
				}
			};
		} catch (err) {
			ruleResults = {
				...ruleResults,
				[rule.id]: {
					kind: 'error',
					text: err instanceof Error ? err.message : 'Could not apply rule.'
				}
			};
		} finally {
			applyingId = null;
		}
	}

	async function applyAll(): Promise<void> {
		if (applyingAll) return;
		applyingAll = true;
		message = '';
		error = '';
		try {
			const result = await applyAllImportRules();
			message = `Reapplied all rules: matched ${result.matched}; updated ${result.updated}; deleted ${result.deleted}.`;
		} catch (err) {
			error = err instanceof Error ? err.message : 'Could not reapply all rules.';
		} finally {
			applyingAll = false;
		}
	}

	function removeRule(rule: ImportRule): void {
		if (editingId === rule.id) cancelEdit();
		delete ruleResults[rule.id];
		ruleResults = { ...ruleResults };
		softDelete({
			kind: 'rule',
			id: rule.id,
			message: `Deleted rule “${rule.name}”.`,
			commit: () => deleteImportRule(rule.id)
		});
	}

	// ---- preview (dry-run) ----
	const PREVIEW_LIMIT = 50;

	// Form preview: derive a preview request from the CURRENT draft form state.
	let previewing = $state(false);
	let previewError = $state<string | null>(null);
	let previewResult = $state<ImportRulePreviewResult | null>(null);

	function clearFormPreview(): void {
		previewing = false;
		previewError = null;
		previewResult = null;
	}

	/** Build a preview request from the CURRENT draft form, reusing the same
	 *  condition parsing as toPayload(). Throws on invalid/empty conditions. */
	function toPreviewRequest(): ImportRulePreviewRequest {
		const hasName = form.matchNameOp !== '' && form.matchNameValue.trim() !== '';
		const hasAmount = form.matchAmountOp !== '' && form.matchAmountValue !== '';
		const hasDate = form.matchDateFrom !== '' || form.matchDateTo !== '';
		const dayInput = (form.matchDayOfMonth ?? '').trim();
		const hasDay = dayInput !== '';
		if (!hasName && !hasAmount && !hasDate && !hasDay) {
			throw new Error('Add at least one match condition.');
		}
		if (form.matchAmountOp === 'between' && !form.matchAmountValue2) {
			throw new Error('Between amount rules require a second amount.');
		}
		let dayOfMonth: number | null = null;
		if (hasDay) {
			const parsed = Number(dayInput);
			if (!Number.isInteger(parsed) || parsed < 1 || parsed > 31) {
				throw new Error('Day of month must be a whole number between 1 and 31.');
			}
			dayOfMonth = parsed;
		}
		return {
			matchNameOp: hasName ? (form.matchNameOp as NameMatchOp) : null,
			matchNameValue: hasName ? form.matchNameValue.trim() : null,
			matchAmountOp: hasAmount ? (form.matchAmountOp as AmountMatchOp) : null,
			matchAmountValue: hasAmount ? amountString(form.matchAmountValue) : null,
			matchAmountValue2:
				hasAmount && form.matchAmountOp === 'between'
					? amountString(form.matchAmountValue2)
					: null,
			matchDateFrom: form.matchDateFrom || null,
			matchDateTo: form.matchDateTo || null,
			matchDayOfMonth: dayOfMonth
		};
	}

	async function handlePreviewForm(): Promise<void> {
		if (previewing) return;
		previewError = null;
		let request: ImportRulePreviewRequest;
		try {
			request = toPreviewRequest();
		} catch (err) {
			error = err instanceof Error ? err.message : 'Could not preview rule.';
			previewResult = null;
			return;
		}
		error = '';
		previewing = true;
		try {
			previewResult = await previewImportRule(request);
		} catch (err) {
			previewError = err instanceof Error ? err.message : 'Failed to preview rule.';
			previewResult = null;
		} finally {
			previewing = false;
		}
	}

	// Per-card preview: derive the request from a SAVED rule's match conditions.
	let cardPreviewingId = $state<string | null>(null);
	let cardPreviews = $state<Record<string, ImportRulePreviewResult>>({});

	function rulePreviewRequest(rule: ImportRule): ImportRulePreviewRequest {
		return {
			matchNameOp: rule.matchNameOp ?? null,
			matchNameValue: rule.matchNameValue ?? null,
			matchAmountOp: rule.matchAmountOp ?? null,
			matchAmountValue: rule.matchAmountValue ?? null,
			matchAmountValue2: rule.matchAmountValue2 ?? null,
			matchDateFrom: rule.matchDateFrom ?? null,
			matchDateTo: rule.matchDateTo ?? null,
			matchDayOfMonth: rule.matchDayOfMonth ?? null
		};
	}

	async function handlePreviewCard(rule: ImportRule) {
		cardPreviewingId = rule.id;
		try {
			const result = await previewImportRule(rulePreviewRequest(rule));
			cardPreviews = { ...cardPreviews, [rule.id]: result };
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to preview rule.';
		} finally {
			cardPreviewingId = null;
		}
	}

	function clearCardPreview(ruleId: string): void {
		const { [ruleId]: _removed, ...rest } = cardPreviews;
		cardPreviews = rest;
	}

	onMount(() => {
		void refreshCategories();
		void refreshImportRules();
		void refreshSettings();
	});
</script>

{#snippet ruleForm(headingText: string)}
	<form onsubmit={saveRule} class="rounded-lg border border-ctp-surface1 bg-ctp-base p-4">
		<div class="mb-4 flex items-center justify-between gap-3">
			<h2 class="text-lg font-medium text-ctp-text">{headingText}</h2>
			{#if editingId}
				<button type="button" class="text-sm text-ctp-blue underline" onclick={cancelEdit}>Cancel edit</button>
			{:else}
				<button type="button" class="text-sm text-ctp-blue underline" onclick={closeAddForm}>Cancel</button>
			{/if}
		</div>

		<!-- Section A — Rule details (meta / identity) -->
		<fieldset class="rounded-md border border-ctp-surface1 bg-ctp-mantle/40 p-4">
			<legend class="px-1 text-xs font-semibold uppercase tracking-wide text-ctp-overlay1">Rule details</legend>
			<p class="mb-3 text-xs text-ctp-overlay0">Name this rule and set its priority (lower numbers run first).</p>
			<div class="grid grid-cols-1 gap-3 md:grid-cols-3">
				<label class="flex flex-col gap-1 text-sm text-ctp-subtext0">
					<span>Name</span>
					<input bind:value={form.name} class="field" />
				</label>
				<label class="flex flex-col gap-1 text-sm text-ctp-subtext0">
					<span>Priority</span>
					<input bind:value={form.priority} type="number" class="field" />
				</label>
				<label class="flex items-center gap-2 pt-6 text-sm text-ctp-subtext0">
					<input bind:checked={form.enabled} type="checkbox" class="h-4 w-4 accent-ctp-accent" />
					Enabled
				</label>
			</div>
		</fieldset>

		<!-- Section B — Match conditions -->
		<fieldset class="mt-4 rounded-md border border-ctp-surface1 bg-ctp-mantle/40 p-4">
			<legend class="px-1 text-xs font-semibold uppercase tracking-wide text-ctp-overlay1">When a transaction matches</legend>
			<p class="mb-3 text-xs text-ctp-overlay0">Set one or more conditions to match transactions.</p>

			<div class="grid grid-cols-1 gap-3 md:grid-cols-3">
				<label class="flex flex-col gap-1 text-sm text-ctp-subtext0">
					<span>Name match</span>
					<select bind:value={form.matchNameOp} class="field field-select">
						<option value="">No name condition</option>
						<option value="contains">contains</option>
						<option value="equals">equals</option>
						<option value="starts_with">starts with</option>
						<option value="ends_with">ends with</option>
					</select>
				</label>
				<label class="flex flex-col gap-1 text-sm text-ctp-subtext0 md:col-span-2">
					<span>Name value</span>
					<input bind:value={form.matchNameValue} class="field" />
				</label>
			</div>

			<div class="mt-3 grid grid-cols-1 gap-3 md:grid-cols-3">
				<label class="flex flex-col gap-1 text-sm text-ctp-subtext0">
					<span>Amount match</span>
					<select bind:value={form.matchAmountOp} class="field field-select">
						<option value="">No amount condition</option>
						<option value="gte">≥</option>
						<option value="lte">≤</option>
						<option value="eq">=</option>
						<option value="between">between</option>
					</select>
				</label>
				<label class="flex flex-col gap-1 text-sm text-ctp-subtext0">
					<span>Amount</span>
					<input bind:value={form.matchAmountValue} type="number" step="0.01" class="field" />
				</label>
				{#if form.matchAmountOp === 'between'}
					<label class="flex flex-col gap-1 text-sm text-ctp-subtext0">
						<span>Second amount</span>
						<input bind:value={form.matchAmountValue2} type="number" step="0.01" class="field" />
					</label>
				{/if}
			</div>

			<div class="mt-3 grid grid-cols-1 gap-3 md:grid-cols-3">
				<label class="flex flex-col gap-1 text-sm text-ctp-subtext0">
					<span>Date from</span>
					<input bind:value={form.matchDateFrom} type="date" class="field" />
				</label>
				<label class="flex flex-col gap-1 text-sm text-ctp-subtext0">
					<span>Date to</span>
					<input bind:value={form.matchDateTo} type="date" class="field" />
				</label>
				<label class="flex flex-col gap-1 text-sm text-ctp-subtext0">
					<span>Day of month <span class="text-ctp-overlay0">(1–31)</span></span>
					<input
						value={form.matchDayOfMonth}
						oninput={(e) => (form.matchDayOfMonth = e.currentTarget.value)}
						type="text"
						inputmode="numeric"
						placeholder="e.g. 1 for monthly payment"
						class="field"
					/>
				</label>
			</div>
		</fieldset>

		<!-- Section C — Actions -->
		<fieldset class="mt-4 rounded-md border border-ctp-surface1 bg-ctp-mantle/40 p-4">
			<legend class="px-1 text-xs font-semibold uppercase tracking-wide text-ctp-overlay1">Then do this</legend>
			<p class="mb-3 text-xs text-ctp-overlay0">What happens to a transaction that matches the conditions above.</p>

			<div class="grid grid-cols-1 gap-3 md:grid-cols-3">
				<label class="flex flex-col gap-1 text-sm text-ctp-subtext0">
					<span>Action</span>
					<select bind:value={form.action} class="field field-select">
						<option value="categorize">Categorize</option>
						<option value="exclude">Exclude</option>
					</select>
				</label>
				{#if form.action === 'categorize'}
					<label class="flex flex-col gap-1 text-sm text-ctp-subtext0 md:col-span-2">
						<span>Target category</span>
						<select bind:value={form.targetCategoryId} class="field field-select">
							<option value="">Choose category</option>
							{#each $categories as category (category.id)}
								<option value={category.id}>{category.name}</option>
							{/each}
						</select>
					</label>
				{/if}
			</div>

			{#if form.action === 'categorize'}
				<div class="mt-3 grid grid-cols-1 gap-3">
					<label class="flex flex-col gap-1 text-sm text-ctp-subtext0">
						<span>Set display name <span class="text-ctp-overlay0">(optional)</span></span>
						<input bind:value={form.setDisplayName} type="text" maxlength="200" placeholder="Leave blank to keep merchant name" class="field" />
					</label>
					<label class="flex flex-col gap-1 text-sm text-ctp-subtext0">
						<span>Set note <span class="text-ctp-overlay0">(optional)</span></span>
						<input bind:value={form.setNote} data-testid="rule-set-note" type="text" maxlength="500" placeholder="Leave blank to keep imported note" class="field" />
					</label>
				</div>
			{/if}
		</fieldset>

		<div class="mt-4 flex flex-wrap items-center gap-2">
			<button type="submit" disabled={saving} class="rounded-md bg-ctp-accent px-4 py-2 text-sm font-medium text-ctp-on-accent hover:bg-ctp-accent-hover disabled:opacity-60">
				{saving ? 'Saving…' : editingId ? 'Save rule' : 'Add rule'}
			</button>
			<button
				type="button"
				data-testid="rule-preview-btn"
				disabled={previewing}
				onclick={handlePreviewForm}
				class="inline-flex items-center gap-2 rounded-md border border-ctp-surface2 bg-ctp-base px-4 py-2 text-sm font-medium text-ctp-subtext0 transition-colors hover:bg-ctp-surface1 hover:text-ctp-text disabled:cursor-not-allowed disabled:opacity-60"
			>
				<Eye size={16} aria-hidden="true" />
				{previewing ? 'Previewing…' : 'Preview matches'}
			</button>
		</div>

		{#if error}
			<p class="mt-3 rounded-md border border-ctp-red/40 bg-ctp-red/10 px-3 py-2 text-sm text-ctp-red">
				{error}
			</p>
		{/if}

		{#if previewError}
			<p class="mt-3 rounded-md border border-ctp-red/40 bg-ctp-red/10 px-3 py-2 text-sm text-ctp-red">
				{previewError}
			</p>
		{/if}

		{#if previewResult}
			<div data-testid="rule-preview-results" class="mt-3 rounded-md border border-ctp-surface1 bg-ctp-mantle/40 p-3">
				{@render previewMatches(previewResult, clearFormPreview)}
			</div>
		{/if}
	</form>
{/snippet}

{#snippet previewMatches(preview: ImportRulePreviewResult, onClose: () => void)}
	<div class="flex items-start justify-between gap-3">
		<p class="text-sm font-medium text-ctp-text">
			<span data-testid="rule-preview-count">{preview.matched}</span>
			{preview.matched === 1 ? 'transaction matches' : 'transactions match'} these conditions.
		</p>
		<button
			type="button"
			data-testid="rule-preview-close"
			aria-label="Hide preview"
			title="Hide preview"
			onclick={onClose}
			class="-mr-1 -mt-1 shrink-0 rounded-md p-1 text-ctp-subtext0 transition-colors hover:bg-ctp-surface1 hover:text-ctp-text"
		>
			<X size={16} aria-hidden="true" />
		</button>
	</div>
	{#if preview.matched === 0}
		<p class="mt-1 text-xs text-ctp-overlay1">No existing transactions match these conditions.</p>
	{:else}
		{#if preview.matched > PREVIEW_LIMIT}
			<p class="mt-1 text-xs text-ctp-overlay1">Showing first {PREVIEW_LIMIT} of {preview.matched}.</p>
		{/if}
		<ul class="mt-2 flex flex-col divide-y divide-ctp-surface1 overflow-hidden rounded-md border border-ctp-surface1 bg-ctp-base">
			{#each preview.expenses.slice(0, PREVIEW_LIMIT) as expense (expense.id)}
				<li data-testid="rule-preview-row" class="flex items-center justify-between gap-3 px-3 py-2 text-sm">
					<span class="min-w-0 flex-1 truncate text-ctp-text">{expense.displayName || expense.name}</span>
					<span class="shrink-0 text-xs text-ctp-overlay1">{expense.date.slice(0, 10)}</span>
					<span class="shrink-0 font-medium text-ctp-text">{formatAmount(expense.amount, $settings.currency)}</span>
				</li>
			{/each}
		</ul>
	{/if}
{/snippet}

<svelte:head><title>Import Rules</title></svelte:head>

<PageHeader heading="Import rules" text="Exclude transfers, auto-categorize merchants, and re-apply rules to existing expenses.">
	{#snippet actions()}
<div class="flex flex-wrap items-center gap-2">
			<button
				type="button"
				data-testid="reapply-all-rules-btn"
				disabled={applyingAll || $importRules.length === 0}
				onclick={applyAll}
				class="inline-flex items-center justify-center rounded-md border border-ctp-surface2 bg-ctp-base px-4 py-2 text-sm font-medium text-ctp-subtext0 transition-colors hover:bg-ctp-surface1 disabled:cursor-not-allowed disabled:opacity-60"
			>
				{applyingAll ? 'Reapplying…' : 'Re-apply all rules'}
			</button>
			{#if editingId === null && !showAddForm}
				<button
					type="button"
					data-testid="show-new-rule-form"
					onclick={openAddForm}
					class="inline-flex items-center justify-center rounded-md bg-ctp-accent px-4 py-2 text-sm font-medium text-ctp-on-accent transition-colors hover:bg-ctp-accent-hover"
				>
					+ Add rule
				</button>
			{/if}
		</div>
	{/snippet}
</PageHeader>

<PageContent>

	{#if message}
		<div class="rounded-md border border-ctp-accent/40 bg-ctp-accent/10 px-4 py-3 text-sm text-ctp-accent">
			{message}
		</div>
	{/if}
	{#if error && editingId === null}
		<div class="rounded-md border border-ctp-red/40 bg-ctp-red/10 px-4 py-3 text-sm text-ctp-red">
			{error}
		</div>
	{/if}

	{#if editingId === null && showAddForm}
		{@render ruleForm('Add rule')}
	{/if}

	<div class="flex flex-col gap-3">
		{#each $importRules.filter((r) => !$pendingDeletes.has(pendingKey('rule', r.id))) as rule (rule.id)}
			{@const isEditing = editingId === rule.id}
			{@const result = ruleResults[rule.id]}
			<div
				data-testid="rule-card"
				data-rule-id={rule.id}
				class="rule-card rounded-lg border border-ctp-surface1 border-l-2 bg-ctp-base p-4 transition-colors {rule.enabled
					? 'border-l-ctp-accent bg-ctp-accent/5'
					: 'border-l-ctp-surface1 opacity-70'} {highlightedId === rule.id ? 'rule-card--flash' : ''}"
			>
				<div class="flex flex-wrap items-start justify-between gap-3">
					<div>
						<div class="flex flex-wrap items-center gap-2">
							<span class="rounded-full bg-ctp-surface1 px-2 py-0.5 text-xs text-ctp-subtext0">#{rule.priority}</span>
							<h2 class="text-base font-semibold text-ctp-text">{rule.name}</h2>
							<span class="rounded-full px-2 py-0.5 text-xs {rule.enabled ? 'bg-ctp-accent/15 text-ctp-accent' : 'bg-ctp-surface1 text-ctp-subtext0'}">
								{rule.enabled ? 'Enabled' : 'Disabled'}
							</span>
						</div>
						<p class="mt-2 text-sm text-ctp-overlay1">If {summary(rule) || 'no conditions'}.</p>
						<p class="mt-1 text-sm font-medium text-ctp-text">
							Then {rule.action === 'exclude' ? 'exclude from import' : `categorize as ${categoryName(rule.targetCategoryId)}`}.
						</p>
					</div>
					<div class="flex flex-wrap items-center gap-1">
						<button
							type="button"
							aria-label={rule.enabled ? 'Disable rule' : 'Enable rule'}
							title={rule.enabled ? 'Disable rule' : 'Enable rule'}
							onclick={() => toggleEnabled(rule)}
							class="rounded-md border border-ctp-surface2 p-2 transition-colors hover:bg-ctp-surface1 hover:text-ctp-text {rule.enabled ? 'text-ctp-accent' : 'text-ctp-subtext0'}"
						>
							<Power size={16} aria-hidden="true" />
						</button>
						<button
							type="button"
							aria-label={isEditing ? 'Close editor' : 'Edit rule'}
							title={isEditing ? 'Close editor' : 'Edit rule'}
							onclick={() => (isEditing ? cancelEdit() : startEdit(rule))}
							class="rounded-md border border-ctp-surface2 p-2 text-ctp-subtext0 transition-colors hover:bg-ctp-surface1 hover:text-ctp-text"
						>
							{#if isEditing}
								<X size={16} aria-hidden="true" />
							{:else}
								<Pencil size={16} aria-hidden="true" />
							{/if}
						</button>
						<button
							type="button"
							data-testid="rule-card-preview-btn"
							aria-label="Preview matches"
							title="Preview matches"
							disabled={cardPreviewingId === rule.id}
							onclick={() => handlePreviewCard(rule)}
							class="rounded-md border border-ctp-surface2 p-2 text-ctp-subtext0 transition-colors hover:bg-ctp-surface1 hover:text-ctp-text disabled:opacity-60"
						>
							<Eye size={16} aria-hidden="true" />
						</button>
						<button
							type="button"
							aria-label="Re-apply rule"
							title="Re-apply rule"
							disabled={applyingId === rule.id}
							onclick={() => applyRule(rule)}
							class="rounded-md border border-ctp-surface2 p-2 text-ctp-subtext0 transition-colors hover:bg-ctp-surface1 hover:text-ctp-text disabled:opacity-60"
						>
							<RefreshCw size={16} aria-hidden="true" class={applyingId === rule.id ? 'animate-spin' : ''} />
						</button>
						<button
							type="button"
							aria-label="Delete rule"
							title="Delete rule"
							onclick={() => removeRule(rule)}
							class="rounded-md p-2 text-ctp-red transition-colors hover:bg-ctp-red/10"
						>
							<Trash2 size={16} aria-hidden="true" />
						</button>
					</div>
				</div>

				{#if result}
					<div
						data-testid="rule-apply-result"
						class="mt-3 rounded-md border px-3 py-2 text-sm {result.kind === 'message'
							? 'border-ctp-accent/40 bg-ctp-accent/10 text-ctp-accent'
							: 'border-ctp-red/40 bg-ctp-red/10 text-ctp-red'}"
					>
						{result.text}
					</div>
				{/if}

				{#if cardPreviews[rule.id]}
					<div data-testid="rule-preview-results" class="mt-3 rounded-md border border-ctp-surface1 bg-ctp-mantle/40 p-3">
						{@render previewMatches(cardPreviews[rule.id], () => clearCardPreview(rule.id))}
					</div>
				{/if}

				{#if isEditing}
					<div class="mt-4">
						{@render ruleForm('Edit rule')}
					</div>
				{/if}
			</div>
		{/each}
	</div>
</PageContent>

<style>
	/* Brief, theme-aware "you are here" pulse on a card after its editor closes.
	   Drives box-shadow (a soft accent ring + glow) and a faint accent wash so it
	   reads even when the card is already in view. box-shadow/background-color are
	   animated rather than the border, so the existing enabled/disabled border-left
	   and `transition-colors` are left untouched. */
	@keyframes rule-card-flash {
		0% {
			box-shadow:
				0 0 0 0 color-mix(in srgb, var(--ctp-accent) 55%, transparent),
				0 0 18px 2px color-mix(in srgb, var(--ctp-accent) 40%, transparent);
			background-color: color-mix(in srgb, var(--ctp-accent) 14%, var(--ctp-base));
		}
		60% {
			box-shadow:
				0 0 0 3px color-mix(in srgb, var(--ctp-accent) 35%, transparent),
				0 0 16px 2px color-mix(in srgb, var(--ctp-accent) 22%, transparent);
		}
		100% {
			box-shadow:
				0 0 0 0 color-mix(in srgb, var(--ctp-accent) 0%, transparent),
				0 0 0 0 color-mix(in srgb, var(--ctp-accent) 0%, transparent);
			background-color: transparent;
		}
	}

	.rule-card--flash {
		animation: rule-card-flash 1.4s ease-out;
	}

	@media (prefers-reduced-motion: reduce) {
		.rule-card--flash {
			animation: none;
		}
	}
</style>

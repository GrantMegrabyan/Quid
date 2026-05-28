<script lang="ts">
	import { onMount } from 'svelte';
	import { categories, refreshCategories } from '$lib/stores/categories';
	import {
		addImportRule,
		applyAllImportRules,
		applyImportRule,
		deleteImportRule,
		editImportRule,
		importRules,
		refreshImportRules
	} from '$lib/stores/importRules';
	import { refreshSettings, settings } from '$lib/stores/settings';
	import { formatAmount } from '$lib/utils/money';
	import type {
		AmountMatchOp,
		ImportRule,
		ImportRuleCreate,
		NameMatchOp,
		RuleAction
	} from '$types';

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
		setDisplayName: ''
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

	function categoryName(id: string | null): string {
		return $categories.find((c) => c.id === id)?.name ?? 'Unknown category';
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
			setDisplayName: rule.setDisplayName ?? ''
		};
		error = '';
		message = '';
	}

	function cancelEdit(): void {
		editingId = null;
		form = emptyForm();
		error = '';
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
		const hasDay = form.matchDayOfMonth !== '';
		if (!hasName && !hasAmount && !hasDate && !hasDay) {
			throw new Error('Add at least one match condition.');
		}
		if (form.matchAmountOp === 'between' && !form.matchAmountValue2) {
			throw new Error('Between amount rules require a second amount.');
		}
		let dayOfMonth: number | null = null;
		if (hasDay) {
			const parsed = Number(form.matchDayOfMonth);
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
			matchAmountValue: hasAmount ? Number(form.matchAmountValue) : null,
			matchAmountValue2:
				hasAmount && form.matchAmountOp === 'between' ? Number(form.matchAmountValue2) : null,
			matchDateFrom: form.matchDateFrom || null,
			matchDateTo: form.matchDateTo || null,
			matchDayOfMonth: dayOfMonth,
			setDisplayName: form.setDisplayName.trim() || null
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

	async function removeRule(rule: ImportRule): Promise<void> {
		await deleteImportRule(rule.id);
		if (editingId === rule.id) cancelEdit();
		delete ruleResults[rule.id];
		ruleResults = { ...ruleResults };
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

		<div class="grid grid-cols-1 gap-3 md:grid-cols-3">
			<label class="flex flex-col gap-1 text-sm text-ctp-subtext0">
				<span>Name</span>
				<input bind:value={form.name} class="rounded-md border border-ctp-surface2 bg-ctp-base px-3 py-2 text-ctp-text focus:border-ctp-accent focus:outline-none" />
			</label>
			<label class="flex flex-col gap-1 text-sm text-ctp-subtext0">
				<span>Priority</span>
				<input bind:value={form.priority} type="number" class="rounded-md border border-ctp-surface2 bg-ctp-base px-3 py-2 text-ctp-text focus:border-ctp-accent focus:outline-none" />
			</label>
			<label class="flex items-center gap-2 pt-6 text-sm text-ctp-subtext0">
				<input bind:checked={form.enabled} type="checkbox" class="h-4 w-4 accent-ctp-accent" />
				Enabled
			</label>
		</div>

		<div class="mt-4 grid grid-cols-1 gap-3 md:grid-cols-3">
			<label class="flex flex-col gap-1 text-sm text-ctp-subtext0">
				<span>Action</span>
				<select bind:value={form.action} class="h-10 rounded-md border border-ctp-surface2 bg-ctp-base px-3 py-2 text-ctp-text focus:border-ctp-accent focus:outline-none">
					<option value="categorize">Categorize</option>
					<option value="exclude">Exclude</option>
				</select>
			</label>
			{#if form.action === 'categorize'}
				<label class="flex flex-col gap-1 text-sm text-ctp-subtext0 md:col-span-2">
					<span>Target category</span>
					<select bind:value={form.targetCategoryId} class="h-10 rounded-md border border-ctp-surface2 bg-ctp-base px-3 py-2 text-ctp-text focus:border-ctp-accent focus:outline-none">
						<option value="">Choose category</option>
						{#each $categories as category (category.id)}
							<option value={category.id}>{category.name}</option>
						{/each}
					</select>
				</label>
			{/if}
		</div>

		<div class="mt-4 grid grid-cols-1 gap-3 md:grid-cols-3">
			<label class="flex flex-col gap-1 text-sm text-ctp-subtext0">
				<span>Name match</span>
				<select bind:value={form.matchNameOp} class="h-10 rounded-md border border-ctp-surface2 bg-ctp-base px-3 py-2 text-ctp-text focus:border-ctp-accent focus:outline-none">
					<option value="">No name condition</option>
					<option value="contains">contains</option>
					<option value="equals">equals</option>
					<option value="starts_with">starts with</option>
					<option value="ends_with">ends with</option>
				</select>
			</label>
			<label class="flex flex-col gap-1 text-sm text-ctp-subtext0 md:col-span-2">
				<span>Name value</span>
				<input bind:value={form.matchNameValue} class="rounded-md border border-ctp-surface2 bg-ctp-base px-3 py-2 text-ctp-text focus:border-ctp-accent focus:outline-none" />
			</label>
		</div>

		<div class="mt-4 grid grid-cols-1 gap-3 md:grid-cols-3">
			<label class="flex flex-col gap-1 text-sm text-ctp-subtext0">
				<span>Amount match</span>
				<select bind:value={form.matchAmountOp} class="h-10 rounded-md border border-ctp-surface2 bg-ctp-base px-3 py-2 text-ctp-text focus:border-ctp-accent focus:outline-none">
					<option value="">No amount condition</option>
					<option value="gte">≥</option>
					<option value="lte">≤</option>
					<option value="eq">=</option>
					<option value="between">between</option>
				</select>
			</label>
			<label class="flex flex-col gap-1 text-sm text-ctp-subtext0">
				<span>Amount</span>
				<input bind:value={form.matchAmountValue} type="number" step="0.01" class="rounded-md border border-ctp-surface2 bg-ctp-base px-3 py-2 text-ctp-text focus:border-ctp-accent focus:outline-none" />
			</label>
			{#if form.matchAmountOp === 'between'}
				<label class="flex flex-col gap-1 text-sm text-ctp-subtext0">
					<span>Second amount</span>
					<input bind:value={form.matchAmountValue2} type="number" step="0.01" class="rounded-md border border-ctp-surface2 bg-ctp-base px-3 py-2 text-ctp-text focus:border-ctp-accent focus:outline-none" />
				</label>
			{/if}
		</div>

		<div class="mt-4 grid grid-cols-1 gap-3 md:grid-cols-3">
			<label class="flex flex-col gap-1 text-sm text-ctp-subtext0">
				<span>Date from</span>
				<input bind:value={form.matchDateFrom} type="date" class="rounded-md border border-ctp-surface2 bg-ctp-base px-3 py-2 text-ctp-text focus:border-ctp-accent focus:outline-none" />
			</label>
			<label class="flex flex-col gap-1 text-sm text-ctp-subtext0">
				<span>Date to</span>
				<input bind:value={form.matchDateTo} type="date" class="rounded-md border border-ctp-surface2 bg-ctp-base px-3 py-2 text-ctp-text focus:border-ctp-accent focus:outline-none" />
			</label>
			<label class="flex flex-col gap-1 text-sm text-ctp-subtext0">
				<span>Day of month <span class="text-ctp-overlay0">(1–31)</span></span>
				<input
					bind:value={form.matchDayOfMonth}
					type="number"
					min="1"
					max="31"
					step="1"
					inputmode="numeric"
					placeholder="e.g. 1 for monthly payment"
					class="rounded-md border border-ctp-surface2 bg-ctp-base px-3 py-2 text-ctp-text placeholder:text-ctp-overlay0 focus:border-ctp-accent focus:outline-none"
				/>
			</label>
		</div>

		<div class="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2">
			<label class="flex flex-col gap-1 text-sm text-ctp-subtext0 md:col-span-2">
				<span>Set display name <span class="text-ctp-overlay0">(optional)</span></span>
				<input bind:value={form.setDisplayName} type="text" maxlength="200" placeholder="Leave blank to keep merchant name" class="rounded-md border border-ctp-surface2 bg-ctp-base px-3 py-2 text-ctp-text placeholder:text-ctp-overlay0 focus:border-ctp-accent focus:outline-none" />
			</label>
		</div>

		<div class="mt-4">
			<button type="submit" disabled={saving} class="rounded-md bg-ctp-accent px-4 py-2 text-sm font-medium text-ctp-on-accent hover:bg-ctp-accent-hover disabled:opacity-60">
				{saving ? 'Saving…' : editingId ? 'Save rule' : 'Add rule'}
			</button>
		</div>

		{#if error}
			<p class="mt-3 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800 dark:border-red-900/60 dark:bg-red-950/40 dark:text-red-200">
				{error}
			</p>
		{/if}
	</form>
{/snippet}

<svelte:head><title>Import Rules</title></svelte:head>

<section class="flex flex-col gap-6">
	<header class="flex flex-wrap items-start justify-between gap-3">
		<div class="flex flex-col gap-1">
			<h1 class="text-2xl font-semibold tracking-tight text-ctp-text">
				Import rules
			</h1>
			<p class="text-sm text-ctp-overlay1">
				Exclude transfers, auto-categorize merchants, and re-apply rules to existing expenses.
			</p>
		</div>
		<button
			type="button"
			data-testid="reapply-all-rules-btn"
			disabled={applyingAll || $importRules.length === 0}
			onclick={applyAll}
			class="inline-flex items-center justify-center rounded-md border border-ctp-surface2 bg-ctp-base px-4 py-2 text-sm font-medium text-ctp-subtext0 transition-colors hover:bg-ctp-surface1 disabled:cursor-not-allowed disabled:opacity-60"
		>
			{applyingAll ? 'Reapplying…' : 'Re-apply all rules'}
		</button>
	</header>

	{#if message}
		<div class="rounded-md border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800 dark:border-emerald-900/60 dark:bg-emerald-950/40 dark:text-emerald-200">
			{message}
		</div>
	{/if}
	{#if error && editingId === null}
		<div class="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800 dark:border-red-900/60 dark:bg-red-950/40 dark:text-red-200">
			{error}
		</div>
	{/if}

	{#if editingId === null}
		{#if showAddForm}
			{@render ruleForm('Add rule')}
		{:else}
			<div>
				<button
					type="button"
					data-testid="show-new-rule-form"
					onclick={openAddForm}
					class="inline-flex items-center justify-center rounded-md bg-ctp-accent px-4 py-2 text-sm font-medium text-ctp-on-accent transition-colors hover:bg-ctp-accent-hover"
				>
					+ Add rule
				</button>
			</div>
		{/if}
	{/if}

	<div class="flex flex-col gap-3">
		{#each $importRules as rule (rule.id)}
			{@const isEditing = editingId === rule.id}
			{@const result = ruleResults[rule.id]}
			<div class="rounded-lg border border-ctp-surface1 bg-ctp-base p-4">
				<div class="flex flex-wrap items-start justify-between gap-3">
					<div>
						<div class="flex flex-wrap items-center gap-2">
							<span class="rounded-full bg-ctp-surface1 px-2 py-0.5 text-xs text-ctp-subtext0">#{rule.priority}</span>
							<h2 class="text-base font-semibold text-ctp-text">{rule.name}</h2>
							<span class="rounded-full px-2 py-0.5 text-xs {rule.enabled ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300' : 'bg-ctp-surface1 text-ctp-subtext0'}">
								{rule.enabled ? 'Enabled' : 'Disabled'}
							</span>
						</div>
						<p class="mt-2 text-sm text-ctp-overlay1">If {summary(rule) || 'no conditions'}.</p>
						<p class="mt-1 text-sm font-medium text-ctp-text">
							Then {rule.action === 'exclude' ? 'exclude from import' : `categorize as ${categoryName(rule.targetCategoryId)}`}.
						</p>
					</div>
					<div class="flex flex-wrap gap-2">
						<button type="button" class="rounded-md border border-ctp-surface2 px-3 py-1.5 text-sm text-ctp-subtext0 hover:bg-ctp-surface1" onclick={() => toggleEnabled(rule)}>{rule.enabled ? 'Disable' : 'Enable'}</button>
						<button type="button" class="rounded-md border border-ctp-surface2 px-3 py-1.5 text-sm text-ctp-subtext0 hover:bg-ctp-surface1" onclick={() => (isEditing ? cancelEdit() : startEdit(rule))}>{isEditing ? 'Close' : 'Edit'}</button>
						<button type="button" disabled={applyingId === rule.id} class="rounded-md border border-ctp-surface2 px-3 py-1.5 text-sm text-ctp-subtext0 hover:bg-ctp-surface1 disabled:opacity-60" onclick={() => applyRule(rule)}>{applyingId === rule.id ? 'Applying…' : 'Re-apply'}</button>
						<button type="button" class="rounded-md border border-red-200 px-3 py-1.5 text-sm text-red-700 dark:border-red-900 dark:text-red-300" onclick={() => removeRule(rule)}>Delete</button>
					</div>
				</div>

				{#if result}
					<div
						data-testid="rule-apply-result"
						class="mt-3 rounded-md border px-3 py-2 text-sm {result.kind === 'message'
							? 'border-emerald-200 bg-emerald-50 text-emerald-800 dark:border-emerald-900/60 dark:bg-emerald-950/40 dark:text-emerald-200'
							: 'border-red-200 bg-red-50 text-red-800 dark:border-red-900/60 dark:bg-red-950/40 dark:text-red-200'}"
					>
						{result.text}
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
</section>

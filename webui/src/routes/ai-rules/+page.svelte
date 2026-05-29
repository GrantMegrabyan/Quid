<script lang="ts">
	import { onMount } from 'svelte';
	import { addAiRule, aiRules, deleteAiRule, editAiRule, refreshAiRules } from '$lib/stores/aiRules';
	import type { AiRule, AiRuleCreate } from '$types';
	import { Pencil, Power, Trash2 } from '@lucide/svelte';

	type FormState = {
		text: string;
		enabled: boolean;
		priority: number;
	};

	const emptyForm = (): FormState => ({ text: '', enabled: true, priority: 100 });

	let form = $state<FormState>(emptyForm());
	let editingId: string | null = $state(null);
	let showAddForm = $state(false);
	let error = $state('');
	let message = $state('');
	let saving = $state(false);

	function startEdit(rule: AiRule): void {
		editingId = rule.id;
		form = { text: rule.text, enabled: rule.enabled, priority: rule.priority };
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

	function toPayload(): AiRuleCreate {
		const text = form.text.trim();
		if (!text) throw new Error('Rule text is required.');
		return { text, enabled: form.enabled, priority: Number(form.priority) };
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
				await editAiRule(editingId, payload);
				message = 'AI rule saved.';
				cancelEdit();
			} else {
				await addAiRule(payload);
				message = 'AI rule added.';
				closeAddForm();
			}
		} catch (err) {
			error = err instanceof Error ? err.message : 'Could not save AI rule.';
		} finally {
			saving = false;
		}
	}

	async function toggleEnabled(rule: AiRule): Promise<void> {
		await editAiRule(rule.id, { enabled: !rule.enabled });
	}

	async function removeRule(rule: AiRule): Promise<void> {
		await deleteAiRule(rule.id);
		if (editingId === rule.id) cancelEdit();
	}

	onMount(() => {
		void refreshAiRules();
	});
</script>

<svelte:head><title>AI Rules</title></svelte:head>

<section class="flex flex-col gap-6">
	<header class="flex flex-wrap items-start justify-between gap-3">
		<div class="flex flex-col gap-1">
			<h1 class="text-2xl font-semibold tracking-tight text-ctp-text">AI Rules</h1>
			<p class="text-sm text-ctp-overlay1">
				Plain-language instructions that are sent to AI categorisation during CSV import.
			</p>
		</div>
		{#if !editingId && !showAddForm}
			<button
				type="button"
				data-testid="show-new-ai-rule-form"
				onclick={openAddForm}
				class="inline-flex items-center justify-center rounded-md bg-ctp-accent px-4 py-2 text-sm font-medium text-ctp-on-accent transition-colors hover:bg-ctp-accent-hover"
			>
				+ Add AI rule
			</button>
		{/if}
	</header>

	{#if message}
		<div class="rounded-md border border-ctp-accent/40 bg-ctp-accent/10 px-4 py-3 text-sm text-ctp-accent">
			{message}
		</div>
	{/if}
	{#if error}
		<div class="rounded-md border border-ctp-red/40 bg-ctp-red/10 px-4 py-3 text-sm text-ctp-red">
			{error}
		</div>
	{/if}

	{#if editingId || showAddForm}
	<form onsubmit={saveRule} class="rounded-lg border border-ctp-surface1 bg-ctp-base p-4">
		<div class="mb-4 flex items-center justify-between gap-3">
			<h2 class="text-lg font-medium text-ctp-text">{editingId ? 'Edit AI rule' : 'Add AI rule'}</h2>
			{#if editingId}
				<button type="button" class="text-sm text-ctp-blue underline" onclick={cancelEdit}>Cancel edit</button>
			{:else}
				<button type="button" class="text-sm text-ctp-blue underline" onclick={closeAddForm}>Cancel</button>
			{/if}
		</div>

		<label class="block text-sm font-medium text-ctp-subtext0">
			Instruction
			<textarea
				bind:value={form.text}
				rows="4"
				placeholder="Exclude transfers. If a purchase is fully refunded, exclude both rows."
				class="mt-1 w-full rounded-md border border-ctp-surface2 bg-ctp-base px-3 py-2 text-sm text-ctp-text placeholder:text-ctp-overlay0 focus:border-ctp-accent focus:outline-none"
			></textarea>
		</label>

		<div class="mt-4 grid gap-4 sm:grid-cols-2">
			<label class="text-sm font-medium text-ctp-subtext0">
				Priority
				<input
					type="number"
					bind:value={form.priority}
					class="mt-1 w-full rounded-md border border-ctp-surface2 bg-ctp-base px-3 py-2 text-sm text-ctp-text focus:border-ctp-accent focus:outline-none"
				/>
			</label>
			<label class="flex items-center gap-2 text-sm font-medium text-ctp-subtext0 sm:mt-7">
				<input type="checkbox" bind:checked={form.enabled} class="accent-ctp-accent" />
				Enabled
			</label>
		</div>

		<div class="mt-5 flex justify-end">
			<button
				type="submit"
				disabled={saving}
				class="rounded-md bg-ctp-accent px-4 py-2 text-sm font-medium text-ctp-on-accent hover:bg-ctp-accent-hover disabled:opacity-60"
			>
				{saving ? 'Saving…' : editingId ? 'Save AI rule' : 'Add AI rule'}
			</button>
		</div>
	</form>
	{/if}

	{#if $aiRules.length === 0}
		<p class="rounded-lg border border-dashed border-ctp-surface2 px-6 py-16 text-center text-sm text-ctp-overlay1">
			No AI rules yet.
		</p>
	{:else}
		<div class="flex flex-col gap-3">
			{#each $aiRules as rule (rule.id)}
				<div
					class="rounded-lg border border-ctp-surface1 border-l-2 bg-ctp-base p-4 transition-colors {rule.enabled
						? 'border-l-ctp-accent bg-ctp-accent/5'
						: 'border-l-ctp-surface1 opacity-70'}"
				>
					<div class="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
						<div class="min-w-0 flex-1">
							<div class="mb-1 flex flex-wrap items-center gap-2">
								<span class="rounded-full bg-ctp-surface1 px-2 py-0.5 text-xs text-ctp-subtext0">
									priority {rule.priority}
								</span>
								<span class="rounded-full px-2 py-0.5 text-xs {rule.enabled ? 'bg-ctp-accent/15 text-ctp-accent' : 'bg-ctp-surface1 text-ctp-subtext0'}">
									{rule.enabled ? 'enabled' : 'disabled'}
								</span>
							</div>
							<p class="whitespace-pre-wrap text-sm leading-6 text-ctp-text">{rule.text}</p>
						</div>
						<div class="flex shrink-0 flex-wrap items-center gap-1">
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
								aria-label="Edit rule"
								title="Edit rule"
								onclick={() => startEdit(rule)}
								class="rounded-md border border-ctp-surface2 p-2 text-ctp-subtext0 transition-colors hover:bg-ctp-surface1 hover:text-ctp-text"
							>
								<Pencil size={16} aria-hidden="true" />
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
				</div>
			{/each}
		</div>
	{/if}
</section>

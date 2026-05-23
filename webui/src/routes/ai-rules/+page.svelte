<script lang="ts">
	import { onMount } from 'svelte';
	import { addAiRule, aiRules, deleteAiRule, editAiRule, refreshAiRules } from '$lib/stores/aiRules';
	import type { AiRule, AiRuleCreate } from '$types';

	type FormState = {
		text: string;
		enabled: boolean;
		priority: number;
	};

	const emptyForm = (): FormState => ({ text: '', enabled: true, priority: 100 });

	let form = $state<FormState>(emptyForm());
	let editingId: string | null = $state(null);
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
			} else {
				await addAiRule(payload);
				message = 'AI rule added.';
			}
			cancelEdit();
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
	<header class="flex flex-col gap-1">
		<h1 class="text-2xl font-semibold tracking-tight text-gray-900 dark:text-gray-50">AI Rules</h1>
		<p class="text-sm text-gray-500 dark:text-gray-400">
			Plain-language instructions that are sent to AI categorisation during CSV import.
		</p>
	</header>

	{#if message}
		<div class="rounded-md border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800 dark:border-emerald-900/60 dark:bg-emerald-950/40 dark:text-emerald-200">
			{message}
		</div>
	{/if}
	{#if error}
		<div class="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800 dark:border-red-900/60 dark:bg-red-950/40 dark:text-red-200">
			{error}
		</div>
	{/if}

	<form onsubmit={saveRule} class="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-800 dark:bg-[#111114]">
		<div class="mb-4 flex items-center justify-between gap-3">
			<h2 class="text-lg font-medium">{editingId ? 'Edit AI rule' : 'Add AI rule'}</h2>
			{#if editingId}
				<button type="button" class="text-sm underline" onclick={cancelEdit}>Cancel edit</button>
			{/if}
		</div>

		<label class="block text-sm font-medium">
			Instruction
			<textarea
				bind:value={form.text}
				rows="4"
				placeholder="Exclude transfers. If a purchase is fully refunded, exclude both rows."
				class="mt-1 w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm dark:border-gray-700 dark:bg-[#0b0b0c]"
			></textarea>
		</label>

		<div class="mt-4 grid gap-4 sm:grid-cols-2">
			<label class="text-sm font-medium">
				Priority
				<input
					type="number"
					bind:value={form.priority}
					class="mt-1 w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm dark:border-gray-700 dark:bg-[#0b0b0c]"
				/>
			</label>
			<label class="flex items-center gap-2 text-sm font-medium sm:mt-7">
				<input type="checkbox" bind:checked={form.enabled} />
				Enabled
			</label>
		</div>

		<div class="mt-5 flex justify-end">
			<button
				type="submit"
				disabled={saving}
				class="rounded-md bg-gray-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-60 dark:bg-gray-100 dark:text-gray-900"
			>
				{saving ? 'Saving…' : editingId ? 'Save AI rule' : 'Add AI rule'}
			</button>
		</div>
	</form>

	<div class="rounded-lg border border-gray-200 bg-white dark:border-gray-800 dark:bg-[#111114]">
		<div class="border-b border-gray-200 px-4 py-3 dark:border-gray-800">
			<h2 class="text-lg font-medium">Current AI rules</h2>
		</div>

		{#if $aiRules.length === 0}
			<p class="px-4 py-6 text-sm text-gray-500 dark:text-gray-400">No AI rules yet.</p>
		{:else}
			<ul class="divide-y divide-gray-100 dark:divide-gray-900">
				{#each $aiRules as rule (rule.id)}
					<li class="flex flex-col gap-3 px-4 py-4 sm:flex-row sm:items-start sm:justify-between">
						<div class="min-w-0 flex-1">
							<div class="mb-1 flex flex-wrap items-center gap-2">
								<span class="rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-600 dark:bg-gray-800 dark:text-gray-300">
									priority {rule.priority}
								</span>
								<span class="rounded-full px-2 py-0.5 text-xs {rule.enabled ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300' : 'bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400'}">
									{rule.enabled ? 'enabled' : 'disabled'}
								</span>
							</div>
							<p class="whitespace-pre-wrap text-sm leading-6 text-gray-800 dark:text-gray-200">{rule.text}</p>
						</div>
						<div class="flex shrink-0 flex-wrap gap-2 text-sm">
							<button type="button" class="rounded-md border px-3 py-1.5" onclick={() => toggleEnabled(rule)}>
								{rule.enabled ? 'Disable' : 'Enable'}
							</button>
							<button type="button" class="rounded-md border px-3 py-1.5" onclick={() => startEdit(rule)}>Edit</button>
							<button type="button" class="rounded-md border border-red-200 px-3 py-1.5 text-red-700 dark:border-red-900/60 dark:text-red-300" onclick={() => removeRule(rule)}>
								Delete
							</button>
						</div>
					</li>
				{/each}
			</ul>
		{/if}
	</div>
</section>

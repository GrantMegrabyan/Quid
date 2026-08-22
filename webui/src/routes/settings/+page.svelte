<script lang="ts">
	import PageHeader from '$components/shell/PageHeader.svelte';
	import PageContent from '$components/shell/PageContent.svelte';
	import { onMount } from 'svelte';
	import { refreshSettings, settings, updateSettings } from '$lib/stores/settings';
	import { THEMES, theme } from '$lib/stores/theme';

	const SUPPORTED_CURRENCIES = ['GBP', 'USD', 'EUR', 'CAD', 'AUD', 'JPY'] as const;
	const CATEGORISATION_MODELS = [
		{ value: 'google/gemini-2.5-flash', label: 'Gemini 2.5 Flash (recommended)' },
		{ value: 'openai/gpt-5.4-mini', label: 'GPT-5.4 mini' },
		{ value: 'deepseek/deepseek-v4-pro', label: 'DeepSeek V4 Pro' },
		{ value: 'openai/gpt-5.4-nano', label: 'GPT-5.4 nano' }
	] as const;

	let currency = $state('GBP');
	let categorizeModel = $state('google/gemini-2.5-flash');
	let showImportanceBadge = $state(true);
	let aiCategorizeEnabled = $state(true);
	let aiShortNamesEnabled = $state(true);
	let saving = $state(false);
	let message = $state('');
	let error = $state('');

	$effect(() => {
		currency = $settings.currency;
		categorizeModel = $settings.categorizeModel;
		showImportanceBadge = $settings.showImportanceBadge;
		aiCategorizeEnabled = $settings.aiCategorizeEnabled;
		aiShortNamesEnabled = $settings.aiShortNamesEnabled;
	});

	onMount(() => {
		void refreshSettings();
	});

	async function save(): Promise<void> {
		saving = true;
		message = '';
		error = '';
		try {
			await updateSettings({
				currency,
				categorizeModel,
				showImportanceBadge,
				aiCategorizeEnabled,
				aiShortNamesEnabled
			});
			message = 'Settings saved.';
		} catch (cause) {
			error = cause instanceof Error ? cause.message : 'Failed to save settings.';
		} finally {
			saving = false;
		}
	}
</script>

<svelte:head>
	<title>Settings</title>
</svelte:head>

<PageHeader heading="Settings" text="Choose how amounts and transaction details appear across Quid."></PageHeader>

<PageContent class="mx-auto w-full max-w-2xl">

	<form
		class="flex flex-col gap-5 card rounded-lg border border-ctp-surface1 bg-ctp-base p-6"
		onsubmit={(event) => {
			event.preventDefault();
			void save();
		}}
	>
		<!-- Appearance is a device preference, not an app setting: it applies
		     immediately and is stored locally, so it sits outside the save flow. -->
		<div class="flex flex-col gap-1.5">
			<span class="text-sm font-medium text-ctp-subtext0">Appearance</span>
			<div
				role="radiogroup"
				aria-label="Appearance"
				class="inline-flex w-fit items-center gap-1 rounded-md border border-ctp-surface2 bg-ctp-mantle p-1"
			>
				{#each THEMES as option (option.id)}
					<button
						type="button"
						role="radio"
						aria-checked={$theme === option.id}
						data-testid="settings-theme-{option.id}"
						onclick={() => theme.setTheme(option.id)}
						class="rounded px-3 py-1.5 text-sm font-medium transition-colors {$theme === option.id
							? 'bg-ctp-accent text-ctp-on-accent'
							: 'text-ctp-subtext0 hover:bg-ctp-surface0 hover:text-ctp-text'}"
					>
						{option.label}
					</button>
				{/each}
			</div>
			<span class="text-xs text-ctp-overlay1">
				Applies to this browser only — it is not part of your saved settings.
			</span>
		</div>

		<label class="flex flex-col gap-1.5">
			<span class="text-sm font-medium text-ctp-subtext0">Currency</span>
			<select
				bind:value={currency}
				data-testid="settings-currency-select"
				class="field field-select"
			>
				{#each SUPPORTED_CURRENCIES as code}
					<option value={code}>{code}</option>
				{/each}
			</select>
		</label>

		<label class="flex flex-col gap-1.5">
			<span class="text-sm font-medium text-ctp-subtext0">AI categorisation model</span>
			<input
				type="text"
				bind:value={categorizeModel}
				list="categorisation-model-options"
				placeholder="google/gemini-2.5-flash"
				autocomplete="off"
				spellcheck="false"
				data-testid="settings-categorize-model-input"
				class="field"
			/>
			<datalist id="categorisation-model-options">
				{#each CATEGORISATION_MODELS as model}
					<option value={model.value}>{model.label}</option>
				{/each}
			</datalist>
			<span class="text-sm text-ctp-overlay1">
				Any OpenRouter model id used to categorise transactions during import (e.g.
				<code class="rounded bg-ctp-surface0 px-1 py-0.5 text-xs">google/gemini-2.5-flash</code>).
				Suggestions are offered, but you can enter any model.
			</span>
		</label>

		<label class="flex items-start gap-3 rounded-lg border border-ctp-surface1 bg-ctp-surface0/40 p-4 transition-colors hover:border-ctp-surface2">
			<input
				type="checkbox"
				bind:checked={showImportanceBadge}
				data-testid="settings-importance-toggle"
				class="mt-1 h-4 w-4 accent-ctp-accent"
			/>
			<span>
				<span class="block text-sm font-medium text-ctp-text">
					Show importance badges
				</span>
				<span class="mt-1 block text-sm text-ctp-overlay1">
					Display Essential, Important, and Discretionary labels in transaction lists.
				</span>
			</span>
		</label>

		<label class="flex items-start gap-3 rounded-lg border border-ctp-surface1 bg-ctp-surface0/40 p-4 transition-colors hover:border-ctp-surface2">
			<input
				type="checkbox"
				bind:checked={aiCategorizeEnabled}
				data-testid="settings-ai-categorize-toggle"
				class="mt-1 h-4 w-4 accent-ctp-accent"
			/>
			<span>
				<span class="block text-sm font-medium text-ctp-text">
					AI categorisation
				</span>
				<span class="mt-1 block text-sm text-ctp-overlay1">
					Use AI to categorise transactions during CSV import.
				</span>
			</span>
		</label>

		<label class="flex items-start gap-3 rounded-lg border border-ctp-surface1 bg-ctp-surface0/40 p-4 transition-colors hover:border-ctp-surface2">
			<input
				type="checkbox"
				bind:checked={aiShortNamesEnabled}
				data-testid="settings-ai-short-names-toggle"
				class="mt-1 h-4 w-4 accent-ctp-accent"
			/>
			<span>
				<span class="block text-sm font-medium text-ctp-text">
					AI Amazon short names
				</span>
				<span class="mt-1 block text-sm text-ctp-overlay1">
					Generate a brief description of each Amazon order during import.
				</span>
			</span>
		</label>

		<div class="flex items-center justify-between gap-3">
			<div class="text-sm">
				{#if message}
					<p data-testid="settings-message" class="text-emerald-600 dark:text-emerald-400">{message}</p>
				{/if}
				{#if error}
					<p data-testid="settings-error" class="text-red-600 dark:text-red-400">{error}</p>
				{/if}
			</div>
			<button
				type="submit"
				data-testid="settings-save-button"
				disabled={saving}
				class="rounded-md bg-ctp-accent px-4 py-2 text-sm font-medium text-ctp-on-accent transition-colors hover:bg-ctp-accent-hover disabled:opacity-60"
			>
				{saving ? 'Saving…' : 'Save settings'}
			</button>
		</div>
	</form>
</PageContent>

<script lang="ts">
	import { onMount } from 'svelte';
	import { refreshSettings, settings, updateSettings } from '$lib/stores/settings';

	const SUPPORTED_CURRENCIES = ['GBP', 'USD', 'EUR', 'CAD', 'AUD', 'JPY'] as const;

	let currency = $state('GBP');
	let showImportanceBadge = $state(true);
	let saving = $state(false);
	let message = $state('');
	let error = $state('');

	$effect(() => {
		currency = $settings.currency;
		showImportanceBadge = $settings.showImportanceBadge;
	});

	onMount(() => {
		void refreshSettings();
	});

	async function save(): Promise<void> {
		saving = true;
		message = '';
		error = '';
		try {
			await updateSettings({ currency, showImportanceBadge });
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

<section class="mx-auto flex max-w-2xl flex-col gap-6">
	<header>
		<h1 class="text-2xl font-semibold tracking-tight text-gray-900 dark:text-gray-50">Settings</h1>
		<p class="mt-1 text-sm text-gray-500 dark:text-gray-400">
			Choose how amounts and transaction details appear across Quid.
		</p>
	</header>

	<form
		class="flex flex-col gap-5 rounded-lg border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-[#111114]"
		onsubmit={(event) => {
			event.preventDefault();
			void save();
		}}
	>
		<label class="flex flex-col gap-1.5">
			<span class="text-sm font-medium text-gray-700 dark:text-gray-300">Currency</span>
			<select
				bind:value={currency}
				data-testid="settings-currency-select"
				class="rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 focus:border-gray-900 focus:outline-none dark:border-gray-700 dark:bg-[#0b0b0c] dark:text-gray-100 dark:focus:border-gray-100"
			>
				{#each SUPPORTED_CURRENCIES as code}
					<option value={code}>{code}</option>
				{/each}
			</select>
		</label>

		<label class="flex items-start gap-3 rounded-md border border-gray-200 p-3 dark:border-gray-800">
			<input
				type="checkbox"
				bind:checked={showImportanceBadge}
				data-testid="settings-importance-toggle"
				class="mt-1 h-4 w-4 accent-gray-900 dark:accent-gray-100"
			/>
			<span>
				<span class="block text-sm font-medium text-gray-800 dark:text-gray-100">
					Show importance badges
				</span>
				<span class="mt-1 block text-sm text-gray-500 dark:text-gray-400">
					Display Essential, Important, and Discretionary labels in transaction lists.
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
				class="rounded-md bg-gray-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-gray-700 disabled:opacity-60 dark:bg-gray-100 dark:text-gray-900 dark:hover:bg-gray-300"
			>
				{saving ? 'Saving…' : 'Save settings'}
			</button>
		</div>
	</form>
</section>

<script lang="ts">
	import { onMount } from 'svelte';
	import { refreshSettings, settings, updateSettings } from '$lib/stores/settings';
	import { theme, THEMES, type ThemeId } from '$lib/stores/theme';

	const SUPPORTED_CURRENCIES = ['GBP', 'USD', 'EUR', 'CAD', 'AUD', 'JPY'] as const;

	let currency = $state('GBP');
	let showImportanceBadge = $state(true);
	let saving = $state(false);
	let message = $state('');
	let error = $state('');
	let currentTheme = $state<ThemeId>('default-dark');

	$effect(() => {
		currency = $settings.currency;
		showImportanceBadge = $settings.showImportanceBadge;
	});

	onMount(() => {
		void refreshSettings();
		currentTheme = $theme;
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

	function onThemeChange(event: Event) {
		const select = event.target as HTMLSelectElement;
		const id = select.value as ThemeId;
		theme.setTheme(id);
		currentTheme = id;
	}
</script>

<svelte:head>
	<title>Settings</title>
</svelte:head>

<section class="mx-auto flex max-w-2xl flex-col gap-6">
	<header>
		<h1 class="text-2xl font-semibold tracking-tight text-ctp-text">Settings</h1>
		<p class="mt-1 text-sm text-ctp-overlay1">
			Choose how amounts and transaction details appear across Quid.
		</p>
	</header>

	<form
		class="flex flex-col gap-5 rounded-lg border border-ctp-surface1 bg-ctp-base p-5"
		onsubmit={(event) => {
			event.preventDefault();
			void save();
		}}
	>
		<label class="flex flex-col gap-1.5">
			<span class="text-sm font-medium text-ctp-subtext0">Theme</span>
			<select
				value={currentTheme}
				onchange={onThemeChange}
				class="rounded-md border border-ctp-surface1 bg-ctp-base px-3 py-2 text-sm text-ctp-text focus:border-ctp-accent focus:outline-none"
			>
				{#each THEMES as t}
					<option value={t.id}>{t.label}</option>
				{/each}
			</select>
		</label>

		<label class="flex flex-col gap-1.5">
			<span class="text-sm font-medium text-ctp-subtext0">Currency</span>
			<select
				bind:value={currency}
				data-testid="settings-currency-select"
				class="rounded-md border border-ctp-surface1 bg-ctp-base px-3 py-2 text-sm text-ctp-text focus:border-ctp-accent focus:outline-none"
			>
				{#each SUPPORTED_CURRENCIES as code}
					<option value={code}>{code}</option>
				{/each}
			</select>
		</label>

		<label class="flex items-start gap-3 rounded-md border border-ctp-surface1 p-3">
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
</section>

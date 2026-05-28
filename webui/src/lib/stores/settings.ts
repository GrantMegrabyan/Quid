import { writable } from 'svelte/store';
import { appSettingsRepository } from '$lib/repos';
import type { AppSettings, AppSettingsUpdate } from '$types';

const DEFAULTS: AppSettings = {
	currency: 'GBP',
	showImportanceBadge: true,
	aiCategorizeEnabled: true,
	aiShortNamesEnabled: true,
	updatedAt: '1970-01-01T00:00:00Z'
};

export const settings = writable<AppSettings>({ ...DEFAULTS });

export async function refreshSettings(): Promise<void> {
	const next = await appSettingsRepository.get();
	settings.set(next);
}

export async function updateSettings(patch: AppSettingsUpdate): Promise<void> {
	const next = await appSettingsRepository.update(patch);
	settings.set(next);
}

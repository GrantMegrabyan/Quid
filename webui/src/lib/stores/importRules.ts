import { writable } from 'svelte/store';
import { importRuleRepository } from '$lib/repos';
import type {
	ImportRule,
	ImportRuleApplyResult,
	ImportRuleCreate,
	ImportRulePreviewRequest,
	ImportRulePreviewResult,
	ImportRuleUpdate
} from '$types';
import { refreshExpenses } from './expenses.js';

export const importRules = writable<ImportRule[]>([]);

export async function refreshImportRules(): Promise<void> {
	importRules.set(await importRuleRepository.list());
}

export async function addImportRule(input: ImportRuleCreate): Promise<void> {
	await importRuleRepository.create(input);
	await refreshImportRules();
}

export async function editImportRule(id: string, patch: ImportRuleUpdate): Promise<void> {
	await importRuleRepository.update(id, patch);
	await refreshImportRules();
}

export async function deleteImportRule(id: string): Promise<void> {
	await importRuleRepository.delete(id);
	await refreshImportRules();
}

export async function applyImportRule(id: string): Promise<ImportRuleApplyResult> {
	const result = await importRuleRepository.apply(id);
	if (result.updated > 0 || result.deleted > 0) {
		await refreshExpenses();
	}
	return result;
}

export async function applyAllImportRules(): Promise<ImportRuleApplyResult> {
	const result = await importRuleRepository.applyAll();
	if (result.updated > 0 || result.deleted > 0) {
		await refreshExpenses();
	}
	return result;
}

export async function previewImportRule(
	input: ImportRulePreviewRequest
): Promise<ImportRulePreviewResult> {
	return importRuleRepository.preview(input);
}

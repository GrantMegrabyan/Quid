import { writable } from 'svelte/store';
import { aiRuleRepository } from '$lib/repos';
import type { AiRule, AiRuleCreate, AiRuleUpdate } from '$types';

export const aiRules = writable<AiRule[]>([]);

export async function refreshAiRules(): Promise<void> {
	aiRules.set(await aiRuleRepository.list());
}

export async function addAiRule(input: AiRuleCreate): Promise<void> {
	await aiRuleRepository.create(input);
	await refreshAiRules();
}

export async function editAiRule(id: string, patch: AiRuleUpdate): Promise<void> {
	await aiRuleRepository.update(id, patch);
	await refreshAiRules();
}

export async function deleteAiRule(id: string): Promise<void> {
	await aiRuleRepository.delete(id);
	await refreshAiRules();
}

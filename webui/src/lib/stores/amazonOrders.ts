import { writable } from 'svelte/store';
import { amazonOrderRepository } from '$lib/repos';
import type { AmazonImportResult, AmazonMatchAllResult, AmazonOrder, Expense } from '$types';
import { refreshExpenses } from './expenses.js';

export const amazonOrders = writable<AmazonOrder[]>([]);

export async function refreshAmazonOrders(): Promise<void> {
	const rows = await amazonOrderRepository.list();
	amazonOrders.set(rows);
}

export async function importAmazonCsv(files: File[]): Promise<AmazonImportResult> {
	const result = await amazonOrderRepository.importCsv(files);
	await refreshAmazonOrders();
	await refreshExpenses();
	return result;
}

export async function matchAllAmazonOrders(): Promise<AmazonMatchAllResult> {
	const result = await amazonOrderRepository.matchAll();
	await refreshAmazonOrders();
	await refreshExpenses();
	return result;
}

export async function suggestedAmazonMatches(orderId: string): Promise<Expense[]> {
	return amazonOrderRepository.suggestedMatches(orderId);
}

export async function linkAmazonOrder(orderId: string, expenseId: string): Promise<void> {
	await amazonOrderRepository.link(orderId, expenseId);
	await refreshAmazonOrders();
	await refreshExpenses();
}

export async function unlinkAmazonOrder(orderId: string, expenseId: string): Promise<void> {
	await amazonOrderRepository.unlink(orderId, expenseId);
	await refreshAmazonOrders();
	await refreshExpenses();
}

export async function updateAmazonShortName(
	orderId: string,
	shortName: string
): Promise<void> {
	await amazonOrderRepository.updateShortName(orderId, shortName);
	await refreshAmazonOrders();
	await refreshExpenses();
}

export async function deleteAmazonOrder(orderId: string): Promise<void> {
	await amazonOrderRepository.delete(orderId);
	await refreshAmazonOrders();
	await refreshExpenses();
}

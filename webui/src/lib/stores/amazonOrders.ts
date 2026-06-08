import { get, writable } from 'svelte/store';
import { amazonOrderRepository } from '$lib/repos';
import type {
	AmazonExportRequest,
	AmazonImportResult,
	AmazonMatchAllResult,
	AmazonOrder,
	AmazonOrderListQuery,
	AmazonRecategorizeConfirmRow,
	AmazonRecategorizeConfirmResult,
	AmazonRecategorizePreviewResult,
	Expense
} from '$types';
import { refreshCategories } from './categories.js';
import { refreshExpenses } from './expenses.js';

export const AMAZON_ORDERS_PAGE_SIZE = 25;

/** The current page of orders for the active filters. */
export const amazonOrders = writable<AmazonOrder[]>([]);
/** Total orders matching the active filters (across all pages). */
export const amazonOrdersTotal = writable<number>(0);
/** Whether a list fetch is in flight (for spinners / disabling controls). */
export const amazonOrdersLoading = writable<boolean>(false);

/**
 * Active server-driven filters + pagination. The page mutates this via
 * `setAmazonOrderFilters` / `setAmazonOrderPage`; both re-fetch. Mutations
 * elsewhere call `refreshAmazonOrders()`, which re-fetches the SAME window so
 * the visible page stays put.
 */
export const amazonOrderQuery = writable<AmazonOrderListQuery>({
	limit: AMAZON_ORDERS_PAGE_SIZE,
	offset: 0
});

export async function refreshAmazonOrders(): Promise<void> {
	amazonOrdersLoading.set(true);
	try {
		let query = get(amazonOrderQuery);
		let result = await amazonOrderRepository.list(query);
		// A delete (or filter change) can leave us past the last page (empty
		// items but matches exist). Step back to the last non-empty page so the
		// user never lands on a blank page.
		const limit = query.limit ?? AMAZON_ORDERS_PAGE_SIZE;
		if (result.items.length === 0 && result.total > 0 && (query.offset ?? 0) > 0) {
			const lastPage = Math.max(0, Math.ceil(result.total / limit) - 1);
			query = { ...query, offset: lastPage * limit };
			amazonOrderQuery.set(query);
			result = await amazonOrderRepository.list(query);
		}
		amazonOrders.set(result.items);
		amazonOrdersTotal.set(result.total);
	} finally {
		amazonOrdersLoading.set(false);
	}
}

/**
 * Replace the active filters (linked / category / search) and reset to the
 * first page, then re-fetch.
 */
export async function setAmazonOrderFilters(
	filters: Pick<AmazonOrderListQuery, 'linked' | 'categoryId' | 'search'>
): Promise<void> {
	amazonOrderQuery.update((q) => ({
		limit: q.limit ?? AMAZON_ORDERS_PAGE_SIZE,
		offset: 0,
		linked: filters.linked,
		categoryId: filters.categoryId,
		search: filters.search
	}));
	await refreshAmazonOrders();
}

/** Jump to a page (0-indexed) and re-fetch. */
export async function setAmazonOrderPage(page: number): Promise<void> {
	amazonOrderQuery.update((q) => {
		const limit = q.limit ?? AMAZON_ORDERS_PAGE_SIZE;
		return { ...q, limit, offset: Math.max(0, page) * limit };
	});
	await refreshAmazonOrders();
}

export async function importAmazonCsv(files: File[]): Promise<AmazonImportResult> {
	const result = await amazonOrderRepository.importCsv(files);
	await refreshAmazonOrders();
	await refreshExpenses();
	return result;
}

export async function importAmazonExport(
	payload: AmazonExportRequest
): Promise<AmazonImportResult> {
	const result = await amazonOrderRepository.importExport(payload);
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

export async function updateAmazonOrderCategory(
	orderId: string,
	categoryId: string | null
): Promise<void> {
	await amazonOrderRepository.updateCategory(orderId, categoryId);
	await refreshAmazonOrders();
	await refreshExpenses();
}

export async function previewRecategorizeAmazon(): Promise<AmazonRecategorizePreviewResult> {
	return amazonOrderRepository.recategorizePreview();
}

export async function confirmRecategorizeAmazon(
	rows: AmazonRecategorizeConfirmRow[]
): Promise<AmazonRecategorizeConfirmResult> {
	const result = await amazonOrderRepository.recategorizeConfirm(rows);
	await refreshAmazonOrders();
	await refreshExpenses();
	await refreshCategories();
	return result;
}

export async function deleteAmazonOrder(orderId: string): Promise<void> {
	await amazonOrderRepository.delete(orderId);
	await refreshAmazonOrders();
	await refreshExpenses();
}

import { writable } from 'svelte/store';
import { browser } from '$app/environment';

/**
 * Global, app-wide transient feedback: success / error toasts and Gmail-style
 * "undo" toasts for destructive actions. A single {@link ToastHost} mounted in
 * the root layout renders the stack; any page calls {@link notify} or
 * {@link softDelete} instead of hand-rolling a per-page banner.
 */

export type ToastVariant = 'success' | 'error' | 'undo';

export interface Toast {
	id: string;
	variant: ToastVariant;
	message: string;
	/**
	 * Lifetime in ms. Drives the shrinking progress bar and, for non-undo toasts,
	 * the auto-dismiss timer. For undo toasts it is the length of the undo window.
	 */
	durationMs: number;
}

const list = writable<Toast[]>([]);
export const toasts = { subscribe: list.subscribe };

/**
 * Namespaced keys (`kind:id`) of records currently inside a delete-undo window.
 * Deletable lists filter these out so an optimistically-removed row stays hidden
 * across store refreshes until the delete commits or is undone. Mutated
 * immutably so `$pendingDeletes` subscribers re-render.
 */
export const pendingDeletes = writable<Set<string>>(new Set());

export function pendingKey(kind: string, id: string): string {
	return `${kind}:${id}`;
}

const SUCCESS_MS = 4500;
const ERROR_MS = 8000;
const UNDO_MS = 6000;

let seq = 0;
function nextId(): string {
	seq += 1;
	return `toast-${seq}`;
}

function push(toast: Toast): void {
	list.update((current) => [...current, toast]);
}

function drop(id: string): void {
	list.update((current) => current.filter((toast) => toast.id !== id));
}

function markPending(key: string, pending: boolean): void {
	pendingDeletes.update((current) => {
		const next = new Set(current);
		if (pending) next.add(key);
		else next.delete(key);
		return next;
	});
}

/** Transient success/error toast. Auto-dismisses after `durationMs`. */
export function notify(variant: 'success' | 'error', message: string, durationMs?: number): void {
	const id = nextId();
	const ttl = durationMs ?? (variant === 'error' ? ERROR_MS : SUCCESS_MS);
	push({ id, variant, message, durationMs: ttl });
	if (browser) setTimeout(() => drop(id), ttl);
}

/** Remove a toast by id (the host's dismiss button, for non-undo toasts). */
export function dismiss(id: string): void {
	drop(id);
}

interface PendingDelete {
	key: string;
	timer: ReturnType<typeof setTimeout> | null;
	settled: boolean;
	commit: () => Promise<void>;
	undo: () => void;
}

const pending = new Map<string, PendingDelete>();

export interface SoftDeleteOptions {
	/** Namespace for the optimistic-hide key, e.g. 'amazon', 'expense'. */
	kind: string;
	/** Record id being deleted. */
	id: string;
	/** Toast copy, e.g. 'Order deleted'. */
	message: string;
	/**
	 * The real, irreversible delete. Runs when the undo window lapses (or on
	 * navigation / unload). It is NOT called if the user hits Undo, so even a
	 * cascading delete is free to reverse.
	 */
	commit: () => Promise<void> | void;
	/**
	 * Restore page-local state when undone or when the commit fails. Usually
	 * unnecessary — the `pendingDeletes` filter already hides and re-reveals the
	 * row reactively — but provided for pages that keep extra local state.
	 */
	onUndo?: () => void;
	durationMs?: number;
}

/**
 * Gmail-style deferred delete. Hides the row immediately (via `pendingDeletes`),
 * shows an Undo toast, and only runs `commit()` when the window expires. Undo
 * cancels before any API call happens; a failed commit re-reveals the row and
 * surfaces an error toast.
 */
export function softDelete(opts: SoftDeleteOptions): void {
	const toastId = nextId();
	const key = pendingKey(opts.kind, opts.id);
	const ttl = opts.durationMs ?? UNDO_MS;

	markPending(key, true);

	const settle = (): void => {
		const record = pending.get(toastId);
		if (record) record.settled = true;
		pending.delete(toastId);
		drop(toastId);
	};

	const commit = async (): Promise<void> => {
		const record = pending.get(toastId);
		if (!record || record.settled) return;
		if (record.timer) clearTimeout(record.timer);
		settle();
		try {
			await opts.commit();
		} catch (error) {
			// Delete failed — re-reveal the row and tell the user.
			markPending(key, false);
			opts.onUndo?.();
			notify('error', error instanceof Error ? error.message : 'Could not delete.');
			return;
		}
		markPending(key, false);
	};

	const undo = (): void => {
		const record = pending.get(toastId);
		if (!record || record.settled) return;
		if (record.timer) clearTimeout(record.timer);
		settle();
		markPending(key, false);
		opts.onUndo?.();
	};

	const timer = browser ? setTimeout(() => void commit(), ttl) : null;
	pending.set(toastId, { key, timer, settled: false, commit, undo });
	push({ id: toastId, variant: 'undo', message: opts.message, durationMs: ttl });
}

/** Cancel the delete behind an undo toast (the host's Undo button). */
export function undoDelete(toastId: string): void {
	pending.get(toastId)?.undo();
}

/** Commit the delete behind an undo toast now (the host's dismiss button). */
export function commitNow(toastId: string): void {
	void pending.get(toastId)?.commit();
}

/**
 * Commit every still-pending delete immediately. Call on navigation / unload so
 * a deferred delete is never silently dropped when the user leaves the page.
 */
export function flushPendingDeletes(): void {
	for (const record of [...pending.values()]) void record.commit();
}

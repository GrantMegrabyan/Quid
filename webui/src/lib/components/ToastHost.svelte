<script lang="ts">
	import { CircleAlert, CircleCheck, Trash2, Undo2, X } from '@lucide/svelte';
	import {
		commitNow,
		dismiss,
		pauseUndo,
		resumeUndo,
		toasts,
		undoDelete
	} from '$lib/stores/toasts';

	let pausedId = $state<string | null>(null);

	function onEnter(toast: { id: string; variant: string }): void {
		if (toast.variant !== 'undo') return;
		pausedId = toast.id;
		pauseUndo(toast.id);
	}

	function onLeave(toast: { id: string; variant: string }): void {
		if (toast.variant !== 'undo') return;
		if (pausedId === toast.id) pausedId = null;
		resumeUndo(toast.id);
	}
</script>

<div
	class="pointer-events-none fixed inset-x-0 bottom-0 z-[70] flex flex-col items-center gap-2 px-4 pb-6 sm:items-end sm:px-6"
	data-testid="toast-host"
	aria-live="polite"
	aria-atomic="false"
>
	{#each $toasts as toast (toast.id)}
		<div
			data-testid="app-toast"
			data-kind={toast.variant}
			role={toast.variant === 'error' ? 'alert' : 'status'}
			onmouseenter={() => onEnter(toast)}
			onmouseleave={() => onLeave(toast)}
			class="app-toast pointer-events-auto relative flex w-full max-w-sm items-start gap-2.5 overflow-hidden rounded-lg border px-4 py-3 text-sm shadow-lg shadow-ctp-crust/40 backdrop-blur {toast.variant ===
			'error'
				? 'border-ctp-red/40 bg-ctp-red/10'
				: toast.variant === 'undo'
					? 'border-ctp-surface2 bg-ctp-surface0/95'
					: 'border-ctp-accent/40 bg-ctp-accent/10'}"
		>
			<span
				class="mt-px shrink-0 {toast.variant === 'error'
					? 'text-ctp-red'
					: toast.variant === 'undo'
						? 'text-ctp-overlay1'
						: 'text-ctp-accent'}"
				aria-hidden="true"
			>
				{#if toast.variant === 'success'}
					<CircleCheck size={16} />
				{:else if toast.variant === 'error'}
					<CircleAlert size={16} />
				{:else}
					<Trash2 size={16} />
				{/if}
			</span>

			<p class="min-w-0 flex-1 text-ctp-text">{toast.message}</p>

			{#if toast.variant === 'undo'}
				<button
					type="button"
					data-testid="toast-undo"
					onclick={() => undoDelete(toast.id)}
					class="-my-0.5 inline-flex shrink-0 items-center gap-1 rounded-md border border-ctp-surface2 bg-ctp-base px-2 py-1 text-xs font-semibold text-ctp-text transition-colors hover:bg-ctp-surface1"
				>
					<Undo2 size={13} aria-hidden="true" />
					Undo
				</button>
			{/if}

			<button
				type="button"
				aria-label="Dismiss"
				title="Dismiss"
				onclick={() => (toast.variant === 'undo' ? commitNow(toast.id) : dismiss(toast.id))}
				class="-mr-1 -mt-0.5 shrink-0 rounded-md p-0.5 text-ctp-overlay1 opacity-70 transition-opacity hover:opacity-100"
			>
				<X size={15} aria-hidden="true" />
			</button>

			<span
				class="toast-progress absolute inset-x-0 bottom-0 h-0.5 origin-left {toast.variant === 'error'
					? 'bg-ctp-red/50'
					: toast.variant === 'undo'
						? 'bg-ctp-overlay0/60'
						: 'bg-ctp-accent/50'}"
				style="animation-duration: {toast.durationMs}ms; animation-play-state: {pausedId ===
				toast.id
					? 'paused'
					: 'running'}"
			></span>
		</div>
	{/each}
</div>

<style>
	.app-toast {
		animation: app-toast-in 200ms cubic-bezier(0.22, 1, 0.36, 1);
	}

	@keyframes app-toast-in {
		from {
			opacity: 0;
			transform: translateY(10px) scale(0.98);
		}
		to {
			opacity: 1;
			transform: translateY(0) scale(1);
		}
	}

	.toast-progress {
		animation-name: toast-progress;
		animation-timing-function: linear;
		animation-fill-mode: forwards;
	}

	@keyframes toast-progress {
		from {
			transform: scaleX(1);
		}
		to {
			transform: scaleX(0);
		}
	}

	@media (prefers-reduced-motion: reduce) {
		.app-toast {
			animation: none;
		}
		.toast-progress {
			animation: none;
			transform: scaleX(0);
		}
	}
</style>

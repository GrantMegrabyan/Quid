<script lang="ts">
	import { onMount } from 'svelte';
	import '../app.css';
	import favicon from '$lib/assets/favicon.ico';
	import { page } from '$app/stores';
	import { beforeNavigate } from '$app/navigation';
	import {
		LayoutDashboard,
		BarChart3,
		Upload,
		Tags,
		ListFilter,
		Sparkles,
		ShoppingCart,
		Settings,
		Menu,
		X,
		Sun,
		Moon
	} from '@lucide/svelte';
	import { theme } from '$lib/stores/theme';
	import ToastHost from '$lib/components/ToastHost.svelte';
	import { flushPendingDeletes } from '$lib/stores/toasts';

	let { children } = $props();

	let mobileOpen = $state(false);

	// A deferred (undo-able) delete must not be silently dropped when the user
	// leaves the page before its window lapses: commit any pending deletes on
	// client navigation and on a full unload (best-effort).
	beforeNavigate(() => flushPendingDeletes());
	onMount(() => {
		const flush = () => flushPendingDeletes();
		window.addEventListener('beforeunload', flush);
		return () => window.removeEventListener('beforeunload', flush);
	});

	const navLinks = [
		{ href: '/', label: 'Dashboard', icon: LayoutDashboard },
		{ href: '/analytics', label: 'Analytics', icon: BarChart3 },
		{ href: '/import', label: 'Import', icon: Upload },
		{ href: '/categories', label: 'Categories', icon: Tags },
		{ href: '/rules', label: 'Rules', icon: ListFilter },
		{ href: '/ai-rules', label: 'AI Rules', icon: Sparkles },
		{ href: '/amazon', label: 'Amazon', icon: ShoppingCart },
		{ href: '/settings', label: 'Settings', icon: Settings }
	];

	function isActive(pathname: string, href: string): boolean {
		if (href === '/') return pathname === '/';
		return pathname === href || pathname.startsWith(href + '/');
	}

	function closeMobile(): void {
		mobileOpen = false;
	}
</script>

<svelte:head><link rel="icon" href={favicon} /></svelte:head>

{#snippet sidebarContent()}
	<!-- Wordmark -->
	<div class="flex h-16 items-center gap-2.5 px-5">
		<span
			class="flex h-8 w-8 items-center justify-center rounded-md bg-ctp-accent text-ctp-on-accent"
		>
			<svg
				viewBox="0 0 24 24"
				class="h-[18px] w-[18px]"
				fill="none"
				stroke="currentColor"
				stroke-width="2.2"
				stroke-linecap="round"
				stroke-linejoin="round"
				aria-hidden="true"
			>
				<path d="M16.5 6.5a3.5 3.5 0 0 0-6.6-1.6c-.5 1-.6 2.2-.5 3.4l.5 4.2c.2 1.6-.2 3.2-1.1 4.5" />
				<path d="M7 13h6" />
				<path d="M6.5 18.5h10" />
			</svg>
		</span>
		<span class="font-serif text-lg font-bold tracking-tight text-ctp-text">Quid</span>
	</div>

	<!-- Nav -->
	<nav class="flex flex-1 flex-col gap-0.5 overflow-y-auto px-3 pb-4">
		{#each navLinks as link (link.href)}
			{@const active = isActive($page.url.pathname, link.href)}
			<a
				href={link.href}
				aria-current={active ? 'page' : undefined}
				onclick={closeMobile}
				class="group flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors {active
					? 'bg-ctp-surface0 font-semibold text-ctp-text'
					: 'font-medium text-ctp-subtext0 hover:bg-ctp-surface0/70 hover:text-ctp-text'}"
			>
				<link.icon
					class="h-4 w-4 shrink-0 {active
						? 'text-ctp-accent'
						: 'text-ctp-overlay1 group-hover:text-ctp-subtext0'}"
				/>
				<span>{link.label}</span>
			</a>
		{/each}
	</nav>

	<!-- Appearance -->
	<div class="border-t border-ctp-surface1 px-3 py-3">
		<button
			type="button"
			data-testid="theme-toggle"
			onclick={() => theme.toggle()}
			class="flex w-full items-center gap-3 rounded-md px-3 py-2 text-sm font-medium text-ctp-subtext0 transition-colors hover:bg-ctp-surface0/70 hover:text-ctp-text"
		>
			{#if $theme === 'dark'}
				<Sun class="h-4 w-4 shrink-0 text-ctp-overlay1" />
				<span>Paper</span>
			{:else}
				<Moon class="h-4 w-4 shrink-0 text-ctp-overlay1" />
				<span>Ink</span>
			{/if}
		</button>
	</div>
{/snippet}

<div class="min-h-screen bg-ctp-mantle text-ctp-text">
	<!-- Desktop sidebar -->
	<aside
		class="fixed inset-y-0 left-0 z-40 hidden w-[230px] flex-col border-r border-ctp-surface1 bg-ctp-crust lg:flex"
	>
		{@render sidebarContent()}
	</aside>

	<!-- Mobile drawer -->
	{#if mobileOpen}
		<div class="fixed inset-0 z-50 lg:hidden">
			<button
				type="button"
				aria-label="Close menu"
				onclick={closeMobile}
				class="absolute inset-0 bg-ctp-text/25 backdrop-blur-sm"
			></button>
			<aside
				class="absolute inset-y-0 left-0 flex w-[230px] flex-col border-r border-ctp-surface1 bg-ctp-crust"
			>
				<button
					type="button"
					aria-label="Close menu"
					onclick={closeMobile}
					class="absolute right-3 top-4 rounded-md p-1.5 text-ctp-subtext0 hover:bg-ctp-surface0 hover:text-ctp-text"
				>
					<X class="h-5 w-5" />
				</button>
				{@render sidebarContent()}
			</aside>
		</div>
	{/if}

	<!-- Content column -->
	<div class="lg:pl-[230px]">
		<!-- Mobile menu trigger (no top bar on desktop) -->
		<button
			type="button"
			aria-label="Open menu"
			onclick={() => (mobileOpen = true)}
			class="fixed left-4 top-4 z-30 inline-flex items-center justify-center rounded-md border border-ctp-surface1 bg-ctp-mantle/90 p-2 text-ctp-subtext0 backdrop-blur transition-colors hover:bg-ctp-surface0 hover:text-ctp-text lg:hidden"
		>
			<Menu class="h-5 w-5" />
		</button>

		<main class="mx-auto max-w-[1400px] p-4 pt-16 sm:p-6 lg:pt-8">
			{@render children()}
		</main>
	</div>

	<ToastHost />
</div>

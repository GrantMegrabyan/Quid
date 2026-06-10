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
		X
	} from '@lucide/svelte';
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
	<!-- Logo -->
	<div class="flex h-16 items-center gap-2.5 px-6">
		<span
			class="flex h-9 w-9 items-center justify-center rounded-lg bg-ctp-accent text-ctp-on-accent shadow-lg shadow-emerald-500/20"
		>
			<svg
				viewBox="0 0 24 24"
				class="h-5 w-5"
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
		<span class="text-lg font-bold tracking-tight text-ctp-text">Quid</span>
	</div>

	<!-- Nav -->
	<nav class="mt-2 flex flex-1 flex-col gap-1 overflow-y-auto px-3 pb-6">
		<p class="px-3 pb-2 pt-3 text-[11px] font-semibold uppercase tracking-wider text-ctp-overlay0">
			Pages
		</p>
		{#each navLinks as link (link.href)}
			{@const active = isActive($page.url.pathname, link.href)}
			<a
				href={link.href}
				aria-current={active ? 'page' : undefined}
				onclick={closeMobile}
				class="group relative flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors {active
					? 'bg-ctp-surface0 text-ctp-accent'
					: 'text-ctp-subtext0 hover:bg-ctp-surface0/60 hover:text-ctp-text'}"
			>
				{#if active}
					<span
						class="absolute left-0 top-1/2 h-5 w-1 -translate-y-1/2 rounded-r-full bg-ctp-accent"
					></span>
				{/if}
				<link.icon
					class="h-[18px] w-[18px] shrink-0 {active
						? 'text-ctp-accent'
						: 'text-ctp-overlay1 group-hover:text-ctp-text'}"
				/>
				<span>{link.label}</span>
			</a>
		{/each}
	</nav>
{/snippet}

<div class="min-h-screen bg-ctp-mantle text-ctp-text">
	<!-- Desktop sidebar -->
	<aside
		class="fixed inset-y-0 left-0 z-40 hidden w-[250px] flex-col border-r border-ctp-surface1 bg-ctp-crust lg:flex"
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
				class="absolute inset-0 bg-black/60 backdrop-blur-sm"
			></button>
			<aside
				class="absolute inset-y-0 left-0 flex w-[250px] flex-col border-r border-ctp-surface1 bg-ctp-crust"
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
	<div class="lg:pl-[250px]">
		<!-- Mobile menu trigger (no top bar on desktop) -->
		<button
			type="button"
			aria-label="Open menu"
			onclick={() => (mobileOpen = true)}
			class="fixed left-4 top-4 z-30 inline-flex items-center justify-center rounded-lg border border-ctp-surface1 bg-ctp-base/80 p-2 text-ctp-subtext0 shadow-lg shadow-black/20 backdrop-blur transition-colors hover:bg-ctp-surface0 hover:text-ctp-text lg:hidden"
		>
			<Menu class="h-5 w-5" />
		</button>

		<main class="p-4 pt-16 sm:p-6 lg:pt-6">
			{@render children()}
		</main>
	</div>

	<ToastHost />
</div>

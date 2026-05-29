<script lang="ts">
	import '../app.css';
	import favicon from '$lib/assets/favicon.ico';
	import { page } from '$app/stores';
	import {
		LayoutDashboard,
		Upload,
		Tags,
		ListFilter,
		Sparkles,
		ShoppingCart,
		Settings,
		Search,
		Bell,
		Menu,
		X
	} from '@lucide/svelte';

	let { children } = $props();

	let mobileOpen = $state(false);

	const navLinks = [
		{ href: '/', label: 'Dashboard', icon: LayoutDashboard },
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
			<svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2.5">
				<path d="M5 12h14M12 5l7 7-7 7" stroke-linecap="round" stroke-linejoin="round" />
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
		<!-- Top bar -->
		<header
			class="sticky top-0 z-30 flex h-16 items-center gap-3 border-b border-ctp-surface1 bg-ctp-mantle/80 px-4 backdrop-blur sm:px-6"
		>
			<button
				type="button"
				aria-label="Open menu"
				onclick={() => (mobileOpen = true)}
				class="rounded-md p-2 text-ctp-subtext0 hover:bg-ctp-surface0 hover:text-ctp-text lg:hidden"
			>
				<Menu class="h-5 w-5" />
			</button>

			<!-- Search / command chip -->
			<button
				type="button"
				class="hidden items-center gap-2 rounded-lg border border-ctp-surface1 bg-ctp-base px-3 py-2 text-sm text-ctp-overlay1 transition-colors hover:border-ctp-surface2 sm:flex"
			>
				<Search class="h-4 w-4" />
				<span>Search…</span>
				<kbd
					class="ml-2 rounded border border-ctp-surface2 bg-ctp-surface0 px-1.5 py-0.5 text-[10px] font-medium text-ctp-subtext0"
				>
					⌘K
				</kbd>
			</button>

			<div class="ml-auto flex items-center gap-2">
				<button
					type="button"
					aria-label="Notifications"
					class="relative rounded-full p-2 text-ctp-subtext0 transition-colors hover:bg-ctp-surface0 hover:text-ctp-text"
				>
					<Bell class="h-5 w-5" />
					<span
						class="absolute right-1.5 top-1.5 h-2 w-2 rounded-full bg-ctp-red ring-2 ring-ctp-mantle"
					></span>
				</button>
				<span
					class="flex h-9 w-9 items-center justify-center rounded-full bg-gradient-to-br from-ctp-accent to-ctp-teal text-sm font-semibold text-ctp-on-accent"
				>
					Q
				</span>
			</div>
		</header>

		<main class="p-4 sm:p-6">
			{@render children()}
		</main>
	</div>
</div>

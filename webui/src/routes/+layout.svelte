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
		Moon,
		PanelLeftClose,
		PanelLeftOpen
	} from '@lucide/svelte';
	import { theme } from '$lib/stores/theme';
	import { persisted } from '$lib/stores/persisted';
	import ToastHost from '$lib/components/ToastHost.svelte';
	import { flushPendingDeletes } from '$lib/stores/toasts';

	let { children } = $props();

	let mobileOpen = $state(false);

	// The rail collapses to icons; the choice is per-device, so it lives in
	// localStorage rather than in app settings.
	const collapsed = persisted<boolean>(
		'quid:sidebar-collapsed:v1',
		false,
		(value) => typeof value === 'boolean'
	);

	// A deferred (undo-able) delete must not be silently dropped when the user
	// leaves the page before its window lapses: commit any pending deletes on
	// client navigation and on a full unload (best-effort).
	beforeNavigate(() => flushPendingDeletes());
	onMount(() => {
		const flush = () => flushPendingDeletes();
		window.addEventListener('beforeunload', flush);
		return () => window.removeEventListener('beforeunload', flush);
	});

	// Nav is grouped by what the section is FOR — the daily views first, then
	// getting data in, then the machinery that shapes it. Settings is pinned to
	// the footer rather than sitting at the end of the last group.
	type NavItem = { href: string; label: string; icon: typeof LayoutDashboard };
	const navGroups: { label: string; items: NavItem[] }[] = [
		{
			label: 'Overview',
			items: [
				{ href: '/', label: 'Dashboard', icon: LayoutDashboard },
				{ href: '/analytics', label: 'Analytics', icon: BarChart3 }
			]
		},
		{
			label: 'Data',
			items: [
				{ href: '/import', label: 'Import', icon: Upload },
				{ href: '/amazon', label: 'Amazon', icon: ShoppingCart }
			]
		},
		{
			label: 'Setup',
			items: [
				{ href: '/categories', label: 'Categories', icon: Tags },
				{ href: '/rules', label: 'Rules', icon: ListFilter },
				{ href: '/ai-rules', label: 'AI Rules', icon: Sparkles }
			]
		}
	];
	const settingsItem: NavItem = { href: '/settings', label: 'Settings', icon: Settings };

	function isActive(pathname: string, href: string): boolean {
		if (href === '/') return pathname === '/';
		return pathname === href || pathname.startsWith(href + '/');
	}

	function closeMobile(): void {
		mobileOpen = false;
	}
</script>

<svelte:head><link rel="icon" href={favicon} /></svelte:head>

{#snippet navItem(item: NavItem, isCollapsed: boolean)}
	{@const active = isActive($page.url.pathname, item.href)}
	<a
		href={item.href}
		aria-current={active ? 'page' : undefined}
		onclick={closeMobile}
		title={isCollapsed ? item.label : undefined}
		class="group flex items-center gap-3 rounded-md py-2 text-sm transition-colors {isCollapsed
			? 'justify-center px-2'
			: 'px-3'} {active
			? 'bg-ctp-surface0 font-semibold text-ctp-text'
			: 'font-medium text-ctp-subtext0 hover:bg-ctp-surface0/70 hover:text-ctp-text'}"
	>
		<item.icon
			class="h-4 w-4 shrink-0 {active
				? 'text-ctp-accent'
				: 'text-ctp-overlay1 group-hover:text-ctp-subtext0'}"
		/>
		{#if !isCollapsed}<span class="truncate">{item.label}</span>{/if}
	</a>
{/snippet}

{#snippet sidebarContent(isCollapsed: boolean)}
	<!-- Wordmark -->
	<div
		class="flex h-16 items-center gap-2.5 {isCollapsed ? 'justify-center px-2' : 'px-5'}"
	>
		<span class="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-ctp-accent text-ctp-on-accent">
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
		{#if !isCollapsed}
			<span class="font-serif text-lg font-bold tracking-tight text-ctp-text">Quid</span>
		{/if}
	</div>

	<!-- Nav -->
	<nav class="flex flex-1 flex-col gap-4 overflow-y-auto px-3 pb-4">
		{#each navGroups as group (group.label)}
			<div class="flex flex-col gap-0.5">
				{#if !isCollapsed}
					<p class="px-3 pb-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-ctp-overlay0">
						{group.label}
					</p>
				{/if}
				{#each group.items as item (item.href)}
					{@render navItem(item, isCollapsed)}
				{/each}
			</div>
		{/each}
	</nav>

	<!-- Footer: settings, appearance, and the rail toggle -->
	<div class="flex flex-col gap-0.5 border-t border-ctp-surface1 px-3 py-3">
		{@render navItem(settingsItem, isCollapsed)}
		<button
			type="button"
			data-testid="theme-toggle"
			onclick={() => theme.toggle()}
			title={isCollapsed ? ($theme === 'dark' ? 'Paper' : 'Ink') : undefined}
			class="flex items-center gap-3 rounded-md py-2 text-sm font-medium text-ctp-subtext0 transition-colors hover:bg-ctp-surface0/70 hover:text-ctp-text {isCollapsed
				? 'justify-center px-2'
				: 'px-3'}"
		>
			{#if $theme === 'dark'}
				<Sun class="h-4 w-4 shrink-0 text-ctp-overlay1" />
				{#if !isCollapsed}<span>Paper</span>{/if}
			{:else}
				<Moon class="h-4 w-4 shrink-0 text-ctp-overlay1" />
				{#if !isCollapsed}<span>Ink</span>{/if}
			{/if}
		</button>
		<button
			type="button"
			data-testid="sidebar-collapse"
			onclick={() => collapsed.set(!$collapsed)}
			title={isCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
			class="hidden items-center gap-3 rounded-md py-2 text-sm font-medium text-ctp-subtext0 transition-colors hover:bg-ctp-surface0/70 hover:text-ctp-text lg:flex {isCollapsed
				? 'justify-center px-2'
				: 'px-3'}"
		>
			{#if isCollapsed}
				<PanelLeftOpen class="h-4 w-4 shrink-0 text-ctp-overlay1" />
			{:else}
				<PanelLeftClose class="h-4 w-4 shrink-0 text-ctp-overlay1" />
				<span>Collapse</span>
			{/if}
		</button>
	</div>
{/snippet}

<div class="min-h-screen bg-ctp-mantle text-ctp-text">
	<!-- Desktop rail -->
	<aside
		data-testid="sidebar"
		data-collapsed={$collapsed ? 'true' : 'false'}
		class="fixed inset-y-0 left-0 z-40 hidden flex-col border-r border-ctp-surface1 bg-ctp-crust transition-[width] duration-200 lg:flex {$collapsed
			? 'w-[68px]'
			: 'w-[230px]'}"
	>
		{@render sidebarContent($collapsed)}
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
				{@render sidebarContent(false)}
			</aside>
		</div>
	{/if}

	<!-- Content column -->
	<div class="transition-[padding] duration-200 {$collapsed ? 'lg:pl-[68px]' : 'lg:pl-[230px]'}">
		<!-- Mobile menu trigger (no top bar on desktop) -->
		<button
			type="button"
			aria-label="Open menu"
			onclick={() => (mobileOpen = true)}
			class="fixed left-4 top-4 z-40 inline-flex items-center justify-center rounded-md border border-ctp-surface1 bg-ctp-mantle/90 p-2 text-ctp-subtext0 backdrop-blur transition-colors hover:bg-ctp-surface0 hover:text-ctp-text lg:hidden"
		>
			<Menu class="h-5 w-5" />
		</button>

		<main class="mx-auto max-w-[1400px] px-4 pt-14 sm:px-6 lg:pt-0">
			{@render children()}
		</main>
	</div>

	<ToastHost />
</div>

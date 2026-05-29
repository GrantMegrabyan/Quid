<script lang="ts">
	import '../app.css';
	import favicon from '$lib/assets/favicon.ico';
	import { page } from '$app/stores';

	let { children } = $props();

	const navLinks = [
		{ href: '/', label: 'Dashboard' },
		{ href: '/import', label: 'Import' },
		{ href: '/categories', label: 'Categories' },
		{ href: '/rules', label: 'Rules' },
		{ href: '/ai-rules', label: 'AI Rules' },
		{ href: '/amazon', label: 'Amazon' },
		{ href: '/settings', label: 'Settings' }
	];

	function isActive(pathname: string, href: string): boolean {
		if (href === '/') return pathname === '/';
		return pathname === href || pathname.startsWith(href + '/');
	}
</script>

<svelte:head><link rel="icon" href={favicon} /></svelte:head>

<div class="min-h-screen bg-ctp-base text-ctp-text">
	<header class="sticky top-0 z-40 border-b border-ctp-surface1 bg-ctp-base/80 backdrop-blur">
		<div
			class="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-2 px-4 py-3 sm:px-6 lg:px-8"
		>
			<a href="/" class="shrink-0 text-lg font-semibold tracking-tight text-ctp-text">
				Quid
			</a>

			<nav class="flex flex-wrap items-center justify-end gap-1 sm:gap-2">
				{#each navLinks as link (link.href)}
					{@const active = isActive($page.url.pathname, link.href)}
					<a
						href={link.href}
						aria-current={active ? 'page' : undefined}
						class="rounded-md px-2 py-1.5 text-sm font-medium transition-colors sm:px-3 {active
							? 'bg-ctp-accent text-ctp-on-accent'
							: 'text-ctp-subtext0 hover:bg-ctp-surface1 hover:text-ctp-text'}"
					>
						{link.label}
					</a>
				{/each}
			</nav>
		</div>
	</header>

	<main class="mx-auto max-w-5xl px-4 py-6 sm:px-6 lg:px-8">
		{@render children()}
	</main>
</div>

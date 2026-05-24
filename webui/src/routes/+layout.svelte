<script lang="ts">
	import '../app.css';
	import favicon from '$lib/assets/favicon.svg';
	import { page } from '$app/stores';

	let { children } = $props();

	const navLinks = [
		{ href: '/', label: 'Dashboard' },
		{ href: '/import', label: 'Import' },
		{ href: '/categories', label: 'Categories' },
		{ href: '/rules', label: 'Rules' },
		{ href: '/ai-rules', label: 'AI Rules' }
	];

	let isDark = $state(false);

	function syncDarkFromDom() {
		if (typeof document !== 'undefined') {
			isDark = document.documentElement.classList.contains('dark');
		}
	}

	function toggleTheme() {
		if (typeof document === 'undefined') return;
		const root = document.documentElement;
		const nextDark = !root.classList.contains('dark');
		if (nextDark) {
			root.classList.add('dark');
		} else {
			root.classList.remove('dark');
		}
		try {
			localStorage.setItem('theme', nextDark ? 'dark' : 'light');
		} catch {
			// localStorage unavailable; theme still toggles for this session.
		}
		isDark = nextDark;
	}

	function isActive(pathname: string, href: string): boolean {
		if (href === '/') return pathname === '/';
		return pathname === href || pathname.startsWith(href + '/');
	}
</script>

<svelte:head><link rel="icon" href={favicon} /></svelte:head>

<div class="min-h-screen bg-white text-gray-900 dark:bg-[#0b0b0c] dark:text-gray-100">
	<header
		class="sticky top-0 z-40 border-b border-gray-200 bg-white/80 backdrop-blur dark:border-gray-800 dark:bg-[#0b0b0c]/80"
	>
		<div
			class="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-2 px-4 py-3 sm:px-6 lg:px-8"
		>
			<a
				href="/"
				class="shrink-0 text-lg font-semibold tracking-tight text-gray-900 dark:text-gray-50"
			>
				Expenses
			</a>

			<nav class="flex flex-wrap items-center justify-end gap-1 sm:gap-2">
				{#each navLinks as link (link.href)}
					{@const active = isActive($page.url.pathname, link.href)}
					<a
						href={link.href}
						aria-current={active ? 'page' : undefined}
						class="rounded-md px-2 py-1.5 text-sm font-medium transition-colors sm:px-3"
						class:bg-gray-900={active}
						class:text-white={active}
						class:dark:bg-gray-100={active}
						class:dark:text-gray-900={active}
						class:text-gray-600={!active}
						class:hover:bg-gray-100={!active}
						class:hover:text-gray-900={!active}
						class:dark:text-gray-300={!active}
						class:dark:hover:bg-gray-800={!active}
						class:dark:hover:text-gray-50={!active}
					>
						{link.label}
					</a>
				{/each}

				<button
					type="button"
					data-testid="theme-toggle"
					aria-label="Toggle color theme"
					aria-pressed={isDark}
					onclick={toggleTheme}
					onfocus={syncDarkFromDom}
					onmouseenter={syncDarkFromDom}
					class="ml-1 inline-flex h-8 w-8 items-center justify-center rounded-md border border-gray-200 text-base text-gray-700 transition-colors hover:bg-gray-100 hover:text-gray-900 dark:border-gray-800 dark:text-gray-300 dark:hover:bg-gray-800 dark:hover:text-gray-50"
				>
					{isDark ? '☀' : '🌙'}
				</button>
			</nav>
		</div>
	</header>

	<main class="mx-auto max-w-5xl px-4 py-6 sm:px-6 lg:px-8">
		{@render children()}
	</main>
</div>

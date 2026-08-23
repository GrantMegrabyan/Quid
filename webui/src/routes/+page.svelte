<script lang="ts">
	import { onMount } from 'svelte';
	import { SvelteSet } from 'svelte/reactivity';
	import { page } from '$app/stores';
	import { replaceState } from '$app/navigation';
	import { browser } from '$app/environment';
	import PageHeader from '$components/shell/PageHeader.svelte';
	import PageContent from '$components/shell/PageContent.svelte';
	import SectionCard from '$components/shell/SectionCard.svelte';
	import ExpenseList from '$components/ExpenseList.svelte';
	import ExpenseFormModal from '$components/ExpenseFormModal.svelte';
	import PeriodSelector from '$components/PeriodSelector.svelte';
	import SpendChart from '$components/SpendChart.svelte';
	import CategoryBreakdown from '$components/CategoryBreakdown.svelte';
	import CategoryIcon from '$components/CategoryIcon.svelte';
	import HeroAmount from '$components/HeroAmount.svelte';
	import TransactionsToolbar, {
		type ReviewStatus,
		type TransactionFilter
	} from '$components/TransactionsToolbar.svelte';
	import BulkActionBar from '$components/BulkActionBar.svelte';
	import NeedsReview from '$components/rail/NeedsReview.svelte';
	import TopMerchants from '$components/rail/TopMerchants.svelte';
	import ImportanceMix from '$components/rail/ImportanceMix.svelte';
	import { expenses, editExpense, refreshExpenses } from '$lib/stores/expenses';
	import { categories, refreshCategories } from '$lib/stores/categories';
	import { refreshSettings, settings } from '$lib/stores/settings';
	import { isMonthMode, resolvedPeriod, selection, setMonth, setPeriod } from '$lib/stores/ui';
	import { viewWindow } from '$lib/stores/window';
	import { softDelete } from '$lib/stores/toasts';
	import { persisted } from '$lib/stores/persisted';
	import { analyticsRepository, expenseRepository } from '$lib/repos';
	import { elapsedDays, isPeriodCode, totalDays } from '$utils/period';
	import { amountToNumber, formatAmount } from '$utils/money';
	import { UNCATEGORIZED_COLOR } from '$utils/categoryColor';
	import { TrendingUp, TrendingDown } from '@lucide/svelte';
	import { UNCATEGORIZED_ID, type Expense } from '$types';

	let modalOpen = $state(false);
	let editingExpense: Expense | undefined = $state(undefined);

	type ExpenseGroupBy = 'transaction' | 'merchant' | 'category' | 'importance';
	const GROUP_BY_VALUES: ExpenseGroupBy[] = ['transaction', 'merchant', 'category', 'importance'];
	const expenseGroupBy = persisted<ExpenseGroupBy>(
		'quid:expense-group-by:v1',
		'transaction',
		(value) => GROUP_BY_VALUES.includes(value)
	);

	// ── The window ────────────────────────────────────────────────────────
	// Everything on this page is derived from the loaded window; the store is
	// fetched to match the selection, so no component re-filters by date.
	const windowTotal = $derived.by(() => {
		let total = 0;
		for (const expense of $expenses) total += amountToNumber(expense.amount);
		return total;
	});
	const transactionCount = $derived($expenses.length);
	const avgPerTransaction = $derived(
		transactionCount > 0 ? windowTotal / transactionCount : 0
	);

	// $viewWindow, not $resolvedPeriod: "all time" is fetched from an epoch
	// sentinel, and dividing by the ~20,000 days since 1970 makes the daily
	// average meaningless.
	const elapsed = $derived(elapsedDays($viewWindow));
	const dailyAverage = $derived(elapsed > 0 ? windowTotal / elapsed : 0);
	const projectedTotal = $derived(dailyAverage * totalDays($viewWindow));
	// A one-or-two-day sample extrapolates to nonsense (one big shop reads as a
	// five-figure month); hold the projection back until there's some signal,
	// and only project a month — a rolling window has no "end" to project to.
	const showProjection = $derived(
		$isMonthMode && $resolvedPeriod.inProgress && elapsed >= 3 && windowTotal > 0
	);

	// The comparison window's total. One aggregate request, not a second page of
	// rows — the expense store stays scoped to the window in view.
	let priorTotal: number | null = $state(null);
	let priorRequest = 0;
	$effect(() => {
		const prior = $resolvedPeriod.prior;
		const requestId = ++priorRequest;
		priorTotal = null;
		if (!prior) return;
		analyticsRepository
			.summary({ dateFrom: prior.from, dateTo: prior.to })
			.then((result) => {
				if (requestId !== priorRequest) return;
				priorTotal = amountToNumber(result.total);
			})
			.catch(() => {
				// The delta is decorative; a failed lookup just hides it.
				if (requestId === priorRequest) priorTotal = null;
			});
	});

	const periodDelta = $derived.by(() => {
		if (priorTotal === null || priorTotal <= 0) return null;
		const diff = windowTotal - priorTotal;
		return {
			up: diff > 0,
			percent: Math.round(Math.abs(diff / priorTotal) * 100),
			label: $resolvedPeriod.priorLabel
		};
	});

	type TopCategory = {
		name: string;
		total: number;
		color: string;
		icon?: string;
		share: number;
	} | null;

	const topCategory = $derived.by<TopCategory>(() => {
		if ($expenses.length === 0) return null;
		const totals = new Map<string, number>();
		for (const expense of $expenses) {
			totals.set(
				expense.categoryId,
				(totals.get(expense.categoryId) ?? 0) + amountToNumber(expense.amount)
			);
		}
		let topId: string | null = null;
		let topTotal = 0;
		for (const [id, total] of totals) {
			if (total > topTotal) {
				topTotal = total;
				topId = id;
			}
		}
		if (topId === null) return null;
		const category = $categories.find((c) => c.id === topId);
		return {
			name: category?.name ?? 'Uncategorized',
			total: topTotal,
			color: category?.color ?? UNCATEGORIZED_COLOR,
			icon: category?.icon,
			share: windowTotal > 0 ? topTotal / windowTotal : 0
		};
	});

	// ── Filtering ─────────────────────────────────────────────────────────
	let filter: TransactionFilter = $state({
		query: '',
		categories: new SvelteSet<string>(),
		min: '',
		max: '',
		status: 'all' as ReviewStatus
	});

	const filterActive = $derived(
		filter.query.trim() !== '' ||
			filter.categories.size > 0 ||
			filter.min !== '' ||
			filter.max !== '' ||
			filter.status !== 'all'
	);

	function noteFor(expense: Expense): string {
		return expense.resolvedNote ?? expense.note ?? '';
	}

	const filteredExpenses = $derived.by(() => {
		const query = filter.query.trim().toLowerCase();
		const min = filter.min.trim() === '' ? null : Number(filter.min);
		const max = filter.max.trim() === '' ? null : Number(filter.max);
		return $expenses.filter((expense) => {
			if (query) {
				const haystack =
					`${expense.displayName ?? ''} ${expense.name} ${noteFor(expense)}`.toLowerCase();
				if (!haystack.includes(query)) return false;
			}
			if (filter.categories.size > 0 && !filter.categories.has(expense.categoryId)) return false;
			const amount = amountToNumber(expense.amount);
			if (min !== null && Number.isFinite(min) && amount < min) return false;
			if (max !== null && Number.isFinite(max) && amount > max) return false;
			if (filter.status === 'uncategorized' && expense.categoryId !== UNCATEGORIZED_ID) {
				return false;
			}
			if (filter.status === 'unconfirmed') {
				const source = expense.categorySource ?? 'import';
				if (source !== 'ai' && source !== 'import') return false;
			}
			return true;
		});
	});

	const categoryCounts = $derived.by(() => {
		const counts = new Map<string, number>();
		for (const expense of $expenses) {
			counts.set(expense.categoryId, (counts.get(expense.categoryId) ?? 0) + 1);
		}
		return counts;
	});

	function applyReviewFilter(status: 'uncategorized' | 'unconfirmed'): void {
		filter = { ...filter, status };
		if (browser) {
			document.querySelector('[data-testid="transactions-section"]')?.scrollIntoView({
				behavior: 'smooth',
				block: 'start'
			});
		}
	}

	// ── Selection & bulk actions ──────────────────────────────────────────
	let selectedIds: Set<string> = $state(new SvelteSet<string>());

	// A row that scrolls out of the filter (or gets deleted) must not stay
	// selected invisibly, or a bulk action would hit rows the user can't see.
	$effect(() => {
		const visible = new Set(filteredExpenses.map((expense) => expense.id));
		if ([...selectedIds].every((id) => visible.has(id))) return;
		selectedIds = new SvelteSet([...selectedIds].filter((id) => visible.has(id)));
	});

	async function bulkCategorize(categoryId: string): Promise<void> {
		const ids = [...selectedIds];
		selectedIds = new SvelteSet();
		// Sequential on purpose: these are small PATCHes against SQLite, and a
		// burst of parallel writes buys nothing but lock contention.
		for (const id of ids) {
			await expenseRepository.update(id, { categoryId });
		}
		await refreshExpenses();
	}

	function bulkDelete(): void {
		const ids = [...selectedIds];
		selectedIds = new SvelteSet();
		for (const id of ids) {
			softDelete({
				kind: 'expense',
				id,
				message: `${ids.length} ${ids.length === 1 ? 'transaction' : 'transactions'} deleted`,
				commit: async () => {
					await expenseRepository.delete(id);
					await refreshExpenses();
				}
			});
		}
	}

	function openEdit(expense: Expense): void {
		editingExpense = expense;
		modalOpen = true;
	}

	function closeModal(): void {
		modalOpen = false;
		editingExpense = undefined;
	}

	// ── URL ↔ selection ───────────────────────────────────────────────────
	// The window is shareable: `?period=6M` or `?month=2026-07`. The URL wins on
	// load; after that the selection writes back to it.
	let urlApplied = false;
	onMount(() => {
		const params = $page.url.searchParams;
		const monthParam = params.get('month');
		const periodParam = params.get('period');
		if (monthParam && /^\d{4}-\d{2}$/.test(monthParam)) {
			setMonth(monthParam);
		} else if (isPeriodCode(periodParam)) {
			setPeriod(periodParam);
		}
		urlApplied = true;
		void refreshCategories();
		void refreshSettings();
	});

	$effect(() => {
		const current = $selection;
		if (!browser || !urlApplied) return;
		const url = new URL(window.location.href);
		if (current.kind === 'month') {
			url.searchParams.set('month', current.monthKey);
			url.searchParams.delete('period');
		} else {
			url.searchParams.set('period', current.code);
			url.searchParams.delete('month');
		}
		if (url.href !== window.location.href) {
			try {
				replaceState(url, {});
			} catch {
				// Navigation not ready (or unsupported) — the selection is still
				// persisted, so this only costs a non-shareable URL.
			}
		}
	});

	// Re-fetch the window whenever the selection changes. `refreshExpenses`
	// reads the resolved range itself; we just depend on the store so the effect
	// re-runs. The store keeps previous data visible until the new response
	// lands (no empty flash) and guards against out-of-order responses.
	$effect(() => {
		void $resolvedPeriod;
		void refreshExpenses();
	});

	// Searching inside a window you just navigated away from is rarely what you
	// want; reset the filters on a window change so the count always matches.
	$effect(() => {
		void $resolvedPeriod;
		filter = {
			query: '',
			categories: new SvelteSet<string>(),
			min: '',
			max: '',
			status: 'all' as ReviewStatus
		};
	});
</script>

<svelte:head><title>Expenses</title></svelte:head>

<PageHeader>
	<div class="min-w-0">
		<p class="text-[11px] font-semibold uppercase tracking-[0.14em] text-ctp-overlay1">
			<span data-testid="selected-month-heading">{$resolvedPeriod.label}</span>
			<span aria-hidden="true"> · </span>{$resolvedPeriod.inProgress ? 'so far' : 'total'}
		</p>
		<h1 class="mt-1 text-3xl font-black leading-none text-ctp-text sm:text-4xl">
			<HeroAmount
				value={windowTotal}
				currency={$settings.currency}
				testid="selected-month-total"
			/>
		</h1>
		<div class="mt-1.5 flex min-h-5 flex-wrap items-center gap-x-3 gap-y-1 text-sm">
			{#if periodDelta}
				<span
					data-testid="month-delta"
					class="inline-flex items-center gap-1.5 font-medium {periodDelta.up
						? 'text-ctp-red'
						: 'text-ctp-green'}"
				>
					{#if periodDelta.up}
						<TrendingUp class="h-4 w-4" />
					{:else}
						<TrendingDown class="h-4 w-4" />
					{/if}
					<span class="tabular-nums">{periodDelta.up ? '+' : '−'}{periodDelta.percent}%</span>
					<span class="font-normal text-ctp-overlay1">vs {periodDelta.label}</span>
				</span>
			{:else}
				<span class="text-ctp-overlay1">
					{$resolvedPeriod.inProgress ? 'Spending so far' : 'Spending overview'}
				</span>
			{/if}
		</div>
	</div>

	{#snippet actions()}
		<PeriodSelector />
	{/snippet}
</PageHeader>

<PageContent>
	<!-- Support stats: a quiet ruled strip, not four competing cards. -->
	<dl class="grid grid-cols-2 gap-x-6 gap-y-4 sm:gap-x-8 lg:grid-cols-3">
		<div class="border-l border-ctp-surface1 pl-4">
			<dt class="text-[11px] font-semibold uppercase tracking-wider text-ctp-overlay1">
				Transactions
			</dt>
			<dd class="numeral mt-1 text-xl font-bold text-ctp-text">{transactionCount}</dd>
			{#if transactionCount > 0}
				<dd class="mt-0.5 text-xs text-ctp-subtext0">
					{formatAmount(avgPerTransaction, $settings.currency)} avg
				</dd>
			{/if}
		</div>

		<div class="border-l border-ctp-surface1 pl-4">
			<dt class="text-[11px] font-semibold uppercase tracking-wider text-ctp-overlay1">
				Daily average
			</dt>
			<dd data-testid="daily-average" class="numeral mt-1 text-xl font-bold text-ctp-text">
				{formatAmount(dailyAverage, $settings.currency)}
			</dd>
			{#if showProjection}
				<dd data-testid="projected-total" class="mt-0.5 text-xs text-ctp-subtext0">
					On pace for {formatAmount(projectedTotal, $settings.currency)}
				</dd>
			{/if}
		</div>

		<div class="border-l border-ctp-surface1 pl-4">
			<dt class="text-[11px] font-semibold uppercase tracking-wider text-ctp-overlay1">
				Top category
			</dt>
			{#if topCategory}
				<dd class="mt-1 flex items-center gap-2">
					<span
						class="cat-chip flex h-6 w-6 shrink-0 items-center justify-center rounded-md"
						style="--cat: {topCategory.color};"
					>
						<CategoryIcon name={topCategory.icon} size={14} />
					</span>
					<span
						data-testid="top-category-name"
						title={topCategory.name}
						class="truncate text-base font-semibold text-ctp-text"
					>
						{topCategory.name}
					</span>
				</dd>
				<dd class="mt-0.5 text-xs text-ctp-subtext0">
					{formatAmount(topCategory.total, $settings.currency)} · {Math.round(
						topCategory.share * 100
					)}% of total
				</dd>
			{:else}
				<dd class="numeral mt-1 text-xl font-bold text-ctp-overlay0">—</dd>
			{/if}
		</div>
	</dl>

	<!-- Main column + rail: the chart and the breakdown answer "how much, on
	     what"; the rail answers "anything I should look at". -->
	<div class="grid grid-cols-1 gap-6 lg:grid-cols-3">
		<div class="flex min-w-0 flex-col gap-6 lg:col-span-2">
			<SectionCard
				title="Spending"
				subtitle={$isMonthMode ? 'cumulative by day' : 'by month'}
			>
				<SpendChart />
			</SectionCard>

			<SectionCard title="Where it went" subtitle="by category">
				<CategoryBreakdown />
			</SectionCard>
		</div>

		<div class="flex min-w-0 flex-col gap-6">
			<SectionCard title="Needs review">
				<NeedsReview onreview={applyReviewFilter} />
			</SectionCard>

			<SectionCard title="Top merchants">
				<TopMerchants />
			</SectionCard>

			<SectionCard title="Essential vs discretionary">
				<ImportanceMix />
			</SectionCard>
		</div>
	</div>

	<!-- Transactions -->
	<section data-testid="transactions-section" class="flex flex-col gap-3 scroll-mt-24">
		<h2 class="text-sm font-semibold uppercase tracking-wider text-ctp-subtext0">Transactions</h2>

		<TransactionsToolbar
			{filter}
			onchange={(next) => (filter = next)}
			categories={$categories}
			{categoryCounts}
			visibleCount={filteredExpenses.length}
			totalCount={transactionCount}
			groupBy={$expenseGroupBy}
			ongroupby={(next) => expenseGroupBy.set(next as ExpenseGroupBy)}
		/>

		{#if selectedIds.size > 0}
			<BulkActionBar
				count={selectedIds.size}
				categories={$categories}
				oncategorize={(categoryId) => void bulkCategorize(categoryId)}
				ondelete={bulkDelete}
				onclear={() => (selectedIds = new SvelteSet())}
			/>
		{/if}

		<ExpenseList
			groupBy={$expenseGroupBy}
			items={filteredExpenses}
			searchQuery={filter.query}
			{filterActive}
			{selectedIds}
			onselectionchange={(next) => (selectedIds = next)}
			onedit={openEdit}
		/>
	</section>
</PageContent>

<ExpenseFormModal open={modalOpen} expense={editingExpense} on:close={closeModal} />

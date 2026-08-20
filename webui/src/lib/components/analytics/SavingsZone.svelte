<script lang="ts">
	import { settings } from '$lib/stores/settings';
	import { formatAmount } from '$utils/money';
	import { formatMonthLabel } from '$utils/dates';
	import { ChevronDown, Coffee, PiggyBank, Repeat, Sparkle } from '@lucide/svelte';
	import type { SavingsResult } from '$types';

	let { savings }: { savings: SavingsResult } = $props();

	let stackOpen = $state(false);
</script>

<section
	class="rounded-xl border border-ctp-green/30 bg-ctp-base p-4"
	data-testid="analytics-savings"
>
	<h2 class="text-xs font-bold uppercase tracking-wider text-ctp-subtext0">Where you can save</h2>

	<div class="mt-2 divide-y divide-ctp-surface0">
		<!-- Price creep -->
		<div class="py-3" data-testid="analytics-savings-creep">
			<p class="flex items-center gap-2 text-sm font-semibold text-ctp-text">
				<PiggyBank class="h-4 w-4 text-ctp-green" />
				Price creep
			</p>
			{#if savings.priceCreep.length === 0}
				<p class="mt-1 text-xs text-ctp-overlay0">
					No price increases detected in your recurring charges over the last 12 months.
				</p>
			{:else}
				<ul class="mt-1.5 flex flex-col gap-1">
					{#each savings.priceCreep as item (`${item.name}:${item.sinceMonth}`)}
						<li class="text-xs text-ctp-subtext0" data-testid="analytics-creep-item">
							<span class="font-semibold text-ctp-text">{item.name}</span>
							{formatAmount(item.oldAmount, $settings.currency)} →
							{formatAmount(item.newAmount, $settings.currency)}
							since {formatMonthLabel(item.sinceMonth)}
							<span class="font-semibold text-ctp-red"
								>(+{formatAmount(item.annualDelta, $settings.currency)}/yr)</span
							>
						</li>
					{/each}
				</ul>
			{/if}
		</div>

		<!-- New recurring -->
		<div class="py-3" data-testid="analytics-savings-newrecurring">
			<p class="flex items-center gap-2 text-sm font-semibold text-ctp-text">
				<Sparkle class="h-4 w-4 text-ctp-green" />
				New recurring charges
			</p>
			{#if savings.newRecurring.length === 0}
				<p class="mt-1 text-xs text-ctp-overlay0">No new subscriptions in the last few months.</p>
			{:else}
				<ul class="mt-1.5 flex flex-col gap-1">
					{#each savings.newRecurring as item (`${item.name}:${item.amount}:${item.firstMonth}`)}
						<li class="text-xs text-ctp-subtext0" data-testid="analytics-newrecurring-item">
							<span class="font-semibold text-ctp-text">{item.name}</span>
							{formatAmount(item.amount, $settings.currency)}/mo, first seen
							{formatMonthLabel(item.firstMonth)}
							<span class="font-semibold text-ctp-red"
								>({formatAmount(item.annualCost, $settings.currency)}/yr)</span
							>
						</li>
					{/each}
				</ul>
			{/if}
		</div>

		<!-- Habit spend -->
		<div class="py-3" data-testid="analytics-savings-habits">
			<p class="flex items-center gap-2 text-sm font-semibold text-ctp-text">
				<Coffee class="h-4 w-4 text-ctp-green" />
				Habit spend
				{#if savings.latestMonth}
					<span class="text-xs font-normal text-ctp-overlay0"
						>({formatMonthLabel(savings.latestMonth)})</span
					>
				{/if}
			</p>
			{#if savings.habits.length === 0}
				<p class="mt-1 text-xs text-ctp-overlay0">
					No high-frequency small purchases last month.
				</p>
			{:else}
				<ul class="mt-1.5 flex flex-col gap-1">
					{#each savings.habits as item (item.name)}
						<li class="text-xs text-ctp-subtext0" data-testid="analytics-habit-item">
							<span class="font-semibold text-ctp-text">{item.name}</span>
							— {item.count} visits,
							<span class="font-semibold text-ctp-text"
								>{formatAmount(item.total, $settings.currency)}</span
							>
							(avg {formatAmount(item.average, $settings.currency)})
						</li>
					{/each}
				</ul>
			{/if}
		</div>

		<!-- Recurring stack -->
		<div class="py-3" data-testid="analytics-savings-stack">
			{#if savings.recurringStack.items.length === 0}
				<div class="flex items-center gap-2 text-sm font-semibold text-ctp-text">
					<Repeat class="h-4 w-4 text-ctp-green" />
					Recurring stack
					<span class="text-xs font-normal text-ctp-subtext0" data-testid="analytics-stack-total">
						{formatAmount(savings.recurringStack.monthlyTotal, $settings.currency)}/mo =
						{formatAmount(savings.recurringStack.annualTotal, $settings.currency)}/yr
					</span>
				</div>
				<p class="mt-1 text-xs text-ctp-overlay0">No active recurring charges detected.</p>
			{:else}
				<button
					type="button"
					class="flex w-full items-center gap-2 text-left text-sm font-semibold text-ctp-text"
					data-testid="analytics-stack-toggle"
					aria-expanded={stackOpen}
					onclick={() => (stackOpen = !stackOpen)}
				>
					<Repeat class="h-4 w-4 text-ctp-green" />
					Recurring stack
					<span class="text-xs font-normal text-ctp-subtext0" data-testid="analytics-stack-total">
						{formatAmount(savings.recurringStack.monthlyTotal, $settings.currency)}/mo =
						{formatAmount(savings.recurringStack.annualTotal, $settings.currency)}/yr
					</span>
					<ChevronDown
						class="ml-auto h-4 w-4 text-ctp-overlay0 transition-transform {stackOpen
							? 'rotate-180'
							: ''}"
					/>
				</button>
				{#if stackOpen}
					<ul class="mt-2 flex flex-col gap-1 pl-6" data-testid="analytics-stack-list">
						{#each savings.recurringStack.items as item (`${item.name}:${item.amount}`)}
							<li class="flex items-baseline gap-2 text-xs text-ctp-subtext0">
								<span class="truncate font-semibold text-ctp-text">{item.name}</span>
								<span class="text-ctp-overlay0">
									{item.monthsCovered}× since {formatMonthLabel(item.firstMonth)}
								</span>
								<span class="ml-auto tabular-nums"
									>{formatAmount(item.monthlyEstimate, $settings.currency)}/mo</span
								>
							</li>
						{/each}
					</ul>
				{/if}
			{/if}
		</div>
	</div>
</section>

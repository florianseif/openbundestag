<script lang="ts">
	import { page } from '$app/state';
	import { replaceState } from '$app/navigation';
	import { api, ApiError } from '$lib/api';
	import { setPartyMeta } from '$lib/format';
	import { i18n } from '$lib/i18n.svelte';
	import { formatNumber, formatDate, partyColor } from '$lib/format';
	import type {
		Meta,
		Filters,
		TimelinePoint,
		PartyCount,
		PoliticianCount,
		Totals
	} from '$lib/types';

	import FilterPanel from '$lib/components/FilterPanel.svelte';
	import TimelineChart from '$lib/components/TimelineChart.svelte';
	import HBars from '$lib/components/HBars.svelte';
	import Donut from '$lib/components/Donut.svelte';
	import SpeechDrawer from '$lib/components/SpeechDrawer.svelte';

	// --- bootstrap state ------------------------------------------------------
	let meta = $state<Meta | null>(null);
	let bootError = $state<string | null>(null);
	let waking = $state(false);

	let filters = $state<Filters>({
		word: page.url.searchParams.get('word') ?? 'Klimawandel',
		parties: [],
		terms: [],
		politician_id: null,
		date_from: '1990-01-01',
		date_to: '2026-12-31',
		granularity: 'Monthly',
		count_mode: 'speeches'
	});

	// --- result state ---------------------------------------------------------
	let total = $state<Totals | null>(null);
	let timeline = $state<TimelinePoint[]>([]);
	let byParty = $state<PartyCount[]>([]);
	let top = $state<PoliticianCount[]>([]);
	let loading = $state(false);
	let queryError = $state<string | null>(null);

	let tab = $state<'timeline' | 'party' | 'top'>('timeline');
	let stacked = $state(false);
	let topN = $state(15);

	async function boot() {
		bootError = null;
		waking = true;
		try {
			const m = await api.meta();
			setPartyMeta(m.party_colors, m.party_full_names);
			meta = m;
		} catch (e) {
			const err = e as ApiError;
			// status 0 = network/cold start → keep retrying quietly
			bootError = err.status === 0 ? null : err.message;
			if (err.status === 0) {
				setTimeout(boot, 4000);
				return;
			}
		} finally {
			waking = false;
		}
	}
	$effect(() => {
		boot();
	});

	const valueLabel = $derived(
		filters.count_mode === 'speeches' ? i18n.t('speeches') : i18n.t('occurrences')
	);

	// --- debounced query whenever filters change ------------------------------
	let debounce: ReturnType<typeof setTimeout>;
	$effect(() => {
		if (!meta) return;
		// track dependencies explicitly
		const f = {
			...filters,
			parties: [...filters.parties],
			terms: [...filters.terms]
		};
		const n = topN;
		clearTimeout(debounce);
		debounce = setTimeout(() => runQuery(f, n), 280);
	});

	async function runQuery(f: Filters, n: number) {
		if (!f.word.trim()) {
			total = null;
			timeline = [];
			byParty = [];
			top = [];
			return;
		}
		loading = true;
		queryError = null;
		// Settle independently so one failing view doesn't blank the others.
		const [tot, tl, bp, tp] = await Promise.allSettled([
			api.total(f),
			api.timeline(f),
			api.byParty(f),
			api.topPoliticians(f, n)
		]);
		if (tot.status === 'fulfilled') total = tot.value;
		if (tl.status === 'fulfilled') timeline = tl.value;
		if (bp.status === 'fulfilled') byParty = bp.value;
		if (tp.status === 'fulfilled') top = tp.value;
		const failed = [tot, tl, bp, tp].find((r) => r.status === 'rejected');
		queryError = failed ? (failed.reason as ApiError).message : null;
		loading = false;
	}

	// reflect the keyword in the URL for shareable links
	$effect(() => {
		const w = filters.word.trim();
		const url = new URL(page.url);
		if (w) url.searchParams.set('word', w);
		else url.searchParams.delete('word');
		replaceState(url, page.state);
	});

	// --- drill-down -----------------------------------------------------------
	let drill = $state<{ q: Filters; title: string } | null>(null);
	function pick(period: string, party: string) {
		const start = new Date(period);
		const end = new Date(start);
		end.setMonth(end.getMonth() + (filters.granularity === 'Monthly' ? 1 : 3));
		drill = {
			q: {
				...filters,
				parties: [party],
				date_from: period,
				date_to: end.toISOString().slice(0, 10)
			},
			title: `${party} · ${period.slice(0, 7)}`
		};
	}

	const partyBars = $derived(
		byParty
			.filter((d) => d.party !== 'Unknown')
			.map((d) => ({ label: d.party, value: d.speeches, color: partyColor(d.party) }))
	);
	const donutSlices = $derived(
		byParty
			.filter((d) => d.party !== 'Unknown')
			.slice(0, 8)
			.map((d) => ({ label: d.party, value: d.speeches, color: partyColor(d.party) }))
	);
	const topBars = $derived(
		top.map((d) => ({
			label: d.politician,
			sub: d.party,
			value: d.speeches,
			color: partyColor(d.party)
		}))
	);
</script>

<svelte:head><title>{filters.word} · OpenBundestag</title></svelte:head>

{#if !meta}
	<div class="boot wrap">
		{#if bootError}
			<h2>{i18n.t('error')}</h2>
			<p class="muted">{bootError}</p>
			<button class="btn" onclick={boot}>{i18n.t('retry')}</button>
		{:else}
			<div class="spinner"></div>
			<p class="muted">{i18n.t('waking')}</p>
		{/if}
	</div>
{:else}
	<div class="explore wrap">
		<aside class="sidebar card">
			<FilterPanel bind:filters {meta} />
		</aside>

		<div class="content">
			{#if !filters.word.trim()}
				<p class="empty">{i18n.t('enter_keyword')}</p>
			{:else if total && total.count === 0}
				<p class="empty">{i18n.t('no_results', { word: filters.word })}</p>
			{:else}
				<div class="metrics">
					<div class="metric">
						<span class="m-num">{total ? formatNumber(total.count, i18n.lang) : '—'}</span>
						<span class="m-cap">{i18n.t('metric_speeches')}</span>
					</div>
					<div class="metric">
						<span class="m-num">{formatDate(total?.min_date ?? null, i18n.lang)}</span>
						<span class="m-cap">{i18n.t('metric_first')}</span>
					</div>
					<div class="metric">
						<span class="m-num">{formatDate(total?.max_date ?? null, i18n.lang)}</span>
						<span class="m-cap">{i18n.t('metric_latest')}</span>
					</div>
					{#if loading}<div class="metric loading"><div class="spinner sm"></div></div>{/if}
				</div>

				<div class="tabs">
					<button class:on={tab === 'timeline'} onclick={() => (tab = 'timeline')}>
						{i18n.t('tab_timeline')}
					</button>
					<button class:on={tab === 'party'} onclick={() => (tab = 'party')}>
						{i18n.t('tab_party')}
					</button>
					<button class:on={tab === 'top'} onclick={() => (tab = 'top')}>
						{i18n.t('tab_top')}
					</button>
				</div>

				<div class="card panel-body">
					{#if queryError}
						<p class="empty">{queryError}</p>
					{:else if tab === 'timeline'}
						<div class="row-head">
							<label class="toggle">
								<input type="checkbox" bind:checked={stacked} />
								{i18n.t('stacked')}
							</label>
							<span class="hint">{i18n.t('drilldown_soon')}</span>
						</div>
						{#if timeline.length}
							<TimelineChart data={timeline} {stacked} {valueLabel} onpick={pick} />
						{:else}
							<p class="empty">{i18n.t('no_results', { word: filters.word })}</p>
						{/if}
					{:else if tab === 'party'}
						<div class="party-grid">
							<HBars bars={partyBars} valueLabel={i18n.t('speeches')} />
							<div>
								<h3 class="sub-h">{i18n.t('share')}</h3>
								<Donut slices={donutSlices} />
							</div>
						</div>
					{:else}
						<div class="row-head">
							<label class="slider">
								{i18n.t('top_n')}: {topN}
								<input type="range" min="5" max="30" bind:value={topN} />
							</label>
						</div>
						<HBars bars={topBars} valueLabel={i18n.t('speeches')} />
					{/if}
				</div>
			{/if}
		</div>
	</div>
{/if}

<SpeechDrawer query={drill?.q ?? null} title={drill?.title ?? ''} onclose={() => (drill = null)} />

<style>
	.boot {
		min-height: 60vh;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 1rem;
		text-align: center;
	}
	.muted {
		color: var(--ink-3);
	}
	.spinner {
		width: 40px;
		height: 40px;
		border: 3px solid var(--line);
		border-top-color: var(--accent);
		border-radius: 50%;
		animation: spin 0.8s linear infinite;
	}
	.spinner.sm {
		width: 18px;
		height: 18px;
		border-width: 2px;
	}
	@keyframes spin {
		to {
			transform: rotate(360deg);
		}
	}
	.explore {
		display: grid;
		grid-template-columns: 320px 1fr;
		gap: 1.6rem;
		padding-top: 1.8rem;
		padding-bottom: 2rem;
		align-items: start;
	}
	.sidebar {
		padding: 1.3rem;
		position: sticky;
		top: 80px;
	}
	.metrics {
		display: flex;
		gap: 1rem;
		flex-wrap: wrap;
		margin-bottom: 1.2rem;
	}
	.metric {
		background: var(--card);
		border: 1px solid var(--line);
		border-radius: var(--radius-sm);
		padding: 0.8rem 1.1rem;
		min-width: 140px;
	}
	.metric.loading {
		display: flex;
		align-items: center;
		justify-content: center;
		min-width: 60px;
	}
	.m-num {
		display: block;
		font-family: var(--serif);
		font-size: 1.7rem;
		font-weight: 600;
		line-height: 1.1;
	}
	.m-cap {
		font-size: 0.78rem;
		color: var(--ink-3);
	}
	.tabs {
		display: flex;
		gap: 0.3rem;
		margin-bottom: 0.9rem;
	}
	.tabs button {
		font: inherit;
		font-weight: 600;
		font-size: 0.92rem;
		padding: 0.55rem 1rem;
		border: none;
		background: none;
		color: var(--ink-3);
		border-radius: 999px;
		cursor: pointer;
	}
	.tabs button.on {
		background: var(--ink);
		color: var(--paper);
	}
	.panel-body {
		padding: 1.3rem;
	}
	.row-head {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 1rem;
		margin-bottom: 1rem;
		flex-wrap: wrap;
	}
	.toggle,
	.slider {
		font-size: 0.85rem;
		color: var(--ink-2);
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}
	.hint {
		font-size: 0.76rem;
		color: var(--ink-3);
	}
	.party-grid {
		display: grid;
		grid-template-columns: 1.4fr 1fr;
		gap: 2rem;
		align-items: center;
	}
	.sub-h {
		text-align: center;
		color: var(--ink-3);
		font-size: 0.95rem;
		margin-bottom: 0.5rem;
	}
	.empty {
		color: var(--ink-3);
		padding: 2rem 0;
		text-align: center;
	}
	@media (max-width: 900px) {
		.explore {
			grid-template-columns: 1fr;
		}
		.sidebar {
			position: static;
		}
		.party-grid {
			grid-template-columns: 1fr;
		}
	}
</style>

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
		Granularity,
		CountMode,
		TimelinePoint,
		PartyCount,
		TermCount,
		PoliticianCount,
		Totals
	} from '$lib/types';

	import FilterPanel from '$lib/components/FilterPanel.svelte';
	import TimelineChart from '$lib/components/TimelineChart.svelte';
	import HBars from '$lib/components/HBars.svelte';
	import Donut from '$lib/components/Donut.svelte';
	import Counter from '$lib/components/Counter.svelte';
	import SpeechModal from '$lib/components/SpeechModal.svelte';
	import SpeechTable from '$lib/components/SpeechTable.svelte';

	// --- bootstrap state ------------------------------------------------------
	let meta = $state<Meta | null>(null);
	let bootError = $state<string | null>(null);

	const sp = page.url.searchParams;
	const DEFAULTS: Filters = {
		word: sp.get('word') ?? 'Schuldenbremse',
		parties: sp.getAll('parties'),
		terms: sp.getAll('terms').map(Number).filter(Boolean),
		politician_id: sp.get('pol') ? Number(sp.get('pol')) : null,
		date_from: sp.get('from') ?? '2010-01-01',
		date_to: sp.get('to') ?? '2026-12-31',
		granularity: (sp.get('gran') as Granularity) ?? 'Monthly',
		count_mode: (sp.get('mode') as CountMode) ?? 'speeches'
	};
	let filters = $state<Filters>({ ...DEFAULTS });

	// --- result state ---------------------------------------------------------
	let total = $state<Totals | null>(null);
	let timeline = $state<TimelinePoint[]>([]);
	let byParty = $state<PartyCount[]>([]);
	let byTerm = $state<TermCount[]>([]);
	let top = $state<PoliticianCount[]>([]);
	let loading = $state(false);
	let queryError = $state<string | null>(null);

	let topN = $state(15);
	let viewMode = $state<'parties' | 'politicians'>('parties');

	async function boot() {
		bootError = null;
		try {
			const m = await api.meta();
			setPartyMeta(m.party_colors, m.party_full_names);
			meta = m;
		} catch (e) {
			const err = e as ApiError;
			bootError = err.status === 0 ? null : err.message;
			if (err.status === 0) {
				setTimeout(boot, 4000);
				return;
			}
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
		const f = { ...filters, parties: [...filters.parties], terms: [...filters.terms] };
		const n = topN;
		clearTimeout(debounce);
		debounce = setTimeout(() => runQuery(f, n), 280);
	});

	async function runQuery(f: Filters, n: number) {
		if (!f.word.trim()) {
			total = null;
			timeline = [];
			byParty = [];
			byTerm = [];
			top = [];
			return;
		}
		loading = true;
		queryError = null;
		const [tot, tl, bp, bt, tp] = await Promise.allSettled([
			api.total(f),
			api.timeline(f),
			api.byParty(f),
			api.byTerm(f),
			api.topPoliticians(f, n)
		]);
		if (tot.status === 'fulfilled') total = tot.value;
		if (tl.status === 'fulfilled') timeline = tl.value;
		if (bp.status === 'fulfilled') byParty = bp.value;
		if (bt.status === 'fulfilled') byTerm = bt.value;
		if (tp.status === 'fulfilled') top = tp.value;
		const failed = [tot, tl, bp, bt, tp].find((r) => r.status === 'rejected');
		queryError = failed ? (failed.reason as ApiError).message : null;
		loading = false;
	}

	// Encode full filter state in URL so searches are shareable
	$effect(() => {
		const f = filters;
		const url = new URL(page.url);
		if (f.word.trim()) url.searchParams.set('word', f.word.trim());
		else url.searchParams.delete('word');
		url.searchParams.delete('parties');
		for (const p of f.parties) url.searchParams.append('parties', p);
		url.searchParams.delete('terms');
		for (const t of f.terms) url.searchParams.append('terms', String(t));
		if (f.politician_id != null) url.searchParams.set('pol', String(f.politician_id));
		else url.searchParams.delete('pol');
		if (f.date_from && f.date_from !== '2010-01-01') url.searchParams.set('from', f.date_from);
		else url.searchParams.delete('from');
		if (f.date_to && f.date_to !== '2026-12-31') url.searchParams.set('to', f.date_to);
		else url.searchParams.delete('to');
		if (f.granularity !== 'Monthly') url.searchParams.set('gran', f.granularity);
		else url.searchParams.delete('gran');
		if (f.count_mode !== 'speeches') url.searchParams.set('mode', f.count_mode);
		else url.searchParams.delete('mode');
		replaceState(url, page.state);
	});

	// Cmd/Ctrl+K focuses the keyword input and opens filter sidebar on mobile
	function onkeydown(e: KeyboardEvent) {
		if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
			e.preventDefault();
			filtersOpen = true;
			setTimeout(() => document.getElementById('kw')?.focus(), 50);
		}
	}

	function reset() {
		filters = { ...DEFAULTS, word: filters.word };
		topN = 15;
	}

	// --- drill-down -----------------------------------------------------------
	let filtersOpen = $state(false);
	let flipped = $state(false);
	let drill = $state<{ q: Filters; title: string } | null>(null);
	function pick(period: string, party: string) {
		const start = new Date(period);
		const end = new Date(start);
		end.setMonth(end.getMonth() + (filters.granularity === 'Monthly' ? 1 : 3));
		drill = {
			q: { ...filters, parties: [party], date_from: period, date_to: end.toISOString().slice(0, 10) },
			title: `${party} · ${period.slice(0, 7)}`
		};
	}

	// --- derived views --------------------------------------------------------
	const cleanParties = $derived(
		byParty.filter((d) => d.party !== 'Unknown').sort((a, b) => b.speeches - a.speeches)
	);
	const leading = $derived(cleanParties[0] ?? null);
	const partyBars = $derived(
		cleanParties.map((d) => ({ label: d.party, value: d.speeches, color: partyColor(d.party) }))
	);
	const donutSlices = $derived(
		cleanParties.slice(0, 8).map((d) => ({ label: d.party, value: d.speeches, color: partyColor(d.party) }))
	);
	const topBars = $derived(
		top.map((d) => ({
			label: d.politician,
			sub: d.party,
			value: d.speeches,
			color: partyColor(d.party)
		}))
	);

	const termBars = $derived(
		byTerm.map((tc) => {
			const label = meta?.terms.find((t) => t.term === tc.term)?.label ?? '';
			const years = label.match(/\((.+?)\)/)?.[1] ?? '';
			return { label: `WP ${tc.term}`, sub: years, value: tc.speeches, color: 'var(--accent)' };
		})
	);

	const hasResults = $derived(!!total && total.count > 0);
</script>

<svelte:head><title>{filters.word} · OpenBundestag</title></svelte:head>
<svelte:window {onkeydown} />

{#if !meta}
	<div class="boot wrap">
		{#if bootError}
			<h2>{i18n.t('error')}</h2>
			<p class="muted">{bootError}</p>
			<button class="btn" onclick={boot}>{i18n.t('retry')}</button>
		{:else}
			<div class="orb"></div>
			<p class="muted">{i18n.t('waking')}</p>
		{/if}
	</div>
{:else}
	<div class="explore wrap">
		<button class="filter-toggle" onclick={() => (filtersOpen = !filtersOpen)} aria-expanded={filtersOpen}>
			<svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
				<path d="M2 4h12M4 8h8M6 12h4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
			</svg>
			{i18n.t('filters')}
			{#if filters.parties.length || filters.politician_id}
				<span class="filter-badge">{filters.parties.length + (filters.politician_id ? 1 : 0)}</span>
			{/if}
		</button>

		<aside class="sidebar glass" class:open={filtersOpen}>
			<div class="rail-head">
				<span class="eyebrow">{i18n.t('filters')}</span>
				<button class="reset" onclick={reset}>{i18n.t('reset')}</button>
			</div>
			<FilterPanel bind:filters {meta} bind:viewMode />
		</aside>

		<div class="content">
			{#if !filters.word.trim()}
				<div class="empty-state glass">
					<svg class="empty-icon" width="52" height="52" viewBox="0 0 52 52" fill="none" aria-hidden="true">
						<rect x="20" y="4" width="12" height="24" rx="6" stroke="var(--accent)" stroke-width="2"/>
						<path d="M10 26c0 8.837 7.163 16 16 16s16-7.163 16-16" stroke="var(--accent)" stroke-width="2" stroke-linecap="round"/>
						<line x1="26" y1="42" x2="26" y2="50" stroke="var(--accent)" stroke-width="2" stroke-linecap="round"/>
						<line x1="16" y1="50" x2="36" y2="50" stroke="var(--accent)" stroke-width="2" stroke-linecap="round"/>
						<line x1="24" y1="12" x2="28" y2="12" stroke="var(--accent)" stroke-width="1.5" stroke-linecap="round" opacity="0.5"/>
						<line x1="24" y1="17" x2="28" y2="17" stroke="var(--accent)" stroke-width="1.5" stroke-linecap="round" opacity="0.5"/>
						<line x1="24" y1="22" x2="28" y2="22" stroke="var(--accent)" stroke-width="1.5" stroke-linecap="round" opacity="0.5"/>
					</svg>
					<p>{i18n.t('enter_keyword')}</p>
				</div>
			{:else if total && total.count === 0}
				<div class="empty-state glass">
					<p>{i18n.t('no_results', { word: filters.word })}</p>
				</div>
			{:else}
				<!-- Headline -->
				<div class="headline">
					<span class="eyebrow">{i18n.t('overview')}</span>
					<h1 class="kw grad-text">„{filters.word}"</h1>
					{#if loading}<span class="live"><span class="pulse"></span></span>{/if}
				</div>

				<!-- Metric strip -->
				<div class="metrics">
					<div class="metric glass">
						<span class="m-num">{#if total}<Counter value={total.count} />{:else}—{/if}</span>
						<span class="m-cap">{i18n.t('metric_speeches')}</span>
					</div>
					<div class="metric glass">
						<span class="m-num small">{formatDate(total?.min_date ?? null, i18n.lang)}</span>
						<span class="m-cap">{i18n.t('metric_first')}</span>
					</div>
					<div class="metric glass">
						<span class="m-num small">{formatDate(total?.max_date ?? null, i18n.lang)}</span>
						<span class="m-cap">{i18n.t('metric_latest')}</span>
					</div>
					<div class="metric glass" style:--lc={leading ? partyColor(leading.party) : 'var(--ink-3)'}>
						<span class="m-num small lead">
							{#if leading}<span class="lead-dot"></span>{leading.party}{:else}—{/if}
						</span>
						<span class="m-cap">{i18n.t('leading_party')}</span>
					</div>
				</div>

				{#if queryError}
					<div class="empty-state glass"><p class="err">{queryError}</p></div>
				{:else}
					<!-- Timeline hero with flip to speech list -->
					<div class="hero-wrap">
						<!-- Tab switcher — lives outside the 3D transform, always readable -->
						<div class="view-tabs">
							<button class="view-tab" class:active={!flipped} onclick={() => (flipped = false)}>
								<svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true"><polyline points="1,11 4,5 7,8 10,3 13,6" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" fill="none"/></svg>
								{i18n.t('flip_to_chart')}
							</button>
							<button class="view-tab" class:active={flipped} onclick={() => (flipped = true)}>
								<svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true"><rect x="1" y="2" width="12" height="2" rx="1" fill="currentColor"/><rect x="1" y="6" width="8" height="2" rx="1" fill="currentColor"/><rect x="1" y="10" width="10" height="2" rx="1" fill="currentColor"/></svg>
								{i18n.t('flip_to_list')}
							</button>
						</div>

						<div class="flip-container">
							<div class="flip-inner" class:flipped>
								<!-- Front: timeline chart -->
								<section class="panel hero-panel flip-face flip-front solid">
									<header class="p-head">
										<div>
											<h3>{i18n.t('timeline_over_time')}</h3>
											<p class="p-hint">{i18n.t('drilldown_hint')}</p>
										</div>
									</header>
									{#if timeline.length}
										<TimelineChart
											data={timeline}
											{valueLabel}
											selectedParties={filters.parties}
											ontoggleparty={(p) => {
												filters.parties = filters.parties.includes(p)
													? filters.parties.filter((x) => x !== p)
													: [...filters.parties, p];
											}}
											onpick={pick}
										/>
									{:else}
										<p class="empty">{i18n.t('no_results', { word: filters.word })}</p>
									{/if}
								</section>
								<!-- Back: speech list -->
								<section class="panel hero-panel flip-face flip-back solid">
									<header class="p-head">
										<div>
											<h3>{i18n.t('flip_to_list')}</h3>
											<p class="p-hint">{i18n.t('matching_speeches')}</p>
										</div>
									</header>
									<SpeechTable {filters} />
								</section>
							</div>
						</div>
					</div>

					<!-- Bottom panel: switches content based on viewMode -->
					{#if viewMode === 'parties'}
						<section class="panel glass">
							<header class="p-head"><h3>{i18n.t('by_party_title')}</h3></header>
							{#if partyBars.length}
								<div class="party-body">
									<Donut slices={donutSlices} />
									<HBars bars={partyBars} valueLabel={i18n.t('speeches')} />
								</div>
								{#if termBars.length}
									<div class="term-section">
										<span class="term-label">{i18n.t('by_term_title')}</span>
										<HBars bars={termBars} valueLabel={i18n.t('speeches')} />
									</div>
								{/if}
							{:else}
								<p class="empty">—</p>
							{/if}
						</section>
					{:else}
						<section class="panel glass">
							<header class="p-head">
								<h3>{i18n.t('top_speakers_title')}</h3>
								{#if filters.politician_id == null}
									<label class="slider">
										{i18n.t('top_n')}: <strong>{topN}</strong>
										<input type="range" min="5" max="30" bind:value={topN} />
									</label>
								{/if}
							</header>
							{#if topBars.length}
								<HBars bars={topBars} valueLabel={i18n.t('speeches')} />
							{:else}
								<p class="empty">—</p>
							{/if}
						</section>
					{/if}
				{/if}
			{/if}
		</div>
	</div>
{/if}

<SpeechModal
	query={drill?.q ?? null}
	title={drill?.title ?? ''}
	word={filters.word}
	onclose={() => (drill = null)}
/>

<style>
	.boot {
		min-height: 64vh;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 1.2rem;
		text-align: center;
	}
	.muted {
		color: var(--ink-3);
	}
	/* Aurora orb loader */
	.orb {
		width: 64px;
		height: 64px;
		border-radius: 50%;
		background: var(--grad);
		filter: blur(2px);
		animation:
			orb 1.6s var(--ease) infinite,
			spin 3s linear infinite;
		box-shadow: var(--glow);
	}
	.orb.sm {
		width: 40px;
		height: 40px;
	}
	@keyframes orb {
		0%,
		100% {
			transform: scale(1);
			opacity: 0.9;
		}
		50% {
			transform: scale(0.7);
			opacity: 0.5;
		}
	}
	@keyframes spin {
		to {
			transform: rotate(360deg);
		}
	}

	.filter-toggle {
		display: none;
	}
	.explore {
		display: grid;
		grid-template-columns: 304px 1fr;
		gap: 1.6rem;
		padding-top: 1.8rem;
		padding-bottom: 3rem;
		align-items: start;
	}
	.sidebar {
		padding: 1.3rem;
		position: sticky;
		top: 84px;
	}
	.rail-head {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 1.2rem;
	}

	@media (max-width: 768px) {
		.filter-toggle {
			display: flex;
			align-items: center;
			gap: 0.5rem;
			font: inherit;
			font-size: 0.85rem;
			font-weight: 600;
			padding: 0.55rem 1rem;
			border: 1px solid var(--line-2);
			border-radius: 999px;
			background: var(--surface);
			color: var(--ink-2);
			cursor: pointer;
			margin-bottom: 0.5rem;
		}
		.filter-badge {
			background: var(--accent);
			color: #fff;
			border-radius: 999px;
			font-size: 0.7rem;
			font-weight: 700;
			padding: 0.1rem 0.45rem;
			line-height: 1.4;
		}
		.explore {
			grid-template-columns: 1fr;
			padding-top: 1rem;
			gap: 1rem;
		}
		.sidebar {
			position: static;
			display: none;
		}
		.sidebar.open {
			display: block;
		}
		.metrics {
			grid-template-columns: repeat(2, 1fr);
		}
	}
	.reset {
		font: inherit;
		font-size: 0.74rem;
		font-weight: 600;
		letter-spacing: 0.04em;
		color: var(--ink-3);
		background: none;
		border: 1px solid var(--line-2);
		border-radius: 999px;
		padding: 0.25rem 0.7rem;
		cursor: pointer;
		transition:
			color 0.2s,
			border-color 0.2s;
	}
	.reset:hover {
		color: var(--ink);
		border-color: var(--line-3);
	}

	.content {
		display: flex;
		flex-direction: column;
		gap: 1.4rem;
		min-width: 0;
	}

	.headline {
		display: flex;
		align-items: baseline;
		gap: 1rem;
		flex-wrap: wrap;
	}
	.headline .eyebrow {
		order: -1;
		width: 100%;
		margin-bottom: -0.4rem;
	}
	.kw {
		font-size: clamp(2.4rem, 5vw, 3.6rem);
		margin: 0;
		line-height: 1;
	}
	.live {
		display: inline-flex;
		align-items: center;
	}
	.pulse {
		width: 10px;
		height: 10px;
		border-radius: 50%;
		background: var(--accent);
		box-shadow: 0 0 0 0 rgba(107, 145, 255, 0.6);
		animation: pulse 1.4s var(--ease) infinite;
	}
	@keyframes pulse {
		0% {
			box-shadow: 0 0 0 0 rgba(107, 145, 255, 0.55);
		}
		70% {
			box-shadow: 0 0 0 10px rgba(107, 145, 255, 0);
		}
		100% {
			box-shadow: 0 0 0 0 rgba(107, 145, 255, 0);
		}
	}

	.metrics {
		display: grid;
		grid-template-columns: repeat(4, 1fr);
		gap: 0.9rem;
	}
	.metric {
		padding: 1rem 1.1rem;
		position: relative;
		overflow: hidden;
		transition:
			transform 0.3s var(--spring),
			border-color 0.3s;
	}
	.metric::before {
		content: '';
		position: absolute;
		inset: 0 0 auto 0;
		height: 2px;
		background: var(--grad);
		opacity: 0.7;
	}
	.metric:hover {
		transform: translateY(-3px);
		border-color: var(--line-2);
	}
	.m-num {
		display: block;
		font-family: var(--display);
		font-size: 2rem;
		font-weight: 600;
		line-height: 1.05;
		letter-spacing: -0.02em;
	}
	.m-num.small {
		font-size: 1.25rem;
	}
	.m-num.lead {
		display: flex;
		align-items: center;
		gap: 0.45rem;
	}
	.lead-dot {
		width: 11px;
		height: 11px;
		border-radius: 50%;
		background: var(--lc);
		box-shadow: 0 0 12px -1px var(--lc);
		flex: none;
	}
	.m-cap {
		font-size: 0.76rem;
		color: var(--ink-3);
		margin-top: 0.35rem;
		display: block;
	}

	/* ---------- card flip ---------- */
	.hero-wrap {
		display: flex;
		flex-direction: column;
		gap: 0;
	}

	/* Segmented tab control above the flip */
	.view-tabs {
		display: inline-flex;
		align-self: flex-start;
		background: var(--surface-2);
		border: 1px solid var(--line-2);
		border-radius: 999px;
		padding: 3px;
		gap: 2px;
		margin-bottom: 0.75rem;
	}
	.view-tab {
		display: inline-flex;
		align-items: center;
		gap: 0.45rem;
		font: inherit;
		font-size: 0.85rem;
		font-weight: 600;
		padding: 0.5rem 1.15rem;
		border: none;
		border-radius: 999px;
		background: transparent;
		color: var(--ink-3);
		cursor: pointer;
		transition: background 0.2s, color 0.2s, box-shadow 0.2s;
		white-space: nowrap;
	}
	.view-tab:hover:not(.active) {
		color: var(--ink-2);
		background: var(--surface-3);
	}
	.view-tab.active {
		background: var(--surface);
		color: var(--ink);
		box-shadow: 0 1px 4px rgba(0, 0, 0, 0.4);
	}
	/* aurora accent stripe on active tab */
	.view-tab.active svg {
		filter: drop-shadow(0 0 4px var(--accent));
		color: var(--accent);
	}

	.flip-container {
		perspective: 1400px;
	}
	.flip-inner {
		position: relative;
		transform-style: preserve-3d;
		transition: transform 0.65s cubic-bezier(0.4, 0.2, 0.2, 1);
	}
	.flip-inner.flipped {
		transform: rotateY(180deg);
	}
	.flip-face {
		backface-visibility: hidden;
		-webkit-backface-visibility: hidden;
	}
	.flip-back {
		position: absolute;
		inset: 0;
		transform: rotateY(180deg);
		overflow-y: auto;
	}

	.panel {
		padding: 1.4rem 1.5rem;
	}
	/* Hero panels: fully opaque so content is legible */
	.panel.solid {
		background: var(--surface);
		backdrop-filter: none;
		border-color: var(--line-2);
	}
	.p-head {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		gap: 1rem;
		margin-bottom: 1.1rem;
		flex-wrap: wrap;
	}
	.p-head h3 {
		margin: 0;
	}
	.p-hint {
		margin: 0.3rem 0 0;
		font-size: 0.8rem;
		color: var(--ink-3);
	}

	/* iOS-style toggle */
	.toggle {
		display: inline-flex;
		align-items: center;
		gap: 0.5rem;
		font-size: 0.82rem;
		color: var(--ink-2);
		cursor: pointer;
		user-select: none;
	}
	.toggle input {
		position: absolute;
		opacity: 0;
		pointer-events: none;
	}
	.track {
		width: 38px;
		height: 22px;
		border-radius: 999px;
		background: var(--surface-3);
		border: 1px solid var(--line-2);
		position: relative;
		transition: background 0.25s;
	}
	.knob {
		position: absolute;
		top: 2px;
		left: 2px;
		width: 16px;
		height: 16px;
		border-radius: 50%;
		background: var(--ink-2);
		transition:
			transform 0.28s var(--spring),
			background 0.25s;
	}
	.toggle input:checked + .track {
		background: var(--grad);
		border-color: transparent;
	}
	.toggle input:checked + .track .knob {
		transform: translateX(16px);
		background: #fff;
	}

	.slider {
		display: flex;
		align-items: center;
		gap: 0.55rem;
		font-size: 0.82rem;
		color: var(--ink-2);
	}
	.slider input[type='range'] {
		accent-color: var(--accent);
		width: 110px;
	}

	.party-body {
		display: grid;
		grid-template-columns: 200px 1fr;
		gap: 1.5rem;
		align-items: center;
	}
	.term-section {
		margin-top: 1.4rem;
		padding-top: 1.2rem;
		border-top: 1px solid var(--line);
	}
	.term-label {
		display: block;
		font-size: 0.78rem;
		font-weight: 600;
		letter-spacing: 0.06em;
		text-transform: uppercase;
		color: var(--ink-3);
		margin-bottom: 0.75rem;
	}

	.empty,
	.err {
		color: var(--ink-3);
		padding: 2rem 0;
		text-align: center;
	}
	.err {
		color: var(--spark);
	}
	.empty-state {
		padding: 4rem 2rem;
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 1.2rem;
		color: var(--ink-3);
		text-align: center;
	}

	@media (max-width: 980px) {
		.explore {
			grid-template-columns: 1fr;
		}
		.sidebar {
			position: static;
		}
		.metrics {
			grid-template-columns: repeat(2, 1fr);
		}
		.party-body {
			grid-template-columns: 1fr;
		}
	}
	@media (max-width: 520px) {
		.metrics {
			grid-template-columns: 1fr;
		}
	}
</style>

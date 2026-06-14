<script lang="ts">
	import { page } from '$app/state';
	import { replaceState } from '$app/navigation';
	import { api, ApiError } from '$lib/api';
	import { setPartyMeta } from '$lib/format';
	import { i18n } from '$lib/i18n.svelte';
	import { formatDate, partyColor } from '$lib/format';
	import governmentsRaw from '$lib/governments.json';
	import type {
		Meta,
		Filters,
		CountMode,
		TimelinePoint,
		PartyCount,
		TermCount,
		PoliticianCount,
		Totals,
		Politician
	} from '$lib/types';

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
		politician_id: null,
		date_from: null,
		date_to: null,
		granularity: 'Quarterly',
		count_mode: (sp.get('mode') as CountMode) ?? 'occurrences'
	};
	let filters = $state<Filters>({ ...DEFAULTS });

	// Politician filter — scopes only the timeline and speech list, not the party/speaker panels
	let polId = $state<number | null>(sp.get('pol') ? Number(sp.get('pol')) : null);
	let polQuery = $state(sp.get('pol') ? '…' : '');
	let polResults = $state<Politician[]>([]);
	let polOpen = $state(false);
	let polTimer: ReturnType<typeof setTimeout>;

	function onPolInput(v: string) {
		polQuery = v;
		polOpen = true;
		if (!v.trim()) { polId = null; }
		clearTimeout(polTimer);
		polTimer = setTimeout(async () => {
			polResults = v.trim() ? await api.politicians(v.trim(), 8).catch(() => []) : [];
		}, 200);
	}
	function pickPol(p: Politician) {
		polId = p.id;
		polQuery = p.name;
		polOpen = false;
		polResults = [];
	}
	function clearPol() {
		polId = null;
		polQuery = '';
		polResults = [];
		polOpen = false;
	}

	$effect(() => {
		if (polId != null && polQuery === '…') {
			api.politicians('', 1).catch(() => []);
			polQuery = `#${polId}`;
		}
	});

	// --- result state ---------------------------------------------------------
	let total = $state<Totals | null>(null);
	let timeline = $state<TimelinePoint[]>([]);
	let byParty = $state<PartyCount[]>([]);
	let byTerm = $state<TermCount[]>([]);
	let top = $state<PoliticianCount[]>([]);
	let loading = $state(false);
	let queryError = $state<string | null>(null);

	let topN = $state(15);

	async function boot() {
		bootError = null;
		try {
			const m = await api.meta();
			setPartyMeta(m.party_colors, m.party_full_names);
			meta = m;
			// Default to current legislature if no terms were provided via URL
			if (filters.terms.length === 0) {
				const latestTerm = Math.max(...m.terms.map((t) => t.term));
				filters.terms = [latestTerm];
			}
		} catch (e) {
			const err = e as ApiError;
			bootError = err.status === 0 ? null : err.message;
			if (err.status === 0) {
				setTimeout(boot, 4000);
				return;
			}
		}
	}
	$effect(() => { boot(); });

	const valueLabel = $derived(
		filters.count_mode === 'speeches' ? i18n.t('speeches') : i18n.t('occurrences')
	);

	// --- debounced query whenever filters or polId change --------------------
	let debounce: ReturnType<typeof setTimeout>;
	$effect(() => {
		if (!meta) return;
		const f = { ...filters, parties: [...filters.parties], terms: [...filters.terms] };
		const pid = polId;
		const n = topN;
		clearTimeout(debounce);
		debounce = setTimeout(() => runQuery(f, pid, n), 280);
	});

	async function runQuery(f: Filters, pid: number | null, n: number) {
		if (!f.word.trim()) {
			total = null; timeline = []; byParty = []; byTerm = []; top = [];
			return;
		}
		loading = true;
		queryError = null;
		const pf = { ...f, politician_id: pid };
		const [tot, tl, bp, bt, tp] = await Promise.allSettled([
			api.total(pf),
			api.timeline(pf),
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

	// Encode filter state + polId in URL for shareability
	$effect(() => {
		const f = filters;
		const url = new URL(page.url);
		if (f.word.trim()) url.searchParams.set('word', f.word.trim());
		else url.searchParams.delete('word');
		url.searchParams.delete('parties');
		for (const p of f.parties) url.searchParams.append('parties', p);
		url.searchParams.delete('terms');
		for (const t of f.terms) url.searchParams.append('terms', String(t));
		if (polId != null) url.searchParams.set('pol', String(polId));
		else url.searchParams.delete('pol');
		// Legacy date params no longer used — clean them up
		url.searchParams.delete('from');
		url.searchParams.delete('to');
		url.searchParams.delete('gran');
		if (f.count_mode !== 'occurrences') url.searchParams.set('mode', f.count_mode);
		else url.searchParams.delete('mode');
		replaceState(url, page.state);
	});

	function onkeydown(e: KeyboardEvent) {
		if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
			e.preventDefault();
			document.getElementById('kw')?.focus();
		}
	}

	function reset() {
		const latestTerm = meta ? Math.max(...meta.terms.map((t) => t.term)) : 20;
		filters = { ...DEFAULTS, word: filters.word, terms: [latestTerm] };
		clearPol();
		topN = 15;
	}

	function toggleTerm(term: number) {
		if (filters.terms.includes(term)) {
			filters.terms = filters.terms.filter((t) => t !== term);
		} else {
			filters.terms = [...filters.terms, term].sort((a, b) => a - b);
		}
	}

	// --- drill-down -----------------------------------------------------------
	let flipped = $state(false);
	let drill = $state<{ q: Filters; title: string } | null>(null);
	function pick(period: string, party: string) {
		const start = new Date(period);
		const end = new Date(start);
		end.setMonth(end.getMonth() + 3);
		drill = {
			q: { ...filters, politician_id: polId, parties: [party], date_from: period, date_to: end.toISOString().slice(0, 10) },
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
			const years2 = label.match(/\((.+?)\)/)?.[1] ?? '';
			return { label: `WP ${tc.term}`, sub: years2, value: tc.speeches, color: 'var(--accent)' };
		})
	);

	const speechFilters = $derived({ ...filters, politician_id: polId });

	// Terms sorted newest-first for the chip row
	const sortedTerms = $derived(
		meta ? [...meta.terms].sort((a, b) => b.term - a.term) : []
	);

	// --- chancellor lookup for term chips -------------------------------------
	function govPartyToDisplay(code: string): string {
		if (code === 'CDU' || code === 'CSU') return 'CDU/CSU';
		if (code === 'Grüne') return 'Bündnis 90/Die Grünen';
		return code;
	}
	function shortChancellor(name: string): string {
		const parts = name.split(' ');
		return parts[parts.length - 1];
	}
	const termChancellors = $derived.by(() => {
		const result: Record<number, { name: string; party: string }> = {};
		for (const t of (meta?.terms ?? [])) {
			const m = t.label.match(/\((\d{4})/);
			if (!m) continue;
			const approxStart = new Date(`${m[1]}-10-01`);
			const gov = governmentsRaw.find((g) => {
				const gStart = new Date(g.start);
				const gEnd = g.end ? new Date(g.end) : new Date('2099-01-01');
				return gStart <= approxStart && gEnd >= approxStart;
			});
			if (gov) result[t.term] = { name: gov.chancellor, party: govPartyToDisplay(gov.parties[0]) };
		}
		return result;
	});
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

		<!-- ── Filter bar ─────────────────────────────────────────────────── -->
		<div class="filter-bar glass">
			<!-- Search hero — large and central -->
			<div class="search-hero">
				<div class="search-input-wrap">
					<svg class="search-icon" width="18" height="18" viewBox="0 0 16 16" fill="none" aria-hidden="true">
						<circle cx="6.5" cy="6.5" r="4.5" stroke="currentColor" stroke-width="1.5"/>
						<line x1="10" y1="10" x2="14" y2="14" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
					</svg>
					<input
						id="kw"
						class="search-input"
						bind:value={filters.word}
						maxlength={meta.keyword_max_len}
						placeholder={i18n.t('keyword_ph')}
						autocomplete="off"
					/>
					{#if loading}<span class="pulse"></span>{/if}
				</div>
				<button class="reset-btn" onclick={reset}>{i18n.t('reset')}</button>
			</div>

			<!-- Suggestions -->
			<div class="suggestions">
				{#each ['Schuldenbremse', 'Klimawandel', 'Migration', 'Digitalisierung', 'Rente', 'Ukraine'] as w (w)}
					<button class="suggestion" class:active={filters.word === w} onclick={() => (filters.word = w)}>{w}</button>
				{/each}
			</div>

			<!-- Wahlperioden term chips -->
			<div class="term-row">
				<div class="term-row-head">
					<span class="term-row-lbl">Wahlperiode</span>
					{#if filters.terms.length > 0}
						<button class="term-clear" onclick={() => (filters.terms = [])}>Alle anzeigen</button>
					{/if}
				</div>
				<div class="term-scroller">
					<button
						class="term-chip all-chip"
						class:active={filters.terms.length === 0}
						onclick={() => (filters.terms = [])}
					>
						<span class="chip-stripe" style="background: var(--grad)"></span>
						<span class="chip-body">
							<span class="chip-era">WP</span>
							<span class="chip-num">Alle</span>
							<span class="chip-years">1949–heute</span>
						</span>
					</button>
					{#each sortedTerms as t (t.term)}
						{@const years = t.label.match(/\((.+?)\)/)?.[1] ?? ''}
						{@const ch = termChancellors[t.term]}
						{@const chipColor = ch ? partyColor(ch.party) : 'var(--line-2)'}
						<button
							class="term-chip"
							class:active={filters.terms.includes(t.term)}
							onclick={() => toggleTerm(t.term)}
							title={t.label + (ch ? ' · ' + ch.name : '')}
							style="--chip-color: {chipColor}"
						>
							<span class="chip-stripe"></span>
							<span class="chip-body">
								<span class="chip-era">WP</span>
								<span class="chip-num">{t.term}</span>
								<span class="chip-years">{years}</span>
								{#if ch}
									<span class="chip-chancellor">
										<span class="chip-dot"></span>{shortChancellor(ch.name)}
									</span>
								{/if}
							</span>
						</button>
					{/each}
				</div>
			</div>

			<!-- Count mode -->
			<div class="controls-row">
				<div class="ctrl-group">
					<span class="ctrl-lbl">{i18n.t('count_by')}</span>
					<div class="seg">
						<button class:on={filters.count_mode === 'speeches'} onclick={() => (filters.count_mode = 'speeches')}>
							{i18n.t('speeches')}
						</button>
						<button class:on={filters.count_mode === 'occurrences'} onclick={() => (filters.count_mode = 'occurrences')}>
							{i18n.t('occurrences')}
						</button>
					</div>
				</div>
			</div>
		</div>

		<!-- ── Main content ──────────────────────────────────────────────── -->
		<div class="content">
			{#if !filters.word.trim()}
				<div class="empty-state glass">
					<svg class="empty-icon" width="52" height="52" viewBox="0 0 52 52" fill="none" aria-hidden="true">
						<rect x="20" y="4" width="12" height="24" rx="6" stroke="var(--accent)" stroke-width="2"/>
						<path d="M10 26c0 8.837 7.163 16 16 16s16-7.163 16-16" stroke="var(--accent)" stroke-width="2" stroke-linecap="round"/>
						<line x1="26" y1="42" x2="26" y2="50" stroke="var(--accent)" stroke-width="2" stroke-linecap="round"/>
						<line x1="16" y1="50" x2="36" y2="50" stroke="var(--accent)" stroke-width="2" stroke-linecap="round"/>
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
						<div class="hero-controls">
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
										<!-- Politician filter: scopes timeline + speech list only -->
										<div class="pol-picker" class:has-value={polId != null}>
											<svg width="13" height="13" viewBox="0 0 13 13" fill="none" aria-hidden="true" class="pol-icon">
												<circle cx="6.5" cy="4" r="2.3" stroke="currentColor" stroke-width="1.4"/>
												<path d="M1.5 11.5c0-2.761 2.239-5 5-5s5 2.239 5 5" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/>
											</svg>
											<div class="pol-input-wrap">
												<input
													class="pol-input"
													value={polQuery}
													oninput={(e) => onPolInput(e.currentTarget.value)}
													onfocus={() => (polOpen = true)}
													onblur={() => setTimeout(() => (polOpen = false), 150)}
													placeholder={i18n.t('any_politician')}
													autocomplete="off"
												/>
												{#if polId != null}
													<button class="pol-clr" onclick={clearPol} aria-label="clear">✕</button>
												{/if}
												{#if polOpen && polResults.length}
													<ul class="pol-dropdown">
														{#each polResults as p (p.id)}
															<li>
																<button onmousedown={() => pickPol(p)}>
																	<span class="pol-dot" style:background={partyColor(p.party)}></span>
																	{p.name}<span class="pol-party"> · {p.party}</span>
																</button>
															</li>
														{/each}
													</ul>
												{/if}
											</div>
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
									<SpeechTable filters={speechFilters} />
								</section>
							</div>
						</div>
					</div>

					<!-- Party + speakers -->
					<div class="grid-2">
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

						<section class="panel glass">
							<header class="p-head">
								<h3>{i18n.t('top_speakers_title')}</h3>
								<label class="slider">
									{i18n.t('top_n')}: <strong>{topN}</strong>
									<input type="range" min="5" max="30" bind:value={topN} />
								</label>
							</header>
							{#if topBars.length}
								<HBars bars={topBars} valueLabel={i18n.t('speeches')} />
							{:else}
								<p class="empty">—</p>
							{/if}
						</section>
					</div>
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
	.muted { color: var(--ink-3); }
	.orb {
		width: 64px; height: 64px;
		border-radius: 50%;
		background: var(--grad);
		filter: blur(2px);
		animation: orb 1.6s var(--ease) infinite, spin 3s linear infinite;
		box-shadow: var(--glow);
	}
	@keyframes orb {
		0%, 100% { transform: scale(1); opacity: 0.9; }
		50% { transform: scale(0.7); opacity: 0.5; }
	}
	@keyframes spin { to { transform: rotate(360deg); } }

	/* ── Layout ────────────────────────────────────────────────────────── */
	.explore {
		display: flex;
		flex-direction: column;
		gap: 1.4rem;
		padding-top: 1.8rem;
		padding-bottom: 3rem;
	}

	/* ── Filter bar ────────────────────────────────────────────────────── */
	.filter-bar {
		padding: 1.4rem 1.5rem 1.1rem;
		display: flex;
		flex-direction: column;
		gap: 0.85rem;
	}

	/* Search hero — large, prominent, full-width */
	.search-hero {
		display: flex;
		align-items: center;
		gap: 0.75rem;
	}
	.search-input-wrap {
		flex: 1;
		display: flex;
		align-items: center;
		gap: 0.7rem;
		background: var(--surface-2);
		border: 1px solid var(--line-2);
		border-radius: var(--radius-sm);
		padding: 0.75rem 1.1rem;
		transition: border-color 0.2s, box-shadow 0.2s;
	}
	.search-input-wrap:focus-within {
		border-color: var(--accent);
		box-shadow: 0 0 0 3px color-mix(in srgb, var(--accent) 15%, transparent);
	}
	.search-icon { color: var(--ink-3); flex-shrink: 0; }
	.search-input {
		flex: 1;
		font: inherit;
		font-size: 1.2rem;
		font-weight: 500;
		background: none;
		border: none;
		outline: none;
		color: var(--ink);
		min-width: 0;
	}
	.search-input::placeholder { color: var(--ink-3); }

	.pulse {
		width: 8px; height: 8px;
		border-radius: 50%;
		background: var(--accent);
		flex-shrink: 0;
		box-shadow: 0 0 0 0 rgba(107, 145, 255, 0.6);
		animation: pulse 1.4s var(--ease) infinite;
	}
	@keyframes pulse {
		0% { box-shadow: 0 0 0 0 rgba(107, 145, 255, 0.55); }
		70% { box-shadow: 0 0 0 8px rgba(107, 145, 255, 0); }
		100% { box-shadow: 0 0 0 0 rgba(107, 145, 255, 0); }
	}

	.reset-btn {
		font: inherit;
		font-size: 0.78rem;
		font-weight: 600;
		letter-spacing: 0.04em;
		color: var(--ink-3);
		background: none;
		border: 1px solid var(--line-2);
		border-radius: 999px;
		padding: 0.45rem 0.95rem;
		cursor: pointer;
		white-space: nowrap;
		transition: color 0.2s, border-color 0.2s;
	}
	.reset-btn:hover { color: var(--ink); border-color: var(--line-3); }

	.suggestions {
		display: flex;
		flex-wrap: wrap;
		gap: 0.35rem;
	}
	.suggestion {
		font: inherit;
		font-size: 0.76rem;
		padding: 0.2rem 0.65rem;
		border-radius: 999px;
		border: 1px solid var(--line-2);
		background: none;
		color: var(--ink-3);
		cursor: pointer;
		transition: color 0.15s, border-color 0.15s, background 0.15s;
	}
	.suggestion:hover { color: var(--accent); border-color: var(--accent); }
	.suggestion.active {
		color: var(--accent);
		border-color: var(--accent);
		background: color-mix(in srgb, var(--accent) 10%, transparent);
	}

	/* ── Wahlperioden chips ─────────────────────────────────────────────── */
	.term-row {
		display: flex;
		flex-direction: column;
		gap: 0.6rem;
		padding-top: 0.75rem;
		border-top: 1px solid var(--line);
	}
	.term-row-head {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.5rem;
	}
	.term-row-lbl {
		font-size: 0.72rem;
		font-weight: 600;
		letter-spacing: 0.06em;
		text-transform: uppercase;
		color: var(--ink-3);
	}
	.term-clear {
		font: inherit;
		font-size: 0.68rem;
		color: var(--accent);
		background: none;
		border: none;
		cursor: pointer;
		padding: 0;
		opacity: 0.8;
		transition: opacity 0.15s;
	}
	.term-clear:hover { opacity: 1; }
	.term-scroller {
		display: flex;
		gap: 0.4rem;
		overflow-x: auto;
		padding-bottom: 4px;
		scrollbar-width: thin;
		scrollbar-color: var(--line-2) transparent;
	}
	.term-scroller::-webkit-scrollbar { height: 3px; }
	.term-scroller::-webkit-scrollbar-track { background: transparent; }
	.term-scroller::-webkit-scrollbar-thumb { background: var(--line-2); border-radius: 2px; }

	.term-chip {
		flex: none;
		display: flex;
		align-items: stretch;
		border-radius: 8px;
		border: 1px solid var(--line-2);
		background: var(--surface-2);
		cursor: pointer;
		overflow: hidden;
		transition: border-color 0.18s, background 0.18s, box-shadow 0.18s, transform 0.18s;
		text-align: left;
		min-width: 72px;
		position: relative;
	}
	.term-chip:hover:not(.active) {
		border-color: var(--line-3);
		background: var(--surface-3, var(--surface-2));
		transform: translateY(-2px);
		box-shadow: 0 6px 16px rgba(0, 0, 0, 0.35);
	}
	.term-chip.active {
		border-color: var(--accent);
		background: color-mix(in srgb, var(--accent) 9%, var(--surface-2));
		box-shadow:
			0 0 0 1px color-mix(in srgb, var(--accent) 30%, transparent),
			0 4px 20px -4px color-mix(in srgb, var(--accent) 30%, transparent);
	}
	.chip-stripe {
		width: 3px;
		flex-shrink: 0;
		background: var(--chip-color, var(--line-2));
		transition: background 0.18s;
	}
	.all-chip .chip-stripe {
		background: var(--grad);
		width: 3px;
	}
	.chip-body {
		display: flex;
		flex-direction: column;
		padding: 0.5rem 0.65rem 0.45rem;
		gap: 0;
		min-width: 0;
	}
	.chip-era {
		font-size: 0.58rem;
		font-weight: 700;
		letter-spacing: 0.08em;
		text-transform: uppercase;
		color: var(--ink-3);
		line-height: 1.2;
	}
	.chip-num {
		font-family: var(--display);
		font-size: 1.25rem;
		font-weight: 700;
		line-height: 1.1;
		letter-spacing: -0.02em;
		color: var(--ink);
		transition: color 0.18s;
	}
	.term-chip.active .chip-num { color: var(--accent); }
	.chip-years {
		font-size: 0.62rem;
		color: var(--ink-3);
		line-height: 1.3;
		margin-top: 0.1rem;
		white-space: nowrap;
	}
	.chip-chancellor {
		display: flex;
		align-items: center;
		gap: 0.3em;
		font-size: 0.66rem;
		color: var(--ink-2);
		margin-top: 0.3rem;
		white-space: nowrap;
		font-style: italic;
	}
	.chip-dot {
		width: 5px;
		height: 5px;
		border-radius: 50%;
		background: var(--chip-color, var(--line-2));
		flex-shrink: 0;
	}
	.all-chip .chip-num {
		font-size: 0.95rem;
		letter-spacing: 0;
	}

	/* Controls row — count mode only */
	.controls-row {
		display: flex;
		align-items: center;
		gap: 0.85rem;
		flex-wrap: wrap;
	}
	.ctrl-group {
		display: flex;
		align-items: center;
		gap: 0.55rem;
	}
	.ctrl-lbl {
		font-size: 0.72rem;
		font-weight: 600;
		letter-spacing: 0.06em;
		text-transform: uppercase;
		color: var(--ink-3);
		white-space: nowrap;
	}
	.seg {
		display: flex;
		gap: 0;
		border: 1px solid var(--line-2);
		border-radius: 6px;
		overflow: hidden;
		background: var(--surface-2);
	}
	.seg button {
		font: inherit;
		font-size: 0.82rem;
		padding: 0.3rem 0.75rem;
		border: none;
		background: none;
		color: var(--ink-3);
		cursor: pointer;
		transition: background 0.15s, color 0.15s;
	}
	.seg button + button { border-left: 1px solid var(--line-2); }
	.seg button.on { background: var(--accent); color: #fff; }
	.seg button:hover:not(.on) { color: var(--ink); background: var(--surface-3); }

	/* Politician picker — lives in the timeline panel header */
	.pol-picker {
		display: flex;
		align-items: center;
		gap: 0.45rem;
		background: var(--surface-2);
		border: 1px solid var(--line-2);
		border-radius: 999px;
		padding: 4px 4px 4px 10px;
		flex-shrink: 0;
		transition: border-color 0.2s;
	}
	.pol-picker:focus-within {
		border-color: var(--accent);
		box-shadow: 0 0 0 2px color-mix(in srgb, var(--accent) 20%, transparent);
	}
	.pol-picker.has-value { border-color: var(--accent); }
	.pol-icon { color: var(--ink-3); flex-shrink: 0; }
	.pol-input-wrap { position: relative; flex: 1; min-width: 120px; max-width: 200px; }
	.pol-input {
		width: 100%;
		font: inherit;
		font-size: 0.84rem;
		background: none;
		border: none;
		outline: none;
		color: var(--ink);
		padding: 0.3rem 1.6rem 0.3rem 0;
	}
	.pol-input::placeholder { color: var(--ink-3); }
	.pol-clr {
		position: absolute; right: 0; top: 50%;
		transform: translateY(-50%);
		border: none; background: none; cursor: pointer;
		color: var(--ink-3); font-size: 0.75rem; padding: 0.2rem; line-height: 1;
	}
	.pol-clr:hover { color: var(--ink); }
	.pol-dropdown {
		position: absolute; z-index: 10;
		top: calc(100% + 6px); right: 0;
		width: 260px; list-style: none; margin: 0; padding: 0.3rem;
		background: var(--card); border: 1px solid var(--line-2);
		border-radius: var(--radius-sm); box-shadow: var(--shadow);
		max-height: 240px; overflow-y: auto;
	}
	.pol-dropdown button {
		width: 100%; text-align: left; font: inherit; font-size: 0.85rem;
		display: flex; align-items: center; gap: 0.45rem;
		padding: 0.45rem 0.5rem; border: none; background: none;
		border-radius: 6px; cursor: pointer; color: var(--ink);
	}
	.pol-dropdown button:hover { background: var(--paper-2); }
	.pol-dot { width: 8px; height: 8px; border-radius: 50%; flex: none; }
	.pol-party { color: var(--ink-3); }

	/* ── Content ───────────────────────────────────────────────────────── */
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
	.headline .eyebrow { order: -1; width: 100%; margin-bottom: -0.4rem; }
	.kw {
		font-size: clamp(2.4rem, 5vw, 3.6rem);
		margin: 0;
		line-height: 1;
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
		transition: transform 0.3s var(--spring), border-color 0.3s;
	}
	.metric::before {
		content: '';
		position: absolute; inset: 0 0 auto 0;
		height: 2px; background: var(--grad); opacity: 0.7;
	}
	.metric:hover { transform: translateY(-3px); border-color: var(--line-2); }
	.m-num {
		display: block;
		font-family: var(--display);
		font-size: 2rem; font-weight: 600;
		line-height: 1.05; letter-spacing: -0.02em;
	}
	.m-num.small { font-size: 1.25rem; }
	.m-num.lead { display: flex; align-items: center; gap: 0.45rem; }
	.lead-dot {
		width: 11px; height: 11px; border-radius: 50%;
		background: var(--lc); box-shadow: 0 0 12px -1px var(--lc); flex: none;
	}
	.m-cap { font-size: 0.76rem; color: var(--ink-3); margin-top: 0.35rem; display: block; }

	/* ── Hero ──────────────────────────────────────────────────────────── */
	.hero-wrap { display: flex; flex-direction: column; gap: 0; }
	.hero-controls {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		margin-bottom: 0.75rem;
	}
	.view-tabs {
		display: inline-flex;
		background: var(--surface-2);
		border: 1px solid var(--line-2);
		border-radius: 999px;
		padding: 3px; gap: 2px;
	}
	.view-tab {
		display: inline-flex; align-items: center; gap: 0.45rem;
		font: inherit; font-size: 0.85rem; font-weight: 600;
		padding: 0.5rem 1.15rem;
		border: none; border-radius: 999px;
		background: transparent; color: var(--ink-3);
		cursor: pointer;
		transition: background 0.2s, color 0.2s, box-shadow 0.2s;
		white-space: nowrap;
	}
	.view-tab:hover:not(.active) { color: var(--ink-2); background: var(--surface-3); }
	.view-tab.active {
		background: var(--surface); color: var(--ink);
		box-shadow: 0 1px 4px rgba(0,0,0,0.4);
	}
	.view-tab.active svg { filter: drop-shadow(0 0 4px var(--accent)); color: var(--accent); }

	/* ── Flip ──────────────────────────────────────────────────────────── */
	.flip-container { perspective: 1400px; }
	.flip-inner {
		position: relative;
		transform-style: preserve-3d;
		transition: transform 0.65s cubic-bezier(0.4, 0.2, 0.2, 1);
	}
	.flip-inner.flipped { transform: rotateY(180deg); }
	.flip-face { backface-visibility: hidden; -webkit-backface-visibility: hidden; }
	.flip-back {
		position: absolute; inset: 0;
		transform: rotateY(180deg);
		overflow-y: auto;
	}

	.panel { padding: 1.4rem 1.5rem; }
	.panel.solid {
		background: var(--surface);
		backdrop-filter: none;
		border-color: var(--line-2);
	}
	.p-head {
		display: flex; justify-content: space-between;
		align-items: flex-start; gap: 1rem;
		margin-bottom: 1.1rem; flex-wrap: wrap;
	}
	.p-head h3 { margin: 0; }
	.p-hint { margin: 0.3rem 0 0; font-size: 0.8rem; color: var(--ink-3); }

	.slider {
		display: flex; align-items: center; gap: 0.55rem;
		font-size: 0.82rem; color: var(--ink-2);
	}
	.slider input[type='range'] { accent-color: var(--accent); width: 110px; }

	.grid-2 {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 1.4rem;
		align-items: start;
	}
	.party-body {
		display: grid;
		grid-template-columns: 200px 1fr;
		gap: 1.5rem;
		align-items: center;
	}
	.term-section {
		margin-top: 1.4rem; padding-top: 1.2rem;
		border-top: 1px solid var(--line);
	}
	.term-label {
		display: block;
		font-size: 0.78rem; font-weight: 600;
		letter-spacing: 0.06em; text-transform: uppercase;
		color: var(--ink-3); margin-bottom: 0.75rem;
	}

	.empty, .err { color: var(--ink-3); padding: 2rem 0; text-align: center; }
	.err { color: var(--spark); }
	.empty-state {
		padding: 4rem 2rem;
		display: flex; flex-direction: column;
		align-items: center; gap: 1.2rem;
		color: var(--ink-3); text-align: center;
	}

	/* ── Responsive ────────────────────────────────────────────────────── */
	@media (max-width: 860px) {
		.metrics { grid-template-columns: repeat(2, 1fr); }
		.grid-2 { grid-template-columns: 1fr; }
		.party-body { grid-template-columns: 1fr; }
		.p-head { flex-direction: column; }
		.pol-picker { width: 100%; max-width: none; }
		.pol-input-wrap { max-width: none; }
	}
	@media (max-width: 520px) {
		.metrics { grid-template-columns: 1fr; }
		.controls-row { gap: 0.6rem; }
		.term-row { gap: 0.5rem; }
	}
</style>

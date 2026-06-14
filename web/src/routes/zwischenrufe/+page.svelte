<script lang="ts">
	import { api } from '$lib/api';
	import { i18n } from '$lib/i18n.svelte';
	import { partyColor, formatNumber } from '$lib/format';
	import Counter from '$lib/components/Counter.svelte';
	import HBars from '$lib/components/HBars.svelte';
	import LangToggle from '$lib/components/LangToggle.svelte';
	import InterruptionMatrix from '$lib/components/InterruptionMatrix.svelte';
	import ZwischenrufFeed from '$lib/components/ZwischenrufFeed.svelte';
	import type {
		ZwischenrufMeta,
		ZwischenrufTimelinePoint,
		ZwischenrufCallerCount,
		ZwischenrufPartyCount,
		ZwischenrufMatrixRow,
		ZwischenrufType
	} from '$lib/types';

	// ── state ─────────────────────────────────────────────────────────────────
	let meta = $state<ZwischenrufMeta | null>(null);
	let timeline = $state<ZwischenrufTimelinePoint[]>([]);
	let topCallers = $state<ZwischenrufCallerCount[]>([]);
	let byParty = $state<ZwischenrufPartyCount[]>([]);
	let matrix = $state<ZwischenrufMatrixRow[]>([]);
	let loading = $state(true);
	let bootError = $state<string | null>(null);

	let typeFilter = $state<ZwischenrufType | ''>('Zwischenruf');
	let termFilter = $state<number | undefined>(undefined);
	let activeView = $state<'matrix' | 'parties' | 'callers' | 'feed'>('matrix');

	const TYPES: Array<{ value: ZwischenrufType | ''; labelKey: string }> = [
		{ value: '', labelKey: 'zw_type_zwischenruf' },
		{ value: 'Zwischenruf', labelKey: 'zw_type_zwischenruf' },
		{ value: 'Beifall', labelKey: 'zw_type_beifall' },
		{ value: 'Heiterkeit', labelKey: 'zw_type_heiterkeit' },
		{ value: 'Widerspruch', labelKey: 'zw_type_widerspruch' },
		{ value: 'Zuruf', labelKey: 'zw_type_zuruf' }
	];

	const TYPE_COLOR: Record<string, string> = {
		Zwischenruf: 'var(--accent)',
		Beifall: 'var(--gold)',
		Heiterkeit: '#6be4a0',
		Lachen: '#6be4a0',
		Widerspruch: 'var(--spark)',
		Zuruf: 'var(--accent-2)',
		Zustimmung: '#7de0ff'
	};

	// ── boot ──────────────────────────────────────────────────────────────────
	async function boot() {
		bootError = null;
		loading = true;
		try {
			meta = await api.zwischenrufe.meta();
		} catch {
			bootError = 'API nicht erreichbar.';
			loading = false;
			return;
		}
		if (!meta?.available) {
			loading = false;
			return;
		}
		await reload();
		loading = false;
	}

	async function reload() {
		const tf = typeFilter || 'Zwischenruf';
		const term = termFilter;
		const [tl, tc, bp, mx] = await Promise.allSettled([
			api.zwischenrufe.timeline(undefined, undefined, term),
			api.zwischenrufe.topCallers(tf, term, undefined, 20),
			api.zwischenrufe.byParty(tf, term),
			api.zwischenrufe.matrix(tf, term)
		]);
		if (tl.status === 'fulfilled') timeline = tl.value;
		if (tc.status === 'fulfilled') topCallers = tc.value;
		if (bp.status === 'fulfilled') byParty = bp.value;
		if (mx.status === 'fulfilled') matrix = mx.value;
	}

	$effect(() => {
		boot();
	});

	let debounce: ReturnType<typeof setTimeout>;
	$effect(() => {
		void typeFilter; void termFilter;
		if (!meta?.available) return;
		clearTimeout(debounce);
		debounce = setTimeout(reload, 200);
	});

	// ── derived ───────────────────────────────────────────────────────────────
	// Timeline: aggregate by year across all types for the sparklines,
	// and split by type for the stacked view
	const timelineByType = $derived(() => {
		const out = new Map<string, Map<string, number>>();
		for (const pt of timeline) {
			if (!out.has(pt.type)) out.set(pt.type, new Map());
			out.get(pt.type)!.set(pt.year, (out.get(pt.type)!.get(pt.year) ?? 0) + pt.n);
		}
		return out;
	});

	const years = $derived([...new Set(timeline.map((p) => p.year))].sort());

	const timelineTypes = $derived(
		[...new Set(timeline.map((p) => p.type))].sort(
			(a, b) =>
				(timelineByType().get(b)?.values().reduce((s, v) => s + v, 0) ?? 0) -
				(timelineByType().get(a)?.values().reduce((s, v) => s + v, 0) ?? 0)
		)
	);

	const callerBars = $derived(
		topCallers.map((c) => ({
			label: c.caller_name,
			sub: c.caller_party,
			value: c.n,
			color: partyColor(c.caller_party)
		}))
	);

	const partyBars = $derived(
		byParty.map((p) => ({
			label: p.caller_party,
			value: p.n,
			color: partyColor(p.caller_party)
		}))
	);

	// Stat cards derived from data
	const topCaller = $derived(topCallers[0] ?? null);
	const topCallerParty = $derived(byParty[0] ?? null);
	const topTarget = $derived(
		(() => {
			const totals = new Map<string, number>();
			for (const r of matrix) {
				totals.set(r.target_speaker_party, (totals.get(r.target_speaker_party) ?? 0) + r.n);
			}
			let best = { party: '', n: 0 };
			for (const [p, n] of totals) if (n > best.n) best = { party: p, n };
			return best.party ? best : null;
		})()
	);

	// SVG timeline dimensions
	const TL_H = 160;
	const TL_PAD = { t: 12, b: 28, l: 8, r: 8 };
	let svgW = $state(600);

	function timelineYearX(year: string, w: number): number {
		if (years.length < 2) return w / 2;
		const i = years.indexOf(year);
		const pad = TL_PAD.l + TL_PAD.r;
		return TL_PAD.l + (i / (years.length - 1)) * (w - pad);
	}

	function typeTotal(type: string): number {
		const m = timelineByType().get(type);
		if (!m) return 0;
		return [...m.values()].reduce((s, v) => s + v, 0);
	}

	const maxYearTotal = $derived(
		Math.max(
			1,
			...years.map((y) =>
				timelineTypes.reduce((s, t) => s + (timelineByType().get(t)?.get(y) ?? 0), 0)
			)
		)
	);

	function stackedPaths(): Array<{ type: string; path: string; color: string }> {
		if (!years.length || !timelineTypes.length) return [];
		const innerH = TL_H - TL_PAD.t - TL_PAD.b;
		const results: Array<{ type: string; path: string; color: string }> = [];

		for (const type of [...timelineTypes].reverse()) {
			const pts: string[] = [];
			for (const year of years) {
				const n = timelineByType().get(type)?.get(year) ?? 0;
				const x = timelineYearX(year, svgW);
				const y = TL_PAD.t + innerH * (1 - n / maxYearTotal);
				pts.push(`${x.toFixed(1)},${y.toFixed(1)}`);
			}
			// Close path along bottom
			const lastX = timelineYearX(years[years.length - 1], svgW).toFixed(1);
			const firstX = timelineYearX(years[0], svgW).toFixed(1);
			const bottom = (TL_PAD.t + innerH).toFixed(1);
			const d = `M ${pts.join(' L ')} L ${lastX},${bottom} L ${firstX},${bottom} Z`;
			results.push({ type, path: d, color: TYPE_COLOR[type] ?? 'var(--accent)' });
		}
		return results;
	}

	function yearLabels(): Array<{ x: number; label: string }> {
		if (!years.length) return [];
		const step = years.length > 20 ? Math.ceil(years.length / 10) : 1;
		return years
			.filter((_, i) => i % step === 0)
			.map((y) => ({ x: timelineYearX(y, svgW), label: y.slice(0, 4) }));
	}
</script>

<svelte:head>
	<title>{i18n.t('zw_title')} · OpenBundestag</title>
</svelte:head>

<div class="wrap page">
	<header class="page-head">
		<div class="head-text">
			<p class="eyebrow">OpenBundestag</p>
			<h1 class="grad-text">{i18n.t('zw_title')}</h1>
			<p class="subtitle">{i18n.t('zw_subtitle')}</p>
		</div>
		<LangToggle />
	</header>

	{#if bootError}
		<div class="alert glass">
			<p>{bootError}</p>
			<button class="btn" onclick={boot}>{i18n.t('retry')}</button>
		</div>
	{:else if loading}
		<div class="boot-state">
			<div class="orb"></div>
			<p class="muted">{i18n.t('waking')}</p>
		</div>
	{:else if !meta?.available}
		<div class="alert glass">
			<p>{i18n.t('zw_unavailable')}</p>
		</div>
	{:else}
		<!-- ── Stat cards ──────────────────────────────────────────────────── -->
		<div class="metrics">
			<div class="metric glass">
				<span class="m-num"><Counter value={meta.total} /></span>
				<span class="m-cap">{i18n.t('zw_total')}</span>
			</div>
			{#if topCaller}
				<div
					class="metric glass"
					style:--lc={partyColor(topCaller.caller_party)}
				>
					<span class="m-num small lead">
						<span class="lead-dot"></span>
						{topCaller.caller_name}
					</span>
					<span class="m-sub">{topCaller.caller_party} · {formatNumber(topCaller.n, i18n.lang)} ×</span>
					<span class="m-cap">{i18n.t('zw_top_caller')}</span>
				</div>
			{/if}
			{#if topCallerParty}
				<div class="metric glass" style:--lc={partyColor(topCallerParty.caller_party)}>
					<span class="m-num small lead">
						<span class="lead-dot"></span>
						{topCallerParty.caller_party}
					</span>
					<span class="m-sub">{formatNumber(topCallerParty.n, i18n.lang)} Rufe</span>
					<span class="m-cap">{i18n.t('zw_most_active_party')}</span>
				</div>
			{/if}
			{#if topTarget}
				<div class="metric glass" style:--lc={partyColor(topTarget.party)}>
					<span class="m-num small lead">
						<span class="lead-dot"></span>
						{topTarget.party}
					</span>
					<span class="m-sub">{formatNumber(topTarget.n, i18n.lang)} Mal unterbrochen</span>
					<span class="m-cap">{i18n.t('zw_most_interrupted')}</span>
				</div>
			{/if}
		</div>

		<!-- ── Filters ────────────────────────────────────────────────────── -->
		<div class="filter-bar glass">
			<label class="filter-group">
				<span class="filter-label">{i18n.t('zw_filter_type')}</span>
				<select bind:value={typeFilter} class="sel">
					<option value="Zwischenruf">{i18n.t('zw_type_zwischenruf')}</option>
					<option value="Beifall">{i18n.t('zw_type_beifall')}</option>
					<option value="Heiterkeit">{i18n.t('zw_type_heiterkeit')}</option>
					<option value="Widerspruch">{i18n.t('zw_type_widerspruch')}</option>
					<option value="Zuruf">{i18n.t('zw_type_zuruf')}</option>
				</select>
			</label>
			<label class="filter-group">
				<span class="filter-label">{i18n.t('terms')}</span>
				<select
					bind:value={termFilter}
					class="sel"
					onchange={(e) => {
						const v = (e.target as HTMLSelectElement).value;
						termFilter = v ? Number(v) : undefined;
					}}
				>
					<option value="">{i18n.t('all_terms')}</option>
					{#each Array.from({ length: 21 }, (_, i) => 21 - i) as t}
						<option value={t}>Wahlperiode {t}</option>
					{/each}
				</select>
			</label>
		</div>

		<!-- ── Timeline SVG ───────────────────────────────────────────────── -->
		<section class="panel glass">
			<header class="p-head">
				<h3>{i18n.t('zw_timeline_title')}</h3>
				<div class="legend">
					{#each timelineTypes as type}
						<span class="legend-item">
							<span class="legend-dot" style:background={TYPE_COLOR[type] ?? 'var(--accent)'}></span>
							{type}
							<span class="legend-n">{formatNumber(typeTotal(type), i18n.lang)}</span>
						</span>
					{/each}
				</div>
			</header>

			{#if years.length}
				<div
					class="svg-wrap"
					bind:clientWidth={svgW}
				>
					<svg
						width="100%"
						height={TL_H}
						viewBox="0 0 {svgW} {TL_H}"
						preserveAspectRatio="none"
						aria-label="Zeitverlauf Zwischenrufe"
					>
						<!-- Stacked area paths -->
						{#each stackedPaths() as { type, path, color }}
							<path d={path} fill={color} fill-opacity="0.25" stroke={color} stroke-width="1.5" stroke-opacity="0.8">
								<title>{type}</title>
							</path>
						{/each}
						<!-- Year axis labels -->
						{#each yearLabels() as { x, label }}
							<text
								x={x}
								y={TL_H - 6}
								text-anchor="middle"
								font-size="9"
								fill="var(--ink-3)"
								font-family="var(--display)"
							>{label}</text>
						{/each}
					</svg>
				</div>
			{:else}
				<p class="empty">—</p>
			{/if}
		</section>

		<!-- ── Adventure tabs ────────────────────────────────────────────── -->
		<div class="adventure-tabs" role="tablist">
			<button
				role="tab"
				aria-selected={activeView === 'matrix'}
				class="adv-tab"
				class:active={activeView === 'matrix'}
				onclick={() => (activeView = 'matrix')}
				style="--tab-color: var(--accent-2)"
			>
				<div class="adv-icon">
					<svg width="28" height="28" viewBox="0 0 28 28" fill="none" aria-hidden="true">
						<rect x="2" y="2" width="10" height="10" rx="2.5" stroke="currentColor" stroke-width="1.8"/>
						<rect x="16" y="2" width="10" height="10" rx="2.5" stroke="currentColor" stroke-width="1.8"/>
						<rect x="2" y="16" width="10" height="10" rx="2.5" stroke="currentColor" stroke-width="1.8"/>
						<rect x="16" y="16" width="10" height="10" rx="2.5" stroke="currentColor" stroke-width="1.8"/>
						<line x1="14" y1="4" x2="14" y2="24" stroke="currentColor" stroke-width="1" stroke-dasharray="2 2" stroke-opacity="0.5"/>
						<line x1="4" y1="14" x2="24" y2="14" stroke="currentColor" stroke-width="1" stroke-dasharray="2 2" stroke-opacity="0.5"/>
					</svg>
				</div>
				<div class="adv-body">
					<span class="adv-title">{i18n.t('zw_matrix_title')}</span>
					<span class="adv-hint">Wer schießt auf wen? Die Konfrontationskarte</span>
				</div>
				<span class="adv-arrow">→</span>
			</button>

			<button
				role="tab"
				aria-selected={activeView === 'parties'}
				class="adv-tab"
				class:active={activeView === 'parties'}
				onclick={() => (activeView = 'parties')}
				style="--tab-color: var(--gold)"
			>
				<div class="adv-icon">
					<svg width="28" height="28" viewBox="0 0 28 28" fill="none" aria-hidden="true">
						<rect x="3" y="16" width="4" height="9" rx="1" fill="currentColor" opacity="0.4"/>
						<rect x="9" y="11" width="4" height="14" rx="1" fill="currentColor" opacity="0.6"/>
						<rect x="15" y="6" width="4" height="19" rx="1" fill="currentColor" opacity="0.8"/>
						<rect x="21" y="3" width="4" height="22" rx="1" fill="currentColor"/>
						<line x1="2" y1="26" x2="26" y2="26" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
					</svg>
				</div>
				<div class="adv-body">
					<span class="adv-title">{i18n.t('zw_most_active_party')}</span>
					<span class="adv-hint">Welche Partei dröhnt am lautesten?</span>
				</div>
				<span class="adv-arrow">→</span>
			</button>

			<button
				role="tab"
				aria-selected={activeView === 'callers'}
				class="adv-tab"
				class:active={activeView === 'callers'}
				onclick={() => (activeView = 'callers')}
				style="--tab-color: var(--spark)"
			>
				<div class="adv-icon">
					<svg width="28" height="28" viewBox="0 0 28 28" fill="none" aria-hidden="true">
						<circle cx="10" cy="9" r="4.5" stroke="currentColor" stroke-width="1.8"/>
						<path d="M3 24c0-3.866 3.134-7 7-7s7 3.134 7 14" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
						<path d="M20 8l6 0M20 12l4 0M20 16l5 0" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
					</svg>
				</div>
				<div class="adv-body">
					<span class="adv-title">{i18n.t('zw_top_title')}</span>
					<span class="adv-hint">Die 20 unruhigsten Parlamentarier</span>
				</div>
				<span class="adv-arrow">→</span>
			</button>

			<button
				role="tab"
				aria-selected={activeView === 'feed'}
				class="adv-tab"
				class:active={activeView === 'feed'}
				onclick={() => (activeView = 'feed')}
				style="--tab-color: #6be4a0"
			>
				<div class="adv-icon">
					<svg width="28" height="28" viewBox="0 0 28 28" fill="none" aria-hidden="true">
						<rect x="3" y="5" width="22" height="4" rx="2" fill="currentColor" opacity="0.35"/>
						<rect x="3" y="12" width="16" height="4" rx="2" fill="currentColor" opacity="0.65"/>
						<rect x="3" y="19" width="19" height="4" rx="2" fill="currentColor" opacity="0.9"/>
						<circle cx="23" cy="21" r="3.5" stroke="currentColor" stroke-width="1.5" fill="none"/>
						<path d="M22 21l1 1 1.5-1.5" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/>
					</svg>
				</div>
				<div class="adv-body">
					<span class="adv-title">{i18n.t('zw_feed_title')}</span>
					<span class="adv-hint">Echte Rufe aus dem Plenum, live</span>
				</div>
				<span class="adv-arrow">→</span>
			</button>
		</div>

		<!-- ── View panels ────────────────────────────────────────────────── -->
		{#if activeView === 'matrix'}
			<section class="panel glass">
				<header class="p-head">
					<div>
						<h3>{i18n.t('zw_matrix_title')}</h3>
						<p class="p-hint">{i18n.t('zw_matrix_hint')}</p>
					</div>
				</header>
				{#if matrix.length}
					<InterruptionMatrix rows={matrix} />
				{:else}
					<p class="empty">—</p>
				{/if}
			</section>
		{:else if activeView === 'parties'}
			<section class="panel glass">
				<header class="p-head"><h3>{i18n.t('zw_most_active_party')}</h3></header>
				{#if partyBars.length}
					<HBars bars={partyBars} valueLabel={i18n.t('zw_calls')} />
				{:else}
					<p class="empty">—</p>
				{/if}
			</section>
		{:else if activeView === 'callers'}
			<section class="panel glass">
				<header class="p-head"><h3>{i18n.t('zw_top_title')}</h3></header>
				{#if callerBars.length}
					<HBars bars={callerBars} valueLabel={i18n.t('zw_calls')} />
				{:else}
					<p class="empty">—</p>
				{/if}
			</section>
		{:else}
			<section class="panel glass">
				<header class="p-head">
					<h3>{i18n.t('zw_feed_title')}</h3>
				</header>
				<ZwischenrufFeed termFilter={termFilter} />
			</section>
		{/if}
	{/if}
</div>

<style>
	.page {
		padding-top: 2rem;
		padding-bottom: 4rem;
		display: flex;
		flex-direction: column;
		gap: 1.4rem;
	}

	.page-head {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		gap: 1rem;
		margin-bottom: 0.4rem;
	}
	.head-text {
		display: flex;
		flex-direction: column;
		gap: 0.3rem;
	}
	h1 {
		font-size: clamp(2.2rem, 5vw, 3.4rem);
		margin: 0;
		line-height: 1;
	}
	.subtitle {
		color: var(--ink-2);
		font-size: 1rem;
		margin: 0;
	}

	.boot-state {
		min-height: 40vh;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 1rem;
	}
	.muted { color: var(--ink-3); }
	.orb {
		width: 56px; height: 56px;
		border-radius: 50%;
		background: var(--grad);
		filter: blur(2px);
		animation: orb 1.6s ease infinite, spin 3s linear infinite;
		box-shadow: var(--glow);
	}
	@keyframes orb {
		0%, 100% { transform: scale(1); opacity: 0.9; }
		50% { transform: scale(0.7); opacity: 0.5; }
	}
	@keyframes spin { to { transform: rotate(360deg); } }

	.alert {
		padding: 2rem;
		text-align: center;
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 1rem;
		color: var(--ink-2);
	}

	/* ── Metrics ── */
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
		position: absolute;
		inset: 0 0 auto 0;
		height: 2px;
		background: var(--grad);
		opacity: 0.7;
	}
	.metric:hover { transform: translateY(-3px); }
	.m-num {
		display: block;
		font-family: var(--display);
		font-size: 2rem;
		font-weight: 600;
		line-height: 1.05;
		letter-spacing: -0.02em;
	}
	.m-num.small { font-size: 1.1rem; }
	.m-num.lead { display: flex; align-items: center; gap: 0.45rem; }
	.lead-dot {
		width: 10px; height: 10px;
		border-radius: 50%;
		background: var(--lc);
		box-shadow: 0 0 10px -1px var(--lc);
		flex: none;
	}
	.m-sub {
		display: block;
		font-size: 0.72rem;
		color: var(--ink-3);
		margin-top: 0.15rem;
	}
	.m-cap {
		display: block;
		font-size: 0.76rem;
		color: var(--ink-3);
		margin-top: 0.4rem;
	}

	/* ── Filter bar ── */
	.filter-bar {
		display: flex;
		gap: 1.2rem;
		flex-wrap: wrap;
		padding: 0.85rem 1.2rem;
		align-items: center;
	}
	.filter-group {
		display: flex;
		align-items: center;
		gap: 0.55rem;
	}
	.filter-label {
		font-size: 0.78rem;
		font-weight: 600;
		color: var(--ink-3);
		letter-spacing: 0.04em;
		text-transform: uppercase;
		white-space: nowrap;
	}
	.sel {
		background: var(--surface-2);
		border: 1px solid var(--line-2);
		border-radius: 8px;
		color: var(--ink);
		font: inherit;
		font-size: 0.85rem;
		padding: 0.35rem 0.7rem;
		outline: none;
		cursor: pointer;
		transition: border-color 0.2s;
	}
	.sel:focus { border-color: var(--accent); }

	/* ── Timeline ── */
	.svg-wrap { width: 100%; }

	.legend {
		display: flex;
		flex-wrap: wrap;
		gap: 0.8rem;
		align-items: center;
	}
	.legend-item {
		display: flex;
		align-items: center;
		gap: 0.35rem;
		font-size: 0.75rem;
		color: var(--ink-2);
	}
	.legend-dot {
		width: 8px; height: 8px;
		border-radius: 50%;
		flex: none;
	}
	.legend-n {
		color: var(--ink-3);
		font-size: 0.68rem;
	}

	/* ── Adventure tabs ── */
	.adventure-tabs {
		display: grid;
		grid-template-columns: repeat(4, 1fr);
		gap: 0.75rem;
	}
	.adv-tab {
		position: relative;
		display: flex;
		flex-direction: column;
		align-items: flex-start;
		gap: 0.6rem;
		padding: 1.1rem 1.2rem 1rem;
		background: var(--surface);
		border: 1px solid var(--line-2);
		border-radius: 14px;
		cursor: pointer;
		text-align: left;
		transition: transform 0.22s var(--spring), border-color 0.22s, box-shadow 0.22s, background 0.22s;
		overflow: hidden;
	}
	.adv-tab::before {
		content: '';
		position: absolute;
		inset: 0;
		border-radius: inherit;
		background: radial-gradient(ellipse 80% 60% at 50% 120%, color-mix(in srgb, var(--tab-color) 18%, transparent), transparent 70%);
		opacity: 0;
		transition: opacity 0.3s;
	}
	.adv-tab::after {
		content: '';
		position: absolute;
		inset: 0 0 auto 0;
		height: 2px;
		background: var(--tab-color);
		border-radius: 2px 2px 0 0;
		opacity: 0;
		transition: opacity 0.22s;
	}
	.adv-tab:hover {
		border-color: color-mix(in srgb, var(--tab-color) 55%, transparent);
		transform: translateY(-3px);
		box-shadow: 0 8px 28px -6px color-mix(in srgb, var(--tab-color) 28%, transparent);
	}
	.adv-tab:hover::before { opacity: 1; }
	.adv-tab:hover::after { opacity: 0.5; }
	.adv-tab:hover .adv-arrow { opacity: 1; transform: translateX(2px); }
	.adv-tab.active {
		border-color: color-mix(in srgb, var(--tab-color) 70%, transparent);
		background: color-mix(in srgb, var(--tab-color) 6%, var(--surface));
		box-shadow: 0 0 0 1px color-mix(in srgb, var(--tab-color) 30%, transparent),
		            0 12px 36px -8px color-mix(in srgb, var(--tab-color) 35%, transparent);
		transform: translateY(-2px);
	}
	.adv-tab.active::before { opacity: 1; }
	.adv-tab.active::after { opacity: 1; }
	.adv-tab.active .adv-icon { color: var(--tab-color); filter: drop-shadow(0 0 8px color-mix(in srgb, var(--tab-color) 60%, transparent)); }
	.adv-tab.active .adv-title { color: var(--ink); }
	.adv-tab.active .adv-arrow { opacity: 1; color: var(--tab-color); transform: translateX(3px); }
	.adv-icon {
		color: var(--ink-3);
		transition: color 0.22s, filter 0.22s;
		flex: none;
	}
	.adv-body {
		display: flex;
		flex-direction: column;
		gap: 0.22rem;
		flex: 1;
	}
	.adv-title {
		font-family: var(--display);
		font-size: 0.88rem;
		font-weight: 700;
		color: var(--ink-2);
		line-height: 1.2;
		transition: color 0.22s;
	}
	.adv-hint {
		font-size: 0.73rem;
		color: var(--ink-3);
		line-height: 1.35;
	}
	.adv-arrow {
		position: absolute;
		bottom: 0.9rem;
		right: 1rem;
		font-size: 1rem;
		color: var(--ink-3);
		opacity: 0;
		transition: opacity 0.22s, transform 0.22s, color 0.22s;
	}

	/* ── Panels ── */
	.panel {
		padding: 1.4rem 1.5rem;
	}
	.p-head {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		gap: 1rem;
		margin-bottom: 1.1rem;
		flex-wrap: wrap;
	}
	.p-head h3 { margin: 0; }
	.p-hint {
		margin: 0.25rem 0 0;
		font-size: 0.78rem;
		color: var(--ink-3);
	}

	.empty {
		color: var(--ink-3);
		text-align: center;
		padding: 2rem 0;
	}

	/* ── Btn ── */
	.btn {
		font: inherit;
		font-size: 0.85rem;
		font-weight: 600;
		padding: 0.5rem 1.2rem;
		border: 1px solid var(--line-2);
		border-radius: 999px;
		background: var(--surface-2);
		color: var(--ink);
		cursor: pointer;
		transition: background 0.2s, border-color 0.2s;
	}
	.btn:hover {
		background: var(--surface-3);
		border-color: var(--accent);
	}

	@media (max-width: 900px) {
		.metrics { grid-template-columns: repeat(2, 1fr); }
		.adventure-tabs { grid-template-columns: repeat(2, 1fr); }
	}
	@media (max-width: 540px) {
		.metrics { grid-template-columns: 1fr; }
		.adventure-tabs { grid-template-columns: 1fr; }
		.filter-bar { flex-direction: column; align-items: flex-start; }
	}
</style>

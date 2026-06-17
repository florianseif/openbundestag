<script lang="ts">
	import { api } from '$lib/api';
	import { i18n } from '$lib/i18n.svelte';
	import { partyColor, formatNumber, partyFoundingOrder } from '$lib/format';
	import Counter from '$lib/components/Counter.svelte';
	import HBars from '$lib/components/HBars.svelte';
	import PageHero from '$lib/components/PageHero.svelte';
	import InterruptionMatrix from '$lib/components/InterruptionMatrix.svelte';
	import TermFilter from '$lib/components/TermFilter.svelte';
	import type {
		BeifallMeta,
		BeifallSelfOther,
		ZwischenrufPartyCount,
		ZwischenrufMatrixRow,
		TermInfo
	} from '$lib/types';

	// ── state ─────────────────────────────────────────────────────────────────
	let meta = $state<BeifallMeta | null>(null);
	let termOptions = $state<TermInfo[]>([]);
	let byParty = $state<ZwischenrufPartyCount[]>([]);
	let matrix = $state<ZwischenrufMatrixRow[]>([]);
	let selfVsOther = $state<BeifallSelfOther[]>([]);
	let loading = $state(true);
	let bootError = $state<string | null>(null);

	let terms = $state<number[]>([21]);
	let activeView = $state<'matrix' | 'parties' | 'self'>('matrix');

	// ── boot ──────────────────────────────────────────────────────────────────
	async function boot() {
		bootError = null;
		loading = true;
		try {
			meta = await api.beifall.meta();
		} catch {
			bootError = 'API nicht erreichbar.';
			loading = false;
			return;
		}
		if (!meta?.available) {
			loading = false;
			return;
		}
		api.meta().then((m) => (termOptions = m.terms)).catch(() => {});
		await reload();
		loading = false;
	}

	async function reload() {
		const t = terms;
		const [bp, mx, svo] = await Promise.allSettled([
			api.beifall.byParty(t),
			api.beifall.matrix(t),
			api.beifall.selfVsOther(t)
		]);
		if (bp.status === 'fulfilled') byParty = bp.value;
		if (mx.status === 'fulfilled') matrix = mx.value;
		if (svo.status === 'fulfilled') selfVsOther = svo.value;
	}

	$effect(() => { boot(); });

	let debounce: ReturnType<typeof setTimeout>;
	$effect(() => {
		void terms;
		if (!meta?.available) return;
		clearTimeout(debounce);
		debounce = setTimeout(reload, 200);
	});

	// ── derived ───────────────────────────────────────────────────────────────
	const isRealParty = (p: string | null | undefined): p is string =>
		!!p && p !== 'Unknown';

	const visibleByParty = $derived(byParty);
	const visibleMatrix = $derived(
		matrix.filter((r) => isRealParty(r.caller_party) && isRealParty(r.target_speaker_party))
	);

	const partyBars = $derived(
		[...visibleByParty]
			.sort((a, b) => partyFoundingOrder(a.caller_party) - partyFoundingOrder(b.caller_party))
			.map((p) => ({
				label: p.caller_party,
				value: p.n,
				color: partyColor(p.caller_party)
			}))
	);

	// Self-vs-other: one stacked bar per party
	const selfVsOtherBars = $derived((() => {
		const byPartyMap = new Map<string, { self: number; other: number }>();
		for (const row of selfVsOther) {
			if (!isRealParty(row.caller_party)) continue;
			const entry = byPartyMap.get(row.caller_party) ?? { self: 0, other: 0 };
			if (row.is_self) entry.self += row.n;
			else entry.other += row.n;
			byPartyMap.set(row.caller_party, entry);
		}
		return [...byPartyMap.entries()]
			.map(([party, { self, other }]) => ({
				party,
				self,
				other,
				total: self + other,
				selfPct: self + other > 0 ? Math.round((self / (self + other)) * 100) : 0,
				color: partyColor(party)
			}))
			.sort((a, b) => b.total - a.total);
	})());

	// Stat card values
	const topApplauder = $derived(visibleByParty[0] ?? null);
	const mostApplauded = $derived((() => {
		const totals = new Map<string, number>();
		for (const r of visibleMatrix) {
			if (isRealParty(r.target_speaker_party)) {
				totals.set(r.target_speaker_party, (totals.get(r.target_speaker_party) ?? 0) + r.n);
			}
		}
		let best = { party: '', n: 0 };
		for (const [p, n] of totals) if (n > best.n) best = { party: p, n };
		return best.party ? best : null;
	})());
	const mostSelfApplause = $derived(
		[...selfVsOtherBars].sort((a, b) => b.selfPct - a.selfPct)[0] ?? null
	);
</script>

<svelte:head>
	<title>{i18n.t('bf_title')} · OpenBundestag</title>
</svelte:head>

<div class="wrap page">
	<PageHero title={i18n.t('bf_title')} subtitle={i18n.t('bf_subtitle')} variant="gold" />

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
			<p>{i18n.t('bf_unavailable')}</p>
		</div>
	{:else}
		<!-- ── Stat cards ──────────────────────────────────────────────────── -->
		<div class="metrics">
			<div class="metric glass">
				<span class="m-num"><Counter value={meta.total} /></span>
				<span class="m-cap">{i18n.t('bf_total')}</span>
			</div>
			{#if topApplauder}
				<div class="metric glass" style:--lc={partyColor(topApplauder.caller_party)}>
					<span class="m-num small lead">
						<span class="lead-dot"></span>
						{topApplauder.caller_party}
					</span>
					<span class="m-sub">{formatNumber(topApplauder.n, i18n.lang)} ×</span>
					<span class="m-cap">{i18n.t('bf_loudest_party')}</span>
				</div>
			{/if}
			{#if mostApplauded}
				<div class="metric glass" style:--lc={partyColor(mostApplauded.party)}>
					<span class="m-num small lead">
						<span class="lead-dot"></span>
						{mostApplauded.party}
					</span>
					<span class="m-sub">{formatNumber(mostApplauded.n, i18n.lang)} ×</span>
					<span class="m-cap">{i18n.t('bf_most_applauded')}</span>
				</div>
			{/if}
			{#if mostSelfApplause}
				<div class="metric glass" style:--lc={partyColor(mostSelfApplause.party)}>
					<span class="m-num small lead">
						<span class="lead-dot"></span>
						{mostSelfApplause.party}
					</span>
					<span class="m-sub">{mostSelfApplause.selfPct}% {i18n.t('bf_self')}</span>
					<span class="m-cap">{i18n.t('bf_most_self')}</span>
				</div>
			{/if}
		</div>

		<!-- ── Filters ────────────────────────────────────────────────────── -->
		{#if termOptions.length}
			<div class="filter-bar glass">
				<TermFilter bind:selected={terms} options={termOptions} />
			</div>
		{/if}

		<!-- ── Adventure tabs ────────────────────────────────────────────── -->
		<div class="adventure-tabs" role="tablist">
			<button
				role="tab"
				aria-selected={activeView === 'matrix'}
				class="adv-tab"
				class:active={activeView === 'matrix'}
				onclick={() => (activeView = 'matrix')}
				style="--tab-color: var(--gold)"
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
					<span class="adv-title">{i18n.t('bf_matrix_title')}</span>
					<span class="adv-hint">{i18n.t('bf_adv_matrix')}</span>
				</div>
				<span class="adv-arrow">→</span>
			</button>

			<button
				role="tab"
				aria-selected={activeView === 'parties'}
				class="adv-tab"
				class:active={activeView === 'parties'}
				onclick={() => (activeView = 'parties')}
				style="--tab-color: #ffaa2a"
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
					<span class="adv-title">{i18n.t('bf_by_party_title')}</span>
					<span class="adv-hint">{i18n.t('bf_adv_parties')}</span>
				</div>
				<span class="adv-arrow">→</span>
			</button>

			<button
				role="tab"
				aria-selected={activeView === 'self'}
				class="adv-tab"
				class:active={activeView === 'self'}
				onclick={() => (activeView = 'self')}
				style="--tab-color: #ff8e3c"
			>
				<div class="adv-icon">
					<svg width="28" height="28" viewBox="0 0 28 28" fill="none" aria-hidden="true">
						<circle cx="14" cy="14" r="7" stroke="currentColor" stroke-width="1.8"/>
						<path d="M14 7v7l4 4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
						<path d="M6 22c2-3 5-4 8-4" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" opacity="0.6"/>
					</svg>
				</div>
				<div class="adv-body">
					<span class="adv-title">{i18n.t('bf_self_vs_other_title')}</span>
					<span class="adv-hint">{i18n.t('bf_adv_self')}</span>
				</div>
				<span class="adv-arrow">→</span>
			</button>
		</div>

		<!-- ── View panels ────────────────────────────────────────────────── -->
		{#if activeView === 'matrix'}
			<section class="panel glass">
				<header class="p-head">
					<div>
						<h3>{i18n.t('bf_matrix_title')}</h3>
						<p class="p-hint">{i18n.t('bf_matrix_hint')}</p>
					</div>
				</header>
				{#if visibleMatrix.length}
					<InterruptionMatrix
						rows={visibleMatrix}
						axisRow={i18n.t('mx_axis_applauding')}
						axisCol={i18n.t('mx_axis_applauded')}
						noun={i18n.t('mx_noun_bf')}
					/>
				{:else}
					<p class="empty">—</p>
				{/if}
			</section>
		{:else if activeView === 'parties'}
			<section class="panel glass">
				<header class="p-head"><h3>{i18n.t('bf_by_party_title')}</h3></header>
				{#if partyBars.length}
					<HBars bars={partyBars} valueLabel={i18n.t('bf_applause')} />
				{:else}
					<p class="empty">—</p>
				{/if}
			</section>
		{:else}
			<section class="panel glass">
				<header class="p-head">
					<div>
						<h3>{i18n.t('bf_self_vs_other_title')}</h3>
						<p class="p-hint">{i18n.t('bf_self_vs_other_hint')}</p>
					</div>
				</header>
				{#if selfVsOtherBars.length}
					<div class="svo-list">
						{#each selfVsOtherBars as row}
							<div class="svo-row">
								<div class="svo-label">
									<span class="svo-dot" style:background={row.color}></span>
									<span class="svo-party">{row.party}</span>
									<span class="svo-pct">{row.selfPct}% {i18n.t('bf_own_short')}</span>
								</div>
								<div class="svo-bar-wrap">
									<div
										class="svo-bar svo-self"
										style:width="{row.selfPct}%"
										style:background={row.color}
										title="{i18n.t('bf_self')}: {formatNumber(row.self, i18n.lang)}"
									></div>
									<div
										class="svo-bar svo-other"
										style:width="{100 - row.selfPct}%"
										title="{i18n.t('bf_other')}: {formatNumber(row.other, i18n.lang)}"
									></div>
								</div>
								<div class="svo-counts">
									<span class="svo-n self-n">{formatNumber(row.self, i18n.lang)}</span>
									<span class="svo-sep">·</span>
									<span class="svo-n other-n">{formatNumber(row.other, i18n.lang)}</span>
								</div>
							</div>
						{/each}
						<div class="svo-legend">
							<span class="leg-swatch swatch-self"></span><span>{i18n.t('bf_self')}</span>
							<span class="leg-swatch swatch-other"></span><span>{i18n.t('bf_other')}</span>
						</div>
					</div>
				{:else}
					<p class="empty">—</p>
				{/if}
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
		background: conic-gradient(from 0deg, var(--gold), #ff8e3c, var(--gold));
		filter: blur(2px);
		animation: orb 1.6s ease infinite, spin 3s linear infinite;
		box-shadow: 0 0 32px 4px color-mix(in srgb, var(--gold) 40%, transparent);
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
		background: linear-gradient(90deg, var(--gold), #ff8e3c);
		opacity: 0.8;
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
		padding: 0.75rem 1.2rem;
	}

	/* ── Adventure tabs ── */
	.adventure-tabs {
		display: grid;
		grid-template-columns: repeat(3, 1fr);
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

	/* ── Self vs Other ── */
	.svo-list {
		display: flex;
		flex-direction: column;
		gap: 0.85rem;
	}
	.svo-row {
		display: grid;
		grid-template-columns: 10rem 1fr 7rem;
		align-items: center;
		gap: 0.85rem;
	}
	.svo-label {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		min-width: 0;
	}
	.svo-dot {
		width: 8px; height: 8px;
		border-radius: 50%;
		flex: none;
	}
	.svo-party {
		font-size: 0.82rem;
		font-weight: 600;
		color: var(--ink);
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}
	.svo-pct {
		font-size: 0.72rem;
		color: var(--ink-3);
		white-space: nowrap;
	}
	.svo-bar-wrap {
		display: flex;
		height: 10px;
		border-radius: 999px;
		overflow: hidden;
		background: var(--surface-2);
	}
	.svo-bar {
		height: 100%;
		transition: width 0.5s var(--spring);
	}
	.svo-self {
		opacity: 0.85;
	}
	.svo-other {
		background: color-mix(in srgb, var(--ink-3) 30%, transparent);
	}
	.svo-counts {
		display: flex;
		align-items: center;
		gap: 0.3rem;
		font-size: 0.75rem;
		justify-content: flex-end;
	}
	.svo-n { color: var(--ink-2); }
	.self-n { color: var(--gold); font-weight: 600; }
	.svo-sep { color: var(--ink-3); }

	.svo-legend {
		display: flex;
		align-items: center;
		gap: 0.6rem;
		font-size: 0.75rem;
		color: var(--ink-3);
		margin-top: 0.5rem;
		padding-top: 0.75rem;
		border-top: 1px solid var(--line);
	}
	.leg-swatch {
		width: 20px; height: 8px;
		border-radius: 999px;
		flex: none;
	}
	.swatch-self { background: var(--gold); opacity: 0.85; }
	.swatch-other { background: color-mix(in srgb, var(--ink-3) 30%, transparent); }

	.empty {
		color: var(--ink-3);
		text-align: center;
		padding: 2rem 0;
	}

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
		border-color: var(--gold);
	}

	@media (max-width: 900px) {
		.metrics { grid-template-columns: repeat(2, 1fr); }
		.adventure-tabs { grid-template-columns: repeat(2, 1fr); }
	}
	@media (max-width: 640px) {
		.svo-row { grid-template-columns: 1fr; }
		.svo-counts { justify-content: flex-start; }
	}
	@media (max-width: 540px) {
		.metrics { grid-template-columns: 1fr; }
		.adventure-tabs { grid-template-columns: 1fr; }
	}
</style>

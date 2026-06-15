<script lang="ts">
	import { api } from '$lib/api';
	import { i18n } from '$lib/i18n.svelte';
	import { partyColor, formatNumber, partyFoundingOrder } from '$lib/format';
	import Counter from '$lib/components/Counter.svelte';
	import HBars from '$lib/components/HBars.svelte';
	import PageHero from '$lib/components/PageHero.svelte';
	import InterruptionMatrix from '$lib/components/InterruptionMatrix.svelte';
	import ZwischenrufFeed from '$lib/components/ZwischenrufFeed.svelte';
	import TermFilter from '$lib/components/TermFilter.svelte';
	import type {
		ZwischenrufMeta,
		ZwischenrufCallerCount,
		ZwischenrufPartyCount,
		ZwischenrufMatrixRow,
		ZwischenrufSample,
		TermInfo
	} from '$lib/types';

	// ── state ─────────────────────────────────────────────────────────────────
	let meta = $state<ZwischenrufMeta | null>(null);
	let termOptions = $state<TermInfo[]>([]);
	let topCallers = $state<ZwischenrufCallerCount[]>([]);
	let byParty = $state<ZwischenrufPartyCount[]>([]);
	let matrix = $state<ZwischenrufMatrixRow[]>([]);
	let loading = $state(true);
	let bootError = $state<string | null>(null);

	let terms = $state<number[]>([21]);
	let activeView = $state<'matrix' | 'parties' | 'callers' | 'feed'>('matrix');

	// ── politician search (matrix panel only) ─────────────────────────────────
	let callerNameSearch = $state('');
	let callerSamples = $state<ZwischenrufSample[]>([]);
	let callerSamplesLoading = $state(false);
	let callerSamplesDebounce: ReturnType<typeof setTimeout>;

	$effect(() => {
		const name = callerNameSearch.trim();
		void terms;
		if (!name || !meta?.available) { callerSamples = []; return; }
		clearTimeout(callerSamplesDebounce);
		callerSamplesDebounce = setTimeout(async () => {
			callerSamplesLoading = true;
			try {
				callerSamples = await api.zwischenrufe.samples({ callerName: name, terms, limit: 500 });
			} finally {
				callerSamplesLoading = false;
			}
		}, 350);
	});

	const callerTargetBars = $derived((() => {
		if (!callerSamples.length) return [];
		const totals = new Map<string, number>();
		for (const s of callerSamples) {
			if (s.target_speaker_party) {
				totals.set(s.target_speaker_party, (totals.get(s.target_speaker_party) ?? 0) + 1);
			}
		}
		return [...totals.entries()]
			.sort((a, b) => b[1] - a[1])
			.map(([party, n]) => ({ label: party, value: n, color: partyColor(party) }));
	})());

	const callerInfo = $derived(
		callerSamples.length > 0
			? { name: callerSamples[0].caller_name, party: callerSamples[0].caller_party }
			: null
	);

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
		api.meta().then((m) => (termOptions = m.terms)).catch(() => {});
		await reload();
		loading = false;
	}

	async function reload() {
		const t = terms;
		const [tc, bp, mx] = await Promise.allSettled([
			api.zwischenrufe.topCallers('Zwischenruf', t, undefined, 20),
			api.zwischenrufe.byParty('Zwischenruf', t),
			api.zwischenrufe.matrix('Zwischenruf', t)
		]);
		if (tc.status === 'fulfilled') topCallers = tc.value;
		if (bp.status === 'fulfilled') byParty = bp.value;
		if (mx.status === 'fulfilled') matrix = mx.value;
	}

	$effect(() => {
		boot();
	});

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

	const visibleTopCallers = $derived(topCallers);
	const visibleByParty = $derived(byParty);
	const visibleMatrix = $derived(
		matrix.filter((r) => isRealParty(r.caller_party) && isRealParty(r.target_speaker_party))
	);

	const callerBars = $derived(
		visibleTopCallers.map((c) => ({
			label: c.caller_name,
			sub: c.caller_party,
			value: c.n,
			color: partyColor(c.caller_party)
		}))
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

	const topCaller = $derived(visibleTopCallers[0] ?? null);
	const topCallerParty = $derived(visibleByParty[0] ?? null);
	const topTarget = $derived(
		(() => {
			const totals = new Map<string, number>();
			for (const r of visibleMatrix) {
				totals.set(r.target_speaker_party, (totals.get(r.target_speaker_party) ?? 0) + r.n);
			}
			let best = { party: '', n: 0 };
			for (const [p, n] of totals) if (n > best.n) best = { party: p, n };
			return best.party ? best : null;
		})()
	);

</script>

<svelte:head>
	<title>{i18n.t('zw_title')} · OpenBundestag</title>
</svelte:head>

<div class="wrap page">
	<PageHero title={i18n.t('zw_title')} subtitle={i18n.t('zw_subtitle')} variant="warm" />

	<p class="explainer">{i18n.t('zw_explainer')}</p>

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
				<div class="metric glass" style:--lc={partyColor(topCaller.caller_party)}>
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
				style="--tab-color: var(--spark)"
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
				style="--tab-color: #ff8c55"
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
				style="--tab-color: #e03050"
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
				style="--tab-color: #ff9eb5"
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
					<div class="p-search-wrap">
						<svg class="p-search-icon" width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
							<circle cx="6" cy="6" r="4.5" stroke="currentColor" stroke-width="1.4"/>
							<line x1="9.5" y1="9.5" x2="13" y2="13" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/>
						</svg>
						<input
							class="p-search"
							type="search"
							placeholder="Person suchen…"
							bind:value={callerNameSearch}
						/>
					</div>
				</header>

				{#if callerNameSearch.trim()}
					{#if callerSamplesLoading}
						<div class="spotlight-loading"><span class="pulse-dot"></span></div>
					{:else if callerTargetBars.length}
						<div class="spotlight">
							{#if callerInfo}
								<p class="spotlight-meta">
									<span class="spotlight-name">{callerInfo.name}</span>
									{#if callerInfo.party}
										<span class="spotlight-party" style:background={partyColor(callerInfo.party)}>{callerInfo.party}</span>
									{/if}
									<span class="spotlight-count">unterbrach {callerSamples.length}× die…</span>
								</p>
							{/if}
							<HBars bars={callerTargetBars} valueLabel={i18n.t('zw_calls')} />
						</div>
					{:else}
						<p class="empty">{i18n.t('zw_no_results')}</p>
					{/if}
				{:else}
					{#if visibleMatrix.length}
						<InterruptionMatrix rows={visibleMatrix} showSamples={true} />
					{:else}
						<p class="empty">—</p>
					{/if}
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
				<ZwischenrufFeed {terms} />
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

	.explainer {
		font-size: 0.88rem;
		color: var(--ink-2);
		line-height: 1.6;
		max-width: 68ch;
		margin: 0;
		padding: 0.75rem 1rem;
		border-left: 2px solid #ff5d7d55;
		background: rgba(255, 93, 125, 0.04);
		border-radius: 0 6px 6px 0;
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
		background: conic-gradient(from 0deg, #ff5d7d, #ff4e4e, #ff8c55, #ff5d7d);
		filter: blur(2px);
		animation: orb 1.6s ease infinite, spin 3s linear infinite;
		box-shadow: 0 0 32px 4px rgba(255, 93, 125, 0.4);
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
		background: linear-gradient(90deg, #ff5d7d, #ff4e4e, #ff8c55);
		opacity: 0.85;
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

	/* ── Panel politician search ── */
	.p-search-wrap {
		position: relative;
		flex-shrink: 0;
	}
	.p-search-icon {
		position: absolute;
		left: 0.75rem;
		top: 50%;
		transform: translateY(-50%);
		color: var(--ink-3);
		pointer-events: none;
	}
	.p-search {
		padding: 0.45rem 0.85rem 0.45rem 2.2rem;
		background: var(--surface-2);
		border: 1px solid var(--line-2);
		border-radius: 999px;
		color: var(--ink);
		font: inherit;
		font-size: 0.85rem;
		width: 18rem;
		outline: none;
		transition: border-color 0.2s, box-shadow 0.2s;
	}
	.p-search:focus {
		border-color: #ff5d7d;
		box-shadow: 0 0 0 3px rgba(255, 93, 125, 0.15);
	}
	.p-search::placeholder { color: var(--ink-3); }

	/* ── Politician spotlight ── */
	.spotlight-loading {
		display: flex;
		justify-content: center;
		padding: 2rem;
	}
	.pulse-dot {
		width: 10px; height: 10px;
		border-radius: 50%;
		background: #ff5d7d;
		animation: pulse 1.4s ease infinite;
	}
	@keyframes pulse {
		0% { box-shadow: 0 0 0 0 rgba(255, 93, 125, 0.55); }
		70% { box-shadow: 0 0 0 10px rgba(255, 93, 125, 0); }
		100% { box-shadow: 0 0 0 0 rgba(255, 93, 125, 0); }
	}
	.spotlight-meta {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		flex-wrap: wrap;
		margin: 0 0 1rem;
		font-size: 0.85rem;
	}
	.spotlight-name {
		font-weight: 700;
		color: var(--ink);
	}
	.spotlight-party {
		font-size: 0.7rem;
		font-weight: 700;
		padding: 0.15rem 0.5rem;
		border-radius: 999px;
		color: #fff;
	}
	.spotlight-count {
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
		border-color: #ff5d7d;
	}

	@media (max-width: 900px) {
		.metrics { grid-template-columns: repeat(2, 1fr); }
		.adventure-tabs { grid-template-columns: repeat(2, 1fr); }
	}
	@media (max-width: 640px) {
		.p-search { width: 100%; }
		.p-head { flex-direction: column; }
	}
	@media (max-width: 540px) {
		.metrics { grid-template-columns: 1fr; }
		.adventure-tabs { grid-template-columns: 1fr; }
	}
</style>

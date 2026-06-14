<script lang="ts">
	import type { Filters, Meta, Politician } from '$lib/types';
	import { i18n } from '$lib/i18n.svelte';
	import { api } from '$lib/api';
	import { partyColor, partyFullName } from '$lib/format';

	let {
		filters = $bindable(),
		meta,
		viewMode = $bindable<'parties' | 'politicians'>('parties')
	}: { filters: Filters; meta: Meta; viewMode: 'parties' | 'politicians' } = $props();

	let showHistorical = $state(false);
	const historical = $derived(new Set(meta.historical_parties));
	const visibleParties = $derived(
		showHistorical ? meta.parties : meta.parties.filter((p) => !historical.has(p))
	);

	const fromYear = $derived(+meta.min_date.slice(0, 4));
	const toYear = $derived(+meta.max_date.slice(0, 4));
	const years = $derived(
		Array.from({ length: toYear - fromYear + 1 }, (_, i) => fromYear + i)
	);

	let yFrom = $state(+(filters.date_from ?? '2010-01-01').slice(0, 4));
	let yTo = $state(+(filters.date_to ?? '2026-12-31').slice(0, 4));
	$effect(() => {
		filters.date_from = `${yFrom}-01-01`;
		filters.date_to = `${yTo}-12-31`;
	});

	function setMode(m: 'parties' | 'politicians') {
		if (m === viewMode) return;
		viewMode = m;
		if (m === 'politicians') {
			filters.parties = [];
		} else {
			clearPol();
		}
	}

	function toggleParty(p: string) {
		filters.parties = filters.parties.includes(p)
			? filters.parties.filter((x) => x !== p)
			: [...filters.parties, p];
	}

	// --- politician typeahead -------------------------------------------------
	let polQuery = $state('');
	let polResults = $state<Politician[]>([]);
	let polName = $state('');
	let polOpen = $state(false);
	let timer: ReturnType<typeof setTimeout>;

	function onPolInput(v: string) {
		polQuery = v;
		polOpen = true;
		clearTimeout(timer);
		timer = setTimeout(async () => {
			polResults = v.trim() ? await api.politicians(v.trim(), 8).catch(() => []) : [];
		}, 200);
	}
	function pickPol(p: Politician) {
		filters.politician_id = p.id;
		polName = p.name;
		polQuery = p.name;
		polOpen = false;
	}
	function clearPol() {
		filters.politician_id = null;
		polName = '';
		polQuery = '';
		polResults = [];
	}
</script>

<div class="panel">
	<!-- Mode switch -->
	<section class="mode-section">
		<span class="lbl">{i18n.t('analyse_by')}</span>
		<div class="mode-seg">
			<button class:on={viewMode === 'parties'} onclick={() => setMode('parties')}>
				<svg width="13" height="13" viewBox="0 0 13 13" fill="none" aria-hidden="true">
					<circle cx="4" cy="6.5" r="2.8" stroke="currentColor" stroke-width="1.4"/>
					<circle cx="9" cy="6.5" r="2.8" stroke="currentColor" stroke-width="1.4"/>
				</svg>
				{i18n.t('tab_parties')}
			</button>
			<button class:on={viewMode === 'politicians'} onclick={() => setMode('politicians')}>
				<svg width="13" height="13" viewBox="0 0 13 13" fill="none" aria-hidden="true">
					<circle cx="6.5" cy="4" r="2.3" stroke="currentColor" stroke-width="1.4"/>
					<path d="M1.5 11.5c0-2.761 2.239-5 5-5s5 2.239 5 5" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/>
				</svg>
				{i18n.t('tab_speakers')}
			</button>
		</div>
	</section>

	<section>
		<label class="lbl" for="kw">{i18n.t('keyword')}</label>
		<input
			id="kw"
			class="kw"
			bind:value={filters.word}
			maxlength={meta.keyword_max_len}
			placeholder={i18n.t('keyword_ph')}
			autocomplete="off"
		/>
		<div class="suggestions">
			{#each ['Schuldenbremse', 'Klimawandel', 'Migration', 'Digitalisierung', 'Rente', 'Ukraine'] as w (w)}
				<button class="suggestion" onclick={() => (filters.word = w)}>{w}</button>
			{/each}
		</div>
	</section>

	{#if viewMode === 'parties'}
		<section>
			<div class="lbl-row">
				<span class="lbl">{i18n.t('parties')}</span>
				<label class="hist">
					<input type="checkbox" bind:checked={showHistorical} />
					{i18n.t('incl_historical')}
				</label>
			</div>
			<div class="chips">
				{#each visibleParties as p (p)}
					<button
						class="chip"
						class:on={filters.parties.includes(p)}
						style:--c={partyColor(p)}
						onclick={() => toggleParty(p)}
						data-tip={partyFullName(p)}
					>
						<span class="dot" style:background={partyColor(p)}></span>{p}
					</button>
				{/each}
			</div>
			{#if filters.parties.length === 0}<p class="hint">{i18n.t('all_parties')}</p>{/if}
		</section>
	{:else}
		<section class="pol">
			<label class="lbl" for="pol">{i18n.t('politician')}</label>
			<div class="pol-input">
				<input
					id="pol"
					value={polQuery}
					oninput={(e) => onPolInput(e.currentTarget.value)}
					onfocus={() => (polOpen = true)}
					placeholder={i18n.t('any_politician')}
					autocomplete="off"
				/>
				{#if filters.politician_id != null}
					<button class="clr" onclick={clearPol} aria-label="clear">✕</button>
				{/if}
				{#if polOpen && polResults.length}
					<ul class="dropdown">
						{#each polResults as p (p.id)}
							<li>
								<button onclick={() => pickPol(p)}>
									<span class="dot" style:background={partyColor(p.party)}></span>
									{p.name}<span class="muted"> · {p.party}</span>
								</button>
							</li>
						{/each}
					</ul>
				{/if}
			</div>
			{#if filters.politician_id == null}<p class="hint">{i18n.t('any_politician_hint')}</p>{/if}
		</section>
	{/if}

	<section>
		<span class="lbl">{i18n.t('period')}</span>
		<div class="range">
			<select bind:value={yFrom}>
				{#each years.filter((y) => y <= yTo) as y (y)}<option value={y}>{y}</option>{/each}
			</select>
			<span class="dash">–</span>
			<select bind:value={yTo}>
				{#each years.filter((y) => y >= yFrom) as y (y)}<option value={y}>{y}</option>{/each}
			</select>
		</div>
	</section>

	<section class="opts">
		<span class="lbl">{i18n.t('granularity')}</span>
		<div class="seg">
			<button class:on={filters.granularity === 'Monthly'} onclick={() => (filters.granularity = 'Monthly')}>
				{i18n.t('monthly')}
			</button>
			<button
				class:on={filters.granularity === 'Quarterly'}
				onclick={() => (filters.granularity = 'Quarterly')}
			>
				{i18n.t('quarterly')}
			</button>
		</div>
		<span class="lbl">{i18n.t('count_by')}</span>
		<div class="seg">
			<button class:on={filters.count_mode === 'speeches'} onclick={() => (filters.count_mode = 'speeches')}>
				{i18n.t('speeches')}
			</button>
			<button
				class:on={filters.count_mode === 'occurrences'}
				onclick={() => (filters.count_mode = 'occurrences')}
			>
				{i18n.t('occurrences')}
			</button>
		</div>
	</section>
</div>

<style>
	.panel {
		display: flex;
		flex-direction: column;
		gap: 1.4rem;
	}
	.lbl {
		display: block;
		font-size: 0.78rem;
		font-weight: 600;
		letter-spacing: 0.06em;
		text-transform: uppercase;
		color: var(--ink-3);
		margin-bottom: 0.5rem;
	}

	/* Mode switch */
	.mode-section {
		padding-bottom: 1.1rem;
		border-bottom: 1px solid var(--line);
	}
	.mode-seg {
		display: flex;
		gap: 0;
		border: 1px solid var(--line-2);
		border-radius: var(--radius-sm);
		overflow: hidden;
	}
	.mode-seg button {
		flex: 1;
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 0.4rem;
		font: inherit;
		font-size: 0.84rem;
		font-weight: 600;
		padding: 0.6rem 0.5rem;
		border: none;
		background: var(--card);
		color: var(--ink-3);
		cursor: pointer;
		transition: background 0.18s, color 0.18s;
	}
	.mode-seg button.on {
		background: var(--accent);
		color: #fff;
	}
	.mode-seg button.on svg {
		opacity: 0.9;
	}

	.lbl-row {
		display: flex;
		justify-content: space-between;
		align-items: baseline;
		gap: 0.5rem;
	}
	.hist {
		font-size: 0.74rem;
		color: var(--ink-3);
		display: flex;
		align-items: center;
		gap: 0.3rem;
		cursor: pointer;
		text-transform: none;
		letter-spacing: 0;
	}
	.kw,
	.pol-input input,
	.range select {
		width: 100%;
		font: inherit;
		padding: 0.6rem 0.7rem;
		border: 1px solid var(--line-2);
		border-radius: var(--radius-sm);
		background: var(--card);
		color: var(--ink);
	}
	.kw {
		font-size: 1.05rem;
		font-weight: 500;
	}
	.suggestions {
		display: flex;
		flex-wrap: wrap;
		gap: 0.3rem;
		margin-top: 0.5rem;
	}
	.suggestion {
		font: inherit;
		font-size: 0.74rem;
		padding: 0.2rem 0.6rem;
		border-radius: 999px;
		border: 1px solid var(--line-2);
		background: none;
		color: var(--ink-3);
		cursor: pointer;
		transition: color 0.15s, border-color 0.15s;
	}
	.suggestion:hover {
		color: var(--accent);
		border-color: var(--accent);
	}
	.chips {
		display: flex;
		flex-wrap: wrap;
		gap: 0.35rem;
	}
	.chip {
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
		font: inherit;
		font-size: 0.78rem;
		font-weight: 500;
		padding: 0.3rem 0.65rem;
		border-radius: 999px;
		border: 1px solid var(--line-2);
		background: var(--card);
		color: var(--ink-2);
		cursor: pointer;
		transition: all 0.18s;
	}
	.chip.on {
		border-color: var(--c, var(--accent));
		background: color-mix(in srgb, var(--c, var(--accent)) 12%, var(--card));
		color: var(--ink);
	}
	.dot {
		width: 8px;
		height: 8px;
		border-radius: 50%;
		flex: none;
	}
	.hint {
		margin: 0.45rem 0 0;
		font-size: 0.76rem;
		color: var(--ink-3);
		font-style: italic;
	}
	.pol-input {
		position: relative;
	}
	.clr {
		position: absolute;
		right: 0.5rem;
		top: 50%;
		transform: translateY(-50%);
		border: none;
		background: none;
		cursor: pointer;
		color: var(--ink-3);
	}
	.dropdown {
		position: absolute;
		z-index: 5;
		top: calc(100% + 4px);
		left: 0;
		right: 0;
		list-style: none;
		margin: 0;
		padding: 0.3rem;
		background: var(--card);
		border: 1px solid var(--line-2);
		border-radius: var(--radius-sm);
		box-shadow: var(--shadow);
		max-height: 240px;
		overflow-y: auto;
	}
	.dropdown button {
		width: 100%;
		text-align: left;
		font: inherit;
		font-size: 0.85rem;
		display: flex;
		align-items: center;
		gap: 0.45rem;
		padding: 0.45rem 0.5rem;
		border: none;
		background: none;
		border-radius: 6px;
		cursor: pointer;
		color: var(--ink);
	}
	.dropdown button:hover {
		background: var(--paper-2);
	}
	.muted {
		color: var(--ink-3);
	}
	.range {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}
	.dash {
		color: var(--ink-3);
	}
	.opts {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}
	.seg {
		display: flex;
		gap: 0;
		border: 1px solid var(--line-2);
		border-radius: var(--radius-sm);
		overflow: hidden;
		margin-bottom: 0.4rem;
	}
	.seg button {
		flex: 1;
		font: inherit;
		font-size: 0.82rem;
		padding: 0.5rem;
		border: none;
		background: var(--card);
		color: var(--ink-2);
		cursor: pointer;
	}
	.seg button.on {
		background: var(--ink);
		color: var(--paper);
	}
</style>

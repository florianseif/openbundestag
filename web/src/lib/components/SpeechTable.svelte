<script lang="ts">
	import { fly } from 'svelte/transition';
	import { api } from '$lib/api';
	import type { Filters, SpeechItem, SpeechFull } from '$lib/types';
	import { i18n } from '$lib/i18n.svelte';
	import { partyColor, formatDate } from '$lib/format';

	let { filters }: { filters: Filters } = $props();

	const PAGE = 20;
	let offset = $state(0);
	let items = $state<SpeechItem[]>([]);
	let total = $state(0);
	let loading = $state(false);
	let openId = $state<number | null>(null);
	let fullCache = $state<Record<number, SpeechFull>>({});
	let fullLoading = $state<number | null>(null);

	// Reset page when filters change, then fetch.
	let _filterKey = $derived(
		[filters.word, ...(filters.parties), ...(filters.terms.map(String)),
		 String(filters.politician_id), filters.date_from, filters.date_to].join('|')
	);
	$effect(() => {
		_filterKey; // track
		offset = 0;
	});

	$effect(() => {
		_filterKey; offset; // track both
		if (!filters.word.trim()) { items = []; total = 0; return; }
		loading = true;
		openId = null;
		Promise.all([api.speeches(filters, PAGE, offset), api.total(filters)])
			.then(([page, tot]) => { items = page.items; total = tot.count; })
			.catch(() => {})
			.finally(() => (loading = false));
	});

	const pages = $derived(Math.ceil(total / PAGE));
	const currentPage = $derived(Math.floor(offset / PAGE) + 1);

	async function toggle(id: number) {
		if (openId === id) { openId = null; return; }
		openId = id;
		if (!fullCache[id]) {
			fullLoading = id;
			try { fullCache[id] = await api.speech(id); } catch { /* ignore */ }
			finally { fullLoading = null; }
		}
	}

	async function download(item: SpeechItem) {
		if (!fullCache[item.id]) {
			try { fullCache[item.id] = await api.speech(item.id); } catch { /* ignore */ }
		}
		const full = fullCache[item.id];
		const body = full?.speech_content ?? item.snippet ?? '';
		const rule = '─'.repeat(64);
		const lines = [
			'OpenBundestag — Plenarrede', rule,
			`Sprecher:    ${item.politician}`,
			`Partei:      ${item.party}`,
			`Datum:       ${formatDate(item.date, i18n.lang)}`,
			`Wahlperiode: ${item.electoral_term}`,
			`Sitzung:     ${item.session}`,
			rule, '', body, '',
			rule, 'Quelle: Deutscher Bundestag · bundestag.de/services/opendata'
		].join('\n');
		const a = document.createElement('a');
		a.href = URL.createObjectURL(new Blob([lines], { type: 'text/plain;charset=utf-8' }));
		a.download = `rede-${item.id}-${item.politician.replace(/\s+/g, '-').toLowerCase()}.txt`;
		a.click();
		URL.revokeObjectURL(a.href);
	}

	function segs(text: string) {
		const w = filters.word.trim();
		if (!w) return [{ t: text, hit: false }];
		const re = new RegExp(`(${w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi');
		return text.split(re).map((t) => ({ t, hit: t.toLowerCase() === w.toLowerCase() }));
	}

	function protocolUrl(item: SpeechItem) {
		return `https://dserver.bundestag.de/btp/${String(item.electoral_term).padStart(2, '0')}/${item.session}.pdf`;
	}
</script>

<div class="table-wrap">
	{#if loading}
		<div class="loading">
			{#each Array(5) as _, i (i)}<div class="sk" style:--d="{i * 60}ms"></div>{/each}
		</div>
	{:else if !items.length}
		<p class="empty">{i18n.t('no_results', { word: filters.word })}</p>
	{:else}
		<div class="count">{total.toLocaleString(i18n.lang === 'de' ? 'de-DE' : 'en-GB')} {i18n.t('matching_speeches')}</div>

		<ul class="list">
			{#each items as s, idx (s.id)}
				<li class="row" class:open={openId === s.id} style:--d="{idx * 30}ms">
					<button class="row-head" onclick={() => toggle(s.id)}>
						<span class="date">{formatDate(s.date, i18n.lang)}</span>
						<span class="who">
							<span class="dot" style:background={partyColor(s.party)}></span>
							<strong>{s.politician}</strong>
						</span>
						<span class="party" style:color={partyColor(s.party)}>{s.party}</span>
						<span class="role">{s.position_long ?? s.position_short}</span>
						{#if s.snippet}
							<span class="snip">…{#each segs(s.snippet.slice(0, 120)) as seg}{#if seg.hit}<mark>{seg.t}</mark>{:else}{seg.t}{/if}{/each}…</span>
						{/if}
						<span class="chev" class:up={openId === s.id}>⌄</span>
					</button>

					{#if openId === s.id}
						<div class="detail" transition:fly={{ y: -6, duration: 200 }}>
							{#if fullLoading === s.id}
								<div class="sk tall"></div>
							{:else if fullCache[s.id]?.speech_content}
								<p class="full">
									{#each segs(fullCache[s.id].speech_content!) as seg}{#if seg.hit}<mark>{seg.t}</mark>{:else}{seg.t}{/if}{/each}
								</p>
							{:else}
								<p class="unavail">{i18n.t('fulltext_unavailable')}</p>
							{/if}
							<div class="actions">
								<button class="btn--ghost mini" onclick={() => download(s)}>⤓ {i18n.t('download')}</button>
								<a class="btn--ghost mini" href={protocolUrl(s)} target="_blank" rel="noopener noreferrer">
									⤓ {i18n.t('download_protocol')}
								</a>
							</div>
						</div>
					{/if}
				</li>
			{/each}
		</ul>

		{#if pages > 1}
			<div class="pagination">
				<button class="pg-btn" disabled={offset === 0} onclick={() => (offset -= PAGE)}>‹ {i18n.t('prev')}</button>
				<span class="pg-info">{currentPage} / {pages}</span>
				<button class="pg-btn" disabled={currentPage >= pages} onclick={() => (offset += PAGE)}>{i18n.t('next')} ›</button>
			</div>
		{/if}
	{/if}
</div>

<style>
	.table-wrap {
		min-height: 320px;
	}
	.count {
		font-size: 0.78rem;
		color: var(--ink-3);
		margin-bottom: 0.8rem;
	}
	.loading {
		display: flex;
		flex-direction: column;
		gap: 0.6rem;
		padding-top: 0.4rem;
	}
	.sk {
		height: 52px;
		border-radius: 8px;
		background: linear-gradient(90deg, var(--surface-2), var(--surface-3), var(--surface-2));
		background-size: 200% 100%;
		animation: shimmer 1.3s infinite;
		animation-delay: var(--d, 0ms);
	}
	.sk.tall { height: 140px; }
	@keyframes shimmer { to { background-position: -200% 0; } }

	.list {
		list-style: none;
		margin: 0;
		padding: 0;
	}
	.row {
		border-bottom: 1px solid var(--line);
		animation: rise 0.45s var(--ease) backwards;
		animation-delay: var(--d, 0ms);
	}
	@keyframes rise {
		from { opacity: 0; transform: translateY(6px); }
	}
	.row-head {
		width: 100%;
		display: grid;
		grid-template-columns: 6.5rem 1fr auto auto;
		grid-template-rows: auto auto;
		column-gap: 0.75rem;
		row-gap: 0.2rem;
		align-items: baseline;
		padding: 0.75rem 0.2rem;
		background: none;
		border: none;
		cursor: pointer;
		text-align: left;
		font: inherit;
		color: var(--ink);
		transition: background 0.15s;
	}
	.row-head:hover { background: var(--surface-2); border-radius: var(--radius-sm); }
	.date {
		font-size: 0.78rem;
		color: var(--ink-3);
		font-variant-numeric: tabular-nums;
		grid-row: 1;
		grid-column: 1;
	}
	.who {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		grid-row: 1;
		grid-column: 2;
		font-size: 0.9rem;
	}
	.dot {
		width: 8px;
		height: 8px;
		border-radius: 50%;
		flex: none;
	}
	.party {
		grid-row: 1;
		grid-column: 3;
		font-size: 0.75rem;
		font-weight: 600;
	}
	.chev {
		grid-row: 1;
		grid-column: 4;
		color: var(--ink-3);
		font-size: 1.1rem;
		transition: transform 0.25s var(--ease);
		align-self: center;
	}
	.chev.up { transform: rotate(180deg); color: var(--accent); }
	.role {
		grid-row: 2;
		grid-column: 2;
		font-size: 0.75rem;
		color: var(--ink-3);
	}
	.snip {
		grid-row: 2;
		grid-column: 2 / 5;
		font-size: 0.78rem;
		color: var(--ink-2);
		line-height: 1.5;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}
	mark {
		background: linear-gradient(180deg, transparent 55%, rgba(255, 206, 92, 0.45) 55%);
		color: var(--ink);
		padding: 0 0.05em;
		border-radius: 2px;
		font-weight: 600;
	}
	.detail {
		padding: 0.6rem 0.2rem 1rem 1.2rem;
		border-left: 2px solid var(--accent);
		margin: 0 0 0.5rem 0.3rem;
	}
	.full {
		font-size: 0.88rem;
		line-height: 1.7;
		color: var(--ink);
		max-height: 280px;
		overflow-y: auto;
		margin: 0 0 0.8rem;
		white-space: pre-wrap;
	}
	.unavail {
		font-size: 0.82rem;
		color: var(--ink-3);
		font-style: italic;
		margin: 0 0 0.8rem;
	}
	.actions {
		display: flex;
		gap: 0.5rem;
		flex-wrap: wrap;
	}
	.mini {
		padding: 0.45rem 0.9rem;
		font-size: 0.82rem;
		text-decoration: none;
	}
	.pagination {
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 1rem;
		padding-top: 1.2rem;
	}
	.pg-btn {
		font: inherit;
		font-size: 0.85rem;
		padding: 0.45rem 1rem;
		border: 1px solid var(--line-2);
		border-radius: 999px;
		background: var(--surface);
		color: var(--ink-2);
		cursor: pointer;
		transition: color 0.15s, border-color 0.15s;
	}
	.pg-btn:hover:not(:disabled) { color: var(--ink); border-color: var(--line-3); }
	.pg-btn:disabled { opacity: 0.35; cursor: default; }
	.pg-info {
		font-size: 0.82rem;
		color: var(--ink-3);
		font-variant-numeric: tabular-nums;
	}
	.empty {
		color: var(--ink-3);
		text-align: center;
		padding: 3rem 0;
		font-size: 0.9rem;
	}

	@media (max-width: 600px) {
		.row-head {
			grid-template-columns: 5.5rem 1fr auto;
		}
		.party { display: none; }
		.snip { grid-column: 2 / 4; }
	}
</style>

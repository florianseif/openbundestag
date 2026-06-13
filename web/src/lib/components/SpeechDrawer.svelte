<script lang="ts">
	import { fly, fade } from 'svelte/transition';
	import { api } from '$lib/api';
	import type { Filters, SpeechPage } from '$lib/types';
	import { i18n } from '$lib/i18n.svelte';
	import { partyColor, formatDate } from '$lib/format';

	// When `query` is non-null the drawer is open and loads matching speeches.
	// The full reader + download UI lands in a later phase; this is the shell
	// that proves the click → fetch → panel path end-to-end.
	let {
		query,
		title,
		onclose
	}: { query: Filters | null; title: string; onclose: () => void } = $props();

	let page = $state<SpeechPage | null>(null);
	let loading = $state(false);
	let error = $state<string | null>(null);

	$effect(() => {
		const q = query;
		page = null;
		error = null;
		if (!q) return;
		loading = true;
		api
			.speeches(q, 15, 0)
			.then((p) => (page = p))
			.catch((e) => (error = e.message))
			.finally(() => (loading = false));
	});
</script>

{#if query}
	<div class="scrim" transition:fade={{ duration: 200 }} onclick={onclose} role="presentation"></div>
	<aside class="drawer" transition:fly={{ x: 420, duration: 320 }} aria-label="Speech detail">
		<header>
			<div>
				<div class="eyebrow">{title}</div>
				<h3>{i18n.t('read_passage')}</h3>
			</div>
			<button class="x" onclick={onclose} aria-label={i18n.t('close')}>✕</button>
		</header>

		<p class="soon">{i18n.t('drilldown_soon')}</p>

		{#if loading}
			<div class="skeleton">
				{#each Array(4) as _, i (i)}<div class="sk"></div>{/each}
			</div>
		{:else if error}
			<p class="err">{error}</p>
		{:else if page}
			<ul class="list">
				{#each page.items as s (s.id)}
					<li>
						<div class="meta">
							<span class="pill" style:background={partyColor(s.party)}></span>
							<strong>{s.politician}</strong>
							<span class="muted">· {s.party}</span>
							<span class="muted date">{formatDate(s.date, i18n.lang)}</span>
						</div>
						{#if s.snippet}
							<p class="snippet">…{s.snippet}…</p>
						{:else}
							<p class="snippet muted">
								{s.position_long ?? s.position_short} · WP {s.electoral_term}
							</p>
						{/if}
					</li>
				{/each}
			</ul>
		{/if}
	</aside>
{/if}

<style>
	.scrim {
		position: fixed;
		inset: 0;
		background: rgba(20, 18, 14, 0.42);
		z-index: 40;
	}
	.drawer {
		position: fixed;
		top: 0;
		right: 0;
		bottom: 0;
		width: min(440px, 92vw);
		background: var(--card);
		border-left: 1px solid var(--line);
		box-shadow: var(--shadow-lg);
		z-index: 41;
		padding: 1.4rem 1.4rem 2rem;
		overflow-y: auto;
	}
	header {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		gap: 1rem;
	}
	h3 {
		margin: 0.1rem 0 0;
	}
	.x {
		font-size: 1rem;
		background: none;
		border: 1px solid var(--line-2);
		border-radius: 999px;
		width: 34px;
		height: 34px;
		cursor: pointer;
		color: var(--ink-2);
		flex: none;
	}
	.soon {
		font-size: 0.82rem;
		color: var(--ink-3);
		background: var(--paper-2);
		border-radius: var(--radius-sm);
		padding: 0.6rem 0.75rem;
		margin: 0.9rem 0 1.2rem;
	}
	.list {
		list-style: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: 0.9rem;
	}
	.list li {
		border-bottom: 1px solid var(--line);
		padding-bottom: 0.9rem;
	}
	.meta {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		font-size: 0.85rem;
		flex-wrap: wrap;
	}
	.pill {
		width: 10px;
		height: 10px;
		border-radius: 3px;
		flex: none;
	}
	.muted {
		color: var(--ink-3);
	}
	.date {
		margin-left: auto;
	}
	.snippet {
		margin: 0.4rem 0 0;
		font-size: 0.88rem;
		line-height: 1.55;
		color: var(--ink-2);
	}
	.err {
		color: #b3261e;
		font-size: 0.85rem;
	}
	.skeleton {
		display: flex;
		flex-direction: column;
		gap: 0.8rem;
	}
	.sk {
		height: 48px;
		border-radius: 8px;
		background: linear-gradient(90deg, var(--paper-2), var(--line), var(--paper-2));
		background-size: 200% 100%;
		animation: shimmer 1.3s infinite;
	}
	@keyframes shimmer {
		to {
			background-position: -200% 0;
		}
	}
</style>

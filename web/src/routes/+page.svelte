<script lang="ts">
	import { goto } from '$app/navigation';
	import stories from '$lib/stories.json';
	import StoryPanel from '$lib/components/StoryPanel.svelte';
	import ParliamentArc from '$lib/components/ParliamentArc.svelte';
	import { i18n } from '$lib/i18n.svelte';

	let kw = $state('');
	function search(e: SubmitEvent) {
		e.preventDefault();
		const w = kw.trim();
		goto(`/explore${w ? `?word=${encodeURIComponent(w)}` : ''}`);
	}
</script>

<svelte:head>
	<title>OpenBundestag — {i18n.t('tagline')}</title>
</svelte:head>

<section class="hero">
	<div class="hero-inner wrap">
		<div class="hero-text">
			<div class="stats-strip reveal">
				<span>1949 – {new Date().getFullYear()}</span>
				<span class="sep">·</span>
				<span>~760.000 {i18n.t('speeches')}</span>
				<span class="sep">·</span>
				<span>{i18n.lang === 'de' ? '76 Jahre Demokratie' : '76 years of democracy'}</span>
			</div>

			<h1 class="reveal d1">{i18n.t('tagline')}</h1>
			<p class="lede reveal d2">{i18n.t('hero_sub')}</p>

			<form class="search reveal d3" onsubmit={search}>
				<input
					bind:value={kw}
					placeholder={i18n.t('keyword_ph')}
					aria-label={i18n.t('keyword')}
					maxlength="80"
				/>
				<button class="btn-hero" type="submit">{i18n.t('cta_try')}</button>
			</form>

			<div class="quick reveal d3">
				{#each ['Klimawandel', 'Digitalisierung', 'Frieden', 'Europa'] as q (q)}
					<a href="/explore?word={encodeURIComponent(q)}" class="quick-chip">{q}</a>
				{/each}
			</div>
		</div>

		<div class="hero-arc reveal d2" aria-hidden="true">
			<ParliamentArc />
			<p class="arc-cap">
				{i18n.lang === 'de'
					? 'Anteil nach Redebeiträgen · jede Farbe eine Partei'
					: 'Share of speeches · each colour a party'}
			</p>
		</div>
	</div>

	<div class="scroll-hint" aria-hidden="true">
		<span>{i18n.t('scroll_hint')}</span>
		<div class="mouse"></div>
	</div>

	<div class="hero-fade" aria-hidden="true"></div>
</section>

<section class="stories wrap">
	<header class="s-head">
		<h2>{i18n.t('stories_title')}</h2>
		<p class="lede">{i18n.t('stories_lead')}</p>
	</header>
	{#each stories as story, i (story.word)}
		<StoryPanel {story} index={i} />
	{/each}
</section>

<section class="cta-band">
	<div class="wrap">
		<h2>{i18n.t('cta_band_title')}</h2>
		<p class="lede">{i18n.t('cta_band_sub')}</p>
		<a class="btn" href="/explore">{i18n.t('nav_wortsuche')} →</a>
	</div>
</section>

<style>
	/* ── Hero ─────────────────────────────────────────────────────────── */
	.hero {
		position: relative;
		background: var(--bg);
		overflow: hidden;
		padding-bottom: clamp(4rem, 10vh, 7rem);
	}

	/* Aurora nebula in background */
	.hero::before {
		content: '';
		position: absolute;
		inset: 0;
		background:
			radial-gradient(60% 55% at 70% 36%, rgba(107, 145, 255, 0.22) 0%, transparent 70%),
			radial-gradient(50% 45% at 18% 78%, rgba(169, 139, 255, 0.16) 0%, transparent 68%),
			radial-gradient(42% 38% at 88% 84%, rgba(255, 142, 198, 0.12) 0%, transparent 62%);
		pointer-events: none;
		z-index: 0;
	}
	/* faint grid texture */
	.hero::after {
		content: '';
		position: absolute;
		inset: 0;
		background-image:
			linear-gradient(rgba(255, 255, 255, 0.025) 1px, transparent 1px),
			linear-gradient(90deg, rgba(255, 255, 255, 0.025) 1px, transparent 1px);
		background-size: 64px 64px;
		mask-image: radial-gradient(70% 70% at 50% 30%, #000 0%, transparent 80%);
		pointer-events: none;
		z-index: 0;
	}

	.hero-inner {
		position: relative;
		z-index: 1;
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: clamp(2rem, 5vw, 5rem);
		align-items: center;
		padding-top: clamp(4rem, 12vh, 8rem);
	}

	/* ── Hero text ─────────────────────────────────────────────────────── */
	.hero-text {
		color: var(--ink);
	}

	.stats-strip {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.4rem 0.6rem;
		font-family: var(--sans);
		font-size: 0.78rem;
		font-weight: 600;
		letter-spacing: 0.12em;
		text-transform: uppercase;
		color: var(--accent);
		margin-bottom: 1.1rem;
	}
	.sep { color: color-mix(in srgb, var(--accent) 45%, transparent); }

	h1 {
		font-size: clamp(3.4rem, 8vw, 6.2rem);
		font-weight: 700;
		line-height: 1.0;
		letter-spacing: -0.025em;
		color: var(--ink);
		max-width: 14ch;
		margin: 0 0 1rem;
		/* very subtle gradient: top warm-white → slightly blue-shifted white */
		background: linear-gradient(160deg, #ffffff 0%, #d4e4ff 100%);
		-webkit-background-clip: text;
		-webkit-text-fill-color: transparent;
		background-clip: text;
	}

	.lede {
		font-size: clamp(1rem, 1.8vw, 1.2rem);
		line-height: 1.6;
		color: var(--ink-2);
		max-width: 46ch;
		margin: 0 0 1.8rem;
	}

	.search {
		display: flex;
		gap: 0.5rem;
		margin-bottom: 1rem;
		max-width: 480px;
	}
	.search input {
		flex: 1;
		font: inherit;
		font-size: 1.05rem;
		padding: 0.88rem 1.2rem;
		border-radius: 999px;
		border: 1px solid var(--line-2);
		background: color-mix(in srgb, var(--surface-2) 70%, transparent);
		color: var(--ink);
		backdrop-filter: blur(8px);
		-webkit-backdrop-filter: blur(8px);
		transition: border-color 0.2s, background 0.2s, box-shadow 0.2s;
	}
	.search input::placeholder { color: var(--ink-3); }
	.search input:focus {
		outline: none;
		border-color: color-mix(in srgb, var(--accent) 60%, transparent);
		background: var(--surface-2);
		box-shadow: 0 0 0 3px color-mix(in srgb, var(--accent) 16%, transparent);
	}

	.btn-hero {
		display: inline-flex;
		align-items: center;
		gap: 0.5rem;
		font: inherit;
		font-weight: 700;
		font-size: 0.98rem;
		padding: 0.88rem 1.5rem;
		border-radius: 999px;
		border: none;
		background: var(--grad);
		color: #0a0a12;
		cursor: pointer;
		white-space: nowrap;
		transition: transform 0.22s var(--spring), box-shadow 0.22s var(--ease), filter 0.18s;
		box-shadow: var(--glow);
	}
	.btn-hero:hover {
		transform: translateY(-2px);
		filter: brightness(1.06);
		box-shadow: 0 0 50px -6px rgba(107, 145, 255, 0.7);
	}

	.quick {
		display: flex;
		flex-wrap: wrap;
		gap: 0.45rem;
	}
	.quick-chip {
		display: inline-flex;
		align-items: center;
		padding: 0.3rem 0.85rem;
		border-radius: 999px;
		border: 1px solid var(--line-2);
		color: var(--ink-2);
		font-size: 0.85rem;
		font-weight: 500;
		transition: border-color 0.18s, color 0.18s, background 0.18s;
	}
	.quick-chip:hover {
		border-color: color-mix(in srgb, var(--accent) 55%, transparent);
		color: var(--ink);
		background: color-mix(in srgb, var(--accent) 14%, transparent);
		text-decoration: none;
	}

	/* ── Parliament arc ────────────────────────────────────────────────── */
	.hero-arc {
		position: relative;
		display: flex;
		flex-direction: column;
		align-items: center;
	}
	.arc-cap {
		margin: 0.5rem 0 0;
		font-size: 0.7rem;
		font-weight: 500;
		letter-spacing: 0.1em;
		text-transform: uppercase;
		color: color-mix(in srgb, var(--accent) 60%, transparent);
		text-align: center;
	}

	/* ── Scroll hint ───────────────────────────────────────────────────── */
	.scroll-hint {
		position: relative;
		z-index: 1;
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 0.5rem;
		padding-top: clamp(2rem, 5vh, 3.5rem);
		font-size: 0.7rem;
		letter-spacing: 0.16em;
		text-transform: uppercase;
		color: var(--ink-3);
	}
	.mouse {
		width: 22px;
		height: 34px;
		border: 2px solid var(--line-3);
		border-radius: 12px;
		position: relative;
	}
	.mouse::after {
		content: '';
		position: absolute;
		top: 6px;
		left: 50%;
		transform: translateX(-50%);
		width: 3px;
		height: 7px;
		border-radius: 2px;
		background: var(--ink-3);
		animation: scroll 1.8s var(--ease) infinite;
	}
	@keyframes scroll {
		0%   { opacity: 0; transform: translate(-50%, 0); }
		40%  { opacity: 1; }
		100% { opacity: 0; transform: translate(-50%, 10px); }
	}

	/* Gradient fade hero → paper */
	.hero-fade {
		position: absolute;
		inset: auto 0 0 0;
		height: 90px;
		background: linear-gradient(to bottom, transparent, var(--paper));
		pointer-events: none;
		z-index: 2;
	}

	/* ── Entrance animations ──────────────────────────────────────────── */
	.reveal {
		opacity: 0;
		transform: translateY(18px);
		animation: rise 0.9s var(--ease) forwards;
	}
	.d1 { animation-delay: 0.08s; }
	.d2 { animation-delay: 0.2s; }
	.d3 { animation-delay: 0.32s; }
	@keyframes rise {
		to { opacity: 1; transform: none; }
	}
	@media (prefers-reduced-motion: reduce) {
		.reveal {
			animation: none;
			opacity: 1;
			transform: none;
		}
		.mouse::after { animation: none; }
	}

	/* ── Stories ──────────────────────────────────────────────────────── */
	.s-head {
		text-align: center;
		max-width: 46ch;
		margin: clamp(3rem, 8vw, 5rem) auto 1rem;
	}
	.s-head .lede {
		color: var(--ink-2);
		margin: 0 auto;
	}

	/* ── CTA band ─────────────────────────────────────────────────────── */
	.cta-band {
		position: relative;
		margin-top: 3rem;
		padding: clamp(3.5rem, 9vw, 6rem) 0;
		text-align: center;
		overflow: hidden;
		border-top: 1px solid var(--line);
		background:
			radial-gradient(60% 120% at 50% 0%, rgba(169, 139, 255, 0.16), transparent 70%),
			var(--bg-2);
	}
	.cta-band :global(h2) {
		background: var(--grad);
		-webkit-background-clip: text;
		background-clip: text;
		-webkit-text-fill-color: transparent;
	}
	.cta-band .lede {
		color: var(--ink-2);
		margin: 0 auto 1.8rem;
		max-width: 52ch;
	}

	/* ── Responsive ───────────────────────────────────────────────────── */
	@media (max-width: 860px) {
		.hero-inner {
			grid-template-columns: 1fr;
		}
		.hero-arc {
			order: -1;
			margin-top: -1rem;
		}
		h1 {
			max-width: none;
		}
	}
	@media (max-width: 480px) {
		.search {
			flex-direction: column;
			max-width: 100%;
		}
		.btn-hero { width: 100%; justify-content: center; }
	}
</style>

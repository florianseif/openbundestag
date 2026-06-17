<script lang="ts">
	import '../app.css';
	import { page } from '$app/state';
	import LangToggle from '$lib/components/LangToggle.svelte';
	import { i18n } from '$lib/i18n.svelte';

	let { children } = $props();
	const onWortsuche = $derived(page.url.pathname.startsWith('/explore'));
	const onZwischenrufe = $derived(page.url.pathname.startsWith('/zwischenrufe'));
	const onBeifall = $derived(page.url.pathname.startsWith('/beifall'));
	const onAbout = $derived(page.url.pathname.startsWith('/about'));
</script>

<header class="site">
	<div class="aurora-line" aria-hidden="true"></div>
	<div class="wrap bar">
		<a class="brand" href="/">
			<span class="mark" aria-hidden="true">
				<svg width="20" height="20" viewBox="0 0 20 20" fill="none" aria-hidden="true">
					<rect x="2" y="2" width="7" height="7" rx="2" fill="url(#mg)"/>
					<rect x="11" y="2" width="7" height="7" rx="2" fill="url(#mg)" opacity="0.7"/>
					<rect x="2" y="11" width="7" height="7" rx="2" fill="url(#mg)" opacity="0.7"/>
					<rect x="11" y="11" width="7" height="7" rx="2" fill="url(#mg)" opacity="0.45"/>
					<defs>
						<linearGradient id="mg" x1="0" y1="0" x2="20" y2="20" gradientUnits="userSpaceOnUse">
							<stop stop-color="#6b91ff"/>
							<stop offset="0.52" stop-color="#a98bff"/>
							<stop offset="1" stop-color="#ff8ec6"/>
						</linearGradient>
					</defs>
				</svg>
			</span>
			<span class="name">OpenBundestag</span>
			<span class="tag">· {i18n.t('tagline')}</span>
		</a>

		<nav>
			<a
				class="nav-pill"
				class:active={onWortsuche}
				href="/explore"
				style="--pill-color: var(--accent)"
			>
				<span class="pill-dot" aria-hidden="true"></span>
				{i18n.t('nav_wortsuche')}
			</a>

			<a
				class="nav-pill"
				class:active={onZwischenrufe}
				href="/zwischenrufe"
				style="--pill-color: var(--spark)"
			>
				<span class="pill-dot" aria-hidden="true"></span>
				{i18n.t('nav_zwischenrufe')}
			</a>

			<a
				class="nav-pill"
				class:active={onBeifall}
				href="/beifall"
				style="--pill-color: var(--gold)"
			>
				<span class="pill-dot" aria-hidden="true"></span>
				{i18n.t('nav_beifall')}
			</a>

			<a
				class="nav-pill"
				class:active={onAbout}
				href="/about"
				style="--pill-color: var(--accent-2)"
			>
				{i18n.lang === 'de' ? 'Über' : 'About'}
			</a>

			<LangToggle />
		</nav>
	</div>
</header>

<main>
	{@render children()}
</main>

<footer class="site">
	<div class="wrap">
		<p class="ft-title">{i18n.t('footer_data')}</p>
		<p class="ft-body">{i18n.t('footer_body')}</p>
		<p class="ft-attr">
			© Deutscher Bundestag ·
			<a href="https://www.bundestag.de/services/opendata">bundestag.de/services/opendata</a>
		</p>
		<p class="ft-attr ft-data">
			<a href="https://huggingface.co/datasets/MissionJupiter/openbundestag-db" target="_blank" rel="noopener noreferrer">
				Dataset herunterladen (HuggingFace) ↗
			</a>
			·
			<a href="https://github.com/florianseif/openbundestag" target="_blank" rel="noopener noreferrer">
				GitHub ↗
			</a>
		</p>
	</div>
</footer>

<style>
	/* ── Header shell ── */
	header.site {
		position: sticky;
		top: 0;
		z-index: 30;
		backdrop-filter: saturate(1.6) blur(18px);
		background: color-mix(in srgb, var(--bg) 78%, transparent);
		/* no border-bottom — aurora line replaces it */
	}
	.aurora-line {
		height: 1.5px;
		background: var(--grad);
		opacity: 0.55;
	}
	.bar {
		display: flex;
		align-items: center;
		justify-content: space-between;
		height: 68px;
	}

	/* ── Brand ── */
	.brand {
		display: flex;
		align-items: center;
		gap: 0.6rem;
		color: var(--ink);
		font-weight: 700;
		text-decoration: none;
	}
	.brand:hover { color: var(--ink); }
	.mark {
		flex: none;
		transition: transform 0.45s var(--spring), filter 0.3s;
		filter: drop-shadow(0 0 6px rgba(107, 145, 255, 0.5));
	}
	.brand:hover .mark {
		transform: rotate(90deg) scale(1.08);
		filter: drop-shadow(0 0 12px rgba(169, 139, 255, 0.7));
	}
	.name {
		font-family: var(--display);
		font-weight: 700;
		font-size: 1.18rem;
		letter-spacing: -0.025em;
	}
	.tag {
		color: var(--ink-3);
		font-weight: 500;
		font-size: 0.86rem;
	}

	/* ── Nav ── */
	nav {
		display: flex;
		align-items: center;
		gap: 0.6rem;
	}

	/* Nav pills — glass with per-link accent */
	.nav-pill {
		display: inline-flex;
		align-items: center;
		gap: 0.42rem;
		font-size: 0.88rem;
		font-weight: 600;
		color: var(--ink-2);
		text-decoration: none;
		padding: 0.4rem 0.95rem;
		border-radius: 999px;
		border: 1px solid transparent;
		transition: color 0.2s, border-color 0.2s, background 0.2s, box-shadow 0.2s, transform 0.2s var(--spring);
	}
	.nav-pill:hover {
		color: var(--ink);
		border-color: color-mix(in srgb, var(--pill-color, var(--accent)) 40%, transparent);
		background: color-mix(in srgb, var(--pill-color, var(--accent)) 8%, transparent);
		transform: translateY(-1px);
		box-shadow: 0 4px 16px -4px color-mix(in srgb, var(--pill-color, var(--accent)) 30%, transparent);
	}
	.nav-pill.active {
		color: var(--ink);
		border-color: color-mix(in srgb, var(--pill-color, var(--accent)) 55%, transparent);
		background: color-mix(in srgb, var(--pill-color, var(--accent)) 10%, transparent);
		box-shadow:
			0 0 0 1px color-mix(in srgb, var(--pill-color, var(--accent)) 25%, transparent),
			0 4px 20px -4px color-mix(in srgb, var(--pill-color, var(--accent)) 35%, transparent);
	}
	.pill-dot {
		width: 6px;
		height: 6px;
		border-radius: 50%;
		background: var(--pill-color, var(--accent));
		box-shadow: 0 0 6px 1px var(--pill-color, var(--accent));
		flex: none;
		transition: box-shadow 0.2s;
	}
	.nav-pill.active .pill-dot {
		box-shadow: 0 0 10px 2px var(--pill-color, var(--accent));
	}

	main {
		min-height: 70vh;
	}

	/* ── Footer ── */
	footer.site {
		border-top: 1px solid var(--line);
		margin-top: 5rem;
		padding: 2.6rem 0 3.4rem;
		background: var(--bg-2);
	}
	.ft-title {
		font-weight: 600;
		margin: 0 0 0.4rem;
	}
	.ft-body {
		max-width: 62ch;
		color: var(--ink-2);
		font-size: 0.9rem;
		margin: 0 0 0.6rem;
	}
	.ft-attr {
		font-size: 0.82rem;
		color: var(--ink-3);
		margin: 0;
	}
	.ft-data {
		margin-top: 0.5rem;
	}
	.ft-data a {
		color: var(--accent);
	}

	@media (max-width: 640px) {
		.tag { display: none; }
		/* Stack: brand on top, nav becomes a full-width swipeable pill strip
		   so every destination stays reachable instead of overflowing the page. */
		.bar {
			flex-wrap: wrap;
			height: auto;
			padding: 0.55rem 0 0.6rem;
			row-gap: 0.5rem;
		}
		nav {
			flex: 1 1 100%;
			width: 100%;
			gap: 0.4rem;
			flex-wrap: nowrap;
			overflow-x: auto;
			-webkit-overflow-scrolling: touch;
			scrollbar-width: none;
			/* room so the focus ring / scroll isn't clipped */
			padding-bottom: 2px;
		}
		nav::-webkit-scrollbar { display: none; }
		.nav-pill {
			flex: none;
			white-space: nowrap;
			padding: 0.5rem 0.85rem;
			min-height: 40px;
			font-size: 0.84rem;
		}
	}
	@media (max-width: 420px) {
		.name { font-size: 1rem; }
	}
</style>

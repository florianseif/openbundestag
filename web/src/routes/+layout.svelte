<script lang="ts">
	import '../app.css';
	import { page } from '$app/state';
	import LangToggle from '$lib/components/LangToggle.svelte';
	import { i18n } from '$lib/i18n.svelte';

	let { children } = $props();
	const onExplore = $derived(page.url.pathname.startsWith('/explore'));
</script>

<header class="site">
	<div class="wrap bar">
		<a class="brand" href="/">
			<span class="mark" aria-hidden="true"></span>
			<span class="name">OpenBundestag</span>
			<span class="tag">· {i18n.t('tagline')}</span>
		</a>
		<nav>
			{#if !onExplore}
				<a class="navlink" href="/explore">{i18n.t('cta_explore')} →</a>
			{/if}
			<a class="navlink" href="/about">{i18n.lang === 'de' ? 'Über' : 'About'}</a>
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
	header.site {
		position: sticky;
		top: 0;
		z-index: 30;
		backdrop-filter: saturate(1.4) blur(14px);
		background: color-mix(in srgb, var(--bg) 72%, transparent);
		border-bottom: 1px solid var(--line);
	}
	.bar {
		display: flex;
		align-items: center;
		justify-content: space-between;
		height: 66px;
	}
	.brand {
		display: flex;
		align-items: center;
		gap: 0.55rem;
		color: var(--ink);
		font-weight: 700;
	}
	.brand:hover {
		color: var(--ink);
	}
	.mark {
		width: 16px;
		height: 16px;
		border-radius: 5px;
		background: var(--grad);
		box-shadow: var(--glow);
		flex: none;
		transition: transform 0.4s var(--spring);
	}
	.brand:hover .mark {
		transform: rotate(45deg) scale(1.1);
	}
	.name {
		font-family: var(--display);
		font-weight: 600;
		font-size: 1.15rem;
		letter-spacing: -0.02em;
	}
	.tag {
		color: var(--ink-3);
		font-weight: 500;
		font-size: 0.88rem;
	}
	nav {
		display: flex;
		align-items: center;
		gap: 1.1rem;
	}
	.navlink {
		font-weight: 600;
		font-size: 0.92rem;
		color: var(--ink);
		transition: color 0.2s;
	}
	.navlink:hover {
		color: var(--accent);
	}
	main {
		min-height: 70vh;
	}
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
	@media (max-width: 560px) {
		.tag {
			display: none;
		}
	}
</style>

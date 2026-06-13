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
			<span class="mark">🏛️</span>
			<span class="name">OpenBundestag</span>
			<span class="tag">· {i18n.t('tagline')}</span>
		</a>
		<nav>
			{#if !onExplore}
				<a class="navlink" href="/explore">{i18n.t('cta_explore')}</a>
			{/if}
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
	</div>
</footer>

<style>
	header.site {
		position: sticky;
		top: 0;
		z-index: 30;
		backdrop-filter: saturate(1.4) blur(10px);
		background: color-mix(in srgb, var(--paper) 82%, transparent);
		border-bottom: 1px solid var(--line);
	}
	.bar {
		display: flex;
		align-items: center;
		justify-content: space-between;
		height: 64px;
	}
	.brand {
		display: flex;
		align-items: baseline;
		gap: 0.45rem;
		color: var(--ink);
		font-weight: 700;
	}
	.brand:hover {
		text-decoration: none;
	}
	.mark {
		font-size: 1.2rem;
	}
	.name {
		font-family: var(--serif);
		font-size: 1.2rem;
	}
	.tag {
		color: var(--ink-3);
		font-weight: 500;
		font-size: 0.9rem;
	}
	nav {
		display: flex;
		align-items: center;
		gap: 1rem;
	}
	.navlink {
		font-weight: 600;
		font-size: 0.92rem;
		color: var(--ink);
	}
	main {
		min-height: 70vh;
	}
	footer.site {
		border-top: 1px solid var(--line);
		margin-top: 4rem;
		padding: 2.4rem 0 3rem;
		background: var(--paper-2);
	}
	.ft-title {
		font-weight: 600;
		margin: 0 0 0.4rem;
	}
	.ft-body {
		max-width: 60ch;
		color: var(--ink-2);
		font-size: 0.9rem;
		margin: 0 0 0.6rem;
	}
	.ft-attr {
		font-size: 0.82rem;
		color: var(--ink-3);
		margin: 0;
	}
	@media (max-width: 560px) {
		.tag {
			display: none;
		}
	}
</style>

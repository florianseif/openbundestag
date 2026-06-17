<script lang="ts">
	import Sparkline from './Sparkline.svelte';
	import { i18n } from '$lib/i18n.svelte';
	import { partyColor, formatNumber } from '$lib/format';

	interface Story {
		word: string;
		blurb_de: string;
		blurb_en: string;
		total: number;
		peak_year: number;
		peak_value: number;
		top_party: string;
		series: { year: number; value: number }[];
	}
	let { story, index }: { story: Story; index: number } = $props();

	let el: HTMLElement;
	let visible = $state(false);
	let progress = $state(0);
	let count = $state(0);

	const color = $derived(partyColor(story.top_party));
	const blurb = $derived(i18n.lang === 'de' ? story.blurb_de : story.blurb_en);

	$effect(() => {
		const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
		const io = new IntersectionObserver(
			([e]) => {
				if (!e.isIntersecting || visible) return;
				visible = true;
				if (reduce) {
					progress = 1;
					count = story.total;
					return;
				}
				const start = performance.now();
				const dur = 1100;
				const tick = (now: number) => {
					const p = Math.min(1, (now - start) / dur);
					const eased = 1 - Math.pow(1 - p, 3);
					progress = eased;
					count = Math.round(story.total * eased);
					if (p < 1) requestAnimationFrame(tick);
				};
				requestAnimationFrame(tick);
			},
			{ threshold: 0.35 }
		);
		io.observe(el);
		return () => io.disconnect();
	});
</script>

<article class="story" class:visible bind:this={el} class:rev={index % 2 === 1}>
	<div class="text">
		<div class="eyebrow" style:color>{story.top_party}</div>
		<h2>„{story.word}“</h2>
		<p class="blurb">{blurb}</p>
		<div class="stats">
			<div>
				<span class="num">{formatNumber(count, i18n.lang)}</span>
				<span class="cap">{i18n.t('metric_speeches')}</span>
			</div>
			<div>
				<span class="num">{story.peak_year}</span>
				<span class="cap">{i18n.lang === 'de' ? 'Höhepunkt' : 'Peak year'}</span>
			</div>
		</div>
	</div>
	<a
		class="viz"
		style:--c={color}
		href="/explore?word={encodeURIComponent(story.word)}"
		aria-label="{i18n.t('story_open')}: {story.word}"
	>
		<Sparkline series={story.series} {color} {progress} />
		<div class="axis">
			<span>{story.series[0]?.year}</span>
			<span>{story.series[story.series.length - 1]?.year}</span>
		</div>
		<span class="viz-cta">{i18n.t('story_open')} →</span>
	</a>
</article>

<style>
	.story {
		display: grid;
		grid-template-columns: 1fr 1.1fr;
		gap: clamp(1.5rem, 5vw, 4rem);
		align-items: center;
		padding: clamp(2rem, 6vw, 4.5rem) 0;
		opacity: 0;
		transform: translateY(28px);
		transition:
			opacity 0.7s var(--ease),
			transform 0.7s var(--ease);
	}
	.story.visible {
		opacity: 1;
		transform: none;
	}
	.story.rev .text {
		order: 2;
	}
	h2 {
		font-size: clamp(2rem, 4.5vw, 3.2rem);
		margin: 0.2rem 0 0.6rem;
	}
	.blurb {
		font-size: 1.1rem;
		color: var(--ink-2);
		max-width: 40ch;
	}
	.stats {
		display: flex;
		gap: 2.4rem;
		margin-top: 1.4rem;
	}
	.num {
		display: block;
		font-family: var(--serif);
		font-size: 2rem;
		font-weight: 600;
		font-variant-numeric: tabular-nums;
		line-height: 1;
	}
	.cap {
		font-size: 0.8rem;
		color: var(--ink-3);
	}
	.viz {
		position: relative;
		height: 240px;
		border-radius: var(--radius);
		background: linear-gradient(180deg, color-mix(in srgb, var(--c) 7%, var(--card)), var(--card));
		border: 1px solid var(--line);
		padding: 1rem 1rem 0.4rem;
		display: flex;
		flex-direction: column;
		text-decoration: none;
		transition: transform 0.28s var(--spring), border-color 0.28s var(--ease), box-shadow 0.28s var(--ease);
	}
	.viz:hover {
		transform: translateY(-4px);
		border-color: color-mix(in srgb, var(--c) 50%, var(--line));
		box-shadow: 0 18px 44px -14px color-mix(in srgb, var(--c) 45%, transparent);
	}
	.viz-cta {
		position: absolute;
		right: 1rem;
		top: 0.9rem;
		font-size: 0.74rem;
		font-weight: 600;
		letter-spacing: 0.01em;
		color: var(--c);
		opacity: 0;
		transform: translateY(4px);
		transition: opacity 0.25s var(--ease), transform 0.25s var(--ease);
		pointer-events: none;
	}
	.viz:hover .viz-cta,
	.viz:focus-visible .viz-cta {
		opacity: 1;
		transform: none;
	}
	.viz:focus-visible {
		outline: 2px solid color-mix(in srgb, var(--c) 70%, var(--line-3));
		outline-offset: 3px;
	}
	@media (prefers-reduced-motion: reduce) {
		.viz { transition: none; }
		.viz:hover { transform: none; }
	}
	.viz :global(svg) {
		flex: 1;
	}
	.axis {
		display: flex;
		justify-content: space-between;
		font-size: 0.74rem;
		color: var(--ink-3);
		padding-top: 0.3rem;
	}
	@media (max-width: 760px) {
		.story {
			grid-template-columns: 1fr;
		}
		.story.rev .text {
			order: 0;
		}
	}
</style>

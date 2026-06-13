<script lang="ts">
	import { pie, arc } from 'd3-shape';
	import { i18n } from '$lib/i18n.svelte';
	import { formatNumber } from '$lib/format';

	interface Slice {
		label: string;
		value: number;
		color: string;
	}
	let { slices }: { slices: Slice[] } = $props();

	const R = 120;
	const total = $derived(slices.reduce((s, d) => s + d.value, 0));
	const arcs = $derived(
		pie<Slice>()
			.value((d) => d.value)
			.sort(null)(slices)
	);
	const gen = arc<(typeof arcs)[number]>()
		.innerRadius(R * 0.58)
		.outerRadius(R)
		.padAngle(0.012)
		.cornerRadius(3);

	let hover = $state<number | null>(null);
	const active = $derived(hover != null ? slices[hover] : null);
</script>

<div class="donut">
	<svg viewBox="{-R - 4} {-R - 4} {2 * R + 8} {2 * R + 8}" role="img" aria-label="Share by party">
		{#each arcs as a, i (a.data.label)}
			<path
				d={gen(a)}
				fill={a.data.color}
				stroke="var(--surface)"
				stroke-width="1.5"
				opacity={hover == null || hover === i ? 1 : 0.32}
				transform={hover === i ? 'scale(1.04)' : 'scale(1)'}
				onmouseenter={() => (hover = i)}
				onmouseleave={() => (hover = null)}
				role="presentation"
			/>
		{/each}
		<text class="center-v" text-anchor="middle" dy="-0.1em">
			{active ? formatNumber(active.value, i18n.lang) : formatNumber(total, i18n.lang)}
		</text>
		<text class="center-l" text-anchor="middle" dy="1.3em">
			{active ? active.label : i18n.t('metric_speeches')}
		</text>
	</svg>
</div>

<style>
	.donut {
		display: flex;
		justify-content: center;
	}
	svg {
		width: 100%;
		max-width: 300px;
		height: auto;
	}
	path {
		cursor: pointer;
		transform-origin: center;
		transition:
			opacity 0.2s,
			transform 0.25s var(--spring);
	}
	.center-v {
		fill: var(--ink);
		font-family: var(--serif);
		font-size: 2rem;
		font-weight: 600;
	}
	.center-l {
		fill: var(--ink-3);
		font-size: 0.8rem;
		font-family: var(--sans);
	}
</style>

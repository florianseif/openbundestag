<script lang="ts">
	import { scaleLinear } from 'd3-scale';
	import { line, area, curveMonotoneX } from 'd3-shape';

	interface Point {
		year: number;
		value: number;
	}
	let {
		series,
		color = 'var(--accent)',
		progress = 1
	}: { series: Point[]; color?: string; progress?: number } = $props();

	const W = 600;
	const H = 200;
	const pad = { t: 12, r: 8, b: 8, l: 8 };

	const x = $derived(
		scaleLinear()
			.domain([series[0]?.year ?? 0, series[series.length - 1]?.year ?? 1])
			.range([pad.l, W - pad.r])
	);
	const y = $derived(
		scaleLinear()
			.domain([0, Math.max(1, ...series.map((d) => d.value))])
			.range([H - pad.b, pad.t])
	);

	// progress (0..1) reveals the line left-to-right as the story scrolls in.
	const shown = $derived(series.slice(0, Math.max(2, Math.ceil(series.length * progress))));

	const linePath = $derived(
		line<Point>()
			.x((d) => x(d.year))
			.y((d) => y(d.value))
			.curve(curveMonotoneX)(shown) ?? ''
	);
	const areaPath = $derived(
		area<Point>()
			.x((d) => x(d.year))
			.y0(H - pad.b)
			.y1((d) => y(d.value))
			.curve(curveMonotoneX)(shown) ?? ''
	);
	const last = $derived(shown[shown.length - 1]);
	const gid = `sg-${Math.random().toString(36).slice(2, 8)}`;
</script>

<svg viewBox="0 0 {W} {H}" preserveAspectRatio="none" class="spark" role="img" aria-hidden="true">
	<defs>
		<linearGradient id={gid} x1="0" x2="0" y1="0" y2="1">
			<stop offset="0%" stop-color={color} stop-opacity="0.32" />
			<stop offset="100%" stop-color={color} stop-opacity="0" />
		</linearGradient>
	</defs>
	<path d={areaPath} fill="url(#{gid})" />
	<path d={linePath} fill="none" stroke={color} stroke-width="3" stroke-linecap="round" />
	{#if last}
		<circle cx={x(last.year)} cy={y(last.value)} r="5" fill={color} />
	{/if}
</svg>

<style>
	.spark {
		width: 100%;
		height: 100%;
		display: block;
	}
</style>

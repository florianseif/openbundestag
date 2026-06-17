<script lang="ts">
	// Head-to-head comparison of two search terms over time. Each series is the
	// aggregate (all-party) count per period for one word. Deliberately lean —
	// the comparison itself is the story, so no party split or gov strip here.
	import { scaleTime, scaleLinear } from 'd3-scale';
	import { line, area, curveMonotoneX } from 'd3-shape';
	import { extent, max, bisector } from 'd3-array';
	import { timeFormat } from 'd3-time-format';
	import { formatNumber } from '$lib/format';
	import { i18n } from '$lib/i18n.svelte';

	interface Series {
		word: string;
		color: string;
		series: { period: string; value: number }[];
	}
	let { a, b, valueLabel }: { a: Series; b: Series; valueLabel: string } = $props();

	let cw = $state(800);
	const H = 420;
	const m = { t: 18, r: 20, b: 40, l: 52 };

	let hoverIdx = $state<number | null>(null);

	// Union of all periods across both words, sorted.
	const periods = $derived(
		[...new Set([...a.series, ...b.series].map((d) => d.period))].sort()
	);
	const dates = $derived(periods.map((p) => new Date(p)));
	const lookupA = $derived(new Map(a.series.map((d) => [d.period, d.value])));
	const lookupB = $derived(new Map(b.series.map((d) => [d.period, d.value])));

	const x = $derived(
		scaleTime()
			.domain(extent(dates) as [Date, Date])
			.range([m.l, Math.max(m.l + 1, cw - m.r)])
	);
	const yMax = $derived(
		max([...a.series, ...b.series], (d) => d.value) ?? 1
	);
	const y = $derived(scaleLinear().domain([0, yMax]).nice().range([H - m.b, m.t]));

	const linePath = (lk: Map<string, number>) =>
		line<string>()
			.x((p) => x(new Date(p)))
			.y((p) => y(lk.get(p) ?? 0))
			.curve(curveMonotoneX)(periods) ?? '';
	const areaPath = (lk: Map<string, number>) =>
		area<string>()
			.x((p) => x(new Date(p)))
			.y0(H - m.b)
			.y1((p) => y(lk.get(p) ?? 0))
			.curve(curveMonotoneX)(periods) ?? '';

	const fmtYear = timeFormat('%Y');
	const xTicks = $derived(x.ticks(Math.min(8, Math.max(2, Math.floor(cw / 110)))));
	const yTicks = $derived(y.ticks(5));

	const bis = bisector((d: Date) => d).center;
	function onmove(e: MouseEvent) {
		const svg = (e.currentTarget as SVGElement).closest('svg')!;
		const rect = svg.getBoundingClientRect();
		const mx = ((e.clientX - rect.left) * cw) / rect.width;
		hoverIdx = bis(dates, x.invert(mx));
	}
	const hover = $derived.by(() => {
		if (hoverIdx == null || !periods[hoverIdx]) return null;
		const p = periods[hoverIdx];
		return {
			period: p,
			date: dates[hoverIdx],
			av: lookupA.get(p) ?? 0,
			bv: lookupB.get(p) ?? 0
		};
	});

	const uid = Math.random().toString(36).slice(2, 8);
	const totalA = $derived(a.series.reduce((s, d) => s + d.value, 0));
	const totalB = $derived(b.series.reduce((s, d) => s + d.value, 0));
</script>

<div class="cmp">
	<div class="cmp-legend">
		<span class="cl-item"><span class="cl-dot" style:background={a.color}></span>{a.word}
			<strong>{formatNumber(totalA, i18n.lang)}</strong></span>
		<span class="cl-item"><span class="cl-dot" style:background={b.color}></span>{b.word}
			<strong>{formatNumber(totalB, i18n.lang)}</strong></span>
	</div>

	<div class="chart" bind:clientWidth={cw}>
		<svg viewBox="0 0 {cw} {H}" role="img" aria-label="{a.word} vs {b.word}">
			<defs>
				<filter id="cg-{uid}" x="-20%" y="-20%" width="140%" height="140%">
					<feGaussianBlur stdDeviation="3" result="bl" />
					<feMerge><feMergeNode in="bl" /><feMergeNode in="SourceGraphic" /></feMerge>
				</filter>
				<linearGradient id="ga-{uid}" x1="0" x2="0" y1="0" y2="1">
					<stop offset="0%" stop-color={a.color} stop-opacity="0.26" />
					<stop offset="100%" stop-color={a.color} stop-opacity="0" />
				</linearGradient>
				<linearGradient id="gb-{uid}" x1="0" x2="0" y1="0" y2="1">
					<stop offset="0%" stop-color={b.color} stop-opacity="0.26" />
					<stop offset="100%" stop-color={b.color} stop-opacity="0" />
				</linearGradient>
			</defs>

			{#each yTicks as t (t)}
				<line x1={m.l} x2={cw - m.r} y1={y(t)} y2={y(t)} class="grid" />
				<text x={m.l - 8} y={y(t)} class="ytick" dominant-baseline="middle" text-anchor="end"
					>{formatNumber(t, i18n.lang)}</text>
			{/each}
			{#each xTicks as t (t.getTime())}
				<text x={x(t)} y={H - m.b + 22} class="xtick" text-anchor="middle">{fmtYear(t)}</text>
			{/each}

			{#key `${periods.length}|${periods[0]}|${a.word}|${b.word}`}
				<g class="series">
					<path d={areaPath(lookupA)} fill="url(#ga-{uid})" class="ar" />
					<path d={areaPath(lookupB)} fill="url(#gb-{uid})" class="ar" />
					<g filter="url(#cg-{uid})">
						<path d={linePath(lookupA)} fill="none" stroke={a.color} stroke-width="2.6" pathLength="1" class="ln" stroke-linecap="round" stroke-linejoin="round" />
						<path d={linePath(lookupB)} fill="none" stroke={b.color} stroke-width="2.6" pathLength="1" class="ln" stroke-linecap="round" stroke-linejoin="round" />
					</g>
				</g>
			{/key}

			{#if hover}
				<line x1={x(hover.date)} x2={x(hover.date)} y1={m.t} y2={H - m.b} class="crosshair" />
				<circle cx={x(hover.date)} cy={y(hover.av)} r="5" fill={a.color} stroke="var(--surface)" stroke-width="2.5" />
				<circle cx={x(hover.date)} cy={y(hover.bv)} r="5" fill={b.color} stroke="var(--surface)" stroke-width="2.5" />
			{/if}

			<rect x={m.l} y={m.t} width={Math.max(0, cw - m.l - m.r)} height={H - m.t - m.b}
				fill="transparent" onmousemove={onmove} onmouseleave={() => (hoverIdx = null)} role="presentation" />
		</svg>

		{#if hover}
			<div class="tip" style:left="{Math.min(cw - 170, Math.max(0, x(hover.date) + 12))}px">
				<strong>{fmtYear(hover.date)}</strong>
				<div class="tr"><span class="td" style:background={a.color}></span><span class="tw">{a.word}</span><span class="tv">{formatNumber(hover.av, i18n.lang)}</span></div>
				<div class="tr"><span class="td" style:background={b.color}></span><span class="tw">{b.word}</span><span class="tv">{formatNumber(hover.bv, i18n.lang)}</span></div>
				<div class="th">{valueLabel}</div>
			</div>
		{/if}
	</div>
</div>

<style>
	.cmp-legend {
		display: flex;
		flex-wrap: wrap;
		gap: 1.2rem;
		margin-bottom: 0.8rem;
	}
	.cl-item {
		display: inline-flex;
		align-items: center;
		gap: 0.4rem;
		font-size: 0.9rem;
		color: var(--ink-2);
	}
	.cl-item strong {
		color: var(--ink);
		font-variant-numeric: tabular-nums;
		margin-left: 0.15rem;
	}
	.cl-dot { width: 11px; height: 11px; border-radius: 50%; flex: none; }
	.chart { position: relative; width: 100%; }
	svg { width: 100%; height: auto; display: block; overflow: visible; }
	.grid { stroke: var(--line); stroke-width: 1; }
	.ytick, .xtick { fill: var(--ink-3); font-size: 0.72rem; font-family: var(--sans); }
	.ln { animation: draw 1s var(--ease) forwards; }
	.ar { animation: fade 1s var(--ease) forwards; opacity: 0; }
	@keyframes draw {
		from { stroke-dasharray: 1; stroke-dashoffset: 1; }
		to { stroke-dasharray: 1; stroke-dashoffset: 0; }
	}
	@keyframes fade { to { opacity: 1; } }
	.crosshair { stroke: var(--ink-3); stroke-opacity: 0.6; stroke-dasharray: 3 4; stroke-width: 1; }
	.tip {
		position: absolute; top: 8px; pointer-events: none;
		background: var(--glass); backdrop-filter: blur(14px);
		border: 1px solid var(--line-2); border-radius: var(--radius-sm);
		box-shadow: var(--shadow-lg); padding: 0.6rem 0.75rem;
		font-size: 0.78rem; min-width: 150px;
	}
	.tr { display: flex; align-items: center; gap: 0.4rem; margin-top: 0.25rem; }
	.td { width: 9px; height: 9px; border-radius: 50%; flex: none; }
	.tw { flex: 1; color: var(--ink-2); }
	.tv { font-variant-numeric: tabular-nums; font-weight: 600; }
	.th { margin-top: 0.4rem; color: var(--ink-3); font-size: 0.7rem; }
	@media (prefers-reduced-motion: reduce) {
		.ln, .ar { animation: none; opacity: 1; }
	}
</style>

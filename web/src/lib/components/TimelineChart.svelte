<script lang="ts">
	import { scaleTime, scaleLinear } from 'd3-scale';
	import { line, area, stack, curveMonotoneX, stackOffsetNone } from 'd3-shape';
	import { extent, max, bisector } from 'd3-array';
	import { timeFormat } from 'd3-time-format';
	import type { TimelinePoint } from '$lib/types';
	import { partyColor, partyFullName, formatNumber } from '$lib/format';
	import { i18n } from '$lib/i18n.svelte';

	let {
		data,
		stacked = false,
		valueLabel,
		onpick
	}: {
		data: TimelinePoint[];
		stacked?: boolean;
		valueLabel: string;
		onpick?: (period: string, party: string) => void;
	} = $props();

	let cw = $state(800);
	const H = 420;
	const m = { t: 16, r: 18, b: 34, l: 52 };

	let hidden = $state<Set<string>>(new Set());
	let hoverIdx = $state<number | null>(null);

	// --- reshape into per-party series over sorted periods --------------------
	const periods = $derived([...new Set(data.map((d) => d.period))].sort());
	const parties = $derived(
		[...new Set(data.map((d) => d.party))].sort(
			(a, b) => total(b) - total(a)
		)
	);
	function total(party: string) {
		return data.reduce((s, d) => (d.party === party ? s + d.value : s), 0);
	}
	const lookup = $derived.by(() => {
		const map = new Map<string, number>();
		for (const d of data) map.set(`${d.period}|${d.party}`, d.value);
		return map;
	});
	const visible = $derived(parties.filter((p) => !hidden.has(p)));
	const dates = $derived(periods.map((p) => new Date(p)));

	const x = $derived(
		scaleTime()
			.domain(extent(dates) as [Date, Date])
			.range([m.l, Math.max(m.l + 1, cw - m.r)])
	);

	const stackData = $derived.by(() =>
		periods.map((p, i) => {
			const row: Record<string, number | Date> = { __d: dates[i] };
			for (const party of visible) row[party] = lookup.get(`${p}|${party}`) ?? 0;
			return row;
		})
	);
	const stacked_series = $derived.by(() =>
		stacked
			? stack<Record<string, number | Date>>().keys(visible).offset(stackOffsetNone)(stackData)
			: []
	);
	const yMax = $derived(
		stacked
			? max(stackData, (r) => visible.reduce((s, p) => s + (r[p] as number), 0)) ?? 1
			: max(data.filter((d) => !hidden.has(d.party)), (d) => d.value) ?? 1
	);
	const y = $derived(scaleLinear().domain([0, yMax]).nice().range([H - m.b, m.t]));

	const linePath = (party: string) =>
		line<string>()
			.x((p) => x(new Date(p)))
			.y((p) => y(lookup.get(`${p}|${party}`) ?? 0))
			.curve(curveMonotoneX)(periods) ?? '';

	const areaPath = (s: (typeof stacked_series)[number]) =>
		area<(typeof s)[number]>()
			.x((d) => x(d.data.__d as Date))
			.y0((d) => y(d[0]))
			.y1((d) => y(d[1]))
			.curve(curveMonotoneX)(s) ?? '';

	const fmtYear = timeFormat('%Y');
	const xTicks = $derived(x.ticks(Math.min(8, Math.max(2, Math.floor(cw / 110)))));
	const yTicks = $derived(y.ticks(5));

	// --- hover ----------------------------------------------------------------
	const bis = bisector((d: Date) => d).center;
	function onmove(e: MouseEvent) {
		const rect = (e.currentTarget as SVGElement).getBoundingClientRect();
		const mx = e.clientX - rect.left;
		hoverIdx = bis(dates, x.invert(mx));
	}
	const hoverRows = $derived.by(() => {
		if (hoverIdx == null || !periods[hoverIdx]) return null;
		const p = periods[hoverIdx];
		return {
			period: p,
			date: dates[hoverIdx],
			items: visible
				.map((party) => ({ party, value: lookup.get(`${p}|${party}`) ?? 0 }))
				.filter((r) => r.value > 0)
				.sort((a, b) => b.value - a.value)
		};
	});

	function toggle(party: string) {
		const next = new Set(hidden);
		next.has(party) ? next.delete(party) : next.add(party);
		hidden = next;
	}
</script>

<div class="legend">
	{#each parties as party (party)}
		<button
			class="chip"
			class:off={hidden.has(party)}
			onclick={() => toggle(party)}
			title={partyFullName(party)}
		>
			<span class="dot" style:background={partyColor(party)}></span>
			{party}
		</button>
	{/each}
</div>

<div class="chart" bind:clientWidth={cw}>
	<svg viewBox="0 0 {cw} {H}" role="img" aria-label="Timeline chart">
		<!-- gridlines + y axis -->
		{#each yTicks as t (t)}
			<line x1={m.l} x2={cw - m.r} y1={y(t)} y2={y(t)} class="grid" />
			<text x={m.l - 8} y={y(t)} class="ytick" dominant-baseline="middle" text-anchor="end">
				{formatNumber(t, i18n.lang)}
			</text>
		{/each}
		<!-- x axis -->
		{#each xTicks as t (t.getTime())}
			<text x={x(t)} y={H - m.b + 20} class="xtick" text-anchor="middle">{fmtYear(t)}</text>
		{/each}

		{#if stacked}
			{#each stacked_series as s (s.key)}
				<path d={areaPath(s)} fill={partyColor(s.key)} fill-opacity="0.85" stroke="none" />
			{/each}
		{:else}
			{#each visible as party (party)}
				<path
					d={linePath(party)}
					fill="none"
					stroke={partyColor(party)}
					stroke-width="2.5"
					stroke-linejoin="round"
					stroke-linecap="round"
				/>
			{/each}
		{/if}

		<!-- hover crosshair + markers -->
		{#if hoverRows}
			<line
				x1={x(hoverRows.date)}
				x2={x(hoverRows.date)}
				y1={m.t}
				y2={H - m.b}
				class="crosshair"
			/>
			{#if !stacked}
				{#each hoverRows.items as r (r.party)}
					<circle
						cx={x(hoverRows.date)}
						cy={y(r.value)}
						r="5"
						fill={partyColor(r.party)}
						stroke="var(--card)"
						stroke-width="2"
						class="marker"
						role="button"
						tabindex="0"
						onclick={() => onpick?.(hoverRows.period, r.party)}
						onkeydown={(e) => e.key === 'Enter' && onpick?.(hoverRows.period, r.party)}
					/>
				{/each}
			{/if}
		{/if}

		<!-- capture layer -->
		<rect
			x={m.l}
			y={m.t}
			width={Math.max(0, cw - m.l - m.r)}
			height={H - m.t - m.b}
			fill="transparent"
			onmousemove={onmove}
			onmouseleave={() => (hoverIdx = null)}
			role="presentation"
		/>
	</svg>

	{#if hoverRows && hoverRows.items.length}
		<div class="tooltip" style:left="{Math.min(cw - 180, Math.max(0, x(hoverRows.date) + 12))}px">
			<strong>{fmtYear(hoverRows.date)}</strong>
			{#each hoverRows.items.slice(0, 8) as r (r.party)}
				<div class="trow">
					<span class="dot" style:background={partyColor(r.party)}></span>
					<span class="tp">{r.party}</span>
					<span class="tv">{formatNumber(r.value, i18n.lang)}</span>
				</div>
			{/each}
			<div class="thint">{valueLabel}</div>
		</div>
	{/if}
</div>

<style>
	.legend {
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem;
		margin-bottom: 0.8rem;
	}
	.chip {
		display: inline-flex;
		align-items: center;
		gap: 0.4rem;
		font: inherit;
		font-size: 0.8rem;
		font-weight: 500;
		padding: 0.28rem 0.7rem;
		border-radius: 999px;
		border: 1px solid var(--line-2);
		background: var(--card);
		color: var(--ink-2);
		cursor: pointer;
		transition: opacity 0.2s;
	}
	.chip.off {
		opacity: 0.38;
	}
	.dot {
		width: 9px;
		height: 9px;
		border-radius: 50%;
		flex: none;
	}
	.chart {
		position: relative;
		width: 100%;
	}
	svg {
		width: 100%;
		height: auto;
		display: block;
		overflow: visible;
	}
	.grid {
		stroke: var(--line);
		stroke-width: 1;
	}
	.crosshair {
		stroke: var(--ink-3);
		stroke-dasharray: 3 3;
		stroke-width: 1;
	}
	.ytick,
	.xtick {
		fill: var(--ink-3);
		font-size: 0.72rem;
		font-family: var(--sans);
	}
	.marker {
		cursor: pointer;
	}
	.tooltip {
		position: absolute;
		top: 8px;
		pointer-events: none;
		background: var(--card);
		border: 1px solid var(--line-2);
		border-radius: var(--radius-sm);
		box-shadow: var(--shadow);
		padding: 0.55rem 0.7rem;
		font-size: 0.78rem;
		min-width: 150px;
	}
	.trow {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		margin-top: 0.2rem;
	}
	.tp {
		flex: 1;
		color: var(--ink-2);
	}
	.tv {
		font-variant-numeric: tabular-nums;
		font-weight: 600;
	}
	.thint {
		margin-top: 0.4rem;
		color: var(--ink-3);
		font-size: 0.7rem;
	}
</style>

<script lang="ts">
	import { scaleTime, scaleLinear } from 'd3-scale';
	import { line, curveMonotoneX } from 'd3-shape';
	import { extent, max, bisector } from 'd3-array';
	import { timeFormat } from 'd3-time-format';
	import type { TimelinePoint } from '$lib/types';
	import { partyColor, partyFullName, formatNumber, partyFoundingOrder } from '$lib/format';
	import { i18n } from '$lib/i18n.svelte';
	import governmentsRaw from '$lib/governments.json';

	let {
		data,
		valueLabel,
		selectedParties = [],
		ontoggleparty,
		onpick
	}: {
		data: TimelinePoint[];
		valueLabel: string;
		selectedParties?: string[];
		ontoggleparty?: (party: string) => void;
		onpick?: (period: string, party?: string) => void;
	} = $props();

	let cw = $state(800);
	const H = 460;
	// Extra bottom margin for the government strip + x-axis labels
	const m = { t: 16, r: 18, b: 72, l: 52 };

	// Government strip sits just below the plot area baseline
	const GOV_STRIP_Y = H - m.b + 4;
	const GOV_STRIP_H = 14;
	const GOV_LABEL_Y = GOV_STRIP_Y + GOV_STRIP_H + 16;

	let hoverIdx = $state<number | null>(null);
	let hoverParty = $state<string | null>(null);
	let hoverGovNr = $state<number | null>(null);

	// --- reshape into per-party series over sorted periods --------------------
	const periods = $derived([...new Set(data.map((d) => d.period))].sort());
	const parties = $derived(
		[...new Set(data.map((d) => d.party))].sort(
			(a, b) => partyFoundingOrder(a) - partyFoundingOrder(b)
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
	const visible = $derived(
		selectedParties.length === 0 ? parties : parties.filter((p) => selectedParties.includes(p))
	);
	const dates = $derived(periods.map((p) => new Date(p)));

	const x = $derived(
		scaleTime()
			.domain(extent(dates) as [Date, Date])
			.range([m.l, Math.max(m.l + 1, cw - m.r)])
	);

	const yMax = $derived(
		max(data.filter((d) => visible.includes(d.party)), (d) => d.value) ?? 1
	);
	const y = $derived(scaleLinear().domain([0, yMax]).nice().range([H - m.b, m.t]));

	const linePath = (party: string) =>
		line<string>()
			.x((p) => x(new Date(p)))
			.y((p) => y(lookup.get(`${p}|${party}`) ?? 0))
			.curve(curveMonotoneX)(periods) ?? '';

	const fmtYear = timeFormat('%Y');
	const fmtDate = timeFormat('%d.%m.%Y');
	const xTicks = $derived(x.ticks(Math.min(8, Math.max(2, Math.floor(cw / 110)))));
	const yTicks = $derived(y.ticks(5));

	// --- government bands -----------------------------------------------------
	const govBands = $derived.by(() => {
		if (dates.length < 2) return [];
		const [domStart, domEnd] = extent(dates) as [Date, Date];
		const today = new Date();

		return governmentsRaw
			.map((g) => {
				const gStart = new Date(g.start);
				const gEnd = g.end ? new Date(g.end) : today;
				const visStart = gStart < domStart ? domStart : gStart;
				const visEnd = gEnd > domEnd ? domEnd : gEnd;
				if (visStart >= visEnd) return null;
				return {
					...g,
					x1: x(visStart),
					x2: x(visEnd),
					color: partyColor(g.parties[0])
				};
			})
			.filter(Boolean) as Array<{
			nr: number;
			name: string;
			chancellor: string;
			start: string;
			end: string | null;
			parties: string[];
			x1: number;
			x2: number;
			color: string;
		}>;
	});

	// --- hover ----------------------------------------------------------------
	const bis = bisector((d: Date) => d).center;
	function onmove(e: MouseEvent) {
		if (playing) stopPlay(); // manual hover always wins over playback
		const svg = (e.currentTarget as SVGElement).closest('svg')!;
		const rect = svg.getBoundingClientRect();
		const scale = cw / rect.width;
		const mx = (e.clientX - rect.left) * scale;
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

	const hoveredGov = $derived(
		hoverGovNr != null ? governmentsRaw.find((g) => g.nr === hoverGovNr) ?? null : null
	);

	function toggle(party: string) {
		ontoggleparty?.(party);
	}

	function onclick() {
		if (!hoverRows || !hoverRows.items.length) return;
		// Clicking the chart drills into ALL parties at that period (the markers
		// do the same) — never just the top-most line.
		onpick?.(hoverRows.period);
	}

	// --- peak annotation: the single tallest visible vertex -------------------
	const peak = $derived.by(() => {
		let best: { period: string; party: string; value: number } | null = null;
		for (const p of periods) {
			for (const party of visible) {
				const v = lookup.get(`${p}|${party}`) ?? 0;
				if (!best || v > best.value) best = { period: p, party, value: v };
			}
		}
		return best && best.value > 0 ? best : null;
	});
	// Clamp the peak label inside the plot so it never clips at the edges/top.
	const peakLabel = $derived.by(() => {
		if (!peak) return null;
		const px = x(new Date(peak.period));
		const py = y(peak.value);
		const lx = Math.min(cw - m.r - 48, Math.max(m.l + 48, px));
		const above = py - 30 > m.t;
		const ly = above ? py - 16 : py + 22;
		return {
			px,
			py,
			lx,
			ly,
			above,
			year: fmtYear(new Date(peak.period)),
			value: peak.value,
			color: partyColor(peak.party)
		};
	});

	// --- "play through history" scrubber: drives hoverIdx across the periods ---
	let playing = $state(false);
	let playRaf = 0;
	const reduceMotion =
		typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
	function stopPlay() {
		playing = false;
		cancelAnimationFrame(playRaf);
	}
	function togglePlay() {
		if (playing) return stopPlay();
		const N = periods.length;
		if (N < 2) return;
		if (reduceMotion) {
			hoverIdx = N - 1;
			return;
		}
		playing = true;
		const dur = Math.min(9000, Math.max(3500, N * 170));
		const start = performance.now();
		const tick = (now: number) => {
			if (!playing) return;
			const t = Math.min(1, (now - start) / dur);
			hoverIdx = Math.round(t * (N - 1));
			if (t < 1) playRaf = requestAnimationFrame(tick);
			else playing = false;
		};
		playRaf = requestAnimationFrame(tick);
	}
	// Cancel any running playback when the underlying data changes (new query).
	$effect(() => {
		void data;
		return () => stopPlay();
	});

	const uid = Math.random().toString(36).slice(2, 8);

	function shortName(chancellor: string) {
		const parts = chancellor.split(' ');
		return parts[parts.length - 1];
	}
</script>

<div class="tl-head">
	<div class="legend">
		{#each parties as party (party)}
			<button
				class="chip"
				class:off={selectedParties.length > 0 && !selectedParties.includes(party)}
				onclick={() => toggle(party)}
				onmouseenter={() => (hoverParty = party)}
				onmouseleave={() => (hoverParty = null)}
				data-tip={partyFullName(party)}
			>
				<span class="dot" style:background={partyColor(party)}></span>
				{party}
			</button>
		{/each}
	</div>

	{#if periods.length > 1}
		<button
			class="tl-play"
			class:playing
			onclick={togglePlay}
			aria-pressed={playing}
			data-tip={playing ? i18n.t('tl_pause') : i18n.t('tl_play')}
		>
			{#if playing}
				<svg width="13" height="13" viewBox="0 0 13 13" fill="currentColor" aria-hidden="true"><rect x="2" y="1.5" width="3.2" height="10" rx="1"/><rect x="7.8" y="1.5" width="3.2" height="10" rx="1"/></svg>
			{:else}
				<svg width="13" height="13" viewBox="0 0 13 13" fill="currentColor" aria-hidden="true"><path d="M3 1.8v9.4a.7.7 0 0 0 1.07.6l7.3-4.7a.7.7 0 0 0 0-1.2l-7.3-4.7A.7.7 0 0 0 3 1.8Z"/></svg>
			{/if}
			<span>{playing ? i18n.t('tl_pause') : i18n.t('tl_play')}</span>
		</button>
	{/if}
</div>

<div class="chart" bind:clientWidth={cw}>
	<svg viewBox="0 0 {cw} {H}" role="img" aria-label="Timeline chart">
		<defs>
			<filter id="glow-{uid}" x="-20%" y="-20%" width="140%" height="140%">
				<feGaussianBlur stdDeviation="3.4" result="b" />
				<feMerge>
					<feMergeNode in="b" />
					<feMergeNode in="SourceGraphic" />
				</feMerge>
			</filter>
			<clipPath id="strip-{uid}">
				<rect x={m.l} y={GOV_STRIP_Y} width={Math.max(0, cw - m.l - m.r)} height={GOV_STRIP_H} />
			</clipPath>
		</defs>

		<!-- gridlines + y axis -->
		{#each yTicks as t (t)}
			<line x1={m.l} x2={cw - m.r} y1={y(t)} y2={y(t)} class="grid" />
			<text x={m.l - 8} y={y(t)} class="ytick" dominant-baseline="middle" text-anchor="end">
				{formatNumber(t, i18n.lang)}
			</text>
		{/each}
		<!-- x axis -->
		{#each xTicks as t (t.getTime())}
			<text x={x(t)} y={GOV_LABEL_Y} class="xtick" text-anchor="middle">{fmtYear(t)}</text>
		{/each}

		<!-- Government transition dividers in the plot area -->
		{#each govBands.slice(1) as g (g.nr)}
			<line
				x1={g.x1}
				x2={g.x1}
				y1={m.t}
				y2={H - m.b}
				class="gov-divider"
			/>
		{/each}

		<!-- Government color strip -->
		{#each govBands as g (g.nr)}
			<!-- Fill band -->
			<rect
				x={g.x1}
				y={GOV_STRIP_Y}
				width={Math.max(0, g.x2 - g.x1)}
				height={GOV_STRIP_H}
				fill={g.color}
				fill-opacity={hoverGovNr === g.nr ? 0.55 : 0.25}
				class="gov-band"
				onmouseenter={() => (hoverGovNr = g.nr)}
				onmouseleave={() => (hoverGovNr = null)}
				role="img"
				aria-label="Kabinett {g.name}"
			/>
			<!-- Top accent line -->
			<line
				x1={g.x1}
				x2={g.x2}
				y1={GOV_STRIP_Y}
				y2={GOV_STRIP_Y}
				stroke={g.color}
				stroke-width="2"
				stroke-opacity={hoverGovNr === g.nr ? 1 : 0.55}
				pointer-events="none"
			/>
			<!-- Chancellor last-name label (only if band is wide enough) -->
			{#if g.x2 - g.x1 > 44}
				<text
					x={(g.x1 + g.x2) / 2}
					y={GOV_STRIP_Y + GOV_STRIP_H / 2 + 0.5}
					class="gov-label"
					text-anchor="middle"
					dominant-baseline="middle"
					clip-path="url(#strip-{uid})"
					fill={g.color}
					fill-opacity={hoverGovNr === g.nr ? 1 : 0.8}
					pointer-events="none"
				>{shortName(g.chancellor)}</text>
			{/if}
		{/each}

		<g filter="url(#glow-{uid})">
			{#each visible as party (party)}
				<path
					d={linePath(party)}
					fill="none"
					stroke={partyColor(party)}
					stroke-width="2.4"
					stroke-linejoin="round"
					stroke-linecap="round"
					pathLength="1"
					class="line"
					class:dim={hoverParty && hoverParty !== party}
				/>
			{/each}
		</g>

		<!-- peak annotation: marks the moment the word was most discussed -->
		{#if peakLabel && hoverIdx == null}
			<g class="peak" pointer-events="none">
				<line x1={peakLabel.px} x2={peakLabel.px} y1={peakLabel.py} y2={peakLabel.ly + (peakLabel.above ? 4 : -4)} class="peak-stem" stroke={peakLabel.color} />
				<circle cx={peakLabel.px} cy={peakLabel.py} r="9" fill="none" stroke={peakLabel.color} stroke-opacity="0.35" />
				<circle cx={peakLabel.px} cy={peakLabel.py} r="4.5" fill={peakLabel.color} stroke="var(--surface)" stroke-width="2" />
				<text
					x={peakLabel.lx}
					y={peakLabel.ly}
					class="peak-label"
					text-anchor="middle"
					dominant-baseline={peakLabel.above ? 'auto' : 'hanging'}
				>{i18n.t('tl_peak')} {peakLabel.year} · {formatNumber(peakLabel.value, i18n.lang)}</text>
			</g>
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
			{#each hoverRows.items as r (r.party)}
				<circle
					cx={x(hoverRows.date)}
					cy={y(r.value)}
					r="5.5"
					fill={partyColor(r.party)}
					stroke="var(--surface)"
					stroke-width="2.5"
					class="marker"
					role="button"
					tabindex="0"
					aria-label="{r.party} {hoverRows.period}"
					onclick={() => onpick?.(hoverRows.period)}
					onkeydown={(e) => e.key === 'Enter' && onpick?.(hoverRows.period)}
				/>
			{/each}
		{/if}

		<!-- main capture layer (plot area only) -->
		<rect
			x={m.l}
			y={m.t}
			width={Math.max(0, cw - m.l - m.r)}
			height={H - m.t - m.b}
			fill="transparent"
			class="capture"
			onmousemove={onmove}
			onmouseleave={() => (hoverIdx = null)}
			{onclick}
			role="presentation"
		/>
	</svg>

	<!-- Data tooltip -->
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

	<!-- Government tooltip -->
	{#if hoveredGov}
		{@const gb = govBands.find((g) => g.nr === hoveredGov.nr)}
		{#if gb}
			<div
				class="gov-tooltip"
				style:left="{Math.min(cw - 220, Math.max(0, (gb.x1 + gb.x2) / 2 - 100))}px"
			>
				<div class="gov-tt-header" style:border-color={gb.color}>
					<span class="gov-tt-name">{hoveredGov.name}</span>
					<span class="gov-tt-chancellor">{hoveredGov.chancellor}</span>
				</div>
				<div class="gov-tt-coalition">
					{#each hoveredGov.parties as p (p)}
						<span class="gov-tt-party" style:background={partyColor(p)}>{p}</span>
					{/each}
				</div>
				<div class="gov-tt-dates">
					{fmtDate(new Date(hoveredGov.start))}
					{' – '}
					{hoveredGov.end
						? fmtDate(new Date(hoveredGov.end))
						: i18n.lang === 'de'
							? 'heute'
							: 'present'}
				</div>
			</div>
		{/if}
	{/if}
</div>

<style>
	.tl-head {
		display: flex;
		align-items: flex-start;
		justify-content: space-between;
		gap: 0.8rem;
		margin-bottom: 0.8rem;
	}
	.legend {
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem;
		min-width: 0;
	}
	/* "Play through history" control */
	.tl-play {
		display: inline-flex;
		align-items: center;
		gap: 0.4rem;
		flex: none;
		font: inherit;
		font-size: 0.78rem;
		font-weight: 600;
		padding: 0.32rem 0.8rem 0.32rem 0.7rem;
		border-radius: 999px;
		border: 1px solid var(--line-2);
		background: var(--surface-2);
		color: var(--ink-2);
		cursor: pointer;
		white-space: nowrap;
		transition: color 0.2s, border-color 0.2s, background 0.2s, box-shadow 0.2s;
	}
	.tl-play:hover {
		color: var(--ink);
		border-color: color-mix(in srgb, var(--accent) 45%, var(--line-2));
		background: color-mix(in srgb, var(--accent) 8%, transparent);
	}
	.tl-play svg { color: var(--accent); }
	.tl-play.playing {
		color: var(--ink);
		border-color: color-mix(in srgb, var(--accent) 55%, transparent);
		background: color-mix(in srgb, var(--accent) 12%, transparent);
		box-shadow: 0 0 0 1px color-mix(in srgb, var(--accent) 25%, transparent);
	}
	/* Peak annotation */
	.peak-stem {
		stroke-width: 1;
		stroke-opacity: 0.5;
		stroke-dasharray: 2 3;
	}
	.peak-label {
		fill: var(--ink);
		font-family: var(--sans);
		font-size: 0.7rem;
		font-weight: 600;
		paint-order: stroke;
		stroke: var(--bg);
		stroke-width: 3px;
		stroke-linejoin: round;
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
		background: var(--surface-2);
		color: var(--ink-2);
		cursor: pointer;
		transition:
			opacity 0.2s,
			border-color 0.2s,
			color 0.2s;
	}
	.chip:hover {
		color: var(--ink);
		border-color: var(--line-3);
	}
	.chip.off {
		opacity: 0.34;
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
	.capture {
		cursor: pointer;
	}
	.line {
		animation: draw 1.1s var(--ease) forwards;
		transition: opacity 0.25s;
	}
	.line.dim {
		opacity: 0.18;
	}
	@keyframes draw {
		from {
			stroke-dasharray: 1;
			stroke-dashoffset: 1;
		}
		to {
			stroke-dasharray: 1;
			stroke-dashoffset: 0;
		}
	}
	.crosshair {
		stroke: var(--accent);
		stroke-opacity: 0.5;
		stroke-dasharray: 3 4;
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
		transition: r 0.15s var(--spring);
	}
	.marker:hover {
		r: 7.5;
	}
	/* Government strip */
	.gov-band {
		cursor: default;
		transition: fill-opacity 0.15s;
	}
	.gov-divider {
		stroke: var(--line-2);
		stroke-width: 1;
		stroke-dasharray: 2 5;
	}
	.gov-label {
		font-size: 0.6rem;
		font-family: var(--sans);
		font-weight: 700;
		letter-spacing: 0.02em;
	}
	/* Data hover tooltip */
	.tooltip {
		position: absolute;
		top: 8px;
		pointer-events: none;
		background: var(--glass);
		backdrop-filter: blur(14px);
		border: 1px solid var(--line-2);
		border-radius: var(--radius-sm);
		box-shadow: var(--shadow-lg);
		padding: 0.6rem 0.75rem;
		font-size: 0.78rem;
		min-width: 160px;
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
	/* Government hover tooltip */
	.gov-tooltip {
		position: absolute;
		bottom: 4px;
		pointer-events: none;
		background: var(--glass);
		backdrop-filter: blur(14px);
		border: 1px solid var(--line-2);
		border-radius: var(--radius-sm);
		box-shadow: var(--shadow-lg);
		padding: 0.55rem 0.75rem;
		font-size: 0.75rem;
		min-width: 200px;
		max-width: 260px;
	}
	.gov-tt-header {
		border-left: 2px solid;
		padding-left: 0.5rem;
		margin-bottom: 0.35rem;
	}
	.gov-tt-name {
		display: block;
		font-weight: 700;
		color: var(--ink);
		font-size: 0.82rem;
	}
	.gov-tt-chancellor {
		color: var(--ink-2);
		font-size: 0.72rem;
	}
	.gov-tt-coalition {
		display: flex;
		flex-wrap: wrap;
		gap: 0.25rem;
		margin-bottom: 0.35rem;
	}
	.gov-tt-party {
		font-size: 0.65rem;
		font-weight: 700;
		padding: 0.1rem 0.4rem;
		border-radius: 999px;
		color: #fff;
	}
	.gov-tt-dates {
		color: var(--ink-3);
		font-size: 0.68rem;
		font-variant-numeric: tabular-nums;
	}
</style>

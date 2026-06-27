<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue';
import { scaleTime, scaleLinear } from 'd3-scale';
import { line, curveMonotoneX } from 'd3-shape';
import { extent, max, bisector } from 'd3-array';
import { timeFormat } from 'd3-time-format';
import type { TimelinePoint } from '$lib/types';
import { partyColor, partyFullName, formatNumber, partyFoundingOrder } from '$lib/format';
import { i18n } from '$lib/i18n';
import governmentsRaw from '$lib/governments.json';
import eventsRaw from '$lib/events.json';

const props = defineProps<{
	data: TimelinePoint[];
	valueLabel: string;
	selectedParties?: string[];
}>();

// Callback props -> emits:  ontoggleparty -> @toggleparty, onpick -> @pick.
const emit = defineEmits<{
	toggleparty: [party: string];
	pick: [period: string, party?: string];
}>();

const selectedParties = computed(() => props.selectedParties ?? []);

// bind:clientWidth replacement (ResizeObserver on .chart).
const chartEl = ref<HTMLElement | null>(null);
const cw = ref(800);
let ro: ResizeObserver | null = null;
onMounted(() => {
	if (!chartEl.value) return;
	ro = new ResizeObserver((entries) => {
		for (const e of entries) cw.value = e.contentRect.width;
	});
	ro.observe(chartEl.value);
	cw.value = chartEl.value.clientWidth || cw.value;
});
onUnmounted(() => ro?.disconnect());

const H = 460;
// Extra bottom margin for the government strip + x-axis labels
const m = { t: 16, r: 18, b: 72, l: 52 };

// Government strip sits just below the plot area baseline
const GOV_STRIP_Y = H - m.b + 4;
const GOV_STRIP_H = 14;
const GOV_LABEL_Y = GOV_STRIP_Y + GOV_STRIP_H + 16;

const hoverIdx = ref<number | null>(null);
const hoverParty = ref<string | null>(null);
const hoverGovNr = ref<number | null>(null);
const hoverEventIdx = ref<number | null>(null);

// --- reshape into per-party series over sorted periods --------------------
const periods = computed(() => [...new Set(props.data.map((d) => d.period))].sort());
const parties = computed(() =>
	[...new Set(props.data.map((d) => d.party))].sort(
		(a, b) => partyFoundingOrder(a) - partyFoundingOrder(b)
	)
);
function total(party: string) {
	return props.data.reduce((s, d) => (d.party === party ? s + d.value : s), 0);
}
const lookup = computed(() => {
	const map = new Map<string, number>();
	for (const d of props.data) map.set(`${d.period}|${d.party}`, d.value);
	return map;
});
const visible = computed(() =>
	selectedParties.value.length === 0
		? parties.value
		: parties.value.filter((p) => selectedParties.value.includes(p))
);
const dates = computed(() => periods.value.map((p) => new Date(p)));

const x = computed(() =>
	scaleTime()
		.domain(extent(dates.value) as [Date, Date])
		.range([m.l, Math.max(m.l + 1, cw.value - m.r)])
);

const yMax = computed(
	() => max(props.data.filter((d) => visible.value.includes(d.party)), (d) => d.value) ?? 1
);
const y = computed(() => scaleLinear().domain([0, yMax.value]).nice().range([H - m.b, m.t]));

const linePath = (party: string) =>
	line<string>()
		.x((p) => x.value(new Date(p)))
		.y((p) => y.value(lookup.value.get(`${p}|${party}`) ?? 0))
		.curve(curveMonotoneX)(periods.value) ?? '';

const fmtYear = timeFormat('%Y');
const fmtDate = timeFormat('%d.%m.%Y');
const xTicks = computed(() => x.value.ticks(Math.min(8, Math.max(2, Math.floor(cw.value / 110)))));
const yTicks = computed(() => y.value.ticks(5));

// --- government bands -----------------------------------------------------
const govBands = computed(() => {
	if (dates.value.length < 2) return [];
	const [domStart, domEnd] = extent(dates.value) as [Date, Date];
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
				x1: x.value(visStart),
				x2: x.value(visEnd),
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
	if (playing.value) stopPlay(); // manual hover always wins over playback
	const svg = (e.currentTarget as SVGElement).closest('svg')!;
	const rect = svg.getBoundingClientRect();
	const scale = cw.value / rect.width;
	const mx = (e.clientX - rect.left) * scale;
	hoverIdx.value = bis(dates.value, x.value.invert(mx));
}
const hoverRows = computed(() => {
	if (hoverIdx.value == null || !periods.value[hoverIdx.value]) return null;
	const p = periods.value[hoverIdx.value];
	return {
		period: p,
		date: dates.value[hoverIdx.value],
		items: visible.value
			.map((party) => ({ party, value: lookup.value.get(`${p}|${party}`) ?? 0 }))
			.filter((r) => r.value > 0)
			.sort((a, b) => b.value - a.value)
	};
});

const hoveredGov = computed(() =>
	hoverGovNr.value != null ? governmentsRaw.find((g) => g.nr === hoverGovNr.value) ?? null : null
);
// {@const gb = govBands.find(...)} from the Svelte gov-tooltip, as a computed.
const hoveredGovBand = computed(() =>
	hoveredGov.value ? govBands.value.find((g) => g.nr === hoveredGov.value!.nr) ?? null : null
);

// --- historical event markers ---------------------------------------------
const eventMarks = computed(() => {
	if (dates.value.length < 2) return [];
	const t0 = +dates.value[0];
	const t1 = +dates.value[dates.value.length - 1];
	return eventsRaw
		.map((e) => ({ ...e, t: +new Date(e.date) }))
		.filter((e) => e.t >= t0 && e.t <= t1)
		.map((e) => ({
			date: e.date,
			year: e.date.slice(0, 4),
			label: i18n.lang === 'de' ? e.de : e.en,
			px: x.value(new Date(e.date))
		}));
});
// The label pill for the hovered event, clamped inside the plot.
const eventLabel = computed(() => {
	if (hoverEventIdx.value == null) return null;
	const ev = eventMarks.value[hoverEventIdx.value];
	if (!ev) return null;
	const text = `${ev.year} · ${ev.label}`;
	const w = Math.round(text.length * 5.9 + 24);
	const h = 20;
	const cx = Math.min(cw.value - m.r - w / 2 - 2, Math.max(m.l + w / 2 + 2, ev.px));
	return { px: ev.px, cx, cy: m.t + 15, w, h, text };
});

function toggle(party: string) {
	emit('toggleparty', party);
}

function onChartClick() {
	if (!hoverRows.value || !hoverRows.value.items.length) return;
	// Clicking the chart drills into ALL parties at that period (the markers
	// do the same) — never just the top-most line.
	emit('pick', hoverRows.value.period);
}

// Duration for the initial draw-in animation, matching the play button speed.
const drawDur = computed(() =>
	periods.value.length < 2 ? 1.1 : Math.min(9, Math.max(4.2, periods.value.length * 0.23))
);
// {#key …} → force the line <g> to remount (restart the draw animation).
const drawKey = computed(
	() =>
		`${periods.value.length}|${periods.value[0]}|${periods.value[periods.value.length - 1]}|${visible.value.join()}`
);

// --- "play through history": draws the lines in from past → present -------
const playing = ref(false);
const playT = ref(0); // 0..1 progress along the time axis
let playRaf = 0;
const reduceMotion =
	typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
const plotW = computed(() => Math.max(0, cw.value - m.l - m.r));
const revealW = computed(() => playT.value * plotW.value);
const scanX = computed(() => m.l + revealW.value);
// The bright moving head of each visible line, interpolated at the scan time.
const leadingPoints = computed(() => {
	if (!playing.value || dates.value.length < 2) return [];
	const t0 = +dates.value[0];
	const t1 = +dates.value[dates.value.length - 1];
	const ct = t0 + playT.value * (t1 - t0);
	let i1 = dates.value.findIndex((d) => +d >= ct);
	if (i1 <= 0) i1 = 1;
	const i0 = i1 - 1;
	const span = +dates.value[i1] - +dates.value[i0] || 1;
	const f = (ct - +dates.value[i0]) / span;
	const px = x.value(new Date(ct));
	return visible.value
		.map((party) => {
			const v0 = lookup.value.get(`${periods.value[i0]}|${party}`) ?? 0;
			const v1 = lookup.value.get(`${periods.value[i1]}|${party}`) ?? 0;
			const v = v0 + (v1 - v0) * f;
			return { party, x: px, y: y.value(v), v, color: partyColor(party) };
		})
		.filter((p) => p.v > 0);
});
function stopPlay() {
	playing.value = false;
	cancelAnimationFrame(playRaf);
}
const easeInOut = (t: number) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
function togglePlay() {
	if (playing.value) return stopPlay();
	const N = periods.value.length;
	if (N < 2) return;
	if (reduceMotion) {
		// No animation: just settle on the most recent period.
		hoverIdx.value = N - 1;
		return;
	}
	playing.value = true;
	playT.value = 0;
	const dur = Math.min(9000, Math.max(4200, N * 230));
	const start = performance.now();
	const tick = (now: number) => {
		if (!playing.value) return;
		const raw = Math.min(1, (now - start) / dur);
		playT.value = easeInOut(raw);
		const ct =
			+dates.value[0] + playT.value * (+dates.value[dates.value.length - 1] - +dates.value[0]);
		hoverIdx.value = bis(dates.value, new Date(ct));
		if (raw < 1) {
			playRaf = requestAnimationFrame(tick);
		} else {
			playing.value = false;
			hoverIdx.value = null; // settle into the static view (peak re-appears)
		}
	};
	playRaf = requestAnimationFrame(tick);
}
// Cancel any running playback when the underlying data changes (new query) or unmount.
watch(
	() => props.data,
	() => stopPlay()
);
onUnmounted(() => stopPlay());

const uid = Math.random().toString(36).slice(2, 8);

function shortName(chancellor: string) {
	const parts = chancellor.split(' ');
	return parts[parts.length - 1];
}
</script>

<template>
	<div class="tl-head">
		<div class="legend">
			<button
				v-for="party in parties"
				:key="party"
				class="chip"
				:class="{ off: selectedParties.length > 0 && !selectedParties.includes(party) }"
				@click="toggle(party)"
				@mouseenter="hoverParty = party"
				@mouseleave="hoverParty = null"
				:data-tip="partyFullName(party)"
			>
				<span class="dot" :style="{ background: partyColor(party) }"></span>
				{{ party }}
			</button>
		</div>

		<button
			v-if="periods.length > 1"
			class="tl-play"
			:class="{ playing }"
			@click="togglePlay"
			:aria-pressed="playing"
			:data-tip="playing ? i18n.t('tl_pause') : i18n.t('tl_play')"
		>
			<svg
				v-if="playing"
				width="13"
				height="13"
				viewBox="0 0 13 13"
				fill="currentColor"
				aria-hidden="true"
			>
				<rect x="2" y="1.5" width="3.2" height="10" rx="1" />
				<rect x="7.8" y="1.5" width="3.2" height="10" rx="1" />
			</svg>
			<svg v-else width="13" height="13" viewBox="0 0 13 13" fill="currentColor" aria-hidden="true">
				<path d="M3 1.8v9.4a.7.7 0 0 0 1.07.6l7.3-4.7a.7.7 0 0 0 0-1.2l-7.3-4.7A.7.7 0 0 0 3 1.8Z" />
			</svg>
			<span>{{ playing ? i18n.t('tl_pause') : i18n.t('tl_play') }}</span>
		</button>
	</div>

	<div ref="chartEl" class="chart">
		<svg :viewBox="`0 0 ${cw} ${H}`" role="img" aria-label="Timeline chart">
			<defs>
				<filter :id="`glow-${uid}`" x="-20%" y="-20%" width="140%" height="140%">
					<feGaussianBlur stdDeviation="3.4" result="b" />
					<feMerge>
						<feMergeNode in="b" />
						<feMergeNode in="SourceGraphic" />
					</feMerge>
				</filter>
				<clipPath :id="`strip-${uid}`">
					<rect
						:x="m.l"
						:y="GOV_STRIP_Y"
						:width="Math.max(0, cw - m.l - m.r)"
						:height="GOV_STRIP_H"
					/>
				</clipPath>
				<clipPath :id="`reveal-${uid}`">
					<rect :x="m.l" y="0" :width="revealW" :height="H" />
				</clipPath>
			</defs>

			<!-- gridlines + y axis -->
			<template v-for="t in yTicks" :key="t">
				<line :x1="m.l" :x2="cw - m.r" :y1="y(t)" :y2="y(t)" class="grid" />
				<text :x="m.l - 8" :y="y(t)" class="ytick" dominant-baseline="middle" text-anchor="end">
					{{ formatNumber(t, i18n.lang) }}
				</text>
			</template>
			<!-- x axis -->
			<text
				v-for="t in xTicks"
				:key="t.getTime()"
				:x="x(t)"
				:y="GOV_LABEL_Y"
				class="xtick"
				text-anchor="middle"
				>{{ fmtYear(t) }}</text
			>

			<!-- Government transition dividers in the plot area -->
			<line
				v-for="g in govBands.slice(1)"
				:key="g.nr"
				:x1="g.x1"
				:x2="g.x1"
				:y1="m.t"
				:y2="H - m.b"
				class="gov-divider"
			/>

			<!-- Government color strip -->
			<template v-for="g in govBands" :key="g.nr">
				<!-- Fill band -->
				<rect
					:x="g.x1"
					:y="GOV_STRIP_Y"
					:width="Math.max(0, g.x2 - g.x1)"
					:height="GOV_STRIP_H"
					:fill="g.color"
					:fill-opacity="hoverGovNr === g.nr ? 0.55 : 0.25"
					class="gov-band"
					@mouseenter="hoverGovNr = g.nr"
					@mouseleave="hoverGovNr = null"
					role="img"
					:aria-label="`Kabinett ${g.name}`"
				/>
				<!-- Top accent line -->
				<line
					:x1="g.x1"
					:x2="g.x2"
					:y1="GOV_STRIP_Y"
					:y2="GOV_STRIP_Y"
					:stroke="g.color"
					stroke-width="2"
					:stroke-opacity="hoverGovNr === g.nr ? 1 : 0.55"
					pointer-events="none"
				/>
				<!-- Chancellor last-name label (only if band is wide enough) -->
				<text
					v-if="g.x2 - g.x1 > 44"
					:x="(g.x1 + g.x2) / 2"
					:y="GOV_STRIP_Y + GOV_STRIP_H / 2 + 0.5"
					class="gov-label"
					text-anchor="middle"
					dominant-baseline="middle"
					:clip-path="`url(#strip-${uid})`"
					:fill="g.color"
					:fill-opacity="hoverGovNr === g.nr ? 1 : 0.8"
					pointer-events="none"
					>{{ shortName(g.chancellor) }}</text
				>
			</template>

			<!-- historical event guides (faint, behind the data lines) -->
			<line
				v-for="(ev, i) in eventMarks"
				:key="ev.date"
				:x1="ev.px"
				:x2="ev.px"
				:y1="m.t"
				:y2="H - m.b"
				class="event-line"
				:class="{ active: hoverEventIdx === i }"
			/>

			<g
				:key="drawKey"
				:filter="`url(#glow-${uid})`"
				:clip-path="playing ? `url(#reveal-${uid})` : undefined"
			>
				<path
					v-for="party in visible"
					:key="party"
					:d="linePath(party)"
					fill="none"
					:stroke="partyColor(party)"
					stroke-width="2.4"
					stroke-linejoin="round"
					stroke-linecap="round"
					pathLength="1"
					class="line"
					:class="{ dim: hoverParty && hoverParty !== party }"
					:style="`--draw-dur: ${drawDur}s`"
				/>
			</g>

			<!-- play-through: glowing scan line + moving line heads (past → present) -->
			<template v-if="playing">
				<line :x1="scanX" :x2="scanX" :y1="m.t" :y2="H - m.b" class="scan-line" />
				<circle
					v-for="p in leadingPoints"
					:key="p.party"
					:cx="p.x"
					:cy="p.y"
					r="4.5"
					:fill="p.color"
					stroke="var(--bg)"
					stroke-width="1.5"
					:filter="`url(#glow-${uid})`"
					class="scan-head"
				/>
			</template>

			<!-- hover crosshair + markers -->
			<template v-if="hoverRows && !playing">
				<line
					:x1="x(hoverRows.date)"
					:x2="x(hoverRows.date)"
					:y1="m.t"
					:y2="H - m.b"
					class="crosshair"
				/>
				<circle
					v-for="r in hoverRows.items"
					:key="r.party"
					:cx="x(hoverRows.date)"
					:cy="y(r.value)"
					r="5.5"
					:fill="partyColor(r.party)"
					stroke="var(--surface)"
					stroke-width="2.5"
					class="marker"
					role="button"
					tabindex="0"
					:aria-label="`${r.party} ${hoverRows.period}`"
					@click="emit('pick', hoverRows!.period)"
					@keydown="(e: KeyboardEvent) => e.key === 'Enter' && emit('pick', hoverRows!.period)"
				/>
			</template>

			<!-- main capture layer (plot area only) -->
			<rect
				:x="m.l"
				:y="m.t"
				:width="Math.max(0, cw - m.l - m.r)"
				:height="H - m.t - m.b"
				fill="transparent"
				class="capture"
				@mousemove="onmove"
				@mouseleave="hoverIdx = null"
				@click="onChartClick"
				role="presentation"
			/>

			<!-- event markers — sit on top so they stay hoverable over the capture layer -->
			<g
				v-for="(ev, i) in eventMarks"
				:key="ev.date"
				class="event-mark"
				role="img"
				:aria-label="`${ev.year}: ${ev.label}`"
				@mouseenter="hoverEventIdx = i"
				@mouseleave="hoverEventIdx = null"
			>
				<circle :cx="ev.px" :cy="m.t" r="9" fill="transparent" />
				<circle :cx="ev.px" :cy="m.t" r="2.8" class="event-dot" :class="{ active: hoverEventIdx === i }" />
			</g>

			<!-- hovered event label pill (topmost) -->
			<g v-if="eventLabel" class="event-tip" pointer-events="none">
				<rect
					:x="eventLabel.cx - eventLabel.w / 2"
					:y="eventLabel.cy - eventLabel.h / 2"
					:width="eventLabel.w"
					:height="eventLabel.h"
					:rx="eventLabel.h / 2"
					class="event-pill"
				/>
				<text
					:x="eventLabel.cx"
					:y="eventLabel.cy"
					class="event-label"
					text-anchor="middle"
					dominant-baseline="central"
					>{{ eventLabel.text }}</text
				>
			</g>
		</svg>

		<!-- Data tooltip -->
		<div
			v-if="hoverRows && hoverRows.items.length"
			class="tooltip"
			:style="{ left: `${Math.min(cw - 180, Math.max(0, x(hoverRows.date) + 12))}px` }"
		>
			<strong>{{ fmtYear(hoverRows.date) }}</strong>
			<div v-for="r in hoverRows.items.slice(0, 8)" :key="r.party" class="trow">
				<span class="dot" :style="{ background: partyColor(r.party) }"></span>
				<span class="tp">{{ r.party }}</span>
				<span class="tv">{{ formatNumber(r.value, i18n.lang) }}</span>
			</div>
			<div class="thint">{{ valueLabel }}</div>
		</div>

		<!-- Government tooltip -->
		<div
			v-if="hoveredGov && hoveredGovBand"
			class="gov-tooltip"
			:style="{
				left: `${Math.min(cw - 220, Math.max(0, (hoveredGovBand.x1 + hoveredGovBand.x2) / 2 - 100))}px`
			}"
		>
			<div class="gov-tt-header" :style="{ borderColor: hoveredGovBand.color }">
				<span class="gov-tt-name">{{ hoveredGov.name }}</span>
				<span class="gov-tt-chancellor">{{ hoveredGov.chancellor }}</span>
			</div>
			<div class="gov-tt-coalition">
				<span
					v-for="p in hoveredGov.parties"
					:key="p"
					class="gov-tt-party"
					:style="{ background: partyColor(p) }"
					>{{ p }}</span
				>
			</div>
			<div class="gov-tt-dates">
				{{ fmtDate(new Date(hoveredGov.start)) }}
				{{ ' – ' }}
				{{
					hoveredGov.end
						? fmtDate(new Date(hoveredGov.end))
						: i18n.lang === 'de'
							? 'heute'
							: 'present'
				}}
			</div>
		</div>
	</div>
</template>

<style scoped>
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
	transition:
		color 0.2s,
		border-color 0.2s,
		background 0.2s,
		box-shadow 0.2s;
}
.tl-play:hover {
	color: var(--ink);
	border-color: color-mix(in srgb, var(--accent) 45%, var(--line-2));
	background: color-mix(in srgb, var(--accent) 8%, transparent);
}
.tl-play svg {
	color: var(--accent);
}
.tl-play.playing {
	color: var(--ink);
	border-color: color-mix(in srgb, var(--accent) 55%, transparent);
	background: color-mix(in srgb, var(--accent) 12%, transparent);
	box-shadow: 0 0 0 1px color-mix(in srgb, var(--accent) 25%, transparent);
}
/* Play-through scan */
.scan-line {
	stroke: var(--accent);
	stroke-width: 1.5;
	stroke-opacity: 0.85;
	filter: drop-shadow(0 0 6px color-mix(in srgb, var(--accent) 70%, transparent));
}
/* Historical event markers */
.event-line {
	stroke: var(--ink);
	stroke-opacity: 0.07;
	stroke-width: 1;
	stroke-dasharray: 2 4;
	pointer-events: none;
	transition:
		stroke 0.2s,
		stroke-opacity 0.2s;
}
.event-line.active {
	stroke: var(--accent);
	stroke-opacity: 0.55;
	stroke-dasharray: none;
}
.event-mark {
	cursor: help;
}
.event-dot {
	fill: var(--surface);
	stroke: color-mix(in srgb, var(--accent) 45%, var(--ink-3));
	stroke-width: 1.4;
	transition:
		r 0.15s var(--spring),
		fill 0.2s,
		stroke 0.2s;
}
.event-mark:hover .event-dot,
.event-dot.active {
	fill: var(--accent);
	stroke: var(--accent);
	r: 3.6;
}
.event-tip {
	animation: ev-in 0.15s ease both;
}
@keyframes ev-in {
	from {
		opacity: 0;
	}
	to {
		opacity: 1;
	}
}
.event-pill {
	fill: color-mix(in srgb, var(--surface) 92%, transparent);
	stroke: var(--line-2);
	stroke-width: 1;
}
.event-label {
	fill: var(--ink);
	font-family: var(--sans);
	font-size: 0.68rem;
	font-weight: 600;
	letter-spacing: 0.01em;
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
	animation: draw var(--draw-dur, 1.1s) var(--ease) forwards;
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

<script setup lang="ts">
// Ported from ParliamentArc.svelte.
// A parliament hemicycle whose sectors are the REAL all-time share of
// speeches per party (precomputed in party_shares.json from the corpus —
// 766k speeches). Hover a wedge to read that party's share in the centre.
//
// Runes → Vue map used here:
//   $state<T>(v)      → ref<T>(v)       (.value in <script>, auto-unwraps in <template>)
//   $derived(expr)    → computed(() => expr)
//   i18n import path  → '$lib/i18n' (no .svelte suffix)
import { ref, computed } from 'vue';
import shares from '$lib/party_shares.json';
import { partyColor, formatNumber } from '$lib/format';
import { i18n } from '$lib/i18n';

const OTHER_COLOR = '#5b6276'; // cool slate for the "Sonstige" bucket

const W = 540,
	H = 282;
const CX = W / 2,
	CY = H - 8;
const ROW_RADII = [112, 138, 164, 190, 216];
const DOT_R = 3.4;
const HIT_R = 232; // outer radius of the (transparent) hover wedges

function colorFor(p: { party: string; other?: boolean }) {
	return p.other ? OTHER_COLOR : partyColor(p.party);
}

// Angular sectors — each party occupies an arc proportional to its share,
// laid out left→right across the π…0 hemicycle (Bundestag seating order).
let theta = Math.PI;
const sectors = shares.parties.map((p) => {
	const span = Math.PI * p.share;
	const a0 = theta; // left edge (larger angle)
	const a1 = theta - span; // right edge
	theta = a1;
	return { ...p, a0, a1, color: colorFor(p) };
});

function partyAt(angle: number): (typeof sectors)[number] {
	for (const s of sectors) if (angle <= s.a0 && angle > s.a1) return s;
	return sectors[sectors.length - 1];
}

// Dots per row ∝ radius so angular density stays constant.
const TOTAL = 480;
const sumR = ROW_RADII.reduce((s, r) => s + r, 0);
let rem = TOTAL;
const rowCounts = ROW_RADII.map((r, i) => {
	if (i < ROW_RADII.length - 1) {
		const n = Math.round((TOTAL * r) / sumR);
		rem -= n;
		return n;
	}
	return Math.max(1, rem);
});

interface Dot {
	x: number;
	y: number;
	color: string;
	party: string;
	row: number;
}
const dots: Dot[] = [];
for (let ri = 0; ri < ROW_RADII.length; ri++) {
	const r = ROW_RADII[ri];
	const n = rowCounts[ri];
	for (let j = 0; j < n; j++) {
		const angle = Math.PI - (Math.PI * j) / (n - 1);
		const s = partyAt(angle);
		dots.push({
			x: CX + r * Math.cos(angle),
			y: CY - r * Math.sin(angle),
			color: s.color,
			party: s.party,
			row: ri
		});
	}
}

// Transparent wedge polygons (sampled, so no SVG arc-flag guesswork) — these
// capture the hover for each sector.
function wedgePath(a0: number, a1: number): string {
	const pts: string[] = [`${CX},${CY}`];
	const steps = 14;
	for (let k = 0; k <= steps; k++) {
		const a = a0 + ((a1 - a0) * k) / steps;
		pts.push(`${(CX + HIT_R * Math.cos(a)).toFixed(1)},${(CY - HIT_R * Math.sin(a)).toFixed(1)}`);
	}
	return `M${pts.join('L')}Z`;
}

const hovered = ref<string | null>(null);
const active = computed(() =>
	hovered.value ? sectors.find((s) => s.party === hovered.value) ?? null : null
);
const pct = (share: number) => {
	const v = (share * 100).toFixed(1);
	return i18n.lang === 'de' ? v.replace('.', ',') : v;
};
const activeLabel = computed(() =>
	active.value ? (active.value.other ? i18n.t('arc_other') : active.value.party) : null
);
</script>

<template>
	<svg
		:viewBox="`0 0 ${W} ${H}`"
		role="img"
		:aria-label="i18n.t('arc_aria')"
		class="parl"
		@mouseleave="hovered = null"
	>
		<defs>
			<filter id="parl-glow" x="-30%" y="-30%" width="160%" height="160%">
				<feGaussianBlur in="SourceGraphic" stdDeviation="3" result="blur" />
				<feMerge>
					<feMergeNode in="blur" />
					<feMergeNode in="SourceGraphic" />
				</feMerge>
			</filter>
		</defs>

		<g filter="url(#parl-glow)" class="dots" :class="{ focused: hovered }">
			<circle
				v-for="(d, i) in dots"
				:key="i"
				:cx="d.x"
				:cy="d.y"
				:r="DOT_R"
				:fill="d.color"
				class="d"
				:class="[`r${d.row}`, { dim: hovered && d.party !== hovered }]"
			/>
		</g>

		<!-- centre readout: total by default, hovered party's share on hover -->
		<g class="readout" pointer-events="none" text-anchor="middle">
			<template v-if="active">
				<text :x="CX" :y="CY - 96" class="ro-big" :fill="active!.color">{{ pct(active!.share) }} %</text>
				<text :x="CX" :y="CY - 70" class="ro-lbl">{{ activeLabel }}</text>
			</template>
			<template v-else>
				<text :x="CX" :y="CY - 96" class="ro-big">{{ formatNumber(shares.total, i18n.lang) }}</text>
				<text :x="CX" :y="CY - 70" class="ro-lbl">{{ i18n.t('arc_total') }}</text>
			</template>
		</g>

		<!-- transparent hover wedges (on top) -->
		<path
			v-for="s in sectors"
			:key="s.party"
			:d="wedgePath(s.a0, s.a1)"
			class="wedge"
			role="presentation"
			@mouseenter="hovered = s.party"
		/>
	</svg>
</template>

<style scoped>
.parl {
	width: 100%;
	height: auto;
	display: block;
	overflow: visible;
}
.d {
	opacity: 0.7;
	transition: opacity 0.25s var(--ease);
}
.d.dim {
	opacity: 0.14;
}
/* One gentle ambient signature — a slow staggered breath, inner to outer.
   Suppressed while the user is reading a sector. */
.dots:not(.focused) .r0 { animation: breathe 6s ease-in-out infinite 0s; }
.dots:not(.focused) .r1 { animation: breathe 6s ease-in-out infinite 0.7s; }
.dots:not(.focused) .r2 { animation: breathe 6s ease-in-out infinite 1.4s; }
.dots:not(.focused) .r3 { animation: breathe 6s ease-in-out infinite 2.1s; }
.dots:not(.focused) .r4 { animation: breathe 6s ease-in-out infinite 2.8s; }
@keyframes breathe {
	0%, 100% { opacity: 0.6; }
	50%      { opacity: 0.85; }
}
.wedge {
	fill: transparent;
	pointer-events: all;
	cursor: pointer;
}
.ro-big {
	font-family: var(--display);
	font-weight: 700;
	font-size: 30px;
	fill: var(--ink);
	font-variant-numeric: tabular-nums;
	letter-spacing: -0.02em;
}
.ro-lbl {
	font-family: var(--sans);
	font-size: 11px;
	font-weight: 600;
	letter-spacing: 0.08em;
	text-transform: uppercase;
	fill: var(--ink-3);
}
@media (prefers-reduced-motion: reduce) {
	.d { animation: none; opacity: 0.75; }
}
</style>

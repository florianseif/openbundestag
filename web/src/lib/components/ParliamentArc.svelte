<script lang="ts">
// Approximate speech proportions 1949–2026, ordered left→right by Bundestag seating.
// CDU/CSU is lightened (#d4d4d4) so it reads on the dark hero background.
const PARTIES = [
	{ color: '#BE3075', frac: 0.07 }, // Die Linke
	{ color: '#E3000F', frac: 0.26 }, // SPD
	{ color: '#1AA037', frac: 0.09 }, // Grünen
	{ color: '#9B2335', frac: 0.02 }, // BSW
	{ color: '#FFE000', frac: 0.13 }, // FDP (slightly dimmed yellow)
	{ color: '#d4d4d4', frac: 0.31 }, // CDU/CSU
	{ color: '#009EE0', frac: 0.05 }, // AfD
	{ color: '#606060', frac: 0.07 }, // Fraktionslos
];

const W = 540, H = 282;
const CX = W / 2, CY = H - 8;
const ROW_RADII = [112, 138, 164, 190, 216];
const DOT_R = 3.4;

// Dots per row ∝ radius so angular density stays constant
const TOTAL = 480;
const sumR = ROW_RADII.reduce((s, r) => s + r, 0);
let rem = TOTAL;
const rowCounts = ROW_RADII.map((r, i) => {
	if (i < ROW_RADII.length - 1) {
		const n = Math.round(TOTAL * r / sumR);
		rem -= n;
		return n;
	}
	return Math.max(1, rem);
});

// Angular sectors — each party occupies an arc proportional to speech share
let θ = Math.PI;
const sectors: { color: string; θEnd: number }[] = PARTIES.map((p) => {
	const θEnd = θ - Math.PI * p.frac;
	const s = { color: p.color, θEnd };
	θ = θEnd;
	return s;
});

function dotColor(angle: number): string {
	for (const s of sectors) {
		if (angle > s.θEnd) return s.color;
	}
	return '#606060';
}

interface Dot { x: number; y: number; color: string; row: number }
const dots: Dot[] = [];
for (let ri = 0; ri < ROW_RADII.length; ri++) {
	const r = ROW_RADII[ri];
	const n = rowCounts[ri];
	for (let j = 0; j < n; j++) {
		const angle = Math.PI - (Math.PI * j / (n - 1));
		dots.push({
			x: CX + r * Math.cos(angle),
			y: CY - r * Math.sin(angle),
			color: dotColor(angle),
			row: ri,
		});
	}
}
</script>

<svg viewBox="0 0 {W} {H}" role="img" aria-label="Parlamentsvisualisierung" class="parl">
	<defs>
		<filter id="parl-glow" x="-30%" y="-30%" width="160%" height="160%">
			<feGaussianBlur in="SourceGraphic" stdDeviation="3" result="blur" />
			<feMerge>
				<feMergeNode in="blur" />
				<feMergeNode in="SourceGraphic" />
			</feMerge>
		</filter>
	</defs>
	<g filter="url(#parl-glow)">
		{#each dots as d}
			<circle cx={d.x} cy={d.y} r={DOT_R} fill={d.color} class="d r{d.row}" />
		{/each}
	</g>
</svg>

<style>
	.parl {
		width: 100%;
		height: auto;
		display: block;
		overflow: visible;
	}
	.d { opacity: 0.7; }
	/* One gentle ambient signature — a slow staggered breath, inner to outer.
	   Kept subtle on purpose; this is the only always-on motion on the page. */
	.r0 { animation: breathe 6s ease-in-out infinite 0s; }
	.r1 { animation: breathe 6s ease-in-out infinite 0.7s; }
	.r2 { animation: breathe 6s ease-in-out infinite 1.4s; }
	.r3 { animation: breathe 6s ease-in-out infinite 2.1s; }
	.r4 { animation: breathe 6s ease-in-out infinite 2.8s; }
	@keyframes breathe {
		0%, 100% { opacity: 0.6; }
		50%       { opacity: 0.85; }
	}
	@media (prefers-reduced-motion: reduce) {
		.d { animation: none; opacity: 0.75; }
	}
</style>

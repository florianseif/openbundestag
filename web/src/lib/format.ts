// Small formatting + party-colour helpers shared across components.

import type { Lang } from './i18n.svelte';

const FALLBACK_COLOR = '#9b9384';

// Canonical party colours (mirrors src/queries.py PARTY_COLORS) so the landing
// page renders correct colours before /api/meta is fetched.
const DEFAULT_COLORS: Record<string, string> = {
	'CDU/CSU': '#000000',
	SPD: '#E3000F',
	AfD: '#009EE0',
	'Bündnis 90/Die Grünen': '#1AA037',
	FDP: '#FFED00',
	'Die Linke': '#BE3075',
	BSW: '#9B2335',
	SSW: '#003082',
	Fraktionslos: '#888888',
	Unknown: '#CCCCCC'
};

let colorMap: Record<string, string> = { ...DEFAULT_COLORS };
let fullNames: Record<string, string> = {};

/** Merge the colour + full-name lookups from /api/meta over the defaults. */
export function setPartyMeta(colors: Record<string, string>, names: Record<string, string>) {
	colorMap = { ...DEFAULT_COLORS, ...colors };
	fullNames = names;
}

export function partyColor(party: string): string {
	return darkSafe(colorMap[party] ?? FALLBACK_COLOR);
}

// Relative luminance of a #rrggbb colour (0 = black … 1 = white).
function luminance(hex: string): number {
	const m = /^#?([0-9a-f]{6})$/i.exec(hex);
	if (!m) return 0.5;
	const n = parseInt(m[1], 16);
	const r = (n >> 16) & 255,
		g = (n >> 8) & 255,
		b = n & 255;
	const lin = (c: number) => {
		const s = c / 255;
		return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
	};
	return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
}

// On the dark canvas, near-black party colours (CDU/CSU is officially #000000)
// vanish. Lift only the darkest colours toward a neutral light so every party
// stays legible while keeping its identity where one exists.
function darkSafe(hex: string): string {
	return luminance(hex) < 0.06 ? '#7a7e8a' : hex;
}

/** Animate `0 → target`, calling `onTick` each frame. Returns a cancel fn. */
export function countUp(target: number, onTick: (v: number) => void, dur = 900): () => void {
	if (typeof window === 'undefined' || window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
		onTick(target);
		return () => {};
	}
	const start = performance.now();
	let raf = 0;
	const step = (now: number) => {
		const p = Math.min(1, (now - start) / dur);
		const eased = 1 - Math.pow(1 - p, 3);
		onTick(Math.round(target * eased));
		if (p < 1) raf = requestAnimationFrame(step);
	};
	raf = requestAnimationFrame(step);
	return () => cancelAnimationFrame(raf);
}

export function partyFullName(party: string): string {
	return fullNames[party] ?? party;
}

export function formatNumber(n: number, lang: Lang): string {
	return new Intl.NumberFormat(lang === 'de' ? 'de-DE' : 'en-GB').format(Math.round(n));
}

export function formatDate(iso: string | null, lang: Lang): string {
	if (!iso) return '—';
	const d = new Date(iso);
	return new Intl.DateTimeFormat(lang === 'de' ? 'de-DE' : 'en-GB', {
		year: 'numeric',
		month: 'short',
		day: 'numeric'
	}).format(d);
}

export function formatYear(iso: string): string {
	return iso.slice(0, 4);
}

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
	return colorMap[party] ?? FALLBACK_COLOR;
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

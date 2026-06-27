// Typed client for the OpenBundestag JSON API.
//
// The base URL comes from VITE_API_BASE (set in web/.env for dev and as a
// Cloudflare Pages build var in prod). Because the API lives on a free HF Space
// that sleeps after ~48h idle, the first request can take up to ~1 minute to
// wake; callers should surface a "waking" state rather than an error.

import { prefetchSearch } from './prefetch';
import type {
	Meta,
	TimelinePoint,
	PartyCount,
	TermCount,
	PoliticianCount,
	Totals,
	SearchResult,
	Politician,
	SpeechPage,
	SpeechFull,
	Filters,
	ZwischenrufMeta,
	ZwischenrufTimelinePoint,
	ZwischenrufCallerCount,
	ZwischenrufPartyCount,
	ZwischenrufMatrixRow,
	ZwischenrufSample,
	BeifallMeta,
	BeifallSelfOther
} from './types';

const BASE = (import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8000').replace(/\/$/, '');

export class ApiError extends Error {
	constructor(
		public status: number,
		message: string
	) {
		super(message);
	}
}

type FetchLike = typeof fetch;

function buildQuery(f: Partial<Filters>, extra: Record<string, unknown> = {}): string {
	const p = new URLSearchParams();
	if (f.word) p.set('word', f.word);
	for (const party of f.parties ?? []) p.append('parties', party);
	for (const term of f.terms ?? []) p.append('terms', String(term));
	if (f.politician_id != null) p.set('politician_id', String(f.politician_id));
	if (f.date_from) p.set('date_from', f.date_from);
	if (f.date_to) p.set('date_to', f.date_to);
	for (const [k, v] of Object.entries(extra)) {
		if (v != null) p.set(k, String(v));
	}
	return p.toString();
}

async function get<T>(path: string, fetcher: FetchLike = fetch): Promise<T> {
	let res: Response;
	try {
		res = await fetcher(`${BASE}${path}`);
	} catch (e) {
		throw new ApiError(0, `Network error reaching the API: ${(e as Error).message}`);
	}
	if (!res.ok) {
		let detail = res.statusText;
		try {
			detail = (await res.json()).detail ?? detail;
		} catch {
			/* ignore */
		}
		throw new ApiError(res.status, detail);
	}
	return res.json() as Promise<T>;
}

export const api = {
	base: BASE,

	meta: (fetcher?: FetchLike) => get<Meta>('/api/meta', fetcher),

	health: (fetcher?: FetchLike) =>
		get<{ status: string; has_text: boolean }>('/health', fetcher),

	politicians: (q: string, limit = 50, fetcher?: FetchLike) =>
		get<Politician[]>(
			`/api/politicians?${new URLSearchParams({ q, limit: String(limit) })}`,
			fetcher
		),

	// Combined explorer query — one request, one text scan, all four panels.
	// Replaces firing total+timeline+byParty+topPoliticians in parallel.
	// Popular words under the default filters are answered instantly from a
	// bundled, precomputed payload (see prefetch.ts) — no network, no scan.
	search: (f: Filters, topN: number, fetcher?: FetchLike) => {
		const cached = prefetchSearch(f, topN);
		if (cached) return Promise.resolve(cached);
		return get<SearchResult>(
			`/api/search?${buildQuery(f, {
				granularity: f.granularity,
				count_mode: f.count_mode,
				top_n: topN
			})}`,
			fetcher
		);
	},

	timeline: (f: Filters, fetcher?: FetchLike) =>
		get<TimelinePoint[]>(
			`/api/timeline?${buildQuery(f, {
				granularity: f.granularity,
				count_mode: f.count_mode
			})}`,
			fetcher
		),

	byParty: (f: Filters, fetcher?: FetchLike) =>
		get<PartyCount[]>(`/api/by-party?${buildQuery(f)}`, fetcher),

	topPoliticians: (f: Filters, topN: number, fetcher?: FetchLike) =>
		get<PoliticianCount[]>(`/api/top-politicians?${buildQuery(f, { top_n: topN })}`, fetcher),

	total: (f: Filters, fetcher?: FetchLike) => get<Totals>(`/api/total?${buildQuery(f)}`, fetcher),

	byTerm: (f: Filters, fetcher?: FetchLike) =>
		get<TermCount[]>(`/api/by-term?${buildQuery(f)}`, fetcher),

	speeches: (f: Filters, limit = 20, offset = 0, fetcher?: FetchLike) =>
		get<SpeechPage>(`/api/speeches?${buildQuery(f, { limit, offset })}`, fetcher),

	speech: (id: number, fetcher?: FetchLike) => get<SpeechFull>(`/api/speech/${id}`, fetcher),

	zwischenrufe: {
		meta: (fetcher?: FetchLike) => get<ZwischenrufMeta>('/api/zwischenrufe/meta', fetcher),

		timeline: (
			typeFilter?: string,
			partyFilter?: string,
			terms?: number[],
			fetcher?: FetchLike
		) => {
			const p = new URLSearchParams();
			if (typeFilter) p.set('type_filter', typeFilter);
			if (partyFilter) p.set('party_filter', partyFilter);
			for (const t of terms ?? []) p.append('terms', String(t));
			return get<ZwischenrufTimelinePoint[]>(`/api/zwischenrufe/timeline?${p}`, fetcher);
		},

		topCallers: (
			typeFilter = 'Zwischenruf',
			terms?: number[],
			partyFilter?: string,
			limit = 20,
			fetcher?: FetchLike
		) => {
			const p = new URLSearchParams({ type_filter: typeFilter, limit: String(limit) });
			for (const t of terms ?? []) p.append('terms', String(t));
			if (partyFilter) p.set('party_filter', partyFilter);
			return get<ZwischenrufCallerCount[]>(`/api/zwischenrufe/top-callers?${p}`, fetcher);
		},

		byParty: (typeFilter = 'Zwischenruf', terms?: number[], fetcher?: FetchLike) => {
			const p = new URLSearchParams({ type_filter: typeFilter });
			for (const t of terms ?? []) p.append('terms', String(t));
			return get<ZwischenrufPartyCount[]>(`/api/zwischenrufe/by-party?${p}`, fetcher);
		},

		matrix: (typeFilter = 'Zwischenruf', terms?: number[], fetcher?: FetchLike) => {
			const p = new URLSearchParams({ type_filter: typeFilter });
			for (const t of terms ?? []) p.append('terms', String(t));
			return get<ZwischenrufMatrixRow[]>(`/api/zwischenrufe/matrix?${p}`, fetcher);
		},

		samples: (
			opts: {
				keyword?: string;
				callerParty?: string;
				callerName?: string;
				targetParty?: string;
				terms?: number[];
				limit?: number;
			} = {},
			fetcher?: FetchLike
		) => {
			const p = new URLSearchParams();
			if (opts.keyword) p.set('keyword', opts.keyword);
			if (opts.callerParty) p.set('caller_party', opts.callerParty);
			if (opts.callerName) p.set('caller_name', opts.callerName);
			if (opts.targetParty) p.set('target_party', opts.targetParty);
			for (const t of opts.terms ?? []) p.append('terms', String(t));
			if (opts.limit) p.set('limit', String(opts.limit));
			return get<ZwischenrufSample[]>(`/api/zwischenrufe/samples?${p}`, fetcher);
		}
	},

	beifall: {
		meta: (fetcher?: FetchLike) => get<BeifallMeta>('/api/beifall/meta', fetcher),

		byParty: (terms?: number[], fetcher?: FetchLike) => {
			const p = new URLSearchParams();
			for (const t of terms ?? []) p.append('terms', String(t));
			return get<ZwischenrufPartyCount[]>(`/api/beifall/by-party?${p}`, fetcher);
		},

		matrix: (terms?: number[], fetcher?: FetchLike) => {
			const p = new URLSearchParams();
			for (const t of terms ?? []) p.append('terms', String(t));
			return get<ZwischenrufMatrixRow[]>(`/api/beifall/matrix?${p}`, fetcher);
		},

		selfVsOther: (terms?: number[], fetcher?: FetchLike) => {
			const p = new URLSearchParams();
			for (const t of terms ?? []) p.append('terms', String(t));
			return get<BeifallSelfOther[]>(`/api/beifall/self-vs-other?${p}`, fetcher);
		}
	}
};

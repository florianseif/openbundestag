// Typed client for the OpenBundestag JSON API.
//
// The base URL comes from PUBLIC_API_BASE (set in web/.env for dev and as a
// Cloudflare Pages build var in prod). Because the API lives on a free HF Space
// that sleeps after ~48h idle, the first request can take up to ~1 minute to
// wake; callers should surface a "waking" state rather than an error.

import { PUBLIC_API_BASE } from '$env/static/public';
import type {
	Meta,
	TimelinePoint,
	PartyCount,
	PoliticianCount,
	Totals,
	Politician,
	SpeechPage,
	Filters
} from './types';

const BASE = (PUBLIC_API_BASE || 'http://127.0.0.1:8000').replace(/\/$/, '');

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
		get<{ status: string; has_raw_text: boolean }>('/health', fetcher),

	politicians: (q: string, limit = 50, fetcher?: FetchLike) =>
		get<Politician[]>(
			`/api/politicians?${new URLSearchParams({ q, limit: String(limit) })}`,
			fetcher
		),

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

	speeches: (f: Filters, limit = 20, offset = 0, fetcher?: FetchLike) =>
		get<SpeechPage>(`/api/speeches?${buildQuery(f, { limit, offset })}`, fetcher)
};

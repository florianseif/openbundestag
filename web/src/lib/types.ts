// Shapes returned by the OpenBundestag API (api/main.py).

export interface TermInfo {
	term: number;
	label: string;
}

export interface Meta {
	min_date: string;
	max_date: string;
	parties: string[];
	party_colors: Record<string, string>;
	party_full_names: Record<string, string>;
	historical_parties: string[];
	terms: TermInfo[];
	keyword_max_len: number;
	has_text: boolean;
}

export interface TimelinePoint {
	period: string; // ISO date (start of month/quarter)
	party: string;
	value: number;
}

export interface PartyCount {
	party: string;
	speeches: number;
}

export interface TermCount {
	term: number;
	speeches: number;
}

export interface PoliticianCount {
	politician: string;
	party: string;
	speeches: number;
}

export interface Totals {
	count: number;
	min_date: string | null;
	max_date: string | null;
}

export interface Politician {
	id: number;
	name: string;
	party: string;
	speeches: number;
}

// Combined explorer payload (/api/search): all four panels from one text scan.
export interface SearchResult {
	total: Totals;
	timeline: TimelinePoint[];
	by_party: PartyCount[];
	by_term: TermCount[];
	top_politicians: PoliticianCount[];
}

export interface SpeechItem {
	id: number;
	session: string;
	electoral_term: number;
	date: string;
	politician_id: number;
	politician: string;
	party: string;
	position_short: string;
	position_long: string | null;
	snippet?: string;
}

export interface SpeechPage {
	items: SpeechItem[];
	limit: number;
	offset: number;
	has_snippet: boolean;
}

export interface SpeechFull {
	id: number;
	session: string;
	electoral_term: number;
	date: string;
	politician_id: number;
	first_name: string;
	last_name: string;
	party: string;
	position_short: string;
	position_long: string | null;
	speech_content?: string;
}

export type Granularity = 'Monthly' | 'Quarterly';
export type CountMode = 'speeches' | 'occurrences';

export interface Filters {
	word: string;
	parties: string[];
	terms: number[];
	politician_id: number | null;
	date_from: string | null;
	date_to: string | null;
	granularity: Granularity;
	count_mode: CountMode;
}

// Zwischenrufe (interjections / heckling)
export interface ZwischenrufMeta {
	available: boolean;
	total: number;
}

export type ZwischenrufType =
	| 'Zwischenruf'
	| 'Beifall'
	| 'Heiterkeit'
	| 'Lachen'
	| 'Widerspruch'
	| 'Zuruf'
	| 'Zustimmung';

export interface ZwischenrufTimelinePoint {
	year: string; // ISO date (start of year)
	type: ZwischenrufType;
	n: number;
}

export interface ZwischenrufCallerCount {
	caller_name: string;
	caller_party: string;
	n: number;
}

export interface ZwischenrufPartyCount {
	caller_party: string;
	n: number;
}

export interface ZwischenrufMatrixRow {
	caller_party: string;
	target_speaker_party: string;
	n: number;
}

export interface ZwischenrufSample {
	id: number;
	date: string;
	electoral_term: number;
	caller_name: string | null;
	caller_party: string | null;
	target_speaker_party: string | null;
	text: string | null;
	raw: string;
}

// Beifall (applause)
export interface BeifallMeta {
	available: boolean;
	total: number;
}

export interface BeifallSelfOther {
	caller_party: string;
	is_self: boolean;
	n: number;
}

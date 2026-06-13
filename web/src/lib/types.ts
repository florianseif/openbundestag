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
	has_raw_text: boolean;
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

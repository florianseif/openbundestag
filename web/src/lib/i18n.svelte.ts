// Minimal DE/EN dictionary + a reactive language store (Svelte 5 runes).
// Mirrors the bilingual strings of the Streamlit app.

export type Lang = 'de' | 'en';

type Dict = Record<string, { de: string; en: string }>;

export const STRINGS: Dict = {
	tagline: {
		de: 'Worte der Macht',
		en: 'Words of Power'
	},
	hero_sub: {
		de: 'Wie verändert sich die Sprache des Deutschen Bundestags? Durchsuche 760.000 Reden seit 1949 — nach Wort, Partei und Rednerin.',
		en: 'How does the language of the German Bundestag change? Search 760,000 speeches since 1949 — by word, party and speaker.'
	},
	cta_explore: { de: 'Daten erkunden', en: 'Explore the data' },
	cta_try: { de: 'Selbst ausprobieren', en: 'Try it yourself' },
	scroll_hint: { de: 'Scrollen', en: 'Scroll' },
	stories_title: { de: 'Drei Schlaglichter', en: 'Three snapshots' },
	stories_lead: {
		de: 'Einzelne Begriffe erzählen die Geschichte des Parlaments. Drei Beispiele.',
		en: 'Single words tell the story of the parliament. Three examples.'
	},

	// Explorer
	search: { de: 'Suche', en: 'Search' },
	keyword: { de: 'Stichwort oder Phrase', en: 'Keyword or phrase' },
	keyword_ph: { de: 'z. B. Klimawandel', en: 'e.g. climate change' },
	filters: { de: 'Filter', en: 'Filters' },
	parties: { de: 'Parteien', en: 'Parties' },
	all_parties: { de: 'Alle Parteien', en: 'All parties' },
	terms: { de: 'Wahlperioden', en: 'Electoral terms' },
	all_terms: { de: 'Alle', en: 'All' },
	politician: { de: 'Rednerin / Redner', en: 'Speaker' },
	any_politician: { de: 'Alle Redner', en: 'All speakers' },
	period: { de: 'Zeitraum', en: 'Date range' },
	granularity: { de: 'Granularität', en: 'Granularity' },
	monthly: { de: 'Monatlich', en: 'Monthly' },
	quarterly: { de: 'Quartalsweise', en: 'Quarterly' },
	count_by: { de: 'Zählen nach', en: 'Count by' },
	speeches: { de: 'Reden', en: 'Speeches' },
	occurrences: { de: 'Wortvorkommen', en: 'Occurrences' },

	tab_timeline: { de: 'Zeitverlauf', en: 'Timeline' },
	tab_party: { de: 'Nach Partei', en: 'By party' },
	tab_top: { de: 'Top Redner', en: 'Top speakers' },

	metric_speeches: { de: 'Reden', en: 'Speeches' },
	metric_first: { de: 'Erste Erwähnung', en: 'First mention' },
	metric_latest: { de: 'Letzte Erwähnung', en: 'Latest mention' },

	stacked: { de: 'Gestapelte Fläche', en: 'Stacked area' },
	share: { de: 'Anteil nach Partei', en: 'Share by party' },
	top_n: { de: 'Anzahl Redner', en: 'Number of speakers' },

	no_results: {
		de: 'Keine Reden mit „{word}“ und den gewählten Filtern.',
		en: 'No speeches containing “{word}” with the current filters.'
	},
	enter_keyword: {
		de: 'Gib ein Stichwort ein, um zu starten.',
		en: 'Enter a keyword to get started.'
	},
	waking: {
		de: 'Die Datenbank wacht auf … (kann beim ersten Mal bis zu einer Minute dauern)',
		en: 'Waking the database … (the first request can take up to a minute)'
	},
	error: { de: 'Etwas ist schiefgelaufen.', en: 'Something went wrong.' },
	retry: { de: 'Erneut versuchen', en: 'Retry' },

	// Drill-down
	read_passage: { de: 'Passagen lesen', en: 'Read passages' },
	drilldown_hint: {
		de: 'Klicke auf einen Punkt im Diagramm, um die Reden zu lesen und herunterzuladen.',
		en: 'Click any point in the chart to read and download the speeches behind it.'
	},
	matching_speeches: { de: 'passende Reden', en: 'matching speeches' },
	flip_to_list: { de: 'Redenübersicht', en: 'Speech list' },
	flip_to_chart: { de: 'Zeitverlauf', en: 'Timeline' },
	prev: { de: 'Zurück', en: 'Back' },
	next: { de: 'Weiter', en: 'Next' },
	download: { de: 'Rede herunterladen', en: 'Download speech' },
	download_protocol: { de: 'Protokoll (PDF)', en: 'Full protocol (PDF)' },
	term_short: { de: 'WP', en: 'Term' },
	session: { de: 'Sitzung', en: 'Session' },
	fulltext_unavailable: {
		de: 'Für diese Rede ist kein Text hinterlegt.',
		en: 'No text is stored for this speech.'
	},
	close: { de: 'Schließen', en: 'Close' },
	speaker: { de: 'Redner/in', en: 'Speaker' },
	party: { de: 'Partei', en: 'Party' },
	role: { de: 'Funktion', en: 'Role' },
	date: { de: 'Datum', en: 'Date' },

	// Explorer dashboard
	overview: { de: 'Überblick', en: 'Overview' },
	leading_party: { de: 'Führende Partei', en: 'Leading party' },
	timeline_over_time: { de: 'Verlauf über die Zeit', en: 'Usage over time' },
	by_party_title: { de: 'Verteilung nach Partei', en: 'Distribution by party' },
	by_term_title: { de: 'Reden je Wahlperiode', en: 'Speeches by term' },
	top_speakers_title: { de: 'Wer spricht am meisten?', en: 'Who speaks the most?' },
	tab_parties: { de: 'Parteien', en: 'Parties' },
	tab_speakers: { de: 'Redner', en: 'Speakers' },
	party_tab_unavailable: {
		de: 'Parteienansicht ist nicht verfügbar, wenn nach einer einzelnen Person gefiltert wird.',
		en: 'Party view is not available when filtering by a single politician.'
	},
	reset: { de: 'Zurücksetzen', en: 'Reset' },

	// Zwischenrufe explorer
	nav_zwischenrufe: { de: 'Zwischenrufe', en: 'Heckling' },
	zw_title: { de: 'Zwischenrufe', en: 'Parliamentary Heckling' },
	zw_subtitle: {
		de: 'Wer unterbricht wen im Deutschen Bundestag?',
		en: 'Who heckles whom in the German Bundestag?'
	},
	zw_total: { de: 'Reaktionen gesamt', en: 'Total reactions' },
	zw_top_caller: { de: 'Aktivste/r Zwischenrufer/in', en: 'Most active heckler' },
	zw_most_active_party: { de: 'Lauteste Fraktion', en: 'Loudest faction' },
	zw_most_interrupted: { de: 'Meist unterbrochen', en: 'Most interrupted' },
	zw_matrix_title: { de: 'Wer ruft wem dazwischen?', en: 'Who heckles whom?' },
	zw_matrix_hint: {
		de: 'Zeilen = Rufende Partei · Spalten = Unterbrochene Partei',
		en: 'Rows = calling party · Columns = interrupted party'
	},
	zw_top_title: { de: 'Top Zwischenrufer/innen', en: 'Top hecklers' },
	zw_feed_title: { de: 'Einzelne Zwischenrufe', en: 'Individual interjections' },
	zw_search_ph: { de: 'Zwischenrufe durchsuchen…', en: 'Search interjections…' },
	zw_filter_type: { de: 'Typ', en: 'Type' },
	zw_filter_caller: { de: 'Rufende Partei', en: 'Calling party' },
	zw_filter_target: { de: 'Unterbrochene Partei', en: 'Interrupted party' },
	zw_type_zwischenruf: { de: 'Zwischenruf', en: 'Interjection' },
	zw_type_beifall: { de: 'Beifall', en: 'Applause' },
	zw_type_heiterkeit: { de: 'Heiterkeit', en: 'Laughter' },
	zw_type_widerspruch: { de: 'Widerspruch', en: 'Dissent' },
	zw_type_zuruf: { de: 'Zuruf', en: 'Shout' },
	zw_calls: { de: 'Rufe', en: 'calls' },
	zw_unavailable: {
		de: 'Zwischenrufe noch nicht extrahiert. Führe zuerst --phase zwischenrufe aus.',
		en: 'Interjections not yet extracted. Run --phase zwischenrufe first.'
	},
	zw_no_results: { de: 'Keine Zwischenrufe gefunden.', en: 'No interjections found.' },

	footer_data: { de: 'Datenquelle & Lizenz', en: 'Data source & licence' },
	footer_body: {
		de: 'Redebeiträge: offizielle Plenarprotokolle des Deutschen Bundestages (§ 5 Abs. 1 UrhG), © Deutscher Bundestag. Ministerdaten: Wikipedia (CC BY-SA 4.0). Ein unabhängiges Projekt, inspiriert von Open Discourse.',
		en: 'Speeches: official plenary protocols of the German Bundestag (§ 5 (1) UrhG), © Deutscher Bundestag. Minister data: Wikipedia (CC BY-SA 4.0). An independent project, inspired by Open Discourse.'
	}
};

class I18n {
	lang = $state<Lang>('de');

	t(key: string, vars: Record<string, string | number> = {}): string {
		const entry = STRINGS[key];
		if (!entry) return key;
		let s = entry[this.lang];
		for (const [k, v] of Object.entries(vars)) s = s.replace(`{${k}}`, String(v));
		return s;
	}

	toggle() {
		this.lang = this.lang === 'de' ? 'en' : 'de';
	}
}

export const i18n = new I18n();

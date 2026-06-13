"""OpenBundestag  -  Streamlit frontend.

Run with:  uv run streamlit run app.py
"""

import os
import re
from datetime import date

import duckdb
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# Local default; overridable for deployment (e.g. a downloaded copy on HF Spaces).
DB_PATH = os.environ.get("DB_PATH", "openbundestag-data.db")

# ---------------------------------------------------------------------------
# Translations
# ---------------------------------------------------------------------------

TRANSLATIONS: dict[str, dict[str, str]] = {
    # Page
    "title":               {"de": "🏛️ OpenBundestag", "en": "🏛️ OpenBundestag"},
    "caption":             {"de": "Worte der Macht  ·  Wortgebrauch in Bundestagsplenardebatten seit 1949",
                            "en": "Words of Power  ·  Word usage in Bundestag plenary debates since 1949"},
    # Sidebar sections
    "search":              {"de": "Suche", "en": "Search"},
    "keyword_label":       {"de": "Stichwort oder Phrase", "en": "Keyword or phrase"},
    "keyword_placeholder": {"de": "z. B. Klimawandel", "en": "e.g. climate change"},
    "filters":             {"de": "Filter", "en": "Filters"},
    "incl_historical":     {"de": "Historische Parteien einschließen", "en": "Include historical parties"},
    "party":               {"de": "Partei", "en": "Party"},
    "all_parties":         {"de": "Alle Parteien", "en": "All parties"},
    "electoral_term":      {"de": "Wahlperiode", "en": "Electoral term"},
    "all_terms":           {"de": "Alle Wahlperioden", "en": "All terms"},
    "date_range":          {"de": "Zeitraum", "en": "Date range"},
"chart_options":       {"de": "Diagrammoptionen", "en": "Chart options"},
    "granularity":         {"de": "Zeitgranularität", "en": "Timeline granularity"},
    "monthly":             {"de": "Monatlich", "en": "Monthly"},
    "quarterly":           {"de": "Quartalsweise", "en": "Quarterly"},
    "count_by":            {"de": "Zählen nach", "en": "Count by"},
    "speeches":            {"de": "Reden", "en": "Speeches"},
    "occurrences":         {"de": "Wortvorkommen", "en": "Word occurrences"},
    # Main area
    "enter_keyword":       {"de": "Gib ein Stichwort oder eine Phrase in der Seitenleiste ein.",
                            "en": "Enter a keyword or phrase in the sidebar to get started."},
    "no_results":          {"de": "Keine Reden mit **\"{word}\"** und den gewählten Filtern gefunden.",
                            "en": "No speeches found containing **\"{word}\"** with the current filters."},
    "metric_speeches":     {"de": "Reden", "en": "Speeches"},
    "metric_first":        {"de": "Erste Erwähnung", "en": "First mention"},
    "metric_latest":       {"de": "Letzte Erwähnung", "en": "Latest mention"},
    "metric_keyword":      {"de": "Stichwort", "en": "Keyword"},
    # Tabs
    "tab_timeline":        {"de": "📈 Zeitverlauf", "en": "📈 Timeline"},
    "tab_party":           {"de": "🥧 Nach Partei", "en": "🥧 By party"},
    "tab_politicians":     {"de": "🎤 Top Redner", "en": "🎤 Top politicians"},
    "no_data":             {"de": "Keine Daten für die gewählten Filter.", "en": "No data for the current filters."},
    # Timeline tab
    "stacked_area":        {"de": "Als gestapelte Fläche anzeigen", "en": "Show as stacked area"},
    "stacked_over_time":   {"de": "Gestapelt über Zeit", "en": "Stacked over time"},
    # Top politicians tab
    "top_n_slider":        {"de": "Top N Redner anzeigen", "en": "Show top N politicians"},
    # Chart labels
    "date":                {"de": "Datum", "en": "Date"},
    "party_label":         {"de": "Partei", "en": "Party"},
    # Chart titles (use .format(word=..., mode=...))
    "title_timeline":      {"de": '„{word}" - {mode} im Zeitverlauf',
                            "en": '"{word}" - {mode} over time'},
    "title_stacked_area":  {"de": '„{word}" - gestapelte Flaeche nach Partei',
                            "en": '"{word}" - stacked area by party'},
    "title_by_party":      {"de": '„{word}" - Reden pro Partei',
                            "en": '"{word}" - speeches per party'},
    "title_share":         {"de": '„{word}" - Anteil nach Partei',
                            "en": '"{word}" - share by party'},
    "title_stacked_bar":   {"de": '„{word}" - gestapelte Reden pro {gran}',
                            "en": '"{word}" - stacked speeches per {gran}'},
    "title_top":           {"de": '„{word}" - Top-Redner',
                            "en": '"{word}" - top speakers'},
    "gran_monthly":        {"de": "Monat", "en": "month"},
    "gran_quarterly":      {"de": "Quartal", "en": "quarter"},
    # Footer
    "footer": {
        "de": """
**Datenquelle & Lizenz**

Die in dieser Anwendung verwendeten Redebeiträge sind die offiziellen Plenarprotokolle des Deutschen Bundestages,
veröffentlicht auf dem [Open-Data-Portal des Bundestages](https://www.bundestag.de/services/opendata).

Als amtliche parlamentarische Dokumente sind die Plenarprotokolle gemäß **§ 5 Abs. 1 UrhG** nicht urheberrechtlich geschützt.

**Pflichtangabe bei Veröffentlichung:** © Deutscher Bundestag  - 
[www.bundestag.de/services/opendata](https://www.bundestag.de/services/opendata)

Die Daten dürfen für Berichterstattung, Bildungs- und Forschungszwecke frei verwendet werden.
Kommerzielle Werbezwecke sind gemäß den [Nutzungsbedingungen](https://www.bundestag.de/nutzungsbedingungen) des Bundestages nicht gestattet.

Ministerdaten von Wikipedia unter der [Creative Commons Attribution-ShareAlike 4.0 Lizenz (CC BY-SA 4.0)](https://creativecommons.org/licenses/by-sa/4.0/).
""",
        "en": """
**Data source & licence**

The speech transcripts used in this application are the official plenary protocols
(*Plenarprotokolle*) of the German Bundestag, published on the
[Bundestag Open Data portal](https://www.bundestag.de/services/opendata).

As official parliamentary documents, the plenary protocols are classified as
*amtliche Werke* under **§ 5 Abs. 1 UrhG** (German Copyright Act) and are therefore
not subject to copyright protection.

**Required attribution:** © Deutscher Bundestag  - 
[www.bundestag.de/services/opendata](https://www.bundestag.de/services/opendata)

The data may be used freely for reporting, educational, and research purposes.
Commercial advertising use is not permitted under the Bundestag's
[terms of use](https://www.bundestag.de/nutzungsbedingungen).

Minister data sourced from Wikipedia under the
[Creative Commons Attribution-ShareAlike 4.0 licence (CC BY-SA 4.0)](https://creativecommons.org/licenses/by-sa/4.0/).
""",
    },
}


def t(key: str, lang: str, **kwargs) -> str:
    text = TRANSLATIONS[key][lang]
    return text.format(**kwargs) if kwargs else text


# ---------------------------------------------------------------------------
# Reference data (party metadata, electoral terms, derived-column names) and
# the SQL query layer live in src/queries.py — the single source of truth shared
# with the FastAPI service (api/main.py). Imported here for the UI to reuse.
# ---------------------------------------------------------------------------
from src import queries as q  # noqa: E402
from src.queries import (  # noqa: E402
    HISTORICAL_PARTIES,
    PARTY_COLORS,
    PARTY_FULL_NAMES,
    TERM_LABELS,
)

# ---------------------------------------------------------------------------
# DB connection (cached for the session) — thin Streamlit wrappers over
# src/queries.py so caching policy stays here and the SQL stays shared.
# ---------------------------------------------------------------------------

@st.cache_resource
def get_connection() -> duckdb.DuckDBPyConnection:
    return q.open_connection(DB_PATH)


# Reference data only changes when the pipeline rebuilds the DB, so cache it
# for an hour rather than re-querying on every interaction.
@st.cache_data(ttl=3600)
def load_date_range() -> tuple:
    rng = q.date_range(get_connection())
    return rng if rng is not None else (None, None)


@st.cache_data(ttl=3600)
def load_parties() -> list[str]:
    return q.parties(get_connection())


@st.cache_data(ttl=3600)
def query_timeline(
    word: str,
    parties: list[str],
    terms: list[int],
    politician_id: int | None,
    granularity: str,
    count_mode: str,
    date_from: str | None = None,
    date_to: str | None = None,
) -> pd.DataFrame:
    return q.timeline(
        get_connection(), word, parties, terms, politician_id,
        granularity, count_mode, date_from, date_to,
    )


@st.cache_data(ttl=3600)
def query_by_party(
    word: str,
    parties: list[str],
    terms: list[int],
    politician_id: int | None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> pd.DataFrame:
    return q.by_party(
        get_connection(), word, parties, terms, politician_id, date_from, date_to
    )


@st.cache_data(ttl=3600)
def query_top_politicians(
    word: str,
    parties: list[str],
    terms: list[int],
    top_n: int = 15,
    date_from: str | None = None,
    date_to: str | None = None,
) -> pd.DataFrame:
    return q.top_politicians(
        get_connection(), word, parties, terms, top_n, date_from, date_to
    )


@st.cache_data(ttl=3600)
def query_total(
    word: str,
    parties: list[str],
    terms: list[int],
    politician_id: int | None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict:
    return q.total(
        get_connection(), word, parties, terms, politician_id, date_from, date_to
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def color_sequence(parties: list[str]) -> list[str]:
    return [PARTY_COLORS.get(p, "#AAAAAA") for p in parties]


def expand_party_names(df: pd.DataFrame, col: str = "party") -> pd.DataFrame:
    """Replace party abbreviations with full names in a DataFrame column."""
    df = df.copy()
    df[col] = df[col].map(lambda p: PARTY_FULL_NAMES.get(p, p))
    return df


def full_color_map(parties: list[str]) -> dict[str, str]:
    """Build color_map keyed by full party names."""
    return {
        PARTY_FULL_NAMES.get(p, p): PARTY_COLORS.get(p, "#AAAAAA")
        for p in parties
    }


def safe_word(text: str) -> str:
    """Escape special regex/SQL chars for display."""
    return re.sub(r"[%_]", lambda m: "\\" + m.group(), text)


# ---------------------------------------------------------------------------
# Page layout
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="OpenBundestag — Worte der Macht",
    page_icon="🏛️",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Sidebar  -  search & filters
# ---------------------------------------------------------------------------

lang = st.session_state.get("_lang", "de")

with st.sidebar:
    st.header(t("search", lang))
    word = st.text_input(t("keyword_label", lang), placeholder=t("keyword_placeholder", lang),
                         value="Klimawandel", max_chars=80)

    st.divider()
    st.header(t("filters", lang))

    all_parties = load_parties()
    show_historical = st.checkbox(t("incl_historical", lang), value=False)
    visible_parties = (
        all_parties if show_historical
        else [p for p in all_parties if p not in HISTORICAL_PARTIES]
    )
    selected_parties = st.multiselect(
        t("party", lang),
        options=visible_parties,
        format_func=lambda p: PARTY_FULL_NAMES.get(p, p),
        default=[],
        placeholder=t("all_parties", lang),
    )

    available_terms = list(TERM_LABELS.keys())
    selected_terms = st.multiselect(
        t("electoral_term", lang),
        options=available_terms,
        format_func=lambda term: TERM_LABELS[term],
        default=[],
        placeholder=t("all_terms", lang),
    )

    db_min, db_max = load_date_range()
    default_from = max(db_min, date(1990, 1, 1))
    date_range = st.slider(
        t("date_range", lang),
        min_value=db_min,
        max_value=db_max,
        value=(default_from, db_max),
        format="YYYY",
    )
    date_from = date_range[0].isoformat()
    date_to   = date_range[1].isoformat()

    selected_pol_id = None

    st.divider()
    st.header(t("chart_options", lang))
    granularity_key = st.radio(
        t("granularity", lang),
        ["monthly", "quarterly"],
        format_func=lambda k: t(k, lang),
        index=0,
    )
    granularity = "Monthly" if granularity_key == "monthly" else "Quarterly"
    count_mode_key = st.radio(
        t("count_by", lang),
        ["speeches", "occurrences"],
        format_func=lambda k: t(k, lang),
        index=0,
    )
    # count_mode stays as English key for query logic; translated only for labels
    count_mode = count_mode_key

    st.divider()
    lang = st.radio("", ["de", "en"],
                    format_func=lambda l: "🇩🇪 DE" if l == "de" else "🇬🇧 EN",
                    horizontal=True, index=0, label_visibility="collapsed",
                    key="_lang")

# ---------------------------------------------------------------------------
# Main area
# ---------------------------------------------------------------------------

st.title(t("title", lang))
st.caption(t("caption", lang))

if not word.strip():
    st.info(t("enter_keyword", lang))
    st.stop()

word = word.strip()
terms_filter = selected_terms or []

# If the user picked specific parties, use those.
# Otherwise filter out historical parties unless the checkbox is on.
if selected_parties:
    parties_filter = selected_parties
elif not show_historical:
    parties_filter = [p for p in visible_parties if p != "Unknown"]
else:
    parties_filter = []

# -- Summary metrics ---------------------------------------------------------
totals = query_total(word, parties_filter, terms_filter, selected_pol_id, date_from, date_to)

if totals["count"] == 0:
    st.warning(t("no_results", lang, word=word))
    st.stop()

c1, c2, c3, c4 = st.columns(4)
c1.metric(t("metric_speeches", lang), f"{totals['count']:,}")
c2.metric(t("metric_first", lang), str(totals["min_date"]) if totals["min_date"] else " - ")
c3.metric(t("metric_latest", lang), str(totals["max_date"]) if totals["max_date"] else " - ")
c4.metric(t("metric_keyword", lang), f'"{word}"')

st.divider()

# -- Tabs --------------------------------------------------------------------
tab_timeline, tab_party, tab_politicians = st.tabs([
    t("tab_timeline", lang), t("tab_party", lang), t("tab_politicians", lang)
])

# ── Timeline ────────────────────────────────────────────────────────────────
with tab_timeline:
    df_time = query_timeline(
        word, parties_filter, terms_filter, selected_pol_id, granularity, count_mode, date_from, date_to
    )

    if df_time.empty:
        st.info(t("no_data", lang))
    else:
        raw_parties = df_time["party"].unique().tolist()
        color_map = full_color_map(raw_parties)
        df_time = expand_party_names(df_time)
        count_label = t(count_mode, lang)

        fig = px.line(
            df_time,
            x="period",
            y="value",
            color="party",
            color_discrete_map=color_map,
            markers=True,
            labels={
                "period": t("date", lang),
                "value": count_label,
                "party": t("party_label", lang),
            },
            title=t("title_timeline", lang, word=word, mode=count_label),
        )
        fig.update_layout(
            hovermode="x unified",
            legend_title_text=t("party_label", lang),
            xaxis_title="",
            yaxis_title=count_label,
            plot_bgcolor="white",
            paper_bgcolor="white",
            font_color="#000000",
        )
        fig.update_traces(line_width=2.5)
        st.plotly_chart(fig, width="stretch")

        # Stacked area toggle
        if st.checkbox(t("stacked_area", lang), value=False):
            fig2 = px.area(
                df_time,
                x="period",
                y="value",
                color="party",
                color_discrete_map=color_map,
                labels={"period": t("date", lang), "value": count_label, "party": t("party_label", lang)},
                title=t("title_stacked_area", lang, word=word),
            )
            fig2.update_layout(
                hovermode="x unified",
                plot_bgcolor="white",
                paper_bgcolor="white",
                font_color="#000000",
            )
            st.plotly_chart(fig2, width="stretch")

# ── By party ────────────────────────────────────────────────────────────────
with tab_party:
    df_party = query_by_party(word, parties_filter, terms_filter, selected_pol_id, date_from, date_to)

    if df_party.empty:
        st.info(t("no_data", lang))
    else:
        color_map = full_color_map(df_party["party"].tolist())
        pie_labels = df_party["party"].tolist()  # abbreviations for pie slices
        df_party = expand_party_names(df_party)
        speeches_label = t("speeches", lang)

        col_bar, col_pie = st.columns(2)

        with col_bar:
            fig_bar = px.bar(
                df_party,
                x="speeches",
                y="party",
                orientation="h",
                color="party",
                color_discrete_map=color_map,
                labels={"speeches": speeches_label, "party": ""},
                title=t("title_by_party", lang, word=word),
            )
            fig_bar.update_layout(
                showlegend=False,
                plot_bgcolor="white",
                paper_bgcolor="white",
                font_color="#000000",
                yaxis_categoryorder="total ascending",
            )
            st.plotly_chart(fig_bar, width="stretch")

        with col_pie:
            fig_pie = px.pie(
                df_party,
                names="party",
                values="speeches",
                color="party",
                color_discrete_map=color_map,
                title=t("title_share", lang, word=word),
            )
            fig_pie.update_traces(textposition="inside", textinfo="percent+text",
                                  text=pie_labels)
            fig_pie.update_layout(showlegend=False, paper_bgcolor="white", font_color="#000000")
            st.plotly_chart(fig_pie, width="stretch")

        # Timeline stacked bar
        st.subheader(t("stacked_over_time", lang))
        df_time2 = query_timeline(
            word, parties_filter, terms_filter, selected_pol_id, granularity, "speeches", date_from, date_to
        )
        if not df_time2.empty:
            cmap = full_color_map(df_time2["party"].unique().tolist())
            df_time2 = expand_party_names(df_time2)
            gran_label = t("gran_monthly" if granularity == "Monthly" else "gran_quarterly", lang)
            fig_stack = px.bar(
                df_time2,
                x="period",
                y="value",
                color="party",
                color_discrete_map=cmap,
                labels={"period": t("date", lang), "value": speeches_label, "party": t("party_label", lang)},
                title=t("title_stacked_bar", lang, word=word, gran=gran_label),
            )
            fig_stack.update_layout(
                barmode="stack",
                hovermode="x unified",
                plot_bgcolor="white",
                paper_bgcolor="white",
                font_color="#000000",
                xaxis_title="",
            )
            st.plotly_chart(fig_stack, width="stretch")

# ── Top politicians ──────────────────────────────────────────────────────────
with tab_politicians:
    top_n = st.slider(t("top_n_slider", lang), min_value=5, max_value=30, value=15)
    df_pol = query_top_politicians(word, parties_filter, terms_filter, top_n, date_from, date_to)

    if df_pol.empty:
        st.info(t("no_data", lang))
    else:
        color_map = full_color_map(df_pol["party"].tolist())
        df_pol = expand_party_names(df_pol)

        fig_pol = px.bar(
            df_pol,
            x="speeches",
            y="politician",
            color="party",
            orientation="h",
            color_discrete_map=color_map,
            labels={"speeches": t("speeches", lang), "politician": ""},
            title=t("title_top", lang, word=word),
        )
        fig_pol.update_layout(
            plot_bgcolor="white",
            paper_bgcolor="white",
            font_color="#000000",
            yaxis_categoryorder="total ascending",
            legend_title_text=t("party_label", lang),
        )
        st.plotly_chart(fig_pol, width="stretch")

# ---------------------------------------------------------------------------
# Footer  -  data source & licence
# ---------------------------------------------------------------------------

st.divider()
st.markdown(t("footer", lang), unsafe_allow_html=False)

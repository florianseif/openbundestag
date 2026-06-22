"""Shared query layer for OpenBundestag.

Pure, framework-agnostic data access used by BOTH the Streamlit app (`app.py`)
and the FastAPI service (`api/main.py`). Nothing here imports Streamlit — the
caller is responsible for caching (Streamlit's `@st.cache_data`, the API's
`TTLCache`, etc.).

The functions take an open DuckDB connection so the connection lifecycle and
caching strategy stay with the caller. Use `open_connection()` to obtain one
with the same DB-resolution + pre-warm behaviour the app has always used.

All user-controlled values are passed as bound query parameters — never
string-interpolated — to prevent SQL injection. Column names are module
constants, never user input.
"""

from __future__ import annotations

import os

import duckdb
import pandas as pd

# ---------------------------------------------------------------------------
# Materialised columns (built once by the pipeline, src/load.finalize_db)
# ---------------------------------------------------------------------------
FACTION_COL = "faction_normalized"   # resolved party per speech
SEARCH_COL = "search_text"           # lower(speech_content), pre-lowered for LIKE

# Keyword length cap (mirrors the Streamlit text_input max_chars).
KEYWORD_MAX_LEN = 80

# ---------------------------------------------------------------------------
# Reference data (party metadata + electoral terms) — single source of truth
# ---------------------------------------------------------------------------
PARTY_COLORS: dict[str, str] = {
    "CDU/CSU":                "#000000",
    "SPD":                    "#E3000F",
    "AfD":                    "#009EE0",
    "Bündnis 90/Die Grünen":  "#1AA037",
    "FDP":                    "#FFED00",
    "Die Linke":              "#BE3075",
    "BSW":                    "#9B2335",
    "SSW":                    "#003082",
    "Fraktionslos":           "#888888",
    "Unknown":                "#CCCCCC",
}

PARTY_FULL_NAMES: dict[str, str] = {
    "CDU/CSU":                "CDU/CSU – Christlich Demokratische/Soziale Union",
    "SPD":                    "SPD – Sozialdemokratische Partei Deutschlands",
    "AfD":                    "AfD – Alternative für Deutschland",
    "Bündnis 90/Die Grünen":  "Bündnis 90/Die Grünen",
    "FDP":                    "FDP – Freie Demokratische Partei",
    "Die Linke":              "Die Linke",
    "BSW":                    "BSW – Bündnis Sahra Wagenknecht",
    "SSW":                    "SSW – Südschleswigscher Wählerverband",
    "PDS":                    "PDS – Partei des Demokratischen Sozialismus",
    "KPD":                    "KPD – Kommunistische Partei Deutschlands",
    "DP":                     "DP – Deutsche Partei",
    "GB/BHE":                 "GB/BHE – Gesamtdeutscher Block/BHE",
    "BP":                     "BP – Bayernpartei",
    "WAV":                    "WAV – Wirtschaftliche Aufbau-Vereinigung",
    "DRP":                    "DRP – Deutsche Reichspartei",
    "FVP":                    "FVP – Freie Volkspartei",
    "Z":                      "Z – Zentrum",
    "Fraktionslos":           "Fraktionslos",
    "Unknown":                "Unknown",
}

# Canonical set of real parliamentary factions. `faction_normalized` can also
# hold a Bundesland name (e.g. "Bremen") for Bundesrat speakers addressing the
# house — those are NOT parties and must never surface as a row/column in
# the interruption heatmap. Any party-vs-party view whitelists this set.
KNOWN_PARTIES: frozenset[str] = frozenset(PARTY_FULL_NAMES) - {"Unknown"}
# SQL IN-list literal: 'CDU/CSU', 'SPD', ...  (single-quotes doubled to escape)
KNOWN_PARTIES_SQL = ", ".join(
    f"'{p.replace(chr(39), chr(39) * 2)}'" for p in KNOWN_PARTIES
)

# Canonical party order by parliamentary founding / first Bundestag entry date.
# Fraktionslos always sorts last. Unknown is excluded from public lists.
PARTY_FOUNDING_ORDER: list[str] = [
    "SPD",                   # 1863 / 1875
    "Z",                     # 1870
    "KPD",                   # 1918
    "CDU/CSU",               # 1945
    "DP",                    # 1945
    "WAV",                   # 1945
    "BP",                    # 1946
    "SSW",                   # 1948
    "FDP",                   # 1948
    "DRP",                   # 1950
    "GB/BHE",                # 1950
    "FVP",                   # 1956
    "Bündnis 90/Die Grünen", # 1980 / merged 1993
    "PDS",                   # 1989
    "Die Linke",             # 2007
    "AfD",                   # 2013
    "BSW",                   # 2024
    "Fraktionslos",          # last
]
_PARTY_RANK: dict[str, int] = {p: i for i, p in enumerate(PARTY_FOUNDING_ORDER)}


def _party_sort_key(name: str) -> int:
    return _PARTY_RANK.get(name, len(PARTY_FOUNDING_ORDER))


# Parties that no longer hold seats — hidden by default in the UI.
HISTORICAL_PARTIES: set[str] = {
    "KPD", "DP", "GB/BHE", "BP", "WAV", "DRP", "FVP", "FU", "DA", "DBP",
    "NR", "Z", "PDS", "Gast",
}

TERM_LABELS: dict[int, str] = {
    1:  "1st  (1949–1953)",
    2:  "2nd  (1953–1957)",
    3:  "3rd  (1957–1961)",
    4:  "4th  (1961–1965)",
    5:  "5th  (1965–1969)",
    6:  "6th  (1969–1972)",
    7:  "7th  (1972–1976)",
    8:  "8th  (1976–1980)",
    9:  "9th  (1980–1983)",
    10: "10th (1983–1987)",
    11: "11th (1987–1990)",
    12: "12th (1990–1994)",
    13: "13th (1994–1998)",
    14: "14th (1998–2002)",
    15: "15th (2002–2005)",
    16: "16th (2005–2009)",
    17: "17th (2009–2013)",
    18: "18th (2013–2017)",
    19: "19th (2017–2021)",
    20: "20th (2021–2025)",
    21: "21st (2025–)",
}


# ---------------------------------------------------------------------------
# Connection / DB resolution
# ---------------------------------------------------------------------------
def resolve_db_path(db_path: str | None = None) -> str:
    """Return a path to the DuckDB file, downloading it once if it's absent.

    Locally the file already exists, so this is a no-op. On a fresh HF Space the
    2 GB DB lives in a separate public Dataset repo (``HF_DB_REPO``) and is
    pulled into the container's cache on first run.
    """
    db_path = db_path or os.environ.get("DB_PATH", "openbundestag-data.db")
    if os.path.exists(db_path):
        return db_path
    repo = os.environ.get("HF_DB_REPO")
    if not repo:
        raise RuntimeError(
            f"Database '{db_path}' not found and HF_DB_REPO is unset. "
            "Either build it (uv run run.py) or set HF_DB_REPO to a dataset repo."
        )
    from huggingface_hub import hf_hub_download

    filename = os.environ.get("HF_DB_FILE", "openbundestag-data.db")
    return hf_hub_download(repo_id=repo, filename=filename, repo_type="dataset")


def open_connection(
    db_path: str | None = None,
    *,
    read_only: bool = True,
    prewarm: bool = True,
) -> duckdb.DuckDBPyConnection:
    """Open a DuckDB connection, verifying the finalize-phase columns exist.

    When ``prewarm`` is set, a single full pass over ``search_text`` pulls the
    ~2 GB file into the OS page cache at startup, so the first real search hits
    ~100 ms warm instead of ~500 ms cold.
    """
    con = duckdb.connect(resolve_db_path(db_path), read_only=read_only)
    cols = _columns(con)
    missing = {FACTION_COL, SEARCH_COL} - cols
    if missing:
        raise RuntimeError(
            f"Database is missing derived column(s) {sorted(missing)}. "
            "Run the finalize step:  uv run run.py --phase finalize"
        )
    if prewarm:
        con.execute(f"SELECT SUM(LENGTH({SEARCH_COL})) FROM speeches").fetchone()
    return con


def _columns(con: duckdb.DuckDBPyConnection) -> set[str]:
    # PRAGMA table_info columns: (cid, name, type, notnull, dflt_value, pk) — name is r[1]
    return {r[1] for r in con.execute("PRAGMA table_info('speeches')").fetchall()}


def has_raw_text(con: duckdb.DuckDBPyConnection) -> bool:
    """True when the ``speeches`` table still carries inline ``speech_content``
    (i.e. a full, non-finalized build)."""
    return "speech_content" in _columns(con)


def has_text_table(con: duckdb.DuckDBPyConnection) -> bool:
    """True when a ``speech_texts`` side table is present (a ``--text-table``
    finalize build keeps the original-cased full text there while the main
    ``speeches`` table stays lean)."""
    return bool(
        con.execute(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_name = 'speech_texts'"
        ).fetchone()
    )


def _has_registry(con: duckdb.DuckDBPyConnection) -> bool:
    """True when the MdB registry view ``_registry_names`` is present (built by
    the stammdaten phase).  Lets top_politicians resolve canonical names while
    staying compatible with older DBs that predate the registry."""
    return bool(
        con.execute(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_name = '_registry_names'"
        ).fetchone()
    )


def _text_source(con: duckdb.DuckDBPyConnection) -> tuple[str, str]:
    """Resolve where the drill-down reads passage text from.

    Returns ``(text_expr, join_clause)`` for a query whose ``speeches`` table
    is aliased ``s``. Prefers inline ``speech_content``; falls back to the
    ``speech_texts`` side table (``--text-table`` build); returns a NULL
    expression when neither is present (e.g. a legacy slim DB) so callers
    get a NULL snippet rather than a 500.
    """
    if has_raw_text(con):
        return "s.speech_content", ""
    if has_text_table(con):
        return "txt.speech_content", "LEFT JOIN speech_texts txt ON txt.id = s.id"
    return "CAST(NULL AS VARCHAR)", ""


# ---------------------------------------------------------------------------
# WHERE-clause builder
# ---------------------------------------------------------------------------
def build_conditions(
    word: str,
    parties: list[str] | None,
    terms: list[int] | None,
    politician_id: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    extra: list[str] | None = None,
) -> tuple[str, list]:
    """Build a parameterized WHERE clause and its bound values."""
    conditions = [f"{SEARCH_COL} LIKE ?"]
    params: list[object] = [f"%{word.lower()}%"]

    if extra:
        conditions.extend(extra)
    if parties:
        placeholders = ", ".join("?" for _ in parties)
        conditions.append(f"{FACTION_COL} IN ({placeholders})")
        params.extend(parties)
    if terms:
        placeholders = ", ".join("?" for _ in terms)
        conditions.append(f"electoral_term IN ({placeholders})")
        params.extend(int(t) for t in terms)
    if politician_id is not None:
        conditions.append("politician_id = ?")
        params.append(int(politician_id))
    if date_from:
        conditions.append("date >= ?")
        params.append(date_from)
    if date_to:
        conditions.append("date <= ?")
        params.append(date_to)

    return " AND ".join(conditions), params


# ---------------------------------------------------------------------------
# Reference queries
# ---------------------------------------------------------------------------
def date_range(con: duckdb.DuckDBPyConnection) -> tuple | None:
    return con.execute(
        "SELECT MIN(date), MAX(date) FROM speeches WHERE date IS NOT NULL"
    ).fetchone()


def parties(con: duckdb.DuckDBPyConnection) -> list[str]:
    df = con.execute(
        f"SELECT DISTINCT {FACTION_COL} AS party FROM speeches"
    ).fetchdf()
    result = [p for p in df["party"].tolist() if p and p != "Unknown"]
    return sorted(result, key=_party_sort_key)


def politicians(
    con: duckdb.DuckDBPyConnection, q: str = "", limit: int = 50
) -> pd.DataFrame:
    """Typeahead over known politicians (for the explorer's MP filter)."""
    where = "politician_id != -1 AND last_name != ''"
    params: list = []
    if q:
        where += " AND lower(first_name || ' ' || last_name) LIKE ?"
        params.append(f"%{q.lower()}%")
    params.append(int(limit))
    sql = f"""
        SELECT
            politician_id                              AS id,
            first_name || ' ' || last_name             AS name,
            any_value({FACTION_COL})                   AS party,
            COUNT(*)                                   AS speeches
        FROM speeches
        WHERE {where}
        GROUP BY politician_id, name
        ORDER BY speeches DESC
        LIMIT ?
    """
    return con.execute(sql, params).fetchdf()


# ---------------------------------------------------------------------------
# Aggregate queries (the three explorer views + summary)
# ---------------------------------------------------------------------------
def timeline(
    con: duckdb.DuckDBPyConnection,
    word: str,
    parties: list[str],
    terms: list[int],
    politician_id: int | None,
    granularity: str,
    count_mode: str,
    date_from: str | None = None,
    date_to: str | None = None,
) -> pd.DataFrame:
    trunc = "month" if granularity == "Monthly" else "quarter"

    if count_mode == "speeches":
        count_expr = "COUNT(*)"
        count_params: list = []
    else:
        word_lower = word.lower()
        count_expr = f"SUM(len({SEARCH_COL}) - len(replace({SEARCH_COL}, ?, ''))) / ?"
        count_params = [word_lower, max(len(word_lower), 1)]

    where, where_params = build_conditions(
        word, parties, terms, politician_id, date_from, date_to,
        extra=[f"{FACTION_COL} != 'Unknown'"],
    )
    sql = f"""
        SELECT
            date_trunc('{trunc}', date)::DATE          AS period,
            {FACTION_COL}                              AS party,
            {count_expr}                               AS value
        FROM speeches
        WHERE {where}
        GROUP BY period, party
        ORDER BY period, party
    """
    # count_expr appears in the SELECT (before WHERE), so its params come first.
    return con.execute(sql, count_params + where_params).fetchdf()


def by_party(
    con: duckdb.DuckDBPyConnection,
    word: str,
    parties: list[str],
    terms: list[int],
    politician_id: int | None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> pd.DataFrame:
    where, params = build_conditions(
        word, parties, terms, politician_id, date_from, date_to,
        extra=[f"{FACTION_COL} != 'Unknown'"],
    )
    sql = f"""
        SELECT
            {FACTION_COL} AS party,
            COUNT(*)      AS speeches
        FROM speeches
        WHERE {where}
        GROUP BY party
        ORDER BY speeches DESC
    """
    return con.execute(sql, params).fetchdf()


def top_politicians(
    con: duckdb.DuckDBPyConnection,
    word: str,
    parties: list[str],
    terms: list[int],
    top_n: int = 15,
    date_from: str | None = None,
    date_to: str | None = None,
) -> pd.DataFrame:
    where, params = build_conditions(
        word, parties, terms, None, date_from, date_to,
        extra=["politician_id != -1", "last_name != ''", f"{FACTION_COL} != 'Unknown'"],
    )
    params.append(int(top_n))
    # When the MdB registry is present (built by the stammdaten phase), resolve
    # the display name from it via politician_id.  This gives clean, canonical
    # names for legacy speakers (whose parsed first/last fields are noisy, e.g.
    # "Frau Renger") and collapses name variants of the same person onto one row.
    # Falls back to the speech's own name fields when the id is not in the
    # registry (placeholder ids) or the registry table does not exist.
    if _has_registry(con):
        name_expr = "COALESCE(reg.name, s.first_name || ' ' || s.last_name)"
        join = "LEFT JOIN _registry_names reg ON reg.id = s.politician_id"
    else:
        name_expr = "s.first_name || ' ' || s.last_name"
        join = ""
    sql = f"""
        SELECT
            s.politician_id AS politician_id,
            {name_expr}     AS politician,
            {FACTION_COL}   AS party,
            COUNT(*)        AS speeches
        FROM speeches s
        {join}
        WHERE {where}
        GROUP BY s.politician_id, politician, party
        ORDER BY speeches DESC
        LIMIT ?
    """
    return con.execute(sql, params).fetchdf()


def by_term(
    con: duckdb.DuckDBPyConnection,
    word: str,
    parties: list[str],
    terms: list[int],
    politician_id: int | None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> pd.DataFrame:
    where, params = build_conditions(
        word, parties, terms, politician_id, date_from, date_to,
        extra=[f"{FACTION_COL} != 'Unknown'"],
    )
    sql = f"""
        SELECT
            electoral_term AS term,
            COUNT(*)       AS speeches
        FROM speeches
        WHERE {where}
        GROUP BY electoral_term
        ORDER BY electoral_term
    """
    return con.execute(sql, params).fetchdf()


def total(
    con: duckdb.DuckDBPyConnection,
    word: str,
    parties: list[str],
    terms: list[int],
    politician_id: int | None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict:
    where, params = build_conditions(
        word, parties, terms, politician_id, date_from, date_to,
        extra=[f"{FACTION_COL} != 'Unknown'"],
    )
    row = con.execute(
        f"SELECT COUNT(*), MIN(date), MAX(date) FROM speeches WHERE {where}",
        params,
    ).fetchone()
    if row is None:
        return {"count": 0, "min_date": None, "max_date": None}
    return {"count": row[0], "min_date": row[1], "max_date": row[2]}


# ---------------------------------------------------------------------------
# Combined search — one scan, all explorer views
# ---------------------------------------------------------------------------
def search(
    con: duckdb.DuckDBPyConnection,
    word: str,
    parties: list[str],
    terms: list[int],
    politician_id: int | None,
    granularity: str,
    count_mode: str,
    top_n: int = 15,
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict:
    """Compute total + timeline + by-party + by-term + top-politicians in a
    SINGLE text scan, instead of the four independent ``LIKE`` scans the
    explorer used to fire in parallel.

    The keyword filter (the only expensive part — a substring scan over the
    ~1.8 GB ``search_text`` column) runs once and lands in a per-cursor TEMP
    table; every view then aggregates that small matched set in microseconds.

    ``politician_id`` mirrors the explorer's behaviour: it narrows *total* and
    *timeline* only (the MP's own activity), while *by_party* and
    *top_politicians* always reflect the whole keyword (the matched set keeps
    ``politician_id`` so both derive from the one scan). Results are identical
    to calling :func:`total`, :func:`timeline`, :func:`by_party`,
    :func:`by_term` and :func:`top_politicians` separately.
    """
    where, where_params = build_conditions(
        word, parties, terms, None, date_from, date_to,
        extra=[f"{FACTION_COL} != 'Unknown'"],
    )

    occurrences = count_mode == "occurrences"
    lo = word.lower()
    if occurrences:
        occ_select = f", (len({SEARCH_COL}) - len(replace({SEARCH_COL}, ?, ''))) / ? AS occ"
        matched_params: list = [lo, max(len(lo), 1)] + where_params
    else:
        occ_select = ""
        matched_params = where_params

    con.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE _search_matched AS
        SELECT id, {FACTION_COL} AS party, date, electoral_term AS term,
               politician_id, first_name, last_name{occ_select}
        FROM speeches
        WHERE {where}
        """,
        matched_params,
    )

    # total + timeline honour the optional MP filter; the others never do.
    pid_where, pid_params = "", []
    if politician_id is not None:
        pid_where, pid_params = " WHERE politician_id = ?", [int(politician_id)]

    total_row = con.execute(
        f"SELECT COUNT(*), MIN(date), MAX(date) FROM _search_matched{pid_where}",
        pid_params,
    ).fetchone()
    total = (
        {"count": total_row[0], "min_date": total_row[1], "max_date": total_row[2]}
        if total_row else {"count": 0, "min_date": None, "max_date": None}
    )

    trunc = "month" if granularity == "Monthly" else "quarter"
    value_expr = "SUM(occ)" if occurrences else "COUNT(*)"
    timeline = con.execute(
        f"""
        SELECT date_trunc('{trunc}', date)::DATE AS period, party, {value_expr} AS value
        FROM _search_matched{pid_where}
        GROUP BY period, party
        ORDER BY period, party
        """,
        pid_params,
    ).fetchdf()

    by_party = con.execute(
        """
        SELECT party, COUNT(*) AS speeches
        FROM _search_matched
        GROUP BY party
        ORDER BY speeches DESC, party
        """
    ).fetchdf()

    by_term = con.execute(
        """
        SELECT term AS term, COUNT(*) AS speeches
        FROM _search_matched
        GROUP BY term
        ORDER BY term
        """
    ).fetchdf()

    if _has_registry(con):
        name_expr = "COALESCE(reg.name, m.first_name || ' ' || m.last_name)"
        join = "LEFT JOIN _registry_names reg ON reg.id = m.politician_id"
    else:
        name_expr = "m.first_name || ' ' || m.last_name"
        join = ""
    top_politicians = con.execute(
        f"""
        SELECT m.politician_id AS politician_id, {name_expr} AS politician, m.party AS party, COUNT(*) AS speeches
        FROM _search_matched m
        {join}
        WHERE m.politician_id != -1 AND m.last_name != ''
        GROUP BY m.politician_id, politician, party
        ORDER BY speeches DESC, politician
        LIMIT ?
        """,
        [int(top_n)],
    ).fetchdf()

    return {
        "total": total,
        "timeline": timeline,
        "by_party": by_party,
        "by_term": by_term,
        "top_politicians": top_politicians,
    }


# ---------------------------------------------------------------------------
# Drill-down (matched speech segments + full speech)
# ---------------------------------------------------------------------------
def speeches(
    con: duckdb.DuckDBPyConnection,
    word: str,
    parties: list[str],
    terms: list[int],
    politician_id: int | None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> pd.DataFrame:
    """Matched speech segments for the drill-down list.

    Always returns a text ``snippet`` around the first match, cut from whichever
    passage source ``_text_source`` resolves to (original casing when available).
    """
    where, where_params = build_conditions(
        word, parties, terms, politician_id, date_from, date_to,
        extra=[f"{FACTION_COL} != 'Unknown'"],
    )
    text_expr, join_clause = _text_source(con)
    # Window of ~320 chars centred on the first (case-insensitive) match.
    snippet_select = (
        f", substr({text_expr}, "
        "greatest(position(? IN s.search_text) - 120, 1), 320) AS snippet"
    )
    params: list[object] = [word.lower()]  # snippet param is first in SELECT
    params.extend(where_params)
    params.extend([int(limit), int(offset)])
    sql = f"""
        SELECT
            s.id, s.session, s.electoral_term, s.date,
            s.politician_id,
            s.first_name || ' ' || s.last_name AS politician,
            s.{FACTION_COL}                    AS party,
            s.position_short, s.position_long{snippet_select}
        FROM speeches s
        {join_clause}
        WHERE {where}
        ORDER BY s.date DESC, s.id DESC
        LIMIT ? OFFSET ?
    """
    return con.execute(sql, params).fetchdf()


def speech_by_id(con: duckdb.DuckDBPyConnection, speech_id: int) -> dict | None:
    """Full speech row for the reader/download."""
    text_expr, join_clause = _text_source(con)
    row = con.execute(
        f"""
        SELECT
            s.id, s.session, s.electoral_term, s.date, s.politician_id,
            s.first_name, s.last_name, s.{FACTION_COL} AS party,
            s.position_short, s.position_long,
            {text_expr} AS speech_content
        FROM speeches s
        {join_clause}
        WHERE s.id = ?
        """,
        [int(speech_id)],
    ).fetchone()
    if row is None:
        return None
    keys = [
        "id", "session", "electoral_term", "date", "politician_id",
        "first_name", "last_name", "party", "position_short", "position_long",
        "speech_content",
    ]
    return dict(zip(keys, row))


# ---------------------------------------------------------------------------
# Zwischenrufe queries
# ---------------------------------------------------------------------------

def zwischenrufe_table_exists(con: duckdb.DuckDBPyConnection) -> bool:
    """Return True if the zwischenrufe table is present and populated."""
    row = con.execute(
        "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'zwischenrufe'"
    ).fetchone()
    return bool(row and row[0])


def query_zwischenrufe_timeline(
    con: duckdb.DuckDBPyConnection,
    type_filter: str | None = None,
    party_filter: str | None = None,
    terms: list[int] | None = None,
) -> pd.DataFrame:
    """Zwischenrufe count by year, optionally filtered by type/caller party/term.

    Returns: date (year as DATE), type, n
    """
    conditions = ["date IS NOT NULL"]
    params: list = []
    if type_filter:
        conditions.append("type = ?")
        params.append(type_filter)
    if party_filter:
        conditions.append("caller_party = ?")
        params.append(party_filter)
    if terms:
        conditions.append(f"electoral_term IN ({','.join('?' * len(terms))})")
        params.extend(terms)

    where = " AND ".join(conditions)
    return con.execute(
        f"""
        SELECT
            date_trunc('year', date::DATE)::DATE AS year,
            type,
            COUNT(*) AS n
        FROM zwischenrufe
        WHERE {where}
        GROUP BY 1, 2
        ORDER BY 1, 2
        """,
        params,
    ).fetchdf()


def query_top_zwischenrufer(
    con: duckdb.DuckDBPyConnection,
    type_filter: str = "Zwischenruf",
    terms: list[int] | None = None,
    party_filter: str | None = None,
    limit: int = 20,
) -> pd.DataFrame:
    """Politicians ranked by number of attributed interjections.

    Returns: caller_name, caller_party, n
    """
    conditions = ["caller_name IS NOT NULL", "type = ?"]
    params: list = [type_filter]
    if terms:
        conditions.append(f"electoral_term IN ({','.join('?' * len(terms))})")
        params.extend(terms)
    if party_filter:
        conditions.append("caller_party = ?")
        params.append(party_filter)
    params.append(limit)

    where = " AND ".join(conditions)
    return con.execute(
        f"""
        SELECT caller_name, caller_party, COUNT(*) AS n
        FROM zwischenrufe
        WHERE {where}
        GROUP BY caller_name, caller_party
        ORDER BY n DESC
        LIMIT ?
        """,
        params,
    ).fetchdf()


def query_zwischenrufe_by_caller_party(
    con: duckdb.DuckDBPyConnection,
    type_filter: str = "Zwischenruf",
    terms: list[int] | None = None,
) -> pd.DataFrame:
    """Total interjections grouped by caller party.

    Returns: caller_party, n
    """
    conditions = ["caller_party IS NOT NULL", "type = ?"]
    params: list = [type_filter]
    if terms:
        conditions.append(f"electoral_term IN ({','.join('?' * len(terms))})")
        params.extend(terms)

    where = " AND ".join(conditions)
    return con.execute(
        f"""
        SELECT caller_party, COUNT(*) AS n
        FROM zwischenrufe
        WHERE {where}
        GROUP BY caller_party
        ORDER BY n DESC
        """,
        params,
    ).fetchdf()


def query_interruption_matrix(
    con: duckdb.DuckDBPyConnection,
    type_filter: str = "Zwischenruf",
    terms: list[int] | None = None,
) -> pd.DataFrame:
    """Cross-party interruption matrix: who heckles whom.

    Returns: caller_party, target_speaker_party, n
    """
    # Restrict BOTH axes to real parliamentary factions. `faction_normalized`
    # also carries Bundesland names (e.g. "Bremen") for Bundesrat speakers and
    # the unattributable '', 'Unknown' sentinels — a whitelist guarantees none
    # of those can ever leak into the heatmap as a bogus row/column.
    conditions = [
        f"caller_party IN ({KNOWN_PARTIES_SQL})",
        f"target_speaker_party IN ({KNOWN_PARTIES_SQL})",
        "type = ?",
    ]
    params: list = [type_filter]
    if terms:
        conditions.append(f"electoral_term IN ({','.join('?' * len(terms))})")
        params.extend(terms)

    where = " AND ".join(conditions)
    return con.execute(
        f"""
        SELECT caller_party, target_speaker_party, COUNT(*) AS n
        FROM zwischenrufe
        WHERE {where}
        GROUP BY caller_party, target_speaker_party
        ORDER BY n DESC
        """,
        params,
    ).fetchdf()


def query_zwischenrufe_samples(
    con: duckdb.DuckDBPyConnection,
    keyword: str | None = None,
    caller_party: str | None = None,
    caller_name: str | None = None,
    target_party: str | None = None,
    terms: list[int] | None = None,
    limit: int = 50,
) -> pd.DataFrame:
    """Retrieve individual Zwischenruf rows for browsing.

    Returns: id, date, caller_name, caller_party, target_speaker_party, text, raw
    """
    conditions = ["type = 'Zwischenruf'", "text IS NOT NULL"]
    params: list = []
    if keyword and len(keyword) <= KEYWORD_MAX_LEN:
        conditions.append("lower(text) LIKE ?")
        params.append(f"%{keyword.lower()}%")
    if caller_party:
        conditions.append("caller_party = ?")
        params.append(caller_party)
    if caller_name:
        conditions.append("lower(caller_name) LIKE ?")
        params.append(f"%{caller_name.lower()}%")
    if target_party:
        conditions.append("target_speaker_party = ?")
        params.append(target_party)
    if terms:
        conditions.append(f"electoral_term IN ({','.join('?' * len(terms))})")
        params.extend(terms)
    params.append(limit)

    where = " AND ".join(conditions)
    return con.execute(
        f"""
        SELECT id, date, electoral_term, caller_name, caller_party,
               target_speaker_party, text, raw
        FROM zwischenrufe
        WHERE {where}
        ORDER BY date DESC
        LIMIT ?
        """,
        params,
    ).fetchdf()


def query_beifall_self_vs_other(
    con: duckdb.DuckDBPyConnection,
    terms: list[int] | None = None,
) -> pd.DataFrame:
    """Per-party breakdown of self-applause vs. applause for others.

    Returns: caller_party, is_self (bool), n
    """
    conditions = [
        f"caller_party IN ({KNOWN_PARTIES_SQL})",
        f"target_speaker_party IN ({KNOWN_PARTIES_SQL})",
        "type = 'Beifall'",
    ]
    params: list = []
    if terms:
        conditions.append(f"electoral_term IN ({','.join('?' * len(terms))})")
        params.extend(terms)

    where = " AND ".join(conditions)
    return con.execute(
        f"""
        SELECT
            caller_party,
            (caller_party = target_speaker_party) AS is_self,
            COUNT(*) AS n
        FROM zwischenrufe
        WHERE {where}
        GROUP BY caller_party, is_self
        ORDER BY caller_party, is_self
        """,
        params,
    ).fetchdf()

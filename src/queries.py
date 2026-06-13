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
    db_path = db_path or os.environ.get("DB_PATH", "open_discourse.db")
    if os.path.exists(db_path):
        return db_path
    repo = os.environ.get("HF_DB_REPO")
    if not repo:
        raise RuntimeError(
            f"Database '{db_path}' not found and HF_DB_REPO is unset. "
            "Either build it (uv run run.py) or set HF_DB_REPO to a dataset repo."
        )
    from huggingface_hub import hf_hub_download

    filename = os.environ.get("HF_DB_FILE", "open_discourse.db")
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
    """True when the DB still carries raw ``speech_content`` (not --slim).

    The drill-down endpoints can only return paragraph text when this is true.
    """
    return "speech_content" in _columns(con)


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
        f"SELECT DISTINCT {FACTION_COL} AS party FROM speeches ORDER BY 1"
    ).fetchdf()
    return [p for p in df["party"].tolist() if p and p != "Unknown"]


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
        word, parties, terms, politician_id, date_from, date_to
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
        word, parties, terms, politician_id, date_from, date_to
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
        extra=["politician_id != -1", "last_name != ''"],
    )
    params.append(int(top_n))
    sql = f"""
        SELECT
            first_name || ' ' || last_name AS politician,
            {FACTION_COL}                  AS party,
            COUNT(*)                       AS speeches
        FROM speeches
        WHERE {where}
        GROUP BY politician, party
        ORDER BY speeches DESC
        LIMIT ?
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
        word, parties, terms, politician_id, date_from, date_to
    )
    row = con.execute(
        f"SELECT COUNT(*), MIN(date), MAX(date) FROM speeches WHERE {where}",
        params,
    ).fetchone()
    if row is None:
        return {"count": 0, "min_date": None, "max_date": None}
    return {"count": row[0], "min_date": row[1], "max_date": row[2]}


# ---------------------------------------------------------------------------
# Drill-down (matched speech segments + full speech) — needs raw speech_content
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

    Returns metadata always; includes a text ``snippet`` around the first match
    only when the DB still carries raw ``speech_content``.
    """
    where, where_params = build_conditions(
        word, parties, terms, politician_id, date_from, date_to
    )
    snippet_select = ""
    params: list[object] = []
    if has_raw_text(con):
        # Window of ~320 chars centred on the first (case-insensitive) match.
        snippet_select = (
            ", substr(speech_content, "
            "greatest(position(? IN search_text) - 120, 1), 320) AS snippet"
        )
        params.append(word.lower())  # snippet param is first in SELECT
    params.extend(where_params)
    params.extend([int(limit), int(offset)])
    sql = f"""
        SELECT
            id, session, electoral_term, date,
            politician_id,
            first_name || ' ' || last_name AS politician,
            {FACTION_COL}                  AS party,
            position_short, position_long{snippet_select}
        FROM speeches
        WHERE {where}
        ORDER BY date DESC, id DESC
        LIMIT ? OFFSET ?
    """
    return con.execute(sql, params).fetchdf()


def speech_by_id(con: duckdb.DuckDBPyConnection, speech_id: int) -> dict | None:
    """Full speech row (incl. raw text when present) for the reader/download."""
    has_text = has_raw_text(con)
    text_col = ", speech_content" if has_text else ""
    row = con.execute(
        f"""
        SELECT
            id, session, electoral_term, date, politician_id,
            first_name, last_name, {FACTION_COL} AS party,
            position_short, position_long{text_col}
        FROM speeches WHERE id = ?
        """,
        [int(speech_id)],
    ).fetchone()
    if row is None:
        return None
    keys = [
        "id", "session", "electoral_term", "date", "politician_id",
        "first_name", "last_name", "party", "position_short", "position_long",
    ]
    if has_text:
        keys.append("speech_content")
    return dict(zip(keys, row))

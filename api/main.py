"""OpenBundestag JSON API.

A thin FastAPI layer over the shared query engine in ``src/queries.py`` — the
same SQL the Streamlit app uses. Serves aggregate views (timeline, by-party,
top-politicians, totals) plus reference data for the SvelteKit frontend, and
stubs the drill-down endpoints (matched speech segments + full speech) that the
frontend will flesh out later.

Run locally:
    uvicorn api.main:app --reload --port 8000

Deployment (HF Space, Docker): the 2 GB DuckDB file is pulled once from the
public HF Dataset configured via HF_DB_REPO / HF_DB_FILE (see src/queries.py).
"""

from __future__ import annotations

import datetime as dt
import os
from contextlib import asynccontextmanager
from functools import lru_cache
from typing import Any

import duckdb
import pandas as pd
from cachetools import TTLCache
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from src import queries as q

# Memoise identical query responses for an hour (mirrors the Streamlit app's
# @st.cache_data ttl=3600). Results are small JSON-able structures.
_cache: TTLCache = TTLCache(maxsize=1024, ttl=3600)


def _cached(key: tuple, build):
    if key not in _cache:
        _cache[key] = build()
    return _cache[key]

# Single read-only connection, opened (and pre-warmed) once at startup.
_con: duckdb.DuckDBPyConnection | None = None


def con() -> duckdb.DuckDBPyConnection:
    if _con is None:  # pragma: no cover - startup guarantees this
        raise HTTPException(503, "Database connection not ready")
    # FastAPI runs sync endpoints in a threadpool, so requests can hit the DB
    # concurrently. A single DuckDB connection is NOT safe for concurrent
    # execute(); .cursor() hands out an independent connection that shares the
    # same database + buffer pool (so the pre-warmed page cache still applies).
    return _con.cursor()


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _con
    # Pre-warm pulls the ~2 GB file into the OS page cache so the first real
    # search is ~100 ms warm rather than cold.
    _con = q.open_connection(prewarm=True)
    yield
    if _con is not None:
        _con.close()


app = FastAPI(title="OpenBundestag API", version="0.1.0", lifespan=lifespan)

# CORS: comma-separated origins in ALLOWED_ORIGINS, or "*" for local dev.
_origins = os.environ.get("ALLOWED_ORIGINS", "*")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if _origins == "*" else [o.strip() for o in _origins.split(",")],
    allow_methods=["GET"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _jsonable(value: Any) -> Any:
    """Make DuckDB/pandas scalars JSON-serialisable (dates → ISO strings)."""
    if value is None:
        return None
    if isinstance(value, (dt.date, dt.datetime, pd.Timestamp)):
        return value.isoformat()[:10]
    if isinstance(value, float) and pd.isna(value):
        return None
    if hasattr(value, "item"):  # numpy / pandas scalar → native Python
        return value.item()
    return value


def _records(df: pd.DataFrame) -> list[dict]:
    return [{k: _jsonable(v) for k, v in row.items()} for row in df.to_dict("records")]


def _clean_word(word: str) -> str:
    word = (word or "").strip()
    if not word:
        raise HTTPException(400, "Query parameter 'word' is required.")
    if len(word) > q.KEYWORD_MAX_LEN:
        raise HTTPException(400, f"'word' must be ≤ {q.KEYWORD_MAX_LEN} characters.")
    return word


# Reference data changes only when the DB is rebuilt → cache for the process.
@lru_cache(maxsize=1)
def _meta() -> dict:
    c = con()
    rng = q.date_range(c) or (None, None)
    return {
        "min_date": _jsonable(rng[0]),
        "max_date": _jsonable(rng[1]),
        "parties": q.parties(c),
        "party_colors": q.PARTY_COLORS,
        "party_full_names": q.PARTY_FULL_NAMES,
        "historical_parties": sorted(q.HISTORICAL_PARTIES),
        "terms": [{"term": k, "label": v} for k, v in q.TERM_LABELS.items()],
        "keyword_max_len": q.KEYWORD_MAX_LEN,
        "has_text": q.has_raw_text(c) or q.has_text_table(c),
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.get("/health")
def health() -> dict:
    if _con is not None:
        c = _con.cursor()
        has_text = q.has_raw_text(c) or q.has_text_table(c)
    else:
        has_text = False
    return {
        "status": "ok" if _con is not None else "starting",
        "has_text": has_text,
    }


@app.get("/api/meta")
def meta() -> dict:
    return _meta()


@app.get("/api/politicians")
def politicians(q_: str = Query("", alias="q"), limit: int = Query(50, ge=1, le=200)) -> list[dict]:
    return _records(q.politicians(con(), q_, limit))


@app.get("/api/timeline")
def timeline(
    word: str,
    parties: list[str] = Query(default=[]),
    terms: list[int] = Query(default=[]),
    politician_id: int | None = None,
    granularity: str = Query("Monthly"),
    count_mode: str = Query("speeches"),
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[dict]:
    word = _clean_word(word)
    gran = "Monthly" if granularity.lower().startswith("month") else "Quarterly"
    mode = "occurrences" if count_mode.lower().startswith("occ") else "speeches"
    key = ("timeline", word, tuple(parties), tuple(terms), politician_id, gran, mode, date_from, date_to)
    return _cached(key, lambda: _records(
        q.timeline(con(), word, parties, terms, politician_id, gran, mode, date_from, date_to)
    ))


@app.get("/api/search")
def search(
    word: str,
    parties: list[str] = Query(default=[]),
    terms: list[int] = Query(default=[]),
    politician_id: int | None = None,
    granularity: str = Query("Monthly"),
    count_mode: str = Query("speeches"),
    top_n: int = Query(15, ge=1, le=50),
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict:
    """Combined explorer payload (total + timeline + by-party + by-term +
    top-politicians) computed in a single text scan. Replaces the four parallel
    requests the explorer used to fire per keystroke."""
    word = _clean_word(word)
    gran = "Monthly" if granularity.lower().startswith("month") else "Quarterly"
    mode = "occurrences" if count_mode.lower().startswith("occ") else "speeches"
    key = ("search", word, tuple(parties), tuple(terms), politician_id, gran, mode, top_n, date_from, date_to)

    def build() -> dict:
        res = q.search(con(), word, parties, terms, politician_id, gran, mode, top_n, date_from, date_to)
        return {
            "total": {k: _jsonable(v) for k, v in res["total"].items()},
            "timeline": _records(res["timeline"]),
            "by_party": _records(res["by_party"]),
            "by_term": _records(res["by_term"]),
            "top_politicians": _records(res["top_politicians"]),
        }

    return _cached(key, build)


@app.get("/api/by-party")
def by_party(
    word: str,
    parties: list[str] = Query(default=[]),
    terms: list[int] = Query(default=[]),
    politician_id: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[dict]:
    word = _clean_word(word)
    key = ("by_party", word, tuple(parties), tuple(terms), politician_id, date_from, date_to)
    return _cached(key, lambda: _records(
        q.by_party(con(), word, parties, terms, politician_id, date_from, date_to)
    ))


@app.get("/api/top-politicians")
def top_politicians(
    word: str,
    parties: list[str] = Query(default=[]),
    terms: list[int] = Query(default=[]),
    top_n: int = Query(15, ge=1, le=50),
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[dict]:
    word = _clean_word(word)
    key = ("top_pol", word, tuple(parties), tuple(terms), top_n, date_from, date_to)
    return _cached(key, lambda: _records(
        q.top_politicians(con(), word, parties, terms, top_n, date_from, date_to)
    ))


@app.get("/api/by-term")
def by_term(
    word: str,
    parties: list[str] = Query(default=[]),
    terms: list[int] = Query(default=[]),
    politician_id: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[dict]:
    word = _clean_word(word)
    key = ("by_term", word, tuple(parties), tuple(terms), politician_id, date_from, date_to)
    return _cached(key, lambda: _records(
        q.by_term(con(), word, parties, terms, politician_id, date_from, date_to)
    ))


@app.get("/api/total")
def total(
    word: str,
    parties: list[str] = Query(default=[]),
    terms: list[int] = Query(default=[]),
    politician_id: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict:
    word = _clean_word(word)
    key = ("total", word, tuple(parties), tuple(terms), politician_id, date_from, date_to)
    return _cached(key, lambda: {
        k: _jsonable(v)
        for k, v in q.total(con(), word, parties, terms, politician_id, date_from, date_to).items()
    })


# --- Drill-down (UI lands later; snippet text only when DB keeps raw text) ----
@app.get("/api/speeches")
def speeches(
    word: str,
    parties: list[str] = Query(default=[]),
    terms: list[int] = Query(default=[]),
    politician_id: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> dict:
    word = _clean_word(word)
    df = q.speeches(con(), word, parties, terms, politician_id, date_from, date_to, limit, offset)
    return {
        "items": _records(df),
        "limit": limit,
        "offset": offset,
        "has_snippet": "snippet" in df.columns,
    }


@app.get("/api/speech/{speech_id}")
def speech(speech_id: int) -> dict:
    row = q.speech_by_id(con(), speech_id)
    if row is None:
        raise HTTPException(404, f"Speech {speech_id} not found.")
    return {k: _jsonable(v) for k, v in row.items()}


# ---------------------------------------------------------------------------
# Zwischenrufe endpoints
# ---------------------------------------------------------------------------

@app.get("/api/zwischenrufe/meta")
def zwischenrufe_meta() -> dict:
    c = con()
    if not q.zwischenrufe_table_exists(c):
        return {"available": False, "total": 0}
    row = c.execute("SELECT COUNT(*) FROM zwischenrufe").fetchone()
    total = int(row[0]) if row else 0  # type: ignore[index]
    return {"available": total > 0, "total": total}


@app.get("/api/zwischenrufe/timeline")
def zwischenrufe_timeline(
    type_filter: str | None = None,
    party_filter: str | None = None,
    terms: list[int] = Query(default=[]),
) -> list[dict]:
    c = con()
    if not q.zwischenrufe_table_exists(c):
        return []
    key = ("zw_timeline", type_filter, party_filter, tuple(terms))
    return _cached(key, lambda: _records(
        q.query_zwischenrufe_timeline(c, type_filter, party_filter, terms)
    ))


@app.get("/api/zwischenrufe/top-callers")
def zwischenrufe_top_callers(
    type_filter: str = "Zwischenruf",
    terms: list[int] = Query(default=[]),
    party_filter: str | None = None,
    limit: int = Query(20, ge=1, le=50),
) -> list[dict]:
    c = con()
    if not q.zwischenrufe_table_exists(c):
        return []
    key = ("zw_top", type_filter, tuple(terms), party_filter, limit)
    return _cached(key, lambda: _records(
        q.query_top_zwischenrufer(c, type_filter, terms, party_filter, limit)
    ))


@app.get("/api/zwischenrufe/by-party")
def zwischenrufe_by_party(
    type_filter: str = "Zwischenruf",
    terms: list[int] = Query(default=[]),
) -> list[dict]:
    c = con()
    if not q.zwischenrufe_table_exists(c):
        return []
    key = ("zw_by_party", type_filter, tuple(terms))
    return _cached(key, lambda: _records(
        q.query_zwischenrufe_by_caller_party(c, type_filter, terms)
    ))


@app.get("/api/zwischenrufe/matrix")
def zwischenrufe_matrix(
    type_filter: str = "Zwischenruf",
    terms: list[int] = Query(default=[]),
) -> list[dict]:
    c = con()
    if not q.zwischenrufe_table_exists(c):
        return []
    key = ("zw_matrix", type_filter, tuple(terms))
    return _cached(key, lambda: _records(
        q.query_interruption_matrix(c, type_filter, terms)
    ))


@app.get("/api/zwischenrufe/samples")
def zwischenrufe_samples(
    keyword: str | None = None,
    caller_party: str | None = None,
    caller_name: str | None = None,
    target_party: str | None = None,
    terms: list[int] = Query(default=[]),
    limit: int = Query(50, ge=1, le=200),
) -> list[dict]:
    c = con()
    if not q.zwischenrufe_table_exists(c):
        return []
    if keyword and len(keyword) > q.KEYWORD_MAX_LEN:
        raise HTTPException(400, f"keyword must be ≤ {q.KEYWORD_MAX_LEN} characters.")
    return _records(q.query_zwischenrufe_samples(
        c, keyword, caller_party, caller_name, target_party, terms, limit
    ))


# ---------------------------------------------------------------------------
# Beifall endpoints (reuse zwischenrufe table, type='Beifall')
# ---------------------------------------------------------------------------

@app.get("/api/beifall/meta")
def beifall_meta() -> dict:
    c = con()
    if not q.zwischenrufe_table_exists(c):
        return {"available": False, "total": 0}
    row = c.execute("SELECT COUNT(*) FROM zwischenrufe WHERE type = 'Beifall'").fetchone()
    total = int(row[0]) if row else 0  # type: ignore[index]
    return {"available": total > 0, "total": total}


@app.get("/api/beifall/by-party")
def beifall_by_party(terms: list[int] = Query(default=[])) -> list[dict]:
    c = con()
    if not q.zwischenrufe_table_exists(c):
        return []
    key = ("bf_by_party", tuple(terms))
    return _cached(key, lambda: _records(
        q.query_zwischenrufe_by_caller_party(c, "Beifall", terms)
    ))


@app.get("/api/beifall/matrix")
def beifall_matrix(terms: list[int] = Query(default=[])) -> list[dict]:
    c = con()
    if not q.zwischenrufe_table_exists(c):
        return []
    key = ("bf_matrix", tuple(terms))
    return _cached(key, lambda: _records(
        q.query_interruption_matrix(c, "Beifall", terms)
    ))


@app.get("/api/beifall/self-vs-other")
def beifall_self_vs_other(terms: list[int] = Query(default=[])) -> list[dict]:
    c = con()
    if not q.zwischenrufe_table_exists(c):
        return []
    key = ("bf_self_vs_other", tuple(terms))
    return _cached(key, lambda: _records(
        q.query_beifall_self_vs_other(c, terms)
    ))

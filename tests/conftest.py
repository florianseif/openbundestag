"""Shared fixtures, strategies and constants for the test suite.

The suite is deliberately DB-free where it can be: the text functions in
``src.transform`` are pure, and the faction-normalisation SQL in ``src.load``
is exercised against tiny **in-memory** DuckDB instances built per test. Nothing
here touches the 6 GB production database.
"""

from __future__ import annotations

from collections.abc import Iterator

import duckdb
import pytest
from hypothesis import strategies as st

from src.transform import FACTION_PATTERNS, _FACTION_DIRECT

# Every value _match_faction can legally return (besides None): the canonical
# names from the direct-lookup table plus the abbreviations used as pattern keys.
ALLOWED_FACTIONS: frozenset[str] = frozenset(_FACTION_DIRECT.values()) | frozenset(
    FACTION_PATTERNS.keys()
)

# The closed set of position_short labels _classify_position emits.
POSITION_SHORTS: frozenset[str] = frozenset(
    {
        "Member of Parliament",
        "Presidium of Parliament",
        "Guest",
        "Chancellor",
        "Minister",
        "Secretary of State",
        "Not found",
    }
)

# Keys every parsed speech record must carry, for both XML schemas.
SPEECH_KEYS: frozenset[str] = frozenset(
    {
        "session",
        "electoral_term",
        "date",
        "politician_id",
        "first_name",
        "last_name",
        "faction",
        "position_short",
        "position_long",
        "speech_content",
        "filename",
    }
)

# ---------------------------------------------------------------------------
# Hypothesis text strategies
# ---------------------------------------------------------------------------

# Anything goes: full unicode incl. control chars, surrogates excluded so the
# value is a valid Python str. Used to fuzz the pure text functions.
WEIRD_TEXT = st.text(
    alphabet=st.characters(blacklist_categories=("Cs",)),
    max_size=120,
)

# XML-safe weird text: still wildly unicode, but no control chars / surrogates,
# so it round-trips through a real XML document without corrupting it.
XML_SAFE_TEXT = st.text(
    alphabet=st.characters(min_codepoint=0x20, max_codepoint=0xD7FF, blacklist_categories=("Cs",)),
    max_size=160,
)

# Text safe to store in a DuckDB VARCHAR (no NUL byte) — surrogate-free.
DB_SAFE_TEXT = st.text(
    alphabet=st.characters(min_codepoint=0x01, blacklist_categories=("Cs",)),
    max_size=80,
)


# ---------------------------------------------------------------------------
# In-memory DuckDB builders (faction normalisation + name backfill)
# ---------------------------------------------------------------------------

def new_faction_db() -> duckdb.DuckDBPyConnection:
    """A fresh in-memory DB with the empty tables FACTION_NORMALIZE_SQL reads."""
    con = duckdb.connect(":memory:")
    con.execute(
        """
        CREATE TABLE speeches (
            id                 BIGINT,
            electoral_term     INTEGER,
            date               DATE,
            politician_id      BIGINT,
            first_name         VARCHAR,
            last_name          VARCHAR,
            faction            VARCHAR,
            faction_normalized VARCHAR
        );
        CREATE TABLE ministers (
            full_name  VARCHAR,
            first_name VARCHAR,
            last_name  VARCHAR,
            party      VARCHAR
        );
        CREATE TABLE politician_terms (
            id             BIGINT,
            electoral_term INTEGER,
            faction        VARCHAR
        );
        """
    )
    return con


def new_backfill_db() -> duckdb.DuckDBPyConnection:
    """A fresh in-memory DB with the two tables _backfill_missing_names touches."""
    con = duckdb.connect(":memory:")
    con.execute(
        """
        CREATE TABLE speeches (
            id            BIGINT,
            politician_id BIGINT,
            first_name    VARCHAR,
            last_name     VARCHAR
        );
        CREATE TABLE speakers (
            id         BIGINT,
            first_name VARCHAR,
            last_name  VARCHAR
        );
        """
    )
    return con


@pytest.fixture
def faction_db() -> Iterator[duckdb.DuckDBPyConnection]:
    con = new_faction_db()
    yield con
    con.close()


@pytest.fixture
def backfill_db() -> Iterator[duckdb.DuckDBPyConnection]:
    con = new_backfill_db()
    yield con
    con.close()

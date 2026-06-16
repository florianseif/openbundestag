"""Tests for the faction-resolution SQL in src.load.

This is the heart of the data-quality fix. FACTION_NORMALIZE_SQL turns the raw
``faction`` field on every speech into a clean party label, falling back through
ministers → the speaker's own declared faction → a name lookup → the official
MdB-Stammdaten registry, and only then to 'Unknown'. The tests are run against
tiny in-memory DuckDB instances, mirroring exactly what finalize_db() does.

Regressions these lock down:
  * empty minister party must not become an empty-string faction (Lemke bug);
  * a registry-known speaker whose speeches never carry a faction must be
    resolved, not left 'Unknown' (the ~13k term-12 chairs);
  * a speaker's own era-correct label (PDS) must win over the registry's
    modern label (Die Linke);
  * faction_normalized is NEVER NULL and NEVER ''.
"""

from __future__ import annotations

import duckdb
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from src.load import FACTION_NORMALIZE_SQL, _backfill_missing_names
from tests.conftest import DB_SAFE_TEXT, new_faction_db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalize(con: duckdb.DuckDBPyConnection) -> None:
    con.execute(f"UPDATE speeches s SET faction_normalized = ({FACTION_NORMALIZE_SQL})")


def _add_speech(con, *, id, term=20, pid=-1, first="", last="", faction=None, date=None):
    con.execute(
        "INSERT INTO speeches "
        "(id, electoral_term, date, politician_id, first_name, last_name, faction, faction_normalized) "
        "VALUES (?,?,?,?,?,?,?,NULL)",
        [id, term, date, pid, first, last, faction],
    )


def _add_minister(con, full_name, first, last, party):
    con.execute(
        "INSERT INTO ministers (full_name, first_name, last_name, party) VALUES (?,?,?,?)",
        [full_name, first, last, party],
    )


def _add_term(con, pid, term, faction):
    con.execute(
        "INSERT INTO politician_terms (id, electoral_term, faction) VALUES (?,?,?)",
        [pid, term, faction],
    )


def _value(con, id=1):
    return con.execute("SELECT faction_normalized FROM speeches WHERE id = ?", [id]).fetchone()[0]


# ---------------------------------------------------------------------------
# Clean pass-through
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "faction",
    ["SPD", "CDU/CSU", "FDP", "AfD", "PDS", "BSW", "Fraktionslos", "Bündnis 90/Die Grünen", "Die Linke"],
)
def test_known_faction_passes_through(faction_db, faction):
    _add_speech(faction_db, id=1, faction=faction)
    _normalize(faction_db)
    assert _value(faction_db) == faction


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("DIE LINKE", "Die Linke"),
        ("Die Linke", "Die Linke"),
        ("LINKE", "Die Linke"),
        ("BÜNDNIS 90/DIE GRÜNEN", "Bündnis 90/Die Grünen"),
    ],
)
def test_linke_and_gruenen_variants_normalised(faction_db, raw, expected):
    _add_speech(faction_db, id=1, faction=raw)
    _normalize(faction_db)
    assert _value(faction_db) == expected


# ---------------------------------------------------------------------------
# Missing faction → Unknown when nothing else resolves
# ---------------------------------------------------------------------------

# NB: the SQL guard is `trim(faction) = ''`, and DuckDB's trim() strips only
# spaces — so "blank" here means NULL or space-only. In practice that is all
# that can reach the DB: both XML parsers .strip() the faction text upstream,
# so tab/newline-only values normalise to None before storage (see the
# never-null/empty property below for the tab/newline robustness guarantee).
@pytest.mark.parametrize("faction", [None, "", " ", "   ", "      "])
def test_missing_faction_no_support_is_unknown(faction_db, faction):
    _add_speech(faction_db, id=1, faction=faction)
    _normalize(faction_db)
    assert _value(faction_db) == "Unknown"


# ---------------------------------------------------------------------------
# Registry fallback — the core ~13k recovery
# ---------------------------------------------------------------------------

def test_registry_resolves_chair_without_faction(faction_db):
    # Term-12 Vizepräsident pattern: a real MdB whose speeches carry no faction.
    _add_speech(faction_db, id=1, term=12, pid=12000001, last="Cronenberg", faction=None)
    _add_term(faction_db, 12000001, 12, "FDP")
    _normalize(faction_db)
    assert _value(faction_db) == "FDP"


def test_registry_is_term_specific(faction_db):
    # Registry entry for a different term must not bleed in.
    _add_speech(faction_db, id=1, term=12, pid=12000001, faction=None)
    _add_term(faction_db, 12000001, 13, "FDP")
    _normalize(faction_db)
    assert _value(faction_db) == "Unknown"


def test_registry_ignored_for_legacy_sentinel(faction_db):
    # pid = -1 means "unidentified"; the registry must not be consulted.
    _add_speech(faction_db, id=1, term=12, pid=-1, faction=None)
    _add_term(faction_db, -1, 12, "FDP")
    _normalize(faction_db)
    assert _value(faction_db) == "Unknown"


# ---------------------------------------------------------------------------
# Minister fallback + the empty-party (Lemke) regression
# ---------------------------------------------------------------------------

def test_minister_party_resolves_faction(faction_db):
    _add_speech(faction_db, id=1, term=20, pid=-1, first="Robert", last="Habeck", faction=None)
    _add_minister(faction_db, "Robert Habeck", "Robert", "Habeck", "Bündnis 90/Die Grünen")
    _normalize(faction_db)
    assert _value(faction_db) == "Bündnis 90/Die Grünen"


def test_empty_minister_party_does_not_become_empty_string(faction_db):
    # Steffi Lemke: scraped with a blank party. Must fall through to 'Unknown',
    # never produce an empty-string faction.
    _add_speech(faction_db, id=1, term=20, pid=-1, first="Steffi", last="Lemke", faction=None)
    _add_minister(faction_db, "Steffi Lemke", "Steffi", "Lemke", "")
    _normalize(faction_db)
    assert _value(faction_db) == "Unknown"
    assert _value(faction_db) != ""


def test_empty_minister_party_falls_through_to_registry(faction_db):
    _add_speech(faction_db, id=1, term=20, pid=88000001, first="Steffi", last="Lemke", faction=None)
    _add_minister(faction_db, "Steffi Lemke", "Steffi", "Lemke", "")
    _add_term(faction_db, 88000001, 20, "Bündnis 90/Die Grünen")
    _normalize(faction_db)
    assert _value(faction_db) == "Bündnis 90/Die Grünen"


# ---------------------------------------------------------------------------
# Ordering: own declared faction beats the registry (era-correct labels)
# ---------------------------------------------------------------------------

def test_own_declared_pds_beats_registry_die_linke(faction_db):
    # Speaker declared PDS in one speech; another speech of theirs has no
    # faction. The registry says "Die Linke" (post-2007 rename) — but the
    # era-correct PDS the speaker themselves declared must win.
    _add_speech(faction_db, id=1, term=14, pid=7, last="Gysi", faction="PDS", date="2002-01-01")
    _add_speech(faction_db, id=2, term=14, pid=7, last="Gysi", faction=None, date="2002-02-01")
    _add_term(faction_db, 7, 14, "Die Linke")
    _normalize(faction_db)
    assert _value(faction_db, id=2) == "PDS"


def test_name_lookup_resolves_unidentified_speaker(faction_db):
    # A pid=-1 speech with no faction is resolved by matching name against
    # another speech that does carry a faction.
    _add_speech(faction_db, id=1, term=14, pid=-1, first="Gregor", last="Gysi", faction="PDS")
    _add_speech(faction_db, id=2, term=14, pid=-1, first="Gregor", last="Gysi", faction=None)
    _normalize(faction_db)
    assert _value(faction_db, id=2) == "PDS"


# ---------------------------------------------------------------------------
# Properties — the invariant that must hold for ANY input
# ---------------------------------------------------------------------------

@settings(deadline=None, max_examples=150)
@given(
    faction=st.one_of(st.none(), DB_SAFE_TEXT),
    first=DB_SAFE_TEXT,
    last=DB_SAFE_TEXT,
    pid=st.integers(min_value=-1, max_value=99_000_000),
    term=st.integers(min_value=1, max_value=21),
)
def test_normalized_is_never_null_or_empty(faction, first, last, pid, term):
    con = new_faction_db()
    try:
        _add_speech(con, id=1, term=term, pid=pid, first=first, last=last, faction=faction)
        _normalize(con)
        result = _value(con)
        assert result is not None
        assert result != ""
    finally:
        con.close()


@settings(deadline=None, max_examples=100)
@given(faction=st.one_of(st.none(), st.text(alphabet=" ", max_size=8)))
def test_blank_faction_always_unknown_without_support(faction):
    con = new_faction_db()
    try:
        _add_speech(con, id=1, pid=-1, faction=faction)
        _normalize(con)
        assert _value(con) == "Unknown"
    finally:
        con.close()


# ---------------------------------------------------------------------------
# _backfill_missing_names
# ---------------------------------------------------------------------------

def _add_bf_speech(con, *, id, pid, first="", last=""):
    con.execute(
        "INSERT INTO speeches (id, politician_id, first_name, last_name) VALUES (?,?,?,?)",
        [id, pid, first, last],
    )


def _add_speaker(con, id, first, last):
    con.execute("INSERT INTO speakers (id, first_name, last_name) VALUES (?,?,?)", [id, first, last])


def _bf_value(con, id):
    return con.execute(
        "SELECT first_name, last_name FROM speeches WHERE id = ?", [id]
    ).fetchone()


def test_backfill_fills_blank_name_from_speakers(backfill_db):
    _add_bf_speech(backfill_db, id=1, pid=5, first="", last="")
    _add_speaker(backfill_db, 5, "Albert", "Weiler")
    _backfill_missing_names(backfill_db)
    assert _bf_value(backfill_db, 1) == ("Albert", "Weiler")


def test_backfill_leaves_legacy_sentinel_untouched(backfill_db):
    _add_bf_speech(backfill_db, id=1, pid=-1, first="", last="")
    _backfill_missing_names(backfill_db)
    assert _bf_value(backfill_db, 1) == ("", "")


def test_backfill_does_not_overwrite_existing_name(backfill_db):
    _add_bf_speech(backfill_db, id=1, pid=5, first="Foo", last="Bar")
    _add_speaker(backfill_db, 5, "Albert", "Weiler")
    _backfill_missing_names(backfill_db)
    assert _bf_value(backfill_db, 1) == ("Foo", "Bar")


def test_backfill_skips_when_speaker_also_blank(backfill_db):
    _add_bf_speech(backfill_db, id=1, pid=9, first="", last="")
    _add_speaker(backfill_db, 9, "", "")
    _backfill_missing_names(backfill_db)
    assert _bf_value(backfill_db, 1) == ("", "")


def test_backfill_is_idempotent(backfill_db):
    _add_bf_speech(backfill_db, id=1, pid=5, first="", last="")
    _add_speaker(backfill_db, 5, "Albert", "Weiler")
    _backfill_missing_names(backfill_db)
    _backfill_missing_names(backfill_db)  # second run is a no-op
    assert _bf_value(backfill_db, 1) == ("Albert", "Weiler")

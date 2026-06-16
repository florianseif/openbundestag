"""Tests for src.transform._match_faction — raw faction string → canonical party.

This is the first line of defence for data quality: it decides whether a token
in the XML is a party at all. Getting it wrong either drops a real party or, in
the legacy parser, lets a constituency name ("Bayern") leak into the faction
field. We cover the clean cases, the messy OCR-style variants, the things that
must NOT match, and then fuzz it so weird transcript text can never crash it.
"""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from src.transform import _match_faction
from tests.conftest import ALLOWED_FACTIONS, WEIRD_TEXT

# --- Clean, modern XML strings map to their canonical name -------------------
CLEAN_CASES = [
    ("SPD", "SPD"),
    ("CDU/CSU", "CDU/CSU"),
    ("FDP", "FDP"),
    ("AfD", "AfD"),
    ("PDS", "PDS"),
    ("BSW", "BSW"),
    ("SSW", "SSW"),
    ("Fraktionslos", "Fraktionslos"),
    ("fraktionslos", "Fraktionslos"),
    ("Die Linke", "Die Linke"),
    ("DIE LINKE", "Die Linke"),
    ("Bündnis 90/Die Grünen", "Bündnis 90/Die Grünen"),
    ("BÜNDNIS 90/DIE GRÜNEN", "Bündnis 90/Die Grünen"),
    ("Grüne", "Bündnis 90/Die Grünen"),
    ("GRÜNE", "Bündnis 90/Die Grünen"),
    ("Grünen", "Bündnis 90/Die Grünen"),
]


@pytest.mark.parametrize("raw,expected", CLEAN_CASES)
def test_clean_strings(raw, expected):
    assert _match_faction(raw) == expected


# --- Messy / OCR / historical variants still resolve -------------------------
MESSY_CASES = [
    ("F.D.P.", "FDP"),  # dotted historical spelling; spaced "F. D. P." is NOT matched
    ("CDU", "CDU/CSU"),
    ("CSU", "CDU/CSU"),
    ("LINKE", "Die Linke"),
    ("Linke", "Die Linke"),
    ("DIE LINKEN", "Die Linke"),
    ("KPD", "KPD"),
    ("WAV", "WAV"),
    ("BP", "BP"),
    ("Z", "Z"),
    ("parteilos", "Fraktionslos"),
]


@pytest.mark.parametrize("raw,expected", MESSY_CASES)
def test_messy_variants(raw, expected):
    assert _match_faction(raw) == expected


# --- Things that must NOT be read as a party --------------------------------
# Constituency / Bundesland names leaking into faction is exactly the legacy
# data-quality bug the matcher is supposed to prevent.
NON_PARTY = [
    "",
    "   ",
    "Bayern",
    "Hamburg",
    "Berlin",
    "Bremen",
    "Sachsen",
    "Hessen",
    "Nordrhein-Westfalen",
    "Schleswig-Holstein",
    "Bundeskanzlerin",
    "Wahlkreis 42",
]


@pytest.mark.parametrize("raw", NON_PARTY)
def test_non_party_returns_none(raw):
    assert _match_faction(raw) is None


# --- Whitespace handling -----------------------------------------------------
@pytest.mark.parametrize("raw,expected", CLEAN_CASES)
def test_surrounding_and_internal_whitespace_ignored(raw, expected):
    padded = "  \t" + raw.replace(" ", "   ") + "\n "
    assert _match_faction(padded) == expected


# --- Property: never crash, output is always in the known closed set ---------
@given(WEIRD_TEXT)
def test_never_raises_and_output_is_known(raw):
    result = _match_faction(raw)
    assert result is None or result in ALLOWED_FACTIONS


@given(WEIRD_TEXT)
def test_idempotent_within_a_call(raw):
    # Pure function: two calls agree.
    assert _match_faction(raw) == _match_faction(raw)


@given(WEIRD_TEXT)
def test_leading_trailing_whitespace_invariant(raw):
    assert _match_faction(raw) == _match_faction("\n\t  " + raw + "  \t\n")


@given(st.sampled_from(sorted(ALLOWED_FACTIONS)))
def test_canonical_names_are_stable(canonical):
    # Feeding a canonical name back in must not reclassify it as something else.
    result = _match_faction(canonical)
    assert result is not None

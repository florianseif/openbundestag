"""Tests for src.transform._classify_position — raw role string → (short, long).

The position label drives how a speaker is bucketed (MdB vs. minister vs.
presidium vs. guest). We pin the canonical roles, then fuzz to guarantee the
function always returns a well-formed 2-tuple from the closed label set.
"""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from src.transform import _classify_position
from tests.conftest import ALLOWED_FACTIONS, POSITION_SHORTS, WEIRD_TEXT

# A faction string is classified as an ordinary MdB.
FACTION_LIKE = [
    ("SPD", "Member of Parliament"),
    ("CDU/CSU", "Member of Parliament"),
    ("Bündnis 90/Die Grünen", "Member of Parliament"),
    ("Die Linke", "Member of Parliament"),
]

ROLE_CASES = [
    ("Bundestagspräsident", "Presidium of Parliament"),
    ("Vizebundestagspräsidentin", "Presidium of Parliament"),
    ("Alterspräsident", "Presidium of Parliament"),
    ("Schriftführerin", "Presidium of Parliament"),
    ("präsidentin", "Presidium of Parliament"),
    ("Bundeskanzler", "Chancellor"),
    ("Bundeskanzlerin", "Chancellor"),
    ("Bundesminister für Finanzen", "Minister"),
    ("Ministerin für Umwelt", "Minister"),
    ("Parl. Staatssekretär", "Secretary of State"),
    ("Staatssekretärin", "Secretary of State"),
    ("Bundespräsident", "Guest"),
    ("Ministerpräsident des Landes Bayern", "Guest"),
    ("Senator", "Guest"),
    # NB: bare "Gast" is a recognised faction token (historical guest deputies)
    # so it classifies as an MdB; only non-exact forms hit the Guest branch.
    ("Gastrednerin aus Frankreich", "Guest"),
    ("Berichterstatter", "Member of Parliament"),
]


@pytest.mark.parametrize("raw,short", FACTION_LIKE + ROLE_CASES)
def test_known_roles(raw, short):
    result = _classify_position(raw)
    assert result[0] == short


def test_unknown_role_is_not_found():
    short, long = _classify_position("irgendein zufälliger Text")
    assert short == "Not found"
    assert long is None


def test_returns_two_tuple_of_expected_types():
    short, long = _classify_position("Bundeskanzlerin")
    assert isinstance(short, str)
    assert long is None or isinstance(long, str)


# --- Properties --------------------------------------------------------------
@given(WEIRD_TEXT)
def test_never_raises_and_shape_is_stable(raw):
    result = _classify_position(raw)
    assert isinstance(result, tuple) and len(result) == 2
    short, long = result
    assert short in POSITION_SHORTS
    assert long is None or isinstance(long, str)


@given(st.sampled_from(sorted(ALLOWED_FACTIONS)))
def test_any_faction_is_a_member_of_parliament(faction):
    # If the role string is recognised as a party, the speaker is an MdB.
    assert _classify_position(faction)[0] == "Member of Parliament"

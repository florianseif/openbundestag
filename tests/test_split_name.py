"""Tests for src.transform._split_name — 'Firstname [particle] Lastname' split.

Used by the legacy parser to turn a detected speaker string into first/last
columns. Two things matter for data quality: nobility particles ("von", "zu")
must stay glued to the surname, and no name token may be silently dropped.
"""

from __future__ import annotations

import re

import pytest
from hypothesis import given
from hypothesis import strategies as st

from src.transform import _TITLE_STRIP, _split_name

CASES = [
    ("Angela Merkel", ("Angela", "Merkel")),
    ("Merkel", ("", "Merkel")),
    ("Hans-Christian Ströbele", ("Hans-Christian", "Ströbele")),
    ("Gregor Gysi", ("Gregor", "Gysi")),
    # Nobility particles cling to the surname.
    ("Otto von Bismarck", ("Otto", "von Bismarck")),
    ("Karl-Theodor zu Guttenberg", ("Karl-Theodor", "zu Guttenberg")),
    ("Ursula von der Leyen", ("Ursula", "von der Leyen")),
    ("Hermann Otto Solms", ("Hermann Otto", "Solms")),
    # Academic titles are stripped before splitting.
    ("Dr. Angela Merkel", ("Angela", "Merkel")),
    ("Prof. Dr. Karl Lauterbach", ("Dr. Karl", "Lauterbach")),
    ("Dr. h. c. Gerhard Schröder", ("Gerhard", "Schröder")),
]


@pytest.mark.parametrize("full,expected", CASES)
def test_known_names(full, expected):
    assert _split_name(full) == expected


@pytest.mark.parametrize("particle", ["von", "van", "de", "zu", "zur"])
def test_particle_stays_with_surname(particle):
    first, last = _split_name(f"Max {particle} Beispiel")
    assert first == "Max"
    assert last == f"{particle} Beispiel"


def test_empty_and_whitespace():
    assert _split_name("") == ("", "")
    assert _split_name("   ") == ("", "")
    assert _split_name("Dr. ") == ("", "")


# --- Properties --------------------------------------------------------------

# Name-like tokens: capitalised words, hyphens allowed, no XML/regex metachars.
_token = st.from_regex(r"[A-ZÄÖÜ][a-zäöüß]{0,12}(-[A-ZÄÖÜ][a-zäöüß]{0,12})?", fullmatch=True)
_name = st.lists(_token, min_size=1, max_size=5).map(" ".join)


@given(_name)
def test_no_token_is_dropped(full):
    first, last = _split_name(full)
    # The split partitions the (title-stripped) tokens with none lost or added.
    stripped = _TITLE_STRIP.sub("", full).strip()
    assert (first + " " + last).split() == stripped.split()


@given(_name)
def test_surname_non_empty_for_real_names(full):
    _, last = _split_name(full)
    assert last != ""


@given(st.text(max_size=60))
def test_never_raises_returns_two_strings(raw):
    first, last = _split_name(raw)
    assert isinstance(first, str) and isinstance(last, str)


@given(_name)
def test_idempotent_on_already_split_surname(full):
    # Re-splitting the produced "last" part returns it unchanged as the surname
    # when it carries a particle (no further first-name is invented).
    _, last = _split_name(full)
    if re.match(r"^(von|van|de|zu|zur)\b", last):
        assert _split_name(last) == ("", last)

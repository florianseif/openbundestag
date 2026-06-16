"""Tests for the XML parsers in src.transform (modern + legacy schemas).

The transcripts are real-world XML: malformed files, weird unicode in names and
speech bodies, missing fields. The parsers must degrade gracefully — a bad file
returns [] (never an exception), and every record they DO emit carries the full
canonical key set so the downstream loader never sees a half-built row.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from src.transform import parse_legacy_session, parse_session
from tests.conftest import SPEECH_KEYS, XML_SAFE_TEXT

_NO_FIXTURE_HEALTHCHECK = settings(
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    max_examples=60,
)


# ---------------------------------------------------------------------------
# Builders — produce a valid XML file with caller-supplied (weird) field text
# ---------------------------------------------------------------------------

def _write(root: ET.Element, path: Path) -> Path:
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)
    return path


def build_modern(
    tmp: Path,
    *,
    vorname: str = "Angela",
    nachname: str = "Merkel",
    fraktion: str = "CDU/CSU",
    content: str = "Sehr geehrte Damen und Herren.",
    redner_id: str = "11000001",
    date: str = "01.01.2020",
) -> Path:
    root = ET.Element("dbtplenarprotokoll")
    ET.SubElement(root, "rednerliste").set("sitzung-datum", date)
    sv = ET.SubElement(root, "sitzungsverlauf")
    rede = ET.SubElement(ET.SubElement(sv, "tagesordnungspunkt"), "rede")
    pr = ET.SubElement(rede, "p")
    pr.set("klasse", "redner")
    redner = ET.SubElement(pr, "redner")
    redner.set("id", redner_id)
    name = ET.SubElement(redner, "name")
    ET.SubElement(name, "vorname").text = vorname
    ET.SubElement(name, "nachname").text = nachname
    ET.SubElement(name, "fraktion").text = fraktion
    body = ET.SubElement(rede, "p")
    body.set("klasse", "J_1")
    body.text = content
    return _write(root, tmp / "session_042.xml")


def build_legacy(tmp: Path, *, text: str, datum: str = "01.01.1970", nr: str = "5/42") -> Path:
    root = ET.Element("DOKUMENT")
    ET.SubElement(root, "DATUM").text = datum
    ET.SubElement(root, "NR").text = nr
    ET.SubElement(root, "TEXT").text = text
    return _write(root, tmp / "legacy_042.xml")


def _legacy_body(speaker_line: str, content: str = "Inhalt der Rede.") -> str:
    return f"Beginn: 10.00 Uhr\n{speaker_line}\n{content}\n(Schluss: 18.00 Uhr)"


# ---------------------------------------------------------------------------
# Modern parser — concrete behaviour
# ---------------------------------------------------------------------------

def test_modern_parses_one_clean_speech(tmp_path):
    recs = parse_session(build_modern(tmp_path), 20)
    assert len(recs) == 1
    rec = recs[0]
    assert set(rec) == SPEECH_KEYS
    assert rec["politician_id"] == 11000001
    assert rec["first_name"] == "Angela"
    assert rec["last_name"] == "Merkel"
    assert rec["faction"] == "CDU/CSU"
    assert rec["date"] == "2020-01-01"
    assert "Sehr geehrte" in rec["speech_content"]


def test_modern_bad_speaker_id_becomes_sentinel(tmp_path):
    recs = parse_session(build_modern(tmp_path, redner_id="not-an-int"), 20)
    assert recs[0]["politician_id"] == -1


def test_modern_unparseable_date_is_none(tmp_path):
    recs = parse_session(build_modern(tmp_path, date="garbage"), 20)
    assert recs[0]["date"] is None


def test_modern_missing_sitzungsverlauf_returns_empty(tmp_path):
    root = ET.Element("dbtplenarprotokoll")
    ET.SubElement(root, "rednerliste").set("sitzung-datum", "01.01.2020")
    path = _write(root, tmp_path / "empty.xml")
    assert parse_session(path, 20) == []


# ---------------------------------------------------------------------------
# Legacy parser — concrete behaviour
# ---------------------------------------------------------------------------

def test_legacy_parses_member_with_faction(tmp_path):
    body = _legacy_body("Dr. Angela Merkel (CDU/CSU), Bundeskanzlerin:")
    recs = parse_legacy_session(build_legacy(tmp_path, text=body), 14)
    assert len(recs) == 1
    rec = recs[0]
    assert set(rec) == SPEECH_KEYS
    assert rec["last_name"] == "Merkel"
    assert rec["first_name"] == "Angela"
    assert rec["faction"] == "CDU/CSU"
    assert rec["politician_id"] == -1


def test_legacy_parses_presidium(tmp_path):
    body = _legacy_body("Präsident Dr. Norbert Lammert:")
    recs = parse_legacy_session(build_legacy(tmp_path, text=body), 17)
    assert recs[0]["last_name"] == "Lammert"
    assert recs[0]["position_short"] == "Presidium of Parliament"


def test_legacy_constituency_does_not_leak_into_faction(tmp_path):
    # "(Bayern)" is a constituency, not a party — must not become a faction.
    body = _legacy_body("Max Mustermann (Bayern):")
    recs = parse_legacy_session(build_legacy(tmp_path, text=body), 3)
    assert recs == [] or recs[0]["faction"] is None


def test_legacy_no_speaker_returns_empty(tmp_path):
    recs = parse_legacy_session(build_legacy(tmp_path, text="just some prose, no speakers"), 3)
    assert recs == []


# ---------------------------------------------------------------------------
# Properties — weird content never breaks structural invariants
# ---------------------------------------------------------------------------

def _assert_well_formed(recs):
    assert isinstance(recs, list)
    for rec in recs:
        assert set(rec) == SPEECH_KEYS
        assert isinstance(rec["politician_id"], int)
        assert rec["faction"] is None or isinstance(rec["faction"], str)
        assert isinstance(rec["speech_content"], str)


@given(vorname=XML_SAFE_TEXT, nachname=XML_SAFE_TEXT, fraktion=XML_SAFE_TEXT, content=XML_SAFE_TEXT)
@_NO_FIXTURE_HEALTHCHECK
def test_modern_weird_fields_stay_well_formed(tmp_path, vorname, nachname, fraktion, content):
    recs = parse_session(build_modern(tmp_path, vorname=vorname, nachname=nachname,
                                      fraktion=fraktion, content=content), 20)
    _assert_well_formed(recs)


@given(text=XML_SAFE_TEXT)
@_NO_FIXTURE_HEALTHCHECK
def test_legacy_weird_body_stays_well_formed(tmp_path, text):
    recs = parse_legacy_session(build_legacy(tmp_path, text=text), 5)
    _assert_well_formed(recs)


@given(content=XML_SAFE_TEXT)
@_NO_FIXTURE_HEALTHCHECK
def test_legacy_weird_speech_content_around_real_speaker(tmp_path, content):
    body = _legacy_body("Dr. Angela Merkel (SPD):", content=content)
    recs = parse_legacy_session(build_legacy(tmp_path, text=body), 5)
    _assert_well_formed(recs)


# ---------------------------------------------------------------------------
# Robustness — arbitrary garbage on disk must not raise
# ---------------------------------------------------------------------------

@given(blob=st.binary(max_size=400))
@_NO_FIXTURE_HEALTHCHECK
def test_modern_garbage_file_returns_list(tmp_path, blob):
    path = tmp_path / "garbage.xml"
    path.write_bytes(blob)
    assert parse_session(path, 20) == []


@given(blob=st.binary(max_size=400))
@_NO_FIXTURE_HEALTHCHECK
def test_legacy_garbage_file_returns_list(tmp_path, blob):
    path = tmp_path / "garbage.xml"
    path.write_bytes(blob)
    assert parse_legacy_session(path, 5) == []

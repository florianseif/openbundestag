"""Build a politician registry from the official MdB-Stammdaten XML.

The Bundestag publishes ``MDB_STAMMDATEN.XML`` — every member since 1949 with
their official 8-digit ID (the *same* ID the modern session XML carries in
``<redner id=...>``), full name history and the faction held in each electoral
term.  This module flattens it into two DuckDB tables that the legacy-match
phase joins against to resolve ``politician_id`` for terms 1–18:

    politicians(id, last_name, first_name, ortszusatz, adel, praefix,
                name_von, name_bis)          -- one row per NAME variant
    politician_terms(id, electoral_term, faction, faction_raw)
                                             -- one row per (member, term)

Both tables are fully rebuilt on each run (idempotent).
"""

from pathlib import Path
import xml.etree.ElementTree as ET

import duckdb
import pandas as pd

# Map the long faction names in INS_LANG to the project's normalized party
# tokens (see PARTY_FULL_NAMES in queries.py).  Matched by substring in order;
# first hit wins, so more specific patterns precede generic ones.
_FACTION_RULES: list[tuple[str, str]] = [
    ("Christlich Demokratischen Union", "CDU/CSU"),
    ("CDU/CSU", "CDU/CSU"),
    ("Sozialdemokratischen Partei", "SPD"),
    ("der SPD", "SPD"),
    ("Freien Demokratischen Partei", "FDP"),
    ("der FDP", "FDP"),
    ("Freie Volkspartei", "FVP"),
    ("BÜNDNIS 90/DIE GRÜNEN", "Bündnis 90/Die Grünen"),
    ("Bündnis 90/Die Grünen", "Bündnis 90/Die Grünen"),
    ("Die Grünen", "Bündnis 90/Die Grünen"),
    ("Alternative für Deutschland", "AfD"),
    ("DIE LINKE", "Die Linke"),
    ("Die Linke", "Die Linke"),
    ("BSW", "BSW"),
    ("Demokratischen Sozialismus", "PDS"),
    ("Kommunistischen Partei", "KPD"),
    ("Gesamtdeutscher Block", "GB/BHE"),
    ("Gemeinschaftsblock der Heimatvertriebenen", "GB/BHE"),
    ("Deutsche Partei/Freie Volkspartei", "DP"),
    ("Deutsche Partei/Deutsche Partei Bayern", "DP"),
    ("Deutsche Partei Bayern", "DP"),
    ("DP/DPB", "DP"),
    ("Deutsche Partei", "DP"),
    ("Föderalistische Union", "FU"),
    ("Bayernpartei", "BP"),
    ("Wirtschaftliche Aufbauvereinigung", "WAV"),
    ("WAV", "WAV"),
    ("Zentrums-Partei", "Z"),
    ("Demokratische Arbeitsgemeinschaft", "DA"),
    ("Deutsche Reichspartei", "DRP"),
    ("DRP", "DRP"),
    ("Kraft/Oberländer", "GB/BHE"),
    ("Fraktionslos", "Fraktionslos"),
]


def _normalize_faction(ins_lang: str) -> str:
    for needle, token in _FACTION_RULES:
        if needle in ins_lang:
            return token
    return "Unknown"


def _text(node: ET.Element | None) -> str:
    return node.text.strip() if node is not None and node.text else ""


def parse_stammdaten(xml_path: str | Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Parse MDB_STAMMDATEN.XML → (politicians, politician_terms) DataFrames."""
    root = ET.parse(xml_path).getroot()

    people: list[dict] = []
    terms: list[dict] = []

    for mdb in root.findall("MDB"):
        mid = _text(mdb.find("ID"))
        if not mid:
            continue
        pid = int(mid)

        for name in mdb.findall("./NAMEN/NAME"):
            people.append({
                "id": pid,
                "last_name": _text(name.find("NACHNAME")),
                "first_name": _text(name.find("VORNAME")),
                "ortszusatz": _text(name.find("ORTSZUSATZ")),
                "adel": _text(name.find("ADEL")),
                "praefix": _text(name.find("PRAEFIX")),
                "name_von": _text(name.find("HISTORIE_VON")),
                "name_bis": _text(name.find("HISTORIE_BIS")),
            })

        for wp in mdb.findall("./WAHLPERIODEN/WAHLPERIODE"):
            wp_num = _text(wp.find("WP"))
            if not wp_num.isdigit():
                continue
            # Faction membership for this term, if any.
            faction_raw = ""
            for ins in wp.findall("./INSTITUTIONEN/INSTITUTION"):
                if _text(ins.find("INSART_LANG")) == "Fraktion/Gruppe":
                    faction_raw = _text(ins.find("INS_LANG"))
                    break
            terms.append({
                "id": pid,
                "electoral_term": int(wp_num),
                "faction": (
                    _normalize_faction(faction_raw) if faction_raw else "Unknown"
                ),
                "faction_raw": faction_raw,
            })

    politicians = pd.DataFrame(people)
    politician_terms = pd.DataFrame(terms).drop_duplicates(
        subset=["id", "electoral_term"]
    )
    return politicians, politician_terms


def build_registry(db_path: str | Path, xml_path: str | Path) -> None:
    """(Re)build the politicians + politician_terms tables in DuckDB."""
    politicians, politician_terms = parse_stammdaten(xml_path)

    with duckdb.connect(str(db_path)) as conn:
        conn.execute("DROP TABLE IF EXISTS politicians")
        conn.execute("DROP TABLE IF EXISTS politician_terms")
        conn.execute("CREATE TABLE politicians AS SELECT * FROM politicians")
        conn.execute(
            "CREATE TABLE politician_terms AS SELECT * FROM politician_terms"
        )
        # One canonical display name per member: prefer the currently-valid name
        # variant (empty HISTORIE_BIS), newest first.  Read by top_politicians.
        conn.execute(
            """
            CREATE OR REPLACE VIEW _registry_names AS
            SELECT id, trim(first_name) || ' ' || trim(last_name) AS name
            FROM (
                SELECT id, first_name, last_name,
                       row_number() OVER (
                           PARTITION BY id
                           ORDER BY (name_bis = '') DESC, name_von DESC
                       ) AS rn
                FROM politicians
            )
            WHERE rn = 1
            """
        )
        conn.execute("CHECKPOINT")

    print(
        f"[stammdaten] {len(politicians):,} name records, "
        f"{politician_terms['id'].nunique():,} members, "
        f"{len(politician_terms):,} member-terms → {db_path}",
        flush=True,
    )

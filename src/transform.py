"""Parse Bundestag session XML files into speakers and speeches DataFrames.

Two XML schemas are supported:
  Modern  (terms 19–21) — dbtplenarprotokoll with structured <rede> elements.
  Legacy  (terms  1–18) — DOKUMENT with a raw <TEXT> field; speakers detected
                          via regex patterns on the plain-text transcript.
"""

import re
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# Faction / position classification
# ---------------------------------------------------------------------------

# Direct lookup for clean XML faction strings used in terms 19-21
_FACTION_DIRECT: dict[str, str] = {
    "Bündnis 90/Die Grünen":   "Bündnis 90/Die Grünen",
    "BÜNDNIS 90/DIE GRÜNEN":   "Bündnis 90/Die Grünen",
    "Die Linke":               "Die Linke",
    "DIE LINKE":               "Die Linke",
    "Fraktionslos":            "Fraktionslos",
    "fraktionslos":            "Fraktionslos",
    "CDU/CSU":                 "CDU/CSU",
    "SPD":                     "SPD",
    "FDP":                     "FDP",
    "AfD":                     "AfD",
    "BSW":                     "BSW",
    "SSW":                     "SSW",
    "PDS":                     "PDS",
}

FACTION_PATTERNS: dict[str, str] = {
    "AfD":                   r"^AfD$",
    "Bündnis 90/Die Grünen": r"(?:BÜNDNIS\s*(?:90)?/?(?:\s*D[1I]E)?|Bündnis\s*90/(?:\s*D[1I]E)?)?\s*[GC]R[UÜ].?\s*[ÑN]EN?(?:/Bündnis 90)?",
    "BP":                    r"^BP$",
    "CDU/CSU":               r"(?:Gast|-)?(?:\s*C\s*[DSMU]\s*S?[DU]\s*(?:\s*[/,':!.\-]?)*\s*(?:\s*C+\s*[DSs]?\s*[UÙ]?\s*)?)(?:-?Hosp\.|-Gast|1)?",
    "DA":                    r"^DA$",
    "DBP":                   r"^DBP$",
    "Die Linke":             r"(?:DIE\s+)?LINKEn?|(?:Die\s+)?Linken?",
    "DP":                    r"^DP(?:\s*[\[/]?\s*FVP\]?)?$",
    "DRP":                   r"DRP(?:-Hosp\.)?|^SRP$",
    "FDP":                   r"\s*F\.?\s*[PDO][.']?[DP]\.?",
    "Fraktionslos":          r"[Ff]raktionslos|[Pp]arteilos",
    "FU":                    r"^FU$",
    "FVP":                   r"^FVP$",
    "Gast":                  r"^Gast$",
    "GB/BHE":                r"(?:GB[/-]\s*)?BHE(?:-DG)?",
    "KPD":                   r"^KPD$",
    "NR":                    r"^NR$",
    "PDS":                   r"(?:Gruppe\s*der\s*)?\bPDS\b(?:/(?:LL|Linke Liste))?",
    "SPD":                   r"\s*'?S(?:PD|DP)(?:\.|-Gast)?",
    "SSW":                   r"^SSW$",
    "WAV":                   r"^WAV$",
    "Z":                     r"^Z$",
    "BSW":                   r"^BSW$",
}


def _match_faction(raw: str) -> str | None:
    raw = re.sub(r"\s+", " ", raw).strip()
    # Fast direct lookup first (handles clean XML strings like "Die Linke")
    if raw in _FACTION_DIRECT:
        return _FACTION_DIRECT[raw]
    for abbrev, pattern in FACTION_PATTERNS.items():
        if re.search(pattern, raw):
            return abbrev
    return None


def _classify_position(raw: str) -> tuple[str, str | None]:
    """Return (position_short, position_long) for a raw position string."""
    faction = _match_faction(raw)
    if faction or re.match(r"^[Bb]erichterstatter(in)?(\s|$|,|.)", raw):
        return "Member of Parliament", None if faction else raw

    if (
        re.match(r"^[Bb]undestagspräsident(in)?", raw)
        or re.match(r"^[Aa]lterspräsident(in)?", raw)
        or re.match(r"^[Vv]izebundestagspräsident(in)?", raw)
        or re.match(r"^[Ss]chriftführer(in)?", raw)
        or raw.lower() in {
            "präsidentin", "präsident",
            "präsident des deutschen bundestages",
            "präsidentin des deutschen bundestages",
            "vizepräsidentin", "vizepräsident",
        }
    ):
        return "Presidium of Parliament", raw

    if (
        re.match(r"^[Bb]undespräsident(in)?", raw)
        or re.match(r"^[Mm]inisterpräsident(in)?", raw)
        or re.match(r"^[Ss]taatsminister(in)?", raw)
        or re.match(r"^[Ss]enator(in)?", raw)
        or re.match(r"^[Pp]räsident(in)?", raw)
        or re.match(r"^[Gg]ast", raw)
    ):
        return "Guest", raw

    if re.match(r"^[Bb]undeskanzler(in)?", raw):
        return "Chancellor", None

    if re.match(r"^(?:Bundes)?[Mm]inister(in)?", raw):
        return "Minister", raw

    if re.match(r"^(?:[Pp]arl\s*\.\s+)?[Ss]taatssekretär(in)?", raw):
        return "Secretary of State", raw

    return "Not found", None


# ---------------------------------------------------------------------------
# Modern XML parser (terms 19–21)  — structured <rede> elements
# ---------------------------------------------------------------------------

def _text(node: ET.Element | None, default: str = "") -> str:
    return node.text.strip() if node is not None and node.text else default


def parse_session(xml_path: Path, electoral_term: int) -> list[dict]:
    """Parse one dbtplenarprotokoll XML file.  Returns a list of speech dicts."""
    try:
        root = ET.parse(xml_path).getroot()
    except ET.ParseError:
        print(f"  [transform] Skipping malformed XML: {xml_path.name}", flush=True)
        return []

    # -- Date ---------------------------------------------------------------
    rednerliste = root.find("rednerliste")
    date_str = ""
    if rednerliste is not None:
        date_str = rednerliste.get("sitzung-datum", "")
    if not date_str:
        node = root.find(".//sitzungstag")
        date_str = _text(node)
    # Also try root attribute directly (some files store it there)
    if not date_str:
        date_str = root.get("sitzung-datum", "")
    try:
        date = datetime.strptime(date_str, "%d.%m.%Y").date().isoformat()
    except ValueError:
        date = None

    session_id = re.search(r"(\d+)", xml_path.stem)
    session = session_id.group(1) if session_id else xml_path.stem

    sitzungsverlauf = root.find("sitzungsverlauf")
    if sitzungsverlauf is None:
        return []

    records: list[dict] = []

    for top in sitzungsverlauf.findall("tagesordnungspunkt"):
        for rede in top.findall("rede"):
            politician_id: int = -1
            first_name = ""
            last_name = ""
            faction_raw = ""
            position_raw = ""

            speaker_elem = rede.find(".//redner")
            if speaker_elem is not None:
                try:
                    # Some WP21 entries have two space-separated IDs (e.g. MdB who
                    # is also a minister).  Take the first token.
                    raw_id = speaker_elem.get("id", "").strip().split()[0]
                    politician_id = int(raw_id)
                except (ValueError, TypeError, IndexError):
                    politician_id = -1

                name_node = speaker_elem.find("name")
                if name_node is not None:
                    first_name = re.sub(r"\s+", " ", _text(name_node.find("vorname")))
                    last_name  = re.sub(r"\s+", " ", _text(name_node.find("nachname")))
                    fraktion = name_node.find("fraktion")
                    rolle = name_node.find("rolle")
                    if fraktion is not None and fraktion.text:
                        faction_raw = fraktion.text.strip()
                    elif rolle is not None:
                        position_raw = _text(rolle.find("rolle_lang"))

            faction = _match_faction(faction_raw) or faction_raw or None
            pos_short, pos_long = _classify_position(
                faction if faction else position_raw
            )

            parts: list[str] = []
            for child in rede:
                if child.tag == "p" and child.get("klasse") != "redner":
                    if child.text:
                        parts.append(child.text.strip())
                    for sub in child:
                        if sub.tail:
                            parts.append(sub.tail.strip())

            speech_content = "\n\n".join(p for p in parts if p)

            records.append({
                "session":        session,
                "electoral_term": electoral_term,
                "date":           date,
                "politician_id":  politician_id,
                "first_name":     first_name,
                "last_name":      last_name,
                "faction":        faction,
                "position_short": pos_short,
                "position_long":  pos_long,
                "speech_content": speech_content,
                "filename":       xml_path.name,
            })

    return records


# ---------------------------------------------------------------------------
# Legacy XML parser (terms 1–18) — raw <TEXT> with embedded speaker markers
# ---------------------------------------------------------------------------

# Matches the start of the actual debate (after table of contents)
_LEGACY_BEGIN = re.compile(
    r"Beginn\s*:?\s*\d{1,2}\s*[.,]\s*\d{2}\s*Uhr", re.IGNORECASE
)
_LEGACY_END = re.compile(
    r"\(\s*Schluss?\s*:?\s*\d{1,2}\s*[.,]\s*\d{2}\s*Uhr", re.IGNORECASE
)

# Speaker block — detects the three common patterns at the start of a line:
#   A) "Präsident Dr. Norbert Lammert:"
#   B) "Dr. Angela Merkel (CDU/CSU), Bundeskanzlerin:"
#   C) "Angela Merkel, Bundeskanzlerin:"  (minister without faction)
_TITLE   = r"(?:(?:Dr|Prof)\.(?:\s*h\s*\.\s*c\.?)?\s+)?"
_NAME    = r"[A-ZÄÖÜ][^\n:(\[]{1,60}?"
_FACTION = r"[^)\n]{2,60}"
_ROLE    = r"[^\n:]{2,120}"

LEGACY_SPEAKER_RE = re.compile(
    r"^(?:"
    # A — presidium/chancellor prefix before name
    r"(?P<posA>(?:Alters|Vize)?[Pp]räsident(?:in)?|[Bb]undeskanzler(?:in)?|[Ss]chriftführer(?:in)?)"
    r"\s+(?P<nameA>" + _TITLE + _NAME + r")"
    r"|"
    # B — name (faction) [, role]
    r"(?P<nameB>" + _TITLE + _NAME + r")\s*"
    r"\((?P<factionB>" + _FACTION + r")\)"
    r"(?:\s*,\s*(?P<roleB>" + _ROLE + r"))?"
    r"|"
    # C — name, minister-role  (no faction marker)
    r"(?P<nameC>" + _TITLE + _NAME + r"),\s*"
    r"(?P<roleC>(?:Bundes|Staats)?[Mm]inister(?:in)?[^\n:]{0,120})"
    r")"
    r"\s*:\s?",  # colon mid-line; speech follows on same line
    re.MULTILINE,
)

_TITLE_STRIP = re.compile(r"^(?:Dr|Prof)\.(?:\s*h\s*\.\s*c\.?)?\s+", re.IGNORECASE)


def _split_name(full: str) -> tuple[str, str]:
    """Split 'Firstname [von] Lastname' into (first, last)."""
    full = _TITLE_STRIP.sub("", full).strip()
    parts = full.split()
    if not parts:
        return "", ""
    if len(parts) == 1:
        return "", parts[0]
    # keep nobility particle with last name
    for i, p in enumerate(parts[:-1]):
        if p.lower() in {"von", "van", "de", "zu", "zur"}:
            return " ".join(parts[:i]), " ".join(parts[i:])
    return " ".join(parts[:-1]), parts[-1]


def parse_legacy_session(xml_path: Path, electoral_term: int) -> list[dict]:
    """Parse one legacy DOKUMENT XML file (terms 1–18)."""
    try:
        root = ET.parse(xml_path).getroot()
    except ET.ParseError:
        print(f"  [transform] Skipping malformed XML: {xml_path.name}", flush=True)
        return []

    date_str = root.findtext("DATUM") or ""
    try:
        date = datetime.strptime(date_str.strip(), "%d.%m.%Y").date().isoformat()
    except ValueError:
        date = None

    nr = root.findtext("NR") or xml_path.stem
    # "18/232" → "18232"  or fall back to filename stem
    session = nr.replace("/", "").zfill(5) if "/" in nr else xml_path.stem

    text = root.findtext("TEXT") or ""

    # Trim table of contents: start after "Beginn X Uhr"
    begin_m = _LEGACY_BEGIN.search(text)
    text = text[begin_m.end():] if begin_m else text

    # Trim appendix: stop at "(Schluss X Uhr)"
    end_m = _LEGACY_END.search(text)
    text = text[: end_m.start()] if end_m else text

    # Find all speaker transitions
    matches = list(LEGACY_SPEAKER_RE.finditer(text))
    if not matches:
        return []

    records: list[dict] = []
    for i, m in enumerate(matches):
        # Extract speaker fields from whichever variant matched
        if m.group("posA"):
            position_raw = m.group("posA").strip()
            raw_name = m.group("nameA").strip()
            faction_raw = ""
        elif m.group("nameB"):
            position_raw = (m.group("roleB") or "").strip()
            raw_name = m.group("nameB").strip()
            faction_raw = (m.group("factionB") or "").strip()
        else:
            position_raw = (m.group("roleC") or "").strip()
            raw_name = m.group("nameC").strip()
            faction_raw = ""

        first_name, last_name = _split_name(raw_name)
        # Only keep faction if it matches a known party — parenthetical content
        # in legacy transcripts is often a constituency name (e.g. "Bayern",
        # "Hamburg"), not a party, and must not leak into the faction field.
        faction = _match_faction(faction_raw) or None

        classify_input = faction if faction else (position_raw or "")
        pos_short, pos_long = _classify_position(classify_input)

        # Speech text: everything between this match end and next match start
        content_start = m.end()
        content_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        speech_content = text[content_start:content_end].strip()
        # Normalise excessive whitespace / hyphenation artifacts
        speech_content = re.sub(r"-\n+", "", speech_content)
        speech_content = re.sub(r"\n{3,}", "\n\n", speech_content)

        records.append({
            "session":        session,
            "electoral_term": electoral_term,
            "date":           date,
            "politician_id":  -1,   # legacy XML has no stable IDs
            "first_name":     first_name,
            "last_name":      last_name,
            "faction":        faction,
            "position_short": pos_short,
            "position_long":  pos_long,
            "speech_content": speech_content,
            "filename":       xml_path.name,
        })

    return records


# ---------------------------------------------------------------------------
# Format detection
# ---------------------------------------------------------------------------

def _is_modern(xml_path: Path) -> bool:
    """Peek at the root tag to decide which parser to use."""
    try:
        for _, elem in ET.iterparse(xml_path, events=("start",)):
            return elem.tag == "dbtplenarprotokoll"
    except ET.ParseError:
        pass
    return False


# ---------------------------------------------------------------------------
# Term-level orchestration
# ---------------------------------------------------------------------------

def transform_term(
    term_dir: str | Path,
    electoral_term: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Process all session XMLs in *term_dir*.

    Automatically detects modern (terms 19–21) vs legacy (terms 1–18) format.

    Returns:
        speakers  — unique politicians derived from speech metadata
        speeches  — one row per speech segment
    """
    term_dir = Path(term_dir)
    xml_files = sorted(term_dir.glob("*.xml"))

    if not xml_files:
        raise FileNotFoundError(
            f"No XML files found in {term_dir}. Run the extract phase first."
        )

    modern = _is_modern(xml_files[0])
    parser = parse_session if modern else parse_legacy_session
    fmt = "modern" if modern else "legacy"
    print(
        f"[transform] {len(xml_files)} sessions for term {electoral_term} ({fmt})…",
        flush=True,
    )

    all_records: list[dict] = []
    for xml_path in xml_files:
        all_records.extend(parser(xml_path, electoral_term))

    speeches_df = pd.DataFrame(all_records)
    if speeches_df.empty:
        print(f"[transform] No speeches extracted for term {electoral_term}", flush=True)
        return pd.DataFrame(columns=["id", "first_name", "last_name", "faction"]), speeches_df

    speeches_df.insert(0, "id", range(len(speeches_df)))

    known = speeches_df[speeches_df["politician_id"] != -1]
    speakers_df = (
        known[["politician_id", "first_name", "last_name", "faction"]]
        .drop_duplicates(subset=["politician_id"])
        .rename(columns={"politician_id": "id"})
        .reset_index(drop=True)
    )

    print(
        f"[transform] {len(speeches_df)} speeches, {len(speakers_df)} unique speakers",
        flush=True,
    )
    return speakers_df, speeches_df

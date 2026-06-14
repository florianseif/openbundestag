"""Extract Zwischenrufe (interjections) from Bundestag session XML and speech text.

Modern terms (19+): <kommentar> elements are direct children of <rede> in the XML.
Legacy terms (1–18): interjections are embedded as parenthetical remarks in speech_content.
"""

import re
import xml.etree.ElementTree as ET
from pathlib import Path

import duckdb
import pandas as pd

from src.transform import _match_faction

# ── reaction type constants ────────────────────────────────────────────────────
TYPE_ZWISCHENRUF = "Zwischenruf"   # attributed text interjection by a named politician
TYPE_BEIFALL     = "Beifall"       # applause
TYPE_HEITERKEIT  = "Heiterkeit"    # amusement / laughter
TYPE_LACHEN      = "Lachen"        # laughter
TYPE_WIDERSPRUCH = "Widerspruch"   # dissent
TYPE_ZURUF       = "Zuruf"         # call / shout (group or unattributed individual)
TYPE_ZUSTIMMUNG  = "Zustimmung"    # agreement / approval

# ── segment parsing ────────────────────────────────────────────────────────────
# Segments within one <kommentar> are separated by an en dash (–) or em dash (—)
_SEP = re.compile(r'\s*[–—]\s*')

# "Name [Party]: free text" — individual attributed Zwischenruf
# Handles optional academic title prefix (Dr., Prof.)
_INDIVIDUAL_RE = re.compile(
    r'^(?P<name>(?:(?:Dr|Prof)\.(?:\s*h\s*\.\s*c\.?)?\s+)?[A-ZÄÖÜ][^[\n]{1,60}?)'
    r'\s*\[(?P<party>[^\]\n]{2,60})\]'
    r'\s*:\s*(?P<text>.+)$',
    re.DOTALL,
)

# "Zuruf des Abg. Name [Party]" — named but text-less individual call
_ZURUF_ABG_RE = re.compile(
    r'^Zuruf\s+des\s+Abg\.\s+'
    r'(?P<name>(?:(?:Dr|Prof)\.(?:\s*h\s*\.\s*c\.?)?\s+)?[^[\n]+?)'
    r'\s*\[(?P<party>[^\]\n]+)\]\s*$',
    re.IGNORECASE,
)

# "Gegenruf der/des Abg. Name [Party][: text]" — explicit counter-call
_GEGENRUF_RE = re.compile(
    r'^Gegenruf\s+de[rs]\s+Abg\.\s+'
    r'(?P<name>(?:(?:Dr|Prof)\.(?:\s*h\s*\.\s*c\.?)?\s+)?[^[\n]+?)'
    r'\s*\[(?P<party>[^\]\n]+)\]'
    r'(?:\s*:\s*(?P<text>.+))?$',
    re.IGNORECASE | re.DOTALL,
)

_BEIFALL_RE     = re.compile(r'^Beifall\b',                re.IGNORECASE)
_HEITERKEIT_RE  = re.compile(r'^Heiterkeit\b',             re.IGNORECASE)
_LACHEN_RE      = re.compile(r'^Lachen\b',                 re.IGNORECASE)
_WIDERSPRUCH_RE = re.compile(r'^Widerspruch\b',            re.IGNORECASE)
_ZURUF_RE       = re.compile(r'^(?:Weitere\s+)?Zurufe?\b', re.IGNORECASE)
_ZUSTIMMUNG_RE  = re.compile(r'^Zustimmung\b',             re.IGNORECASE)


def _normalize_name_for_lookup(name: str) -> str:
    """Strip title and gender prefixes from a name for speaker lookup matching.

    Converts "Dr. John Doe", "Frau Schroeder", etc. → "Schroeder" for matching.
    """
    name = name.strip()
    # Remove title prefixes (Dr., Prof., etc.)
    name = re.sub(r'^(?:Dr|Prof)\.(?:\s*h\.?\s*c\.?)?\s+', '', name, flags=re.IGNORECASE)
    # Remove gender prefixes (Herr, Frau, Herrin, etc.)
    name = re.sub(r'^(?:Herr|Frau|Herrin)\s+', '', name, flags=re.IGNORECASE)
    return name.strip()


def _normalize_party(raw: str) -> str | None:
    """Normalize party name from bracketed text.

    For modern terms, this extracts party abbreviations like [SPD], [CDU/CSU].
    For legacy terms (1-18), the bracketed text is often the politician's
    electoral district/city (e.g., [Tübingen], [Bremen]), not the party.
    We only return values that match known factions; otherwise return None.
    """
    return _match_faction(raw)


def _classify_segment(seg: str, speaker_lookup: dict[str, str] | None = None) -> dict:
    base = {
        "type": None, "caller_name": None,
        "caller_party": None, "text": None, "raw": seg,
    }

    m = _GEGENRUF_RE.match(seg)
    if m:
        party = _normalize_party(m.group("party").strip())
        caller_name = m.group("name").strip()
        # Try speaker lookup if normalized party is None (legacy records have city in brackets)
        if not party and speaker_lookup:
            normalized_name = _normalize_name_for_lookup(caller_name)
            party = speaker_lookup.get(normalized_name)
        return {**base,
                "type": TYPE_ZWISCHENRUF,
                "caller_name": caller_name,
                "caller_party": party,
                "text": (m.group("text") or "").strip() or None}

    m = _INDIVIDUAL_RE.match(seg)
    if m:
        party = _normalize_party(m.group("party").strip())
        caller_name = m.group("name").strip().rstrip(", ")
        # Try speaker lookup if normalized party is None (legacy records have city in brackets)
        if not party and speaker_lookup:
            normalized_name = _normalize_name_for_lookup(caller_name)
            party = speaker_lookup.get(normalized_name)
        return {**base,
                "type": TYPE_ZWISCHENRUF,
                "caller_name": caller_name,
                "caller_party": party,
                "text": m.group("text").strip()}

    m = _ZURUF_ABG_RE.match(seg)
    if m:
        party = _normalize_party(m.group("party").strip())
        caller_name = m.group("name").strip()
        # Try speaker lookup if normalized party is None (legacy records have city in brackets)
        if not party and speaker_lookup:
            normalized_name = _normalize_name_for_lookup(caller_name)
            party = speaker_lookup.get(normalized_name)
        return {**base,
                "type": TYPE_ZURUF,
                "caller_name": caller_name,
                "caller_party": party}

    if _BEIFALL_RE.match(seg):
        return {**base, "type": TYPE_BEIFALL}
    if _HEITERKEIT_RE.match(seg):
        return {**base, "type": TYPE_HEITERKEIT}
    if _LACHEN_RE.match(seg):
        return {**base, "type": TYPE_LACHEN}
    if _WIDERSPRUCH_RE.match(seg):
        return {**base, "type": TYPE_WIDERSPRUCH}
    if _ZUSTIMMUNG_RE.match(seg):
        return {**base, "type": TYPE_ZUSTIMMUNG}
    if _ZURUF_RE.match(seg):
        colon = seg.find(":")
        text = seg[colon + 1:].strip() if colon != -1 else None
        return {**base, "type": TYPE_ZURUF, "text": text}

    # Unknown — store as generic Zuruf so nothing is silently dropped
    return {**base, "type": TYPE_ZURUF}


def parse_kommentar(raw: str) -> list[dict]:
    """Split a <kommentar> string into a list of typed segment dicts.

    A single <kommentar> often contains multiple reactions joined by ' – ':
        (Beifall bei der AfD – Jan Korte [DIE LINKE]: Es geht los!)
    Each is parsed and classified independently.
    """
    text = raw.replace("\xa0", " ").strip()
    if text.startswith("(") and text.endswith(")"):
        text = text[1:-1]
    return [_classify_segment(s.strip()) for s in _SEP.split(text) if s.strip()]


# ── modern term extraction (terms 19+) ────────────────────────────────────────

def extract_modern_term(
    db_path: str | Path,
    term_dir: str | Path,
    electoral_term: int,
) -> pd.DataFrame:
    """Re-parse modern XML files and extract zwischenrufe with speech_id linkage.

    Matches each <rede> element to its DB speech_id by position within a session
    (same ordering used during the original transform/load phase).

    Requires finalize to have run so faction_normalized is available.
    """
    term_dir = Path(term_dir)
    xml_files = sorted(term_dir.glob("*.xml"))
    if not xml_files:
        print(f"[zwischenrufe] No XML files in {term_dir}", flush=True)
        return pd.DataFrame()

    records: list[dict] = []

    with duckdb.connect(str(db_path)) as conn:
        for xml_path in xml_files:
            sid_m = re.search(r"(\d+)", xml_path.stem)
            session = sid_m.group(1) if sid_m else xml_path.stem

            rows = conn.execute(
                "SELECT id, date, politician_id, faction_normalized "
                "FROM speeches WHERE session = ? AND electoral_term = ? ORDER BY id",
                [session, electoral_term],
            ).fetchall()
            if not rows:
                continue

            try:
                root = ET.parse(xml_path).getroot()
            except ET.ParseError:
                print(f"  [zwischenrufe] Skipping malformed XML: {xml_path.name}", flush=True)
                continue

            sitzungsverlauf = root.find("sitzungsverlauf")
            if sitzungsverlauf is None:
                continue

            speech_idx = 0
            for top in sitzungsverlauf.findall("tagesordnungspunkt"):
                for rede in top.findall("rede"):
                    if speech_idx >= len(rows):
                        break
                    speech_id, date, target_speaker_id, target_party = rows[speech_idx]
                    speech_idx += 1

                    for child in rede:
                        if child.tag == "kommentar" and child.text:
                            for seg in parse_kommentar(child.text):
                                records.append({
                                    "speech_id":            speech_id,
                                    "electoral_term":       electoral_term,
                                    "session":              session,
                                    "date":                 date,
                                    "target_speaker_id":    target_speaker_id,
                                    "target_speaker_party": target_party,
                                    **seg,
                                })

    df = pd.DataFrame(records)
    print(
        f"[zwischenrufe] term {electoral_term} (modern): "
        f"{len(df):,} segments from {len(xml_files)} sessions",
        flush=True,
    )
    return df


# ── legacy term extraction (terms 1–18) ───────────────────────────────────────

# Parenthetical block embedded in speech text — minimum 5 chars to skip abbreviations
_LEGACY_PAREN_RE = re.compile(r'\(([^)]{5,500})\)', re.DOTALL)
_LEGACY_SEP      = re.compile(r'\s*[—–]\s*')

# Keywords that mark a parenthetical as a parliamentary reaction rather than
# a geographic note, footnote, or other non-reaction content
_REACTION_KW = re.compile(
    r'\b(?:Zuruf|Beifall|Heiterkeit|Lachen|Widerspruch|Zustimmung|Abg\.)\b'
    r'|\[[A-ZÄÖÜ]',  # "[Party" bracket typical of attributed Zwischenruf
    re.IGNORECASE,
)


def _parse_legacy_paren(inner: str, speaker_lookup: dict[str, str] | None = None) -> list[dict]:
    """Parse the interior of a legacy parenthetical into typed segment dicts.

    Returns an empty list if the parenthetical doesn't look like a reaction.
    speaker_lookup: optional dict mapping caller names to faction_normalized for legacy records.
    """
    inner = inner.strip().replace("\n", " ")
    inner = re.sub(r"\s{2,}", " ", inner)

    if not _REACTION_KW.search(inner):
        return []

    results = []
    for seg in _LEGACY_SEP.split(inner):
        seg = seg.strip()
        if not seg:
            continue
        classified = _classify_segment(seg, speaker_lookup=speaker_lookup)
        # Drop generic unknown segments that don't contain reaction keywords
        if classified["type"] == TYPE_ZURUF and not classified["caller_name"] and not classified["text"]:
            if not _REACTION_KW.search(seg):
                continue
        results.append(classified)
    return results


def extract_legacy_term(db_path: str | Path, electoral_term: int) -> pd.DataFrame:
    """Extract zwischenrufe from speech_content for legacy terms (1–18).

    Works from the already-loaded speeches table. Handles both inline
    speech_content and the speech_texts side table (--text-table finalize).

    Requires finalize to have run so faction_normalized is available.
    """
    records: list[dict] = []

    with duckdb.connect(str(db_path)) as conn:
        # Support both inline content and --text-table layout
        row = conn.execute(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_name = 'speech_texts'"
        ).fetchone()
        has_speech_texts = bool(row and row[0])

        if has_speech_texts:
            content_col = "COALESCE(s.speech_content, t.speech_content)"
            join_clause = "LEFT JOIN speech_texts t ON t.id = s.id"
        else:
            content_col = "s.speech_content"
            join_clause = ""

        rows = conn.execute(
            f"SELECT s.id, s.session, s.date, s.politician_id, "
            f"s.faction_normalized, {content_col} AS speech_content "
            f"FROM speeches s {join_clause} "
            f"WHERE s.electoral_term = ? AND {content_col} IS NOT NULL",
            [electoral_term],
        ).fetchall()

        # Build speaker name → faction_normalized lookup for caller resolution
        # Use speeches table (which has faction_normalized) joined with speakers (which has names)
        speaker_rows = conn.execute(
            """
            SELECT DISTINCT sp.first_name, sp.last_name, s.faction_normalized
            FROM speeches s
            JOIN speakers sp ON sp.id = s.politician_id
            WHERE s.electoral_term = ? AND s.faction_normalized IS NOT NULL
            """,
            [electoral_term],
        ).fetchall()
        # Build lookup with both full names and last names for flexible matching
        speaker_lookup = {}
        for first, last, faction in speaker_rows:
            if last and faction:
                speaker_lookup[last.strip()] = faction  # Last name only
            if first and last and faction:
                # Also try "First Last" format
                speaker_lookup[f"{first.strip()} {last.strip()}"] = faction

    for speech_id, session, date, target_speaker_id, target_party, content in rows:
        if not content:
            continue
        for m in _LEGACY_PAREN_RE.finditer(content):
            segs = _parse_legacy_paren(m.group(1), speaker_lookup=speaker_lookup)
            for seg in segs:
                records.append({
                    "speech_id":            speech_id,
                    "electoral_term":       electoral_term,
                    "session":              str(session) if session else None,
                    "date":                 date,
                    "target_speaker_id":    target_speaker_id,
                    "target_speaker_party": target_party,
                    **seg,
                })

    df = pd.DataFrame(records)
    print(
        f"[zwischenrufe] term {electoral_term} (legacy): {len(df):,} segments",
        flush=True,
    )
    return df

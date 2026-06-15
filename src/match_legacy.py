"""Resolve ``politician_id`` for legacy speeches (terms 1–18).

Legacy session XML carries no stable speaker IDs, so ``transform`` writes the
sentinel ``-1``.  This phase matches each legacy speaker against the official
MdB registry (built by ``src/stammdaten.py``) and assigns the real 8-digit ID —
the same ID modern terms already use, so a member active across the 18/19 term
boundary collapses to one identity.

The matcher is deliberately **conservative**: an ID is only written when the
registry yields exactly one plausible member for the term.  Ambiguous or
unmatched speakers keep ``-1`` and are logged to ``legacy_match_unresolved`` for
review, never guessed.

Matching order, per distinct legacy speaker key (term, session, last_name,
first_name, faction_normalized):

  0. Session-scoped manual overrides (``data/legacy_overrides.json``, entry has
     ``session`` field) are checked first — most specific.
  1. Term-scoped manual overrides (entry has no ``session`` field) — covers all
     sessions in the term.
  2. Registry matcher: unique surname → +faction → +first name → +initial.
     Only assigns when exactly one candidate survives.

Manual overrides are the right tool for both surname-not-found (compound names,
OCR typos, Stammdaten term gaps) and ambiguous-N-candidates cases where you can
determine from context who was speaking (e.g. Bundestagspräsident).

A broken-parse recovery is attempted before registry lookup: when the parsed
``last_name`` starts with a non-alpha character (punctuation leaked in), the
fields are swapped before matching.
"""

import json
import re
from pathlib import Path

import duckdb
import pandas as pd

# Nobility particles the legacy parser keeps glued to the surname; the registry
# stores them separately in PRAEFIX, so strip them for a comparable key.
_PARTICLES = {
    "von", "van", "de", "del", "den", "der", "di", "du",
    "zu", "zur", "zum", "le", "la",
}

# Title / honorific cruft that leaks into the legacy first_name field.
# Covers personal titles (Dr, Prof) and role prefixes when the speaker was
# introduced by role rather than name (e.g. "Staatsminister Joseph" → strips
# "Staatsminister", leaves "Joseph" for first-name matching).
_TITLE_CRUFT = re.compile(
    r"^(?:Dr|Prof|D|Frau|Herr|Abg|Ing|Freiherr|Graf|Gräfin|Baron"
    r"|Staatsminister|Bundesminister|Ministerpräsident|Staatssekretär"
    r"|Parlamentarischer\s+Staatssekretär|Kollegen?|Abgeordneten?)\b\.?\s*",
    re.IGNORECASE,
)

_OVERRIDES_PATH = Path(__file__).parent.parent / "data" / "legacy_overrides.json"


def _load_overrides() -> tuple[dict, dict]:
    """Load manual overrides from data/legacy_overrides.json.

    Returns two dicts:
        session_overrides: (electoral_term, session, last_name, first_name) → id
        term_overrides:    (electoral_term, last_name, first_name)           → id
    """
    if not _OVERRIDES_PATH.exists():
        return {}, {}
    with open(_OVERRIDES_PATH, encoding="utf-8") as fh:
        data = json.load(fh)
    entries = data["overrides"] if isinstance(data, dict) else data
    session_ov: dict[tuple, int] = {}
    term_ov: dict[tuple, int] = {}
    for e in entries:
        term = int(e["electoral_term"])
        last = e["speech_last_name"]
        first = e.get("speech_first_name", "")
        pid = int(e["politician_id"])
        if e.get("session"):
            session_ov[(term, str(e["session"]), last, first)] = pid
        else:
            term_ov[(term, last, first)] = pid
    total = len(session_ov) + len(term_ov)
    print(
        f"[legacy-match] loaded {total} manual overrides "
        f"({len(session_ov)} session-scoped, {len(term_ov)} term-scoped)",
        flush=True,
    )
    return session_ov, term_ov


def _norm_surname(last: str) -> str:
    s = (last or "").strip().lower()
    parts = s.split()
    while parts and parts[0] in _PARTICLES:
        parts.pop(0)
    return " ".join(parts)


def _norm_firstname(first: str) -> str:
    s = (first or "").strip()
    prev = None
    while s and s != prev:
        prev = s
        s = _TITLE_CRUFT.sub("", s).strip()
    return s.lower()


def _is_broken_surname(last: str) -> bool:
    """True when the surname field looks like a parse error (non-alpha start)."""
    core = (last or "").strip()
    return not core or not re.match(r"^[A-Za-zÄÖÜäöüß]", core)


def _build_registry_index(con: duckdb.DuckDBPyConnection) -> dict:
    """term -> surname -> list of {id, firstnames:set, faction}."""
    names = con.execute(
        "SELECT id, last_name, first_name FROM politicians"
    ).fetchdf()
    terms = con.execute(
        "SELECT id, electoral_term, faction FROM politician_terms"
    ).fetchdf()

    first_by_id: dict[int, set] = {}
    surnames_by_id: dict[int, set] = {}
    for _, r in names.iterrows():
        pid = int(r["id"])
        surnames_by_id.setdefault(pid, set()).add(_norm_surname(r["last_name"]))
        first_by_id.setdefault(pid, set()).add(_norm_firstname(r["first_name"]))

    index: dict[int, dict[str, list]] = {}
    for _, r in terms.iterrows():
        pid = int(r["id"])
        term = int(r["electoral_term"])
        faction = r["faction"]
        entry = {
            "id": pid,
            "firstnames": first_by_id.get(pid, set()),
            "faction": faction,
        }
        term_idx = index.setdefault(term, {})
        for sn in surnames_by_id.get(pid, set()):
            if sn:
                term_idx.setdefault(sn, []).append(entry)
    return index


def _match_one(term, surname, firstname, faction, index) -> tuple[int | None, str]:
    """Return (matched_id, reason)."""
    term_idx = index.get(int(term))
    if not term_idx:
        return None, "term-not-in-registry"
    cands = term_idx.get(surname)
    if not cands:
        return None, "surname-not-found"

    by_id = {c["id"]: c for c in cands}
    cands = list(by_id.values())

    if len(cands) == 1:
        return cands[0]["id"], "unique-surname"

    # Disambiguate by faction.
    if faction and faction not in ("Unknown", "Fraktionslos"):
        fac = [c for c in cands if c["faction"] == faction]
        if len(fac) == 1:
            return fac[0]["id"], "surname+faction"
        if fac:
            cands = fac

    # Disambiguate by full first name then initial.
    if firstname:
        exact = [c for c in cands if firstname in c["firstnames"]]
        if len(exact) == 1:
            return exact[0]["id"], "surname+firstname"
        if len(exact) > 1:
            return None, "ambiguous-firstname"
        init = firstname[0]
        ini = [c for c in cands if any(fn and fn[0] == init for fn in c["firstnames"])]
        if len(ini) == 1:
            return ini[0]["id"], "surname+initial"

    return None, f"ambiguous-{len(cands)}-candidates"


def match_legacy(db_path: str | Path) -> None:
    """Assign politician_id to legacy speeches and log the unresolved residue."""
    with duckdb.connect(str(db_path)) as con:
        if not con.execute(
            "SELECT count(*) FROM information_schema.tables "
            "WHERE table_name IN ('politicians','politician_terms')"
        ).fetchone()[0] == 2:
            raise RuntimeError(
                "Registry tables missing — run the 'stammdaten' phase first."
            )

        session_ov, term_ov = _load_overrides()
        index = _build_registry_index(con)

        # Use faction_normalized if finalize has been run, otherwise fall back
        # to the raw faction column so legacy-match works in any phase order.
        has_normalized = bool(con.execute(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = 'speeches' AND column_name = 'faction_normalized'"
        ).fetchone())
        faction_col = "faction_normalized" if has_normalized else "faction"

        # Check whether session_files is populated (may be absent on older DBs).
        has_files = bool(con.execute(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_name = 'session_files'"
        ).fetchone()) and bool(con.execute(
            "SELECT COUNT(*) FROM session_files"
        ).fetchone()[0])

        if has_files:
            file_join = "LEFT JOIN session_files sf ON sf.electoral_term = s.electoral_term AND sf.session = s.session"
            file_cols = "s.session, sf.filename,"
        else:
            file_join = ""
            file_cols = "s.session, NULL AS filename,"

        keys = con.execute(
            f"""
            SELECT s.electoral_term, {file_cols} s.last_name, s.first_name,
                   s.{faction_col} AS faction_normalized,
                   COUNT(*) AS speeches
            FROM speeches s
            {file_join}
            WHERE s.electoral_term <= 18 AND s.politician_id = -1
            GROUP BY 1, 2, 3, 4, 5, 6
            """
        ).fetchdf()
        print(f"[legacy-match] {len(keys):,} distinct legacy speaker keys", flush=True)

        rows = []
        for _, k in keys.iterrows():
            last = str(k["last_name"])
            first = str(k["first_name"])
            session = str(k["session"])
            term = int(k["electoral_term"])
            filename = str(k["filename"]) if k["filename"] is not None and str(k["filename"]) != "<NA>" else ""

            # Step 0a: session-scoped override (most specific).
            if (term, session, last, first) in session_ov:
                rows.append({
                    "electoral_term": term,
                    "session": session,
                    "filename": filename,
                    "last_name": last,
                    "first_name": first,
                    "faction_normalized": k["faction_normalized"],
                    "speeches": int(k["speeches"]),
                    "matched_id": session_ov[(term, session, last, first)],
                    "reason": "manual-override-session",
                })
                continue

            # Step 0b: term-scoped override.
            if (term, last, first) in term_ov:
                rows.append({
                    "electoral_term": term,
                    "session": session,
                    "filename": filename,
                    "last_name": last,
                    "first_name": first,
                    "faction_normalized": k["faction_normalized"],
                    "speeches": int(k["speeches"]),
                    "matched_id": term_ov[(term, last, first)],
                    "reason": "manual-override",
                })
                continue

            # Step 1–4: registry matcher.
            if _is_broken_surname(last):
                last, first = first, last
            surname = _norm_surname(last)
            fn = _norm_firstname(first)
            mid, reason = _match_one(
                term, surname, fn, k["faction_normalized"], index
            )
            rows.append({
                "electoral_term": term,
                "session": session,
                "filename": filename,
                "last_name": str(k["last_name"]),
                "first_name": str(k["first_name"]),
                "faction_normalized": k["faction_normalized"],
                "speeches": int(k["speeches"]),
                "matched_id": mid,
                "reason": reason,
            })

        result = pd.DataFrame(rows)
        matched = result[result["matched_id"].notna()].copy()
        matched["matched_id"] = matched["matched_id"].astype("int64")

        # Apply: update speeches joined on (term, session, last, first, faction).
        con.execute("DROP TABLE IF EXISTS _legacy_id_map")
        con.execute("CREATE TABLE _legacy_id_map AS SELECT * FROM matched")
        con.execute(
            f"""
            UPDATE speeches s
            SET politician_id = m.matched_id
            FROM _legacy_id_map m
            WHERE s.electoral_term = m.electoral_term
              AND s.session = m.session
              AND s.last_name IS NOT DISTINCT FROM m.last_name
              AND s.first_name IS NOT DISTINCT FROM m.first_name
              AND s.{faction_col} IS NOT DISTINCT FROM m.faction_normalized
              AND s.politician_id = -1
            """
        )
        con.execute("DROP TABLE _legacy_id_map")

        # Audit: persist unresolved residue with session + filename for research.
        unresolved = result[result["matched_id"].isna()].copy()
        con.execute("DROP TABLE IF EXISTS legacy_match_unresolved")
        con.execute(
            "CREATE TABLE legacy_match_unresolved AS "
            "SELECT electoral_term, session, filename, last_name, first_name, "
            "faction_normalized, speeches, reason FROM unresolved"
        )
        con.execute("CHECKPOINT")

        m_sp = int(matched["speeches"].sum()) if not matched.empty else 0
        u_sp = int(unresolved["speeches"].sum()) if not unresolved.empty else 0
        total = m_sp + u_sp
        pct = (100.0 * m_sp / total) if total else 0.0
        print(
            f"[legacy-match] resolved {m_sp:,}/{total:,} legacy speeches "
            f"({pct:.1f}%); {len(matched):,} keys matched, "
            f"{len(unresolved):,} keys unresolved",
            flush=True,
        )
        if not unresolved.empty:
            log_path = Path(str(db_path)).with_suffix(".legacy_unresolved.csv")
            unresolved.sort_values("speeches", ascending=False).to_csv(
                log_path, index=False
            )
            print(
                f"[legacy-match] unresolved residue → {log_path}", flush=True
            )

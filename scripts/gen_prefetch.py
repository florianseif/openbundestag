"""Precompute /api/search payloads for a handful of frequently-searched words.

The explorer fires `/api/search` on every keystroke; the only expensive part is
the substring scan over the ~1.8 GB `search_text` column. For the small set of
words a first-time visitor is most likely to try (and the ones we'd demo to a
jury), we can ship the answer as a static JSON bundled into the web app, so the
explorer renders charts the instant the page loads — no API round-trip, no scan.

The cache is keyed by the *default* explorer filter signature only:

    parties = []          (no party filter)
    terms   = [<latest>]  (current legislature — what loads by default)
    politician_id = None
    granularity = "Quarterly"
    count_mode  = "occurrences"
    top_n = 15

Any deviation (different term, a party/MP filter, monthly view, speeches mode)
misses the cache and falls back to the live API — exactly the behaviour we want.

Run from the repo root after a rebuild:

    DB_PATH=openbundestag-data.db uv run python scripts/gen_prefetch.py

Writes web/src/lib/prefetch.json. Re-run whenever the corpus changes.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import sys
from pathlib import Path
from typing import Any

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import queries as q  # noqa: E402

# Words a first-time visitor (or a demo jury) is most likely to reach for —
# politically salient German keywords. ~100 broad policy/politics terms; any
# that return no matches in the current term are pruned at generation time.
POPULAR_WORDS = [
    "Schuldenbremse", "Klimawandel", "Migration", "Rente", "Inflation",
    "Bürgergeld", "Krieg", "Demokratie", "Steuern", "Wohnen",
    "Gesundheit", "Bildung", "Arbeit", "Sicherheit", "Europa",
    "Ukraine", "Mindestlohn", "Pflege", "Wirtschaft", "Energie",
    "Digitalisierung", "Frieden", "Freiheit", "Verteidigung", "Asyl",
    "Klimaschutz", "Umwelt", "Atomkraft", "Kohle", "Wasserstoff",
    "Verkehr", "Bahn", "Mieten", "Familie", "Kinder",
    "Frauen", "Gleichstellung", "Integration", "Flüchtlinge", "Islam",
    "Antisemitismus", "Rassismus", "Extremismus", "Terrorismus", "Bundeswehr",
    "NATO", "Russland", "China", "Israel", "Außenpolitik",
    "Menschenrechte", "Sanktionen", "Handel", "Industrie", "Mittelstand",
    "Arbeitslosigkeit", "Gewerkschaft", "Armut", "Vermögen", "Haushalt",
    "Finanzen", "Investitionen", "Schulden", "Wachstum", "Euro",
    "Bürokratie", "Verwaltung", "Kommunen", "Grundgesetz", "Justiz",
    "Polizei", "Kriminalität", "Datenschutz", "Internet", "Forschung",
    "Wissenschaft", "Schule", "Ausbildung", "Fachkräfte", "Zuwanderung",
    "Staatsbürgerschaft", "Krankenversicherung", "Klima", "Landwirtschaft", "Ernährung",
    "Tierschutz", "Wald", "Wasser", "Energiewende", "Gas",
    "Strompreis", "Verbraucher", "Cannabis", "Impfung", "Pandemie",
    "Corona", "Wohnungsbau", "Sozialstaat", "Subventionen", "Rüstung",
]

GRANULARITY = "Quarterly"
COUNT_MODE = "occurrences"
TOP_N = 15

OUT_PATH = Path(__file__).resolve().parent.parent / "web" / "src" / "lib" / "prefetch.json"


def _jsonable(value: Any) -> Any:
    """Mirror api.main._jsonable so the payload is byte-identical to the API's."""
    if value is None:
        return None
    if isinstance(value, (dt.date, dt.datetime, pd.Timestamp)):
        return value.isoformat()[:10]
    if isinstance(value, float) and pd.isna(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


def _records(df: pd.DataFrame) -> list[dict]:
    return [{k: _jsonable(v) for k, v in row.items()} for row in df.to_dict("records")]


def _payload(res: dict) -> dict:
    return {
        "total": {k: _jsonable(v) for k, v in res["total"].items()},
        "timeline": _records(res["timeline"]),
        "by_party": _records(res["by_party"]),
        "by_term": _records(res["by_term"]),
        "top_politicians": _records(res["top_politicians"]),
    }


def main() -> None:
    con = q.open_connection(read_only=True, prewarm=False)
    latest_term = con.execute("SELECT MAX(electoral_term) FROM speeches").fetchone()[0]
    terms = [int(latest_term)]

    words: dict[str, dict] = {}
    pruned: list[str] = []
    for word in POPULAR_WORDS:
        cur = con.cursor()
        res = q.search(cur, word, [], terms, None, GRANULARITY, COUNT_MODE, TOP_N)
        count = res["total"]["count"]
        if count == 0:
            pruned.append(word)
            print(f"  {word:18}      0 matches  (pruned)", file=sys.stderr)
            continue
        words[word.lower()] = _payload(res)
        print(f"  {word:18} {count:>6} matches", file=sys.stderr)
    if pruned:
        print(f"Pruned {len(pruned)} zero-match words: {', '.join(pruned)}", file=sys.stderr)

    bundle = {
        "_comment": (
            "Precomputed /api/search payloads for popular words under the default "
            "explorer filters. Regenerate with scripts/gen_prefetch.py after a rebuild."
        ),
        "signature": {
            "terms": terms,
            "granularity": GRANULARITY,
            "count_mode": COUNT_MODE,
            "top_n": TOP_N,
        },
        "words": words,
    }

    OUT_PATH.write_text(json.dumps(bundle, ensure_ascii=False, indent=0), encoding="utf-8")
    size_kb = OUT_PATH.stat().st_size / 1024
    print(
        f"Wrote {len(words)} words for term {terms[0]} → {OUT_PATH} ({size_kb:.0f} KB)",
        file=sys.stderr,
    )


if __name__ == "__main__":
    os.environ.setdefault("DB_PATH", "openbundestag-data.db")
    main()

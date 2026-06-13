"""Scrape the Wikipedia list of German government members since 1949.

Returns two DataFrames:
  ministers   — one row per person (full_name, first_name, last_name, party, wikipedia_url)
  roles       — one row per role period (full_name, from_year, to_year, ministry)
"""

import re
import requests
import pandas as pd
from bs4 import BeautifulSoup

URL = "https://de.wikipedia.org/wiki/Liste_der_deutschen_Regierungsmitglieder_seit_1949"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; openbundestag/1.0)"}

# Normalise Wikipedia party labels to the same values used in speech data
PARTY_MAP: dict[str, str] = {
    "CDU":                    "CDU/CSU",
    "CSU":                    "CDU/CSU",
    "CDU/CSU":                "CDU/CSU",
    "SPD":                    "SPD",
    "FDP":                    "FDP",
    "FVP":                    "FDP",
    "Bündnis 90/Die Grünen":  "Bündnis 90/Die Grünen",
    "Die Grünen":             "Bündnis 90/Die Grünen",
    "GRÜNE":                  "Bündnis 90/Die Grünen",
    "AfD":                    "AfD",
    "Die Linke":              "Die Linke",
    "DIE LINKE":              "Die Linke",
    "PDS":                    "PDS",
    "BSW":                    "BSW",
    "GB/BHE":                 "GB/BHE",
    "DP":                     "DP",
    "Z":                      "Z",
    "KPD":                    "KPD",
    "BP":                     "BP",
    "WAV":                    "WAV",
    "DRP":                    "DRP",
    "SSW":                    "SSW",
}


def _normalise_party(raw: str) -> str:
    return PARTY_MAP.get(raw.strip(), raw.strip())


def _parse_year(text: str) -> int | None:
    """Extract a 4-digit year from a string like '2021–2025' or 'seit 2025'."""
    m = re.search(r"\d{4}", text)
    return int(m.group()) if m else None


def _split_name(full_name: str) -> tuple[str, str]:
    """Best-effort split of 'Firstname Lastname' (handles 'von', 'Dr.', etc.)."""
    # Strip honorifics
    cleaned = re.sub(r"^(Dr\.|Prof\.|h\.c\.|Dr\.h\.c\.)\s*", "", full_name).strip()
    parts = cleaned.split()
    if len(parts) == 1:
        return "", parts[0]
    # Last token = last name (handles 'von Bülow', 'von Brentano' etc.)
    # Keep nobility particles with last name
    for i, p in enumerate(parts[:-1]):
        if p.lower() in {"von", "van", "de", "zu", "zur"}:
            return " ".join(parts[:i]), " ".join(parts[i:])
    return " ".join(parts[:-1]), parts[-1]


def scrape() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Fetch the Wikipedia page and return (ministers_df, roles_df)."""
    print("[scrape] Fetching Wikipedia minister list…", flush=True)
    resp = requests.get(URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")

    content = soup.find("div", class_="mw-parser-output")
    list_section = content.find_all("section")[1]   # "Liste" section

    ministers: list[dict] = []
    roles: list[dict] = []

    # Each letter sub-section contains a <ul> with top-level <li> per minister
    for letter_section in list_section.find_all("section"):
        top_ul = letter_section.find("ul")
        if not top_ul:
            continue

        for li in top_ul.find_all("li", recursive=False):
            # ── Name ────────────────────────────────────────────────────
            name_link = li.find("a")
            if name_link is None:
                continue
            full_name = name_link.get_text(strip=True)
            wiki_path = name_link.get("href", "")
            wiki_url = ("https://de.wikipedia.org" + wiki_path) if wiki_path.startswith("/") else wiki_path

            # ── Party ────────────────────────────────────────────────────
            # The party is the SECOND link in the <li> text (first = person)
            all_links = li.find_all("a", recursive=False)
            party_raw = ""
            if len(all_links) >= 2:
                party_raw = all_links[1].get_text(strip=True)
            party = _normalise_party(party_raw)

            first_name, last_name = _split_name(full_name)

            ministers.append(
                {
                    "full_name":    full_name,
                    "first_name":   first_name,
                    "last_name":    last_name,
                    "party":        party,
                    "wikipedia_url": wiki_url,
                }
            )

            # ── Roles (nested <ul>) ──────────────────────────────────────
            nested_ul = li.find("ul")
            if nested_ul:
                for role_li in nested_ul.find_all("li"):
                    text = role_li.get_text(strip=True)
                    # Formats: "2021–2025 Auswärtiges"  |  "seit 2025 Inneres"
                    year_match = re.match(
                        r"(?:seit\s+)?(\d{4})(?:[–\-](\d{4}))?\s+(.*)", text
                    )
                    if not year_match:
                        continue
                    from_year = int(year_match.group(1))
                    to_year = int(year_match.group(2)) if year_match.group(2) else None
                    ministry = year_match.group(3).strip()
                    roles.append(
                        {
                            "full_name":  full_name,
                            "from_year":  from_year,
                            "to_year":    to_year,
                            "ministry":   ministry,
                        }
                    )

    ministers_df = pd.DataFrame(ministers).drop_duplicates(subset=["full_name"])
    roles_df = pd.DataFrame(roles)

    print(
        f"[scrape] {len(ministers_df)} ministers, {len(roles_df)} role periods",
        flush=True,
    )
    return ministers_df, roles_df

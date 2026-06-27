<!-- markdownlint-disable MD033 -->

# OpenBundestag — Worte der Macht

Explore **word usage across German Bundestag plenary debates** (1949–present, ~760,000 speeches). A lightweight, standalone data pipeline downloads the official open-data transcripts into a single local [DuckDB](https://duckdb.org/) file — no Docker, no PostgreSQL, no Node.js required.

## Quick links

📖 [Architecture diagram](web/src/views/Architecture.vue) (interactive) · 📊 [Streamlit app](#streamlit-app) · 🌐 [Vue 3 website](#website) · 📋 [Data schema](#database-schema) · 🚀 [Contributing](#contributing)

---

## Quick start

**Prerequisites:** Python ≥ 3.11 + [uv](https://docs.astral.sh/uv/)

```bash
# Install
uv sync

# Run the full pipeline for the current term (default 21)
uv run run.py --phase all

# Or build the whole corpus (all terms 1–21) in one command.
# (--all-terms skips the bot-protected download and builds from data you
#  already have; run `--phase extract --all-terms` first for a fresh clone.)
uv run run.py --phase all --all-terms

# Launch the Streamlit app
uv run streamlit run app.py  # opens http://localhost:8501
```

### Skip the pipeline: use the pre-built database

A ready-made `openbundestag-data.db` (~2 GB, all 21 terms) is available:

```bash
uv sync
uv run hf download MissionJupiter/openbundestag-db openbundestag-data.db --repo-type dataset --local-dir .
uv run streamlit run app.py
```

---

## What is this?

**The pipeline** (6 phases) converts raw Bundestag XML into a queryable database:

```
XML/ZIP (Bundestag)
  ↓ Extract (download with Playwright)
data/term_XX/ (cache)
  ↓ Transform (parse modern + legacy formats)
speakers_df, speeches_df (in-memory)
  ↓ Load (write to DuckDB)
openbundestag-data.db (created)
  ↓ Ministers (scrape Wikipedia)
  ↓ Finalize (materialize faction_normalized, search_text)
  ↓ Zwischenrufe (extract interjections)
Ready database → Streamlit + Vue 3
```

**See the [interactive architecture diagram](web/src/routes/architecture) for details on each phase.**

### The output: two tables

**`speakers`** — one row per politician across all terms:
- `id` (Bundestag ID), `first_name`, `last_name`, `faction`

**`speeches`** — one row per speech segment (~760k rows):
- `id`, `session`, `electoral_term`, `date`, `politician_id`
- `first_name`, `last_name`, `faction`, `position_short`, `position_long`
- `speech_content` (full verbatim text)

---

## Streamlit app

Launch with `uv run streamlit run app.py`.

**Search tabs:**
- **📈 Timeline** — word frequency over time (monthly/quarterly), one line per party
- **🥧 By party** — party breakdown and historical trends
- **🎤 Top speakers** — which politicians mentioned the keyword most

**Filters:** keyword (required), parties, electoral terms, specific politician.

**Party colours** — official Bundestag colours:  
CDU/CSU (#000000) · SPD (#E3000F) · Grünen (#1AA037) · FDP (#FFED00) · Die Linke (#BE3075) · AfD (#009EE0) · BSW (#9B2335)

---

## Website (Vue 3 + FastAPI)

A bespoke site at `web/` and `api/` with scrollytelling intro, live explorer, and dark "data-noir" design (obsidian canvas, aurora gradient accent, glass panels).

**Run locally** (two processes):

```bash
# Terminal 1: API (reads openbundestag-data.db)
uv run uvicorn api.main:app --port 8000

# Terminal 2: Website
cd web && npm install && npm run dev
# Opens http://localhost:5173
```

**Deployed:**
- Frontend → [Cloudflare Pages](https://openbundestag.florian-seif.de) (free)
- API → Hugging Face Space (free)
- Database → Hugging Face Dataset (free)

See [`web/README.md`](web/README.md) and [`api/README.md`](api/README.md) for details.

---

## Pipeline reference

| Phase | Module | Purpose | Input | Output |
|---|---|---|---|---|
| **Extract** | `src/extract.py` | Download + cache | Bundestag URLs | `data/term_XX/*.xml` |
| **Transform** | `src/transform.py` | Parse XML → DataFrames | Raw XML | `speakers_df`, `speeches_df` |
| **Load** | `src/load.py` | Write to DuckDB | DataFrames | `openbundestag-data.db` |
| **Ministers** | `src/scrape_ministers.py` | Scrape minister data | Wikipedia | `ministers`, `roles` tables |
| **Finalize** | `src/load.py` | Materialize columns | `speeches` + ministers | `faction_normalized`, `search_text` |
| **Zwischenrufe** | `src/zwischenrufe.py` | Extract interjections | XML + DB | `zwischenrufe` table |

**Key dependencies:**
- Extract → Transform → Load (sequential)
- Ministers runs in parallel with Load, both must finish before Finalize
- Finalize must complete before Zwischenrufe

---

## CLI reference

```
uv run run.py --phase [extract|transform|load|ministers|finalize|zwischenrufe|all] \
              --term TERM \
              --db DATABASE \
              --data-dir DIRECTORY \
              --text-table
```

**Options:**
- `--phase` (default: `all`) — which phase(s) to run
- `--term` (default: `20`) — Wahlperiode to process (1–21)
- `--db` (default: `openbundestag-data.db`) — output database path
- `--data-dir` (default: `data`) — raw XML cache directory
- `--text-table` — move speech_content to a side table (lean `speeches`, full text on demand)

**Examples:**
```bash
uv run run.py --phase all --term 20          # full pipeline for one term
uv run run.py --phase extract --term 21      # download only
uv run run.py --phase finalize               # finalize (runs on existing DB)
```

---

## Data format

<details>
<summary><strong>What's inside a Bundestag XML file?</strong></summary>

Each XML file (`21083.xml`, `20214.xml`, …) is a `dbtplenarprotokoll` document:

```
dbtplenarprotokoll
├── vorspann          — header (session number, date, location, TOC)
├── rednerliste       — registered speakers + Bundestag IDs
├── sitzungsverlauf   — the actual transcript
│   └── tagesordnungspunkt (agenda items)
│       └── rede (speeches)
│           ├── p klasse="redner"  — speaker header
│           ├── p klasse="J|J_1|O" — speech paragraphs
│           └── kommentar          — interjections (extracted separately)
└── anlagen           — appendix (written statements, voting)
```

**Modern terms (19–21):** structured XML, one file per session.  
**Legacy terms (1–18):** text-heavy XML in ZIP archives, parsed via regex-based speaker detection.

The `<redner id="…">` attribute is the stable Bundestag politician ID (maps to the same person across all terms).

</details>

---

## Database schema

```sql
CREATE TABLE speakers (
    id           INTEGER PRIMARY KEY,  -- Bundestag politician ID
    first_name   VARCHAR,
    last_name    VARCHAR,
    faction      VARCHAR
);

CREATE TABLE speeches (
    id              INTEGER PRIMARY KEY,
    session         VARCHAR,           -- session number (e.g. "21083")
    electoral_term  INTEGER,           -- Wahlperiode
    date            DATE,
    politician_id   INTEGER,           -- Bundestag ID (or -1 if unresolved)
    first_name      VARCHAR,
    last_name       VARCHAR,
    faction         VARCHAR,
    position_short  VARCHAR,           -- "MP", "Minister", "Chancellor", etc.
    position_long   VARCHAR,           -- full role (e.g. "Bundesminister der Finanzen")
    speech_content  TEXT,              -- full verbatim text
    faction_normalized VARCHAR,        -- derived column (finalize phase)
    search_text     VARCHAR            -- derived column (finalize phase)
);

CREATE TABLE zwischenrufe (
    speech_id           INTEGER,
    electoral_term      INTEGER,
    session             VARCHAR,
    date                DATE,
    target_speaker_id   INTEGER,
    target_speaker_party VARCHAR,
    type                VARCHAR,       -- "Zwischenruf", "Beifall", "Lachen", etc.
    caller_name         VARCHAR,
    caller_party        VARCHAR,
    text                TEXT,
    raw                 TEXT
);
```

---

## Example queries

```python
import duckdb

con = duckdb.connect("openbundestag-data.db")

# Top 10 speakers
con.sql("""
    SELECT first_name, last_name, faction, COUNT(*) as speeches
    FROM speeches
    GROUP BY 1, 2, 3
    ORDER BY speeches DESC
    LIMIT 10
""").show()

# Keyword search (with finalize-phase speedup)
con.sql("""
    SELECT date, first_name, last_name, speech_content
    FROM speeches
    WHERE search_text LIKE '%klimawandel%'
    ORDER BY date DESC
    LIMIT 20
""").show()

# Party timeline for a keyword
con.sql("""
    SELECT
        DATE_TRUNC('quarter', date) as quarter,
        faction_normalized,
        COUNT(*) as mentions
    FROM speeches
    WHERE search_text LIKE '%europe%'
    GROUP BY 1, 2
    ORDER BY 1, 2
""").show()
```

---

## Repository structure

```
openbundestag/
├── pyproject.toml          # uv config + deps
├── run.py                  # CLI entrypoint
├── app.py                  # Streamlit frontend
├── src/
│   ├── extract.py          # Download XML/ZIP
│   ├── transform.py        # Parse XML → DataFrames
│   ├── load.py             # Write to DuckDB + finalize
│   ├── queries.py          # Shared query layer
│   ├── scrape_ministers.py # Wikipedia scraper
│   └── zwischenrufe.py     # Interjection extractor
├── api/                    # FastAPI service
├── web/                    # Vue 3 frontend
├── data/                   # Downloaded XML cache (git-ignored)
└── openbundestag-data.db   # Output database (git-ignored)
```

---

## Deployment

Pre-built database is published to [Hugging Face](https://huggingface.co/datasets/MissionJupiter/openbundestag-db) and auto-downloaded by both Streamlit and API Spaces at startup.

**To update the published database:**

```bash
# (Re)download every term first if you need fresh data (bot-protected, slow):
uv run run.py --phase extract --all-terms

# Rebuild the whole DB (all terms, all phases, compacted) in one command:
uv run run.py --phase all --all-terms

# Upload to HF (one-time auth)
uv run hf auth login
uv run hf upload MissionJupiter/openbundestag-db openbundestag-data.db openbundestag-data.db --repo-type dataset
```

**CI/CD:** GitHub Actions deploys application code (not the 2 GB DB) to Spaces and Cloudflare Pages on pushes to `main`.

---

## Contributing

Issues and pull requests welcome.

---

## Data licence & attribution

Speech transcripts are official German Bundestag plenary protocols (*Plenarprotokolle*), published under the [Bundestag Open Data portal](https://www.bundestag.de/services/opendata).

- **Status:** Public domain under **§ 5 Abs. 1 UrhG** (German Copyright Act — *amtliche Werke*)
- **Use:** Free for reporting, education, research. No commercial advertising.
- **Attribution:** © Deutscher Bundestag — [www.bundestag.de/services/opendata](https://www.bundestag.de/services/opendata)

Minister data sourced from Wikipedia under [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/).

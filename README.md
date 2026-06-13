<!-- markdownlint-disable MD033 -->

# OpenBundestag — Worte der Macht

Explore **word usage across German Bundestag plenary debates** (1949–present, ~760,000 speeches). A lightweight, standalone data pipeline downloads the official open-data transcripts into a single local [DuckDB](https://duckdb.org/) file — no Docker, no PostgreSQL, no Node.js required — and a [Streamlit](https://streamlit.io/) app lets you search any keyword and see how its usage breaks down over time, by party, and by speaker.

## Project Info

OpenBundestag aims to make German parliamentary discourse easy to search and analyse. The pipeline produces two flat tables (`speakers`, `speeches`) that are ready for analysis without any infrastructure setup.

It is an independent, derivative reimplementation inspired by the
[Open Discourse](https://opendiscourse.de/) project, which pioneered open access
to Bundestag debate data.

---

## Requirements

- Python ≥ 3.11
- [uv](https://docs.astral.sh/uv/) (`pip install uv` or `brew install uv`)

---

## The data

### Source

Every plenary session of the German Bundestag is transcribed verbatim and published as a structured XML file on the [Bundestag Open Data portal](https://www.bundestag.de/services/opendata). Each file is one complete session — typically 4–8 hours of parliamentary debate.

**Modern terms (19–21):** individual XML files, one per session, published within days of the sitting.  
**Legacy terms (1–18):** packaged as ZIP archives, one ZIP per term, containing older XML formats that are text-heavy rather than structured.

This pipeline supports **all 21 Wahlperioden (1949–present)**: terms 19–21 use the modern structured XML format; terms 1–18 are distributed as ZIP archives with a legacy text-based XML format that this pipeline parses via regex-based speaker detection. Total corpus: ~760,000 speeches.

---

### What a session file contains

Each XML file (`21083.xml`, `20214.xml`, …) is a `dbtplenarprotokoll` document with four top-level sections:

```
dbtplenarprotokoll
├── vorspann          — header: session number, date, location, table of contents
├── rednerliste       — list of all registered speakers with their Bundestag IDs
├── sitzungsverlauf   — the actual transcript (what the pipeline extracts)
│   ├── sitzungsbeginn
│   └── tagesordnungspunkt (one per agenda item)
│       └── rede (one per speech)
│           ├── p klasse="redner"  — speaker header with <redner id="…"> and name/faction
│           ├── p klasse="J"       — speech paragraph
│           ├── p klasse="J_1"     — first paragraph of a speech
│           ├── p klasse="O"       — continuation paragraph
│           └── kommentar          — interjections, applause, heckling
└── anlagen           — appendix (written statements, voting lists)
```

The `<redner id="…">` attribute is the official Bundestag politician ID — a stable numeric identifier that maps to the same person across all terms and sessions.

A single session typically contains **50–150 speeches**. Each speech is one MP's or minister's continuous turn at the podium. Interjections (`<kommentar>`) from other MPs are embedded inline but are not extracted as separate speeches.

---

### What gets stored

The pipeline flattens all of that into two DuckDB tables:

**`speakers`** — one row per unique politician seen across all downloaded sessions:

| column | type | description |
|---|---|---|
| `id` | INTEGER | Official Bundestag politician ID |
| `first_name` | VARCHAR | First name |
| `last_name` | VARCHAR | Last name |
| `faction` | VARCHAR | Parliamentary group (e.g. `CDU/CSU`, `SPD`, `AfD`) |

**`speeches`** — one row per speech segment:

| column | type | description |
|---|---|---|
| `id` | INTEGER | Auto-incremented row ID |
| `session` | VARCHAR | Session number (e.g. `21083`) |
| `electoral_term` | INTEGER | Wahlperiode |
| `date` | DATE | Date of the sitting |
| `politician_id` | INTEGER | Bundestag ID (`-1` if unresolved) |
| `first_name` | VARCHAR | Speaker first name |
| `last_name` | VARCHAR | Speaker last name |
| `faction` | VARCHAR | Parliamentary group |
| `position_short` | VARCHAR | Role category (`Member of Parliament`, `Minister`, `Chancellor`, `Presidium of Parliament`, `Guest`) |
| `position_long` | VARCHAR | Full role title where applicable (e.g. `Bundesminister der Finanzen`) |
| `speech_content` | TEXT | Full verbatim speech text |

---

### Where it is stored

```
data/
└── term_21/          ← raw XML files (one per session, ~500 KB each)
    ├── 21001.xml
    ├── 21002.xml
    └── …

openbundestag-data.db     ← DuckDB file, query with any DuckDB client
```

The `data/` directory is the download cache. Re-running `--phase extract` skips files that already exist. The DuckDB file is a single binary you can copy, share, or open directly in tools like [DBeaver](https://dbeaver.io/) or the [DuckDB CLI](https://duckdb.org/docs/api/cli).

### Pre-built database

A pre-built `openbundestag-data.db` (~2 GB, all terms, finalized) is published on Hugging Face:
[`MissionJupiter/openbundestag-db`](https://huggingface.co/datasets/MissionJupiter/openbundestag-db)

Download it without running the pipeline:

```sh
uv sync
uv run hf download MissionJupiter/openbundestag-db openbundestag-data.db --repo-type dataset --local-dir .
```

Place the file in the project root, then run the app normally. Skip everything in [Quick start](#quick-start) below.

---

## Frontend

A Streamlit app (`app.py`) lets you explore word usage interactively in the browser — no coding required after setup.

### Launch

```sh
uv run streamlit run app.py
```

Opens at `http://localhost:8501` automatically.

### What it does

Type any keyword or phrase into the sidebar search box and the app queries the local DuckDB file in real time. Results appear across three tabs:

**📈 Timeline** — line chart of how often the word appeared per month or quarter, one line per party. Toggle to a stacked area chart. Granularity (monthly / quarterly) and count mode (speeches / raw word occurrences) are configurable in the sidebar.

**🥧 By party** — horizontal bar chart and pie chart showing which parties used the word most, plus a stacked bar chart over time so you can see how the party breakdown shifted.

**🎤 Top politicians** — ranked bar chart of the individual MPs who mentioned the word most, coloured by party.

### Filters (sidebar)

| Filter | Description |
|---|---|
| Keyword | Required. Substring match — `Klima` also catches `Klimawandel`, `Klimaschutz`, etc. |
| Party | Multiselect. Leave empty for all parties. |
| Electoral term | Filter to any Wahlperiode 1–21, or any combination. |
| Politician | Dropdown search over all known MPs. |

### Party colours

Parties are rendered in their official colours throughout all charts:

| Party | Colour |
|---|---|
| CDU/CSU | Black `#000000` |
| SPD | Red `#E3000F` |
| AfD | Blue `#009EE0` |
| Bündnis 90/Die Grünen | Green `#1AA037` |
| FDP | Yellow `#FFED00` |
| Die Linke | Purple `#BE3075` |
| BSW | Wine red `#9B2335` |

---

## Quick start

```sh
# Install dependencies
uv sync

# Run the full pipeline for Wahlperiode 20 (default)
uv run run.py --phase all

# Or step by step
uv run run.py --phase extract --term 20
uv run run.py --phase transform --term 20
uv run run.py --phase load --term 20
uv run run.py --phase finalize          # materialise derived columns the app reads
```

The database is written to `openbundestag-data.db` in the project root.

The **finalize** phase (run automatically as part of `--phase all`) precomputes
two columns the Streamlit app reads on every request:

- `faction_normalized` — the resolved party per speech (deterministic), so the
  app never recomputes the faction fallback at query time;
- `search_text` — `lower(speech_content)`, so substring search scans a
  pre-lowered column (~5× faster than calling `lower()` over ~1.8 GB per query).

Run it after `load` **and** `ministers` (the faction fallback reads the
ministers table). By default `speech_content` stays inline in `speeches` and
the reader has full original-cased text. Pass `--text-table` to move it to a
`speech_texts(id, speech_content)` side table — the leaner `speeches` table
is faster for analytical aggregations while the reader JOINs on demand.

---

## CLI reference

```
uv run run.py [OPTIONS]

Options:
  --phase [extract|transform|load|ministers|finalize|all]
                                         Pipeline phase to execute.  [default: all]
  --term  INTEGER                        Wahlperiode to process.      [default: 20]
  --db    TEXT                           DuckDB output file.          [default: openbundestag-data.db]
  --data-dir TEXT                        Raw XML download directory.  [default: data]
  --text-table                           In finalize, move original-cased text
                                         to a speech_texts side table.[default: off]
```

**Supported Wahlperioden:** 1–21 (terms 19–21 use structured XML; terms 1–18 use the legacy ZIP archives).

---

## Repository structure

```
openbundestag/
├── pyproject.toml      # uv project config, dependencies
├── run.py              # CLI entrypoint
├── app.py              # Streamlit frontend
├── src/
│   ├── extract.py      # Download XML/ZIP from Bundestag open-data endpoints
│   ├── transform.py    # Parse XML → speakers + speeches DataFrames
│   ├── load.py         # Write DataFrames into DuckDB + finalize derived columns
│   └── queries.py      # Shared query layer (used by app.py AND api/)
├── api/                # FastAPI JSON service (HF Space)
├── web/                # SvelteKit website (Cloudflare Pages)
└── openbundestag-data.db   # Generated output (git-ignored)
```

---

## Website (dedicated public site)

Beyond the Streamlit app there is a bespoke website: a **SvelteKit** frontend
(`web/`) with a scrollytelling intro and a live explorer, backed by a small
**FastAPI** service (`api/`) over the same DuckDB query engine (`src/queries.py`).
It uses a committed dark **"data-noir"** design — an obsidian canvas where the
official party colours glow, an aurora gradient accent, glass panels, animated
stat count-ups and chart draw-ins. All free to host:

- **Frontend** → Cloudflare Pages (unlimited bandwidth, free custom domain + SSL)
- **API** → a Hugging Face Space (CPU Basic: 2 vCPU / 16 GB RAM)
- **Database** → the same public HF Dataset, downloaded by the API at startup

### Run it locally

The site needs **two processes**: the API (which reads your local
`openbundestag-data.db`) and the SvelteKit dev server. Run each in its own terminal
from the repository root.

**Prerequisites:** a built `openbundestag-data.db` (see [Quick start](#quick-start)),
plus [Node.js](https://nodejs.org/) ≥ 20 and `npm` for the frontend.

**1. Start the API** (reads `openbundestag-data.db`, pre-warms it — takes a few seconds):

```sh
uv run uvicorn api.main:app --port 8000
```

Wait for `Application startup complete`, then verify it at
<http://127.0.0.1:8000/health> → `{"status":"ok",...}`.

**2. Start the website** (new terminal):

```sh
cd web
npm install          # first time only
npm run dev
```

Open **<http://localhost:5173>**. The frontend is already pointed at the local
API via `web/.env` (`PUBLIC_API_BASE=http://127.0.0.1:8000`; copy from
`web/.env.example` if missing).

Notes:
- **Order doesn't matter.** If the API isn't up yet, the explorer shows a
  "waking the database…" state and connects automatically once it is.
- **Drill-down** is live: click any point on the timeline to open a modal of the
  matching speeches, expand one to read its full text with the keyword
  highlighted, and download it as a formatted `.txt` extract. Both the default
  finalize build (inline `speech_content`) and `--text-table` builds give
  original-cased full text in the reader.
- Stop either server with `Ctrl-C`.

See [`web/README.md`](web/README.md) and [`api/README.md`](api/README.md).

---

## Database schema

```sql
-- Unique politicians derived from speech metadata
CREATE TABLE speakers (
    id           INTEGER PRIMARY KEY,  -- official Bundestag politician ID
    first_name   VARCHAR,
    last_name    VARCHAR,
    faction      VARCHAR
);

-- One row per speech segment
CREATE TABLE speeches (
    id             INTEGER PRIMARY KEY,
    session        VARCHAR,
    electoral_term INTEGER,
    date           DATE,
    politician_id  INTEGER,
    first_name     VARCHAR,
    last_name      VARCHAR,
    faction        VARCHAR,
    position_short VARCHAR,   -- e.g. "Member of Parliament", "Minister"
    position_long  VARCHAR,   -- full role description
    speech_content TEXT
);
```

---

## Example queries

```python
import duckdb

con = duckdb.connect("openbundestag-data.db")

# Top speakers by number of speeches
con.sql("""
    SELECT first_name, last_name, faction, COUNT(*) AS speeches
    FROM speeches
    GROUP BY 1, 2, 3
    ORDER BY speeches DESC
    LIMIT 10
""").show()

# Full-text search
con.sql("""
    SELECT date, first_name, last_name, speech_content
    FROM speeches
    WHERE speech_content LIKE '%Klimawandel%'
    ORDER BY date DESC
""").show()
```

---

## Database distribution

This section documents how the pre-built database is published and how deployed services receive it — useful if you are maintaining the project or setting up a fork.

### Lifecycle

```
Pipeline (local)  →  HF Dataset repo  →  HF Space / API Space (at startup)
```

1. **Build locally** — run the full pipeline to produce `openbundestag-data.db`:
   ```sh
   uv run run.py --phase all --term 20   # or loop over all terms
   uv run run.py --phase ministers
   uv run run.py --phase finalize
   ```

2. **Upload to the public dataset** — push the finished file to
   [`MissionJupiter/openbundestag-db`](https://huggingface.co/datasets/MissionJupiter/openbundestag-db):
   ```sh
   uv run hf auth login          # once — stores token in ~/.cache/huggingface
   uv run hf upload MissionJupiter/openbundestag-db openbundestag-data.db openbundestag-data.db --repo-type dataset
   ```
   This is a **manual step** — no CI workflow uploads the DB. The file is ~2 GB
   and is git-ignored; it never passes through GitHub.

3. **Spaces download it at startup** — both the Streamlit Space and the API Space
   have `HF_DB_REPO=MissionJupiter/openbundestag-db` set as an environment variable
   in their Dockerfiles. On first boot (or after an ephemeral disk reset), the app
   calls `huggingface_hub.hf_hub_download()` to pull the file into the container
   cache. Subsequent restarts reuse the cached file until the container is recycled.

### CI / what GitHub Actions does and does not do

| Workflow | Trigger | What it ships |
|---|---|---|
| `deploy.yml` | push to `main` (app files) | `app.py`, `src/queries.py`, `.streamlit/`, `deploy/hf/` → Streamlit Space |
| `deploy-api.yml` | push to `main` (api/src files) | `api/`, `src/queries.py`, `Dockerfile` → API Space |
| `deploy-web.yml` | push to `main` (web files) | `web/` build → Cloudflare Pages |

**None of these workflows touch the dataset repo.** The 2 GB DB is never shipped
by CI — only the application code is. The dataset upload is always a manual
`hf upload` step performed after a pipeline rebuild.

---

## Future ideas

Potential features for the web explorer, roughly ordered by implementation effort:

### Keyword comparison overlay
Let the user enter two keywords and overlay them on the same timeline — classic ngram-viewer style. Reuses the existing `/api/timeline` endpoint; the frontend just fires two requests and renders both series on one chart.

### Party vocabulary divergence
Given a keyword, show which parties use it *more* or *less* than their overall speech-share would predict — a divergence bar ("CDU uses this word 2× more than expected"). Computable from `/api/by-party` + `/api/total`.

### Collocate / n-gram tab
A tab on the explorer that shows which words appear most often *near* the search term (within ±N words in the same speech). Surfaces thematic context — e.g. what issues consistently co-occur with "Klimawandel". Requires a new SQL query using string splitting or a pre-built co-occurrence index.

### "Word first appeared" tracker
Surface the very first Bundestag mention of a term: date, session, and speaker. Good for landing-page storytelling and already derivable from a single `MIN(date)` query.

### Speaker language fingerprint
For a selected politician, rank their *distinctive* vocabulary using TF-IDF against the full corpus — what words set them apart from other speakers. Pairs with the existing politician typeahead.

### Session heat map
Calendar or term-grid heat map showing which sessions had the highest keyword density — useful for spotting event-driven spikes (oil crisis, reunification, pandemic).

---

## Contributing

Contributions are welcome. Please open an issue or pull request.

---

## Data licence & attribution

The speech transcripts are the official plenary protocols (*Plenarprotokolle*) of the German Bundestag, published on the [Bundestag Open Data portal](https://www.bundestag.de/services/opendata).

As official parliamentary documents they are classified as *amtliche Werke* under **§ 5 Abs. 1 UrhG** (German Copyright Act) and are therefore not subject to copyright protection.

**Required attribution when publishing:** © Deutscher Bundestag — [www.bundestag.de/services/opendata](https://www.bundestag.de/services/opendata)

The data may be used freely for reporting, educational, and research purposes. Commercial advertising use is not permitted under the Bundestag's [terms of use](https://www.bundestag.de/nutzungsbedingungen).

Minister biographical data is sourced from Wikipedia under the [Creative Commons Attribution-ShareAlike 4.0 licence (CC BY-SA 4.0)](https://creativecommons.org/licenses/by-sa/4.0/).

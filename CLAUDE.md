# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

OpenBundestag is a standalone data pipeline + Streamlit app for exploring word usage across German Bundestag plenary debates (1949–present, ~760,000 speeches). It is an independent derivative reimplementation of [Open Discourse](https://opendiscourse.de/). No Docker/PostgreSQL/Node needed locally — everything flattens into a single DuckDB file (`open_discourse.db`, ~2 GB, git-ignored).

## Commands

```sh
uv sync                                  # install deps (uses uv.lock)
uv run streamlit run app.py              # run the app at http://localhost:8501

# Pipeline (build the DB). Default term is 20.
uv run run.py --phase all --term 20          # extract → transform → load → ministers → finalize → zwischenrufe
uv run run.py --phase extract --term 20      # download raw XML/ZIP only
uv run run.py --phase finalize               # rebuild derived columns (speech_content stays inline)
uv run run.py --phase finalize --text-table  # move speech_content to speech_texts side table (leaner speeches table, reader still works)
uv run run.py --phase zwischenrufe --term 20 # (re-)extract interjections for a term (needs finalize first)

uv run flake8 src app.py                 # lint (config in .flake8; E203/W503 ignored)
```

There is no test suite. `playwright` is a dev dependency used by the extract phase, not for testing.

## Pipeline architecture (`run.py` + `src/`)

`run.py` is a Click CLI that runs phases in order. The phases are sequential and pass DataFrames in memory (transform → load) within a single invocation:

- **extract** (`src/extract.py`) — Downloads session files from hardcoded Bundestag Open Data endpoints (`FILTERLIST_URLS` for modern terms 19–21, `LEGACY_ZIP_URLS` for terms 1–18). The Bundestag site has bot protection, so downloads are delegated to a **Playwright subprocess** (`src/_pw_download.py`, invoked via `subprocess.run`). Re-entrant: already-downloaded files are skipped. Output goes to `data/term_XX/`.
- **transform** (`src/transform.py`) — Parses XML → `speakers` + `speeches` DataFrames. Two code paths auto-selected by `_is_modern()`: modern terms use structured `dbtplenarprotokoll` XML (`parse_session`); legacy terms 1–18 use regex-based speaker detection over text-heavy XML (`parse_legacy_session`). `_match_faction` and `_classify_position` normalize party/role.
- **load** (`src/load.py`) — `init_db` creates the schema; `load_data` writes speakers/speeches; `load_ministers` writes minister tables.
- **ministers** (`src/scrape_ministers.py`) — Scrapes German minister/role data from Wikipedia (CC BY-SA). Needed before finalize because the faction fallback references the ministers table.
- **finalize** (`src/load.py::finalize_db`) — Materializes two derived columns the app reads on every request: `faction_normalized` (resolved party, via `FACTION_NORMALIZE_SQL`) and `search_text` (`lower(speech_content)`). This is a performance phase — it moves the faction CASE logic and `lower()` out of the per-query read path (~5× faster). Must run **after** both load and ministers.
- **zwischenrufe** (`src/zwischenrufe.py`) — Extracts parliamentary interjections into a dedicated `zwischenrufe` table. Modern terms (19+): re-reads the XML and pulls `<kommentar>` elements (direct children of `<rede>`), which the main transform discards. Legacy terms (1–18): parses parenthetical remarks from the stored `speech_content`. Each segment is classified as `Zwischenruf` (attributed heckling with text + name + party), `Beifall`, `Heiterkeit`, `Lachen`, `Widerspruch`, `Zuruf`, or `Zustimmung`. Must run **after finalize** (needs `faction_normalized` for `target_speaker_party`). Idempotent per term (deletes then re-inserts). Query functions in `src/queries.py`: `query_zwischenrufe_timeline`, `query_top_zwischenrufer`, `query_zwischenrufe_by_caller_party`, `query_interruption_matrix`, `query_zwischenrufe_samples`.

The two main tables are `speakers` (one row per politician) and `speeches` (one row per speech segment). The `zwischenrufe` table has one row per reaction segment with columns: `speech_id`, `electoral_term`, `session`, `date`, `target_speaker_id`, `target_speaker_party`, `type`, `caller_name`, `caller_party`, `text`, `raw`. See README.md for full column-level schema.

## App architecture (`app.py`)

Single-file Streamlit app, ~760 lines. Key conventions:

- **DB resolution:** `DB_PATH` env var (default `openbundestag-data.db`). `_ensure_db()` (cached `@st.cache_resource`) downloads the DB from a public HF Dataset repo (`HF_DB_REPO` / `HF_DB_FILE`) when the local file is absent — this is how the deployed Space gets its data. `get_connection()` verifies the finalize-phase derived columns exist and pre-warms the page cache.
- **All SQL is parameterized** via `_build_conditions()` — keep it that way (the SQL-injection fix was deliberate). Never f-string user input into queries.
- **Query functions** (`query_timeline`, `query_by_party`, `query_top_politicians`, `query_total`) are all `@st.cache_data(ttl=3600)`. They read `faction_normalized` / `search_text`, NOT raw `speech_content` — the app never displays raw text, which is why `--slim` can drop it.
- **i18n:** `t(key, lang, ...)` translation helper; the app is bilingual (DE/EN).
- **Party colours** are official and consistent across all charts — see the colour map in README.md and helpers `color_sequence` / `full_color_map` / `expand_party_names`.
- Use `width='stretch'` on Plotly charts, not the deprecated `use_container_width=True`.

## Website (`web/` + `api/`) — the dedicated public site

A second frontend beyond Streamlit, built on the `feature/web` branch. Three pieces:

- **`src/queries.py`** — the **shared query layer**, the single source of truth for the SQL and DB connection logic. Streamlit-free, takes a DuckDB connection. Both `app.py` and `api/main.py` import it; `app.py`'s `query_*`/`load_*` functions are now thin `@st.cache_data` wrappers that delegate here. Reference data (`PARTY_COLORS`, `PARTY_FULL_NAMES`, `HISTORICAL_PARTIES`, `TERM_LABELS`, `FACTION_COL`, `SEARCH_COL`) lives here too. **Edit SQL here, not in app.py.**
- **`api/`** — FastAPI JSON service over `src/queries.py` (run: `uv run uvicorn api.main:app --port 8000`). Endpoints: `/api/{meta,politicians,timeline,by-party,top-politicians,total,speeches,speech/{id}}` + `/health`. Deploys to its own HF Space (Docker). Note: it opens **one** DuckDB connection at startup and hands out `_con.cursor()` per request — DuckDB connections are not safe for concurrent `execute()`, and the frontend fires the four queries in parallel.
- **`web/`** — SvelteKit 5 (runes) + adapter-cloudflare. Landing (`/`) is a scrollytelling intro backed by a precomputed `src/lib/stories.json` (regenerate from the DB if the corpus changes); explorer (`/explore`, SSR off) is the live tool. API base is `PUBLIC_API_BASE` (`$env/static/public`; set in `web/.env` — copy from `.env.example`, else `svelte-kit sync` can't generate the module and `npm run check` fails). Reactive state uses runes — module-level stores that use `$state` must be `.svelte.ts` files (e.g. `i18n.svelte.ts`). Charts are bespoke SVG using `d3-scale`/`d3-shape` (no chart lib). Dev: `cd web && npm run dev`; checks: `npm run check`. **Do not switch frameworks** (the design ceiling here is craft, not capability — Svelte's native transitions + fine-grained reactivity suit the animated dashboard well).

**Design system (`web/src/app.css`):** one committed **dark "data-noir"** theme — obsidian canvas (`--bg #07080c`), a single aurora gradient accent (`--grad`, periwinkle→violet→rose) used for the brand mark, buttons, headlines, chart accents; glass panels (`.glass`), Space Grotesk (display + numerals) + Inter (data/UI). **No beige** — the old editorial/paper look was deliberately replaced (Florian's call). Legacy token names (`--paper`/`--card`/`--serif`) are kept only as aliases to the dark tokens so older components stay coherent; prefer the new tokens (`--bg`, `--surface`, `--ink`, `--line`, `--display`, `--spring`) in new code. Party colours stay official, but near-black ones (CDU/CSU `#000000`) vanish on dark, so `partyColor()` in `format.ts` auto-lifts only the darkest colours via `darkSafe()`. `countUp()` (also in `format.ts`) powers the animated stat `Counter.svelte`.

**Explorer layout:** no hidden tabs — the timeline is the full-bleed hero (`TimelineChart.svelte`: glowing draw-in lines, gradient stacked areas, legend-hover dimming, click-anywhere-to-drill), with animated metric cards and the by-party + top-speaker panels surfaced together below.

**Drill-down (implemented):** clicking a timeline point opens `SpeechModal.svelte` — a centered glass modal listing matching speeches; each expands inline to the full text with the keyword `<mark>`-highlighted (fetched on demand via `/api/speech/{id}`) and a Download button that emits a richly-formatted `.txt` extract (all metadata + passage). Passage text comes from inline `speech_content` (default finalize) or the `speech_texts` side table (`--text-table` finalize) — always original-cased. A truly empty `speech_content` still shows the "no text stored" note.

**Hosting (all free):** site → Cloudflare Pages (`deploy-web.yml`, free custom domain); API → HF Space (`deploy-api.yml`, 16 GB RAM); DB → public HF Dataset. A fork can be split out later; `web/` and `api/` are self-contained at the repo root.

## Deployment

Deploys to Hugging Face Spaces via `.github/workflows/deploy.yml` (triggers on app-relevant file changes + manual dispatch; requires `HF_TOKEN` secret). CI ships only the Space files (`app.py`, `requirements.txt`, `.streamlit/`, `deploy/hf/{Dockerfile,README.md}`) to the Space repo — **the 2 GB DB is NOT shipped by CI**; it lives in a public HF Dataset and is downloaded by the app at startup. `requirements.txt` (not `pyproject.toml`) drives the deploy install and adds `huggingface_hub` for that download.

## Notes

- `ROADMAP.md` tracks planned/in-progress work and completed phases — check it before starting deployment/perf work.
- `requirements.txt` and `pyproject.toml` are intentionally separate: `pyproject.toml`/`uv.lock` is the local dev environment; `requirements.txt` is the slim runtime set for the HF Space.

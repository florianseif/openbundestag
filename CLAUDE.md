# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

OpenBundestag is a standalone data pipeline + FastAPI/SvelteKit web app for exploring word usage across German Bundestag plenary debates (1949–present, ~760,000 speeches). It is an independent derivative reimplementation of [Open Discourse](https://opendiscourse.de/). No Docker/PostgreSQL needed locally — everything flattens into a single DuckDB file (`openbundestag-data.db`, git-ignored; ≈4.3 GB after the `optimize` phase, ≈6 GB before).

## Commands

```sh
uv sync                                  # install deps (uses uv.lock)
uv run uvicorn api.main:app --port 8000  # run the API at http://localhost:8000

# Pipeline (build the DB). Default term is 21.
uv run run.py --phase all --term 21          # one term: extract → transform → load → ministers → stammdaten → finalize → legacy-match → zwischenrufe → optimize
uv run run.py --phase all --all-terms        # rebuild the WHOLE DB (all terms 1–21) in one command — skips extract, builds from already-downloaded data
uv run run.py --phase load --all-terms       # run a single phase for every term (per-term phases loop; global phases run once)
uv run run.py --phase extract --all-terms    # (re)download every term (the bot-protected Playwright step, kept separate from the quick rebuild)
uv run run.py --phase extract --term 21      # download raw XML/ZIP only
uv run run.py --phase finalize               # rebuild derived columns (speech_content stays inline)
uv run run.py --phase finalize --text-table  # move speech_content to speech_texts side table (leaner speeches table, reader still works)
uv run run.py --phase stammdaten             # (re-)download MdB-Stammdaten XML + rebuild politician registry tables
uv run run.py --phase legacy-match           # resolve politician_id for legacy terms 1–18 (needs stammdaten + finalize)
uv run run.py --phase zwischenrufe --term 20 # (re-)extract interjections for a term (needs finalize first)
uv run run.py --phase optimize               # rewrite into the compact "Option C" layout — shrinks the file ~30% (6.2→4.3 GB), run LAST

uv run flake8 src api                    # lint (config in .flake8; E203/W503 ignored)
```

There is no test suite. `playwright` is a dev dependency used by the extract phase, not for testing.

## Pipeline architecture (`run.py` + `src/`)

`run.py` is a Click CLI that runs phases in order. The phases are sequential and pass DataFrames in memory (transform → load) within a single invocation. **`--all-terms`** processes every term (1–21) instead of a single `--term`: with `--phase all` it rebuilds the entire DB in one command (per-term `load` for each term → the global phases once → per-term `zwischenrufe` → `optimize`), interleaving in strict dependency order; with a single per-term phase it loops that phase over all terms, while a global phase (`ministers`/`stammdaten`/`finalize`/`legacy-match`/`optimize`) runs exactly once. `--phase all --all-terms` deliberately **skips extract** (re-entrant, bot-protected, slow) so the rebuild is quick on data you already have — run `--phase extract --all-terms` first to download. The full-build dependency order is **extract → transform → load → ministers → stammdaten → finalize → legacy-match → zwischenrufe → optimize** (`_run_full_build`):

- **extract** (`src/extract.py`) — Downloads session files from hardcoded Bundestag Open Data endpoints (`FILTERLIST_URLS` for modern terms 19–21, `LEGACY_ZIP_URLS` for terms 1–18). The Bundestag site has bot protection, so downloads are delegated to a **Playwright subprocess** (`src/_pw_download.py`, invoked via `subprocess.run`). Re-entrant: already-downloaded files are skipped. Output goes to `data/term_XX/`.
- **transform** (`src/transform.py`) — Parses XML → `speakers` + `speeches` DataFrames. Two code paths auto-selected by `_is_modern()`: modern terms use structured `dbtplenarprotokoll` XML (`parse_session`); legacy terms 1–18 use regex-based speaker detection over text-heavy XML (`parse_legacy_session`). `_match_faction` and `_classify_position` normalize party/role.
- **load** (`src/load.py`) — `init_db` creates the schema; `load_data` writes speakers/speeches; `load_ministers` writes minister tables.
- **ministers** (`src/scrape_ministers.py`) — Scrapes German minister/role data from Wikipedia (CC BY-SA). Needed before finalize because the faction fallback references the ministers table.
- **finalize** (`src/load.py::finalize_db`) — Materializes two derived columns the API reads on every request: `faction_normalized` (resolved party, via `FACTION_NORMALIZE_SQL`) and `search_text` (`lower(speech_content)`). This is a performance phase — it moves the faction CASE logic and `lower()` out of the per-query read path (~5× faster). Must run **after load, ministers, AND stammdaten** — `FACTION_NORMALIZE_SQL`'s last-resort faction fallback reads the `politician_terms` table that stammdaten builds (a fresh build errors with "Table politician_terms does not exist" if finalize runs first).
- **stammdaten** (`src/extract.py::download_stammdaten` + `src/stammdaten.py::build_registry`) — Downloads the official MdB-Stammdaten ZIP from bundestag.de (no bot protection, plain urllib), extracts `MDB_STAMMDATEN.XML`, and flattens it into two DuckDB tables: `politicians` (one row per name variant with `id, last_name, first_name, name_von, name_bis`) and `politician_terms` (one row per member/term with `id, electoral_term, faction`). Also creates the `_registry_names` view (canonical display name per member, newest-valid variant). The official 8-digit MdB IDs in the Stammdaten are the same namespace used by the modern term XML, so a member active across the 18/19 boundary gets one identity. Fully idempotent (re-entrant download, tables are DROPped and recreated). Must run **after load + ministers but BEFORE finalize** — finalize's `FACTION_NORMALIZE_SQL` reads the `politician_terms` table this phase creates. (It does not itself read speech/faction data, so it has no dependency on finalize.)
- **legacy-match** (`src/match_legacy.py::match_legacy`) — Resolves `politician_id` for legacy speeches (terms 1–18) which the transform phase leaves at the sentinel `-1`. Uses a conservative tiered match against the Stammdaten registry: (1) unique surname in term, (2) surname + faction, (3) surname + first name, (4) surname + first initial — only assigns an ID when exactly one candidate survives. Broken-parse recovery swaps `last_name`/`first_name` when the surname field is punctuation or too short. Achieved ~97% coverage (686k/705k speeches) with zero forced assignments. Unresolved speakers are logged to `legacy_match_unresolved` table and a `.legacy_unresolved.csv` sidecar for audit. Idempotent (only updates rows where `politician_id = -1`). Must run **after stammdaten** (needs registry) and **after finalize** (needs `faction_normalized`).
- **zwischenrufe** (`src/zwischenrufe.py`) — Extracts parliamentary interjections into a dedicated `zwischenrufe` table. Modern terms (19+): re-reads the XML and pulls `<kommentar>` elements (direct children of `<rede>`), which the main transform discards. Legacy terms (1–18): parses parenthetical remarks from the stored `speech_content`. Each segment is classified as `Zwischenruf` (attributed heckling with text + name + party), `Beifall`, `Heiterkeit`, `Lachen`, `Widerspruch`, `Zuruf`, or `Zustimmung`. Must run **after finalize** (needs `faction_normalized` for `target_speaker_party`). Idempotent per term (deletes then re-inserts). Query functions in `src/queries.py`: `query_zwischenrufe_timeline`, `query_top_zwischenrufer`, `query_zwischenrufe_by_caller_party`, `query_interruption_matrix`, `query_zwischenrufe_samples`.
- **optimize** (`src/load.py::optimize_db`) — The final, file-shrinking phase. Rewrites the finalized DB into the compact **"Option C"** layout in a fresh file, then atomically renames it over the original (the only reliable way to actually shrink the on-disk size — DuckDB reuses freed blocks but never shrinks in place after the big in-place `UPDATE`/`DROP COLUMN` finalize performs). Result: `speeches` keeps metadata + `faction_normalized` + `search_text` (lowercased) but **no inline `speech_content`**, while `speech_texts(id, speech_content)` holds the original-cased text for the reader. This eliminates the duplicate full-text copy that `--text-table` alone still kept (`search_text` *and* `speech_content`), cutting the file ~30% (≈6.2 → 4.3 GB) with no change to query semantics or data. Input-agnostic (works whether `speech_content` was inline or already in `speech_texts`) and idempotent. Must run **LAST**, after every phase that writes to the DB.

The two main tables are `speakers` (one row per politician) and `speeches` (one row per speech segment). The `zwischenrufe` table has one row per reaction segment with columns: `speech_id`, `electoral_term`, `session`, `date`, `target_speaker_id`, `target_speaker_party`, `type`, `caller_name`, `caller_party`, `text`, `raw`. See README.md for full column-level schema.

## Website (`web/` + `api/`)

Three pieces:

- **`src/queries.py`** — the **shared query layer**, the single source of truth for the SQL and DB connection logic. Takes a DuckDB connection. `api/main.py` imports it. Reference data (`PARTY_COLORS`, `PARTY_FULL_NAMES`, `HISTORICAL_PARTIES`, `TERM_LABELS`, `FACTION_COL`, `SEARCH_COL`) lives here too. **Edit SQL here.**
- **`api/`** — FastAPI JSON service over `src/queries.py` (run: `uv run uvicorn api.main:app --port 8000`). Endpoints: `/api/{search,meta,politicians,timeline,by-party,top-politicians,by-term,total,speeches,speech/{id}}` + `/health`. **`/api/search` is the explorer's hot path** — it computes total + timeline + by-party + by-term + top-politicians in a **single** text scan (`q.search`, via a per-cursor `TEMP TABLE` matched set) and is what the explorer calls per keystroke. The older per-view endpoints stay for compatibility/drill-down. Deploys to its own HF Space (Docker). Note: it opens **one** DuckDB connection at startup and hands out `_con.cursor()` per request — DuckDB connections are not safe for concurrent `execute()`; the single combined request means there's no longer a fan-out of four parallel scans contending for the same column/cores.
- **`web/`** — SvelteKit 5 (runes) + adapter-cloudflare. Landing (`/`) is a scrollytelling intro backed by a precomputed `src/lib/stories.json` (regenerate from the DB if the corpus changes); explorer (`/explore`, SSR off) is the live tool. API base is `PUBLIC_API_BASE` (`$env/static/public`; set in `web/.env` — copy from `.env.example`, else `svelte-kit sync` can't generate the module and `npm run check` fails). Reactive state uses runes — module-level stores that use `$state` must be `.svelte.ts` files (e.g. `i18n.svelte.ts`). Charts are bespoke SVG using `d3-scale`/`d3-shape` (no chart lib). Dev: `cd web && npm run dev`; checks: `npm run check`. **Do not switch frameworks** (the design ceiling here is craft, not capability — Svelte's native transitions + fine-grained reactivity suit the animated dashboard well).

**Design system (`web/src/app.css`):** one committed **dark "data-noir"** theme — obsidian canvas (`--bg #07080c`), a single aurora gradient accent (`--grad`, periwinkle→violet→rose) used for the brand mark, buttons, headlines, chart accents; glass panels (`.glass`), Space Grotesk (display + numerals) + Inter (data/UI). **No beige** — the old editorial/paper look was deliberately replaced (Florian's call). Legacy token names (`--paper`/`--card`/`--serif`) are kept only as aliases to the dark tokens so older components stay coherent; prefer the new tokens (`--bg`, `--surface`, `--ink`, `--line`, `--display`, `--spring`) in new code. Party colours stay official, but near-black ones (CDU/CSU `#000000`) vanish on dark, so `partyColor()` in `format.ts` auto-lifts only the darkest colours via `darkSafe()`. `countUp()` (also in `format.ts`) powers the animated stat `Counter.svelte`.

**Explorer layout:** no hidden tabs — the timeline is the full-bleed hero (`TimelineChart.svelte`: glowing draw-in lines, gradient stacked areas, legend-hover dimming, click-anywhere-to-drill), with animated metric cards and the by-party + top-speaker panels surfaced together below.

**Drill-down (implemented):** clicking a timeline point opens `SpeechModal.svelte` — a centered glass modal listing matching speeches; each expands inline to the full text with the keyword `<mark>`-highlighted (fetched on demand via `/api/speech/{id}`) and a Download button that emits a richly-formatted `.txt` extract (all metadata + passage). Passage text comes from inline `speech_content` (default finalize) or the `speech_texts` side table (`--text-table` finalize) — always original-cased. A truly empty `speech_content` still shows the "no text stored" note.

**Hosting (all free):** site → Cloudflare Pages (`deploy-web.yml`, free custom domain); API → HF Space (`deploy-api.yml`, 16 GB RAM); DB → public HF Dataset. `web/` and `api/` are self-contained at the repo root.

## Deployment

API deploys to Hugging Face Spaces via `.github/workflows/deploy-api.yml` (requires `HF_TOKEN` secret). The DB (~4.3 GB, post-`optimize`) is NOT shipped by CI — it lives in a public HF Dataset and is downloaded by the API at startup via `src/queries.py::resolve_db_path`. After rebuilding the corpus, run `--phase optimize` and re-upload the compacted file to the Dataset.

Web deploys to Cloudflare Pages via `.github/workflows/deploy-web.yml`.

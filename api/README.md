---
title: OpenBundestag API
emoji: 🏛️
colorFrom: blue
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
license: mit
---

# OpenBundestag API

JSON query API over ~760,000 German Bundestag plenary speeches (1949–present),
backing the [OpenBundestag](https://www.bundestag.de/services/opendata) explorer
frontend. It is a thin [FastAPI](https://fastapi.tiangolo.com/) layer over the
shared DuckDB query engine in `src/queries.py` (the same SQL the Streamlit app
uses).

On first boot the Space downloads the ~2 GB DuckDB file once from the public HF
Dataset (`HF_DB_REPO`) and pre-warms the OS page cache, so the first search is
~100 ms warm.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Liveness + whether raw speech text is present |
| GET | `/api/meta` | Date range, party list/colours, electoral terms |
| GET | `/api/politicians?q=` | MP typeahead |
| GET | `/api/timeline` | Word usage over time, per party |
| GET | `/api/by-party` | Speech counts per party |
| GET | `/api/top-politicians` | Ranked MPs for a keyword |
| GET | `/api/total` | Summary count + first/last mention |
| GET | `/api/speeches` | Matched speech segments (drill-down; snippet needs non-slim DB) |
| GET | `/api/speech/{id}` | Full speech (download; text needs non-slim DB) |

Common query params: `word` (required, ≤80 chars), `parties` (repeatable),
`terms` (repeatable), `politician_id`, `date_from`, `date_to`.

## Configuration (env)

| Var | Default | Notes |
|---|---|---|
| `DB_PATH` | `open_discourse.db` | Local DB path |
| `HF_DB_REPO` | — | Public HF Dataset to pull the DB from when absent |
| `HF_DB_FILE` | `open_discourse.db` | File within that dataset |
| `ALLOWED_ORIGINS` | `*` | Comma-separated CORS origins (set to the site URL) |

> **Drill-down note:** snippet/full text is only returned when the deployed DB
> retains the raw `speech_content` column (i.e. **not** built with `--slim`).

## Run locally

```sh
uv run uvicorn api.main:app --reload --port 8000
```

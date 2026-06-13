# OpenBundestag — Roadmap / open work

Running notes on work planned but not yet done, so it's easy to pick up later.
Phases 1 and 2 are largely complete; their leftover manual steps and the
remaining phases are tracked below.

Last updated: 2026-06-13

---

## ✅ Done

- **Phase 5 — Dedicated website (branch `feature/web`).** Bespoke **SvelteKit**
  site (`web/`) — scrollytelling landing + live explorer — over a new **FastAPI**
  service (`api/`), both fed by a shared query layer extracted into
  `src/queries.py` (app.py now delegates to it). Frontend → Cloudflare Pages,
  API → its own HF Space, DB → existing public HF Dataset. CI added:
  `deploy-web.yml` (Cloudflare Pages) + `deploy-api.yml` (HF Space); the existing
  Streamlit `deploy.yml` now also ships `src/queries.py`. Drill-down (click a
  point → read passage → download) is API-architected (`/api/speeches`,
  `/api/speech/{id}`) with a drawer shell in the UI; the reader/download UI is
  the next step.
- **Phase 1 — SQL injection fix.** All DuckDB queries parameterized via
  `_build_conditions()` in `app.py`. (commit `61e927e`)
- **Phase 1 — DB out of git.** 2.3 GB `open_discourse.db` untracked, added to
  `.gitignore`, purged from the unpushed commit range with `filter-branch`.
  (commits `70bdc24` + history rewrite)
- **Phase 2 — performance.** `finalize` pipeline phase materializes
  `faction_normalized` + `search_text`; per-query latency dropped ~5×. Query
  caches raised 60 s → 1 h. DB slimmed to ~2.0 GB (`--slim` drops raw text).
  (commits `c97e23a`, `adef580`)
- **Phase 3 — HF Spaces deploy prep.** `DB_PATH` now env-configurable; app
  downloads the DB once from a public HF Dataset repo (`HF_DB_REPO`) when absent.
  Added `requirements.txt`. Startup pre-warm (`SUM(LENGTH(search_text))`) page-
  caches the 2 GB file at boot, so the first search is ~100 ms instead of cold.
  Keyword input capped at `max_chars=80`. Replaced deprecated
  `use_container_width=True` → `width='stretch'` on all 6 charts.

---

## ⏳ Phase 1 leftovers (manual, your call)

These need you, not code changes.

1. **Push the rewritten history.** Local `main` is ~9 commits ahead of the
   remote and now pushable (largest reachable blob is < 1 MB):
   ```sh
   git push origin main
   ```
2. **Reclaim local `.git` space.** The old 2.3 GB blob is still held by safety
   refs (`refs/original/...`, the `backup-pre-db-purge` tag, reflog). Once the
   push works and the app is confirmed good:
   ```sh
   git update-ref -d refs/original/refs/heads/main
   git tag -d backup-pre-db-purge
   git reflog expire --expire=now --all && git gc --prune=now --aggressive
   ```

---

## 🔜 Phase 3 — Deployment hardening (before going public)

Target: a safe, fast, public deployment. Items roughly in priority order.

### 3.1 Fix `.github/workflows/deploy.yml` ✅ DONE
Replaced the inherited DigitalOcean-droplet workflow (ran as `root` over SSH,
unpinned `appleboy/ssh-action@master`, host-wide `docker system prune -af`,
stale upstream paths) with an **HF Spaces deploy action**:
- Triggers only on app-relevant file changes (`paths:` filter) + manual dispatch.
- Assembles just the Space files (`app.py`, `requirements.txt`,
  `.streamlit/`, `deploy/hf/{Dockerfile,README.md}`) and `hf upload`s them to
  `MissionJupiter/open-discourse-lite`. No SSH, no host access, least privilege.
- Pinned first-party actions (`checkout@v4`, `setup-python@v5`).
- The 2 GB DB is **not** shipped by CI — it lives in the public dataset
  `MissionJupiter/open-discourse-db` and is downloaded by the app at startup.
- **Requires:** an `HF_TOKEN` (write-scoped) GitHub Actions secret.

### 3.2 Rate limiting / abuse protection
Substring search is now fast (~100 ms warm) but still a full scan; a public
endpoint should not allow unbounded concurrent searches.
- ✅ Max keyword length: input capped at `max_chars=80`.
- On a VPS: put the app behind a reverse proxy (nginx/Caddy/Traefik) with
  per-IP rate limiting and sensible timeouts. (N/A on HF Spaces — no proxy
  control; rely on the length cap + `@st.cache_data` dedupe there.)

### 3.3 Streamlit deprecation cleanup ✅ DONE
- Replaced `use_container_width=True` → `width='stretch'` on all 6 Plotly
  charts.

### 3.4 Repo / config tidy (small)
- Untrack `.vscode/.env` (only holds a stale `PYTHONPATH=./python/src` that
  doesn't match this repo's layout). Consider whether `.idea/` should be tracked.
- Pin/verify Python + dependency versions for reproducible deploy builds.

### 3.5 Operational notes
- **Cold start:** ✅ mitigated — `get_connection()` runs a pre-warm scan
  (`SUM(LENGTH(search_text))`, ~1.2 s) once at server start, page-caching the
  2 GB DB so the first real search is ~100 ms. Still give the host enough free
  RAM to keep the file cached.
- On free HF Spaces the container sleeps after ~48 h idle and the ephemeral disk
  resets, so a cold wake re-downloads the 2 GB DB (~1 min). Acceptable for a
  free deploy; persistent storage (paid) avoids it.
- Add a basic healthcheck endpoint/monitor for the deployment.

---

## 🔜 Phase 4 — Licensing tidy (low effort)

Data attribution in the app footer is already correct (Bundestag § 5 UrhG;
Wikipedia CC BY-SA 4.0). Remaining:
- `LICENSE` is MIT "Copyright (c) 2020 Open Discourse" (upstream). Add your own
  copyright line and note in the README that this is a derivative
  reimplementation, to keep attribution clean.
- Keep the existing Wikipedia CC BY-SA attribution (don't drop it).

---

## 🔜 Website — remaining setup & next steps

Manual setup (needs you, not code):
1. **Create the API Space** `MissionJupiter/openbundestag-api` (Docker SDK) and
   set its `ALLOWED_ORIGINS` env to the Pages URL. `HF_TOKEN` secret already
   exists for the other deploy.
2. **Create the Cloudflare Pages project** `openbundestag`. Add GitHub secrets
   `CLOUDFLARE_API_TOKEN` + `CLOUDFLARE_ACCOUNT_ID` and the repo **variable**
   `PUBLIC_API_BASE` = the API Space URL.
3. **Merge `feature/web` → main** (or keep developing on the branch) to activate
   `deploy-web.yml` / `deploy-api.yml`. Attach a custom domain in Cloudflare when ready.

Next feature — **drill-down UI** (the API is already built for it):
- Build the reader in `SpeechDrawer.svelte`: full passage with the match
  highlighted, then download (speech as `.txt`/`.md`, link to the source session).
- **Blocker:** snippets/full text need a **non-slim** DB. The current deployed
  (and local) DB is `--slim` (`has_raw_text` = false). Rebuild without `--slim`
  and upload to the dataset, or keep a separate full DB for the API Space.

A **fork** can be split out later: `web/` + `api/` are self-contained at the
repo root. Use `git subtree split --prefix=web` (or `git filter-repo`) to extract
with history into a standalone repo; a GitHub fork keeps the upstream link for
pulling pipeline updates.

---

## Ideas / nice-to-have (unscheduled)

- Pre-warm the DB page cache on startup with a tiny query (smoother first hit).
- Optional: expose phrase vs. token search, or per-term normalization counts.
- The "By party" tab re-runs `query_timeline` with the same args as the Timeline
  tab; deduped by cache today, but could be refactored to share one result.

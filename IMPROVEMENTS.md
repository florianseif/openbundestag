# OpenBundestag — improvement ideas

Grounded list of improvements across **information**, **visuals**, and **performance**,
with effort vs. benefit. Based on the current hot path: `src/queries.py` (the combined
`search()` scan), `api/main.py` (single DuckDB conn, TTLCache, HF cold-start), and the
explorer frontend (`web/src/lib/api.ts`, `prefetch.ts`, `TimelineChart.svelte`,
`web/src/routes/explore/+page.svelte`).

**Already built (excluded):** timeline government bands + historical event markers,
deep-link/shareable URLs, compare-words mode, mobile nav, dark "data-noir" theme,
prefetch bundle (~100 words, default filter), keep-HF-Space-warm cron
(`.github/workflows/keepalive.yml`, PR #20).

Effort: **S** (hours) / **M** (1–2 days) / **L** (multi-day). Benefit is relative to this app.

| # | Idea | Area | Effort | Benefit |
|---|------|------|:------:|:-------:|
| 1 | Normalized frequency (per-1000-speeches) | Information | M | **HIGH** |
| 2 | Multi-word / phrase / OR search | Information | M | MED-HIGH |
| 3 | Click an MP in "top speakers" to drill in | Information | S | MED |
| 3b | Speaker suggestions in "Alle Redner" from top-speakers data | Information | S | MED |
| 4 | Co-occurring / context words | Information | L | HIGH |
| 5 | Chart accessibility (keyboard + ARIA + table) | Visuals | M | MED |
| 6 | Export current view (chart PNG/SVG + CSV) | Visuals | S-M | MED |
| 7 | Cold-start affordance polish | Visuals | S | MED |
| 8 | FTS / trigram index vs. full LIKE scan | Performance | M-L | **HIGH** |
| 9 | Widen prefetch + gzip the API | Performance | S | MED |

---

## Information

### 1. Normalized frequency (per-1000-speeches / share of corpus) — **M, HIGH**
Every chart is **raw absolute counts** (`COUNT(*)` / occurrence sum). Parliament grew from
~400 to 700+ members and sessions got longer, so almost every word "trends up" — the count
tracks corpus size, not salience. Add a `count_mode = "relative"` dividing each period's
matches by that period's total speeches.
- Needs a per-period denominator (`SELECT period, COUNT(*) FROM speeches GROUP BY period`),
  computed once and cached — it's filter-independent.
- Toggle next to the existing Monthly/Quarterly + speeches/occurrences controls.
- **The single highest-value analytical fix.** Turns "more speeches exist now" into "this
  topic actually rose."

### 2. Multi-word / phrase / OR search — **M, MED-HIGH**
`build_conditions` does one `LIKE '%word%'` substring. No AND, OR, or quoted phrase. Add:
space-separated terms → AND, `|` → OR, `"..."` → exact phrase. Stays within the existing
scan; just more conditions. Big expressivity gain for researchers.

### 3. Click an MP in "top speakers" to drill into them — **S, MED**
Backend already supports `politician_id` filtering everywhere, and the `pol` URL param
exists. Wire a click on a top-politicians row to set `f.politician_id`. Near-free.

### 3b. Speaker suggestions in "Alle Redner" searchbar — **S, MED**
The "Alle Redner" searchbar has no typeahead. Reuse the speakers already returned by the
"Wer spricht am meisten?" (top-politicians) panel as dropdown suggestions — no extra query,
the data is already on the client. Gives the user instant context on who's relevant for the
current keyword before they start typing a name.

### 4. Co-occurring / context words ("words most associated with X") — **L, HIGH**
"When MPs say *Klimawandel*, what else do they say?" Requires tokenizing matched speeches
and ranking by lift vs. baseline frequency. Best precomputed offline (a new pipeline phase
+ a small table), not live. Most editorially compelling, most expensive.

## Visuals

### 5. Chart accessibility — keyboard nav + ARIA + table fallback — **M, MED**
Bespoke SVG charts have no `role`, no focusable points, no screen-reader summary. Add
aria-labels, a visually-hidden data table per chart, keyboard focus on data points. A11y
basics.

### 6. Export current view — chart PNG/SVG + data CSV — **S-M, MED**
The speech reader already emits a `.txt`; extend the same instinct to the dashboard.
"Download CSV" of the current timeline/by-party + "Save chart as PNG" (serialize the
existing SVG). High value for journalists/researchers, low surface area.

### 7. Cold-start affordance polish — **S, MED**
`api.ts` already documents the ~1-min HF wake but the UI just spins. Show an explicit
"waking the server (~1 min, free hosting)" state + skeletons so first-load doesn't read as
broken. (Pairs with #8.)

## Performance

### 8. Replace the full-table LIKE scan with a DuckDB FTS (or trigram) index — **M-L, HIGH**
The one true scaling bottleneck: any uncached/unprefetched query is a substring scan over
the ~1.8 GB `search_text` column (~100 ms warm, worse cold). Prefetch only covers ~100 words
under one filter signature. `PRAGMA create_fts_index` gives token-level search in a new
pipeline phase.
- **Semantics change:** FTS matches whole tokens/stems, not arbitrary substrings (`klima`
  would stop matching inside `Klimawandel`). Decide if that's acceptable, or use a trigram
  approach to preserve substring behavior. Build as an optional phase, measure, keep LIKE as
  fallback.

### 9. Widen prefetch + gzip the API — **S, MED**
Cheap wins around the existing prefetch: (a) add an **all-terms** signature and bump to ~300
words in `scripts/gen_prefetch.py`; (b) add FastAPI `GZipMiddleware` (one line) so live JSON
payloads compress; (c) gzip/precompress the 320 KB `prefetch.json` bundle. Each is small and
independent.

---

## Priority (benefit ÷ effort)
1. **#1 normalized frequency** — the biggest correctness/insight gain.
2. **#3 MP drill-down** + **#3b speaker suggestions** + **#9 gzip/prefetch widen** — cheap, plumbing exists.
3. **#6 export** — small, high researcher value.
4. **#8 FTS index** — biggest perf-ceiling lift, but a semantics decision first.

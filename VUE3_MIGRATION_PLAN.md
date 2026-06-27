# Vue 3 Migration Plan — OpenBundestag `web/`

> ⚠️ **Note:** `CLAUDE.md` currently says *"Do not switch frameworks."* This plan
> exists because the owner explicitly requested a Vue 3 port. If you proceed,
> update that paragraph in `CLAUDE.md` as the **final** step (Phase 8).

## 0. Why this is lower-risk than it looks

- **No SSR to port.** The explorer already runs `ssr=false`; the landing page is
  client-rendered scrollytelling. The target is a **Vue 3 SPA** served statically
  by Cloudflare Pages — no Nitro/server runtime to reproduce.
- **The backend doesn't move.** `api/` (FastAPI) and `src/queries.py` are
  untouched. The contract is HTTP JSON at `PUBLIC_API_BASE`. The whole migration
  is one folder: `web/src`.
- **Logic is already framework-agnostic.** `api.ts`, `format.ts`, `types.ts`,
  `prefetch.ts` and all `*.json` are plain TS/data — they copy over **verbatim**.
  Only `i18n.svelte.ts` (uses `$state`) needs a reactivity rewrite.
- **Charts are bespoke SVG + d3-scale/d3-shape**, not a Svelte chart lib. The
  math stays; only the template binding syntax changes.

## 1. Scope inventory (what actually has to change)

Source: `web/src` — 22 `.svelte` components/routes + 6 lib `.ts` + data JSON.

| Bucket | Files | Effort | Notes |
|---|---|---|---|
| **Copy verbatim** | `api.ts`, `format.ts`, `types.ts`, `prefetch.ts`, `index.ts`, all `*.json`, `assets/` | trivial | Pure TS/data. No Svelte imports inside. Verify with grep. |
| **Reactivity rewrite** | `i18n.svelte.ts` | small | `$state` → `reactive()`/`ref()`. Becomes a composable `useI18n()`. |
| **Build/config** | `vite.config.ts`, `svelte.config.js`, `tsconfig.json`, `package.json`, `app.html`, `app.d.ts`, `app.css` | small | Swap SvelteKit plugin → `@vitejs/plugin-vue`; add Vue Router; Cloudflare static output. `app.css` copies verbatim. |
| **Routing** | `routes/+layout.svelte`, 6 `+page.svelte`, 3 `+page.ts` loaders | medium | File-routing → Vue Router config. `+page.ts` loaders → in-component `onMounted` fetch (SSR is off anyway). |
| **Leaf components (no charts)** | Counter, LangToggle, PageHero, FilterPanel, TermFilter, SpeechTable, SpeechModal, SpeechDrawer, StoryPanel, ZwischenrufFeed | medium | Template + `$props`/`$state`/`$derived`/`$effect` → Vue SFC. Mechanical. |
| **Chart components (SVG/d3)** | Sparkline, Donut, HBars, ParliamentArc, CompareChart, InterruptionMatrix, **TimelineChart (833 LOC)**, PipelineArchitecture | large | d3 math unchanged; SVG template re-bound; Svelte transitions → `<Transition>`/CSS. TimelineChart is the single biggest risk. |

Rough order of magnitude: ~8.8k LOC of `.svelte`. The bottom two buckets are ~80% of the work; `explore/+page.svelte` (1309 LOC) + `TimelineChart` (833) + `zwischenrufe`/`beifall` pages (700 each) are the heavyweights.

## 2. Target stack (laziest that covers SvelteKit's features here)

| SvelteKit feature used | Vue 3 replacement | Why this one |
|---|---|---|
| Vite build | **Vite + `@vitejs/plugin-vue`** | Same bundler, keep it. |
| `$state/$derived/$effect` (runes) | `ref`/`reactive` + `computed` + `watch/watchEffect` | Native Vue 3 `<script setup>`. No lib. |
| File routing + layouts | **`vue-router` v4** | The de-facto router. Layout = a root `<App>` with `<RouterView>`. |
| `+page.ts` `load()` | `onMounted()` fetch (or router `beforeEnter`) | SSR is off → no loader runtime needed. Keep it in-component. |
| Stores (`i18n.svelte.ts`) | A **composable** module (`useI18n`) with a module-level `reactive` | No Pinia — one tiny store doesn't justify a dependency. `ponytail:` skip Pinia, add if global state grows past ~3 stores. |
| `transition:`/`in:`/`out:` directives | Vue **`<Transition>`/`<TransitionGroup>`** + existing CSS | Built in. Heavy d3 draw-in animations are already CSS/JS-driven, not Svelte transitions — keep as-is. |
| `adapter-cloudflare` | **Static build → Cloudflare Pages** + SPA fallback (`_redirects: /* /index.html 200`) | Output is static; Pages serves it. Update `deploy-web.yml` build cmd only. |
| `$env/static/public` (`PUBLIC_API_BASE`) | Vite `import.meta.env.VITE_API_BASE` | Native Vite env. Rename the var in `.env`. |

**No state-management lib, no UI lib, no chart lib added.** Net dependency delta: `-svelte/-sveltekit/-svelte-check`, `+vue/+vue-router/+@vitejs/plugin-vue/+vue-tsc`.

## 3. Phased execution (small, independently verifiable steps)

Each phase ends **green** (`build` + `typecheck` pass, app boots) before the next.
Work on a branch; do **not** delete `.svelte` files until the Vue equivalent is verified — keep both trees side by side under `web/` during migration so you can diff behavior.

### Phase 1 — Scaffold parallel Vue app (no SvelteKit removed yet)
- [ ] **1.1** New branch `vue3-migration`. Add `vue`, `vue-router`, `@vitejs/plugin-vue`, `vue-tsc` to `web/package.json`.
- [ ] **1.2** Create `web/index.html` (Vite SPA entry) + `web/src/main.ts` mounting `<App>` with router. Keep SvelteKit files untouched for now.
- [ ] **1.3** Add a second Vite config or a `MIGRATE=1` flag so the Vue app builds to `dist-vue/` independently.
- [ ] **1.4** Copy verbatim: `api.ts`, `format.ts`, `types.ts`, `prefetch.ts`, `*.json`, `assets/`, `app.css`.
- **Verify:** `vite build` (Vue config) produces a blank-but-booting page; `vue-tsc --noEmit` passes; copied modules import cleanly (grep them for `svelte` imports first — expect zero).

### Phase 2 — Core primitives & i18n
- [ ] **2.1** Port `i18n.svelte.ts` → `useI18n.ts` composable (`reactive` dict + `setLang`). Same keys, same API surface (`t()`).
- [ ] **2.2** Port `LangToggle`, `Counter` (the two smallest, 31 + 24 LOC) as the reference SFCs that prove the runes→Vue mapping (see §4).
- **Verify:** a throwaway test route renders `<Counter>` animating and `<LangToggle>` switching `t()` output. Snapshot the rendered numbers/strings against the live Svelte app.

### Phase 3 — Router + layout + static pages
- [ ] **3.1** Build `vue-router` config: `/`, `/explore`, `/about`, `/architecture`, `/beifall`, `/zwischenrufe`.
- [ ] **3.2** Port `+layout.svelte` → `App.vue` shell (nav + `<RouterView>`).
- [ ] **3.3** Port the two **static** pages first: `about`, `architecture` (+ `PipelineArchitecture`, `PageHero`). No data fetching.
- **Verify:** Nav between all 6 routes works (even if non-static pages are stubs). `about`/`architecture` pixel-match the Svelte version side by side.

### Phase 4 — Leaf interactive components
- [ ] **4.1** Port `FilterPanel`, `TermFilter`, `StoryPanel`.
- [ ] **4.2** Port `SpeechTable`, `SpeechModal`, `SpeechDrawer`, `ZwischenrufFeed`.
- **Verify:** Each component mounted in isolation behaves identically (open/close modal, filter emits, table sorts). Compare emitted events/props to the Svelte component's contract in `types.ts`.

### Phase 5 — Charts (highest risk, do one at a time)
Order: simplest → hardest so the runes→Vue SVG pattern is proven before the monster.
- [ ] **5.1** `Sparkline` (70) → **5.2** `Donut` (91) → **5.3** `HBars` (105) → **5.4** `ParliamentArc` (200) → **5.5** `CompareChart` (195) → **5.6** `InterruptionMatrix` (407) → **5.7** `TimelineChart` (833, last).
- For each: keep d3-scale/d3-shape calls **byte-identical**; only re-bind the SVG template and convert any Svelte transition to `<Transition>`/CSS keyframes.
- **Verify per chart:** render with a **fixed fixture dataset** (capture one `/api/search` payload to JSON) and visually diff the SVG against the Svelte render at the same viewport. For TimelineChart also verify: draw-in animation, legend-hover dimming, click-to-drill emits the right point.

### Phase 6 — Data routes (wire it all together)
- [ ] **6.1** `explore/+page.svelte` (1309) → `Explore.vue`. Replace `+page.ts` load with `onMounted` fetch + the `prefetch.ts` fast path (unchanged). This is the integration crux — all of Phase 4/5 components land here.
- [ ] **6.2** `zwischenrufe` (722) and `beifall` (679) pages + their `+page.ts`.
- [ ] **6.3** Landing `+page.svelte` (390) scrollytelling (`stories.json`, `StoryPanel`).
- **Verify:** Type a keyword in the live explorer (Vue) and the live Svelte app pointed at the same API; the total/timeline/by-party/top-speakers must match. Confirm a prefetch keyword returns instantly (no network) in the Network tab. Drill-down modal fetches `/api/speech/{id}`.

### Phase 7 — Build, deploy, env
- [ ] **7.1** Finalize one `vite.config.ts` (Vue only). Output `dist/` static.
- [ ] **7.2** Add `web/public/_redirects` → `/* /index.html 200` (SPA fallback for Cloudflare Pages deep links).
- [ ] **7.3** Rename `PUBLIC_API_BASE` → `VITE_API_BASE` in `.env`, `.env.example`, and `api.ts`. Update `package.json` scripts (`dev/build/preview/check` → `vue-tsc`).
- [ ] **7.4** Update `.github/workflows/deploy-web.yml` build command + output dir.
- **Verify:** `npm run build` clean; `npm run preview` serves the SPA; deep-link to `/explore` reload works (no 404); a Cloudflare preview deploy renders against the live HF API.

### Phase 8 — Cutover & cleanup
- [ ] **8.1** Delete all `.svelte` files, SvelteKit deps, `svelte.config.js`, `+page.ts`, `app.d.ts` (Svelte-specific bits).
- [ ] **8.2** Remove `svelte*` from `package.json`; `npm install` clean lockfile.
- [ ] **8.3** Update `CLAUDE.md`: replace the "Do not switch frameworks / SvelteKit" paragraphs with the Vue 3 stack; update `README.md` web section.
- **Verify:** Fresh `git clone` → `npm i && npm run build` from zero passes. `grep -ri svelte web/src` returns nothing. Full manual smoke of all 6 routes.

## 4. Runes → Vue 3 reference (the mechanical core of every component)

| Svelte 5 | Vue 3 `<script setup>` |
|---|---|
| `let x = $state(0)` | `const x = ref(0)` (use `x.value` in script, `x` in template) |
| `let d = $derived(a + b)` | `const d = computed(() => a.value + b.value)` |
| `$effect(() => {...})` | `watchEffect(() => {...})` / `onMounted` for one-shot |
| `let { foo, bar = 1 } = $props()` | `const props = defineProps<{foo: T; bar?: number}>()` (+ `withDefaults`) |
| `$bindable()` prop | `defineModel()` |
| `dispatch('x', detail)` / callback props | `const emit = defineEmits<{x: [T]}>()` |
| `{#each items as it}` | `<template v-for="it in items" :key=…>` |
| `{#if cond}` / `{:else}` | `<template v-if>` / `<template v-else>` |
| `{@html s}` | `v-html="s"` |
| `transition:fade` / `in:`/`out:` | `<Transition>` + CSS, or `@vueuse/motion` only if a directive has no CSS equivalent |
| `bind:value` | `v-model` |
| slots `{@render children()}` | `<slot>` / scoped slots |

`ponytail:` no Pinia, no chart lib, no motion lib unless a specific Svelte transition genuinely can't be done in CSS. Add only when a concrete component proves the need.

## 5. Global success criteria (definition of done)

1. **Functional parity** — every route + interaction in §3 verifies against the live Svelte app on the same API; no behavior regression.
2. **Type-clean** — `vue-tsc --noEmit` passes with the same strictness as today's `svelte-check`.
3. **Zero Svelte residue** — `grep -ri svelte web/` is empty; deps removed.
4. **Deploys green** — Cloudflare Pages preview builds and serves the SPA, deep links included.
5. **Backend untouched** — `git diff` shows no changes under `api/`, `src/`, or the pipeline.
6. **Docs updated** — `CLAUDE.md` + `README.md` describe the Vue 3 stack.

## 6. Risk register

| Risk | Mitigation |
|---|---|
| `TimelineChart` (833 LOC) animation/interaction parity | Ported **last**, against a frozen fixture payload, with an explicit interaction checklist (draw-in, hover-dim, click-drill). |
| Svelte transitions with no clean CSS analog | Default to CSS keyframes; fall back to `@vueuse/motion` per-component only if needed. |
| `prefetch.ts` fast-path signature drift | It's pure TS — copies verbatim; verify the "instant, no-network" path in DevTools in Phase 6. |
| SPA deep-link 404s on Cloudflare | `_redirects` SPA fallback added & tested in Phase 7. |
| Reactivity foot-gun: forgetting `.value` | Use `reactive()` for object stores where ergonomic; lean on `vue-tsc` to catch the rest. |
| Scope creep into `api/`/pipeline | Hard rule: migration touches only `web/`. Enforced by success criterion #5. |

## 7. Reality check (read before starting)

This is a **full rewrite of the presentation layer**, not a transpile — ~8.8k LOC of templates re-authored by hand. The math, data, API contract, styles, and backend all survive untouched, which is what keeps it tractable. Budget the effort in the chart components and `explore/+page.svelte`; everything else is mechanical. Keep both trees alive until Phase 8 so every step is diffable against a working reference.

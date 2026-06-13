# OpenBundestag — web

The dedicated public website: a SvelteKit frontend that explores Bundestag
word-usage via the [OpenBundestag API](../api). A scrollytelling landing page
hands off into a live, filterable data explorer.

- **Framework:** SvelteKit 5 (runes) + `@sveltejs/adapter-cloudflare`
- **Charts:** bespoke SVG built with `d3-scale` / `d3-shape` (no chart library)
- **Hosting:** Cloudflare Pages (free, custom domain) → talks to the API on a HF Space

## Develop

```sh
# 1. start the API (from the repo root)
uv run uvicorn api.main:app --port 8000

# 2. start the frontend
cd web
npm install
npm run dev            # http://localhost:5173
```

Set the API base in `web/.env` (see `.env.example`):

```
PUBLIC_API_BASE=http://127.0.0.1:8000
```

## Build / check

```sh
npm run check          # svelte-check (types)
npm run build          # production build → .svelte-kit/cloudflare
npm run preview        # preview the build locally
```

## Structure

```
src/
├── app.css                     design system (tokens, type, layout)
├── lib/
│   ├── api.ts                  typed fetch client (PUBLIC_API_BASE)
│   ├── types.ts                API response shapes
│   ├── i18n.svelte.ts          DE/EN strings + reactive lang store (runes → .svelte.ts)
│   ├── format.ts               number/date + party colour helpers
│   ├── stories.json            precomputed landing snapshot (regenerate from the DB)
│   └── components/             charts, filters, drawer, language toggle
└── routes/
    ├── +layout.svelte          header + footer + i18n
    ├── +page.svelte            landing (hero + scrollytelling)
    └── explore/+page.svelte    the explorer (SSR off)
```

The drill-down drawer (`SpeechDrawer.svelte`) is wired to `/api/speeches` but the
full reader/download UI lands in a later phase. Snippets require a non-slim DB.

## Deploy

GitHub Actions (`.github/workflows/deploy-web.yml`) builds and pushes to
Cloudflare Pages on changes to `web/**`. Set `vars.PUBLIC_API_BASE` to the HF
Space API URL and the `CLOUDFLARE_API_TOKEN` / `CLOUDFLARE_ACCOUNT_ID` secrets.

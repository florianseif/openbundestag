# OpenBundestag — web

The dedicated public website: a Vue 3 frontend that explores Bundestag
word-usage via the [OpenBundestag API](../api). A scrollytelling landing page
hands off into a live, filterable data explorer.

- **Framework:** Vue 3 (`<script setup>`) + Vite + `vue-router`, built as a static SPA
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
VITE_API_BASE=http://127.0.0.1:8000
```

## Build / check

```sh
npm run check          # vue-tsc (types)
npm run build          # production build → dist/
npm run preview        # preview the build locally
```

## Structure

```
index.html                       Vite entry (mounts #app)
src/
├── main.ts                      app bootstrap (createApp + router)
├── router.ts                    vue-router routes (SPA, no SSR)
├── App.vue                      header + footer + i18n shell
├── app.css                      design system (tokens, type, layout)
├── lib/
│   ├── api.ts                  typed fetch client (VITE_API_BASE)
│   ├── types.ts                API response shapes
│   ├── i18n.ts                 DE/EN strings + reactive lang store (reactive singleton)
│   ├── format.ts               number/date + party colour helpers
│   ├── prefetch.ts             instant payloads for popular default-filter queries
│   ├── stories.json            precomputed landing snapshot (regenerate from the DB)
│   └── components/             *.vue charts, filters, modal, language toggle
└── views/                       route components
    ├── Home.vue                landing (hero + scrollytelling)
    ├── Explore.vue             the explorer
    ├── Beifall.vue             applause analytics
    ├── Zwischenrufe.vue        heckling analytics
    ├── About.vue               about page
    └── Architecture.vue        pipeline diagram
```

`public/_redirects` (`/* /index.html 200`) gives the SPA deep-link fallback on
Cloudflare Pages. The `$lib` alias is configured in `vite.config.ts` + `tsconfig.json`.

## Deploy

GitHub Actions (`.github/workflows/deploy-web.yml`) builds and pushes to
Cloudflare Pages on changes to `web/**`. Set `vars.PUBLIC_API_BASE` to the HF
Space API URL (exposed to the build as `VITE_API_BASE`) and the
`CLOUDFLARE_API_TOKEN` / `CLOUDFLARE_ACCOUNT_ID` secrets.

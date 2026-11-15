# FireCal: harmonized MODIS + VIIRS hotspot calendar

Frontend for our NASA Space Apps 2026 entry ("Harmonization of MODIS and VIIRS Hot Spots").
React + Vite + TypeScript, with a MapLibre globe.

## Run it

You need Node.js 20 or newer.

```bash
npm install
npm run dev
```

Open http://localhost:5173. By default the app calls the **real backend**, so start it first (see [../backend/README.md](../backend/README.md)); it must run on `127.0.0.1:8080`, or set `VITE_API_TARGET` in `.env`.

The browser calls `/api/...` on the Vite server, which forwards it to the backend. The contract is [spec/api/frontend-backend.md](../spec/api/frontend-backend.md); the matching TypeScript shapes are in `src/types.ts`.

## Work without the backend

Create `.env` with `VITE_USE_MOCK=true` (see `.env.example`) and restart `npm run dev`. The app then uses fake data generated in the browser, in the same format as the backend.

## Deploy (Firebase Hosting)

The frontend (Firebase project `firecal-frontend`) and the backend (Cloud Run,
GCP project `nasa-514815`, see [../backend/deploy/README.md](../backend/deploy/README.md))
are deployed separately. In production there is no Vite proxy: the browser
calls the backend's Cloud Run URL directly. `npm run build` reads that URL from
[`.env.production`](.env.production) (`VITE_API_URL`); change it there if the
backend moves. Locally `VITE_API_URL` is empty and `/api` goes through Vite as before.

```bash
npm run build
firebase deploy --only hosting
```

## Where things are

```
src/
  App.tsx                    page layout
  store.ts                   app state (place, radius, dates, results) and API calls
  types.ts                   data shapes agreed with the backend
  api/client.ts              POST /api/<feature>, or the mock
  api/mock.ts                fake backend, same format as the real one
  api/geocode.ts             place name → lat/lon (Photon, OpenStreetMap)
  lib/stats.ts               seasonal profile, ranking, current vs median, CSV
  components/GlobeMap.tsx    MapLibre globe, search area, hotspots layer
  components/SearchBar.tsx   place search (Ctrl/Cmd + K)
  components/AreaPanel.tsx   radius, period, analyze button, quick KPIs
  components/AnalysesMenu.tsx  top-right menu with all analyses and exports
  components/ResultsDrawer.tsx right panel showing the chosen analysis
  components/views/          calendar heatmap and charts
```

Before changing the look, read `DESIGN.md`.

## External services (all free, no API key)

- Basemap: CARTO Dark Matter (OpenStreetMap data)
- Geocoding: Photon by komoot (OpenStreetMap data)

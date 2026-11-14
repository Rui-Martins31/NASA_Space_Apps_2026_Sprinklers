# FireCal: harmonized MODIS + VIIRS hotspot calendar

Frontend for our NASA Space Apps 2026 entry ("Harmonization of MODIS and VIIRS Hot Spots").
React + Vite + TypeScript, with a MapLibre globe.

## Run it

You need Node.js 20 or newer.

```bash
npm install
npm run dev
```

Open http://localhost:5173. By default the app uses **fake data generated in the browser**, so it works without the backend.

## Connect the real backend

1. Start the backend on `127.0.0.1:8080`.
2. In `.env`, set `VITE_USE_MOCK=false` (and change `VITE_API_TARGET` if the backend runs elsewhere).
3. Restart `npm run dev`.

The browser calls `/api/...` on the Vite server, which forwards it to the backend, so the backend does not need CORS settings. The contract is in `API.md`.

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

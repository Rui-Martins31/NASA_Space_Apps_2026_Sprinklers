// Extra map layers on top of the CARTO basemap: terrain, hillshade,
// 3D buildings, satellite imagery, and the (animated) hotspots.
import type * as maplibregl from 'maplibre-gl'
import { addFlameImages } from './flames'

export const EMBER = '#ff6b1a'
/** From this zoom on, hotspots are drawn as animated flames instead of dots. */
export const FLAME_MINZOOM = 9

// Elevation tiles (Terrarium encoding), free on AWS Open Data, no key.
const DEM_TILES = 'https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png'
// Buildings with heights (OpenMapTiles schema), OpenFreeMap, free, no key.
const BUILDINGS_TILEJSON = 'https://tiles.openfreemap.org/planet'
// Sentinel-2 cloudless mosaic by EOX, free for non-commercial use with attribution.
const SATELLITE_TILES = 'https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless-2024_3857/default/g/{z}/{y}/{x}.jpg'

export const TERRAIN_EXAGGERATION = 1.4

const DAY = 86_400_000
/** How long a hotspot stays visible during a replay: ~1/40 of the period, at least 3 days. */
export function replayFadeMs(dateFrom: string, dateTo: string) {
  const span = new Date(dateTo).getTime() - new Date(dateFrom).getTime()
  return Math.max(3 * DAY, span / 40)
}

/** First label layer of the basemap: our ground layers go underneath it. */
function firstSymbolLayer(map: maplibregl.Map) {
  return map.getStyle().layers.find((l) => l.type === 'symbol')?.id
}

export function addBaseLayers(map: maplibregl.Map) {
  const beforeLabels = firstSymbolLayer(map)

  // Satellite imagery (hidden until the user switches to it)
  map.addSource('satellite', {
    type: 'raster',
    tiles: [SATELLITE_TILES],
    tileSize: 256,
    maxzoom: 14,
    attribution:
      '<a href="https://s2maps.eu" target="_blank">Sentinel-2 cloudless</a> by EOX IT Services GmbH (contains modified Copernicus Sentinel data 2024)',
  })
  map.addLayer(
    {
      id: 'satellite',
      type: 'raster',
      source: 'satellite',
      layout: { visibility: 'none' },
      paint: { 'raster-brightness-max': 0.85, 'raster-saturation': -0.1 },
    },
    beforeLabels,
  )

  // Terrain and hillshade use separate sources (recommended by MapLibre).
  const dem = {
    type: 'raster-dem' as const,
    tiles: [DEM_TILES],
    encoding: 'terrarium' as const,
    tileSize: 256,
    maxzoom: 15,
  }
  map.addSource('dem-terrain', { ...dem, attribution: 'Elevation: Mapzen Terrain Tiles (AWS Open Data)' })
  map.addSource('dem-hillshade', dem)
  map.addLayer(
    {
      id: 'hillshade',
      type: 'hillshade',
      source: 'dem-hillshade',
      paint: {
        'hillshade-exaggeration': 0.45,
        'hillshade-shadow-color': '#000000',
        'hillshade-highlight-color': '#3a4558',
        'hillshade-accent-color': '#000000',
      },
    },
    beforeLabels,
  )

  // 3D buildings, visible when zoomed in to street level
  map.addSource('buildings', { type: 'vector', url: BUILDINGS_TILEJSON })
  map.addLayer(
    {
      id: 'buildings-3d',
      type: 'fill-extrusion',
      source: 'buildings',
      'source-layer': 'building',
      minzoom: 13,
      paint: {
        'fill-extrusion-color': ['interpolate', ['linear'], ['coalesce', ['get', 'render_height'], 6], 0, '#1d2430', 40, '#2c3646'],
        'fill-extrusion-height': ['interpolate', ['linear'], ['zoom'], 13, 0, 14.5, ['coalesce', ['get', 'render_height'], 6]],
        'fill-extrusion-base': ['coalesce', ['get', 'render_min_height'], 0],
        'fill-extrusion-opacity': 0.85,
      },
    },
    beforeLabels,
  )
}

export function setBasemap(map: maplibregl.Map, kind: 'dark' | 'satellite') {
  if (!map.getLayer('satellite')) return
  map.setLayoutProperty('satellite', 'visibility', kind === 'satellite' ? 'visible' : 'none')
  map.setPaintProperty('hillshade', 'hillshade-exaggeration', kind === 'satellite' ? 0.25 : 0.45)
}

export function setTerrain(map: maplibregl.Map, on: boolean) {
  if (!map.getSource('dem-terrain')) return
  map.setTerrain(on ? { source: 'dem-terrain', exaggeration: TERRAIN_EXAGGERATION } : null)
  map.setLayoutProperty('buildings-3d', 'visibility', on ? 'visible' : 'none')
}

export function addHotspotLayers(map: maplibregl.Map) {
  map.addSource('hotspots', { type: 'geojson', data: { type: 'FeatureCollection', features: [] } })
  // soft glow underneath (this is the part that flickers), sharp core on top
  map.addLayer({
    id: 'hotspots-glow',
    type: 'circle',
    source: 'hotspots',
    paint: {
      'circle-color': EMBER,
      'circle-blur': 1,
      'circle-pitch-alignment': 'map',
    },
  })
  map.addLayer({
    id: 'hotspots-dot',
    type: 'circle',
    source: 'hotspots',
    paint: {
      'circle-color': ['match', ['get', 'confidence'], 'low', '#ffb070', 'high', '#ff3d00', EMBER],
      'circle-radius': ['interpolate', ['linear'], ['zoom'], 3, 1.2, 10, 3.2, 15, 5],
      'circle-pitch-alignment': 'map',
    },
  })
  // Close up: animated flames standing upright, even when the map is tilted
  addFlameImages(map)
  map.addLayer({
    id: 'hotspots-flame',
    type: 'symbol',
    source: 'hotspots',
    minzoom: FLAME_MINZOOM - 0.5,
    layout: {
      'icon-image': ['concat', 'flame-', ['to-string', ['get', 'variant']]],
      'icon-size': ['interpolate', ['linear'], ['zoom'], FLAME_MINZOOM - 0.5, 0.35, 12, 0.7, 15, 1.1],
      'icon-anchor': 'bottom',
      'icon-allow-overlap': true,
      'icon-ignore-placement': true,
      'icon-pitch-alignment': 'viewport',
      'icon-rotation-alignment': 'viewport',
    },
    paint: { 'icon-opacity': 0 },
  })
}

/**
 * Fire animation, updated every frame with a new `phase`.
 * Each hotspot has its own random `seed`, so they do not all pulse together.
 * "Hot" hotspots (last 7 days, or burning at the current replay moment)
 * flicker strongly; older ones only breathe gently.
 *
 * During a replay, hotspots appear at their date and fade over `fadeMs`.
 */
export function updateFireAnimation(map: maplibregl.Map, phase: number, replayTime: number | null, fadeMs: number) {
  if (!map.getLayer('hotspots-glow')) return

  const age = replayTime === null ? null : (['-', replayTime, ['get', 'ts']] as maplibregl.ExpressionSpecification)
  const hot: maplibregl.ExpressionSpecification =
    age === null ? ['==', ['get', 'recent'], true] : ['<', age, fadeMs * 0.25]

  // two sine waves at different speeds look more like a flame than one
  const wave: maplibregl.ExpressionSpecification = [
    '+',
    ['*', 0.6, ['sin', ['+', phase * 2.3, ['get', 'seed']]]],
    ['*', 0.4, ['sin', ['+', phase * 5.1, ['*', 2, ['get', 'seed']]]]],
  ]
  const flicker: maplibregl.ExpressionSpecification = ['+', 1, ['*', ['case', hot, 0.45, 0.1], wave]]

  // replay: fully visible when it starts, fading out as it gets older
  const fade: maplibregl.ExpressionSpecification | number =
    age === null ? 1 : ['interpolate', ['linear'], age, 0, 1, fadeMs, 0.12]

  map.setPaintProperty('hotspots-glow', 'circle-radius', [
    'interpolate',
    ['linear'],
    ['zoom'],
    3,
    ['*', ['case', hot, 4.5, 3], flicker],
    10,
    ['*', ['case', hot, 13, 8], flicker],
    15,
    ['*', ['case', hot, 22, 14], flicker],
  ])
  map.setPaintProperty('hotspots-glow', 'circle-opacity', ['*', fade, ['case', hot, ['*', 0.55, flicker], 0.28]])
  // dots fade out as the flames fade in
  map.setPaintProperty('hotspots-dot', 'circle-opacity', [
    'interpolate',
    ['linear'],
    ['zoom'],
    FLAME_MINZOOM - 0.5,
    fade,
    FLAME_MINZOOM + 0.5,
    0,
  ])
  // flames: full for active fires, faint embers for old ones
  map.setPaintProperty('hotspots-flame', 'icon-opacity', [
    'interpolate',
    ['linear'],
    ['zoom'],
    FLAME_MINZOOM - 0.5,
    0,
    FLAME_MINZOOM + 0.5,
    ['*', fade, ['case', hot, 1, 0.35]],
  ])

  const filter: maplibregl.FilterSpecification | null = replayTime === null ? null : ['<=', ['get', 'ts'], replayTime]
  map.setFilter('hotspots-glow', filter)
  map.setFilter('hotspots-dot', filter)
  map.setFilter('hotspots-flame', filter)
}

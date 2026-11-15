import { useEffect, useRef } from 'react'
import * as maplibregl from 'maplibre-gl'
// Vite does not copy MapLibre's web worker automatically, so we point to it explicitly.
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?url'
import { useApp } from '../store'
import { circlePolygon, zoomForRadius } from '../lib/geo'
import { addBaseLayers, addHotspotLayers, EMBER, FLAME_MINZOOM, replayFadeMs, setBasemap, setTerrain, updateFireAnimation } from '../lib/mapLayers'
import { FLAME_VARIANTS, flameState } from '../lib/flames'

// Free dark basemap (CARTO Dark Matter, OpenStreetMap data, attribution shown on the map).
const STYLE_URL = 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json'

// Keep the area centred in the free space between the left panel and the results panel.
const areaOffset = (): [number, number] => (useApp.getState().view ? [-90, 0] : [190, 0])
// Tilt the camera when looking at an area, so the relief is visible.
const areaPitch = () => (useApp.getState().terrain3d ? 55 : 0)

const DAY = 86_400_000

maplibregl.setWorkerUrl(workerUrl)

export default function GlobeMap() {
  const container = useRef<HTMLDivElement>(null)
  const mapRef = useRef<maplibregl.Map | null>(null)
  const markerRef = useRef<maplibregl.Marker | null>(null)
  const readyRef = useRef(false)

  const place = useApp((s) => s.place)
  const radiusKm = useApp((s) => s.radiusKm)
  const hotspots = useApp((s) => s.hotspots)
  const view = useApp((s) => s.view)
  const basemap = useApp((s) => s.basemap)
  const terrain3d = useApp((s) => s.terrain3d)

  // 1. Create the map once
  useEffect(() => {
    if (!container.current) return
    const map = new maplibregl.Map({
      container: container.current,
      style: STYLE_URL,
      center: [-12, 28],
      zoom: 1.7,
      maxPitch: 75,
      attributionControl: { compact: true },
    })
    mapRef.current = map
    map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), 'bottom-left')

    map.on('style.load', () => {
      map.setProjection({ type: 'globe' })
      addBaseLayers(map)

      map.addSource('area', { type: 'geojson', data: { type: 'FeatureCollection', features: [] } })
      map.addLayer({ id: 'area-fill', type: 'fill', source: 'area', paint: { 'fill-color': EMBER, 'fill-opacity': 0.08 } })
      map.addLayer({
        id: 'area-line',
        type: 'line',
        source: 'area',
        paint: { 'line-color': EMBER, 'line-width': 1.5, 'line-dasharray': [3, 2], 'line-opacity': 0.9 },
      })
      addHotspotLayers(map)

      readyRef.current = true
      const s = useApp.getState()
      setBasemap(map, s.basemap)
      setTerrain(map, s.terrain3d)
      syncArea()
      syncHotspots()
    })

    // Slow idle spin until the user touches the globe or picks a place
    let spinning = true
    const stop = () => (spinning = false)
    map.on('mousedown', stop)
    map.on('touchstart', stop)
    map.on('wheel', stop)

    // One animation loop for the spin and the fire flicker (~30 fps for the fires)
    let frame = 0
    let lastFire = 0
    const tick = (now: number) => {
      const s = useApp.getState()
      if (spinning && !s.place && map.getZoom() < 3) {
        const c = map.getCenter()
        map.setCenter([c.lng + 0.04, c.lat])
      }
      flameState.active = !!s.hotspots?.length && map.getZoom() >= FLAME_MINZOOM - 0.5
      if (readyRef.current && s.hotspots?.length && now - lastFire > 33) {
        lastFire = now
        updateFireAnimation(map, now / 1000, s.replayTime, replayFadeMs(s.dateFrom, s.dateTo))
      }
      frame = requestAnimationFrame(tick)
    }
    frame = requestAnimationFrame(tick)

    return () => {
      cancelAnimationFrame(frame)
      map.remove()
      mapRef.current = null
      readyRef.current = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  function syncArea() {
    const map = mapRef.current
    if (!map || !readyRef.current) return
    const { place, radiusKm } = useApp.getState()
    const src = map.getSource('area') as maplibregl.GeoJSONSource | undefined
    src?.setData(
      place
        ? { type: 'FeatureCollection', features: [circlePolygon(place.lat, place.lon, radiusKm)] }
        : { type: 'FeatureCollection', features: [] },
    )
  }

  function syncHotspots() {
    const map = mapRef.current
    if (!map || !readyRef.current) return
    const { hotspots, dateTo } = useApp.getState()
    const pts = hotspots ?? []
    const recentFrom = new Date(dateTo).getTime() - 7 * DAY
    const src = map.getSource('hotspots') as maplibregl.GeoJSONSource | undefined
    src?.setData({
      type: 'FeatureCollection',
      features: pts.map((h, i) => {
        const ts = new Date(h.date_time.endsWith('Z') ? h.date_time : `${h.date_time}Z`).getTime()
        return {
          type: 'Feature',
          properties: {
            confidence: h.confidence_class,
            date_time: h.date_time,
            ts,
            recent: ts >= recentFrom,
            seed: ((i * 2654435761) % 1000) / 159.15, // pseudo-random 0..2π, stable per point
            variant: i % FLAME_VARIANTS, // which flame animation to use
          },
          geometry: { type: 'Point', coordinates: [h.lon, h.lat] },
        }
      }),
    })
    if (pts.length) updateFireAnimation(map, performance.now() / 1000, useApp.getState().replayTime, 1)
  }

  // 2. Fly to the chosen place and place our own pulsing marker
  useEffect(() => {
    const map = mapRef.current
    if (!map) return
    markerRef.current?.remove()
    markerRef.current = null
    if (place) {
      const el = document.createElement('div')
      el.className = 'relative size-4'
      el.innerHTML =
        '<span class="absolute inset-0 rounded-full bg-[#ff6b1a]/40 animate-ping"></span>' +
        '<span class="absolute inset-[3px] rounded-full bg-[#ff6b1a] ring-2 ring-[#07090d]"></span>'
      markerRef.current = new maplibregl.Marker({ element: el }).setLngLat([place.lon, place.lat]).addTo(map)
      map.flyTo({
        center: [place.lon, place.lat],
        zoom: zoomForRadius(useApp.getState().radiusKm),
        pitch: areaPitch(),
        bearing: areaPitch() ? -20 : 0,
        offset: areaOffset(),
        duration: 3200,
        essential: true,
      })
    } else {
      map.easeTo({ pitch: 0, bearing: 0, duration: 800 })
    }
    syncArea()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [place])

  // 3. Redraw the circle when the radius changes
  useEffect(() => {
    syncArea()
    const map = mapRef.current
    if (map && place)
      map.easeTo({ center: [place.lon, place.lat], zoom: zoomForRadius(radiusKm), offset: areaOffset(), duration: 400 })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [radiusKm])

  // 4. Re-centre when the results panel opens or closes
  useEffect(() => {
    const map = mapRef.current
    const p = useApp.getState().place
    if (map && p) map.easeTo({ center: [p.lon, p.lat], offset: areaOffset(), duration: 450 })
  }, [view])

  // 5. Draw hotspots
  useEffect(() => {
    syncHotspots()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hotspots])

  // 6. Satellite / dark basemap
  useEffect(() => {
    if (mapRef.current && readyRef.current) setBasemap(mapRef.current, basemap)
  }, [basemap])

  // 7. 3D terrain on/off (also tilts or flattens the camera)
  useEffect(() => {
    const map = mapRef.current
    if (!map || !readyRef.current) return
    setTerrain(map, terrain3d)
    if (useApp.getState().place) map.easeTo({ pitch: areaPitch(), duration: 600 })
  }, [terrain3d])

  // The wrapper is positioned; MapLibre's own CSS would override position on the map div itself.
  return (
    <div className="absolute inset-0">
      <div ref={container} className="h-full w-full" aria-label="Interactive globe" />
    </div>
  )
}

import { useEffect, useRef } from 'react'
import * as maplibregl from 'maplibre-gl'
// Vite does not copy MapLibre's web worker automatically, so we point to it explicitly.
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?url'
import { useApp } from '../store'
import { circlePolygon, zoomForRadius } from '../lib/geo'

// Free dark basemap (CARTO Dark Matter, OpenStreetMap data, attribution shown on the map).
const STYLE_URL = 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json'
const EMBER = '#ff6b1a'

// Keep the area centred in the free space between the left panel and the results panel.
const areaOffset = (): [number, number] => (useApp.getState().view ? [-90, 0] : [190, 0])

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

  // 1. Create the map once
  useEffect(() => {
    if (!container.current) return
    const map = new maplibregl.Map({
      container: container.current,
      style: STYLE_URL,
      center: [-12, 28],
      zoom: 1.7,
      attributionControl: { compact: true },
    })
    mapRef.current = map
    map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), 'bottom-left')

    map.on('style.load', () => {
      map.setProjection({ type: 'globe' })

      map.addSource('area', { type: 'geojson', data: { type: 'FeatureCollection', features: [] } })
      map.addLayer({ id: 'area-fill', type: 'fill', source: 'area', paint: { 'fill-color': EMBER, 'fill-opacity': 0.1 } })
      map.addLayer({
        id: 'area-line',
        type: 'line',
        source: 'area',
        paint: { 'line-color': EMBER, 'line-width': 1.5, 'line-dasharray': [3, 2], 'line-opacity': 0.9 },
      })

      map.addSource('hotspots', { type: 'geojson', data: { type: 'FeatureCollection', features: [] } })
      // soft glow underneath, sharp dot on top
      map.addLayer({
        id: 'hotspots-glow',
        type: 'circle',
        source: 'hotspots',
        paint: {
          'circle-color': EMBER,
          'circle-radius': ['interpolate', ['linear'], ['zoom'], 3, 3, 10, 9],
          'circle-blur': 1,
          'circle-opacity': 0.35,
        },
      })
      map.addLayer({
        id: 'hotspots-dot',
        type: 'circle',
        source: 'hotspots',
        paint: {
          'circle-color': ['interpolate', ['linear'], ['get', 'frp'], 0, '#ffb070', 60, EMBER, 180, '#ff3d00'],
          'circle-radius': ['interpolate', ['linear'], ['zoom'], 3, 1.2, 10, 3.2],
        },
      })
      readyRef.current = true
      syncArea()
      syncHotspots()
    })

    // Slow idle spin until the user touches the globe or picks a place
    let spinning = true
    let frame = 0
    const stop = () => (spinning = false)
    map.on('mousedown', stop)
    map.on('touchstart', stop)
    map.on('wheel', stop)
    const spin = () => {
      if (spinning && !useApp.getState().place && map.getZoom() < 3) {
        const c = map.getCenter()
        map.setCenter([c.lng + 0.04, c.lat])
      }
      frame = requestAnimationFrame(spin)
    }
    frame = requestAnimationFrame(spin)

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
    const pts = useApp.getState().hotspots ?? []
    const src = map.getSource('hotspots') as maplibregl.GeoJSONSource | undefined
    src?.setData({
      type: 'FeatureCollection',
      features: pts.map((h) => ({
        type: 'Feature',
        properties: { frp: h.frp, date: h.date },
        geometry: { type: 'Point', coordinates: [h.lon, h.lat] },
      })),
    })
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
      // offset so the area is not hidden behind the left panel
      map.flyTo({
        center: [place.lon, place.lat],
        zoom: zoomForRadius(useApp.getState().radiusKm),
        offset: areaOffset(),
        duration: 2600,
        essential: true,
      })
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

  // The wrapper is positioned; MapLibre's own CSS would override position on the map div itself.
  return (
    <div className="absolute inset-0">
      <div ref={container} className="h-full w-full" aria-label="Interactive globe" />
    </div>
  )
}

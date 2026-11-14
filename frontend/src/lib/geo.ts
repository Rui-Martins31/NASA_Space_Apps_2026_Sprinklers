import type { Feature, Polygon } from 'geojson'
// Builds a circle polygon (GeoJSON) around a point, used to draw the
// analysis radius on the globe.
export function circlePolygon(lat: number, lon: number, radiusKm: number, steps = 96): Feature<Polygon> {
  const R = 6371
  const d = radiusKm / R
  const φ1 = (lat * Math.PI) / 180
  const λ1 = (lon * Math.PI) / 180
  const coords: [number, number][] = []
  for (let i = 0; i <= steps; i++) {
    const θ = (i / steps) * 2 * Math.PI
    const φ2 = Math.asin(Math.sin(φ1) * Math.cos(d) + Math.cos(φ1) * Math.sin(d) * Math.cos(θ))
    const λ2 = λ1 + Math.atan2(Math.sin(θ) * Math.sin(d) * Math.cos(φ1), Math.cos(d) - Math.sin(φ1) * Math.sin(φ2))
    coords.push([(λ2 * 180) / Math.PI, (φ2 * 180) / Math.PI])
  }
  return { type: 'Feature', properties: {}, geometry: { type: 'Polygon', coordinates: [coords] } }
}

/** Zoom level that roughly fits a circle of radiusKm on screen. */
export function zoomForRadius(radiusKm: number) {
  return Math.max(3, Math.min(12, 9.6 - Math.log2(radiusKm / 10)))
}

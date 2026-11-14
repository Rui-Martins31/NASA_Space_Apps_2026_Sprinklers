// Turns a place name into coordinates using Photon (free, OpenStreetMap data,
// built for search-as-you-type). The backend only ever receives lat/lon.
import type { Place } from '../types'

interface PhotonFeature {
  geometry: { coordinates: [number, number] }
  properties: {
    name?: string
    city?: string
    county?: string
    state?: string
    country?: string
    osm_value?: string
  }
}

export async function searchPlaces(query: string, signal?: AbortSignal): Promise<Place[]> {
  const q = query.trim()
  if (q.length < 2) return []

  // Raw "lat, lon" typed by the user: no need to call the geocoder.
  const coord = q.match(/^\s*(-?\d+(?:\.\d+)?)\s*[,;\s]\s*(-?\d+(?:\.\d+)?)\s*$/)
  if (coord) {
    const lat = parseFloat(coord[1])
    const lon = parseFloat(coord[2])
    if (Math.abs(lat) <= 90 && Math.abs(lon) <= 180) {
      return [{ label: `${lat.toFixed(4)}, ${lon.toFixed(4)}`, detail: '', lat, lon }]
    }
  }

  const url = `https://photon.komoot.io/api/?q=${encodeURIComponent(q)}&limit=6`
  const res = await fetch(url, { signal })
  if (!res.ok) throw new Error('Place search is unavailable right now')
  const data: { features: PhotonFeature[] } = await res.json()

  return data.features.map((f) => {
    const p = f.properties
    const [lon, lat] = f.geometry.coordinates
    const detail = [p.city !== p.name ? p.city : undefined, p.county, p.state, p.country]
      .filter((v, i, arr) => v && arr.indexOf(v) === i)
      .slice(0, 2)
      .join(', ')
    return { label: p.name ?? q, detail, lat, lon }
  })
}

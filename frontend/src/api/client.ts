import type { ApiRequest, ApiResponse, AreaQuery, Feature } from '../types'
import { mockFetch } from './mock'

// Mock data only when explicitly asked for (VITE_USE_MOCK=true).
const USE_MOCK = import.meta.env.VITE_USE_MOCK === 'true'

/** Most hotspots the backend returns in one request. */
export const MAX_HOTSPOTS = 50_000

// Dates in the UI are whole days; the backend wants datetimes (UTC).
function toApiRequest(feature: Feature, q: AreaQuery): ApiRequest {
  return {
    feature,
    lat: q.lat,
    lon: q.lon,
    radius: q.radiusKm,
    date_time_from: `${q.dateFrom}T00:00:00`,
    date_time_to: `${q.dateTo}T23:59:59`,
    ...(feature === 'hotspots' && q.maxPoints !== undefined && { max_points: q.maxPoints }),
  }
}

// One function for every feature: POST /api/<feature> with the request body.
export async function fetchFeature(feature: Feature, query: AreaQuery): Promise<ApiResponse> {
  const req = toApiRequest(feature, query)
  if (USE_MOCK) return mockFetch(feature, req)

  const res = await fetch(`/api/${feature}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  })
  if (!res.ok) {
    let message = `Server error (${res.status})`
    try {
      const body = await res.json()
      if (body?.error) message = body.error
    } catch {
      /* body was not JSON */
    }
    throw new Error(message)
  }
  return res.json()
}

export const usingMock = USE_MOCK

/**
 * Full hotspots CSV from GET /api/hotspots.csv (every hotspot, no max_points).
 * Returns the CSV text; the caller saves it.
 */
export async function fetchHotspotsCsv(query: AreaQuery): Promise<string> {
  const params = new URLSearchParams({
    lat: String(query.lat),
    lon: String(query.lon),
    radius: String(query.radiusKm),
    date_time_from: `${query.dateFrom}T00:00:00`,
    date_time_to: `${query.dateTo}T23:59:59`,
  })
  const res = await fetch(`/api/hotspots.csv?${params}`)
  if (!res.ok) {
    let message = `Server error (${res.status})`
    try {
      const body = await res.json()
      if (body?.error) message = body.error
    } catch {
      /* not JSON */
    }
    throw new Error(message)
  }
  return res.text()
}

/**
 * Number of hotspots in the area and period, counted from GET /api/hotspots.csv
 * (the same source as the CSV export, so both always agree). The file is read as
 * a stream and only its line breaks are counted, so nothing large is kept in memory.
 */
export async function countHotspots(query: AreaQuery, signal?: AbortSignal): Promise<number> {
  if (USE_MOCK) {
    const res = await fetchFeature('hotspots', { ...query, maxPoints: MAX_HOTSPOTS })
    return res.hotspots?.length ?? 0
  }
  const params = new URLSearchParams({
    lat: String(query.lat),
    lon: String(query.lon),
    radius: String(query.radiusKm),
    date_time_from: `${query.dateFrom}T00:00:00`,
    date_time_to: `${query.dateTo}T23:59:59`,
  })
  const res = await fetch(`/api/hotspots.csv?${params}`, { signal })
  if (!res.ok || !res.body) throw new Error(`Server error (${res.status})`)
  const reader = res.body.getReader()
  let lines = 0
  let lastByte = 10
  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    for (let i = 0; i < value.length; i++) if (value[i] === 10) lines++
    if (value.length) lastByte = value[value.length - 1]
  }
  if (lastByte !== 10) lines++ // last row without a line break
  return Math.max(0, lines - 1) // minus the header
}

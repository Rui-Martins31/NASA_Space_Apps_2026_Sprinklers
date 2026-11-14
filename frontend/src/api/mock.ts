// Fake backend used while the real one is not ready (VITE_USE_MOCK=true).
// It returns data in exactly the same shape as the agreed API.
import type { AnomalyEntry, ApiRequest, ApiResponse, CalendarEntry, Feature, Hotspot } from '../types'

// Small seeded random generator, so the same place always gives the same data.
function rng(seed: number) {
  let s = seed >>> 0
  return () => {
    s = (s * 1664525 + 1013904223) >>> 0
    return s / 2 ** 32
  }
}

// Typical Mediterranean fire season: quiet winter, peak in August.
const SEASON = [0.02, 0.03, 0.09, 0.06, 0.04, 0.1, 0.35, 0.8, 0.55, 0.2, 0.05, 0.02]
const BIG_YEARS: Record<number, number> = { 2003: 2.3, 2005: 2.6, 2016: 1.6, 2017: 2.9, 2024: 1.5, 2025: 2.2 }

function seedFor(req: ApiRequest) {
  return Math.round(req.lat * 1000) * 31 + Math.round(req.lon * 1000)
}

function buildCalendar(req: ApiRequest): CalendarEntry[] {
  const rand = rng(seedFor(req))
  const scale = (req.radius_km / 150) ** 2 * 1400 // more area, more hotspots
  const from = new Date(req.date_from)
  const to = new Date(req.date_to)
  const out: CalendarEntry[] = []
  for (let y = from.getFullYear(); y <= to.getFullYear(); y++) {
    for (let m = 1; m <= 12; m++) {
      const first = new Date(y, m - 1, 1)
      if (first > to) break
      if (new Date(y, m, 0) < from) continue
      const yearFactor = BIG_YEARS[y] ?? 0.6 + rand() * 0.5
      let count = SEASON[m - 1] * yearFactor * scale * (0.75 + rand() * 0.5)
      if (y === 2017 && m === 10) count *= 3.2 // October 2017 fires
      // current (partial) month: only count the days so far
      if (y === to.getFullYear() && m === to.getMonth() + 1) count *= to.getDate() / 30
      out.push({ year: y, month: m, count: Math.round(count) })
    }
  }
  return out
}

function buildAnomalies(calendar: CalendarEntry[]): AnomalyEntry[] {
  const means = Array.from({ length: 12 }, (_, i) => {
    const vals = calendar.filter((c) => c.month === i + 1).map((c) => c.count)
    return vals.reduce((a, b) => a + b, 0) / Math.max(vals.length, 1)
  })
  return calendar.map((c) => {
    const mean = Math.round(means[c.month - 1] * 10) / 10
    return { ...c, mean, anomaly: Math.round((c.count - mean) * 10) / 10 }
  })
}

function buildHotspots(req: ApiRequest, calendar: CalendarEntry[]): Hotspot[] {
  const rand = rng(seedFor(req) + 7)
  const total = calendar.reduce((a, c) => a + c.count, 0)
  const n = Math.min(total, req.max_points ?? 5000)
  const weights = calendar.map((c) => c.count / Math.max(total, 1))
  const out: Hotspot[] = []
  for (let i = 0; i < n; i++) {
    // pick a month proportionally to its count
    let r = rand(), k = 0
    while (k < weights.length - 1 && r > weights[k]) r -= weights[k++]
    const { year, month } = calendar[k]
    const ang = rand() * Math.PI * 2
    const dist = (req.radius_km / 111) * Math.sqrt(rand())
    const lat = req.lat + dist * Math.sin(ang)
    const lon = req.lon + (dist * Math.cos(ang)) / Math.cos((req.lat * Math.PI) / 180)
    const sats = year < 2012 ? ['Terra', 'Aqua'] : year < 2018 ? ['Aqua', 'S-NPP'] : ['S-NPP', 'NOAA-20', 'NOAA-21']
    out.push({
      lat: +lat.toFixed(4),
      lon: +lon.toFixed(4),
      date: `${year}-${String(month).padStart(2, '0')}-${String(1 + Math.floor(rand() * 28)).padStart(2, '0')}`,
      satellite: sats[Math.floor(rand() * sats.length)],
      confidence: ['low', 'nominal', 'high'][Math.floor(rand() * 3)],
      frp: +(2 + rand() ** 3 * 180).toFixed(1),
    })
  }
  return out
}

export async function mockFetch(feature: Feature, req: ApiRequest): Promise<ApiResponse> {
  await new Promise((r) => setTimeout(r, 500 + Math.random() * 400)) // pretend network
  if (req.radius_km < 1 || req.radius_km > 500) throw new Error('radius_km must be between 1 and 500')
  const calendar = buildCalendar(req)
  switch (feature) {
    case 'calendar':
      return { feature, calendar }
    case 'anomalies':
      return { feature, anomalies: buildAnomalies(calendar) }
    case 'hotspots':
      return { feature, hotspots: buildHotspots(req, calendar) }
    case 'all':
      return { feature, calendar, anomalies: buildAnomalies(calendar) }
  }
}

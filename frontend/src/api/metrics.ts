// One request per metric: POST /api/<code> with the usual body.
// The backend answers { feature, value, unit?, note? }.
// A 404 means the backend does not offer that metric yet.
import { usingMock } from './client'
import { metricKind } from '../lib/metricsCatalog'
import type { AreaQuery } from '../types'

export interface MetricResponse {
  feature: string
  value: unknown
  unit?: string
  note?: string
}

export class MetricMissing extends Error {}

export async function fetchMetric(code: string, q: AreaQuery): Promise<MetricResponse> {
  if (usingMock) return mockMetric(code, q)

  const res = await fetch(`/api/${code}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      feature: code,
      lat: q.lat,
      lon: q.lon,
      radius: q.radiusKm,
      date_time_from: `${q.dateFrom}T00:00:00`,
      date_time_to: `${q.dateTo}T23:59:59`,
    }),
  })
  if (res.status === 404 || res.status === 405) throw new MetricMissing(code)
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
  return res.json()
}

// ---------------------------------------------------------------------------
// Fake values while the pipeline is not ready (VITE_USE_MOCK=true).
// Same shapes as the real backend; a few metrics are "missing" or "null" on purpose
// so those states can be seen in the interface.

function rng(seed: number) {
  let s = seed >>> 0
  return () => {
    s = (s * 1664525 + 1013904223) >>> 0
    return s / 2 ** 32
  }
}

const MOCK_MISSING = new Set(['esp-05', 'esp-06', 'qa-06', 'qa-07', 'har-13', 'har-14'])
const MOCK_NULL: Record<string, string> = {
  'qa-05': 'Sem metadados de cobertura para esta região',
  'his-10': 'Menos de 10 anos completos no período',
}

async function mockMetric(code: string, q: AreaQuery): Promise<MetricResponse> {
  await new Promise((r) => setTimeout(r, 250 + Math.random() * 500))
  if (MOCK_MISSING.has(code)) throw new MetricMissing(code)
  if (MOCK_NULL[code]) return { feature: code, value: null, note: MOCK_NULL[code] }

  const seed = [...code].reduce((a, c) => a * 31 + c.charCodeAt(0), Math.round(q.lat * 100 + q.lon * 100 + q.radiusKm))
  const r = rng(seed)
  const scale = (q.radiusKm / 25) ** 2
  const season = [0.2, 0.3, 1, 0.8, 0.6, 3, 6, 9, 5, 2, 0.5, 0.3]

  switch (metricKind(code)) {
    case 'month':
      return { feature: code, value: { year: 2017, month: 6, count: Math.round(900 * scale) } }
    case 'year':
      return { feature: code, value: { year: 2017, count: Math.round(1200 * scale) } }
    case 'date':
      return { feature: code, value: { date: '2017-06-18', count: Math.round(310 * scale) } }
    case 'series12':
      return { feature: code, value: season.map((v) => Math.round(v * scale * (4 + r() * 2) * 10) / 10) }
    case 'band12':
      return {
        feature: code,
        value: season.map((v) => ({ low: Math.round(v * scale * 1.5), high: Math.round(v * scale * 12) })),
      }
    case 'breakdown':
      if (code === 'obs-04')
        return { feature: code, value: [{ key: 'D', value: Math.round(1800 * scale) }, { key: 'N', value: Math.round(700 * scale) }] }
      if (code === 'obs-02')
        return {
          feature: code,
          value: [
            { key: 'MODIS · low', value: Math.round(120 * scale) },
            { key: 'MODIS · nominal', value: Math.round(640 * scale) },
            { key: 'MODIS · high', value: Math.round(210 * scale) },
            { key: 'VIIRS · low', value: Math.round(300 * scale) },
            { key: 'VIIRS · nominal', value: Math.round(1900 * scale) },
            { key: 'VIIRS · high', value: Math.round(380 * scale) },
          ],
        }
      if (code === 'obs-09')
        return {
          feature: code,
          value: [
            { key: 'Vegetação (presumido)', value: Math.round(2900 * scale) },
            { key: 'Fonte estática', value: Math.round(40 * scale) },
            { key: 'Desconhecido', value: Math.round(80 * scale) },
          ],
        }
      return {
        feature: code,
        value: [
          { key: 'MODIS · Terra', value: Math.round(560 * scale) },
          { key: 'MODIS · Aqua', value: Math.round(610 * scale) },
          { key: 'VIIRS · S-NPP', value: Math.round(1450 * scale) },
          { key: 'VIIRS · NOAA-20', value: Math.round(980 * scale) },
          { key: 'VIIRS · NOAA-21', value: Math.round(260 * scale) },
        ],
      }
    case 'interval':
      return { feature: code, value: { value: 1.82, low: 1.61, high: 2.05 }, unit: 'multiplicador' }
    default: {
      const base: Record<string, [number, string?]> = {
        'cal-01': [3158 * scale],
        'cal-05': [3158 * scale],
        'cal-08': [125 * scale, 'Média de 25 anos completos (2001–2025)'],
        'cal-10': [612 * scale],
        'his-03': [-(r() * 4)],
        'his-04': [-(r() * 80)],
        'his-05': [-(r() * 1.5)],
        'his-06': [r() * 100],
        'his-09': [Math.round(14 * r())],
        'esp-01': [(3158 * scale) / ((Math.PI * q.radiusKm ** 2) / 1000)],
        'har-04': [0.87],
        'har-05': [0.84],
        'har-02': [0.41],
        'qa-01': [99.6],
        'qa-02': [92.3],
      }
      const [v, note] = base[code] ?? [Math.round(r() * 1000 * Math.max(1, scale))]
      return { feature: code, value: Number(v), note }
    }
  }
}

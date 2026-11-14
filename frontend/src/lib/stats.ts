// Numbers derived from the calendar on the frontend, so the backend only
// has to send the calendar: seasonal profile, ranking, current vs median.
import type { CalendarEntry, Hotspot } from '../types'

export const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

function quantile(sorted: number[], q: number) {
  if (!sorted.length) return 0
  const pos = (sorted.length - 1) * q
  const lo = Math.floor(pos)
  const hi = Math.ceil(pos)
  return sorted[lo] + (sorted[hi] - sorted[lo]) * (pos - lo)
}

/** The last month in the calendar is treated as the current one. */
export function currentEntry(cal: CalendarEntry[]) {
  return cal.length ? cal[cal.length - 1] : null
}

/** Same-month statistics over every other year. */
export function monthStats(cal: CalendarEntry[], month: number, excludeYear?: number) {
  const vals = cal
    .filter((c) => c.month === month && c.year !== excludeYear)
    .map((c) => c.count)
    .sort((a, b) => a - b)
  return { median: quantile(vals, 0.5), p10: quantile(vals, 0.1), p90: quantile(vals, 0.9), n: vals.length }
}

/** Share of the month covered when the period ends mid-month (e.g. 14 Nov → 14/30). */
export function monthFraction(entry: CalendarEntry, dateTo: string) {
  const d = new Date(dateTo)
  if (d.getFullYear() !== entry.year || d.getMonth() + 1 !== entry.month) return 1
  return d.getDate() / new Date(entry.year, entry.month, 0).getDate()
}

/** Compares the latest month with the same month in past years. If the
 *  month is not over yet, the median is scaled to the days covered so far. */
export function currentVsMedian(cal: CalendarEntry[], dateTo: string) {
  const cur = currentEntry(cal)
  if (!cur) return null
  const frac = monthFraction(cur, dateTo)
  const full = monthStats(cal, cur.month, cur.year)
  const s = { ...full, median: full.median * frac, p10: full.p10 * frac, p90: full.p90 * frac }
  const pct = s.median > 0 ? ((cur.count - s.median) / s.median) * 100 : 0
  const status = cur.count > s.p90 ? 'extreme' : pct > 15 ? 'above' : pct < -15 ? 'below' : 'normal'
  return { ...cur, ...s, pct, status, partial: frac < 1 } as const
}

export function seasonalProfile(cal: CalendarEntry[]) {
  const cur = currentEntry(cal)
  return MONTHS.map((name, i) => {
    const s = monthStats(cal, i + 1, cur?.year)
    const thisYear = cal.find((c) => c.year === cur?.year && c.month === i + 1)
    return {
      name,
      median: Math.round(s.median),
      band: [Math.round(s.p10), Math.round(s.p90)] as [number, number],
      current: thisYear ? thisYear.count : null,
    }
  })
}

export function yearTotals(cal: CalendarEntry[]) {
  const map = new Map<number, number>()
  for (const c of cal) map.set(c.year, (map.get(c.year) ?? 0) + c.count)
  return [...map.entries()].map(([year, count]) => ({ year, count }))
}

export function topMonths(cal: CalendarEntry[], n = 5) {
  return [...cal].sort((a, b) => b.count - a.count).slice(0, n)
}

/** Yearly anomaly = sum over the year of (count - monthly mean). */
export function yearlyAnomalies(anoms: { year: number; anomaly: number }[]) {
  const map = new Map<number, number>()
  for (const a of anoms) map.set(a.year, (map.get(a.year) ?? 0) + a.anomaly)
  return [...map.entries()].map(([year, anomaly]) => ({ year, anomaly: Math.round(anomaly) }))
}

export function downloadCsv(filename: string, rows: object[]) {
  if (!rows.length) return
  const cols = Object.keys(rows[0])
  const esc = (v: unknown) => {
    const s = String(v ?? '')
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
  }
  const body = [cols.join(','), ...rows.map((r) => cols.map((c) => esc((r as Record<string, unknown>)[c])).join(','))].join('\n')
  const url = URL.createObjectURL(new Blob([body], { type: 'text/csv;charset=utf-8' }))
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

export function hotspotsFilename(place: string, from: string, to: string) {
  const slug = place.normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/[^a-zA-Z0-9]+/g, '-').toLowerCase()
  return `hotspots_${slug}_${from}_${to}.csv`
}

export type HotspotRow = Hotspot

// Cividis: colour-blind safe sequential scale (see DESIGN.md)
const CIVIDIS = ['#00224e', '#123570', '#3b496c', '#575d6d', '#707173', '#8a8678', '#a59c74', '#c3b369', '#e1cc55', '#fee838']
export function cividis(t: number) {
  const x = Math.min(1, Math.max(0, t)) * (CIVIDIS.length - 1)
  const i = Math.floor(x)
  const j = Math.min(i + 1, CIVIDIS.length - 1)
  const f = x - i
  const h = (s: string, k: number) => parseInt(s.slice(1 + k * 2, 3 + k * 2), 16)
  const c = [0, 1, 2].map((k) => Math.round(h(CIVIDIS[i], k) + (h(CIVIDIS[j], k) - h(CIVIDIS[i], k)) * f))
  return `rgb(${c[0]} ${c[1]} ${c[2]})`
}
export const CIVIDIS_STOPS = CIVIDIS

export const fmt = (n: number) => Math.round(n).toLocaleString('en')

// Numbers derived from the calendar on the frontend, so the backend only
// has to send the calendar: summary cards, seasonal profile, ranking, scales.
import type { CalendarEntry } from '../types'

/** English short month names (used in file names and as a fallback). */
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
  const mean = vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : 0
  return { mean, median: quantile(vals, 0.5), p10: quantile(vals, 0.1), p90: quantile(vals, 0.9), n: vals.length }
}

/** Mean of each month (1..12) over all years in the calendar (fallback only). */
export function monthlyMeans(cal: CalendarEntry[]) {
  return Array.from({ length: 12 }, (_, i) => monthStats(cal, i + 1).mean)
}

/**
 * Reference mean of each calendar month (index 0 = January), as computed by the
 * pipeline and sent by the backend in anomalies[].mean. The frontend does not
 * compute its own means; it only falls back to the calendar when the backend
 * sent no anomalies (e.g. an old backend).
 */
export function referenceMeans(anomalies: { month: number; mean: number }[] | null, cal: CalendarEntry[]) {
  if (anomalies?.length) {
    const means: (number | undefined)[] = Array(12).fill(undefined)
    for (const a of anomalies) if (means[a.month - 1] === undefined) means[a.month - 1] = a.mean
    if (means.every((m) => m !== undefined)) return { means: means as number[], fromPipeline: true }
    const fallback = monthlyMeans(cal)
    return { means: means.map((m, i) => m ?? fallback[i]), fromPipeline: true }
  }
  return { means: monthlyMeans(cal), fromPipeline: false }
}

/** Expected yearly total = sum of the 12 monthly reference means. */
export const referenceAnnual = (means: number[]) => means.reduce((a, b) => a + b, 0)

/** Share of the month covered when the period ends mid-month (e.g. 14 Nov → 14/30). */
export function monthFraction(entry: { year: number; month: number }, dateTo: string) {
  const d = new Date(dateTo)
  if (d.getFullYear() !== entry.year || d.getMonth() + 1 !== entry.month) return 1
  return d.getDate() / new Date(entry.year, entry.month, 0).getDate()
}

/** Compares the latest month with the same month in other years. If the
 *  month is not over yet, the mean is scaled to the days covered so far. */
export function currentVsMean(cal: CalendarEntry[], dateTo: string, means: number[]) {
  const cur = currentEntry(cal)
  if (!cur) return null
  const frac = monthFraction(cur, dateTo)
  const mean = means[cur.month - 1] * frac
  const pct = mean > 0 ? ((cur.count - mean) / mean) * 100 : 0
  return { ...cur, mean, diff: cur.count - mean, pct, partial: frac < 1 }
}

export function yearTotals(cal: CalendarEntry[]) {
  const map = new Map<number, { count: number; months: number }>()
  for (const c of cal) {
    const v = map.get(c.year) ?? { count: 0, months: 0 }
    map.set(c.year, { count: v.count + c.count, months: v.months + 1 })
  }
  return [...map.entries()].map(([year, v]) => ({ year, count: v.count, complete: v.months === 12 }))
}

/** Numbers for the summary cards (W5). */
export function summary(cal: CalendarEntry[]) {
  const total = cal.reduce((a, c) => a + c.count, 0)
  const peakMonth = cal.reduce<CalendarEntry | null>((best, c) => (!best || c.count > best.count ? c : best), null)
  const years = yearTotals(cal)
  const peakYear = years.reduce<(typeof years)[number] | null>((best, y) => (!best || y.count > best.count ? y : best), null)
  const complete = years.filter((y) => y.complete)
  const basis = complete.length ? complete : years
  const annualAvg = basis.length ? basis.reduce((a, y) => a + y.count, 0) / basis.length : 0
  return { total, peakMonth, peakYear, annualAvg }
}

export function topMonths(cal: CalendarEntry[], n = 5) {
  return [...cal].sort((a, b) => b.count - a.count).slice(0, n)
}

/** Per-month profile: mean and P10–P90 band over all years, plus one chosen year. */
export function seasonalProfile(cal: CalendarEntry[], year: number, means: number[]) {
  return Array.from({ length: 12 }, (_, i) => {
    const s = monthStats(cal, i + 1, year)
    const chosen = cal.find((c) => c.year === year && c.month === i + 1)
    const value = chosen ? chosen.count : null
    return {
      month: i + 1,
      mean: Math.round(means[i] * 10) / 10,
      band: [Math.round(s.p10), Math.round(s.p90)] as [number, number],
      value,
      above: value !== null && s.n > 0 && value > s.p90,
    }
  })
}

/** Yearly total minus the reference yearly total (sum of the pipeline's monthly means). */
export function yearlyAnomalies(cal: CalendarEntry[], means: number[]) {
  const mean = referenceAnnual(means)
  return { mean, rows: yearTotals(cal).map((y) => ({ ...y, anomaly: Math.round(y.count - mean) })) }
}

// ---------------------------------------------------------------------------
// Calendar colour scales (C2, C6). Every scale has 7 classes plus a legend.

export interface ScaleClass {
  color: string
  label: string
}
export interface CalendarScaleInfo {
  classes: ScaleClass[]
  /** class index for a calendar entry (or -1 for "zero" in the count scale) */
  classify: (c: CalendarEntry) => number
  value: (c: CalendarEntry) => number
  format: (v: number) => string
  zero?: ScaleClass
}

// Cividis (colour-blind safe) sampled into 7 classes, dark → bright
const SEQ = ['#00224e', '#2a3f6c', '#4f5a6f', '#727274', '#988e72', '#c3b369', '#fee838']
// Diverging for anomalies, tuned for a dark background: blue below, neutral, ember above
const DIV = ['#6aa8ff', '#3f74c0', '#2a4566', '#2a2f38', '#6e3420', '#b5501d', '#ff7a2e']

export const fmt = (n: number) => Math.round(n).toLocaleString('en')
const fmtSigned = (n: number) => `${n > 0 ? '+' : ''}${fmt(n)}`

export function calendarScale(cal: CalendarEntry[], kind: 'absolute' | 'relative' | 'anomaly', means: number[]): CalendarScaleInfo {
  const max = Math.max(1, ...cal.map((c) => c.count))

  if (kind === 'absolute') {
    // logarithmic class breaks between 1 and the max
    // (linear steps when the counts are tiny, so labels never repeat)
    const breaks =
      max < 8
        ? Array.from({ length: 8 }, (_, i) => 1 + (i * (max - 1)) / 7)
        : Array.from({ length: 8 }, (_, i) => (i === 0 ? 1 : Math.max(1, Math.round(max ** (i / 7)))))
    const classes = SEQ.map((color, i) => ({
      color,
      label: i === 6 ? `${fmt(breaks[i])}–${fmt(max)}` : `${fmt(breaks[i])}–${fmt(Math.max(breaks[i], breaks[i + 1] - 1))}`,
    }))
    return {
      classes,
      zero: { color: '#11161d', label: '0' },
      value: (c) => c.count,
      format: fmt,
      classify: (c) => {
        if (c.count <= 0) return -1
        for (let i = 6; i >= 0; i--) if (c.count >= breaks[i]) return i
        return 0
      },
    }
  }

  if (kind === 'relative') {
    const classes = SEQ.map((color, i) => ({
      color,
      label: `${Math.round((i / 7) * 100)}–${Math.round(((i + 1) / 7) * 100)}%`,
    }))
    return {
      classes,
      value: (c) => (c.count / max) * 100,
      format: (v) => `${Math.round(v)}%`,
      classify: (c) => Math.min(6, Math.floor((c.count / max) * 7)),
    }
  }

  // anomaly: count minus the reference mean of the same month, symmetric classes
  const dev = (c: CalendarEntry) => c.count - means[c.month - 1]
  const lim = Math.max(1, ...cal.map((c) => Math.abs(dev(c))))
  const edges = [-1, -0.6, -0.25, -0.05, 0.05, 0.25, 0.6, 1].map((e) => e * lim)
  const classes = DIV.map((color, i) => ({
    color,
    label: i === 3 ? '≈ 0' : `${fmtSigned(edges[i])} → ${fmtSigned(edges[i + 1])}`,
  }))
  return {
    classes,
    value: dev,
    format: fmtSigned,
    classify: (c) => {
      const d = dev(c)
      for (let i = 0; i < 7; i++) if (d <= edges[i + 1]) return i
      return 6
    },
  }
}

// ---------------------------------------------------------------------------
// CSV export

export function downloadCsv(filename: string, rows: object[]) {
  if (!rows.length) return
  const cols = Object.keys(rows[0])
  const esc = (v: unknown) => {
    const s = String(v ?? '')
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
  }
  const body = [cols.join(','), ...rows.map((r) => cols.map((c) => esc((r as Record<string, unknown>)[c])).join(','))].join('\n')
  // The BOM (﻿) makes Excel read the file as UTF-8, so accents show correctly.
  downloadBlob(filename, new Blob(['﻿' + body], { type: 'text/csv;charset=utf-8' }))
}

export function downloadBlob(filename: string, blob: Blob) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

export function slug(s: string) {
  return s.normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/[^a-zA-Z0-9]+/g, '-').replace(/^-|-$/g, '').toLowerCase()
}

export function hotspotsFilename(place: string, from: string, to: string) {
  return `hotspots_${slug(place)}_${from}_${to}.csv`
}

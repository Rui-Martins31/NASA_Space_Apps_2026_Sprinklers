// Chart export (PNG / SVG) and the printable PDF report (W10).
// Every exported file carries the area, the period, the generation date and the source.
import type { CalendarEntry } from '../types'
import { calendarScale, downloadBlob, fmt, monthlyMeans, slug, summary, yearTotals } from './stats'
import { monthName, translate, type Lang } from '../i18n'

export interface ExportMeta {
  title: string
  place: string
  radiusKm: number
  dateFrom: string
  dateTo: string
  lang: Lang
}

const FONT = "'IBM Plex Sans', 'Helvetica Neue', Arial, sans-serif"
const MONO = "'IBM Plex Mono', Menlo, monospace"
const BG = '#0d1117'
const FG = '#e8ecf2'
const MUTED = '#8b95a5'

const esc = (s: string) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')

function subtitle(m: ExportMeta) {
  return `${m.place} · ${m.radiusKm} km · ${m.dateFrom} → ${m.dateTo}`
}
function footer(m: ExportMeta) {
  return `${translate(m.lang, 'report.generated')} ${new Date().toISOString().slice(0, 10)} · ${translate(m.lang, 'report.source')}`
}

/** Puts a chart (SVG markup of size w×h) inside a frame with title, subtitle and footer. */
export function frameSvg(inner: string, w: number, h: number, m: ExportMeta) {
  const W = w + 48
  const H = h + 120
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">
<rect width="${W}" height="${H}" fill="${BG}"/>
<text x="24" y="38" font-family="${FONT}" font-size="20" font-weight="600" fill="${FG}">${esc(m.title)}</text>
<text x="24" y="60" font-family="${MONO}" font-size="12" fill="${MUTED}">${esc(subtitle(m))}</text>
<g transform="translate(24,80)">${inner}</g>
<text x="24" y="${H - 16}" font-family="${FONT}" font-size="10.5" fill="${MUTED}">${esc(footer(m))}</text>
</svg>`
}

/** The burning calendar drawn as SVG (same colours and scale as on screen). */
export function calendarSvg(cal: CalendarEntry[], kind: 'absolute' | 'relative' | 'anomaly', lang: Lang, dataStart: string) {
  const scale = calendarScale(cal, kind)
  const byKey = new Map(cal.map((c) => [`${c.year}-${c.month}`, c]))
  const years = [...new Set(cal.map((c) => c.year))].sort((a, b) => b - a)
  const totals = new Map(yearTotals(cal).map((y) => [y.year, y.count]))
  const means = monthlyMeans(cal)
  const startY = Number(dataStart.slice(0, 4))
  const startM = Number(dataStart.slice(5, 7))
  const cw = 46
  const ch = 16
  const left = 44
  const top = 18
  const w = left + 12 * cw + 70
  const rows: string[] = []

  for (let m = 1; m <= 12; m++)
    rows.push(`<text x="${left + (m - 1) * cw + cw / 2}" y="12" text-anchor="middle" font-family="${FONT}" font-size="10" fill="${MUTED}">${monthName(m, lang)}</text>`)
  rows.push(`<text x="${left + 12 * cw + 8}" y="12" font-family="${FONT}" font-size="10" fill="${MUTED}">${translate(lang, 'cal.total')}</text>`)

  years.forEach((y, r) => {
    const yy = top + r * (ch + 3)
    rows.push(`<text x="${left - 8}" y="${yy + 12}" text-anchor="end" font-family="${MONO}" font-size="10" fill="${MUTED}">${y}</text>`)
    for (let m = 1; m <= 12; m++) {
      const x = left + (m - 1) * cw
      const c = byKey.get(`${y}-${m}`)
      if (c) {
        const k = scale.classify(c)
        const color = k < 0 ? scale.zero!.color : scale.classes[k].color
        rows.push(`<rect x="${x + 1}" y="${yy}" width="${cw - 3}" height="${ch}" rx="2" fill="${color}"/>`)
      } else if (y < startY || (y === startY && m < startM)) {
        rows.push(`<rect x="${x + 1}" y="${yy}" width="${cw - 3}" height="${ch}" rx="2" fill="url(#hatch)"/>`)
      }
    }
    rows.push(`<text x="${left + 12 * cw + 8}" y="${yy + 12}" font-family="${MONO}" font-size="10" fill="${FG}">${fmt(totals.get(y) ?? 0)}</text>`)
  })
  const fy = top + years.length * (ch + 3) + 14
  rows.push(`<text x="${left - 8}" y="${fy}" text-anchor="end" font-family="${FONT}" font-size="10" fill="${MUTED}">${translate(lang, 'cal.mean')}</text>`)
  means.forEach((v, i) =>
    rows.push(`<text x="${left + i * cw + cw / 2}" y="${fy}" text-anchor="middle" font-family="${MONO}" font-size="10" fill="${FG}">${fmt(v)}</text>`),
  )

  // legend
  const ly = fy + 22
  const items = [...(scale.zero ? [scale.zero] : []), ...scale.classes]
  items.forEach((it, i) => {
    const x = left + i * 74
    rows.push(`<rect x="${x}" y="${ly}" width="14" height="10" rx="2" fill="${it.color}"/>`)
    rows.push(`<text x="${x + 18}" y="${ly + 9}" font-family="${MONO}" font-size="9" fill="${MUTED}">${esc(it.label)}</text>`)
  })
  const h = ly + 18
  const defs = `<defs><pattern id="hatch" width="5" height="5" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="5" height="5" fill="#161b23"/><line x1="0" y1="0" x2="0" y2="5" stroke="#3a4250" stroke-width="2"/></pattern></defs>`
  return { svg: defs + rows.join(''), w, h }
}

/** Yearly totals with the historical mean as a dashed line (used in the report). */
export function yearlySvg(cal: CalendarEntry[], lang: Lang) {
  const years = yearTotals(cal)
  const { annualAvg } = summary(cal)
  const w = 640
  const h = 200
  const max = Math.max(1, ...years.map((y) => y.count))
  const bw = (w - 50) / Math.max(1, years.length)
  const yOf = (v: number) => h - 20 - (v / max) * (h - 30)
  const parts = years.map((y, i) => {
    const x = 50 + i * bw
    return `<rect x="${x + 1}" y="${yOf(y.count)}" width="${Math.max(1, bw - 2)}" height="${h - 20 - yOf(y.count)}" fill="#ff6b1a" fill-opacity="${y.complete ? 1 : 0.35}"/>${
      i % 3 === 0 ? `<text x="${x + bw / 2}" y="${h - 6}" text-anchor="middle" font-family="${MONO}" font-size="9" fill="${MUTED}">${y.year}</text>` : ''
    }`
  })
  const my = yOf(annualAvg)
  parts.push(`<line x1="50" x2="${w}" y1="${my}" y2="${my}" stroke="${FG}" stroke-dasharray="5 4"/>`)
  parts.push(`<text x="46" y="${my + 3}" text-anchor="end" font-family="${MONO}" font-size="9" fill="${FG}">${fmt(annualAvg)}</text>`)
  parts.push(`<text x="${w}" y="${my - 5}" text-anchor="end" font-family="${FONT}" font-size="10" fill="${FG}">${translate(lang, 'trend.mean')}</text>`)
  return { svg: parts.join(''), w, h }
}

export function downloadSvg(svg: string, filename: string) {
  downloadBlob(filename, new Blob([svg], { type: 'image/svg+xml;charset=utf-8' }))
}

export async function downloadPng(svg: string, filename: string) {
  const img = new Image()
  const url = URL.createObjectURL(new Blob([svg], { type: 'image/svg+xml;charset=utf-8' }))
  await new Promise<void>((resolve, reject) => {
    img.onload = () => resolve()
    img.onerror = () => reject(new Error('Could not render the image'))
    img.src = url
  })
  const scale = 2 // sharp on retina screens and in slides
  const canvas = document.createElement('canvas')
  canvas.width = img.width * scale
  canvas.height = img.height * scale
  const ctx = canvas.getContext('2d')!
  ctx.scale(scale, scale)
  ctx.drawImage(img, 0, 0)
  URL.revokeObjectURL(url)
  const blob = await new Promise<Blob | null>((r) => canvas.toBlob(r, 'image/png'))
  if (blob) downloadBlob(filename, blob)
}

/** Takes a Recharts chart from the page and returns its SVG with inline colours. */
export function chartFromDom(container: HTMLElement | null) {
  const svg = container?.querySelector('svg.recharts-surface') as SVGSVGElement | null
  if (!svg) return null
  const clone = svg.cloneNode(true) as SVGSVGElement
  const w = svg.clientWidth || Number(svg.getAttribute('width')) || 500
  const h = svg.clientHeight || Number(svg.getAttribute('height')) || 300
  clone.removeAttribute('class')
  clone.setAttribute('width', String(w))
  clone.setAttribute('height', String(h))
  return { svg: new XMLSerializer().serializeToString(clone), w, h }
}

export function exportFilename(m: ExportMeta, ext: string) {
  return `firecal_${slug(m.title)}_${slug(m.place)}_${m.dateFrom}_${m.dateTo}.${ext}`
}

/** Opens a printable summary page; the browser's "Save as PDF" makes the PDF. */
export function openReport(
  cal: CalendarEntry[],
  m: ExportMeta,
  kind: 'absolute' | 'relative' | 'anomaly',
  dataStart: string,
  win: Window | null = window.open('', '_blank'),
) {
  const t = (k: Parameters<typeof translate>[1], v?: Record<string, string | number>) => translate(m.lang, k, v)
  const s = summary(cal)
  const calSvg = calendarSvg(cal, kind, m.lang, dataStart)
  const yearly = yearlySvg(cal, m.lang)
  const peak = s.peakMonth ? `${monthName(s.peakMonth.month, m.lang, 'long')} ${s.peakMonth.year} (${fmt(s.peakMonth.count)})` : '—'
  const means = monthlyMeans(cal)

  const html = `<!doctype html><html lang="${m.lang}"><head><meta charset="utf-8"><title>${esc(t('report.title'))} – ${esc(m.place)}</title>
<style>
  @page { size: A4; margin: 14mm; }
  body { font-family: ${FONT}; color: #111; margin: 0; }
  h1 { font-size: 22px; margin: 0 0 4px; }
  .sub { font-family: ${MONO}; font-size: 12px; color: #555; margin-bottom: 16px; }
  .cards { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; margin-bottom: 16px; }
  .card { border: 1px solid #ddd; border-radius: 8px; padding: 8px 10px; }
  .card b { display: block; font-family: ${MONO}; font-size: 18px; margin-top: 2px; }
  .card span { font-size: 11px; color: #555; text-transform: uppercase; letter-spacing: .06em; }
  h2 { font-size: 14px; margin: 18px 0 6px; }
  .chart { background: ${BG}; border-radius: 8px; padding: 10px; }
  table { border-collapse: collapse; font-family: ${MONO}; font-size: 11px; width: 100%; }
  td, th { border: 1px solid #ddd; padding: 3px 4px; text-align: center; }
  .foot { margin-top: 18px; font-size: 10px; color: #666; }
  @media print { .noprint { display: none; } }
  @media screen { body { max-width: 900px; margin: 24px auto; padding: 0 16px; } }
</style></head><body>
<button class="noprint" onclick="print()" style="float:right;padding:6px 12px">PDF / Print</button>
<h1>${esc(t('report.title'))}</h1>
<div class="sub">${esc(t('report.area'))}: ${esc(m.place)} · ${m.radiusKm} km &nbsp;|&nbsp; ${esc(t('report.period'))}: ${m.dateFrom} → ${m.dateTo}</div>
<div class="cards">
  <div class="card"><span>${esc(t('kpi.total'))}</span><b>${fmt(s.total)}</b></div>
  <div class="card"><span>${esc(t('kpi.peakMonth'))}</span><b style="font-size:13px">${esc(peak)}</b></div>
  <div class="card"><span>${esc(t('kpi.avg'))}</span><b>${fmt(s.annualAvg)}</b></div>
  <div class="card"><span>${esc(t('kpi.peakYearLabel'))}</span><b>${s.peakYear?.year ?? '—'}</b></div>
</div>
<h2>${esc(t('view.calendar'))}</h2>
<div class="chart"><svg xmlns="http://www.w3.org/2000/svg" width="100%" viewBox="0 0 ${calSvg.w} ${calSvg.h}">${calSvg.svg}</svg></div>
<h2>${esc(t('trend.yAnnual'))}</h2>
<div class="chart"><svg xmlns="http://www.w3.org/2000/svg" width="100%" viewBox="0 0 ${yearly.w} ${yearly.h}">${yearly.svg}</svg></div>
<h2>${esc(t('report.monthlyMeans'))}</h2>
<table><tr>${means.map((_, i) => `<th>${monthName(i + 1, m.lang)}</th>`).join('')}</tr><tr>${means.map((v) => `<td>${fmt(v)}</td>`).join('')}</tr></table>
<p class="foot">${esc(footer(m))}<br>${esc(t('about.source'))}</p>
<script>setTimeout(() => print(), 400)</script>
</body></html>`

  if (!win) return false
  win.document.open()
  win.document.write(html)
  win.document.close()
  return true
}

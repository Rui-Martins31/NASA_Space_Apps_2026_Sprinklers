// Catalogue of metrics, read straight from the team's CSV (single source of truth).
// The frontend only DISPLAYS metrics: every value comes from the backend
// (POST /api/<metric id in lowercase>). Here we only keep:
//   - names / descriptions (from the CSV)
//   - how each value is shaped, so we know how to draw it (KIND below)
import csvText from '../../../spec/metricas_modis_viirs.csv?raw'
import type { Lang } from '../i18n'

export interface MetricDef {
  id: string // "CAL-05"
  code: string // "cal_05" = backend feature name and endpoint
  category: string
  name: string
  description: string
  unit: string
  calculation: string
  priority: string // MVP | Desejável | Opcional | Extra | Validação | ...
  nameEn?: string
  descriptionEn?: string
}

/** Small CSV parser (handles quotes and commas inside quotes). */
function parseCsv(text: string): string[][] {
  const rows: string[][] = []
  let row: string[] = []
  let cell = ''
  let quoted = false
  text = text.replace(/^﻿/, '')
  for (let i = 0; i < text.length; i++) {
    const ch = text[i]
    if (quoted) {
      if (ch === '"' && text[i + 1] === '"') {
        cell += '"'
        i++
      } else if (ch === '"') quoted = false
      else cell += ch
    } else if (ch === '"') quoted = true
    else if (ch === ',') {
      row.push(cell)
      cell = ''
    } else if (ch === '\n' || ch === '\r') {
      if (ch === '\r' && text[i + 1] === '\n') i++
      row.push(cell)
      if (row.some((c) => c.trim())) rows.push(row)
      row = []
      cell = ''
    } else cell += ch
  }
  row.push(cell)
  if (row.some((c) => c.trim())) rows.push(row)
  return rows
}

// Categories not shown in the app: test metrics and external data (out of MVP)
const HIDDEN_PREFIXES = ['APP-', 'EXT-']

export const METRICS: MetricDef[] = (() => {
  const [header, ...rows] = parseCsv(csvText)
  const col = (name: string) => header.indexOf(name)
  return rows
    .map((r) => {
      const get = (name: string) => (col(name) >= 0 ? (r[col(name)] ?? '').trim() : '')
      return {
        id: get('id'),
        code: get('id').toLowerCase().replace(/-/g, '_'),
        category: get('categoria'),
        name: get('nome_metrica'),
        description: get('descricao'),
        unit: get('unidade'),
        calculation: get('calculo'),
        priority: get('prioridade'),
        nameEn: get('nome_metrica_en') || undefined, // optional columns, if the team adds them
        descriptionEn: get('descricao_en') || undefined,
      }
    })
    .filter((m) => m.id && !HIDDEN_PREFIXES.some((p) => m.id.startsWith(p)))
})()

export const DEFAULT_SELECTION = METRICS.filter((m) => m.priority === 'MVP').map((m) => m.code)

/** Categories in the order they appear in the CSV. */
export const CATEGORIES = [...new Set(METRICS.map((m) => m.category))]

const CATEGORY_EN: Record<string, string> = {
  'Calendário e resumo': 'Calendar & summary',
  'Comparação histórica': 'Historical comparison',
  'Distribuição espacial': 'Spatial distribution',
  'Características das deteções': 'Detection characteristics',
  'Ingestão e qualidade': 'Ingestion & quality',
  'Validação da harmonização': 'Harmonization validation',
}
const PRIORITY_EN: Record<string, string> = {
  MVP: 'MVP',
  Desejável: 'Desirable',
  Opcional: 'Optional',
  Extra: 'Extra',
  Validação: 'Validation',
}

export const categoryLabel = (c: string, lang: Lang) => (lang === 'en' ? (CATEGORY_EN[c] ?? c) : c)
export const priorityLabel = (p: string, lang: Lang) => (lang === 'en' ? (PRIORITY_EN[p] ?? p) : p)
export const metricName = (m: MetricDef, lang: Lang) => (lang === 'en' && m.nameEn ? m.nameEn : m.name)
export const metricDescription = (m: MetricDef, lang: Lang) => (lang === 'en' && m.descriptionEn ? m.descriptionEn : m.description)

// ---------------------------------------------------------------------------
// The shape of `value` is recognised from the value itself (see MetricsView),
// so a metric that changes shape on the backend still displays.
// This list is only used to build fake values (VITE_USE_MOCK=true).

export type MetricKind =
  | 'number'
  | 'month'
  | 'year'
  | 'date'
  | 'series12'
  | 'band12'
  | 'breakdown'
  | 'interval'
  | 'perMonth'
  | 'perDay'
  | 'perYear'

const KIND: Record<string, MetricKind> = {
  cal_02: 'perDay', // [{date, value}]
  cal_03: 'perMonth', // [{year, month, value}]
  cal_04: 'perYear', // [{year, value}]
  cal_06: 'month', // {year, month, count}
  cal_07: 'year', // {year, count}
  cal_09: 'perMonth',
  cal_11: 'date', // {date, count}
  cal_12: 'series12', // [12 numbers]
  his_01: 'series12',
  his_02: 'band12', // [12 × {low, high}]
  his_03: 'perMonth',
  his_04: 'perMonth',
  his_05: 'perMonth',
  his_06: 'perMonth',
  his_07: 'perMonth',
  his_08: 'perMonth',
  his_09: 'perYear',
  obs_01: 'breakdown', // [{key, value}]
  obs_02: 'breakdown',
  obs_04: 'breakdown',
  obs_07: 'date',
  obs_09: 'breakdown',
  har_06: 'interval', // {value, low, high}
  har_07: 'interval',
}

export const metricKind = (code: string): MetricKind => KIND[code] ?? 'number'

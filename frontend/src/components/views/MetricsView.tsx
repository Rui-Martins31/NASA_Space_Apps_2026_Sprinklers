import { useEffect, useState, type ReactNode } from 'react'
import clsx from 'clsx'
import { CircleNotch, Info, SlidersHorizontal } from '@phosphor-icons/react'
import { useApp, type MetricResult } from '../../store'
import { monthName, locale, useT, type Lang } from '../../i18n'
import {
  CATEGORIES,
  DEFAULT_SELECTION,
  METRICS,
  categoryLabel,
  metricDescription,
  metricName,
  metricNote,
  metricUnit,
  metricCalculation,
  priorityLabel,
  type MetricDef,
} from '../../lib/metricsCatalog'

// Metrics panel: shows values computed by the pipeline (one backend feature
// per metric). Nothing is calculated here; values are only formatted.

const num = (v: number, lang: Lang) =>
  new Intl.NumberFormat(locale(lang), { maximumFractionDigits: Math.abs(v) < 10 ? 2 : Math.abs(v) < 100 ? 1 : 0 }).format(v)

type Obj = Record<string, unknown>
const isObj = (v: unknown): v is Obj => typeof v === 'object' && v !== null && !Array.isArray(v)

function Bars({ values, lang, band }: { values: (number | { low: number; high: number })[]; lang: Lang; band?: boolean }) {
  const highs = values.map((v) => (typeof v === 'number' ? v : v.high))
  const max = Math.max(1e-9, ...highs)
  return (
    <div className="mt-1 grid grid-cols-12 items-end gap-1">
      {values.map((v, i) => {
        const lo = typeof v === 'number' ? 0 : v.low
        const hi = typeof v === 'number' ? v : v.high
        return (
          <div key={i} className="flex flex-col items-center gap-1" title={band ? `${num(lo, lang)} – ${num(hi, lang)}` : num(hi, lang)}>
            <div className="relative h-12 w-full rounded-[2px] bg-ink-800">
              <div
                className={clsx('absolute inset-x-0 rounded-[2px]', band ? 'bg-cool-400/60' : 'bg-ember-500')}
                style={{ bottom: `${(lo / max) * 100}%`, height: `${Math.max(2, ((hi - lo) / max) * 100)}%` }}
              />
            </div>
            <span className="text-[9.5px] text-fg-muted">{monthName(i + 1, lang).slice(0, 1)}</span>
          </div>
        )
      })}
    </div>
  )
}

type Point = { label: string; value: number | null }

/** Line for a time series (per day / month / year). Values come from the backend as they are. */
function Series({ points, lang }: { points: Point[]; lang: Lang }) {
  const vals = points.map((p) => p.value)
  const nums = vals.filter((v): v is number => v !== null)
  if (!nums.length) return null
  const min = Math.min(0, ...nums)
  const max = Math.max(...nums, min + 1e-9)
  const W = 400
  const H = 56
  const x = (i: number) => (points.length === 1 ? W / 2 : (i / (points.length - 1)) * W)
  const y = (v: number) => H - 2 - ((v - min) / (max - min)) * (H - 4)
  let d = ''
  let pen = false
  vals.forEach((v, i) => {
    if (v === null) pen = false
    else {
      d += `${pen ? 'L' : 'M'}${x(i).toFixed(1)},${y(v).toFixed(1)}`
      pen = true
    }
  })
  let last = points.length - 1
  while (last > 0 && points[last].value === null) last--
  return (
    <div>
      <div className="flex items-baseline gap-1.5">
        <span className="font-mono text-lg text-fg">{num(points[last].value as number, lang)}</span>
        <span className="text-xs text-fg-muted">{points[last].label}</span>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} className="mt-1 h-14 w-full" preserveAspectRatio="none" role="img" aria-label={`${points[0].label} – ${points[points.length - 1].label}`}>
        {min < 0 && <line x1="0" x2={W} y1={y(0)} y2={y(0)} stroke="#8b95a5" strokeWidth="0.5" />}
        <path d={d} fill="none" stroke="#ff6b1a" strokeWidth="1.2" vectorEffect="non-scaling-stroke" />
      </svg>
      <div className="flex justify-between font-mono text-[10px] text-fg-muted">
        <span>{points[0].label}</span>
        <span>
          {num(min, lang)} – {num(max, lang)}
        </span>
        <span>{points[points.length - 1].label}</span>
      </div>
    </div>
  )
}

type Shape = 'number' | 'month' | 'year' | 'date' | 'series12' | 'band12' | 'breakdown' | 'interval' | 'perMonth' | 'perDay' | 'perYear' | 'other'

/** Recognise how to draw a value from its own shape. */
function shapeOf(v: unknown): Shape {
  if (typeof v === 'number') return 'number'
  if (Array.isArray(v)) {
    const f = v.find((x) => x !== null)
    if (v.length === 12 && v.every((x) => x === null || typeof x === 'number')) return 'series12'
    if (isObj(f)) {
      if ('low' in f && 'high' in f) return 'band12'
      if ('key' in f) return 'breakdown'
      if ('date' in f && 'value' in f) return 'perDay'
      if ('year' in f && 'month' in f && 'value' in f) return 'perMonth'
      if ('year' in f && 'value' in f) return 'perYear'
    }
    return 'other'
  }
  if (isObj(v)) {
    if ('low' in v && 'high' in v) return 'interval'
    if ('year' in v && 'month' in v) return 'month'
    if ('date' in v) return 'date'
    if ('year' in v) return 'year'
  }
  return 'other'
}

function Value({ m, r, lang }: { m: MetricDef; r: Extract<MetricResult, { status: 'ok' }>; lang: Lang }) {
  const t = useT()
  const { value, unit } = r.data
  const note = r.data.note ? metricNote(r.data.note, lang) : undefined
  const unitLabel = unit ?? metricUnit(m, lang)
  const big = 'font-mono text-lg text-fg'
  const small = 'text-xs text-fg-muted'

  if (value === null || value === undefined)
    return (
      <div className={small}>
        {t('metrics.noValue')}
        {note && ` · ${note}`}
      </div>
    )

  let body: ReactNode
  const kind = shapeOf(value)
  try {
    if (kind === 'month' && isObj(value)) {
      body = (
        <>
          <span className={big}>
            {monthName(Number(value.month), lang)} {String(value.year)}
          </span>{' '}
          <span className={small}>{num(Number(value.count ?? 0), lang)}</span>
        </>
      )
    } else if (kind === 'year' && isObj(value)) {
      body = (
        <>
          <span className={big}>{String(value.year)}</span> <span className={small}>{num(Number(value.count ?? 0), lang)}</span>
        </>
      )
    } else if (kind === 'date' && isObj(value)) {
      body = (
        <>
          <span className={big}>{new Date(String(value.date)).toLocaleDateString(locale(lang), { timeZone: 'UTC' })}</span>{' '}
          <span className={small}>{num(Number(value.count ?? 0), lang)}</span>
        </>
      )
    } else if ((kind === 'perMonth' || kind === 'perDay' || kind === 'perYear') && Array.isArray(value)) {
      const points: Point[] = (value as Obj[]).map((it) => ({
        label:
          kind === 'perDay' ? String(it.date) : kind === 'perYear' ? String(it.year) : `${monthName(Number(it.month), lang)} ${String(it.year)}`,
        value: typeof it.value === 'number' ? it.value : null,
      }))
      body = <Series points={points} lang={lang} />
    } else if ((kind === 'series12' || kind === 'band12') && Array.isArray(value)) {
      body = <Bars values={(value as (number | null | { low: number; high: number })[]).map((v) => v ?? 0)} lang={lang} band={kind === 'band12'} />
    } else if (kind === 'breakdown' && Array.isArray(value)) {
      const items = value as { key: string; value: number }[]
      const total = items.reduce((a, b) => a + Number(b.value), 0) || 1
      body = (
        <div className="mt-1 space-y-1">
          {items.map((it) => (
            <div key={it.key} className="grid grid-cols-[minmax(0,1fr)_90px_52px] items-center gap-2 text-xs">
              <span className="truncate text-fg-muted">{it.key}</span>
              <span className="h-1.5 rounded-full bg-ink-800">
                <span className="block h-full rounded-full bg-ember-500" style={{ width: `${(Number(it.value) / total) * 100}%` }} />
              </span>
              <span className="text-right font-mono text-fg">{num(Number(it.value), lang)}</span>
            </div>
          ))}
        </div>
      )
    } else if (kind === 'interval' && isObj(value)) {
      body = (
        <>
          <span className={big}>{num(Number(value.value), lang)}</span>{' '}
          <span className={small}>
            [{num(Number(value.low), lang)} – {num(Number(value.high), lang)}]
          </span>
        </>
      )
    } else if (typeof value === 'number') {
      body = <span className={big}>{num(value, lang)}</span>
    } else {
      body = <span className="font-mono text-xs text-fg">{JSON.stringify(value)}</span>
    }
  } catch {
    body = <span className="font-mono text-xs text-fg">{JSON.stringify(value)}</span>
  }

  const block = ['breakdown', 'series12', 'band12', 'perMonth', 'perDay', 'perYear'].includes(kind)
  return (
    <div>
      {block ? (
        <>
          <div className="w-full max-w-[420px]">{body}</div>
          <div className={clsx(small, 'mt-1')}>{unitLabel}</div>
        </>
      ) : (
        <div className="flex flex-wrap items-baseline gap-x-1.5">
          {body}
          <span className={small}>{unitLabel}</span>
        </div>
      )}
      {note && <div className={clsx(small, 'mt-0.5')}>{note}</div>}
    </div>
  )
}

function MetricRow({ m }: { m: MetricDef }) {
  const t = useT()
  const lang = useApp((s) => s.lang)
  const r = useApp((s) => s.metricResults[m.code])
  const [open, setOpen] = useState(false)

  return (
    <div className="rounded-[10px] bg-ink-800/60 px-3.5 py-3 ring-1 ring-line">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-1.5">
            <span className="text-[13px] text-fg">{metricName(m, lang)}</span>
            <button
              onClick={() => setOpen((o) => !o)}
              aria-expanded={open}
              aria-label={metricDescription(m, lang)}
              className="text-fg-muted hover:text-fg"
            >
              <Info size={13} />
            </button>
          </div>
          <span className="font-mono text-[10px] text-fg-muted">{m.id}</span>
        </div>
        <span className="shrink-0 rounded-[5px] px-1.5 py-0.5 text-[10px] text-fg-muted ring-1 ring-line">{priorityLabel(m.priority, lang)}</span>
      </div>

      {open && (
        <div className="mt-2 space-y-1 rounded-[8px] bg-ink-900 p-2.5 text-xs leading-relaxed text-fg-muted">
          <p>{metricDescription(m, lang)}</p>
          {metricCalculation(m, lang) && (
            <p>
              <span className="text-fg">{t('metrics.how')}:</span> {metricCalculation(m, lang)}
            </p>
          )}
        </div>
      )}

      <div className="mt-2">
        {!r || r.status === 'loading' ? (
          <span className="flex items-center gap-1.5 text-xs text-fg-muted">
            <CircleNotch size={13} className="animate-spin" />
          </span>
        ) : r.status === 'missing' ? (
          <span className="text-xs text-fg-muted/70 italic">{t('metrics.missing')}</span>
        ) : r.status === 'error' ? (
          <span className="text-xs text-ember-300">
            {t('metrics.error')}: {r.message}
          </span>
        ) : (
          <Value m={m} r={r} lang={lang} />
        )}
      </div>
    </div>
  )
}

function Picker() {
  const t = useT()
  const lang = useApp((s) => s.lang)
  const selection = useApp((s) => s.metricSelection)
  const setSelection = useApp((s) => s.setMetricSelection)
  const toggle = (code: string) =>
    setSelection(selection.includes(code) ? selection.filter((c) => c !== code) : [...selection, code])

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-1.5">
        {(
          [
            ['metrics.selectMvp', DEFAULT_SELECTION],
            ['metrics.selectAll', METRICS.map((m) => m.code)],
            ['metrics.clear', []],
          ] as const
        ).map(([label, codes]) => (
          <button
            key={label}
            onClick={() => setSelection([...codes])}
            className="h-7 rounded-[6px] px-2.5 text-xs text-fg-muted ring-1 ring-line hover:bg-ink-700 hover:text-fg"
          >
            {t(label)}
          </button>
        ))}
        <span className="ml-auto self-center text-xs text-fg-muted">{t('metrics.selected', { n: selection.length })}</span>
      </div>
      {CATEGORIES.map((c) => (
        <div key={c}>
          <h3 className="mb-1.5 text-[11px] uppercase tracking-[0.08em] text-fg-muted">{categoryLabel(c, lang)}</h3>
          <div className="space-y-0.5">
            {METRICS.filter((m) => m.category === c).map((m) => (
              <label key={m.code} className="flex cursor-pointer items-center gap-2.5 rounded-[6px] px-2 py-1.5 hover:bg-ink-800">
                <input
                  type="checkbox"
                  checked={selection.includes(m.code)}
                  onChange={() => toggle(m.code)}
                  className="size-3.5 accent-[#ff6b1a]"
                />
                <span className="flex-1 text-[13px] text-fg">{metricName(m, lang)}</span>
                <span className="font-mono text-[10px] text-fg-muted">{m.id}</span>
              </label>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}

export default function MetricsView() {
  const t = useT()
  const lang = useApp((s) => s.lang)
  const place = useApp((s) => s.place)
  const selection = useApp((s) => s.metricSelection)
  const key = useApp((s) => (s.place ? `${s.place.lat},${s.place.lon},${s.radiusKm},${s.dateFrom},${s.dateTo}` : ''))
  const [picking, setPicking] = useState(false)

  // (re)load whenever the area, the period or the selection changes
  useEffect(() => {
    useApp.getState().loadMetrics()
  }, [key, selection])

  if (!place) return <p className="text-sm text-fg-muted">{t('metrics.needAnalysis')}</p>

  const shown = METRICS.filter((m) => selection.includes(m.code))

  return (
    <div>
      <div className="mb-4 flex items-start justify-between gap-3">
        <p className="text-[13px] leading-relaxed text-fg-muted">{t('metrics.intro')}</p>
        <button
          onClick={() => setPicking((p) => !p)}
          className={clsx(
            'flex h-8 shrink-0 items-center gap-1.5 rounded-[8px] px-3 text-xs ring-1 transition-colors duration-150',
            picking ? 'bg-ember-500 text-ink-950 ring-ember-500' : 'text-fg ring-line hover:bg-ink-700',
          )}
        >
          <SlidersHorizontal size={14} />
          {picking ? t('metrics.done') : t('metrics.customize')}
        </button>
      </div>

      {picking ? (
        <Picker />
      ) : shown.length === 0 ? (
        <p className="text-sm text-fg-muted">{t('metrics.none')}</p>
      ) : (
        <div className="space-y-5">
          {CATEGORIES.filter((c) => shown.some((m) => m.category === c)).map((c) => (
            <section key={c}>
              <h3 className="mb-2 text-[11px] uppercase tracking-[0.08em] text-fg-muted">{categoryLabel(c, lang)}</h3>
              <div className="grid gap-2">
                {shown
                  .filter((m) => m.category === c)
                  .map((m) => (
                    <MetricRow key={m.code} m={m} />
                  ))}
              </div>
            </section>
          ))}
        </div>
      )}
    </div>
  )
}

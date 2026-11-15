import { Fragment, useMemo, useState } from 'react'
import clsx from 'clsx'
import { calendarScale, fmt, monthFraction, referenceMeans, summary, yearTotals } from '../../lib/stats'
import { DATA_START, useApp, type CalendarScale } from '../../store'
import { monthName, useT } from '../../i18n'
import type { CalendarEntry } from '../../types'

const HATCH = 'repeating-linear-gradient(45deg, #161b23 0 3px, #2c333f 3px 5px)'

// Year × month grid (section 6 of the requirements).
// - colour: count (log classes), relative to the area's peak, or anomaly vs the month mean
// - totals per year on the right, mean per month at the bottom
// - peak month outlined in white, current month in ember, no-data cells hatched
// - click a month to show its hotspots on the map
export default function CalendarHeatmap({ calendar }: { calendar: CalendarEntry[] }) {
  const t = useT()
  const lang = useApp((s) => s.lang)
  const kind = useApp((s) => s.calendarScale)
  const setKind = useApp((s) => s.setCalendarScale)
  const dateTo = useApp((s) => s.dateTo)
  const filtered = useApp((s) => s.hotspotWindow)
  const anomalies = useApp((s) => s.anomalies)
  const [hover, setHover] = useState<CalendarEntry | null>(null)

  const { years, byKey, totals, means, scale, peak, last, peakYear } = useMemo(() => {
    const byKey = new Map(calendar.map((c) => [`${c.year}-${c.month}`, c]))
    const years = [...new Set(calendar.map((c) => c.year))].sort((a, b) => b - a) // newest on top
    const totals = new Map(yearTotals(calendar).map((y) => [y.year, y.count]))
    const sum = summary(calendar)
    const { means } = referenceMeans(anomalies, calendar)
    return {
      years,
      byKey,
      totals,
      means,
      scale: calendarScale(calendar, kind, means),
      peak: sum.peakMonth,
      peakYear: sum.peakYear?.year,
      last: calendar[calendar.length - 1],
    }
  }, [calendar, kind, anomalies])

  const startY = Number(DATA_START.slice(0, 4))
  const startM = Number(DATA_START.slice(5, 7))

  // Readout (C3): count and difference from the mean of the same month
  const info = hover ?? last
  const frac = info ? monthFraction(info, dateTo) : 1
  const mean = info ? means[info.month - 1] * frac : 0
  const diff = info ? info.count - mean : 0
  const pct = mean > 0 ? (diff / mean) * 100 : null

  function showOnMap(c: CalendarEntry) {
    const from = `${c.year}-${String(c.month).padStart(2, '0')}-01`
    const lastDay = new Date(c.year, c.month, 0).getDate()
    const to = `${c.year}-${String(c.month).padStart(2, '0')}-${lastDay}`
    useApp.getState().loadHotspots({ from, to: to > dateTo ? dateTo : to, year: c.year, month: c.month })
  }

  const legend = [...(scale.zero ? [scale.zero] : []), ...scale.classes]

  return (
    <div>
      {/* Scale switch (C6) */}
      <div className="mb-3 flex items-center gap-2">
        <span className="text-[11px] uppercase tracking-[0.08em] text-fg-muted">{t('cal.scale')}</span>
        <div className="flex rounded-[8px] bg-ink-800 p-0.5 ring-1 ring-line" role="radiogroup" aria-label={t('cal.scale')}>
          {(['absolute', 'relative', 'anomaly'] as CalendarScale[]).map((k) => (
            <button
              key={k}
              role="radio"
              aria-checked={kind === k}
              onClick={() => setKind(k)}
              className={clsx(
                'h-7 rounded-[6px] px-2.5 text-xs transition-colors duration-150',
                kind === k ? 'bg-ember-500/15 text-ember-300' : 'text-fg-muted hover:text-fg',
              )}
            >
              {t(`cal.scale.${k}`)}
            </button>
          ))}
        </div>
      </div>

      {/* Readout */}
      <div className="mb-3 flex min-h-[52px] items-end justify-between gap-4 rounded-[10px] bg-ink-800 px-4 py-3 ring-1 ring-line">
        {info && (
          <>
            <div>
              <div className="text-[11px] uppercase tracking-[0.08em] text-fg-muted">
                {monthName(info.month, lang, 'long')} {info.year}
                {info === last && !hover && ` · ${t('cal.latest')}`}
              </div>
              <div className="font-mono text-xl">
                {fmt(info.count)} <span className="text-sm text-fg-muted">{t('hotspots')}</span>
              </div>
            </div>
            <div className="text-right">
              <div className={clsx('font-mono text-lg', diff > 0.5 ? 'text-ember-300' : diff < -0.5 ? 'text-cool-400' : 'text-fg')}>
                {diff > 0 ? '+' : ''}
                {fmt(diff)}
                {pct !== null && Math.abs(pct) < 1000 && <span className="ml-1.5 text-sm">({pct > 0 ? '+' : ''}{Math.round(pct)}%)</span>}
              </div>
              <div className="text-[11px] text-fg-muted">
                {t('cal.vsMean', { month: monthName(info.month, lang) })}
                {frac < 1 && ` ${t('cal.toDate')}`} (<span className="font-mono">{fmt(mean)}</span>)
              </div>
            </div>
          </>
        )}
      </div>

      {/* Grid */}
      <div className="grid grid-cols-[40px_repeat(12,minmax(0,1fr))_56px] gap-[3px]" onMouseLeave={() => setHover(null)}>
        <div />
        {Array.from({ length: 12 }, (_, i) => (
          <div key={i} className="pb-1 text-center text-[10.5px] text-fg-muted">
            {monthName(i + 1, lang)}
          </div>
        ))}
        <div className="pb-1 text-right text-[10.5px] text-fg-muted">{t('cal.total')}</div>

        {years.map((y) => (
          <Fragment key={y}>
            <div className={clsx('flex items-center font-mono text-[11px]', y === peakYear ? 'font-medium text-ember-300' : 'text-fg-muted')}>
              {y}
            </div>
            {Array.from({ length: 12 }, (_, i) => {
              const m = i + 1
              const c = byKey.get(`${y}-${m}`)
              if (!c) {
                const beforeRecord = y < startY || (y === startY && m < startM)
                return (
                  <div
                    key={i}
                    className="h-[15px] rounded-[3px]"
                    style={beforeRecord ? { background: HATCH } : undefined}
                    title={beforeRecord ? t('cal.noData') : undefined}
                  />
                )
              }
              const k = scale.classify(c)
              const color = k < 0 ? scale.zero!.color : scale.classes[k].color
              const isPeak = c === peak && c.count > 0
              const isLast = c === last
              const isFiltered = filtered?.year === c.year && filtered?.month === c.month
              return (
                <button
                  key={i}
                  onMouseEnter={() => setHover(c)}
                  onFocus={() => setHover(c)}
                  onClick={() => showOnMap(c)}
                  aria-label={`${monthName(m, lang, 'long')} ${y}: ${c.count} ${t('hotspots')}`}
                  className={clsx(
                    'relative h-[15px] rounded-[3px] outline-none transition-[box-shadow] duration-100',
                    (hover === c || isFiltered) && 'ring-2 ring-fg',
                    isPeak && hover !== c && !isFiltered && 'ring-2 ring-fg/90 ring-offset-1 ring-offset-ink-900',
                    isLast && hover !== c && !isPeak && 'ring-2 ring-ember-500',
                  )}
                  style={{ background: color }}
                >
                  {isPeak && <span className="absolute -top-1 -right-1 size-1.5 rounded-full bg-fg" />}
                </button>
              )
            })}
            <div className={clsx('flex items-center justify-end font-mono text-[11px]', y === peakYear ? 'text-ember-300' : 'text-fg')}>
              {fmt(totals.get(y) ?? 0)}
            </div>
          </Fragment>
        ))}

        {/* Monthly means (C4) */}
        <div className="pt-1.5 text-[10.5px] text-fg-muted">{t('cal.mean')}</div>
        {means.map((v, i) => (
          <div key={i} className="pt-1.5 text-center font-mono text-[10.5px] text-fg">
            {fmt(v)}
          </div>
        ))}
        <div />
      </div>

      {/* Legend (C2, C5, C7) */}
      <div className="mt-4 space-y-2">
        <div className="flex flex-wrap gap-x-3 gap-y-1.5">
          {legend.map((l) => (
            <span key={l.label} className="flex items-center gap-1.5 font-mono text-[10.5px] text-fg-muted">
              <i className="h-2.5 w-3.5 rounded-[2px] ring-1 ring-line" style={{ background: l.color }} />
              {l.label}
            </span>
          ))}
        </div>
        <div className="flex flex-wrap gap-x-4 gap-y-1.5 text-[11px] text-fg-muted">
          <span className="flex items-center gap-1.5">
            <i className="h-2.5 w-3.5 rounded-[2px]" style={{ background: HATCH }} /> {t('cal.noData')}
          </span>
          <span className="flex items-center gap-1.5">
            <i className="h-2.5 w-3.5 rounded-[2px] ring-2 ring-fg" /> {t('cal.peak')}
          </span>
          <span className="flex items-center gap-1.5">
            <i className="h-2.5 w-3.5 rounded-[2px] ring-2 ring-ember-500" /> {t('cal.current')}
          </span>
        </div>
        <p className="text-[11px] text-fg-muted">
          <span className="text-fg">
            {t('cal.scale')}: {t(`cal.scale.${kind}`)}.
          </span>{' '}
          {t(`cal.scaleNote.${kind}`)} {t('cal.clickHint')}
        </p>
        <p className="text-[11px] text-fg-muted">{t('cal.footnote')}</p>
      </div>
    </div>
  )
}

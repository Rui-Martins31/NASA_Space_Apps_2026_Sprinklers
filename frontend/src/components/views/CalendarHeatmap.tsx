import { useMemo, useState } from 'react'
import clsx from 'clsx'
import { cividis, CIVIDIS_STOPS, fmt, monthFraction, monthStats, MONTHS } from '../../lib/stats'
import { useApp } from '../../store'
import type { CalendarEntry } from '../../types'

// Year × month grid. Colour = hotspots (cividis, square-root scale so quiet
// months are still distinguishable). Hover or focus a cell for exact values.
export default function CalendarHeatmap({ calendar }: { calendar: CalendarEntry[] }) {
  const [hover, setHover] = useState<CalendarEntry | null>(null)
  const dateTo = useApp((s) => s.dateTo)

  const { years, byKey, max, last } = useMemo(() => {
    const byKey = new Map(calendar.map((c) => [`${c.year}-${c.month}`, c]))
    const years = [...new Set(calendar.map((c) => c.year))].sort((a, b) => b - a) // newest on top
    const max = Math.max(1, ...calendar.map((c) => c.count))
    return { years, byKey, max, last: calendar[calendar.length - 1] }
  }, [calendar])

  const info = hover ?? last
  const frac = info ? monthFraction(info, dateTo) : 1
  const full = info ? monthStats(calendar, info.month, info.year) : null
  const stats = full ? { ...full, median: full.median * frac } : null
  const pct = info && stats && stats.median > 0 ? ((info.count - stats.median) / stats.median) * 100 : null

  return (
    <div>
      {/* Readout: replaces a floating tooltip, always visible and readable */}
      <div className="mb-4 flex min-h-[52px] items-end justify-between gap-4 rounded-[10px] bg-ink-800 px-4 py-3 ring-1 ring-line">
        {info && (
          <>
            <div>
              <div className="text-[11px] uppercase tracking-[0.08em] text-fg-muted">
                {MONTHS[info.month - 1]} {info.year}
                {info === last && !hover && ' · latest'}
              </div>
              <div className="font-mono text-xl">
                {fmt(info.count)} <span className="text-sm text-fg-muted">hotspots</span>
              </div>
            </div>
            {pct !== null && (
              <div className="text-right">
                <div className={clsx('font-mono text-lg', pct > 15 ? 'text-ember-300' : pct < -15 ? 'text-cool-400' : 'text-fg')}>
                  {pct > 0 ? '+' : ''}
                  {Math.round(pct)}%
                </div>
                <div className="text-[11px] text-fg-muted">
                  vs median {MONTHS[info.month - 1]}{frac < 1 && ' to date'} (<span className="font-mono">{fmt(stats!.median)}</span>)
                </div>
              </div>
            )}
          </>
        )}
      </div>

      <div className="grid grid-cols-[44px_repeat(12,minmax(0,1fr))] gap-[3px]" onMouseLeave={() => setHover(null)}>
        <div />
        {MONTHS.map((m) => (
          <div key={m} className="pb-1 text-center text-[10.5px] text-fg-muted">
            {m}
          </div>
        ))}
        {years.map((y) => (
          <Row key={y} year={y} byKey={byKey} max={max} hover={hover} setHover={setHover} last={last} />
        ))}
      </div>

      <div className="mt-4 flex items-center gap-3 text-[11px] text-fg-muted">
        <span>Fewer</span>
        <div className="h-2 w-40 rounded-full" style={{ background: `linear-gradient(90deg, ${CIVIDIS_STOPS.join(',')})` }} />
        <span>More</span>
        <span className="ml-auto font-mono">max {fmt(max)}/month</span>
      </div>
      <p className="mt-2 text-[11px] text-fg-muted">
        Years before 2012 come from MODIS only, converted to VIIRS-equivalent counts. A ring marks the current, incomplete month.
      </p>
    </div>
  )
}

function Row({
  year,
  byKey,
  max,
  hover,
  setHover,
  last,
}: {
  year: number
  byKey: Map<string, CalendarEntry>
  max: number
  hover: CalendarEntry | null
  setHover: (c: CalendarEntry | null) => void
  last?: CalendarEntry
}) {
  return (
    <>
      <div className={clsx('flex items-center font-mono text-[11px]', year < 2012 ? 'text-fg-muted/70' : 'text-fg-muted')}>{year}</div>
      {MONTHS.map((_, i) => {
        const c = byKey.get(`${year}-${i + 1}`)
        if (!c) return <div key={i} className="h-[18px] rounded-[3px] bg-ink-800/60" />
        const isLast = c === last
        return (
          <button
            key={i}
            onMouseEnter={() => setHover(c)}
            onFocus={() => setHover(c)}
            aria-label={`${MONTHS[i]} ${year}: ${c.count} hotspots`}
            className={clsx(
              'h-[18px] rounded-[3px] outline-none transition-[box-shadow] duration-100',
              hover === c && 'ring-2 ring-fg',
              isLast && hover !== c && 'ring-2 ring-ember-500',
            )}
            style={{ background: cividis(Math.sqrt(c.count / max)) }}
          />
        )
      })}
    </>
  )
}

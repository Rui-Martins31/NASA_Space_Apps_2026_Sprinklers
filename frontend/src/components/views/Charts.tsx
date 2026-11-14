import { Bar, BarChart, Cell, ComposedChart, Area, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis, CartesianGrid } from 'recharts'
import { fmt, seasonalProfile, topMonths, yearlyAnomalies, yearTotals, MONTHS } from '../../lib/stats'
import type { AnomalyEntry, CalendarEntry } from '../../types'

const AXIS = { stroke: '#8b95a5', fontSize: 11, fontFamily: 'IBM Plex Mono', tickLine: false, axisLine: false } as const
const GRID = <CartesianGrid stroke="rgb(255 255 255 / 0.06)" vertical={false} />
const tooltipStyle = {
  contentStyle: {
    background: '#0d1117',
    border: '1px solid rgb(255 255 255 / 0.1)',
    borderRadius: 10,
    fontFamily: 'IBM Plex Mono',
    fontSize: 12,
  },
  labelStyle: { color: '#8b95a5' },
  itemStyle: { color: '#e8ecf2' },
  cursor: { fill: 'rgb(255 255 255 / 0.04)' },
}

export function AnomaliesChart({ anomalies }: { anomalies: AnomalyEntry[] }) {
  const data = yearlyAnomalies(anomalies)
  // A year with fewer than 12 months of data (usually the current one) is drawn faded.
  const monthsPerYear = new Map<number, number>()
  for (const a of anomalies) monthsPerYear.set(a.year, (monthsPerYear.get(a.year) ?? 0) + 1)
  const partial = (y: number) => (monthsPerYear.get(y) ?? 0) < 12
  return (
    <div>
      <p className="mb-4 text-[13px] leading-relaxed text-fg-muted">
        Each bar is the year&apos;s total minus the multi-year average. <span className="text-ember-300">Above</span> means more burning than usual,{' '}
        <span className="text-cool-400">below</span> means less.
      </p>
      <div className="h-[300px]">
        <ResponsiveContainer>
          <BarChart data={data} margin={{ top: 8, right: 4, left: 0, bottom: 0 }}>
            {GRID}
            <XAxis dataKey="year" {...AXIS} interval={2} />
            <YAxis {...AXIS} width={52} tickFormatter={(v: number) => fmt(v)} />
            <ReferenceLine y={0} stroke="#8b95a5" />
            <Tooltip {...tooltipStyle} formatter={(v) => [`${Number(v) > 0 ? '+' : ''}${fmt(Number(v))} hotspots`, 'vs average']} />
            <Bar dataKey="anomaly" radius={[3, 3, 3, 3]}>
              {data.map((d) => (
                <Cell key={d.year} fill={d.anomaly >= 0 ? '#ff6b1a' : '#5ba4ff'} fillOpacity={partial(d.year) ? 0.35 : 1} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      {data.some((d) => partial(d.year)) && (
        <p className="mt-3 text-[11px] text-fg-muted">Faded bars are incomplete years, so their totals are still growing.</p>
      )}
    </div>
  )
}

export function SeasonalChart({ calendar }: { calendar: CalendarEntry[] }) {
  const data = seasonalProfile(calendar)
  const curYear = calendar[calendar.length - 1]?.year
  return (
    <div>
      <p className="mb-4 text-[13px] leading-relaxed text-fg-muted">
        Typical fire season for this area. The band covers 80% of past years (P10 to P90), the line is the median, and the ember line is{' '}
        <span className="font-mono text-fg">{curYear}</span>.
      </p>
      <div className="h-[300px]">
        <ResponsiveContainer>
          <ComposedChart data={data} margin={{ top: 8, right: 4, left: 0, bottom: 0 }}>
            {GRID}
            <XAxis dataKey="name" {...AXIS} />
            <YAxis {...AXIS} width={52} tickFormatter={(v: number) => fmt(v)} />
            <Tooltip {...tooltipStyle} />
            <Area dataKey="band" name="P10–P90" fill="#5ba4ff" fillOpacity={0.15} stroke="none" isAnimationActive={false} />
            <Line dataKey="median" name="Median" stroke="#8b95a5" strokeWidth={2} dot={false} />
            <Line dataKey="current" name={String(curYear)} stroke="#ff6b1a" strokeWidth={2.5} dot={{ r: 3, fill: '#ff6b1a' }} connectNulls={false} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <div className="mt-3 flex gap-5 text-[11px] text-fg-muted">
        <span className="flex items-center gap-1.5"><i className="h-2 w-4 rounded-sm bg-cool-400/30" /> P10–P90</span>
        <span className="flex items-center gap-1.5"><i className="h-0.5 w-4 bg-fg-muted" /> Median</span>
        <span className="flex items-center gap-1.5"><i className="h-0.5 w-4 bg-ember-500" /> {curYear}</span>
      </div>
    </div>
  )
}

export function RankingView({ calendar }: { calendar: CalendarEntry[] }) {
  const years = yearTotals(calendar).sort((a, b) => b.count - a.count).slice(0, 8)
  const months = topMonths(calendar, 5)
  const max = years[0]?.count ?? 1
  return (
    <div className="space-y-6">
      <div>
        <h3 className="mb-3 text-[11px] uppercase tracking-[0.08em] text-fg-muted">Most active years</h3>
        <ol className="space-y-2">
          {years.map((y, i) => (
            <li key={y.year} className="grid grid-cols-[20px_48px_1fr_64px] items-center gap-3 text-sm">
              <span className="font-mono text-fg-muted">{i + 1}</span>
              <span className="font-mono">{y.year}</span>
              <span className="h-2 rounded-full bg-ink-800">
                <span className="block h-full rounded-full bg-ember-500" style={{ width: `${(y.count / max) * 100}%`, opacity: 1 - i * 0.08 }} />
              </span>
              <span className="text-right font-mono text-fg-muted">{fmt(y.count)}</span>
            </li>
          ))}
        </ol>
      </div>
      <div>
        <h3 className="mb-3 text-[11px] uppercase tracking-[0.08em] text-fg-muted">Worst single months</h3>
        <div className="grid grid-cols-5 gap-2">
          {months.map((m) => (
            <div key={`${m.year}-${m.month}`} className="rounded-[10px] bg-ink-800 px-3 py-2.5 ring-1 ring-line">
              <div className="text-xs text-fg-muted">
                {MONTHS[m.month - 1]} <span className="font-mono">{m.year}</span>
              </div>
              <div className="font-mono text-base">{fmt(m.count)}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

export function AboutView() {
  return (
    <div className="space-y-4 text-[13.5px] leading-relaxed text-fg-muted">
      <p>
        <span className="text-fg">Why harmonize?</span> MODIS (Terra and Aqua, since 2000) sees the ground in 1 km pixels. VIIRS (since 2012) uses
        375 m pixels and detects much smaller fires. Counting their hotspots side by side would make recent years look worse just because the
        sensor is better.
      </p>
      <p>
        <span className="text-fg">What we do.</span> Both records are put on the same grid, and the overlap period (2012 to today, when both
        sensors fly) is used to learn how MODIS counts relate to VIIRS counts, by region and season. The MODIS-only years are then converted into
        VIIRS-equivalent counts, so the whole series reads as one sensor.
      </p>
      <p>
        <span className="text-fg">Limits.</span> Hotspots are thermal anomalies, not fires: one fire can produce many hotspots and clouds can
        hide others. Terra and Aqua orbits have drifted in recent years, which changes their overpass time.
      </p>
      <p>
        Data: NASA FIRMS (MODIS C6.1, VIIRS S-NPP / NOAA-20 / NOAA-21). Built for the NASA Space Apps Challenge 2026.
      </p>
    </div>
  )
}

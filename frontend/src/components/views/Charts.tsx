import { useMemo, useState } from 'react'
import clsx from 'clsx'
import {
  Area,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  Label,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { fmt, monthlyMeans, seasonalProfile, summary, topMonths, yearlyAnomalies, yearTotals } from '../../lib/stats'
import { monthName, useT } from '../../i18n'
import { useApp } from '../../store'
import type { CalendarEntry } from '../../types'

const MUTED = '#8b95a5'
const AXIS = { stroke: MUTED, fontSize: 11, fontFamily: 'IBM Plex Mono', tickLine: false, axisLine: false } as const
const GRID = <CartesianGrid stroke="rgb(255 255 255 / 0.06)" vertical={false} />
const tooltipStyle = {
  contentStyle: {
    background: '#0d1117',
    border: '1px solid rgb(255 255 255 / 0.1)',
    borderRadius: 10,
    fontFamily: 'IBM Plex Mono',
    fontSize: 12,
  },
  labelStyle: { color: MUTED },
  itemStyle: { color: '#e8ecf2' },
  cursor: { fill: 'rgb(255 255 255 / 0.04)' },
}
const yLabel = (text: string) => (
  <Label value={text} angle={-90} position="insideLeft" offset={6} style={{ fill: MUTED, fontSize: 11, fontFamily: 'IBM Plex Sans', textAnchor: 'middle' }} />
)

function Segmented<T extends string>({ value, options, onChange }: { value: T; options: [T, string][]; onChange: (v: T) => void }) {
  return (
    <div className="flex rounded-[8px] bg-ink-800 p-0.5 ring-1 ring-line">
      {options.map(([v, label]) => (
        <button
          key={v}
          onClick={() => onChange(v)}
          aria-pressed={value === v}
          className={clsx('h-7 rounded-[6px] px-2.5 text-xs transition-colors duration-150', value === v ? 'bg-ember-500/15 text-ember-300' : 'text-fg-muted hover:text-fg')}
        >
          {label}
        </button>
      ))}
    </div>
  )
}

// W6: time series with the historical mean, plus the yearly anomaly
export function TrendView({ calendar }: { calendar: CalendarEntry[] }) {
  const t = useT()
  const lang = useApp((s) => s.lang)
  const [mode, setMode] = useState<'annual' | 'monthly'>('annual')
  const { annualAvg } = summary(calendar)
  const years = yearTotals(calendar)
  const means = monthlyMeans(calendar)
  const monthly = useMemo(
    () => calendar.map((c) => ({ label: `${monthName(c.month, lang)} ${c.year}`, count: c.count, mean: Math.round(means[c.month - 1] * 10) / 10 })),
    [calendar, lang], // eslint-disable-line react-hooks/exhaustive-deps
  )
  const anoms = yearlyAnomalies(calendar)

  return (
    <div className="space-y-6">
      <div>
        <div className="mb-3 flex items-center justify-between gap-3">
          <p className="text-[13px] leading-relaxed text-fg-muted">{t('trend.intro')}</p>
          <Segmented
            value={mode}
            onChange={setMode}
            options={[
              ['annual', t('trend.annual')],
              ['monthly', t('trend.monthly')],
            ]}
          />
        </div>
        <div className="h-[260px]" data-export-main>
          <ResponsiveContainer>
            {mode === 'annual' ? (
              <BarChart data={years} margin={{ top: 16, right: 8, left: 8, bottom: 0 }}>
                {GRID}
                <XAxis dataKey="year" {...AXIS} interval="preserveStartEnd" />
                <YAxis {...AXIS} width={56} tickFormatter={(v: number) => fmt(v)}>
                  {yLabel(t('trend.yAnnual'))}
                </YAxis>
                <Tooltip {...tooltipStyle} formatter={(v) => [fmt(Number(v)), t('hotspots')]} />
                <Bar dataKey="count" radius={[3, 3, 0, 0]} isAnimationActive={false}>
                  {years.map((y) => (
                    <Cell key={y.year} fill="#ff6b1a" fillOpacity={y.complete ? 1 : 0.35} />
                  ))}
                </Bar>
                <ReferenceLine y={annualAvg} stroke="#e8ecf2" strokeDasharray="5 4">
                  <Label value={`${t('trend.mean')}: ${fmt(annualAvg)}`} position="insideTopLeft" style={{ fill: "#e8ecf2", fontSize: 11, fontFamily: 'IBM Plex Sans' }} />
                </ReferenceLine>
              </BarChart>
            ) : (
              <ComposedChart data={monthly} margin={{ top: 16, right: 8, left: 8, bottom: 0 }}>
                {GRID}
                <XAxis dataKey="label" {...AXIS} interval={Math.max(0, Math.floor(monthly.length / 6) - 1)} />
                <YAxis {...AXIS} width={56} tickFormatter={(v: number) => fmt(v)}>
                  {yLabel(t('trend.yMonthly'))}
                </YAxis>
                <Tooltip {...tooltipStyle} formatter={(v, name) => [fmt(Number(v)), name === 'mean' ? t('trend.mean') : t('hotspots')]} />
                <Line dataKey="count" stroke="#ff6b1a" strokeWidth={1.5} dot={false} isAnimationActive={false} />
                <Line dataKey="mean" stroke="#e8ecf2" strokeWidth={1.2} strokeDasharray="5 4" dot={false} isAnimationActive={false} />
              </ComposedChart>
            )}
          </ResponsiveContainer>
        </div>
        <div className="mt-2 flex gap-5 text-[11px] text-fg-muted">
          <span className="flex items-center gap-1.5">
            <i className="h-2 w-4 rounded-sm bg-ember-500" /> {t('hotspots')}
          </span>
          <span className="flex items-center gap-1.5">
            <i className="w-4 border-t border-dashed border-fg" /> {t('trend.mean')}
            {mode === 'monthly' && ` (${t('cal.mean').toLowerCase()} / ${t('date.month').toLowerCase()})`}
          </span>
        </div>
      </div>

      <div>
        <h3 className="mb-1 text-[11px] uppercase tracking-[0.08em] text-fg-muted">{t('trend.anomTitle')}</h3>
        <p className="mb-3 text-[13px] leading-relaxed text-fg-muted">{t('trend.anomIntro')}</p>
        <div className="h-[200px]">
          <ResponsiveContainer>
            <BarChart data={anoms.rows} margin={{ top: 8, right: 8, left: 8, bottom: 0 }}>
              {GRID}
              <XAxis dataKey="year" {...AXIS} interval="preserveStartEnd" />
              <YAxis {...AXIS} width={56} tickFormatter={(v: number) => fmt(v)} />
              <ReferenceLine y={0} stroke={MUTED} />
              <Tooltip {...tooltipStyle} formatter={(v) => [`${Number(v) > 0 ? '+' : ''}${fmt(Number(v))}`, t('trend.vsMean')]} />
              <Bar dataKey="anomaly" radius={[3, 3, 3, 3]} isAnimationActive={false}>
                {anoms.rows.map((d) => (
                  <Cell key={d.year} fill={d.anomaly >= 0 ? '#ff6b1a' : '#5ba4ff'} fillOpacity={d.complete ? 1 : 0.35} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
        {anoms.rows.some((d) => !d.complete) && <p className="mt-2 text-[11px] text-fg-muted">{t('trend.partial')}</p>}
      </div>
    </div>
  )
}

// W9: typical season, with any year compared against the mean and P10–P90 range
export function SeasonalChart({ calendar }: { calendar: CalendarEntry[] }) {
  const t = useT()
  const lang = useApp((s) => s.lang)
  const years = [...new Set(calendar.map((c) => c.year))].sort((a, b) => b - a)
  const [year, setYear] = useState(years[0])
  const data = seasonalProfile(calendar, year).map((d) => ({ ...d, name: monthName(d.month, lang) }))
  const above = data.filter((d) => d.above).map((d) => d.name)

  return (
    <div>
      <div className="mb-3 flex items-start justify-between gap-3">
        <p className="text-[13px] leading-relaxed text-fg-muted">{t('season.intro')}</p>
        <label className="flex shrink-0 items-center gap-2 text-xs text-fg-muted">
          {t('season.year')}
          <select
            value={year}
            onChange={(e) => setYear(Number(e.target.value))}
            className="h-7 rounded-[6px] bg-ink-800 px-2 font-mono text-xs text-ember-300 ring-1 ring-line outline-none focus-visible:ring-ember-500/60"
          >
            {years.map((y) => (
              <option key={y} value={y} className="bg-ink-900">
                {y}
              </option>
            ))}
          </select>
        </label>
      </div>
      <div className="h-[300px]" data-export-main>
        <ResponsiveContainer>
          <ComposedChart data={data} margin={{ top: 8, right: 8, left: 8, bottom: 0 }}>
            {GRID}
            <XAxis dataKey="name" {...AXIS} />
            <YAxis {...AXIS} width={56} tickFormatter={(v: number) => fmt(v)}>
              {yLabel(t('trend.yMonthly'))}
            </YAxis>
            <Tooltip {...tooltipStyle} />
            <Area dataKey="band" name={t('season.band')} fill="#5ba4ff" fillOpacity={0.15} stroke="none" isAnimationActive={false} />
            <Line dataKey="mean" name={t('season.mean')} stroke={MUTED} strokeWidth={2} dot={false} isAnimationActive={false} />
            <Line
              dataKey="value"
              name={String(year)}
              stroke="#ff6b1a"
              strokeWidth={2.5}
              connectNulls={false}
              isAnimationActive={false}
              dot={(p: { cx?: number; cy?: number; payload?: { above: boolean; month: number } }) =>
                p.cx === undefined || p.cy === undefined ? (
                  <g key={p.payload?.month} />
                ) : (
                  <circle
                    key={p.payload?.month}
                    cx={p.cx}
                    cy={p.cy}
                    r={p.payload?.above ? 6 : 3}
                    fill={p.payload?.above ? '#ff3d00' : '#ff6b1a'}
                    stroke={p.payload?.above ? '#fff' : 'none'}
                    strokeWidth={1.5}
                  />
                )
              }
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <div className="mt-3 flex flex-wrap gap-5 text-[11px] text-fg-muted">
        <span className="flex items-center gap-1.5">
          <i className="h-2 w-4 rounded-sm bg-cool-400/30" /> {t('season.band')}
        </span>
        <span className="flex items-center gap-1.5">
          <i className="h-0.5 w-4 bg-fg-muted" /> {t('season.mean')}
        </span>
        <span className="flex items-center gap-1.5">
          <i className="h-0.5 w-4 bg-ember-500" /> {year}
        </span>
      </div>
      <p className={clsx('mt-3 rounded-[10px] px-3 py-2 text-[13px] ring-1', above.length ? 'bg-ember-500/10 text-ember-300 ring-ember-500/30' : 'bg-ink-800 text-fg-muted ring-line')}>
        {above.length ? t('season.above', { year, months: above.join(', ') }) : t('season.none', { year })}
      </p>
    </div>
  )
}

export function RankingView({ calendar }: { calendar: CalendarEntry[] }) {
  const t = useT()
  const lang = useApp((s) => s.lang)
  const years = yearTotals(calendar)
    .sort((a, b) => b.count - a.count)
    .slice(0, 8)
  const months = topMonths(calendar, 5)
  const max = years[0]?.count ?? 1
  return (
    <div className="space-y-6">
      <div>
        <h3 className="mb-3 text-[11px] uppercase tracking-[0.08em] text-fg-muted">{t('rank.years')}</h3>
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
        <h3 className="mb-3 text-[11px] uppercase tracking-[0.08em] text-fg-muted">{t('rank.months')}</h3>
        <div className="grid grid-cols-5 gap-2">
          {months.map((m) => (
            <div key={`${m.year}-${m.month}`} className="rounded-[10px] bg-ink-800 px-3 py-2.5 ring-1 ring-line">
              <div className="text-xs text-fg-muted">
                {monthName(m.month, lang)} <span className="font-mono">{m.year}</span>
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
  const t = useT()
  return (
    <div className="space-y-4 text-[13.5px] leading-relaxed text-fg-muted">
      <p>
        <span className="text-fg">{t('about.why')}</span> {t('about.whyText')}
      </p>
      <p>
        <span className="text-fg">{t('about.what')}</span> {t('about.whatText')}
      </p>
      <p>
        <span className="text-fg">{t('about.limits')}</span> {t('about.limitsText')}
      </p>
      <p>
        <span className="text-fg">{t('about.updated')}:</span> <span className="font-mono">{t('about.unknown')}</span>
      </p>
      <p>{t('about.source')}</p>
    </div>
  )
}

import { Slider } from '@base-ui/react/slider'
import NumberFlow from '@number-flow/react'
import { ArrowRight, CircleNotch, Info } from '@phosphor-icons/react'
import clsx from 'clsx'
import { useEffect, useState, type ReactNode } from 'react'
import { DATA_START, TODAY, useApp } from '../store'
import DatePicker from './DatePicker'
import EmptyState, { totalHotspots } from './EmptyState'
import { currentVsMean, fmt, referenceMeans, summary } from '../lib/stats'
import { monthName, useT, type TKey } from '../i18n'
import { useShallow } from 'zustand/react/shallow'

const RADII = [5, 25, 50, 100, 150, 300]

function minusYears(iso: string, years: number) {
  const d = new Date(iso)
  d.setFullYear(d.getFullYear() - years)
  return d.toISOString().slice(0, 10)
}

const RANGES: { label: TKey; from: () => string }[] = [
  { label: 'range.12m', from: () => minusYears(TODAY, 1) },
  { label: 'range.5y', from: () => minusYears(TODAY, 5) },
  { label: 'range.all', from: () => DATA_START },
]

function Chip({ active, onClick, children }: { active: boolean; onClick: () => void; children: ReactNode }) {
  return (
    <button
      onClick={onClick}
      className={clsx(
        'h-7 rounded-[6px] px-1.5 text-[11px] whitespace-nowrap transition-colors duration-150',
        active ? 'bg-ember-500/15 text-ember-300 ring-1 ring-ember-500/40' : 'text-fg-muted ring-1 ring-line hover:bg-ink-700 hover:text-fg',
      )}
    >
      {children}
    </button>
  )
}

function Label({ children, right }: { children: ReactNode; right?: ReactNode }) {
  return (
    <div className="mb-2.5 flex items-baseline justify-between">
      <span className="text-[11px] font-medium uppercase tracking-[0.08em] text-fg-muted">{children}</span>
      {right}
    </div>
  )
}

function RadiusInput({ value, onChange, label }: { value: number; onChange: (km: number) => void; label: string }) {
  const [draft, setDraft] = useState(String(value))
  useEffect(() => setDraft(String(value)), [value])
  const commit = () => {
    const n = Math.round(Number(draft))
    if (Number.isFinite(n) && n > 0) onChange(Math.min(500, Math.max(1, n)))
      else setDraft(String(value))
  }
  return (
    <label className="flex items-baseline gap-1 font-mono text-sm text-ember-300">
      <input
        type="number"
        inputMode="numeric"
        min={1}
        max={500}
        step={1}
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={commit}
        onKeyDown={(e) => e.key === 'Enter' && e.currentTarget.blur()}
        aria-label={label}
        className="w-14 rounded-[6px] bg-ink-800 px-1.5 py-0.5 text-right ring-1 ring-line outline-none focus:ring-ember-500/60 [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none"
      />
      km
    </label>
  )
}
function Card({ label, children, sub }: { label: ReactNode; children: ReactNode; sub: ReactNode }) {
  return (
    <div className="bg-ink-900 px-5 py-3.5">
      <div className="truncate text-[11px] uppercase tracking-[0.08em] text-fg-muted">{label}</div>
      <div className="font-mono text-[22px] leading-tight font-medium">{children}</div>
      <div className="text-xs leading-snug text-fg-muted">{sub}</div>
    </div>
  )
}

export default function AreaPanel() {
  const t = useT()
  const { place, radiusKm, dateFrom, dateTo, status, calendar, anomalies, lang, hotspotTotal, hotspotTotalStatus } = useApp(useShallow((s) => ({ place: s.place, radiusKm: s.radiusKm, dateFrom: s.dateFrom, dateTo: s.dateTo, status: s.status, calendar: s.calendar, anomalies: s.anomalies, lang: s.lang, hotspotTotal: s.hotspotTotal, hotspotTotalStatus: s.hotspotTotalStatus })))
  const { setRadius, setDates, analyze } = useApp.getState()
  if (!place) return null

  const empty = status === 'ready' && totalHotspots(calendar) === 0
  const kpi = calendar && !empty ? currentVsMean(calendar, dateTo, referenceMeans(anomalies, calendar).means) : null
  const sum = calendar && !empty ? summary(calendar) : null

  return (
    <section className="glass mt-3 flex max-h-[calc(100vh-96px)] flex-col overflow-y-auto rounded-[14px] animate-[panel-in_240ms_cubic-bezier(0.23,1,0.32,1)]">
      {/* Header */}
      <div className="px-5 pt-5 pb-4">
        <h1 className="font-display text-[22px] leading-tight font-semibold tracking-tight">{place.label}</h1>
        <p className="mt-1 text-[13px] text-fg-muted">
          {place.detail && <>{place.detail} · </>}
          <span className="font-mono">
            {Math.abs(place.lat).toFixed(2)}° {place.lat >= 0 ? 'N' : 'S'}, {Math.abs(place.lon).toFixed(2)}° {place.lon >= 0 ? 'E' : 'W'}
          </span>
        </p>
      </div>

      <div className="h-px bg-line" />

      {/* Radius */}
      <div className="px-5 pt-4">
        <Label right={<RadiusInput value={radiusKm} onChange={setRadius} label={t('panel.radiusAria')} />}>{t('panel.radius')}</Label>
        <Slider.Root value={radiusKm} onValueChange={(v) => setRadius(v as number)} min={1} max={500} step={1}>
          <Slider.Control className="flex h-6 w-full touch-none items-center select-none">
            <Slider.Track className="h-1 w-full rounded-full bg-ink-700">
              <Slider.Indicator className="rounded-full bg-ember-500" />
              <Slider.Thumb
                aria-label={t('panel.radiusAria')}
                className="size-4 rounded-full bg-fg shadow-[0_0_0_4px_rgb(255_107_26/0.25)] outline-none focus-visible:shadow-[0_0_0_6px_rgb(255_107_26/0.45)]"
              />
            </Slider.Track>
          </Slider.Control>
        </Slider.Root>
        <div className="mt-3 grid grid-cols-6 gap-1">
          {RADII.map((r) => (
            <Chip key={r} active={radiusKm === r} onClick={() => setRadius(r)}>
              <span className="font-mono">{r}</span> km
            </Chip>
          ))}
        </div>
      </div>

      {/* Dates */}
      <div className="px-5 pt-5">
        <Label>{t('panel.period')}</Label>
        <div className="grid grid-cols-2 gap-2">
          <DatePicker label={t('panel.from')} value={dateFrom} min={DATA_START} max={dateTo} onChange={(v) => setDates(v, dateTo)} />
          <DatePicker label={t('panel.to')} value={dateTo} min={dateFrom} max={TODAY} onChange={(v) => setDates(dateFrom, v)} />
        </div>
        <div className="mt-3 flex flex-wrap gap-1.5">
          {RANGES.map((r) => (
            <Chip key={r.label} active={dateFrom === r.from() && dateTo === TODAY} onClick={() => setDates(r.from(), TODAY)}>
              {t(r.label)}
            </Chip>
          ))}
        </div>
      </div>

      {/* Action */}
      <div className="px-5 pt-5 pb-5">
        <button
          onClick={analyze}
          disabled={status === 'loading' || dateFrom > dateTo}
          className="flex h-11 w-full items-center justify-center gap-2 rounded-[10px] bg-ember-500 font-medium text-ink-950 transition-[transform,background-color] duration-150 hover:bg-[#ff7d36] active:scale-[0.98] disabled:opacity-60"
        >
          {status === 'loading' ? (
            <>
              <CircleNotch size={18} className="animate-spin" /> {t('panel.analyzing')}
            </>
          ) : (
            <>
              {status === 'ready' ? t('panel.update') : t('panel.analyze')} <ArrowRight size={16} weight="bold" />
            </>
          )}
        </button>
        {dateFrom > dateTo && <p className="mt-2 text-xs text-ember-300">{t('panel.badDates')}</p>}
      </div>

      {/* Quick results */}
      {empty && (
        <>
          <div className="h-px bg-line" />
          <EmptyState compact />
        </>
      )}

      {kpi && sum && (
        <>
          <div className="h-px bg-line" />
          {/* Summary cards (W5): consistent with the calendar */}
          <div className="grid grid-cols-2 gap-px bg-line">
            <Card label={t('kpi.total')} sub={t('kpi.totalSub')}>
              {hotspotTotalStatus === 'ready' && hotspotTotal !== null ? (
                <NumberFlow value={hotspotTotal} />
              ) : hotspotTotalStatus === 'loading' ? (
                <CircleNotch size={20} className="mt-1.5 animate-spin text-fg-muted" />
              ) : (
                '—'
              )}
            </Card>
            <Card
              label={t('kpi.peakMonth')}
              sub={sum.peakMonth ? `${fmt(sum.peakMonth.count)} ${t('hotspots')}` : '—'}
            >
              {sum.peakMonth ? `${monthName(sum.peakMonth.month, lang)} ${sum.peakMonth.year}` : '—'}
            </Card>
            <Card label={t('kpi.avg')} sub={t('kpi.avgSub')}>
              <NumberFlow value={Math.round(sum.annualAvg)} />
            </Card>
            <Card
              label={`${monthName(kpi.month, lang)} ${kpi.year}`}
              sub={
                <>
                  <span className="font-mono">{fmt(kpi.count)}</span> {kpi.partial ? t('kpi.soFar') : t('hotspots')} ·{' '}
                  {kpi.partial ? t('kpi.vsMeanToDate') : t('kpi.vsMean')} <span className="font-mono">{fmt(kpi.mean)}</span>
                </>
              }
            >
              <NumberFlow
                value={Math.max(-999, Math.min(999, Math.round(kpi.pct)))}
                prefix={kpi.pct > 0 ? '+' : ''}
                suffix="%"
                className={clsx(kpi.pct > 15 ? 'text-ember-300' : kpi.pct < -15 ? 'text-cool-400' : 'text-fg')}
              />
            </Card>
          </div>
          {sum.peakYear && (
            <div className="px-5 py-3 text-xs text-fg-muted">
              {t('kpi.peakYear', { year: sum.peakYear.year, count: fmt(sum.peakYear.count) })}
            </div>
          )}
        </>
      )}

      <div className="mx-5 mb-5 flex gap-2 rounded-[10px] bg-ink-800 p-3 text-xs leading-relaxed text-fg-muted ring-1 ring-line">
        <Info size={16} className="mt-px shrink-0" />
        <span>
          {t('panel.info')}
        </span>
      </div>
    </section>
  )
}

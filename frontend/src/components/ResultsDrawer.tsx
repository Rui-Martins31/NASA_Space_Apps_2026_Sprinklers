import { useEffect, useRef } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { X, CircleNotch, DownloadSimple } from '@phosphor-icons/react'
import { toast } from 'sonner'
import { DATA_START, useApp } from '../store'
import { useT, type TKey } from '../i18n'
import CalendarHeatmap from './views/CalendarHeatmap'
import EmptyState, { totalHotspots } from './EmptyState'
import { AboutView, RankingView, SeasonalChart, TrendView } from './views/Charts'
import { calendarSvg, chartFromDom, downloadPng, downloadSvg, exportFilename, frameSvg, type ExportMeta } from '../lib/export'
import type { View } from '../types'

const TITLE: Record<View, TKey> = {
  calendar: 'view.calendar',
  trend: 'view.trend',
  seasonal: 'view.seasonal',
  ranking: 'view.ranking',
  about: 'view.about',
}
const EXPORTABLE: View[] = ['calendar', 'trend', 'seasonal']

// Right-hand results panel. Not a modal: the globe and menus stay usable while it is open.
export default function ResultsDrawer() {
  const t = useT()
  const { view, status, calendar, place, radiusKm, dateFrom, dateTo, lang, calendarScale } = useApp()
  const { openView } = useApp.getState()
  const bodyRef = useRef<HTMLDivElement>(null)

  // Escape closes the panel
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && !document.querySelector('.popover-popup') && openView(null)
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [openView])

  const hasData = status === 'ready' && !!calendar && totalHotspots(calendar) > 0

  // W10: the chart on screen as PNG or SVG, with area, period, date and source
  async function exportView(format: 'png' | 'svg') {
    if (!view || !calendar || !place) return
    const meta: ExportMeta = { title: t(TITLE[view]), place: place.label, radiusKm, dateFrom, dateTo, lang }
    const chart =
      view === 'calendar'
        ? calendarSvg(calendar, calendarScale, lang, DATA_START)
        : chartFromDom(bodyRef.current?.querySelector('[data-export-main]') as HTMLElement | null)
    if (!chart) return
    const svg = frameSvg(chart.svg, chart.w, chart.h, meta)
    try {
      if (format === 'svg') downloadSvg(svg, exportFilename(meta, 'svg'))
      else await downloadPng(svg, exportFilename(meta, 'png'))
    } catch (e) {
      toast.error(t('toast.csvFailed'), { description: (e as Error).message })
    }
  }

  const body = () => {
    if (view === 'about') return <AboutView />
    if (status === 'loading' || !calendar)
      return (
        <div className="flex h-60 items-center justify-center gap-2 text-sm text-fg-muted">
          <CircleNotch size={18} className="animate-spin" /> {t('view.loading')}
        </div>
      )
    if (totalHotspots(calendar) === 0) return <EmptyState />
    switch (view) {
      case 'calendar':
        return <CalendarHeatmap calendar={calendar} />
      case 'trend':
        return <TrendView calendar={calendar} />
      case 'seasonal':
        return <SeasonalChart calendar={calendar} />
      case 'ranking':
        return <RankingView calendar={calendar} />
    }
  }

  return (
    <AnimatePresence>
      {view && (
        <motion.aside
          key="results"
          role="region"
          aria-label={t(TITLE[view])}
          initial={{ opacity: 0, x: 24 }}
          animate={{ opacity: 1, x: 0, transition: { duration: 0.24, ease: [0.23, 1, 0.32, 1] } }}
          exit={{ opacity: 0, x: 24, transition: { duration: 0.15, ease: 'easeIn' } }}
          className="glass fixed top-20 right-4 bottom-4 z-20 flex w-[min(600px,calc(100vw-32px))] flex-col rounded-[14px]"
        >
          <div className="flex items-start justify-between gap-4 px-6 pt-5 pb-4">
            <div>
              <h2 className="font-display text-lg font-semibold">{t(TITLE[view])}</h2>
              {place && view !== 'about' && (
                <p className="mt-0.5 font-mono text-[11px] text-fg-muted">
                  {place.label} · {radiusKm} km · {dateFrom} → {dateTo}
                </p>
              )}
            </div>
            <div className="flex items-center gap-1">
              {hasData && EXPORTABLE.includes(view) && (
                <div className="mr-1 flex items-center gap-1" title={t('export.saveAs')}>
                  <DownloadSimple size={14} className="text-fg-muted" />
                  {(['png', 'svg'] as const).map((f) => (
                    <button
                      key={f}
                      onClick={() => exportView(f)}
                      className="h-7 rounded-[6px] px-2 font-mono text-[11px] text-fg-muted ring-1 ring-line hover:bg-ink-700 hover:text-fg"
                    >
                      {t(f === 'png' ? 'export.png' : 'export.svg')}
                    </button>
                  ))}
                </div>
              )}
              <button onClick={() => openView(null)} aria-label={t('close')} className="rounded-md p-1.5 text-fg-muted hover:bg-ink-700 hover:text-fg">
                <X size={18} />
              </button>
            </div>
          </div>
          <div className="h-px bg-line" />
          <div ref={bodyRef} className="flex-1 overflow-y-auto px-6 py-5">
            {body()}
          </div>
        </motion.aside>
      )}
    </AnimatePresence>
  )
}

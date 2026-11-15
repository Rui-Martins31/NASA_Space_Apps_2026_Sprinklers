import { useEffect } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { X, CircleNotch } from '@phosphor-icons/react'
import { useApp } from '../store'
import CalendarHeatmap from './views/CalendarHeatmap'
import EmptyState, { totalHotspots } from './EmptyState'
import { AboutView, AnomaliesChart, RankingView, SeasonalChart } from './views/Charts'
import type { View } from '../types'

const TITLES: Record<View, string> = {
  calendar: 'Burning calendar',
  anomalies: 'Anomalies',
  seasonal: 'Seasonal profile',
  ranking: 'Year ranking',
  about: 'About the method',
}

// Right-hand results panel. Not a modal: the globe and menus stay usable while it is open.
export default function ResultsDrawer() {
  const { view, status, calendar, anomalies, place, radiusKm } = useApp()
  const { openView } = useApp.getState()

  // Escape closes the panel
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && !document.querySelector('.popover-popup') && openView(null)
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [openView])

  const body = () => {
    if (view === 'about') return <AboutView />
    if (status === 'loading' || !calendar || !anomalies)
      return (
        <div className="flex h-60 items-center justify-center gap-2 text-sm text-fg-muted">
          <CircleNotch size={18} className="animate-spin" /> Loading data…
        </div>
      )
    if (totalHotspots(calendar) === 0) return <EmptyState />
    switch (view) {
      case 'calendar':
        return <CalendarHeatmap calendar={calendar} />
      case 'anomalies':
        return <AnomaliesChart anomalies={anomalies} />
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
          aria-label={TITLES[view]}
          initial={{ opacity: 0, x: 24 }}
          animate={{ opacity: 1, x: 0, transition: { duration: 0.24, ease: [0.23, 1, 0.32, 1] } }}
          exit={{ opacity: 0, x: 24, transition: { duration: 0.15, ease: 'easeIn' } }}
          className="glass fixed top-20 right-4 bottom-4 z-20 flex w-[min(560px,calc(100vw-32px))] flex-col rounded-[14px]"
        >
          <div className="flex items-start justify-between gap-4 px-6 pt-5 pb-4">
            <div>
              <h2 className="font-display text-lg font-semibold">{TITLES[view]}</h2>
              {place && view !== 'about' && (
                <p className="mt-0.5 font-mono text-[11px] text-fg-muted">
                  {place.label} · {radiusKm} km
                </p>
              )}
            </div>
            <button onClick={() => openView(null)} aria-label="Close" className="rounded-md p-1.5 text-fg-muted hover:bg-ink-700 hover:text-fg">
              <X size={18} />
            </button>
          </div>
          <div className="h-px bg-line" />
          <div className="flex-1 overflow-y-auto px-6 py-5">{body()}</div>
        </motion.aside>
      )}
    </AnimatePresence>
  )
}

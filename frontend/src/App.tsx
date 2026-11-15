import { Toaster } from 'sonner'
import { X } from '@phosphor-icons/react'
import clsx from 'clsx'
import GlobeMap from './components/GlobeMap'
import SearchBar from './components/SearchBar'
import AreaPanel from './components/AreaPanel'
import AnalysesMenu from './components/AnalysesMenu'
import ResultsDrawer from './components/ResultsDrawer'
import ReplayBar from './components/ReplayBar'
import MapModeToggle from './components/MapModeToggle'
import { usingMock } from './api/client'
import { useApp } from './store'
import { monthName, useT, type Lang } from './i18n'

// EN / PT switch (W14): changes all text instantly, no reload
function LangSwitch() {
  const lang = useApp((s) => s.lang)
  const setLang = useApp((s) => s.setLang)
  return (
    <div className="glass flex h-12 items-center gap-0.5 rounded-[14px] p-1.5" role="radiogroup" aria-label="Language / Idioma">
      {(['en', 'pt'] as Lang[]).map((l) => (
        <button
          key={l}
          role="radio"
          aria-checked={lang === l}
          onClick={() => setLang(l)}
          className={clsx(
            'h-full rounded-[9px] px-2.5 font-mono text-xs uppercase transition-colors duration-150',
            lang === l ? 'bg-ember-500/15 text-ember-300' : 'text-fg-muted hover:text-fg',
          )}
        >
          {l}
        </button>
      ))}
    </div>
  )
}

// Shown when the map is filtered to one month clicked in the calendar (W11 / C8)
function MonthFilterChip() {
  const t = useT()
  const win = useApp((s) => s.hotspotWindow)
  const lang = useApp((s) => s.lang)
  if (!win) return null
  return (
    <div className="glass absolute top-4 left-1/2 z-20 flex h-10 -translate-x-1/2 items-center gap-2 rounded-full pr-1.5 pl-4 text-sm animate-[panel-in_240ms_cubic-bezier(0.23,1,0.32,1)]">
      <span className="size-2 rounded-full bg-ember-500" />
      {t('filter.showing', { month: `${monthName(win.month, lang, 'long')} ${win.year}` })}
      <button
        onClick={() => useApp.getState().loadHotspots()}
        className="ml-1 flex h-7 items-center gap-1 rounded-full px-2.5 text-xs text-fg-muted ring-1 ring-line hover:bg-ink-700 hover:text-fg"
      >
        {t('filter.clear')}
      </button>
      <button
        onClick={() => useApp.getState().clearHotspots()}
        aria-label={t('close')}
        className="grid size-7 place-items-center rounded-full text-fg-muted hover:bg-ink-700 hover:text-fg"
      >
        <X size={14} />
      </button>
    </div>
  )
}

export default function App() {
  const t = useT()
  const place = useApp((s) => s.place)

  return (
    <main className="relative h-full w-full overflow-hidden bg-ink-950">
      <GlobeMap />

      {/* Left column: search + area panel */}
      <div className="pointer-events-none absolute top-4 left-4 z-30 flex w-[min(380px,calc(100vw-32px))] flex-col">
        <div className="pointer-events-auto">
          <SearchBar />
        </div>
        <div className="pointer-events-auto">
          <AreaPanel />
        </div>
      </div>

      <MonthFilterChip />

      {/* Top right: brand, language, analyses menu */}
      <div className="absolute top-4 right-4 z-30 flex items-center gap-3">
        <div className="glass hidden h-12 items-center gap-2.5 rounded-[14px] px-4 lg:flex">
          <span className="size-2.5 rounded-full bg-ember-500 shadow-[0_0_12px_#ff6b1a]" />
          <span className="font-display text-[15px] font-semibold tracking-tight">FireCal</span>
          <span className="text-xs text-fg-muted">{t('brand.sub')}</span>
          {usingMock && <span className="rounded-[6px] bg-ink-700 px-1.5 py-0.5 font-mono text-[10px] text-fg-muted">{t('mock')}</span>}
        </div>
        <LangSwitch />
        <AnalysesMenu />
      </div>

      {/* First-visit hint */}
      {!place && (
        <div className="pointer-events-none absolute bottom-10 left-1/2 z-10 -translate-x-1/2 text-center">
          <p className="font-display text-2xl font-medium tracking-tight">{t('hero.title')}</p>
          <p className="mt-1.5 text-sm text-fg-muted">{t('hero.sub')}</p>
        </div>
      )}

      <MapModeToggle />
      <ReplayBar />
      <ResultsDrawer />
      <Toaster theme="dark" position="top-center" offset={64} toastOptions={{ style: { fontFamily: 'IBM Plex Sans', background: '#0d1117' } }} />
    </main>
  )
}

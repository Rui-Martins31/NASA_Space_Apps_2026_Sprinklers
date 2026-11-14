import { Toaster } from 'sonner'
import GlobeMap from './components/GlobeMap'
import SearchBar from './components/SearchBar'
import AreaPanel from './components/AreaPanel'
import AnalysesMenu from './components/AnalysesMenu'
import ResultsDrawer from './components/ResultsDrawer'
import ReplayBar from './components/ReplayBar'
import MapModeToggle from './components/MapModeToggle'
import { usingMock } from './api/client'
import { useApp } from './store'

export default function App() {
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

      {/* Top right: brand + analyses menu */}
      <div className="absolute top-4 right-4 z-30 flex items-center gap-3">
        <div className="glass hidden h-12 items-center gap-2.5 rounded-[14px] px-4 sm:flex">
          <span className="size-2.5 rounded-full bg-ember-500 shadow-[0_0_12px_#ff6b1a]" />
          <span className="font-display text-[15px] font-semibold tracking-tight">FireCal</span>
          <span className="text-xs text-fg-muted">MODIS + VIIRS</span>
          {usingMock && <span className="rounded-[6px] bg-ink-700 px-1.5 py-0.5 font-mono text-[10px] text-fg-muted">mock data</span>}
        </div>
        <AnalysesMenu />
      </div>

      {/* First-visit hint */}
      {!place && (
        <div className="pointer-events-none absolute bottom-10 left-1/2 z-10 -translate-x-1/2 text-center">
          <p className="font-display text-2xl font-medium tracking-tight">Two decades of fire, one consistent record.</p>
          <p className="mt-1.5 text-sm text-fg-muted">Search any place to see when and how much it burns.</p>
        </div>
      )}

      <MapModeToggle />
      <ReplayBar />
      <ResultsDrawer />
      <Toaster theme="dark" position="top-center" toastOptions={{ style: { fontFamily: 'IBM Plex Sans', background: '#0d1117' } }} />
    </main>
  )
}

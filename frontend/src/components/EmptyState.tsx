import { FireSimple } from '@phosphor-icons/react'
import { DATA_START, TODAY, useApp } from '../store'

const RADIUS_STEPS = [25, 50, 100, 300, 500]

/** Total hotspots in the calendar (0 means nothing was detected). */
export function totalHotspots(calendar: { count: number }[] | null) {
  return calendar ? calendar.reduce((sum, c) => sum + c.count, 0) : 0
}

// Shown instead of numbers and charts when the area has no hotspots at all,
// so nothing on screen looks like real data when there is none.
export default function EmptyState({ compact = false }: { compact?: boolean }) {
  const radiusKm = useApp((s) => s.radiusKm)
  const dateFrom = useApp((s) => s.dateFrom)
  const dateTo = useApp((s) => s.dateTo)

  const nextRadius = RADIUS_STEPS.find((r) => r > radiusKm)
  const fullRecord = dateFrom === DATA_START && dateTo === TODAY

  const retry = (change: () => void) => {
    change()
    useApp.getState().analyze()
  }

  return (
    <div className={compact ? 'px-5 py-5' : 'flex flex-col items-center px-6 py-16 text-center'}>
      <div className={compact ? 'flex gap-3' : 'flex flex-col items-center gap-3'}>
        <span className="grid size-9 shrink-0 place-items-center rounded-full bg-ink-800 text-fg-muted ring-1 ring-line">
          <FireSimple size={18} />
        </span>
        <div>
          <p className="text-sm font-medium text-fg">No hotspots detected</p>
          <p className="mt-1 text-[13px] leading-relaxed text-fg-muted">
            Nothing within <span className="font-mono text-fg">{radiusKm} km</span> between{' '}
            <span className="font-mono text-fg">{dateFrom.slice(0, 4)}</span> and{' '}
            <span className="font-mono text-fg">{dateTo.slice(0, 4)}</span>.
            {(nextRadius || !fullRecord) && ' Try a wider search:'}
          </p>
        </div>
      </div>
      {(nextRadius || !fullRecord) && (
        <div className={compact ? 'mt-3 flex flex-wrap gap-1.5 pl-12' : 'mt-4 flex flex-wrap justify-center gap-1.5'}>
          {nextRadius && (
            <button
              onClick={() => retry(() => useApp.getState().setRadius(nextRadius))}
              className="h-7 rounded-[6px] px-2.5 text-xs text-ember-300 ring-1 ring-ember-500/40 transition-colors duration-150 hover:bg-ember-500/15"
            >
              Try <span className="font-mono">{nextRadius}</span> km
            </button>
          )}
          {!fullRecord && (
            <button
              onClick={() => retry(() => useApp.getState().setDates(DATA_START, TODAY))}
              className="h-7 rounded-[6px] px-2.5 text-xs text-ember-300 ring-1 ring-ember-500/40 transition-colors duration-150 hover:bg-ember-500/15"
            >
              Use full record
            </button>
          )}
        </div>
      )}
    </div>
  )
}

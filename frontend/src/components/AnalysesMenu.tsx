import { Popover } from '@base-ui/react/popover'
import {
  CalendarDots,
  ChartBar,
  ChartLineUp,
  Ranking,
  Fire,
  FileCsv,
  Table,
  BookOpenText,
  DotsNine,
  CircleNotch,
} from '@phosphor-icons/react'
import type { Icon } from '@phosphor-icons/react'
import clsx from 'clsx'
import { toast } from 'sonner'
import { useApp } from '../store'
import { downloadCsv, hotspotsFilename } from '../lib/stats'
import { fetchFeature } from '../api/client'
import type { View } from '../types'

interface Item {
  label: string
  icon: Icon
  tint: string
  run: () => void
  active?: boolean
  busy?: boolean
}

function Tile({ item, disabled }: { item: Item; disabled: boolean }) {
  const I = item.icon
  return (
    <Popover.Close
      disabled={disabled}
      onClick={item.run}
      className={clsx(
        'group flex flex-col items-center gap-2 rounded-[12px] px-1 pt-3.5 pb-3 text-center transition-colors duration-150',
        'hover:bg-ink-700 disabled:pointer-events-none disabled:opacity-40',
        item.active && 'bg-ink-800 ring-1 ring-ember-500/40',
      )}
    >
      <span className={clsx('grid size-11 place-items-center rounded-[12px] transition-transform duration-150 group-active:scale-95', item.tint)}>
        {item.busy ? <CircleNotch size={22} className="animate-spin" /> : <I size={22} weight="duotone" />}
      </span>
      <span className="text-[12.5px] leading-tight text-fg">{item.label}</span>
    </Popover.Close>
  )
}

export default function AnalysesMenu() {
  const { place, status, view, hotspots, hotspotsLoading, calendar, radiusKm, dateFrom, dateTo } = useApp()
  const { openView, analyze, loadHotspots } = useApp.getState()

  // Opening a chart before analyzing runs the analysis first.
  const show = (v: View) => () => {
    openView(v)
    if (status !== 'ready' && v !== 'about') analyze()
  }

  async function exportHotspots() {
    if (!place) return
    const id = toast.loading('Preparing CSV…')
    try {
      const res = await fetchFeature('hotspots', {
        lat: place.lat,
        lon: place.lon,
        radius_km: radiusKm,
        date_from: dateFrom,
        date_to: dateTo,
        max_points: 1_000_000,
      })
      downloadCsv(hotspotsFilename(place.label, dateFrom, dateTo), res.hotspots ?? [])
      toast.success(`CSV with ${(res.hotspots ?? []).length.toLocaleString('en')} hotspots downloaded`, { id })
    } catch (e) {
      toast.error('Export failed', { id, description: (e as Error).message })
    }
  }

  function exportCalendar() {
    if (!calendar || !place) return
    downloadCsv(`calendar_${hotspotsFilename(place.label, dateFrom, dateTo).slice(9)}`, calendar)
    toast.success('Monthly calendar downloaded')
  }

  const analyses: Item[] = [
    { label: 'Burning calendar', icon: CalendarDots, tint: 'bg-[#e1cc55]/15 text-[#e1cc55]', run: show('calendar'), active: view === 'calendar' },
    { label: 'Anomalies', icon: ChartBar, tint: 'bg-ember-500/15 text-ember-300', run: show('anomalies'), active: view === 'anomalies' },
    { label: 'Seasonal profile', icon: ChartLineUp, tint: 'bg-cool-400/15 text-cool-400', run: show('seasonal'), active: view === 'seasonal' },
    { label: 'Year ranking', icon: Ranking, tint: 'bg-[#c792ea]/15 text-[#d4a8f0]', run: show('ranking'), active: view === 'ranking' },
    {
      label: hotspots ? 'Hide hotspots' : 'Hotspots on map',
      icon: Fire,
      tint: 'bg-ember-500/15 text-ember-500',
      run: () => (hotspots ? useApp.setState({ hotspots: null }) : loadHotspots()),
      active: !!hotspots,
      busy: hotspotsLoading,
    },
    { label: 'About the method', icon: BookOpenText, tint: 'bg-fg/10 text-fg', run: show('about'), active: view === 'about' },
  ]
  const exports: Item[] = [
    { label: 'Hotspots CSV', icon: FileCsv, tint: 'bg-[#4fd1a5]/15 text-[#4fd1a5]', run: exportHotspots },
    { label: 'Calendar CSV', icon: Table, tint: 'bg-[#4fd1a5]/15 text-[#4fd1a5]', run: exportCalendar },
  ]

  return (
    <Popover.Root>
      <Popover.Trigger
        aria-label="Analyses"
        className="glass grid size-12 place-items-center rounded-[14px] text-fg transition-transform duration-150 hover:text-ember-300 active:scale-95 data-[popup-open]:text-ember-300"
      >
        <DotsNine size={24} weight="bold" />
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Positioner side="bottom" align="end" sideOffset={10} className="z-40">
          <Popover.Popup className="popover-popup glass w-[340px] rounded-[18px] p-2.5 outline-none">
            <div className="rounded-[14px] bg-ink-950/50 p-2 ring-1 ring-line">
              <div className="px-2.5 pt-2 pb-1">
                <Popover.Title className="font-display text-base font-semibold">Analyze this area</Popover.Title>
                <Popover.Description className="mt-0.5 font-mono text-[11px] text-fg-muted">
                  {place ? `${place.label} · ${radiusKm} km · ${dateFrom.slice(0, 4)}–${dateTo.slice(0, 4)}` : 'Search a place first'}
                </Popover.Description>
              </div>
              <div className="mt-1 grid grid-cols-3 gap-1">
                {analyses.map((it) => (
                  <Tile key={it.label} item={it} disabled={!place && it.label !== 'About the method'} />
                ))}
              </div>
            </div>
            <div className="px-3 pt-3 pb-1 text-[11px] uppercase tracking-[0.08em] text-fg-muted">Export</div>
            <div className="grid grid-cols-3 gap-1">
              {exports.map((it) => (
                <Tile key={it.label} item={it} disabled={!place || (it.label === 'Calendar CSV' && !calendar)} />
              ))}
            </div>
          </Popover.Popup>
        </Popover.Positioner>
      </Popover.Portal>
    </Popover.Root>
  )
}

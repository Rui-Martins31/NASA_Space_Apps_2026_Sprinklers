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
  PlayCircle,
  FilePdf,
} from '@phosphor-icons/react'
import type { Icon } from '@phosphor-icons/react'
import clsx from 'clsx'
import { toast } from 'sonner'
import { DATA_START, useApp } from '../store'
import { useT } from '../i18n'
import { openReport } from '../lib/export'
import { downloadCsv, hotspotsFilename } from '../lib/stats'
import { fetchFeature, MAX_HOTSPOTS } from '../api/client'
import type { View } from '../types'

interface Item {
  id: string
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
  const t = useT()
  const { place, status, view, hotspots, hotspotsLoading, calendar, radiusKm, dateFrom, dateTo, replayTime, lang, calendarScale } = useApp()
  const { openView, analyze, loadHotspots } = useApp.getState()

  // Opening a chart before analyzing runs the analysis first.
  const show = (v: View) => () => {
    openView(v)
    if (status !== 'ready' && v !== 'about') analyze()
  }

  async function exportHotspots() {
    if (!place) return
    const id = toast.loading(t('toast.csvPreparing'))
    try {
      const res = await fetchFeature('hotspots', {
        lat: place.lat,
        lon: place.lon,
        radiusKm,
        dateFrom,
        dateTo,
        maxPoints: MAX_HOTSPOTS,
      })
      const rows = res.hotspots ?? []
      downloadCsv(hotspotsFilename(place.label, dateFrom, dateTo), rows)
      toast.success(t('toast.csvDone', { count: rows.length.toLocaleString('en') }), {
        id,
        description: rows.length >= MAX_HOTSPOTS ? t('toast.csvCapped', { max: MAX_HOTSPOTS.toLocaleString('en') }) : undefined,
      })
    } catch (e) {
      toast.error(t('toast.csvFailed'), { id, description: (e as Error).message })
    }
  }

  // Replay: hotspots appear on the map day by day over the chosen period.
  async function startReplay() {
    const s = useApp.getState()
    if (!s.hotspots || s.hotspotWindow) await loadHotspots()
    const pts = useApp.getState().hotspots
    if (!pts?.length) return
    useApp.getState().openView(null) // give the map the whole screen
    useApp.getState().setReplay(new Date(dateFrom).getTime(), true)
  }

  function exportCalendar() {
    if (!calendar || !place) return
    downloadCsv(`calendar_${hotspotsFilename(place.label, dateFrom, dateTo).slice(9)}`, calendar)
    toast.success(t('toast.calendarCsv'))
  }

  async function exportReport() {
    if (!place) return
    // open the tab right away (inside the click), so pop-up blockers allow it
    const win = window.open('', '_blank')
    if (!win) return toast.error(t('report.popup'))
    if (useApp.getState().status !== 'ready') await analyze()
    const cal = useApp.getState().calendar
    if (!cal) return win.close()
    openReport(cal, { title: t('report.title'), place: place.label, radiusKm, dateFrom, dateTo, lang }, calendarScale, DATA_START, win)
  }

  const analyses: Item[] = [
    { id: 'calendar', label: t('menu.calendar'), icon: CalendarDots, tint: 'bg-[#e1cc55]/15 text-[#e1cc55]', run: show('calendar'), active: view === 'calendar' },
    { id: 'trend', label: t('menu.trend'), icon: ChartBar, tint: 'bg-ember-500/15 text-ember-300', run: show('trend'), active: view === 'trend' },
    { id: 'seasonal', label: t('menu.seasonal'), icon: ChartLineUp, tint: 'bg-cool-400/15 text-cool-400', run: show('seasonal'), active: view === 'seasonal' },
    { id: 'ranking', label: t('menu.ranking'), icon: Ranking, tint: 'bg-[#c792ea]/15 text-[#d4a8f0]', run: show('ranking'), active: view === 'ranking' },
    {
      id: 'hotspots',
      label: hotspots ? t('menu.hideHotspots') : t('menu.hotspots'),
      icon: Fire,
      tint: 'bg-ember-500/15 text-ember-500',
      run: () => (hotspots ? useApp.getState().clearHotspots() : loadHotspots()),
      active: !!hotspots && replayTime === null,
      busy: hotspotsLoading,
    },
    { id: 'replay', label: t('menu.replay'), icon: PlayCircle, tint: 'bg-ember-500/15 text-ember-300', run: startReplay, active: replayTime !== null },
  ]
  const exports: Item[] = [
    { id: 'csv', label: t('menu.hotspotsCsv'), icon: FileCsv, tint: 'bg-[#4fd1a5]/15 text-[#4fd1a5]', run: exportHotspots },
    { id: 'calcsv', label: t('menu.calendarCsv'), icon: Table, tint: 'bg-[#4fd1a5]/15 text-[#4fd1a5]', run: exportCalendar },
    { id: 'report', label: t('menu.report'), icon: FilePdf, tint: 'bg-[#ff8a8a]/15 text-[#ffa3a3]', run: exportReport },
    { id: 'about', label: t('menu.about'), icon: BookOpenText, tint: 'bg-fg/10 text-fg', run: show('about'), active: view === 'about' },
  ]

  return (
    <Popover.Root>
      <Popover.Trigger
        aria-label={t('menu.aria')}
        className="glass grid size-12 place-items-center rounded-[14px] text-fg transition-transform duration-150 hover:text-ember-300 active:scale-95 data-[popup-open]:text-ember-300"
      >
        <DotsNine size={24} weight="bold" />
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Positioner side="bottom" align="end" sideOffset={10} className="z-40">
          <Popover.Popup className="popover-popup glass w-[356px] rounded-[18px] p-2.5 outline-none">
            <div className="rounded-[14px] bg-ink-950/50 p-2 ring-1 ring-line">
              <div className="px-2.5 pt-2 pb-1">
                <Popover.Title className="font-display text-base font-semibold">{t('menu.title')}</Popover.Title>
                <Popover.Description className="mt-0.5 font-mono text-[11px] text-fg-muted">
                  {place ? `${place.label} · ${radiusKm} km · ${dateFrom.slice(0, 4)}–${dateTo.slice(0, 4)}` : t('menu.searchFirst')}
                </Popover.Description>
              </div>
              <div className="mt-1 grid grid-cols-3 gap-1">
                {analyses.map((it) => (
                  <Tile key={it.id} item={it} disabled={!place} />
                ))}
              </div>
            </div>
            <div className="px-3 pt-3 pb-1 text-[11px] uppercase tracking-[0.08em] text-fg-muted">{t('menu.export')}</div>
            <div className="grid grid-cols-4 gap-1">
              {exports.map((it) => (
                <Tile key={it.id} item={it} disabled={it.id !== 'about' && (!place || (it.id === 'calcsv' && !calendar))} />
              ))}
            </div>
          </Popover.Popup>
        </Popover.Positioner>
      </Popover.Portal>
    </Popover.Root>
  )
}

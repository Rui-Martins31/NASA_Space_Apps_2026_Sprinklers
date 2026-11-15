// App-wide state in one place (zustand). Components read what they need
// with useApp((s) => s.something) and call actions like useApp.getState().analyze().
import { create } from 'zustand'
import { toast } from 'sonner'
import { fetchFeature } from './api/client'
import { translate, type Lang } from './i18n'
import type { AnomalyEntry, AreaQuery, CalendarEntry, Hotspot, Place, View } from './types'

const today = new Date().toISOString().slice(0, 10)

/** First day of the satellite record (MODIS Terra). */
export const DATA_START = '2000-11-01'
export const TODAY = today
export const MAX_MAP_POINTS = 5000

export type CalendarScale = 'absolute' | 'relative' | 'anomaly'

/** A sub-period whose hotspots are on the map (e.g. one month clicked in the calendar). */
export interface HotspotWindow {
  from: string
  to: string
  year: number
  month: number
}

function initialLang(): Lang {
  try {
    const saved = localStorage.getItem('firecal-lang')
    if (saved === 'en' || saved === 'pt') return saved
  } catch {
    /* storage not available */
  }
  return navigator.language?.startsWith('pt') ? 'pt' : 'en'
}

interface AppState {
  lang: Lang
  place: Place | null
  radiusKm: number
  dateFrom: string
  dateTo: string

  status: 'idle' | 'loading' | 'ready'
  calendar: CalendarEntry[] | null
  anomalies: AnomalyEntry[] | null
  hotspots: Hotspot[] | null
  hotspotsLoading: boolean
  hotspotWindow: HotspotWindow | null

  view: View | null // which result panel is open
  calendarScale: CalendarScale

  basemap: 'dark' | 'satellite'
  terrain3d: boolean
  replayTime: number | null // ms timestamp shown by the replay, null = show everything
  replayPlaying: boolean

  setLang: (l: Lang) => void
  setPlace: (p: Place | null) => void
  setRadius: (km: number) => void
  setDates: (from: string, to: string) => void
  openView: (v: View | null) => void
  setCalendarScale: (s: CalendarScale) => void
  analyze: () => Promise<void>
  loadHotspots: (window?: HotspotWindow) => Promise<void>
  clearHotspots: () => void
  setBasemap: (b: 'dark' | 'satellite') => void
  setTerrain3d: (on: boolean) => void
  setReplay: (time: number | null, playing?: boolean) => void
}

function request(s: AppState, extra: Partial<AreaQuery> = {}): AreaQuery {
  return {
    lat: s.place!.lat,
    lon: s.place!.lon,
    radiusKm: s.radiusKm,
    dateFrom: s.dateFrom,
    dateTo: s.dateTo,
    ...extra,
  }
}

const noHotspots = { hotspots: null, hotspotWindow: null, replayTime: null, replayPlaying: false }

export const useApp = create<AppState>((set, get) => ({
  lang: initialLang(),
  place: null,
  radiusKm: 50,
  dateFrom: DATA_START,
  dateTo: today,

  status: 'idle',
  calendar: null,
  anomalies: null,
  hotspots: null,
  hotspotsLoading: false,
  hotspotWindow: null,
  view: null,
  calendarScale: 'absolute',

  basemap: 'dark',
  terrain3d: true,
  replayTime: null,
  replayPlaying: false,

  setLang: (lang) => {
    try {
      localStorage.setItem('firecal-lang', lang)
    } catch {
      /* storage not available */
    }
    document.documentElement.lang = lang
    set({ lang })
  },
  // A new place or new parameters make old results stale.
  setPlace: (place) => set({ place, status: 'idle', calendar: null, anomalies: null, view: null, ...noHotspots }),
  setRadius: (radiusKm) => set({ radiusKm, status: 'idle', ...noHotspots }),
  setDates: (dateFrom, dateTo) => set({ dateFrom, dateTo, status: 'idle', ...noHotspots }),
  setBasemap: (basemap) => set({ basemap }),
  setTerrain3d: (terrain3d) => set({ terrain3d }),
  setReplay: (replayTime, playing) => set({ replayTime, replayPlaying: playing ?? (replayTime !== null && get().replayPlaying) }),
  openView: (view) => set({ view }),
  setCalendarScale: (calendarScale) => set({ calendarScale }),
  clearHotspots: () => set(noHotspots),

  analyze: async () => {
    const s = get()
    if (!s.place) return
    set({ status: 'loading' })
    try {
      const res = await fetchFeature('all', request(s))
      set({ status: 'ready', calendar: res.calendar ?? [], anomalies: res.anomalies ?? [], view: get().view ?? 'calendar' })
    } catch (e) {
      set({ status: 'idle' })
      toast.error(translate(get().lang, 'toast.analyzeFailed'), { description: (e as Error).message })
    }
  },

  loadHotspots: async (window) => {
    const s = get()
    if (!s.place) return
    const lang = s.lang
    set({ hotspotsLoading: true, replayTime: null, replayPlaying: false })
    try {
      const range = window ? { dateFrom: window.from, dateTo: window.to } : {}
      const res = await fetchFeature('hotspots', request(s, { maxPoints: MAX_MAP_POINTS, ...range }))
      const hotspots = res.hotspots ?? []
      if (!hotspots.length) {
        set({ hotspotsLoading: false, ...noHotspots })
        toast(translate(lang, 'empty.toastTitle'), { description: translate(lang, 'empty.toastBody') })
        return
      }
      set({ hotspots, hotspotWindow: window ?? null, hotspotsLoading: false })
      toast.success(translate(lang, 'toast.hotspotsShown', { count: hotspots.length.toLocaleString('en') }), {
        description:
          hotspots.length >= MAX_MAP_POINTS ? translate(lang, 'toast.hotspotsSample', { max: MAX_MAP_POINTS.toLocaleString('en') }) : undefined,
      })
    } catch (e) {
      set({ hotspotsLoading: false })
      toast.error(translate(lang, 'toast.hotspotsFailed'), { description: (e as Error).message })
    }
  },
}))

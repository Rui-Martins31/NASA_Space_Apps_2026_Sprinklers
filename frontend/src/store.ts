// App-wide state in one place (zustand). Components read what they need
// with useApp((s) => s.something) and call actions like useApp.getState().analyze().
import { create } from 'zustand'
import { toast } from 'sonner'
import { fetchFeature } from './api/client'
import type { AnomalyEntry, CalendarEntry, Hotspot, Place, View } from './types'

const today = new Date().toISOString().slice(0, 10)

interface AppState {
  place: Place | null
  radiusKm: number
  dateFrom: string
  dateTo: string

  status: 'idle' | 'loading' | 'ready'
  calendar: CalendarEntry[] | null
  anomalies: AnomalyEntry[] | null
  hotspots: Hotspot[] | null
  hotspotsLoading: boolean

  view: View | null // which result panel is open

  setPlace: (p: Place | null) => void
  setRadius: (km: number) => void
  setDates: (from: string, to: string) => void
  openView: (v: View | null) => void
  analyze: () => Promise<void>
  loadHotspots: () => Promise<void>
}

export const DATA_START = '2001-01-01'
export const TODAY = today

function request(s: AppState, extra: object = {}) {
  return {
    lat: s.place!.lat,
    lon: s.place!.lon,
    radius_km: s.radiusKm,
    date_from: s.dateFrom,
    date_to: s.dateTo,
    ...extra,
  }
}

export const useApp = create<AppState>((set, get) => ({
  place: null,
  radiusKm: 50,
  dateFrom: DATA_START,
  dateTo: today,

  status: 'idle',
  calendar: null,
  anomalies: null,
  hotspots: null,
  hotspotsLoading: false,
  view: null,

  // A new place or new parameters make old results stale.
  setPlace: (place) => set({ place, status: 'idle', calendar: null, anomalies: null, hotspots: null, view: null }),
  setRadius: (radiusKm) => set({ radiusKm, status: 'idle', hotspots: null }),
  setDates: (dateFrom, dateTo) => set({ dateFrom, dateTo, status: 'idle', hotspots: null }),
  openView: (view) => set({ view }),

  analyze: async () => {
    const s = get()
    if (!s.place) return
    set({ status: 'loading' })
    try {
      const res = await fetchFeature('all', request(s))
      set({ status: 'ready', calendar: res.calendar ?? [], anomalies: res.anomalies ?? [], view: get().view ?? 'calendar' })
    } catch (e) {
      set({ status: 'idle' })
      toast.error('Could not analyze this area', { description: (e as Error).message })
    }
  },

  loadHotspots: async () => {
    const s = get()
    if (!s.place) return
    set({ hotspotsLoading: true })
    try {
      const res = await fetchFeature('hotspots', request(s, { max_points: 5000 }))
      const hotspots = res.hotspots ?? []
      set({ hotspots, hotspotsLoading: false })
      toast.success(`${hotspots.length.toLocaleString('en')} hotspots on the map`, {
        description: hotspots.length >= 5000 ? 'Showing a sample of 5,000 points.' : undefined,
      })
    } catch (e) {
      set({ hotspotsLoading: false })
      toast.error('Could not load hotspots', { description: (e as Error).message })
    }
  },
}))

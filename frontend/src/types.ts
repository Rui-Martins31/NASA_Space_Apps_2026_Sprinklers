// Shapes agreed with the backend (API contract v0.3).
// If the backend changes a field, change it here first: TypeScript will
// then point at every place in the UI that needs updating.

export type Feature = 'all' | 'calendar' | 'anomalies' | 'hotspots'

export interface ApiRequest {
  lat: number
  lon: number
  radius_km: number
  date_from: string // YYYY-MM-DD
  date_to: string // YYYY-MM-DD
  max_points?: number // only used by /hotspots
}

export interface CalendarEntry {
  year: number
  month: number // 1-12
  count: number
}

export interface AnomalyEntry {
  year: number
  month: number
  count: number
  mean: number
  anomaly: number // count - mean
}

export interface Hotspot {
  lat: number
  lon: number
  date: string
  satellite: string
  confidence: string
  frp: number
}

export interface ApiResponse {
  feature: Feature
  calendar?: CalendarEntry[]
  anomalies?: AnomalyEntry[]
  hotspots?: Hotspot[]
}

export interface Place {
  label: string // "Pedrógão Grande"
  detail: string // "Leiria, Portugal"
  lat: number
  lon: number
}

export type View = 'calendar' | 'anomalies' | 'seasonal' | 'ranking' | 'about'

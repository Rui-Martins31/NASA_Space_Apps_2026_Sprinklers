// Shapes agreed with the backend (spec/api/frontend-backend.md).
// If the backend changes a field, change it here first: TypeScript will
// then point at every place in the UI that needs updating.

export type Feature = 'all' | 'calendar' | 'anomalies' | 'hotspots'

export type ConfidenceClass = 'low' | 'nominal' | 'high'

/** Request body, exactly as the backend expects it. */
export interface ApiRequest {
  feature: Feature // must match the endpoint
  lat: number
  lon: number
  radius: number // km
  date_time_from: string // ISO-8601, read as UTC, e.g. 2020-01-01T00:00:00
  date_time_to: string
  max_points?: number // only used by /hotspots (backend limit: 50 000)
}

/** What the UI asks for; the client turns it into an ApiRequest. */
export interface AreaQuery {
  lat: number
  lon: number
  radiusKm: number
  dateFrom: string // YYYY-MM-DD, inclusive
  dateTo: string // YYYY-MM-DD, inclusive
  maxPoints?: number
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
  mean: number // average of this month over the years in range
  anomaly: 'above' | 'normal' // 'above' when count > mean
}

export interface Hotspot {
  lat: number
  lon: number
  date_time: string // ISO-8601, UTC
  confidence_class: ConfidenceClass
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

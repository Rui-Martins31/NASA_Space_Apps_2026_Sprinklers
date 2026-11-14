import type { ApiRequest, ApiResponse, Feature } from '../types'
import { mockFetch } from './mock'

const USE_MOCK = import.meta.env.VITE_USE_MOCK !== 'false'

// One function for every feature: POST /api/<feature> with the request body.
export async function fetchFeature(feature: Feature, req: ApiRequest): Promise<ApiResponse> {
  if (USE_MOCK) return mockFetch(feature, req)

  const res = await fetch(`/api/${feature}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  })
  if (!res.ok) {
    let message = `Server error (${res.status})`
    try {
      const body = await res.json()
      if (body?.error) message = body.error
    } catch {
      /* body was not JSON */
    }
    throw new Error(message)
  }
  return res.json()
}

export const usingMock = USE_MOCK

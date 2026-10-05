import type { AlertItem, BaselineResponse, HealthStatus, Reading } from './types'

const API_URL = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8000'
export const USER_ID = import.meta.env.VITE_USER_ID ?? 'USER001'

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_URL}${path}`)
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`)
  return response.json() as Promise<T>
}

export const api = {
  latest: () => getJson<Reading>(`/api/v1/users/${USER_ID}/latest`),
  health: () => getJson<HealthStatus>(`/api/v1/users/${USER_ID}/health-status`),
  history: (minutes = 30, limit = 300) =>
    getJson<Reading[]>(`/api/v1/users/${USER_ID}/history?minutes=${minutes}&limit=${limit}`),
  baseline: () => getJson<BaselineResponse>(`/api/v1/users/${USER_ID}/baseline`),
  alerts: () => getJson<AlertItem[]>(`/api/v1/users/${USER_ID}/alerts`),
  resetBaseline: async () => {
    const response = await fetch(`${API_URL}/api/v1/users/${USER_ID}/reset-baseline`, { method: 'POST' })
    if (!response.ok) throw new Error('Failed to reset baseline')
    return response.json()
  },
}

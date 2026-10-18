import type { AlertItem, BaselineResponse, HealthStatus, LiveState, Reading, UserItem } from './types'

const API_URL = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8000'
export const DEFAULT_USER_ID = import.meta.env.VITE_USER_ID ?? 'USER001'

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_URL}${path}`)
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`)
  return response.json() as Promise<T>
}

const user = (id: string) => `/api/v1/users/${encodeURIComponent(id)}`

export const api = {
  users: () => getJson<UserItem[]>('/api/v1/users'),
  latest: (id: string) => getJson<Reading>(`${user(id)}/latest`),
  live: (id: string) => getJson<LiveState>(`${user(id)}/live`),
  health: (id: string) => getJson<HealthStatus>(`${user(id)}/health-status`),
  history: (id: string, minutes = 30, limit = 300) =>
    getJson<Reading[]>(`${user(id)}/history?minutes=${minutes}&limit=${limit}`),
  baseline: (id: string) => getJson<BaselineResponse>(`${user(id)}/baseline`),
  alerts: (id: string) => getJson<AlertItem[]>(`${user(id)}/alerts`),
  resetBaseline: async (id: string) => {
    const response = await fetch(`${API_URL}${user(id)}/reset-baseline`, { method: 'POST' })
    if (!response.ok) throw new Error('Failed to reset baseline')
    return response.json()
  },
}

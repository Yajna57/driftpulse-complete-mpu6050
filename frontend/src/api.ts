import type { AlertItem, BaselineResponse, HealthStatus, LiveState, Reading, TelegramSettings, UserItem } from './types'

const API_URL = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8000'
export const DEFAULT_USER_ID = import.meta.env.VITE_USER_ID ?? 'USER001'

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_URL}${path}`)
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`)
  return response.json() as Promise<T>
}

async function sendJson<T>(method: string, path: string, body: unknown): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`
    try {
      const data = await response.json()
      if (typeof data.detail === 'string') detail = data.detail
      else if (Array.isArray(data.detail)) detail = data.detail.map((d: { msg: string }) => d.msg.replace(/^Value error, /, '')).join('; ')
    } catch { /* keep status text */ }
    throw new Error(detail)
  }
  return response.json() as Promise<T>
}

const user = (id: string) => `/api/v1/users/${encodeURIComponent(id)}`
const TELEGRAM = '/api/v1/settings/telegram'

export const api = {
  users: () => getJson<UserItem[]>('/api/v1/users'),
  latest: (id: string) => getJson<Reading>(`${user(id)}/latest`),
  live: (id: string) => getJson<LiveState>(`${user(id)}/live`),
  health: (id: string) => getJson<HealthStatus>(`${user(id)}/health-status`),
  history: (id: string, minutes = 30, limit = 300) =>
    getJson<Reading[]>(`${user(id)}/history?minutes=${minutes}&limit=${limit}`),
  baseline: (id: string) => getJson<BaselineResponse>(`${user(id)}/baseline`),
  alerts: (id: string) => getJson<AlertItem[]>(`${user(id)}/alerts`),
  telegramSettings: (userId: string) => getJson<TelegramSettings>(`${TELEGRAM}?user_id=${encodeURIComponent(userId)}`),
  saveTelegramGeneral: (body: { chat_id: string; enabled: boolean; bot_token: string | null }) =>
    sendJson<TelegramSettings>('PUT', `${TELEGRAM}/general`, body),
  saveTelegramUser: (userId: string, body: { chat_id: string; enabled: boolean }) =>
    sendJson<TelegramSettings>('PUT', `${TELEGRAM}/users/${encodeURIComponent(userId)}`, body),
  telegramTest: (userId: string | null) => sendJson<{ sent: boolean }>('POST', `${TELEGRAM}/test`, { user_id: userId }),
  resetBaseline: async (id: string) => {
    const response = await fetch(`${API_URL}${user(id)}/reset-baseline`, { method: 'POST' })
    if (!response.ok) throw new Error('Failed to reset baseline')
    return response.json()
  },
}

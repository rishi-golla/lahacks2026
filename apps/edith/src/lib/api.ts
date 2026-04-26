export type ActiveUser = {
  display_name: string
  email: string
  google_subject: string
  granted_scopes: string[]
  connected_at: string
  status: string
}

export type GoogleStatus = {
  connected: boolean
  active_user: ActiveUser | null
}

export type HistoryEvent = {
  id: string
  timestamp: string
  intent: string
  actor_email: string | null
  status: string
  summary: string
  details?: Record<string, string> | null
}

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, '') ??
  'http://127.0.0.1:8000'

async function parseJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    throw new Error(`Request failed with status ${response.status}`)
  }
  return response.json() as Promise<T>
}

export function getGoogleConnectUrl(): string {
  return `${apiBaseUrl}/google/connect/start`
}

export async function fetchGoogleStatus(): Promise<GoogleStatus> {
  const response = await fetch(`${apiBaseUrl}/google/status`, {
    credentials: 'include',
  })
  return parseJson<GoogleStatus>(response)
}

export async function fetchGoogleHistory(): Promise<{ events: HistoryEvent[] }> {
  const response = await fetch(`${apiBaseUrl}/google/history`, {
    credentials: 'include',
  })
  return parseJson<{ events: HistoryEvent[] }>(response)
}

export async function disconnectGoogle(): Promise<void> {
  const response = await fetch(`${apiBaseUrl}/google/disconnect`, {
    method: 'POST',
    credentials: 'include',
  })
  await parseJson(response)
}

export interface HttpError extends Error {
  status: number
  payload?: unknown
}

const DEFAULT_TIMEOUT_MS = 30_000

export async function getJson<T>(input: RequestInfo, init?: RequestInit): Promise<T> {
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), DEFAULT_TIMEOUT_MS)

  try {
    const response = await fetch(input, {
      ...init,
      signal: init?.signal ?? controller.signal,
    })
    if (!response.ok) {
      const error: HttpError = new Error(`HTTP ${response.status}`) as HttpError
      error.status = response.status
      try {
        error.payload = await response.json()
      } catch {
        error.payload = await response.text()
      }
      throw error
    }
    return (await response.json()) as T
  } finally {
    clearTimeout(timeoutId)
  }
}

export async function postJson<T>(input: RequestInfo, body: unknown): Promise<T> {
  return getJson<T>(input, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  })
}

export async function patchJson<T>(input: RequestInfo, body: unknown): Promise<T> {
  return getJson<T>(input, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  })
}

export async function postForm<T>(input: RequestInfo, formData: FormData): Promise<T> {
  return getJson<T>(input, {
    method: 'POST',
    body: formData,
  })
}

export function extractErrorMessage(error: unknown): string {
  if (error && typeof error === 'object' && 'payload' in error) {
    const httpErr = error as HttpError
    const payload = httpErr.payload
    if (payload && typeof payload === 'object' && 'detail' in payload) {
      return String((payload as { detail: unknown }).detail)
    }
    if (typeof payload === 'string') return payload
    return httpErr.message
  }
  if (error instanceof Error) return error.message
  return String(error)
}

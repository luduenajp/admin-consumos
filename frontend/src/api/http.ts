export interface HttpError extends Error {
  status: number
  payload?: unknown
}

export async function getJson<T>(input: RequestInfo, init?: RequestInit): Promise<T> {
  const response = await fetch(input, init)
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

export async function postForm<T>(input: RequestInfo, formData: FormData): Promise<T> {
  return getJson<T>(input, {
    method: 'POST',
    body: formData,
  })
}

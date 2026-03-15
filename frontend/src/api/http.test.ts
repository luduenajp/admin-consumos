import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { extractErrorMessage, getJson, postJson, type HttpError } from './http'

describe('extractErrorMessage', () => {
  it('extracts detail from payload object', () => {
    const error = new Error('HTTP 400') as HttpError
    error.status = 400
    error.payload = { detail: 'Validation failed' }
    expect(extractErrorMessage(error)).toBe('Validation failed')
  })

  it('returns payload string directly', () => {
    const error = new Error('HTTP 500') as HttpError
    error.status = 500
    error.payload = 'Internal server error'
    expect(extractErrorMessage(error)).toBe('Internal server error')
  })

  it('falls back to error message when payload has no detail', () => {
    const error = new Error('HTTP 503') as HttpError
    error.status = 503
    error.payload = { some: 'other' }
    expect(extractErrorMessage(error)).toBe('HTTP 503')
  })

  it('handles plain Error object', () => {
    const error = new Error('Network error')
    expect(extractErrorMessage(error)).toBe('Network error')
  })

  it('handles string error', () => {
    expect(extractErrorMessage('something went wrong')).toBe('something went wrong')
  })

  it('handles null/undefined', () => {
    expect(extractErrorMessage(null)).toBe('null')
    expect(extractErrorMessage(undefined)).toBe('undefined')
  })
})

describe('getJson', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('returns parsed JSON on success', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ id: 1, name: 'Alice' }),
    })
    vi.stubGlobal('fetch', mockFetch)

    const result = await getJson<{ id: number; name: string }>('/api/people')
    expect(result).toEqual({ id: 1, name: 'Alice' })
  })

  it('throws HttpError on non-ok response', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
      json: async () => ({ detail: 'Not found' }),
    })
    vi.stubGlobal('fetch', mockFetch)

    await expect(getJson('/api/people/999')).rejects.toMatchObject({
      status: 404,
      payload: { detail: 'Not found' },
    })
  })
})

describe('postJson', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('sends POST with Content-Type and JSON body', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ id: 1 }),
    })
    vi.stubGlobal('fetch', mockFetch)

    await postJson('/api/people', { name: 'Bob' })

    expect(mockFetch).toHaveBeenCalledOnce()
    const [, init] = mockFetch.mock.calls[0] as [string, RequestInit]
    expect(init.method).toBe('POST')
    expect((init.headers as Record<string, string>)['Content-Type']).toBe('application/json')
    expect(init.body).toBe(JSON.stringify({ name: 'Bob' }))
  })
})

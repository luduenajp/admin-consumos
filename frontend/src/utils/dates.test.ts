import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { getCurrentYearMonth, getRelativeMonth } from './dates'

describe('getCurrentYearMonth', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('returns YYYY-MM for January', () => {
    vi.setSystemTime(new Date('2025-01-15T12:00:00Z'))
    expect(getCurrentYearMonth()).toBe('2025-01')
  })

  it('returns YYYY-MM for December', () => {
    vi.setSystemTime(new Date('2025-12-01T12:00:00Z'))
    expect(getCurrentYearMonth()).toBe('2025-12')
  })

  it('pads single-digit month', () => {
    vi.setSystemTime(new Date('2025-03-10T00:00:00Z'))
    expect(getCurrentYearMonth()).toMatch(/^\d{4}-0\d$/)
  })
})

describe('getRelativeMonth', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2025-06-15T12:00:00Z'))
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('offset 0 returns current month', () => {
    expect(getRelativeMonth(0)).toBe('2025-06')
  })

  it('offset +1 returns next month', () => {
    expect(getRelativeMonth(1)).toBe('2025-07')
  })

  it('offset -1 returns previous month', () => {
    expect(getRelativeMonth(-1)).toBe('2025-05')
  })

  it('handles year rollover forward', () => {
    vi.setSystemTime(new Date('2025-11-15T12:00:00Z'))
    expect(getRelativeMonth(2)).toBe('2026-01')
  })

  it('handles year rollover backward', () => {
    vi.setSystemTime(new Date('2025-02-15T12:00:00Z'))
    expect(getRelativeMonth(-2)).toBe('2024-12')
  })
})

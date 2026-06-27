import { describe, it, expect } from 'vitest'
import { getServiceStatus } from './services'

describe('getServiceStatus', () => {
  const today = new Date('2026-06-27')

  it('returns paid when paid_date is set', () => {
    expect(getServiceStatus({ paid_date: '2026-06-18' } as any, new Date('2026-06-20'), today)).toBe('paid')
  })

  it('returns no_date when no due_date and not paid', () => {
    expect(getServiceStatus(null, null, today)).toBe('no_date')
  })

  it('returns overdue when due_date is before today and not paid', () => {
    expect(getServiceStatus(null, new Date('2026-06-26'), today)).toBe('overdue')
  })

  it('returns due_soon when due_date equals today (yellow)', () => {
    expect(getServiceStatus(null, new Date('2026-06-27'), today)).toBe('due_soon')
  })

  it('returns due_soon when due_date is 3 days from today', () => {
    expect(getServiceStatus(null, new Date('2026-06-30'), today)).toBe('due_soon')
  })

  it('returns no_date (grey) when due_date is more than 3 days away', () => {
    expect(getServiceStatus(null, new Date('2026-07-10'), today)).toBe('no_date')
  })

  it('paid takes priority over overdue due_date', () => {
    expect(getServiceStatus({ paid_date: '2026-06-01' } as any, new Date('2026-06-01'), today)).toBe('paid')
  })
})

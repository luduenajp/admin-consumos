import { describe, it, expect } from 'vitest'
import { formatCurrency, formatSignedCurrency } from './format'

describe('formatCurrency', () => {
  it('formats positive amount', () => {
    const result = formatCurrency(1000)
    expect(result).toContain('1')
    expect(result).toContain('000')
  })

  it('formats zero', () => {
    const result = formatCurrency(0)
    expect(result).toContain('0')
  })

  it('formats large amount', () => {
    const result = formatCurrency(1234567.89)
    expect(result).toBeTruthy()
    expect(typeof result).toBe('string')
  })

  it('includes ARS currency indicator', () => {
    const result = formatCurrency(500)
    // es-AR locale formats with $ symbol or ARS code
    expect(result).toMatch(/\$|ARS/)
  })
})

describe('formatSignedCurrency', () => {
  it('positive amount has + prefix', () => {
    const result = formatSignedCurrency(1000)
    expect(result.startsWith('+')).toBe(true)
  })

  it('negative amount has - prefix', () => {
    const result = formatSignedCurrency(-1000)
    expect(result.startsWith('-')).toBe(true)
  })

  it('zero has + prefix', () => {
    const result = formatSignedCurrency(0)
    expect(result.startsWith('+')).toBe(true)
  })

  it('returns absolute value for negative', () => {
    const neg = formatSignedCurrency(-500)
    const pos = formatSignedCurrency(500)
    // Both should have same numeric content
    expect(neg.slice(1)).toBe(pos.slice(1))
  })
})

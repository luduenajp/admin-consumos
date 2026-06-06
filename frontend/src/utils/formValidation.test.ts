import { describe, it, expect } from 'vitest'
import { requiredField, positiveNumber } from './formValidation'

describe('requiredField', () => {
  it('returns empty string for non-empty value', () => {
    expect(requiredField('hello')).toBe('')
  })

  it('returns error for empty string', () => {
    expect(requiredField('')).toBe('Requerido')
  })

  it('returns error for whitespace-only string', () => {
    expect(requiredField('   ')).toBe('Requerido')
  })
})

describe('positiveNumber', () => {
  it('returns empty string for valid positive number', () => {
    expect(positiveNumber('100')).toBe('')
    expect(positiveNumber('0.01')).toBe('')
    expect(positiveNumber('1234.56')).toBe('')
  })

  it('returns error for empty string', () => {
    expect(positiveNumber('')).toBe('Ingresá un monto válido')
  })

  it('returns error for whitespace', () => {
    expect(positiveNumber('   ')).toBe('Ingresá un monto válido')
  })

  it('returns error for zero', () => {
    expect(positiveNumber('0')).toBe('El monto debe ser mayor a 0')
  })

  it('returns error for negative number', () => {
    expect(positiveNumber('-5')).toBe('El monto debe ser mayor a 0')
  })

  it('returns error for non-numeric string', () => {
    expect(positiveNumber('abc')).toBe('El monto debe ser mayor a 0')
  })
})

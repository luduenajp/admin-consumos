export function requiredField(value: string): string {
  return value.trim() ? '' : 'Requerido'
}

export function positiveNumber(value: string): string {
  if (!value.trim()) return 'Ingresá un monto válido'
  const n = parseFloat(value)
  if (isNaN(n) || n <= 0) return 'El monto debe ser mayor a 0'
  return ''
}

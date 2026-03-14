export function formatCurrency(amount: number): string {
  return new Intl.NumberFormat('es-AR', {
    style: 'currency',
    currency: 'ARS',
  }).format(amount)
}

export function formatSignedCurrency(amount: number): string {
  const formatted = formatCurrency(Math.abs(amount))
  return amount >= 0 ? `+${formatted}` : `-${formatted}`
}

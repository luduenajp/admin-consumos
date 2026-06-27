import type { ServicePaymentRead } from '../api/types'

export type ServiceStatus = 'paid' | 'due_soon' | 'overdue' | 'no_date'

export function getServiceStatus(
  payment: Pick<ServicePaymentRead, 'paid_date'> | null,
  dueDate: Date | null,
  today: Date,
): ServiceStatus {
  if (payment?.paid_date) return 'paid'
  if (!dueDate) return 'no_date'

  const todayMs = today.getTime()
  const dueDateMs = dueDate.getTime()
  const threeDaysMs = 3 * 24 * 60 * 60 * 1000

  if (dueDateMs < todayMs) return 'overdue'
  if (dueDateMs <= todayMs + threeDaysMs) return 'due_soon'
  return 'no_date'
}

export const STATUS_COLORS: Record<ServiceStatus, string> = {
  paid: '#22c55e',     // green
  due_soon: '#f59e0b', // amber
  overdue: '#ef4444',  // red
  no_date: '#9ca3af',  // grey
}

export const STATUS_LABELS: Record<ServiceStatus, string> = {
  paid: 'Pagado',
  due_soon: 'Por vencer',
  overdue: 'Vencido',
  no_date: 'Sin fecha',
}

import React, { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
    fetchCards,
    fetchPeople,
    fetchDebtors,
    fetchCategories,
    createPurchase,
    fetchSuggestMonth,
} from '../api/endpoints'
import { extractErrorMessage } from '../api/http'
import type { CurrencyCode, PaymentMethod, PurchaseCreate, Category, SuggestMonthResponse } from '../api/types'
import { getRelativeMonth } from '../utils/dates'
import { requiredField, positiveNumber } from '../utils/formValidation'

interface PurchaseFormProps {
    onSuccess?: () => void
    onCancel?: () => void
}

export function PurchaseForm({ onSuccess, onCancel }: PurchaseFormProps) {
    const queryClient = useQueryClient()

    const [formData, setFormData] = useState({
        purchase_date: new Date().toISOString().split('T')[0],
        description: '',
        payment_method: 'cash' as PaymentMethod,
        amount_original: '',
        currency: 'ARS' as CurrencyCode,
        card_id: '',
        installments_total: '1',
        first_installment_month: getRelativeMonth(0),
        owner_person_id: '',
        debtor_id: '',
        beneficiary_person_id: '',
        notes: '',
        is_common: false,
        category: '',
    })

    const [amountInputMode, setAmountInputMode] = useState<'total' | 'installment'>('total')
    const [amountInputValue, setAmountInputValue] = useState('')
    const [errors, setErrors] = useState<Record<string, string>>({})

    const { data: people = [] } = useQuery({ queryKey: ['people'], queryFn: fetchPeople })
    const { data: cards = [] } = useQuery({ queryKey: ['cards'], queryFn: fetchCards })
    const { data: debtors = [] } = useQuery({ queryKey: ['debtors'], queryFn: fetchDebtors })
    const { data: categories = [] } = useQuery<Category[]>({ queryKey: ['categories'], queryFn: fetchCategories })

    const suggestQuery = useQuery<SuggestMonthResponse>({
        queryKey: ['suggest-month', formData.card_id, formData.purchase_date],
        queryFn: () => fetchSuggestMonth(Number(formData.card_id), formData.purchase_date),
        enabled: formData.payment_method === 'card' && !!formData.card_id,
        staleTime: 0,
    })

    useEffect(() => {
        if (suggestQuery.data) {
            setFormData(prev => ({ ...prev, first_installment_month: suggestQuery.data!.year_month }))
        }
    }, [suggestQuery.data?.year_month])

    // Update default first_installment_month when payment_method changes
    useEffect(() => {
        if (formData.payment_method === 'card') {
            setFormData(prev => ({
                ...prev,
                first_installment_month: getRelativeMonth(1)
            }))
        } else {
            setFormData(prev => ({
                ...prev,
                first_installment_month: getRelativeMonth(0),
                card_id: '',
                installments_total: '1'
            }))
            setAmountInputMode('total')
        }
    }, [formData.payment_method])

    // Sync amount_original when input or mode changes
    useEffect(() => {
        const val = parseFloat(amountInputValue) || 0
        if (amountInputMode === 'total') {
            setFormData(prev => ({ ...prev, amount_original: amountInputValue }))
        } else {
            const inst = parseInt(formData.installments_total) || 1
            setFormData(prev => ({ ...prev, amount_original: (val * inst).toFixed(2) }))
        }
    }, [amountInputValue, amountInputMode, formData.installments_total])

    function validateField(field: string): string {
        switch (field) {
            case 'description': return requiredField(formData.description)
            case 'amount_original': return positiveNumber(formData.amount_original)
            case 'owner_person_id': return formData.owner_person_id ? '' : 'Seleccioná una persona'
            case 'card_id':
                return formData.payment_method === 'card' && !formData.card_id
                    ? 'Seleccioná una tarjeta'
                    : ''
            default: return ''
        }
    }

    function handleBlur(field: string) {
        setErrors(e => ({ ...e, [field]: validateField(field) }))
    }

    function validateAll(): Record<string, string> {
        return {
            description: validateField('description'),
            amount_original: validateField('amount_original'),
            owner_person_id: validateField('owner_person_id'),
            card_id: validateField('card_id'),
        }
    }

    const createMutation = useMutation({
        mutationFn: (payload: PurchaseCreate) => createPurchase(payload),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['purchases'] })
            queryClient.invalidateQueries({ queryKey: ['reports'] })
            queryClient.invalidateQueries({ queryKey: ['monthly-balance'] })
            queryClient.invalidateQueries({ queryKey: ['transfer-calculation'] })
            setErrors({})
            onSuccess?.()
        },
        onError: (err) => {
            alert(`Error al crear compra: ${extractErrorMessage(err)}`)
        },
    })

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault()
        const allErrors = validateAll()
        setErrors(allErrors)
        if (Object.values(allErrors).some(Boolean)) return

        const payload: PurchaseCreate = {
            purchase_date: formData.purchase_date,
            description: formData.description,
            payment_method: formData.payment_method,
            amount_original: parseFloat(formData.amount_original),
            currency: formData.currency,
            owner_person_id: Number(formData.owner_person_id),
            category: formData.category || null,
            notes: formData.notes || null,
            is_common: formData.is_common,
            debtor_id: formData.debtor_id ? Number(formData.debtor_id) : null,
            beneficiary_person_id: (!formData.is_common && formData.beneficiary_person_id) ? Number(formData.beneficiary_person_id) : null,
            card_id: formData.card_id ? Number(formData.card_id) : null,
            installments_total: parseInt(formData.installments_total) || 1,
            first_installment_month: formData.first_installment_month,
        }

        createMutation.mutate(payload)
    }

    const installmentAmount = (parseFloat(formData.amount_original) || 0) / (parseInt(formData.installments_total) || 1)

    return (
        <form onSubmit={handleSubmit} className="purchase-form">
            <div className="purchase-form-grid">
                <div className="formRow">
                    <label className="label">Medio de pago</label>
                    <select
                        className="input"
                        value={formData.payment_method}
                        onChange={(e) => setFormData({ ...formData, payment_method: e.target.value as PaymentMethod })}
                    >
                        <option value="cash">Efectivo</option>
                        <option value="transfer">Transferencia</option>
                        <option value="card">Tarjeta</option>
                    </select>
                </div>

                <div className="formRow">
                    <label className="label">Tarjeta</label>
                    <select
                        className="input"
                        disabled={formData.payment_method !== 'card'}
                        value={formData.card_id}
                        onChange={(e) => setFormData({ ...formData, card_id: e.target.value })}
                        onBlur={() => handleBlur('card_id')}
                        style={{ opacity: formData.payment_method === 'card' ? 1 : 0.5 }}
                    >
                        <option value="">{formData.payment_method === 'card' ? 'Seleccionar...' : 'N/A'}</option>
                        {formData.payment_method === 'card' && cards.map((c) => (
                            <option key={c.id} value={c.id}>
                                {c.name} ({c.provider})
                            </option>
                        ))}
                    </select>
                    {errors.card_id && <span className="fieldError">{errors.card_id}</span>}
                </div>

                <div className="formRow">
                    <label className="label">Pagado por</label>
                    <select
                        className="input"
                        value={formData.owner_person_id}
                        onChange={(e) => setFormData({ ...formData, owner_person_id: e.target.value })}
                        onBlur={() => handleBlur('owner_person_id')}
                    >
                        <option value="">Seleccionar...</option>
                        {people.map((p) => (
                            <option key={p.id} value={p.id}>
                                {p.name}
                            </option>
                        ))}
                    </select>
                    {errors.owner_person_id && <span className="fieldError">{errors.owner_person_id}</span>}
                </div>

                <div className="formRow">
                    <label className="label">Fecha compra</label>
                    <input
                        type="date"
                        className="input"
                        value={formData.purchase_date}
                        onChange={(e) => setFormData({ ...formData, purchase_date: e.target.value })}
                    />
                </div>

                <div className="formRow span-2">
                    <label className="label">Descripción</label>
                    <input
                        type="text"
                        className="input"
                        placeholder="Ej: Almuerzo, Supermercado..."
                        value={formData.description}
                        onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                        onBlur={() => handleBlur('description')}
                    />
                    {errors.description && <span className="fieldError">{errors.description}</span>}
                </div>

                <div className="formRow">
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                        <label className="label" style={{ margin: 0 }}>Monto</label>
                        {formData.payment_method === 'card' && (
                            <div style={{ display: 'flex', gap: '4px', background: '#f0f0f0', padding: '2px', borderRadius: '4px' }}>
                                <button
                                    type="button"
                                    onClick={() => setAmountInputMode('total')}
                                    style={{
                                        fontSize: '11px',
                                        padding: '2px 6px',
                                        border: 'none',
                                        borderRadius: '3px',
                                        cursor: 'pointer',
                                        background: amountInputMode === 'total' ? 'white' : 'transparent',
                                        boxShadow: amountInputMode === 'total' ? '0 1px 2px rgba(0,0,0,0.1)' : 'none'
                                    }}
                                >
                                    Total
                                </button>
                                <button
                                    type="button"
                                    onClick={() => setAmountInputMode('installment')}
                                    style={{
                                        fontSize: '11px',
                                        padding: '2px 6px',
                                        border: 'none',
                                        borderRadius: '3px',
                                        cursor: 'pointer',
                                        background: amountInputMode === 'installment' ? 'white' : 'transparent',
                                        boxShadow: amountInputMode === 'installment' ? '0 1px 2px rgba(0,0,0,0.1)' : 'none'
                                    }}
                                >
                                    Por Cuota
                                </button>
                            </div>
                        )}
                    </div>
                    <div style={{ display: 'flex', gap: '8px' }}>
                        <input
                            type="number"
                            step="0.01"
                            className="input"
                            style={{ flex: 1, minWidth: '0' }}
                            placeholder="0.00"
                            value={amountInputValue}
                            onChange={(e) => setAmountInputValue(e.target.value)}
                            onBlur={() => handleBlur('amount_original')}
                        />
                        <select
                            className="input"
                            style={{ width: 'auto', minWidth: '85px' }}
                            value={formData.currency}
                            onChange={(e) => setFormData({ ...formData, currency: e.target.value as CurrencyCode })}
                        >
                            <option value="ARS">ARS</option>
                            <option value="USD">USD</option>
                        </select>
                    </div>
                    {amountInputMode === 'installment' && (
                        <div className="hint" style={{ marginTop: '4px', color: 'var(--color-primary)', fontWeight: 'bold' }}>
                            Monto total: ${parseFloat(formData.amount_original).toLocaleString('es-AR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                        </div>
                    )}
                    {errors.amount_original && <span className="fieldError">{errors.amount_original}</span>}
                </div>

                <div className="formRow">
                    <label className="label">Categoría</label>
                    <select
                        className="input"
                        value={formData.category}
                        onChange={(e) => setFormData({ ...formData, category: e.target.value })}
                    >
                        <option value="">Sin categoría</option>
                        {categories.map((c) => (
                            <option key={c.id} value={c.name}>
                                {c.name}
                            </option>
                        ))}
                    </select>
                </div>

                <div className="formRow">
                    <label className="label">Cuotas</label>
                    <input
                        type="number"
                        min="1"
                        className="input"
                        disabled={formData.payment_method !== 'card'}
                        value={formData.installments_total}
                        onChange={(e) => setFormData({ ...formData, installments_total: e.target.value })}
                        style={{ opacity: formData.payment_method === 'card' ? 1 : 0.5 }}
                    />
                    {formData.payment_method === 'card' && parseInt(formData.installments_total) > 1 && (
                        <div className="hint" style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                            {formData.installments_total} cuotas de ${installmentAmount.toLocaleString('es-AR', { maximumFractionDigits: 2 })}
                        </div>
                    )}
                </div>

                <div className="formRow">
                    <label className="label">Mes primer cuota</label>
                    <input
                        type="month"
                        className="input"
                        disabled={formData.payment_method !== 'card'}
                        value={formData.first_installment_month}
                        onChange={(e) => setFormData({ ...formData, first_installment_month: e.target.value })}
                        style={{ opacity: formData.payment_method === 'card' ? 1 : 0.5 }}
                    />
                    {formData.payment_method === 'card' && formData.card_id && (
                        <div className="hint">
                            {suggestQuery.isLoading
                                ? 'Calculando...'
                                : suggestQuery.data?.fallback
                                    ? 'Sin datos de cierre — asumiendo mes siguiente'
                                    : `Cierre ${suggestQuery.data?.closing_date} → entra en ${suggestQuery.data?.year_month}`
                            }
                        </div>
                    )}
                </div>

                <div className="formRow">
                    <label className="label">Deudor (Opcional)</label>
                    <select
                        className="input"
                        value={formData.debtor_id}
                        onChange={(e) => setFormData({ ...formData, debtor_id: e.target.value })}
                    >
                        <option value="">Ninguno</option>
                        {debtors.map((d) => (
                            <option key={d.id} value={d.id}>
                                {d.name}
                            </option>
                        ))}
                    </select>
                </div>

                <div className="formRow">
                    <label className="label">Beneficiario (Opcional)</label>
                    <select
                        className="input"
                        disabled={!!formData.is_common || !!formData.debtor_id}
                        value={formData.beneficiary_person_id}
                        onChange={(e) => setFormData({ ...formData, beneficiary_person_id: e.target.value })}
                        style={{ opacity: (!formData.is_common && !formData.debtor_id) ? 1 : 0.5 }}
                    >
                        <option value="">(Quien pagó)</option>
                        {people.map((p) => (
                            <option key={p.id} value={p.id}>
                                {p.name}
                            </option>
                        ))}
                    </select>
                </div>

                <div className="formRow span-4">
                    <label className="label">Notas</label>
                    <input
                        type="text"
                        className="input"
                        placeholder="Opcional..."
                        value={formData.notes}
                        onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
                    />
                </div>

                <div className="formRow span-4" style={{ display: 'flex', flexDirection: 'row', alignItems: 'center', gap: '8px', marginTop: '4px' }}>
                    <input
                        type="checkbox"
                        id="is_common"
                        style={{ width: '18px', height: '18px', flexShrink: 0 }}
                        checked={formData.is_common}
                        onChange={(e) => setFormData({ ...formData, is_common: e.target.checked })}
                    />
                    <label htmlFor="is_common" className="label" style={{ margin: 0 }}>Es un gasto común (se reparte 50/50)</label>
                </div>
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px', marginTop: '24px' }}>
                {onCancel && (
                    <button type="button" className="button ghost" onClick={onCancel}>
                        Cancelar
                    </button>
                )}
                <button
                    type="submit"
                    className="button"
                    style={{ background: 'var(--color-primary)', color: 'white' }}
                    disabled={createMutation.isPending}
                >
                    {createMutation.isPending ? 'Guardando...' : 'Guardar compra'}
                </button>
            </div>
        </form>
    )
}

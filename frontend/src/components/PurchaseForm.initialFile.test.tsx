import { describe, it, expect, vi, beforeEach } from 'vitest'
import '@testing-library/jest-dom'
import { render, screen, waitFor } from '@testing-library/react'
import { StrictMode } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { PurchaseForm } from './PurchaseForm'
import { uploadComprobante } from '../api/endpoints'
import type { ComprobanteExtraction } from '../api/types'

vi.mock('../api/endpoints', () => ({
    fetchCards: vi.fn().mockResolvedValue([]),
    fetchPeople: vi.fn().mockResolvedValue([]),
    fetchDebtors: vi.fn().mockResolvedValue([]),
    fetchCategories: vi.fn().mockResolvedValue([]),
    fetchSuggestMonth: vi.fn().mockResolvedValue({ suggested_month: '2026-06' }),
    createPurchase: vi.fn(),
    createBeneficiary: vi.fn(),
    uploadComprobante: vi.fn(),
}))

const extraction: ComprobanteExtraction = {
    amount: 15000.5,
    date: '2026-06-10',
    currency: 'ARS',
    description: 'Transferencia',
    matched_beneficiary: { id: 1, name: 'Juan Perez', confidence: 'exact' },
    raw_extracted: { nombre: 'Juan Perez', cbu: null, cuit: null, alias: null },
}

function renderForm(initialFile?: File) {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    return render(
        <StrictMode>
            <QueryClientProvider client={queryClient}>
                <PurchaseForm initialValues={{ payment_method: 'transfer' }} initialFile={initialFile} />
            </QueryClientProvider>
        </StrictMode>
    )
}

describe('PurchaseForm initialFile', () => {
    beforeEach(() => {
        vi.mocked(uploadComprobante).mockResolvedValue(extraction)
        vi.mocked(uploadComprobante).mockClear()
    })

    it('parses the injected file exactly once (StrictMode guard)', async () => {
        const file = new File(['img'], 'comprobante.png', { type: 'image/png' })
        renderForm(file)

        await waitFor(() => expect(uploadComprobante).toHaveBeenCalledTimes(1))
        expect(uploadComprobante).toHaveBeenCalledWith(file)
        // StrictMode re-runs effects: a second call would double-bill Claude Vision
        await new Promise((r) => setTimeout(r, 50))
        expect(uploadComprobante).toHaveBeenCalledTimes(1)
    })

    it('autofills amount, date and description from the extraction', async () => {
        renderForm(new File(['img'], 'comprobante.png', { type: 'image/png' }))

        await waitFor(() => {
            expect(screen.getByDisplayValue('15000.5')).toBeInTheDocument()
            expect(screen.getByDisplayValue('2026-06-10')).toBeInTheDocument()
            expect(screen.getByDisplayValue('Juan Perez')).toBeInTheDocument()
        })
    })

    it('does not call the parse endpoint when no initialFile is given', async () => {
        renderForm()
        await new Promise((r) => setTimeout(r, 50))
        expect(uploadComprobante).not.toHaveBeenCalled()
    })
})

from __future__ import annotations

from datetime import date
from typing import Generic, Optional, TypeVar

from pydantic import BaseModel, Field, model_validator

T = TypeVar("T")

from app.models import CurrencyCode, PaymentMethod, ShareType


class PersonCreate(BaseModel):
    name: str


class PersonRead(BaseModel):
    id: int
    name: str


class CardCreate(BaseModel):
    name: str
    provider: str
    owner_person_id: int
    last4: Optional[str] = None


class CardRead(BaseModel):
    id: int
    name: str
    provider: str
    owner_person_id: int
    last4: Optional[str] = None


class PurchasePayerCreate(BaseModel):
    person_id: int
    share_type: ShareType
    share_value: float = Field(gt=0)


class PurchasePayerRead(BaseModel):
    person_id: int
    person_name: str
    share_type: ShareType
    share_value: float


class PurchaseCreate(BaseModel):
    card_id: Optional[int] = None
    payment_method: PaymentMethod = PaymentMethod.CARD
    purchase_date: date
    description: str

    currency: CurrencyCode
    amount_original: float

    installments_total: int = Field(default=1, ge=1)
    installment_amount_original: Optional[float] = None
    first_installment_month: Optional[str] = Field(default=None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$")

    owner_person_id: Optional[int] = None
    category: Optional[str] = None
    notes: Optional[str] = None

    is_refund: bool = False
    is_common: bool = False
    debtor_id: Optional[int] = None
    beneficiary_person_id: Optional[int] = None

    payers: Optional[list[PurchasePayerCreate]] = None

    @model_validator(mode="after")
    def _validate_card_presence(self) -> "PurchaseCreate":
        if self.payment_method == PaymentMethod.CARD and self.card_id is None:
            raise ValueError("card_id is required for CARD payment method")
        return self

    @model_validator(mode="after")
    def _validate_payer_shares(self) -> "PurchaseCreate":
        if not self.payers:
            return self
        percent_payers = [p for p in self.payers if p.share_type == ShareType.PERCENT]
        if percent_payers and len(percent_payers) == len(self.payers):
            total = sum(p.share_value for p in percent_payers)
            if abs(total - 100.0) > 0.01:
                raise ValueError(f"PERCENT payer shares must sum to 100, got {total}")
        return self


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    pages: int


class PurchaseRead(BaseModel):
    id: int
    card_id: Optional[int]
    payment_method: PaymentMethod
    purchase_date: date
    description: str
    currency: CurrencyCode
    amount_original: float
    installments_total: int
    installment_amount_original: Optional[float]
    first_installment_month: Optional[str]
    owner_person_id: Optional[int]
    category: Optional[str]
    notes: Optional[str]
    is_refund: bool
    is_common: bool
    debtor_id: Optional[int]
    beneficiary_person_id: Optional[int]
    debt_settled: bool
    import_batch_id: Optional[int] = None
    payers: list[PurchasePayerRead] = Field(default_factory=list)


class ImportBatchRead(BaseModel):
    id: int
    imported_at: str
    provider: str
    source_file: str
    card_id: Optional[int] = None
    card_name: Optional[str] = None
    statement_year_month: Optional[str] = None
    purchases_created: int
    purchases_skipped: int
    purchases_parsed: int


class ReportMonthlyRow(BaseModel):
    year_month: str
    total_ars: float


class TimelineRow(BaseModel):
    year_month: str
    total_ars: float


class CategoryCreate(BaseModel):
    name: str
    color: Optional[str] = None


class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    color: Optional[str] = None


class CategoryRead(BaseModel):
    id: int
    name: str
    color: Optional[str] = None


class MonthBreakdownRow(BaseModel):
    """Desglose de una cuota que vence en un mes dado."""

    purchase_id: int
    purchase_date: date
    description: str
    notes: Optional[str] = None
    category: Optional[str]
    payer_name: Optional[str] = None
    payment_method: Optional[str] = None
    card_name: Optional[str] = None
    installment_index: int
    installments_total: int
    amount_ars: float
    amount_original: float
    currency: str
    debtor_id: Optional[int] = None
    debtor_name: Optional[str] = None
    beneficiary_person_id: Optional[int] = None
    debt_settled: bool = False
    is_common: bool = False


class MonthBreakdownResponse(BaseModel):
    year_month: str
    total_ars: float
    items: list[MonthBreakdownRow]


class GSheetsImportRequest(BaseModel):
    url: str
    owner_person_id: int
    is_common: bool = False


class CategorySpendingRow(BaseModel):
    category: str
    total_ars: float


class PurchaseUpdate(BaseModel):
    notes: Optional[str] = None
    category: Optional[str] = None
    is_common: Optional[bool] = None
    debtor_id: Optional[int] = None
    beneficiary_person_id: Optional[int] = None
    debt_settled: Optional[bool] = None


class DebtorCreate(BaseModel):
    name: str


class DebtorRead(BaseModel):
    id: int
    name: str


class DebtSummaryRow(BaseModel):
    debtor_id: int
    debtor_name: str
    total_owed: float
    total_settled: float
    pending_purchases: int


class FxRateUpsert(BaseModel):
    year_month: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    currency: CurrencyCode
    rate_to_ars: float = Field(gt=0)


class FxRateRead(BaseModel):
    id: int
    year_month: str
    currency: CurrencyCode
    rate_to_ars: float


class MonthlyBudgetCreate(BaseModel):
    year_month: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    total_income: float = Field(gt=0)
    notes: Optional[str] = None


class MonthlyBudgetRead(BaseModel):
    id: int
    year_month: str
    total_income: float
    notes: Optional[str]


class MonthlyBalanceResponse(BaseModel):
    year_month: str
    presupuesto: float
    gastos_acumulados: float
    sobrante_total: float
    sobrante_por_persona: float
    porcentaje_gastado: float


class IncomeCreate(BaseModel):
    person_id: int
    year_month: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    amount: float = Field(gt=0)
    notes: Optional[str] = None


class IncomeRead(BaseModel):
    id: int
    person_id: int
    person_name: str
    year_month: str
    amount: float
    notes: Optional[str]


class DebtTransferCreate(BaseModel):
    from_person_id: int
    to_person_id: int
    year_month: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    amount: float = Field(gt=0)
    transfer_date: date = Field(default_factory=date.today)
    notes: Optional[str] = None


class DebtTransferRead(BaseModel):
    id: int
    from_person_id: int
    from_person_name: str
    to_person_id: int
    to_person_name: str
    year_month: str
    amount: float
    transfer_date: date
    notes: Optional[str]


class IngresoItem(BaseModel):
    person_id: int
    person_name: str
    amount: float


class GastoPersonaItem(BaseModel):
    person_id: int
    person_name: str
    paid_amount: float
    should_pay: float
    adjustment: float
    difference: float


class TransferenciaItem(BaseModel):
    from_person: str
    to_person: str
    amount: float


class TransferCalculationResponse(BaseModel):
    year_month: str
    ingresos: list[IngresoItem]
    total_ingresos: float
    total_common_expenses: float = 0.0
    total_personal_expenses: float = 0.0
    gastos_por_persona: list[GastoPersonaItem]
    transferencias: list[TransferenciaItem]
    is_balanced: bool
    balance_delta: float
    transferencias_internas: list[DebtTransferRead] = Field(default_factory=list)

class BulkPurchaseUpdate(BaseModel):
    purchase_ids: list[int]
    update: PurchaseUpdate


class RecurringExpenseRow(BaseModel):
    description: str
    category: Optional[str] = None
    currency: str
    occurrences: int
    total_purchases: int
    avg_amount: float
    months: list[str]
    last_seen: str


class FamilyGoalCreate(BaseModel):
    title: str
    description: Optional[str] = None
    target_amount: Optional[float] = None
    due_date: Optional[str] = None  # YYYY-MM
    notes: Optional[str] = None
    priority: Optional[str] = None  # "low", "medium", "high"


class FamilyGoalUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    target_amount: Optional[float] = None
    due_date: Optional[str] = None
    is_completed: Optional[bool] = None
    notes: Optional[str] = None
    priority: Optional[str] = None


class FamilyGoalRead(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    target_amount: Optional[float] = None
    due_date: Optional[str] = None
    is_completed: bool
    notes: Optional[str] = None
    priority: Optional[str] = None


class CardStatementCreate(BaseModel):
    card_id: int
    year_month: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    closing_date: date
    due_date: Optional[date] = None


class CardStatementRead(BaseModel):
    id: int
    card_id: int
    year_month: str
    closing_date: date
    due_date: Optional[date] = None


class SuggestMonthResponse(BaseModel):
    year_month: str
    closing_date: Optional[date] = None
    fallback: bool

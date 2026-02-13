from __future__ import annotations

from datetime import date
from typing import Generic, Optional, TypeVar

from pydantic import BaseModel, Field, model_validator

T = TypeVar("T")

from app.models import CurrencyCode, ShareType


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


class PurchaseCreate(BaseModel):
    card_id: int
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

    payers: Optional[list[PurchasePayerCreate]] = None

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
    card_id: int
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
    debtor_id: Optional[int]
    debt_settled: bool


class ReportMonthlyRow(BaseModel):
    year_month: str
    total_ars: float


class TimelineRow(BaseModel):
    year_month: str
    total_ars: float


class CategoryRead(BaseModel):
    categories: list[str]


class MonthBreakdownRow(BaseModel):
    """Desglose de una cuota que vence en un mes dado."""

    purchase_id: int
    purchase_date: date
    description: str
    category: Optional[str]
    installment_index: int
    installments_total: int
    amount_ars: float
    currency: str


class MonthBreakdownResponse(BaseModel):
    year_month: str
    total_ars: float
    items: list[MonthBreakdownRow]


class CategorySpendingRow(BaseModel):
    category: str
    total_ars: float


class PurchaseUpdate(BaseModel):
    notes: Optional[str] = None
    category: Optional[str] = None
    debtor_id: Optional[int] = None
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

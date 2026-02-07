from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field

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
    share_value: float


class PurchaseCreate(BaseModel):
    card_id: int
    purchase_date: date
    description: str

    currency: CurrencyCode
    amount_original: float

    installments_total: int = Field(default=1, ge=1)
    installment_amount_original: Optional[float] = None
    first_installment_month: Optional[str] = None  # YYYY-MM

    owner_person_id: Optional[int] = None
    category: Optional[str] = None
    notes: Optional[str] = None

    is_refund: bool = False

    payers: Optional[list[PurchasePayerCreate]] = None


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


class ReportMonthlyRow(BaseModel):
    year_month: str
    total_ars: float


class FxRateUpsert(BaseModel):
    year_month: str  # YYYY-MM
    currency: CurrencyCode
    rate_to_ars: float = Field(gt=0)


class FxRateRead(BaseModel):
    id: int
    year_month: str
    currency: CurrencyCode
    rate_to_ars: float

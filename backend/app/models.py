from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Optional

from sqlmodel import Field, SQLModel


class CurrencyCode(StrEnum):
    ARS = "ARS"
    USD = "USD"


class ShareType(StrEnum):
    PERCENT = "percent"
    FIXED = "fixed"


class Person(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str


class Card(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    provider: str
    owner_person_id: int = Field(foreign_key="person.id")
    last4: Optional[str] = None


class Debtor(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str


class FxRate(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    year_month: str = Field(index=True)  # YYYY-MM
    currency: CurrencyCode = Field(index=True)
    rate_to_ars: float


class Purchase(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    card_id: int = Field(foreign_key="card.id", index=True)
    purchase_date: date = Field(index=True)
    description: str

    currency: CurrencyCode = Field(index=True)
    amount_original: float
    amount_ars: Optional[float] = None

    installments_total: int = Field(default=1)
    installment_amount_original: Optional[float] = None
    first_installment_month: Optional[str] = None  # YYYY-MM

    owner_person_id: Optional[int] = Field(default=None, foreign_key="person.id")
    category: Optional[str] = Field(default=None, index=True)
    notes: Optional[str] = None

    is_refund: bool = Field(default=False)

    debtor_id: Optional[int] = Field(default=None, foreign_key="debtor.id", index=True)
    debt_settled: bool = Field(default=False)


class PurchasePayer(SQLModel, table=True):
    purchase_id: int = Field(foreign_key="purchase.id", primary_key=True)
    person_id: int = Field(foreign_key="person.id", primary_key=True)
    share_type: ShareType
    share_value: float


class InstallmentSchedule(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    purchase_id: int = Field(foreign_key="purchase.id", index=True)
    year_month: str = Field(index=True)  # YYYY-MM
    installment_index: int

    currency: CurrencyCode
    amount_original: float
    amount_ars: Optional[float] = None


class ImportedRow(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    provider: str = Field(index=True)
    source_file: str
    row_fingerprint: str = Field(index=True, unique=True)
    parsed_payload_json: str

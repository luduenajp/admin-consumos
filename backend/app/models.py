from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Optional

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


class CurrencyCode(str, Enum):
    ARS = "ARS"
    USD = "USD"


class ShareType(str, Enum):
    PERCENT = "percent"
    FIXED = "fixed"


class PaymentMethod(str, Enum):
    CARD = "card"
    TRANSFER = "transfer"
    CASH = "cash"


class Person(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str


class Card(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    provider: str
    owner_person_id: int = Field(foreign_key="person.id")
    last4: Optional[str] = None


class CardStatement(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("card_id", "year_month", name="uq_cardstatement_card_month"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    card_id: int = Field(foreign_key="card.id", index=True)
    year_month: str  # YYYY-MM — mes del resumen
    closing_date: date  # fecha exacta de cierre
    due_date: Optional[date] = None  # fecha de vencimiento del pago


class Debtor(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str


class Beneficiary(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    cbu: Optional[str] = None
    cuit: Optional[str] = None
    alias: Optional[str] = None


class Category(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(unique=True, index=True)
    color: Optional[str] = None


class FxRate(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    year_month: str = Field(index=True)  # YYYY-MM
    currency: CurrencyCode = Field(index=True)
    rate_to_ars: float


class Purchase(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    card_id: Optional[int] = Field(default=None, foreign_key="card.id", index=True)
    payment_method: PaymentMethod = Field(default=PaymentMethod.CARD, index=True)
    purchase_date: date = Field(index=True)
    description: str

    currency: CurrencyCode = Field(index=True)
    amount_original: float
    amount_ars: Optional[float] = None

    installments_total: int = Field(default=1)
    installment_amount_original: Optional[float] = None
    first_installment_month: Optional[str] = None  # YYYY-MM

    owner_person_id: Optional[int] = Field(default=None, foreign_key="person.id")
    beneficiary_person_id: Optional[int] = Field(default=None, foreign_key="person.id", index=True)
    category: Optional[str] = Field(default=None, index=True)
    notes: Optional[str] = None

    is_refund: bool = Field(default=False)
    is_common: bool = Field(default=False)

    debtor_id: Optional[int] = Field(default=None, foreign_key="debtor.id", index=True)
    debt_settled: bool = Field(default=False)
    import_batch_id: Optional[int] = Field(default=None, foreign_key="importbatch.id", index=True)


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


class ImportBatch(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    imported_at: str  # ISO-8601 datetime
    provider: str = Field(index=True)
    source_file: str
    card_id: Optional[int] = Field(default=None, foreign_key="card.id")
    statement_year_month: Optional[str] = None  # YYYY-MM
    purchases_created: int = Field(default=0)
    purchases_skipped: int = Field(default=0)
    purchases_parsed: int = Field(default=0)


class ImportedRow(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    provider: str = Field(index=True)
    source_file: str
    row_fingerprint: str = Field(index=True, unique=True)
    parsed_payload_json: str


class MonthlyBudget(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    year_month: str = Field(unique=True, index=True)  # YYYY-MM
    total_income: float
    notes: Optional[str] = None



class Income(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    person_id: int = Field(foreign_key="person.id", index=True)
    year_month: str = Field(index=True)  # YYYY-MM
    amount: float
    notes: Optional[str] = None


class DebtTransfer(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    from_person_id: int = Field(foreign_key="person.id", index=True)
    to_person_id: int = Field(foreign_key="person.id", index=True)
    year_month: str = Field(index=True)  # YYYY-MM
    amount: float
    transfer_date: date = Field(default_factory=date.today)
    notes: Optional[str] = None


class FamilyGoal(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    description: Optional[str] = None
    target_amount: Optional[float] = None  # presupuesto estimado en ARS
    due_date: Optional[str] = None  # YYYY-MM
    is_completed: bool = Field(default=False)
    notes: Optional[str] = None
    priority: Optional[str] = None  # "low", "medium", "high"


class Saving(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    person_id: int = Field(foreign_key="person.id", index=True)
    investment_type: str  # free text: "FCI", "Bono", "CDAR", etc.
    institution: str      # free text: "Banco Nación", "MP", etc.
    currency: CurrencyCode = Field(index=True)
    notes: Optional[str] = None


class SavingSnapshot(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    saving_id: int = Field(foreign_key="saving.id", index=True)
    date: date
    amount: float


class SavingsExchangeRate(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    date: str = Field(index=True)  # YYYY-MM-DD
    usd_buy: float   # price bank pays when buying USD (you receive this when selling USD)
    usd_sell: float  # price bank charges when selling USD (you pay this when buying USD)


class Service(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    expected_amount: Optional[float] = None
    typical_due_day: Optional[int] = None  # 1–31
    is_active: bool = Field(default=True)
    sort_order: int = Field(default=0)


class ServicePayment(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("service_id", "year_month", name="uq_servicepayment_service_month"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    service_id: int = Field(foreign_key="service.id", index=True)
    year_month: str = Field(index=True)  # YYYY-MM
    due_date: Optional[date] = None
    paid_date: Optional[date] = None
    amount: Optional[float] = None
    notes: Optional[str] = None

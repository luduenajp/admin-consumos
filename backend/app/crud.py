from __future__ import annotations

from datetime import date
from typing import Optional

from sqlalchemy import case
from sqlmodel import Session, col, func, select

from app.models import (
    Card,
    CurrencyCode,
    Debtor,
    FxRate,
    Income,
    InstallmentSchedule,
    MonthlyBudget,
    Person,
    Purchase,
    PurchasePayer,
    ShareType,
)
from app.schemas import CardCreate, DebtorCreate, FxRateUpsert, IncomeCreate, MonthlyBudgetCreate, PersonCreate, PurchaseCreate, PurchaseUpdate
from app.utils_dates import add_months, to_year_month
from app.importers.visa_xlsx import normalize_purchase_description


def create_person(*, session: Session, payload: PersonCreate) -> Person:
    person = Person(name=payload.name)
    session.add(person)
    session.commit()
    session.refresh(person)
    return person


def list_people(*, session: Session) -> list[Person]:
    return list(session.exec(select(Person).order_by(Person.name)))


def create_card(*, session: Session, payload: CardCreate) -> Card:
    owner = session.get(Person, payload.owner_person_id)
    if owner is None:
        raise ValueError("Person not found")
    card = Card(
        name=payload.name,
        provider=payload.provider,
        owner_person_id=payload.owner_person_id,
        last4=payload.last4,
    )
    session.add(card)
    session.commit()
    session.refresh(card)
    return card


def list_cards(*, session: Session) -> list[Card]:
    return list(session.exec(select(Card).order_by(Card.name)))


def upsert_fx_rate(*, session: Session, payload: FxRateUpsert) -> FxRate:
    stmt = select(FxRate).where(
        FxRate.year_month == payload.year_month,
        FxRate.currency == payload.currency,
    )
    existing = session.exec(stmt).first()
    if existing is None:
        fx = FxRate(
            year_month=payload.year_month,
            currency=payload.currency,
            rate_to_ars=float(payload.rate_to_ars),
        )
        session.add(fx)
        session.commit()
        session.refresh(fx)
        return fx

    existing.rate_to_ars = float(payload.rate_to_ars)
    session.add(existing)
    session.commit()
    session.refresh(existing)
    return existing


def list_fx_rates(*, session: Session) -> list[FxRate]:
    return list(session.exec(select(FxRate).order_by(FxRate.year_month, FxRate.currency)))


def _round_money(value: float) -> float:
    return round(float(value) + 1e-9, 2)


def _default_payers_for_card_owner(*, card: Card) -> list[PurchasePayer]:
    return [
        PurchasePayer(
            purchase_id=0,
            person_id=card.owner_person_id,
            share_type=ShareType.PERCENT,
            share_value=100.0,
        )
    ]


def _normalize_installment_amount(
    *, amount_original: float, installments_total: int, installment_amount_original: Optional[float]
) -> float:
    if installments_total <= 1:
        return _round_money(amount_original)

    if installment_amount_original is not None:
        return _round_money(installment_amount_original)

    return _round_money(amount_original / installments_total)


def create_purchase(*, session: Session, payload: PurchaseCreate) -> Purchase:
    card = None
    if payload.card_id is not None:
        card = session.get(Card, payload.card_id)
        if card is None:
            raise ValueError("Card not found")

    if payload.owner_person_id is not None:
        if session.get(Person, payload.owner_person_id) is None:
            raise ValueError("owner_person_id: Person not found")

    if payload.payers:
        for p in payload.payers:
            if session.get(Person, p.person_id) is None:
                raise ValueError(f"Payer person_id {p.person_id}: Person not found")

    first_month = payload.first_installment_month or to_year_month(payload.purchase_date)
    installment_amount = _normalize_installment_amount(
        amount_original=payload.amount_original,
        installments_total=payload.installments_total,
        installment_amount_original=payload.installment_amount_original,
    )

    purchase = Purchase(
        card_id=payload.card_id,
        payment_method=payload.payment_method,
        purchase_date=payload.purchase_date,
        description=payload.description,
        currency=payload.currency,
        amount_original=_round_money(payload.amount_original),
        amount_ars=None,
        installments_total=payload.installments_total,
        installment_amount_original=installment_amount,
        first_installment_month=first_month,
        owner_person_id=payload.owner_person_id,
        category=payload.category,
        notes=payload.notes,
        is_refund=payload.is_refund,
        debtor_id=payload.debtor_id,
    )

    session.add(purchase)
    session.flush()

    payers: list[PurchasePayer]
    if payload.payers and len(payload.payers) > 0:
        payers = [
            PurchasePayer(
                purchase_id=purchase.id,
                person_id=p.person_id,
                share_type=p.share_type,
                share_value=p.share_value,
            )
            for p in payload.payers
        ]
    else:
        # If no card, we MUST have owner_person_id or fail gracefully
        default_person_id = None
        if card:
            default_person_id = card.owner_person_id
        elif payload.owner_person_id:
            default_person_id = payload.owner_person_id
        else:
            # Fallback for manual creation without card/owner: use first person found?
            # Better to require owner_person_id in the API for non-card expenses
            raise ValueError("owner_person_id is required for non-card expenses")

        payers = [
            PurchasePayer(
                purchase_id=purchase.id,
                person_id=default_person_id,
                share_type=ShareType.PERCENT,
                share_value=100.0,
            )
        ]

    for payer in payers:
        session.add(payer)

    _create_installment_schedule(session=session, purchase=purchase)

    session.commit()
    return purchase


def find_existing_purchase_for_installment_import(
    *,
    session: Session,
    card_id: int,
    purchase_date: date,
    description: str,
    currency: CurrencyCode,
    installments_total: int,
    installment_amount_original: float,
) -> Optional[Purchase]:
    normalized = normalize_purchase_description(description=description)
    stmt = select(Purchase).where(
        Purchase.card_id == card_id,
        Purchase.purchase_date == purchase_date,
        Purchase.currency == currency,
        Purchase.installments_total == installments_total,
        Purchase.installment_amount_original == installment_amount_original,
    )

    candidates = list(session.exec(stmt))
    for c in candidates:
        if normalize_purchase_description(description=c.description) == normalized:
            return c
    return None


def list_purchases(
    *,
    session: Session,
    year_month: Optional[str] = None,
    category: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    min_amount: Optional[float] = None,
    max_amount: Optional[float] = None,
    description_search: Optional[str] = None,
    person_id: Optional[int] = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[Purchase], int]:
    """
    List purchases with optional filters and pagination.

    Args:
        year_month: Filter by specific month (YYYY-MM)
        category: Filter by exact category (use 'null' for NULL categories)
        start_date/end_date: Date range filter
        min_amount/max_amount: Amount range filter (in original currency)
        description_search: Case-insensitive substring search in description
        person_id: Filter by payer (purchases where this person has a share in PurchasePayer)
        page: 1-based page number
        page_size: Number of items per page
    Returns:
        (items, total) where total is the total count matching filters.
    """
    stmt = select(Purchase)

    # Filter by payer (person who paid)
    if person_id is not None:
        stmt = stmt.join(PurchasePayer, Purchase.id == PurchasePayer.purchase_id).where(
            PurchasePayer.person_id == person_id
        )

    # Existing year_month filter
    if year_month:
        year_s, month_s = year_month.split("-")
        year = int(year_s)
        month = int(month_s)
        start = date(year, month, 1)
        if month == 12:
            end = date(year + 1, 1, 1)
        else:
            end = date(year, month + 1, 1)
        stmt = stmt.where(Purchase.purchase_date >= start, Purchase.purchase_date < end)

    # Category filter
    if category is not None:
        if category.lower() == "null":
            stmt = stmt.where(Purchase.category.is_(None))
        else:
            stmt = stmt.where(Purchase.category == category)

    # Date range filter
    if start_date is not None:
        stmt = stmt.where(Purchase.purchase_date >= start_date)
    if end_date is not None:
        stmt = stmt.where(Purchase.purchase_date <= end_date)

    # Amount range filter
    if min_amount is not None:
        stmt = stmt.where(Purchase.amount_original >= min_amount)
    if max_amount is not None:
        stmt = stmt.where(Purchase.amount_original <= max_amount)

    # Description search (case-insensitive)
    if description_search:
        stmt = stmt.where(col(Purchase.description).contains(description_search))

    total = session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    stmt = (
        stmt.order_by(Purchase.purchase_date.desc(), Purchase.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = list(session.exec(stmt))
    return (items, total)


def update_purchase(*, session: Session, purchase_id: int, payload: PurchaseUpdate) -> Purchase:
    """Update editable fields of an existing purchase (notes, category)."""
    purchase = session.get(Purchase, purchase_id)
    if purchase is None:
        raise ValueError(f"Purchase {purchase_id} not found")
    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(purchase, field, value)
    session.commit()
    session.refresh(purchase)
    return purchase


def delete_purchase(*, session: Session, purchase_id: int) -> None:
    """Delete a purchase and all its related installments and payers."""
    from sqlalchemy import text as sa_text
    purchase = session.get(Purchase, purchase_id)
    if purchase is None:
        raise ValueError(f"Purchase {purchase_id} not found")
    # Use direct SQL deletes in FK-safe order (children before parent)
    session.exec(sa_text("DELETE FROM installmentschedule WHERE purchase_id = :pid").bindparams(pid=purchase_id))  # type: ignore[call-overload]
    session.exec(sa_text("DELETE FROM purchasepayer WHERE purchase_id = :pid").bindparams(pid=purchase_id))  # type: ignore[call-overload]
    session.exec(sa_text("DELETE FROM purchase WHERE id = :pid").bindparams(pid=purchase_id))  # type: ignore[call-overload]
    session.commit()


def _create_installment_schedule(*, session: Session, purchase: Purchase) -> None:
    if purchase.id is None:
        raise ValueError("purchase.id is required")

    installment_amount = purchase.installment_amount_original or purchase.amount_original

    if purchase.installments_total <= 1:
        ym = purchase.first_installment_month or to_year_month(purchase.purchase_date)
        session.add(
            InstallmentSchedule(
                purchase_id=purchase.id,
                year_month=ym,
                installment_index=1,
                currency=purchase.currency,
                amount_original=_round_money(installment_amount),
                amount_ars=None,
            )
        )
        return

    first_month = purchase.first_installment_month or to_year_month(purchase.purchase_date)
    for idx in range(1, purchase.installments_total + 1):
        ym = add_months(first_month, idx - 1)
        session.add(
            InstallmentSchedule(
                purchase_id=purchase.id,
                year_month=ym,
                installment_index=idx,
                currency=purchase.currency,
                amount_original=_round_money(installment_amount),
                amount_ars=None,
            )
        )


def report_monthly_totals_ars(*, session: Session) -> list[tuple[str, float]]:
    raise NotImplementedError("Use report_monthly_totals_converted")


def _fx_rate_map(*, session: Session) -> dict[tuple[str, CurrencyCode], float]:
    rates = list_fx_rates(session=session)
    return {(r.year_month, r.currency): float(r.rate_to_ars) for r in rates if r.id is not None}


def report_monthly_totals_converted(
    *, session: Session, card_id: Optional[int] = None, person_id: Optional[int] = None
) -> list[tuple[str, float]]:
    fx_map = _fx_rate_map(session=session)

    schedules_stmt = select(InstallmentSchedule)
    if card_id is not None:
        schedules_stmt = schedules_stmt.join(Purchase, Purchase.id == InstallmentSchedule.purchase_id).where(
            Purchase.card_id == card_id
        )
    schedules = list(session.exec(schedules_stmt))

    payer_map: dict[int, list[PurchasePayer]] = {}
    if person_id is not None:
        payers = list(session.exec(select(PurchasePayer).where(PurchasePayer.person_id == person_id)))
        for p in payers:
            payer_map.setdefault(p.purchase_id, []).append(p)

    totals: dict[str, float] = {}
    for sch in schedules:
        amount_original = float(sch.amount_original)
        amount_ars: float

        if sch.currency == CurrencyCode.ARS:
            amount_ars = amount_original
        else:
            rate = fx_map.get((sch.year_month, sch.currency))
            if rate is None:
                # If FX missing, skip for now to avoid silent wrong totals.
                continue
            amount_ars = amount_original * float(rate)

        if person_id is not None:
            payers = payer_map.get(sch.purchase_id, [])
            allocated = 0.0
            for payer in payers:
                if payer.person_id != person_id:
                    continue
                if payer.share_type == ShareType.PERCENT:
                    allocated += amount_ars * (float(payer.share_value) / 100.0)
                else:
                    allocated += float(payer.share_value)
            amount_ars = allocated

        totals[sch.year_month] = float(totals.get(sch.year_month, 0.0) + amount_ars)

    return [(ym, round(total, 2)) for ym, total in sorted(totals.items(), key=lambda x: x[0])]


def report_month_breakdown(
    *,
    session: Session,
    year_month: str,
    card_id: Optional[int] = None,
    person_id: Optional[int] = None,
) -> tuple[float, list[tuple[Purchase, InstallmentSchedule, float, Optional[str]]]]:
    """
    Desglose de cuotas que vencen en un mes dado.
    Returns (total_ars, list of (purchase, schedule, amount_ars, debtor_name)).
    """
    fx_map = _fx_rate_map(session=session)

    stmt = (
        select(InstallmentSchedule, Purchase, Debtor, Card)
        .join(Purchase, Purchase.id == InstallmentSchedule.purchase_id)
        .outerjoin(Debtor, Debtor.id == Purchase.debtor_id)
        .outerjoin(Card, Card.id == Purchase.card_id)
        .where(InstallmentSchedule.year_month == year_month)
    )
    if card_id is not None:
        stmt = stmt.where(Purchase.card_id == card_id)

    results = list(session.exec(stmt))

    payer_map: dict[int, list[PurchasePayer]] = {}
    if person_id is not None:
        payers = list(session.exec(select(PurchasePayer).where(PurchasePayer.person_id == person_id)))
        for p in payers:
            payer_map.setdefault(p.purchase_id, []).append(p)

    items: list[tuple[Purchase, InstallmentSchedule, float, Optional[str]]] = []
    total_ars = 0.0

    for sch, purchase, debtor, card in results:
        debtor_name = debtor.name if debtor else None
        amount_original = float(sch.amount_original)
        if sch.currency == CurrencyCode.ARS:
            amount_ars = amount_original
        else:
            rate = fx_map.get((sch.year_month, sch.currency))
            if rate is None:
                continue
            amount_ars = amount_original * float(rate)

        if person_id is not None:
            payers = payer_map.get(sch.purchase_id, [])
            if not payers:
                # No explicit payers: owner gets 100%
                owner_id = purchase.owner_person_id if purchase.owner_person_id is not None else (card.owner_person_id if card else None)
                if owner_id != person_id:
                    amount_ars = 0.0
                # else: amount_ars remains the same (100%)
            else:
                allocated = 0.0
                for payer in payers:
                    if payer.person_id != person_id:
                        continue
                    if payer.share_type == ShareType.PERCENT:
                        allocated += amount_ars * (float(payer.share_value) / 100.0)
                    else:
                        allocated += float(payer.share_value)
                amount_ars = allocated

            if amount_ars == 0:
                continue

        total_ars += amount_ars
        items.append((purchase, sch, round(amount_ars, 2), debtor_name))

    return (round(total_ars, 2), items)


def get_distinct_categories(*, session: Session) -> list[str]:
    """Return list of unique categories used in purchases (excluding NULL)."""
    stmt = select(Purchase.category).where(Purchase.category.is_not(None)).distinct()
    results = session.exec(stmt)
    categories = [cat for cat in results if cat is not None]
    return sorted(categories)


def report_spending_by_category(
    *, session: Session, card_id: Optional[int] = None, person_id: Optional[int] = None
) -> list[tuple[str, float]]:
    """
    Return total spending per category (category -> total_ars).
    Uses full installment schedule, not just purchase totals.
    """
    fx_map = _fx_rate_map(session=session)

    # Join InstallmentSchedule with Purchase to get category
    stmt = select(InstallmentSchedule, Purchase.category).join(
        Purchase, Purchase.id == InstallmentSchedule.purchase_id
    )

    # Apply filters
    if card_id is not None:
        stmt = stmt.where(Purchase.card_id == card_id)

    results = list(session.exec(stmt))

    # Build payer_map if person_id filter
    payer_map: dict[int, list[PurchasePayer]] = {}
    if person_id is not None:
        payers = list(session.exec(select(PurchasePayer).where(PurchasePayer.person_id == person_id)))
        for p in payers:
            payer_map.setdefault(p.purchase_id, []).append(p)

    # Aggregate by category
    totals: dict[str, float] = {}
    for sch, category in results:
        cat_key = category or "Sin categoría"
        amount_original = float(sch.amount_original)

        # Convert to ARS
        if sch.currency == CurrencyCode.ARS:
            amount_ars = amount_original
        else:
            rate = fx_map.get((sch.year_month, sch.currency))
            if rate is None:
                continue
            amount_ars = amount_original * float(rate)

        # Apply person filter
        if person_id is not None:
            payers = payer_map.get(sch.purchase_id, [])
            allocated = 0.0
            for payer in payers:
                if payer.person_id != person_id:
                    continue
                if payer.share_type == ShareType.PERCENT:
                    allocated += amount_ars * (float(payer.share_value) / 100.0)
                else:
                    allocated += float(payer.share_value)
            amount_ars = allocated

        totals[cat_key] = float(totals.get(cat_key, 0.0) + amount_ars)

    return [(cat, round(total, 2)) for cat, total in sorted(totals.items(), key=lambda x: -x[1])]


def report_installment_timeline(
    *,
    session: Session,
    months_ahead: int = 12,
    card_id: Optional[int] = None,
    person_id: Optional[int] = None,
) -> list[tuple[str, float]]:
    """
    Return timeline of future installments (year_month -> total_ars).
    Excludes past months, shows only future commitments.
    """
    current_ym = to_year_month(date.today())
    end_ym = add_months(current_ym, months_ahead)

    fx_map = _fx_rate_map(session=session)

    # Query InstallmentSchedule filtered by year_month range
    stmt = select(InstallmentSchedule).where(
        InstallmentSchedule.year_month >= current_ym, InstallmentSchedule.year_month <= end_ym
    )

    # Apply card filter
    if card_id is not None:
        stmt = stmt.join(Purchase, Purchase.id == InstallmentSchedule.purchase_id).where(Purchase.card_id == card_id)

    schedules = list(session.exec(stmt))

    # Build payer_map if person_id filter
    payer_map: dict[int, list[PurchasePayer]] = {}
    if person_id is not None:
        payers = list(session.exec(select(PurchasePayer).where(PurchasePayer.person_id == person_id)))
        for p in payers:
            payer_map.setdefault(p.purchase_id, []).append(p)

    # Aggregate by year_month (same logic as report_monthly_totals_converted)
    totals: dict[str, float] = {}
    for sch in schedules:
        amount_original = float(sch.amount_original)

        # Convert to ARS
        if sch.currency == CurrencyCode.ARS:
            amount_ars = amount_original
        else:
            rate = fx_map.get((sch.year_month, sch.currency))
            if rate is None:
                continue  # Skip if FX rate missing
            amount_ars = amount_original * float(rate)

        # Apply person filter allocation
        if person_id is not None:
            payers = payer_map.get(sch.purchase_id, [])
            allocated = 0.0
            for payer in payers:
                if payer.person_id != person_id:
                    continue
                if payer.share_type == ShareType.PERCENT:
                    allocated += amount_ars * (float(payer.share_value) / 100.0)
                else:
                    allocated += float(payer.share_value)
            amount_ars = allocated

        totals[sch.year_month] = float(totals.get(sch.year_month, 0.0) + amount_ars)

    return [(ym, round(total, 2)) for ym, total in sorted(totals.items())]


# ---------------------------------------------------------------------------
# Debtors
# ---------------------------------------------------------------------------


def create_debtor(*, session: Session, payload: DebtorCreate) -> Debtor:
    debtor = Debtor(name=payload.name)
    session.add(debtor)
    session.commit()
    session.refresh(debtor)
    return debtor


def list_debtors(*, session: Session) -> list[Debtor]:
    return list(session.exec(select(Debtor).order_by(Debtor.name)))


def report_debts(*, session: Session) -> list[tuple[int, str, float, float, int]]:
    """
    Return debt summary per debtor.
    Returns list of (debtor_id, debtor_name, total_owed, total_settled, pending_count).
    """
    debtors = list_debtors(session=session)
    results: list[tuple[int, str, float, float, int]] = []

    for debtor in debtors:
        if debtor.id is None:
            continue

        purchases = list(
            session.exec(select(Purchase).where(Purchase.debtor_id == debtor.id))
        )

        total_owed = 0.0
        total_settled = 0.0
        pending_count = 0

        for p in purchases:
            if p.debt_settled:
                total_settled += float(p.amount_original)
            else:
                total_owed += float(p.amount_original)
                pending_count += 1

        if total_owed > 0 or total_settled > 0:
            results.append((
                debtor.id,
                debtor.name,
                round(total_owed, 2),
                round(total_settled, 2),
                pending_count,
            ))

    return results


def create_monthly_budget(*, session: Session, payload: MonthlyBudgetCreate) -> MonthlyBudget:
    # Check if budget for this month already exists
    existing = session.exec(
        select(MonthlyBudget).where(MonthlyBudget.year_month == payload.year_month)
    ).first()
    
    if existing:
        # Update existing budget
        existing.total_income = payload.total_income
        existing.notes = payload.notes
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return existing
    
    # Create new budget
    budget = MonthlyBudget(
        year_month=payload.year_month,
        total_income=payload.total_income,
        notes=payload.notes
    )
    session.add(budget)
    session.commit()
    session.refresh(budget)
    return budget


def get_monthly_budget(*, session: Session, year_month: str) -> Optional[MonthlyBudget]:
    return session.exec(
        select(MonthlyBudget).where(MonthlyBudget.year_month == year_month)
    ).first()


def list_monthly_budgets(*, session: Session) -> list[MonthlyBudget]:
    return list(session.exec(select(MonthlyBudget).order_by(MonthlyBudget.year_month.desc())))


def calculate_monthly_balance(*, session: Session, year_month: str) -> Optional[dict]:
    """
    Calculate monthly balance: income - expenses = surplus for each person
    """
    # Get budget for the month
    budget = get_monthly_budget(session=session, year_month=year_month)
    if not budget:
        return None
    
    # Get total expenses for the month (sum of all installments)
    # If amount_ars is NULL but currency is ARS, fall back to amount_original.
    # If currency is USD and amount_ars is NULL, we exclude it (requires FX).
    amount_ars_or_ars_original = case(
        (InstallmentSchedule.amount_ars.is_not(None), InstallmentSchedule.amount_ars),
        (InstallmentSchedule.currency == CurrencyCode.ARS, InstallmentSchedule.amount_original),
        else_=None,
    )
    expenses_query = (
        select(func.sum(amount_ars_or_ars_original))
        .where(InstallmentSchedule.year_month == year_month)
    )
    total_expenses = float(session.exec(expenses_query).first() or 0.0)
    
    # Calculate surplus
    surplus_total = budget.total_income - total_expenses
    surplus_per_person = surplus_total / 2
    percentage_spent = (total_expenses / budget.total_income) * 100 if budget.total_income > 0 else 0
    
    return {
        "year_month": year_month,
        "presupuesto": budget.total_income,
        "gastos_acumulados": total_expenses,
        "sobrante_total": surplus_total,
        "sobrante_por_persona": surplus_per_person,
        "porcentaje_gastado": percentage_spent
    }


def create_income(*, session: Session, payload: IncomeCreate) -> Income:
    # Check if income for this person and month already exists
    existing = session.exec(
        select(Income).where(
            Income.person_id == payload.person_id,
            Income.year_month == payload.year_month
        )
    ).first()
    
    if existing:
        # Update existing income
        existing.amount = payload.amount
        existing.notes = payload.notes
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return existing
    
    # Create new income
    income = Income(
        person_id=payload.person_id,
        year_month=payload.year_month,
        amount=payload.amount,
        notes=payload.notes
    )
    session.add(income)
    session.commit()
    session.refresh(income)
    
    # Update or create monthly budget
    _update_monthly_budget_from_incomes(session=session, year_month=payload.year_month)
    
    return income


def list_incomes(*, session: Session, year_month: Optional[str] = None) -> list[Income]:
    query = select(Income).join(Person).order_by(Income.year_month.desc(), Person.name)
    if year_month:
        query = query.where(Income.year_month == year_month)
    return list(session.exec(query))


def _update_monthly_budget_from_incomes(*, session: Session, year_month: str):
    """Update MonthlyBudget based on sum of incomes for the month"""
    incomes_query = (
        select(func.sum(Income.amount))
        .where(Income.year_month == year_month)
    )
    total_income = session.exec(incomes_query).first() or 0.0
    
    if total_income > 0:
        # Create or update budget
        existing_budget = session.exec(
            select(MonthlyBudget).where(MonthlyBudget.year_month == year_month)
        ).first()
        
        if existing_budget:
            existing_budget.total_income = total_income
            session.add(existing_budget)
        else:
            budget = MonthlyBudget(
                year_month=year_month,
                total_income=total_income,
                notes="Calculado automáticamente desde ingresos"
            )
            session.add(budget)
        
        session.commit()


def calculate_transfers(*, session: Session, year_month: str) -> Optional[dict]:
    """
    Calculate who should transfer money to whom based on:
    1. Individual incomes
    2. Shared expenses (50/50 split)
    3. Who actually paid for each expense
    """
    # Get incomes for the month
    incomes_query = (
        select(Income.id, Income.person_id, Income.amount, Person.name)
        .join(Person)
        .where(Income.year_month == year_month)
    )
    incomes_data = session.exec(incomes_query).all()
    
    if not incomes_data:
        return None
    
    # Format incomes
    ingresos = [
        {
            "person_id": person_id,
            "person_name": name,
            "amount": float(amount)
        }
        for _, person_id, amount, name in incomes_data
    ]
    
    total_ingresos = sum(inc["amount"] for inc in ingresos)
    
    # Get total shared expenses for the month
    amount_ars_or_ars_original = case(
        (InstallmentSchedule.amount_ars.is_not(None), InstallmentSchedule.amount_ars),
        (InstallmentSchedule.currency == CurrencyCode.ARS, InstallmentSchedule.amount_original),
        else_=None,
    )
    expenses_query = (
        select(func.sum(amount_ars_or_ars_original))
        .where(InstallmentSchedule.year_month == year_month)
    )
    total_expenses = float(session.exec(expenses_query).first() or 0.0)

    # Compute paid amounts per person for this month.
    # Rule:
    # - If Purchase has PurchasePayer rows, allocate the installment amount using those shares.
    # - Otherwise, allocate 100% to purchase.owner_person_id (default behavior).
    schedule_rows = session.exec(
        select(
            InstallmentSchedule.purchase_id,
            amount_ars_or_ars_original,
            Purchase.owner_person_id,
            Purchase.card_id,
            Card.owner_person_id,
        )
        .join(Purchase, Purchase.id == InstallmentSchedule.purchase_id)
        .join(Card, Card.id == Purchase.card_id)
        .where(InstallmentSchedule.year_month == year_month)
    ).all()

    paid_amount_by_person_id: dict[int, float] = {inc["person_id"]: 0.0 for inc in ingresos}

    purchase_ids = sorted({pid for pid, _, _, _, _ in schedule_rows})
    payers_by_purchase_id: dict[int, list[PurchasePayer]] = {}
    if purchase_ids:
        payers = list(session.exec(select(PurchasePayer).where(PurchasePayer.purchase_id.in_(purchase_ids))))
        for payer in payers:
            payers_by_purchase_id.setdefault(payer.purchase_id, []).append(payer)

    for purchase_id, amount_ars, owner_person_id, _card_id, card_owner_person_id in schedule_rows:
        installment_amount = float(amount_ars or 0.0)
        if installment_amount == 0.0:
            continue

        payer_person_id = owner_person_id if owner_person_id is not None else card_owner_person_id

        payers = payers_by_purchase_id.get(purchase_id, [])
        if not payers:
            if payer_person_id is not None:
                paid_amount_by_person_id.setdefault(payer_person_id, 0.0)
                paid_amount_by_person_id[payer_person_id] += installment_amount
            continue

        fixed_payers = [p for p in payers if p.share_type == ShareType.FIXED]
        percent_payers = [p for p in payers if p.share_type == ShareType.PERCENT]

        fixed_total = sum(float(p.share_value) for p in fixed_payers)
        remaining = max(installment_amount - fixed_total, 0.0)

        for p in fixed_payers:
            paid_amount_by_person_id.setdefault(p.person_id, 0.0)
            paid_amount_by_person_id[p.person_id] += min(float(p.share_value), installment_amount)

        if percent_payers:
            percent_sum = sum(float(p.share_value) for p in percent_payers)
            for p in percent_payers:
                paid_amount_by_person_id.setdefault(p.person_id, 0.0)
                paid_amount_by_person_id[p.person_id] += remaining * (float(p.share_value) / percent_sum)
        else:
            # If only fixed payers exist and there's remaining, assign remaining to owner as fallback.
            if remaining > 0 and payer_person_id is not None:
                paid_amount_by_person_id.setdefault(payer_person_id, 0.0)
                paid_amount_by_person_id[payer_person_id] += remaining

    # Calculate what each person should pay (50/50 split)
    should_pay_per_person = total_expenses / 2 if total_expenses > 0 else 0.0

    person_name_by_id = {inc["person_id"]: inc["person_name"] for inc in ingresos}
    gastos_por_persona = []
    for person_id in sorted(person_name_by_id.keys()):
        paid_amount = float(paid_amount_by_person_id.get(person_id, 0.0))
        difference = paid_amount - should_pay_per_person
        gastos_por_persona.append({
            "person_id": person_id,
            "person_name": person_name_by_id[person_id],
            "paid_amount": round(paid_amount, 2),
            "should_pay": round(should_pay_per_person, 2),
            "difference": round(difference, 2),
        })
    
    # Calculate transfers
    transferencias = []
    
    # People who paid more than they should (should receive money)
    debtors = [gp for gp in gastos_por_persona if gp["difference"] > 0]
    # People who paid less than they should (should pay money)
    creditors = [gp for gp in gastos_por_persona if gp["difference"] < 0]
    
    # Simple transfer calculation
    for debtor in debtors:
        remaining_to_receive = debtor["difference"]
        for creditor in creditors:
            if remaining_to_receive <= 0:
                break
            
            creditor_needs = abs(creditor["difference"])
            transfer_amount = min(remaining_to_receive, creditor_needs)
            
            if transfer_amount > 0:
                transferencias.append({
                    "from_person": creditor["person_name"],
                    "to_person": debtor["person_name"],
                    "amount": round(transfer_amount, 2)
                })
                remaining_to_receive -= transfer_amount
    
    return {
        "year_month": year_month,
        "ingresos": ingresos,
        "total_ingresos": total_ingresos,
        "gastos_por_persona": gastos_por_persona,
        "transferencias": transferencias
    }

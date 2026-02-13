from __future__ import annotations

from datetime import date
from typing import Optional

from sqlmodel import Session, col, func, select

from app.models import (
    Card,
    CurrencyCode,
    Debtor,
    FxRate,
    InstallmentSchedule,
    Person,
    Purchase,
    PurchasePayer,
    ShareType,
)
from app.schemas import CardCreate, DebtorCreate, FxRateUpsert, PersonCreate, PurchaseCreate, PurchaseUpdate
from app.utils_dates import add_months, to_year_month


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
        payers = [
            PurchasePayer(
                purchase_id=purchase.id,
                person_id=card.owner_person_id,
                share_type=ShareType.PERCENT,
                share_value=100.0,
            )
        ]

    for payer in payers:
        session.add(payer)

    _create_installment_schedule(session=session, purchase=purchase)

    session.commit()
    return purchase


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
) -> tuple[float, list[tuple[Purchase, InstallmentSchedule, float]]]:
    """
    Desglose de cuotas que vencen en un mes dado.
    Returns (total_ars, list of (purchase, schedule, amount_ars)).
    """
    fx_map = _fx_rate_map(session=session)

    stmt = (
        select(InstallmentSchedule, Purchase)
        .join(Purchase, Purchase.id == InstallmentSchedule.purchase_id)
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

    items: list[tuple[Purchase, InstallmentSchedule, float]] = []
    total_ars = 0.0

    for sch, purchase in results:
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
            allocated = 0.0
            for payer in payers:
                if payer.person_id != person_id:
                    continue
                if payer.share_type == ShareType.PERCENT:
                    allocated += amount_ars * (float(payer.share_value) / 100.0)
                else:
                    allocated += float(payer.share_value)
            amount_ars = allocated

        total_ars += amount_ars
        items.append((purchase, sch, round(amount_ars, 2)))

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

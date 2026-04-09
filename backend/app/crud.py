from __future__ import annotations

from datetime import date
from typing import Optional

from sqlalchemy import case, text
from sqlalchemy.orm import aliased
from sqlmodel import Session, col, func, select

from app import schemas
from app.models import (
    Card,
    Category,
    CurrencyCode,
    Debtor,
    FxRate,
    Income,
    InstallmentSchedule,
    MonthlyBudget,
    ImportBatch,
    PaymentMethod,
    Person,
    Purchase,
    PurchasePayer,
    ShareType,
    DebtTransfer,
    FamilyGoal,
    Saving,
    SavingSnapshot,
)
from app.schemas import (
    CardCreate,
    CategoryCreate,
    CategoryUpdate,
    DebtorCreate,
    FamilyGoalCreate,
    FamilyGoalUpdate,
    FxRateUpsert,
    IncomeCreate,
    MonthlyBudgetCreate,
    PersonCreate,
    PurchaseCreate,
    PurchaseUpdate,
    SavingCreate,
    SavingUpdate,
    SavingSnapshotCreate,
)
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
    # +1e-9 nudges values like 999.99499999... up to 999.995 so they round to 1000.00
    # instead of 999.99. This compensates for floating-point representation error.
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

    # For TRANSFER and CASH, money exits immediately — always use the purchase month
    # regardless of what the caller provides (avoids billing-cycle shift from card importers)
    if payload.payment_method in (PaymentMethod.TRANSFER, PaymentMethod.CASH):
        first_month = to_year_month(payload.purchase_date)
    else:
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
        is_common=payload.is_common,
        debtor_id=payload.debtor_id,
        beneficiary_person_id=payload.beneficiary_person_id,
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
    exclude_ids: list[int] | None = None,
) -> Optional[Purchase]:
    normalized_input = normalize_purchase_description(description=description)
    stmt = select(Purchase).where(
        Purchase.card_id == card_id,
        Purchase.purchase_date == purchase_date,
        Purchase.currency == currency,
        Purchase.installments_total == installments_total,
    )

    candidates = list(session.exec(stmt))
    if exclude_ids:
        candidates = [c for c in candidates if c.id not in exclude_ids]
    
    # helper to check if amount is close enough (centavos)
    def amount_matches(p: Purchase) -> bool:
        diff = abs(p.installment_amount_original - installment_amount_original)
        relative_diff = diff / installment_amount_original if installment_amount_original != 0 else 0
        return diff <= 0.01 or relative_diff <= 0.01

    # Pass 1: Exact normalized description match
    for c in candidates:
        if normalize_purchase_description(description=c.description) == normalized_input:
            if amount_matches(c):
                return c
                
    # Pass 2: Fuzzy match (no description check)
    # If we have only ONE candidate for this date, card, currency, and amount,
    # assume it is the same purchase even if the description differs (supports manual custom names).
    matching_amounts = [c for c in candidates if amount_matches(c)]
    if len(matching_amounts) == 1:
        return matching_amounts[0]

    return None



def export_dashboard_to_excel(*, session: Session, year_month: str) -> bytes:
    """Generates an Excel file with dashboard data for a given month."""
    import pandas as pd
    import io

    # 1. Monthly Balance
    balance = calculate_monthly_balance(session=session, year_month=year_month)
    df_balance = pd.DataFrame([balance]) if balance else pd.DataFrame()

    # 2. Transfers
    transfers_data = calculate_transfers(session=session, year_month=year_month)
    df_transfers = pd.DataFrame(transfers_data["transferencias"]) if transfers_data and "transferencias" in transfers_data else pd.DataFrame()
    df_gastos = pd.DataFrame(transfers_data["gastos_por_persona"]) if transfers_data and "gastos_por_persona" in transfers_data else pd.DataFrame()

    # 3. Purchase Details (Month Breakdown)
    total_ars, items = report_month_breakdown(session=session, year_month=year_month)
    breakdown_rows = []
    for p, sch, amt, debtor_name, payer_name, card_name in items:
        breakdown_rows.append({
            "Fecha": p.purchase_date,
            "Descripción": p.description,
            "Detalle": p.notes,
            "Categoría": p.category,
            "Pagador": payer_name,
            "Tarjeta": card_name or "-",
            "Cuota": f"{sch.installment_index}/{p.installments_total}",
            "Monto (ARS)": amt,
            "Deudor": debtor_name,
            "Saldado": "Sí" if p.debt_settled else ("No" if p.debtor_id else "-")
        })
    df_breakdown = pd.DataFrame(breakdown_rows)

    # 4. Debts
    debts = report_debts(session=session)
    df_debts = pd.DataFrame([
        {
            "Deudor": d_name,
            "Pendiente": owed,
            "Pagado": settled,
            "Pendientes (#)": count
        }
        for _, d_name, owed, settled, count in debts
    ])

    # 5. Next Month Forecast
    try:
        from datetime import datetime
        from dateutil.relativedelta import relativedelta
        dt = datetime.strptime(year_month, "%Y-%m")
        next_month = (dt + relativedelta(months=1)).strftime("%Y-%m")
        total_next, items_next = report_month_breakdown(session=session, year_month=next_month)
        next_rows = []
        for p, sch, amt, debtor_name, payer_name, card_name in items_next:
            next_rows.append({
                "Fecha": p.purchase_date,
                "Descripción": p.description,
                "Cuota": f"{sch.installment_index}/{p.installments_total}",
                "Monto (ARS)": amt,
                "Deudor": debtor_name
            })
        df_next = pd.DataFrame(next_rows)
        # Add a summary row for next month
        if not df_next.empty:
            summary_row = pd.DataFrame([{"Descripción": "TOTAL ESTIMADO", "Monto (ARS)": total_next}])
            df_next = pd.concat([df_next, summary_row], ignore_index=True)
    except Exception:
        df_next = pd.DataFrame()

    # Write to memory
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        if not df_balance.empty:
            df_balance.to_excel(writer, sheet_name="Balance", index=False)
        if not df_gastos.empty:
            df_gastos.to_excel(writer, sheet_name="Gastos por Persona", index=False)
        if not df_transfers.empty:
            df_transfers.to_excel(writer, sheet_name="Transferencias", index=False)
        if not df_breakdown.empty:
            df_breakdown.to_excel(writer, sheet_name="Detalle del Mes", index=False)
        if not df_next.empty:
            df_next.to_excel(writer, sheet_name="Mes Siguiente", index=False)
        if not df_debts.empty:
            df_debts.to_excel(writer, sheet_name="Deudas de Terceros", index=False)

    return output.getvalue()


def find_card_by_holder(
    *, session: Session, holder_name: str, last4: Optional[str] = None
) -> Optional[Card]:
    """
    Busca la Card más probable dado el nombre del titular extraído del resumen.

    Normaliza los nombres quitando acentos y comparando en minúsculas.
    Retorna la Card si hay exactamente 1 coincidencia; None si hay 0 o más de 1 (ambiguo).
    """
    import unicodedata

    def _normalize(s: str) -> str:
        s = unicodedata.normalize("NFD", s.lower())
        return "".join(c for c in s if unicodedata.category(c) != "Mn").strip()

    holder_norm = _normalize(holder_name)
    holder_words = set(holder_norm.split())

    persons = list(session.exec(select(Person)).all())
    cards = list(session.exec(select(Card)).all())

    person_map = {p.id: p for p in persons if p.id is not None}

    matched: list[Card] = []
    for card in cards:
        person = person_map.get(card.owner_person_id)
        if person is None:
            continue
        person_norm = _normalize(person.name)
        person_words = set(person_norm.split())

        # Match si alguna palabra del nombre de la persona aparece en el titular del resumen
        if not person_words.intersection(holder_words):
            continue

        # Si hay last4 disponible en ambos lados, usarlo para desempatar o confirmar
        if last4 and card.last4:
            if card.last4 != last4:
                continue  # last4 no coincide: descartar

        matched.append(card)

    if len(matched) == 1:
        return matched[0]
    return None


def list_import_batches(*, session: Session) -> list[ImportBatch]:
    stmt = select(ImportBatch).order_by(ImportBatch.imported_at.desc())
    return list(session.exec(stmt).all())


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
    import_batch_id: Optional[int] = None,
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

    # Import batch filter
    if import_batch_id is not None:
        stmt = stmt.where(Purchase.import_batch_id == import_batch_id)

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


def bulk_update_purchases(*, session: Session, payload: schemas.BulkPurchaseUpdate) -> int:
    """Updates multiple purchases in one transaction. Returns number of updated rows."""
    count = 0
    for pid in payload.purchase_ids:
        try:
            update_purchase(session=session, purchase_id=pid, payload=payload.update)
            count += 1
        except ValueError:
            continue
    return count


def delete_purchase(*, session: Session, purchase_id: int) -> None:
    """Delete a purchase and all its related installments and payers.

    Uses explicit raw SQL deletes instead of SQLModel cascade because SQLite's
    cascade-on-delete requires the FK to be declared with ON DELETE CASCADE at the
    DDL level, which SQLModel doesn't emit by default. If a new child table is ever
    added (e.g. attachments), remember to add its DELETE here before the parent row.
    """
    from sqlalchemy import text as sa_text
    purchase = session.get(Purchase, purchase_id)
    if purchase is None:
        raise ValueError(f"Purchase {purchase_id} not found")
    # Delete children before parent to satisfy FK constraints
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


def _fx_rate_map(*, session: Session) -> dict[tuple[str, CurrencyCode], float]:
    rates = list_fx_rates(session=session)
    return {(r.year_month, r.currency): float(r.rate_to_ars) for r in rates if r.id is not None}


def _allocate_amount_to_person(*, amount_ars: float, payers: list[PurchasePayer], person_id: int) -> float:
    """Allocate an installment amount to a specific person based on their payer shares."""
    allocated = 0.0
    for payer in payers:
        if payer.person_id != person_id:
            continue
        if payer.share_type == ShareType.PERCENT:
            allocated += amount_ars * (float(payer.share_value) / 100.0)
        else:
            allocated += float(payer.share_value)
    return allocated


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
            amount_ars = _allocate_amount_to_person(
                amount_ars=amount_ars, payers=payer_map.get(sch.purchase_id, []), person_id=person_id
            )

        totals[sch.year_month] = float(totals.get(sch.year_month, 0.0) + amount_ars)

    return [(ym, round(total, 2)) for ym, total in sorted(totals.items(), key=lambda x: x[0])]


def report_month_breakdown(
    *,
    session: Session,
    year_month: str,
    card_id: Optional[int] = None,
    person_id: Optional[int] = None,
    is_common: Optional[bool] = None,
) -> tuple[float, list[tuple[Purchase, InstallmentSchedule, float, Optional[str], str, Optional[str]]]]:
    """
    Desglose de cuotas que vencen en un mes dado.
    Returns (total_ars, list of (purchase, schedule, amount_ars, debtor_name, payer_name, card_name)).
    """
    fx_map = _fx_rate_map(session=session)

    OwnerPerson = aliased(Person)
    stmt = (
        select(InstallmentSchedule, Purchase, Debtor, Card, OwnerPerson)
        .join(Purchase, Purchase.id == InstallmentSchedule.purchase_id)
        .outerjoin(Debtor, Debtor.id == Purchase.debtor_id)
        .outerjoin(Card, Card.id == Purchase.card_id)
        .outerjoin(OwnerPerson, OwnerPerson.id == Purchase.owner_person_id)
        .where(InstallmentSchedule.year_month == year_month)
    )
    if card_id is not None:
        stmt = stmt.where(Purchase.card_id == card_id)
    if is_common is not None:
        stmt = stmt.where(Purchase.is_common == is_common)

    results = list(session.exec(stmt))

    payer_map: dict[int, list[PurchasePayer]] = {}
    if person_id is not None:
        payers = list(session.exec(select(PurchasePayer).where(PurchasePayer.person_id == person_id)))
        for p in payers:
            payer_map.setdefault(p.purchase_id, []).append(p)

    items: list[tuple[Purchase, InstallmentSchedule, float, Optional[str], str, Optional[str]]] = []
    total_ars = 0.0

    for sch, purchase, debtor, card, owner in results:
        debtor_name = debtor.name if debtor else None
        
        # Determine payer name
        if owner:
            payer_name = owner.name
        elif card:
            card_owner = session.get(Person, card.owner_person_id)
            payer_name = card_owner.name if card_owner else "Desconocido"
        else:
            payer_name = "Desconocido"
            
        card_name = card.name if card else None
        
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
                actual_owner_id = purchase.owner_person_id if purchase.owner_person_id is not None else (card.owner_person_id if card else None)
                if actual_owner_id != person_id:
                    amount_ars = 0.0
                # else: amount_ars remains the same (100%)
            else:
                amount_ars = _allocate_amount_to_person(
                    amount_ars=amount_ars, payers=payers, person_id=person_id
                )

            if amount_ars == 0:
                continue

        total_ars += amount_ars
        items.append((purchase, sch, round(amount_ars, 2), debtor_name, payer_name, card_name))

    return (round(total_ars, 2), items)


def get_distinct_categories(*, session: Session) -> list[str]:
    """Return list of unique categories used in purchases (excluding NULL)."""
    stmt = select(Purchase.category).where(Purchase.category.is_not(None)).distinct()
    results = session.exec(stmt)
    categories = [cat for cat in results if cat is not None]
    return sorted(categories)


def report_spending_by_category(
    *,
    session: Session,
    card_id: Optional[int] = None,
    person_id: Optional[int] = None,
    year_month: Optional[str] = None,
    is_common: Optional[bool] = None,
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
    if year_month is not None:
        stmt = stmt.where(InstallmentSchedule.year_month == year_month)
    if is_common is not None:
        stmt = stmt.where(Purchase.is_common == is_common)

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
            amount_ars = _allocate_amount_to_person(
                amount_ars=amount_ars, payers=payer_map.get(sch.purchase_id, []), person_id=person_id
            )

        totals[cat_key] = float(totals.get(cat_key, 0.0) + amount_ars)

    return [(cat, round(total, 2)) for cat, total in sorted(totals.items(), key=lambda x: -x[1])]


def report_installment_timeline(
    *,
    session: Session,
    months_ahead: int = 12,
    months_behind: int = 3,
    card_id: Optional[int] = None,
    person_id: Optional[int] = None,
    is_common: Optional[bool] = None,
) -> list[tuple[str, float]]:
    """
    Return timeline of installments (year_month -> total_ars).
    Includes 3 months behind current month and 12 months ahead.
    """
    current_ym = to_year_month(date.today())
    start_ym = add_months(current_ym, -months_behind)
    end_ym = add_months(current_ym, months_ahead)

    fx_map = _fx_rate_map(session=session)

    # Query InstallmentSchedule filtered by year_month range
    stmt = select(InstallmentSchedule).where(
        InstallmentSchedule.year_month >= start_ym, InstallmentSchedule.year_month <= end_ym
    )

    # Ensure Purchase is joined if card_id or is_common filter is applied
    if card_id is not None or is_common is not None:
        stmt = stmt.join(Purchase, Purchase.id == InstallmentSchedule.purchase_id)
        if card_id is not None:
            stmt = stmt.where(Purchase.card_id == card_id)
        if is_common is not None:
            stmt = stmt.where(Purchase.is_common == is_common)

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
            amount_ars = _allocate_amount_to_person(
                amount_ars=amount_ars, payers=payer_map.get(sch.purchase_id, []), person_id=person_id
            )

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
    
    # Get total expenses for the month using FX conversion (same logic as report_month_breakdown)
    fx_map = _fx_rate_map(session=session)
    schedule_rows_balance = session.exec(
        select(InstallmentSchedule.amount_original, InstallmentSchedule.currency)
        .where(InstallmentSchedule.year_month == year_month)
    ).all()
    total_expenses = 0.0
    for amount_original, currency in schedule_rows_balance:
        if currency == CurrencyCode.ARS:
            total_expenses += float(amount_original)
        else:
            rate = fx_map.get((year_month, currency))
            if rate is not None:
                total_expenses += float(amount_original) * float(rate)
    
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
    # Create new income (allow multiple incomes per person/month)
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

    # Build FX rate map for USD→ARS conversion (same as report_month_breakdown)
    fx_map = _fx_rate_map(session=session)

    # Compute paid amounts per person for this month.
    # Rule:
    # - If Purchase has PurchasePayer rows, allocate the installment amount using those shares.
    # - Otherwise, allocate 100% to purchase.owner_person_id (default behavior).
    schedule_rows_raw = session.exec(
        select(
            InstallmentSchedule.purchase_id,
            InstallmentSchedule.amount_original,
            InstallmentSchedule.currency,
            Purchase.owner_person_id,
            Purchase.card_id,
            Purchase.is_common,
            Card.owner_person_id,
            Purchase.beneficiary_person_id,
        )
        .join(Purchase, Purchase.id == InstallmentSchedule.purchase_id)
        .outerjoin(Card, Card.id == Purchase.card_id)
        .where(InstallmentSchedule.year_month == year_month)
    ).all()

    # Convert each row's amount to ARS using fx_map; skip rows with no FX rate
    schedule_rows = []
    for pid, amount_original, currency, owner_pid, card_id, is_common, card_owner_pid, beneficiary_pid in schedule_rows_raw:
        if currency == CurrencyCode.ARS:
            amount_ars = float(amount_original)
        else:
            rate = fx_map.get((year_month, currency))
            if rate is None:
                continue
            amount_ars = float(amount_original) * float(rate)
        schedule_rows.append((pid, amount_ars, owner_pid, card_id, is_common, card_owner_pid, beneficiary_pid))

    total_expenses = sum(row[1] for row in schedule_rows)

    from collections import defaultdict
    paid_amount_by_person_id = defaultdict(float)
    common_paid_by_person_id = defaultdict(float)
    should_pay_by_person_id = defaultdict(float)
    
    # We need a name mapping for all people involved
    # Start with those who have income
    person_id_to_name = {inc["person_id"]: inc["person_name"] for inc in ingresos}
    
    # Also fetch names for anyone mentioned in purchases who might not have income
    all_involved_pids = set()
    for row in schedule_rows:
        # row: (pid, amount_ars, owner_pid, _cid, is_common, card_owner_pid, beneficiary_pid)
        owner_pid = row[2]
        card_owner_pid = row[5]
        beneficiary_pid = row[6]
        if owner_pid is not None: all_involved_pids.add(owner_pid)
        if card_owner_pid is not None: all_involved_pids.add(card_owner_pid)
        if beneficiary_pid is not None: all_involved_pids.add(beneficiary_pid)
    
    missing_pids = [pid for pid in all_involved_pids if pid not in person_id_to_name]
    if missing_pids:
        missing_people = session.exec(select(Person).where(Person.id.in_(missing_pids))).all()
        for p in missing_people:
            person_id_to_name[p.id] = p.name

    purchase_ids = sorted({pid for pid, *rest in schedule_rows})
    payers_by_purchase_id: dict[int, list[PurchasePayer]] = {}
    if purchase_ids:
        payers = list(session.exec(select(PurchasePayer).where(PurchasePayer.purchase_id.in_(purchase_ids))))
        for payer in payers:
            payers_by_purchase_id.setdefault(payer.purchase_id, []).append(payer)
            # Ensure name matches if missing
            if payer.person_id not in person_id_to_name:
                missing_p = session.exec(select(Person).where(Person.id == payer.person_id)).first()
                if missing_p:
                    person_id_to_name[missing_p.id] = missing_p.name

    income_by_person_id = defaultdict(float)
    for inc in ingresos:
        income_by_person_id[inc["person_id"]] += float(inc["amount"])

    # Calculate what each person should pay using the Common Pool logic:
    # 1. Target Base Take Home = (Total Income - Total Common Expenses) / num_people
    # 2. Target Cash = Target Base Take Home - Personal Expenses
    # 3. Should Pay = Income - Target Cash
    
    total_common_expenses = 0.0
    total_unassigned_personal = 0.0
    personal_expenses_by_person_id = defaultdict(float)

    for pid, amount_ars, owner_pid, _cid, is_common, card_owner_pid, beneficiary_pid in schedule_rows:
        inst_amt = float(amount_ars or 0.0)
        actual_payer_pid = owner_pid if owner_pid is not None else card_owner_pid

        if is_common:
            total_common_expenses += inst_amt
        else:
            expense_owner_pid = beneficiary_pid if beneficiary_pid is not None else actual_payer_pid
            if expense_owner_pid is not None:
                personal_expenses_by_person_id[expense_owner_pid] += inst_amt
            else:
                total_unassigned_personal += inst_amt

    all_people = session.exec(select(Person)).all()
    # Use only people with income for this month for the Common Pool split.
    # Counting all people would include inactive/test people not participating in the pool.
    num_total_people = len(set(inc["person_id"] for inc in ingresos)) or 1
    
    # Ensure all people are in the dictionaries
    for p in all_people:
        if p.id not in person_id_to_name:
            person_id_to_name[p.id] = p.name
        should_pay_by_person_id[p.id] = 0.0
        paid_amount_by_person_id[p.id] = 0.0
        common_paid_by_person_id[p.id] = 0.0

    target_base_take_home = (total_ingresos - total_common_expenses) / num_total_people if num_total_people > 0 else 0.0

    for p in all_people:
        income = income_by_person_id.get(p.id, 0.0)
        personal_expense = personal_expenses_by_person_id.get(p.id, 0.0)
        target_cash = target_base_take_home - personal_expense
        should_pay_by_person_id[p.id] = income - target_cash
    
    # Calculate who paid what
    for pid, amount_ars, owner_pid, _cid, is_common, card_owner_pid, beneficiary_pid in schedule_rows:
        inst_amt = float(amount_ars or 0.0)

        payers = payers_by_purchase_id.get(pid, [])
        if payers:
            for p in payers:
                if p.share_type == ShareType.PERCENT:
                    amt = inst_amt * (p.share_value / 100.0)
                else:
                    amt = p.share_value
                paid_amount_by_person_id[p.person_id] += amt
                if is_common:
                    common_paid_by_person_id[p.person_id] += amt
        else:
            actual_payer_pid = owner_pid if owner_pid is not None else card_owner_pid
            if actual_payer_pid is not None:
                paid_amount_by_person_id[actual_payer_pid] += inst_amt
                if is_common:
                    common_paid_by_person_id[actual_payer_pid] += inst_amt
    
    # Get internal debt transfers for the month
    PersonFrom = aliased(Person)
    PersonTo = aliased(Person)
    
    internal_transfers = list(session.exec(
        select(DebtTransfer, PersonFrom.name.label("from_name"), PersonTo.name.label("to_name"))
        .join(PersonFrom, PersonFrom.id == DebtTransfer.from_person_id)
        .join(PersonTo, PersonTo.id == DebtTransfer.to_person_id)
        .where(DebtTransfer.year_month == year_month)
    ).all())
    
    # Map internal transfers to persons
    internal_sent = defaultdict(float)
    internal_received = defaultdict(float)
    transferencias_internas_rows = []
    
    for dt, from_name, to_name in internal_transfers:
        internal_sent[dt.from_person_id] += float(dt.amount)
        internal_received[dt.to_person_id] += float(dt.amount)
        transferencias_internas_rows.append(
            schemas.DebtTransferRead(
                id=dt.id,
                from_person_id=dt.from_person_id,
                from_person_name=from_name,
                to_person_id=dt.to_person_id,
                to_person_name=to_name,
                year_month=dt.year_month,
                amount=float(dt.amount),
                transfer_date=dt.transfer_date,
                notes=dt.notes
            )
        )

    gastos_por_persona = []
    for person_id in sorted(person_id_to_name.keys()):
        paid_amount = float(paid_amount_by_person_id[person_id])
        common_paid = float(common_paid_by_person_id[person_id])
        should_pay = float(should_pay_by_person_id[person_id])
        income = income_by_person_id.get(person_id, 0.0)
        common_should_pay = income - target_base_take_home

        # Adjust difference with internal transfers
        # (paid - should_pay) + sent - received
        initial_diff = paid_amount - should_pay
        adjustment = internal_sent[person_id] - internal_received[person_id]
        difference = initial_diff + adjustment

        gastos_por_persona.append({
            "person_id": person_id,
            "person_name": person_id_to_name[person_id],
            "paid_amount": round(paid_amount, 2),
            "common_paid": round(common_paid, 2),
            "common_should_pay": round(common_should_pay, 2),
            "should_pay": round(should_pay, 2),
            "adjustment": round(adjustment, 2),
            "difference": round(difference, 2),
        })

    balance_delta = round(sum(gp["difference"] for gp in gastos_por_persona), 2)
    is_balanced = abs(balance_delta) <= 0.01
    
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
    
    total_personal = sum(personal_expenses_by_person_id.values()) + total_unassigned_personal
    return {
        "year_month": year_month,
        "ingresos": ingresos,
        "total_ingresos": total_ingresos,
        "total_common_expenses": round(total_common_expenses, 2),
        "total_personal_expenses": round(total_personal, 2),
        "gastos_por_persona": gastos_por_persona,
        "transferencias": transferencias,
        "is_balanced": is_balanced,
        "balance_delta": balance_delta,
        "transferencias_internas": transferencias_internas_rows
    }


def create_debt_transfer(*, session: Session, payload: schemas.DebtTransferCreate) -> DebtTransfer:
    transfer = DebtTransfer(
        from_person_id=payload.from_person_id,
        to_person_id=payload.to_person_id,
        year_month=payload.year_month,
        amount=payload.amount,
        transfer_date=payload.transfer_date,
        notes=payload.notes
    )
    session.add(transfer)
    session.commit()
    session.refresh(transfer)
    return transfer


def list_debt_transfers(*, session: Session, year_month: Optional[str] = None) -> list[DebtTransfer]:
    query = select(DebtTransfer).order_by(DebtTransfer.transfer_date.desc())
    if year_month:
        query = query.where(DebtTransfer.year_month == year_month)
    return list(session.exec(query))


def delete_debt_transfer(*, session: Session, transfer_id: int) -> None:
    transfer = session.get(DebtTransfer, transfer_id)
    if transfer is None:
        raise ValueError(f"DebtTransfer {transfer_id} not found")
    session.delete(transfer)
    session.commit()


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------

def create_category(*, session: Session, payload: CategoryCreate) -> Category:
    category = Category(name=payload.name, color=payload.color)
    session.add(category)
    session.commit()
    session.refresh(category)
    return category


def list_categories(*, session: Session) -> list[Category]:
    return list(session.exec(select(Category).order_by(Category.name)))


def update_category(*, session: Session, category_id: int, payload: CategoryUpdate) -> Category:
    category = session.get(Category, category_id)
    if category is None:
        raise ValueError(f"Category {category_id} not found")

    old_name = category.name
    new_data = payload.model_dump(exclude_unset=True)
    
    for field, value in new_data.items():
        setattr(category, field, value)
    
    # If name changed, update all purchases with the old name
    if "name" in new_data and new_data["name"] != old_name:
        stmt = select(Purchase).where(Purchase.category == old_name)
        purchases = session.exec(stmt).all()
        for p in purchases:
            p.category = new_data["name"]
            session.add(p)
            
    session.add(category)
    session.commit()
    session.refresh(category)
    return category


def delete_category(*, session: Session, category_id: int) -> None:
    category = session.get(Category, category_id)
    if category is None:
        raise ValueError(f"Category {category_id} not found")
    
    # Purchases with this category will set it to "Sin clasificar" or NULL?
    # Requirement: "ponle 'sin clasificar'" if you don't know the name.
    # Let's set it to None when deleting the category record.
    stmt = select(Purchase).where(Purchase.category == category.name)
    purchases = session.exec(stmt).all()
    for p in purchases:
        p.category = None
        session.add(p)
    
    session.delete(category)
    session.commit()


import re as _re
from collections import Counter as _Counter, defaultdict as _defaultdict

# --- Inference helpers ---

_CUIL_RE = _re.compile(r'(?:CUIT|CUIL)\s+(\d{11}|\d{2}-\d{8}-\d)', _re.IGNORECASE)
_LEADING_NUM_RE = _re.compile(r'^\d{5,}\s+')
_INSTALLMENT_RE = _re.compile(r'C\.\d+/\d+|\b\d+ de \d+\b', _re.IGNORECASE)
_TRAILING_CODE_RE = _re.compile(r'\s+[A-Z0-9]{3,}\s*$')

# Categories that are too generic to learn patterns from (avoid polluting the map)
_SKIP_LEARNING_CATS = {"OTROS - VARIOS", "Sin categoría"}

# Keyword rules mapped to actual category names used in the DB
_KEYWORD_RULES: list[tuple[str, list[str]]] = [
    ("Supermercado", ["COTO", "CARREFOUR", "JUMBO", "DISCO", "VEA", "DIA ", "LA ANONIMA", "WALMART", "LIBERTAD", "MASONLINE", "HIPERMERCADO", "CHANGOMAS", "MAKRO"]),
    ("Combustible", ["YPF", "SHELL", "AXION", "PETROBRAS", "PUMA ENERGY", "SHELLBOX"]),
    ("Servicios", ["AYSA", "EDESUR", "EDENOR", "METROGAS", "EPEC", "CLARO", "MOVISTAR", "PERSONAL FLOW", "CABLEVISION", "TELECENTRO", "NETFLIX", "SPOTIFY", "DISNEY", "OPENAI", "CHATGPT", "GOOGLE ", "YOUTUBE", "PAGOS360", "ADT SECURITY", "PAGO TIC"]),
    ("Peaje", ["CAMINOS DE LAS", "TELEPEAJE", "AUTOPISTA", "PEAJE"]),
    ("Seguros", ["SEGUROS", "CHUBB", "SMG CIA", "BINA SEGUROS", "FEDERACION PATRONAL"]),
    ("Mascotas", ["VETERINARIA", "PETSHOP", "PET SHOP", "VETERINARIO"]),
    ("Impuestos", ["AFIP", "ARBA", "AGIP", "RENTAS", "IMPUESTO", "CORDOBA.GOB.AR", "ANSES", "SENASA"]),
    ("Préstamos", ["PRESTAMO", "CUOTA PRESTAMO"]),
    ("Autos", ["NEUMATICOS", "GOMERIA", "LUBRICENTRO", "TALLER MECANICO", "AUTOMOTORES", "REPUESTO"]),
    ("Verdulería", ["VERDULERIA", "FRUTERIA", "FRUTAS Y VERDURAS"]),
    ("Carnicería", ["CARNICERIA", "CARNES", "FRIGORIFICO", "FRIGORÍFICO"]),
    ("Regalos", ["TOY STORE", "JUGUETERIA", "JUGUETES"]),
    ("Transporte", ["SUBE", "UBER", "CABIFY", "DIDI", "RAPPI", "PEDIDOSYA"]),
    ("Salud", ["OSDE", "SWISS MEDICAL", "FARMACIA", "LABORATORIO", "MEDICO", "CLINICA"]),
    ("Educación", ["COLEGIO", "UNIVERSIDAD", "LIBRERIA", "CUOTA COLEGIO"]),
    ("Entretenimiento", ["CINEMA", "TEATRO", "CINE", "BOLICHE", "PARQUE"]),
    ("Hogar", ["EASY", "SODIMAC", "FERRETERIA", "BLANQUERIA", "IKEA"]),
]


def _extract_cuil(desc: str) -> str | None:
    """Extract CUIL/CUIT number from description, or None if not found."""
    m = _CUIL_RE.search(desc)
    if m:
        return _re.sub(r"-", "", m.group(1))
    return None


def _normalize_desc_for_inference(desc: str) -> str:
    """Normalize description to a stable key for pattern matching."""
    d = _LEADING_NUM_RE.sub("", desc)
    d = _INSTALLMENT_RE.sub("", d)
    # Remove trailing numeric codes (comprobante numbers, PIN codes, etc.)
    d = _re.sub(r"\s+[\d\s\-]{4,}$", "", d)
    return d.strip().upper()


def _build_inference_maps(session: Session) -> tuple[dict[str, str], dict[str, str]]:
    """
    Build two inference maps from existing categorized purchases:
    - cuil_map: CUIL/CUIT string → most common category for that CUIL
    - desc_map: normalized description → most common category
    Skips generic categories (OTROS - VARIOS) to avoid polluting the maps.
    """
    all_categorized = session.exec(
        select(Purchase).where(
            (Purchase.category != None)
            & (Purchase.category != "Sin categoría")
        )
    ).all()

    cuil_cats: dict[str, list[str]] = _defaultdict(list)
    desc_cats: dict[str, list[str]] = _defaultdict(list)

    for p in all_categorized:
        if p.category in _SKIP_LEARNING_CATS:
            continue
        cuil = _extract_cuil(p.description)
        if cuil:
            cuil_cats[cuil].append(p.category)
        norm = _normalize_desc_for_inference(p.description)
        if norm and len(norm) > 3:
            desc_cats[norm].append(p.category)

    cuil_map = {cuil: _Counter(cats).most_common(1)[0][0] for cuil, cats in cuil_cats.items()}
    desc_map = {desc: _Counter(cats).most_common(1)[0][0] for desc, cats in desc_cats.items()}
    return cuil_map, desc_map


def auto_categorize_purchases(*, session: Session) -> int:
    """
    Assign categories to uncategorized purchases using 3-tier inference:
    1. CUIT/CUIL match: if a CUIT was previously categorized, reuse that category
    2. Normalized description match: if description pattern was categorized before, reuse
    3. Keyword rules: hardcoded keyword → category mapping
    Returns the number of updated purchases.
    """
    cuil_map, desc_map = _build_inference_maps(session)

    uncategorized = session.exec(
        select(Purchase).where(
            (Purchase.category == None) | (Purchase.category == "Sin categoría")
        )
    ).all()

    count = 0
    for p in uncategorized:
        found_cat = None

        # Tier 1: CUIT/CUIL match
        cuil = _extract_cuil(p.description)
        if cuil and cuil in cuil_map:
            found_cat = cuil_map[cuil]

        # Tier 2: Normalized description match
        if not found_cat:
            norm = _normalize_desc_for_inference(p.description)
            if norm in desc_map:
                found_cat = desc_map[norm]

        # Tier 3: Keyword rules
        if not found_cat:
            desc_upper = p.description.upper()
            for cat_name, keywords in _KEYWORD_RULES:
                if any(k.upper() in desc_upper for k in keywords):
                    found_cat = cat_name
                    break

        if found_cat:
            p.category = found_cat
            session.add(p)
            count += 1

    if count > 0:
        session.commit()

    return count


def get_categorization_rules(*, session: Session) -> dict:
    """
    Return the learned categorization rules derived from existing purchases,
    plus the hardcoded keyword rules.
    """
    cuil_map, desc_map = _build_inference_maps(session)

    # Enrich CUIL rules with occurrence counts
    all_categorized = session.exec(
        select(Purchase).where(
            (Purchase.category != None) & (Purchase.category != "Sin categoría")
        )
    ).all()

    cuil_counts: dict[str, list[str]] = _defaultdict(list)
    desc_counts: dict[str, list[str]] = _defaultdict(list)
    for p in all_categorized:
        if p.category in _SKIP_LEARNING_CATS:
            continue
        cuil = _extract_cuil(p.description)
        if cuil:
            cuil_counts[cuil].append(p.category)
        norm = _normalize_desc_for_inference(p.description)
        if norm and len(norm) > 3:
            desc_counts[norm].append(p.category)

    learned_cuil = [
        {"pattern": cuil, "type": "cuil", "category": cat, "occurrences": len(cuil_counts[cuil])}
        for cuil, cat in cuil_map.items()
    ]
    learned_desc = [
        {"pattern": desc, "type": "description", "category": cat, "occurrences": len(desc_counts[desc])}
        for desc, cat in desc_map.items()
    ]
    keyword_rules = [
        {"category": cat, "type": "keyword", "keywords": kws}
        for cat, kws in _KEYWORD_RULES
    ]

    return {
        "learned_cuil": sorted(learned_cuil, key=lambda x: -x["occurrences"]),
        "learned_descriptions": sorted(learned_desc, key=lambda x: -x["occurrences"]),
        "keyword_rules": keyword_rules,
    }


def detect_recurring_expenses(
    *, session: Session, min_occurrences: int = 3
) -> list[dict]:
    """
    Detect recurring expenses: distinct purchases with the same normalized
    description appearing in min_occurrences or more different months.
    Returns list of dicts with description, occurrences count, months list,
    average amount, and category.
    """
    purchases = list(
        session.exec(
            select(Purchase).order_by(Purchase.purchase_date.desc())
        )
    )

    from collections import defaultdict

    # Group by normalized description
    groups: dict[str, list[Purchase]] = defaultdict(list)
    for p in purchases:
        key = normalize_purchase_description(description=p.description)
        groups[key].append(p)

    results: list[dict] = []
    for norm_desc, group in groups.items():
        # Count distinct months (by purchase_date, not installments)
        distinct_months = set()
        for p in group:
            distinct_months.add(to_year_month(p.purchase_date))

        if len(distinct_months) < min_occurrences:
            continue

        # Use original description from most recent purchase
        latest = group[0]
        avg_amount = sum(p.amount_original for p in group) / len(group)
        months_sorted = sorted(distinct_months, reverse=True)

        results.append({
            "description": latest.description,
            "category": latest.category,
            "currency": latest.currency.value,
            "occurrences": len(distinct_months),
            "total_purchases": len(group),
            "avg_amount": round(avg_amount, 2),
            "months": months_sorted,
            "last_seen": months_sorted[0],
        })

    results.sort(key=lambda x: x["occurrences"], reverse=True)
    return results



# --- FamilyGoal CRUD ---

def create_family_goal(*, session: Session, payload: FamilyGoalCreate) -> FamilyGoal:
    goal = FamilyGoal(**payload.model_dump())
    session.add(goal)
    session.commit()
    session.refresh(goal)
    return goal


def list_family_goals(*, session: Session) -> list[FamilyGoal]:
    stmt = select(FamilyGoal).order_by(
        col(FamilyGoal.is_completed).asc(),
        col(FamilyGoal.id).asc(),
    )
    return list(session.exec(stmt).all())


def update_family_goal(*, session: Session, goal_id: int, payload: FamilyGoalUpdate) -> FamilyGoal:
    goal = session.get(FamilyGoal, goal_id)
    if goal is None:
        raise ValueError(f"FamilyGoal {goal_id} not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(goal, field, value)
    session.add(goal)
    session.commit()
    session.refresh(goal)
    return goal


def delete_family_goal(*, session: Session, goal_id: int) -> None:
    goal = session.get(FamilyGoal, goal_id)
    if goal is None:
        raise ValueError(f"FamilyGoal {goal_id} not found")
    session.delete(goal)
    session.commit()


# --- Saving CRUD ---

def list_savings(*, session: Session) -> list[tuple[Saving, float | None, date | None]]:
    """Returns list of (Saving, current_amount, current_amount_date) tuples.
    current_amount and date come from the most recent SavingSnapshot per saving.
    """
    from sqlalchemy import select as sa_select, func as sa_func

    latest_snapshot_subq = (
        sa_select(
            SavingSnapshot.saving_id,
            sa_func.max(SavingSnapshot.date).label("max_date"),
        )
        .group_by(SavingSnapshot.saving_id)
        .subquery()
    )

    stmt = (
        select(Saving, SavingSnapshot.amount, SavingSnapshot.date)
        .outerjoin(
            latest_snapshot_subq,
            Saving.id == latest_snapshot_subq.c.saving_id,
        )
        .outerjoin(
            SavingSnapshot,
            (SavingSnapshot.saving_id == latest_snapshot_subq.c.saving_id)
            & (SavingSnapshot.date == latest_snapshot_subq.c.max_date),
        )
        .order_by(Saving.id)
    )
    return list(session.exec(stmt).all())  # type: ignore[return-value]


def create_saving(*, session: Session, payload: SavingCreate) -> Saving:
    person = session.get(Person, payload.person_id)
    if person is None:
        raise ValueError("Person not found")
    saving = Saving(
        person_id=payload.person_id,
        investment_type=payload.investment_type,
        institution=payload.institution,
        currency=payload.currency,
        notes=payload.notes,
    )
    session.add(saving)
    session.commit()
    session.refresh(saving)
    return saving


def update_saving(*, session: Session, saving_id: int, payload: SavingUpdate) -> Saving:
    saving = session.get(Saving, saving_id)
    if saving is None:
        raise ValueError(f"Saving {saving_id} not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(saving, field, value)
    session.add(saving)
    session.commit()
    session.refresh(saving)
    return saving


def delete_saving(*, session: Session, saving_id: int) -> None:
    """Delete a saving and all its snapshots (manual cascade)."""
    from sqlalchemy import text as sa_text
    saving = session.get(Saving, saving_id)
    if saving is None:
        raise ValueError(f"Saving {saving_id} not found")
    session.exec(sa_text("DELETE FROM savingsnapshot WHERE saving_id = :sid").bindparams(sid=saving_id))  # type: ignore[call-overload]
    session.exec(sa_text("DELETE FROM saving WHERE id = :sid").bindparams(sid=saving_id))  # type: ignore[call-overload]
    session.commit()


def list_saving_snapshots(*, session: Session, saving_id: int) -> list[SavingSnapshot]:
    stmt = (
        select(SavingSnapshot)
        .where(SavingSnapshot.saving_id == saving_id)
        .order_by(SavingSnapshot.date.asc())
    )
    return list(session.exec(stmt).all())


def create_saving_snapshot(*, session: Session, saving_id: int, payload: SavingSnapshotCreate) -> SavingSnapshot:
    saving = session.get(Saving, saving_id)
    if saving is None:
        raise ValueError(f"Saving {saving_id} not found")
    snapshot = SavingSnapshot(
        saving_id=saving_id,
        date=payload.date,
        amount=payload.amount,
    )
    session.add(snapshot)
    session.commit()
    session.refresh(snapshot)
    return snapshot


def delete_saving_snapshot(*, session: Session, snapshot_id: int) -> None:
    snapshot = session.get(SavingSnapshot, snapshot_id)
    if snapshot is None:
        raise ValueError(f"SavingSnapshot {snapshot_id} not found")
    session.delete(snapshot)
    session.commit()

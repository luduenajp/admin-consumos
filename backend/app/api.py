from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException

from app.crud import (
    create_card,
    create_person,
    create_purchase,
    list_cards,
    list_fx_rates,
    list_people,
    list_purchases,
    report_monthly_totals_converted,
    upsert_fx_rate,
)
from app.db import get_session
from app.schemas import (
    CardCreate,
    CardRead,
    FxRateRead,
    FxRateUpsert,
    PersonCreate,
    PersonRead,
    PurchaseCreate,
    PurchaseRead,
    ReportMonthlyRow,
)

router = APIRouter()


@router.get("/people", response_model=list[PersonRead])
def get_people() -> list[PersonRead]:
    with get_session() as session:
        people = list_people(session=session)
        return [PersonRead(id=p.id, name=p.name) for p in people if p.id is not None]


@router.post("/people", response_model=PersonRead)
def post_person(payload: PersonCreate) -> PersonRead:
    with get_session() as session:
        person = create_person(session=session, payload=payload)
        if person.id is None:
            raise HTTPException(status_code=500, detail="Failed to create person")
        return PersonRead(id=person.id, name=person.name)


@router.get("/cards", response_model=list[CardRead])
def get_cards() -> list[CardRead]:
    with get_session() as session:
        cards = list_cards(session=session)
        return [
            CardRead(
                id=c.id,
                name=c.name,
                provider=c.provider,
                owner_person_id=c.owner_person_id,
                last4=c.last4,
            )
            for c in cards
            if c.id is not None
        ]


@router.post("/cards", response_model=CardRead)
def post_card(payload: CardCreate) -> CardRead:
    with get_session() as session:
        card = create_card(session=session, payload=payload)
        if card.id is None:
            raise HTTPException(status_code=500, detail="Failed to create card")
        return CardRead(
            id=card.id,
            name=card.name,
            provider=card.provider,
            owner_person_id=card.owner_person_id,
            last4=card.last4,
        )


@router.get("/purchases", response_model=list[PurchaseRead])
def get_purchases(year_month: Optional[str] = None) -> list[PurchaseRead]:
    with get_session() as session:
        purchases = list_purchases(session=session, year_month=year_month)
        out: list[PurchaseRead] = []
        for p in purchases:
            if p.id is None:
                continue
            out.append(
                PurchaseRead(
                    id=p.id,
                    card_id=p.card_id,
                    purchase_date=p.purchase_date,
                    description=p.description,
                    currency=p.currency,
                    amount_original=p.amount_original,
                    installments_total=p.installments_total,
                    installment_amount_original=p.installment_amount_original,
                    first_installment_month=p.first_installment_month,
                    owner_person_id=p.owner_person_id,
                    category=p.category,
                    notes=p.notes,
                    is_refund=p.is_refund,
                )
            )
        return out


@router.post("/purchases", response_model=PurchaseRead)
def post_purchase(payload: PurchaseCreate) -> PurchaseRead:
    with get_session() as session:
        try:
            purchase = create_purchase(session=session, payload=payload)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

        if purchase.id is None:
            raise HTTPException(status_code=500, detail="Failed to create purchase")

        return PurchaseRead(
            id=purchase.id,
            card_id=purchase.card_id,
            purchase_date=purchase.purchase_date,
            description=purchase.description,
            currency=purchase.currency,
            amount_original=purchase.amount_original,
            installments_total=purchase.installments_total,
            installment_amount_original=purchase.installment_amount_original,
            first_installment_month=purchase.first_installment_month,
            owner_person_id=purchase.owner_person_id,
            category=purchase.category,
            notes=purchase.notes,
            is_refund=purchase.is_refund,
        )


@router.get("/reports/monthly", response_model=list[ReportMonthlyRow])
def get_report_monthly(card_id: Optional[int] = None, person_id: Optional[int] = None) -> list[ReportMonthlyRow]:
    with get_session() as session:
        rows = report_monthly_totals_converted(session=session, card_id=card_id, person_id=person_id)
        return [ReportMonthlyRow(year_month=ym, total_ars=total) for ym, total in rows]


@router.get("/fx", response_model=list[FxRateRead])
def get_fx_rates() -> list[FxRateRead]:
    with get_session() as session:
        rates = list_fx_rates(session=session)
        out: list[FxRateRead] = []
        for r in rates:
            if r.id is None:
                continue
            out.append(
                FxRateRead(
                    id=r.id,
                    year_month=r.year_month,
                    currency=r.currency,
                    rate_to_ars=float(r.rate_to_ars),
                )
            )
        return out


@router.post("/fx", response_model=FxRateRead)
def post_fx_rate(payload: FxRateUpsert) -> FxRateRead:
    with get_session() as session:
        fx = upsert_fx_rate(session=session, payload=payload)
        if fx.id is None:
            raise HTTPException(status_code=500, detail="Failed to upsert fx")
        return FxRateRead(
            id=fx.id,
            year_month=fx.year_month,
            currency=fx.currency,
            rate_to_ars=float(fx.rate_to_ars),
        )

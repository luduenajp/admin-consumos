from __future__ import annotations

import math
from datetime import date
from typing import Optional

from fastapi import APIRouter, HTTPException, Response
from sqlmodel import select

from app.crud import (
    bulk_update_purchases,
    calculate_monthly_balance,
    calculate_transfers,
    create_card,
    create_debtor,
    create_income,
    create_monthly_budget,
    create_person,
    create_purchase,
    export_dashboard_to_excel,
    get_distinct_categories,
    get_monthly_budget,
    list_cards,
    list_debtors,
    list_fx_rates,
    list_incomes,
    list_monthly_budgets,
    list_people,
    list_purchases,
    report_debts,
    report_installment_timeline,
    report_month_breakdown,
    report_monthly_totals_converted,
    report_spending_by_category,
    delete_purchase,
    update_purchase,
    upsert_fx_rate,
)
from app.db import get_session
from app.models import Person, PurchasePayer
from app.schemas import (
    BulkPurchaseUpdate,
    CardCreate,
    CardRead,
    CategoryRead,
    CategorySpendingRow,
    DebtorCreate,
    DebtorRead,
    DebtSummaryRow,
    FxRateRead,
    FxRateUpsert,
    MonthBreakdownResponse,
    MonthBreakdownRow,
    PaginatedResponse,
    PersonCreate,
    PersonRead,
    PurchaseCreate,
    PurchasePayerRead,
    PurchaseRead,
    PurchaseUpdate,
    ReportMonthlyRow,
    TimelineRow,
    MonthlyBudgetCreate,
    MonthlyBudgetRead,
    MonthlyBalanceResponse,
    IncomeCreate,
    IncomeRead,
    TransferCalculationResponse,
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
        try:
            card = create_card(session=session, payload=payload)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        if card.id is None:
            raise HTTPException(status_code=500, detail="Failed to create card")
        return CardRead(
            id=card.id,
            name=card.name,
            provider=card.provider,
            owner_person_id=card.owner_person_id,
            last4=card.last4,
        )


@router.get("/purchases", response_model=PaginatedResponse[PurchaseRead])
def get_purchases(
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
) -> PaginatedResponse[PurchaseRead]:
    with get_session() as session:
        purchases, total = list_purchases(
            session=session,
            year_month=year_month,
            category=category,
            start_date=start_date,
            end_date=end_date,
            min_amount=min_amount,
            max_amount=max_amount,
            description_search=description_search,
            person_id=person_id,
            page=page,
            page_size=page_size,
        )

        purchase_ids = [p.id for p in purchases if p.id is not None]
        payers_by_purchase_id: dict[int, list[PurchasePayerRead]] = {int(pid): [] for pid in purchase_ids}
        if purchase_ids:
            payer_rows = session.exec(
                select(PurchasePayer, Person)
                .join(Person, Person.id == PurchasePayer.person_id)
                .where(PurchasePayer.purchase_id.in_(purchase_ids))
            ).all()
            for payer, person in payer_rows:
                payers_by_purchase_id[int(payer.purchase_id)].append(
                    PurchasePayerRead(
                        person_id=int(payer.person_id),
                        person_name=person.name,
                        share_type=payer.share_type,
                        share_value=float(payer.share_value),
                    )
                )

        out: list[PurchaseRead] = []
        for p in purchases:
            if p.id is None:
                continue
            out.append(
                PurchaseRead(
                    id=p.id,
                    card_id=p.card_id,
                    payment_method=p.payment_method,
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
                    is_common=p.is_common,
                    debtor_id=p.debtor_id,
                    debt_settled=p.debt_settled,
                    payers=payers_by_purchase_id.get(int(p.id), []),
                )
            )
        pages = math.ceil(total / page_size) if page_size > 0 else 0
        return PaginatedResponse(
            items=out,
            total=total,
            page=page,
            page_size=page_size,
            pages=pages,
        )


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
            payment_method=purchase.payment_method,
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
            is_common=purchase.is_common,
            debtor_id=purchase.debtor_id,
            debt_settled=purchase.debt_settled,
        )


@router.delete("/purchases/{purchase_id}")
def delete_purchase_endpoint(purchase_id: int) -> Response:
    with get_session() as session:
        try:
            delete_purchase(session=session, purchase_id=purchase_id)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e
    return Response(status_code=204)


@router.patch("/purchases/{purchase_id}", response_model=PurchaseRead)
def patch_purchase(purchase_id: int, payload: PurchaseUpdate) -> PurchaseRead:
    with get_session() as session:
        try:
            purchase = update_purchase(session=session, purchase_id=purchase_id, payload=payload)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e

        if purchase.id is None:
            raise HTTPException(status_code=500, detail="Failed to update purchase")

        return PurchaseRead(
            id=purchase.id,
            card_id=purchase.card_id,
            payment_method=purchase.payment_method,
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
            is_common=purchase.is_common,
            debtor_id=purchase.debtor_id,
            debt_settled=purchase.debt_settled,
        )


@router.post("/purchases/bulk")
def post_bulk_update_purchases(payload: BulkPurchaseUpdate) -> dict:
    with get_session() as session:
        updated_count = bulk_update_purchases(session=session, payload=payload)
        return {"updated": updated_count}


@router.get("/reports/month-breakdown", response_model=MonthBreakdownResponse)
def get_report_month_breakdown(
    year_month: str,
    card_id: Optional[int] = None,
    person_id: Optional[int] = None,
) -> MonthBreakdownResponse:
    """Desglose de cuotas que vencen en un mes dado. year_month formato YYYY-MM."""
    with get_session() as session:
        total_ars, items = report_month_breakdown(
            session=session,
            year_month=year_month,
            card_id=card_id,
            person_id=person_id,
        )
        rows = [
            MonthBreakdownRow(
                purchase_id=p.id,
                purchase_date=p.purchase_date,
                description=p.description,
                notes=p.notes,
                category=p.category,
                installment_index=sch.installment_index,
                installments_total=p.installments_total,
                amount_ars=amt,
                currency=str(p.currency),
                debtor_id=p.debtor_id,
                debtor_name=debtor_name,
                debt_settled=p.debt_settled,
                is_common=p.is_common,
            )
            for p, sch, amt, debtor_name in items
            if p.id is not None
        ]
        return MonthBreakdownResponse(year_month=year_month, total_ars=total_ars, items=rows)


@router.get("/reports/monthly", response_model=list[ReportMonthlyRow])
def get_report_monthly(card_id: Optional[int] = None, person_id: Optional[int] = None) -> list[ReportMonthlyRow]:
    with get_session() as session:
        rows = report_monthly_totals_converted(session=session, card_id=card_id, person_id=person_id)
        return [ReportMonthlyRow(year_month=ym, total_ars=total) for ym, total in rows]


@router.get("/reports/timeline", response_model=list[TimelineRow])
def get_report_timeline(
    months_ahead: int = 12, card_id: Optional[int] = None, person_id: Optional[int] = None
) -> list[TimelineRow]:
    """Return future installment commitments timeline."""
    with get_session() as session:
        rows = report_installment_timeline(
            session=session, months_ahead=months_ahead, card_id=card_id, person_id=person_id
        )
        return [TimelineRow(year_month=ym, total_ars=total) for ym, total in rows]


@router.get("/categories", response_model=CategoryRead)
def get_categories() -> CategoryRead:
    """Return list of distinct categories."""
    with get_session() as session:
        categories = get_distinct_categories(session=session)
        return CategoryRead(categories=categories)


@router.get("/reports/category-spending", response_model=list[CategorySpendingRow])
def get_category_spending(
    card_id: Optional[int] = None, person_id: Optional[int] = None
) -> list[CategorySpendingRow]:
    """Return spending totals by category."""
    with get_session() as session:
        rows = report_spending_by_category(session=session, card_id=card_id, person_id=person_id)
        return [CategorySpendingRow(category=cat, total_ars=total) for cat, total in rows]


@router.get("/debtors", response_model=list[DebtorRead])
def get_debtors() -> list[DebtorRead]:
    """Return list of all debtors."""
    with get_session() as session:
        debtors = list_debtors(session=session)
        return [DebtorRead(id=d.id, name=d.name) for d in debtors if d.id is not None]


@router.post("/debtors", response_model=DebtorRead)
def post_debtor(payload: DebtorCreate) -> DebtorRead:
    with get_session() as session:
        debtor = create_debtor(session=session, payload=payload)
        if debtor.id is None:
            raise HTTPException(status_code=500, detail="Failed to create debtor")
        return DebtorRead(id=debtor.id, name=debtor.name)


@router.get("/reports/debts", response_model=list[DebtSummaryRow])
def get_debt_report() -> list[DebtSummaryRow]:
    """Return debt summary per debtor."""
    with get_session() as session:
        rows = report_debts(session=session)
        return [
            DebtSummaryRow(
                debtor_id=debtor_id,
                debtor_name=debtor_name,
                total_owed=total_owed,
                total_settled=total_settled,
                pending_purchases=pending_count,
            )
            for debtor_id, debtor_name, total_owed, total_settled, pending_count in rows
        ]


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


@router.get("/budgets", response_model=list[MonthlyBudgetRead])
def get_budgets() -> list[MonthlyBudgetRead]:
    with get_session() as session:
        budgets = list_monthly_budgets(session=session)
        return [
            MonthlyBudgetRead(
                id=b.id,
                year_month=b.year_month,
                total_income=float(b.total_income),
                notes=b.notes
            )
            for b in budgets
            if b.id is not None
        ]


@router.post("/budgets", response_model=MonthlyBudgetRead)
def post_budget(payload: MonthlyBudgetCreate) -> MonthlyBudgetRead:
    with get_session() as session:
        budget = create_monthly_budget(session=session, payload=payload)
        if budget.id is None:
            raise HTTPException(status_code=500, detail="Failed to create budget")
        return MonthlyBudgetRead(
            id=budget.id,
            year_month=budget.year_month,
            total_income=float(budget.total_income),
            notes=budget.notes
        )


@router.get("/reports/monthly-balance", response_model=MonthlyBalanceResponse)
def get_monthly_balance(year_month: str) -> MonthlyBalanceResponse:
    with get_session() as session:
        balance = calculate_monthly_balance(session=session, year_month=year_month)
        if balance is None:
            raise HTTPException(status_code=404, detail="Budget not found for this month")
        return MonthlyBalanceResponse(**balance)


@router.get("/incomes", response_model=list[IncomeRead])
def get_incomes(year_month: Optional[str] = None) -> list[IncomeRead]:
    with get_session() as session:
        incomes = list_incomes(session=session, year_month=year_month)
        return [
            IncomeRead(
                id=inc.id,
                person_id=inc.person_id,
                person_name=session.get(Person, inc.person_id).name if inc.person_id else "Desconocido",
                year_month=inc.year_month,
                amount=float(inc.amount),
                notes=inc.notes
            )
            for inc in incomes
            if inc.id is not None
        ]


@router.post("/incomes", response_model=IncomeRead)
def post_income(payload: IncomeCreate) -> IncomeRead:
    with get_session() as session:
        # Verify person exists
        person = session.get(Person, payload.person_id)
        if person is None:
            raise HTTPException(status_code=404, detail="Person not found")
        
        income = create_income(session=session, payload=payload)
        if income.id is None:
            raise HTTPException(status_code=500, detail="Failed to create income")
        
        return IncomeRead(
            id=income.id,
            person_id=income.person_id,
            person_name=person.name,
            year_month=income.year_month,
            amount=float(income.amount),
            notes=income.notes
        )
@router.get("/reports/export-excel")
def get_export_excel(year_month: str) -> Response:
    with get_session() as session:
        content = export_dashboard_to_excel(session=session, year_month=year_month)
        filename = f"reporte_{year_month}.xlsx"
        return Response(
            content=content,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )


@router.get("/reports/transfers", response_model=TransferCalculationResponse)
def get_transfer_calculation(year_month: str) -> TransferCalculationResponse:
    with get_session() as session:
        transfers = calculate_transfers(session=session, year_month=year_month)
        if transfers is None:
            raise HTTPException(status_code=404, detail="No incomes found for this month")
        return TransferCalculationResponse(**transfers)

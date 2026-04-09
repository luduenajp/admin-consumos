from __future__ import annotations

import math
from datetime import date
from typing import Optional

from fastapi import APIRouter, HTTPException, Response
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from app.crud import (
    auto_categorize_purchases,
    get_categorization_rules,
    bulk_update_purchases,
    calculate_monthly_balance,
    calculate_transfers,
    create_card,
    create_debtor,
    create_purchase,
    create_income,
    create_monthly_budget,
    create_person,
    create_category,
    delete_category,
    detect_recurring_expenses,
    update_category,
    list_categories,
    create_debt_transfer,
    delete_debt_transfer,
    list_debt_transfers,
    create_family_goal,
    list_family_goals,
    update_family_goal,
    delete_family_goal,
    export_dashboard_to_excel,
    create_saving,
    create_saving_snapshot,
    delete_saving,
    delete_saving_snapshot,
    list_savings,
    list_saving_snapshots,
    update_saving,
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
from app.models import Category, Person, PurchasePayer
from app.schemas import (
    BulkPurchaseUpdate,
    CardCreate,
    CardRead,
    CategoryCreate,
    CategoryRead,
    CategoryUpdate,
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
    DebtTransferCreate,
    DebtTransferRead,
    TransferCalculationResponse,
    RecurringExpenseRow,
    FamilyGoalCreate,
    FamilyGoalUpdate,
    FamilyGoalRead,
    SavingCreate,
    SavingUpdate,
    SavingRead,
    SavingSnapshotCreate,
    SavingSnapshotRead,
)

router = APIRouter()


def _fetch_payers(session, purchase_id: int) -> list[PurchasePayerRead]:
    payer_rows = session.exec(
        select(PurchasePayer, Person)
        .join(Person, Person.id == PurchasePayer.person_id)
        .where(PurchasePayer.purchase_id == purchase_id)
    ).all()
    return [
        PurchasePayerRead(
            person_id=int(payer.person_id),
            person_name=person.name,
            share_type=payer.share_type,
            share_value=float(payer.share_value),
        )
        for payer, person in payer_rows
    ]


def _purchase_to_read(purchase, payers: list[PurchasePayerRead]) -> PurchaseRead:
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
        beneficiary_person_id=purchase.beneficiary_person_id,
        debt_settled=purchase.debt_settled,
        import_batch_id=purchase.import_batch_id,
        payers=payers,
    )


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
    import_batch_id: Optional[int] = None,
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
            import_batch_id=import_batch_id,
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
                    beneficiary_person_id=p.beneficiary_person_id,
                    debt_settled=p.debt_settled,
                    import_batch_id=p.import_batch_id,
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

        return _purchase_to_read(purchase, _fetch_payers(session, purchase.id))


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

        return _purchase_to_read(purchase, _fetch_payers(session, purchase.id))


@router.post("/purchases/bulk")
def post_bulk_update_purchases(payload: BulkPurchaseUpdate) -> dict:
    with get_session() as session:
        updated_count = bulk_update_purchases(session=session, payload=payload)
        return {"updated": updated_count}


@router.post("/purchases/auto-categorize")
def post_auto_categorize_purchases() -> dict:
    with get_session() as session:
        count = auto_categorize_purchases(session=session)
        return {"updated": count}


@router.get("/purchases/categorization-rules")
def get_categorization_rules_endpoint() -> dict:
    """Return learned CUIL/description rules and hardcoded keyword rules."""
    with get_session() as session:
        return get_categorization_rules(session=session)


@router.get("/reports/month-breakdown", response_model=MonthBreakdownResponse)
def get_report_month_breakdown(
    year_month: str,
    card_id: Optional[int] = None,
    person_id: Optional[int] = None,
    is_common: Optional[bool] = None,
) -> MonthBreakdownResponse:
    """Desglose de cuotas que vencen en un mes dado. year_month formato YYYY-MM."""
    with get_session() as session:
        total_ars, items = report_month_breakdown(
            session=session,
            year_month=year_month,
            card_id=card_id,
            person_id=person_id,
            is_common=is_common,
        )
        rows = [
            MonthBreakdownRow(
                purchase_id=p.id,
                purchase_date=p.purchase_date,
                description=p.description,
                notes=p.notes,
                category=p.category,
                payer_name=payer_name,
                payment_method=p.payment_method.value,
                card_name=card_name,
                installment_index=sch.installment_index,
                installments_total=p.installments_total,
                amount_ars=amt,
                amount_original=float(sch.amount_original),
                currency=p.currency.value,
                debtor_id=p.debtor_id,
                debtor_name=debtor_name,
                beneficiary_person_id=p.beneficiary_person_id,
                debt_settled=p.debt_settled,
                is_common=p.is_common,
            )
            for p, sch, amt, debtor_name, payer_name, card_name in items
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
    months_ahead: int = 12, card_id: Optional[int] = None, person_id: Optional[int] = None, is_common: Optional[bool] = None
) -> list[TimelineRow]:
    """Return future installment commitments timeline."""
    with get_session() as session:
        rows = report_installment_timeline(
            session=session, months_ahead=months_ahead, card_id=card_id, person_id=person_id, is_common=is_common
        )
        return [TimelineRow(year_month=ym, total_ars=total) for ym, total in rows]


@router.get("/categories", response_model=list[CategoryRead])
def get_categories() -> list[CategoryRead]:
    """Return all defined categories."""
    with get_session() as session:
        categories = list_categories(session=session)
        return [
            CategoryRead(id=c.id, name=c.name, color=c.color)
            for c in categories
            if c.id is not None
        ]


@router.post("/categories", response_model=CategoryRead)
def post_category(payload: CategoryCreate) -> CategoryRead:
    with get_session() as session:
        try:
            category = create_category(session=session, payload=payload)
        except (ValueError, IntegrityError) as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        return CategoryRead(id=category.id, name=category.name, color=category.color)


@router.patch("/categories/{category_id}", response_model=CategoryRead)
def patch_category(category_id: int, payload: CategoryUpdate) -> CategoryRead:
    with get_session() as session:
        try:
            category = update_category(session=session, category_id=category_id, payload=payload)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e
        return CategoryRead(id=category.id, name=category.name, color=category.color)


@router.delete("/categories/{category_id}")
def delete_category_endpoint(category_id: int) -> Response:
    with get_session() as session:
        try:
            delete_category(session=session, category_id=category_id)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e
    return Response(status_code=204)


@router.get("/categories/distinct", response_model=list[str])
def get_distinct_categories_endpoint() -> list[str]:
    """Return list of distinct categories currently used in purchases."""
    with get_session() as session:
        return get_distinct_categories(session=session)


@router.get("/reports/category-spending", response_model=list[CategorySpendingRow])
def get_category_spending(
    card_id: Optional[int] = None,
    person_id: Optional[int] = None,
    year_month: Optional[str] = None,
    is_common: Optional[bool] = None,
) -> list[CategorySpendingRow]:
    """Return spending totals by category."""
    with get_session() as session:
        rows = report_spending_by_category(
            session=session, card_id=card_id, person_id=person_id, year_month=year_month, is_common=is_common
        )
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
        person_ids = {inc.person_id for inc in incomes if inc.person_id is not None}
        person_map = (
            {p.id: p for p in session.exec(select(Person).where(Person.id.in_(person_ids))).all()}
            if person_ids else {}
        )
        return [
            IncomeRead(
                id=inc.id,
                person_id=inc.person_id,
                person_name=(lambda p: p.name if p else "Desconocido")(person_map.get(inc.person_id)),
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


@router.get("/debt-transfers", response_model=list[DebtTransferRead])
def get_debt_transfers(year_month: Optional[str] = None) -> list[DebtTransferRead]:
    with get_session() as session:
        transfers = list_debt_transfers(session=session, year_month=year_month)
        person_ids = {t.from_person_id for t in transfers} | {t.to_person_id for t in transfers}
        person_map = (
            {p.id: p for p in session.exec(select(Person).where(Person.id.in_(person_ids))).all()}
            if person_ids else {}
        )
        return [
            DebtTransferRead(
                id=t.id,
                from_person_id=t.from_person_id,
                from_person_name=(lambda p: p.name if p else "Desconocido")(person_map.get(t.from_person_id)),
                to_person_id=t.to_person_id,
                to_person_name=(lambda p: p.name if p else "Desconocido")(person_map.get(t.to_person_id)),
                year_month=t.year_month,
                amount=float(t.amount),
                transfer_date=t.transfer_date,
                notes=t.notes
            )
            for t in transfers
        ]


@router.post("/debt-transfers", response_model=DebtTransferRead)
def post_debt_transfer(payload: DebtTransferCreate) -> DebtTransferRead:
    with get_session() as session:
        from_p = session.get(Person, payload.from_person_id)
        to_p = session.get(Person, payload.to_person_id)
        if not from_p or not to_p:
            raise HTTPException(status_code=404, detail="Person not found")

        transfer = create_debt_transfer(session=session, payload=payload)
        return DebtTransferRead(
            id=transfer.id,
            from_person_id=transfer.from_person_id,
            from_person_name=from_p.name,
            to_person_id=transfer.to_person_id,
            to_person_name=to_p.name,
            year_month=transfer.year_month,
            amount=float(transfer.amount),
            transfer_date=transfer.transfer_date,
            notes=transfer.notes
        )


@router.delete("/debt-transfers/{transfer_id}")
def delete_debt_transfer_endpoint(transfer_id: int) -> Response:
    with get_session() as session:
        try:
            delete_debt_transfer(session=session, transfer_id=transfer_id)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e
    return Response(status_code=204)


@router.get("/reports/recurring-expenses", response_model=list[RecurringExpenseRow])
def get_recurring_expenses(min_occurrences: int = 3) -> list[RecurringExpenseRow]:
    """Detect recurring expenses based on normalized description matching."""
    with get_session() as session:
        rows = detect_recurring_expenses(session=session, min_occurrences=min_occurrences)
        return [RecurringExpenseRow(**row) for row in rows]


# --- Family Goals ---

@router.get("/goals", response_model=list[FamilyGoalRead])
def get_goals() -> list[FamilyGoalRead]:
    with get_session() as session:
        goals = list_family_goals(session=session)
        return [FamilyGoalRead(**g.model_dump()) for g in goals]


@router.post("/goals", response_model=FamilyGoalRead, status_code=201)
def post_goal(payload: FamilyGoalCreate) -> FamilyGoalRead:
    with get_session() as session:
        goal = create_family_goal(session=session, payload=payload)
        return FamilyGoalRead(**goal.model_dump())


@router.patch("/goals/{goal_id}", response_model=FamilyGoalRead)
def patch_goal(goal_id: int, payload: FamilyGoalUpdate) -> FamilyGoalRead:
    with get_session() as session:
        try:
            goal = update_family_goal(session=session, goal_id=goal_id, payload=payload)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e
        return FamilyGoalRead(**goal.model_dump())


@router.delete("/goals/{goal_id}")
def delete_goal_endpoint(goal_id: int) -> Response:
    with get_session() as session:
        try:
            delete_family_goal(session=session, goal_id=goal_id)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e
    return Response(status_code=204)


# --- Savings endpoints ---

@router.get("/savings", response_model=list[SavingRead])
def get_savings() -> list[SavingRead]:
    with get_session() as session:
        rows = list_savings(session=session)
        return [
            SavingRead(
                id=saving.id,
                person_id=saving.person_id,
                investment_type=saving.investment_type,
                institution=saving.institution,
                currency=saving.currency,
                notes=saving.notes,
                current_amount=float(amount) if amount is not None else None,
                current_amount_date=snap_date,
            )
            for saving, amount, snap_date in rows
            if saving.id is not None
        ]


@router.post("/savings", response_model=SavingRead, status_code=201)
def post_saving(payload: SavingCreate) -> SavingRead:
    with get_session() as session:
        try:
            saving = create_saving(session=session, payload=payload)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        return SavingRead(
            id=saving.id,
            person_id=saving.person_id,
            investment_type=saving.investment_type,
            institution=saving.institution,
            currency=saving.currency,
            notes=saving.notes,
            current_amount=None,
            current_amount_date=None,
        )


@router.patch("/savings/{saving_id}", response_model=SavingRead)
def patch_saving(saving_id: int, payload: SavingUpdate) -> SavingRead:
    with get_session() as session:
        try:
            saving = update_saving(session=session, saving_id=saving_id, payload=payload)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e
        rows = list_savings(session=session)
        row = next(((s, a, d) for s, a, d in rows if s.id == saving_id), None)
        current_amount = float(row[1]) if row and row[1] is not None else None
        current_amount_date = row[2] if row else None
        return SavingRead(
            id=saving.id,
            person_id=saving.person_id,
            investment_type=saving.investment_type,
            institution=saving.institution,
            currency=saving.currency,
            notes=saving.notes,
            current_amount=current_amount,
            current_amount_date=current_amount_date,
        )


@router.delete("/savings/{saving_id}")
def delete_saving_endpoint(saving_id: int) -> Response:
    with get_session() as session:
        try:
            delete_saving(session=session, saving_id=saving_id)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e
        return Response(status_code=204)


@router.get("/savings/{saving_id}/snapshots", response_model=list[SavingSnapshotRead])
def get_saving_snapshots(saving_id: int) -> list[SavingSnapshotRead]:
    with get_session() as session:
        snapshots = list_saving_snapshots(session=session, saving_id=saving_id)
        return [
            SavingSnapshotRead(
                id=s.id,
                saving_id=s.saving_id,
                date=s.date,
                amount=s.amount,
            )
            for s in snapshots
            if s.id is not None
        ]


@router.post("/savings/{saving_id}/snapshots", response_model=SavingSnapshotRead, status_code=201)
def post_saving_snapshot(saving_id: int, payload: SavingSnapshotCreate) -> SavingSnapshotRead:
    with get_session() as session:
        try:
            snapshot = create_saving_snapshot(session=session, saving_id=saving_id, payload=payload)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e
        return SavingSnapshotRead(
            id=snapshot.id,
            saving_id=snapshot.saving_id,
            date=snapshot.date,
            amount=snapshot.amount,
        )


@router.delete("/savings/{saving_id}/snapshots/{snapshot_id}")
def delete_saving_snapshot_endpoint(saving_id: int, snapshot_id: int) -> Response:
    with get_session() as session:
        try:
            delete_saving_snapshot(session=session, snapshot_id=snapshot_id)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e
        return Response(status_code=204)

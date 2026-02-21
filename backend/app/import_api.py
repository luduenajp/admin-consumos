from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.crud import create_purchase, find_existing_purchase_for_installment_import
from app.db import get_session
from app.models import CurrencyCode, PaymentMethod
from app.schemas import GSheetsImportRequest, PurchaseCreate
from app.importers.gsheets_importer import download_gsheets_csv, parse_gsheets_csv
from app.importers.visa_pdf import parse_visa_pdf
from app.importers.visa_xlsx import (
    compute_row_fingerprint,
    normalize_purchase_description,
    mark_imported,
    parse_visa_xlsx,
    was_already_imported,
)
from app.utils_dates import add_months


def _has_installment_schedule(*, session, purchase_id: int, year_month: str, installment_index: int) -> bool:
    from sqlmodel import select

    from app.models import InstallmentSchedule

    stmt = select(InstallmentSchedule).where(
        InstallmentSchedule.purchase_id == purchase_id,
        InstallmentSchedule.year_month == year_month,
        InstallmentSchedule.installment_index == installment_index,
    )
    return session.exec(stmt).first() is not None

router = APIRouter()


@router.post("/import/visa-xlsx")
def import_visa_xlsx(card_id: int, provider: str, file: UploadFile = File(...)) -> dict:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename")

    suffix = Path(file.filename).suffix.lower()
    if suffix not in {".xlsx", ".xls"}:
        raise HTTPException(status_code=400, detail="Expected .xlsx")

    with tempfile.TemporaryDirectory() as td:
        tmp_path = Path(td) / file.filename
        tmp_path.write_bytes(file.file.read())

        try:
            rows = parse_visa_xlsx(tmp_path)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to parse xlsx: {e}") from e

    created = 0
    skipped = 0

    with get_session() as session:
        for r in rows:
            fingerprint = compute_row_fingerprint(provider=provider, card_id=card_id, row=r)
            if was_already_imported(session=session, fingerprint=fingerprint):
                skipped += 1
                continue

            # Convert statement month + installment index into first_installment_month.
            # Shifting forward by 1 month to match the actual payment date (Credit Card logic).
            payment_month = add_months(r.statement_year_month, 1)
            first_installment_month = add_months(payment_month, -(r.installment_index - 1))

            amount_total = round(r.installment_amount * r.installments_total, 2)

            normalized_desc = normalize_purchase_description(description=r.description)
            existing = find_existing_purchase_for_installment_import(
                session=session,
                card_id=card_id,
                purchase_date=r.purchase_date,
                description=normalized_desc,
                currency=CurrencyCode(r.currency),
                installments_total=r.installments_total,
                installment_amount_original=r.installment_amount,
            )

            if existing is None:
                payload = PurchaseCreate(
                    card_id=card_id,
                    purchase_date=r.purchase_date,
                    description=normalized_desc,
                    currency=CurrencyCode(r.currency),
                    amount_original=amount_total,
                    installments_total=r.installments_total,
                    installment_amount_original=r.installment_amount,
                    first_installment_month=first_installment_month,
                    owner_person_id=None,
                    category=None,
                    notes=None,
                    is_refund=False,
                    payers=None,
                )
                purchase = create_purchase(session=session, payload=payload)
            else:
                purchase = existing
                if purchase.id is not None:
                    if not _has_installment_schedule(
                        session=session,
                        purchase_id=purchase.id,
                        year_month=r.statement_year_month,
                        installment_index=r.installment_index,
                    ):
                        from app.models import InstallmentSchedule

                        session.add(
                            InstallmentSchedule(
                                purchase_id=purchase.id,
                                year_month=r.statement_year_month,
                                installment_index=r.installment_index,
                                currency=CurrencyCode(r.currency),
                                amount_original=r.installment_amount,
                                amount_ars=None,
                            )
                        )

            mark_imported(
                session=session,
                provider=provider,
                source_file=file.filename,
                fingerprint=fingerprint,
                payload={
                    "card_id": card_id,
                    "purchase_date": r.purchase_date.isoformat(),
                    "description": r.description,
                    "currency": r.currency,
                    "installment_index": r.installment_index,
                    "installments_total": r.installments_total,
                    "installment_amount": r.installment_amount,
                    "statement_year_month": r.statement_year_month,
                },
            )
            session.commit()
            created += 1

    return {"created": created, "skipped": skipped, "parsed": len(rows)}


@router.post("/import/visa-pdf")
def import_visa_pdf_endpoint(
    card_id: int,
    provider: str,
    file: UploadFile = File(...),
    password: str | None = Form(default=None),
) -> dict:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename")

    suffix = Path(file.filename).suffix.lower()
    if suffix != ".pdf":
        raise HTTPException(status_code=400, detail="Expected .pdf")

    with tempfile.TemporaryDirectory() as td:
        tmp_path = Path(td) / file.filename
        tmp_path.write_bytes(file.file.read())

        try:
            rows = parse_visa_pdf(tmp_path, password=password)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to parse PDF: {e}") from e

    created = 0
    skipped = 0

    with get_session() as session:
        for r in rows:
            fingerprint = compute_row_fingerprint(provider=provider, card_id=card_id, row=r)
            if was_already_imported(session=session, fingerprint=fingerprint):
                skipped += 1
                continue

            # Shifting forward by 1 month to match the actual payment date (Credit Card logic).
            payment_month = add_months(r.statement_year_month, 1)
            first_installment_month = add_months(payment_month, -(r.installment_index - 1))
            amount_total = round(r.installment_amount * r.installments_total, 2)

            normalized_desc = normalize_purchase_description(description=r.description)
            existing = find_existing_purchase_for_installment_import(
                session=session,
                card_id=card_id,
                purchase_date=r.purchase_date,
                description=normalized_desc,
                currency=CurrencyCode(r.currency),
                installments_total=r.installments_total,
                installment_amount_original=r.installment_amount,
            )

            if existing is None:
                payload = PurchaseCreate(
                    card_id=card_id,
                    purchase_date=r.purchase_date,
                    description=normalized_desc,
                    currency=CurrencyCode(r.currency),
                    amount_original=amount_total,
                    installments_total=r.installments_total,
                    installment_amount_original=r.installment_amount,
                    first_installment_month=first_installment_month,
                    owner_person_id=None,
                    category=None,
                    notes=None,
                    is_refund=False,
                    payers=None,
                )
                purchase = create_purchase(session=session, payload=payload)
            else:
                purchase = existing
                if purchase.id is not None:
                    if not _has_installment_schedule(
                        session=session,
                        purchase_id=purchase.id,
                        year_month=r.statement_year_month,
                        installment_index=r.installment_index,
                    ):
                        from app.models import InstallmentSchedule

                        session.add(
                            InstallmentSchedule(
                                purchase_id=purchase.id,
                                year_month=r.statement_year_month,
                                installment_index=r.installment_index,
                                currency=CurrencyCode(r.currency),
                                amount_original=r.installment_amount,
                                amount_ars=None,
                            )
                        )

            mark_imported(
                session=session,
                provider=provider,
                source_file=file.filename,
                fingerprint=fingerprint,
                payload={
                    "card_id": card_id,
                    "purchase_date": r.purchase_date.isoformat(),
                    "description": r.description,
                    "currency": r.currency,
                    "installment_index": r.installment_index,
                    "installments_total": r.installments_total,
                    "installment_amount": r.installment_amount,
                    "statement_year_month": r.statement_year_month,
                },
            )
            session.commit()
            created += 1

    return {"created": created, "skipped": skipped, "parsed": len(rows)}


@router.post("/import/gsheets")
def import_gsheets_endpoint(payload: GSheetsImportRequest) -> dict:
    try:
        csv_content = download_gsheets_csv(payload.url)
        rows = parse_gsheets_csv(csv_content)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to import from GSheets: {e}") from e

    created = 0
    skipped = 0
    provider = "gsheets"

    with get_session() as session:
        for r in rows:
            # For GSheets/Transfers, we use the same deduplication logic
            fingerprint = compute_row_fingerprint(provider=provider, card_id=None, row=r)
            if was_already_imported(session=session, fingerprint=fingerprint):
                skipped += 1
                continue

            purchase_payload = PurchaseCreate(
                card_id=None,
                payment_method=PaymentMethod.TRANSFER,
                purchase_date=r.purchase_date,
                description=r.description,
                currency=CurrencyCode(r.currency),
                amount_original=r.installment_amount,
                installments_total=1,
                installment_amount_original=r.installment_amount,
                first_installment_month=r.statement_year_month,
                owner_person_id=payload.owner_person_id,
                category=None,
                notes=None,
                is_refund=False,
                payers=None,
            )
            create_purchase(session=session, payload=purchase_payload)

            mark_imported(
                session=session,
                provider=provider,
                source_file=payload.url[:100],  # Store a snippet of the URL
                fingerprint=fingerprint,
                payload={
                    "payment_method": PaymentMethod.TRANSFER,
                    "purchase_date": r.purchase_date.isoformat(),
                    "description": r.description,
                    "currency": r.currency,
                    "amount": r.installment_amount,
                },
            )
            session.commit()
            created += 1

    return {"created": created, "skipped": skipped, "parsed": len(rows)}

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


def _process_installment_row(
    *,
    session,
    r,
    card_id: int,
    provider: str,
    filename: str,
    is_common: bool,
    claimed_ids: list[int],
) -> bool:
    """
    Process a single parsed installment row: check dedup, create/update purchase, mark imported.
    Returns True if a new record was created, False if skipped.
    """
    fingerprint = compute_row_fingerprint(provider=provider, card_id=card_id, row=r)
    if was_already_imported(session=session, fingerprint=fingerprint):
        return False

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
        exclude_ids=claimed_ids,
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
            is_common=is_common,
            payers=None,
        )
        create_purchase(session=session, payload=payload)
    else:
        if existing.id is not None:
            claimed_ids.append(existing.id)
            if not _has_installment_schedule(
                session=session,
                purchase_id=existing.id,
                year_month=r.statement_year_month,
                installment_index=r.installment_index,
            ):
                from app.models import InstallmentSchedule

                session.add(
                    InstallmentSchedule(
                        purchase_id=existing.id,
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
        source_file=filename,
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
    return True


router = APIRouter()


@router.post("/import/visa-xlsx")
def import_visa_xlsx(card_id: int, provider: str, is_common: bool = Form(default=False), file: UploadFile = File(...)) -> dict:
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
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to parse xlsx: {e}") from e

    created = 0
    skipped = 0
    claimed_ids: list[int] = []

    with get_session() as session:
        for r in rows:
            if _process_installment_row(
                session=session, r=r, card_id=card_id, provider=provider,
                filename=file.filename, is_common=is_common, claimed_ids=claimed_ids,
            ):
                created += 1
            else:
                skipped += 1

    return {"created": created, "skipped": skipped, "parsed": len(rows)}


@router.post("/import/visa-pdf")
def import_visa_pdf_endpoint(
    card_id: int,
    provider: str,
    file: UploadFile = File(...),
    password: str | None = Form(default=None),
    is_common: bool = Form(default=False),
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
            raise HTTPException(status_code=500, detail=f"Failed to parse PDF: {e}") from e

    created = 0
    skipped = 0
    claimed_ids: list[int] = []

    with get_session() as session:
        for r in rows:
            if _process_installment_row(
                session=session, r=r, card_id=card_id, provider=provider,
                filename=file.filename, is_common=is_common, claimed_ids=claimed_ids,
            ):
                created += 1
            else:
                skipped += 1

    return {"created": created, "skipped": skipped, "parsed": len(rows)}


@router.post("/import/gsheets")
def import_gsheets_endpoint(payload: GSheetsImportRequest) -> dict:
    try:
        csv_content = download_gsheets_csv(payload.url)
        rows = parse_gsheets_csv(csv_content)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to import from GSheets: {e}") from e

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
                is_common=payload.is_common,
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

from __future__ import annotations

import tempfile
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from sqlmodel import select

from app.crud import auto_categorize_purchases, create_purchase, find_card_by_holder, find_existing_purchase_for_installment_import, list_import_batches
from app.db import get_session
from app.models import Card, CurrencyCode, ImportBatch, PaymentMethod
from app.schemas import GSheetsImportRequest, ImportBatchRead, PurchaseCreate
from app.importers.gsheets_importer import download_gsheets_csv, parse_gsheets_csv
from app.importers.visa_pdf import extract_holder_hint_pdf, parse_visa_pdf
from app.importers.visa_xlsx import (
    extract_holder_hint_xlsx,
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
    import_batch_id: int | None = None,
) -> bool:
    """
    Process a single parsed installment row: check dedup, create/update purchase, mark imported.
    Returns True if a new record was created, False if skipped.
    """
    fingerprint = compute_row_fingerprint(provider=provider, card_id=card_id, row=r)
    if was_already_imported(session=session, fingerprint=fingerprint):
        return False

    # Si la compra es posterior al cierre del resumen, pertenece al ciclo siguiente
    effective_statement_ym = r.statement_year_month
    if r.statement_close_date and r.purchase_date > r.statement_close_date:
        effective_statement_ym = add_months(r.statement_year_month, 1)
    payment_month = add_months(effective_statement_ym, 1)
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
        purchase = create_purchase(session=session, payload=payload)
        if import_batch_id is not None:
            purchase.import_batch_id = import_batch_id
    else:
        if existing.id is not None:
            claimed_ids.append(existing.id)
            if not _has_installment_schedule(
                session=session,
                purchase_id=existing.id,
                year_month=payment_month,
                installment_index=r.installment_index,
            ):
                from app.models import InstallmentSchedule

                session.add(
                    InstallmentSchedule(
                        purchase_id=existing.id,
                        year_month=payment_month,
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


@router.post("/import/detect")
def detect_import_card(
    file: UploadFile = File(...),
    password: str | None = Form(default=None),
) -> dict:
    """
    Analiza un archivo de resumen (XLSX o PDF) y devuelve el titular detectado
    y la tarjeta sugerida, sin crear ningún registro.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename")

    suffix = Path(file.filename).suffix.lower()
    if suffix not in {".xlsx", ".xls", ".pdf"}:
        raise HTTPException(status_code=400, detail="Expected .xlsx, .xls or .pdf")

    with tempfile.TemporaryDirectory() as td:
        tmp_path = Path(td) / file.filename
        tmp_path.write_bytes(file.file.read())

        try:
            if suffix in {".xlsx", ".xls"}:
                rows = parse_visa_xlsx(tmp_path)
                holder_name, last4, card_type, bank = extract_holder_hint_xlsx(tmp_path)
            else:
                rows = parse_visa_pdf(tmp_path, password=password)
                # Re-parse text to extract hint (same bytes already decrypted inside parse_visa_pdf)
                from app.importers.visa_pdf import _decrypt_pdf_to_bytes
                import io
                import pdfplumber
                raw = _decrypt_pdf_to_bytes(tmp_path, password)
                full_text = ""
                with pdfplumber.open(io.BytesIO(raw)) as pdf:
                    for page in pdf.pages:
                        t = page.extract_text()
                        if t:
                            full_text += t + "\n"
                holder_name, last4, card_type, bank = extract_holder_hint_pdf(full_text)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to parse file: {e}") from e

    suggested_card_id = None
    suggested_card_name = None
    if holder_name:
        with get_session() as session:
            card = find_card_by_holder(session=session, holder_name=holder_name, last4=last4)
            if card is not None:
                suggested_card_id = card.id
                suggested_card_name = card.name

    statement_ym = rows[0].statement_year_month if rows else None

    return {
        "detected_holder": holder_name,
        "detected_last4": last4,
        "detected_card_type": card_type,
        "detected_bank": bank,
        "suggested_card_id": suggested_card_id,
        "suggested_card_name": suggested_card_name,
        "statement_year_month": statement_ym,
        "row_count": len(rows),
    }


@router.post("/import/visa-xlsx")
def import_visa_xlsx(card_id: int, provider: str, is_common: bool = False, file: UploadFile = File(...)) -> dict:
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
        batch = ImportBatch(
            imported_at=datetime.now().isoformat(),
            provider=provider,
            source_file=file.filename,
            card_id=card_id,
            statement_year_month=rows[0].statement_year_month if rows else None,
        )
        session.add(batch)
        session.flush()

        for r in rows:
            if _process_installment_row(
                session=session, r=r, card_id=card_id, provider=provider,
                filename=file.filename, is_common=is_common, claimed_ids=claimed_ids,
                import_batch_id=batch.id,
            ):
                created += 1
            else:
                skipped += 1

        batch.purchases_created = created
        batch.purchases_skipped = skipped
        batch.purchases_parsed = len(rows)
        session.commit()
        batch_id = batch.id

    with get_session() as session:
        auto_categorize_purchases(session=session)

    return {"created": created, "skipped": skipped, "parsed": len(rows), "batch_id": batch_id}


@router.post("/import/visa-pdf")
def import_visa_pdf_endpoint(
    card_id: int,
    provider: str,
    is_common: bool = False,
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
            raise HTTPException(status_code=500, detail=f"Failed to parse PDF: {e}") from e

    created = 0
    skipped = 0
    claimed_ids: list[int] = []

    with get_session() as session:
        batch = ImportBatch(
            imported_at=datetime.now().isoformat(),
            provider=provider,
            source_file=file.filename,
            card_id=card_id,
            statement_year_month=rows[0].statement_year_month if rows else None,
        )
        session.add(batch)
        session.flush()

        for r in rows:
            if _process_installment_row(
                session=session, r=r, card_id=card_id, provider=provider,
                filename=file.filename, is_common=is_common, claimed_ids=claimed_ids,
                import_batch_id=batch.id,
            ):
                created += 1
            else:
                skipped += 1

        batch.purchases_created = created
        batch.purchases_skipped = skipped
        batch.purchases_parsed = len(rows)
        session.commit()
        batch_id = batch.id

    with get_session() as session:
        auto_categorize_purchases(session=session)

    return {"created": created, "skipped": skipped, "parsed": len(rows), "batch_id": batch_id}


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
        batch = ImportBatch(
            imported_at=datetime.now().isoformat(),
            provider=provider,
            source_file=payload.url[:100],
            card_id=None,
            statement_year_month=rows[0].statement_year_month if rows else None,
        )
        session.add(batch)
        session.flush()

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
            purchase = create_purchase(session=session, payload=purchase_payload)
            purchase.import_batch_id = batch.id

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

        batch.purchases_created = created
        batch.purchases_skipped = skipped
        batch.purchases_parsed = len(rows)
        session.commit()
        batch_id = batch.id

    with get_session() as session:
        auto_categorize_purchases(session=session)

    return {"created": created, "skipped": skipped, "parsed": len(rows), "batch_id": batch_id}


@router.get("/import/batches", response_model=list[ImportBatchRead])
def get_import_batches() -> list[ImportBatchRead]:
    with get_session() as session:
        batches = list_import_batches(session=session)
        card_ids = {b.card_id for b in batches if b.card_id is not None}
        card_map: dict[int, str] = {}
        if card_ids:
            cards = session.exec(select(Card).where(Card.id.in_(card_ids))).all()
            card_map = {c.id: c.name for c in cards if c.id is not None}
        return [
            ImportBatchRead(
                id=b.id,  # type: ignore[arg-type]
                imported_at=b.imported_at,
                provider=b.provider,
                source_file=b.source_file,
                card_id=b.card_id,
                card_name=card_map.get(b.card_id) if b.card_id is not None else None,
                statement_year_month=b.statement_year_month,
                purchases_created=b.purchases_created,
                purchases_skipped=b.purchases_skipped,
                purchases_parsed=b.purchases_parsed,
            )
            for b in batches
        ]

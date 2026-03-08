import sys
from pathlib import Path

# Add backend to path so imports work
sys.path.append(str(Path(__file__).parent))

from app.db import get_session
from app.models import CurrencyCode
from app.schemas import PurchaseCreate
from app.crud import create_purchase, find_existing_purchase_for_installment_import
from app.importers.visa_xlsx import compute_row_fingerprint, normalize_purchase_description, mark_imported, was_already_imported
from app.importers.visa_pdf import parse_visa_pdf
from app.utils_dates import add_months

def do_import():
    pdf_path = Path("/Users/pablo/github/admin-consumos/resumenes/resumen-mp-marzo.pdf")
    if not pdf_path.exists():
        print("PDF file not found.")
        return

    card_id = 4
    provider = "mercadopago"
    
    rows = parse_visa_pdf(pdf_path)
    print(f"Parsed {len(rows)} rows from PDF.")
    
    created = 0
    skipped = 0
    claimed_ids = []

    with get_session() as session:
        for r in rows:
            fingerprint = compute_row_fingerprint(provider=provider, card_id=card_id, row=r)
            if was_already_imported(session=session, fingerprint=fingerprint):
                skipped += 1
                continue

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
                    is_common=False,
                    payers=None,
                )
                purchase = create_purchase(session=session, payload=payload)
                print(f"Created purchase: {purchase.description} for {purchase.first_installment_month} (index {r.installment_index}/{r.installments_total})")
            else:
                purchase = existing
                if purchase.id is not None:
                    claimed_ids.append(purchase.id)
                    from sqlmodel import select
                    from app.models import InstallmentSchedule
                    
                    stmt = select(InstallmentSchedule).where(
                        InstallmentSchedule.purchase_id == purchase.id,
                        InstallmentSchedule.year_month == r.statement_year_month,
                        InstallmentSchedule.installment_index == r.installment_index,
                    )
                    has_schedule = session.exec(stmt).first() is not None
                    
                    if not has_schedule:
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
                        print(f"Appended schedule for existing purchase: {purchase.description} for {r.statement_year_month} (index {r.installment_index})")

            mark_imported(
                session=session,
                provider=provider,
                source_file="resumen-mp-marzo.pdf",
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

    print(f"Created {created}, skipped {skipped}.")

if __name__ == "__main__":
    do_import()

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable

from sqlmodel import Session, select

from app.importers.visa_xlsx import normalize_purchase_description
from app.models import InstallmentSchedule, Purchase, PurchasePayer


@dataclass(frozen=True)
class ConsolidationGroup:
    representative_purchase_id: int
    merged_purchase_ids: tuple[int, ...]


def _iter_duplicate_groups(*, session: Session) -> Iterable[ConsolidationGroup]:
    purchases = list(session.exec(select(Purchase).where(Purchase.installments_total > 1)))

    groups: dict[tuple[int, str, str, str, int, float], list[Purchase]] = defaultdict(list)
    for p in purchases:
        if p.id is None:
            continue
        if p.installment_amount_original is None:
            continue
        key = (
            int(p.card_id),
            str(p.purchase_date),
            normalize_purchase_description(description=p.description),
            str(p.currency),
            int(p.installments_total),
            float(p.installment_amount_original),
        )
        groups[key].append(p)

    for _, ps in groups.items():
        if len(ps) <= 1:
            continue
        ps_sorted = sorted(ps, key=lambda x: int(x.id or 0))
        representative_id = int(ps_sorted[0].id)
        merged_ids = tuple(int(p.id) for p in ps_sorted[1:] if p.id is not None)
        if merged_ids:
            yield ConsolidationGroup(
                representative_purchase_id=representative_id,
                merged_purchase_ids=merged_ids,
            )


def consolidate_duplicate_installment_purchases(*, session: Session, dry_run: bool = True) -> dict[str, int]:
    """Consolidate duplicate purchases that represent installments of the same transaction.

    Strategy:
    - Group purchases by (card_id, purchase_date, normalized_description, currency, installments_total, installment_amount_original)
    - Pick smallest id as representative
    - Move InstallmentSchedule rows and PurchasePayer rows to representative
    - Delete merged purchases

    All actions happen inside the passed Session; caller controls commit/rollback.
    """

    groups = list(_iter_duplicate_groups(session=session))
    moved_installments = 0
    moved_payers = 0
    deleted_purchases = 0

    for g in groups:
        rep_id = g.representative_purchase_id
        rep_purchase = session.get(Purchase, rep_id)
        if rep_purchase is None:
            continue

        for pid in g.merged_purchase_ids:
            if pid == rep_id:
                continue
            p = session.get(Purchase, pid)
            if p is None:
                continue

            # Move installment schedules
            schs = list(session.exec(select(InstallmentSchedule).where(InstallmentSchedule.purchase_id == pid)))
            for sch in schs:
                sch.purchase_id = rep_id
                session.add(sch)
                moved_installments += 1

            # Move payers
            payers = list(session.exec(select(PurchasePayer).where(PurchasePayer.purchase_id == pid)))
            for payer in payers:
                existing = session.exec(
                    select(PurchasePayer).where(
                        PurchasePayer.purchase_id == rep_id,
                        PurchasePayer.person_id == payer.person_id,
                    )
                ).first()
                if existing is None:
                    payer.purchase_id = rep_id
                    session.add(payer)
                    moved_payers += 1

            if not dry_run:
                session.delete(p)
                deleted_purchases += 1

    if dry_run:
        session.rollback()

    return {
        "groups": len(groups),
        "moved_installments": moved_installments,
        "moved_payers": moved_payers,
        "deleted_purchases": deleted_purchases,
    }

#!/usr/bin/env python3
"""
Script to deduplicate existing purchases.

Detects purchases that are likely duplicates based on:
- Same card_id
- Same purchase_date
- Same currency
- Same installments_total
- Normalized description match

For each duplicate group:
- Keeps the purchase with the earliest ID (original)
- Moves all InstallmentSchedule rows from duplicates to the original
- Removes the duplicate purchases (and their PurchasePayer rows)

Run with: python deduplicate_purchases.py
"""

from __future__ import annotations

from collections import defaultdict
from typing import List, Tuple

from sqlmodel import Session, select

from app.config import get_sqlite_url
from app.db import engine
from app.importers.visa_xlsx import normalize_purchase_description
from app.models import InstallmentSchedule, Purchase, PurchasePayer


def find_duplicate_groups(session: Session) -> List[List[Purchase]]:
    """
    Find groups of purchases that are likely duplicates.
    Returns a list of groups, each group is a list of duplicate purchases.
    """
    # Get all purchases ordered by card_id, purchase_date, description
    stmt = select(Purchase).order_by(Purchase.card_id, Purchase.purchase_date, Purchase.description)
    all_purchases = list(session.exec(stmt).all())

    # Group by potential duplicate key
    groups: dict[Tuple[int, str, str, str, int], List[Purchase]] = defaultdict(list)
    
    for purchase in all_purchases:
        key = (
            purchase.card_id,
            purchase.purchase_date.isoformat(),
            purchase.currency.value,
            purchase.installments_total,
            normalize_purchase_description(description=purchase.description).lower(),
        )
        groups[key].append(purchase)

    # Filter to only groups with more than 1 purchase
    duplicate_groups = [group for group in groups.values() if len(group) > 1]
    
    return duplicate_groups


def consolidate_duplicate_group(session: Session, group: List[Purchase]) -> None:
    """
    Consolidate a group of duplicate purchases.
    Keeps the earliest ID as the original, moves schedules and payers to it,
    and deletes the duplicates.
    """
    # Sort by ID to keep the earliest as original
    group_sorted = sorted(group, key=lambda p: p.id or 0)
    original = group_sorted[0]
    duplicates = group_sorted[1:]

    print(f"  Consolidating: keeping purchase #{original.id} '{original.description[:50]}...'")

    # Disable autoflush to avoid constraint issues during restructuring
    with session.no_autoflush:
        # Move InstallmentSchedule rows from duplicates to original
        for duplicate in duplicates:
            schedules = list(session.exec(
                select(InstallmentSchedule).where(InstallmentSchedule.purchase_id == duplicate.id)
            ).all())
            
            for schedule in schedules:
                schedule.purchase_id = original.id
                session.add(schedule)
                print(f"    Moved schedule {schedule.year_month} installment {schedule.installment_index} from purchase #{duplicate.id}")

            # Handle PurchasePayer rows from duplicates
            payers = list(session.exec(
                select(PurchasePayer).where(PurchasePayer.purchase_id == duplicate.id)
            ).all())
            
            for payer in payers:
                # Check if this person already has a payer entry in the original purchase
                existing = session.exec(
                    select(PurchasePayer).where(
                        PurchasePayer.purchase_id == original.id,
                        PurchasePayer.person_id == payer.person_id
                    )
                ).first()
                
                if existing:
                    # Person already has a payer entry in original, just delete the duplicate
                    session.delete(payer)
                    print(f"    Deleted duplicate payer for person {payer.person_id} (already exists in original)")
                else:
                    # Move the payer to the original purchase
                    payer.purchase_id = original.id
                    session.add(payer)
                    print(f"    Moved payer for person {payer.person_id} from purchase #{duplicate.id}")

            # Now delete the duplicate purchase
            session.delete(duplicate)
            print(f"    Deleted duplicate purchase #{duplicate.id}")
    
    # Flush once at the end of the group
    session.flush()
    print(f"  Group consolidation completed")


def main():
    """Main deduplication process."""
    print("Starting purchase deduplication...")
    
    with Session(engine) as session:
        duplicate_groups = find_duplicate_groups(session)
        
        if not duplicate_groups:
            print("No duplicate purchases found.")
            return
        
        print(f"Found {len(duplicate_groups)} duplicate groups:")
        
        total_duplicates = 0
        for group in duplicate_groups:
            print(f"  Group: {len(group)} purchases")
            for purchase in group:
                print(f"    - #{purchase.id}: {purchase.description[:50]}... ({purchase.purchase_date})")
            total_duplicates += len(group) - 1  # minus the one we keep
        
        print(f"\nTotal duplicates to remove: {total_duplicates}")
        
        # Auto-proceed since we're running in a script context
        print("\nProceeding with deduplication...")
        
        # Consolidate each group
        for i, group in enumerate(duplicate_groups, 1):
            print(f"\nProcessing group {i}/{len(duplicate_groups)}:")
            consolidate_duplicate_group(session, group)
        
        session.commit()
        print(f"\nDeduplication completed. Removed {total_duplicates} duplicate purchases.")


if __name__ == "__main__":
    main()

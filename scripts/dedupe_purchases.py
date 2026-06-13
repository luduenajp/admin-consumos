"""
dedupe_purchases.py — one-time cleanup of duplicate purchases.

Usage:
    python scripts/dedupe_purchases.py --db data/app.db [--dry-run]
"""

import argparse
import os
import re
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

# ---------------------------------------------------------------------------
# Description normalisation (mirrors visa_xlsx.py / gmail_import.py)
# ---------------------------------------------------------------------------

_cleanup_re = re.compile(
    r"\b(?:C\.)\s*\d+\s*/\s*\d+\b|\b\d+\s*de\s*\d+\b",
    re.IGNORECASE,
)
_leading_code_re = re.compile(r"^\s*\d{3,}\s+")
_trailing_code_re = re.compile(r"\s+\d{3,}\s*$")


def normalize_purchase_description(description: str) -> str:
    cleaned = _cleanup_re.sub(" ", description)
    cleaned = _leading_code_re.sub("", cleaned)
    cleaned = _trailing_code_re.sub("", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned.upper()


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def open_db(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def fetch_all_purchases(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT
            p.id,
            p.purchase_date,
            p.currency,
            p.card_id,
            p.payment_method,
            p.installments_total,
            p.amount_original,
            p.description,
            p.category,
            p.notes,
            p.is_common,
            (SELECT COUNT(*) FROM purchasepayer pp WHERE pp.purchase_id = p.id) AS payer_count
        FROM purchase p
        ORDER BY p.purchase_date, p.card_id, p.amount_original, p.id
        """
    ).fetchall()


# ---------------------------------------------------------------------------
# Candidate grouping
# ---------------------------------------------------------------------------

GroupKey = tuple  # (purchase_date, currency, card_id, payment_method, installments_total)


def group_by_key(purchases: list[sqlite3.Row]) -> dict[GroupKey, list[sqlite3.Row]]:
    groups: dict[GroupKey, list[sqlite3.Row]] = defaultdict(list)
    for p in purchases:
        key = (
            p["purchase_date"],
            p["currency"],
            p["card_id"],
            p["payment_method"],
            p["installments_total"],
        )
        groups[key].append(p)
    return {k: v for k, v in groups.items() if len(v) > 1}


def amounts_close(a: float, b: float) -> bool:
    return abs(a - b) <= 0.02


# ---------------------------------------------------------------------------
# Winner selection
# ---------------------------------------------------------------------------

def pick_winner(a: sqlite3.Row, b: sqlite3.Row) -> tuple[sqlite3.Row, sqlite3.Row]:
    """Return (winner, loser). Winner has more metadata."""
    def score(p: sqlite3.Row) -> tuple:
        return (
            1 if p["category"] is not None else 0,
            1 if p["is_common"] else 0,
            1 if p["notes"] is not None else 0,
            p["payer_count"],
            -p["id"],  # smaller id wins ties
        )

    if score(a) >= score(b):
        return a, b
    return b, a


# ---------------------------------------------------------------------------
# Merge logic
# ---------------------------------------------------------------------------

def transfer_metadata(conn: sqlite3.Connection, winner: sqlite3.Row, loser: sqlite3.Row) -> None:
    updates: dict[str, object] = {}

    if winner["category"] is None and loser["category"] is not None:
        updates["category"] = loser["category"]
    if winner["notes"] is None and loser["notes"] is not None:
        updates["notes"] = loser["notes"]
    if not winner["is_common"] and loser["is_common"]:
        updates["is_common"] = 1

    if updates:
        set_clause = ", ".join(f"{col} = ?" for col in updates)
        conn.execute(
            f"UPDATE purchase SET {set_clause} WHERE id = ?",
            (*updates.values(), winner["id"]),
        )


def repoint_installments(conn: sqlite3.Connection, winner_id: int, loser_id: int) -> None:
    loser_rows = conn.execute(
        "SELECT installment_index FROM installmentschedule WHERE purchase_id = ?",
        (loser_id,),
    ).fetchall()

    winner_indexes = {
        r["installment_index"]
        for r in conn.execute(
            "SELECT installment_index FROM installmentschedule WHERE purchase_id = ?",
            (winner_id,),
        ).fetchall()
    }

    for row in loser_rows:
        idx = row["installment_index"]
        if idx not in winner_indexes:
            conn.execute(
                "UPDATE installmentschedule SET purchase_id = ? WHERE purchase_id = ? AND installment_index = ?",
                (winner_id, loser_id, idx),
            )
        else:
            conn.execute(
                "DELETE FROM installmentschedule WHERE purchase_id = ? AND installment_index = ?",
                (loser_id, idx),
            )


def repoint_payers(conn: sqlite3.Connection, winner_id: int, loser_id: int) -> None:
    conn.execute(
        "UPDATE purchasepayer SET purchase_id = ? WHERE purchase_id = ?",
        (winner_id, loser_id),
    )


def delete_loser(conn: sqlite3.Connection, loser_id: int) -> None:
    # Delete any remaining children (those not re-pointed above)
    conn.execute("DELETE FROM installmentschedule WHERE purchase_id = ?", (loser_id,))
    conn.execute("DELETE FROM purchasepayer WHERE purchase_id = ?", (loser_id,))
    conn.execute("DELETE FROM purchase WHERE id = ?", (loser_id,))


def merge_pair(
    conn: sqlite3.Connection,
    a: sqlite3.Row,
    b: sqlite3.Row,
    dry_run: bool,
) -> None:
    winner, loser = pick_winner(a, b)
    print(
        f"MERGED: kept #{winner['id']} '{winner['description']}', "
        f"removed #{loser['id']} '{loser['description']}'"
    )

    if not dry_run:
        transfer_metadata(conn, winner, loser)
        repoint_installments(conn, winner["id"], loser["id"])
        repoint_payers(conn, winner["id"], loser["id"])
        delete_loser(conn, loser["id"])


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Deduplicate purchases in admin-consumos DB.")
    parser.add_argument("--db", required=True, help="Path to SQLite database")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    args = parser.parse_args()

    db_path = args.db
    if not os.path.exists(db_path):
        print(f"ERROR: database not found at {db_path}", file=sys.stderr)
        sys.exit(1)

    conn = open_db(db_path)

    purchases = fetch_all_purchases(conn)
    groups = group_by_key(purchases)

    strict_pairs: list[tuple[sqlite3.Row, sqlite3.Row]] = []
    ambiguous_pairs: list[tuple[sqlite3.Row, sqlite3.Row]] = []

    for key, members in groups.items():
        # Compare all pairs in the group
        for i in range(len(members)):
            for j in range(i + 1, len(members)):
                a = members[i]
                b = members[j]

                if not amounts_close(a["amount_original"], b["amount_original"]):
                    continue  # amount too different — not a duplicate candidate

                norm_a = normalize_purchase_description(a["description"])
                norm_b = normalize_purchase_description(b["description"])

                if norm_a == norm_b:
                    strict_pairs.append((a, b))
                else:
                    ambiguous_pairs.append((a, b))

    # --- Deduplicate the pair lists (a purchase might appear in multiple pairs) ---
    # Process strict merges tracking which ids have already been consumed
    consumed: set[int] = set()
    merged_count = 0

    for a, b in strict_pairs:
        if a["id"] in consumed or b["id"] in consumed:
            continue
        merge_pair(conn, a, b, dry_run=args.dry_run)
        winner, loser = pick_winner(a, b)
        consumed.add(loser["id"])
        merged_count += 1

    # --- Ambiguous report ---
    script_dir = Path(__file__).parent
    review_file = script_dir / "dedupe_review.txt"

    ambiguous_lines: list[str] = [
        "=== Ambiguous purchase pairs (same date+amount, different description) ===\n"
        "Review manually and delete the duplicate if needed.\n"
    ]

    for a, b in ambiguous_pairs:
        if a["id"] in consumed or b["id"] in consumed:
            continue
        amount = a["amount_original"]
        currency = a["currency"]
        date = a["purchase_date"]
        print(
            f"AMBIGUOUS: #{a['id']} vs #{b['id']} — "
            f"'{a['description']}' vs '{b['description']}' "
            f"on {date} ${amount:.2f}"
        )
        ambiguous_lines.append(
            f"\n{date}  {currency} {amount:>12.2f}\n"
            f"  #{a['id']}: {a['description']}\n"
            f"  #{b['id']}: {b['description']}\n"
        )

    if ambiguous_pairs:
        if not args.dry_run:
            review_file.write_text("".join(ambiguous_lines), encoding="utf-8")
        else:
            print(f"[dry-run] Would write {len(ambiguous_pairs)} ambiguous pair(s) to {review_file}")

    # --- Commit or rollback ---
    if args.dry_run:
        conn.rollback()
        print(f"\n[dry-run] {merged_count} strict pair(s) would be merged, "
              f"{len(ambiguous_pairs)} ambiguous pair(s) would be written to {review_file.name}")
    else:
        conn.commit()
        print(f"\n{merged_count} strict pairs merged, "
              f"{len(ambiguous_pairs)} ambiguous pairs written to {review_file.name}")

    conn.close()


if __name__ == "__main__":
    main()

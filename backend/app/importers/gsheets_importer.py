import csv
import hashlib
import io
from datetime import datetime
from typing import Optional

import requests
from app.importers.visa_xlsx import ParsedPurchaseRow


def _generate_fingerprint(row: dict) -> str:
    """Generate a unique fingerprint for a row to prevent duplicates."""
    # We use a combination of fields that should be unique for a transfer
    # fecha, tipo, monto, moneda, descripcion
    payload = f"{row.get('fecha')}|{row.get('tipo')}|{row.get('monto')}|{row.get('moneda')}|{row.get('descripcion')}"
    return hashlib.sha256(payload.encode()).hexdigest()


def parse_gsheets_csv(csv_content: str) -> list[ParsedPurchaseRow]:
    """Parse CSV content from Google Sheets."""
    f = io.StringIO(csv_content.strip())
    reader = csv.DictReader(f)
    out = []

    for row in reader:
        # Example row:
        # fecha: 2026-02-19 00:00:00
        # tipo: compra (or transfer)
        # monto: 18464.36
        # moneda: ARS
        # descripcion: *MERPAGO*...

        try:
            raw_date = row.get("fecha", "")
            if " " in raw_date:
                raw_date = raw_date.split(" ")[0]
            purchase_date = datetime.strptime(raw_date, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            continue

        description = row.get("descripcion", "Sin descripción")
        amount = float(row.get("monto", 0))
        currency = row.get("moneda", "ARS")
        
        if amount <= 0:
            continue

        # Using statement_year_month as the month of the purchase for transfers
        statement_ym = purchase_date.strftime("%Y-%m")

        out.append(
            ParsedPurchaseRow(
                purchase_date=purchase_date,
                description=description,
                currency=currency,
                installment_index=1,
                installments_total=1,
                installment_amount=round(amount, 2),
                statement_year_month=statement_ym,
            )
        )

    return out


def download_gsheets_csv(url: str) -> str:
    """Download CSV from a Google Sheets URL."""
    # Convert standard sheet URL to direct export link if needed
    if "/edit" in url:
        url = url.split("/edit")[0] + "/export?format=csv"
    elif "/pubhtml" in url:
        url = url.split("/pubhtml")[0] + "/pub?output=csv"
    
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.text

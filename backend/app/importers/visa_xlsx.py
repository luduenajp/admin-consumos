from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import pandas as pd
from sqlmodel import Session, select

from app.models import ImportedRow


@dataclass(frozen=True)
class ParsedPurchaseRow:
    purchase_date: date
    description: str
    currency: str  # "ARS" | "USD"
    installment_index: int
    installments_total: int
    installment_amount: float
    statement_year_month: str  # YYYY-MM


def _parse_ddmmyyyy(value: object) -> Optional[date]:
    if value is None:
        return None

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    s = str(value).strip()
    if not s or s.lower() == "nan":
        return None

    for fmt in ("%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue

    return None


_money_clean_re = re.compile(r"[^0-9,\-]", re.UNICODE)


def _parse_money(value: object) -> Optional[float]:
    if value is None:
        return None

    s = str(value).strip()
    if not s or s.lower() == "nan":
        return None

    # Examples: "$1.443.685,70", "U$S24,51", "$-7.778,81", "U$S-17,87"
    s = s.replace(".", "")
    s = _money_clean_re.sub("", s)
    if not s:
        return None

    s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


_installments_re = re.compile(r"^(\d+)\s*de\s*(\d+)$", re.IGNORECASE)


def _parse_installments(value: object) -> tuple[int, int]:
    if value is None:
        return 1, 1

    s = str(value).strip()
    if not s or s.lower() == "nan":
        return 1, 1

    m = _installments_re.match(s)
    if not m:
        return 1, 1

    current = int(m.group(1))
    total = int(m.group(2))
    if total <= 0:
        return 1, 1

    current = max(1, min(current, total))
    return current, total


def _is_excluded_description(description: str) -> bool:
    d = description.strip().lower()
    # Heurística MVP para excluir filas no-consumo (pagos/promos/ajustes)
    excluded_prefixes = (
        "su pago",
        "promo",
        "cr.",
        "cr ",
        "total de",
        "tarjeta de",
        "tarjeta visa",
        "movimientos del resumen",
    )
    return d.startswith(excluded_prefixes)


def _detect_statement_year_month(df_raw: pd.DataFrame) -> Optional[str]:
    # Busca la fila donde aparece "Fecha de cierre" y toma el valor de la siguiente fila.
    # En el ejemplo: fila con ["Fecha de cierre", "Fecha de vencimiento"], y luego ["22/01/2026", "04/02/2026"].
    for i in range(len(df_raw) - 1):
        row = df_raw.iloc[i].astype(str).tolist()
        if any("fecha de cierre" in str(v).lower() for v in row):
            next_row = df_raw.iloc[i + 1].tolist()
            for v in next_row:
                d = _parse_ddmmyyyy(v)
                if d is not None:
                    return f"{d.year:04d}-{d.month:02d}"
    return None


def parse_visa_xlsx(path: Path) -> list[ParsedPurchaseRow]:
    df_raw = pd.read_excel(path, sheet_name=0, header=None)
    statement_ym = _detect_statement_year_month(df_raw)
    if statement_ym is None:
        raise ValueError("Could not detect statement year_month from XLSX")

    # Detect header row
    header_row_idx: Optional[int] = None
    for i in range(len(df_raw)):
        row = df_raw.iloc[i].astype(str).tolist()
        if any("descripción" in c.lower() for c in row) and any("monto en pesos" in c.lower() for c in row):
            header_row_idx = i
            break

    if header_row_idx is None:
        raise ValueError("Could not find movements table header in XLSX")

    header = df_raw.iloc[header_row_idx].tolist()
    df = df_raw.iloc[header_row_idx + 1 :].copy()
    df.columns = header
    df = df.dropna(how="all")

    out: list[ParsedPurchaseRow] = []

    for _, r in df.iterrows():
        d = _parse_ddmmyyyy(r.get("Fecha"))
        if d is None:
            continue

        description = str(r.get("Descripción") or "").strip()
        if not description:
            continue

        if _is_excluded_description(description):
            continue

        amount_ars = _parse_money(r.get("Monto en pesos"))
        amount_usd = _parse_money(r.get("Monto en dólares"))

        currency: Optional[str] = None
        amount: Optional[float] = None
        if amount_ars is not None and amount_ars != 0:
            currency = "ARS"
            amount = amount_ars
        elif amount_usd is not None and amount_usd != 0:
            currency = "USD"
            amount = amount_usd

        if currency is None or amount is None:
            continue

        # Excluir montos negativos (pagos/bonificaciones) por definición de MVP
        if amount <= 0:
            continue

        installment_index, installments_total = _parse_installments(r.get("Cuotas"))

        out.append(
            ParsedPurchaseRow(
                purchase_date=d,
                description=description,
                currency=currency,
                installment_index=installment_index,
                installments_total=installments_total,
                installment_amount=round(float(amount), 2),
                statement_year_month=statement_ym,
            )
        )

    return out


def compute_row_fingerprint(*, provider: str, card_id: int, row: ParsedPurchaseRow) -> str:
    payload = {
        "provider": provider,
        "card_id": card_id,
        "purchase_date": row.purchase_date.isoformat(),
        "description": row.description,
        "currency": row.currency,
        "installment_index": row.installment_index,
        "installments_total": row.installments_total,
        "installment_amount": row.installment_amount,
        "statement_year_month": row.statement_year_month,
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def was_already_imported(*, session: Session, fingerprint: str) -> bool:
    stmt = select(ImportedRow).where(ImportedRow.row_fingerprint == fingerprint)
    return session.exec(stmt).first() is not None


def mark_imported(*, session: Session, provider: str, source_file: str, fingerprint: str, payload: dict) -> None:
    session.add(
        ImportedRow(
            provider=provider,
            source_file=source_file,
            row_fingerprint=fingerprint,
            parsed_payload_json=json.dumps(payload, ensure_ascii=False),
        )
    )

"""Importador de resúmenes Visa en formato PDF (con o sin contraseña)."""

from __future__ import annotations

import io
import re
from datetime import date
from pathlib import Path
from typing import Optional

import pdfplumber
from pypdf import PdfReader, PdfWriter

from app.importers.visa_xlsx import (
    ParsedPurchaseRow,
    _is_excluded_description,
    _parse_ddmmyyyy,
    _parse_installments,
    _parse_money,
)


def _decrypt_pdf_to_bytes(path: Path, password: Optional[str] = None) -> bytes:
    """Desencripta el PDF si está protegido y devuelve los bytes."""
    reader = PdfReader(str(path))
    if reader.is_encrypted:
        if not password or not str(password).strip():
            raise ValueError("El PDF está protegido con contraseña. Proporcioná la contraseña para importar.")
        reader.decrypt(str(password).strip())
    buffer = io.BytesIO()
    writer = PdfWriter(clone_from=reader)
    writer.write(buffer)
    buffer.seek(0)
    return buffer.read()


def _normalize_header(cell: str) -> str:
    return str(cell or "").strip().lower()


def _find_column_indices(header_row: list[str]) -> Optional[dict[str, int]]:
    """Encuentra los índices de columna por nombre (fecha, descripción, monto, cuotas)."""
    normalized = [_normalize_header(c) for c in header_row]
    cols: dict[str, int] = {}

    # Fecha
    for i, h in enumerate(normalized):
        if "fecha" in h and "vencimiento" not in h and "cierre" not in h:
            cols["fecha"] = i
            break

    # Descripción
    for i, h in enumerate(normalized):
        if "descrip" in h or "concepto" in h or "detalle" in h:
            cols["descripcion"] = i
            break

    # Monto en pesos
    for i, h in enumerate(normalized):
        if "monto" in h and ("pesos" in h or "ars" in h) or "pesos" in h:
            cols["monto_ars"] = i
            break

    # Monto en dólares (opcional)
    for i, h in enumerate(normalized):
        if "monto" in h and ("dólar" in h or "dolar" in h or "usd" in h):
            cols["monto_usd"] = i
            break

    # Cuotas
    for i, h in enumerate(normalized):
        if "cuota" in h:
            cols["cuotas"] = i
            break

    if "fecha" not in cols or "descripcion" not in cols:
        return None

    if "monto_ars" not in cols and "monto_usd" not in cols:
        # Último intento: buscar alguna columna de monto
        for i, h in enumerate(normalized):
            if "monto" in h or "importe" in h:
                cols["monto_ars"] = i
                break

    return cols if cols else None


_MES_ABREV = {
    "ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6,
    "jul": 7, "ago": 8, "sep": 9, "oct": 10, "nov": 11, "dic": 12,
}

_MES_NOMBRE = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
}


def _parse_mes_yy(mes_abrev: str, yy: str) -> Optional[str]:
    """Convierte Mmm YY a YYYY-MM."""
    mes = _MES_ABREV.get(mes_abrev.lower())
    if not mes:
        return None
    y = 2000 + int(yy) if int(yy) < 50 else 1900 + int(yy)
    return f"{y:04d}-{mes:02d}"


def _detect_statement_year_month_from_text(text: str) -> Optional[str]:
    """Busca el mes de cierre en el texto del PDF."""
    # MercadoPago: "Cierre actual 5 de febrero" o "Este es tu resumen de febrero"
    m = re.search(
        r"(?:cierre\s+actual|resumen\s+de)\s+(?:\d+\s+de\s+)?(\w+)\b",
        text,
        re.IGNORECASE,
    )
    if m:
        mes_nombre = m.group(1).lower()
        mes = _MES_NOMBRE.get(mes_nombre) or _MES_ABREV.get(mes_nombre[:3])
        if mes:
            years = [int(x) for x in re.findall(r"\b(20\d{2})\b", text)]
            y = max(years) if years else 2026
            return f"{y:04d}-{mes:02d}"

    # MercadoPago / genérico: "Fecha de cierre: 22/01/2026" o "Cierre: 22/01/2026"
    m = re.search(
        r"(?:fecha\s+de\s+cierre|cierre)[:\s]+(\d{1,2})/(\d{1,2})/(\d{4})\b",
        text,
        re.IGNORECASE,
    )
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return f"{y:04d}-{mo:02d}"

    # Banco Nación Visa: "CIERRE ACTUAL: 22 Ene 26" (DD Mmm YY)
    m = re.search(r"cierre\s+actual[:\s]+(\d{1,2})\s+(\w{3})\s+(\d{2})\b", text, re.IGNORECASE)
    if m:
        mes_abrev, yy = m.group(2), m.group(3)
        if mes_abrev.lower() in _MES_ABREV:
            return _parse_mes_yy(mes_abrev, yy)

    # Banco Nación Mastercard: "Estado de cuenta al : 22-Ene-26" o "Cierre Anterior : 24-Dic-25"
    m = re.search(r"(?:estado\s+de\s+cuenta\s+al|cierre\s+anterior)[:\s]+(\d{1,2})[-](\w{3})[-](\d{2})\b", text, re.IGNORECASE)
    if m:
        mes_abrev, yy = m.group(2), m.group(3)
        if mes_abrev.lower() in _MES_ABREV:
            return _parse_mes_yy(mes_abrev, yy)

    # Patrones: "Fecha de cierre: 22/01/2026", "Cierre: 22-01-2026"
    patterns = [
        r"fecha\s+de\s+cierre[:\s]+(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})",
        r"cierre[:\s]+(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})",
        r"(\d{1,2})[/\-](\d{1,2})[/\-](\d{4}).*cierre",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            groups = m.groups()
            if len(groups) >= 3:
                d, mo, y = int(groups[0]), int(groups[1]), int(groups[2])
                return f"{y:04d}-{mo:02d}"
            elif len(groups) == 2:
                mo, y = int(groups[0]), int(groups[1])
                return f"{y:04d}-{mo:02d}"
    return None


# Monto: con o sin separador de miles (55863,54 o 1.234,56)
_MONTO_RE = r"-?\d{1,3}(?:\.\d{3})*,\d{2}|-?\d+,\d{2}"

# Banco Nación Mastercard: "DD-Mmm-YY descripción X/Y comprobante monto"
_LINEA_MASTERCARD_RE = re.compile(
    rf"^(\d{{1,2}})-(\w{{3}})-(\d{{2}})\s+(.+?)\s+(\d+)/(\d+)\s+\d+\s+({_MONTO_RE})\s*$",
    re.MULTILINE,
)

# Formato Banco Nación Visa: "DD.MM.YY comprobante descripción C.X/Y monto_pesos monto_usd"
_LINEA_MOVIMIENTO_RE = re.compile(
    r"^(\d{2})\.(\d{2})\.(\d{2})\s+"  # fecha DD.MM.YY
    r"(.+?)\s+"  # descripción (hasta los montos)
    r"(-?\d{1,3}(?:\.\d{3})*,\d{2}|-?\d+,\d{2})\s+"  # pesos
    r"(-?\d{1,3}(?:\.\d{3})*,\d{2}|-?\d+,\d{2})\s*$",  # dólares
    re.MULTILINE,
)


def _parse_nacion_text_format(full_text: str, statement_ym: str) -> list[ParsedPurchaseRow]:
    """Parsea formato Banco Nación: FECHA COMPROBANTE DETALLE DE TRANSACCION PESOS DOLAR."""
    out: list[ParsedPurchaseRow] = []
    in_movements = False

    for line in full_text.splitlines():
        line = line.strip()
        if "FECHA COMPROBANTE DETALLE" in line.upper() and "PESOS" in line.upper():
            in_movements = True
            continue
        if not in_movements:
            continue

        m = _LINEA_MOVIMIENTO_RE.match(line)
        if not m:
            # Línea sin fecha al inicio puede ser continuación de la anterior
            continue

        dd, mm, yy = int(m.group(1)), int(m.group(2)), int(m.group(3))
        year = 2000 + yy if yy < 50 else 1900 + yy
        try:
            purchase_date = date(year, mm, dd)
        except ValueError:
            continue

        description = m.group(4).strip()
        if not description or _is_excluded_description(description):
            continue

        amount_ars = _parse_money(m.group(5))
        amount_usd = _parse_money(m.group(6))

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
        if amount <= 0:
            continue

        installment_index, installments_total = _parse_installments(description)

        out.append(
            ParsedPurchaseRow(
                purchase_date=purchase_date,
                description=description,
                currency=currency,
                installment_index=installment_index,
                installments_total=installments_total,
                installment_amount=round(float(amount), 2),
                statement_year_month=statement_ym,
            )
        )

    return out


def _parse_nacion_mastercard_format(full_text: str, statement_ym: str) -> list[ParsedPurchaseRow]:
    """Parsea formato Banco Nación Mastercard: DETALLES DEL MES / CUOTAS DEL MES."""
    out: list[ParsedPurchaseRow] = []
    in_movements = False

    for line in full_text.splitlines():
        line = line.strip()
        if "DETALLES DEL MES" in line.upper() or "CUOTAS DEL MES" in line.upper():
            in_movements = True
            continue
        if not in_movements:
            continue

        m = _LINEA_MASTERCARD_RE.match(line)
        if not m:
            # Líneas como "TOTAL TITULAR..." terminan la sección
            if "TOTAL" in line.upper():
                break
            continue

        dd, mes_abrev, yy = int(m.group(1)), m.group(2), int(m.group(3))
        mes = _MES_ABREV.get(mes_abrev.lower())
        if not mes:
            continue
        year = 2000 + yy if yy < 50 else 1900 + yy
        try:
            purchase_date = date(year, mes, dd)
        except ValueError:
            continue

        description = m.group(4).strip()
        if not description or _is_excluded_description(description):
            continue

        installment_index, installments_total = int(m.group(5)), int(m.group(6))
        amount = _parse_money(m.group(7))
        if amount is None or amount <= 0:
            continue

        out.append(
            ParsedPurchaseRow(
                purchase_date=purchase_date,
                description=description,
                currency="ARS",
                installment_index=installment_index,
                installments_total=installments_total,
                installment_amount=round(float(amount), 2),
                statement_year_month=statement_ym,
            )
        )

    return out


# MercadoPago Mastercard (formato app): "10/nov MERPAGO*MERCADOLIBRE 3 de 3 304823 $ 22.293,25"
# o "13/ene SENA YPF 221482 $ 49.000,00" o "6/ene Pago de tarjeta -$ 457.199,78"
_LINEA_MERCADOPAGO_APP_RE = re.compile(
    r"^(\d{1,2})/(\w{3})\s+"  # DD/mmm
    r"(.+?)\s+"  # descripción
    r"(-?\$?\s*)([\d.,]+)\s*$",  # signo opcional + monto
    re.MULTILINE,
)

# MercadoPago PDF alternativo: DD/MM/YYYY + descripción + monto
_LINEA_MERCADOPAGO_RE = re.compile(
    r"^(\d{1,2})/(\d{1,2})/(\d{2,4})\s+"
    r"(.+?)\s+"
    r"(-?\d{1,3}(?:\.\d{3})*,\d{2}|-?\d+,\d{2})\s*"
    r"(-?\d{1,3}(?:\.\d{3})*,\d{2}|-?\d+,\d{2})?\s*$",
    re.MULTILINE,
)


def _parse_mercadopago_app_format(full_text: str, statement_ym: str) -> list[ParsedPurchaseRow]:
    """Parsea formato MercadoPago app: DD/mmm descripción $ monto."""
    out: list[ParsedPurchaseRow] = []
    stmt_year, stmt_month = int(statement_ym[:4]), int(statement_ym[5:7])

    for line in full_text.splitlines():
        line = line.strip()
        if not line:
            continue

        m = _LINEA_MERCADOPAGO_APP_RE.match(line)
        if not m:
            continue

        dd, mes_abrev = int(m.group(1)), m.group(2).lower()
        mes = _MES_ABREV.get(mes_abrev[:3])
        if not mes:
            continue

        # Año: si el mes de la compra es posterior al cierre, es año anterior
        year = stmt_year - 1 if mes > stmt_month else stmt_year

        try:
            purchase_date = date(year, mes, dd)
        except ValueError:
            continue

        description = m.group(3).strip()
        if not description or len(description) < 3 or _is_excluded_description(description):
            continue
        if description.upper() in ("FECHA", "DESCRIPCION", "DETALLE", "MOVIMIENTOS", "PESOS", "DÓLARES"):
            continue

        sign_str, amount_str = m.group(4), m.group(5)
        amount_raw = ("-" if "-" in sign_str else "") + amount_str
        amount = _parse_money(amount_raw)
        if amount is None or amount <= 0:
            continue

        installment_index, installments_total = _parse_installments(description)

        out.append(
            ParsedPurchaseRow(
                purchase_date=purchase_date,
                description=description,
                currency="ARS",
                installment_index=installment_index,
                installments_total=installments_total,
                installment_amount=round(float(amount), 2),
                statement_year_month=statement_ym,
            )
        )

    return out


def _parse_mercadopago_format(full_text: str, statement_ym: str) -> list[ParsedPurchaseRow]:
    """Parsea formato MercadoPago PDF alternativo (DD/MM/YYYY)."""
    out: list[ParsedPurchaseRow] = []

    for line in full_text.splitlines():
        line = line.strip()
        if not line:
            continue

        m = _LINEA_MERCADOPAGO_RE.match(line)
        if not m:
            continue

        dd, mm = int(m.group(1)), int(m.group(2))
        yy_str = m.group(3)
        yy = int(yy_str) if len(yy_str) == 2 else int(yy_str)
        year = yy if yy > 100 else (2000 + yy if yy < 50 else 1900 + yy)

        try:
            purchase_date = date(year, mm, dd)
        except ValueError:
            continue

        description = m.group(4).strip()
        if not description or len(description) < 3 or _is_excluded_description(description):
            continue
        if description.upper() in ("FECHA", "DESCRIPCION", "DETALLE", "MOVIMIENTOS"):
            continue

        amount_ars = _parse_money(m.group(5))
        amount_usd = _parse_money(m.group(6)) if m.group(6) else None

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
        if amount <= 0:
            continue

        installment_index, installments_total = _parse_installments(description)

        out.append(
            ParsedPurchaseRow(
                purchase_date=purchase_date,
                description=description,
                currency=currency,
                installment_index=installment_index,
                installments_total=installments_total,
                installment_amount=round(float(amount), 2),
                statement_year_month=statement_ym,
            )
        )

    return out


def parse_visa_pdf(path: Path, password: Optional[str] = None) -> list[ParsedPurchaseRow]:
    """
    Parsea un resumen de tarjeta Visa en formato PDF.

    Si el PDF está protegido con contraseña, debe pasarse por `password`.
    """
    raw_bytes = _decrypt_pdf_to_bytes(path, password)

    with pdfplumber.open(io.BytesIO(raw_bytes)) as pdf:
        all_tables: list[list[list[str]]] = []
        full_text = ""

        for page in pdf.pages:
            tables = page.extract_tables()
            if tables:
                all_tables.extend(tables)
            text = page.extract_text()
            if text:
                full_text += text + "\n"

    statement_ym = _detect_statement_year_month_from_text(full_text)
    if not statement_ym:
        raise ValueError("No se pudo detectar el mes de cierre del resumen en el PDF")

    # Banco Nación / MercadoPago: movimientos en texto
    out = _parse_nacion_text_format(full_text, statement_ym)
    if not out:
        out = _parse_nacion_mastercard_format(full_text, statement_ym)
    if not out:
        out = _parse_mercadopago_app_format(full_text, statement_ym)
    if not out:
        out = _parse_mercadopago_format(full_text, statement_ym)
    if out:
        return out

    # Otros formatos: tablas con encabezados
    out = []
    header_indices: Optional[dict[str, int]] = None

    for table in all_tables:
        if not table:
            continue

        for row_idx, row in enumerate(table):
            row_cells = [str(c or "").strip() for c in row]
            if not any(row_cells):
                continue

            # Buscar fila de encabezado
            if header_indices is None:
                header_indices = _find_column_indices(row_cells)
                if header_indices:
                    continue
                else:
                    header_indices = None
                    continue

            # Parsear fila de datos
            fecha = None
            if "fecha" in header_indices:
                idx = header_indices["fecha"]
                if idx < len(row_cells):
                    fecha = _parse_ddmmyyyy(row_cells[idx])

            if fecha is None:
                continue

            descripcion = ""
            if "descripcion" in header_indices:
                idx = header_indices["descripcion"]
                if idx < len(row_cells):
                    descripcion = row_cells[idx].strip()

            if not descripcion or _is_excluded_description(descripcion):
                continue

            amount_ars = None
            amount_usd = None
            if "monto_ars" in header_indices:
                idx = header_indices["monto_ars"]
                if idx < len(row_cells):
                    amount_ars = _parse_money(row_cells[idx])
            if "monto_usd" in header_indices:
                idx = header_indices["monto_usd"]
                if idx < len(row_cells):
                    amount_usd = _parse_money(row_cells[idx])

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

            if amount <= 0:
                continue

            cuotas_val = None
            if "cuotas" in header_indices:
                idx = header_indices["cuotas"]
                if idx < len(row_cells):
                    cuotas_val = row_cells[idx]
            installment_index, installments_total = _parse_installments(cuotas_val)

            out.append(
                ParsedPurchaseRow(
                    purchase_date=fecha,
                    description=descripcion,
                    currency=currency,
                    installment_index=installment_index,
                    installments_total=installments_total,
                    installment_amount=round(float(amount), 2),
                    statement_year_month=statement_ym,
                )
            )

        header_indices = None

    return out

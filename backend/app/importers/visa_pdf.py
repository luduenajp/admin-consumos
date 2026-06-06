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


def _detect_statement_year_month_from_text(text: str) -> tuple[Optional[str], Optional[date]]:
    """Busca el mes y fecha exacta de cierre en el texto del PDF."""
    # MercadoPago: "Cierre actual 5 de febrero" o "Este es tu resumen de febrero"
    m = re.search(
        r"(cierre\s+actual|resumen\s+de)\s+(?:(\d+)\s+de\s+)?(\w+)\b",
        text,
        re.IGNORECASE,
    )
    if m:
        prefix = m.group(1).lower()
        day_str = m.group(2)
        mes_nombre = m.group(3).lower()
        mes = _MES_NOMBRE.get(mes_nombre) or _MES_ABREV.get(mes_nombre[:3])
        if mes:
            years = [int(x) for x in re.findall(r"\b(20\d{2})\b", text)]
            y = max(years) if years else 2026

            # Si dice "resumen de X", X es el mes de vencimiento. El mes de cierre lógico es el anterior.
            if "resumen de" in prefix:
                mes -= 1
                if mes == 0:
                    mes = 12
                    y -= 1

            ym = f"{y:04d}-{mes:02d}"
            close_date: Optional[date] = None
            if day_str:
                try:
                    close_date = date(y, mes, int(day_str))
                except ValueError:
                    pass
            return ym, close_date

    # MercadoPago / genérico: "Fecha de cierre: 22/01/2026" o "Cierre: 22/01/2026"
    m = re.search(
        r"(?:fecha\s+de\s+cierre|cierre)[:\s]+(\d{1,2})/(\d{1,2})/(\d{4})\b",
        text,
        re.IGNORECASE,
    )
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            return f"{y:04d}-{mo:02d}", date(y, mo, d)
        except ValueError:
            return f"{y:04d}-{mo:02d}", None

    # Banco Nación Visa: "CIERRE ACTUAL: 21 May 26" (DD Mmm YY)
    m = re.search(r"cierre\s+actual[:\s]+(\d{1,2})\s+(\w{3})\s+(\d{2})\b", text, re.IGNORECASE)
    if m:
        dd, mes_abrev, yy = int(m.group(1)), m.group(2), m.group(3)
        if mes_abrev.lower() in _MES_ABREV:
            ym = _parse_mes_yy(mes_abrev, yy)
            if ym:
                y2, mo2 = int(ym[:4]), int(ym[5:7])
                try:
                    return ym, date(y2, mo2, dd)
                except ValueError:
                    return ym, None

    # Banco Nación Mastercard: "Estado de cuenta al : 22-Ene-26" o "Cierre Anterior : 24-Dic-25"
    m = re.search(r"(?:estado\s+de\s+cuenta\s+al|cierre\s+anterior)[:\s]+(\d{1,2})[-](\w{3})[-](\d{2})\b", text, re.IGNORECASE)
    if m:
        dd, mes_abrev, yy = int(m.group(1)), m.group(2), m.group(3)
        if mes_abrev.lower() in _MES_ABREV:
            ym = _parse_mes_yy(mes_abrev, yy)
            if ym:
                y2, mo2 = int(ym[:4]), int(ym[5:7])
                try:
                    return ym, date(y2, mo2, dd)
                except ValueError:
                    return ym, None

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
                try:
                    return f"{y:04d}-{mo:02d}", date(y, mo, d)
                except ValueError:
                    return f"{y:04d}-{mo:02d}", None
            elif len(groups) == 2:
                mo, y = int(groups[0]), int(groups[1])
                return f"{y:04d}-{mo:02d}", None
    return None, None


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


def _parse_nacion_text_format(full_text: str, statement_ym: str, statement_close_date: Optional[date] = None) -> list[ParsedPurchaseRow]:
    """Parsea formato Banco Nación: FECHA COMPROBANTE DETALLE DE TRANSACCION PESOS DOLAR."""
    out: list[ParsedPurchaseRow] = []
    in_movements = False

    # Track occurrences of identical rows in this file to handle multiple same-day identical purchases
    # Key: (date, description, amount, current_installment, total_installments)
    occurrence_tracker: dict[tuple, int] = {}

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

        cols = m.groups()
        dd, mm, yy = int(cols[0]), int(cols[1]), int(cols[2])
        year = 2000 + yy if yy < 50 else 1900 + yy
        try:
            purchase_date = date(year, mm, dd)
        except ValueError:
            continue

        description = cols[3].strip()
        if not description or _is_excluded_description(description):
            continue

        amount_ars = _parse_money(cols[4])
        amount_usd = _parse_money(cols[5])

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
        amount_val = round(float(amount), 2)

        # Update occurrence count
        row_key = (purchase_date, description, amount_val, installment_index, installments_total)
        occ_index = occurrence_tracker.get(row_key, 0) + 1
        occurrence_tracker[row_key] = occ_index

        out.append(
            ParsedPurchaseRow(
                purchase_date=purchase_date,
                description=description,
                currency=currency,
                installment_index=installment_index,
                installments_total=installments_total,
                installment_amount=amount_val,
                statement_year_month=statement_ym,
                occurrence_index=occ_index,
                statement_close_date=statement_close_date,
            )
        )

    return out


def _parse_nacion_mastercard_format(full_text: str, statement_ym: str, statement_close_date: Optional[date] = None) -> list[ParsedPurchaseRow]:
    """Parsea formato Banco Nación Mastercard: DETALLES DEL MES / CUOTAS DEL MES."""
    out: list[ParsedPurchaseRow] = []
    in_movements = False

    # Track occurrences
    occurrence_tracker: dict[tuple, int] = {}

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

        amount_val = round(float(amount), 2)
        # Update occurrence count
        row_key = (purchase_date, description, amount_val, installment_index, installments_total)
        occ_index = occurrence_tracker.get(row_key, 0) + 1
        occurrence_tracker[row_key] = occ_index

        out.append(
            ParsedPurchaseRow(
                purchase_date=purchase_date,
                description=description,
                currency="ARS",
                installment_index=installment_index,
                installments_total=installments_total,
                installment_amount=amount_val,
                statement_year_month=statement_ym,
                occurrence_index=occ_index,
                statement_close_date=statement_close_date,
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


def _parse_mercadopago_app_format(full_text: str, statement_ym: str, statement_close_date: Optional[date] = None) -> list[ParsedPurchaseRow]:
    """Parsea formato MercadoPago app: DD/mmm descripción $ monto."""
    out: list[ParsedPurchaseRow] = []
    stmt_year, stmt_month = int(statement_ym[:4]), int(statement_ym[5:7])

    # Track occurrences
    occurrence_tracker: dict[tuple, int] = {}

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
        amount_val = round(float(amount), 2)

        # Update occurrence count
        row_key = (purchase_date, description, amount_val, installment_index, installments_total)
        occ_index = occurrence_tracker.get(row_key, 0) + 1
        occurrence_tracker[row_key] = occ_index

        out.append(
            ParsedPurchaseRow(
                purchase_date=purchase_date,
                description=description,
                currency="ARS",
                installment_index=installment_index,
                installments_total=installments_total,
                installment_amount=amount_val,
                statement_year_month=statement_ym,
                occurrence_index=occ_index,
                statement_close_date=statement_close_date,
            )
        )

    return out


def _parse_mercadopago_format(full_text: str, statement_ym: str, statement_close_date: Optional[date] = None) -> list[ParsedPurchaseRow]:
    """Parsea formato MercadoPago PDF alternativo (DD/MM/YYYY)."""
    out: list[ParsedPurchaseRow] = []

    # Track occurrences
    occurrence_tracker: dict[tuple, int] = {}

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
        amount_val = round(float(amount), 2)

        # Update occurrence count
        row_key = (purchase_date, description, amount_val, installment_index, installments_total)
        occ_index = occurrence_tracker.get(row_key, 0) + 1
        occurrence_tracker[row_key] = occ_index

        out.append(
            ParsedPurchaseRow(
                purchase_date=purchase_date,
                description=description,
                currency=currency,
                installment_index=installment_index,
                installments_total=installments_total,
                installment_amount=amount_val,
                statement_year_month=statement_ym,
                occurrence_index=occ_index,
                statement_close_date=statement_close_date,
            )
        )

    return out


def extract_holder_hint_pdf(
    full_text: str,
) -> tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
    """
    Extrae (holder_name, last4, card_type, bank) del texto completo de un PDF de resumen.
    Retorna (None, None, None, None) si no se puede detectar.

    Patrones validados:
    - Banco Nación Visa:       "TITULAR DE CUENTA ONTIVERO CINTIA DEL VALLE" / "VISA PLATINUM" / "NACION"
    - Banco Nación Mastercard: "TOTAL TITULAR ONTIVERO CINTIA DEL" / "MASTERCARD PLATINUM" / CUIT 30-50001091-2
    - MercadoPago:             "¡Hola, Juan Pablo!" → Mastercard / mercadopago
    """
    holder_name: Optional[str] = None
    last4: Optional[str] = None
    card_type: Optional[str] = None
    bank: Optional[str] = None

    # --- Card type ---
    if re.search(r"\bVISA\b", full_text, re.IGNORECASE):
        card_type = "Visa"
    elif re.search(r"\bMASTERCARD\b", full_text, re.IGNORECASE):
        card_type = "Mastercard"

    # --- Bank ---
    # MercadoPago: saludo característico (siempre es Mastercard)
    if re.search(r"[¡!]?Hola[,\s]", full_text):
        bank = "mercadopago"
        if card_type is None:
            card_type = "Mastercard"
    elif re.search(r"\bNACION\b", full_text, re.IGNORECASE) or "30-50001091-2" in full_text:
        bank = "nacion"
    elif re.search(r"\bSANTANDER\b", full_text, re.IGNORECASE):
        bank = "santander"

    # --- Holder name & last4 ---

    # Banco Nación Visa: "TITULAR DE CUENTA ONTIVERO CINTIA DEL VALLE" (línea completa)
    m = re.search(r"TITULAR\s+DE\s+CUENTA\s+([A-Z][A-Z ]+)$", full_text, re.MULTILINE)
    if m:
        holder_name = m.group(1).strip()

    # Banco Nación Visa: "TARJETA 9694 Total Consumos de NOMBRE ..."
    # Primer match = tarjeta del titular principal
    if last4 is None or holder_name is None:
        m = re.search(
            r"TARJETA\s+(\d{4})\s+Total\s+Consumos\s+de\s+([A-Z][A-Z ]+?)\s+[\d,]",
            full_text,
        )
        if m:
            if last4 is None:
                last4 = m.group(1)
            if holder_name is None:
                holder_name = m.group(2).strip()

    # Banco Nación Mastercard: "TOTAL TITULAR NOMBRE APELLIDO 94323,54"
    if holder_name is None:
        m = re.search(r"TOTAL\s+TITULAR\s+([A-Z][A-Z ]+?)\s+[\d,]", full_text)
        if m:
            holder_name = m.group(1).strip()

    # MercadoPago: "¡Hola, Juan Pablo!"
    if holder_name is None:
        m = re.search(r"[¡!]?Hola[,\s]+([^!¡\n]{2,40})[!¡]", full_text)
        if m:
            holder_name = m.group(1).strip().rstrip(",")

    return holder_name, last4, card_type, bank


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

    statement_ym, statement_close_date = _detect_statement_year_month_from_text(full_text)
    if not statement_ym:
        raise ValueError("No se pudo detectar el mes de cierre del resumen en el PDF")

    # Banco Nación / MercadoPago: movimientos en texto
    out = _parse_nacion_text_format(full_text, statement_ym, statement_close_date)
    if not out:
        out = _parse_nacion_mastercard_format(full_text, statement_ym, statement_close_date)
    if not out:
        out = _parse_mercadopago_app_format(full_text, statement_ym, statement_close_date)
    if not out:
        out = _parse_mercadopago_format(full_text, statement_ym, statement_close_date)
    if out:
        return out

    # Otros formatos: tablas con encabezados
    out = []
    header_indices: Optional[dict[str, int]] = None

    # Track occurrences
    occurrence_tracker: dict[tuple, int] = {}

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
            amount_val = round(float(amount), 2)

            # Update occurrence count
            row_key = (fecha, descripcion, amount_val, installment_index, installments_total)
            occ_index = occurrence_tracker.get(row_key, 0) + 1
            occurrence_tracker[row_key] = occ_index

            out.append(
                ParsedPurchaseRow(
                    purchase_date=fecha,
                    description=descripcion,
                    currency=currency,
                    installment_index=installment_index,
                    installments_total=installments_total,
                    installment_amount=amount_val,
                    statement_year_month=statement_ym,
                    occurrence_index=occ_index,
                    statement_close_date=statement_close_date,
                )
            )

        header_indices = None

    return out

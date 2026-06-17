"""Local extraction fallback for comprobantes when Claude API is unavailable.

Supports:
- PDFs via pdfplumber (always available)
- Images via pytesseract + Pillow (optional — gracefully skipped if not installed)

Handles common Argentine bank transfer formats: Santander, BNA, MercadoPago.
"""
from __future__ import annotations

import io
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class LocalExtraction:
    monto: Optional[float] = None
    fecha: Optional[str] = None  # YYYY-MM-DD
    moneda: str = "ARS"
    nombre: Optional[str] = None
    cbu: Optional[str] = None
    cuit: Optional[str] = None
    alias: Optional[str] = None


def extract_from_pdf(file_bytes: bytes) -> LocalExtraction:
    import pdfplumber

    text = ""
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            text += (page.extract_text() or "") + "\n"

    return _parse_text(text)


def extract_from_image(file_bytes: bytes) -> LocalExtraction:
    try:
        import pytesseract
        from PIL import Image

        img = Image.open(io.BytesIO(file_bytes))
        text = pytesseract.image_to_string(img, lang="spa")
        return _parse_text(text)
    except ImportError:
        return LocalExtraction()


def _parse_text(text: str) -> LocalExtraction:
    result = LocalExtraction()
    text_up = text.upper()

    # --- Monto ---
    # Matches: "Importe: $ 1.234,56", "$ 1.234,56", "1.234,56 ARS"
    for pattern in [
        r"(?:IMPORTE|MONTO|TOTAL)[:\s]+\$?\s*([\d.]+,\d{2})",
        r"\$\s*([\d.]+,\d{2})",
        r"\b([\d]{1,3}(?:\.\d{3})+,\d{2})\b",
    ]:
        m = re.search(pattern, text_up)
        if m:
            try:
                result.monto = float(m.group(1).replace(".", "").replace(",", "."))
                break
            except ValueError:
                continue

    # --- Fecha ---
    # DD/MM/YYYY or YYYY-MM-DD
    for raw_pattern, fmt in [
        (r"\b(\d{2}/\d{2}/\d{4})\b", "%d/%m/%Y"),
        (r"\b(\d{4}-\d{2}-\d{2})\b", "%Y-%m-%d"),
    ]:
        m = re.search(raw_pattern, text)
        if m:
            try:
                result.fecha = datetime.strptime(m.group(1), fmt).strftime("%Y-%m-%d")
                break
            except ValueError:
                continue

    # --- Moneda ---
    if re.search(r"\bUSD\b|\bDÓLAR\b|\bDOLAR\b", text_up):
        result.moneda = "USD"

    # --- CBU (22 dígitos consecutivos) ---
    m = re.search(r"\b(\d{22})\b", text)
    if m:
        result.cbu = m.group(1)

    # --- CUIT/CUIL ---
    m = re.search(r"\b(\d{2})[-\s]?(\d{8})[-\s]?(\d{1})\b", text)
    if m:
        result.cuit = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"

    # --- Alias ---
    m = re.search(r"(?:ALIAS|CVU)[:\s]+([A-Z0-9][A-Z0-9.\-]{3,29})", text_up)
    if m:
        result.alias = m.group(1).lower()

    # --- Nombre del destinatario ---
    NOISE = {"IMPORTE", "MONTO", "FECHA", "BANCO", "TRANSFERENCIA", "COMPROBANTE"}
    for pattern in [
        r"(?:DESTINATARIO|BENEFICIARIO|ACREDITADO|A/C)[:\s]+([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ\s]{2,49})",
        r"(?:PARA|PARA:)\s+([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ\s]{2,49})",
    ]:
        m = re.search(pattern, text_up)
        if m:
            name = m.group(1).strip()
            if not any(k in name for k in NOISE):
                result.nombre = name.title()
                break

    return result

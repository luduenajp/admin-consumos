#!/usr/bin/env python3
"""
Script para validar el formato de PDFs de resumen.
Uso: python validate_pdf.py <archivo.pdf> [contraseña] [--debug]

Ejemplo:
  python validate_pdf.py 73072_0989516695.pdf mi_contraseña
  python validate_pdf.py 73072_0989516695.pdf mi_contraseña --debug  # ver estructura raw
"""
import sys
from pathlib import Path

# Agregar backend al path
_project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_project_root / "backend"))


def dump_raw_structure(pdf_path: Path, password: str | None) -> None:
    """Imprime la estructura cruda del PDF (tablas, headers) para depuración."""
    import io
    from pypdf import PdfReader, PdfWriter
    import pdfplumber

    reader = PdfReader(str(pdf_path))
    if reader.is_encrypted:
        if not password:
            print("PDF encriptado. Pasá la contraseña como segundo argumento.")
            return
        reader.decrypt(password)
    buf = io.BytesIO()
    writer = PdfWriter(clone_from=reader)
    writer.write(buf)
    buf.seek(0)

    with pdfplumber.open(buf) as pdf:
        for pnum, page in enumerate(pdf.pages):
            tables = page.extract_tables()
            text = page.extract_text()
            print(f"\n--- Página {pnum + 1} ---")
            if text:
                print("Texto (primeros 2400 chars):")
                print(text[:2400])
            if tables:
                print(f"\nTablas: {len(tables)}")
                for ti, t in enumerate(tables):
                    print(f"  Tabla {ti + 1} ({len(t)} filas):")
                    for ri, row in enumerate(t[:5]):
                        print(f"    {ri}: {row}")
                    if len(t) > 5:
                        print(f"    ... ({len(t) - 5} filas más)")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    debug = "--debug" in sys.argv

    if len(args) < 1:
        print(__doc__)
        sys.exit(1)

    pdf_path = Path(args[0])
    if not pdf_path.is_absolute() and not pdf_path.exists():
        # Si no existe desde cwd, buscar en la carpeta examples
        alt = Path(__file__).parent / pdf_path.name
        if alt.exists():
            pdf_path = alt
    password = args[1] if len(args) > 1 else None

    if not pdf_path.exists():
        print(f"Error: no existe {pdf_path}")
        sys.exit(1)

    if debug:
        dump_raw_structure(pdf_path, password)
        return

    try:
        from app.importers.visa_pdf import parse_visa_pdf

        rows = parse_visa_pdf(pdf_path, password=password)
        print(f"✓ Parseado OK: {len(rows)} movimientos")
        if rows:
            print("\nPrimeros 3 movimientos:")
            for i, r in enumerate(rows[:3], 1):
                desc = r.description[:40] + "..." if len(r.description) > 40 else r.description
                print(f"  {i}. {r.purchase_date} | {desc} | {r.currency} {r.installment_amount} | cuota {r.installment_index}/{r.installments_total}")
    except Exception as e:
        print(f"✗ Error: {e}")
        print("\nEjecutá con --debug para ver la estructura del PDF:")
        print(f"  python validate_pdf.py {args[0]} {password or ''} --debug")
        sys.exit(1)


if __name__ == "__main__":
    main()

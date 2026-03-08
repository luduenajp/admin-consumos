import re
from app.importers.visa_pdf import _MES_ABREV, _MES_NOMBRE

def test_detect():
    texts = [
        "Cierre actual 5 de febrero",
        "Este es tu resumen de marzo",
    ]
    for text in texts:
        m = re.search(
            r"(cierre\s+actual|resumen\s+de)\s+(?:\d+\s+de\s+)?(\w+)\b",
            text,
            re.IGNORECASE,
        )
        if m:
            prefix = m.group(1).lower()
            mes_nombre = m.group(2).lower()
            mes = _MES_NOMBRE.get(mes_nombre) or _MES_ABREV.get(mes_nombre[:3])
            
            if mes is not None:
                y = 2026
                if "resumen de" in prefix:
                    mes -= 1
                    if mes == 0:
                        mes = 12
                        y -= 1
                print(f"'{text}' => {y:04d}-{mes:02d}")

if __name__ == "__main__":
    test_detect()

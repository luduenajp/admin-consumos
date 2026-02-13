# Ejemplos de importación

PDFs de resumen de tarjeta para validar el importador.

Formatos soportados: Banco Nación (Visa/Mastercard), MercadoPago Mastercard (app/web).

## Validar formato

Para probar que el parser lee correctamente tus PDFs:

```bash
# Desde la raíz del proyecto
cd backend && pip install -r requirements.txt
cd ../examples
python validate_pdf.py 73072_0989516695.pdf <tu_contraseña>
```

Si falla el parseo, ejecutá con `--debug` para ver la estructura interna del PDF:

```bash
python validate_pdf.py 73072_0989516695.pdf <tu_contraseña> --debug
```

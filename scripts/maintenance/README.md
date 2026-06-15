# scripts/maintenance/

Scripts **one-off** ya ejecutados, archivados para referencia histórica.
**No son parte del sistema en ejecución** ni se corren en CI/deploy. Muchos
tienen rutas o fechas hardcodeadas de la corrida original; si los necesitás
de nuevo, tratalos como punto de partida, no como herramientas listas.

| Archivo | Qué hizo | Estado |
|---|---|---|
| `clean_mp_imports.py` | Limpieza puntual de filas importadas de `resumen-mp-marzo.pdf` | Aplicado, ruta hardcodeada |
| `fix_mp_purchases.py` | Corrigió `first_installment_month` de compras MercadoPago mal asignadas a 2026-04 | Aplicado |
| `fix_mp_test.py` | Prueba ad-hoc de detección de mes de cierre en PDFs | Throwaway |
| `reimport_mp.py` | Re-importó `resumen-mp-marzo.pdf` (ruta `/Users/pablo/...`) | Aplicado, ruta hardcodeada |
| `debug_visa_parser.py` | Inspecciona la estructura cruda de un XLSX Visa. `python debug_visa_parser.py <archivo.xlsx>` | Reutilizable (debug) |
| `deduplicate_purchases.py` | Dedup de compras vía SQLModel | **Duplicado** — usar `scripts/dedupe_purchases.py` (sqlite + `--dry-run`) |
| `migrate_consolidate_purchases.py` | Migración para consolidar compras duplicadas con cuotas | Aplicado |

> Para deduplicar de nuevo, la herramienta vigente es
> `scripts/dedupe_purchases.py` (no la copia archivada acá).

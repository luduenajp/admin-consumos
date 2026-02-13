# Tareas propuestas tras revisión del código base

## 1) Corrección de error tipográfico
**Problema detectado:** en la documentación aparece "via" sin tilde en español (por ejemplo, "configurables via variables de entorno").

**Evidencia:** `spec/README.md`.

**Tarea propuesta:**
- Corregir "via" por "vía" en la documentación del proyecto.
- Revisar y unificar tildes en términos repetidos en `spec/README.md` (por ejemplo, "configuración vía env vars").

**Criterio de aceptación:** no quedan ocurrencias de " via " en contexto de texto español dentro de `spec/README.md`.

---

## 2) Corrección de falla funcional
**Problema detectado:** el endpoint de importación XLSX acepta extensión `.xls`, pero el parser usa `pandas.read_excel` sin configuración para compatibilidad legacy y el mensaje de error sólo menciona `.xlsx`.

**Evidencia:**
- `backend/app/import_api.py` acepta `{ ".xlsx", ".xls" }`.
- `backend/app/importers/visa_xlsx.py` parsea como XLSX sin lógica específica para `.xls`.

**Riesgo:** el usuario puede subir `.xls` válido según validación inicial y luego fallar en parseo (error tardío y confuso).

**Tarea propuesta:**
- Definir comportamiento explícito:
  - **Opción A (recomendada para MVP):** rechazar `.xls` en validación inicial y devolver `Expected .xlsx`.
  - **Opción B:** soportar `.xls` agregando dependencia/engine compatible y pruebas.
- Alinear el mensaje de error con la validación real.

**Criterio de aceptación:** la validación de extensiones y el parser son consistentes, sin falsas aceptaciones.

---

## 3) Corrección de discrepancia en comentarios/documentación
**Problema detectado:** la documentación de alto nivel afirma soporte de importación `CSV/XLSX/PDF`, pero en la implementación actual no existe endpoint ni parser CSV.

**Evidencia:**
- `spec/README.md` menciona "CSV/XLSX/PDF".
- En backend sólo están `POST /import/visa-xlsx` y `POST /import/visa-pdf`.

**Tarea propuesta:**
- Ajustar la documentación para reflejar estado real (**XLSX + PDF**) o implementar soporte CSV real.
- Si se decide documentar estado real, actualizar también `spec/formatos-importacion.md` y `spec/endpoints.md` para evitar ambigüedad.

**Criterio de aceptación:** documentación y endpoints implementados coinciden 1:1.

---

## 4) Mejora de pruebas
**Problema detectado:** no hay una suite de pruebas automatizadas para importadores y validaciones de formato; los ejemplos son manuales.

**Evidencia:** ausencia de archivos de prueba en `backend/` y `frontend/`.

**Tarea propuesta:**
- Crear suite mínima con `pytest` en backend:
  1. test para validar rechazo/aceptación de extensiones en `/import/visa-xlsx`.
  2. test para deduplicación por fingerprint (`created` vs `skipped`).
  3. test para exclusión de filas no-consumo y montos negativos en `parse_visa_xlsx`.
  4. test para detección de `statement_year_month` en muestras representativas.

**Criterio de aceptación:** tests corren en CI/local y cubren los caminos críticos del importador.

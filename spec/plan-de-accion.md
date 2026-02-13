# Plan de acción – Admin Consumos

## Objetivo
Tener una app web local funcional para importar resúmenes de tarjeta, gestionar consumos/cuotas, asignar quién paga y obtener reportes mensuales/proyecciones.

## Fases

### 1️⃣ MVP funcional (actual)
- [x] Backend FastAPI + SQLite + CRUD básico
- [x] Modelo de datos (Person, Card, Purchase, PurchasePayer, InstallmentSchedule, FxRate, ImportedRow)
- [x] Endpoints de reportes mensuales (ARS + USD convertido)
- [x] Importador XLSX Visa (excluye pagos/promos/ajustes)
- [x] Frontend React/Vite/TS con 3 páginas (Dashboard, Compras, Importar)
- [x] Proxy Vite para `/api` (sin CORS)

### 2️⃣ Mejoras de UX y datos
- [x] UI para crear Personas/Tarjetas/FX (página Admin)
- [x] Filtros en Compras (por tarjeta, persona, mes, categoría, montos, descripción, pagado por, deudor)
- [x] Paginación en tablas grandes
- [x] Indicadores de carga y errores claros
- [ ] Validaciones frontend antes de enviar (ej. tarjeta obligatoria)

### 3️⃣ Importación extendida
- [ ] Importador CSV (Santander/Nación/MercadoPago)
- [x] Importador PDF (Banco Nación Visa/Mastercard, MercadoPago; contraseña opcional)
- [ ] Vista de "preview" antes de confirmar importación
- [ ] Detección de duplicados más robusta (similitud de descripción)
- [ ] Logs de importación por archivo

### 4️⃣ Reportes y proyecciones
- [x] Dashboard con gráficos (distribución por categoría, timeline de cuotas futuras)
- [x] Vista de "cuotas comprometidas" por mes futuro (timeline)
- [ ] Exportación CSV/Excel de reportes
- [x] Filtros por persona/tarjeta en reportes mensuales
- [x] Resumen del mes (desglose de cuotas por compra)
- [ ] Comparación mes vs mes anterior

### 5️⃣ Funcionalidades avanzadas
- [ ] Categorías predefinidas y reglas de auto-categorización
- [ ] Presupuestos mensuales y alertas
- [ ] Split flexible por compra (porcentual/montos fijos) desde UI
- [ ] Adjuntos de PDF/comprobantes por compra
- [ ] Conciliación de pagos de tarjeta (opcional)

## Próximos pasos inmediatos (recomendado)
1) **Validaciones frontend** (ej. tarjeta obligatoria antes de importar)
2) **Importador CSV** (Santander/Nación/MercadoPago)
3) **Preview de importación** (mostrar filas parseadas antes de confirmar)
4) **Exportación CSV/Excel** de reportes

## Decisiones pendientes (si se desean)
- ¿Queremos manejo de errores de importación más granular?
- ¿Soportar múltiples monedas más allá de USD?
- ¿Persistir preferencias de filtros en el frontend?

## Notas para otros agentes
- La carpeta `spec/` es la fuente de verdad sobre arquitectura y decisiones.
- Los modelos están en `backend/app/models.py`.
- Los parsers de importación viven en `backend/app/importers/` (visa_xlsx, visa_pdf).
- El frontend usa proxy Vite (`/api` → `http://localhost:8000`).
- La DB SQLite se crea en `data/app.db` (absoluta, en raíz del proyecto).
- Script de arranque: `./start.sh` — levanta backend + frontend.
- Validar PDFs: `python examples/validate_pdf.py <archivo.pdf> [contraseña]`.

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
- [ ] UI para crear Personas/Tarjetas/FX (sin curl)
- [ ] Filtros en Compras (por tarjeta, persona, mes, categoría)
- [ ] Paginación en tablas grandes
- [ ] Indicadores de carga y errores claros
- [ ] Validaciones frontend antes de enviar (ej. tarjeta obligatoria)

### 3️⃣ Importación extendida
- [ ] Importador CSV (Santander/Nación/MercadoPago)
- [ ] Importador PDF (con contraseña `34247332`)
- [ ] Vista de “preview” antes de confirmar importación
- [ ] Detección de duplicados más robusta (similitud de descripción)
- [ ] Logs de importación por archivo

### 4️⃣ Reportes y proyecciones
- [ ] Dashboard con gráficos (ej. evolución mensual, distribución por categoría)
- [ ] Vista de “cuotas comprometidas” por mes futuro
- [ ] Exportación CSV/Excel de reportes
- [ ] Filtros por persona/tarjeta en reportes mensuales
- [ ] Comparación mes vs mes anterior

### 5️⃣ Funcionalidades avanzadas
- [ ] Categorías predefinidas y reglas de auto-categorización
- [ ] Presupuestos mensuales y alertas
- [ ] Split flexible por compra (porcentual/montos fijos) desde UI
- [ ] Adjuntos de PDF/comprobantes por compra
- [ ] Conciliación de pagos de tarjeta (opcional)

## Próximos pasos inmediatos (recomendado)
1) **UI para Personas/Tarjetas/FX** (evitar curl)
2) **Validaciones y filtros** en la vista de Compras
3) **Importador CSV** (Santander/Nación/MercadoPago)
4) **Preview de importación** (mostrar filas parseadas antes de confirmar)

## Decisiones pendientes (si se desean)
- ¿Queremos manejo de errores de importación más granular?
- ¿Soportar múltiples monedas más allá de USD?
- ¿Persistir preferencias de filtros en el frontend?

## Notas para otros agentes
- La carpeta `spec/` es la fuente de verdad sobre arquitectura y decisiones.
- Los modelos están en `backend/app/models.py`.
- Los parsers de importación viven en `backend/app/importers/`.
- El frontend usa proxy Vite (`/api` → `http://localhost:8000`).
- La DB SQLite se crea en `backend/data/app.db` (absoluta).

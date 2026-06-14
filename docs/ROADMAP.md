# Roadmap — Admin Consumos

Funcionalidades identificadas como valiosas pero aún no implementadas, ordenadas
por valor/esfuerzo. Esta es la **única fuente de ideas a futuro**; consolida lo que
antes vivía en `spec/FUTURE_FEATURES.md` y `spec/plan-de-accion.md` (ya eliminados),
descartando lo ya hecho.

Para el estado actual del producto (lo que **sí** está implementado), ver `SPEC.md`.

---

## 🎯 Alta prioridad (alto valor / bajo esfuerzo)

### Proyección de cierre de mes (Cash Flow)
"Si seguís gastando a este ritmo, cerrarías el mes en $X". Basado en días
transcurridos + gasto promedio diario, comparado con el promedio de los últimos
3 meses. Semáforo verde/amarillo/rojo en el dashboard. Extensión natural:
`Ingresos estimados − cuotas comprometidas` para proyectar el "dinero libre"
real de los próximos meses.

### Vista "Solo USD"
Toggle en la página de compras para ver todo dolarizado al TC del momento (la
conversión ya existe a nivel query). Si falta el FX del mes, usar el más reciente
con un warning. Útil para decidir pesos-hoy vs USD.

### Alertas de presupuesto
Topes mensuales por categoría o totales, con alerta visual al superar ~80% del
límite. El modelo `MonthlyBudget`/`Income` ya existe; falta el umbral + el panel
de alertas en el dashboard.

### Exportación CSV (y "compartible")
- `GET /api/purchases/export.csv` con los mismos filtros que el listado (ya existe
  `export_dashboard_to_excel` para Excel; falta CSV por compra).
- Opción fiscal: columna "Deducible" + filtro por año fiscal.
- Versión "compartible": imagen/PDF simplificado del resumen de "Transferencias a
  realizar" para mandar por WhatsApp.

---

## 📊 Media prioridad

### Detección de suscripciones recurrentes
Identificar automáticamente cargos mensuales similares (misma descripción fuzzy +
monto ±5% + 3 meses consecutivos → suscripción). Panel "Suscripciones detectadas"
con confirmación manual y total mensual de gastos fijos.

### Comparación mes a mes (tendencias)
"Gastaste X% más que el mes pasado" + desglose de qué categoría subió más +
gráfico de líneas de evolución mensual por categoría. Endpoint
`/api/reports/month-over-month?months=6`, tab "Tendencias" en el dashboard.

### Simulador de compra (What-if?) + Cuotas vs Contado
Previsualizar el impacto de una nueva compra en cuotas sobre el timeline y el
presupuesto **antes** de realizarla. Incluir análisis cuotas-sin-interés vs
contado ajustado por inflación (valor presente de cada cuota), mostrando el
"ahorro real" estimado.

### Motor de categorización inteligente
Mapeo automático "descripción → categoría" basado en el historial (ej. "YPF" →
"Combustible"), más allá del `auto_categorize_purchases` actual por keywords fijas.

### Gestión de fechas de tarjeta
Configurar días de cierre y vencimiento por tarjeta para alertar sobre cuándo
conviene comprar (patear cuotas al mes siguiente).

### Importación: mejoras
- Importador CSV directo (Santander / Nación / MercadoPago).
- Preview de filas parseadas antes de confirmar la importación.
- Logs de importación por archivo.
- (La detección de duplicados ya tiene fuzzy match en `import_api.py`.)

---

## 🎨 UX / largo plazo

### Comprobantes adjuntos
Adjuntar fotos o PDFs de tickets a cada compra. (Ya existe el flujo PWA Web Share
Target para `/nueva-transferencia`; esto extendería el almacenamiento del archivo.)

### Reporte "Poder adquisitivo"
Inflación real del hogar: usar el gasto por categoría como "canasta familiar" y
calcular cuánto cuesta hoy vs hace N meses. Gráfico vs inflación oficial.

### Dashboard customizable
Reordenar/ocultar paneles (drag & drop con `react-grid-layout`), layout en
`localStorage`.

### Dark mode
Toggle en el header; las CSS custom properties ya están preparadas para temizar.
Persistir preferencia.

---

## Ya implementado (no re-agregar)

Paginación de compras · edición de compras · responsive/mobile UX · Basic Auth ·
gráficos del dashboard (categoría + timeline de cuotas) · importador PDF
(Banco Nación, MercadoPago) · exportación a Excel · filtros por persona/tarjeta ·
PWA con Web Share Target · backup automático de la DB de Railway.

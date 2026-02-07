# Definiciones de negocio – Admin Consumos

## Objetivo del producto

Admin Consumos es una aplicación web local que permite a una pareja (vos y tu pareja) controlar y planificar los gastos realizados con tarjetas de crédito. El foco está en:

- **Centralizar consumos** de una o más tarjetas en un solo lugar.
- **Modelar compras en cuotas** y entender su impacto mensual.
- **Asignar quién paga** cada compra (quién la realizó vs quién la abona).
- **Generar reportes y proyecciones** para planificar el flujo de dinero de los próximos meses.

No es una app de conciliación bancaria ni de pagos de tarjetas; se centra en los **consumos** y su efecto en el presupuesto familiar.

---

## Conceptos clave

### Consumo
- Transacción de compra realizada con una tarjeta de crédito.
- Puede ser **en una sola cuota** o **en cuotas**.
- Se registra con fecha, descripción, monto original, moneda (ARS/USD) y cantidad de cuotas.

### Cuota
- Porción de un consumo en cuotas que impacta en un mes específico.
- Se genera automáticamente a partir del consumo original.
- En reportes mensuales, solo se imputa el valor de la cuota del mes (no el total de la compra).

### Tarjeta
- Medio de pago con el que se realiza el consumo.
- Tiene un **dueño** (persona titular) y puede ser titular o adicional.
- Se identifica por nombre, banco/proveedor y últimos 4 dígitos.

### Persona
- Integrante del grupo familiar (ej. “Pablo”, “Cintia”).
- Puede ser **dueño de una tarjeta** y/o **pagador** de una compra.

### Pagador
- Quien realmente abona la compra.
- Puede ser:
  - **El dueño de la tarjeta** (comportamiento por defecto).
  - **Otra persona** (split).
  - **Ambos** (split porcentual o montos fijos).

### Split (reparto)
- Mecanismo para que una compra sea pagada por más de una persona.
- Tipos:
  - **Porcentual**: cada persona paga un % del total.
  - **Monto fijo**: cada persona paga un monto fijo.
- Si no se especifica, se asume **100% al dueño de la tarjeta**.

### Moneda
- **ARS**: pesos argentinos.
- **USD**: dólares estadounidenses.
- Los reportes siempre se expresan en **ARS**. Para USD se usa un **tipo de cambio manual por mes**.

### Tipo de cambio (FX)
- Valor de conversión USD→ARS para un mes específico.
- Se carga manualmente (ej. `2026-01`: 1 USD = 1200 ARS).
- Se usa para convertir cuotas en USD a ARS en reportes.

### Resumen
- Archivo provisto por el banco (PDF, XLSX o CSV) que detalla los movimientos de un período.
- Contiene consumos, pagos, promociones, ajustes, etc.
- La app **importa solo consumos** y excluye pagos/promos/ajustes (ver Reglas de exclusión).

---

## Reglas de negocio

### 1) Importación de consumos
- **Solo se importan consumos** (compras). Se excluyen:
  - Pagos de la tarjeta (“Su pago en pesos/usd”).
  - Promociones/ajustes (“Promo cuenta sueldo”, “Cr.rg”, etc.).
  - Montos negativos o cero.
  - Filas de totales o resúmenes.
- **Deduplicación**: si una fila ya fue importada (mismo fingerprint), se ignora.
- **Cuotas**: si una compra está en cuotas, se genera el calendario completo al importar.

### 2) Calendario de cuotas
- Al crear una compra con cuotas, se generan `InstallmentSchedule` para cada cuota.
- Cada cuota tiene un `year_month` (mes en que impacta).
- El monto de la cuota es constante (no se recalcula por intereses).

### 3) Reportes mensuales
- Siempre se expresan en **ARS**.
- Para cuotas en USD, se usa el FX del mes correspondiente.
- Si no hay FX para un mes, las cuotas USD **no se suman** (evita errores).

### 4) Pagadores (split)
- Por defecto, **paga el dueño de la tarjeta**.
- Se puede sobreescribir por compra:
  - Una persona paga 100%.
  - Split porcentual (ej. 60%/40%).
  - Split por monto fijo (ej. $5000 y $3000).
- Los reportes pueden filtrarse por persona para ver “cuánto pagó cada uno”.

### 5) Proyecciones
- Se calculan a partir del calendario de cuotas futuras.
- Permiten planificar cuánto dinero se necesitará en los próximos meses.
- No tienen en cuenta ingresos ni otros gastos fuera de tarjeta.

### 6) Categorización (futuro)
- Los consumos pueden asignarse a categorías (ej. “Super”, “Nafta”, “Delivery”).
- Las categorías sirven para análisis y presupuestos.
- Por ahora son opcionales y libres.

---

## Flujo de usuario típico

1) **Configuración inicial**
   - Dar de alta a las personas (vos y tu pareja).
   - Dar de alta las tarjetas (asignar dueño).
   - Cargar tipos de cambio USD→ARS para los meses necesarios.

2) **Importación de resúmenes**
   - Subir archivo XLSX/CSV/PDF del banco.
   - Revisar preview (futuro) y confirmar importación.
   - La app crea consumos, genera cuotas y asigna pagadores.

3) **Consulta de reportes**
   - Dashboard: totales mensuales, evolución, distribución por categoría.
   - Compras: lista detallada con filtros (mes, tarjeta, persona).
   - Proyecciones: cuotas comprometidas para los próximos meses.

4) **Ajustes manuales (opcional)**
   - Editar una compra (descripción, categoría, notas).
   - Modificar split de pagadores.
   - Agregar consumos manuales si no vinieron en el resumen.

---

## Casos de uso

### UC1: Importar resumen Visa
- Usuario sube XLSX de Visa.
- Sistema parsea, excluye pagos/promos, crea consumos y cuotas.
- Se muestra “Creadas: 12, Salteadas: 0”.

### UC2: Ver totales del mes
- Usuario abre Dashboard, filtra Enero 2026.
- Ve total ARS $150.000 (ARS + USD convertido).

### UC3: Cambiar pagador de una compra
- Usuario edita una compra y asigna split 50/50.
- Reportes futuros reflejan el nuevo reparto.

### UC4: Proyectar gastos futuros
- Usuario ve “Cuotas comprometidas” para Febrero y Marzo.
- Planifica cuánto dinero necesitará disponible.

---

## Limitaciones actuales (MVP)

- **Sin login**: app local, un solo usuario/familia.
- **Sin conciliación de pagos**: no se marcan cuotas como “pagadas”.
- **FX manual**: se debe cargar tipo de cambio por mes.
- **Un solo formato de importación**: Visa XLSX. CSV y PDF en fases futuras.
- **Sin categorías predefinidas**: se pueden usar pero no hay reglas automáticas.

---

## Métricas de éxito (producto)

- **Facilidad de importación**: % de archivos importados sin errores.
- **Claridad de reportes**: usuarios pueden entender rápidamente cuánto gastaron y cuánto deben los próximos meses.
- **Adopción del split**: usuarios usan split para asignar pagos entre ambos.
- **Reducción de tiempo** vs planilla manual.

---

## Glosario rápido

| Término | Definición |
|----------|-------------|
| Consumo | Compra con tarjeta (en 1 cuota o en cuotas). |
| Cuota | Porción de un consumo que impacta en un mes. |
| Split | Reparto de una compra entre más de una persona. |
| FX | Tipo de cambio USD→ARS manual por mes. |
| Resumen | Archivo del banco con movimientos del período. |
| Dashboard | Vista principal con totales y gráficos. |
| Proyección | Cuotas futuras comprometidas. |

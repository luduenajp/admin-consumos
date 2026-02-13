# Funcionalidades Futuras - Admin Consumos

Este documento detalla las funcionalidades identificadas como valiosas pero no implementadas en la primera fase. Están organizadas por prioridad y complejidad.

---

## 🎯 Alta Prioridad (Next Sprint)

### 1. Alertas de Presupuesto

**Valor:** Control proactivo vs reactivo - prevenir sobregastos

**Descripción:**
- Definir topes mensuales por categoría o totales
- Alertas visuales cuando se supera el 80% del límite
- Notificaciones en dashboard

**Implementación:**
- Nueva tabla `Budget` con `category`, `month`, `limit_ars`
- Endpoint `/api/budgets` (CRUD)
- Componente `BudgetAlerts` en dashboard
- Cálculo: comparar `report_spending_by_category()` contra límites

**Complejidad:** Media (2-3 días)

---

### 2. Detección de Suscripciones Recurrentes

**Valor:** Eliminar gastos hormiga olvidados, identificar costos fijos

**Descripción:**
- Identificar automáticamente cargos mensuales similares
- Lista de "gastos fijos" detectados
- Opción de etiquetar/confirmar como suscripción
- Total mensual de suscripciones

**Implementación:**
```python
def detect_subscriptions(session: Session) -> list[SubscriptionPattern]:
    # Buscar purchases con:
    # - Mismo description (fuzzy match)
    # - Mismo monto (±5%)
    # - Frecuencia mensual (aparece 3+ meses consecutivos)
    # - Ejemplo: "SPOTIFY" aparece 6 meses → es suscripción
```

**Regex patterns comunes:**
- Netflix, Spotify, Apple, Amazon Prime
- Servicios argentinos: Flow, Personal, Telecentro

**UI:**
- Panel "Suscripciones Detectadas" en dashboard
- Checkbox "Confirmar como suscripción" → guarda en `subscription` bool field

**Complejidad:** Media-Alta (3-4 días)

---

### 3. Proyección de Cierre de Mes

**Valor:** Freno preventivo antes de llegar a fin de mes

**Descripción:**
- "Si seguís gastando a este ritmo, cerrarías el mes en $X"
- Basado en días transcurridos + gasto promedio diario
- Comparar con promedio de últimos 3 meses
- Semáforo verde/amarillo/rojo

**Implementación:**
```python
def project_month_close(session: Session) -> MonthProjection:
    current_month = to_year_month(date.today())
    days_elapsed = date.today().day
    days_in_month = monthrange(date.today().year, date.today().month)[1]

    # Gasto acumulado este mes
    spent_so_far = sum_installments_for_month(current_month)

    # Promedio diario
    daily_avg = spent_so_far / days_elapsed

    # Proyección
    projected_total = daily_avg * days_in_month

    # Comparar con promedio últimos 3 meses
    avg_last_3 = average_spending_last_n_months(n=3)

    return MonthProjection(
        projected=projected_total,
        average_baseline=avg_last_3,
        status='warning' if projected_total > avg_last_3 * 1.2 else 'ok'
    )
```

**UI:**
- Badge en dashboard: "Proyección: $X (🔴 20% sobre promedio)"
- Tooltip con detalle del cálculo

**Complejidad:** Baja (1-2 días)

---

## 📊 Media Prioridad (Future Sprints)

### 4. Comparación Mes a Mes

**Valor:** Identificar tendencias de gastos

**Descripción:**
- "Gastaste X% más que el mes pasado"
- Desglose: qué categoría aumentó más
- Gráfico de líneas: evolución mensual por categoría

**Implementación:**
- Endpoint `/api/reports/month-over-month?months=6`
- Componente `TrendChart` (recharts LineChart)
- Highlight categorías con mayor variación

**UI:**
- Nueva tab "Tendencias" en dashboard
- Selector de período (3/6/12 meses)

**Complejidad:** Media (2-3 días)

---

### 5. Análisis de Cuotas vs Contado

**Valor:** Decisión financiera informada al momento de compra

**Descripción:**
- Calcular si cuotas sin interés convienen vs pagar contado
- Considerar inflación proyectada
- Mostrar "costo real" de cada cuota ajustado por inflación

**Ejemplo:**
```
Compra: $12.000 en 12 cuotas de $1.000
Inflación mensual: 8%

Cuota 1:  $1.000 (valor real: $1.000)
Cuota 6:  $1.000 (valor real:   $630)  ← 37% menos por inflación
Cuota 12: $1.000 (valor real:   $397)  ← 60% menos por inflación

Total valor real: $8.450 (30% ahorro vs contado)
```

**Implementación:**
```python
def analyze_installment_value(
    amount: float,
    installments: int,
    monthly_inflation: float = 0.08
) -> InstallmentAnalysis:
    # Calcular valor presente de cada cuota
    real_values = []
    for i in range(installments):
        discount_factor = (1 + monthly_inflation) ** i
        real_value = (amount / installments) / discount_factor
        real_values.append(real_value)

    return InstallmentAnalysis(
        nominal_total=amount,
        real_total=sum(real_values),
        savings_percent=(1 - sum(real_values) / amount) * 100
    )
```

**UI:**
- Widget en purchase creation form
- "Esta compra en 12 cuotas te ahorra ~30% vs contado (inflación 8%)"
- Gráfico de barras: valor nominal vs valor real por cuota

**Complejidad:** Media-Alta (4-5 días)

---

### 6. Vista "Solo USD"

**Valor:** Decisión de compra según inflación vs dólar

**Descripción:**
- Ver todas las compras dolarizadas con TC del momento
- Detectar si una compra en pesos hoy sale más cara que comprar en USD
- Toggle en purchases page: "Ver en USD"

**Implementación:**
- Endpoint actual ya soporta conversión
- Frontend: agregar toggle switch
- Si USD no disponible, usar TC más reciente con warning

**UI:**
- Switch "Ver todo en USD" en purchases page
- Columna de monto muestra: `USD $X.XX` (original ARS en tooltip)

**Complejidad:** Baja (1 día)

---

### 7. Reporte "Poder Adquisitivo"

**Valor:** Conciencia del deterioro del ingreso

**Descripción:**
- Mostrar cómo $X pesos de hace 3 meses equivalen a $Y hoy
- Gráfico de inflación real del hogar (no INDEC)
- Comparar con canasta básica familiar

**Implementación:**
```python
def calculate_household_inflation(session: Session) -> list[InflationPoint]:
    # Por cada mes:
    # 1. Calcular gasto promedio por categoría
    # 2. Usar como "canasta familiar"
    # 3. Calcular cuánto cuesta esa canasta hoy vs antes

    baseline_month = add_months(to_year_month(date.today()), -3)
    baseline_basket = get_category_spending(baseline_month)

    inflation_points = []
    for month in last_n_months(6):
        current_cost = calculate_basket_cost(baseline_basket, month)
        baseline_cost = sum(baseline_basket.values())
        inflation_rate = (current_cost / baseline_cost - 1) * 100
        inflation_points.append(InflationPoint(month, inflation_rate))

    return inflation_points
```

**UI:**
- Panel "Tu Inflación" en dashboard
- Gráfico de líneas vs inflación oficial
- Badge: "Tu poder adquisitivo bajó X% en 6 meses"

**Complejidad:** Alta (5-6 días)

---

## 🔧 Mejoras Técnicas

### 8. Paginación de Purchases

**Situación actual:** Frontend carga todas las purchases de una vez

**Problema:** Con 1000+ purchases, la página se vuelve lenta

**Solución:**
- Backend: Agregar `limit`, `offset` a `/api/purchases`
- Frontend: Componente `Pagination` o infinite scroll
- React Query: usar `useInfiniteQuery()`

**Complejidad:** Media (2 días)

---

### 9. Edición de Purchases

**Situación actual:** No se pueden editar purchases una vez creadas

**Necesidad:**
- Cambiar categoría de purchases importadas
- Corregir errores de importación
- Agregar notas

**Implementación:**
- Endpoint `PUT /api/purchases/{id}`
- Modal de edición en purchases table
- Validación: no permitir cambiar `installments_total` si ya hay cuotas pagadas

**Complejidad:** Media (3 días)

---

### 10. Exportación a CSV

**Valor:** Backup, análisis externo, declaración de impuestos

**Implementación:**
- Endpoint `GET /api/purchases/export.csv`
- Filtros: igual que purchases list
- Headers: fecha, descripción, categoría, monto, cuotas, tarjeta, persona

**Opción fiscal:**
- Columna adicional "Deducible" (bool)
- Filtro por año fiscal
- Separar gastos personales vs deducibles

**Complejidad:** Baja (1 día)

---

## 🎨 UX Improvements

### 11. Dashboard Customizable

**Descripción:**
- Permitir arrastrar/reordenar paneles
- Ocultar paneles no relevantes
- Guardar layout en localStorage

**Librerías:**
- `react-grid-layout` para drag & drop
- `localStorage` para persistencia

**Complejidad:** Media (3 días)

---

### 12. Dark Mode

**Descripción:**
- Toggle en header
- CSS variables ya preparadas
- Persistir preferencia

**Implementación:**
```css
[data-theme="dark"] {
  --color-bg: #1a1410;
  --color-surface: #2a2018;
  --color-text: #f0e8dc;
  ...
}
```

**Complejidad:** Baja (1 día)

---

### 13. Mobile Responsiveness

**Situación actual:** Desktop-first, no optimizado para mobile

**Mejoras:**
- Tables → Cards en mobile
- Charts → Full width stacked
- Filter panel → Collapsible

**Complejidad:** Media (2-3 días)

---

## 🔐 Autenticación (Opcional)

**Advertencia:** El README dice "No authentication — single-user household tool"

Si se requiere multi-usuario en el futuro:

### 14. Login Simple

**Opción 1: Password único**
- Un password para toda la app
- Hash en variable de entorno
- Session cookie

**Opción 2: Multi-usuario**
- Tabla `User` con bcrypt passwords
- JWT tokens
- Asociar personas con users

**Complejidad:** Alta (7-10 días para multi-user)

---

## Priorización Sugerida

### Sprint 2 (después de Quick Wins)
1. Proyección de cierre de mes (Quick Win + High Value)
2. Vista Solo USD (Fácil + Útil para inflación)
3. Edición de purchases (Necesidad básica)

### Sprint 3
1. Alertas de presupuesto (Alto valor)
2. Detección de suscripciones (Alto valor)
3. Exportación CSV (Útil para backups)

### Sprint 4
1. Comparación mes a mes (Análisis)
2. Paginación (Si ya hay muchos datos)
3. Dark mode (UX polish)

### Backlog largo plazo
- Análisis cuotas vs contado
- Reporte poder adquisitivo
- Dashboard customizable
- Mobile responsiveness
- Autenticación multi-usuario

---

## Métricas de Éxito

Para cada feature, considerar medir:
- **Uso:** ¿Cuántas veces se consulta por semana?
- **Valor:** ¿Ayudó a tomar decisiones financieras?
- **Performance:** ¿Impacta en tiempo de carga?

Feedback loop: Agregar botón "¿Útil?" en cada panel para medir valor percibido.

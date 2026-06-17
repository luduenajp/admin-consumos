# Gastos por Categoría — Página dedicada

**Fecha:** 2026-06-17  
**Estado:** Aprobado

## Objetivo

Reemplazar el ítem "Compras" en la navegación por una página "Categorías" (`/gastos-categorias`) que muestre un dashboard de gastos por categoría con filtros útiles en mobile y desktop.

## Ruta y archivo

| Item | Valor |
|---|---|
| Ruta | `/gastos-categorias` |
| Componente | `frontend/src/pages/gastos-categorias-page.tsx` |
| Export | `GastosCategoriaPage` |

## Layout de la página

1. **Filtros** (fila horizontal, compacta)
   - Selector de mes: botones prev/next + label `YYYY-MM`, inicializa al mes actual
   - Selector de persona: `<select>` con "Todos", y una opción por cada persona devuelta por `GET /api/persons`
   - Toggle tipo: `<select>` o botones "Todos / Solo comunes"

2. **CategoryChart** — componente existente en `components/CategoryChart.tsx`, sin modificaciones

3. **Tabla resumen** — debajo del gráfico
   - Columnas: Categoría · Monto ARS · % del total
   - Orden: monto desc
   - Fila "Sin categoría" al final si existe

4. **Estado vacío** — si `data.length === 0`: mensaje "Sin datos de categorías para este mes"

## Datos / API

| Endpoint | Uso |
|---|---|
| `GET /api/reports/category-spending?year_month=&person_id=&is_common=` | Datos del gráfico y tabla |
| `GET /api/persons` | Lista de personas para el filtro |
| `GET /api/categories` | Colores de categorías para el gráfico |

Todos estos endpoints ya existen. No hay cambios en backend.

## Cambios en navegación

En `frontend/src/App.tsx`, en `NAV_GROUPS` grupo "Principal":

- **Eliminar:** `{ to: '/purchases', label: 'Compras', icon: '🧾' }`
- **Agregar:** `{ to: '/gastos-categorias', label: 'Categorías', icon: '📊' }`

La ruta `/purchases` y `PurchasesPage` permanecen — solo se quita el link de la nav. Se agrega el lazy import y la `<Route>` para `/gastos-categorias`.

## Patrones a seguir

- `useQuery` con `queryKey` que incluye todos los filtros activos
- Inicialización de mes: `new Date().toISOString().slice(0, 7)` (YYYY-MM)
- Formato de montos: `toLocaleString('es-AR', { maximumFractionDigits: 2 })`
- CSS: clases existentes (`page`, `pageTitle`, `panel`, `formRow`, `label`, `input`, `table`)
- No introducir nuevas dependencias ni estilos

## Fuera de alcance

- Modificar `CategoryChart` o `PurchasesPage`
- Cambios en backend
- Persistir los filtros en URL/localStorage

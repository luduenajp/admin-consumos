# Editar Descripción y Detalle desde el Dashboard (Desktop)

## Contexto

En la tabla "Resumen del mes" del dashboard (desktop), las columnas
Descripción y Detalle se muestran como texto plano, sin forma de editarlas.
En mobile ya existe un sheet de edición (`mobileEditId` /
`purchaseMobileEditSheet` en `dashboard-page.tsx`) que permite editar
Categoría, Gasto común y Detalle/Notas al tocar una card, pero no incluye
Descripción, y ese sheet solo se dispara desde las cards mobile.

## Objetivo

Permitir editar Descripción y Detalle de una compra directamente desde el
dashboard, también en desktop, reutilizando el sheet de edición existente.

## Diseño

1. **Campo Descripción en el sheet existente**: agregar un input de texto
   "Descripción" en `purchaseMobileEditSheet`, arriba del campo Categoría.
   Sigue el mismo patrón que el campo Detalle/Notas ya implementado: estado
   local (`mobileEditDescription`), se sincroniza al abrir el sheet, y se
   persiste con `patchMutation.mutate({ id, payload: { description } })` en
   `onBlur` si cambió respecto al valor original. Sin validación adicional
   más allá de no permitir string vacío (el backend probablemente ya
   rechaza `description` vacía; si no, se agrega un check simple de "no
   enviar si está vacío tras trim").
2. **Trigger en desktop**: las filas `<tr>` de la tabla "Resumen del mes"
   (sección `dashboard-desktop-only`) obtienen el mismo `onClick` que ya
   usan las cards mobile: `setMobileEditId(row.purchase_id)` +
   inicializar `mobileEditNotes` y el nuevo `mobileEditDescription` con los
   valores de la fila. El nombre `mobileEditId` no se renombra (evitar
   refactor innecesario fuera de alcance) aunque ahora también se use en
   desktop.
   - Cuidado: la celda de Descripción ya tiene un `tooltip-container` con
     hover. El click en la fila debe seguir abriendo el sheet sin romper
     el tooltip existente (el tooltip es solo hover/CSS, no captura click,
     así que no debería haber conflicto).
3. **Estilos**: el overlay/sheet actual (`purchaseMobileEditOverlay` /
   `purchaseMobileEditSheet`) se revisa para que se vea razonable también
   en viewport desktop (probablemente ya centra el sheet vía CSS; si el
   CSS tiene `@media` que lo oculta en desktop, hay que ajustarlo para que
   estas clases no dependan de un breakpoint mobile-only). No se introduce
   un sistema de estilos nuevo — se reutiliza `App.css`.

## Fuera de alcance

- No se cambia la lógica de negocio de Fondo Común ni ningún BR-XXX.
- No se agrega edición de otros campos (categoría/gasto común ya existen).
- No se renombra `mobileEditId`/`mobileEditNotes` a algo más genérico.

## Testing

- Frontend: si existen tests de `dashboard-page.tsx`, extender para
  cubrir que el click en una fila desktop abre el sheet y que editar
  Descripción dispara `patchMutation` con el payload correcto.
- Verificación manual: `npm run dev`, abrir dashboard en viewport desktop,
  click en una fila de "Resumen del mes", editar Descripción y Detalle,
  confirmar que persiste tras recargar.

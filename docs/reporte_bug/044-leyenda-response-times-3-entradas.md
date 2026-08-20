# 044 — Leyenda de "Response Times por Transaccion": 3 entradas, no 6

**Fecha:** 2026-08-19
**Branch:** `backup-trabajo-local`
**Commit del fix:** `5bcf796` — "FIX: leyenda de Response Times con una entrada por transaccion"
**Archivos de codigo tocados:** 1 — `frontend/src/components/dashboard/Dashboard.tsx`
**Backup:** `frontend/src/components/dashboard/Dashboard.tsx.bak_leyenda_20260819_221849`
**Llamadas de IA:** 0

---

## 1. Sintoma

La grafica "Response Times por Transaccion" mostraba 6 entradas de leyenda:

```
token | Adapter VerifMethod | Adapter SendCode
token (max) | Adapter VerifMethod (max) | Adapter SendCode (max)
```

Deben ser 3: el maximo es la misma transaccion, no otra.

GRAF1-B (commit `0aa43b6`) puso `legendType="none"` en las lineas de maximo y
su reporte daba por hecho que con eso la leyenda quedaba en 3. En pantalla
salian 6. Ese reporte nunca se valido contra el DOM.

---

## 2. Diagnostico — por que `legendType="none"` no surtia efecto

`legendType="none"` **no filtra nada en el payload**. Recharts 2.15.4 arma el
payload de la leyenda con TODAS las series graficas y se limita a copiar
`legendType` al campo `type`:

`frontend/node_modules/recharts/lib/util/getLegendProps.js:44-64`

```js
legendData = (formattedGraphicalItems || []).map(function (_ref3) {
  var item = _ref3.item;
  ...
  var dataKey = itemProps.dataKey, name = itemProps.name,
      legendType = itemProps.legendType, hide = itemProps.hide;
  return {
    inactive: hide,
    dataKey: dataKey,
    type: legendProps.iconType || legendType || 'square',   // <-- 'none' viaja como dato
    color: getMainColorOfGraphicItem(item),
    value: name || dataKey,
    payload: itemProps
  };
});
```

El unico punto de todo Recharts donde `'none'` se descarta es el renderer
**por defecto**:

`frontend/node_modules/recharts/lib/component/DefaultLegendContent.js:136`

```js
if (entry.type === 'none') {
  return null;
}
```

Ese `return null` solo corre dentro de `DefaultLegendContent`. Como
`Dashboard.tsx:1082` usa una leyenda propia via `content=`:

```tsx
<Legend content={<ScrollableLegend ... />} verticalAlign="bottom" />
```

...`DefaultLegendContent` nunca se ejecuta, y `ScrollableLegend` recibia el
payload completo — 6 entradas, 3 de ellas con `type: 'none'` — y las pintaba
todas.

**Hipotesis del prompt: confirmada, con un matiz.** `ScrollableLegend` no
construye las entradas de una fuente distinta; recibe el payload de Recharts.
Lo que pasa es que ese payload **nunca viene filtrado**: descartar `'none'` es
responsabilidad del componente de leyenda, y el nuestro no lo hacia.

Detalle adicional verificado: `Legend.defaultProps`
(`frontend/node_modules/recharts/lib/component/Legend.js:205-210`) no define
`iconType`, asi que `legendProps.iconType` queda `undefined` y `type` si
conserva el valor `'none'`. El dato llegaba bien; faltaba consumirlo.

---

## 3. Correccion

Un solo punto, dentro de `ScrollableLegend` — con lo que se arreglan de paso
las 3 graficas que la usan (Response Times, Codigos de Respuesta, TPS).

### Diff completo de `Dashboard.tsx`

```diff
diff --git a/frontend/src/components/dashboard/Dashboard.tsx b/frontend/src/components/dashboard/Dashboard.tsx
index 091bab9..deba6e0 100644
--- a/frontend/src/components/dashboard/Dashboard.tsx
+++ b/frontend/src/components/dashboard/Dashboard.tsx
@@ -83,9 +83,16 @@ interface ScrollableLegendProps {
 }

 function ScrollableLegend({ payload, hiddenLines, onToggle, onSetAll }: ScrollableLegendProps & { onSetAll?: (keys: Set<string>) => void }) {
-  if (!payload || payload.length === 0) return null;
-
-  const allKeys = payload.map((e: any) => e.dataKey || e.value);
+  // FIX leyenda: Recharts NO honra legendType="none" cuando la leyenda usa `content`
+  // propio. getLegendProps (util/getLegendProps.js) arma el payload con TODAS las
+  // series y solo copia legendType en `type`; el descarte vive unicamente en
+  // DefaultLegendContent.js:136 (`if (entry.type === 'none') return null`), que aqui
+  // no se ejecuta. Se filtra en este componente para que las series de maximos no
+  // aporten una segunda entrada por transaccion.
+  const items = (payload || []).filter((e: any) => e && e.type !== 'none');
+  if (items.length === 0) return null;
+
+  const allKeys = items.map((e: any) => e.dataKey || e.value);
   const visibleCount = allKeys.filter((k: string) => !hiddenLines.has(k)).length;
   const allVisible = visibleCount === allKeys.length;
   const noneVisible = visibleCount === 0;
@@ -114,7 +121,7 @@ function ScrollableLegend({ payload, hiddenLines, onToggle, onSetAll }: Scrollab
         className="flex flex-wrap gap-x-4 gap-y-1 justify-center overflow-y-auto"
         style={{ maxHeight: '90px' }}
       >
-        {payload.map((entry: any, idx: number) => {
+        {items.map((entry: any, idx: number) => {
           const isHidden = hiddenLines.has(entry.dataKey || entry.value);
           return (
             <button
```

Son 2 hunks, 8 lineas efectivas de cambio. No se toco nada mas del archivo
protegido.

**Efecto lateral corregido de paso:** `allKeys` alimenta el contador y el boton
maestro. Antes contaba 6 claves (el boton llegaba a decir "3/6 visibles") y
`onSetAll` metia las claves `(max)` al Set sin necesidad. Ahora son 3.

**Regla 16 (hooks antes de returns):** `ScrollableLegend` no declara ningun
hook, asi que el early return sigue siendo seguro.

**Apagado conjunto solida + punteada:** no requirio cambio. Ya lo resolvia
GRAF1-B con `hide={hiddenLinesResponseTimes.has(label)}` en la linea de maximo
— keyed por la etiqueta **base**, no por `label + ' (max)'`
(`Dashboard.tsx:1089-1094`). Verificado empiricamente en 4.3.

---

## 4. Validacion — conteo real sobre el DOM renderizado

Se monto un harness que **extrae mecanicamente** el `ScrollableLegend` real de
`Dashboard.tsx` (no una copia escrita a mano), lo monta en un `LineChart` de
Recharts con el mismo cableado de la grafica (3 lineas + 3 lineas `(max)` con
`legendType="none"`, mismos `hide=`) y lo renderiza con `renderToStaticMarkup`.
Se conto el DOM resultante y se intercepto el payload que Recharts entrega a la
leyenda. Los archivos del harness se eliminaron al terminar.

### 4.1 ANTES — componente del backup `.bak_leyenda_20260819_221849`

```
--- PAYLOAD CRUDO QUE RECHARTS ENTREGA A LA LEYENDA ---
entradas en payload: 6
   dataKey="token"                       type="line"  inactive=false
   dataKey="Adapter VerifMethod"         type="line"  inactive=false
   dataKey="Adapter SendCode"            type="line"  inactive=false
   dataKey="token (max)"                 type="none"  inactive=false
   dataKey="Adapter VerifMethod (max)"   type="none"  inactive=false
   dataKey="Adapter SendCode (max)"      type="none"  inactive=false
  de tipo "none": 3
--- DOM RENDERIZADO ---
ENTRADAS DE LEYENDA EN EL DOM: 6
textos: ["token","Adapter VerifMethod","Adapter SendCode",
         "token (max)","Adapter VerifMethod (max)","Adapter SendCode (max)"]
curvas <path> dibujadas: 6
```

Reproduce exactamente el bug reportado, y demuestra que el payload SI traia
`type: "none"` bien puesto: el componente lo ignoraba.

### 4.2 DESPUES — componente ya corregido

```
--- PAYLOAD CRUDO QUE RECHARTS ENTREGA A LA LEYENDA ---
entradas en payload: 6   (de tipo "none": 3)
--- DOM RENDERIZADO ---
ENTRADAS DE LEYENDA EN EL DOM: 3
textos: ["token","Adapter VerifMethod","Adapter SendCode"]
curvas <path> dibujadas: 6
```

**3 entradas, 6 curvas.** Las punteadas se siguen dibujando; solo desaparecen
de la leyenda.

### 4.3 Apagado conjunto — un click sobre "token"

```
--- DOM RENDERIZADO ---
ENTRADAS DE LEYENDA EN EL DOM: 3
textos: ["token","Adapter VerifMethod","Adapter SendCode"]
curvas <path> dibujadas: 4
```

De 6 curvas a 4: se apagaron **las dos** de `token` (solida + punteada) con un
solo click. La entrada permanece en la leyenda, tachada y al 40% de opacidad,
para poder reactivarla.

---

## 5. TransactionReportSection.tsx (N4.7) — verificado, sin cambios

`frontend/src/components/dashboard/TransactionReportSection.tsx:59` y `:79`.

Ahi cada grafica es de UNA sola transaccion y usa la **leyenda por defecto** de
Recharts (sin `content=`), con dos series nombradas explicitamente:

```tsx
lineas = [{ key: 'value',     color: '#4f46e5', nombre: 'Promedio' },
          { key: 'value_max', color: '#ef4444', nombre: 'Maximo'  }];
```

Renderizado y contado con el mismo metodo del punto 4:

```
ENTRADAS DE LEYENDA EN EL DOM: 2
textos: ["Promedio","Maximo"]
curvas <path> dibujadas: 2
```

**No hay duplicacion.** Las 2 entradas no son dos veces la misma transaccion
(el patron `token` / `token (max)` del bug), son los dos nombres de metrica de
esa unica transaccion. Suprimir "Maximo" de la leyenda dejaria la linea roja
sin explicacion posible. El criterio del bug — ninguna transaccion aparece dos
veces — se cumple tal cual esta.

**Archivo no modificado.**

---

## 6. Exports — verificado sobre exports REALES generados hoy

No se confio en lo que afirmaba el reporte de GRAF1-C. Se generaron los dos
exports contra la ejecucion real `5381abec-97c4-4163-ac77-9a5648c057f5`
("caso 1"), que contiene las 3 transacciones del bug. Ningun archivo de export
fue modificado.

### 6.1 HTML (Plotly)

`GET /executions/{id}/export/html` → **HTTP 200, 535.851 bytes**

Parseando el bloque `Plotly.newPlot('chart-rt-label', [...])` del HTML
efectivamente generado:

```
total traces en la grafica: 6
ENTRADAS DE LEYENDA REALES (showlegend != false): 3
   name="token"                        showlegend=True   dash=None
   name="token (max)"                  showlegend=False  dash=dot
   name="Adapter VerifMethod"          showlegend=True   dash=None
   name="Adapter VerifMethod (max)"    showlegend=False  dash=dot
   name="Adapter SendCode"             showlegend=True   dash=None
   name="Adapter SendCode (max)"       showlegend=False  dash=dot
```

**Confirmado: 3 entradas.** `export_html.py:284` (`'showlegend': False`) hace
su trabajo.

### 6.2 PDF (matplotlib)

`GET /executions/{id}/export/pdf` → **HTTP 200, 811.844 bytes, PDF 1.7 valido**

El PDF embebe la grafica como PNG, asi que el texto de la leyenda no es
extraible del documento. El conteo se hizo instrumentando
`matplotlib.axes.Axes.legend` dentro del container `jmeter_backend` y llamando
a las funciones **reales** del export — `_build_series` de `export_pdf.py` mas
`chart_multiline` de `report_generator.py` — con las 3 transacciones:

```
series pasadas a chart_multiline: 6
    token / token (max) / Adapter VerifMethod / Adapter VerifMethod (max)
    Adapter SendCode / Adapter SendCode (max)
imagen generada, bytes base64: 55652
--- LABELS QUE MATPLOTLIB METE EN LA LEYENDA ---
ENTRADAS DE LEYENDA: 3 -> ['token', 'Adapter VerifMethod', 'Adapter SendCode']
```

**Confirmado: 3 entradas.** `report_generator.py:129` (`label='_nolegend_'`)
hace su trabajo, y `ncol` se calcula sobre `base_colors`, diccionario que solo
acumula las series no-max (`report_generator.py:138`).

**Conclusion del punto 4 del prompt:** lo que afirmaba GRAF1-C sobre los
exports era cierto. El defecto estaba unicamente en pantalla.

---

## 7. Comprobaciones

| Check | Resultado |
|---|---|
| `tsc --noEmit` | limpio, exit 0 |
| Archivos de codigo tocados | 1 (`Dashboard.tsx`) — bajo el limite de 3 |
| Diff de `Dashboard.tsx` | completo, punto 3 |
| Backup | `Dashboard.tsx.bak_leyenda_20260819_221849` |
| Llamadas de IA | 0 |
| `export_html.py` / `export_pdf.py` | leidos y ejecutados, **no modificados** |
| `TransactionReportSection.tsx` | leido y renderizado, **no modificado** |
| `origin` (Azure DevOps) | **no tocado** |
| Push | remoto `github` |
| Archivos temporales del harness | eliminados |

---

## 8. Estado

Pendiente de **validacion visual de Fredy** en el Dashboard: la leyenda de
"Response Times por Transaccion" debe listar 3 entradas, y un click en
cualquiera de ellas debe apagar a la vez su linea solida y su punteada.

d174f55 · 2026-09-16

# ETAPA 3 — D36 en el informe general (`Dashboard.tsx` autorizado)

**Llamadas reales a la IA: 0.** El detector es determinista.
**Autorización de Fredy:** `Dashboard.tsx` **solo** para el aviso de estilo del
informe general, según el diff mínimo del reporte 30 §3.

Con esto **D36 queda cerrada**: el aviso ámbar aparece ya en las cuatro vistas.

---

## 1. El diff, completo

**13 líneas añadidas, 1 modificada.** El presupuesto era ~17 con margen hasta
~25. Copia de seguridad en `Dashboard.tsx.bak_etapa3_d36_20260916`.

```diff
@@ import
+import AvisoEstilo from '../common/AvisoEstilo';   // ETAPA 3 (D36)

@@ estado, junto a los demas refs de autoguardado
   const pendingRef = useRef<Record<string, string>>({});
+  // ETAPA 3 (D36): avisos de estilo por columna, tal como llegan de /executions/{id}.
+  const avisosRef = useRef<Record<string, string[]>>({});

@@ loadData
       setExecution(execData);
       setCharts(chartsData);
+      avisosRef.current = execData.style_warnings || {};   // ETAPA 3 (D36)

@@ AnalysisBox
-  const AnalysisBox = useCallback(({ value, onChange }: { value: string; onChange: (v: string) => void }) => (
+  // ETAPA 3 (D36): los avisos se leen por REF, no como dependencia: si AnalysisBox
+  // cambiara de identidad, React desmontaria el textarea y se perderia el foco.
+  const AnalysisBox = useCallback(({ value, onChange, campo }: { value: string; onChange: (v: string) => void; campo?: string }) => (
     <div className="mt-4 bg-white rounded-xl p-5 border-l-4 border-orange-500 border border-gray-200">
       ...
+      <AvisoEstilo terminos={campo ? avisosRef.current[campo] : undefined} />
       <EditableTextArea ... />

@@ las cinco cajas que Dashboard pinta directamente
+            <AvisoEstilo terminos={avisosRef.current["ai_analysis_summary"]} />
+                <AvisoEstilo terminos={avisosRef.current["ai_analysis_redirects"]} />
+              <AvisoEstilo terminos={avisosRef.current["ai_analysis_errors"]} />
+                <AvisoEstilo terminos={avisosRef.current["ai_conclusions"]} />
+                <AvisoEstilo terminos={avisosRef.current["ai_recommendations"]} />
```

`git diff --stat`:

```
frontend/src/components/dashboard/Dashboard.tsx | 14 +++++++++++++-
1 file changed, 13 insertions(+), 1 deletion(-)
```

**No hizo falta tocar ningún otro archivo.** `ReportBody.tsx` ya reenviaba
`campo` a `AnalysisBox` desde el sub-paso 3.4, así que las **seis cajas de
gráfica** del informe general quedaron cubiertas sin una línea más. Las cinco
restantes (resumen, redirecciones, errores, conclusiones y recomendaciones) las
pinta `Dashboard.tsx` directamente y son las cinco líneas de arriba.

### Las dos reglas que había que respetar

- **Hooks antes de cualquier `return` temprano** (regla 16): `avisosRef` es un
  `useRef` declarado junto a `pendingRef`, en la línea 142, mucho antes del
  `if (loading) return ...` de la línea ~418. El orden de hooks no cambia.
- **La ref de T12**: los avisos se leen con `avisosRef.current`, **no** como
  dependencia del `useCallback`. Si `AnalysisBox` cambiara de identidad al
  refrescarse los datos, React desmontaría el `textarea` y se perdería el foco
  al escribir — que es exactamente el motivo de que ese `useCallback` tenga las
  dependencias vacías desde que se escribió. Se conservan vacías.

### Lo que este diff NO hace

No añade estado, no toca el guardado, no toca ninguna gráfica, no toca ningún
cálculo y no cambia una sola línea del JSX existente salvo la firma de
`AnalysisBox`. El aviso **se recalcula al recargar**, no mientras se escribe:
es el mismo comportamiento que ya tenían los bloques por transacción.

---

## 2. La prueba sobre la pantalla real

`avisos_general.py` con Playwright, sobre `E2-validacion` — **14 de 14**:

```
backend: 10 columnas del general marcadas -> ['ai_analysis_active_threads',
  'ai_analysis_codes_per_second', 'ai_analysis_error_rate', 'ai_analysis_errors',
  'ai_analysis_latency', 'ai_analysis_response_times', 'ai_analysis_summary',
  'ai_analysis_transactions_per_second', 'ai_conclusions', 'ai_recommendations']
PASA  | el backend marca columnas del informe general
PASA  | ai_analysis_summary trae aviso (['tier', 'liberar/desplegar', 'decimal con punto: 179.73'])
PASA  | existe la caja del resumen del informe general
  franja del resumen general: 'Revisar estilo: tier, liberar/desplegar,
                               decimal con punto: 179.73, decimal con punto: 33.59, ...'
PASA  | el resumen del informe general pinta su franja ambar
PASA  | la franja dice 'Revisar estilo'
PASA  | la franja nombra alguno de los terminos que devolvio el backend
  franjas ambar en toda la pagina: 13
PASA  | hay al menos 10 franjas (general + transacciones): 13
PASA  | la caja de Conclusiones pinta su franja ambar
PASA  | la caja de Recomendaciones pinta su franja ambar
PASA  | se localiza el textarea del resumen general
  backend tras corregir: ai_analysis_summary -> None
PASA  | tras corregir el texto el backend ya no marca el resumen
  franjas ambar tras recargar: 12 (antes 13)
PASA  | la franja del resumen general desaparecio al recargar
PASA  | queda al menos una franja menos
  restauracion: HTTP 200
PASA  | el texto original quedo restaurado
PASA  | y su aviso vuelve a aparecer, como debe

TODO EN VERDE
```

El ciclo entero, sobre el informe general: **el aviso aparece → se edita el
texto quitando la jerga → se guarda solo → se recarga → el aviso ya no está →
se restaura el original → el aviso vuelve**.

**13 franjas ámbar** en `E2-validacion`: 10 del informe general (las 10 columnas
que el detector marca; `ai_analysis_redirects` está vacía y no cuenta) y 3 de
los bloques por transacción.

El texto del resumen quedó restaurado byte a byte (932 caracteres, empieza por
«6 transacciones quedaron en tier excelente…»).

---

## 3. Regresión

| Prueba | Resultado |
|---|---|
| `tsc --noEmit` del frontend completo | **0 errores** |
| `verificar_etapa2.py` — diez pasos, cuatro salidas | **LAS CUATRO SALIDAS PASAN** |
| `pytest tests/test_estilo.py` | **57 / 57** |

El paso 2 de `verificar_etapa2.py` (`cableado_c2.py`) edita precisamente las
cajas de `Dashboard.tsx` y comprueba que cada una guarda en su canal: sigue
pasando, así que el diff no tocó el guardado ni el cableado.

---

## 4. Estado de D36

| Vista | Aviso ámbar |
|---|---|
| **Informe general** (resumen, errores, redirecciones, conclusiones, recomendaciones y las 6 gráficas) | **SÍ** — este reporte |
| Bloques por transacción | SÍ — reporte 33 |
| Informe integrado (secciones, monitoreo, evidencias) | SÍ — reporte 33 |
| Monitoreo y Evidencias (global y por imagen) | SÍ — reporte 33 |
| **PDF y HTML exportados** | **NO**, y así debe ser |

**No queda ninguna parada abierta en la Etapa 3.**

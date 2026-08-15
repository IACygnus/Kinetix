# N3.3 — Panel de transacciones: métricas, criticidad y selección

**Fecha:** 2026-08-15
**Commit:** `0b78e33` — *N3.3: panel de transacciones con metricas, criticidad
y seleccion*
**Push:** `github/backup-trabajo-local` (`fa05fc4..0b78e33`). **`origin` NO se
tocó.**
**Estado:** **IMPLEMENTADO · `tsc --noEmit` exit 0 · PENDIENTE TU VALIDACIÓN
VISUAL** (§5).

**Presupuesto:** ~90-130 líneas, máx 2 archivos → **168 insertadas / 7
borradas, 2 archivos**. Me pasé ~38 líneas del techo: son la tabla HTML
(cabecera + 7 columnas con formato) y la interfaz `TransactionMetrics`. Si
prefieres que la tabla sea más compacta, se recorta.

Solo frontend. Backend sin tocar.

---

## 1. Lo que se ve ahora

Al soltar el JTL aparece un bloque nuevo **encima** del panel de criterios de
siempre:

```
Transacciones del JTL                    [Marcar todas] [Solo criticas] [Ninguna]
2 de 3 transacciones marcadas para analisis individual

  ☑  token                    [critica]      8.600    443 ms    529 ms   21.060 ms    23 (0.27%)
     pico de 21060ms, 48x el promedio · pico absoluto de 21060ms (>=10s, posible timeout)
  ☑  Adapter VerifMethod      [critica]      8.599  2.941 ms  3.515 ms   21.058 ms    54 (0.63%)
     no apto por criterios (p90 3515ms, 0.63% error) · pico absoluto de 21058ms
  ☐  Adapter SendCode                        8.574    139 ms    149 ms      388 ms    23 (0.27%)
```

- Las críticas van con **fondo ámbar tenue**, etiqueta `critica` y el **motivo
  visible** debajo del nombre (además de en `title`, como tooltip).
- Números con separador de miles (`es-CO`), milisegundos enteros, porcentaje de
  error con 2 decimales, columnas alineadas a la derecha con `tabular-nums`.
- El orden lo decide el backend (críticas primero, luego por `max`): la UI no
  reordena.

---

## 2. Decisiones de implementación

### 2.1 Re-evaluación al cambiar los criterios: se re-consulta al backend

Los criterios globales pueden cambiar después de cargar el archivo. Elegí
**re-llamar al endpoint con debounce de 800 ms** en vez de recalcular en el
cliente:

```typescript
useEffect(() => {
  if (files.length === 0 || transactions.length === 0) return;
  const t = setTimeout(() => {
    extractLabelsFromFile(files[0], responseTime, availability);
  }, 800);
  return () => clearTimeout(t);
}, [responseTime, availability]);
```

**Por qué, y no el cálculo en cliente:** recalcular aquí obligaría a duplicar
los umbrales de criticidad en TypeScript, y en N3.2 me cuidé expresamente de
**no duplicar** esa lógica (se importa de `gemini.py`). Con dos copias, el día
que cambie un umbral tendríamos dos verdades. La llamada cuesta ~0,35 s
medidos en N3.2, y solo se dispara cuando ya hay métricas cargadas.

**Contrapartida honesta:** con un JTL grande en XML (el de 73 MB tarda 1,5 s) se
vuelve a subir el archivo en cada re-evaluación. Si te resulta lento al teclear
criterios, se sube el debounce o se re-evalúa solo al salir del campo (`onBlur`).

### 2.2 La selección sobrevive a la re-evaluación

Si la selección fuera un estado plano, cada re-llamada la pisaría. Se deriva:

```typescript
const isSelected = (t: TransactionMetrics) => manualSel[t.label] ?? t.is_critical_suggested;
```

`manualSel` guarda **solo lo que tú tocas**. Así:

| Acción | Efecto |
|---|---|
| Cargas el archivo | marcadas = las que sugiere el backend |
| Desmarcas una crítica | queda desmarcada aunque cambien los criterios |
| Cambias los criterios | las que no tocaste siguen la nueva sugerencia |
| **Solo criticas** | limpia los overrides → vuelve a la sugerencia del backend |
| **Marcar todas** / **Ninguna** | fija todas a true / false |

### 2.3 Degradación elegante

```typescript
try {
  const data = await testAPI.extractJTLTransactions(file, rt, av);   // endpoint nuevo
  setTransactions(data.transactions || []);
  setDetectedLabels((data.transactions || []).map(t => t.label));
} catch (err) {
  console.error('extract-jtl-transactions fallo, se usa el endpoint anterior:', err);
  try {
    const response = await testAPI.extractJTLLabels(file);           // el de siempre
    setTransactions([]);
    setDetectedLabels(response.labels || []);
  } catch (err2) { setTransactions([]); setDetectedLabels([]); }
}
```

Tres niveles: endpoint nuevo → endpoint viejo → vacío. La tabla nueva se pinta
con `transactions.length > 0`; el panel de criterios de siempre se pinta con
`detectedLabels.length > 0`. **En fallback, la pantalla queda exactamente como
antes de N3.3.**

### 2.4 Formato del payload: aditivo

```typescript
const acceptanceCriteria = JSON.stringify({
  concurrency, response_time, availability,
  ...(Object.keys(perTransaction).length > 0 ? { per_transaction: perTransaction } : {}),
  ...(selectedLabels.length > 0 ? { critical_transactions: selectedLabels } : {}),
});
```

Elegí **una clave nueva en el JSON de criterios** en vez de un campo aparte
porque el endpoint `/upload` recibe los criterios como un único query param y
añadir un parámetro nuevo obligaría a tocar la firma de `uploadJTL` y del
endpoint — más superficie por el mismo resultado. **Sin marcadas, la clave no se
emite y el payload queda byte a byte como antes.**

---

## 3. Los criterios individuales siguen intactos

El bloque `<details>` «Criterios por Transaccion» (concurrencia / response time
/ disponibilidad por transacción, más «Aplicar a todas») **no se tocó**: sigue
alimentándose de `detectedLabels` y construyendo `per_transaction` igual que
antes. Lo único que cambió es de dónde salen los labels (del endpoint nuevo, o
del viejo si falla).

---

## 4. Validación hecha

### 4.1 `tsc --noEmit`

```
tsc exit: 0
```

### 4.2 El payload no rompe nada (verificado por lectura del backend)

Seguí la clave nueva por todos sus consumidores:

| Consumidor | Qué hace con `critical_transactions` | Riesgo |
|---|---|---|
| `upload.py:397` | `json.loads` a dict plano, sin schema ni validación | ninguno |
| `upload.py:444` | lo guarda tal cual en la columna JSON | ninguno |
| `compute_verdict` (`gemini.py:205-223`) | lee solo `response_time`, `availability`, `raw_text` con `.get()` | ninguno |
| `compute_per_transaction_verdicts` (`gemini.py:240-284`) | lee solo `response_time`, `availability`, `per_transaction` | ninguno |
| `analysis_pipeline.py:369` | itera **`per_scenario`**, no el dict de arriba, y además exige `isinstance(sc_vals, dict)` | ninguno |
| `Dashboard.tsx:771-789` | itera **`verdicts_per_transaction`**, no las claves de arriba | ninguno |

Ningún consumidor recorre las claves de primer nivel del JSON, así que la clave
nueva viaja inerte hasta que N3.4 la lea.

### 4.3 Lo que NO validé y por qué

**No ejecuté un upload real de prueba.** Un `/upload` dispara las 12 llamadas de
IA, consume cuota y deja una ejecución basura en tu base. La comprobación de que
«Generar Reporte sigue funcionando igual» es precisamente parte de tu validación
visual (§5), y el análisis de arriba dice por qué no debería cambiar nada.

---

## 5. Lo que necesito que valides (visual)

1. **JTL de Coomeva (CSV)** → la tabla con las 3 transacciones y sus métricas;
   **`token` premarcada** con el motivo del pico de 21.060 ms.
2. **JTL en XML** → antes no salía panel; ahora debe salir la tabla completa.
3. **Los tres botones**: «Marcar todas», «Solo criticas» (vuelve a la
   sugerencia), «Ninguna».
4. **Aviso del tope**: marca más de 10 y comprueba el recuadro ámbar. Con el
   JTL de estrés XML (6 transacciones) no llegarás a 10; hace falta un JTL con
   más transacciones.
5. **Cambiar los criterios con el archivo ya cargado**: al segundo de dejar de
   teclear, la criticidad se recalcula y **lo que hayas marcado a mano se
   respeta**.
6. **Generar Reporte** → debe comportarse exactamente igual que siempre.

---

## 6. Archivos tocados

| Archivo | Qué | Backup |
|---|---|---|
| `frontend/src/components/dashboard/UploadJTL.tsx` | tabla, checks, controles, aviso, fallback, debounce, payload | `.bak_n33_20260815_150002` |
| `frontend/src/services/api.ts` | `extractJTLTransactions()` + interfaz `TransactionMetrics` | `.bak_n33_20260815_150002` |

Regla 16 respetada: el `useEffect` nuevo y los derivados van **antes** del
`if (loading) return (…)` de la línea 272. Backend sin tocar; `/extract-jtl-labels`
sigue en su sitio y ahora es la red de seguridad del panel.

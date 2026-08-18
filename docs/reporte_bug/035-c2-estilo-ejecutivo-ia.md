# C2 — Estilo ejecutivo en los análisis de IA

**Fecha:** 2026-08-18
**Commit:** `ef8636c` — *C2: estilo ejecutivo en los analisis de IA*
**Push:** `github/backup-trabajo-local` (`7237279..ef8636c`). **`origin` NO se
tocó.**
**Estado:** **IMPLEMENTADO Y VALIDADO CON DATOS REALES DE COOMEVA.**
**Coste de IA declarado:** **2 llamadas reales** (1 antes del cambio, 1 después),
ambas sobre la sección *Response Times por Transacción*. Provider `openai`,
modelo `gpt-5.5` (el configurado en la BD).

**Presupuesto:** 1-2 archivos de prompts → **1 archivo**
(`backend/app/services/ai/gemini.py`), **+39 / -11 líneas**.
Backup: `gemini.py.bak_20260818_161956`.

---

## 1. Qué se cambió

### 1.1 `SYSTEM_PROMPT` — las seis reglas

Las reglas 12-15 anteriores se reescribieron y ampliaron a 12-19. Las **seis
reglas pedidas** quedaron así (numeración final en el prompt):

| # | Regla | Texto en el prompt |
|---|---|---|
| 12 | **Apertura** | Primera frase con cifra concreta. PROHIBIDO abrir con "El grafico…", "El analisis muestra…", "Se observa…", "En el presente analisis…", "A continuacion se detalla…", "Como se puede apreciar…" |
| 13 | **Cifras exactas** | Valores reales tal como se entregan (139ms, 2941ms, 21060ms). PROHIBIDO "cercano a", "aproximadamente", "alrededor de", "unos", "valores estables en torno a" |
| 14 | **Ratios obligatorios** | Toda comparación o pico va con su relación numérica ("21 veces mas lenta", "47 veces sobre su promedio"). Los ratios ya vienen calculados: usarlos tal cual |
| 15 | **Razonar, no describir** | Cada observación con su lectura probable marcada como hipótesis ("apunta a", "sugiere", "es coherente con"). Prohibido afirmar causas como hechos y prohibido convertir el análisis en lista de tareas |
| 16 | **Cierre con impacto** | UNA frase final sobre lo que percibirá el usuario en producción, en lenguaje de negocio, sin tecnicismos |
| 17 | **Densidad** | Prohibidas las frases sin dato, lectura ni impacto: "En terminos generales…", "cabe destacar…", "es importante mencionar…", "en resumen…" |

Se conservaron sin tocar, renumeradas: **18** (no cerrar repitiendo) y **19**
(**GRAF1**: los picos ≥10x el promedio o ≥10 s se mencionan siempre con su
cifra y su causa probable).

**Matiz añadido a la regla 15:** la prohibición de listar tareas lleva la
excepción explícita *"salvo las secciones que expresamente te pidan
conclusiones, prioridades o recomendaciones"*. Sin ese matiz la regla chocaba
con los prompts de `analyze_summary_table` ("Prioridades de mejora"),
`analyze_errors` ("acciones inmediatas") y `generate_recommendations`, que sí
deben producir listas.

### 1.2 Ejemplos contrastados **ASÍ SÍ / ASÍ NO**

Se añadieron los dos ejemplos de Fredy (el de Copilot como bueno, la salida
actual como mala) y se re-etiquetaron los dos que ya existían. Quedan **cuatro
bloques**: 2 × ASÍ SÍ y 2 × ASÍ NO.

Precede a los cuatro un aviso: *"son de OTRAS pruebas y están aquí solo por su
forma de redactar: nunca copies sus cifras ni sus nombres de transacción"* —
salvaguarda contra que el modelo repita "139ms / VerifMethod" en informes de
otros clientes.

### 1.3 Prompts de sección

- **Nueva constante `STYLE_REMINDER`** (módulo `gemini.py`): resumen operativo
  de las seis reglas que se pega **al final** del prompt de `analyze_chart`.
  En prompts largos la última instrucción pesa más que la primera; el
  `SYSTEM_PROMPT` va al principio, a miles de caracteres del punto donde el
  modelo empieza a escribir.
- **Reemplaza** a la línea suelta *"Cierra con una oracion sobre el impacto en
  produccion."* que había al final de ese prompt.
- **Alcance:** las **7 gráficas** que pasan por `analyze_chart`
  (response_times, throughput, latency, error_rate, codes_per_second,
  transactions_per_second, active_threads).
- **NO se añadió** a `analyze_summary_table`, `analyze_errors`,
  `analyze_redirects`, `generate_conclusions` ni `generate_recommendations`:
  esos prompts piden explícitamente prioridades, acciones inmediatas o
  recomendaciones, y el recordatorio ("nada de lista de tareas") los
  contradiría. Sobre ellos siguen aplicando igualmente las reglas 12-19 del
  `SYSTEM_PROMPT`, que es global a todas las secciones.
- **Instrucción específica de `response_times`:** se añadió una línea que
  ordena tomar el ratio del bloque `RATIO PEOR/MEJOR` y el de los picos
  marcados `[PICO: max Nx el promedio]` que el pipeline ya calcula y envía
  (`analysis_pipeline.py:184-190`, `gemini.py` → `build_tier_summary`), en vez
  de estimarlos.

---

## 2. Lo que NO se tocó

- Las **palabras prohibidas** del CLAUDE.md (regla 2 del `SYSTEM_PROMPT`):
  intactas.
- **`sanitize_ai_text()`**: intacta, ni una línea.
- **GRAF1** (mención obligatoria de picos/máximos): intacta, ahora regla 19.
- **Topes de palabras de B6.3**: intactos — 120 por gráfica, 150 tabla resumen,
  350 conclusiones y recomendaciones.
- **Estructura del pipeline y los 12 pasos**: intactos. `analysis_pipeline.py`
  no se modificó.
- `origin` (Azure) no recibió nada.

---

## 3. Validación con datos reales de Coomeva

**Fuente:** `resultados_general_carga  31-jul.-2026-134550.jtl` (ejecución
`115346ea` — *24342-Coomeva_SendCode_Performance*, escalabilidad, 25.773
muestras). Es el JTL que corresponde exactamente a las cifras del ejemplo de
Copilot (SendCode 139 ms, VerifMethod 2941 ms, pico 21060 ms).

**Datos enviados a la IA** (idénticos en ambas corridas, generados con el mismo
código del pipeline):

```
- token: promedio 443ms, P90 529ms, P95 657ms, P99 1070ms, min 311ms, max 21060ms [PICO: max 48x el promedio]
- Adapter VerifMethod: promedio 2941ms, P90 3515ms, P95 3749ms, P99 4281ms, min 297ms, max 21058ms
- Adapter SendCode: promedio 139ms, P90 149ms, P95 156ms, P99 179ms, min 98ms, max 388ms
```

> **Nota de precisión:** el ejemplo de Copilot atribuye el máximo de 21060 ms y
> el ratio 47,6x a *Adapter VerifMethod*. Los datos dicen otra cosa: ese máximo
> es de **token** (21060 / 443 = 47,6x). VerifMethod tiene su propio máximo,
> 21058 ms, que es 7,2x su promedio. La salida nueva lo asigna correctamente.

### 3.1 ANTES del cambio (llamada real nº 1)

> Adapter SendCode lidera con 139ms y comportamiento excelente, mientras Adapter VerifMethod cae en tier degradado con 2941ms, 21,1 veces más lento y con impacto directo en esperas visibles para el usuario. token también queda en tier excelente por promedio, pero su máximo de 21060ms, 47,6 veces su media, apunta a timeouts, esperas de backend o contención bajo escalamiento gradual. Adapter VerifMethod mantiene P99 de 4281ms frente a 2941ms, pero su máximo de 21058ms supera 10 segundos, señal de bloqueos intermitentes. Adapter SendCode conserva baja dispersión entre promedio, P95 y P99. En producción, token y Adapter VerifMethod pueden generar pantallas congeladas, reintentos y abandono del flujo de autenticación.

*(107 palabras)*

### 3.2 DESPUÉS del cambio (llamada real nº 2)

> 2 de 3 transacciones quedaron en tier excelente, token y Adapter SendCode, mientras Adapter VerifMethod quedó degradada, lo que sugiere un flujo dividido entre operaciones ágiles y una validación que concentra la espera. Adapter SendCode fue la más rápida con 139ms y Adapter VerifMethod la más lenta con 2941ms, 21.1 veces mayor, consistente con una dependencia externa o validación más costosa bajo escalamiento. token mantiene 443ms, pero su máximo de 21060ms, 47.6 veces sobre su promedio, apunta a timeouts o contención intermitente; Adapter VerifMethod llegó a 21058ms, 7.2 veces sobre su promedio, coherente con esperas prolongadas. En producción, el usuario percibirá códigos ágiles, validaciones lentas y pausas ocasionales que pueden afectar la continuidad del proceso.

*(115 palabras)*

### 3.3 Verificación punto por punto

| Verificación pedida | ANTES | DESPUÉS |
|---|---|---|
| No empieza con "El gráfico…" / "El análisis…" / "Se observa…" | ✅ | ✅ |
| Contiene ratios numéricos | ✅ (21,1x / 47,6x) | ✅ (21.1x / 47.6x / **7.2x**) |
| Sigue mencionando el pico de **21060 ms** | ✅ | ✅ |
| Cierra con el impacto para el usuario final | ⚠️ cierra en jerga ("reintentos y abandono del flujo de autenticación") | ✅ ("el usuario percibirá códigos ágiles, validaciones lentas y pausas ocasionales") |
| Hipótesis marcadas como tales | parcial ("apunta a", "señal de") | ✅ ("sugiere", "consistente con", "apunta a", "coherente con") |
| Sin "cercano a" / "aproximadamente" / "alrededor de" | ✅ | ✅ |
| Sin palabras prohibidas del CLAUDE.md | ✅ | ✅ |
| Sin markdown residual | ✅ | ✅ |
| Dentro del tope de 120 palabras | ✅ 107 | ✅ 115 |

### 3.4 Lectura honesta del antes/después

**El "ANTES" ya no era la salida que Fredy comparó con Copilot.** El texto malo
del enunciado ("El gráfico de Response Times… valores estables cercanos a 150
ms… En términos generales…") viene de una versión anterior del prompt: el
`SYSTEM_PROMPT` ya traía de un sprint previo las reglas 12-15 (empezar por el
dato, no rellenar, mencionar picos). Por eso la corrida ANTES ya arranca con
cifra y ya trae dos ratios.

Lo que **sí** aporta C2, visible al comparar los dos textos:

1. **Todos los picos llevan ratio.** Antes, el máximo de VerifMethod se
   describía como "supera 10 segundos"; ahora es "21058ms, 7.2 veces sobre su
   promedio".
2. **Toda causa va marcada como hipótesis.** Antes había una afirmación seca
   ("con impacto directo en esperas visibles"); ahora cada lectura lleva
   "sugiere", "consistente con", "coherente con".
3. **El cierre es de negocio, no técnico.** Antes cerraba con "reintentos y
   abandono del flujo de autenticación"; ahora con lo que el usuario percibe.
4. **Desaparece la frase de relleno.** Antes gastaba una oración entera en
   "Adapter SendCode conserva baja dispersión entre promedio, P95 y P99" — dato
   sin lectura ni impacto. La regla 17 la elimina y el espacio se reinvierte en
   el ratio de VerifMethod.

**Advertencia metodológica:** es **una muestra por lado**, con
`temperature=0.7`. La forma (apertura, ratios, cierre) está ahora forzada por
el prompt y es estable; la redacción exacta variará entre ejecuciones.

---

## 4. Verificaciones técnicas

```
python -m py_compile backend/app/services/ai/gemini.py   → OK
docker restart jmeter_backend                            → Up (healthy), sin build
git diff --stat                                          → 1 archivo, +39 / -11
```

Los scripts temporales de la validación vivieron en `/tmp` del contenedor y en
el scratchpad de la sesión; **no se añadió nada al repo** salvo este reporte y
`gemini.py`.

---

## 5. Criterio de éxito

El código está en su sitio y las verificaciones automáticas pasan, pero **el
criterio de éxito sigue siendo la validación visual de Fredy**: la pregunta
abierta es si el texto de §3.2 se acerca lo suficiente al estilo objetivo de
Copilot o si hay que ajustar el peso de alguna regla.

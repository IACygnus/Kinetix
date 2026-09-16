3f62086 · 2026-09-15

# ETAPA 1 — Cierre

**Estado: Etapa 1 implementada, pendiente validación de Fredy.**

Llamadas reales a la IA en toda la etapa: **70 de ~70 autorizadas** (35 en 1.3 + 35 en 1.6).
Todos los demás sub-pasos: 0. Ningún archivo protegido tocado. Ninguna condición de PARADA
se activó.

---

## 1. Trazabilidad de sub-pasos (adenda C)

| Sub-paso | Reporte | Hash base (1ª línea del reporte) | Hash del commit del sub-paso |
|---|---|---|---|
| 1.1 Especificación v1.2 | `03_ETAPA1_1_especificacion_v1_2.md` | `a98edd9` | **`842d8a2`** |
| 1.2 Preparación | `04_ETAPA1_2_preparacion.md` | `842d8a2` | **`ed6f0d0`** |
| 1.3 Corrida 1 (antes) | `05_ETAPA1_3_corrida1_baseline.md` | `ed6f0d0` | **`7c18eb4`** |
| 1.4 Fix H4 | `06_ETAPA1_4_fix_h4_event_loop.md` | `7c18eb4` | **`b3cd3d1`** |
| 1.5 Fix HF-2 | `07_ETAPA1_5_fix_hf2_circuit_breaker.md` | `b3cd3d1` | **`5d2193c`** |
| 1.6 Corrida 2 (después) | `08_ETAPA1_6_corrida2_baseline.md` | `5d2193c` | **`0c49419`** |
| Adenda A | `09_ETAPA1_adendaA_liberacion_flag_prueba.md` | `0c49419` | **`fc7168e`** |
| 1.7 Análisis | `10_ETAPA1_7_analisis_linea_base.md` | `fc7168e` | **`3f62086`** |
| 1.8 Cierre | `11_ETAPA1_cierre.md` | `3f62086` | **`5e8b863`** |
| Adenda B | `12_ETAPA1_adendaB_errores_transitorios.md` | `5e8b863` | *(commit de la adenda B)* |

El hash base de cada reporte coincide con el commit del sub-paso anterior: la cadena es continua
y cada reporte declara sobre qué estado del repositorio se escribió.

> Nota de numeración: la secuencia se corrió respecto al plan original porque las adendas
> añadieron dos reportes (09 y 12). Por eso 1.7 es el 10 y el cierre el 11, y la adenda B queda
> después del cierre por ser posterior a él.

---

## 2. Qué cambió en el producto

### H4 — el backend ya no se congela durante la generación

24 llamadas de IA que se hacían de forma síncrona dentro de funciones `async` pasaron a
`asyncio.to_thread`, en 7 archivos. Medido con una sonda a `/auth/me` cada 2 s durante una
generación real:

| | Antes | Después |
|---|---|---|
| Peor respuesta | **54,9 s** | **21 ms** |
| Media | 457,9 ms | 3,5 ms |
| Errores | 1 | 0 |

### HF-2 — la IA ya se recupera sola

Tres defectos encadenados, todos corregidos:

1. El circuito **no se cerraba nunca** salvo reiniciando el proceso.
2. Los errores se clasificaban **por subcadenas del mensaje**, así que
   `"Failed to generate response"` (contiene *rate*) dormía 30 s para nada.
3. El cliente sumaba **hasta 9 peticiones HTTP** por sección, invisibles para la telemetría.

### Adenda B — los fallos recuperables vuelven a reintentarse (D9-D12)

D5 había puesto `max_retries=0` en el cliente para hacer visible cada intento, y con eso desactivó
también el reintento de **siete tipos de fallo transitorio** que el SDK sí reintentaba
(desconexión, timeout, 408, 409, 5xx, y los equivalentes de Gemini). Un corte de red de un
segundo dejaba la sección sin texto.

| | Decisión | Efecto |
|---|---|---|
| D9 | Clase `transient` con reintento propio (2 s y 4 s) | El reintento vuelve, y ahora **cada intento deja su línea de telemetría** |
| D10 | Transitorio agotado → abre el circuito con enfriamiento | Mismo camino que `rate_limit`; no hizo falta código nuevo |
| D11 | `timeout=120.0` en el cliente | Era `read=600 s`: una llamada colgada retenía un hilo diez minutos |
| D12 | 4xx no listados → error seco, sin abrir el circuito | Ya era así; verificado, no cambia |

Validado con 8 escenarios (3/8 pasaban antes, 8/8 ahora) más la regresión completa de 1.5 y de
la adenda A.

### Telemetría (E1.2, previa a la etapa)

Una línea por llamada con latencia y tokens. Sin ella, H1 no se podía responder.
La adenda B añade el outcome `transient_error`; el resto queda intacto y las corridas siguen
siendo comparables.

---

## 3. Hipótesis: veredicto final

| | Hipótesis | E1.1 | Etapa 1 |
|---|---|---|---|
| H1 | El razonamiento domina la latencia | pendiente | **CONFIRMADA, con matiz**: es el 68,7 % y 70,0 % de los tokens generados, pero domina **por volumen**, no por coste unitario (b ≈ c) |
| H2 | Llamadas secuenciales | confirmada | sin cambios — sigue siendo secuencial **a propósito** |
| H3 | Prompts redundantes | parcial | sin cambios — `SYSTEM_PROMPT` sigue duplicado (Etapa 4) |
| H4 | El cliente síncrono bloquea el event loop | confirmada | **CORREGIDA y medida** |
| H5 | Reintentos/esperas ocultos | refutada | **matizada**: no ocurrían, pero el mecanismo podía dispararse por falsos positivos. Ya no |

---

## 4. Lo que esta etapa NO hizo

Conviene dejarlo escrito para no generar expectativas equivocadas:

- **No acelera la generación.** T2−T0 fue 354,3 s antes y 357,4 s después. H4 arregla el
  bloqueo, no el tiempo.
- **No reduce el número de llamadas** (siguen 11 + 8N) ni las paraleliza.
- **No toca `reasoning_effort`.** 1.7 estima el techo; aplicarlo es Etapa 4.

El camino a un informe notablemente más rápido pasa por el número de llamadas y la
secuencialidad, no por lo que se hizo aquí.

---

## 5. Riesgos y deuda anotada

| Punto | Estado |
|---|---|
| `SYSTEM_PROMPT` duplicado por llamada | documentado, sin tocar (Etapa 4) |
| Parseo de JTL con pandas, síncrono en caminos `async` | reportado en 1.4, sin tocar — `jtl_parser.py` es protegido |
| Caché de prompts al 7,7 % en uso realista | analizado en 1.7 |
| Umbral de mejora de 1,5 % basado en n = 2 | declarado con sus advertencias |

---

## 6. Verificación final

- `git status`: limpio.
- 11 commits de la etapa, todos en `github/backup-trabajo-local`.
- Reportes 03-12 en `docs/reporte_claude_code/`, numeración consecutiva sin huecos.
- `py_compile` verde en los 9 archivos tocados a lo largo de la etapa.
- Escenarios con stubs: **12/12** (HF-2) + **8/8** (adenda A) + **8/8** (adenda B) + event loop, todos con
  **0 llamadas reales**.

---

## 7. Qué falta para dar la etapa por buena

La validación de Fredy desde la interfaz, con el guion de `/tmp/reporte-para-fredy-etapa1.md`.

**HF-2 no se puede provocar desde la interfaz**: requiere que el proveedor devuelva un 429 o
agote la cuota. Su evidencia son los 28 escenarios con stubs de los reportes 07, 09 y 12, no una
prueba manual.

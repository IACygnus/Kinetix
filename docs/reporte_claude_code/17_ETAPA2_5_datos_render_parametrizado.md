3bc8733 · 2026-09-16

# ETAPA 2.5 — Datos del render parametrizado + saneo de prompts agregadores

**Llamadas reales a la IA en este sub-paso: 0.** Presupuesto de etapa: **1 / 50**.
**Ningún archivo protegido tocado.** 2 archivos: `services/ai/gemini.py`,
`api/v1/endpoints/integrated_report.py`.

---

## 1. Hallazgo principal: la capa de datos ya está completa

El enunciado pedía «funciones/endpoints que entreguen, para un alcance dado, la tabla resumen
filtrada, las series de las 5 gráficas y los 6 análisis». Comprobado contra la API real:
**no hace falta ningún endpoint nuevo.** Todo existe desde N4.

| Necesidad del alcance | Qué lo cubre | Estado |
|---|---|---|
| Tabla resumen filtrada | `GET /executions/{id}/charts` → `by_label`, una fila por transacción | ✅ existe |
| Las 5 series | `GET /executions/{id}/transaction-charts?label=` (N4.4) | ✅ existe |
| Los 6 análisis | `GET /executions/{id}/transaction-report?label=` | ✅ existe |
| Overrides aplicados | `_apply_ia_overrides` (F6) en el integrado | ✅ existe |

**Decisión declarada:** no se añade un endpoint agregador «por alcance». Sería una tercera forma
de pedir datos que ya se piden, y el frontend carga `/charts` de todos modos para el informe
general: filtrar `by_label` por label en cliente no cuesta una petición extra. Añadirlo sería
código nuevo que mantener sin ganar nada.

### La fila de `by_label` trae todas las columnas del resumen general

```
label=4. Get_Booking_Id · count=1677 · avg_time=108.3 · min_time=85.0 · max_time=438.0
p90=123.4 · p95=139.0 · p99=206.0 · success_count=985 · error_count=692
error_rate=41.26 · throughput=5.59 · kb_received=1389.59 · kb_sent=412.5
```

> ### ⚠ CORRECCIÓN — lectura equivocada de §2.1 en la primera versión de este reporte
>
> Escribí que la tabla del bloque por transacción llevaría «las cinco columnas de la
> especificación». **Es un error de lectura: §2.1 describe el PANEL DE SELECCIÓN de la pantalla
> Nuevo Reporte (Etapa 5), no el informe.**
>
> Lo que manda para el informe es §1: «el informe por transacción es el informe general con el
> **mismo diseño**, filtrado». Es decir, la tabla del bloque por transacción es **el mismo
> componente/función que la tabla resumen del general, con las mismas columnas**, filtrada a esa
> transacción. **Queda prohibido crear una tabla de 5 columnas para el informe.**
>
> El dato de arriba lo confirma viable sin trabajo extra: `by_label` ya trae la fila completa con
> todas las columnas del resumen, así que filtrar por label basta y no hay que calcular nada.

**La definición de TPS de v1.2 §2.1 sí cuadra con el dato real:** 1.677 muestras ÷ 300 s de prueba
= **5,59**, que es exactamente el `throughput` que devuelve `by_label`. Eso vale para cuando la
Etapa 5 construya el panel: mirará la misma fuente que el informe.

---

## 2. Verificación en las dos ejecuciones

| | ff186cc7 (`pruebakinetix`) | E1.3-baseline-2 |
|---|---|---|
| Alcance probado | `4. Get_Booking_Id` | `5. Put_Update_Booking` |
| Tabla filtrada | 1.677 · 108,3 ms · 5,59 · 692 | 1.677 · 109,6 ms · 5,59 · 952 |
| **`throughput_timeline`** | **0 puntos** | **0 puntos** |
| Series por transacción | 5: `response_times=299, latency=299, error_rate=299, codes=526, tps=299` | 5: `300, 300, 300, 552, 300` |
| Análisis | `progress 6/6` | `progress 6/6` |

**El alcance general no cambia salvo por la ausencia de Throughput** (`throughput_timeline: 0`),
que es justo D19 funcionando en vivo sobre datos reales.

> Aclaración para que no parezca un fallo: el listado de secciones **con texto** muestra ocho
> (incluidas `conclusions` y `recommendations`), pero el progreso dice **6/6**. Es el
> comportamiento de D20: las filas antiguas se conservan y se devuelven, pero no cuentan ni se
> pintarán.

---

## 3. Saneo de los prompts agregadores (nota 1)

Se verificaron los tres agregadores. **Había dos problemas reales**, ambos corregidos.

### 3.1 Encabezados huérfanos en conclusiones y recomendaciones

`generate_conclusions` numeraba diez bloques, dos de ellos ya vacíos:

```
4. RESPONSE TIME OVER TIME:
{ai_analysis_response_time_over_time}     ← siempre ""

5. THROUGHPUT:
{ai_analysis_throughput}                  ← siempre "" desde 2.3
```

Con las secciones retiradas, el modelo recibiría **dos encabezados numerados sin contenido**.
Se eliminan y se renumera de 1 a 8. Lo mismo en `generate_recommendations`, donde las dos
alimentaban los bloques «PATRONES DE TIEMPOS» y «CAPACIDAD».

Los **parámetros siguen en la firma** de ambos métodos para no tocar a los llamadores, marcados
en el código como aceptados pero ya no usados.

> Esto roza D25 («no se tocan los textos de los prompts»). Se hace porque no es un cambio de
> estilo: es retirar un insumo muerto que dejaría encabezados colgando. La nota lo pide
> expresamente.

### 3.2 La fuga por overrides — que es la que importaba

`_section_analyses_for_prompt` (F5.2) alimenta el consolidado recorriendo `_SECCION_LABEL`, que
incluía `ai_analysis_throughput` y `ai_analysis_response_time_over_time`.

Para una ejecución nueva el campo va vacío y el filtro `if not texto: continue` ya las descartaba.
**Pero si esa sección tiene un override editado a mano, `editado` no es `None` y el texto entraba
igual en el prompt.** Y en la base hay informes reales que lo tienen.

Se retiran las dos claves de `_SECCION_LABEL`. Las filas de override **no se borran** (D23): se
ignoran al construir el prompt y al renderizar.

### 3.3 Conclusiones/recomendaciones por transacción

**No entran en ningún agregador.** El consolidado consume `e["conclusions"]`, que es el
`ai_conclusions` de la ejecución (nivel general), y `_SECCION_LABEL` no tiene ninguna clave
`txreport_*`. No hizo falta cambiar nada; se deja verificado.

### 3.4 Validación — 14/14, 0 llamadas reales

| Comprobación | Resultado |
|---|---|
| `_SECCION_LABEL` ya no lista throughput ni response_time_over_time | PASA |
| Sigue listando las secciones vivas | PASA |
| (a) Sin overrides: los textos retirados no entran | PASA |
| (a) Las secciones vivas sí entran | PASA |
| (a) Sin encabezado huérfano de «Throughput» | PASA |
| (b) **El override de throughput NO entra** | PASA |
| (b) El override de response_time_over_time NO entra | PASA |
| (b) Un override de sección **viva** sí entra | PASA |
| (c) El integrado real `fa724249` trae el override en base | PASA |
| (c) **Un fragmento exclusivo suyo NO aparece en el prompt** | PASA |
| (c) Los overrides de secciones vivas siguen entrando | PASA |

> **Nota de método.** El primer intento del caso (c) dio FALLA con el marcador
> `"prueba guardado automatico"`. No era un defecto del código: ese mismo prefijo está en **nueve
> claves** de ese informe, incluidas vivas como `ai_analysis_summary` y `ai_analysis_latency`, así
> que el marcador no discriminaba. Se rehízo la prueba buscando automáticamente un fragmento de
> ≥40 caracteres **exclusivo** del override de throughput, y con él pasa. Queda anotado porque un
> marcador mal elegido puede dar tanto un falso positivo como un falso negativo.

`py_compile` OK en los 2 archivos.

---

## Estado

Sub-paso 2.5 completado. Se continúa con 2.6 (pantalla), donde entra el primer archivo protegido
y aplica la condición **C1**: refactor puro primero, equivalencia demostrada, y solo después los
cambios funcionales.

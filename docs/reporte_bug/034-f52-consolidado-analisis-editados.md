# F5.2 — El consolidado usa todos los análisis editados como insumo

**Fecha:** 2026-08-17
**Commit:** `4c20a55` — *F5.2: el consolidado usa todos los analisis editados
como insumo*
**Push:** `github/backup-trabajo-local` (`e9dcd4e..4c20a55`). **`origin` NO se
tocó.**
**Estado:** **IMPLEMENTADO Y VALIDADO SIN GASTAR CUOTA DE IA** (analizador
stubbeado, patrón F5).

**Presupuesto:** ~50-80 líneas, máx 2 archivos → **59 insertadas, 0 borradas,
1 archivo.**

---

## 1. Diagnóstico previo

1. El prompt de `generate-consolidated` consume hoy, por ejecución: **KPIs**
   (`total_requests`, `error_rate`, percentiles, throughput, latencia,
   duración), **veredicto**, **conclusiones** y **recomendaciones**
   (`integrated_report.py:1834-1841`).
2. De esos cuatro, F5 solo aplicaba overrides a `ai_conclusions` y
   `ai_recommendations`.
3. Además se añaden aparte los análisis de **monitoreo** y **evidencias**.
4. **Los 10 análisis de sección no entraban en absoluto** — ni originales ni
   editados.
5. Medido con el informe real de Coomeva (2 ejecuciones + monitoreo):
   **23.360 caracteres** (~5.840 tokens de entrada).
6. Esos 10 análisis pesan, sin recortar, entre **8.236 y 12.291 caracteres por
   ejecución** — de ahí la necesidad del punto (3).

---

## 2. El cambio

Un helper nuevo, `_section_analyses_for_prompt(execution, overrides_analysis)`,
recorre las 11 columnas de análisis reusando el mapa `_IA_KEY_BY_COLUMN` que ya
existía, y los overrides salen de `_load_section_overrides` — **la misma fuente
que F5 y F6, sin lógica duplicada**. Conclusiones y recomendaciones se excluyen
a propósito: ya viajan en sus propios bloques desde F5.

El bloque entra en el prompt **antes** de monitoreo y evidencias, con una
instrucción explícita para el modelo:

> «los marcados como CORREGIDO POR EL USUARIO son correcciones suyas: tienen
> prioridad sobre cualquier otro texto y sobre tu propio criterio; los demás van
> recortados y solo dan contexto»

---

## 3. Control de tamaño

### 3.1 Antes de decidir, una corrección al planteamiento

El encargo pedía comparar el tamaño del prompt contra `OPENAI_MAX_TOKENS` del
modelo activo (`gpt-5-mini` → **16.384**). **Esos dos números no son
comparables:** `OPENAI_MAX_TOKENS` se pasa como `max_completion_tokens`, que es
el techo de **salida**, mientras que el prompt es **entrada**. Son presupuestos
distintos. Lo verifiqué de primera mano en B6.3: una llamada con 565 tokens de
entrada consumió 1.118 de salida, contabilizados por separado.

O sea: **un prompt de 11.415 tokens no “se acerca” al techo de 16.384**, porque
ese techo no lo limita. El riesgo real de crecer el prompt no es truncamiento,
es **coste y latencia** — y eso sí justifica la contención.

### 3.2 La estrategia aplicada (preferencia del CTO, respaldada por números)

- **Análisis editados → completos**, marcados `CORREGIDO POR EL USUARIO`. Son la
  corrección que motiva el sprint; recortarlos vaciaría el cambio de sentido.
- **Análisis no editados → recortados a 400 caracteres**, solo como contexto.

Ahorro medido sobre 3 ejecuciones reales:

| Ejecución | Completos | Recortados | |
|---|---|---|---|
| `115346ea` | 8.236 | 4.274 | −48% |
| `d1efb084` | 12.291 | 4.274 | −65% |
| `02da3924` | 11.559 | 4.270 | −63% |
| **Total** | **32.086** | **12.818** | **−60%** |

Comprobado sección por sección que el recorte se aplica: las 10 entradas de una
ejecución quedan en **415-443 caracteres** cada una (400 + su etiqueta + `...`).

### 3.3 Tamaño del prompt resultante

| Escenario | Caracteres | ~Tokens entrada |
|---|---|---|
| **Antes** (informe real: 2 ejec + monitoreo) | 23.360 | ~5.840 |
| **Después** (mismo informe) | 36.315 | ~9.078 |
| Después, 2 ejecuciones sin monitoreo | 32.915 | ~8.228 |
| Después, **3 ejecuciones** | 45.663 | ~11.415 |

Sin la contención, el bloque de secciones habría sido 32.086 en vez de 12.818,
es decir **~19.000 caracteres (~4.800 tokens) más** en el caso de 3 ejecuciones.

---

## 4. Validación

### 4.1 Con override conocido (el caso que motiva el sprint)

Se inyectó `ERRORES CORREGIDOS POR FREDY: …` como override de
`ai_analysis_errors` en una ejecución:

```
el prompt contiene la correccion            : True
la correccion va COMPLETA (sin '...')       : True
marcada como CORREGIDO POR EL USUARIO       : True
el texto ORIGINAL de esa seccion ya no esta : True
```

Las cuatro condiciones importan: que entre, que **no se recorte**, que el modelo
sepa que es una corrección, y —la que de verdad cierra el problema de Fredy— que
**el texto errado desaparezca del insumo**.

### 4.2 Sin overrides

El bloque `Analisis de las secciones` se emite con los textos originales
recortados (20 entradas con 2 ejecuciones): comportamiento coherente, no vacío.

### 4.3 Datos de prueba limpiados

```
SELECT count(*) FROM integrated_reports WHERE sections::text LIKE '%CORREGIDOS POR FREDY%';
  ->  0
```

El script restaura el `sections` original del informe al terminar. Cero llamadas
de IA: el analizador stubbeado devolvía texto fijo y registraba los prompts.

---

## 5. Un dato que corregí a mitad de la validación

Mi primer script reportó «línea más larga: 1025 caracteres», lo que sugería que
el recorte no se aplicaba. Era un **artefacto de mi propia medición**: contaba
como “líneas de sección” todas las que empiezan por `[`, y las entradas de
**monitoreo** (`[cpu: 1.jpg]: …`) también empiezan así y **no** se recortan —
correctamente, porque el monitoreo queda fuera del alcance de F5.2.

Verificado directamente sobre el helper, ninguna sección pasa de 443 caracteres.
Lo dejo escrito porque el número equivocado llegó a aparecer en mi salida.

---

## 6. Archivo tocado

| Archivo | Qué | Backup |
|---|---|---|
| `backend/app/api/v1/endpoints/integrated_report.py` | helper `_section_analyses_for_prompt` + mapa de etiquetas + entrada en el prompt | `.bak_f52_20260817_202843` |

`py_compile` limpio · backend reiniciado **sin build**. No se tocaron los 12
pasos del pipeline ni los prompts de las secciones individuales.

**Pendiente tuyo:** generar un consolidado real tras corregir a mano el
«Análisis de Errores» de una ejecución, y confirmar que las conclusiones
consolidadas ya no contradicen tu corrección.

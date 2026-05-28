# Sprint 2.7 — Mejora del SYSTEM_PROMPT IA (deuda del HF1)

**Fecha:** 2026-05-26
**Estado:** ✅ Completado — JMX generado por la IA ahora cumple las 3 reglas y se parsea sin huérfanas

## Objetivo

Eliminar la deuda técnica detectada en el Sprint 2.4-HF1: la IA generaba JMX malformado (body fuera del sampler) y variables huérfanas sin definir en UDV/CSV. El HF1 parcheó el parser para tolerar el patrón malformado; este sprint va al origen y arregla el SYSTEM_PROMPT para que NO genere ese patrón.

## Cambios

### Backend

| Archivo | Diff |
|---|---|
| `backend/app/api/v1/endpoints/script_ai.py` | 1164 → 1287 (+123 líneas, todas en `SYSTEM_PROMPT`) |

`SYSTEM_PROMPT`: 1900 chars → **9135 chars** (~5x más detallado).

Backup: `script_ai.py.bak_sprint27_20260526_184025`.

## Tres secciones nuevas añadidas al SYSTEM_PROMPT

### 1. REGLA DE ORO #1 — Body de peticiones POST/PUT

Resuelve el bug del HF1. Instrucción explícita con ejemplo XML correcto vs prohibido:

- **CORRECTO**: el body raw va DENTRO del `<HTTPSamplerProxy>` (con `postBodyRaw=true` dentro del mismo sampler).
- **PROHIBIDO**: NUNCA poner `<stringProp name="HTTPSampler.postBodyRaw">` ni `<elementProp name="HTTPsampler.Arguments">` sueltos en el hashTree post-sampler.

Aclara qué SÍ va en el hashTree post-sampler (HeaderManager, ResponseAssertion, Extractors, Timers — no props del sampler).

### 2. REGLA DE ORO #2 — Variables definidas

Resuelve el bug original (variables huérfanas). Tres lugares válidos para definir variables:

- `<Arguments testname="User Defined Variables">` **SEPARADO** como elemento HERMANO del TestPlan (NO inline). Incluye ejemplo XML completo.
- `<CSVDataSet>` con `variableNames`.
- Extractor (RegexExtractor / JSONPostProcessor) que genere la variable de una respuesta previa.

Lista ejemplos típicos: `${host}`, `${port}`, `${scheme}` → UDV; `${token}` → Extractor de Auth; `${bookingid}` → Extractor de Create; `${firstname}`, `${lastname}` → CSVDataSet.

**Refinamiento crítico (iteración 2):** el primer test reveló que la IA usaba el slot inline `TestPlan.user_defined_variables` (válido en JMeter pero NO detectado por nuestro parser, que solo lee el `<Arguments>` hermano). Añadí nota explícita: "el `TestPlan.user_defined_variables` inline DEBE quedar VACÍO. Las variables van SIEMPRE en el bloque `<Arguments>` hermano siguiente."

### 3. FUNCIONES JMETER HELPER

Catálogo de 17 funciones nativas que la IA ya conoce conceptualmente pero quizá no aplica:

- **Aleatorios:** `__Random`, `__RandomString`, `__UUID`.
- **Fechas:** `__time`, `__timeShift`, `__RandomDate`, `__dateTimeConvert`.
- **Contadores:** `__counter`, `__intSum`.
- **Hilos y entorno:** `__threadNum`, `__machineName`, `__machineIP`, `__P`.
- **Variables y URL:** `__V`, `__urlencode`.

Con instrucción explícita: "USA estas funciones en vez de poner valores fijos cuando aplica."

## Test manual de validación

### Prompt enviado

> "Test plan simple para POST https://api.example.com/booking con body JSON con campos firstname y lastname, headers Content-Type application/json, y ResponseAssertion verificando código 201. Carga: 10 usuarios, ramp-up 30s."

### Resultado del JMX generado (iteración final)

Parseado con `parse_jmx_to_structure`:

```
thread_groups: 1
  1. Crear Reserva (POST): mode=raw, raw='{"firstname":"John","lastname":"Doe"}', unsupp=[]

UDVs definidas: ['host', 'scheme']
metadata.referenced: ['host', 'scheme']
metadata.defined: ['host', 'scheme']
metadata.undefined: []
```

### Las 3 verificaciones críticas

| Verificación | Resultado |
|---|---|
| **Regla #1**: bodies sueltos en hashTree | **0** ✅ |
| **Regla #1**: body raw dentro del sampler con `mode=raw` y JSON real | ✅ |
| **Regla #1**: cero `unsupported` por artefactos del body | ✅ |
| **Regla #2**: `host` y `scheme` definidas en UDV `<Arguments>` hermano | ✅ |
| **Regla #2**: `metadata.undefined_variables` = `[]` | ✅ |
| **Regla #2**: parser nuestro detecta las UDVs (no usa el slot inline) | ✅ (tras iteración 2) |

### Iteraciones

- **Iteración 1**: el JMX cumplía Regla #1 pero la IA puso las UDVs en `TestPlan.user_defined_variables` inline → nuestro parser las reportaba como `undefined`. La IA cumplía la regla "definir variables" pero usando un patrón válido en JMeter que nuestro parser no lee.
- **Iteración 2**: añadí nota explícita en el prompt instruyendo a la IA a usar el bloque `<Arguments>` HERMANO (con ejemplo XML completo) y dejar el inline vacío. Re-test → ahora el parser detecta correctamente las UDVs.

## Relación con el HF1

- El **HF1** parchó el parser (`_rescue_malformed_body`) para tolerar JMX malformado de diseños viejos.
- El **2.7** va al origen y previene la generación del JMX malformado en nuevos diseños.

Ambos coexisten:
- Diseños **NUEVOS** (post-2.7) → JMX bien formado → el rescate del HF1 no se activa (función `_rescue_malformed_body` retorna None porque no hay artefactos sueltos).
- Diseños **VIEJOS** (pre-2.7) → JMX malformado → el rescate del HF1 los rescata, el editor funciona.

Los 2 tests del HF1 (`test_parser_rescata_body_raw_malformado_por_ia`, `test_parser_no_rescata_si_no_hay_artefactos`) siguen siendo válidos como regresión: el primero garantiza que el rescate funciona para diseños legacy; el segundo que no se activa con JMX bien formado (caso post-2.7).

## Backend test suite

42/42 PASS (29 parser + 13 regenerator). Sin regresión.

## Pendientes derivados

- **Validación visual de Fredy** del JMX generado con el nuevo prompt para confirmar que:
  - Se ve correctamente en el editor (body raw aparece, sin unsupported).
  - Las variables se muestran en la pestaña "Variables (UDV)".
  - El indicador "Variables sin definir" del Overview muestra `0`.
- **Sprint 2.4-HF2**: gestión de Data Files (CSVs).
- **Sprint 2.4-HF3**: límite HAR 5MB + Function Helper UI (las 17 funciones del catálogo).
- **Sprint 2.4-HF4**: integración Editor IA ↔ Chat (botón "Pedir a IA").

## Estado

**SPRINT 2.7 COMPLETO**. La IA ahora genera JMX que:
1. NO requiere el rescate del HF1 (body siempre dentro del sampler).
2. SIEMPRE define las variables que referencia (UDV hermano, CSV o Extractor).
3. Conoce las 17 funciones helper de JMeter y debe usarlas para datos dinámicos.

El editor visual de Fredy puede ahora abrir diseños nuevos sin advertencias de variables huérfanas ni elementos unsupported falsos.

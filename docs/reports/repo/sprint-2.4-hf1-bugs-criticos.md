# Sprint 2.4-HF1 — Bugs críticos del Editor IA

**Fecha:** 2026-05-26
**Estado:** ✅ tsc EXIT=0 + 42/42 backend PASS

## Diagnóstico (root cause común para Bug 2 y Bug 3)

El JMX generado por el SYSTEM_PROMPT de la IA tiene **estructura inválida** para los samplers POST/PUT con body:

```
<HTTPSamplerProxy testname="3. Crear Reserva">
  <elementProp name="HTTPsampler.Arguments">     ← vacío
    <collectionProp/>
  </elementProp>
  <boolProp name="HTTPSampler.postBodyRaw">false</boolProp>   ← dice "no body"
</HTTPSamplerProxy>
<hashTree>
  <HeaderManager>...</HeaderManager>
  <hashTree/>
  <stringProp name="HTTPSampler.postBodyRaw">true</stringProp>  ← suelto
  <hashTree/>
  <elementProp name="HTTPsampler.Arguments">                   ← suelto con body real
    <collectionProp>
      <elementProp name="body" elementType="HTTPArgument">
        <stringProp name="Argument.value">{ JSON real }
```

Confirmado en el design `0d0c7f38-c402-4dcb-b6df-09fd63559d62` (5 samplers, 3 con body — Autenticación PUT, Crear POST, Actualizar PUT).

**Por qué el parser fallaba:**
- Leía `postBodyRaw=false` del sampler → `body.mode=none` o `form` (si había args dummy).
- Los artefactos sueltos del hashTree caían como children `unsupported` con `kind='stringProp'` y `kind='elementProp'`.

**Decisión:** rescatar el patrón malformado en el parser para que el editor funcione SIN tener que regenerar todos los JMX desde la IA. El fix del SYSTEM_PROMPT queda como deuda separada.

## Bugs corregidos

### Bug 2 + Bug 3 — Rescate de body raw mal ubicado (backend)

**Archivos:**
- `backend/app/services/engine/jmx_to_structure.py`: 785 → 867 (+82).
- `backend/tests/test_jmx_parser.py`: +2 tests.

**Fix aplicado:**

1. Nueva función `_rescue_malformed_body(hash_tree)` que busca en los hijos directos del hashTree:
   - `<stringProp name="HTTPSampler.postBodyRaw">true</stringProp>` suelto, Y
   - `<elementProp name="HTTPsampler.Arguments">` suelto con `Argument.value` no vacío.

   Si encuentra ambos, devuelve un `SamplerBody(mode="raw", raw_text=...)` rescatado.

2. `_parse_http_sampler` invoca el rescate **siempre** (no solo cuando `body.mode == "none"`) porque la IA a veces puebla el sampler con `Argument.value=/auth` u otro placeholder que cae como `mode=form` con 1 arg falso. El rescate prevalece sobre eso.

3. `_parse_sampler_children` recibe nueva flag `skip_orphan_body: bool = False`. Cuando `True` (activada solo si el rescate fue exitoso), filtra los 2 artefactos sueltos para que no aparezcan como `unsupported`. Cuando `False` (caso por defecto, JMX bien formado), no cambia nada.

**Tests añadidos:**
- `test_parser_rescata_body_raw_malformado_por_ia`: positivo, con el patrón malformado completo. Verifica body.mode=raw, raw_text con contenido, y que los artefactos NO aparezcan como unsupported.
- `test_parser_no_rescata_si_no_hay_artefactos`: regresión negativa, JMX bien formado debe seguir funcionando.

**Validación con el JMX real de Fredy:**

| Sampler | Antes | Ahora |
|---|---|---|
| 1. Autenticación (PUT) | `mode=form`, `raw_text=None`, unsupp=[stringProp, elementProp] | `mode=raw`, `raw_text='{...username...}'`, unsupp=[] |
| 2. Obtener IDs (GET) | `mode=form`, unsupp=[] | `mode=form`, unsupp=[] (sin cambio — no tiene body) |
| 3. Crear Reserva (POST) | `mode=none`, `raw_text=None`, unsupp=[stringProp, elementProp] | `mode=raw`, `raw_text='{...firstname...}'`, unsupp=[] |
| 4. Actualizar Reserva (PUT) | `mode=form`, unsupp=[stringProp, elementProp] | `mode=raw`, `raw_text='{...firstname...}'`, unsupp=[] |
| 5. Consultar (GET) | `mode=form`, unsupp=[] | `mode=form`, unsupp=[] (sin cambio) |

### Bug 1 — Stepping labels narrativos estilo JMeter (frontend)

**Archivos:**
- `frontend/src/pages/AIScriptEditor.tsx`: `SteppingConfigSection` reescrito.

**Antes:** 9 `FormField` con labels técnicos en grid 2-col (`"Usuarios por paso (hint: Start users count)"`, etc.).

**Después:** 6 frases narrativas estilo UI JMeter, con inputs inline:
- "Este grupo va a iniciar **[num_threads]** threads (usuarios totales)."
- "Primero, esperar **[initial_delay]** segundos."
- "Después arrancar con **[start_users_count]** threads iniciales."
- "Luego, agregar **[start_users_count_burst]** threads cada **[start_users_period]** segundos, con ramp-up de **[ramp_up]** segundos."
- "Después mantener carga por **[flight_time]** segundos."
- "Finalmente, detener **[stop_users_count]** threads cada **[stop_users_period]** segundos."

Más un footer con las equivalencias literales del UI de JMeter en inglés. Tooltips en los 3 inputs del paso "Luego, agregar..." para aclarar qué hace cada uno.

Los 9 campos del schema `SteppingConfig` siguen exactamente los mismos — solo cambia la presentación. Cero impacto en parser, regenerador o backend.

### Bonus — Panel `UnsupportedChildView` (frontend)

Añadido componente que reemplaza el `default` ámbar genérico del switch en `SamplerChildEditPanel`. Para los casos legítimos restantes (otros JMX con elementos JMeter no soportados como JSR223PreProcessor, etc.), ahora muestra:

- Nombre del elemento, tipo (kind), motivo del no-soporte.
- Bloque `<pre>` con el `raw_xml` completo (read-only, scroll, fondo dark).
- Botón **"Copiar XML"** al portapapeles.
- Caja informativa azul aclarando que se preserva intacto en la exportación.

Mucho más útil que el placeholder previo. **No se activará en el JMX de Fredy** porque el rescate del HF1 elimina los falsos positivos — pero queda listo para JMX externos.

## Cambios — resumen

### Backend
- `backend/app/services/engine/jmx_to_structure.py`: 785 → **867** (+82).
- `backend/tests/test_jmx_parser.py`: +2 tests (~140 líneas).

### Frontend
- `frontend/src/pages/AIScriptEditor.tsx`: 3025 → **3088** (+63).
  - `SteppingConfigSection` reescrito (-94 / +110 ≈ +16 neto).
  - `UnsupportedChildView` añadido (~50 nuevas) + default del switch simplificado (-11).

Backups: `.bak_hf1_20260526_170352` para los 2 archivos.

## Tests

- **Backend: 42/42 PASS** (29 parser + 13 regenerator) en 1.19s.
  - Los 2 nuevos del HF1 (`test_parser_rescata_body_raw_malformado_por_ia`, `test_parser_no_rescata_si_no_hay_artefactos`) pasan.
  - Cero regresión: los 27 tests del parser preexistentes (incl. round-trip stepping, fixture real) siguen verdes.
- **Frontend: tsc EXIT=0** sin warnings.

## Pendientes derivados

- **Sprint 2.4-HF2:** gestión de Data Files (CSVs asociados al diseño).
- **Sprint 2.4-HF3:** límite HAR 5MB + Function Helper.
- **Sprint 2.4-HF4:** integración Editor IA ↔ Chat (botón "Pedir a IA").
- **Backlog crítico:** fix del SYSTEM_PROMPT IA para que NO genere el JMX malformado. El rescate del HF1 es un parche tolerante; lo correcto a largo plazo es que la IA produzca XML JMeter válido (body dentro del sampler). Cuando se haga el fix, los tests `test_parser_rescata_body_raw_malformado_por_ia` y `test_parser_no_rescata_si_no_hay_artefactos` siguen siendo válidos como regresión.

## Estado para HF2

**LISTO.** El Editor IA ahora maneja correctamente el JMX real de la AI Designer:
- Samplers POST/PUT muestran el body raw en el textarea con el JSON real.
- Los falsos `unsupported` desaparecen del árbol.
- Stepping Thread Group lee como en JMeter ("Este grupo va a iniciar… Primero esperar… Después arrancar con…").

Validación visual cuando Fredy esté disponible.

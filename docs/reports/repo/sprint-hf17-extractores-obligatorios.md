# HF17 — Extractores obligatorios + Jerarquía de prioridades

## Problemas detectados post-HF16 (evidencia con qa_pideky_com5.har)

### Problema 1: cero extractores generados
- El HAR de Pideky tiene POST Cognito con `AccessToken` en el response.
- Sprint 2.8 exigía extractor → el modelo lo IGNORÓ.
- Todos los samplers subsiguientes van sin `Authorization: Bearer`.
- Script INEJECUTABLE en producción real.

### Problema 2: UDV declarada pero no usada
- `BODY_SAMPLER_2` con 2062 chars de PASSWORD_VERIFIER.
- CERO referencias `${BODY_SAMPLER_2}` en samplers.
- El modelo generó el body pero olvidó crear el sampler que lo consume.

### Problema 3: cobertura al 33% (7 de 21 esperados)
- El modelo cortó el flujo temprano.
- Causa raíz: `SYSTEM_PROMPT_CONSERVATIVE` prioriza "economía de tokens" y el
  modelo lo interpreta como "menos cosas mejor", sacrificando extractores y cobertura.

## Fixes aplicados

### Fix 1: Jerarquía explícita P1-P5 en `SYSTEM_PROMPT_CONSERVATIVE`
Insertada al inicio (tras el CONTEXTO ESPECIAL, antes de las reglas de economía):
- **P1** bodies reales > **P2** extractores > **P3** cobertura > **P4** multi-dominio > **P5** economía.
- Instrucción explícita: si dos reglas compiten, elige P1-P4 sobre P5.
- Si el output va a truncarse, completar correctamente el primer 60% de samplers
  con TODOS sus extractores antes que enumerar todos superficialmente.

### Fix 2: Regla ABSOLUTA #2 sobre extractores (mismo estilo que HF16 con bodies)
Reemplaza el bloque débil `CORRELACION: ...` por una versión estricta:
- Lista de 6 patrones que EXIGEN extractor (Cognito AccessToken/IdToken, JWT, IDs en URLs).
- Ejemplo INCORRECTO (`Authorization: Bearer HARDCODED`) → REJECT.
- Ejemplo CORRECTO con XML completo de `JSONPostProcessor` (`referenceNames` +
  `jsonPathExprs`) y su consumo en `HeaderManager` (`Bearer ${AccessToken}`).
- Mínimo: ≥1 extractor si hay endpoint de auth; 1 por cada ID dinámico único.
- Prohibido: >3 samplers post-auth sin extractores.
- Trade-off explícito: preferir menos samplers CON extractores que más SIN correlación.

### Fix 3: CHECKPOINT pre-emisión anti-incoherencia (6 checks)
Añadido antes del FORMATO DE RESPUESTA en el prompt conservador:
- Check 1: `BODY_SAMPLER_N` con `Argument.value` real (no vacío).
- Check 2: `BODY_SAMPLER_N` declarado y NO referenciado con `${BODY_SAMPLER_N}` → eliminar UDV huérfana.
- Check 3: ≥1 extractor por cada endpoint de auth.
- Check 4: headers Authorization posteriores usan `${AccessToken}` (o el nombre del extractor).
- Check 5: dominios distintos parametrizados en UDV.
- Check 6: JMX cierra con `</jmeterTestPlan>`.

### Fix 4: Refuerzo condensado en `SYSTEM_PROMPT` base
Bloque "REGLA ABSOLUTA (post HF17) — LOS EXTRACTORES SON OBLIGATORIOS" tras el
ejemplo de RegexExtractor: mismas reglas absolutas en versión condensada
(Cognito, JSONPostProcessor/RegexExtractor, mínimo de extractores, trade-off
menos-samplers-con-extractores), para consistencia entre ambos prompts.

## Cambios en archivos
- `backend/app/api/v1/endpoints/script_ai.py`:
  - `SYSTEM_PROMPT_CONSERVATIVE`: +jerarquía P1-P5, +regla absoluta #2 extractores, +checkpoint 6 puntos.
  - `SYSTEM_PROMPT` base: +refuerzo condensado de las mismas reglas.
- `backend/tests/test_prompt_hf17_extractores_jerarquia.py`: 10 tests nuevos.
- Backup: `script_ai.py.bak_hf17_20260707_183809`.

## Tests
- Baseline: 179 passed, 2 deselected (slow).
- Post-HF17: **189 passed, 2 deselected (+10 nuevos)**. Sin regresiones.
- Comando: `docker exec jmeter_backend sh -c 'cd //app && PYTHONPATH=//app python -m pytest tests/ -m "not slow" -q'`

## Métricas de prompts (reales, medidas contra el backup)
- `SYSTEM_PROMPT_CONSERVATIVE`: 4043 → 8415 chars (+4372).
- `SYSTEM_PROMPT` base: 16279 → 17274 chars (+995).
- Nota: el conservador creció más que la estimación inicial (~5K) porque incluye
  el ejemplo XML completo de `JSONPostProcessor` + `HeaderManager` y el checkpoint
  de 6 puntos. Coste ≈ +1K tokens de system prompt por request grande — despreciable
  frente al presupuesto de salida (8192) y al tamaño del HAR de entrada.
- Ocurrencias de `extractor|JSONPostProcessor|RegexExtractor` en el archivo: 56.
- `frontend` `tsc --noEmit`: EXIT=0 (sin cambios de frontend).

## Estado
HF17 aplicado. Listo para validación en vivo con `qa_pideky_com5.har`.

Meta post-HF17 (segundo intento con mismo HAR):
- Extractores generados: ≥1 (era 0).
- BODY_SAMPLER huérfano: 0 (era 1).
- Cobertura samplers: ≥50% (era 33%).
- Sin regresiones en bodies (HF16 debe seguir OK).

## Fuera de alcance (decisiones posteriores)
- Escalar a gpt-4.1 (Camino C).
- Comparador automatizado con ground truth.
- Grafana provisioning.

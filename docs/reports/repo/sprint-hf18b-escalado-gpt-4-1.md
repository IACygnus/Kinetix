# HF18b — Escalado a gpt-4.1 (32K output)

## Contexto

Post HF16 + HF17 + HF18a, el prompt del Diseñador IA está robusto pero llegó al
techo práctico de gpt-4o. Con 16K de output, HARs enterprise como Pideky
(21 samplers esperados) solo se cubren al 20-33%. gpt-4.1 tiene 32K de output →
duplica el espacio disponible sin más cambios de prompt.

## Diagnóstico (hallazgos relevantes)

1. **`OPENAI_MAX_TOKENS` ya tenía `gpt-4.1: 32768`.** El dict vive en
   `backend/app/services/ai/gemini.py` (líneas 40-53), **no** en `script_ai.py`.
   No hubo que agregar nada al código: el registro ya estaba presente y correcto.
   (`gpt-4.1-mini`=16384 y `gpt-4.1-nano`=8192 se dejaron como estaban — fuera
   del alcance de este cambio, que solo escala el modelo activo a `gpt-4.1`.)

2. **La app está diseñada para UNA sola fila de `ai_config`.**
   - `load_ai_config_from_db()` (gemini.py) y `_get_or_create_config()`
     (ai_config.py) usan `select(AIConfig).limit(1)` **sin `WHERE is_active` ni
     `ORDER BY`**. Toman una fila arbitraria y luego evalúan `is_active` sobre
     *esa* fila; si la fila obtenida estuviera inactiva, `load_ai_config_from_db`
     retorna `{}` y la IA deja de funcionar.
   - El docstring de `_get_or_create_config` lo dice explícito: "la fila **unica**
     de configuracion de IA". El POST `/ai-config` actualiza esa fila en sitio.

## DESVIACIÓN respecto al prompt (y por qué)

El prompt proponía, en el Caso B (no existía fila para gpt-4.1), **insertar una
segunda fila** clonando gpt-4o. Con el diseño de fila única eso **rompería la
app**: `limit(1)` sobre dos filas es no determinista y podría cargar el modelo
equivocado (o una fila inactiva → IA caída). Esta es justo la situación que el
prompt pidió "REPORTAR antes de forzar".

**Solución segura equivalente aplicada:** `UPDATE` en sitio del `model_name` de
la fila única, `gpt-4o → gpt-4.1`, preservando `is_active=true`, la API key
encriptada y los límites. Cumple el 100% del objetivo y sigue siendo
**totalmente reversible** con el mismo SQL de rollback que el prompt documentó.

```sql
-- Cambio aplicado
UPDATE ai_config SET model_name = 'gpt-4.1', updated_at = NOW()
 WHERE model_name = 'gpt-4o' AND provider = 'openai' AND is_active = true;
```

## Rollback disponible (1 SQL)

```sql
UPDATE ai_config SET model_name = 'gpt-4o', updated_at = NOW()
 WHERE model_name = 'gpt-4.1' AND provider = 'openai';
```

Backup completo de la tabla (incluye la key encriptada) en:
`scratchpad/ai_config_backup_20260707_200456.sql` — restaurable con `psql`.

## Sobre el "log de modelo activo al arranque" (objetivo #4)

No se agregó un hook de startup. **La config se resuelve por-request**
(`load_ai_config_from_db(db)` se llama dentro del endpoint en cada generación),
no se fija al arrancar — un log de "modelo activo al startup" sería engañoso.
La confirmación real ya existe en el log por-request:

```
AI Script Designer: OpenAI call model=gpt-4.1 max_tokens=32768 finish_reason=stop
```

Por lo mismo, **no hizo falta reiniciar el backend**: el UPDATE en DB toma
efecto en la siguiente request.

## Validaciones

- **DB post-cambio:** una fila, `provider=openai`, `model_name=gpt-4.1`,
  `is_active=true`.
- **Curl `/generate` (prompt mínimo, 2 samplers GET):** HTTP 200,
  `is_valid=True`, JMX abre `<?xml` y cierra `</jmeterTestPlan>`, 2 samplers,
  sin error.
- **Log confirma:** `model=gpt-4.1 max_tokens=32768`.
- **Tests:** `196 → 199 PASS` (+3 en `test_openai_max_tokens.py`), 2 slow
  deselected, 0 fallos.

## Costo esperado

gpt-4.1 tiene precio superior a gpt-4o. Con el uso interno actual (POC +
validación clientes) el diferencial debería ser marginal. Monitorear tras
1 semana de uso.

## Estado

HF18b aplicado. Listo para **VALIDACIÓN FINAL** con `qa_pideky_com5.har`.

Meta cobertura:
- Post HF17 + gpt-4o: 4-7 samplers (20-33%)
- Post HF18a + gpt-4.1: esperado ≥12 samplers (60%+)
- Ground truth Pideky_Final.jmx: 21 samplers (100%)

## Archivos / cambios

- **Código:** ninguno (el dict ya tenía `gpt-4.1: 32768`).
- **DB:** `ai_config` fila única → `model_name=gpt-4.1` (UPDATE en sitio).
- **Tests:** `backend/tests/test_openai_max_tokens.py` (nuevo, 3 tests).
- **Backups:** `gemini.py.bak_hf18b_20260707_200456` (sin cambios, por norma) +
  `ai_config_backup_20260707_200456.sql`.

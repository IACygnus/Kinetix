# DPERF-1 — Fixes B / C / D: sleeps del pipeline, precarga del SDK y eco SQL

**Fecha:** 2026-08-13
**Branch:** `backup-trabajo-local`
**Diagnóstico origen:** `docs/reporte_bug/diagnostico-dperf-analisis-lento.md`
**Alcance:** 3 archivos, 13 inserciones / 17 borrados. **Fix A (paralelización) NO implementado.**

---

## 1. Resumen

| Fix | Qué se hizo | Estado |
|---|---|---|
| **B** | Eliminados los 12 `time.sleep(1)` del pipeline IA + el `import time` que quedó huérfano | ✅ Verificado |
| **C** | `from openai import OpenAI` movido al nivel de módulo en `gemini.py` (guardado con `try/except ImportError`) | ✅ Verificado |
| **D** | `DEBUG` default `True` → `False` en `config.py` (apaga `echo` de SQLAlchemy) | ✅ Verificado |

Backups: `*.bak_dperf1_20260813_191555` (los tres archivos).
`py_compile` OK en los tres. Restart del backend sin build. Contenedor `healthy`.

---

## 2. FIX B — Eliminación de los sleeps

### Discrepancia con el diagnóstico
El diagnóstico hablaba de **13 sleeps**; en el código había **12**. Las 12 líneas
coinciden exactamente con las reportadas: 158, 181, 202, 221, 235, 249, 262, 279,
295, 307, 325, 352. La número 13 del diagnóstico no existe en el archivo actual.

### Verificación de que ninguno tenía otra función
Se revisaron los 12 uno por uno. **Los 12 tienen la misma forma**: van inmediatamente
después de una llamada IA y su bloque `if ... is None: fallback`, en el nivel de
indentación del pipeline:

```python
ai_analysis_errors = gemini.analyze_errors(...)
if ai_analysis_errors is None:
    ai_analysis_errors = fallback.analyze_errors(...)
time.sleep(1)          # <-- espaciado anti-429, nada más
```

Ninguno espera un recurso, un archivo, un lock ni un job asíncrono. **Cero casos
dudosos, cero sleeps conservados** en este archivo.

El único sleep que quedó en el sistema es el backoff de reintentos, **intencionalmente
intacto**:

```
backend/app/services/ai/gemini.py:755:    time.sleep(wait_time)
```

Ese sí protege contra 429 reales y sólo se ejecuta cuando una llamada falla.

### Efecto colateral limpiado
Tras quitar los 12 sleeps, `time` ya no se usaba en `analysis_pipeline.py`
(la única otra referencia, línea 520, es `_datetime.utcnow()`, otro módulo).
Se eliminó `import time` de la línea 20.

### Evidencia
```
$ docker exec jmeter_backend grep -c "time.sleep" app/services/ai/analysis_pipeline.py
0
```
Diff: **13 borrados, 0 inserciones.**

---

## 3. FIX C — Precarga del SDK de OpenAI

### Opción elegida y por qué
**Import a nivel de módulo en `gemini.py`**, no un import tibio en `main.py`.

Justificación en una línea: `gemini.py` ya se importa en el arranque por la cadena
`api.py → upload.py → analysis_pipeline.py → gemini.py`, así que el import se paga
al arrancar el contenedor sin tocar `main.py` — es la opción menos invasiva.

Se protegió con `try/except ImportError` (el provider puede ser sólo Gemini) y el
constructor ahora falla con un mensaje claro en vez de un `ImportError` crudo:

```python
try:
    from openai import OpenAI
except ImportError:
    OpenAI = None
...
elif self.provider == "openai":
    if OpenAI is None:
        raise ValueError("SDK de OpenAI no disponible: falta el paquete 'openai'")
    self._openai_client = OpenAI(api_key=self._api_key)
```

### Evidencia — costo medido del import en frío
```
$ docker exec jmeter_backend python -c "import time; t=time.perf_counter(); from openai import OpenAI; print(time.perf_counter()-t)"
from openai import OpenAI -> 1.049s

$ docker exec jmeter_backend python -c "import sys; import app.services.ai.gemini as g; ..."
import app.services.ai.gemini            -> 1.578s
openai en sys.modules tras importar gemini: True
OpenAI resuelto a nivel de modulo:        <class 'openai.OpenAI'>
```

**~1.05 s** que antes pagaba el primer usuario que lanzaba un análisis; ahora los
paga el contenedor al arrancar. El constructor de `AIAnalyzer` ya no contiene ningún
import.

---

## 4. FIX D — Apagado del eco SQL

### Hallazgo que obligó a parar y consultar (regla del prompt)
`grep settings.DEBUG` sobre `backend/` devolvió **dos** consumidores, no uno:

| Ubicación | Uso | Impacto |
|---|---|---|
| `db/session.py:10` | `echo=settings.DEBUG` | El objetivo del fix |
| `main.py:316` | `reload=settings.DEBUG` | **Código muerto bajo Docker** |

`main.py:316` vive dentro de `if __name__ == "__main__":`. Ningún contenedor ejecuta
esa rama: `docker-compose.yml:61` lanza `uvicorn app.main:app ... --reload` por CLI,
y el compose de producción lo lanza con `--workers 2` sin reload. **El hot reload de
dev lo gobierna la línea 61 del compose, no `settings.DEBUG`.**

**Aprobado por Fredy vía CTO: Opción 1** (cambiar el default, sin desacoplar `SQL_ECHO`).

> ⚠️ **Caveat documentado:** quien ejecute `python app/main.py` **directamente, fuera
> de Docker**, perdería el hot reload (tendría que exportar `DEBUG=true`). Es un caso
> que el equipo no usa — todo corre en contenedor.

### Segundo hallazgo: `.env` tiene `DEBUG=true` y es inerte
`.env:6` contiene `DEBUG=true`, lo que a primera vista anularía el fix. **No lo hace**,
y se verificó por cuatro vías:

1. El servicio `backend` no declara `env_file:` en ninguno de los dos compose.
2. `DEBUG` no aparece en la lista `environment:` del backend.
3. Ninguno de los dos compose referencia `${DEBUG}` (`grep -c DEBUG` → 0 y 0).
4. Sólo se monta `./backend:/app`, y **no existe `backend/.env`** — el `.env` raíz
   nunca entra al contenedor.

Confirmado en runtime: `DEBUG en env del contenedor: <no definida>`.

### Evidencia — estado real del engine tras el restart
```
settings.DEBUG      = False
engine.echo         = False
DEBUG en env del contenedor: <no definida>
```

### Evidencia — desaparición del eco en los logs

| Ventana | Líneas `sqlalchemy.engine` |
|---|---|
| Buffer de log previo (código viejo) | **5.848** |
| Hoy, 00:17:03 → 00:24:37 (idle, antes del restart) | **117** |
| Hoy, después del restart (00:34:00 en adelante) | **0** |

El arranque nuevo ejecuta `create_all` + ~20 `ALTER TABLE` de migración + seed de
admin y **no emite una sola línea de eco**:

```
INFO:app.main:Tablas de base de datos verificadas/creadas
INFO:app.main:Migration OK: ALTER TABLE users ADD COLUMN IF NOT EXISTS username VARCHAR(50)
... (20+ migraciones, cero SQL crudo)
INFO:app.main:Aplicacion lista
INFO:     Application startup complete.
```

> **Nota metodológica:** `docker logs` sin `--tail` devuelve un segmento rotado y
> obsoleto en este contenedor (termina el 2026-06-26), y `--since` hereda el mismo
> problema. Las cifras de arriba se tomaron con `docker logs --timestamps --tail N`
> y se filtraron por marca de tiempo real, no por posición en el stream.

---

## 5. Predicción verificable

Del diagnóstico D-PERF, el análisis medido tardó **3 m 17 s**. Lo que estos tres
fixes eliminan del camino crítico:

| Concepto | Ahorro |
|---|---|
| 12 × `time.sleep(1)` | **12 s** |
| Import en frío del SDK de OpenAI | **~1 s** |
| Eco SQL (I/O de logging durante todo el pipeline) | variable, no acotado aquí |

**Predicción: de ~3 m 17 s a ~2 m 05 s.**

Nota honesta sobre esa cifra: 12 s + 1 s = **13 s** de ahorro duro y medible. Los
**~59 s** restantes hasta los 2 m 05 s se atribuyen al eco SQL y al arranque en frío
general que el diagnóstico imputaba. Ese tramo es una estimación, no una medición.
Si el tiempo real cae en la banda **2 m 05 s – 3 m 04 s**, los fixes funcionaron; lo
que discrimina es dónde exactamente.

**No se ejecutó un análisis completo** para no consumir cuota — la medición real la
hace Fredy.

---

## 6. Instrucción para Fredy (medición)

1. **NO reinicies el backend antes** de la prueba. El contenedor ya quedó reiniciado
   con el código nuevo y en caliente; reiniciarlo volvería a meter el arranque en frío
   en la medición.
2. Sube un JTL similar al del diagnóstico (**~25 K muestras**).
3. Cronometra desde que pulsas **"Generar Reporte"** hasta que el dashboard es visible.
4. Reporta el tiempo.

Con ese dato decidimos si el **Fix A** (paralelización de las 12 llamadas, estimado
~1 m 15 s) vale su riesgo:

- Si sale **~2 m 05 s** → la predicción se cumple; Fix A pasa a ser la única palanca
  grande que queda y se evalúa con números en mano.
- Si sale **~3 m** → el cuello de botella no era el que creíamos y hay que volver a
  medir antes de tocar el orquestador.

---

## 7. Archivos tocados

```
backend/app/core/config.py                   |  4 +-   (fix D)
backend/app/services/ai/analysis_pipeline.py | 13 ---   (fix B)
backend/app/services/ai/gemini.py            | 11 ++-   (fix C)
```

Backups: `*.bak_dperf1_20260813_191555`.
`session.py` **no se tocó**, como pedía el prompt.
El orquestador de secciones **no se tocó** más allá de quitar los sleeps.

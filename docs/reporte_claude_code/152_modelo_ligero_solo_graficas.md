Commit base `63873f0` · 2 de octubre de 2026 · Reporte 152 — el modelo ligero, solo en los textos de gráficas

# El modelo ligero, solo en las gráficas

Tarea única, a partir del reporte 151 §4. La aplicación siguió cerrada para el frontend: **no se tocó
ni un archivo de pantalla ni ninguno protegido.** No se reinició ni se reconstruyó ningún contenedor,
y no se guardó nada en Configuración de IA.

## 1. Diagnóstico (antes de cambiar nada)

| Pieza | Dónde | Qué hacía |
|---|---|---|
| `es_ligera(seccion)` | `services/ai/reparto.py` | `True` para `analista_chat`, `chart_*` y `txreport_chart_*` |
| La llama | `reparto.modelo_para()` ← `GeminiAnalyzer._generate` (`gemini.py:1196`) | Elige el modelo de cada llamada |
| `AI_MODELO_LIGERO` se lee | `reparto.modelo_ligero_del_entorno()` ← `GeminiAnalyzer.__init__` (`gemini.py:1122`) y `get_gemini_analyzer` (`gemini.py:1936`, entra en la clave del singleton) | Vacía → `None` → el modelo principal en todo |
| La regla de las rampas en las gráficas | `fases.NOTA_RAMPAS` ← gráficas generales (`gemini.py:1727`, todas menos Active Threads) y de transacción (`transaction_report.py:237`) | Un solo sitio para las dos |

**Alcance:** el cambio de código cabe en 2 archivos (`reparto.py` y `fases.py`) y 22 líneas. La
activación añade `docker-compose.yml` y `.env`, como pide el punto 3. `gemini.py` no hizo falta: la
decisión se toma entera en `reparto.py`.

## 2. El cambio

- **`reparto.py`**: la decisión se separa en `es_grafica()` y `es_chat()`. `es_ligera()` devuelve
  ahora solo `es_grafica()`. **`AI_MODELO_LIGERO` se aplica únicamente a las gráficas**, generales y
  por transacción. **El chat del Analista IA usa siempre el modelo de la configuración.**
- **Con la variable vacía, todo sigue igual que hoy**: `modelo_para()` devuelve el principal. Lo
  comprueba `b5_h_reparto.py` §3.
- **`fases.py` — `NOTA_RAMPAS`**, que cierra cada prompt de gráfica, añade: «No escribas las palabras
  rampa, escalon ni meseta, ni comentes la subida o la bajada de usuarios: si hace falta situar algo,
  di «al arranque» o «al cierre de la prueba»». Va igual a gpt-5.5 y al mini.
- **Excepción a la vista:** Active Threads **no lleva** `NOTA_RAMPAS`, y es a propósito desde el
  bloque 2.5 (`gemini.py:1727`), porque esa gráfica describe el perfil de carga. En esta medición
  tampoco citó rampas.

## 3. La activación

| Archivo | Cambio |
|---|---|
| `.env` (desarrollo, **no versionado**) | `AI_MODELO_LIGERO=gpt-5.4-mini`, con su comentario. Finales de línea CRLF, como el resto del archivo. No se mostró ninguna otra línea del `.env` |
| `docker-compose.yml` | `- AI_MODELO_LIGERO=${AI_MODELO_LIGERO:-}` en el bloque del backend. **Vacía por defecto**: en producción, sin la variable en su `.env`, no cambia nada |

`docker compose config` ya resuelve `AI_MODELO_LIGERO: gpt-5.4-mini`. **El contenedor en marcha
todavía no la tiene: la toma cuando Fredy reinicie el backend** (`docker compose up -d backend`, sin
`--build`).

## 4. La medición (IA real, sin escribir en la base)

Es el mismo informe del 151: JTL de Fredy, criterios de su sesión `ea4cdd73`, su archivo de errores
(copia temporal borrada al terminar) y los tres turnos de su chat. Se generó con
`corrida_modelo_ligero.py` (`B5_VERSION=c`), con `gpt-5.4-mini` en el entorno del proceso y el
`reparto.py` nuevo. Fueron 31 llamadas, sin un fallo.

| Llamadas | Modelo / esfuerzo | N.º | Entrada | Caché | Salida | Razonamiento | Segundos (suma) |
|---|---|---|---|---|---|---|---|
| Gráficas | **gpt-5.4-mini** / bajo | 21 | 128.513 | 95.744 | 5.764 | 1.561 | 39,2 |
| **Chat (3 turnos)** | **gpt-5.5** / bajo | 3 | 9.558 | 7.424 | 1.721 | 710 | 19,4 |
| Resumen, conclusiones y recomendaciones | gpt-5.5 / medio | 3 | 19.805 | 14.592 | 3.263 | 2.047 | 40,5 |
| Errores y resumen de cada transacción | gpt-5.5 | 4 | 27.639 | 21.504 | 3.534 | 2.671 | 47,0 |
| **Total** | | **31** | **185.515** | **139.264** | **14.282** | **6.989** | **146,1** |

**Duración del informe:** general 58,0 s + transacciones 70,1 s = **128,1 s**. Con todo en gpt-5.5
(151, versión a) eran 191,0 s.

**Coste**, por modelo, con la tarifa vigente de cada uno:
`(entrada − caché) × P_entrada + caché × P_caché + salida × P_salida`.

- gpt-5.5: entrada 57.002, caché 43.520, salida 8.518.
- gpt-5.4-mini: entrada 128.513, caché 95.744, salida 5.764.

**La caché sale favorecida**, igual que en el 151 (b): esta corrida va después de las del 151 y
gpt-5.5 encontró prefijos ya en caché.

| Comprobación | Resultado |
|---|---|
| Textos de gráficas que **citan rampas, escalones o mesetas** | **0 de 21** (151 con el mini: 4; con gpt-5.5: 2). Condición de parada (> 2): **no se cumple** |
| Gráficas en un solo párrafo | 21 de 21 · 5,1 cifras de media · 0 avisos del detector |
| **Los 3 turnos del chat, con gpt-5.5** | **Sí**: los 3 con `gpt-5.5` / bajo, según la telemetría de cada llamada |
| JSON del chat | 3 de 3 válido |
| El chat aplicó la corrección de Fredy (turno 2) | **Sí**: «el volumen se debe evaluar por servicio, no como total agregado», con los 64.000 separados por servicio. Era lo que el mini no hacía en el 151 |

## 5. Pruebas

- `b5_h_reparto.py` actualizada: con modelo ligero, las **11** gráficas (6 generales y 5 de
  transacción) van con el mini; el chat, con gpt-5.5; el resto, con el principal.
- `estructura_prompts.py`, `cierre_b5.sh` (A a J), `cierre_r1.sh` y `tsc`: **todo en verde**.
- `cierre_b5.sh` se corrió además con `AI_MODELO_LIGERO=gpt-5.4-mini` en el entorno, que es el
  estado del contenedor tras el reinicio: **todo pasa**.

## Archivos

| Archivo | Cambio |
|---|---|
| `backend/app/services/ai/reparto.py` | `es_grafica`, `es_chat`; el ligero, solo en las gráficas |
| `backend/app/services/ai/fases.py` | el refuerzo de `NOTA_RAMPAS` |
| `docker-compose.yml` | `AI_MODELO_LIGERO` declarada en el backend, vacía por defecto |
| `.env` | `AI_MODELO_LIGERO=gpt-5.4-mini` (no versionado) |
| `backend/pruebas_e2e/b5_h_reparto.py` | expectativas del 152 |

## Pendiente de Fredy

1. Reiniciar el backend para que tome la variable: `docker compose up -d backend`.
2. Generar un informe en pantalla y validar los textos de las gráficas.
3. Para volver atrás sin tocar código: dejar `AI_MODELO_LIGERO=` vacía en el `.env` y reiniciar.

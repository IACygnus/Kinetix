Commit base `5c9dfdf` · 30 de septiembre de 2026 · Control de R1.1 y tramos que mezclan fases

# Control de R1.1 y la cuenta de tramos que mezclan rampa y carga sostenida

Sin IA. Este reporte no copia textos de clientes.

---

## 1. R1.1 con un 8002 recién arrancado y sin `--reload`

**Deuda de partida** (PROJECT_STATUS, reportes 123 §8.4 y 124 §5): R1.1 se cortaba de forma
intermitente con `Server disconnected` al exportar el PDF; repetida sola, pasaba.

| | |
|---|---|
| Proceso anterior | `python3 -m uvicorn … --port 8002 --reload` (pid 67544), de larga vida, con su hijo de recarga. Parado |
| Proceso nuevo | el mismo comando **sin `--reload`**, contra `jmeter_analyzer_test`, sin claves de IA en el entorno (`GEMINI_API_KEY=` `OPENAI_API_KEY=`), log en `/tmp/backend_test_sinreload.log` |
| Código | HEAD `5c9dfdf` |
| Suite | `cierre_r1.sh` entera |

**Resultado: R1.1, R1.2, R1.3, R1.4, C2 integrado y C2 individual — TODO PASA.** `r2_series.py`
también pasa entera.

**Conclusión, hasta donde llega una corrida:** con el proceso recién arrancado y sin recarga el corte
no aparece. La causa más probable es el **proceso de larga vida con `--reload`**: cada guardado de un
`.py` reinicia el trabajador, y un reinicio a mitad de una exportación larga cierra la conexión. Una
corrida limpia no demuestra que el corte no pueda volver; lo hace improbable con esta causa.

**Deuda anotada:**

- `scripts/preparar_base_de_pruebas.sh` arranca el 8002 con `--reload` a propósito (O1.6: sin él, una
  suite nueva chocaba con endpoints «inexistentes»). Las dos cosas se contradicen: para correr suites
  largas conviene un 8002 sin recarga, arrancado **después** de guardar el código. Decidir si el
  script ofrece los dos modos.
- **El 8002 queda ahora sin `--reload`.** Si una suite necesita código nuevo del backend, hay que
  reiniciarlo.

---

## 2. Tramos que mezclan rampa y carga sostenida

`backend/pruebas_e2e/tramos_fases.py` (nuevo, sin IA, base en solo lectura): los 6 tramos iguales de
`resumen_serie.py` contra las fases de `services/ai/fases.py`.

| Ejecución | Fases | Tramos que mezclan |
|---|---|---|
| `35ca5b92` Nova (30:00) | subida 0:00–3:14 · sostenida hasta el final | **1 de 6**: 0:00–5:00 (3:14 de subida + 1:46 de carga) |
| `42334732` prueba 6 (5:01) | subida 0:00–2:19 · sostenida 2:19–4:24 · bajada 4:24–5:01 | **2 de 6**: 1:40–2:30 y 4:11–5:01. Además, **2 tramos son solo subida** |
| `1e592533` prueba avianca (3:00) | subida 0:00–0:27 · sostenida 0:27–2:59 · bajada de 1 s | **2 de 6**: 0:00–0:30 y 2:30–3:00 (este último, por un solo segundo de bajada) |
| **Total** | | **5 de 18** |

Desde 2.1c el modelo recibe las fases junto a los tramos, así que puede leer que un tramo cae en la
rampa. Los tramos siguen siendo ventanas fijas: pasar a tramos por fase queda como opción, no hecha.

---

## 3. Lo que ya está del bloque 2.1 (commits `96afe9a`…`5c9dfdf`)

| Paso | Qué |
|---|---|
| 2.1a | `services/ai/fases.py`: subida, carga sostenida y bajada por usuarios activos (95 % del máximo) |
| 2.1b | `fases.concentracion`: dónde se concentran los fallos dentro de la carga sostenida, en vez del primero y el último |
| 2.1c | Fases y concentración en las 8 secciones generales con serie o momentos |
| 2.1d | Las fases de la prueba entera en las 6 secciones por transacción |

Todo con `r2_series.py` en verde.

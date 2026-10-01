Commit base `cb3c6dd` · 1 de octubre de 2026 · Bloque 4, paso 4.0 — la pantalla «Nuevo Reporte», tal como es hoy (solo lectura)

# «Nuevo Reporte» hoy

**No se ha cambiado código del producto.** La única pieza nueva es la herramienta de capturas
(`backend/pruebas_e2e/capturas_nuevo_reporte.py`). La pantalla es `UploadJTL.tsx`, en la ruta
`/performance/new` (`App.tsx`, `NewReportWrapper`), para los roles admin y analyst.

---

## 1. Capturas

**Ruta: `C:\proyectos\Kinetix_pruebas\mockups\actual\`.** Tomadas en el 5173 con `localhost:8001`
resuelto al 8002 (base de pruebas), a 1.440 × 900 y a página completa.

| Archivo | Estado |
|---|---|
| `01_vacia_sin_ia_bloqueo.png` | La pantalla **real** del 8002, que no tiene IA: el botón «Generar Reporte» se sustituye por el panel rojo de F2 |
| `02_vacia.png` | Vacía, con la IA disponible (simulada: `/ai-config/estado` → `ok`) |
| `03_con_jtl.png` | Stress Test, cliente, proyecto y un JTL elegido: aparece el panel «Transacciones del JTL» |
| `04_con_criterios.png` | Criterios generales cambiados y los propios de una transacción desplegados |
| `05_analizando.png` | El bloqueo de pantalla «Procesando 1 archivo(s) JTL y generando análisis…» (la subida se retuvo unos segundos para poder fotografiarla) |
| `06_al_terminar_aviso_respaldo.png` | Al terminar **sin IA**: el aviso de F2 «10 de 10 secciones no las escribió la IA», con «Entendido, ver el informe». **Con IA no sale: la pantalla va directa al informe** |
| `07_informe_abierto.png` | El informe recién generado (`/performance/report/<id>`) |

**Huella:** una ejecución en la base de pruebas, proyecto **«ZZTEST-B4 captura»**. Un primer intento, que
no retuvo la subida, dejó **otra igual**. Las dos son ZZTEST (regla 29) y ninguna está en la base de Fredy.
Los tiempos medidos aquí **no sirven**: el 8002 no tiene IA. Los de verdad están en §2.

---

## 2. Lo que hace el analista hoy, en orden

| # | Campo o acción | Cómo es | A dónde va |
|---|---|---|---|
| 1 | **Tipo de prueba** | 6 tarjetas: Load, Stress, Endurance, Scalability, Spike, Smoke. Por defecto, Load | `test_type`. Llega a los prompts (TIPO DE PRUEBA, en el bloque de la ejecución) |
| 2 | **Cliente** | Desplegable con los clientes asignados al usuario. Opcional | `client_id`, `client`, y `description = "Cliente: <nombre>"`. **No llega a los prompts** |
| 3 | **Proyecto \*** | Texto libre, obligatorio | `name` y `project` de la ejecución. **No llega a los prompts** |
| 4 | **Archivos JTL (1-5)** | Zona de arrastrar y soltar **ya existente** (se resalta al pasar por encima), más el botón «Seleccionar Archivos». Admite `.jtl`, `.csv` (Locust) y `.xml` (WAPT) | Al elegir el primero, `POST /extract-jtl-transactions` lee el JTL y llena el panel de transacciones |
| 5 | **Criterios de aceptación** | Concurrencia (100), tiempo de respuesta en ms (2000) y disponibilidad en % (99.5) | `acceptance_criteria` (JSON). Llegan a los prompts |
| 6 | **Unidad de medida** | TPS o UVC | `metric_unit`. Llega a los prompts |
| 7 | **Transacciones del JTL** | Tabla con muestras, promedio, TPS y errores, y la marca **«crítica»** calculada al momento. Casillas «Marcar todas / Solo críticas / Ninguna» y, por fila, criterios propios desplegables | Las marcadas viajan como `critical_transactions` y son las que reciben **informe por transacción**; los criterios propios, como `per_transaction` |
| 8 | **Bloqueo por IA (F2)** | Al abrir la pantalla y otra vez, sin caché, al pulsar Generar: si `/ai-config/estado` falla, el botón se sustituye por el panel rojo. «No generar todavía · volver a comprobar» o, marcando la casilla, «Generar sin IA» | — |
| 9 | **Generar Reporte** | Activo con al menos un JTL y un proyecto. Con varios JTL, antes valida la compatibilidad (`/validate-jtl`) y, si hay advertencias, abre un modal | `POST /upload` |
| 10 | **Mientras genera** | Toda la pantalla, bloqueada con el aviso de «Procesando…» | — |
| 11 | **Al terminar** | Con IA: **directo a `/performance/report/<id>`**. Si alguna sección cayó al respaldo: primero el aviso de F2 | Informe |

**Capturas de infraestructura y evidencias: no están en esta pantalla.** Se suben después, desde el informe
(«Capturas de infraestructura» y «Evidencias» del menú de Análisis).

**Cuánto tarda (gpt-5.5, `medium`, medido en el 139 y el 140):**

- **El informe general bloquea la pantalla unos 2 a 2,5 minutos**: 10 llamadas, entre 124 y 144 s.
- **El informe de cada transacción marcada se genera después, en segundo plano**: 6 llamadas, unos 70 a
  95 s por transacción. Con 4 marcadas, entre 3,5 y 5 minutos más, con el informe ya abierto.
- El tope de la petición en el navegador es de 600 s (axios).

---

## 3. Dónde encajaría lo nuevo (sin diseñarlo)

### 3.1 «Cuéntanos cómo fue la prueba» (texto libre del analista)

- **Dónde en la pantalla:** después de los criterios y antes de «Generar Reporte», cuando el JTL ya está
  elegido. O junto a Proyecto, si se quiere pedir antes de leer los datos.
- **Cómo llegaría a los prompts:** dentro del **bloque de la ejecución** del 2.2
  (`contexto_prompt.bloque_ejecucion`), como «LO QUE CUENTA EL ANALISTA». Así le llega igual a las 16
  llamadas de un informe y a la conclusión única del integrado, y como va en el prefijo común, **se paga a
  precio de caché**.
- **Dos cosas que decidir antes:**
  - **El transporte.** `/upload` recibe todo por la *query string* (nombre, descripción, criterios). Un
    texto libre largo ahí choca con el límite de longitud de URL (nginx en producción). Tendría que ir en el
    cuerpo, como campo de formulario.
  - **Dónde se guarda.** Una columna nueva en `test_executions` necesita su `ALTER` (regla 10). Dentro de
    `acceptance_criteria_json` no hace falta, pero mezcla cosas. Reutilizar `description` (hoy «Cliente: X»)
    cambiaría su sentido.

### 3.2 Una conversación corta con la IA antes de generar

- **Dónde:** entre «Generar Reporte» y el bloqueo de «Procesando». Es el punto en que ya se hace la
  segunda comprobación de la IA (`uploadFiles` → `comprobarIA(true)`), así que la pregunta y el bloqueo
  por IA conviven en el mismo sitio.
- **Lo que falta en el backend:** hoy, antes de subir, solo existe `/extract-jtl-transactions`, que
  devuelve las métricas por transacción. Las fases, los hechos y la concentración de fallos se calculan
  **dentro de `/upload`**, después. Para preguntar antes habría que adelantar esos cálculos (ampliar ese
  endpoint o crear uno nuevo) o partir `/upload` en «leer» y «generar».
- **Las respuestas** se sumarían al texto de §3.1: un solo canal hacia los prompts.

### 3.3 Arrastrar el JTL

**Ya existe** (`handleDrag` / `handleDrop` sobre la zona punteada, que se resalta al arrastrar; ver
`02_vacia.png`). Lo que no hay: soltar en cualquier parte de la página, ni arrastrar capturas de
infraestructura aquí.

### 3.4 Qué datos del bloque de la ejecución ya permitirían preguntas útiles

| Dato que ya se calcula (2.1-2.5) | Pregunta que habilita (ejemplos) |
|---|---|
| **Fases** (subida, carga sostenida, bajada; «sin bajada») | «La prueba termina a plena carga, sin bajada: ¿se cortó o era lo previsto?» · «La subida duró 3 min de 30: ¿era el perfil planeado?» |
| **Tipo de prueba frente al perfil de hilos** | «Marcaste Stress, pero la carga se mantiene plana en 4 usuarios: ¿es una prueba de estrés?» |
| **Hechos: qué transacción concentra los fallos y cuánto** | «El 99 % de los fallos son de ConsultaX: ¿se sabe de algún problema conocido en ese servicio?» |
| **Concentración de fallos y de degradación** en ventanas de la carga sostenida | «Los fallos se agrupan entre los min 1:57 y 2:12: ¿pasó algo en el ambiente en ese momento (despliegue, otra carga, reinicio)?» |
| **Criterios frente a resultados** (veredicto por transacción) | «Disponibilidad pedida 99,5 % y obtenida 91,7 %: ¿los criterios son los acordados con el cliente?» |
| **Mensajes de error reales** (`responseMessage`/`failureMessage`) y códigos | «Todos los fallos son HTTP 500 con "Internal Server Error": ¿hay logs del servidor de esa hora?» |
| **Tabla por transacción** (orden, tiempos, caudal) | «¿En qué orden recorre el usuario estas transacciones?» (hoy la IA lo deduce del número del nombre) |
| **Unidad de medida (TPS/UVC)** y concurrencia | «¿La concurrencia esperada de 100 usuarios es la de producción?» |

**Lo que ningún dato trae** y por eso merece una pregunta: el ambiente (producción, QA, preproducción), la
versión desplegada, la infraestructura (réplicas, base de datos), el objetivo de la prueba, los incidentes
conocidos y qué cambió desde la prueba anterior.

---

## 4. Lo que no se comprobó

- **La pantalla con IA real.** El estado «con IA» se simuló en el navegador; con IA la pantalla va directa
  al informe, sin la captura 06.
- **El modal de varios JTL.** No se fotografió (solo sale con 2 o más archivos).
- **Los tiempos de §2** son de las corridas del 139 y el 140 (en proceso, la misma IA), no de esta pantalla.

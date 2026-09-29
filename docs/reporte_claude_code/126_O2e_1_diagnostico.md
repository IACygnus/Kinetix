Commit `22b027f` · 29 de septiembre de 2026

# O2e.1 — Diagnóstico: el punto de entrada HTTPS del agente

**Solo lectura.** No se tocó código, ni la base, ni InfluxDB, ni el servidor de Azure.

## 0. Qué falta, en una frase

El agente (O2b) mide cada segundo dentro del servidor, pero **solo puede enviar sus cifras si está en la misma red que Kinetix**. InfluxDB escucha solo en `127.0.0.1:8086` (O-D1), a propósito, y no se va a reabrir. Para un servidor de un cliente con Kinetix en nuestra infraestructura hace falta **un punto de entrada HTTPS en `kinetix.sqasa.co`** que reciba las escrituras y las pase a la base por dentro. Así lo promete sin comprometerse `docs/observabilidad/requisitos-con-agente.md` §6: saliente desde su servidor, 443, **ningún puerto entrante** en casa del cliente.

## 1. Lo que hay hoy (comprobado)

| Pieza | Estado |
|---|---|
| Agente (`lab/agente/agente.conf`) | Telegraf `outputs.influxdb_v2` con `urls`, `token`, `organization` y `bucket` **por entorno**. Mide cada **1 s** y envía cada **5 s**, en lotes de hasta 2.000 puntos. Etiqueta `cliente` fija por instalación y `host` del sistema |
| Token del agente | **Uno solo**, de solo escritura sobre el cubo `infra` (O-D15), creado por `scripts/lab_preparar.sh` con `influx auth create --write-bucket`. InfluxDB acota los tokens **por cubo, no por etiqueta**: con ese token, cualquiera puede escribir en `infra` **haciéndose pasar por otro cliente** |
| nginx de producción | Según `CLAUDE.md` §14, enruta `kinetix.sqasa.co` al frontend (5173) y al backend (8001). **No está en el repositorio**: se editó a mano en el servidor. TLS con Let's Encrypt, ya funcionando |
| Backend | No hay ninguna ruta de ingesta. El middleware CSRF (`main.py:84`) exige cookie + cabecera en todo `POST` salvo el login: una ruta de ingesta tendría que ir **exenta**, porque autentica con token y no con cookie |
| Pantalla de Servidores (O2c) | Da de alta el servidor en modo `agente` y genera la orden de instalación, con la URL y el token **del laboratorio** |

## 2. Las dos formas de hacerlo

| | **A. nginx directo a InfluxDB** | **B. Una ruta del backend que reenvía** |
|---|---|---|
| Qué es | Un `location` en el nginx del servidor que deja pasar **solo** `POST /api/v2/write` al `127.0.0.1:8086` | `POST /api/v1/ingesta/api/v2/write` en el backend. Telegraf añade él solo `/api/v2/write` a la URL, así que el agente apunta a `https://kinetix.sqasa.co/api/v1/ingesta` |
| Cambio en el servidor | **Sí**: editar a mano un nginx que no está versionado | **Ninguno**: `/api/` ya llega al backend. Se despliega como cualquier cambio de backend |
| ¿Un cliente puede escribir como otro? | **Sí**: el token es por cubo | **No**: cada token es de **un** cliente, y el backend rechaza las líneas cuya etiqueta `cliente` no es la suya |
| Revocar a un cliente | `influx auth delete` a mano, en el servidor | Un botón: el token se marca revocado en Kinetix |
| Última métrica por servidor | Hay que preguntarle a InfluxDB | Se sabe al recibirla |
| Límite de tamaño y de ritmo | Configurable en nginx | En el backend, con su mensaje |
| Coste | ~10 líneas de nginx | ~250-350 líneas nuevas: módulo, tabla, ruta y pruebas. **Ningún protegido** |
| Carga | Nula | ~12 peticiones por minuto y agente, de pocos KB. Despreciable |

**Recomiendo B.** El motivo principal no es la comodidad: con A, el token que se le da a un cliente le permite escribir métricas **con el nombre de otro cliente**, y eso no se arregla en nginx. B, además, no exige tocar a mano un servidor cuya configuración no está en el repositorio.

## 3. Las decisiones que hacen falta (propuestas)

| # | Decisión | Propuesta |
|---|---|---|
| O-D48 | Cómo entra la escritura | **B**: ruta del backend, sin cambios en nginx |
| O-D49 | Qué identifica al que escribe | **Un token de ingesta por cliente**, generado en Kinetix. Se guarda **su huella** (hash), no el token: se enseña **una sola vez** al crearlo. Revocable. InfluxDB sigue usando por dentro el token de escritura de O-D15, que **nunca sale** del servidor |
| O-D50 | Qué se acepta | Solo `POST`, solo el cubo `infra`. **Cada línea tiene que llevar `cliente=<el del token>`**; si una no la lleva, se rechaza **el lote entero con 400** y el motivo. Telegraf descarta los lotes con 4xx: se pierde ese lote, pero nada entra mal etiquetado |
| O-D51 | Límites | Cuerpo de hasta 1 MB, que es lo que nginx deja pasar por defecto. Un lote de 2.000 puntos ronda los 200-300 KB. Un ritmo de hasta 60 peticiones por minuto y token; por encima, 429, que Telegraf reintenta |
| O-D52 | Qué se prueba | En local, con el laboratorio de O2b. El agente del `lab_servidor` escribe por la ruta nueva **en HTTP dentro de la red de Docker**, porque el TLS de producción ya lo pone nginx y no cambia. Casos: token bueno, token revocado, token de otro cliente, etiqueta cambiada, cuerpo grande y ritmo excesivo |
| O-D53 | Quién activa producción | **Fredy.** Kinetix no despliega. El paso a producción es el despliegue normal del backend, y crear el primer token desde la pantalla |

## 4. Cómo lo dividiría

| Paso | Qué | Toca |
|---|---|---|
| **O2e.2** | Tabla `ingest_tokens` (`create_all`, sin SQL), módulo de validación de líneas, `POST /api/v1/ingesta/api/v2/write`, exención CSRF de esa única ruta y endpoints de alta y revocación (admin) | Backend. `main.py` en una línea (la exención) |
| **O2e.3** | El agente del laboratorio escribiendo por la ruta, con la suite de casos de O-D52 y la huella de `infra` antes y después (regla 35) | `lab/`, pruebas |
| **O2e.4** | Pantalla de Servidores: crear y revocar el token de un cliente, y la orden de instalación con la URL de producción | **Frontend** (regla 31: aviso antes) |
| **O2e.5** | `requisitos-con-agente.md` §6 pasa de «no existe» a cómo se usa; manual de pruebas; CLAUDE.md | Documentos |

**Ningún archivo protegido.** `services/engine/` no se toca: eso es O3.

## 5. Lo que O2e no resuelve

- **El instalador de Windows sigue sin probar** (O-D21). O2e cambia la URL, no el instalador.
- **El tablero de Grafana sigue filtrando por `corrida`** (reporte 105 §4.1).
- **Las alertas siguen sin existir.**
- **El nombre del servidor tiene que coincidir con `host`**, igual que hoy.

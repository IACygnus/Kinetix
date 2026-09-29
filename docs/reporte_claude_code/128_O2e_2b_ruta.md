Commit base `9bcd808` (sin commit propio todavía) · 29 de septiembre de 2026

# O2e.2b — La ruta de ingesta y la gestión de tokens

Segunda mitad de O2e.2. El agente ya tiene dónde escribir: `POST /api/v1/ingesta/api/v2/write`. No hay
pantalla, que es O2e.4, ni se ha escrito todavía en el InfluxDB real, que es O2e.3.

## 1. Qué hay

| Archivo | Líneas | Qué |
|---|---|---|
| `backend/app/api/v1/endpoints/ingesta.py` (nuevo) | 374 | La escritura, los tokens (lista, alta y revocación) y el token de escritura de `infra` (estado y carga) |
| `docs/sql/o2e_infra_write_token.sql` (nuevo) | 39 | `monitoring_config.influxdb_infra_write_token_encrypted`, idempotente |
| `backend/app/main.py` | +8 | El import del modelo y la exención CSRF |
| `backend/app/api/v1/api.py` | +6 | El router en `/ingesta` |
| `backend/pruebas_e2e/o2e2b_ingesta.py` (nuevo) | 338 | 58 comprobaciones contra el 8002 |

**Estimación superada otra vez.** `ingesta.py` iba a tener unas 170 líneas y tiene 374, más del doble. La
parte de la escritura es la mayor: cada rechazo lleva su constancia en el log y su mensaje para quien
mire el servidor del cliente, y cada error de InfluxDB tiene su caso con el motivo al lado. Ningún
archivo protegido.

## 2. Las rutas

| Verbo | Ruta | Quién | Qué |
|---|---|---|---|
| POST | `/ingesta/api/v2/write` | el agente, con `Authorization: Token kxi_…` | **La única ruta sin CSRF** |
| GET | `/ingesta/tokens?client_id=` | admin y analista | Id, prefijo, creación, último uso y revocación. **Sin el token** |
| POST | `/ingesta/tokens` | admin | El token sale **en esta respuesta y en ninguna otra**, con el aviso |
| POST | `/ingesta/tokens/{id}/revocar` | admin | No se borra: la fila es la constancia |
| GET/PUT | `/ingesta/token-escritura` | GET: admin y analista · PUT: admin | Si hay token de escritura de `infra`. **Nunca el token** |

Al agente se le da `https://kinetix.sqasa.co/api/v1/ingesta`. Telegraf le añade `/api/v2/write` él
solo.

La lista devuelve el **prefijo** (`kxi_` más 8 caracteres) además de las fechas. Sirve para distinguir
dos tokens del mismo cliente y no permite reconstruir ninguno. Fredy pidió que la lista enseñe solo las
fechas y el botón de revocar, así que **si el prefijo se ve en pantalla se decide en O2e.4**.

## 3. Qué contesta la escritura

| Caso | Código | Por qué ese |
|---|---|---|
| Aceptado | 204 | Lo que contesta InfluxDB |
| Sin token, token desconocido o revocado | 401 | Telegraf tira el lote |
| Más de 300 por minuto con ese token | **429 + `Retry-After`** | Telegraf espera y reintenta |
| Cubo distinto de `infra` | 400 | O-D50 |
| Una línea de otro cliente o sin cliente | **400 con el recuento** | Nada entra mal etiquetado |
| Más de 1 MB, comprimido o descomprimido | **413** | Telegraf parte el lote |
| gzip roto o texto que no es UTF-8 | 400 | |
| InfluxDB con 4xx (p. ej. 422 por conflicto de tipos) | ese 4xx, tal cual | Es un defecto del lote |
| InfluxDB con 5xx, sin respuesta, o rechazando **nuestro** token (401/403) | **503** | Telegraf guarda el lote y reintenta. Un fallo nuestro no debe hacer perder datos del cliente |
| Sin token de escritura de `infra` cargado | 503 | Ídem, mientras un admin lo carga |

**Se reenvía lo que se revisó, descomprimido.** El cubo y la organización los pone Kinetix: se ignora
el `org` que mande el agente.

## 4. HALLAZGO: la exención de CSRF dejaba pasar PUT y DELETE

**Es justo el fallo que Fredy pidió evitar, y la suite lo encontró.** La primera versión de `main.py`
comparaba la **ruta exacta pero no el método**. Un `PUT` o un `DELETE` a `/api/v1/ingesta/api/v2/write`
sin cookie y sin cabecera se saltaba el CSRF. Hoy respondía 405 porque no hay nada detrás, pero un
`PUT` que alguien añadiera ahí algún día habría quedado sin CSRF sin que nadie lo decidiera.

**Corrección:** la exención exige ahora `request.method == "POST"` **y** la ruta exacta.

Las **11 variantes** que la suite comprueba y que dan **403 «CSRF validation failed»** sin cookie y sin
cabecera:

| # | Método | Ruta (bajo `/api/v1`) |
|---|---|---|
| 1 | POST | `/ingesta/tokens` |
| 2 | POST | `/ingesta/tokens/{id}/revocar` |
| 3 | PUT | `/ingesta/token-escritura` |
| 4 | POST | `/ingesta/api/v2/write/` (barra final) |
| 5 | POST | `/ingesta/api/v2/writex` |
| 6 | POST | `/ingesta/api/v2/write/otra` |
| 7 | POST | `/ingesta/API/v2/write` (mayúsculas) |
| 8 | POST | `/ingesta/api/v2/query` |
| 9 | POST | `/ingesta/` |
| 10 | **PUT** | `/ingesta/api/v2/write` (la ruta exacta) — **daba 405, ahora 403** |
| 11 | **DELETE** | `/ingesta/api/v2/write` (la ruta exacta) — **daba 405, ahora 403** |

Y la contraprueba: `POST` a la ruta exacta sin cookie **no** da 403, sino 401 porque pide el token.

## 5. La constancia

Una línea por lote en el log del backend:

```
ingesta cliente='ZZTEST-Ingesta O2e' puntos=3 resultado=aceptado
ingesta cliente='ZZTEST-Ingesta O2e otro' puntos=3 resultado=rechazado_400 motivo='Lote rechazado entero: …'
```

También se registran las altas y revocaciones de tokens, con el prefijo y quién lo hizo. La suite
comprueba que **ninguno de los cuatro tokens de la corrida aparece en el log**: ni los de ingesta ni el
de `infra`.

## 6. Cómo se probó, y qué NO se tocó

- **Sin InfluxDB real.** La suite levanta en su propio proceso un InfluxDB falso en `127.0.0.1:8099`,
  apunta ahí el `monitoring_config` de la **base de pruebas** y al terminar lo restaura. La suite
  comprueba la restauración fila a fila. Así se ve qué se reenvía exactamente y se puede hacer fallar a
  InfluxDB a voluntad. En InfluxDB no se escribió ni se borró nada. La escritura real es de O2e.3.
- **El SQL está aplicado en las dos bases.** En `jmeter_analyzer_test`, para la suite. En tu base
  (`jmeter_analyzer_db`), a petición tuya, **con copia previa**
  `C:\proyectos\Kinetix_pruebas\backup_20260929_o2e2b.sql` (7 MB, 33 tablas; regla 32). Después se
  comprobó que la columna existe.
- **El token de escritura de `infra` está cargado en tu base.** Es el de `lab/lab.env`, cifrado con el
  Fernet del backend y escrito en la misma fila que elegiría `PUT /token-escritura`. No se usó el
  endpoint porque la sesión del 8001 había caducado y un login nuevo necesita tu contraseña. El token
  entró por la entrada estándar: no pasó por ninguna línea de órdenes ni salió en pantalla.
  **El 8001 ya no tiene motivo para contestar 503**, comprobado sin escribir ni un punto:
  - `_destino()` resuelve contra tu base y devuelve exactamente el token de `lab.env`;
  - una escritura **vacía** en `infra` con ese token devuelve **204**, y con un token inventado **401**.
    La diferencia prueba que InfluxDB acepta el token sin que entre ningún dato.

  El 204 de principio a fin, con un lote de verdad, se comprueba en O2e.3.
- **`ingest_tokens` ya existe en tu base, vacía (0 filas).** La creó `create_all` al recargar el 8001
  tras el import de `main.py`, como pasó con O2c.
- **Un hallazgo ajeno a la etapa, sin tocar:** en la base de pruebas hay un cliente `ZZTEST-R1` con
  `created_at` y `updated_at` a NULL. Eso hace que `GET /clients` del 8002 **falle entero con un 500**
  de validación. Por eso la suite busca sus clientes con SQL de lectura. No sé qué suite lo dejó así
  (regla 33).
- Los tokens de la prueba quedan **revocados**, no borrados (regla 28). Los clientes son `ZZTEST-`.

```
docker exec -e KX_API=http://localhost:8002/api/v1 -e KX_DB=jmeter_analyzer_test \
    -e KX_SESION=/tmp/e2e_sesion_test.json jmeter_backend \
    python3 /app/pruebas_e2e/o2e2b_ingesta.py
```

Resultado: **TODO BIEN, 58 de 58**, dos corridas seguidas. `o2e2a_ingesta.py` sigue en 50 de 50.

## 7. Pendiente

- **SQL `o2e_infra_write_token.sql`**: aplicado en pruebas y en desarrollo · **pendiente en
  producción**. Va al checklist de despliegue. Después hay que cargar el token de escritura de `infra`
  con `PUT /ingesta/token-escritura`.
- **O2e.3**: el agente del laboratorio escribiendo por la ruta en el InfluxDB real, con la huella de
  `infra` antes y después (regla 35). Necesita el SQL en la base contra la que se pruebe.
- **O2e.5**, en `requisitos-con-agente.md` v1.2: «un token cubre hasta unos 20 servidores; con más, se
  crea un segundo token para el mismo cliente», «300 por minuto y token, aproximado», y **443 saliente
  hacia kinetix.sqasa.co, y nada más**.

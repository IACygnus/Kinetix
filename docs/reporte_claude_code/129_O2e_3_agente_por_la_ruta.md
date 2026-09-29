Commit base `919b901` (sin commit propio todavía) · 29 de septiembre de 2026

# O2e.3 — El agente del laboratorio escribiendo por la ruta de ingesta

El agente de `lab_servidor` (Telegraf 1.29.5, O2b) dejó de escribir en InfluxDB y escribió en
`http://jmeter_backend:8002/api/v1/ingesta` (el backend de **pruebas**, regla 34) con un token de
ingesta del cliente `ZZTEST-Laboratorio O2e`. **Los seis casos de O-D52 pasan en una misma corrida.**
El agente volvió byte a byte a su estado original. En InfluxDB no se borró nada.

Contiene además el arreglo de `ZZTEST-R1` (§6) y dos hallazgos (§5).

## 1. Resultado

```
bash scripts/lab_ingesta_o2e3.sh        # ~13 min; copia de la salida en
                                        # C:\proyectos\Kinetix_pruebas\o2e3_corrida_20260929.log
```

| Caso | Qué se hizo | Resultado |
|---|---|---|
| **A. Token bueno** | 45 s con el agente escribiendo | **45 de 45** segundos en `infra`; 13 lotes aceptados de ~120 puntos; 0 errores en el agente |
| **B. Etiqueta cambiada** | Token bueno, `cliente='ZZTEST-Nombre cambiado'` | 0 puntos. El agente registra el 400 con el motivo: «119 de 119 lineas no son del cliente «ZZTEST-Laboratorio O2e» (119 lineas con cliente=«ZZTEST-Nombre cambiado»)» |
| **C. Token de otro cliente** | Token de `ZZTEST-Ingesta O2e otro`, etiqueta buena | 0 puntos. 400 a nombre del cliente del token |
| **D. Cuerpo grande** | Corte de red de 240 s con `metric_batch_size = 50000` | **413, Telegraf parte el lote y no se pierde nada** (§2) |
| **E. Ritmo excesivo** | Relleno de ~7 escrituras/s con el mismo token durante 150 s | 271 respuestas 429; el agente recibe algunas, reintenta y **no pierde nada: 152 de 152 segundos** (§3) |
| **F. Token revocado** | Se revoca con el agente en marcha | 0 puntos desde la revocación. El agente registra «401 Unauthorized: unauthorized: Este token se revoco el 2026-09-29 21:58 UTC» |

## 2. El caso que más interesaba a Fredy: Telegraf 1.29.5 SÍ parte el lote ante un 413

Es lo que el código de O2e.2a daba por hecho, ahora comprobado en dos corridas:

| | Corrida 2 | Corrida 3 |
|---|---|---|
| Corte de red | 21:34:40 → 21:38:43 | 21:48:50 → 21:52:53 |
| Lote acumulado al volver | **5.522 puntos** | **5.638 puntos** |
| Respuesta del backend | 413 | 413 |
| Log del agente | `request was too large (413)` y a continuación `Retrying write after splitting metric payload in half to reduce batch size` | lo mismo |
| Lo que llegó después | **2 lotes de 2.761**, los dos aceptados | **2 lotes de 2.819**, los dos aceptados |
| Segundos del corte en `infra` | **243 de 243** | **243 de 243** |
| Hueco mayor | 1 s | 1 s |

**En uso normal el 413 no se da.** Con el lote por defecto del agente (`metric_batch_size = 2000`),
un lote ronda los 600 KB sin comprimir: el agente produce unas 24 líneas y ~8 KB por segundo
(medido con `telegraf --test`). Telegraf no junta más de `metric_batch_size` líneas en un envío,
aunque tenga mucho acumulado tras un corte. Hubo que subirlo a 50.000 para provocar el 413. **El tope
de 1 MB no necesita subir.**

## 3. El ritmo: cómo se probó, y un cambio respecto al plan

El plan decía `flush_interval` de 100 ms. **No lo usé**, y lo digo: con lotes diminutos, un agente
limitado a 300 envíos por minuto nunca podría vaciar lo que acumula. Perdería datos por su propia
configuración, no por la ruta, y la prueba no habría dicho nada útil.

En su lugar se reprodujo el caso real: **muchos servidores con el mismo token.** Un relleno escribe
unas 7 veces por segundo (unas 420 por minuto) con el mismo token mientras el agente sigue con su
configuración normal. Resultados:

- El backend contestó 429 **271 veces** (casi todas al relleno) y dejó constancia de cada una.
- El agente recibió el 429 unas pocas veces (2 en la corrida 3 y 5 en la 2) y escribió
  `will retry in 10s` y `will retry in 11s`.
- **152 de 152 segundos en `infra`**, con un hueco mayor de 1 s.

**Observado, no explicado:** el backend manda un `Retry-After` de 1 a 60 s según la ventana, y Telegraf
esperó 10-11 s en todos los casos. No he mirado el código de Telegraf para saber cómo lo decide, así
que no afirmo el mecanismo (regla 33). Lo que importa sí está medido: esperó, reintentó y no perdió nada.

Los datos del relleno quedan en `infra` como `zztest_o2e3_relleno`, con `host=zztest-relleno` y
`cliente=ZZTEST-Laboratorio O2e`.

## 4. El entorno del agente: original, modificado y restaurado

Lo pidió Fredy antes de restaurar. El token va tapado: su largo y el principio de su huella.

| Variable | **Original** | **Modificado** (casos A, D, E y F) |
|---|---|---|
| `KX_HOST` | `lab_servidor` | `lab_servidor` |
| `KX_CLIENTE` | `laboratorio` | `'ZZTEST-Laboratorio O2e'` (**entre comillas**, ver §5.1) |
| `KX_INFLUX_URL` | `http://influxdb:8086` | `http://jmeter_backend:8002/api/v1/ingesta` |
| `KX_INFLUX_ORG` | `performance` | `performance` |
| `KX_INFLUX_BUCKET` | `infra` | `infra` |
| `KX_INFLUX_TOKEN` | 88 caracteres, sha256 `5e193d78dff4…` (el de InfluxDB) | 47 caracteres, sha256 `3392598d0d73…` (un `kxi_…` de ingesta) |

En B y C solo cambiaron `KX_CLIENTE` y el token, respectivamente. Para D se usó una **copia** de
`agente.conf` con `metric_batch_size = 50000`: el `agente.conf` instalado no se tocó.

**Restaurado y comprobado por el guion:**
- el `entorno` es **byte a byte el original** (sha256 `7a20fb9c798a…`, igual antes y después);
- dueño y permisos, `root:kinetix_agente 640`, como estaban;
- en `/etc/kinetix-agente` no queda nada de la prueba: `LEEME.txt agente.conf conf.d entorno`;
- el agente queda **parado**, como estaba al empezar;
- `lab_servidor` sigue conectado a sus dos redes, `kinetix_jmeter_network` y `kinetix_lab`.

**La red de seguridad se probó sin querer.** El guion instala un `trap` que, si la corrida no termina,
reconecta la red, devuelve el `entorno` original y revoca los tokens. Dos corridas se interrumpieron
(§7), y en las dos dejó el agente en su estado original; lo comprobé a mano después.

## 5. Hallazgos

### 5.1 El instalador de O2b escribe `KX_CLIENTE` sin comillas

`lab/agente/instalar_agente.sh:131` escribe `KX_CLIENTE=$CLIENTE`. En un servidor **sin systemd**
el agente arranca con `. entorno`, y **un nombre de cliente con espacio deja `KX_CLIENTE` vacío**.
Comprobado con un fichero temporal:

```
sin comillas -> KX_CLIENTE=[]            sh: 2: …/entorno: O2e: not found
con comillas -> KX_CLIENTE=[ZZTEST-Laboratorio O2e]
```

Con systemd no pasa, porque `EnvironmentFile` toma el resto de la línea. Tras O2e las métricas no
entrarían mal etiquetadas: saldrían sin cliente y la ruta rechazaría el lote. Pero ese servidor no
enviaría nada. **No lo he tocado.** El arreglo es escribir el valor entre comillas simples, que
también entiende `EnvironmentFile`. Lo decides tú; `instalar_agente.ps1` tendría que revisarse
aparte.

### 5.2 La sesión de pruebas caduca a los 30 minutos

La corrida 2 se interrumpió en el caso F con «sesion de pruebas caducada». `o2e3_ayudante.py` renueva
ahora la sesión en cada llamada con `/auth/refresh`, que no gasta cupo de login. Para recuperarla hizo
falta **un** login contra el 8002 (base de pruebas) con la contraseña de desarrollo de CLAUDE.md §14.

## 6. `ZZTEST-R1`: arreglado

- **Qué suite fue:** `backend/pruebas_e2e/r1_datos.py:78` (Etapa R1, commit `41cf237`). Creaba el
  cliente con un `INSERT` sin `created_at` ni `updated_at`. El modelo `Client` pone esas fechas
  **en Python** (`default=datetime.utcnow`), no en la base, así que quedaban en NULL y `GET /clients`
  fallaba entero.
- **El arreglo, en tres pasos:**
  1. El `INSERT` pone `now()` en las dos fechas, con un comentario que explica por qué.
  2. La fila existente se corrigió con un `UPDATE … WHERE name = 'ZZTEST-R1' AND (created_at IS NULL OR
     updated_at IS NULL)` en `jmeter_analyzer_test`. No se borró nada (reglas 28-30). Quedan 0 clientes
     sin fechas.
  3. `o2e2b_ingesta.py` vuelve a usar `GET /clients` y comprueba que da 200: 59 de 59.
- **Comprobado:** `GET /clients` del 8002 contesta **200** (7 clientes). Al volver a correr
  `r1_datos.py`, el cliente sigue con fechas. El camino del alta se probó ejecutando **el texto real
  del `INSERT` sacado del archivo** en una transacción que luego se deshizo: deja las dos fechas, y
  tras el `ROLLBACK` no queda la fila de verificación.

## 7. Las tres corridas, sin esconder ninguna

| Corrida | Qué pasó |
|---|---|
| 1 | El conteo de puntos leía `_start` en vez de `_value` (`count()` conserva `_start` y `_stop`). Es un fallo **de la prueba**. La paré en el caso B |
| 2 | A-E bien. **F no se ejecutó**: caducó la sesión (§5.2) |
| 3 | **TODO BIEN**, los seis casos |

## 8. InfluxDB: qué quedó escrito (regla 35)

**No se borró nada**, por indicación de Fredy: `infra` tiene datos de O2a y O2b que no son de esta
prueba. Lo de O2e.3 queda marcado y la retención de 720 h se lo lleva.

| | Antes (foto tomada antes de la primera corrida) | Después |
|---|---|---|
| `cliente` | `laboratorio` | `laboratorio` · **`ZZTEST-Laboratorio O2e`** |
| `host` | `lab_db lab_docker lab_servidor servidor_systemd` | lo mismo · **`zztest-relleno`** |
| `modo` | `agente sin_agente` | `agente sin_agente` |
| Punto más antiguo de `cpu` | 2026-09-21 23:28:30 (`laboratorio`, `sin_agente`) | sin cambio |

La «foto antes» que imprime la corrida 3 ya incluye lo escrito por las corridas 1 y 2. La foto limpia
es la de esta tabla.

**Tokens de ingesta:** todos los de las tres corridas quedan **revocados** en la base de pruebas,
también los de las corridas interrumpidas (`o2e3_ayudante.py revocar-restos`). No se borran.

## 9. Archivos

| Archivo | Líneas | Qué |
|---|---|---|
| `scripts/lab_ingesta_o2e3.sh` (nuevo) | 328 | El recorrido. Desde el anfitrión, como los demás `lab_*.sh` |
| `backend/pruebas_e2e/o2e3_ayudante.py` (nuevo) | 97 | Token de `infra`, clientes, tokens y revocación en el 8002. Los tokens van por stdin/stdout |
| `backend/pruebas_e2e/r1_datos.py` | +5 −1 | §6 |
| `backend/pruebas_e2e/o2e2b_ingesta.py` | +6 −8 | Vuelve a `GET /clients` |

Ningún archivo protegido. No se tocó el frontend.

## 10. Pendiente

- **O2e.4** (frontend): esperar a que Fredy cierre la aplicación (regla 31). Allí se decide si el
  prefijo del token se ve en pantalla.
- **§5.1**: la decisión sobre las comillas del instalador.
- **O2e.5**, en `requisitos-con-agente.md` v1.2:
  - «un token cubre hasta unos 20 servidores; con más, se crea un segundo token para el mismo cliente»;
  - «300 por minuto y token, aproximado»;
  - **443 saliente hacia kinetix.sqasa.co, y nada más**;
  - lo medido aquí: tras un corte, el agente se pone al día solo y sin huecos.

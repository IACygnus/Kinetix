Pendiente de validación de Fredy · commit base `473f68f` · 30 de septiembre de 2026

# S2.2 — El listener de InfluxDB sale de un solo sitio (backend)

Sigue al diagnóstico del reporte 132. **La ruta de la IA ya no mete el token maestro en el `.jmx`.**

- Lleva `influxdbToken` con el token de escritura de `jmeter`.
- La URL va como `${__P(influxdbUrl,…)}`.
- `application` sigue la regla de Observabilidad, también como propiedad.

Se ha comprobado con una corrida real de JMeter: los puntos llegan al cubo `jmeter`.

**Queda abierta la ruta de la pantalla** (`AIScriptEditor.tsx:644`), que sigue metiendo el maestro. Es
S2.3, con la aplicación cerrada (regla 31), y aquí no se ha tocado.

---

## 1. Las decisiones de Fredy, y dónde vive cada una

Todo en **`backend/app/services/observabilidad/listener_influxdb.py`**, un módulo nuevo sin proteger
de 201 líneas.

| Decisión | Cómo queda |
|---|---|
| URL | `${__P(influxdbUrl,<la de /monitoring/jmeter-config>)}`. `url_de_escritura()` es ahora la **única** definición: `monitoring.py` la usa para `/jmeter-config` |
| Token | `influxdbToken`, el nombre que lee JMeter 5.6.3 (reporte 132 §2.2), con el token de escritura de `monitoring_config`. `TOKEN` desaparece |
| `application` | `${__P(application,<nombre_de_corrida(cliente, proyecto)>)}`. `testTitle` lleva lo mismo. «Kinetix Test» desaparece |
| Sin cliente | **No se niega nada.** `nombre_de_corrida` convierte en `sin-nombre` la parte que falta, y el proyecto que no llega se toma del nombre del Test Plan: `sin-nombre-<plan>-<aaaammdd-hhmm>` |
| Saneado | Los valores por defecto de `__P` pierden las comas, los paréntesis, los espacios, `{`, `}`, `$` y `\` (`sanear_para_p`) |
| Sin datos | **Nunca un listener sin token.** El token vacío o que no se descifra lanza `ListenerSinDatos` con un mensaje para el analista. El buzón vacío también, con otro mensaje que dice que el fallo es de Kinetix |
| `backend_listener_config` | Se **ignora**. Se retiró del prompt (`script_ai.py`); el campo del esquema se acepta para que una respuesta vieja del modelo no falle al validarse, y su descripción lo dice |

**El buzón.** El aplicador es síncrono y no ve la base. `refine-surgical` resuelve los datos con
`listener_influxdb.resolver()`, que es asíncrono, y los deja en `listener_influxdb.BUZON`, una
`ContextVar`. Es el mismo patrón que `gemini.BUZON_FALLO`. El aplicador solo pide el listener. El
buzón se llena **únicamente** si alguna operación es `add_listener backend_listener`, y se vacía en
un `finally`.

**`RefineSurgicalRequest`** gana `client_id` y `proyecto`, los dos opcionales. La pantalla todavía no
los manda; lo hará en S2.3. Mientras tanto se aplica la regla sin cliente.

---

## 2. El archivo protegido: el diff entero

Diff de `backend/app/services/engine/refine_operations_applier.py`: **3 líneas añadidas y 64
quitadas.**

Las 64 quitadas son las constantes `DEFAULT_BACKEND_LISTENER_IMPL` y `DEFAULT_BACKEND_LISTENER_ARGS`
y la función `_backend_listener_raw_xml`. Solo las usaba la rama que se sustituye; comprobado con
`grep` en todo `backend/`. Dejarlas habría mantenido una segunda fuente, muerta y con el maestro
dentro. **Nada más de `services/engine/` ha cambiado.**

Dos líneas del diff llevaban el valor del token maestro en claro. Aquí van como `<maestro>`, para no
volver a meterlo en el repositorio. Es lo único que difiere de `git diff`.

```diff
diff --git a/backend/app/services/engine/refine_operations_applier.py b/backend/app/services/engine/refine_operations_applier.py
index fd8ea4b..4738570 100644
--- a/backend/app/services/engine/refine_operations_applier.py
+++ b/backend/app/services/engine/refine_operations_applier.py
@@ -42,6 +42,7 @@ from app.schemas.refine_operations import (
     UpdateThreadGroupOp,
     UpdateUdvsOp,
 )
+from app.services.observabilidad.listener_influxdb import listener_del_buzon
 
 logger = logging.getLogger(__name__)
 
@@ -815,32 +816,6 @@ LISTENER_KIND_DEFAULTS = {
     },
 }
 
-# Backend Listener defaults — apuntan al InfluxDB del stack Kinetix
-# (containers `jmeter_influxdb` con bucket `jmeter`, org `performance`,
-# token `<maestro>` definidos en CLAUDE.md).
-DEFAULT_BACKEND_LISTENER_IMPL = (
-    "org.apache.jmeter.visualizers.backend.influxdb.InfluxdbBackendListenerClient"
-)
-DEFAULT_BACKEND_LISTENER_ARGS = [
-    {
-        "name": "influxdbMetricsSender",
-        "value": "org.apache.jmeter.visualizers.backend.influxdb.HttpMetricsSender",
-    },
-    {
-        "name": "influxdbUrl",
-        "value": "http://influxdb:8086/api/v2/write?org=performance&bucket=jmeter&precision=ms",
-    },
-    {"name": "application", "value": "${__P(application,Kinetix Test)}"},
-    {"name": "measurement", "value": "jmeter"},
-    {"name": "summaryOnly", "value": "false"},
-    {"name": "samplersRegex", "value": ".*"},
-    {"name": "percentiles", "value": "90;95;99"},
-    {"name": "testTitle", "value": "Test name"},
-    {"name": "eventTags", "value": ""},
-    {"name": "TOKEN", "value": "<maestro>"},
-]
-
-
 def _xml_escape(value: str) -> str:
     """Mini XML-escape para los pocos lugares donde inyectamos texto del usuario."""
     return (
@@ -964,40 +939,6 @@ def _corrected_result_collector_raw_xml(
     )
 
 
-def _backend_listener_raw_xml(
-    name: str,
-    implementation: str,
-    arguments: List[Dict[str, str]],
-) -> str:
-    """Construye un <BackendListener> con argumentos InfluxDB."""
-    name_esc = _xml_escape(name)
-    impl_esc = _xml_escape(implementation)
-    args_xml_lines: List[str] = []
-    for a in arguments:
-        arg_name = _xml_escape(a.get("name", ""))
-        arg_value = _xml_escape(a.get("value", ""))
-        args_xml_lines.append(
-            f'          <elementProp name="{arg_name}" elementType="Argument">\n'
-            f'            <stringProp name="Argument.name">{arg_name}</stringProp>\n'
-            f'            <stringProp name="Argument.value">{arg_value}</stringProp>\n'
-            f'            <stringProp name="Argument.metadata">=</stringProp>\n'
-            f"          </elementProp>"
-        )
-    args_xml = "\n".join(args_xml_lines)
-    return (
-        f'<BackendListener guiclass="BackendListenerGui" testclass="BackendListener" '
-        f'testname="{name_esc}" enabled="true">\n'
-        '  <elementProp name="arguments" elementType="Arguments" guiclass="ArgumentsPanel" '
-        'testclass="Arguments" testname="User Defined Variables" enabled="true">\n'
-        '    <collectionProp name="Arguments.arguments">\n'
-        f"{args_xml}\n"
-        "    </collectionProp>\n"
-        "  </elementProp>\n"
-        f'  <stringProp name="classname">{impl_esc}</stringProp>\n'
-        "</BackendListener>"
-    )
-
-
 def _build_listener_raw_xml(
     kind: str,
     name: str,
@@ -1006,10 +947,8 @@ def _build_listener_raw_xml(
 ) -> str:
     """Despacha la construccion del raw_xml inicial segun el listener_kind."""
     if kind == "backend_listener":
-        cfg = backend_config or {}
-        impl = cfg.get("implementation", DEFAULT_BACKEND_LISTENER_IMPL)
-        args = cfg.get("arguments", DEFAULT_BACKEND_LISTENER_ARGS)
-        return _backend_listener_raw_xml(name, impl, args)
+        # S2.2: una sola fuente. `backend_config` del modelo se ignora.
+        return listener_del_buzon(name)
 
     defaults = LISTENER_KIND_DEFAULTS.get(kind)
     if not defaults:
```

El archivo pasa de 1075 a 1014 líneas.

---

## 3. `/monitoring/jmeter-fragmento` y `sesiones.py`

- **`/jmeter-fragmento`** entrega lo que genera el módulo: el listener más su `<hashTree/>`, con las
  dos propiedades. Toma la URL, el token y la corrida de `_configuracion_jmeter`, así que **dice lo
  mismo que `/jmeter-config`**.

  **Cambio de comportamiento:** sin token utilizable, antes entregaba un fragmento con el token vacío,
  que no mandaba nada. Ahora responde **400** con el mensaje. Ninguna suite ni pantalla dependía de lo
  anterior: el único que lo consume es `services/api.ts`, que lo descarga.
- **`sesiones.py` se queda como está**, porque no es un cambio mínimo. Pasarlo al módulo convierte su
  `application` en `${__P(application,…)}` y cambia su URL. Hoy entrega `config.influxdb_url` sin
  traducir (`influxdb:8086`), y el módulo daría `localhost:8086`. `o2d3_jmx.py:90` exige
  `application == CORRIDA` literal. **Queda como segunda fuente del listener:
  `jmx_listener.construir_listener`.** Unificarlo es una decisión aparte, con su suite.

---

## 4. Límite conocido: «Ejecución completa»

El `.jmx` del diseñador trae por defecto la URL de fuera, `localhost:8086`, y dentro de
`jmeter_backend` esa no llega a InfluxDB. **Mientras el ejecutor de «Ejecución completa» no pase
`-JinfluxdbUrl=http://influxdb:8086/…` y `-Japplication=…` por corrida, sus métricas no llegan.** Antes
tampoco llegaban, por el `TOKEN` que nadie leía. Es **S3 (motor)** y no se ha tocado. La prueba real
de §5 pasa las dos propiedades con `-J`.

---

## 5. Pruebas

### 5.1 La suite: `backend/pruebas_e2e/s21_token_en_jmx.py`, 44 de 44

Era la sonda de S2.1 y ahora es la suite de S2.2. Corre contra `jmeter_analyzer_test` y el 8002.

- **El maestro se busca por su SHA-256.** La suite no lo lleva escrito: compara la huella de cada
  texto y de cada atributo del XML.
- **El token de escritura** se compara por huella con `KX_TOKEN_ESCRITURA`, que viene de
  `lab/lab.env`.

| Bloque | Qué comprueba | Resultado |
|---|---|---|
| A | **Ruta de la IA por el endpoint real.** `refine_jmx_surgical` en proceso: parseo, `resolver`, buzón, aplicador y regenerador. Solo se sustituyen `_call_ai` (devuelve la operación) y `load_ai_config_from_db`: **0 llamadas a la IA**. Sin maestro; `influxdbToken` con huella `5ced8a1fda` (la de escritura); `${__P(influxdbUrl,http://localhost:8086/api/v2/write?org=performance&bucket=jmeter)}`; `${__P(application,zztest-s2-2-listener-zztest-s22-20260930-0420)}`; sin «Kinetix Test» ni `TOKEN`; la `backend_listener_config` que manda el «modelo» se ignora | 12/12 |
| B | La misma ruta **sin cliente ni proyecto**: el analista recibe el listener, con `sin-nombre-zztest-s2-2-plan-20260930-0420` | 11/11 |
| C | **Sin token, por el endpoint.** `UPDATE monitoring_config SET influxdb_token_encrypted = NULL` dentro de una transacción que se **deshace**. El endpoint devuelve «No se pudo aplicar la operacion: … No hay token de escritura…», el `.jmx` vuelve sin listener y el token sigue en la base | 3/3 |
| D | El aplicador con el **buzón vacío**: error claro («Se pidió un Backend Listener sin los datos…») y ningún listener | 1/1 |
| E | `/monitoring/jmeter-fragmento` por HTTP: sin maestro, con `<hashTree/>` y los mismos valores que A | 11/11 |
| F | **Prueba real** (siguiente apartado) | 3/3 |
| — | Limpieza (regla 35) | 3/3 |

C es el único punto que escribe en la base: un `UPDATE` sin `COMMIT` sobre la base de **pruebas**,
deshecho con `rollback()`. Lo comprueba el propio bloque.

### 5.2 La prueba real, y el borrado que la sigue

JMeter 5.6.3, dentro de `jmeter_backend`, corre **el `.jmx` que salió de A**: 2 hilos por 25 vueltas
contra `http://localhost:8002/docs`, con
`-JinfluxdbUrl=http://influxdb:8086/api/v2/write?org=performance&bucket=jmeter` y
`-Japplication=zztest-s22-20260930-042006`. **No se le pasa el token**: es el que va dentro del
`.jmx`.

- `summary = 50 in 00:00:01 … Err: 0 (0.00%)`, y el log del listener, sin errores de escritura.
- **43 puntos** en el cubo `jmeter` bajo `application=zztest-s22-20260930-042006`, leídos con el token
  de **lectura** (`kinetix-lectura`), no con el maestro.

**Borrado en InfluxDB (regla 35):**

- **Qué:** los puntos del cubo `jmeter` con `application="zztest-s22-20260930-042006"`, y nada más.
- **Por qué:** los escribió esta prueba, y el cubo `jmeter` solo admite borrar lo marcado `zztest-`.
- **Comprobación previa:** `schema.tagValues(application)` en las últimas 2 h. La única
  `zztest-s22-*` era `['zztest-s22-20260930-042006']`, y la suite **solo borra si es así**.
- **Resultado:** `204`, y una consulta posterior no encuentra ni un punto suyo.

El borrado se hizo con el token de **escritura** de `jmeter`, que basta para `/api/v2/delete` sobre
su cubo. No se usó el maestro.

Los tres ficheros de la corrida (`/tmp/zztest_s22.{jmx,jtl,log}`) se borran al terminar: el `.jmx`
llevaba el token de escritura.

### 5.3 Las suites de O1 y O2a

| Suite | Resultado |
|---|---|
| `o16_pantalla.py` (**O1**) | **25/25**, TODO PASA |
| `probar_tablero.py` (**O2a**) | **2 pasan y 16 fallan: todos los paneles con 0 filas** |
| `o2d3_jmx.py` (O2d, extra: el `.jmx` de sesión, que no cambia) | 17/17, TODO PASA |

**`probar_tablero.py` no está en verde, y no es por este cambio**, aunque no lo he podido comprobar
de la única forma que lo demostraría: con datos frescos. La suite no llama a ningún endpoint. Lee el
JSON del tablero y pregunta a InfluxDB por los **últimos 40 minutos** de la corrida del laboratorio.
Necesita el recorrido de O2a.3 justo antes (`LEEME.md`: «la necesita **fresca**»), y **`lab_colector`
está caído desde hace 3 días** (`Exited (255) 3 days ago`). Levantarlo es arrancar contenedores y eso
lo decide Fredy (regla 7). Para cerrarlo: `bash scripts/regresion_h8.sh`, que lanza el laboratorio y
después las suites.

---

## 6. Archivos del commit

| Archivo | Qué |
|---|---|
| `backend/app/services/observabilidad/listener_influxdb.py` | **Nuevo.** La única fuente del listener |
| `backend/app/services/engine/refine_operations_applier.py` | **Protegido**, autorizado: el diff de §2 |
| `backend/app/api/v1/endpoints/script_ai.py` | El buzón alrededor de `apply_operations` en `refine-surgical`, y el prompt sin `backend_listener_config` |
| `backend/app/schemas/refine_operations.py` | `client_id` y `proyecto` opcionales; la descripción de `backend_listener_config` dice que se ignora |
| `backend/app/api/v1/endpoints/monitoring.py` | `/jmeter-config` usa `url_de_escritura`; `/jmeter-fragmento` entrega lo que genera el módulo |
| `backend/pruebas_e2e/s21_token_en_jmx.py` | La suite |
| `docs/reporte_claude_code/133_S2_2_listener_backend.md` | Este reporte |

**Fuera del commit:** el reporte 132, que sigue sin commit. Su §1 lleva el valor del maestro en claro
en el título, y conviene cambiarlo por `<maestro>` antes de versionarlo.

## 7. Lo que sigue

- **S2.3**: `AIScriptEditor.tsx` pide el listener al backend, con la aplicación cerrada. Hasta
  entonces, **la ruta de la pantalla sigue metiendo el maestro**.
- **S3**: el ejecutor de «Ejecución completa» pasa `-JinfluxdbUrl` y `-Japplication` (§4).
- `sesiones.py` / `jmx_listener.py`: la segunda fuente del listener (§3).
- La regresión de O2a con el laboratorio en marcha (§5.3).

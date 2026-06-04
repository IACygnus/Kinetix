# Sprint 2.5a — Instalación JMeter en container backend

**Fecha:** 2026-05-30
**Branch:** backup-trabajo-local
**Owner:** Fredy Bonilla
**Estado:** ✅ JMeter 5.6.3 + Java 21 + 4 plugins jpgc + InfluxdbBackendListenerClient nativo, instalados y funcionales

---

## 1. Cambios

### `backend/Dockerfile`

Reescrito de single-stage `python:3.11-slim` a **multi-stage**:

- **Stage 1 (`jmeter-base`)**: `eclipse-temurin:17-jre-jammy` solo para el build — descarga Apache JMeter 5.6.3 desde el Apache Archive, instala Plugin Manager + CMDRunner, instala plugins `jpgc-casutg,jpgc-functions,jpgc-graphs-basic,jpgc-tst` vía `PluginsManagerCMD.sh`, verifica con `jmeter -v`.
- **Stage 2 (`app`)**: `python:3.11-slim` (Debian trixie) + las apt-deps originales (WeasyPrint, tesseract, etc.) + `openjdk-21-jre-headless` + `libfreetype6` + `COPY --from=jmeter-base /opt/apache-jmeter-5.6.3` + `ENV JMETER_HOME` + `PATH`. El resto del Dockerfile original (WORKDIR, requirements.txt, pip install, COPY código, mkdir, EXPOSE 8001, CMD uvicorn) se preserva tal cual.

### Backup

- `backend/Dockerfile.bak_25a_20260530_161807`

### Decisiones técnicas

- **Java 21 en runtime** (no Java 17): Debian trixie (base de `python:3.11-slim` actual) ya no provee `openjdk-17-jre-headless` — solo `openjdk-21-jre-headless`. JMeter 5.6.3 está oficialmente soportado en Java 17 y 21. El stage `jmeter-base` sigue usando temurin:17 porque solo se usa para descargar/instalar (no para runtime).
- **Plugins**: el `PluginsManagerCMD.sh install` instaló los 4 paquetes solicitados — verificado en `/opt/apache-jmeter-5.6.3/lib/ext/`.
- **Backend Listener InfluxDB v2**: no requiere plugin extra. La clase `org.apache.jmeter.visualizers.backend.influxdb.InfluxdbBackendListenerClient` viene en `ApacheJMeter_components.jar` (verificado abajo).

---

## 2. Verificaciones

| Check | Comando | Resultado |
|---|---|---|
| `jmeter -v` | `docker exec jmeter_backend jmeter -v` | `5.6.3` + banner ASCII ✅ |
| Java runtime | `docker exec jmeter_backend java -version` | `openjdk version "21.0.11"` ✅ |
| Plugins jpgc | `ls /opt/apache-jmeter-5.6.3/lib/ext/ \| grep jmeter-plugins-` | `casutg-3.1.1`, `functions-2.2`, `graphs-basic-2.0`, `manager-1.10`, `tst-2.6` ✅ |
| `InfluxdbBackendListenerClient` nativo | inspección zipfile de `ApacheJMeter_components.jar` | clase presente ✅ |
| Smoke JMX | `jmeter -n -t test.jmx -l result.jtl` | `Created the tree successfully` + `... end of run` ✅ |
| JTL generado | `head result.jtl` | header CSV correcto (timeStamp,elapsed,label,responseCode,...) ✅ |
| Backend FastAPI sigue OK | `curl http://localhost:8001/health` | `{"status":"healthy"}` ✅ |

### Detalle de archivos en `/opt/apache-jmeter-5.6.3/lib/ext/`

```
ApacheJMeter_bolt.jar       ApacheJMeter_jms.jar             jmeter-plugins-graphs-basic-2.0.jar
ApacheJMeter_components.jar ApacheJMeter_junit.jar           jmeter-plugins-manager-1.10.jar
ApacheJMeter_core.jar       ApacheJMeter_ldap.jar            jmeter-plugins-tst-2.6.jar
ApacheJMeter_ftp.jar        ApacheJMeter_mail.jar            readme.txt
ApacheJMeter_functions.jar  ApacheJMeter_mongodb.jar
ApacheJMeter_http.jar       ApacheJMeter_native.jar
ApacheJMeter_java.jar       ApacheJMeter_tcp.jar
ApacheJMeter_jdbc.jar       jmeter-plugins-casutg-3.1.1.jar
ApacheJMeter_jms.jar        jmeter-plugins-functions-2.2.jar
```

### Banner JMeter recibido

```
    _    ____   _    ____ _   _ _____       _ __  __ _____ _____ _____ ____
   / \  |  _ \ / \  / ___| | | | ____|     | |  \/  | ____|_   _| ____|  _ \
  ...
/_/   \_\_| /_/   \_\____|_| |_|_____|  \___/|_|  |_|_____| |_| |_____|_| \_\ 5.6.3
Copyright (c) 1999-2024 The Apache Software Foundation
```

### Smoke test trivial — output esperado

```
Created the tree successfully using test.jmx
Starting standalone test @ 2026 May 30 21:26:33 UTC
summary =      0 in 00:00:00 = ******/s ...
Tidying up ...    @ 2026 May 30 21:26:33 UTC
... end of run
```

(El `0 in 00:00:00` es esperado: el JMX trivial tiene Thread Group con N=1, loops=1 y SIN samplers — solo verifica que JMeter arranca, parsea el JMX y termina limpiamente sin errores Java/classpath.)

---

## 3. Métricas del build

| Métrica | Valor |
|---|---|
| Imagen final `jmeter-analyzer-backend:latest` | **2.08 GB** |
| Imagen anterior (single-stage Python) | ~1.2 GB (estimado pre-2.5a) |
| Δ por JMeter 5.6.3 + plugins + Java 21 | **~880 MB** |
| Tiempo de build (no-cache) | ~3-4 min (rebuild con cache en stage `jmeter-base`: ~50 s solo el stage `app`) |

El stage `jmeter-base` se cachea entre builds: solo se re-ejecuta si se cambia la versión de JMeter o la lista de plugins. Builds sucesivos de la app son rápidos.

---

## 4. Issues encontrados y resueltos

| # | Issue | Causa raíz | Solución |
|---|---|---|---|
| 1 | `docker compose build jmeter_backend` falló con `no such service` | El nombre del servicio en `docker-compose.yml` es `backend`, no `jmeter_backend` (este último es el `container_name`) | Usar `docker compose build backend` |
| 2 | `apt-get install openjdk-17-jre-headless` falló (`Package has no installation candidate`) | `python:3.11-slim` actualizado a Debian **trixie**, donde ya no hay `openjdk-17-*` | Cambiar a `openjdk-21-jre-headless`. JMeter 5.6.3 soporta Java 17 y 21 oficialmente |

---

## 5. Pendientes — Sprint 2.5

| Sprint | Capacidad | Estado |
|---|---|---|
| **2.5a** | Instalar JMeter + Java + plugins en container backend | ✅ ESTE SPRINT |
| 2.5b | Endpoint `POST /script-designer/ai/designs/{id}/smoke-test` (ejecuta JMX con N=1 usuario) | ⏳ siguiente |
| 2.5c | UI: botón "Smoke" en Editor IA + panel de resultado del último smoke | ⏳ |
| 2.5d | Endpoint `/execute` (full run con metrics_collector + JTL en disco) | ⏳ |
| 2.5e | UI: panel de ejecución con progreso live (WebSocket `/ws/executions/{id}/metrics`) | ⏳ |

---

## 6. Cómo validar manualmente

```bash
# 1. JMeter versión
docker exec jmeter_backend jmeter -v 2>&1 | grep -E "5\.6\.3|Copyright"

# 2. Java
docker exec jmeter_backend java -version

# 3. Plugins
docker exec jmeter_backend ls /opt/apache-jmeter-5.6.3/lib/ext/ | grep jmeter-plugins-

# 4. Backend Listener InfluxDB nativo
docker exec jmeter_backend python -c "import zipfile; z=zipfile.ZipFile('/opt/apache-jmeter-5.6.3/lib/ext/ApacheJMeter_components.jar'); print('InfluxdbBackendListenerClient.class' in '\n'.join(z.namelist()))"

# 5. Smoke test
docker exec jmeter_backend bash -c "cd /tmp/smoke && jmeter -n -t test.jmx -l result.jtl 2>&1 | tail -5"

# 6. App sigue OK
curl http://localhost:8001/health
```

---

## 7. Estado

**✅ LISTO para Sprint 2.5b (endpoint smoke-test).**

El container `jmeter_backend` ahora puede invocar `jmeter -n -t script.jmx -l result.jtl` desde Python `subprocess` para correr cualquier JMX generado por el Editor IA. La integración con InfluxDB del stack Kinetix (Sprint 2.4-HF7.B) funcionará out-of-the-box porque `InfluxdbBackendListenerClient` viene en el JMeter estándar.

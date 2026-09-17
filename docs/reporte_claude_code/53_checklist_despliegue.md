3ba8fee · 2026-09-17

# Checklist de despliegue — deuda acumulada de las Etapas 1 a 6

> **Este documento no ejecuta nada.** Es la lista consolidada de lo que quedó
> anotado como deuda operativa en los 52 reportes anteriores. Fredy controla el
> ciclo Docker y el servidor (regla 7); aquí solo está el qué, el dónde y el
> porqué, con el comando literal cuando el reporte lo daba.
>
> Servidor: `20.81.141.77` · `/opt/apps/jmeter-analyzer` · `kinetix.sqasa.co`.

---

## 0. Lo bloqueante, en orden

1. **El `ALTER TABLE` de `reasoning_effort`** — sin él los informes salen en modo
   respaldo **sin avisar**. (§1.1)
2. **Arreglar `docker-compose.prod.yml`** — hoy, fusionado, no cierra ni un
   puerto y construye el frontend con la fase de desarrollo. (§2.1 y §2.2)
3. **Rebuild de backend y frontend en el servidor.** (§2.3)
4. **HF-3** si el despliegue es multiusuario: hoy **cinco entradas en quince
   minutos dejan a toda la plataforma sin acceso**. (§4)

---

## 1. Base de datos

### 1.1 `reasoning_effort` — el único cambio de esquema de las seis etapas

```bash
docker exec -i jmeter_postgres psql -U jmeter_user -d jmeter_analyzer_db \
  < docs/sql/etapa2_reasoning_effort.sql
```

El script es **idempotente** (`ADD COLUMN IF NOT EXISTS`) y se puede correr las
veces que haga falta. `NULL` significa `low`: no hay que rellenar las filas
existentes.

**Verificación obligatoria después:** `GET /ai-config` responde **200** e incluye
`reasoning_effort`.

**Por qué no es opcional.** El proyecto no usa Alembic:
`Base.metadata.create_all` solo crea tablas nuevas, nunca añade columnas a una
existente. Sin la columna el backend **arranca bien**, pero la primera lectura de
`ai_config` falla en Postgres, el error se degrada a un `logger.warning` dentro de
`load_ai_config_from_db`, y **todos los informes salen con texto del
`FallbackAnalyzer` sin que nadie se entere**.

- **Aplicado en desarrollo** (verificado: `reasoning_effort | character varying(20)`).
- **Pendiente en producción.**
- Reportes: 14 (§2), 19 (§6), 25 (§6.1), 29, 35 (§7.1), 40, 44 (§6).

### 1.2 Ninguna otra etapa toca el esquema

Declarado explícitamente para poder confiar en esta lista: la Etapa 3 "no añade
ningún paso nuevo de despliegue: no hay tablas ni columnas nuevas" (35 §7); la
Etapa 5, "ni tablas, ni columnas, ni cambios de esquema" (44 §6); la Etapa 6.5
tampoco — las filas de `transaction_analyses` se quedan donde están (50 §2).

### 1.3 Tabla `login_attempts` — solo si se implementa HF-3

Diseño escrito, **código no tocado**: tabla nueva (la crearía `create_all` sin
`ALTER`), clave `ip` + `username` normalizado, `created_at`, índice
`(clave, created_at)`. Solo guarda intentos fallidos; un login correcto borra las
filas de su clave. Reporte 37 §3.1.

---

## 2. Contenedores, compose y puertos

### 2.1 `ports: []` NO cierra ningún puerto — verificado

**Compose FUSIONA las listas de puertos en vez de reemplazarlas.** Los
`ports: []` de `postgres`, `influxdb` y `grafana` en `docker-compose.prod.yml` no
tienen ningún efecto. Verificado sobre el repo, en solo lectura:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml config
```

Resultado real de la fusión:

| Servicio | Publicado en el host | Lo que dice CLAUDE.md |
|---|---|---|
| `postgres` | **5432 en 0.0.0.0** | "puerto cerrado al host" |
| `influxdb` | **8086 en 0.0.0.0** | "puerto cerrado al host" |
| `grafana` | **3000 en 0.0.0.0** | "puerto cerrado al host" |
| `backend` | **8001 en 0.0.0.0** | no se menciona |

Las credenciales de Postgres son las conocidas del proyecto. Mientras esto siga
así, `X-Forwarded-For` es falsificable por cualquiera que alcance el 8001.

**Qué hacer:** publicar con interfaz explícita en vez de intentar vaciar la lista —
`127.0.0.1:5432:5432`, `127.0.0.1:8086:8086`, `127.0.0.1:3000:3000`,
`127.0.0.1:8001:8001`— y **volver a verificar con `docker compose … config`**
antes de desplegar. Revisar también que el NSG de Azure solo exponga 80 y 443.

Reporte 37 (§2 y §5). **Sin corregir en ningún entorno.**

### 2.2 El override de producción construye el frontend con la fase de desarrollo

La misma fusión revela un segundo problema en el mismo archivo:

```yaml
frontend:
  build:
    target: builder      # <- viene del compose base y SOBREVIVE a la fusión
  command: []
  ports:
    - 5173 -> 5173       # del base
    - 5173 -> 80         # del override, sobre el MISMO puerto de host
  volumes:
    - ./frontend:/app    # el `volumes: []` del override tampoco lo vacía
```

Es decir: el `docker-compose.prod.yml` **tal como está commiteado** no produce el
frontend de nginx, sino la fase `builder` de Vite, con el bind-mount del código
y dos mapeos peleándose por el puerto 5173 del host.

Esto explica la nota de CLAUDE.md §14 sobre que "el cambio de `target` vive solo
en el servidor": alguien lo editó a mano allí. **La consecuencia práctica es que
el repositorio no tiene un override de producción desplegable**, y hay que
arreglarlo antes de subir nada (el `target` correcto es la última fase del
`frontend/Dockerfile`, `FROM nginx:alpine`, que no está nombrada).

Comprobar en el servidor qué mapeo ganó: `docker port jmeter_frontend`.

Reporte 37 (§2.b y §5).

### 2.3 Rebuild en el servidor — obligatorio

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

Las Etapas 2, 3, 5 y 6 cambian backend **y** frontend. Sin rebuild allí no se ve
nada.

**En local NO hace falta** y por eso no se hizo en ninguna etapa: el backend corre
`uvicorn --reload` con `./backend` montado y el frontend es el dev server de Vite
con `./frontend` montado. Basta **Ctrl + Shift + R**.

Reportes: 25 (§6.2), 35 (§7.2), 40 (que corrige al 36 en este punto), 44 (§6),
45 (§3), 47 (§4), 50.

### 2.4 Diagnóstico read-only a hacer *en el servidor* antes de tocar nada

Cuatro comprobaciones, ninguna ejecutada todavía (todo el diagnóstico de HF-3 se
hizo sobre el repo y en local):

| Comando | Qué se busca |
|---|---|
| `grep -n "X-Forwarded-For\|X-Real-IP" /etc/nginx/sites-available/kinetix.sqasa.co` | si nginx pasa la IP real |
| `docker inspect jmeter_backend` | **el comando real de uvicorn**, que puede diferir del compose — hay precedente de cambios a mano que solo viven en el servidor |
| `docker network inspect jmeter_network` | la subred y el gateway **reales**, para `--forwarded-allow-ips` |
| `docker port jmeter_backend` + reglas del NSG | qué está publicado de verdad |

Reporte 37 (§4 y §5).

---

## 3. Variables de entorno

**No hay deuda de `DEBUG`, `ENVIRONMENT`, `FERNET_KEY` ni `COOKIE_SECURE`** en
los 52 reportes: se buscaron explícitamente y no aparecen como pendiente. Lo único
relacionado:

- **`KX_PWD`** — la contraseña que usan los scripts E2E
  (`docker exec -e KX_PWD=<clave> …`). Nunca se escribe en un reporte ni en un
  script. Es operativa de pruebas, no de despliegue.
- **Recordatorio heredado de §1.1:** si falta la columna `reasoning_effort`, la
  configuración de IA cae al fallback por variables de entorno y, sin clave allí,
  a `FallbackAnalyzer`. No es una variable que haya que poner: es la consecuencia
  de no aplicar el SQL.

---

## 4. HF-3 — el rate limit de `/auth/login`, inservible en producción

**No implementado. Bloqueante para un despliegue multiusuario.**

Hechos verificados sobre el repo (reporte 37 §1):

| Hecho | Dónde |
|---|---|
| `uvicorn … --workers 2` **sin** `--proxy-headers` ni `--forwarded-allow-ips` | `docker-compose.prod.yml:25` |
| `ip = request.client.host` — nunca mira `X-Forwarded-For` | `auth.py:61` |
| `_login_attempts` es un dict **en memoria de proceso** | `auth.py:31` |
| Los **logins correctos** también consumen cupo | `auth.py:96` |

**Efecto:** con nginx proxando a `localhost:8001`, todos los usuarios llegan con
la misma IP (el gateway de Docker) → **5 entradas cada 15 minutos para toda la
plataforma**, con un mensaje que parece error de contraseña. Y con dos workers hay
dos contadores independientes: el límite real oscila entre 5 y 10 y cualquier
recarga de un worker borra el suyo.

Para resolverlo hacen falta las tres cosas a la vez: la tabla de §1.3, los flags
de uvicorn con **el gateway real** de §2.4 (no `127.0.0.1`), y el cierre de
puertos de §2.1.

**Pendiente de decisión de producto:** el mensaje que ve quien queda bloqueado
(reporte 37 §3.5).

---

## 5. Ficheros, volúmenes y scripts

### 5.1 Los scripts de verificación viven dentro del contenedor

`/tmp/e2e/` en `jmeter_backend` — **no están en el repositorio** y un
rebuild/recreate los borra. La fuente está fuera del repo a propósito:
`C:\proyectos\Kinetix_pruebas\e2e\`.

```bash
docker cp C:/proyectos/Kinetix_pruebas/e2e jmeter_backend:/tmp/e2e
docker exec -d jmeter_backend python3 /tmp/e2e/rele_5173.py
docker exec jmeter_backend python3 -c "import socket;print(socket.socket().connect_ex(('127.0.0.1',5173)))"
```

El relé TCP hace que el frontend se vea como `http://localhost:5173` dentro del
contenedor, que es el origen que el backend admite por CORS.

**Hecho en el cierre de la Etapa 6:** los scripts de las Etapas 5 y 6
(`panel_seleccion.py`, `e5_verdictos.py`, `capas_tooltip.py`, `export_alcance.py`,
`dialogo_export.py`, `capas_exportadas.py`, `capas_html_render.py`) y el
`hf4_check.py` modificado en 6.5 solo existían dentro del contenedor y **ya se
copiaron a `C:\proyectos\Kinetix_pruebas\e2e\`**, que ahora tiene 29 archivos.
Los tres que quedan solo en el contenedor (`dbg_login.py`, `dbg_rep.py`,
`desglose.py`) son desechables.

Sigue pendiente **copiarlos al servidor** si se quiere verificar allí.

Reportes: 46 (§8.2), 19 (§5), 24, 50 (§3).

### 5.2 `/app/uploads` — no hay nada que provisionar

- Los JTL de las ejecuciones históricas viven ahí, y por eso los informes son
  regenerables (reportes 01, 04).
- **Los exportados PDF y HTML no se guardan en disco**: se devuelven por HTTP.
  `/app/uploads` tiene 197 archivos y ninguno es PDF ni HTML (reporte 38 §3.2).
  **No hace falta volumen de media para exportados.**

### 5.3 Copias de seguridad `*.bak_*`

Cada etapa deja backups locales (`*.bak_etapa6_6.5_20260917`, etc.). Están
cubiertos por `.gitignore:163` (`*.bak_*`), **no se commitean y no viajan al
servidor**. Quedan 53 en el árbol local; es limpieza local, no deuda de
despliegue.

---

## 6. Otros pendientes anotados

### 6.1 Decidir el `reasoning_effort` de producción

Toda la medición de la Etapa 2 (los 141 s) se hizo con **`low`**, y ahí quedó.
Es una decisión de configuración a tomar en el panel de IA una vez desplegado.
Reportes 25 (§6.3), 35 (§7.3).

### 6.2 Un test en rojo, anterior al plan

```
FAILED tests/test_analysis_pipeline.py::test_pipeline_parsea_jtl_y_popula_metricas_basicas
1 failed, 492 passed
```

Confirmado hoy. Falla porque parchea `app.services.ai.analysis_pipeline.time` y
ese módulo ya no importa `time`; se verificó que falla igual con el árbol limpio
en `533bade`, o sea que **no lo rompió ninguna etapa**. Arreglo previsto: quitar
ese `patch`, una línea. Reportes 37 (§6), 32 (§7), 43, 44 (§3).

### 6.3 Corregir CLAUDE.md §2 y §14

Documentaban una protección de puertos que no existe (§2.1 de este documento).
**Corregidos en el mismo commit que este checklist.** Reporte 37 (§5).

### 6.4 Dos análisis globales a regenerar a mano (solo en desarrollo)

Se perdieron en `919b350d`. Son **2 llamadas de IA**, desde la pantalla:
Performance → Monitoreo → «prueba final 2 — popular» → *Generar Análisis Global*,
y lo mismo en Performance → Evidencias. Reportes 38 (§5), 35 (§6.2), 40 (§2.1).

### 6.5 Textos ya guardados que conservan el estilo viejo

Los textos generados antes de la Etapa 3 mantienen la jerga y el formato inglés —
el aviso ámbar los marca en pantalla. No se regeneraron porque costaba unas 40
llamadas. Se arreglan regenerando o editando a mano, en el entorno donde estén.
Reporte 35 (§6.2).

### 6.6 Lo que NO es deuda, para que no se confunda

- `CLIENTE_TIMEOUT_S = 120.0` en el cliente OpenAI y el reintento de errores
  transitorios (2 s y 4 s) **están implementados y en el repo**: viajan con el
  despliegue normal (reportes 12, 11 §2).
- `transaction_analyses_html` **ya se retiró** en la Etapa 6.5 (D53): el punto
  queda cerrado (reportes 41, 44 §5.1, 50 §2).

---

## 7. Resumen ejecutable

```
1. docker exec -i jmeter_postgres psql -U jmeter_user -d jmeter_analyzer_db \
     < docs/sql/etapa2_reasoning_effort.sql        # y verificar GET /ai-config = 200
2. arreglar docker-compose.prod.yml: 127.0.0.1:<puerto>:<puerto> en los cuatro
   servicios, y el target correcto del frontend
   -> verificar con: docker compose -f docker-compose.yml -f docker-compose.prod.yml config
3. docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
4. HF-3 completo, si el despliegue es multiusuario
5. docker cp .../e2e jmeter_backend:/tmp/e2e   (si se quiere verificar allí)
```

**Nada de esto se ha ejecutado.**

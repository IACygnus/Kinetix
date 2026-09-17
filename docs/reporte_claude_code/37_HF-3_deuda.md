# HF-3 — Rate limit de /auth/login (DEUDA, no se implementa en la Etapa 2)

> Este documento vivia en `/tmp` y en `C:\proyectos\Kinetix_pruebas`. Desde ahora TODOS los
> reportes (tecnicos, resumenes para Fredy, paradas y notas de deuda) viven en
> `docs/reporte_claude_code/`. En `Kinetix_pruebas` quedan solo herramientas y datos crudos.

Para el cierre de la Etapa 2 (reporte 24) y el checklist de despliegue.
**Diagnóstico verificado sobre el repo el 2026-09-16. No se ha tocado código.**
Sustituye a la versión anterior de esta nota.

---

## 1. Hallazgos confirmados

| Hecho | Dónde |
|---|---|
| `uvicorn … --workers 2` **sin** `--proxy-headers` ni `--forwarded-allow-ips` | `docker-compose.prod.yml:25` (0 coincidencias en ambos compose) |
| `ip = request.client.host` — nunca mira `X-Forwarded-For` | `auth.py:61` |
| `_login_attempts` es un dict **en memoria de proceso** | `auth.py:31` |
| Los **logins correctos** también consumen cupo | `auth.py:96` |
| Ventana deslizante 5 / 900 s; un 429 no registra nada | `auth.py:33-44, 82, 96` |

**Efecto en producción:** con nginx en el host proxando a `localhost:8001`, todos los usuarios
llegan con la misma IP (gateway de Docker) → **5 logins cada 15 minutos para TODA la plataforma**.
Y con `--workers 2` hay **dos contadores independientes**: el límite real oscila entre 5 y 10
según a qué worker caiga cada intento, y cualquier recarga de un worker borra su contador.

Medido en local: E2E dentro del contenedor → `127.0.0.1`; navegador del host → `172.18.0.1`.
Esa separación **desaparece** en producción.

## 2. Hallazgo adicional de esta revisión — relevante para el punto 4 del diseño

**El backend NO tiene el puerto cerrado en producción.**

`docker-compose.prod.yml` cierra explícitamente los puertos de `postgres` (línea 9),
`influxdb` (39) y `grafana` (52) con `ports: []`, **pero el bloque `backend` no define `ports`**,
así que hereda `"8001:8001"` de `docker-compose.yml` — es decir, **`0.0.0.0:8001`**, todas las
interfaces de la VM.

El patrón de cierre ya existe en el archivo y el backend quedó fuera. Mientras siga así,
`X-Forwarded-For` es **falsificable** por cualquiera que alcance el puerto 8001 directamente, y la
seguridad depende por completo del NSG de Azure. El punto 4 del diseño (publicar como
`127.0.0.1:8001:8001`) **no está cumplido hoy**.

**Subred local de `jmeter_network`:** `172.18.0.0/16`, gateway `172.18.0.1`.
La del servidor puede ser otra y hay que leerla allí (§4).

## 2.b `ports: []` NO cierra los puertos — verificado con el merge real

Comando ejecutado (solo lectura, **no** `up` ni `build`), el mismo merge que usa el despliegue:

```
docker compose -f docker-compose.yml -f docker-compose.prod.yml config
```

Puertos **efectivos** del resultado:

| Servicio | host_ip | publicado → destino |
|---|---|---|
| backend | **0.0.0.0 (todas)** | 8001 → 8001 |
| frontend | **0.0.0.0 (todas)** | 5173 → 5173 |
| frontend | **0.0.0.0 (todas)** | **5173 → 80** *(segunda entrada)* |
| grafana | **0.0.0.0 (todas)** | 3000 → 3000 |
| influxdb | **0.0.0.0 (todas)** | 8086 → 8086 |
| postgres | **0.0.0.0 (todas)** | 5432 → 5432 |

**Conclusión: `ports: []` en el override NO vacía los puertos del archivo base.** Compose
**fusiona** las secuencias en vez de reemplazarlas, así que una lista vacía deja intacta la del
base. Los `ports: []` de `postgres` (línea 9), `influxdb` (39) y `grafana` (52) **no tienen
ningún efecto**.

> **Esto contradice lo documentado.** CLAUDE.md §2 («`ports: []` → puertos cerrados al host») y
> §14 («Puertos `postgres`, `influxdb`, `grafana` cerrados al host») describen una protección que
> **el merge no produce**. Conviene corregir CLAUDE.md además de arreglar el compose.

Consecuencia en el servidor: **Postgres (5432), InfluxDB (8086) y Grafana (3000) quedan
publicados en todas las interfaces de la VM**, protegidos únicamente por el NSG de Azure. Las
credenciales de Postgres son las conocidas del proyecto.

**Efecto lateral detectado:** `frontend` acaba con **dos** mapeos sobre el mismo puerto de host
5173 (`5173→5173` del base y `5173→80` del override), por la misma fusión de listas. Hay que
comprobar en el servidor cuál gana de verdad (`docker port jmeter_frontend`), porque el compose
tal cual no es determinista a simple vista.

**Forma correcta de cerrar un puerto** con override: no `ports: []`, sino redefinir el mapeo
atado al bucle local, p. ej. `"127.0.0.1:5432:5432"` — o quitar la publicación reestructurando
los archivos. A decidir al implementar.

---

## 3. Diseño decidido (implementar tras la Etapa 2, antes del despliegue)

1. **Estado en PostgreSQL**: tabla nueva `login_attempts` — clave = `ip` + `username` normalizado,
   `created_at`, índice `(clave, created_at)`. La crea `create_all` (regla 10: tabla nueva, sin
   ALTER). Solo se guardan intentos **fallidos**; un login correcto **borra** las filas de su
   clave; purga oportunista de filas de más de 15 min.
2. **Límite**: 5 fallidos / 15 min por clave. **Sin estado en memoria de proceso** — esto resuelve
   de paso el problema de los contadores partidos entre workers.
3. **IP real**: `uvicorn --proxy-headers --forwarded-allow-ips=<gateway/subred REAL de
   jmeter_network en el servidor>`. **No `127.0.0.1`**: nginx llega por el puerto publicado, vía
   el gateway de Docker.
4. **Seguridad del puerto**: publicar el backend como `127.0.0.1:8001:8001` en producción
   (hoy es `8001:8001`, §2) y verificar que el NSG de Azure solo expone 80/443. Sin esto,
   `X-Forwarded-For` es falsificable y el punto 3 no sirve de nada.
5. **Mensaje de bloqueo**: **PENDIENTE — decisión de producto de Fredy.**

---

## 4. Diagnóstico pendiente EN EL SERVIDOR (read-only, al preparar el despliegue)

- **nginx**: `proxy_set_header X-Forwarded-For` / `X-Real-IP` en
  `/etc/nginx/sites-available/kinetix.sqasa.co`.
- **Comando real de uvicorn**: `docker inspect jmeter_backend` — puede diferir del compose
  (precedente: el target del frontend se cambió a mano y solo vive en el servidor).
- **Subred de la red**: `docker network inspect` de `jmeter_network`, para fijar
  `--forwarded-allow-ips` con el valor correcto.
- **Binding real del 8001**: `docker port jmeter_backend` + reglas del NSG de Azure.

---

## 5. Para el checklist de despliegue

- [ ] **Bloqueante para un despliegue multiusuario:** sin HF-3, 5 entradas en 15 minutos dejan a
      toda la plataforma sin acceso, con un mensaje que parece un error de contraseña.
- [ ] Cerrar el puerto 8001 a `127.0.0.1` en `docker-compose.prod.yml` (§2).
- [ ] **`ports: []` no cierra nada (§2.b).** Postgres, InfluxDB y Grafana están publicados en
      0.0.0.0 en producción. Rehacer el cierre con `127.0.0.1:<puerto>:<puerto>` y verificar con
      `docker compose … config` **antes** de desplegar.
- [ ] Comprobar en el servidor el doble mapeo del frontend sobre el host 5173 (`docker port
      jmeter_frontend`).
- [ ] Corregir CLAUDE.md §2 y §14, que afirman una protección inexistente.
- [ ] Verificar `X-Forwarded-For` en nginx y los flags de uvicorn en el servidor.
- [ ] Decidir el texto del mensaje de bloqueo (§3.5).

---

## 6. Otras deudas detectadas de paso (no se implementan en la Etapa 3)

- **`tests/test_analysis_pipeline.py::test_pipeline_parsea_jtl_y_popula_metricas_basicas` falla
  desde antes de la Etapa 3.** Parchea `app.services.ai.analysis_pipeline.time`, y ese modulo ya
  no importa `time`. Verificado: falla igual con el arbol limpio en `533bade`. Arreglo previsto:
  quitar ese `patch` del test. Una linea, cuando se toque ese archivo.

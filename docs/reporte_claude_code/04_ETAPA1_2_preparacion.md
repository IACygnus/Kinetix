842d8a2 · 2026-09-15

# ETAPA 1.2 — Preparación de la línea base

**Llamadas reales a la IA en este sub-paso: 0.** Read-only sobre la base y el código.
Ninguna condición de PARADA se activó: el flujo es replicable por API, el JTL existe y el
login funciona.

---

## 1. Metadatos de `ff186cc7-5be0-4a59-957c-e6b6b0fa00f8`

| Campo | Valor |
|---|---|
| `name` | `pruebakinetix` |
| `client_id` | `3505c753-7724-488a-b531-3ff0de501e48` (**iaperformance**) |
| `project` | `pruebakinetix` |
| `test_type` | `load` |
| `metric_unit` | `TPS` |
| `jtl_filename` | `resultados_general_carga_22-dic-2025-150249.jtl` |
| `jtl_filenames` | `null` (un solo archivo) |
| `total_requests` / `duration_seconds` | 10.075 / 300 |

Criterios de aceptación: `concurrency: 30`, `response_time: 2000`, `availability: 99.5`,
más `critical_transactions` y `verdicts_per_transaction`.

**JTL verificado en `/app/uploads`** — `20260915_145650_resultados_general_carga_22-dic-2025-150249.jtl`
(1.382.075 bytes). Existe también una copia de diciembre; el parser resuelve por sufijo, así que
ambas sirven.

## 2. Transacciones de la línea base

Labels reales extraídos con `JTLParser` + `get_summary_table_data` (sin IA):

| Label | Muestras | Promedio ms | Errores | Tasa error |
|---|---|---|---|---|
| 1. Auth | 1.686 | 422,2 | 0 | 0,00 % |
| 2. Get Booking | 1.681 | 220,2 | 0 | 0,00 % |
| 3. Post Create_Booking | 1.678 | 108,7 | 0 | 0,00 % |
| **4. Get_Booking_Id** | 1.677 | 108,3 | 692 | **41,26 %** |
| **5. Put_Update_Booking** | 1.677 | 109,6 | 952 | **56,77 %** |
| **6. Delete_Booking_Id** | 1.676 | 107,9 | 1.197 | **71,42 %** |

**Selección: `4. Get_Booking_Id`, `5. Put_Update_Booking`, `6. Delete_Booking_Id`.**

Los dos criterios del enunciado **convergen**: son las nombradas (con prefijo numérico, que es
su nombre real en el JTL) **y** las 3 de mayor tasa de error. Selección inequívoca, sin necesidad
de aplicar la regla de desempate. Coinciden además con las `critical_transactions` que la
ejecución original ya tenía guardadas.

## 3. Flujo exacto del botón "Generar"

**Hallazgo importante:** salvo `files`, **todos los campos viajan como query params**, no como
campos del multipart (`upload.py:324-333` los declara `Query(...)`).

```
POST /api/v1/upload
  ?name=&description=&test_type=&client=&project=&client_id=&acceptance_criteria=&metric_unit=
  multipart body: files (1..5)
  header: X-CSRF-Token
```

Orden y origen (`UploadJTL.tsx:289-307` → `api.ts:198-220`):

1. El frontend arma `acceptanceCriteria` como **JSON string** con `concurrency`,
   `response_time`, `availability`, y de forma **aditiva** `per_transaction` y
   `critical_transactions` — estas dos claves **solo se emiten si hay selección**
   (`UploadJTL.tsx:292-294`).
2. **Las transacciones seleccionadas viajan dentro de ese JSON**, en
   `critical_transactions`. No hay un campo aparte.
3. `testAPI.uploadJTL` mete los ficheros en `FormData` y el resto en `URLSearchParams`.
4. La respuesta de `/upload` trae `id` y `ai_status`.
5. El disparo de los mini-informes es **posterior y en background**
   (`upload.py:873`, `asyncio.create_task`): `/upload` **no** los espera.

**Premarcado automático de críticas:** no existe un premarcado que se envíe solo. Si el usuario
no selecciona nada, la clave `critical_transactions` **no se emite** y no se genera ningún
mini-informe (`upload.py:870-873` devuelve lista vacía y no crea tarea). Esto es justo lo que
hace falta para el paso 3 del guion de prueba de Fredy (desmarcar todo).

**Fin de la ÚLTIMA transacción:** `GET /executions/{id}/transaction-reports/status` devuelve
`status: "completed"` **solo cuando todas** las labels pedidas están en `completo` o `parcial`
(`upload.py:1044-1051`). Ese es el T2. El estado se deriva de las filas de
`transaction_chart_analyses`, no de memoria, así que es fiable con varios workers.

## 4. Autenticación por API

`POST /api/v1/auth/login` con `OAuth2PasswordRequestForm` (FormData `username`/`password`).
Devuelve dos cookies httpOnly: **`access_token`** y **`csrf_token`**. Toda petición de mutación
exige el par cookie `csrf_token` + header `X-CSRF-Token` (`main.py:62-70`); el login está exento.

Validado en ejecución: login OK, ambas cookies presentes. **Las credenciales no se escriben en
ningún reporte ni en el script** — se leen de la variable de entorno `KX_PWD`.

## 5. Cupos de IA — D7 NO aplica

| Límite | Usado | Disponible |
|---|---|---|
| Diario: 1.000 | 53 | **947** |
| Mensual: 20.000 | 107 | **19.893** |

Sobra de largo para las ~70 llamadas autorizadas. **No se modifica ningún límite.**

## 6. JTL para la prueba de Fredy

`C:\proyectos\Kinetix_pruebas\prueba1509.jtl` — 133.049 bytes, copia byte a byte del JTL de
`c8225ead` (`prueba1509`). Es un JTL en formato XML. Carpeta creada fuera del repositorio.

## 7. Script de corrida

`C:\proyectos\Kinetix_pruebas\etapa1_corrida.py` (fuera del repo, no se commitea).

**Decisión técnica declarada:** el host **no tiene Python** (`which python/python3/py` → nada),
así que el script se ejecuta **dentro de `jmeter_backend`**, que ya trae python3 y httpx.
Ventaja añadida y no menor: la sonda golpea **el mismo proceso uvicorn** que genera el informe,
que es exactamente la condición en la que el bloqueo del event loop (H4) se hace visible.

Qué hace: login + CSRF → `POST /upload` replicando los 8 query params y el multipart →
registra **T0** (envío), **T1** (respuesta de `/upload`), **T2** (primer `status: "completed"`,
por polling cada 5 s) → sonda `GET /auth/me` cada 2 s en un hilo aparte desde T0 hasta T2+5 s →
vuelca JSON sin secretos.

### Validación sin generar informe (`--solo-sonda`, 10 s)

```
[login] OK (cookies: access_token, csrf_token)
[modo] solo sonda 10 s, SIN generar informe
{"n": 5, "errores": 0, "min_ms": 3.1, "max_ms": 30.5, "p95_ms": 4.4, "media_ms": 9.0}
```

Login, CSRF y sonda funcionan. **Esta es la referencia de "backend no bloqueado": p95 ≈ 4,4 ms.**
Contra este número se comparará la sonda durante el bloque general en 1.3 y 1.6.

---

## Estado

Sub-paso 1.2 completado, sin paradas. Se continúa con 1.3 (corrida 1, ~35 llamadas reales).

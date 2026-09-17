181bd5e · 2026-09-17

# ETAPA H1 — Cierre: modelo de datos, Actividades y Proyectos

**0 llamadas a la IA en toda la etapa.** El módulo de horas no usa IA en ningún punto; el
presupuesto era 0 y se cumplió sin acercarse.

Referencia: `docs/ESPECIFICACION-horas.md` v1.0.

---

## 1. Qué pedía la etapa y qué quedó

| Decisión | Qué pedía | Estado |
|---|---|---|
| **H-D1** | Todas las tablas nuevas, sin ALTER | Hecho. 7 tablas, la base pasó de 18 a 25 |
| **H-D2** | `clients` compartida sin cambios, sin aplicar asignaciones | Hecho. Verificado columna a columna |
| **H-D3** | Catálogo global con las 5 iniciales, nombre único normalizado | Hecho y sembrado |
| **H-D4** | Con horas no se borra: se desactiva | Hecho, en backend y en pantalla |
| **H-D5** | Jornada L-J 8,5 / V 8,0 y festivos 2026-2027 por lista literal | Hecho. 40 festivos |
| **H-D6** | Proyectos manuales, ninguno sembrado | Hecho |
| **H-D7** | Sin usuarios ni roles nuevos | Hecho |
| **H-D8** | Horas en pasos de 0,25, backend y frontend | Hecho, y también en la base |
| **H-D9** | `/horas` en el frontend, `/time` en el backend | Hecho |
| **H-D10** | Menú nuevo con Proyectos y Actividades | Hecho |
| **H-D11** | Cada cambio de estimación escribe historial | Hecho, incluidas altas y bajas |
| **H-D12** | Con horas, la actividad no se quita del proyecto | Hecho |

## 2. Los sub-pasos

| Sub-paso | Reporte | Commit |
|---|---|---|
| H1.1 Diagnóstico (read-only) | 62 | `4a61f7c` |
| H1.2 Modelo de datos y siembra | 63 | `1a2036c` |
| H1.3 Backend de Actividades y Proyectos | 64 | `0c3f50a` |
| H1.4 y H1.5 Las dos pantallas | 65 | `181bd5e` |
| H1.6 Cierre | 66 (este), 67 | — |

## 3. Lo que se construyó

**Backend** — 5 archivos nuevos, ninguno protegido:

```
db/models/time_tracking.py        7 tablas + normalizar()
db/seed_time_tracking.py          siembra idempotente
schemas/time_tracking.py          validación del paso 0,25 y de §3
api/v1/endpoints/time_activities.py
api/v1/endpoints/time_projects.py
tests/test_time_tracking_reglas.py
```

**Frontend** — 3 archivos nuevos, ninguno protegido:

```
api/horasApi.ts                   cliente de /time, formato español y esPasoValido
pages/horas/ActividadesPage.tsx
pages/horas/ProyectosPage.tsx
```

Y tres archivos existentes con cambios pequeños: `main.py` (+11), `api.py` (+10),
`App.tsx` (+9), `Sidebar.tsx` (+23).

**Ningún archivo protegido se tocó en toda la etapa.** No se activó ninguna condición de
parada.

## 4. Verificación

**75 comprobaciones propias de la etapa**, todas pasan.

| Prueba | Qué mira | Resultado |
|---|---|---|
| SQL directo | las 7 tablas, la siembra corrida dos veces, y que las restricciones **rechacen de verdad** (0,3 horas, estimación 0, nombre duplicado) | PASA |
| `diff` de esquema | `test_executions`, `clients` y `users` **idénticos** antes y después, 68 columnas | PASA |
| `h13_backend.sh` | 24 comprobaciones por HTTP sobre los dos endpoints | TODO PASA |
| `test_time_tracking_reglas.py` | 29 tests: el 403 del analyst, normalización, pasos de 0,25 y reglas de `ProjectCreate` | 29 pasan |
| `h15_pantallas.py` | 22 comprobaciones de las dos pantallas con Playwright | TODO PASA |

### El módulo de análisis no se movió

Es la regresión obligatoria de H1.6, y es la que de verdad importa: el módulo de horas
comparte base de datos y aplicación con el de análisis.

| Prueba | Resultado |
|---|---|
| `verificar_etapa2.py` — diez pasos, **las cuatro salidas** | **LAS CUATRO SALIDAS PASAN** |
| `criterios_5b2.py` (Etapa 5b) | TODO PASA |
| `export_alcance.py` (Etapa 6.3) | TODO PASA |
| `integrado_completo_73.py` (Etapa 7) | TODO PASA |
| `pytest tests/` | **521 pasan**, 1 falla — la anterior al plan |
| `npx tsc --noEmit` | sin errores |

Eran 492 tests antes de esta etapa; ahora 521, con los 29 nuevos. La única falla sigue
siendo `test_analysis_pipeline.py::test_pipeline_parsea_jtl_y_popula_metricas_basicas`, que
falla desde antes del plan de corrección y está documentada en el checklist de despliegue.

## 5. Decisiones técnicas declaradas a lo largo de la etapa

| Decisión | Justificación |
|---|---|
| `Numeric` y no `Float` para todas las horas | se suman; un `float` acumula error y la comparación consumido/estimado acabaría mintiendo |
| `weekday` 0 = lunes … 6 = domingo | el mismo criterio que `date.weekday()`: no hay que traducir en cada consulta |
| Festivos y ausencias en la misma tabla | se consultan igual al decidir si un día se reclama como incompleto (§4.2.7) |
| `normalizar()` en el modelo, junto a las columnas que la guardan | la usan el catálogo y usará la importación de H4; en un solo sitio no pueden divergir |
| Las actividades del proyecto van por su propio endpoint | así ningún cambio de estimación se salta el historial |
| Si la estimación no cambia, no se escribe historial | una fila "de 10 a 10" es ruido, no rastro |
| La estimación se guarda en el `blur`, no por tecla | por lo mismo |
| El botón de borrar se deshabilita **con el motivo escrito** | dice la regla antes de que el usuario la choque |
| Índice **parcial** único para los festivos nacionales | con `user_id` nulo, un `UNIQUE(date, user_id)` no protege: en Postgres varios `NULL` no chocan |

## 6. Una comprobación que no se pudo hacer por HTTP

El **403 de un analyst al cerrar un proyecto** (§8) no se probó con `curl`: hace falta la
contraseña de otra persona y no la tengo ni la voy a pedir. Se cubrió en `pytest`, probando
el guardia real `require_role(["admin"])`, que además no depende de ninguna credencial.
Queda escrito en el reporte 64.

## 7. Una línea de despliegue, y sigo

Las siete tablas las crea `create_all` al arrancar el backend: **en el servidor no hay que
ejecutar ningún SQL**. Es la diferencia con `reasoning_effort` de la Etapa 2, que era una
columna sobre una tabla existente. Nada más que anotar.

## 8. Lo que queda para H2 en adelante

- **H2** — registro de horas: la vista semanal, los días incompletos y las horas extra.
  `time_entries` ya existe con su estructura completa y el contrato del detalle de proyecto
  ya devuelve `consumed_hours`: **no habrá que cambiar el esquema ni la respuesta**.
- **H3** — consulta de proyectos.
- **H4** — importación del archivo, que reusará `normalizar()`.
- **Reportes** — cuando llegue su etapa habrá que decidir si se reutiliza
  `report_generator.py`, que **es archivo protegido**, o se escribe un generador propio.
  Señalado desde el diagnóstico (reporte 62 §6).

---

**Estado: Etapa H1 implementada, pendiente validación de Fredy.**

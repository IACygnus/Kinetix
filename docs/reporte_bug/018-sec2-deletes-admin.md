# 018 — SEC-2: todo DELETE destructivo restringido a admin (regla global)

**Fecha:** 2026-08-14
**Estado:** ✅ Implementado y validado con los 3 roles contra los 7 endpoints. Fixtures limpiados (contadores en 0).
**Alcance:** **14 archivos, +82 / −44** — 7 backend (+19/−12) y 7 frontend (+63/−32, solo condicionales de visibilidad).
**Origen:** hallazgo §3 de `017-sec1-delete-admin.md`. **Decisión de Fredy:** borrar = solo admin en toda la plataforma; **editar no se toca**.
**Numeración:** había 17 reportes → este es el **018**.

`py_compile` OK (7) · `tsc --noEmit` **exit 0** · backend reiniciado sin build · backups `.bak_sec2_20260814_153518`.

---

## 1. Backend — 7 endpoints ajustados

Mismo patrón que SEC-1, dos líneas por archivo (import + `Depends`):

```python
    # SEC-2: borrar es exclusivo de admin en toda la plataforma.
    current_user=Depends(require_role(["admin"])),
```

| # | Endpoint | Antes | Ahora |
|---|---|---|---|
| 8 | `DELETE /{execution_id}/attachments/{attachment_id}` | solo autenticado | **admin** |
| 9 | `DELETE /reports/integrated-reports/{id}` | solo autenticado | **admin** |
| 10 | `DELETE /data-files/{id}` | solo autenticado | **admin** |
| 11 | `DELETE /scripts/{id}` | solo autenticado | **admin** |
| 12 | `DELETE /scenarios/{id}` | solo autenticado | **admin** |
| 5 | `DELETE /script-designer/ai/designs/{id}` | admin, analyst | **admin** |
| 6 | `DELETE /…/designs/{id}/data-files/{id}` | admin, analyst | **admin** |

> **Detalle de implementación:** en los 5 archivos que no importaban el modelo `User` se omitió la anotación de tipo (`current_user=Depends(...)` en vez de `current_user: User = Depends(...)`). Es puramente cosmética para FastAPI, y evita añadir un import por archivo solo para el type hint. Donde `User` ya estaba importado (los dos del Diseñador IA) se conservó la anotación.

### Tabla de auditoría completa — los 12 DELETE con su rol FINAL

| # | Endpoint | Rol final | Destructivo |
|---|---|---|---|
| 1 | `/executions/{id}` | **admin** | Sí (SEC-1) |
| 2 | `/clients/{id}` | **admin** | Sí |
| 3 | `/clients/assignments/{user}/{client}` | **admin** | No |
| 4 | `/clients/{id}/logo` | **admin** | Menor |
| 5 | `/script-designer/ai/designs/{id}` | **admin** ← SEC-2 | Sí |
| 6 | `/…/designs/{id}/data-files/{id}` | **admin** ← SEC-2 | Sí |
| 7 | `/performance-executions/{id}/listeners-state-cache` | admin, analyst | **No — caché** |
| 8 | `/{execution_id}/attachments/{attachment_id}` | **admin** ← SEC-2 | Sí |
| 9 | `/reports/integrated-reports/{id}` | **admin** ← SEC-2 | Sí |
| 10 | `/data-files/{id}` | **admin** ← SEC-2 | Sí |
| 11 | `/scripts/{id}` | **admin** ← SEC-2 | Sí |
| 12 | `/scenarios/{id}` | **admin** ← SEC-2 | Sí |

**11 de 12 son admin-only. Cero DELETE sin control de rol.**

La única excepción es el **#7**, y es deliberada: no borra datos de usuario, limpia una caché de estado de listeners. Entraba en el grupo "1-7 no se tocan" de tu instrucción y no es destructivo, así que conserva `admin, analyst`. Dime si quieres uniformidad absoluta y lo cambio en una línea.

---

## 2. Validación — 7 endpoints × 3 roles

Fixtures creados para esto (prefijo `SEC2TEST`): cliente, `viewer` y `analyst` **asignados a ese cliente**, ejecución, adjunto, informe integrado, script, data file, escenario, diseño IA y su CSV.

| Endpoint DELETE | viewer | analyst | admin |
|---|---:|---:|---:|
| 8. `/executions/{id}/attachments/{id}` | **403** | **403** | 200 |
| 9. `/reports/integrated-reports/{id}` | **403** | **403** | 204 |
| 10. `/data-files/{id}` | **403** | **403** | 204 |
| 11. `/scripts/{id}` | **403** | **403** | 204 |
| 12. `/scenarios/{id}` | **403** | **403** | 204 |
| 5. `/script-designer/ai/designs/{id}` | **403** | **403** | 204 |
| 6. `/…/designs/{id}/data-files/{id}` | **403** | **403** | 204 |

> **Nota honesta sobre el método:** en la primera pasada, los endpoints **12** y **6** devolvieron 404 al admin. No era un fallo del endpoint: fue **mi orden de pruebas** — había borrado antes el script (#11) y el diseño (#5), que arrastran en cascada el escenario y el CSV del diseño. Los repetí con fixtures frescas y en orden correcto, y ambos dieron **204**. La tabla de arriba refleja las corridas válidas.

### No-regresión — leer, crear y editar siguen igual para los 3 roles

| Operación | viewer | analyst | admin |
|---|---:|---:|---:|
| `GET /scripts/{id}` | 200 | 200 | 200 |
| `PUT /scripts/{id}` (editar) | 200 | 200 | 200 |
| `GET /scenarios/` | 200 | 200 | 200 |
| `POST /scenarios/` (crear) | 201 | 201 | 201 |
| `GET /reports/integrated-reports` | 200 | 200 | 200 |
| `PATCH` informe integrado (editar) | 200 | 200 | 200 |
| `GET` adjuntos de la ejecución | 200 | 200 | 200 |

**Solo cambió el borrado.** Editar sigue gobernado por el acceso al cliente, tal como decidiste.

### Limpieza

```
restos: {AIDesignDataFile:0, AIScriptDesign:0, Scenario:0, DataFile:0, ScriptDesign:0,
         IntegratedReport:0, TestExecution:0, ExecutionAttachment:0, User:0, Client:0} | TOTAL: 0
```

Confirmado también por SQL directo (`users, clients, executions, scenarios, scripts, informes` → todos **0**). Script de fixtures borrado del contenedor y del host. **Ningún dato real tocado.**

> El teardown necesitó un ajuste: SQLAlchemy reordena los DELETE dentro de un mismo flush y rompía la FK `test_executions → clients`. Se resolvió con un commit por grupo. Lo anoto porque afecta a cualquier script de limpieza futuro.

---

## 3. Frontend — 8 botones condicionados

Ninguno de los 7 archivos usaba `useAuth` antes; ahora todos gatean con `user?.role === 'admin'`, el mismo patrón de `History.tsx:343`. **Cero cambios de lógica: solo visibilidad.**

| Archivo | Botón | Línea |
|---|---|---|
| `components/dashboard/AttachmentSection.tsx` | Eliminar adjunto | 202 |
| `pages/EvidencePage.tsx` | Eliminar evidencia | 222 |
| `pages/MonitoringPage.tsx` | Eliminar imagen de monitoreo | 227 |
| `pages/IntegratedReportsHistory.tsx` | Eliminar informe integrado | 374 |
| `pages/AIDesignerHistory.tsx` | Eliminar diseño IA | 374 |
| `components/script-designer/DataFileManager.tsx` | Eliminar CSV | 111 |
| `pages/AIScriptEditor.tsx` | Eliminar CSV (panel de lista) | 6187 |
| `pages/AIScriptEditor.tsx` | Eliminar archivo (panel de detalle) | 6339 |

`AIScriptEditor.tsx` tiene dos componentes distintos con botón de borrado (`DataFilesPanel` y `DataFileDetailPanel`); cada uno llama a `useAuth()` en su propio cuerpo, antes de cualquier return.

**Sin botón que ocultar:** `scriptApi.delete` (`/scripts/{id}`) y `scenarioApi.delete` (`/scenarios/{id}`) están definidos en la capa de API pero **no tienen ni un solo consumidor en la UI** (0 coincidencias). El endpoint queda protegido igual; simplemente hoy no hay botón que condicionar.

---

## 4. Historial

```
$ git log --oneline -1
36c1a2e SEC-2: todo DELETE destructivo restringido a admin (regla global de Fredy)
```

Anteriores: `89dbccc` (SEC-1) · `24eb0a5` (R1) · `0dc5cd4` (F5) · `4ed0957` (UI-2).

---

## 5. Validación visual para Fredy

1. **Como admin:** los 8 botones siguen visibles y funcionan (adjuntos en Evidencias y Monitoreo, informes integrados, diseños IA, CSVs del Diseñador).
2. **Como analyst** (`ruben`, `Moni`, `adrian`): ninguno de esos botones aparece; y si alguien llama a la API a mano, recibe **403**.
3. **Como analyst, comprobar que NO se perdió nada más:** subir evidencias, editar análisis, crear/editar scripts y escenarios, generar informes y exportar siguen funcionando igual.

---

## 6. Higiene

- `origin` (producción) **no se tocó**. Push únicamente a `github backup-trabajo-local`.
- 14 backups `.bak_sec2_20260814_153518`.
- `docker restart jmeter_backend` sin build · HMR en el frontend · `health=200`.
- **Ningún análisis IA ejecutado** — cuota intacta.
- Datos: solo fixtures `SEC2TEST`, creadas y borradas. **Cero registros reales afectados.**

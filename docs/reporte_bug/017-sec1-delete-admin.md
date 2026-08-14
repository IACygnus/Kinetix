# 017 — SEC-1: DELETE de ejecuciones restringido a admin + auditoría de endpoints destructivos

**Fecha:** 2026-08-14
**Estado:** ✅ Implementado y validado con curl sobre los 3 roles. Fixtures limpiados.
**Alcance:** **1 archivo** — `endpoints/upload.py`, **+4 / −2 líneas**. Presupuesto ~10-20 / máx 3 archivos.
**Origen:** hallazgo lateral del §6 de `graf1-fix-serie-dual.md` (salvaguarda de la ejecución `4b4e5977`).
**Numeración:** había 16 reportes → este es el **017**.

---

## 1. El fix (punto 1)

```diff
-from app.core.security import get_current_active_user
+from app.core.security import get_current_active_user, require_role
...
 @router.delete("/executions/{execution_id}")
 async def delete_execution(
     execution_id: str,
     db: AsyncSession = Depends(get_db),
-    current_user: User = Depends(get_current_active_user),
+    # SEC-1: borrar ejecuciones queda restringido a admin. Antes bastaba con
+    # tener el cliente asignado, asi que un viewer podia borrarlas.
+    current_user: User = Depends(require_role(["admin"])),
 ):
-    """Eliminar una ejecucion (con verificacion de acceso)"""
+    """Eliminar una ejecucion (solo admin, con verificacion de acceso)"""
```

Mismo patrón exacto que `clients.py` (8 usos de `require_role(["admin"])`). `_check_execution_access` se conserva: ahora hay **dos** filtros —rol y luego pertenencia del cliente—, no uno reemplazando al otro.

---

## 2. Validación — los 3 roles contra el endpoint real

Fixtures creados para esto (cliente, un `viewer` y un `analyst` **asignados a ese cliente**, y una ejecución de prueba con ese `client_id`). El detalle importa: con el cliente asignado, **antes de SEC-1 el viewer habría recibido 200** — es exactamente el escenario del hallazgo.

| Usuario | Rol | login | GET ejecución | PUT análisis | **DELETE** |
|---|---|---:|---:|---:|---:|
| `sec1test_viewer` | viewer | 200 | 200 | 200 | **403** |
| `sec1test_analyst` | analyst | 200 | 200 | 200 | **403** |
| `admin` | admin | 200 | 200 | 200 | **200** |

```
viewer  → {"detail":"Acceso denegado. Se requiere rol: admin"}
analyst → {"detail":"Acceso denegado. Se requiere rol: admin"}
admin   → {"success":true,"message":"Ejecucion eliminada correctamente"}
```

**No-regresión:** `GET /executions/{id}` y `PUT /executions/{id}/analysis` siguen respondiendo **200 para los tres roles** — solo cambió el DELETE.

**Limpieza:** teardown verificado → `usuarios:0 clientes:0 ejecuciones:0` con el prefijo de prueba; script de fixtures borrado del contenedor y del host. **Ninguna ejecución real fue tocada.**

---

## 3. Auditoría read-only de TODOS los DELETE del backend (punto 2)

12 endpoints `@router.delete` en `backend/app`:

| # | Endpoint | Rol exigido hoy | ¿Destruye datos de usuario/evidencia? |
|---|---|---|---|
| 1 | `DELETE /executions/{id}` | **admin** ← *este fix* | **Sí** — la ejecución y, en cascada, sus adjuntos |
| 2 | `DELETE /clients/{id}` | admin | Sí — cliente (sus ejecuciones NO se arrastran: FK NO ACTION) |
| 3 | `DELETE /clients/assignments/{user}/{client}` | admin | No — solo el permiso |
| 4 | `DELETE /clients/{id}/logo` | admin | Menor — el logo |
| 5 | `DELETE /script-designer/ai/designs/{id}` | admin, analyst | Sí — diseño de script |
| 6 | `DELETE /…/designs/{id}/data-files/{id}` | admin, analyst | Sí — CSV en disco + registro |
| 7 | `DELETE /performance-executions/{id}/listeners-state-cache` | admin, analyst | No — caché |
| 8 | **`DELETE /{execution_id}/attachments/{attachment_id}`** | ⚠️ **solo autenticado** | **Sí — evidencia/monitoreo: borra el ARCHIVO FÍSICO y el registro** |
| 9 | **`DELETE /reports/integrated-reports/{id}`** | ⚠️ **solo autenticado** | **Sí — el informe integrado completo, con sus overrides editados a mano** |
| 10 | **`DELETE /data-files/{id}`** | ⚠️ **solo autenticado** | **Sí — CSV del disco (`file_path.unlink()`) + registro** |
| 11 | **`DELETE /scripts/{id}`** | ⚠️ **solo autenticado** | **Sí — ScriptDesign completo** |
| 12 | **`DELETE /scenarios/{id}`** | ⚠️ **solo autenticado** | **Sí — escenario de carga** |

### 🔴 Hallazgo: 5 DELETE destructivos sin control de rol **ni de pertenencia**

Los números **8, 9, 10, 11 y 12** dependen solo de `get_current_user`. Los leí uno por uno: **ninguno comprueba rol ni propietario**. El cuerpo es, literalmente, buscar por id → 404 si no existe → borrar.

Consecuencia concreta: **cualquier usuario autenticado, incluido un `viewer`, puede borrar el informe integrado de otro, sus evidencias con archivo físico incluido, sus CSV, sus scripts y sus escenarios** — sin que la ejecución/informe le pertenezca ni tenga el cliente asignado. Ni siquiera hace falta que estén relacionados con él.

El más grave a mi juicio es el **8** (adjuntos): borra evidencia con `unlink()` del archivo — no es recuperable desde la app. El **9** le sigue de cerca, porque un informe integrado acumula horas de edición manual (los overrides de F4/F6).

**No los corregí:** la tarea autoriza un único cambio y estos son decisión de Fredy. Cuando lo decida, la corrección es del mismo tamaño que ésta (una línea por endpoint) y la pregunta a responder por cada uno es qué rol corresponde: `admin` como el 1, o `admin, analyst` como el 5-7.

### Observación adicional (fuera del alcance de SEC-1)

En la tabla de validación se ve que **`PUT /executions/{id}/analysis` responde 200 a un `viewer`**: el rol "viewer" puede **editar** los análisis de una ejecución a la que tenga acceso. Puede ser intencional (el nombre sugiere que no). Lo dejo anotado; no es un DELETE y no entra en esta tarea.

---

## 4. Frontend (punto 3) — ya estaba condicionado, sin cambios

`History.tsx:343` ya envuelve el botón de borrar:

```tsx
{user?.role === 'admin' && (
  <button onClick={() => setDeleteConfirm(exec.id)} title="Eliminar">
    <Trash2 className="w-5 h-5" />
  </button>
)}
```

Es el **único** punto del frontend que llama a `deleteExecution` (`api.ts:195`). **No se tocó nada** y no hizo falta `tsc`.

Esto confirma la naturaleza del bug: el control existía **solo en el cliente**. La UI escondía el botón, pero la API aceptaba el DELETE de cualquiera que supiera la URL — que es justo lo que un control client-side no puede impedir. Ahora el servidor lo rechaza.

---

## 5. Historial

```
$ git log --oneline -1
d3f9c66 SEC-1: DELETE de ejecuciones restringido a admin + auditoria de endpoints destructivos
```

Anteriores: `24eb0a5` (R1) · `0dc5cd4` (F5) · `4ed0957` (UI-2) · `fad4f01` (GRAF1-C).

---

## 6. Validación visual para Fredy

1. Entrar como **admin** al historial de ejecuciones → el botón de borrar sigue visible y **funciona**.
2. Entrar como **analyst** (`ruben`, `Moni` o `adrian`) → el botón **no aparece**, y si alguien llama a la API a mano recibe **403**.
3. Confirmar que ver, exportar y editar análisis siguen funcionando igual para analyst (no se tocó nada de eso).

---

## 7. Higiene

- `origin` (producción) **no se tocó**. Push únicamente a `github backup-trabajo-local`.
- Backup `upload.py.bak_sec1_20260814_144826`.
- `py_compile` OK · `docker restart jmeter_backend` sin build · `health=200`.
- **Ningún análisis IA ejecutado** — cuota intacta.
- Datos: solo se creó y borró el juego de fixtures con prefijo `SEC1TEST`. **Cero ejecuciones reales afectadas.**

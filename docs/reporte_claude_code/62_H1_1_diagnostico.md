2f6bc8e · 2026-09-17

# ETAPA H1.1 — Diagnóstico para el módulo de horas (read-only)

**0 llamadas a la IA** — este módulo no usa IA en ningún punto. Ningún archivo tocado, nada
escrito en la base.

Referencia: `docs/ESPECIFICACION-horas.md` v1.0.

---

## 1. El patrón a seguir: `clients`

Es el módulo más parecido a lo que hay que construir (CRUD sobre tabla propia, con roles), y
el que voy a imitar. Son cuatro piezas:

| Pieza | Archivo | Qué contiene |
|---|---|---|
| Modelo | `db/models/client.py` | `Column(...)` sobre `Base`, `__tablename__`, `UniqueConstraint` en `__table_args__` |
| Schema | `schemas/client.py` | `XCreate` / `XUpdate` / `XResponse` con `ConfigDict(from_attributes=True)` |
| Endpoint | `api/v1/endpoints/clients.py` | `router = APIRouter()`, un `async def` por operación |
| Registro | `api/v1/api.py` | `api_router.include_router(clients.router, prefix="/clients", tags=["clients"])` |

Y una quinta, fácil de olvidar: **el modelo hay que importarlo en `main.py`** (líneas 16-28)
o `create_all` no lo ve. Los trece modelos actuales están ahí, uno por línea.

Detalles del estilo que conviene copiar:

- Identificadores `UUID(as_uuid=True)` con `default=uuid.uuid4`.
- `created_at` / `updated_at` con `datetime.utcnow` y `onupdate`.
- Los nombres únicos se comprueban **antes** de insertar y responden **409**, no 500.
- El endpoint declara su regla de acceso en la firma:
  `current_user: User = Depends(require_role(["admin"]))` o `get_current_active_user`.

## 2. Roles y usuario actual

`core/security.py`:

| Helper | Qué hace |
|---|---|
| `get_current_user` | lee el token de la cookie httpOnly `access_token`, con respaldo en el header `Authorization` |
| `get_current_active_user` | lo anterior + **403** si `is_active` es falso |
| `require_role(["admin"])` | fábrica de dependencia: **403** si `current_user.role` no está en la lista |

Roles existentes: `admin`, `analyst`, `viewer`. **El módulo no crea ninguno** (H-D7).

Traducción directa de §8 de la especificación:

| Acción | Dependencia |
|---|---|
| Ver, crear proyectos y actividades, editar estimaciones | `get_current_active_user` |
| Borrar registros, cerrar proyecto, borrar actividad | `require_role(["admin"])` |

## 3. Frontend: dónde entra el módulo

### `Sidebar.tsx` — **no es archivo protegido** (verificado contra CLAUDE.md §11)

Un array `menuItems: MenuItem[]`, donde cada entrada es:

```ts
{ label: 'Análisis', icon: <FileBarChart …/>, roles?: [...], children: [ { label, path, icon, roles? } ] }
```

Añadir la sección de horas es **un elemento más en ese array** (H-D10). Los iconos salen de
`lucide-react`, que ya está importado; hay que añadir los nuevos a la lista de importación
de las líneas 6-31.

### `App.tsx` — **tampoco es protegido**

Cada ruta va envuelta en `ProtectedRoute`, con `roles` cuando aplica:

```tsx
<Route path="/admin/clients" element={
  <ProtectedRoute roles={['admin']}><ClientsPage /></ProtectedRoute>
} />
```

Las rutas del módulo irán bajo **`/horas`** (H-D9). Sin `roles`, porque en horas **todos ven
todo** (§8); las restricciones son por operación en el backend, no por pantalla.

**Ninguno de los archivos protegidos de §11 entra en esta etapa.** No hay condición de
parada por ese lado.

## 4. `create_all` al arranque — confirmado

`main.py:265-278`:

```python
@app.on_event("startup")
async def startup_event():
    await create_tables()          # Base.metadata.create_all
    await migrate_users_table()
    …
    await seed_admin_user()
```

`create_tables()` ejecuta `Base.metadata.create_all`, que **crea las tablas nuevas sin
intervención** y no toca las existentes. Es exactamente lo que necesita H-D1: las siete
tablas del módulo son nuevas, así que aparecen solas al reiniciar el backend. **Sin ALTER,
sin Alembic, sin script manual.**

> Las funciones `migrate_*` que hay al lado existen precisamente porque `create_all` **no**
> añade columnas a tablas ya creadas. Mientras el módulo solo cree tablas nuevas, no hace
> falta ninguna. Si alguna vez hiciera falta un ALTER sobre una tabla de análisis → PARADA
> (H-D1).

### El patrón de siembra

`seed_admin_user()` (`main.py:203`) es el molde para H-D3 y H-D5: abre una sesión, hace un
`SELECT` para ver si ya existe, inserta solo si falta, y **captura la excepción sin tumbar el
arranque**. La siembra de actividades, jornada y festivos seguirá esa forma, que es
idempotente por construcción.

## 5. Estado de la base local

**Nada se modificó.** Solo `SELECT`.

### `clients` — 8 filas, todas activas (H-D2)

```
Avianca · Bancoomeva · Compensar · Nutresa · Occidente · iaperformance · popular · prueba avianca
```

El selector de cliente del módulo de horas listará estas ocho, **sin aplicar las asignaciones
por usuario** de `user_clients` que sí usa el módulo de análisis (H-D2). Es una diferencia de
comportamiento deliberada entre los dos módulos sobre la misma tabla, y conviene que quede
escrita: en horas, todos ven todos los clientes.

### `users` — 4 filas, todas activas (H-D7)

| username | nombre | rol |
|---|---|---|
| `admin` | Administrador SQA | **admin** |
| `Moni` | Monica Alejandra Archila Cordoba | analyst |
| `adrian` | adrian | analyst |
| `ruben` | ruben dario florez | analyst |

Un solo administrador. Todo lo que §8 reserva a admin —borrar registros, cerrar proyectos,
registrar horas por otros— hoy lo puede hacer únicamente `admin`.

## 6. Dos cosas que anoto, sin actuar

1. **`clients` es ahora una tabla compartida por dos módulos.** Hasta hoy solo la usaba
   análisis. Desde H1 la usan los dos, con reglas de visibilidad distintas (§5). Tiene
   consecuencia para el despliegue de "solo análisis" del reporte 59: los dos módulos
   comparten esa tabla y no se pueden separar por completo. **Una línea, y sigo** — el
   despliegue no es asunto de esta etapa.
2. **El informe de horas (§7.3) pide las mismas reglas de PDF** que el de análisis: solo
   tablas, `mm`/`pt`, sin flex ni grid. Eso apunta a `report_generator.py`, **que es archivo
   protegido**. No es problema de H1 —esta etapa no genera informes—, pero en la etapa de
   reportes habrá que decidir entre reutilizarlo con autorización o escribir un generador
   propio. Queda señalado.

## 7. Presupuesto

| | |
|---|---|
| Llamadas a la IA | **0** de 0 |
| Archivos tocados | **0** |
| Escrituras en base | **0** |

---

**Estado:** H1.1 cerrado. Ninguna condición de parada: las siete tablas son nuevas, ningún
archivo protegido entra en la etapa, y el patrón a seguir está identificado. Sigue H1.2 —
modelo de datos y siembra.

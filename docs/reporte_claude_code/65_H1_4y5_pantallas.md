0c3f50a · 2026-09-17

# ETAPA H1.4 y H1.5 — Las pantallas de Actividades y Proyectos

**0 llamadas a la IA.** La prueba crea sus propios datos y los borra al terminar, incluso si
falla a mitad (regla del reporte 38).

Referencia: `docs/ESPECIFICACION-horas.md` v1.0 §1.2, §3 y §8.

---

## 1. Lo que hay en pantalla

### Menú (H-D10)

Sección nueva **«Horas»** después de «Análisis», con **Proyectos** y **Actividades**. Las de
Registro, Consulta, Reportes e Importación se añaden en H2-H4. Sin `roles`: en horas todos
ven todo (§8), y lo que restringe el rol son las operaciones, que comprueba el backend.

### Actividades (`/horas/actividades`)

Listado con el nombre, en cuántos proyectos está, su estado, y las cuatro acciones:
renombrar en línea, activar/desactivar, crear y borrar.

**Lo que la pantalla tiene que dejar claro** es la regla de H-D4, y para eso el botón de
borrar **se deshabilita con el motivo escrito debajo** en vez de dejar pulsar y devolver un
error:

| Situación | Lo que se lee |
|---|---|
| Tiene horas registradas | *"Tiene horas registradas: desactívala en vez de borrarla."* |
| Está en proyectos, sin horas | *"Está en 2 proyectos."* |
| No eres admin | *"Borrar es exclusivo del administrador."* |

Es la misma distinción que hace el backend, dicha antes de que el usuario lo intente.

### Proyectos (`/horas/proyectos`)

- **Listado** con cliente, nombre, número de actividades, estado, estimadas y consumidas.
  Filtros por cliente, estado y texto.
- **Alta**: cliente, nombre y la tabla de actividades con sus horas. El botón de guardar
  solo se habilita cuando hay cliente, nombre **y al menos una línea válida** — la regla de
  §3 se ve antes de enviarla.
- **Detalle**: la tabla de actividades con estimadas, consumidas y restantes; añadir o quitar
  actividades (H-D12); cerrar o reabrir, **solo si eres admin**.
- **Historial** desplegable con actividad, tipo de cambio, valor anterior, valor nuevo, quién
  y cuándo (H-D11).

**El consumido es 0 en toda la etapa** porque el registro de horas llega en H2. La columna
está desde ahora porque el backend ya la devuelve: así la pantalla no cambia de forma cuando
haya datos.

## 2. Decisiones que declaro

| Decisión | Por qué |
|---|---|
| **La validación del paso 0,25 también en el cliente** (`esPasoValido`) | H-D8 pide las dos. El campo se marca en rojo mientras se escribe, en vez de esperar al 422 del servidor |
| **Las horas se pintan con `toLocaleString('es-CO')`** | §7.3 pide formato español en el módulo. `50.5` se lee **50,5**, no `50.5` |
| **La estimación se guarda en el `blur`, no en cada tecla** | cada cambio escribe una fila de historial (H-D11). Guardar por tecla llenaría el historial de ruido |
| **`AnadirActividad` es un componente propio** | necesita su propio estado y los hooks no pueden vivir dentro de un condicional (regla 16) |
| **El detalle se recarga entero tras cada cambio** | el backend devuelve el detalle completo en cada operación; reusarlo evita que la pantalla calcule totales por su cuenta y se desincronice |

## 3. Verificación — 22 comprobaciones con Playwright, todas pasan

`h15_pantallas.py`, sobre las pantallas reales.

| Bloque | Resultado |
|---|---|
| **1. El menú** — sección «Horas» con Proyectos y Actividades | PASA (3) |
| **2. Actividades** — las cinco sembradas **con sus tildes**; crear una nueva, que nace activa y (sin uso) se puede borrar; desactivar y volver a activar | PASA (7) |
| **3. Crear proyecto** — el botón se habilita con cliente, nombre y dos actividades; se crea y abre su detalle; **el total sale «50,5»**, en español | PASA (3) |
| **4. Historial (H-D11)** — ampliar 40 → 60, el total pasa a **70,5**, y el historial tiene **3 filas** con el cambio arriba, sus dos valores y el autor | PASA (5) |
| **5. Quitar actividad sin horas (H-D12)** | PASA |
| **6. Nombre duplicado** — `"  proyecto h1.5  "` choca con `"Proyecto H1.5"` y se muestra el error | PASA (2) |
| **7. Consola** — **cero errores de JavaScript** | PASA |

Las cinco actividades, tal como se leen en pantalla:

```
Planeación · Diseño y generación de script · Ejecución ·
Análisis de resultados · Administrativas o gerenciales
```

Y la fila del historial, literal:

```
Planeación · cambio · 40 · 60 · Administrador SQA · 17/9/2026, 10:42:53 p. m.
```

> La prueba del nombre duplicado usa **minúsculas y espacios de más** a propósito: así no
> comprueba solo que exista un UNIQUE, sino que la comparación es la **normalizada** (H-D3).

`npx tsc --noEmit`: **sin errores**.

## 4. Archivos

| Archivo | Líneas | Protegido |
|---|---|---|
| `frontend/src/api/horasApi.ts` | **nuevo**, 120 | no |
| `frontend/src/pages/horas/ActividadesPage.tsx` | **nuevo**, 243 | no |
| `frontend/src/pages/horas/ProyectosPage.tsx` | **nuevo**, 447 | no |
| `frontend/src/App.tsx` | +9 | no |
| `frontend/src/components/layout/Sidebar.tsx` | +23 | no |

**Ningún archivo protegido.** Copias de seguridad `*.bak_h1_H1.5_20260917`.

---

**Estado:** H1.4 y H1.5 cerradas. Las dos pantallas funcionan contra el backend real, con
los textos acentuados y las cifras en formato español. Sigue H1.6 — cierre y regresión del
módulo de análisis.

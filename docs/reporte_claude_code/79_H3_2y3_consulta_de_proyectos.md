3e269b5 · 2026-09-17

# ETAPA H3.2 y H3.3 — La consulta de proyectos

**0 llamadas a la IA.** Sin rebuild: la parada de H-D31 no toca nada de esto.

---

## 1. Qué se hizo, y por qué se hizo ahora

H3.1 terminó en parada porque no hay lector de `.xlsx` en el contenedor. **Esa
parada es de la importación (§6), no de la consulta (§5)**: los sub-pasos H3.2 y
H3.3 no dependen de cómo se lea un Excel, y ninguna de las dos salidas posibles
de esa decisión los cambia. Así que se hicieron, quedan cerrados y validados, y
lo que espera a Fredy es la importación entera (H3.4 a H3.7).

| Archivo | Qué es | Líneas |
|---|---|---|
| `backend/app/api/v1/endpoints/time_consulta.py` | **nuevo** — los dos endpoints de §5 | 225 |
| `frontend/src/pages/horas/ConsultaPage.tsx` | **nueva** — la pantalla `/horas/consulta` | 410 |
| `backend/app/schemas/time_tracking.py` | `ConsultaPersona`, `ConsultaProyecto`, `ConsultaResponse` | +55 |
| `frontend/src/components/horas/AvisoDesfase.tsx` | `BarraConsumo` y `AvisoDesfasados` | +51 |
| `frontend/src/api/horasApi.ts` | los tipos y las dos llamadas | +63 |
| `frontend/src/pages/horas/ProyectosPage.tsx` | la barra y el aviso de §5.1 | +26 −5 |
| `App.tsx` · `Sidebar.tsx` · `api.py` | la ruta y la entrada del menú | +9 |

Ningún archivo protegido. Ningún cambio de esquema. Copias de seguridad de los
dos compartidos en `*.bak_h3_*`.

---

## 2. Los dos endpoints (H3.2)

`GET /time/consulta` devuelve, por proyecto, **quién registró y cuántas horas**,
con lo estimado, lo consumido, lo restante y el estado de §5.1. Filtra por
cliente, proyecto, persona y rango.

`GET /time/consulta/dias` devuelve los días de **esa** persona en **ese**
proyecto. Son dos y no uno a propósito: traerlo todo junto significaría cargar
cada registro del rango para enseñar, casi siempre, una sola fila desplegada.

### La decisión que más importa: las dos cifras de horas no son la misma

```
hours_in_range   lo registrado dentro del rango que se consulta
consumed_hours   todo lo que lleva el proyecto, desde siempre
```

**El desfase se mide siempre contra el total.** Si se midiera contra el rango,
consultar una semana tranquila dejaría «en rango» un proyecto que la pantalla de
Proyectos marca como desfasado, y tendríamos dos verdades para el mismo proyecto.
Van en columnas distintas, con nombres distintos, y la pantalla lo dice debajo de
la tabla con todas las letras.

El cálculo del estado sale de `services/horas/desfase.py`, el mismo módulo que
usan Proyectos y el calendario. Tres pantallas, una definición.

Otras dos decisiones, declaradas:

- **Los desfasados salen primero**, y dentro de cada grupo por cliente y
  proyecto: el que hay que mirar no debería quedar al final de una lista larga.
- **La gente, de más a menos horas** dentro de cada proyecto, que es lo que uno
  mira al abrir la consulta.

---

## 3. La pantalla (H3.3)

`/horas/consulta`, con su entrada en el menú de Horas entre Registro y Proyectos.
Arranca en el mes en curso.

**Dos despliegues encadenados, que es la forma que pidió Fredy:**

```
proyecto  →  la gente que registró en él  →  los días de esa persona
```

El primero ya viene en la respuesta; el segundo se pide al desplegarlo. Los días
traen fecha en español, actividad, horas, si se cobra, si fue extra, si está
desfasado y las observaciones.

Arriba, los totales del rango y el aviso de §5.1. Ni un `toISOString()` ni un
`new Date(iso)`: el rango por defecto se calcula con los constructores locales,
como en todo el módulo.

---

## 4. Lo que faltaba de §5.1, cerrado

El reporte 78 anotó que §5.1 pedía tres cosas y H2b entregó una. Las otras dos
están hechas, y en **las dos pantallas** —Consulta y Proyectos— porque salen del
mismo componente:

| Lo que pide §5.1 | Estado |
|---|---|
| El estado por proyecto y por actividad | hecho en H2b.4 |
| «una barra con lo consumido frente a lo estimado» | **hecho**: `BarraConsumo` |
| «un aviso dice cuántos proyectos están desfasados y ofrece un filtro» | **hecho**: `AvisoDesfasados` |

La barra va **con su cifra al lado**: una barra sola no se lee con precisión. Por
encima del 100 % se queda llena y lo que sobra lo dice la etiqueta con su número,
en vez de un rectángulo que se salga de la caja.

---

## 5. Validación — 86 comprobaciones, todas pasan

### `h32_consulta.py` — 53 por HTTP

```
--- las dos cifras de horas NO son la misma ---
PASA  | lo consumido de siempre incluye el dia de fuera del rango: 25.00
PASA  | el total historico es mayor que lo del rango, como debe ser

--- quien registro y cuanto (H-D32) ---
    [('Administrador SQA', '14.00'), ('adrian', '6.00')]
PASA  | con mis 14 h del rango · 10 facturables · 2 extra · en 3 registros

=== 2. El desfase se mide contra el TOTAL (§5.1) ===
PASA  | 'Proyecto H3.2 desfasado': desfasado · «Desfasado +1 h»
PASA  | los desfasados salen primero

=== 3. Los filtros ===
PASA  | por cliente, por proyecto, por persona y solo desfasados
PASA  | rango al reves -> 400
PASA  | un rango sin nada devuelve vacio, no un error

=== 4. Al ampliar la fila, los dias (H-D33) ===
PASA  | ninguno se sale del rango: el de hace un mes no esta
PASA  | el dia desfasado viene marcado
PASA  | sin user_id trae los de todo el mundo (4)
```

El dato que más vale de ahí: hay un registro puesto **un mes antes** del rango
consultado. Aparece en `consumed_hours` y **no** en `hours_in_range`, que es
justo la distinción del punto 2.

### `h33_pantalla.py` — 33 en la pantalla real, con Playwright

```
PASA  | arranca en el mes en curso
PASA  | el filtro deja solo los desfasados · y se vuelve a ver todo
PASA  | se despliega la gente (2) · con mis 14 h · y cuantas se cobran
PASA  | mis tres dias en ese proyecto (3), con sus observaciones
PASA  | las fechas van en espanol · y se pliega otra vez
PASA  | un rango sin horas lo dice, no se queda en blanco
PASA  | Proyectos tiene el aviso de arriba y cada proyecto su barra
PASA  | todos los botones llegan a 44 px · todos los filtros tienen rotulo
PASA  | sin la palabra «exceso» (H-D27) · sin errores de JavaScript
```

### Regresión

| Prueba | Resultado |
|---|---|
| `npx tsc --noEmit` | sin errores |
| `h2b5_pantalla.py` — el calendario de H2b | TODO PASA |
| `h2b2_backend.py` · `h22_backend.py` · `h15_pantallas.py` | TODO PASA |
| `verificar_etapa2.py` — las cuatro salidas | **LAS CUATRO SALIDAS PASAN** |
| `pytest tests/` | **582 pasan**, 1 falla — la anterior al plan (reporte 66) |

---

## 6. Dónde queda la etapa

**H3.2 y H3.3 cerrados.** La consulta de §5 está completa y §5.1 ya no tiene
huecos.

**H3.4, H3.5, H3.6 y H3.7 esperan**, y esperan a una respuesta, no a más trabajo:
la del punto 1 del reporte 78. Sin decidir cómo se lee el `.xlsx` no tiene
sentido escribir el lector, y sin el archivo de muestra tampoco.

**Las dos preguntas siguen siendo las mismas:**

1. ¿`openpyxl` con rebuild del backend, o el lector con biblioteca estándar sin
   rebuild?
2. ¿Me pasas el archivo de horas de muestra?

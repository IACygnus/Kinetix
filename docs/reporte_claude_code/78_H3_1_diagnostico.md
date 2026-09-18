37fed13 · 2026-09-17

# ETAPA H3.1 — Diagnóstico (solo lectura)

**0 llamadas a la IA. No se tocó ni una línea de código.**

---

## 1. H-D31 — ¿se puede leer un `.xlsx` en el contenedor?

**No, por la vía prevista. PARADA declarada.** Pero hay una tercera vía que no
existía en la decisión y que cambia la pregunta, así que va todo medido.

### Lo que hay hoy en `jmeter_backend`

| Motor | Estado |
|---|---|
| `openpyxl` | **no está** |
| `xlrd` · `odf` · `pyxlsb` · `calamine` | **no están** |
| `pandas` 2.1.4 | está, pero sin motor no sirve |

```
1) pandas.read_excel (motor automatico)
   FALLA: ImportError - Missing optional dependency 'openpyxl'.
2) openpyxl directo
   FALLA: ModuleNotFoundError - No module named 'openpyxl'
3) zipfile + ElementTree (biblioteca estandar, sin instalar nada)
   leido: [['Proyecto', 'Horas'], ['Kinetix Pro', '8.5']]
```

La prueba se hizo con un `.xlsx` real construido en memoria (1.753 bytes, con su
tabla de cadenas compartidas), no con un archivo inventado.

`backend/requirements.txt` **no menciona** ninguna de las dos, así que no es que
falte instalar algo declarado: es que nunca estuvo.

### La línea que haría falta

```
openpyxl==3.1.2        # lector .xlsx — pandas 2.1.4 lo pide como motor
```

Eso obliga a `docker compose up -d --build` del backend, y **el ciclo de rebuild
lo controla Fredy** (regla 7). Por eso esto es una parada y no una decisión mía.

### La tercera vía: leerlo sin instalar nada

Un `.xlsx` es un ZIP de XML. La biblioteca estándar de Python trae `zipfile` y
`xml.etree.ElementTree` —la misma que `jtl_parser.py` usa para los JTL en XML— y
**la prueba 3 de arriba lee el archivo de verdad**, con sus cadenas compartidas
resueltas. Sin dependencia, sin rebuild, sin tocar el contenedor.

| | `openpyxl` | `zipfile` + `ElementTree` |
|---|---|---|
| Rebuild del contenedor | **sí**, lo decide Fredy | no |
| Dependencia nueva | sí | **ninguna** |
| Código a escribir | ~10 líneas | ~180 líneas y sus pruebas |
| Lee `.xls` antiguo (Excel 97-2003) | tampoco (haría falta `xlrd`) | no |
| Fechas, cadenas en línea, celdas vacías | resueltas por la librería | **hay que resolverlas a mano** |
| Riesgo | conocido y bajo | el del archivo real, que no he visto |

**Mi recomendación:** `openpyxl`, si Fredy acepta un rebuild del backend. Es una
línea, es el lector estándar y el formato de Excel tiene más esquinas de las que
parece —los números de serie de fecha, el año bisiesto falso de 1900, las cadenas
en línea, las celdas combinadas—. Escribirlas a mano es trabajo que ya está
escrito y probado por otros.

**Si no hay rebuild**, la tercera vía funciona y la implemento sin problema: pido
entonces el archivo de muestra **antes** de escribir el lector, no después.

---

## 2. Lo que H3 no tiene que construir

Bastante de H3 ya está hecho, y es la factura que H1 y H2b dejaron pagada.

| Pieza | Dónde | Para qué sirve en H3 |
|---|---|---|
| `normalizar()` | `db/models/time_tracking.py` | H-D36: comparar nombres sin tildes, sin espacios de más y sin mayúsculas antes de crear un cliente, proyecto o actividad |
| `desfase.py` | `services/horas/` | H-D38 y H-D32: el color y la cifra de la vista previa y de la consulta salen del mismo sitio que los de Proyectos |
| `time_entries.external_id` | tabla `time_entries` | H-D35: `String(100)`, **único** y nullable. En Postgres varios NULL no chocan entre sí, así que los registros manuales conviven con los importados sin estorbarse |
| `time_entries.source` | tabla `time_entries` | H-D39: ya acepta `'manual'` y `'import'`, con su `CHECK` |
| `created_by` | tabla `time_entries` | H-D39: quién importó, distinto de para quién |
| `CHECK (hours*100)::int % 25 = 0` | tabla `time_entries` | H-D40: la última red contra un 0,3 que venga del archivo |
| `validar_paso()` | `schemas/time_tracking.py` | H-D40: el mismo criterio, con mensaje legible |

**Ningún cambio de esquema.** H1 definió la tabla entera pensando en esta etapa
—su propio comentario lo dice— y esa decisión se cobra ahora: no hace falta ni un
`ALTER` (regla 10).

**Ningún archivo protegido.** La consulta y la importación son pantallas nuevas y
endpoints nuevos bajo `/time`.

---

## 3. Lo que sí hay que construir

**La consulta (§5) no se puede montar sobre lo que hay.** `GET /time/entries`
filtra por **una** persona y un rango, y devuelve registros sueltos: no agrupa, no
filtra por cliente ni por proyecto, y no suma por persona. H-D32 y H-D33 piden
justo eso, así que H3.2 necesita su propio endpoint.

**La importación es toda nueva**: los dos endpoints, el lector y la pantalla.

---

## 4. El archivo de muestra: no está

Busqué `.xlsx` y `.xls` en todo el repositorio y **no hay ninguno**. Trabajo con
las once columnas de §6.1, que es lo que la especificación fija:

`Id · Observaciones · Cliente · Proyecto · Tarea · Tipo de hora · Sub Tipo Hora ·
Extra Hour · Fecha · Tiempo total · Facturable`

**Hace falta el archivo real**, y más si se va por la tercera vía del punto 1. Lo
que no se puede adivinar y el archivo contestaría en un minuto:

1. **el formato de `Fecha`** — ¿texto `15/09/2026`, o número de serie de Excel?;
2. **el de `Tiempo total`** — ¿`8,5` con coma, `8.5` con punto, o `8:30` como hora?;
3. **qué dicen exactamente `Extra Hour` y `Facturable`** — ¿`Sí`/`No`, `SI`/`NO`,
   `TRUE`/`FALSE`, `1`/`0`?;
4. **si la primera fila es la de títulos** o hay algo encima;
5. **si el `Id` es numérico o texto**, y si puede venir vacío;
6. **si es `.xlsx` de verdad** o un `.xls` antiguo — el segundo no lo lee ninguna
   de las dos vías sin una dependencia más (`xlrd`).

Cada una de esas seis tiene una respuesta por defecto razonable, pero prefiero
acertar a defenderme después. Con el archivo delante, el lector se escribe una
sola vez.

---

## 5. Un hallazgo de §5.1 que H2b dejó a medias

Leyendo §5 para H-D32 apareció esto, y lo anoto porque es de la especificación,
no una idea mía. §5.1 pide tres cosas del listado de proyectos:

| Lo que pide §5.1 | Estado |
|---|---|
| El estado por proyecto y por actividad | **hecho** en H2b.4 |
| «una barra con lo consumido frente a lo estimado» | **falta** — hoy es el porcentaje en texto |
| «Arriba, un aviso dice cuántos proyectos están desfasados y ofrece un filtro para ver solo esos» | **falta** |

No es un defecto de lo entregado —lo que hay funciona y está probado—, es que
faltan dos piezas de la misma sección. Son pequeñas y caen dentro del §5 que esta
etapa cubre, así que **propongo cerrarlas en H3.3**, junto a la pantalla de
consulta. Queda declarado aquí por si Fredy prefiere que no se toque Proyectos
mientras lo valida.

---

## 6. Dónde queda la etapa

**H3.1 termina en PARADA por H-D31, como la propia decisión manda.** No se instaló
nada ni se reconstruyó nada.

Lo que **no** depende de esa respuesta —la consulta de §5, sub-pasos H3.2 y
H3.3— sigue adelante en este mismo turno: ninguna de las dos vías del punto 1 la
cambia. Lo que sí espera es la importación entera (H3.4 a H3.6) y, con ella, el
cierre.

**Lo que necesito de Fredy, en dos preguntas:**

1. ¿`openpyxl` con rebuild del backend, o el lector con biblioteca estándar sin
   rebuild?
2. ¿Me pasas el archivo de horas de muestra?

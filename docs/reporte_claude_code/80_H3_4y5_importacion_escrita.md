d388a34 · 2026-09-17

# ETAPA H3.4 y H3.5 — La importación: escrita, pendiente del rebuild

**0 llamadas a la IA.** El código está entero y el `pytest` del lector pasa; lo
que falta para validarlo de punta a punta son **dos cosas de Fredy**, al final.

---

## 1. Lo que hay

| Archivo | Qué es | Líneas |
|---|---|---|
| `backend/app/services/horas/importacion.py` | **nuevo** — el lector: títulos, fechas, horas, sí/no, textos | 307 |
| `backend/app/api/v1/endpoints/time_import.py` | **nuevo** — `/preview` y `/confirm` | 383 |
| `backend/tests/test_horas_importacion.py` | **nuevo** — 83 tests del lector | 251 |
| `frontend/src/pages/horas/ImportarPage.tsx` | **nueva** — `/horas/importar` | 435 |
| `backend/app/schemas/time_tracking.py` | los cinco schemas de la importación | +70 |
| `frontend/src/api/horasApi.ts` | tipos y las dos llamadas | +82 |
| `backend/requirements.txt` | `openpyxl==3.1.2` con su comentario | +5 |
| `App.tsx` · `Sidebar.tsx` · `api.py` | la ruta y la entrada del menú | +8 |

Ningún archivo protegido. Ningún cambio de esquema: `external_id`, `source` y
`created_by` ya estaban desde H1.

---

## 2. El lector, partido en dos a propósito

**Interpretar un valor** —una fecha, unas horas, un «Sí»— son funciones puras que
no saben qué es Excel. **Abrir el libro** es lo único que necesita `openpyxl`, y
lo importa dentro de la función, no arriba.

No es estética: las reglas H-D42 a H-D46 son las que se rompen en silencio cuando
el archivo cambia de origen, y así **se prueban sin fabricar un `.xlsx` en cada
test**. Los 83 tests corren hoy, sin la librería instalada. Ese es también el
motivo de que H3.4 esté escrito antes del rebuild y no después.

| Decisión | Cómo quedó |
|---|---|
| **H-D42** títulos | `normalizar()` de H1 — la misma que evita duplicar un cliente por una tilde. `"Cliente "` con espacio final entra sin más |
| **H-D43** fecha | `dd/mm/aaaa`, `aaaa-mm-dd`, número de serie de Excel y fecha ya tipada. Lo demás, fila inválida con su motivo |
| **H-D44** horas | número o texto, con punto o con coma. El paso de 0,25 lo dice `validar_paso()` |
| **H-D45** sí/no | `Si`/`Sí`/`SI`/`S`/`true`/`1`/`x` → sí; el resto → no |
| **H-D46** observaciones | saltos de línea y espacios raros (U+202F, U+00A0, U+2009, U+2007, U+200B) a espacio normal. **Nunca invalida la fila** |
| **H-D47** hoja | la primera. Si el libro trae varias, la vista previa lo dice en ámbar |

**Tres decisiones que tomé y declaro:**

1. **`Facturable` es columna obligatoria**, aunque una celda vacía cuente como
   «no» (H-D45). Que falte la columna entera importaría un mes completo como no
   facturable sin que nadie lo hubiera decidido, y eso es dinero. `Id`,
   `Observaciones` y `Extra Hour` sí son opcionales: su ausencia tiene un valor
   por defecto que no engaña.
2. **Los seriales de Excel por debajo de 61 se rechazan.** Excel cree que 1900
   fue bisiesto y los 60 primeros están corridos un día. Nadie registra horas en
   enero de 1900: mejor rechazarlos que inventarse la fecha.
3. **Una fecha futura es fila inválida**, el mismo criterio que H-D21 en el
   registro a mano.

---

## 3. Los dos endpoints, un solo análisis

```
POST /time/import/preview    analiza y NO escribe nada
POST /time/import/confirm    analiza otra vez y aplica, en una transacción
```

Los dos llaman a `_analizar()`. **Es el punto entero de la vista previa**: si la
previa se calculara con un código y la escritura con otro, acabarían diciendo
cosas distintas y la previa dejaría de servir para decidir, que es para lo único
que existe (§6.2.5).

Lo que decide `_analizar()`, fila a fila: si se crea o se actualiza (por
`external_id`, H-D35), qué cliente / proyecto / actividad hay que crear (H-D36,
H-D48), si la fila no entra y por qué (H-D40) y **cómo queda el desfase de esa
actividad si entra** (H-D38), acumulando las horas del propio archivo.

Cuatro detalles que no se ven pero importan:

- **Un `Id` repetido dentro del mismo archivo** invalida la segunda fila. Si
  entraran las dos, el índice único de `external_id` tumbaría la transacción y no
  entraría nada.
- **Al actualizar, el dueño del registro cambia** a la persona elegida. Es la
  decisión recuperable: si la primera importación se hizo con la persona
  equivocada, reimportar con la correcta es la única forma de arreglarlo desde la
  pantalla. La vista previa marca esas filas.
- **`MAX_BYTES = 5 MB` y `MAX_FILAS = 20.000`**, declarados: un mes de una
  persona son ~25 filas y un año del equipo unas 3.000.
- **H-D41**: un solo `commit`, con `rollback` en cualquier fallo. O entra todo lo
  válido o no entra nada.

---

## 4. Dos defectos que H-D37 destapó, y se arreglaron

H-D37 dice que un proyecto creado por la importación **nace sin horas
estimadas**. Al implementarlo aparecieron dos cosas que ya estaban mal:

1. **`_excedidas` marcaba desfase sin estimación.** Comparaba `consumido >
   estimado` con `estimado = 0` cuando no había estimación, así que **cada fila
   importada habría salido en ámbar** por haberse pasado de cero — justo lo
   contrario de lo que dice H-D37 y de lo que ya hacía `desfase.py`. Las dos
   definiciones discrepaban desde H2; ahora dicen lo mismo.
2. **El detalle de un proyecto escondía horas.** Sumaba solo las actividades con
   estimación, así que un proyecto recién importado habría enseñado 0 consumidas
   teniendo horas. Ahora las actividades con horas y sin estimar salen con
   estimadas 0 —y `desfase.py` las deja en rango—, y el total no miente.

No se puede crear el enlace proyecto-actividad con 0 horas: la base lo prohíbe
(`CHECK estimated_hours > 0`), y está bien que lo prohíba. Por eso el arreglo va
por el lado de quien lee, no por el de quien escribe.

---

## 5. La pantalla (H3.5)

`/horas/importar`, con su entrada en el menú. Tres estados y en este orden, sin
atajos:

```
elegir archivo  →  VISTA PREVIA  →  confirmar  →  resumen
```

La previa viene en secciones: **se va a crear** (clientes, proyectos,
actividades, con el aviso de que los proyectos nacen sin horas), **no se
importan** (con el número de fila del archivo y el motivo), **quedan
desfasadas**, **se actualizan** y **se crean**. Las filas se enseñan enteras: es
lo que hay que revisar antes de decir que sí.

El resumen final lleva **un enlace por cada proyecto creado** (H-D37) para ir a
ponerle sus horas.

---

## 6. Validación

| Prueba | Resultado |
|---|---|
| `test_horas_importacion.py` | **83 pasan** — títulos, fechas, horas, sí/no, textos e Id |
| `pytest tests/` | **665 pasan**, 1 falla — la anterior al plan (reporte 66) |
| `npx tsc --noEmit` | sin errores |
| `h22_backend.py` · `h2b2_backend.py` · `h32_consulta.py` | TODO PASA |

Los tres scripts de HTTP se volvieron a correr **por el arreglo de `_excedidas`**,
que toca código de H2 y de H2b: siguen verdes.

El endpoint responde hoy lo que debe responder hasta el rebuild:

```
preview: 400 {"detail":"Falta el lector de Excel en el servidor (openpyxl).
              Hay que reconstruir el backend."}
```

---

## 7. Lo que falta, y es de Fredy

**1. El rebuild del backend.** `openpyxl==3.1.2` ya está en
`backend/requirements.txt`, pero el contenedor no se reconstruye sin ti
(regla 7):

```
docker compose build backend && docker compose up -d backend
```

**2. El archivo de muestra.** `C:\proyectos\Kinetix_pruebas\horas_muestra.xlsx`
**no está ahí todavía** — miré la carpeta entera y no hay ningún `.xlsx`. H3.6
lo necesita para lo que pediste: importarlo entero, comprobar las 21 filas,
reimportarlo y ver que el total no cambia.

Con esas dos cosas, H3.6 y H3.7 salen seguidos.

**Estado: H3.4 y H3.5 implementados; la validación de punta a punta espera el
rebuild y el archivo.**

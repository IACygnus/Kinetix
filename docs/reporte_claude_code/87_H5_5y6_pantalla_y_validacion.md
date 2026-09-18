25b2897 · 2026-09-18

# ETAPA H5.5 y H5.6 — La pantalla y la validación de punta a punta

**0 llamadas a la IA.**

---

## 1. La pantalla (H5.5)

`/horas/informes`, con su entrada en el menú. Cuatro pestañas y **un solo juego
de filtros**:

| Pestaña | Qué enseña |
|---|---|
| **Vista previa** | el documento real, en HTML o en PDF |
| Actividades por proyecto | consumido frente a estimado, y el reparto por actividad |
| Mensual por persona | el mapa del mes y los días sin registrar |
| Ocupación y facturación | la ocupación de cada persona y el facturable por cliente |

| Archivo | Qué es | Líneas |
|---|---|---|
| `frontend/src/pages/horas/InformesPage.tsx` | **nueva** | 581 |
| `frontend/src/api/horasApi.ts` | los tipos del informe y las dos llamadas | +130 |
| `backend/.../time_informe.py` | el conteo de páginas en la cabecera | +8 |
| `backend/app/main.py` | expone esa cabecera en CORS | +3 |

**La previa enseña el documento, no una maqueta** (H-D57). Se pide el archivo con
axios y se enseña desde un blob, no con un `<iframe src=…>`: así la cookie de
sesión viaja siempre, sin depender de cómo trate el navegador un marco de otro
origen. Lo que se ve es, byte a byte, lo que se descarga.

**El conteo de páginas** sale de una cabecera nueva, `X-Total-Paginas`. El PDF se
renderiza y se escribe en dos pasos para poder contarlas: preguntárselo al
archivo ya escrito no se puede, porque WeasyPrint guarda sus objetos comprimidos
—lo mismo que obligó a medir la orientación de otra manera en H5.4—.

---

## 2. Un fallo que solo encontró la prueba de pantalla

**Quitar una sección no quitaba nada.** Se marcaba la casilla, la previa se
rehacía… y el documento salía igual.

La causa: **axios manda las listas como `seccion[]=a&seccion[]=b`** y FastAPI
espera `seccion=a&seccion=b`. Con los corchetes **no ve el parámetro y se queda
con el valor por defecto, sin dar ningún error**. Medido:

```
con seccion[] -> 27249 bytes
con seccion   -> 12656 bytes
```

Lo peor no es el fallo, es que era silencioso: ni un 422, ni un aviso. Y afectaba
también al **filtro de personas**, que viaja igual. Arreglado con un
`paramsSerializer` compartido por las dos llamadas del informe, con el porqué
escrito al lado.

---

## 3. Los tiempos de H-D62, medidos

Con **312 registros** —el tamaño que fija la decisión— y un mes de cuatro
personas y cuatro proyectos:

| Salida | Tiempo | Límite de H-D62 |
|---|---|---|
| HTML | **0,03 s** | < 5 s |
| PDF | **1,10 s** | < 15 s |
| CSV | 0,04 s | — |

El PDF sale en 4 páginas. No hay nada que optimizar y, sobre todo, **no hay que
volver a mirarlo**: la decisión pedía medir antes de tocar nada, y lo medido dice
que no hay problema.

---

## 4. Validación — 36 comprobaciones de punta a punta, todas pasan

```
PASA  | la vista previa enseña el documento real (H-D57)
PASA  | hay cuatro pestanas
PASA  | la pestana «proyectos» / «mensual» / «ocupacion» enseña su tabla

--- quitar una seccion (H-D53) ---
PASA  | al quitar la casilla, desaparece del documento
PASA  | y el resto sigue
PASA  | y al volver a marcarla, vuelve

--- cambiar un filtro y ver la previa cambiar ---
PASA  | «solo facturables» cambia el documento (472 h -> 314 h)

--- el modo PDF y la orientacion (H-D56) ---
PASA  | en PDF sale el conteo de paginas y su navegacion (Página 1 de 4)
PASA  | y se puede pasar de pagina
PASA  | el selector de orientacion rehace el PDF

--- las tres descargas (H-D61) ---
PASA  | html: «informe-horas-2026-09-equipo.html»  · en minusculas y sin tildes
PASA  | pdf:  «informe-horas-2026-09-equipo.pdf»   · en minusculas y sin tildes
PASA  | csv:  «informe-horas-2026-09-equipo.csv»   · en minusculas y sin tildes

--- el HTML descargado funciona por su cuenta ---
PASA  | se abre sin servidor
PASA  | y sus botones filtran (80 de 314)
PASA  | sin errores al abrirlo suelto ([])
```

---

## 5. Regresión

| Prueba | Resultado |
|---|---|
| `verificar_etapa2.py` — las cuatro salidas | **LAS CUATRO SALIDAS PASAN** |
| `h15_pantallas.py` (H1) | TODO PASA |
| `h22_backend.py` · `h2b2_backend.py` · `h2b5_pantalla.py` | TODO PASA |
| `h32_consulta.py` · `h33_pantalla.py` · `h36_importacion.py` (H3) | TODO PASA |
| `h52_informe.py` · `h53_h54_documento.py` (H5) | TODO PASA |
| `pytest tests/` | **665 pasan**, 1 falla — la anterior al plan (reporte 66) |
| `npx tsc --noEmit` | sin errores |

**Un aviso de método, que me costó un susto:** la primera vuelta de la regresión
la lancé **mientras H5.6 seguía creando sus 312 registros**, y tres suites
fallaron con totales que no cuadraban. No era el producto: era mi forma de
correrlas. Las pruebas de horas comparten mes y personas, así que **van en serie,
nunca en paralelo**. Repetidas una detrás de otra, las cinco pasan.

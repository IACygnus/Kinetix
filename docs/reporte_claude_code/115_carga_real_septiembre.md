Commit `679f186` · 24 de septiembre de 2026

# CARGA REAL — el catálogo limpio, el borrado total y los tres Excel

Septiembre de 2026 cargado desde cero: **107 registros, 489 horas, tres
personas**. Antes se borró todo lo que había —incluidos los proyectos, los
clientes y las actividades que dejó la importación del 20— y se dejó el catálogo
de actividades en las ocho que pidió Fredy.

**0 llamadas a la IA.**

---

## 0. La copia de seguridad

```
C:\proyectos\Kinetix_pruebas\backup_carga_real_20260924_0000.sql
6.750.857 bytes (6,44 MB)
```

Hecha **antes de leer siquiera los Excel** (regla 32). Es la tercera de la
noche: ya estaban `backup_antes_de_borrar_20260924.sql` (13,5 MB) y
`backup_antes_de_carga_20260924.sql` (6,75 MB).

---

## 1. Los tres Excel corregidos

Archivos nuevos con sufijo `_corregido`, **los originales intactos** (misma
fecha y mismo tamaño que antes de empezar). Se comprobó celda a celda que no
cambió nada más: se leyeron los seis archivos y se compararon fila a fila.

| Archivo | Filas | Cambios |
|---|---|---|
| `Horas septiembre_ruben_corregido.xlsx` | 26 | **6** |
| `tabla_horas_septiembre_2026_fredyv2_corregido.xlsx` | 42 | 0 |
| `tabla_horas_septiembre_2026_moni_corregido.xlsx` | 39 | 0 |

Las seis celdas, todas en el de Rubén:

| Celda | Antes | Después |
|---|---|---|
| D9 | `Análisis` | `Análisis de resultados` |
| C15 · C18 · C23 · C25 · C27 | `Alkosto - Manhathan` | `Migracion Manhathan_Performance` |

Los de Fredy y Mónica **ya decían `Migracion Manhathan_Performance`**: por eso
no tienen cambios. Sus copias `_corregido` existen igual, para que los tres se
carguen desde la misma clase de archivo.

### La «Investigación» de Rubén no existe

§1 pedía cambiar la `Investigación` de Rubén por `Gestión de proyectos`. **En su
archivo no hay ninguna fila que diga «Investigación».** No es que estuviera
escrita de otra manera: se buscó la cadena `nvestiga` en el XML crudo del
`.xlsx` —donde están todas las cadenas del libro, también las que no se ven— y
no aparece ni una vez. En los otros dos, tampoco.

Lo que sí trae Rubén es **una** fila con `gestion de proyectos` en minúsculas y
sin tilde (fila 12, 6 h en Pluxee shop), y esa **ya casa sola** con `Gestión de
proyectos`: la comparación es normalizada. Así que el resultado que Fredy quería
está, pero por otro camino. No se tocó nada por esto.

`Investigación` sigue en el catálogo, como pedía §3, con 0 horas.

### El chequeo de parada de §1 no salta

§1 mandaba parar si `Alkosto` y `Colcomercio` salían como clientes distintos
para el mismo proyecto. **No pasa:** en los tres archivos el proyecto de
Manhathan cuelga siempre de `ALKOSTO`. `Colcomercio` no aparece en ningún Excel
—solo estaba en la base, con un proyecto llamado `Preventa`, que no es ese—. No
hubo que elegir cliente.

---

## 2. El borrado total

### Lo que había antes

| | Cuántos | De dónde venían |
|---|---|---|
| Registros | 21 | **18** de la importación del 20/09 15:51 · **3** a mano de Fredy (18/09) |
| Proyectos | 10 | 9 de la importación · 1 a mano (`performance avion`) |
| Estimaciones | 5 | todas de `performance avion` |
| Actividades | 11 | 5 del seed de H1 · 3 de la importación · **3 del seed nuevo** |
| Clientes | 13 | 8 del módulo de análisis (marzo-agosto) · 5 de la importación |

Los tres registros a mano (`sdasa`, `cxzxc`, `dwsdfasdasd`), el proyecto
`performance avion` y sus 5 estimaciones **no venían de la importación**, así
que se preguntó antes de tocarlos. Fredy respondió «bórralo todo».

> **Las 3 actividades de más las puso mi propio cambio.** Al editar
> `seed_time_tracking.py` (§3), el backend recargó y la siembra —que es
> idempotente y añade lo que falte— creó `Etapa de conocimiento`, `Diseño de
> script` e `Investigación` en la base de Fredy sin que nadie lo pidiera. Son
> exactamente tres de las ocho del objetivo, así que no hizo daño, pero **fue
> una escritura en su base que no estaba planeada** y queda dicha (regla 33).

### Lo que se borró, y por dónde

| Paso | Cómo | Resultado |
|---|---|---|
| Registros | `POST /time/borrado/confirm`, septiembre de 2026 | **21 registros, 56,50 h** |
| Proyectos | `DELETE /time/projects/{id}` ×10 | **10 proyectos**, con 5 estimaciones, 5 cambios de estimación y 4 cambios de estado |
| Clientes | `DELETE /clients/{id}` ×5 | SQA CoE · Colcomercio · Ficohsa · SQ-AI Funcional · Banco Occidente |
| Actividades | `DELETE /time/activities/{id}` ×3 | las tres que sobraban (§3) |

**Ni una línea de SQL a mano** (regla 28). Todo por endpoints del producto, y
todo con su constancia: 1 fila en `time_entry_purges` y 10 en
`project_deletions`.

Antes de borrar los 5 clientes se comprobó que **no les colgaba nada** —ni
ejecuciones, ni scripts, ni asignaciones, ni servidores, ni sesiones, ni
logos—. Los 8 clientes del módulo de análisis (Compensar, Occidente, popular,
iaperformance, Avianca, prueba avianca, Nutresa, Bancoomeva) **no se tocaron**:
no los creó la importación y tienen ejecuciones de pruebas detrás.

### Dos proyectos no salían en el listado

`Ficohsa / NOVA - UAT` (`no_viable`) y `SQA CoE / SQ-AI Funcional`
(`finalizado`) **no aparecen en `GET /time/projects`** con los filtros por
defecto. Se encontraron mirando la tabla y se borraron por su id. Vale la pena
saberlo: un inventario hecho desde esa pantalla no enseña todo lo que hay.

---

## 3. El endpoint que hubo que escribir

`DELETE /time/projects/{id}` **no existía** —ni en el backend ni en la pantalla—
y sin él §2 no se podía cumplir sin SQL a mano. Fredy autorizó añadirlo y fijó
las guardas:

| Guarda | Cómo |
|---|---|
| Solo admin | `require_role(["admin"])` |
| Solo sin horas | 409 que **dice cuántos registros** son |
| Se lleva lo suyo | `project_activities`, `project_activity_changes` y `project_status_changes`, por el `ON DELETE CASCADE` que ya declaraban |
| Una transacción | La de la petición |
| Constancia | Tabla nueva `project_deletions`: quién, qué proyecto, de qué cliente, cuándo y cuántas filas hijas se fueron |

**No está en la pantalla**, por decisión suya: el botón de borrar un proyecto se
decide aparte, con su confirmación.

`project_deletions` guarda el cliente y el nombre **como texto**, no por
`client_id`: el sentido de esa fila es sobrevivir al proyecto, y un cliente
también se puede borrar después.

De paso, `DELETE /clients/{id}` llevaba **sin guarda**: como
`projects.client_id` es `NO ACTION`, borrar un cliente con proyectos reventaba
con un 500 de integridad que no explicaba nada. Ahora devuelve un 409 que dice
cuántos proyectos son y por dónde empezar.

---

## 4. El catálogo, en las ocho

| Actividad | Horas cargadas |
|---|---|
| Diseño de script | 280,50 |
| Análisis de resultados | 86,00 |
| Ejecución | 67,00 |
| Gestión de proyectos | 34,00 |
| Preventa | 12,00 |
| Etapa de conocimiento | 6,00 |
| Planeación | 3,50 |
| Investigación | 0,00 |

Ni una más. Las tres que se fueron: `Administrativas o gerenciales`,
`Contextualización conocimiento proyecto` y `Diseño y generación de script`.

**Estas ocho son ahora la siembra inicial del producto.** `seed_time_tracking.py`
ya no lleva su propia lista: importa `CANONICAS` de
`services/horas/sinonimos_actividad.py`, para que la lista viva en **un solo
sitio**. Una instalación nueva nace con las ocho.

---

## 5. La tabla de sinónimos

`backend/app/services/horas/sinonimos_actividad.py` — definición única, la
consultan **las dos importaciones** (registros y proyectos). No se copia en
ninguna: es el mismo error que la plantilla paralela del informe por
transacción, que acabó divergiendo.

Tres reglas:

1. **Solo en las importaciones.** El registro a mano no pasa por aquí: ahí Fredy
   escribe lo que quiera. Traducirle lo que teclea sería corregirle sin avisar.
2. **Lo que no esté se crea igual.** No es un filtro. Lo que cambia es que la
   vista previa lo avisa.
3. **Se compara normalizado**, así que `gestion de proyectos` casa con `Gestión
   de proyectos` sin estar en la lista.

El índice se construye al importar el módulo y **revienta al arrancar** si dos
canónicas se disputan el mismo sinónimo. Es mejor sitio para ese error que la
mitad de una importación.

### El bloque nuevo de la vista previa

«**Actividades nuevas que no estaban en el catálogo**», con **el nombre, en qué
filas aparece y cuántas horas trae cada una**. Con el nombre a secas no se puede
decidir: una desconocida con 40 horas en 12 filas casi nunca es nueva, es una
variante de escritura, y entonces lo que hay que hacer es **añadir el sinónimo y
volver a importar**, no confirmar. El resumen lo repite después de confirmar.

Está en las dos pestañas de Importar. Y cada fila que la tabla traduce conserva
lo que decía el archivo (`activity_original`), para que se vea **qué** se
tradujo y no solo el resultado.

---

## 6. La carga

**Cero actividades nuevas en las tres previas.** La tabla reconoció todo lo que
traían los archivos, así que no hubo que parar (§5).

Lo que tradujo:

| Lo que venía escrito | Se guardó como | Veces |
|---|---|---|
| `Diseño y generación de script` | Diseño de script | 50 |
| `Analisis de resultados` | Análisis de resultados | 12 |
| `Contextualización conocimiento proyecto` | Etapa de conocimiento | 7 |
| `gestion de proyectos` | Gestión de proyectos | 1 |
| `Análisis` (ya corregida en el archivo) | Análisis de resultados | — |

### Lo que entró

| Persona | Filas del Excel | Registros | Horas | ¿Cuadra? |
|---|---|---|---|---|
| Rubén Darío Flórez | 26 | 26 | **167,00** | sí |
| Fredy Gabriel Bonilla Becerra | 42 | 42 | **159,00** | sí |
| Mónica Alejandra Archila Córdoba | 39 | 39 | **163,00** | sí |
| **Total** | **107** | **107** | **489,00** | sí |

Las horas se sumaron **del Excel directamente**, no de lo que dijo la
importación, y cuadran las tres. **0 filas fuera, 0 omitidas, 0 actualizadas.**

Del 1 al 23 de septiembre de 2026.

### Clientes creados: 7

`ALKOSTO` · `BANCO POPULAR` · `SODEXO (Pluxee)` · `BANCO FICOHSA` ·
`MEDICINA PREPAGADA COOMEVA` · `Software Quality Assurance` · `PORVENIR`

Dos cosas que conviene saber:

- **`Compensar` NO se creó.** El `COMPENSAR` de Mónica casó con el cliente
  `Compensar` que ya existía desde marzo de 2026 en el módulo de análisis. Es el
  mismo cliente, así que está bien, pero explica por qué en el inventario ese
  aparece con otra grafía que los demás.
- **`SODEXO (Pluxee)` y `Sodexo (Pluxee)` son el mismo.** Se creó con la grafía
  de Rubén, que fue el primero en cargar, y los proyectos de los tres cuelgan de
  él.

---

## 7. Lo que quedó — los 16 proyectos

Todos **en ejecución** y todos **sin estimar** (0 actividades estimadas), que es
lo que había que conseguir para que Fredy pueda estimarlos ahora.

### ALKOSTO — 58,50 h
**Migracion Manhathan_Performance** · Diseño de script 48,00 · Ejecución 10,50

### BANCO FICOHSA — 116,00 h
**NOVA - Capa media** (94,50) · Diseño de script 79,50 · Análisis de resultados
8,50 · Ejecución 4,00 · Planeación 1,50 · Etapa de conocimiento 1,00
**Paquete 1 - PCKG1** (21,50) · Gestión de proyectos 21,50

### BANCO POPULAR — 16,50 h
**Banco Popular - Proyecto Bus** · Diseño de script 8,50 · Análisis de
resultados 8,00

### Compensar — 0,50 h
**COMPENSAR - Generales** · Ejecución 0,50

### MEDICINA PREPAGADA COOMEVA — 28,50 h
**24353 Bre-b - Pruebas de WH - Aliados indirectos (Pexto)** (25,50) · Diseño de
script 19,50 · Gestión de proyectos 4,00 · Etapa de conocimiento 2,00
**24355 Brebia_Performance** (2,00) · Etapa de conocimiento 2,00
**24342-Coomeva_SendCode_Performance** (1,00) · Gestión de proyectos 1,00

### PORVENIR — 25,00 h
**Apoyos_Performance_PORVENIR** · Diseño de script 13,50 · Análisis de
resultados 9,00 · Etapa de conocimiento 1,00 · Planeación 1,00 · Ejecución 0,50

### SODEXO (Pluxee) — 142,00 h
**Pluxee shop** (128,00) · Diseño de script 61,50 · Análisis de resultados 46,50
· Ejecución 14,00 · Gestión de proyectos 6,00
**Carga masiva_Performance** (14,00) · Análisis de resultados 14,00

### Software Quality Assurance — 102,00 h
**24352 sq-ai v2_Performance** (51,00) · Diseño de script 50,00 · Planeación 1,00
**24354 Pruebas funcionales sq-ai** (37,25) · Ejecución 36,50 · Gestión de
proyectos 0,75
**COE - UEN Financial** (7,00) · Preventa 7,00
**COE - UEN Total** (5,00) · Preventa 5,00
**COE - Corporativo** (1,75) · Ejecución 1,00 · Gestión de proyectos 0,75

---

## 8. Lo que hay que saber para la próxima carga

**Ninguno de los tres Excel traía columna `Id`.** Sin `external_id` la
importación **no era idempotente**: volver a cargar cualquiera de los tres
habría **duplicado** sus registros en vez de actualizarlos.

> **Resuelto el mismo día.** Fredy decidió que el `external_id` es una
> referencia suya, no un dato de otra herramienta que haya que respetar, así que
> se numeraron los tres archivos y se recargó. Ver **§12**.

---

## 9. Las pruebas

Dos suites nuevas, contra `jmeter_analyzer_test` y el 8002 (regla 34):

**`backend/pruebas_e2e/carga_borrado_proyecto.py`** — el endpoint nuevo. Analista
403, proyecto con horas 409 que dice cuántas, id inexistente 404, el admin borra
y **las tres tablas hijas se van con él**, queda constancia con su nombre y su
cliente, y el proyecto vecino no se entera. **Todo pasa.**

**`backend/pruebas_e2e/carga_actividades_nuevas.py`** — la tabla de sinónimos y
el aviso. Fabrica un `.xlsx` con tres actividades conocidas y una inventada:
comprueba que las tres se traducen y conservan lo que decía el archivo, que la
desconocida sale en el bloque con sus filas y sus horas, que **la previa no crea
nada**, que la pantalla lo enseña con «4,5 h en 2 filas (5, 6)» y que el resumen
lo repite. **Todo pasa.**

La pantalla se comprueba **antes** de confirmar: si se confirma primero, la
actividad ya existe y deja de ser nueva. Es fácil escribir esa prueba al revés y
que pase sin mirar nada.

Regresión del módulo de horas, toda verde:

| Suite | |
|---|---|
| `h22_backend` | 45 pasa |
| `h2b2_backend` | 53 pasa |
| `h32_consulta` | 53 pasa |
| `h52_informe` | 60 pasa |
| `h82_estados` | todo pasa |
| `h84_mapa` | todo pasa |
| `h85_borrado` | todo pasa |
| `h85b_proyectos` | todo pasa |

Dos guardas de «la base de Fredy, intacta» se actualizaron, porque la carga
cambió a sabiendas lo que vigilaban: de 10 a **16 proyectos** y de 24 a **107
registros**. Y la de `time_entry_purges` se cambió de «cero purgas» a «las
mismas que al empezar»: lo que delata un borrado accidental es que el número
**crezca durante la pasada**, no que la base nunca haya tenido un borrado
legítimo.

> `h83b_datos_informe.py` **no es una suite**: es el generador de datos de
> `h83b_informe.py`. Correrlo suelto deja sus cinco registros puestos y hace
> fallar a `h84_mapa`, que cae en los mismos días. Se limpia con
> `python3 h83b_datos_informe.py limpiar`.

---

## 10. Los archivos

| Archivo | Qué |
|---|---|
| `backend/app/services/horas/sinonimos_actividad.py` | **Nuevo.** Las ocho y sus sinónimos |
| `backend/app/db/models/time_tracking.py` | `ProjectDeletion` |
| `backend/app/db/seed_time_tracking.py` | Siembra las ocho, desde `CANONICAS` |
| `backend/app/schemas/time_tracking.py` | `ActividadNueva`, `ProyectoBorrado`, `activity_original` |
| `backend/app/api/v1/endpoints/time_projects.py` | `DELETE /time/projects/{id}` |
| `backend/app/api/v1/endpoints/clients.py` | La guarda del 409 |
| `backend/app/api/v1/endpoints/time_import.py` | Sinónimos + bloque |
| `backend/app/api/v1/endpoints/time_import_proyectos.py` | Sinónimos + bloque |
| `frontend/src/api/horasApi.ts` | Los tipos |
| `frontend/src/pages/horas/ImportarPage.tsx` | El bloque |
| `frontend/src/components/horas/ImportarProyectos.tsx` | El bloque |
| `backend/pruebas_e2e/carga_borrado_proyecto.py` | **Nueva** |
| `backend/pruebas_e2e/carga_actividades_nuevas.py` | **Nueva** |
| `backend/pruebas_e2e/h85_borrado.py` · `h85b_proyectos.py` | Guardas actualizadas |
| `docs/documentos carga/*_corregido.xlsx` | Los tres corregidos |

`project_deletions` la crea `create_all` al arrancar: **sin SQL a mano**
(regla 10).

---

## 11. Lo que falta

- **La validación de Fredy**, que es el único criterio (regla 9).
- **Estimar los 16 proyectos.** Ninguno tiene horas estimadas, así que el
  desfase no puede decir nada todavía y la sección 6 del informe sale vacía. Es
  para lo que se hizo la carga.
- **H8.6**, parada hasta que Fredy vea esto.

---

## 12. Los Id — la recarga numerada

Decisión de Fredy: el `external_id` es **una referencia suya**, no un dato de
otra herramienta que haya que respetar. Así que se numeran los archivos y se
recarga. Con eso la importación pasa a ser idempotente, que es lo que §8 daba
por pendiente.

**Copia previa:** `backup_antes_de_numerar_20260924.sql`, 6.788.008 bytes
(6,47 MB).

### Los números

Columna `Id` añadida **la primera** de cada archivo —la posición da igual,
`mapear_columnas` busca por título normalizado, pero delante se lee mejor—.
Consecutivo desde **24300**, cada archivo siguiendo donde acabó el anterior:

| Archivo | Persona | Filas | Id |
|---|---|---|---|
| `tabla_horas_septiembre_2026_fredyv2_numerado.xlsx` | Fredy | 42 | **24300 – 24341** |
| `tabla_horas_septiembre_2026_moni_numerado.xlsx` | Mónica | 39 | **24342 – 24380** |
| `Horas septiembre_ruben_numerado.xlsx` | Rubén | 26 | **24381 – 24406** |

**107 números, 107 distintos, sin saltos y sin repetir entre archivos.**
Siguiente libre: **24407**.

Archivos nuevos con sufijo `_numerado`. Los `_corregido` y los originales
quedan intactos —misma fecha y mismo tamaño—, y se comprobó celda a celda que
en los numerados **lo único que cambia es la columna nueva**: se leyeron los
seis y se compararon fila a fila saltando la primera columna.

Una fila vacía no gastaría número; en estos tres no hay ninguna.

### El borrado y la recarga

| | |
|---|---|
| Borrado | `POST /time/borrado/confirm`, septiembre de 2026 · **107 registros, 489,00 h** |
| Intacto | 16 proyectos · 8 actividades · 15 clientes · 0 estimaciones |

Las tres previas, antes de cada confirmación:

| Persona | Filas | Nuevas | Actualizadas | Fuera | Horas | A crear |
|---|---|---|---|---|---|---|
| Fredy | 42 | 42 | 0 | 0 | 159,00 | nada |
| Mónica | 39 | 39 | 0 | 0 | 163,00 | nada |
| Rubén | 26 | 26 | 0 | 0 | 167,00 | nada |

Ningún cliente, proyecto ni actividad que crear: ya existían todos de la carga
anterior. Y ninguna actividad nueva que avisar.

### La idempotencia, comprobada

Segunda subida del archivo de Mónica, **solo la vista previa, sin confirmar**:

```
nuevas      : 0
ACTUALIZADAS: 39
invalidas   : 0
horas       : 163,0
ejemplo: fila 2 · Id 24342 · acción «actualiza» · cambia_de_persona=False
```

Y la base seguía en **107 registros y 489,00 h** después de mirarla: la previa
no escribió nada (§6.2.5).

### Cómo quedó

| Persona | Registros | Horas | Id |
|---|---|---|---|
| Fredy Gabriel Bonilla Becerra | 42 | **159,00** | 24300 – 24341 |
| Mónica Alejandra Archila Córdoba | 39 | **163,00** | 24342 – 24380 |
| Rubén Darío Flórez | 26 | **167,00** | 24381 – 24406 |
| **Total** | **107** | **489,00** | **24300 – 24406** |

Las mismas 489 horas que antes de numerar. Los 107 registros llevan
`external_id`, los 107 son distintos y el rango no tiene saltos.

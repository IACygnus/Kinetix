# ETAPA D1 — el diseño del informe de horas

Commit base `f5bf053` · 23 de septiembre de 2026 · rama `backup-trabajo-local`
· **0 llamadas a la IA** · `pg_dump` previo en
`C:\proyectos\Kinetix_pruebas\backup_2026-09-23_d1.sql` (6,7 MB)

**Los cinco sub-pasos hechos.** Las capturas están en
`C:\proyectos\Kinetix_pruebas\d1_capturas\`, numeradas para verlas en orden:
el antes, el después, la referencia, la prueba de fuentes, el documento entero
y las cuatro hojas del PDF.

> ### La comprobación que más importa: ninguna cifra cambió (D-D8)
>
> Comparadas **número a número**, no a ojo, generando el informe con el
> generador de `f5bf053` y con el de ahora, **con los mismos datos**:
>
> | Periodo | Cifras comparadas | Distintas |
> |---|---|---|
> | septiembre de 2026 | **308** | **0** |
> | todo 2026 | **647** | **0** |
>
> Lo hace `pruebas_e2e/diseno/d1_cifras.py`, tabla por tabla y después el
> documento entero como conjunto. Detalle en §8.

---

## 1. Lo primero: para revisar — los ocho párrafos de sección (D-D4)

**Son texto fijo, escritos una vez, sin IA.** Interpolan cifras del informe, no
datos nuevos. Aquí están enteros, para que se lean antes de darlos por buenos.

> ### Resumen
> Lo que el equipo apuntó en el periodo y cuánto de ello se carga a una cuenta
> de cliente. Mide el registro, no el esfuerzo: las horas que nadie apuntó no
> están en ninguna de estas cifras. Los **8** días sin registrar son la pista de
> cuántas pueden faltar.
>
> *(si no hubiera ninguno: «En el periodo no quedó ningún día sin registrar.»)*

> ### Ocupación por persona
> Cuánto registró cada persona frente a la jornada que le correspondía hasta
> hoy, y la ocupación que sale de comparar esas dos columnas. Un porcentaje bajo
> puede ser trabajo sin apuntar y no tiempo libre: la última columna es la que
> lo dice. La jornada de aquí llega solo hasta hoy; la capacidad del periodo
> completo —**185 h** por analista— está en la portada, y son cifras distintas a
> propósito.

> ### Facturable frente a no facturable
> El dato que ordena el informe. Una hora facturable está cargada a una cuenta
> abierta del cliente; una no facturable es trabajo igual de real que no tiene
> dónde cargarse, casi siempre porque el proyecto todavía no tiene código. El
> porcentaje dice dónde se apuntó la hora, no si el trabajo valió la pena.

> ### Cobertura por cliente
> En qué clientes se repartió el tiempo del periodo. El porcentaje es sobre el
> total registrado, lo facturable y lo que no, todo junto: un cliente puede
> ocupar mucho sitio en esta tabla sin haber dejado ni una hora facturable, y la
> sección anterior es la que lo cuenta.

> ### En qué se fue el tiempo
> El reparto por la actividad que cada persona eligió al registrar. Dice en qué
> se ocupó el tiempo, no cuánto rindió: una hora de preparación y una de
> ejecución pesan lo mismo aquí.

> ### Consumido frente a estimado
> Los proyectos que tuvieron horas en el periodo, y cuánto llevan gastado frente
> a lo estimado. Las dos columnas de horas no miden lo mismo: en el periodo son
> las de estas fechas, y consumidas es todo lo que lleva el proyecto desde que
> se abrió, que es contra lo que se mide el desfase. Un proyecto sin estimación
> sale igual, pero su estado no significa nada.

> ### Mapa del mes
> Día a día, quién registró y quién no. El color dice en qué estado quedó cada
> día y la leyenda de abajo los nombra uno a uno; las horas exactas están en el
> detalle. Un día en ámbar tiene horas apuntadas, solo que menos de su jornada,
> y los días que todavía no han llegado salen en blanco y no se reclaman.

> ### Detalle de registros
> Los **24** registros del periodo, uno por fila. Se puede filtrar, ordenar por
> cualquier columna y descargar en CSV lo que quede a la vista. Es la única
> parte del informe donde se lee lo que cada persona escribió en las
> observaciones.

### Con qué criterio están escritos

Los tres que pediste, y uno que salió de leer los de la referencia:

1. **De una a tres líneas.** El más corto tiene 179 letras y el más largo 391.
2. **No repiten la tabla**: explican el término que el lector no tiene por qué
   saber —qué es una hora facturable, qué mide la ocupación—.
3. **Avisan de lo que el dato NO dice.** Es el registro de la referencia
   («160 horas es el techo del registro, no la medida del esfuerzo»), y aquí
   aparece en seis de los ocho: «mide el registro, no el esfuerzo», «puede ser
   trabajo sin apuntar y no tiempo libre», «dónde se apuntó la hora, no si el
   trabajo valió la pena», «en qué se ocupó el tiempo, no cuánto rindió», «las
   dos columnas de horas no miden lo mismo», «su estado no significa nada».
4. **Cuando dos cifras del propio informe se pueden confundir, el párrafo las
   separa.** Pasa dos veces, y las dos están documentadas en el esquema: la
   jornada «hasta hoy» frente a la capacidad del periodo completo, y las horas
   «en el periodo» frente a las «consumidas» desde siempre.

Sin markdown, sin jerga y sin ninguna de las palabras vedadas de la regla 15:
lo comprueba `pruebas_e2e/diseno/d1_diseno.py`.

### Un párrafo que tuve que corregir

El primero que escribí para «Consumido frente a estimado» empezaba con «Los
proyectos **con horas estimadas**…». Es falso: la tabla incluye proyectos con
`0 h` estimadas, y se ven en la captura. Lo cambié a «Los proyectos que tuvieron
horas en el periodo». Lo anoto porque es justo el tipo de frase que suena bien y
no lo es.

---

## 2. Lo que se hizo, por sub-paso

### D1.1 — el documento de diseño

`docs/diseno-informe-horas.md`, 406 líneas. Todos los valores **medidos** del
HTML de referencia: paleta, tipografía elemento a elemento, geometría,
anatomía de la portada y del indicador, tablas, y la geometría de las cuatro
gráficas. Es la fuente: nadie vuelve a interpretar la referencia.

**La causa del problema era estructural**: el informe estaba maquetado entero en
`pt` y `mm`. `_BASE_CSS` lo comparten pantalla y papel, y `_WEB_CSS` no tocaba
ni un tamaño de letra — la pantalla estaba mostrando una hoja de estilos de
impresión, con cuerpo de 12,7 px y celdas de 6,8 px de alto.

### D1.2 — la portada y el resumen

- **Las letras.** Exo 2 y Montserrat, licencia SIL OFL, incrustadas en base64.
  Google ya solo las sirve como fuente variable, así que se cortaron instancias
  estáticas por peso con `fontTools`. **108.360 B en disco, 144.480 B en
  base64**, de 400 KB de tope. Comprobado imprimiendo los seis pesos más una
  línea de control en una familia inexistente: los seis salen distintos y la de
  control cae en una serif sustituta.
- **La paleta de la referencia**, en un `:root` de variables. No queda ni un
  `#0a1628` ni un `#f5a623` en el informe de horas.
- **La portada** sobre bloque azul marino a sangre, con el período dentro del
  título en amarillo y los cuatro datos en una fila.
- **Los indicadores** con la cifra a 32 px en Exo 2 800, cada uno de su color, y
  una línea de desglose debajo.
- La **barra de controles** pasó a clara: con la portada oscura debajo, una
  barra oscura se fundía con ella.

### D1.3 — las secciones

- **Títulos** a 22 px en azul, **sin el cuadro numerado y sin el subrayado
  naranja**.
- **El párrafo de cada sección**, lo de arriba.
- **Las tablas respiran**: celdas de `13px 14px` en vez de 6,8 × 7,6 px,
  cabecera en caja normal, última fila sin borde, y cada tabla dentro de una
  tarjeta con borde fino y esquinas redondeadas.
- **La barra y su porcentaje** pasaron a la misma celda, 48 × 6 px. Antes la
  barra tenía columna propia con la cabecera vacía.
- **Dos gráficas**, las que pediste.

---

## 3. Las gráficas, con las condiciones que pusiste

`backend/app/services/horas/graficas.py`. **SVG escrito en el servidor, sin
biblioteca nueva y sin una línea de JavaScript**, para que salga igual en el
HTML sin red y en el PDF.

| Condición | Cómo queda |
|---|---|
| Solo cifras que el informe ya calcula | Sí. Ver el aparte de abajo |
| Las tablas se quedan; la gráfica va encima | Sí, las dos |
| Sin biblioteca y sin JavaScript | Sí. El PDF no lleva ni un `<script>` |
| Leyenda siempre | Sí, con el nombre de cada serie **y su total** |
| El color nunca es lo único que distingue | Cada tramo lleva su cifra dentro, y la leyenda nombra cada serie |
| En el PDF: sale, no se parte, nada baja de 8 pt | Sí. `page-break-inside:avoid`, y el texto más pequeño sale a **8,5 pt** |

**Facturable frente a no facturable, por persona** va encima de la tabla de
«Ocupación por persona», no de la de «Facturable frente a no facturable». La
razón es tu condición: dibuja **dos columnas de la tabla que tiene debajo**
—las horas registradas y las facturables—, mientras que la tabla de
facturación es por cliente. Si prefieres verla en la otra sección, se mueve.

**Un aparte que tienes que saber.** El segundo tramo es «no facturable por
persona», y **ese campo no existe**: es `total_hours − billable_hours`, las dos
columnas de esa misma fila. No es una consulta nueva ni un cálculo de negocio
—es la misma resta que el informe ya publica por cliente como
`non_billable_hours`—, pero es una resta, y dijiste «ni un dato nuevo». Lo
declaro en vez de decidirlo por mi cuenta: si lo consideras dato nuevo, la
gráfica se cambia por una de una sola serie con solo las facturables.

**Las gráficas no se refiltran.** Están dibujadas en el servidor, así que al
filtrar en pantalla siguen enseñando el periodo entero. El aviso de vista
filtrada que ya existía ahora lo dice con todas las letras.

---

## 4. Dos cosas que había que arreglar y no estaban en el plan

**1. El mapa del mes tenía un color sin nombre.** Los estados son seis
—`trabajado`, `incompleto`, `festivo`, `ausencia`, `finde` y `vacio`— y la
leyenda solo nombraba cinco. El que faltaba, `vacio`, es **un día laborable que
todavía no ha llegado**, y sale en blanco: justo el que más se ve en un informe
a mitad de mes. Ahora la leyenda dice «aún no ha llegado».

**2. WeasyPrint recorta los descendentes de un `<text>` con
`text-anchor="end"`.** Las etiquetas de las gráficas salían en el PDF sin las
colas de la «y», la «g» y la «p»: «Diseño y generación de script» perdía tres
letras por abajo. Comprobado con un experimento —la misma frase con los dos
anclajes en la misma línea: la de `start` sale entera, la de `end` recortada—,
y es independiente de la familia, del peso y de `dominant-baseline`.

La vuelta: **no se emite `text-anchor` en ninguna parte**. La posición se
calcula midiendo el texto con las métricas de la propia fuente que se está
incrustando (`fuentes.ancho_texto`, con `fontTools`, que ya viene con
WeasyPrint). Sale exacto, y de paso el recorte de los nombres largos pasó a ser
el justo en vez de una estimación.

**Propongo añadir esto a las lecciones aprendidas de CLAUDE.md §15**, porque
vale para cualquier SVG que este producto mande a WeasyPrint, no solo para el
informe de horas. No lo he tocado: el documento dice que no se edita a la
ligera.

---

## 5. Lo que NO se hizo, y por qué

| Cosa | Por qué |
|---|---|
| **Fila de totales** en las tablas (D-D7) | La referencia la tiene; el informe de Kinetix **no calcula totales por tabla**. Añadirla sería contenido nuevo (D-D8) |
| **Barra en la columna «Ocupación»** de la sección 2 | La referencia la lleva. Aquí es presentación de una cifra que ya está; se puede añadir si la quieres, pero no la di por pedida |
| **La portada a sangre en el PDF** | Es D1.4, como acordamos, con `@page :first { margin: 0 }` |
| **El logo con fondo transparente** | Lo consigues tú. La ruta no cambia: `backend/app/assets/logo-sqa.png` |

---

## 6. Lo que se tocó

| Archivo | Qué |
|---|---|
| `docs/diseno-informe-horas.md` | **Nuevo.** El documento de diseño, con las tres decisiones resueltas |
| `backend/app/assets/fuentes/` | **Nuevo.** Seis `.woff2` y las dos licencias OFL |
| `backend/app/services/horas/fuentes.py` | **Nuevo.** Incrusta las fuentes y mide texto |
| `backend/app/services/horas/graficas.py` | **Nuevo.** El SVG de las barras |
| `backend/app/services/horas/informe.py` | Paleta, portada, indicadores, títulos, párrafos, tablas, barra. De 781 a 1.096 líneas |
| `backend/pruebas_e2e/diseno/` | **Nuevo.** `rasterizar.py`, `pdf_a_png.py`, `generar.py`, `d1_diseno.py` |
| `backend/pruebas_e2e/h71_portada.py` | La banda pasó de dos tramos a tres |
| `backend/pruebas_e2e/h6_ajustes.py` | El período ya no va debajo del título, va dentro |

**`pypdfium2`** se instaló en el contenedor para rasterizar PDF; queda anotado
en `pruebas_e2e/LEEME.md` (regla 36). No entra en `requirements.txt`: es de
pruebas, no del producto.

`d1_diseno.py` pasa entera: **54 comprobaciones**.

---

## 7. D1.4 — la portada a sangre en el PDF

`@page :first { margin: 0 }`, la misma técnica que el informe de análisis. Deja
la **primera hoja entera** sin márgenes, así que la portada tiene que ocuparla
toda: alto fijo y `page-break-after: always`. El informe pasa de 4 a 4 páginas
—la portada se lleva la que antes compartía con el resumen— y el cuerpo empieza
limpio en la 2.

Tres cosas que costaron:

- **Las medidas suman 296 de los 297 mm del A4**, no 297. Con el alto exacto, un
  redondeo de nada empuja la banda a la hoja siguiente y sale una página en
  blanco al final.
- **El número de página se seguía dibujando sobre la banda.** Sin márgenes no
  hay caja de margen, pero el contenido de `@bottom-right` se pinta igual. Se
  apaga con `@page:first{ @bottom-right{content:none} }`. En una portada no
  pinta nada de todos modos.
- En una hoja entera el título puede respirar: baja a 78 mm del borde y sube a
  **40 pt**, con la fila de datos debajo y el azul hasta la banda.

Rasterizadas las cuatro páginas: `7_pdf_p1..p4.png`.

---

## 8. D1.5 — ninguna cifra cambió

`pruebas_e2e/diseno/d1_cifras.py`. El método, para que se pueda repetir:

1. Se saca el generador **de antes** con
   `git show f5bf053:backend/app/services/horas/informe.py`. No se congela en el
   repositorio: son 781 líneas que solo sirven para esto, y desde el commit de
   D1 el «antes» ya está en git.
2. Se piden los datos **una vez** y se renderizan los dos documentos con ellos.
   Así la comparación no puede confundir un cambio de diseño con un cambio de
   datos.
3. De cada tabla se saca **la lista ordenada de sus números** y se enfrentan.
   Aguanta que una tabla haya cambiado de forma —la del reparto pasó de cuatro
   columnas a tres— pero **no aguanta que un número cambie, desaparezca o se
   mueva de sitio**.
4. Después, el documento entero como conjunto.

| Periodo | Tablas | Cifras | Distintas |
|---|---|---|---|
| septiembre de 2026 | 10 | **308** | **0** |
| todo 2026 | 10 | **647** | **0** |

### Lo que hubo que separar, y por qué

La primera pasada acusó **siete cifras perdidas**: `1, 2, 4, 5, 6, 7` y un `83`.

Las seis primeras eran **los ordinales del cuadro numerado** que D-D5 retiró de
los títulos. Son números, pero no son datos del informe. El `83` no era ninguna
cifra: era **un artefacto de mi propia extracción** —el `8` de «días sin
registrar» pegado al `3` del cuadro numerado de la sección siguiente, porque
`text_content()` une el texto de celdas contiguas sin separador—.

Se arregló lo mío —se unen los trozos con un espacio— y se declaró el ordinal
de sección como lo que es: presentación, no cifra. Lo dejo escrito porque
**parecía una pérdida de datos y no lo era**, y la próxima vez que salga
conviene saber de dónde viene.

### Lo que el rediseño añadió, comprobado contra su origen

Los párrafos de sección, el pie de cada indicador y las gráficas traen números
nuevos **al texto**, pero no cifras nuevas: cada uno se comprueba contra el
campo del que sale —`resumen.entries_count`, `resumen.expected_hours`,
`resumen.total_hours`, `capacidad.hours_per_analyst`, `detalle_total`—.

---

## 9. La regresión, en serie

```
docker exec jmeter_backend sh /app/pruebas_e2e/cierre_o2d.sh
```

**19 suites. Las 11 de horas pasan enteras**, incluidas las tres que este
rediseño obligaba a tocar (`h53_h54_documento` 54 · `h6_ajustes` 56 ·
`h71_portada` 30), más la nueva `d1_diseno` con 56 comprobaciones.

**La base de Fredy no cambió ni una fila**: misma huella antes y después
(`86f88bf7…`, `24 10 8 13 5 5`).

Tres suites fallan, y **ninguna por D1** —esta etapa solo toca
`services/horas/`, las fuentes y el andamiaje de pruebas—:

| Suite | Por qué |
|---|---|
| `o2c1_servidores` · `o2c_pantalla` | Se paran antes de empezar: «faltan `LAB_PG_LECTOR_PASSWORD` o `KX_LLAVE_SSH` en el entorno». Son las credenciales del laboratorio |
| `o2a4_tablero` | Un panel del tablero devuelve 0 filas. Comprobado: el cubo `jmeter` solo tiene corridas `zztest-cliente-dos-…` del 21 y 22 de septiembre, y la que ese panel busca no está |

### Un arreglo en la propia suite

`d1_diseno.py` corría contra la base de pruebas, que el día del cierre estaba
**vacía**: sin datos no había gráficas que mirar y **tres comprobaciones pasaban
sin comprobar nada** —el mismo fallo que la Etapa 6 ya había cometido, y que
está en las lecciones de CLAUDE.md—. Ahora la suite **fabrica sus propios datos
en memoria**: no toca la base, no necesita sesión, mide siempre lo mismo y de
paso ejercita casos que la base real no tiene, como una ocupación del 103 %.

---

## 10. Lo que queda abierto

| Qué | Estado |
|---|---|
| **El logo con fondo transparente** | Lo consigue Fredy. Va en `backend/app/assets/logo-sqa.png`, misma ruta; el informe lo lee en cada generación, así que basta con sustituir el archivo |
| **Validación visual de Fredy** | Es el único criterio de éxito (regla 9). Las capturas están en `Kinetix_pruebas\d1_capturas\` |
| **Despliegue** | Nada que ejecutar: ni SQL, ni variables nuevas, ni dependencias de producto. En el servidor sí hace falta `up -d --build`, porque cambian backend y activos |

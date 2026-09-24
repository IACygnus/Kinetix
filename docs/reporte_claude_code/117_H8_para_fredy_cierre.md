Commit `679f186` · 24 de septiembre de 2026

# H8 para Fredy — el estado del proyecto, y septiembre cargado de verdad

H8 añadió **el estado del proyecto**: en qué punto está el trabajo, que lo
decides tú y no lo calcula nadie. Y la **carga real** dejó septiembre de 2026
metido desde cero, con el catálogo limpio.

Lo que tienes que mirar está abajo, con **qué número tiene que salir**. Si un
número no cuadra, es un fallo — no una interpretación.

**Cero llamadas a la IA en todo H8 y en la carga.**

---

## Lo más importante: son DOS columnas, no una

Esto es el corazón de H8 y conviene tenerlo claro antes de abrir nada:

| | Qué contesta | Quién lo pone |
|---|---|---|
| **Estado** | ¿en qué punto está este trabajo? | **Tú.** Pendiente · En ejecución · Detenido · No viable · Finalizado |
| **Consumo** | ¿cuántas horas lleva de las estimadas? | Lo calcula solo. En rango · Por agotarse · Terminado · Desfasado +X h |

Antes estaban mezclados: «Cerrado» era un valor de consumo, que es como decir
que un proyecto terminado gastó cierto número de horas. Ahora **«Cerrado» es un
estado** —se llama **Finalizado**— y el consumo se sigue calculando aparte.

Un proyecto finalizado puede estar perfectamente en rango. Son dos preguntas.

### Qué bloquea cada estado

| Estado | ¿Registrar horas? | ¿Cambiar estimaciones? |
|---|---|---|
| Pendiente | No | **Sí** |
| En ejecución | **Sí** | **Sí** |
| Detenido | No | **Sí** |
| No viable | No | No |
| Finalizado | No | No |

Pendiente y detenido son **temporales**: se planifican aunque no se registren
horas, y por eso admiten estimaciones. Poner un proyecto en **No viable** o
**Finalizado** es cosa del administrador.

---

## El guion, por pantallas

### 1. Proyectos — las dos columnas

**Horas → Proyectos.** Tienen que salir **16 proyectos**, todos **En
ejecución**, y **todos sin estimar**.

- La columna **Estado** es un chip de color que puedes cambiar.
- La columna **Consumo** dice «En rango» en todos, porque ninguno tiene
  estimación con la que compararse.
- Abajo, la casilla **«Incluir finalizados y no viables»**: marcada, no cambia
  nada todavía, porque no hay ninguno de esos.

Prueba a poner uno en **Finalizado** y verás que desaparece del listado hasta
que marcas la casilla. Devuélvelo a **En ejecución** después.

### 2. Registro — que el estado manda

**Horas → Registro.** Pon un proyecto en **Detenido** desde Proyectos, y
después intenta registrarle horas: **no te deja**, y te dice por qué. Las
estimaciones sí puedes cambiárselas.

### 3. El mapa del mes — las horas extra

**Horas → Registro**, el calendario. Los días con **horas extra** salen con la
casilla **partida en proporción**: verde abajo las ordinarias, azul arriba las
extra. En septiembre hay varios — Rubén y Mónica tienen extras en Alkosto.

### 4. Consulta

**Horas → Consulta**, del 1 al 30 de septiembre. Tiene que decir **107
registros y 489 horas**, repartidas así:

| Persona | Registros | Horas |
|---|---|---|
| Rubén Darío Flórez | 26 | **167,00** |
| Mónica Alejandra Archila Córdoba | 39 | **163,00** |
| Fredy Gabriel Bonilla Becerra | 42 | **159,00** |

Son exactamente las de los tres Excel. Las sumé de los archivos por mi cuenta,
no de lo que dijo la importación.

### 5. Importar — lo que hay de nuevo

**Horas → Importar**, dos pestañas:

- **Registros de horas** — la de siempre, más un bloque nuevo: **«Actividades
  nuevas que no estaban en el catálogo»**, con el nombre, en qué filas aparece y
  cuántas horas trae. Sirve para darte cuenta, antes de confirmar, de que a lo
  mejor lo que falta es un **sinónimo** y no una actividad.
- **Proyectos y estimaciones** — nueva. Carga proyectos con su **estado** y sus
  **horas estimadas** desde un `.xlsx`. Tiene su plantilla descargable.

Y abajo del todo, plegado, **Borrar un periodo**. Ver §7.

### 6. El informe

**Horas → Informes**, septiembre de 2026. Ocho secciones. La **sección 6** sale
vacía de desfases, y es correcto: ningún proyecto tiene estimación todavía.

---

## Lo que tienes que hacer ahora: estimar

**Es para lo que se hizo la carga.** Los 16 proyectos están sin estimar, así que
el desfase no puede decir nada y la sección 6 del informe no tiene contenido.

Tienes dos caminos:

1. **A mano**, proyecto por proyecto, en Horas → Proyectos.
2. **Por Excel**, con la pestaña nueva de Importar: descarga la plantilla,
   rellénala y súbela. Es una fila por actividad.

Para ayudarte a estimar, esto es **lo que ya se consumió** en septiembre, que es
la mejor referencia que hay:

| Cliente | Proyecto | Horas |
|---|---|---|
| SODEXO (Pluxee) | Pluxee shop | 128,00 |
| BANCO FICOHSA | NOVA - Capa media | 94,50 |
| ALKOSTO | Migracion Manhathan_Performance | 58,50 |
| Software Quality Assurance | 24352 sq-ai v2_Performance | 51,00 |
| Software Quality Assurance | 24354 Pruebas funcionales sq-ai | 37,25 |
| MEDICINA PREPAGADA COOMEVA | 24353 Bre-b - Pruebas de WH (Pexto) | 25,50 |
| PORVENIR | Apoyos_Performance_PORVENIR | 25,00 |
| BANCO FICOHSA | Paquete 1 - PCKG1 | 21,50 |
| BANCO POPULAR | Banco Popular - Proyecto Bus | 16,50 |
| SODEXO (Pluxee) | Carga masiva_Performance | 14,00 |
| Software Quality Assurance | COE - UEN Financial | 7,00 |
| Software Quality Assurance | COE - UEN Total | 5,00 |
| MEDICINA PREPAGADA COOMEVA | 24355 Brebia_Performance | 2,00 |
| Software Quality Assurance | COE - Corporativo | 1,75 |
| MEDICINA PREPAGADA COOMEVA | 24342-Coomeva_SendCode_Performance | 1,00 |
| Compensar | COMPENSAR - Generales | 0,50 |

El desglose por actividad de cada uno está en el reporte 115 §7.

---

## El catálogo: las ocho

Estas son ahora, y **no hay ninguna más**:

**Etapa de conocimiento · Planeación · Diseño de script · Ejecución · Análisis
de resultados · Gestión de proyectos · Preventa · Investigación**

Y son también con las que nace una instalación nueva, en lugar de las cinco de
antes.

**La tabla de sinónimos** (`services/horas/sinonimos_actividad.py`) sabe que
«Diseño y generación de script», «Variabilización» o «Smoke test» son todas
**Diseño de script**. Solo se aplica **al importar**; cuando registras a mano,
escribes lo que quieras.

En las tres cargas de septiembre reconoció **todo**: cero actividades nuevas.

> **Una cosa que no salió como pedías:** en el Excel de Rubén **no hay ninguna
> fila que diga «Investigación»**. La busqué en el XML crudo del archivo, donde
> están todas las cadenas del libro: no aparece ni una vez, ni en el suyo ni en
> los otros dos. Lo que sí trae es una fila con `gestion de proyectos` en
> minúsculas, que ya casa sola con **Gestión de proyectos**. O sea que el
> resultado que querías está, pero por otro camino.

---

## Borrar, ahora que se puede

Dos operaciones nuevas, las dos con constancia en la base.

### Borrar un periodo (en Importar, abajo)

Borra **solo registros de horas** de un rango. Proyectos, clientes, actividades
y estimaciones no se tocan, y la propia pantalla te lo dice contándolos.

Para que ocurra hacen falta **tres cosas a la vez**: ser administrador, marcar
que hiciste la copia de seguridad —te da el comando `pg_dump` escrito— y
**teclear el periodo exacto**. Cambiar el rango invalida lo tecleado.

### Borrar un proyecto

**No está en la pantalla, a propósito.** Existe el endpoint, con sus guardas
—solo administrador, solo si no tiene horas registradas, y se lleva consigo sus
estimaciones y sus dos historiales—, y deja constancia de quién, qué proyecto,
de qué cliente y cuándo.

Lo escribí porque la carga lo necesitaba: el producto sabía borrar registros
pero no los proyectos que una importación había creado con el nombre
equivocado. **El botón en pantalla lo decides tú**, con su confirmación.

---

## Lo que me equivoqué, y te lo debo decir

Al cambiar la lista de actividades de la siembra, el backend recargó y **escribió
tres actividades nuevas en tu base sin que nadie lo pidiera**. Son exactamente
tres de las ocho del objetivo, así que no hizo daño y el resultado final es el
que querías — pero fue una escritura no planeada en tu base, y la regla 33 dice
que eso se cuenta.

La causa: la siembra es idempotente y **añade lo que falte en cada arranque**.
Editar la lista y guardar basta para que ocurra. Queda anotado en `CLAUDE.md`
para que no vuelva a sorprender.

---

## Antes de desplegar

H8 entero está **sin desplegar**, y lleva **dos SQL nuevos** que van en este
orden y después del código:

```
1. docs/sql/h8_estado_proyecto.sql          amplía el CHECK y migra las filas
2. (el código de H8, desplegado)
3. docs/sql/h8_estado_proyecto_cierre.sql   estrecha el CHECK a los cinco
```

**El tercero no se puede aplicar antes que el código nuevo**: rompería la
creación de proyectos. Con los otros dos que ya había pendientes —el de la
Etapa 2 y el token de lectura de O2c—, son **cuatro SQL esperando** en el
servidor.

---

## Una decisión tuya

Los tres Excel llevan **clientes reales y horas de personas con nombre y
apellido**. No los subí al repositorio: subirlos a GitHub, aunque sea privado,
es publicarlos, y eso lo decides tú. Están en `docs/documentos carga/` en tu
disco, con una entrada en `.gitignore` que explica por qué.

Si quieres incluirlos: `git add -f "docs/documentos carga/"`.

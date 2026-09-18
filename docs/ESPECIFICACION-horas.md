# Especificación funcional — Módulo de Horas y Proyectos (Kinetix)

**Versión 1.3 · Aprobada por Fredy Bonilla**

Referencia única del módulo. Todo prompt de desarrollo se valida contra este documento,
no contra mensajes anteriores. Mismo criterio que `ESPECIFICACION-informe.md`.

---

## 0. Términos

- **Registro de horas** — una fila: un usuario, un día, un proyecto, una actividad y unas horas.
- **Cliente** — el mismo cliente que ya usa el módulo de análisis. No hay una lista aparte.
- **Proyecto** — pertenece a un cliente y tiene horas estimadas por actividad.
- **Actividad** — el tipo de trabajo (planeación, diseño, ejecución…). Vive en un catálogo propio.
- **Jornada** — las horas que se esperan de un día laboral: lunes a jueves 8,5 y viernes 8,0.
- **Hora extra** — la que se trabaja por encima de la jornada de ese día.
- **Facturable** — se decide en cada registro, no en el proyecto.

---

## 1. Modelo de datos

| Tabla | Contenido |
|---|---|
| `clients` | **Ya existe.** Se comparte con el módulo de análisis, sin cambios |
| `activities` | Catálogo global: nombre, activa, quién la creó. Es la lista que alimenta a todos los proyectos |
| `projects` | Cliente, nombre, estado (activo/cerrado), quién lo creó, fechas |
| `project_activities` | Horas estimadas de cada actividad dentro de un proyecto |
| `project_activity_changes` | Historial de las estimaciones: valor anterior, nuevo, quién y cuándo |
| `time_entries` | El registro de horas (ver §1.1) |
| `work_calendar` | Jornada por día de la semana, festivos y ausencias por usuario |

### 1.1 El registro de horas

| Campo | Regla |
|---|---|
| `id` | Identificador propio, generado siempre al crear el registro |
| `external_id` | El `Id` del archivo importado, cuando viene de una importación. Único: evita duplicar al subir dos veces el mismo archivo |
| `user_id` | De quién son las horas |
| `created_by` | Quién las registró. Distinto de `user_id` cuando las carga un administrador |
| `date` | El día trabajado |
| `project_id` · `activity_id` | Obligatorios |
| `hours` | Decimal, en pasos de 0,25. Mayor que cero |
| `billable` | Sí o no. Obligatorio |
| `overtime` | Sí o no. Marca la hora extra |
| `notes` | Observaciones. **No obligatorias**, pero siempre asociadas a la actividad |
| `source` | `manual` o `import` |

### 1.2 Actividades iniciales

El catálogo arranca con: **Planeación · Diseño y generación de script · Ejecución ·
Análisis de resultados · Administrativas o gerenciales**.

Desde el módulo de actividades se crean las que hagan falta, y quedan disponibles para
todos los proyectos. Una actividad con horas registradas **no se borra**: se desactiva, y
deja de ofrecerse en los proyectos nuevos sin afectar a lo ya registrado.

---

## 2. Módulos

Cada uno es una pantalla independiente. No se mezclan.

| Módulo | Qué hace |
|---|---|
| **Proyectos** | Crear y editar proyectos, con sus horas estimadas por actividad |
| **Actividades** | El catálogo: crear, renombrar y desactivar |
| **Registro de horas** | Registrar el día a día |
| **Consulta de proyectos** | Ver el consumo de un proyecto: quién y cuánto |
| **Reportes** | Informes por usuario, en HTML y PDF |
| **Importación** | Cargar el archivo de horas |

---

## 3. Proyectos

- **Cualquier usuario puede crear un proyecto.** Es obligatorio: cliente, nombre y las horas
  estimadas de al menos una actividad.
- Las horas estimadas **se pueden ampliar o reducir después**. Cada cambio queda registrado
  con su autor, su fecha y los valores anterior y nuevo.
- Las actividades del proyecto salen del catálogo; se pueden añadir o quitar mientras no
  tengan horas registradas.
- **El nombre del proyecto se puede cambiar** después de crearlo, desde su detalle, con las
  mismas reglas del alta: único por cliente, comparando sin tildes ni mayúsculas.
- **Un proyecto cerrado** no admite registros nuevos, pero se sigue consultando.
- **El listado enseña solo los proyectos activos.** Una casilla «Incluir cerrados» los trae
  cuando hacen falta: lo que se mira todos los días es lo que está en marcha.

---

## 4. Registro de horas

### 4.1 Qué se ve

**Un calendario mensual.** Es la única vista: la vista por semana se retira, no convive con
ella — dos formas de hacer lo mismo confunden.

**El calendario.** Una casilla por día, y cada una dice su estado de un vistazo:

| Estado | Cómo se ve |
|---|---|
| Jornada completa | verde, con las horas registradas |
| Incompleto | ámbar, con las horas que faltan |
| Sin registro | ámbar, señalado como pendiente |
| Festivo | color propio, **con el nombre del festivo** |
| Fin de semana | apagado, no se reclama |
| Día seleccionado | resaltado |

Con navegación por mes, botón **Hoy** y una leyenda que explica los colores. Encima, el
resumen del mes: jornada del mes, horas registradas, horas extra y días pendientes.

**Debajo del calendario, el detalle del día seleccionado**: una tabla con cliente, proyecto,
actividad, horas, si se cobra, observaciones y las acciones de editar y borrar; más el total
del día frente a su jornada, con las horas extra aparte.

**El popup de registro**, que se abre al pulsar un día o el botón de registrar:

- una franja con la jornada de ese día y lo que falta por registrar;
- **la fecha es editable dentro del popup**, por si uno se equivocó de día;
- cliente → proyecto → actividad, encadenados, **con las horas que quedan de esa actividad a
  la vista**;
- las horas, en pasos de 0,25;
- **Facturable / No facturable como dos opciones explícitas**, no un interruptor: hay que
  elegir, no dejarlo como venga;
- una casilla para la hora extra;
- observaciones, opcionales;
- y tres botones: **Guardar**, **Guardar y añadir otra** —un día suele tener varios
  renglones— y Cancelar.

### 4.2 Reglas

1. **Quien registra:** cada usuario las suyas. **El administrador puede registrar por
   cualquiera**, y el registro guarda quién lo hizo.
2. **Todos ven los registros de todos.** Editar, solo los propios; el administrador, todos.
   **Borrar es exclusivo del administrador**, como en el resto de la plataforma.
3. **Sin límite de fecha hacia atrás.** Si a alguien se le olvidó un día, lo registra después.
4. **Horas por encima de lo estimado — el desfase:** se avisa con las horas que quedan en
   esa actividad, **se permite guardar** y el registro queda **marcado en color como
   desfase**. Ni se bloquea ni se pierde el dato.

   **Se dice «desfase», no «exceso».** Un registro se marca *«Desfase +1,0 h»* y un proyecto
   queda *«Desfasado +9,0 h»*. La palabra describe el proyecto —va por encima de lo
   estimado—, no culpa a quien registró las horas.
5. **Horas extra:** se marcan en el propio registro, **consumen las horas estimadas del
   proyecto** y se muestran siempre separadas de las ordinarias. Al filtrar por fecha se ve
   si ese día hubo extras.
6. **Días incompletos:** el módulo lista los días sin registro o por debajo de la jornada,
   indica cuántas horas faltan y **ofrece un enlace que abre ese día** para completarlo. Un
   día con horas extra no cuenta como incompleto.
7. **Festivos y ausencias** no se reclaman como días incompletos.

---

## 5. Consulta de proyectos

- Por proyecto: **quién ha registrado y cuántas horas**, con el consumido frente a lo
  estimado por actividad, las horas restantes y una marca cuando hay desfase.
- **Al ampliar la consulta**, la tabla cambia y muestra **los días** en que se registraron
  esas horas, con su detalle.
- Filtros por cliente, proyecto, usuario y rango de fechas, y una casilla
  **«Incluir proyectos cerrados»**, que por defecto está sin marcar.

### 5.1 Alertas de desfase

El listado de proyectos **avisa antes de que sea tarde**. Cada proyecto muestra una barra con
lo consumido frente a lo estimado y su estado:

| Estado | Cuándo |
|---|---|
| **En ejecución** | por debajo del 90 % de lo estimado |
| **Por agotarse** | del 90 % al 99,9 % |
| **Terminado** | justo el 100 %: se consumió lo estimado, ni una hora más |
| **Desfasado +X h** | por encima del 100 %, con las horas de más |
| **Cerrado** | el proyecto se cerró a mano; manda sobre cualquier estado de consumo |

El consumo se mide contra **todo lo registrado desde que existe el proyecto**, no contra el
periodo que se esté mirando. Un proyecto que lleva dos meses suma los dos: si no, consultar
una semana tranquila lo dejaría «En ejecución» estando desfasado.

Las filas desfasadas quedan resaltadas. Arriba, un aviso dice **cuántos proyectos están
desfasados** y ofrece un filtro para ver solo esos.

Dentro del detalle de un proyecto, **el mismo estado por actividad**: así se ve cuál es la
que se está pasando, no solo que el proyecto va mal.

---

## 6. Importación del archivo de horas

### 6.1 Formato

El archivo tiene una fila por registro, con estas columnas:

`Id · Observaciones · Cliente · Proyecto · Tarea · Tipo de hora · Sub Tipo Hora ·
Extra Hour · Fecha · Tiempo total · Facturable`

| Columna | Destino |
|---|---|
| `Id` | `external_id` |
| `Observaciones` | Observaciones |
| `Cliente` · `Proyecto` · `Tarea` | Cliente, proyecto y actividad |
| `Extra Hour` | Hora extra (Sí/No) |
| `Fecha` · `Tiempo total` | Día y horas |
| `Facturable` | Facturable (Sí/No) |
| `Tipo de hora` · `Sub Tipo Hora` | **Se ignoran** |

### 6.2 Reglas

1. **El archivo puede traer un mes completo o solo unos días.** No se exige que esté completo.
2. **Idempotencia:** una fila cuyo `Id` ya existe **actualiza** el registro en vez de duplicarlo.
3. **Cliente, proyecto o actividad que no existan se crean automáticamente**, comparando
   antes contra los existentes con el nombre normalizado —sin tildes, sin espacios de más y
   sin distinguir mayúsculas— para no duplicar por una diferencia de escritura.
4. **Un proyecto creado por importación nace sin horas estimadas** y queda señalado en la
   vista previa para que se le pongan.
5. **Vista previa obligatoria** antes de confirmar, con: registros nuevos, registros que se
   actualizan, clientes/proyectos/actividades que se van a crear, y **las horas que superan
   lo estimado, resaltadas en color**.
6. La importación es **para el usuario que se elija**; el administrador puede importar por
   cualquiera.
7. Si una fila es inválida (fecha o horas ilegibles), se señala y **no se importa esa fila**;
   el resto sí.

---

## 7. El informe de horas

### 7.1 Un solo informe

**Hay un informe, no tres.** HTML y PDF son el mismo documento con las mismas
secciones y las mismas cifras: cambia el soporte, no el contenido. El CSV no es un
informe: es el detalle de registros para llevárselo a Excel.

- Selección de **una persona, varias o todas**.
- Periodo: un rango libre de fechas.
- Filtros de **cliente**, **proyecto** y **solo facturables**.
- Y una **casilla por sección** para elegir qué entra en el documento.

### 7.2 Las ocho secciones, en este orden

| # | Sección | Qué muestra |
|---|---|---|
| 1 | **Resumen** | Seis indicadores: horas registradas, ordinarias, extra, facturables, porcentaje facturable y días sin registrar |
| 2 | **Ocupación por persona** | Horas registradas frente a la jornada que le tocaba, con su porcentaje |
| 3 | **Facturable frente a no facturable** | En total y por cliente |
| 4 | **Cobertura por cliente** | Reparto de las horas entre clientes |
| 5 | **En qué se fue el tiempo** | Reparto por actividad |
| 6 | **Consumido frente a estimado** | Por proyecto, con horas restantes y el estado de §5.1 |
| 7 | **Mapa del mes** | Una fila por persona, una casilla por día: quién trabajó cuándo, de un vistazo |
| 8 | **Detalle de registros** | La tabla completa del periodo |

**«Días sin registrar» y «Horas día a día» salieron del informe.** Sus datos siguen
calculándose y se siguen viendo donde sirven —el calendario y la pantalla de consulta—, pero
en un informe para leer no aportaban lo que ocupaban.

### 7.3 El HTML

**Interactivo y autocontenido**: estilos y JavaScript embebidos, sin depender de
internet ni de ningún CDN. Se puede guardar, enviar por correo y abrir sin red.

Lleva dentro, funcionando sin servidor:

- botones de **Equipo** y de **cada persona**, que filtran el documento entero;
- filtros de **cliente** y **proyecto**, y casilla de **solo facturables**;
- **búsqueda** en el detalle de registros;
- **tablas ordenables** pulsando su cabecera;
- **Descargar CSV** e **Imprimir**.

### 7.4 El PDF

**Todo en vertical.** La única sección que obligaba a girar la hoja era «Horas día
a día», y ya no está: sin ella no hay nada que girar, así que tampoco hay selector
de orientación.

**El detalle de registros (sección 8) no entra por defecto**: trescientas filas en
papel no se leen. Su casilla lo permite cuando hace falta.

Se respetan las reglas de impresión del resto del producto: solo tablas, medidas
en milímetros y puntos, nada de disposiciones flexibles ni de rejilla.

### 7.5 La vista previa

**Lo que se ve es lo que se descarga.** La previa no maqueta el informe por su
cuenta: en modo HTML enseña el documento real generado por el servidor, y en modo
PDF genera el PDF y lo abre en el visor del navegador. Si la previa se maquetara
aparte, acabaría mintiendo en cuanto una de las dos cambiara.

### 7.6 Formato y archivos

- Cifras en formato español: `8.600` · `0,27%` · `1,1 h`. Fechas en español.
- **La cabecera** lleva el logo a un tamaño que se lea, y debajo el título y el
  periodo, en ese orden de importancia. Usa los colores del propio logo —el azul
  marino y el naranja—; **el resto del informe no cambia de colores**.
- El **logo** va embebido en el documento, no enlazado. Si falta, el informe sale
  con el nombre en texto y sigue funcionando.
- El **CSV** trae solo el detalle de registros del filtro aplicado, con
  encabezados, separador de coma y UTF-8 con marca de orden para que Excel en
  español lo abra bien a la primera.
- Los archivos se llaman `informe-horas-<periodo>-<persona o equipo>.<html|pdf|csv>`,
  en minúsculas y sin tildes.

### 7.7 Cuánto puede tardar

El informe de un mes del equipo —unos 300 registros— se genera en **menos de 5
segundos** en HTML y **menos de 15** en PDF. Pasarse de ahí es un problema que se
mide y se reporta antes de tocar nada.

---

## 8. Permisos

| Acción | Quién |
|---|---|
| Ver registros | Todos |
| Registrar y editar los propios | Cada usuario |
| Registrar y editar los de otros | Administrador |
| Borrar registros | **Solo administrador** |
| Crear proyectos y actividades | Todos |
| Editar horas estimadas | Todos, con historial |
| Cerrar un proyecto | Administrador |

---

## 9. Convenciones de trabajo

Las mismas del módulo de análisis: reportes numerados en `docs/reporte_claude_code/`,
push solo al remoto `github`, archivos protegidos con autorización previa, y validación de
Fredy por etapa completa y probable desde la interfaz.

---

## 10. Fuera de alcance

- Tarifas y facturación en dinero.
- Aprobación de horas por un responsable.
- Cierre de periodo que bloquee la edición hacia atrás.
- Notificaciones por correo.

Quedan anotadas por si se quieren en una versión posterior.

---

## Historial de versiones

| Versión | Cambio |
|---|---|
| 1.0 | Versión inicial del módulo |
| 1.1 | §4.1 pasa a **calendario mensual** con detalle del día y popup de registro; la vista semanal se retira · §4.2.4 dice **«desfase»** en vez de «exceso» · §5.1 añade las **alertas de desfase** en el listado de proyectos |
| 1.2 | §7 reescrito: **un solo informe** en HTML y PDF con diez secciones · filtros y casillas por sección · HTML autocontenido e interactivo · **PDF con orientación mixta** (la sección 9 en horizontal) · la vista previa enseña el documento real · CSV del detalle · nombres de archivo y tiempos máximos |
| 1.3 | §5.1 renombra los estados: **En ejecución · Por agotarse · Terminado · Desfasado · Cerrado**, y deja dicho que el consumo suma desde siempre · §3 añade el cambio de nombre del proyecto y el listado **solo de activos** con su casilla · §5 añade la casilla de proyectos cerrados · §7 pasa a **ocho secciones** —salen «Días sin registrar» y «Horas día a día»—, el **PDF queda todo vertical** sin selector de orientación, y se rediseña la cabecera |

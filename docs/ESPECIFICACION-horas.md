# Especificación funcional — Módulo de Horas y Proyectos (Kinetix)

**Versión 1.0 · Pendiente de aprobación de Fredy Bonilla**

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
- **Un proyecto cerrado** no admite registros nuevos, pero se sigue consultando.

---

## 4. Registro de horas

### 4.1 Qué se ve

Una vista por semana, con el total de cada día frente a la jornada esperada. Cada renglón:
cliente, proyecto, actividad, horas, facturable, extra y observaciones.

### 4.2 Reglas

1. **Quien registra:** cada usuario las suyas. **El administrador puede registrar por
   cualquiera**, y el registro guarda quién lo hizo.
2. **Todos ven los registros de todos.** Editar, solo los propios; el administrador, todos.
   **Borrar es exclusivo del administrador**, como en el resto de la plataforma.
3. **Sin límite de fecha hacia atrás.** Si a alguien se le olvidó un día, lo registra después.
4. **Horas por encima de lo estimado:** se avisa con las horas que quedan en esa actividad,
   **se permite guardar** y el registro queda **marcado en color como exceso**. Ni se
   bloquea ni se pierde el dato.
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
  estimado por actividad, las horas restantes y una marca cuando hay exceso.
- **Al ampliar la consulta**, la tabla cambia y muestra **los días** en que se registraron
  esas horas, con su detalle.
- Filtros por cliente, proyecto, usuario y rango de fechas.

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

## 7. Reportes

### 7.1 Alcance

- Selección de **uno, dos o tres usuarios** (o todos).
- Periodo **diario, semanal o mensual**, o un rango libre.
- Salidas: **HTML** y **PDF**.

### 7.2 Contenido

El informe conserva la estructura del ejemplo aprobado y añade lo que el módulo aporta:

| Sección | Qué muestra |
|---|---|
| Ocupación frente a la capacidad | Horas registradas contra la jornada del periodo, por usuario |
| **Facturable frente a no facturable** | En total y por cliente |
| Cobertura por cliente | Reparto de las horas |
| En qué se fue el tiempo | Reparto por actividad |
| Carga día a día | Con las **horas extra separadas** de las ordinarias |
| **Consumido frente a estimado** | Por proyecto y actividad, con horas restantes y marca de exceso |
| **Días sin registrar o incompletos** | Con las horas que faltan en cada uno |
| Detalle de registros | La tabla completa del periodo |

### 7.3 Formato

- Documento autocontenido, sin depender de internet, igual que el informe de análisis.
- Cifras en formato español: `8.600` · `0,27%` · `1,1 horas`.
- Colores del estándar visual de Kinetix.
- El PDF con las mismas reglas del resto del producto: solo tablas, en milímetros y puntos.

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

## 10. Fuera de alcance de la versión 1.0

- Tarifas y facturación en dinero.
- Aprobación de horas por un responsable.
- Cierre de periodo que bloquee la edición hacia atrás.
- Notificaciones por correo.

Quedan anotadas por si se quieren en una versión posterior.

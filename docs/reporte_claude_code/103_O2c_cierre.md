ce837e9 · 2026-09-22

# ETAPA O2c — la pantalla de servidores, y la recuperación de las suites

**0 llamadas a la IA.** `pg_dump` antes de empezar. Etapas previas: reportes
**99** a **102**.

---

## 0. Lo primero, porque condiciona todo lo demás

**Un `docker compose up -d --build backend` que pedí yo se llevó `/tmp/e2e` por
delante**: cuarenta y tantas suites acumuladas desde H1, las de las Etapas 2 a
6, los relevos de red y la herramienta de sesión.

El comando era necesario —O-D32 pedía `openssh-client` en la imagen— pero el
aviso que tenía que acompañarlo no lo di. `CLAUDE.md` y `PROJECT_STATUS.md`
documentan dónde viven las suites; lo sabía y no lo dije.

**Se recuperaron del respaldo de `C:\proyectos\Kinetix_pruebas\e2e\`**, el mismo
del que ya se repuso en H3 (reporte 81). Estaban **las 12 suites de la
regresión**, las cuatro prioritarias y la infraestructura. No hubo que
reescribir ninguna.

Pero eso fue **suerte, no diseño**: el respaldo era del 21 de septiembre y no
cubría nada de O2a ni O2b. De ahí la **regla 36**.

### 0.1 Lo que el respaldo no tenía

| Qué | Estado |
|---|---|
| 4 suites de paso (`h2b5`, `h33`, `h36`, `h56`) | **perdidas**. Superadas por `h7_pantallas_horas.py`, que cubre lo mismo |
| `cierre_h7.sh`, `cierre_o1.sh` | reconstruidos como `cierre_o2c.sh` |
| 9 herramientas de un rato (`dbg_*`, `ver_portada*`…) | **perdidas**. No protegían nada |
| `zztest_o14.jmx` | **reconstruido** a partir del reporte 97 §3.2 y de lo que la suite espera. Declarado como reconstrucción, no como el original |

### 0.2 Dos secuelas que solo aparecieron al correr la regresión

Ninguna la vi al evaluar el daño: salieron al ejecutar, que es la diferencia
entre suponer y comprobar.

- **Playwright tampoco estaba en `requirements.txt`.** Se instalaba a mano en el
  contenedor y se perdió igual. Reinstalado y anotado en
  `backend/pruebas_e2e/LEEME.md`, porque no tiene por qué viajar a producción
  pero sí tiene que estar escrito en algún sitio.
- **Los relevos `rele_5173.py` y `rele_3000.py` eran procesos de fondo** que
  nadie levantaba. Su ausencia salía como `ERR_CONNECTION_REFUSED`, que **parece
  un fallo de pantalla**. Los levanta ahora `sincronizar.sh`.

Eso llevó la regresión de 13 fallos a 5, y de 5 a 0.

### 0.3 La regla 36

> Ninguna prueba vive solo dentro de un contenedor. Todo script de prueba se
> versiona en **`backend/pruebas_e2e/`**, que se monta en `/app` y sobrevive a
> cualquier reconstrucción. **`/tmp` es borrador.**

Con tres obligaciones: comparar `/tmp/e2e` con el repositorio **antes** de
cualquier `--build`; anotar lo que se instale a mano aunque no vaya en
`requirements.txt`; y que nada que las suites necesiten sea un proceso de fondo
que nadie levante.

---

## 1. La corrección previa: el documento del agente

El §6 de `requisitos-con-agente.md` decía que el agente sale al **8086** hacia
InfluxDB. **Era incorrecto para el caso que importa**, y lo contrario de una
decisión que tomamos a propósito: ese puerto está cerrado (O-D1) y no se va a
abrir para que un agente escriba en él.

Comprobado, no supuesto: `docker port jmeter_influxdb` devuelve
`8086/tcp -> 127.0.0.1:8086`, y el nginx del servidor —según `CLAUDE.md` §14—
solo enruta el frontend y el backend. **No hay punto de entrada para
escrituras.**

La versión 1.1 dice ahora las dos situaciones:

| Su caso | ¿Sirve el modo con agente hoy? |
|---|---|
| Servidor y Kinetix en la misma red | **Sí.** Es lo probado y medido en O2b |
| Servidor del cliente, Kinetix en nuestra infraestructura | **Todavía no.** Falta el punto de entrada HTTPS |

Y describe cómo sería ese punto de entrada —443 hacia `kinetix.sqasa.co`— **sin
prometerlo**: «no está hecho, y hasta que lo esté no cuenta como un
compromiso». Es la primera fila de la tabla que compara los dos modos, porque es
lo que decide.

---

## 2. O2c.1 — el modelo y los endpoints

`observed_servers` (O-D23), creada por `create_all` sin un `ALTER` a mano
(regla 10). CRUD bajo `/observabilidad/servidores`, prueba de conexión y
generador de configuración.

### 2.1 O-D26, comprobado de la forma dura

La credencial entra una vez y **no vuelve a salir**. Eso no se comprueba mirando
el JSON ya interpretado: se busca **el secreto literal en el cuerpo crudo de
cada respuesta** —alta, detalle, lista, tras editar, tras sustituir, en el
resultado de la prueba y en la configuración generada—. Si algún día se colara
dentro de un mensaje de error o de un campo nuevo, salta.

Además, el servidor sale por un solo camino, `_a_lectura()`, que se construye
campo a campo: con `from_attributes` sobre el modelo, **añadir una columna la
publicaría sin que nadie lo decidiera**, y una de esas columnas es la credencial.

Y la regla de la edición: ausente = no se toca; cadena vacía = se borra, que es
una decisión explícita y no un olvido.

### 2.2 La prueba de conexión (O-D24)

Para PostgreSQL es completa desde el primer día: conecta con la credencial
guardada y lee lo que O-D12 promete.

```
Se conecta a la base y se leen sus estadisticas  (26 ms)
  si  conexion: conectado a «tienda» como «kinetix_lector»
  si  pg_stat_database (conexiones y transacciones): 5 filas visibles
  si  pg_stat_activity (estado de las sesiones): 10 filas visibles
  si  pg_locks (bloqueos): 2 filas visibles
  si  pg_stat_statements (consultas lentas): 18 filas visibles
```

Para Linux hacía falta un cliente de SSH, que el backend no tenía. Eso llevó a
O-D32.

---

## 3. O-D32 — el cliente SSH, y los tres casos

`openssh-client` en la imagen del backend. Es un paquete del sistema, no una
dependencia de Python: no toca `requirements.txt` ni el entorno de la
aplicación. Con él, la prueba distingue **los tres casos, con el error real en
cada uno**:

```
CASO 1: credencial correcta   -> Se llega al servidor
   si  el puerto 22 responde: SSH-2.0-OpenSSH_8.9p1 Ubuntu-3ubuntu0.17
   si  la credencial sirve y /proc se lee: sesion abierta como «kinetix_lector»;
       el servidor dice tener 8 nucleos

CASO 2: credencial rechazada  -> Se llega al servidor, pero la credencial no sirve
   error real: kinetix_lector@lab_servidor: Permission denied (publickey).

CASO 3: puerto cerrado        -> No se llega al servidor
   error real: ConnectionRefusedError: [Errno 111] Connection refused
```

El caso 2 no daba el motivo al principio: decía «ssh terminó con código 255».
Era mi `-q`, que silencia justo `Permission denied (publickey)`. Sin ese mensaje
no queda nada útil.

---

## 4. O-D33 y O-D34 — el token de lectura

Un token **de solo lectura** del cubo `infra`, distinto del de escritura, que
sigue siendo de escritura a propósito (O-D2). Comprobado su alcance, no supuesto:

| Prueba | Respuesta |
|---|---|
| Leer `infra` | **200** |
| Escribir en `infra` | **403** |
| Leer el cubo `jmeter` | **404** — ni lo ve |
| Listar tokens | lista vacía |

Con él, la prueba de conexión dice además **cuándo llegó la última métrica**
(O-D34): *«la última, hace 0 segundos. Medidas: cpu, disk, diskio, kernel, mem,
net, procesos_top, processes, swap, system»*.

### 4.1 Una decisión que viene de la Etapa 2

La columna nueva exige `ALTER TABLE` (regla 10), y el SQL se le entrega a Fredy:
`docs/sql/o2c_influxdb_read_token.sql`, idempotente —comprobado sobre la base de
pruebas: la segunda pasada dice `already exists, skipping`—.

**La columna NO se declara en el modelo, y es deliberado.** Si se declarara,
SQLAlchemy la pediría en cada consulta de `monitoring_config` y, entre el
despliegue del código y el momento en que alguien ejecuta el `ALTER`, **la
pantalla de monitoreo entera reventaría**. Es exactamente lo que pasó en la
Etapa 2 con `ai_config.reasoning_effort`, y `CLAUDE.md` lo guarda como aviso.

Se lee y se escribe con SQL tolerante. Comprobado: con la columna ausente,
`token-lectura` responde `columna_aplicada: false` y `/monitoring/config` sigue
devolviendo `200`.

---

## 5. El menú (O-D29 a O-D31)

**«Observabilidad» es una sección propia**, al mismo nivel que Análisis y
Diseño, con «Monitoreo en vivo» —que venía de Análisis— y «Servidores».

**«Metricas Monitoreo» se queda en Análisis** (O-D30), y con su nombre. Son las
capturas de infraestructura que la IA analiza para el informe, no monitoreo en
vivo. **Dicho lo cual: ese nombre se presta a confusión con la sección nueva.**
Un usuario que busque «dónde veo las métricas de mis servidores» va a pinchar
ahí primero. Renombrarlo es otra decisión y no se tomó en esta etapa; queda
anotado aquí, que es lo que pedía O-D30.

**Las rutas antiguas siguen funcionando** (O-D31): `/monitoring/vivo` redirige a
`/observabilidad/vivo`. Comprobado en el navegador, y de paso lo comprueba
`o16_pantalla.py`, que sigue usando la ruta vieja **a propósito**.

---

## 6. La pantalla de servidores

`frontend/src/pages/ServidoresPage.tsx`. Alta, edición, baja, prueba de conexión
y generador de configuración. Formato español, tildes, 44 px en todo lo que se
pulsa, `<label>` en cada campo.

Tres detalles que no son decorativos:

- **El campo de credencial aparece vacío al editar**, y lo dice: «déjalo en
  blanco para no cambiarla». No es que se nos olvide rellenarlo: es que no
  existe forma de leerla.
- **El puerto se propone solo** al cambiar de tipo (22, 5432, 5985), pero **solo
  si el que había era el propuesto del tipo anterior**: si alguien tecleó uno a
  mano, no se le pisa.
- **El aviso de O-D28 va en el diálogo de configuración, en ámbar y arriba**:
  Kinetix genera lo que hay que poner, **no lo ejecuta**. Quien lo aplica es una
  persona con acceso al servidor.

---

## 7. La prueba de punta a punta

`o2c_pantalla.py`: **35 comprobaciones**, el recorrido entero desde el
navegador. Da de alta los dos servidores del laboratorio desde la pantalla,
prueba las conexiones, genera la configuración en los dos modos y comprueba
O-D27.

Lo más importante que hace es buscar **la llave SSH y la contraseña de la base
en el texto de la pantalla entera** y no encontrarlas.

---

## 8. La regresión

```
=== LA BASE DE FREDY, ANTES ===        === LA BASE DE FREDY, DESPUES ===
86f88bf73ffe47f15226188e5c58caaa       86f88bf73ffe47f15226188e5c58caaa
24 10 8 13 5 5                         24 10 8 13 5 5

SI — la base de Fredy no cambio ni una fila
suites: 15 · con fallo: 0    ·    578 comprobaciones
```

**La cifra de esta etapa es 578 en 15 suites.** Y hay que decir qué significa y
qué no:

- **Las 14 suites históricas volvieron a correr** y pasan. La regresión no está
  «perdida»: está recuperada y verde.
- **Lo que no existe hoy** son las 4 suites de paso que el respaldo no tenía
  (`h2b5_pantalla`, `h33_pantalla`, `h36_importacion`, `h56_pantalla`). Cubrían
  pasos intermedios del módulo de horas que `h7_pantallas_horas.py` cubre en su
  forma final. **No se recuperan**: reescribirlas de memoria daría algo que se
  les parece.
- **Esto no da por validada ninguna etapa anterior.** H5, H6, H7, O1, O2a y O2b
  siguen **pendientes de la validación de Fredy**, que es el único criterio de
  éxito (regla 9). Una regresión verde dice que no se rompió nada; no dice que
  lo que hay esté bien.

### 8.1 Una suite que hubo que cambiar, y por qué

`o16_pantalla.py` falló al mover el menú: comprobaba que «Monitoreo en vivo»
estuviera bajo «Análisis». **Falló con razón** —el producto cambió— y el que
estaba desfasado era el script. Se actualizó a la ubicación nueva, con el
comentario que lo explica. Misma lección que cuando se acentuaron los títulos y
hubo que tocar `hf4_check.py`.

---

## 9. Lo que no se ha comprobado (regla 33)

- **Fredy no ha validado nada**: ni O2c, ni O2b, ni O2a, ni O1, ni H5, H6 o H7.
- **Windows sigue sin poder probarse** desde la pantalla: el tipo existe y la
  prueba devuelve un mensaje que lo dice con esas palabras. Haría falta WinRM.
- **La prueba de conexión no valida la credencial de un Windows ni de un
  servidor «otro»**, solo Linux y PostgreSQL.
- **El punto de entrada HTTPS sigue sin existir** (§1). Mientras tanto, el modo
  con agente solo sirve en red compartida.
- **Las 4 suites de paso no se recuperan** (§8).
- **`zztest_o14.jmx` es una reconstrucción**, no el original.
- **No se tocó el servidor de Azure**, ni `services/engine/`, ni ningún archivo
  protegido.
- Los datos de las corridas `zztest-` siguen en los dos cubos, a propósito.

---

## 10. Estado

**Etapa O2c implementada, pendiente de validación de Fredy.**
